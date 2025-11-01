import argparse
import sys
from typing import Dict, Any

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
    
    def run(self) -> None:
        try:
            args = self.parse_arguments()
            self.validate_arguments(args)
            self.config = args
            self.display_configuration(args)
            print("\nЗависимости будут проанализированы с указанными параметрами")
            print("(Основная логика анализа будет реализована на следующих этапах)")
            
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