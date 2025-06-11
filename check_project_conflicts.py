#!/usr/bin/env python3
"""
Полный анализатор структуры проекта DailycheckBot2025
Проверяет конфликты, дубликаты и дает рекомендации по оптимизации
"""

import os
import re
import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, Counter
from datetime import datetime

class Colors:
    """ANSI цвета для красивого вывода"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class ProjectAnalyzer:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.results = {
            'folders': {},
            'functions': {},
            'classes': {},
            'imports': {},
            'conflicts': [],
            'recommendations': [],
            'file_stats': {}
        }
        
    def print_header(self, text: str, color: str = Colors.CYAN, char: str = "="):
        """Красивый заголовок"""
        print(f"\n{color}{Colors.BOLD}{char * 60}{Colors.END}")
        print(f"{color}{Colors.BOLD}{text.center(60)}{Colors.END}")
        print(f"{color}{Colors.BOLD}{char * 60}{Colors.END}")
        
    def print_section(self, text: str, color: str = Colors.BLUE):
        """Заголовок секции"""
        print(f"\n{color}{Colors.BOLD}🔍 {text}{Colors.END}")
        print(f"{color}{'-' * (len(text) + 4)}{Colors.END}")

    def analyze_folder_structure(self):
        """Анализ структуры папок"""
        self.print_section("АНАЛИЗ СТРУКТУРЫ ПАПОК", Colors.BLUE)
        
        # Ожидаемые папки для DailycheckBot2025
        expected_folders = {
            'handlers': 'Обработчики команд и коллбеков',
            'services': 'Бизнес-логика (TaskService, AIService)',
            'ui': 'Пользовательский интерфейс (клавиатуры, темы)',
            'models': 'Модели данных',
            'database': 'Управление базой данных',
            'data': 'Пользовательские данные',
            'dashboard': 'Веб-дашборд',
            'bot': 'Инициализация бота',
            'localization': 'Переводы и локализация',
            'scripts': 'Скрипты автоматизации'
        }
        
        # Потенциально конфликтующие папки
        conflicting_folders = {
            'utils': 'Может конфликтовать с handlers/utils.py',
            'shared': 'Может дублировать handlers/states.py',
            'helpers': 'Слишком общее название',
            'lib': 'Неспецифичное название'
        }
        
        # Временные/ненужные папки
        temp_folders = {
            'temp', 'tmp', 'old', 'backup', 'deprecated', 
            '__pycache__', '.pytest_cache', 'test_temp'
        }
        
        existing_folders = []
        for item in self.project_root.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                existing_folders.append(item.name)
        
        print(f"{Colors.GREEN}✅ Найденные папки:{Colors.END}")
        for folder in sorted(existing_folders):
            folder_path = self.project_root / folder
            py_files = list(folder_path.rglob("*.py"))
            size_mb = sum(f.stat().st_size for f in folder_path.rglob("*") if f.is_file()) / 1024 / 1024
            
            # Классификация папки
            status = ""
            if folder in expected_folders:
                status = f"{Colors.GREEN}(необходимая){Colors.END}"
                description = expected_folders[folder]
            elif folder in conflicting_folders:
                status = f"{Colors.YELLOW}(проверить){Colors.END}"
                description = conflicting_folders[folder]
            elif folder in temp_folders:
                status = f"{Colors.RED}(удалить){Colors.END}"
                description = "Временная папка"
            else:
                status = f"{Colors.CYAN}(дополнительная){Colors.END}"
                description = "Неизвестное назначение"
            
            print(f"  📁 {folder:<15} {status:<20} | {len(py_files):>3} файлов | {size_mb:>5.1f} MB")
            print(f"     {Colors.WHITE}{description}{Colors.END}")
            
            self.results['folders'][folder] = {
                'path': str(folder_path),
                'py_files_count': len(py_files),
                'size_mb': size_mb,
                'status': status,
                'description': description
            }
        
        # Отсутствующие важные папки
        missing = [f for f in expected_folders if f not in existing_folders]
        if missing:
            print(f"\n{Colors.YELLOW}⚠️  Отсутствующие важные папки:{Colors.END}")
            for folder in missing:
                print(f"  📁 {folder} - {expected_folders[folder]}")

    def extract_python_elements(self, file_path: Path) -> Dict:
        """Извлечение функций, классов и импортов из Python файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            functions = []
            classes = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'is_async': isinstance(node, ast.AsyncFunctionDef)
                    })
                
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        'name': node.name,
                        'line': node.lineno,
                        'bases': [ast.unparse(base) if hasattr(ast, 'unparse') else str(base) for base in node.bases]
                    })
                
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({
                            'type': 'import',
                            'module': alias.name,
                            'alias': alias.asname,
                            'line': node.lineno
                        })
                
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.append({
                            'type': 'from_import',
                            'module': node.module,
                            'name': alias.name,
                            'alias': alias.asname,
                            'line': node.lineno
                        })
            
            return {
                'functions': functions,
                'classes': classes,
                'imports': imports,
                'lines': len(content.splitlines()),
                'size': file_path.stat().st_size
            }
            
        except Exception as e:
            return {
                'functions': [],
                'classes': [],
                'imports': [],
                'lines': 0,
                'size': 0,
                'error': str(e)
            }

    def analyze_code_elements(self):
        """Анализ функций, классов и импортов"""
        self.print_section("АНАЛИЗ КОДА", Colors.MAGENTA)
        
        all_functions = defaultdict(list)
        all_classes = defaultdict(list)
        all_imports = defaultdict(list)
        
        total_files = 0
        total_lines = 0
        
        for py_file in self.project_root.rglob("*.py"):
            if any(part.startswith('.') or part == '__pycache__' for part in py_file.parts):
                continue
                
            total_files += 1
            relative_path = py_file.relative_to(self.project_root)
            folder = relative_path.parts[0] if len(relative_path.parts) > 1 else 'root'
            
            elements = self.extract_python_elements(py_file)
            total_lines += elements['lines']
            
            # Собираем функции
            for func in elements['functions']:
                all_functions[func['name']].append({
                    'file': str(relative_path),
                    'folder': folder,
                    'line': func['line'],
                    'args': func['args'],
                    'is_async': func['is_async']
                })
            
            # Собираем классы
            for cls in elements['classes']:
                all_classes[cls['name']].append({
                    'file': str(relative_path),
                    'folder': folder,
                    'line': cls['line'],
                    'bases': cls['bases']
                })
            
            # Собираем импорты
            for imp in elements['imports']:
                all_imports[folder].append(imp)
        
        print(f"{Colors.GREEN}📊 Общая статистика:{Colors.END}")
        print(f"  • Файлов Python: {total_files}")
        print(f"  • Строк кода: {total_lines:,}")
        print(f"  • Уникальных функций: {len(all_functions)}")
        print(f"  • Уникальных классов: {len(all_classes)}")
        
        self.results['functions'] = dict(all_functions)
        self.results['classes'] = dict(all_classes)
        self.results['imports'] = dict(all_imports)
        
        return all_functions, all_classes

    def find_conflicts(self, all_functions: Dict, all_classes: Dict):
        """Поиск конфликтов и дубликатов"""
        self.print_section("ПОИСК КОНФЛИКТОВ", Colors.RED)
        
        conflicts = []
        
        # Дубликаты функций
        function_duplicates = {name: locations for name, locations in all_functions.items() 
                             if len(locations) > 1}
        
        if function_duplicates:
            print(f"{Colors.RED}⚠️  ДУБЛИКАТЫ ФУНКЦИЙ:{Colors.END}")
            for func_name, locations in function_duplicates.items():
                print(f"\n  📝 {Colors.YELLOW}{func_name}{Colors.END}:")
                for loc in locations:
                    args_str = f"({', '.join(loc['args'])})" if loc['args'] else "()"
                    async_mark = "async " if loc['is_async'] else ""
                    print(f"    • {loc['folder']}/{loc['file']}:{loc['line']} - {async_mark}{func_name}{args_str}")
                
                conflicts.append({
                    'type': 'function_duplicate',
                    'name': func_name,
                    'locations': locations
                })
        else:
            print(f"{Colors.GREEN}✅ Дубликатов функций не найдено{Colors.END}")
        
        # Дубликаты классов
        class_duplicates = {name: locations for name, locations in all_classes.items() 
                           if len(locations) > 1}
        
        if class_duplicates:
            print(f"\n{Colors.RED}⚠️  ДУБЛИКАТЫ КЛАССОВ:{Colors.END}")
            for class_name, locations in class_duplicates.items():
                print(f"\n  🏗️  {Colors.YELLOW}{class_name}{Colors.END}:")
                for loc in locations:
                    bases_str = f"({', '.join(loc['bases'])})" if loc['bases'] else ""
                    print(f"    • {loc['folder']}/{loc['file']}:{loc['line']} - class {class_name}{bases_str}")
                
                conflicts.append({
                    'type': 'class_duplicate',
                    'name': class_name,
                    'locations': locations
                })
        else:
            print(f"{Colors.GREEN}✅ Дубликатов классов не найдено{Colors.END}")
        
        self.results['conflicts'] = conflicts
        return conflicts

    def check_critical_elements(self, all_functions: Dict, all_classes: Dict):
        """Проверка критических элементов DailycheckBot"""
        self.print_section("КРИТИЧЕСКИЕ ЭЛЕМЕНТЫ DAILYCHECKBOT", Colors.CYAN)
        
        # Критические функции из handlers/utils.py
        critical_functions = {
            'get_user_data': 'Получение данных пользователя',
            'save_user_data': 'Сохранение данных пользователя',
            'log_action': 'Логирование действий',
            'add_xp': 'Добавление опыта',
            'check_achievements': 'Проверка достижений',
            'update_user_activity': 'Обновление активности',
            'initialize_user': 'Инициализация пользователя',
            'format_user_profile': 'Форматирование профиля'
        }
        
        # Критические классы из handlers/states.py
        critical_classes = {
            'UserState': 'Перечисление состояний пользователя',
            'StateData': 'Данные состояния',
            'UserStateManager': 'Менеджер состояний',
            'TaskService': 'Сервис задач',
            'AIService': 'AI сервис'
        }
        
        print(f"{Colors.YELLOW}🔧 Проверка критических функций:{Colors.END}")
        for func_name, description in critical_functions.items():
            if func_name in all_functions:
                locations = all_functions[func_name]
                if len(locations) == 1:
                    loc = locations[0]
                    print(f"  ✅ {func_name:<20} | {loc['folder']}/{loc['file']}")
                else:
                    print(f"  ⚠️  {func_name:<20} | ДУБЛИКАТ в {len(locations)} местах!")
                    for loc in locations:
                        print(f"     → {loc['folder']}/{loc['file']}")
            else:
                print(f"  ❌ {func_name:<20} | НЕ НАЙДЕНА")
        
        print(f"\n{Colors.YELLOW}🏗️  Проверка критических классов:{Colors.END}")
        for class_name, description in critical_classes.items():
            if class_name in all_classes:
                locations = all_classes[class_name]
                if len(locations) == 1:
                    loc = locations[0]
                    print(f"  ✅ {class_name:<20} | {loc['folder']}/{loc['file']}")
                else:
                    print(f"  ⚠️  {class_name:<20} | ДУБЛИКАТ в {len(locations)} местах!")
                    for loc in locations:
                        print(f"     → {loc['folder']}/{loc['file']}")
            else:
                print(f"  ❌ {class_name:<20} | НЕ НАЙДЕН")

    def analyze_dependencies(self):
        """Анализ зависимостей между модулями"""
        self.print_section("АНАЛИЗ ЗАВИСИМОСТЕЙ", Colors.GREEN)
        
        internal_imports = defaultdict(set)
        external_imports = defaultdict(Counter)
        
        for folder, imports in self.results['imports'].items():
            for imp in imports:
                module = imp.get('module', '')
                
                if module and ('handlers' in module or 'services' in module or 
                              'ui' in module or 'models' in module):
                    # Внутренний импорт
                    internal_imports[folder].add(module)
                elif module and not module.startswith('.'):
                    # Внешний импорт
                    external_imports[folder][module.split('.')[0]] += 1
        
        print(f"{Colors.CYAN}🔗 Внутренние зависимости:{Colors.END}")
        for folder, modules in internal_imports.items():
            if modules:
                print(f"  📁 {folder}:")
                for module in sorted(modules):
                    print(f"    → {module}")
        
        print(f"\n{Colors.CYAN}📦 Внешние библиотеки (топ-5 на папку):{Colors.END}")
        for folder, modules in external_imports.items():
            if modules:
                print(f"  📁 {folder}:")
                for module, count in modules.most_common(5):
                    print(f"    → {module} ({count} раз)")

    def generate_recommendations(self):
        """Генерация рекомендаций по оптимизации"""
        self.print_section("РЕКОМЕНДАЦИИ ПО ОПТИМИЗАЦИИ", Colors.YELLOW)
        
        recommendations = []
        
        # Проверка конфликтов
        if self.results['conflicts']:
            recommendations.append({
                'priority': 'HIGH',
                'action': 'Устранить дубликаты функций/классов',
                'details': f"Найдено {len(self.results['conflicts'])} конфликтов"
            })
        
        # Проверка папок
        folders = self.results['folders']
        
        # utils/ vs handlers/utils.py
        if 'utils' in folders and 'handlers' in folders:
            recommendations.append({
                'priority': 'MEDIUM',
                'action': 'Проверить конфликт utils/ с handlers/utils.py',
                'details': 'Возможно дублирование функционала'
            })
        
        # shared/ vs handlers/states.py
        if 'shared' in folders and 'handlers' in folders:
            recommendations.append({
                'priority': 'MEDIUM', 
                'action': 'Проверить конфликт shared/ с handlers/states.py',
                'details': 'Возможно дублирование состояний'
            })
        
        # Пустые папки
        empty_folders = [name for name, info in folders.items() 
                        if info['py_files_count'] <= 1]
        if empty_folders:
            recommendations.append({
                'priority': 'LOW',
                'action': f'Рассмотреть удаление пустых папок: {", ".join(empty_folders)}',
                'details': 'Папки содержат только __init__.py или пусты'
            })
        
        # Большие файлы
        large_folders = [name for name, info in folders.items() 
                        if info['size_mb'] > 10]
        if large_folders:
            recommendations.append({
                'priority': 'INFO',
                'action': f'Большие папки: {", ".join(large_folders)}',
                'details': 'Рассмотрите разбиение на подмодули'
            })
        
        # Отсутствие важных папок
        important_missing = [f for f in ['services', 'models', 'ui'] 
                           if f not in folders]
        if important_missing:
            recommendations.append({
                'priority': 'HIGH',
                'action': f'Создать отсутствующие папки: {", ".join(important_missing)}',
                'details': 'Необходимы для правильной архитектуры'
            })
        
        self.results['recommendations'] = recommendations
        
        # Выводим рекомендации
        priority_colors = {
            'HIGH': Colors.RED,
            'MEDIUM': Colors.YELLOW,
            'LOW': Colors.CYAN,
            'INFO': Colors.WHITE
        }
        
        for rec in recommendations:
            color = priority_colors.get(rec['priority'], Colors.WHITE)
            print(f"  {color}[{rec['priority']}]{Colors.END} {rec['action']}")
            print(f"       {Colors.WHITE}{rec['details']}{Colors.END}")
        
        if not recommendations:
            print(f"  {Colors.GREEN}✅ Структура проекта оптимальна!{Colors.END}")

    def create_cleanup_script(self):
        """Создание скрипта для очистки проекта"""
        self.print_section("СКРИПТ ОЧИСТКИ", Colors.MAGENTA)
        
        cleanup_commands = []
        
        # Команды для backup
        cleanup_commands.append("# Создание backup важных папок")
        cleanup_commands.append("mkdir -p backups/")
        
        # Потенциально конфликтующие папки
        if 'utils' in self.results['folders']:
            cleanup_commands.append("mv utils/ backups/utils_backup_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || echo 'utils/ не найдена'")
        
        if 'shared' in self.results['folders']:
            cleanup_commands.append("mv shared/ backups/shared_backup_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || echo 'shared/ не найдена'")
        
        # Временные папки
        temp_folders = ['temp', 'tmp', 'old', 'backup', 'deprecated']
        existing_temp = [f for f in temp_folders if f in self.results['folders']]
        
        if existing_temp:
            cleanup_commands.append("\n# Удаление временных папок")
            for folder in existing_temp:
                cleanup_commands.append(f"rm -rf {folder}/ 2>/dev/null || echo '{folder}/ не найдена'")
        
        # Очистка __pycache__
        cleanup_commands.append("\n# Очистка кэша Python")
        cleanup_commands.append("find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
        cleanup_commands.append("find . -name '*.pyc' -delete 2>/dev/null")
        
        if len(cleanup_commands) > 3:  # Больше чем просто комментарии
            cleanup_script = "#!/bin/bash\n" + "\n".join(cleanup_commands)
            
            with open(self.project_root / "cleanup_project.sh", 'w') as f:
                f.write(cleanup_script)
            
            os.chmod(self.project_root / "cleanup_project.sh", 0o755)
            
            print(f"{Colors.GREEN}✅ Создан скрипт cleanup_project.sh{Colors.END}")
            print(f"  Выполните: {Colors.CYAN}./cleanup_project.sh{Colors.END}")
        else:
            print(f"{Colors.GREEN}✅ Очистка не требуется{Colors.END}")

    def save_report(self):
        """Сохранение отчета в JSON"""
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'results': self.results
        }
        
        report_file = self.project_root / "project_analysis_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n{Colors.GREEN}💾 Отчет сохранен: {report_file}{Colors.END}")

    def run_analysis(self):
        """Запуск полного анализа"""
        self.print_header("АНАЛИЗАТОР ПРОЕКТА DAILYCHECKBOT2025", Colors.CYAN)
        
        print(f"{Colors.WHITE}Корень проекта: {self.project_root.absolute()}{Colors.END}")
        print(f"{Colors.WHITE}Время анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
        
        # 1. Анализ структуры папок
        self.analyze_folder_structure()
        
        # 2. Анализ кода
        all_functions, all_classes = self.analyze_code_elements()
        
        # 3. Поиск конфликтов
        self.find_conflicts(all_functions, all_classes)
        
        # 4. Проверка критических элементов
        self.check_critical_elements(all_functions, all_classes)
        
        # 5. Анализ зависимостей
        self.analyze_dependencies()
        
        # 6. Рекомендации
        self.generate_recommendations()
        
        # 7. Скрипт очистки
        self.create_cleanup_script()
        
        # 8. Сохранение отчета
        self.save_report()
        
        self.print_header("АНАЛИЗ ЗАВЕРШЕН", Colors.GREEN)

def main():
    """Главная функция"""
    try:
        analyzer = ProjectAnalyzer()
        analyzer.run_analysis()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚡ Анализ прерван пользователем{Colors.END}")
    except Exception as e:
        print(f"\n{Colors.RED}❌ Ошибка выполнения: {e}{Colors.END}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()check_project_conflicts.py
