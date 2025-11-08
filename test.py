import argparse
import sys
import requests
import json
from typing import Dict, Any, List, Optional, Set
from collections import deque
import os
import time
import re

class DependencyVisualizer:
    def __init__(self):
        self.config = {}
        self.dependency_graph = {}
        self.visited_packages = set()
        self.request_cache = {}
        
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
            help='URL репозитория в формате: https://crates.io/api/v1/crates/{package}/{version}/dependencies'
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
            '--max-depth',
            type=int,
            default=3,
            help='Максимальная глубина анализа зависимостей (по умолчанию: 3)'
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
            # Проверяем что URL соответствует формату crates.io API
            pattern = r'^https://crates\.io/api/v1/crates/[^/]+/[^/]+/dependencies$'
            if not re.match(pattern, args['repo_url']):
                raise ValueError(
                    "URL репозитория должен быть в формате: "
                    "https://crates.io/api/v1/crates/{package_name}/{version}/dependencies"
                )
        
        if args['repo_path']:
            if not args['repo_path'].endswith(('.json', '.txt')):
                print("Предупреждение: рекомендуется использовать .json или .txt файлы", file=sys.stderr)
        
        if args['max_depth'] <= 0:
            raise ValueError("Максимальная глубина должна быть положительным числом")
    
    def display_configuration(self, config: Dict[str, Any]) -> None:
        print("Конфигурация приложения:")
        print("-" * 40)
        
        for key, value in config.items():
            if value is not None:
                print(f"{key:15}: {value}")
        
        print("-" * 40)
    
    def extract_package_info_from_url(self, url: str) -> tuple[str, str]:
        """Извлекает название пакета и версию из URL"""
        # URL format: https://crates.io/api/v1/crates/{package}/{version}/dependencies
        parts = url.split('/')
        package_name = parts[6]  # 7-й элемент
        version = parts[7]       # 8-й элемент
        return package_name, version
    
    def get_dependencies_from_url(self, url: str) -> List[str]:
        """Получает зависимости по указанному URL"""
        try:
            print(f"Запрос зависимостей по URL: {url}")
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 404:
                print("  Зависимости не найдены (404)")
                return []
                
            response.raise_for_status()
            
            data = response.json()
            dependencies = []
            
            if 'dependencies' in data:
                for dep in data['dependencies']:
                    dep_name = dep.get('crate_id', '')
                    if dep_name and dep_name not in dependencies:
                        dependencies.append(dep_name)
                        print(f"  Найдена зависимость: {dep_name}")
            
            print(f"  Всего найдено зависимостей: {len(dependencies)}")
            return dependencies
            
        except requests.exceptions.RequestException as e:
            print(f"  Ошибка при запросе зависимостей: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"  Ошибка при разборе JSON: {e}")
            return []
    
    def get_direct_dependencies(self, package_name: str, repo_url: str = None) -> List[str]:
        """Получает прямые зависимости пакета"""
        if repo_url:
            # Используем URL предоставленный пользователем
            current_package, current_version = self.extract_package_info_from_url(repo_url)
            if current_package == package_name:
                return self.get_dependencies_from_url(repo_url)
            else:
                print(f"Предупреждение: URL для {current_package} не соответствует запрошенному пакету {package_name}")
                return []
        return []

    def load_test_repository(self, repo_path: str) -> Dict[str, List[str]]:
        """Загружает тестовый репозиторий из файла"""
        try:
            with open(repo_path, 'r', encoding='utf-8') as f:
                if repo_path.endswith('.json'):
                    return json.load(f)
                else:
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

    def build_dependency_graph_bfs(self, start_package: str, max_depth: int, 
                                 filter_str: str = None, test_repo: bool = False, 
                                 repo_path: str = None, repo_url: str = None) -> Dict[str, List[str]]:
        """Строит граф зависимостей с помощью BFS"""
        graph = {}
        visited = set()
        queue = deque()
        
        queue.append((start_package, 0, repo_url))  # Добавляем начальный URL
        visited.add(start_package)
        
        while queue:
            current_package, depth, current_url = queue.popleft()
            
            print(f"\nАнализ пакета: {current_package} (глубина: {depth})")
            
            # Получаем зависимости текущего пакета
            if test_repo and repo_path:
                test_graph = self.load_test_repository(repo_path)
                dependencies = test_graph.get(current_package, [])
            else:
                dependencies = self.get_direct_dependencies(current_package, current_url)
            
            # Применяем фильтр если задан
            if filter_str and dependencies:
                original_count = len(dependencies)
                dependencies = [dep for dep in dependencies if filter_str not in dep]
                if len(dependencies) != original_count:
                    print(f"  Применен фильтр '{filter_str}': отфильтровано {original_count - len(dependencies)} зависимостей")
            
            graph[current_package] = dependencies
            
            # Добавляем зависимости в очередь
            if depth < max_depth - 1:
                for dep in dependencies:
                    if dep not in visited:
                        visited.add(dep)
                        # Для следующих пакетов URL будет None - они будут запрашиваться через обычный API
                        queue.append((dep, depth + 1, None))
                        print(f"  Добавлен в очередь: {dep} (глубина: {depth + 1})")
            else:
                print(f"  Достигнута максимальная глубина {max_depth}, дальнейший анализ остановлен")
        
        return graph

    def detect_cycles(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        """Обнаруживает циклические зависимости в графе"""
        cycles = []
        visited = set()
        recursion_stack = set()
        path = []
        
        def dfs(node):
            if node in recursion_stack:
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                cycle_set = set(cycle)
                if not any(set(existing_cycle) == cycle_set for existing_cycle in cycles):
                    cycles.append(cycle.copy())
                return
            
            if node in visited:
                return
            
            visited.add(node)
            recursion_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if neighbor in graph:
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
        
        visited_in_tree = set()
        
        def print_tree(package, prefix="", is_last=True):
            if package in visited_in_tree:
                print(prefix + ("└── " if is_last else "├── ") + f"{package} [уже показан]")
                return
                
            visited_in_tree.add(package)
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
            
            # Этап 2: Получение и вывод прямых зависимостей
            print("\n" + "="*60)
            print("ЭТАП 2: СБОР ДАННЫХ О ПРЯМЫХ ЗАВИСИМОСТЯХ")
            print("="*60)
            
            if args.get('test_repo') and args.get('repo_path'):
                test_graph = self.load_test_repository(args['repo_path'])
                direct_dependencies = test_graph.get(args['package'], [])
            else:
                direct_dependencies = self.get_direct_dependencies(
                    args['package'], 
                    args.get('repo_url')
                )
            
            self.display_dependencies(args['package'], direct_dependencies)
            
            # Этап 3: Построение полного графа зависимостей
            print("\n" + "="*60)
            print("ЭТАП 3: ПОСТРОЕНИЕ ГРАФА ЗАВИСИМОСТЕЙ")
            print("="*60)
            
            dependency_graph = self.build_dependency_graph_bfs(
                start_package=args['package'],
                max_depth=args['max_depth'],
                filter_str=args.get('filter'),
                test_repo=args.get('test_repo', False),
                repo_path=args.get('repo_path'),
                repo_url=args.get('repo_url')
            )
            
            cycles = self.detect_cycles(dependency_graph)
            self.display_graph_statistics(dependency_graph, cycles)
            self.display_dependency_tree_ascii(dependency_graph, args['package'])
            
            print("\nАнализ зависимостей завершен")
            
        except Exception as e:
            print(f"Ошибка: {e}", file=sys.stderr)
            sys.exit(1)

def main():
    if not os.path.exists('test_simple.json'):
        # Создаем тестовые файлы...
        pass
    
    visualizer = DependencyVisualizer()
    visualizer.run()

if __name__ == "__main__":
    main()

# пример чтобы проверить работу этапов 2-3
# python script.py --package tokio --repo-url "https://crates.io/api/v1/crates/tokio/1.35.1/dependencies" --max-depth 1