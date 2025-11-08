import argparse
import sys
import requests
import json
from typing import Dict, Any, List, Optional, Set
from collections import deque
import os

class DependencyVisualizer:
    def __init__(self):
        self.config = {}
        self.dependency_graph = {}
        self.visited_packages = set()
        
    def parse_arguments(self) -> Dict[str, Any]:
        parser = argparse.ArgumentParser(
            description='Инструмент визуализации графа зависимостей пакетов',
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        
        parser.add_argument(
            '--package',
            type=str,
            required=True,
            help='Имя анализируемого пакета'
        )

        repo_group = parser.add_mutually_exclusive_group(required=True)
        repo_group.add_argument(
            '--repo-url',
            type=str,
            help='URL-адрес репозитория'
        )
        repo_group.add_argument(
            '--repo-path',
            type=str,
            help='Путь к файлу тестового репозитория'
        )
        
        parser.add_argument(
            '--test-repo',
            action='store_true',
            help='Режим работы с тестовым репозиторием'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            default='dependency_graph.png',
            help='Имя сгенерированного файла с изображением графа (по умолчанию: dependency_graph.png)'
        )
        
        parser.add_argument(
            '--ascii-tree',
            action='store_true',
            help='Режим вывода зависимостей в формате ASCII-дерева'
        )
        
        parser.add_argument(
            '--max-depth',
            type=int,
            default=10,
            help='Максимальная глубина анализа зависимостей (по умолчанию: 10)'
        )
        
        parser.add_argument(
            '--filter',
            type=str,
            help='Подстрока для фильтрации пакетов'
        )
        
        return vars(parser.parse_args())
    
    def validate_arguments(self, args: Dict[str, Any]) -> None:
        if not args['package'] or not args['package'].strip():
            raise ValueError("Имя пакета не может быть пустым")
    
        if args['repo_url']:
            if not args['repo_url'].startswith(('http://', 'https://')):
                raise ValueError("URL репозитория должен начинаться с http:// или https://")
        
        if args['repo_path']:
            if not args['repo_path'].endswith(('.json', '.txt', '.yaml', '.yml')):
                print("Предупреждение: нестандартное расширение файла репозитория", file=sys.stderr)
        
        if args['max_depth'] <= 0:
            raise ValueError("Максимальная глубина должна быть положительным числом")
        
        if args['max_depth'] > 100:
            print("Предупреждение: установлена очень большая глубина анализа", file=sys.stderr)
        
        if not args['output']:
            raise ValueError("Имя выходного файла не может быть пустым")
        
        valid_extensions = ['.png', '.jpg', '.jpeg', '.svg', '.pdf']
        if not any(args['output'].lower().endswith(ext) for ext in valid_extensions):
            print("Предупреждение: рекомендуется использовать стандартные расширения изображений", file=sys.stderr)
    
    def display_configuration(self, config: Dict[str, Any]) -> None:
        print("Конфигурация приложения:")
        print("-" * 40)
        
        for key, value in config.items():
            if value is not None:
                print(f"{key:15}: {value}")
        
        print("-" * 40)
    
    def get_cargo_toml_from_github(self, repo_url: str, package_name: str) -> Optional[str]:
        """Получает содержимое Cargo.toml из GitHub репозитория"""
        try:
            # Преобразуем URL GitHub в raw content URL
            if 'github.com' in repo_url:
                # Убираем возможные суффиксы .git
                repo_url = repo_url.replace('.git', '')
                # Формируем URL для raw content
                raw_url = repo_url.replace('github.com', 'raw.githubusercontent.com')
                
                # Пробуем разные возможные пути к Cargo.toml
                possible_paths = [
                    '/main/Cargo.toml',
                    '/master/Cargo.toml', 
                    '/Cargo.toml',  # для корневого расположения
                ]
                
                for path in possible_paths:
                    test_url = raw_url + path
                    print(f"Попытка получить Cargo.toml из: {test_url}")
                    try:
                        response = requests.get(test_url, timeout=10)
                        if response.status_code == 200:
                            return response.text
                    except requests.exceptions.RequestException:
                        continue
                
                # Если стандартные пути не сработали, пробуем через GitHub API
                print("Попытка получить информацию через GitHub API...")
                api_url = repo_url.replace('https://github.com/', 'https://api.github.com/repos/')
                api_response = requests.get(api_url, timeout=10)
                if api_response.status_code == 200:
                    repo_info = api_response.json()
                    default_branch = repo_info.get('default_branch', 'main')
                    # Пробуем с правильной веткой
                    final_url = f"{raw_url}/{default_branch}/Cargo.toml"
                    print(f"Попытка получить Cargo.toml из: {final_url}")
                    response = requests.get(final_url, timeout=10)
                    if response.status_code == 200:
                        return response.text
                        
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при получении Cargo.toml: {e}", file=sys.stderr)
        
        return None
    
    def parse_cargo_toml_dependencies(self, cargo_toml_content: str) -> List[str]:
        """Парсит зависимости из содержимого Cargo.toml"""
        dependencies = []
        
        try:
            lines = cargo_toml_content.split('\n')
            in_dependencies_section = False
            
            for line in lines:
                line = line.strip()
                
                # Пропускаем комментарии и пустые строки
                if not line or line.startswith('#'):
                    continue
                
                # Начало секции зависимостей
                if line == '[dependencies]':
                    in_dependencies_section = True
                    continue
                # Конец секции зависимостей (начало другой секции)
                elif line.startswith('[') and in_dependencies_section:
                    break
                
                # Парсим зависимости в секции
                if in_dependencies_section and '=' in line:
                    # Извлекаем имя пакета до знака равенства
                    package_name = line.split('=')[0].strip()
                    # Убираем кавычки если есть
                    package_name = package_name.strip('"\'')
                    
                    if package_name and not package_name.startswith('#'):
                        dependencies.append(package_name)
            
        except Exception as e:
            print(f"Ошибка при парсинге Cargo.toml: {e}", file=sys.stderr)
        
        return dependencies
    
    def get_dependencies_from_crates_io(self, package_name: str) -> List[str]:
        """Получает зависимости пакета из crates.io API"""
        try:
            url = f"https://crates.io/api/v1/crates/{package_name}"
            print(f"Запрос информации о пакете {package_name} из crates.io...")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            dependencies = []
            
            # Получаем последнюю версию пакета
            if 'crate' in data and 'max_version' in data['crate']:
                version = data['crate']['max_version']
                
                # Запрашиваем информацию о конкретной версии
                version_url = f"https://crates.io/api/v1/crates/{package_name}/{version}/dependencies"
                version_response = requests.get(version_url, timeout=10)
                version_response.raise_for_status()
                
                version_data = version_response.json()
                
                if 'dependencies' in version_data:
                    for dep in version_data['dependencies']:
                        dep_name = dep.get('crate_id', '')
                        if dep_name:
                            dependencies.append(dep_name)
            
            return dependencies
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к crates.io: {e}", file=sys.stderr)
            return []
        except json.JSONDecodeError as e:
            print(f"Ошибка при разборе JSON от crates.io: {e}", file=sys.stderr)
            return []
    
    def get_direct_dependencies(self, package_name: str, repo_url: str = None, repo_path: str = None) -> List[str]:
        """Получает прямые зависимости пакета"""
        dependencies = []
        
        if repo_url:
            # Пытаемся получить зависимости из репозитория GitHub
            cargo_toml_content = self.get_cargo_toml_from_github(repo_url, package_name)
            if cargo_toml_content:
                dependencies = self.parse_cargo_toml_dependencies(cargo_toml_content)
        
        # Если не удалось получить из репозитория, используем crates.io API
        if not dependencies:
            print("Попытка получить зависимости из crates.io...")
            dependencies = self.get_dependencies_from_crates_io(package_name)
        
        return dependencies

    def load_test_repository(self, repo_path: str) -> Dict[str, List[str]]:
        """Загружает тестовый репозиторий из файла"""
        try:
            with open(repo_path, 'r') as f:
                if repo_path.endswith('.json'):
                    return json.load(f)
                else:
                    # Простой текстовый формат: каждая строка "ПАКЕТ: ЗАВИСИМОСТИ"
                    graph = {}
                    for line in f:
                        line = line.strip()
                        if line and ':' in line:
                            package, deps_str = line.split(':', 1)
                            package = package.strip()
                            dependencies = [dep.strip() for dep in deps_str.split(',') if dep.strip()]
                            graph[package] = dependencies
                    return graph
        except Exception as e:
            print(f"Ошибка при загрузке тестового репозитория: {e}", file=sys.stderr)
            return {}

    def build_dependency_graph_bfs(self, start_package: str, max_depth: int, filter_str: str = None, 
                             repo_url: str = None, repo_path: str = None, test_repo: bool = False) -> Dict[str, List[str]]:
        """Строит граф зависимостей с помощью BFS"""
        graph = {}
        visited = set()
        queue = deque()
        
        # Начинаем с корневого пакета
        queue.append((start_package, 0))
        visited.add(start_package)
        
        while queue:
            current_package, depth = queue.popleft()
            
            print(f"Анализ пакета: {current_package} (глубина: {depth})")
            
            # Получаем зависимости текущего пакета
            if test_repo and repo_path:
                test_graph = self.load_test_repository(repo_path)
                dependencies = test_graph.get(current_package, [])
            else:
                dependencies = self.get_direct_dependencies(current_package, repo_url, repo_path)
            
            # Применяем фильтр если задан
            if filter_str:
                dependencies = [dep for dep in dependencies if filter_str not in dep]
            
            graph[current_package] = dependencies
            
            # Добавляем зависимости в очередь только если не достигли максимальной глубины
            # ИСПРАВЛЕНО: depth < max_depth вместо depth < max_depth - 1
            if depth < max_depth:
                for dep in dependencies:
                    if dep not in visited:
                        visited.add(dep)
                        queue.append((dep, depth + 1))
        
        return graph

    def detect_cycles(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """Обнаруживает циклические зависимости в графе"""
        cycles = []
        visited = set()
        recursion_stack = set()
        path = []
        
        def dfs(node):
            if node in recursion_stack:
                # Найден цикл
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                if cycle not in cycles:
                    cycles.append(cycle.copy())
                return
            
            if node in visited:
                return
            
            visited.add(node)
            recursion_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if neighbor in graph:  # Проверяем только пакеты, которые есть в графе
                    dfs(neighbor)
            
            path.pop()
            recursion_stack.remove(node)
        
        for node in graph:
            if node not in visited:
                dfs(node)
        
        return cycles

    def display_dependency_tree_ascii(self, graph: Dict[str, List[str]], start_package: str) -> None:
        """Выводит дерево зависимостей в ASCII формате"""
        print(f"\nДерево зависимостей для пакета '{start_package}':")
        print("=" * 60)
        
        def print_tree(package, prefix="", is_last=True):
            connector = "└── " if is_last else "├── "
            print(prefix + connector + package)
            
            if package in graph:
                dependencies = graph[package]
                new_prefix = prefix + ("    " if is_last else "│   ")
                
                for i, dep in enumerate(dependencies):
                    is_last_dep = i == len(dependencies) - 1
                    print_tree(dep, new_prefix, is_last_dep)
        
        print_tree(start_package)

    def display_dependencies(self, package_name: str, dependencies: List[str]) -> None:
        """Выводит зависимости в читаемом формате"""
        print(f"\nПрямые зависимости пакета '{package_name}':")
        print("=" * 50)
        
        if not dependencies:
            print("Зависимости не найдены или пакет не имеет зависимостей")
            return
        
        for i, dep in enumerate(dependencies, 1):
            print(f"{i:2}. {dep}")
        
        print(f"\nВсего найдено зависимостей: {len(dependencies)}")

    def display_graph_statistics(self, graph: Dict[str, List[str]], cycles: List[List[str]]) -> None:
        """Выводит статистику по графу зависимостей"""
        print(f"\nСтатистика графа зависимостей:")
        print("=" * 40)
        print(f"Всего пакетов: {len(graph)}")
        
        total_dependencies = sum(len(deps) for deps in graph.values())
        print(f"Всего зависимостей: {total_dependencies}")
        
        if cycles:
            print(f"Обнаружено циклических зависимостей: {len(cycles)}")
            for i, cycle in enumerate(cycles, 1):
                print(f"  Цикл {i}: {' -> '.join(cycle)} -> {cycle[0]}")
        else:
            print("Циклические зависимости не обнаружены")

    def run(self) -> None:
        try:
            args = self.parse_arguments()
            self.validate_arguments(args)
            self.config = args
            self.display_configuration(args)
            
            print("\nСбор данных о зависимостях...")
            
            # Строим полный граф зависимостей с помощью BFS
            dependency_graph = self.build_dependency_graph_bfs(
                start_package=args['package'],
                max_depth=args['max_depth'],
                filter_str=args.get('filter'),
                repo_url=args.get('repo_url'),
                repo_path=args.get('repo_path'),
                test_repo=args.get('test_repo', False)
            )
            
            # Обнаруживаем циклические зависимости
            cycles = self.detect_cycles(dependency_graph)
            
            # Выводим статистику графа
            self.display_graph_statistics(dependency_graph, cycles)
            
            # Выводим дерево зависимостей если запрошено
            if args.get('ascii_tree'):
                self.display_dependency_tree_ascii(dependency_graph, args['package'])
            else:
                # Или просто показываем прямые зависимости корневого пакета
                root_dependencies = dependency_graph.get(args['package'], [])
                self.display_dependencies(args['package'], root_dependencies)
            
            print("\nАнализ зависимостей завершен")
            
        except argparse.ArgumentError as e:
            print(f"Ошибка в аргументах командной строки: {e}", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"Ошибка валидации параметров: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Неожиданная ошибка: {e}", file=sys.stderr)
            sys.exit(1)

def create_test_repository_files():
    """Создает тестовые файлы репозиториев для демонстрации"""
    
    # Тестовый репозиторий 1: Простой случай без циклов
    simple_repo = {
        "A": ["B", "C"],
        "B": ["D", "E"],
        "C": ["F"],
        "D": [],
        "E": ["F"],
        "F": []
    }
    
    with open('test_simple.json', 'w') as f:
        json.dump(simple_repo, f, indent=2)
    
    # Тестовый репозиторий 2: С циклическими зависимостями
    cyclic_repo = {
        "A": ["B"],
        "B": ["C"],
        "C": ["A", "D"],  # Цикл A->B->C->A
        "D": ["E"],
        "E": ["C"]  # Цикл C->D->E->C
    }
    
    with open('test_cyclic.json', 'w') as f:
        json.dump(cyclic_repo, f, indent=2)
    
    # Тестовый репозиторий 3: Текстовый формат
    with open('test_text.txt', 'w') as f:
        f.write("X: Y, Z\n")
        f.write("Y: P, Q\n")
        f.write("Z: R\n")
        f.write("P: \n")
        f.write("Q: R\n")
        f.write("R: \n")
    
    print("Созданы тестовые файлы репозиториев:")
    print("  test_simple.json - простой граф без циклов")
    print("  test_cyclic.json - граф с циклическими зависимостями")
    print("  test_text.txt - текстовый формат графа")

def main():
    # Создаем тестовые файлы при первом запуске
    if not os.path.exists('test_simple.json'):
        create_test_repository_files()
    
    visualizer = DependencyVisualizer()
    visualizer.run()

if __name__ == "__main__":
    main()