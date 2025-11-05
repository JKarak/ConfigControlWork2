import argparse
import sys
import requests
import json
from typing import Dict, Any, List, Optional

class DependencyVisualizer:
    def __init__(self):
        self.config = {}
        
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
    
    def run(self) -> None:
        try:
            args = self.parse_arguments()
            self.validate_arguments(args)
            self.config = args
            self.display_configuration(args)
            
            print("\nСбор данных о зависимостях...")
            
            # Получаем прямые зависимости
            dependencies = self.get_direct_dependencies(
                package_name=args['package'],
                repo_url=args.get('repo_url'),
                repo_path=args.get('repo_path')
            )
            
            # Выводим зависимости (требование этапа 2)
            self.display_dependencies(args['package'], dependencies)
            
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

def main():
    visualizer = DependencyVisualizer()
    visualizer.run()

if __name__ == "__main__":
    main()