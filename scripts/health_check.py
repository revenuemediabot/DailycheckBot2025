#!/usr/bin/env python3
"""
Скрипт проверки состояния системы
Использование: python scripts/health_check.py [--web] [--bot] [--data] [--all] [--json]
"""

import sys
import os
import asyncio
import argparse
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# Добавляем корневую папку в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class HealthChecker:
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
        
    async def check_environment(self) -> Dict[str, Any]:
        """Проверка переменных окружения"""
        env_checks = {
            "BOT_TOKEN": bool(os.getenv('BOT_TOKEN')),
            "WEBHOOK_URL": bool(os.getenv('WEBHOOK_URL')),
            "ENVIRONMENT": os.getenv('ENVIRONMENT', 'production'),
            "PORT": os.getenv('PORT', 'not_set'),
            "WEBHOOK_PORT": os.getenv('WEBHOOK_PORT', 'not_set')
        }
        
        # Проверяем критичные переменные
        critical_missing = []
        if not env_checks["BOT_TOKEN"]:
            critical_missing.append("BOT_TOKEN")
            
        status = "healthy" if not critical_missing else "unhealthy"
        
        return {
            "status": status,
            "environment_variables": env_checks,
            "critical_missing": critical_missing,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": sys.platform
        }
    
    async def check_dependencies(self) -> Dict[str, Any]:
        """Проверка установленных зависимостей"""
        dependencies = {
            "python-telegram-bot": False,
            "fastapi": False,
            "uvicorn": False,
            "pydantic": False,
            "aiofiles": False,
            "jinja2": False
        }
        
        missing_deps = []
        
        for dep_name in dependencies:
            try:
                if dep_name == "python-telegram-bot":
                    import telegram
                    dependencies[dep_name] = True
                elif dep_name == "fastapi":
                    import fastapi
                    dependencies[dep_name] = True
                elif dep_name == "uvicorn":
                    import uvicorn
                    dependencies[dep_name] = True
                elif dep_name == "pydantic":
                    import pydantic
                    dependencies[dep_name] = True
                elif dep_name == "aiofiles":
                    import aiofiles
                    dependencies[dep_name] = True
                elif dep_name == "jinja2":
                    import jinja2
                    dependencies[dep_name] = True
                    
            except ImportError:
                missing_deps.append(dep_name)
        
        status = "healthy" if not missing_deps else "unhealthy"
        
        return {
            "status": status,
            "dependencies": dependencies,
            "missing": missing_deps,
            "total_checked": len(dependencies),
            "installed_count": sum(dependencies.values())
        }
    
    async def check_file_structure(self) -> Dict[str, Any]:
        """Проверка структуры файлов проекта"""
        required_paths = {
            # Основные папки
            "bot/": project_root / "bot",
            "dashboard/": project_root / "dashboard", 
            "data/": project_root / "data",
            "scripts/": project_root / "scripts",
            "shared/": project_root / "shared",
            
            # Важные файлы
            "README.md": project_root / "README.md",
            "requirements.txt": project_root / "requirements.txt",
            "requirements-web.txt": project_root / "requirements-web.txt",
            
            # API файлы
            "dashboard/app.py": project_root / "dashboard" / "app.py",
            "dashboard/config.py": project_root / "dashboard" / "config.py",
            "dashboard/core/data_manager.py": project_root / "dashboard" / "core" / "data_manager.py",
            
            # Скрипты
            "scripts/start_bot.py": project_root / "scripts" / "start_bot.py",
            "scripts/start_web.py": project_root / "scripts" / "start_web.py",
            
            # Данные
            "data/users.json": project_root / "data" / "users.json",
            "data/tasks.json": project_root / "data" / "tasks.json"
        }
        
        file_status = {}
        missing_files = []
        existing_files = []
        
        for name, path in required_paths.items():
            exists = path.exists()
            file_status[name] = {
                "exists": exists,
                "path": str(path),
                "is_file": path.is_file() if exists else None,
                "is_dir": path.is_dir() if exists else None,
                "size": path.stat().st_size if exists and path.is_file() else None
            }
            
            if exists:
                existing_files.append(name)
            else:
                missing_files.append(name)
        
        # Создаем недостающие папки и файлы данных
        await self._create_missing_data_files()
        
        status = "healthy" if len(missing_files) <= 2 else "warning"  # Позволяем до 2 отсутствующих файлов
        
        return {
            "status": status,
            "files": file_status,
            "missing": missing_files,
            "existing": existing_files,
            "total_checked": len(required_paths),
            "existing_count": len(existing_files)
        }
    
    async def _create_missing_data_files(self):
        """Создание недостающих файлов данных"""
        data_dir = project_root / "data"
        data_dir.mkdir(exist_ok=True)
        
        # Создаем users.json если не существует
        users_file = data_dir / "users.json"
        if not users_file.exists():
            with open(users_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        
        # Создаем tasks.json если не существует
        tasks_file = data_dir / "tasks.json"
        if not tasks_file.exists():
            with open(tasks_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        
        # Создаем папку для логов
        logs_dir = project_root / "logs"
        logs_dir.mkdir(exist_ok=True)
    
    async def check_data_integrity(self) -> Dict[str, Any]:
        """Проверка целостности данных"""
        try:
            data_dir = project_root / "data"
            
            # Проверяем users.json
            users_status = await self._check_json_file(data_dir / "users.json", "users")
            
            # Проверяем tasks.json
            tasks_status = await self._check_json_file(data_dir / "tasks.json", "tasks")
            
            # Общий статус
            overall_status = "healthy"
            if users_status["status"] != "healthy" or tasks_status["status"] != "healthy":
                overall_status = "warning"
            
            return {
                "status": overall_status,
                "users_file": users_status,
                "tasks_file": tasks_status,
                "data_directory": str(data_dir),
                "backup_available": (data_dir / "backups").exists()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "users_file": {"status": "unknown"},
                "tasks_file": {"status": "unknown"}
            }
    
    async def _check_json_file(self, file_path: Path, file_type: str) -> Dict[str, Any]:
        """Проверка JSON файла"""
        if not file_path.exists():
            return {
                "status": "missing",
                "exists": False,
                "readable": False,
                "valid_json": False,
                "record_count": 0
            }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            record_count = len(data) if isinstance(data, dict) else 0
            
            return {
                "status": "healthy",
                "exists": True,
                "readable": True,
                "valid_json": True,
                "record_count": record_count,
                "file_size": file_path.stat().st_size,
                "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }
            
        except json.JSONDecodeError as e:
            return {
                "status": "corrupted",
                "exists": True,
                "readable": True,
                "valid_json": False,
                "error": f"JSON decode error: {str(e)}",
                "record_count": 0
            }
        except Exception as e:
            return {
                "status": "error",
                "exists": True,
                "readable": False,
                "valid_json": False,
                "error": str(e),
                "record_count": 0
            }
    
    async def check_bot_health(self) -> Dict[str, Any]:
        """Проверка состояния бота"""
        try:
            bot_token = os.getenv('BOT_TOKEN')
            if not bot_token:
                return {
                    "status": "unconfigured",
                    "error": "BOT_TOKEN not found",
                    "bot_info": None
                }
            
            # Попытка подключения к Telegram API
            try:
                from telegram import Bot
                
                bot = Bot(token=bot_token)
                
                # Получаем информацию о боте
                bot_info = await bot.get_me()
                
                # Проверяем webhook
                webhook_info = await bot.get_webhook_info()
                
                return {
                    "status": "healthy",
                    "bot_info": {
                        "id": bot_info.id,
                        "username": bot_info.username,
                        "first_name": bot_info.first_name,
                        "can_join_groups": bot_info.can_join_groups,
                        "can_read_all_group_messages": bot_info.can_read_all_group_messages,
                        "supports_inline_queries": bot_info.supports_inline_queries
                    },
                    "webhook_info": {
                        "url": webhook_info.url,
                        "has_custom_certificate": webhook_info.has_custom_certificate,
                        "pending_update_count": webhook_info.pending_update_count,
                        "last_error_date": webhook_info.last_error_date.isoformat() if webhook_info.last_error_date else None,
                        "last_error_message": webhook_info.last_error_message
                    }
                }
                
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "error": f"Telegram API error: {str(e)}",
                    "bot_info": None
                }
                
        except ImportError:
            return {
                "status": "dependency_missing",
                "error": "python-telegram-bot library not installed",
                "bot_info": None
            }
    
    async def check_web_health(self) -> Dict[str, Any]:
        """Проверка состояния веб-сервиса"""
        try:
            # Проверяем доступность FastAPI
            try:
                import aiohttp
                
                # Попытка подключения к локальному веб-серверу
                port = int(os.getenv('PORT', 8000))
                url = f"http://localhost:{port}/health"
                
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                return {
                                    "status": "healthy",
                                    "web_server": "running",
                                    "port": port,
                                    "response": data
                                }
                            else:
                                return {
                                    "status": "unhealthy",
                                    "web_server": "error",
                                    "port": port,
                                    "http_status": response.status
                                }
                    except aiohttp.ClientConnectorError:
                        return {
                            "status": "offline",
                            "web_server": "not_running",
                            "port": port,
                            "error": "Connection refused"
                        }
                        
            except ImportError:
                return {
                    "status": "dependency_missing",
                    "error": "aiohttp library not installed for web health check"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def run_comprehensive_check(self) -> Dict[str, Any]:
        """Запуск всех проверок"""
        print("🔍 Запуск проверки состояния системы...")
        
        checks = [
            ("environment", self.check_environment()),
            ("dependencies", self.check_dependencies()),
            ("file_structure", self.check_file_structure()),
            ("data_integrity", self.check_data_integrity()),
            ("bot_health", self.check_bot_health()),
            ("web_health", self.check_web_health())
        ]
        
        results = {}
        
        for check_name, check_coro in checks:
            print(f"  Проверка {check_name}...")
            try:
                results[check_name] = await check_coro
                status = results[check_name]["status"]
                emoji = "✅" if status == "healthy" else "⚠️" if status == "warning" else "❌"
                print(f"  {emoji} {check_name}: {status}")
            except Exception as e:
                results[check_name] = {
                    "status": "error",
                    "error": str(e)
                }
                print(f"  ❌ {check_name}: error - {str(e)}")
        
        # Общий статус системы
        statuses = [result["status"] for result in results.values()]
        if all(s == "healthy" for s in statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "warning"
        
        execution_time = time.time() - self.start_time
        
        return {
            "overall_status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "execution_time": round(execution_time, 2),
            "checks": results,
            "summary": {
                "total_checks": len(checks),
                "healthy": sum(1 for s in statuses if s == "healthy"),
                "warnings": sum(1 for s in statuses if s == "warning"),
                "unhealthy": sum(1 for s in statuses if s == "unhealthy"),
                "errors": sum(1 for s in statuses if s == "error")
            }
        }

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Проверка состояния системы')
    parser.add_argument('--web', action='store_true', help='Только проверка веб-сервиса')
    parser.add_argument('--bot', action='store_true', help='Только проверка бота')
    parser.add_argument('--data', action='store_true', help='Только проверка данных')
    parser.add_argument('--env', action='store_true', help='Только проверка окружения')
    parser.add_argument('--all', action='store_true', help='Все проверки (по умолчанию)')
    parser.add_argument('--json', action='store_true', help='Вывод в формате JSON')
    parser.add_argument('--output', type=str, help='Сохранить результат в файл')
    
    args = parser.parse_args()
    
    # Если не указаны конкретные проверки, запускаем все
    if not any([args.web, args.bot, args.data, args.env]):
        args.all = True
    
    async def run_checks():
        checker = HealthChecker()
        
        if args.all:
            result = await checker.run_comprehensive_check()
        else:
            # Запуск конкретных проверок
            result = {
                "timestamp": datetime.now().isoformat(),
                "checks": {}
            }
            
            if args.env:
                result["checks"]["environment"] = await checker.check_environment()
            if args.data:
                result["checks"]["data_integrity"] = await checker.check_data_integrity()
            if args.bot:
                result["checks"]["bot_health"] = await checker.check_bot_health()
            if args.web:
                result["checks"]["web_health"] = await checker.check_web_health()
        
        return result
    
    try:
        result = asyncio.run(run_checks())
        
        if args.json:
            output = json.dumps(result, indent=2, ensure_ascii=False)
        else:
            # Человекочитаемый вывод
            output = format_human_readable(result)
        
        # Вывод результата
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f"Результат сохранен в {args.output}")
        else:
            print(output)
        
        # Возвращаем код завершения
        if result.get("overall_status") == "healthy":
            sys.exit(0)
        elif result.get("overall_status") == "warning":
            sys.exit(1)
        else:
            sys.exit(2)
            
    except KeyboardInterrupt:
        print("\n⚠️ Проверка прервана пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

def format_human_readable(result: Dict[str, Any]) -> str:
    """Форматирование результата в человекочитаемом виде"""
    lines = []
    
    # Заголовок
    overall = result.get("overall_status", "unknown")
    emoji = "✅" if overall == "healthy" else "⚠️" if overall == "warning" else "❌"
    lines.append(f"\n{emoji} Общий статус системы: {overall.upper()}")
    lines.append(f"🕐 Время проверки: {result.get('timestamp', 'unknown')}")
    
    if "execution_time" in result:
        lines.append(f"⏱️ Время выполнения: {result['execution_time']} сек")
    
    lines.append("\n" + "="*50)
    
    # Детали проверок
    checks = result.get("checks", {})
    
    for check_name, check_result in checks.items():
        status = check_result.get("status", "unknown")
        emoji = "✅" if status == "healthy" else "⚠️" if status == "warning" else "❌"
        
        lines.append(f"\n{emoji} {check_name.upper()}: {status}")
        
        # Дополнительная информация
        if check_name == "environment" and "critical_missing" in check_result:
            missing = check_result["critical_missing"]
            if missing:
                lines.append(f"   ❌ Отсутствуют критичные переменные: {', '.join(missing)}")
        
        elif check_name == "dependencies" and "missing" in check_result:
            missing = check_result["missing"]
            if missing:
                lines.append(f"   ❌ Отсутствуют зависимости: {', '.join(missing)}")
        
        elif check_name == "bot_health" and "bot_info" in check_result:
            bot_info = check_result["bot_info"]
            if bot_info:
                lines.append(f"   🤖 Бот: @{bot_info['username']} ({bot_info['first_name']})")
        
        elif "error" in check_result:
            lines.append(f"   ❌ Ошибка: {check_result['error']}")
    
    # Сводка
    if "summary" in result:
        summary = result["summary"]
        lines.append("\n" + "="*50)
        lines.append("📊 СВОДКА:")
        lines.append(f"   Всего проверок: {summary.get('total_checks', 0)}")
        lines.append(f"   ✅ Здоровых: {summary.get('healthy', 0)}")
        lines.append(f"   ⚠️ Предупреждений: {summary.get('warnings', 0)}")
        lines.append(f"   ❌ Нездоровых: {summary.get('unhealthy', 0)}")
        lines.append(f"   💥 Ошибок: {summary.get('errors', 0)}")
    
    return "\n".join(lines) + "\n"

if __name__ == "__main__":
    main()
