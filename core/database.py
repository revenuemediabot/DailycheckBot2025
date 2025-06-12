#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Bot v4.0 - Enhanced Database Manager
Система управления данными с кэшированием и резервным копированием

Автор: AI Assistant
Версия: 4.0.1
Дата: 2025-06-12
"""

import os
import json
import asyncio
import threading
import time
import shutil
import gzip
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Callable, Set
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import logging

# Проверяем доступность дополнительных библиотек
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# Импорты из нашего проекта
from core.models import User, ValidationError
from config import config

logger = logging.getLogger(__name__)

# ===== EXCEPTIONS =====

class DatabaseError(Exception):
    """Базовое исключение для ошибок базы данных"""
    pass

class DatabaseConnectionError(DatabaseError):
    """Ошибка подключения к базе данных"""
    pass

class DatabaseCorruptionError(DatabaseError):
    """Ошибка повреждения данных"""
    pass

class DatabaseLockError(DatabaseError):
    """Ошибка блокировки базы данных"""
    pass

# ===== HELPER CLASSES =====

@dataclass
class DatabaseStats:
    """Статистика базы данных"""
    total_users: int = 0
    total_tasks: int = 0
    total_completions: int = 0
    database_size_mb: float = 0.0
    cache_hit_rate: float = 0.0
    last_backup: Optional[str] = None
    last_save: Optional[str] = None
    save_count: int = 0
    load_count: int = 0
    error_count: int = 0
    uptime_seconds: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_users': self.total_users,
            'total_tasks': self.total_tasks,
            'total_completions': self.total_completions,
            'database_size_mb': round(self.database_size_mb, 2),
            'cache_hit_rate': round(self.cache_hit_rate, 2),
            'last_backup': self.last_backup,
            'last_save': self.last_save,
            'save_count': self.save_count,
            'load_count': self.load_count,
            'error_count': self.error_count,
            'uptime_hours': round(self.uptime_seconds / 3600, 2)
        }

@dataclass
class CacheStats:
    """Статистика кэша"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 1000
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

class DatabaseCache:
    """Умный кэш для пользователей с LRU eviction"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: Dict[int, User] = {}
        self.access_times: Dict[int, float] = {}
        self.dirty_users: Set[int] = set()  # Пользователи, требующие сохранения
        self.stats = CacheStats(max_size=max_size)
        self._lock = threading.RLock()
    
    def get(self, user_id: int) -> Optional[User]:
        """Получить пользователя из кэша"""
        with self._lock:
            if user_id in self.cache:
                self.access_times[user_id] = time.time()
                self.stats.hits += 1
                return self.cache[user_id]
            else:
                self.stats.misses += 1
                return None
    
    def put(self, user: User) -> None:
        """Добавить пользователя в кэш"""
        with self._lock:
            user_id = user.user_id
            
            # Если кэш переполнен, удаляем старые записи
            if len(self.cache) >= self.max_size and user_id not in self.cache:
                self._evict_lru()
            
            self.cache[user_id] = user
            self.access_times[user_id] = time.time()
            self.stats.size = len(self.cache)
    
    def mark_dirty(self, user_id: int) -> None:
        """Отметить пользователя как требующего сохранения"""
        with self._lock:
            if user_id in self.cache:
                self.dirty_users.add(user_id)
    
    def get_dirty_users(self) -> List[User]:
        """Получить всех пользователей, требующих сохранения"""
        with self._lock:
            dirty_list = []
            for user_id in list(self.dirty_users):
                if user_id in self.cache:
                    dirty_list.append(self.cache[user_id])
            return dirty_list
    
    def clear_dirty(self, user_id: int) -> None:
        """Очистить флаг "грязности" пользователя"""
        with self._lock:
            self.dirty_users.discard(user_id)
    
    def clear_all_dirty(self) -> None:
        """Очистить все флаги "грязности"""
        with self._lock:
            self.dirty_users.clear()
    
    def remove(self, user_id: int) -> bool:
        """Удалить пользователя из кэша"""
        with self._lock:
            if user_id in self.cache:
                del self.cache[user_id]
                del self.access_times[user_id]
                self.dirty_users.discard(user_id)
                self.stats.size = len(self.cache)
                return True
            return False
    
    def clear(self) -> None:
        """Очистить весь кэш"""
        with self._lock:
            self.cache.clear()
            self.access_times.clear()
            self.dirty_users.clear()
            self.stats.size = 0
    
    def _evict_lru(self) -> None:
        """Удалить наименее недавно использованного пользователя"""
        if not self.access_times:
            return
        
        # Находим пользователя с самым старым временем доступа
        lru_user_id = min(self.access_times.keys(), key=lambda uid: self.access_times[uid])
        
        # Если пользователь "грязный", сохраняем его
        if lru_user_id in self.dirty_users:
            logger.warning(f"Evicting dirty user {lru_user_id} from cache - data may be lost!")
        
        self.remove(lru_user_id)
        self.stats.evictions += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        with self._lock:
            return {
                'size': self.stats.size,
                'max_size': self.stats.max_size,
                'hits': self.stats.hits,
                'misses': self.stats.misses,
                'evictions': self.stats.evictions,
                'hit_rate': self.stats.hit_rate,
                'dirty_count': len(self.dirty_users)
            }

class BackupManager:
    """Менеджер резервных копий"""
    
    def __init__(self, backup_dir: Path, max_backups: int = 10):
        self.backup_dir = backup_dir
        self.max_backups = max_backups
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, source_file: Path, compressed: bool = True) -> Optional[Path]:
        """Создать резервную копию"""
        try:
            if not source_file.exists():
                logger.warning(f"Source file {source_file} does not exist for backup")
                return None
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"backup_{timestamp}.json"
            
            if compressed:
                backup_name += ".gz"
                backup_path = self.backup_dir / backup_name
                
                with open(source_file, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        f_out.writelines(f_in)
            else:
                backup_path = self.backup_dir / backup_name
                shutil.copy2(source_file, backup_path)
            
            logger.info(f"Backup created: {backup_path}")
            self._cleanup_old_backups()
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None
    
    def restore_backup(self, backup_path: Path, target_file: Path) -> bool:
        """Восстановить из резервной копии"""
        try:
            if not backup_path.exists():
                logger.error(f"Backup file {backup_path} does not exist")
                return False
            
            # Создаем backup текущего файла перед восстановлением
            if target_file.exists():
                safety_backup = target_file.with_suffix('.safety_backup.json')
                shutil.copy2(target_file, safety_backup)
                logger.info(f"Safety backup created: {safety_backup}")
            
            if backup_path.name.endswith('.gz'):
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(target_file, 'wb') as f_out:
                        f_out.writelines(f_in)
            else:
                shutil.copy2(backup_path, target_file)
            
            logger.info(f"Backup restored from {backup_path} to {target_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """Получить список всех резервных копий"""
        backups = []
        
        for backup_file in self.backup_dir.glob("backup_*.json*"):
            try:
                stat = backup_file.stat()
                backups.append({
                    'name': backup_file.name,
                    'path': str(backup_file),
                    'size_mb': stat.st_size / (1024 * 1024),
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'compressed': backup_file.name.endswith('.gz')
                })
            except Exception as e:
                logger.warning(f"Failed to get info for backup {backup_file}: {e}")
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def _cleanup_old_backups(self) -> None:
        """Удалить старые резервные копии"""
        try:
            backups = list(self.backup_dir.glob("backup_*.json*"))
            backups.sort(key=lambda x: x.stat().st_ctime, reverse=True)
            
            # Удаляем лишние backup'ы
            for backup in backups[self.max_backups:]:
                backup.unlink()
                logger.info(f"Removed old backup: {backup}")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")

class DatabaseMigration:
    """Система миграций базы данных"""
    
    VERSION_KEY = "__database_version__"
    CURRENT_VERSION = "4.0.1"
    
    @classmethod
    def get_version(cls, data: Dict[str, Any]) -> str:
        """Получить версию базы данных"""
        return data.get(cls.VERSION_KEY, "1.0.0")
    
    @classmethod
    def set_version(cls, data: Dict[str, Any], version: str) -> None:
        """Установить версию базы данных"""
        data[cls.VERSION_KEY] = version
    
    @classmethod
    def needs_migration(cls, data: Dict[str, Any]) -> bool:
        """Проверить, нужна ли миграция"""
        current_version = cls.get_version(data)
        return current_version != cls.CURRENT_VERSION
    
    @classmethod
    def migrate(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить миграцию данных"""
        current_version = cls.get_version(data)
        logger.info(f"Migrating database from version {current_version} to {cls.CURRENT_VERSION}")
        
        try:
            # Миграция с версии 1.0.0 до 4.0.1
            if current_version == "1.0.0":
                data = cls._migrate_from_1_0_0(data)
            
            # Добавить другие миграции здесь при необходимости
            
            cls.set_version(data, cls.CURRENT_VERSION)
            logger.info(f"Database migration completed successfully")
            return data
            
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
            raise DatabaseError(f"Migration failed: {e}")
    
    @classmethod
    def _migrate_from_1_0_0(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Миграция с версии 1.0.0"""
        migrated_users = {}
        
        for user_id_str, user_data in data.items():
            if user_id_str.startswith("__"):  # Системные ключи
                continue
            
            try:
                # Добавляем новые поля, если их нет
                if 'created_at' not in user_data:
                    user_data['created_at'] = datetime.now().isoformat()
                
                if 'last_seen' not in user_data:
                    user_data['last_seen'] = None
                
                if 'is_premium' not in user_data:
                    user_data['is_premium'] = False
                
                if 'subscription_type' not in user_data:
                    user_data['subscription_type'] = "free"
                
                if 'preferences' not in user_data:
                    user_data['preferences'] = {}
                
                # Мигрируем настройки
                if 'settings' in user_data:
                    settings = user_data['settings']
                    
                    # Добавляем новые настройки
                    if 'compact_view' not in settings:
                        settings['compact_view'] = False
                    
                    if 'dark_mode' not in settings:
                        settings['dark_mode'] = False
                    
                    if 'data_export_format' not in settings:
                        settings['data_export_format'] = "json"
                    
                    if 'privacy_level' not in settings:
                        settings['privacy_level'] = "friends"
                
                # Мигрируем статистику
                if 'stats' in user_data:
                    stats = user_data['stats']
                    
                    # Добавляем новые поля статистики
                    if 'tasks_by_category' not in stats:
                        stats['tasks_by_category'] = {}
                    
                    if 'tasks_by_priority' not in stats:
                        stats['tasks_by_priority'] = {}
                    
                    if 'days_active' not in stats:
                        stats['days_active'] = 0
                    
                    if 'perfect_days' not in stats:
                        stats['perfect_days'] = 0
                    
                    if 'social_interactions' not in stats:
                        stats['social_interactions'] = 0
                
                # Мигрируем задачи
                if 'tasks' in user_data:
                    for task_id, task_data in user_data['tasks'].items():
                        if 'last_modified' not in task_data:
                            task_data['last_modified'] = datetime.now().isoformat()
                        
                        if 'archived_at' not in task_data:
                            task_data['archived_at'] = None
                        
                        if 'color' not in task_data:
                            task_data['color'] = None
                        
                        if 'icon' not in task_data:
                            task_data['icon'] = None
                
                migrated_users[user_id_str] = user_data
                
            except Exception as e:
                logger.warning(f"Failed to migrate user {user_id_str}: {e}")
                # Сохраняем пользователя как есть
                migrated_users[user_id_str] = user_data
        
        return migrated_users

class DatabaseManager:
    """Улучшенный менеджер базы данных с async поддержкой"""
    
    def __init__(self, data_file: Optional[Path] = None):
        # Инициализация путей
        self.data_file = data_file or config.database.path
        self.backup_manager = BackupManager(config.database.backup_dir, config.database.max_backups)
        
        # Кэш и блокировки
        self.cache = DatabaseCache(config.security.max_users_cache)
        self.file_lock = threading.RLock()
        self.save_lock = asyncio.Lock()
        
        # Статистика и мониторинг
        self.stats = DatabaseStats()
        self.start_time = time.time()
        
        # Пул потоков для I/O операций
        self.executor = ThreadPoolExecutor(max_workers=config.max_workers)
        
        # Планировщик для автоматических операций
        self.scheduler = None
        if SCHEDULER_AVAILABLE and config.database.auto_backup:
            self.scheduler = AsyncIOScheduler()
        
        # Флаги состояния
        self.is_initialized = False
        self.is_shutting_down = False
        
        # Callbacks
        self.save_callbacks: List[Callable] = []
        self.load_callbacks: List[Callable] = []
        
        # Инициализация
        self._initialize()
    
    def _initialize(self) -> None:
        """Инициализация базы данных"""
        try:
            logger.info("Initializing database manager...")
            
            # Создаем директории
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Загружаем данные
            self._load_all_users_sync()
            
            # Запускаем планировщик
            self._start_scheduler()
            
            self.is_initialized = True
            logger.info(f"Database manager initialized with {self.cache.stats.size} users in cache")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise DatabaseConnectionError(f"Database initialization failed: {e}")
    
    def _start_scheduler(self) -> None:
        """Запуск планировщика задач"""
        if not self.scheduler:
            return
        
        try:
            # Автоматическое сохранение каждые 5 минут
            self.scheduler.add_job(
                self._periodic_save,
                IntervalTrigger(minutes=5),
                id='periodic_save',
                replace_existing=True
            )
            
            # Автоматическое резервное копирование
            if config.database.auto_backup:
                self.scheduler.add_job(
                    self._periodic_backup,
                    IntervalTrigger(hours=config.database.backup_interval_hours),
                    id='periodic_backup',
                    replace_existing=True
                )
            
            # Очистка кэша каждый час
            self.scheduler.add_job(
                self._cleanup_cache,
                IntervalTrigger(hours=1),
                id='cleanup_cache',
                replace_existing=True
            )
            
            self.scheduler.start()
            logger.info("Database scheduler started")
            
        except Exception as e:
            logger.warning(f"Failed to start scheduler: {e}")
    
    async def _periodic_save(self) -> None:
        """Периодическое сохранение"""
        try:
            if self.cache.dirty_users:
                await self.save_dirty_users()
                logger.debug(f"Periodic save completed")
        except Exception as e:
            logger.error(f"Periodic save failed: {e}")
    
    async def _periodic_backup(self) -> None:
        """Периодическое резервное копирование"""
        try:
            await self.create_backup()
            logger.info("Periodic backup completed")
        except Exception as e:
            logger.error(f"Periodic backup failed: {e}")
    
    async def _cleanup_cache(self) -> None:
        """Очистка кэша от неактивных пользователей"""
        try:
            # Находим пользователей, которые не были активны более 24 часов
            current_time = time.time()
            inactive_users = []
            
            for user_id, access_time in self.cache.access_times.items():
                if current_time - access_time > 24 * 3600:  # 24 часа
                    if user_id not in self.cache.dirty_users:  # Не удаляем несохраненных
                        inactive_users.append(user_id)
            
            # Удаляем неактивных пользователей
            for user_id in inactive_users[:10]:  # Максимум 10 за раз
                self.cache.remove(user_id)
            
            if inactive_users:
                logger.debug(f"Cleaned {len(inactive_users)} inactive users from cache")
                
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
    
    def _load_all_users_sync(self) -> None:
        """Синхронная загрузка всех пользователей"""
        try:
            if not self.data_file.exists():
                logger.info("Database file does not exist, starting with empty database")
                self.stats.load_count += 1
                return
            
            with self.file_lock:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Проверяем и выполняем миграцию если нужно
                if DatabaseMigration.needs_migration(data):
                    logger.info("Database migration required")
                    # Создаем backup перед миграцией
                    self.backup_manager.create_backup(self.data_file)
                    data = DatabaseMigration.migrate(data)
                    # Сохраняем мигрированные данные
                    self._save_data_sync(data)
                
                # Загружаем пользователей в кэш
                loaded_count = 0
                for user_id_str, user_data in data.items():
                    if user_id_str.startswith("__"):  # Пропускаем системные ключи
                        continue
                    
                    try:
                        user_id = int(user_id_str)
                        user = User.from_dict(user_data)
                        self.cache.put(user)
                        loaded_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to load user {user_id_str}: {e}")
                        self.stats.error_count += 1
                
                self.stats.total_users = loaded_count
                self.stats.load_count += 1
                self.stats.last_save = datetime.now().isoformat()
                
                # Подсчитываем статистику
                self._update_stats()
                
                logger.info(f"Loaded {loaded_count} users from database")
                
        except json.JSONDecodeError as e:
            logger.error(f"Database file is corrupted: {e}")
            self._handle_corruption()
        except Exception as e:
            logger.error(f"Failed to load database: {e}")
            raise DatabaseError(f"Failed to load database: {e}")
    
    def _handle_corruption(self) -> None:
        """Обработка повреждения базы данных"""
        logger.warning("Attempting to recover from database corruption...")
        
        # Пробуем восстановить из последнего backup'а
        backups = self.backup_manager.list_backups()
        
        for backup in backups:
            try:
                backup_path = Path(backup['path'])
                if self.backup_manager.restore_backup(backup_path, self.data_file):
                    logger.info(f"Successfully restored from backup: {backup['name']}")
                    self._load_all_users_sync()
                    return
            except Exception as e:
                logger.warning(f"Failed to restore from backup {backup['name']}: {e}")
        
        # Если восстановление не удалось, создаем пустую базу
        logger.warning("Could not restore from any backup, starting with empty database")
        self.cache.clear()
        self.stats = DatabaseStats()
    
    def _save_data_sync(self, data: Dict[str, Any]) -> None:
        """Синхронное сохранение данных"""
        with self.file_lock:
            # Атомарное сохранение через временный файл
            temp_file = self.data_file.with_suffix('.tmp')
            
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # Проверяем целостность записанного файла
                with open(temp_file, 'r', encoding='utf-8') as f:
                    json.load(f)  # Проверка парсинга
                
                # Заменяем основной файл
                if self.data_file.exists():
                    backup_file = self.data_file.with_suffix('.prev')
                    shutil.move(self.data_file, backup_file)
                
                shutil.move(temp_file, self.data_file)
                
                # Удаляем предыдущую версию
                backup_file = self.data_file.with_suffix('.prev')
                if backup_file.exists():
                    backup_file.unlink()
                
                self.stats.save_count += 1
                self.stats.last_save = datetime.now().isoformat()
                
            except Exception as e:
                # Очищаем временный файл в случае ошибки
                if temp_file.exists():
                    temp_file.unlink()
                raise
    
    def _update_stats(self) -> None:
        """Обновление статистики базы данных"""
        try:
            total_tasks = 0
            total_completions = 0
            
            for user in self.cache.cache.values():
                total_tasks += len(user.tasks)
                for task in user.tasks.values():
                    total_completions += len([c for c in task.completions if c.completed])
            
            self.stats.total_tasks = total_tasks
            self.stats.total_completions = total_completions
            self.stats.uptime_seconds = int(time.time() - self.start_time)
            
            # Размер файла базы данных
            if self.data_file.exists():
                self.stats.database_size_mb = self.data_file.stat().st_size / (1024 * 1024)
            
            # Статистика кэша
            cache_stats = self.cache.get_stats()
            self.stats.cache_hit_rate = cache_stats['hit_rate']
            
        except Exception as e:
            logger.warning(f"Failed to update database stats: {e}")
    
    # ===== PUBLIC API =====
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        if not self.is_initialized:
            raise DatabaseError("Database not initialized")
        
        # Сначала проверяем кэш
        user = self.cache.get(user_id)
        if user:
            return user
        
        # Пользователь не найден ни в кэше, ни в базе
        return None
    
    def get_or_create_user(self, user_id: int, **kwargs) -> User:
        """Получить пользователя или создать нового"""
        if not self.is_initialized:
            raise DatabaseError("Database not initialized")
        
        # Проверяем кэш
        user = self.cache.get(user_id)
        if user:
            # Обновляем данные пользователя
            if 'username' in kwargs:
                user.username = kwargs['username']
            if 'first_name' in kwargs:
                user.first_name = kwargs['first_name']
            if 'last_name' in kwargs:
                user.last_name = kwargs['last_name']
            
            user.update_activity()
            self.cache.mark_dirty(user_id)
            return user
        
        # Создаем нового пользователя
        try:
            user = User.create(
                user_id=user_id,
                username=kwargs.get('username'),
                first_name=kwargs.get('first_name'),
                last_name=kwargs.get('last_name')
            )
            
            self.cache.put(user)
            self.cache.mark_dirty(user_id)
            self.stats.total_users += 1
            
            logger.info(f"Created new user: {user.display_name} (ID: {user_id})")
            return user
            
        except ValidationError as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            raise DatabaseError(f"Failed to create user: {e}")
    
    def save_user(self, user: User) -> None:
        """Отметить пользователя для сохранения"""
        if not self.is_initialized:
            raise DatabaseError("Database not initialized")
        
        self.cache.put(user)  # Обновляем в кэше
        self.cache.mark_dirty(user.user_id)
    
    def remove_user(self, user_id: int) -> bool:
        """Удалить пользователя"""
        if not self.is_initialized:
            raise DatabaseError("Database not initialized")
        
        if self.cache.remove(user_id):
            self.stats.total_users = max(0, self.stats.total_users - 1)
            logger.info(f"Removed user {user_id}")
            return True
        return False
    
    def get_all_users(self) -> List[User]:
        """Получить всех пользователей"""
        if not self.is_initialized:
            raise DatabaseError("Database not initialized")
        
        return list(self.cache.cache.values())
    
    def get_users_count(self) -> int:
        """Получить количество пользователей"""
        return len(self.cache.cache)
    
    def search_users(self, query: str, limit: int = 10) -> List[User]:
        """Поиск пользователей по имени/username"""
        if not self.is_initialized:
            raise DatabaseError("Database not initialized")
        
        query = query.lower().strip()
        if not query:
            return []
        
        results = []
        for user in self.cache.cache.values():
            if len(results) >= limit:
                break
            
            # Поиск по имени и username
            if (user.first_name and query in user.first_name.lower()) or \
               (user.username and query in user.username.lower()) or \
               (user.display_name.lower().find(query) != -1):
                results.append(user)
        
        return results
    
    async def save_dirty_users(self) -> bool:
        """Сохранить всех пользователей, требующих сохранения"""
        if not self.is_initialized or self.is_shutting_down:
            return False
        
        dirty_users = self.cache.get_dirty_users()
        if not dirty_users:
            return True
        
        try:
            async with self.save_lock:
                # Подготавливаем данные для сохранения
                data = {}
                
                # Добавляем системную информацию
                DatabaseMigration.set_version(data, DatabaseMigration.CURRENT_VERSION)
                
                # Добавляем всех пользователей из кэша
                for user in self.cache.cache.values():
                    data[str(user.user_id)] = user.to_dict()
                
                # Сохраняем асинхронно
                await asyncio.get_event_loop().run_in_executor(
                    self.executor, self._save_data_sync, data
                )
                
                # Очищаем флаги dirty
                self.cache.clear_all_dirty()
                
                # Обновляем статистику
                self._update_stats()
                
                # Вызываем callbacks
                for callback in self.save_callbacks:
                    try:
                        await callback()
                    except Exception as e:
                        logger.warning(f"Save callback failed: {e}")
                
                logger.debug(f"Saved {len(dirty_users)} dirty users")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save users: {e}")
            self.stats.error_count += 1
            return False
    
    async def save_all_users(self) -> bool:
        """Принудительное сохранение всех пользователей"""
        if not self.is_initialized:
            return False
        
        # Помечаем всех пользователей как dirty
        for user_id in self.cache.cache.keys():
            self.cache.mark_dirty(user_id)
        
        return await self.save_dirty_users()
    
    async def create_backup(self, compressed: bool = True) -> Optional[Path]:
        """Создать резервную копию"""
        try:
            if not self.data_file.exists():
                logger.warning("Cannot create backup: database file does not exist")
                return None
            
            backup_path = await asyncio.get_event_loop().run_in_executor(
                self.executor, self.backup_manager.create_backup, self.data_file, compressed
            )
            
            if backup_path:
                self.stats.last_backup = datetime.now().isoformat()
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None
    
    async def restore_backup(self, backup_path: Path) -> bool:
        """Восстановить из резервной копии"""
        try:
            # Создаем safety backup текущих данных
            await self.create_backup()
            
            # Восстанавливаем данные
            success = await asyncio.get_event_loop().run_in_executor(
                self.executor, self.backup_manager.restore_backup, backup_path, self.data_file
            )
            
            if success:
                # Перезагружаем данные
                self.cache.clear()
                await asyncio.get_event_loop().run_in_executor(
                    self.executor, self._load_all_users_sync
                )
                
                logger.info(f"Successfully restored from backup: {backup_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False
    
    def get_backups(self) -> List[Dict[str, Any]]:
        """Получить список резервных копий"""
        return self.backup_manager.list_backups()
    
    def export_user_data(self, user_id: int, format: str = "json") -> Optional[bytes]:
        """Экспорт данных пользователя"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        try:
            if format.lower() == "json":
                data = user.to_dict()
                export_data = {
                    "export_info": {
                        "format": "json",
                        "version": DatabaseMigration.CURRENT_VERSION,
                        "exported_at": datetime.now().isoformat(),
                        "user_id": user_id
                    },
                    "user_data": data
                }
                return json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8')
            
            elif format.lower() == "csv" and PANDAS_AVAILABLE:
                # Экспорт задач в CSV
                tasks_data = []
                for task in user.tasks.values():
                    for completion in task.completions:
                        tasks_data.append({
                            "task_id": task.task_id,
                            "title": task.title,
                            "category": task.category,
                            "priority": task.priority,
                            "status": task.status,
                            "date": completion.date,
                            "completed": completion.completed,
                            "time_spent": completion.time_spent,
                            "note": completion.note,
                            "streak": task.current_streak,
                            "xp_value": task.xp_value
                        })
                
                if tasks_data:
                    df = pd.DataFrame(tasks_data)
                    return df.to_csv(index=False).encode('utf-8')
                else:
                    return "task_id,title,category,priority,status,date,completed,time_spent,note,streak,xp_value\n".encode('utf-8')
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to export user data: {e}")
            return None
    
    def add_save_callback(self, callback: Callable) -> None:
        """Добавить callback для событий сохранения"""
        self.save_callbacks.append(callback)
    
    def add_load_callback(self, callback: Callable) -> None:
        """Добавить callback для событий загрузки"""
        self.load_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику базы данных"""
        self._update_stats()
        
        return {
            "database": self.stats.to_dict(),
            "cache": self.cache.get_stats(),
            "backups": len(self.backup_manager.list_backups()),
            "scheduler_running": self.scheduler.running if self.scheduler else False
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Получить статус здоровья базы данных"""
        try:
            stats = self.get_stats()
            
            # Определяем статус здоровья
            health_score = 100.0
            issues = []
            
            # Проверяем частоту ошибок
            if self.stats.error_count > 10:
                health_score -= 20
                issues.append("High error count")
            
            # Проверяем hit rate кэша
            if stats['cache']['hit_rate'] < 80:
                health_score -= 10
                issues.append("Low cache hit rate")
            
            # Проверяем размер базы данных
            if stats['database']['database_size_mb'] > 100:
                health_score -= 5
                issues.append("Large database size")
            
            # Проверяем время последнего backup'а
            if self.stats.last_backup:
                last_backup = datetime.fromisoformat(self.stats.last_backup)
                if (datetime.now() - last_backup).days > 1:
                    health_score -= 10
                    issues.append("Old backup")
            else:
                health_score -= 15
                issues.append("No backups")
            
            status = "healthy" if health_score >= 90 else "warning" if health_score >= 70 else "critical"
            
            return {
                "status": status,
                "health_score": round(health_score, 1),
                "issues": issues,
                "stats": stats,
                "uptime_hours": round(self.stats.uptime_seconds / 3600, 2),
                "initialized": self.is_initialized
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "initialized": self.is_initialized
            }
    
    async def shutdown(self) -> None:
        """Корректное завершение работы"""
        if self.is_shutting_down:
            return
        
        self.is_shutting_down = True
        logger.info("Shutting down database manager...")
        
        try:
            # Останавливаем планировщик
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown(wait=False)
            
            # Сохраняем все данные
            await self.save_all_users()
            
            # Создаем финальный backup
            await self.create_backup()
            
            # Очищаем кэш
            self.cache.clear()
            
            # Закрываем пул потоков
            self.executor.shutdown(wait=True)
            
            logger.info("Database manager shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during database shutdown: {e}")

# ===== CONVENIENCE FUNCTIONS =====

def create_database_manager(data_file: Optional[Path] = None) -> DatabaseManager:
    """Создать менеджер базы данных"""
    return DatabaseManager(data_file)

async def migrate_database(source_file: Path, target_file: Path) -> bool:
    """Мигрировать базу данных"""
    try:
        # Загружаем исходные данные
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Выполняем миграцию
        if DatabaseMigration.needs_migration(data):
            data = DatabaseMigration.migrate(data)
        
        # Сохраняем в новый файл
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Database migrated from {source_file} to {target_file}")
        return True
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        return False

# ===== EXPORT =====

__all__ = [
    'DatabaseError',
    'DatabaseConnectionError', 
    'DatabaseCorruptionError',
    'DatabaseLockError',
    'DatabaseStats',
    'CacheStats',
    'DatabaseCache',
    'BackupManager',
    'DatabaseMigration',
    'DatabaseManager',
    'create_database_manager',
    'migrate_database'
]
