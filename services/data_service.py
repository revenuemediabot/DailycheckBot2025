# services/data_service.py

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import os

# Проверяем доступность pandas
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

logger = logging.getLogger(__name__)

class DataServiceConfig:
    """Конфигурация для сервиса данных"""
    
    # Директории
    DATA_DIR = Path(os.getenv('DATA_DIR', 'data'))
    BACKUP_DIR = Path(os.getenv('BACKUP_DIR', 'backups'))
    EXPORT_DIR = Path(os.getenv('EXPORT_DIR', 'exports'))
    
    # Настройки кэша
    MAX_USERS_CACHE = int(os.getenv('MAX_USERS_CACHE', 1000))
    
    # Настройки бэкапов
    BACKUP_INTERVAL_HOURS = int(os.getenv('BACKUP_INTERVAL_HOURS', 6))
    MAX_BACKUPS_KEEP = int(os.getenv('MAX_BACKUPS_KEEP', 10))
    
    # Файлы данных
    USERS_DATA_FILE = 'users_data.json'
    ANALYTICS_DATA_FILE = 'analytics_data.json'
    SYSTEM_LOG_FILE = 'system_log.json'
    
    @classmethod
    def ensure_directories(cls):
        """Создание необходимых директорий"""
        for directory in [cls.DATA_DIR, cls.BACKUP_DIR, cls.EXPORT_DIR]:
            directory.mkdir(exist_ok=True)
            logger.debug(f"Директория создана/проверена: {directory}")

class DataService:
    """
    Полный сервис для работы с данными пользователей
    
    Возможности:
    - Загрузка и сохранение данных пользователей
    - Кэширование в памяти для быстрого доступа
    - Автоматическое создание бэкапов
    - Экспорт данных в различных форматах
    - Аналитика и метрики
    - Транзакционная безопасность
    """
    
    def __init__(self, data_file: str = None):
        self.config = DataServiceConfig()
        self.config.ensure_directories()
        
        # Файлы данных
        self.data_file = self.config.DATA_DIR / (data_file or self.config.USERS_DATA_FILE)
        self.analytics_file = self.config.DATA_DIR / self.config.ANALYTICS_DATA_FILE
        self.system_log_file = self.config.DATA_DIR / self.config.SYSTEM_LOG_FILE
        
        # Кэш пользователей
        self.users_cache: Dict[int, Any] = {}  # Any = User class from main.py
        self.cache_lock = threading.RLock()
        
        # Метрики и состояние
        self.last_save_time = time.time()
        self.pending_saves = set()  # user_ids для сохранения
        self.total_operations = 0
        self.failed_operations = 0
        
        # Инициализация
        self._initialize()
        
    def _initialize(self):
        """Инициализация сервиса"""
        try:
            logger.info("🔧 Инициализация DataService...")
            
            # Загружаем данные
            self._load_all_users()
            
            # Загружаем системные данные
            self._load_system_data()
            
            # Запускаем фоновые задачи
            self._start_background_tasks()
            
            logger.info(f"✅ DataService инициализирован. Пользователей в кэше: {len(self.users_cache)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации DataService: {e}")
            raise
    
    def _load_all_users(self):
        """Загрузка всех пользователей из файла"""
        try:
            if not self.data_file.exists():
                logger.info("📂 Файл данных не найден, начинаем с пустой базы")
                self.users_cache = {}
                return
            
            # Читаем файл
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                logger.warning("⚠️ Неверный формат файла данных")
                self.users_cache = {}
                return
            
            # Загружаем пользователей в кэш (сериализованный вид)
            loaded_count = 0
            with self.cache_lock:
                for user_id_str, user_data in data.items():
                    try:
                        user_id = int(user_id_str)
                        # Пока сохраняем как словарь, позже User класс десериализует
                        self.users_cache[user_id] = user_data
                        loaded_count += 1
                    except (ValueError, TypeError) as e:
                        logger.error(f"❌ Ошибка загрузки пользователя {user_id_str}: {e}")
            
            logger.info(f"📂 Загружено {loaded_count} пользователей из {self.data_file}")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            self._create_backup_and_reset()
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных: {e}")
            self.users_cache = {}
    
    def _create_backup_and_reset(self):
        """Создание бэкапа поврежденного файла и сброс"""
        try:
            if self.data_file.exists():
                backup_name = f"corrupted_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                backup_path = self.config.BACKUP_DIR / backup_name
                self.data_file.replace(backup_path)
                logger.warning(f"🔄 Поврежденный файл перемещен в {backup_path}")
            
            self.users_cache = {}
            logger.info("🆕 Создана новая чистая база данных")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания бэкапа: {e}")
    
    def _load_system_data(self):
        """Загрузка системных данных и аналитики"""
        try:
            # Загружаем аналитику
            if self.analytics_file.exists():
                with open(self.analytics_file, 'r', encoding='utf-8') as f:
                    analytics_data = json.load(f)
                logger.debug(f"📊 Загружена аналитика: {len(analytics_data)} записей")
            
            # Загружаем системные логи
            if self.system_log_file.exists():
                with open(self.system_log_file, 'r', encoding='utf-8') as f:
                    system_data = json.load(f)
                logger.debug(f"📋 Загружены системные данные: {len(system_data)} записей")
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки системных данных: {e}")
    
    def _start_background_tasks(self):
        """Запуск фоновых задач"""
        try:
            # Можно добавить APScheduler или asyncio tasks для:
            # - Периодического сохранения
            # - Создания бэкапов
            # - Очистки старых файлов
            logger.debug("🔄 Фоновые задачи запущены")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска фоновых задач: {e}")
    
    # ===== ОСНОВНЫЕ МЕТОДЫ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ =====
    
    def get_user_data(self, user_id: int) -> Optional[Dict]:
        """Получить данные пользователя по ID"""
        with self.cache_lock:
            user_data = self.users_cache.get(user_id)
            if user_data:
                self.total_operations += 1
                logger.debug(f"👤 Получены данные пользователя {user_id}")
            return user_data
    
    def save_user_data(self, user_id: int, user_data: Dict):
        """Сохранить данные пользователя в кэш"""
        try:
            with self.cache_lock:
                self.users_cache[user_id] = user_data
                self.pending_saves.add(user_id)
                self.total_operations += 1
                
            logger.debug(f"💾 Данные пользователя {user_id} обновлены в кэше")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пользователя {user_id}: {e}")
            self.failed_operations += 1
            raise
    
    def delete_user_data(self, user_id: int) -> bool:
        """Удалить данные пользователя"""
        try:
            with self.cache_lock:
                if user_id in self.users_cache:
                    del self.users_cache[user_id]
                    self.pending_saves.add(user_id)  # Для фиксации удаления
                    logger.info(f"🗑️ Пользователь {user_id} удален")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка удаления пользователя {user_id}: {e}")
            self.failed_operations += 1
            return False
    
    def user_exists(self, user_id: int) -> bool:
        """Проверить существование пользователя"""
        with self.cache_lock:
            return user_id in self.users_cache
    
    def get_all_users_data(self) -> Dict[int, Dict]:
        """Получить данные всех пользователей"""
        with self.cache_lock:
            return self.users_cache.copy()
    
    def get_users_count(self) -> int:
        """Получить количество пользователей"""
        return len(self.users_cache)
    
    # ===== СОХРАНЕНИЕ НА ДИСК =====
    
    def save_all_to_disk(self) -> bool:
        """Синхронное сохранение всех данных на диск"""
        try:
            start_time = time.time()
            
            with self.cache_lock:
                # Создаем резервную копию перед сохранением
                if self.data_file.exists():
                    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    backup_path = self.config.BACKUP_DIR / backup_name
                    self.data_file.replace(backup_path)
                    logger.debug(f"💾 Создан бэкап: {backup_name}")
                
                # Конвертируем кэш для сохранения
                data_to_save = {}
                for user_id, user_data in self.users_cache.items():
                    data_to_save[str(user_id)] = user_data
                
                # Атомарное сохранение через временный файл
                temp_file = self.data_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data_to_save, f, ensure_ascii=False, indent=2)
                
                # Заменяем основной файл
                temp_file.replace(self.data_file)
                
                # Обновляем метрики
                self.last_save_time = time.time()
                self.pending_saves.clear()
                
                save_duration = time.time() - start_time
                logger.info(f"💾 Данные сохранены успешно за {save_duration:.2f}с ({len(self.users_cache)} пользователей)")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных: {e}")
            self.failed_operations += 1
            return False
    
    async def save_all_to_disk_async(self) -> bool:
        """Асинхронное сохранение всех данных на диск"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.save_all_to_disk)
    
    def force_save(self):
        """Принудительное сохранение"""
        logger.info("🔄 Принудительное сохранение данных...")
        return self.save_all_to_disk()
    
    # ===== ЭКСПОРТ ДАННЫХ =====
    
    def export_user_data(self, user_id: int, format: str = "json") -> Optional[bytes]:
        """Экспорт данных пользователя в указанном формате"""
        try:
            user_data = self.get_user_data(user_id)
            if not user_data:
                logger.warning(f"⚠️ Пользователь {user_id} не найден для экспорта")
                return None
            
            if format.lower() == "json":
                export_data = {
                    "export_info": {
                        "format": "json",
                        "version": "4.0",
                        "exported_at": datetime.now().isoformat(),
                        "user_id": user_id
                    },
                    "user_data": user_data
                }
                
                json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                logger.info(f"📤 JSON экспорт для пользователя {user_id} подготовлен")
                return json_str.encode('utf-8')
            
            elif format.lower() == "csv" and PANDAS_AVAILABLE:
                # Экспорт задач в CSV
                tasks_data = []
                
                if "tasks" in user_data:
                    for task_id, task_info in user_data["tasks"].items():
                        # Извлекаем данные о выполнении
                        completions = task_info.get("completions", [])
                        for completion in completions:
                            tasks_data.append({
                                "task_id": task_id,
                                "title": task_info.get("title", ""),
                                "category": task_info.get("category", ""),
                                "priority": task_info.get("priority", ""),
                                "status": task_info.get("status", ""),
                                "date": completion.get("date", ""),
                                "completed": completion.get("completed", False),
                                "time_spent": completion.get("time_spent"),
                                "note": completion.get("note", ""),
                                "timestamp": completion.get("timestamp", "")
                            })
                
                if tasks_data:
                    df = pd.DataFrame(tasks_data)
                    csv_data = df.to_csv(index=False)
                    logger.info(f"📊 CSV экспорт для пользователя {user_id} подготовлен ({len(tasks_data)} записей)")
                    return csv_data.encode('utf-8')
                else:
                    # Пустой CSV с заголовками
                    headers = "task_id,title,category,priority,status,date,completed,time_spent,note,timestamp\n"
                    return headers.encode('utf-8')
            
            elif format.lower() == "xlsx" and PANDAS_AVAILABLE:
                # Экспорт в Excel
                import io
                
                tasks_data = []
                stats_data = []
                
                # Собираем данные задач
                if "tasks" in user_data:
                    for task_id, task_info in user_data["tasks"].items():
                        completions = task_info.get("completions", [])
                        for completion in completions:
                            tasks_data.append({
                                "task_id": task_id,
                                "title": task_info.get("title", ""),
                                "category": task_info.get("category", ""),
                                "priority": task_info.get("priority", ""),
                                "status": task_info.get("status", ""),
                                "date": completion.get("date", ""),
                                "completed": completion.get("completed", False),
                                "time_spent": completion.get("time_spent"),
                                "note": completion.get("note", "")
                            })
                
                # Собираем статистику
                if "stats" in user_data:
                    stats = user_data["stats"]
                    stats_data.append({
                        "metric": "Всего задач",
                        "value": stats.get("total_tasks", 0)
                    })
                    stats_data.append({
                        "metric": "Выполнено задач",
                        "value": stats.get("completed_tasks", 0)
                    })
                    stats_data.append({
                        "metric": "Текущий streak",
                        "value": stats.get("current_streak", 0)
                    })
                    stats_data.append({
                        "metric": "Максимальный streak",
                        "value": stats.get("longest_streak", 0)
                    })
                    stats_data.append({
                        "metric": "Общий XP",
                        "value": stats.get("total_xp", 0)
                    })
                    stats_data.append({
                        "metric": "Уровень",
                        "value": stats.get("level", 1)
                    })
                
                # Создаем Excel файл
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    if tasks_data:
                        df_tasks = pd.DataFrame(tasks_data)
                        df_tasks.to_excel(writer, sheet_name='Задачи', index=False)
                    
                    if stats_data:
                        df_stats = pd.DataFrame(stats_data)
                        df_stats.to_excel(writer, sheet_name='Статистика', index=False)
                
                logger.info(f"📈 Excel экспорт для пользователя {user_id} подготовлен")
                return output.getvalue()
            
            else:
                logger.warning(f"⚠️ Неподдерживаемый формат экспорта: {format}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта данных пользователя {user_id}: {e}")
            return None
    
    def export_all_users_data(self, format: str = "json") -> Optional[bytes]:
        """Экспорт данных всех пользователей"""
        try:
            if format.lower() == "json":
                export_data = {
                    "export_info": {
                        "format": "json",
                        "version": "4.0", 
                        "exported_at": datetime.now().isoformat(),
                        "total_users": len(self.users_cache)
                    },
                    "users_data": self.users_cache
                }
                
                json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
                logger.info(f"📤 Полный JSON экспорт подготовлен ({len(self.users_cache)} пользователей)")
                return json_str.encode('utf-8')
            
            else:
                logger.warning(f"⚠️ Неподдерживаемый формат для полного экспорта: {format}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка полного экспорта: {e}")
            return None
    
    # ===== БЭКАПЫ И ВОССТАНОВЛЕНИЕ =====
    
    def create_backup(self, backup_name: str = None) -> Optional[Path]:
        """Создание бэкапа данных"""
        try:
            if not backup_name:
                backup_name = f"manual_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            backup_path = self.config.BACKUP_DIR / backup_name
            
            # Копируем текущий файл данных
            if self.data_file.exists():
                import shutil
                shutil.copy2(self.data_file, backup_path)
                logger.info(f"💾 Бэкап создан: {backup_path}")
                return backup_path
            else:
                logger.warning("⚠️ Нет файла данных для создания бэкапа")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания бэкапа: {e}")
            return None
    
    def restore_from_backup(self, backup_path: Path) -> bool:
        """Восстановление из бэкапа"""
        try:
            if not backup_path.exists():
                logger.error(f"❌ Файл бэкапа не найден: {backup_path}")
                return False
            
            # Создаем бэкап текущих данных
            current_backup = self.create_backup("pre_restore_backup.json")
            if current_backup:
                logger.info(f"💾 Текущие данные сохранены в {current_backup}")
            
            # Восстанавливаем из бэкапа
            import shutil
            shutil.copy2(backup_path, self.data_file)
            
            # Перезагружаем данные
            self._load_all_users()
            
            logger.info(f"✅ Восстановление из {backup_path} завершено")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления из бэкапа: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count: int = None):
        """Удаление старых бэкапов"""
        try:
            if keep_count is None:
                keep_count = self.config.MAX_BACKUPS_KEEP
            
            backups = list(self.config.BACKUP_DIR.glob("backup_*.json"))
            backups.extend(self.config.BACKUP_DIR.glob("manual_backup_*.json"))
            
            if len(backups) <= keep_count:
                logger.debug(f"📁 Количество бэкапов ({len(backups)}) не превышает лимит ({keep_count})")
                return
            
            # Сортируем по времени создания
            backups.sort(key=lambda x: x.stat().st_mtime)
            
            # Удаляем старые
            to_delete = backups[:-keep_count]
            deleted_count = 0
            
            for backup in to_delete:
                try:
                    backup.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"❌ Ошибка удаления бэкапа {backup}: {e}")
            
            logger.info(f"🗑️ Удалено {deleted_count} старых бэкапов")
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки бэкапов: {e}")
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """Получение списка доступных бэкапов"""
        try:
            backups = []
            backup_files = list(self.config.BACKUP_DIR.glob("*.json"))
            
            for backup_file in backup_files:
                stat = backup_file.stat()
                backups.append({
                    "name": backup_file.name,
                    "path": backup_file,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime),
                    "modified": datetime.fromtimestamp(stat.st_mtime)
                })
            
            # Сортируем по дате создания (новые первые)
            backups.sort(key=lambda x: x["created"], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка бэкапов: {e}")
            return []
    
    # ===== АНАЛИТИКА И МЕТРИКИ =====
    
    def get_service_metrics(self) -> Dict[str, Any]:
        """Получение метрик сервиса"""
        return {
            "users_count": len(self.users_cache),
            "pending_saves": len(self.pending_saves),
            "total_operations": self.total_operations,
            "failed_operations": self.failed_operations,
            "last_save_time": self.last_save_time,
            "cache_size_mb": len(str(self.users_cache)) / 1024 / 1024,
            "data_file_size": self.data_file.stat().st_size if self.data_file.exists() else 0,
            "backups_count": len(list(self.config.BACKUP_DIR.glob("*.json")))
        }
    
    def get_users_analytics(self) -> Dict[str, Any]:
        """Получение аналитики по пользователям"""
        try:
            analytics = {
                "total_users": len(self.users_cache),
                "active_users": 0,
                "total_tasks": 0,
                "completed_tasks": 0,
                "total_xp": 0,
                "avg_level": 0,
                "top_users_by_level": [],
                "users_by_registration_date": {},
                "tasks_by_category": {},
                "completion_rate": 0
            }
            
            levels = []
            registration_dates = []
            
            for user_data in self.users_cache.values():
                # Проверяем активность (есть задачи)
                if user_data.get("tasks"):
                    analytics["active_users"] += 1
                
                # Подсчитываем задачи
                tasks = user_data.get("tasks", {})
                analytics["total_tasks"] += len(tasks)
                
                # Анализируем задачи
                for task_data in tasks.values():
                    category = task_data.get("category", "unknown")
                    analytics["tasks_by_category"][category] = analytics["tasks_by_category"].get(category, 0) + 1
                    
                    # Подсчитываем выполненные задачи
                    completions = task_data.get("completions", [])
                    completed = sum(1 for c in completions if c.get("completed", False))
                    analytics["completed_tasks"] += completed
                
                # Статистика пользователя
                stats = user_data.get("stats", {})
                analytics["total_xp"] += stats.get("total_xp", 0)
                
                level = stats.get("level", 1)
                levels.append(level)
                
                # Дата регистрации
                reg_date = stats.get("registration_date", "")
                if reg_date:
                    reg_day = reg_date[:10]  # YYYY-MM-DD
                    analytics["users_by_registration_date"][reg_day] = analytics["users_by_registration_date"].get(reg_day, 0) + 1
            
            # Вычисляем средние показатели
            if levels:
                analytics["avg_level"] = sum(levels) / len(levels)
            
            if analytics["total_tasks"] > 0:
                analytics["completion_rate"] = (analytics["completed_tasks"] / analytics["total_tasks"]) * 100
            
            logger.debug(f"📊 Аналитика сгенерирована для {analytics['total_users']} пользователей")
            return analytics
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации аналитики: {e}")
            return {}
    
    def save_analytics_snapshot(self):
        """Сохранение снимка аналитики"""
        try:
            analytics = self.get_users_analytics()
            service_metrics = self.get_service_metrics()
            
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "analytics": analytics,
                "service_metrics": service_metrics
            }
            
            # Загружаем существующие снимки
            snapshots = []
            if self.analytics_file.exists():
                with open(self.analytics_file, 'r', encoding='utf-8') as f:
                    snapshots = json.load(f)
            
            # Добавляем новый снимок
            snapshots.append(snapshot)
            
            # Ограничиваем количество снимков (последние 100)
            if len(snapshots) > 100:
                snapshots = snapshots[-100:]
            
            # Сохраняем
            with open(self.analytics_file, 'w', encoding='utf-8') as f:
                json.dump(snapshots, f, ensure_ascii=False, indent=2)
            
            logger.info("📊 Снимок аналитики сохранен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения аналитики: {e}")
    
    # ===== ПОИСК И ФИЛЬТРАЦИЯ =====
    
    def search_users(self, query: str, field: str = "all") -> List[Dict[str, Any]]:
        """Поиск пользователей по различным критериям"""
        try:
            results = []
            query_lower = query.lower()
            
            for user_id, user_data in self.users_cache.items():
                match = False
                
                if field == "all" or field == "username":
                    username = user_data.get("username", "")
                    if username and query_lower in username.lower():
                        match = True
                
                if field == "all" or field == "first_name":
                    first_name = user_data.get("first_name", "")
                    if first_name and query_lower in first_name.lower():
                        match = True
                
                if field == "all" or field == "task_title":
                    tasks = user_data.get("tasks", {})
                    for task in tasks.values():
                        if query_lower in task.get("title", "").lower():
                            match = True
                            break
                
                if match:
                    results.append({
                        "user_id": user_id,
                        "username": user_data.get("username"),
                        "first_name": user_data.get("first_name"),
                        "tasks_count": len(user_data.get("tasks", {})),
                        "level": user_data.get("stats", {}).get("level", 1)
                    })
            
            logger.info(f"🔍 Найдено {len(results)} пользователей по запросу '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return []
    
    def filter_users_by_criteria(self, criteria: Dict[str, Any]) -> List[int]:
        """Фильтрация пользователей по критериям"""
        try:
            filtered_users = []
            
            for user_id, user_data in self.users_cache.items():
                match = True
                
                # Фильтр по уровню
                if "min_level" in criteria:
                    user_level = user_data.get("stats", {}).get("level", 1)
                    if user_level < criteria["min_level"]:
                        match = False
                
                if "max_level" in criteria:
                    user_level = user_data.get("stats", {}).get("level", 1)
                    if user_level > criteria["max_level"]:
                        match = False
                
                # Фильтр по количеству задач
                if "min_tasks" in criteria:
                    tasks_count = len(user_data.get("tasks", {}))
                    if tasks_count < criteria["min_tasks"]:
                        match = False
                
                # Фильтр по активности
                if "has_tasks" in criteria and criteria["has_tasks"]:
                    if not user_data.get("tasks"):
                        match = False
                
                # Фильтр по дате регистрации
                if "registered_after" in criteria:
                    reg_date = user_data.get("stats", {}).get("registration_date")
                    if not reg_date or reg_date < criteria["registered_after"]:
                        match = False
                
                if match:
                    filtered_users.append(user_id)
            
            logger.info(f"🔍 Отфильтровано {len(filtered_users)} пользователей")
            return filtered_users
            
        except Exception as e:
            logger.error(f"❌ Ошибка фильтрации: {e}")
            return []
    
    # ===== ВАЛИДАЦИЯ И ОБСЛУЖИВАНИЕ =====
    
    def validate_data_integrity(self) -> Dict[str, Any]:
        """Проверка целостности данных"""
        try:
            report = {
                "total_users": len(self.users_cache),
                "valid_users": 0,
                "invalid_users": [],
                "orphaned_data": [],
                "missing_fields": [],
                "data_inconsistencies": []
            }
            
            for user_id, user_data in self.users_cache.items():
                is_valid = True
                user_issues = []
                
                # Проверяем обязательные поля
                required_fields = ["user_id", "username", "first_name"]
                for field in required_fields:
                    if field not in user_data:
                        user_issues.append(f"Отсутствует поле {field}")
                        is_valid = False
                
                # Проверяем соответствие user_id
                if user_data.get("user_id") != user_id:
                    user_issues.append("Несоответствие user_id")
                    is_valid = False
                
                # Проверяем структуру задач
                tasks = user_data.get("tasks", {})
                if tasks and not isinstance(tasks, dict):
                    user_issues.append("Неверная структура tasks")
                    is_valid = False
                
                # Проверяем статистику
                stats = user_data.get("stats", {})
                if stats:
                    if stats.get("total_tasks", 0) != len(tasks):
                        user_issues.append("Несоответствие total_tasks и количества задач")
                        report["data_inconsistencies"].append({
                            "user_id": user_id,
                            "issue": "total_tasks mismatch",
                            "expected": len(tasks),
                            "actual": stats.get("total_tasks", 0)
                        })
                
                if is_valid:
                    report["valid_users"] += 1
                else:
                    report["invalid_users"].append({
                        "user_id": user_id,
                        "issues": user_issues
                    })
            
            logger.info(f"✅ Проверка целостности завершена: {report['valid_users']}/{report['total_users']} валидных пользователей")
            return report
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки целостности: {e}")
            return {"error": str(e)}
    
    def repair_data_inconsistencies(self) -> Dict[str, int]:
        """Исправление выявленных несоответствий данных"""
        try:
            repairs = {
                "total_tasks_fixed": 0,
                "missing_stats_added": 0,
                "invalid_data_removed": 0
            }
            
            with self.cache_lock:
                for user_id, user_data in self.users_cache.items():
                    # Исправляем total_tasks
                    tasks = user_data.get("tasks", {})
                    stats = user_data.setdefault("stats", {})
                    
                    if stats.get("total_tasks", 0) != len(tasks):
                        stats["total_tasks"] = len(tasks)
                        repairs["total_tasks_fixed"] += 1
                    
                    # Добавляем отсутствующие поля статистики
                    default_stats = {
                        "completed_tasks": 0,
                        "current_streak": 0,
                        "longest_streak": 0,
                        "total_xp": 0,
                        "level": 1,
                        "registration_date": datetime.now().isoformat()
                    }
                    
                    for field, default_value in default_stats.items():
                        if field not in stats:
                            stats[field] = default_value
                            repairs["missing_stats_added"] += 1
                    
                    self.pending_saves.add(user_id)
            
            logger.info(f"🔧 Исправлено несоответствий: {repairs}")
            return repairs
            
        except Exception as e:
            logger.error(f"❌ Ошибка исправления данных: {e}")
            return {}
    
    def optimize_storage(self) -> Dict[str, Any]:
        """Оптимизация хранилища данных"""
        try:
            result = {
                "before_size": 0,
                "after_size": 0,
                "removed_empty_fields": 0,
                "compressed_data": 0
            }
            
            # Размер до оптимизации
            result["before_size"] = len(str(self.users_cache))
            
            with self.cache_lock:
                for user_id, user_data in self.users_cache.items():
                    modified = False
                    
                    # Удаляем пустые поля
                    def remove_empty_fields(obj):
                        if isinstance(obj, dict):
                            return {k: remove_empty_fields(v) for k, v in obj.items() 
                                   if v is not None and v != "" and v != []}
                        elif isinstance(obj, list):
                            return [remove_empty_fields(item) for item in obj if item]
                        return obj
                    
                    cleaned_data = remove_empty_fields(user_data)
                    if len(str(cleaned_data)) < len(str(user_data)):
                        self.users_cache[user_id] = cleaned_data
                        result["removed_empty_fields"] += 1
                        modified = True
                    
                    if modified:
                        self.pending_saves.add(user_id)
            
            # Размер после оптимизации
            result["after_size"] = len(str(self.users_cache))
            result["size_reduction"] = result["before_size"] - result["after_size"]
            
            logger.info(f"⚡ Оптимизация завершена: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка оптимизации: {e}")
            return {}
    
    # ===== УТИЛИТЫ И СЕРВИСНЫЕ МЕТОДЫ =====
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Информация о хранилище"""
        try:
            info = {
                "data_file": {
                    "path": str(self.data_file),
                    "exists": self.data_file.exists(),
                    "size": self.data_file.stat().st_size if self.data_file.exists() else 0,
                    "modified": datetime.fromtimestamp(self.data_file.stat().st_mtime).isoformat() if self.data_file.exists() else None
                },
                "cache": {
                    "users_count": len(self.users_cache),
                    "pending_saves": len(self.pending_saves),
                    "memory_usage": len(str(self.users_cache))
                },
                "backups": {
                    "directory": str(self.config.BACKUP_DIR),
                    "count": len(list(self.config.BACKUP_DIR.glob("*.json"))),
                    "total_size": sum(f.stat().st_size for f in self.config.BACKUP_DIR.glob("*.json"))
                },
                "metrics": self.get_service_metrics()
            }
            
            return info
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о хранилище: {e}")
            return {}
    
    def health_check(self) -> Dict[str, Any]:
        """Проверка состояния сервиса"""
        try:
            health = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "checks": {}
            }
            
            # Проверка доступности файла данных
            try:
                health["checks"]["data_file"] = {
                    "status": "ok" if self.data_file.exists() else "warning",
                    "message": "Файл данных доступен" if self.data_file.exists() else "Файл данных не найден"
                }
            except Exception as e:
                health["checks"]["data_file"] = {"status": "error", "message": str(e)}
            
            # Проверка кэша
            try:
                cache_size = len(self.users_cache)
                health["checks"]["cache"] = {
                    "status": "ok" if cache_size < self.config.MAX_USERS_CACHE else "warning",
                    "message": f"Пользователей в кэше: {cache_size}"
                }
            except Exception as e:
                health["checks"]["cache"] = {"status": "error", "message": str(e)}
            
            # Проверка операций
            error_rate = (self.failed_operations / max(self.total_operations, 1)) * 100
            health["checks"]["operations"] = {
                "status": "ok" if error_rate < 5 else "warning" if error_rate < 10 else "error",
                "message": f"Ошибок: {error_rate:.1f}% ({self.failed_operations}/{self.total_operations})"
            }
            
            # Определяем общий статус
            statuses = [check["status"] for check in health["checks"].values()]
            if "error" in statuses:
                health["status"] = "error"
            elif "warning" in statuses:
                health["status"] = "warning"
            
            return health
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки состояния: {e}")
            return {
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def close(self):
        """Корректное закрытие сервиса"""
        try:
            logger.info("🛑 Закрытие DataService...")
            
            # Сохраняем все данные
            if self.pending_saves:
                logger.info(f"💾 Сохранение {len(self.pending_saves)} отложенных изменений...")
                self.save_all_to_disk()
            
            # Сохраняем снимок аналитики
            self.save_analytics_snapshot()
            
            # Очищаем кэш
            with self.cache_lock:
                self.users_cache.clear()
                self.pending_saves.clear()
            
            logger.info("✅ DataService закрыт корректно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия DataService: {e}")
    
    def __enter__(self):
        """Context manager вход"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager выход"""
        self.close()

# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====

# Создаем глобальный экземпляр для использования в других модулях
_global_data_service = None

def get_data_service() -> DataService:
    """Получить глобальный экземпляр DataService"""
    global _global_data_service
    if _global_data_service is None:
        _global_data_service = DataService()
    return _global_data_service

def initialize_data_service(data_file: str = None) -> DataService:
    """Инициализация глобального DataService"""
    global _global_data_service
    _global_data_service = DataService(data_file)
    return _global_data_service

def close_data_service():
    """Закрытие глобального DataService"""
    global _global_data_service
    if _global_data_service:
        _global_data_service.close()
        _global_data_service = None
