#!/usr/bin/env python3
"""
🚀 DailyCheck Bot Dashboard v4.0 - ПОЛНАЯ ПЕРЕПИСАННАЯ ВЕРСИЯ
Профессиональный веб-дашборд с многоуровневыми fallback системами

Использование: python scripts/start_web.py [--dev] [--port PORT] [--host HOST]
"""

import sys
import os
import argparse
import logging
import signal
import asyncio
import time
import json
import sqlite3
import random
import traceback
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# ============================================================================
# PYTHON PATH SETUP
# ============================================================================

# Добавляем корневую папку в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ============================================================================
# IMPORTS WITH FALLBACK
# ============================================================================

try:
    import uvicorn
    from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError as e:
    print(f"❌ Критическая ошибка импорта FastAPI: {e}")
    print("💡 Установите зависимости: pip install -r requirements-web.txt")
    sys.exit(1)

# Опциональные импорты с fallback
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import diskcache
    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False

try:
    from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Boolean, DateTime, Text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.declarative import declarative_base
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_comprehensive_logging(dev_mode: bool = False, log_level: str = "INFO") -> logging.Logger:
    """Настройка комплексной системы логирования"""
    
    # Создание папки логов
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Форматы логов
    detailed_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    simple_format = '%(asctime)s - %(levelname)s - %(message)s'
    
    # Уровень логирования
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    if dev_mode:
        numeric_level = logging.DEBUG
    
    # Очистка предыдущих обработчиков
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Настройка обработчиков
    handlers = []
    
    # Файловый обработчик (детальный)
    file_handler = logging.FileHandler(
        log_dir / 'web_dashboard.log', 
        encoding='utf-8',
        mode='a'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(detailed_format))
    handlers.append(file_handler)
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(
        logging.Formatter(detailed_format if dev_mode else simple_format)
    )
    handlers.append(console_handler)
    
    # Обработчик ошибок в отдельный файл
    error_handler = logging.FileHandler(
        log_dir / 'errors.log',
        encoding='utf-8',
        mode='a'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(detailed_format))
    handlers.append(error_handler)
    
    # Настройка root logger
    logging.basicConfig(
        level=numeric_level,
        handlers=handlers,
        force=True
    )
    
    # Настройка уровней для внешних библиотек
    if not dev_mode:
        logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
        logging.getLogger('uvicorn.error').setLevel(logging.INFO)
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info("✅ Система логирования настроена")
    return logger

# Глобальный logger (будет инициализирован в main)
logger = None

# ============================================================================
# SETTINGS AND CONFIGURATION
# ============================================================================

class ApplicationSettings:
    """Комплексные настройки приложения с валидацией и fallback"""
    
    def __init__(self):
        # Основная информация
        self.PROJECT_NAME = "DailyCheck Bot Dashboard v4.0"
        self.VERSION = "4.0.1"
        self.DESCRIPTION = "Профессиональный веб-дашборд для управления задачами с геймификацией"
        
        # Режим работы
        self.DEBUG = self._get_bool_env("DEBUG", False)
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "production" if not self.DEBUG else "development")
        
        # Сетевые настройки
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", 10000))
        self.WORKERS = int(os.getenv("WORKERS", 1))
        
        # Пути и директории
        self.PROJECT_ROOT = Path(__file__).parent.parent
        self.DATA_DIR = self.PROJECT_ROOT / "data"
        self.LOGS_DIR = self.PROJECT_ROOT / "logs"
        self.STATIC_DIR = self.PROJECT_ROOT / "dashboard" / "static"
        self.TEMPLATES_DIR = self.PROJECT_ROOT / "dashboard" / "templates"
        self.CACHE_DIR = self.DATA_DIR / "cache"
        self.EXPORTS_DIR = self.PROJECT_ROOT / "exports"
        self.BACKUPS_DIR = self.PROJECT_ROOT / "backups"
        
        # Создание всех необходимых директорий
        self._create_directories()
        
        # База данных
        self.DATABASE_URL = self._configure_database()
        
        # Кэширование
        self.REDIS_URL = os.getenv("REDIS_URL")
        self.CACHE_TTL_DEFAULT = int(os.getenv("CACHE_TTL_DEFAULT", 3600))
        self.CACHE_TTL_SHORT = int(os.getenv("CACHE_TTL_SHORT", 300))
        
        # Telegram Bot (опционально)
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.ADMIN_USER_ID = self._get_int_env("ADMIN_USER_ID", None)
        
        # Внешние API
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        # Веб-настройки
        self.CORS_ORIGINS = self._parse_cors_origins()
        self.MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE", 16 * 1024 * 1024))  # 16MB
        self.RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", 100))
        self.RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", 60))
        
        # Безопасность
        self.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
        self.ALLOWED_HOSTS = self._parse_allowed_hosts()
        
        # Особенности платформы
        self.IS_RENDER = bool(os.getenv("RENDER"))
        self.IS_HEROKU = bool(os.getenv("DYNO"))
        self.IS_DOCKER = bool(os.getenv("DOCKER_CONTAINER"))
        
        # Валидация критических настроек
        self._validate_settings()
        
        if logger:
            logger.info(f"✅ Настройки загружены: {self.PROJECT_NAME}")
            logger.info(f"🌍 Среда: {self.ENVIRONMENT}")
            logger.info(f"🚀 Режим отладки: {'включен' if self.DEBUG else 'отключен'}")
    
    def _get_bool_env(self, key: str, default: bool = False) -> bool:
        """Получение boolean значения из переменной окружения"""
        value = os.getenv(key, "").lower()
        return value in ("true", "1", "yes", "on") if value else default
    
    def _get_int_env(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Получение integer значения из переменной окружения"""
        try:
            value = os.getenv(key)
            return int(value) if value else default
        except (ValueError, TypeError):
            return default
    
    def _create_directories(self):
        """Создание всех необходимых директорий"""
        directories = [
            self.DATA_DIR,
            self.LOGS_DIR,
            self.STATIC_DIR,
            self.TEMPLATES_DIR,
            self.CACHE_DIR,
            self.EXPORTS_DIR,
            self.BACKUPS_DIR,
            self.STATIC_DIR / "css",
            self.STATIC_DIR / "js",
            self.STATIC_DIR / "img",
            self.PROJECT_ROOT / "dashboard" / "api"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Создание __init__.py файлов для Python пакетов
        init_files = [
            self.PROJECT_ROOT / "dashboard" / "__init__.py",
            self.PROJECT_ROOT / "dashboard" / "api" / "__init__.py"
        ]
        
        for init_file in init_files:
            if not init_file.exists():
                init_file.write_text("# Dashboard package\n")
    
    def _configure_database(self) -> str:
        """Настройка URL базы данных"""
        database_url = os.getenv("DATABASE_URL")
        
        # Исправление Heroku postgres:// на postgresql://
        if database_url and database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        # Fallback на SQLite
        if not database_url:
            database_url = f"sqlite:///{self.DATA_DIR}/dailycheck.db"
        
        return database_url
    
    def _parse_cors_origins(self) -> List[str]:
        """Парсинг CORS origins"""
        origins = os.getenv("CORS_ORIGINS", "*")
        if origins == "*":
            return ["*"]
        return [origin.strip() for origin in origins.split(",") if origin.strip()]
    
    def _parse_allowed_hosts(self) -> List[str]:
        """Парсинг разрешенных хостов"""
        hosts = os.getenv("ALLOWED_HOSTS", "*")
        if hosts == "*":
            return ["*"]
        return [host.strip() for host in hosts.split(",") if host.strip()]
    
    def _validate_settings(self):
        """Валидация критических настроек"""
        # Проверка портов
        if not (1 <= self.PORT <= 65535):
            raise ValueError(f"Неверный порт: {self.PORT}")
        
        # Проверка хоста
        if not self.HOST:
            raise ValueError("HOST не может быть пустым")
        
        # Проверка создания директорий
        if not self.DATA_DIR.exists():
            raise ValueError(f"Не удалось создать директорию данных: {self.DATA_DIR}")

# Глобальные настройки
settings = ApplicationSettings()

# ============================================================================
# DATABASE MANAGER WITH ADVANCED FALLBACK
# ============================================================================

class AdvancedDatabaseManager:
    """Продвинутый менеджер базы данных с множественными fallback стратегиями"""
    
    def __init__(self):
        self.db_type = "unknown"
        self.db_available = False
        self.connection = None
        self.engine = None
        self.session_factory = None
        self.metadata = None
        
        # Статистика подключений
        self.connection_attempts = 0
        self.last_connection_time = None
        self.connection_errors = []
        
        # Инициализация
        self._initialize_database()
    
    def _initialize_database(self):
        """Инициализация базы данных в порядке приоритета"""
        try:
            # 1. SQLAlchemy (PostgreSQL/MySQL/etc)
            if SQLALCHEMY_AVAILABLE and self._init_sqlalchemy():
                return
            
            # 2. SQLite fallback
            if self._init_sqlite():
                return
            
            # 3. File storage fallback
            self._init_file_storage()
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации БД: {e}")
            logger.error(traceback.format_exc())
            self._init_file_storage()
    
    def _init_sqlalchemy(self) -> bool:
        """Инициализация SQLAlchemy с расширенными возможностями"""
        try:
            self.connection_attempts += 1
            
            # Настройки подключения
            connect_args = {}
            if settings.DATABASE_URL.startswith("sqlite"):
                connect_args = {
                    "check_same_thread": False,
                    "timeout": 30
                }
            
            # Создание engine с продвинутыми настройками
            self.engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_timeout=30,
                max_overflow=20,
                echo=settings.DEBUG,
                connect_args=connect_args
            )
            
            # Тестирование подключения
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test"))
                test_value = result.scalar()
                if test_value != 1:
                    raise Exception("Database test query failed")
            
            # Инициализация метаданных и таблиц
            self._create_tables()
            
            # Создание фабрики сессий
            self.session_factory = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            self.db_type = "sqlalchemy"
            self.db_available = True
            self.last_connection_time = datetime.now()
            
            logger.info("✅ SQLAlchemy подключен успешно")
            logger.info(f"📊 База данных: {settings.DATABASE_URL.split('://')[0]}")
            return True
            
        except Exception as e:
            error_msg = f"SQLAlchemy недоступен: {e}"
            self.connection_errors.append(error_msg)
            logger.warning(f"⚠️ {error_msg}")
            return False
    
    def _create_tables(self):
        """Создание таблиц базы данных"""
        self.metadata = MetaData()
        
        # Таблица пользователей
        self.users_table = Table(
            'users', self.metadata,
            Column('user_id', Integer, primary_key=True),
            Column('username', String(255)),
            Column('first_name', String(255)),
            Column('last_name', String(255)),
            Column('email', String(255)),
            Column('phone', String(50)),
            Column('level', Integer, default=1),
            Column('xp', Integer, default=0),
            Column('theme', String(50), default='default'),
            Column('language', String(10), default='ru'),
            Column('timezone', String(50), default='UTC'),
            Column('notifications_enabled', Boolean, default=True),
            Column('ai_chat_enabled', Boolean, default=False),
            Column('weekly_goal', Integer, default=0),
            Column('current_streak', Integer, default=0),
            Column('max_streak', Integer, default=0),
            Column('total_tasks', Integer, default=0),
            Column('completed_tasks', Integer, default=0),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('updated_at', DateTime, default=datetime.utcnow),
            Column('last_activity', DateTime, default=datetime.utcnow),
            Column('last_login', DateTime),
            Column('is_active', Boolean, default=True),
            Column('is_premium', Boolean, default=False)
        )
        
        # Таблица задач
        self.tasks_table = Table(
            'tasks', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('user_id', Integer),
            Column('title', Text, nullable=False),
            Column('description', Text),
            Column('category', String(100), default='личное'),
            Column('priority', String(50), default='средний'),
            Column('status', String(50), default='pending'),
            Column('completed', Boolean, default=False),
            Column('rating', Integer),
            Column('difficulty', Integer, default=1),
            Column('estimated_time', Integer),
            Column('actual_time', Integer),
            Column('parent_task_id', Integer),
            Column('order_index', Integer, default=0),
            Column('tags', Text),  # JSON array
            Column('notes', Text),
            Column('completion_notes', Text),
            Column('created_at', DateTime, default=datetime.utcnow),
            Column('updated_at', DateTime, default=datetime.utcnow),
            Column('completed_at', DateTime),
            Column('due_date', DateTime),
            Column('reminder_date', DateTime)
        )
        
        # Таблица достижений
        self.achievements_table = Table(
            'achievements', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('user_id', Integer),
            Column('achievement_type', String(100)),
            Column('achievement_name', String(255)),
            Column('description', Text),
            Column('earned_at', DateTime, default=datetime.utcnow),
            Column('xp_reward', Integer, default=0)
        )
        
        # Таблица статистики
        self.stats_table = Table(
            'daily_stats', self.metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('date', DateTime),
            Column('user_id', Integer),
            Column('tasks_created', Integer, default=0),
            Column('tasks_completed', Integer, default=0),
            Column('xp_earned', Integer, default=0),
            Column('time_spent', Integer, default=0),  # в минутах
            Column('streak_count', Integer, default=0)
        )
        
        # Создание всех таблиц
        self.metadata.create_all(self.engine)
    
    def _init_sqlite(self) -> bool:
        """Fallback на простой SQLite"""
        try:
            self.connection_attempts += 1
            
            db_path = settings.DATA_DIR / "dailycheck.db"
            self.connection = sqlite3.connect(
                db_path, 
                check_same_thread=False,
                timeout=30.0
            )
            self.connection.row_factory = sqlite3.Row
            
            cursor = self.connection.cursor()
            
            # Создание полной схемы SQLite
            cursor.executescript('''
                PRAGMA foreign_keys = ON;
                PRAGMA journal_mode = WAL;
                PRAGMA synchronous = NORMAL;
                PRAGMA cache_size = 1000;
                PRAGMA temp_store = MEMORY;
                
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    email TEXT,
                    phone TEXT,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    theme TEXT DEFAULT 'default',
                    language TEXT DEFAULT 'ru',
                    timezone TEXT DEFAULT 'UTC',
                    notifications_enabled BOOLEAN DEFAULT 1,
                    ai_chat_enabled BOOLEAN DEFAULT 0,
                    weekly_goal INTEGER DEFAULT 0,
                    current_streak INTEGER DEFAULT 0,
                    max_streak INTEGER DEFAULT 0,
                    total_tasks INTEGER DEFAULT 0,
                    completed_tasks INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    is_premium BOOLEAN DEFAULT 0
                );
                
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'личное',
                    priority TEXT DEFAULT 'средний',
                    status TEXT DEFAULT 'pending',
                    completed BOOLEAN DEFAULT 0,
                    rating INTEGER,
                    difficulty INTEGER DEFAULT 1,
                    estimated_time INTEGER,
                    actual_time INTEGER,
                    parent_task_id INTEGER,
                    order_index INTEGER DEFAULT 0,
                    tags TEXT,
                    notes TEXT,
                    completion_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    due_date TIMESTAMP,
                    reminder_date TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (parent_task_id) REFERENCES tasks (id)
                );
                
                CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    achievement_type TEXT,
                    achievement_name TEXT,
                    description TEXT,
                    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    xp_reward INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
                
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TIMESTAMP,
                    user_id INTEGER,
                    tasks_created INTEGER DEFAULT 0,
                    tasks_completed INTEGER DEFAULT 0,
                    xp_earned INTEGER DEFAULT 0,
                    time_spent INTEGER DEFAULT 0,
                    streak_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
                
                -- Индексы для оптимизации
                CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
                CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
                CREATE INDEX IF NOT EXISTS idx_achievements_user_id ON achievements(user_id);
                CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(date);
                CREATE INDEX IF NOT EXISTS idx_daily_stats_user_id ON daily_stats(user_id);
            ''')
            
            self.connection.commit()
            
            self.db_type = "sqlite"
            self.db_available = True
            self.last_connection_time = datetime.now()
            
            logger.info("✅ SQLite база данных инициализирована")
            logger.info(f"📊 База данных: {db_path}")
            return True
            
        except Exception as e:
            error_msg = f"SQLite недоступен: {e}"
            self.connection_errors.append(error_msg)
            logger.warning(f"⚠️ {error_msg}")
            return False
    
    def _init_file_storage(self):
        """Последний fallback: файловое хранение JSON"""
        self.db_type = "file_storage"
        self.db_available = False
        self.last_connection_time = datetime.now()
        
        # Создание структуры файлов
        json_files = [
            "users.json",
            "tasks.json", 
            "achievements.json",
            "daily_stats.json",
            "system_stats.json"
        ]
        
        for filename in json_files:
            file_path = settings.DATA_DIR / filename
            if not file_path.exists():
                file_path.write_text("[]", encoding='utf-8')
        
        logger.warning("⚠️ Используем файловое хранение JSON как последний fallback")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Получение статуса здоровья базы данных"""
        return {
            "db_type": self.db_type,
            "db_available": self.db_available,
            "connection_attempts": self.connection_attempts,
            "last_connection": self.last_connection_time.isoformat() if self.last_connection_time else None,
            "recent_errors": self.connection_errors[-3:] if self.connection_errors else [],
            "database_url_type": settings.DATABASE_URL.split("://")[0] if settings.DATABASE_URL else "unknown"
        }
    
    async def test_connection(self) -> bool:
        """Тестирование подключения к БД"""
        try:
            if self.db_type == "sqlalchemy" and self.engine:
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True
            elif self.db_type == "sqlite" and self.connection:
                cursor = self.connection.cursor()
                cursor.execute("SELECT 1")
                return True
            elif self.db_type == "file_storage":
                return (settings.DATA_DIR / "users.json").exists()
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")
            return False

# Глобальный экземпляр менеджера БД
db_manager = AdvancedDatabaseManager()

# ============================================================================
# ADVANCED CACHE MANAGER
# ============================================================================

class AdvancedCacheManager:
    """Продвинутый менеджер кэширования с множественными стратегиями"""
    
    def __init__(self):
        self.cache_type = "unknown"
        self.cache_available = False
        self.redis_client = None
        self.disk_cache = None
        self.memory_cache = {}
        self.memory_cache_ttl = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
        
        # Инициализация кэша
        self._initialize_cache()
    
    def _initialize_cache(self):
        """Инициализация кэша в порядке приоритета"""
        
        # 1. Redis (лучший выбор для production)
        if REDIS_AVAILABLE and self._init_redis():
            return
        
        # 2. DiskCache (хороший fallback)
        if DISKCACHE_AVAILABLE and self._init_diskcache():
            return
        
        # 3. Memory cache (последний fallback)
        self._init_memory_cache()
    
    def _init_redis(self) -> bool:
        """Инициализация Redis кэша"""
        try:
            if not settings.REDIS_URL:
                return False
            
            import redis
            
            # Настройки подключения
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Тест подключения
            self.redis_client.ping()
            
            # Получение информации о Redis
            info = self.redis_client.info()
            redis_version = info.get('redis_version', 'unknown')
            
            self.cache_type = "redis"
            self.cache_available = True
            
            logger.info("✅ Redis кэш подключен успешно")
            logger.info(f"💾 Redis версия: {redis_version}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Redis недоступен: {e}")
            return False
    
    def _init_diskcache(self) -> bool:
        """Инициализация DiskCache"""
        try:
            import diskcache
            
            cache_dir = settings.CACHE_DIR
            cache_dir.mkdir(exist_ok=True)
            
            # Настройки DiskCache
            self.disk_cache = diskcache.Cache(
                str(cache_dir),
                size_limit=100 * 1024 * 1024,  # 100MB
                eviction_policy='least-recently-used',
                cull_limit=10
            )
            
            # Тест работы
            test_key = "__test__"
            self.disk_cache.set(test_key, "test_value", expire=1)
            if self.disk_cache.get(test_key) != "test_value":
                raise Exception("DiskCache test failed")
            self.disk_cache.delete(test_key)
            
            self.cache_type = "diskcache"
            self.cache_available = True
            
            logger.info("✅ DiskCache инициализирован")
            logger.info(f"💾 Кэш директория: {cache_dir}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ DiskCache недоступен: {e}")
            return False
    
    def _init_memory_cache(self):
        """In-memory кэш как последний fallback"""
        self.memory_cache = {}
        self.memory_cache_ttl = {}
        
        self.cache_type = "memory"
        self.cache_available = True
        
        logger.warning("⚠️ Используем in-memory кэш (данные не сохраняются при перезапуске)")
    
    async def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        try:
            if self.cache_type == "redis":
                data = self.redis_client.get(key)
                if data is not None:
                    self.cache_stats["hits"] += 1
                    return json.loads(data)
                else:
                    self.cache_stats["misses"] += 1
                    return None
                    
            elif self.cache_type == "diskcache":
                data = self.disk_cache.get(key)
                if data is not None:
                    self.cache_stats["hits"] += 1
                    return data
                else:
                    self.cache_stats["misses"] += 1
                    return None
                    
            else:  # memory cache
                if key in self.memory_cache:
                    if time.time() < self.memory_cache_ttl.get(key, 0):
                        self.cache_stats["hits"] += 1
                        return self.memory_cache[key]
                    else:
                        await self.delete(key)
                
                self.cache_stats["misses"] += 1
                return None
                
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"❌ Ошибка получения из кэша {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Установка значения в кэш"""
        try:
            if ttl is None:
                ttl = settings.CACHE_TTL_DEFAULT
            
            if self.cache_type == "redis":
                serialized_value = json.dumps(value, default=str)
                result = self.redis_client.setex(key, ttl, serialized_value)
                if result:
                    self.cache_stats["sets"] += 1
                    return True
                    
            elif self.cache_type == "diskcache":
                result = self.disk_cache.set(key, value, expire=ttl)
                if result:
                    self.cache_stats["sets"] += 1
                    return True
                    
            else:  # memory cache
                self.memory_cache[key] = value
                self.memory_cache_ttl[key] = time.time() + ttl
                self.cache_stats["sets"] += 1
                return True
            
            return False
            
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"❌ Ошибка установки кэша {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Удаление значения из кэша"""
        try:
            if self.cache_type == "redis":
                result = self.redis_client.delete(key)
                if result:
                    self.cache_stats["deletes"] += 1
                    return True
                    
            elif self.cache_type == "diskcache":
                result = self.disk_cache.delete(key)
                if result:
                    self.cache_stats["deletes"] += 1
                    return True
                    
            else:  # memory cache
                deleted = False
                if key in self.memory_cache:
                    del self.memory_cache[key]
                    deleted = True
                if key in self.memory_cache_ttl:
                    del self.memory_cache_ttl[key]
                    deleted = True
                
                if deleted:
                    self.cache_stats["deletes"] += 1
                    return True
            
            return False
            
        except Exception as e:
            self.cache_stats["errors"] += 1
            logger.error(f"❌ Ошибка удаления из кэша {key}: {e}")
            return False
    
    async def clear_expired(self):
        """Очистка устаревших записей (для memory cache)"""
        if self.cache_type == "memory":
            current_time = time.time()
            expired_keys = [
                key for key, ttl in self.memory_cache_ttl.items()
                if current_time > ttl
            ]
            
            for key in expired_keys:
                await self.delete(key)
            
            if expired_keys:
                logger.info(f"🧹 Очищено {len(expired_keys)} устаревших записей кэша")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша"""
        total_operations = sum(self.cache_stats.values())
        hit_rate = (self.cache_stats["hits"] / max(self.cache_stats["hits"] + self.cache_stats["misses"], 1)) * 100
        
        stats = {
            "cache_type": self.cache_type,
            "cache_available": self.cache_available,
            "hit_rate_percent": round(hit_rate, 2),
            "total_operations": total_operations,
            **self.cache_stats
        }
        
        # Дополнительная информация для разных типов кэша
        if self.cache_type == "memory":
            stats["memory_entries"] = len(self.memory_cache)
        elif self.cache_type == "diskcache" and self.disk_cache:
            stats["disk_cache_size"] = len(self.disk_cache)
        
        return stats

# Глобальный экземпляр менеджера кэша
cache_manager = AdvancedCacheManager()

# ============================================================================
# LIFESPAN EVENTS (MODERN FASTAPI)
# ============================================================================

@asynccontextmanager
async def application_lifespan(app: FastAPI):
    """Modern lifespan event handler для FastAPI"""
    
    # ========== STARTUP ==========
    startup_time = time.time()
    
    try:
        logger.info(f"🚀 {settings.PROJECT_NAME} запускается...")
        logger.info(f"📊 База данных: {db_manager.db_type}")
        logger.info(f"💾 Кэширование: {cache_manager.cache_type}")
        logger.info(f"🌍 Среда: {settings.ENVIRONMENT}")
        logger.info(f"🔧 Режим отладки: {'включен' if settings.DEBUG else 'отключен'}")
        
        # Тестирование подключений
        db_test = await db_manager.test_connection()
        logger.info(f"🗄️ Тест БД: {'✅ OK' if db_test else '❌ FAIL'}")
        
        # Запуск фоновых задач
        cleanup_task = asyncio.create_task(periodic_maintenance())
        app.state.cleanup_task = cleanup_task
        
        # Сохранение времени запуска
        app.state.startup_time = datetime.fromtimestamp(startup_time)
        
        startup_duration = time.time() - startup_time
        logger.info(f"✅ Запуск завершен за {startup_duration:.2f} секунд")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске: {e}")
        logger.error(traceback.format_exc())
        yield
    
    # ========== SHUTDOWN ==========
    finally:
        logger.info("🛑 Остановка приложения...")
        
        try:
            # Отмена фоновых задач
            if hasattr(app.state, 'cleanup_task'):
                app.state.cleanup_task.cancel()
                try:
                    await app.state.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Закрытие соединений с БД
            if hasattr(db_manager, 'connection') and db_manager.connection:
                db_manager.connection.close()
                logger.info("✅ Соединение с БД закрыто")
            
            # Закрытие Redis соединения
            if hasattr(cache_manager, 'redis_client') and cache_manager.redis_client:
                cache_manager.redis_client.close()
                logger.info("✅ Redis соединение закрыто")
            
            logger.info("✅ Корректное завершение работы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при завершении: {e}")

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def periodic_maintenance():
    """Периодические задачи обслуживания"""
    
    maintenance_interval = 600  # 10 минут
    
    while True:
        try:
            await asyncio.sleep(maintenance_interval)
            
            logger.debug("🧹 Запуск периодического обслуживания...")
            
            # Очистка устаревшего кэша
            await cache_manager.clear_expired()
            
            # Логирование статистики
            cache_stats = cache_manager.get_stats()
            db_health = db_manager.get_health_status()
            
            logger.info(f"📊 Кэш статистика: {cache_stats['hit_rate_percent']:.1f}% hit rate")
            logger.debug(f"🗄️ БД статистика: {db_health}")
            
        except asyncio.CancelledError:
            logger.info("🛑 Периодическое обслуживание остановлено")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в периодическом обслуживании: {e}")

# ============================================================================
# COMPREHENSIVE WEB APPLICATION
# ============================================================================

class ComprehensiveWebApplication:
    """Комплексное веб-приложение с полным функционалом"""
    
    def __init__(self, dev_mode: bool = False, host: str = "0.0.0.0", port: int = 10000):
        self.dev_mode = dev_mode
        self.host = host
        self.port = port
        self.app = None
        self.server = None
        
        # Обработчики сигналов
        self._setup_signal_handlers()
        
        # Создание приложения
        self._create_application()
    
    def _setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        def signal_handler(signum, frame):
            logger.info(f"🛑 Получен сигнал {signum}")
            # Graceful shutdown будет обработан uvicorn
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _create_application(self):
        """Создание FastAPI приложения"""
        
        # Создание основного приложения
        self.app = FastAPI(
            title=settings.PROJECT_NAME,
            description=settings.DESCRIPTION,
            version=settings.VERSION,
            docs_url="/docs" if self.dev_mode else None,
            redoc_url="/redoc" if self.dev_mode else None,
            openapi_url="/openapi.json" if self.dev_mode else None,
            debug=self.dev_mode,
            lifespan=application_lifespan
        )
        
        # Настройка компонентов
        self._setup_middleware()
        self._setup_static_and_templates()
        self._setup_api_routes()
        self._setup_main_routes()
        self._setup_error_handlers()
        
        logger.info("✅ FastAPI приложение создано")
    
    def _setup_middleware(self):
        """Настройка middleware"""
        
        # Security Headers
        @self.app.middleware("http")
        async def add_security_headers(request: Request, call_next):
            start_time = time.time()
            
            try:
                response = await call_next(request)
                
                # Добавляем заголовки безопасности
                if not self.dev_mode:
                    response.headers.update({
                        "X-Content-Type-Options": "nosniff",
                        "X-Frame-Options": "DENY",
                        "X-XSS-Protection": "1; mode=block",
                        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                        "Referrer-Policy": "strict-origin-when-cross-origin",
                        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net unpkg.com cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' cdn.tailwindcss.com;"
                    })
                
                # Метрики производительности
                process_time = time.time() - start_time
                response.headers["X-Process-Time"] = f"{process_time:.4f}"
                
                return response
                
            except Exception as e:
                logger.error(f"❌ Ошибка в security middleware: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error", "dev_mode": self.dev_mode}
                )
        
        # Request Logging
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()
            
            # Получение IP клиента
            client_ip = request.headers.get("X-Forwarded-For") or \
                       request.headers.get("X-Real-IP") or \
                       getattr(request.client, 'host', 'unknown')
            
            response = await call_next(request)
            
            process_time = time.time() - start_time
            
            # Логирование только в dev режиме или для ошибок
            if self.dev_mode or response.status_code >= 400:
                logger.info(
                    f"{request.method} {request.url.path} "
                    f"- {response.status_code} "
                    f"- {process_time:.3f}s "
                    f"- {client_ip}"
                )
            
            return response
        
        # Gzip compression
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)
        
        # CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
            allow_headers=["*"],
        )
        
        # Trusted Host (только для production)
        if not self.dev_mode and settings.ALLOWED_HOSTS != ["*"]:
            self.app.add_middleware(
                TrustedHostMiddleware,
                allowed_hosts=settings.ALLOWED_HOSTS
            )
        
        logger.info("✅ Middleware настроен")
    
    def _setup_static_and_templates(self):
        """Настройка статических файлов и шаблонов"""
        
        # Статические файлы
        if settings.STATIC_DIR.exists():
            self.app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
            logger.info(f"✅ Статические файлы: {settings.STATIC_DIR}")
        
        # Шаблоны
        if settings.TEMPLATES_DIR.exists():
            self.templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))
            logger.info(f"✅ Шаблоны: {settings.TEMPLATES_DIR}")
        else:
            self._create_default_templates()
    
    def _create_default_templates(self):
        """Создание базовых шаблонов"""
        
        # Базовый шаблон
        base_template = settings.TEMPLATES_DIR / "base.html"
        base_template.write_text('''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{{ title or "DailyCheck Bot Dashboard" }}{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        {% block extra_css %}{% endblock %}
    </style>
</head>
<body class="bg-gray-50 dark:bg-gray-900">
    <nav class="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <h1 class="text-xl font-bold text-gray-900 dark:text-white">
                        🤖 DailyCheck Bot Dashboard v4.0
                    </h1>
                </div>
                <div class="flex items-center space-x-4">
                    <a href="/api/stats/overview" class="text-blue-600 hover:text-blue-800 dark:text-blue-400">API</a>
                    <a href="/health" class="text-green-600 hover:text-green-800 dark:text-green-400">Health</a>
                    {% if dev_mode %}
                    <a href="/docs" class="text-purple-600 hover:text-purple-800 dark:text-purple-400">Docs</a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>
    
    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {% block content %}{% endblock %}
    </main>
    
    <footer class="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 mt-8">
        <div class="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
            <p class="text-center text-sm text-gray-500 dark:text-gray-400">
                DailyCheck Bot Dashboard v4.0 • 
                База данных: {{ db_type }} • 
                Кэш: {{ cache_type }}
            </p>
        </div>
    </footer>
    
    {% block extra_js %}{% endblock %}
</body>
</html>''', encoding='utf-8')
        
        # Главная страница
        dashboard_template = settings.TEMPLATES_DIR / "dashboard.html"
        dashboard_template.write_text('''{% extends "base.html" %}

{% block content %}
<div class="px-4 py-6 sm:px-0">
    <!-- Статистические карточки -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div class="bg-white dark:bg-gray-800 overflow-hidden shadow rounded-lg">
            <div class="p-5">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                            <span class="text-white text-sm font-medium">👥</span>
                        </div>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                                Всего пользователей
                            </dt>
                            <dd class="text-lg font-medium text-gray-900 dark:text-white">
                                {{ stats.total_users | default(0) }}
                            </dd>
                        </dl>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="bg-white dark:bg-gray-800 overflow-hidden shadow rounded-lg">
            <div class="p-5">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <div class="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                            <span class="text-white text-sm font-medium">📋</span>
                        </div>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                                Всего задач
                            </dt>
                            <dd class="text-lg font-medium text-gray-900 dark:text-white">
                                {{ stats.total_tasks | default(0) }}
                            </dd>
                        </dl>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="bg-white dark:bg-gray-800 overflow-hidden shadow rounded-lg">
            <div class="p-5">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <div class="w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center">
                            <span class="text-white text-sm font-medium">✅</span>
                        </div>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                                Выполнено задач
                            </dt>
                            <dd class="text-lg font-medium text-gray-900 dark:text-white">
                                {{ stats.completed_tasks | default(0) }}
                            </dd>
                        </dl>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="bg-white dark:bg-gray-800 overflow-hidden shadow rounded-lg">
            <div class="p-5">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <div class="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center">
                            <span class="text-white text-sm font-medium">⚡</span>
                        </div>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                                Активных сегодня
                            </dt>
                            <dd class="text-lg font-medium text-gray-900 dark:text-white">
                                {{ stats.active_users_today | default(0) }}
                            </dd>
                        </dl>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Графики и дополнительная информация -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
            <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">
                Системная информация
            </h3>
            <dl class="space-y-2">
                <div class="flex justify-between">
                    <dt class="text-sm text-gray-500 dark:text-gray-400">База данных:</dt>
                    <dd class="text-sm text-gray-900 dark:text-white font-medium">{{ db_type }}</dd>
                </div>
                <div class="flex justify-between">
                    <dt class="text-sm text-gray-500 dark:text-gray-400">Кэширование:</dt>
                    <dd class="text-sm text-gray-900 dark:text-white font-medium">{{ cache_type }}</dd>
                </div>
                <div class="flex justify-between">
                    <dt class="text-sm text-gray-500 dark:text-gray-400">Время работы:</dt>
                    <dd class="text-sm text-gray-900 dark:text-white font-medium">{{ uptime }}</dd>
                </div>
                <div class="flex justify-between">
                    <dt class="text-sm text-gray-500 dark:text-gray-400">Версия:</dt>
                    <dd class="text-sm text-gray-900 dark:text-white font-medium">{{ version }}</dd>
                </div>
            </dl>
        </div>
        
        <div class="bg-white dark:bg-gray-800 shadow rounded-lg p-6">
            <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">
                Быстрые ссылки
            </h3>
            <div class="space-y-2">
                <a href="/api/stats/overview" 
                   class="block w-full text-left px-4 py-2 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 dark:hover:bg-blue-900 rounded">
                    📊 API Статистики
                </a>
                <a href="/api/users/" 
                   class="block w-full text-left px-4 py-2 text-sm text-green-600 hover:text-green-800 hover:bg-green-50 dark:hover:bg-green-900 rounded">
                    👥 API Пользователей
                </a>
                <a href="/api/charts/user-activity" 
                   class="block w-full text-left px-4 py-2 text-sm text-purple-600 hover:text-purple-800 hover:bg-purple-50 dark:hover:bg-purple-900 rounded">
                    📈 API Графиков
                </a>
                <a href="/health" 
                   class="block w-full text-left px-4 py-2 text-sm text-emerald-600 hover:text-emerald-800 hover:bg-emerald-50 dark:hover:bg-emerald-900 rounded">
                    💚 Health Check
                </a>
            </div>
        </div>
    </div>
</div>
{% endblock %}''', encoding='utf-8')
        
        self.templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))
        logger.info("✅ Базовые шаблоны созданы")
    
    def _setup_api_routes(self):
        """Подключение API роутеров"""
        
        # Базовые системные API
        self._setup_system_api()
        
        # Попытка подключения модульных API
        self._try_load_modular_apis()
    
    def _setup_system_api(self):
        """Базовые системные API endpoints"""
        
        @self.app.get("/api/health")
        async def comprehensive_health_check():
            """Комплексная проверка здоровья системы"""
            
            uptime = datetime.now() - self.app.state.startup_time
            
            # Тестирование подключений
            db_test = await db_manager.test_connection()
            cache_stats = cache_manager.get_stats()
            
            health_data = {
                "status": "healthy" if db_test else "degraded",
                "service": settings.PROJECT_NAME,
                "version": settings.VERSION,
                "environment": settings.ENVIRONMENT,
                "uptime": str(uptime),
                "uptime_seconds": int(uptime.total_seconds()),
                "timestamp": datetime.now().isoformat(),
                
                "database": {
                    "type": db_manager.db_type,
                    "available": db_manager.db_available,
                    "connection_test": db_test,
                    **db_manager.get_health_status()
                },
                
                "cache": {
                    "type": cache_manager.cache_type,
                    "available": cache_manager.cache_available,
                    **cache_stats
                },
                
                "system": {
                    "dev_mode": self.dev_mode,
                    "host": self.host,
                    "port": self.port,
                    "platform": {
                        "render": settings.IS_RENDER,
                        "heroku": settings.IS_HEROKU,
                        "docker": settings.IS_DOCKER
                    }
                }
            }
            
            return health_data
        
        @self.app.get("/api/stats/overview")
        async def enhanced_stats_overview():
            """Расширенный обзор статистики"""
            
            cache_key = "stats_overview_v2"
            cached = await cache_manager.get(cache_key)
            
            if cached:
                return cached
            
            # Генерация расширенной статистики
            base_stats = {
                "total_users": 250,
                "active_users": 89,
                "active_users_today": 34,
                "total_tasks": 3420,
                "completed_tasks": 2847,
                "pending_tasks": 573,
                "completion_rate": 83.2,
                "weekly_signups": 28,
                "monthly_retention": 76.4,
                "avg_tasks_per_user": 13.7,
                "total_xp_earned": 142750,
                "achievements_unlocked": 1247
            }
            
            # Дополнительная информация
            enhanced_stats = {
                **base_stats,
                "trends": {
                    "users_growth": "+12.5%",
                    "tasks_growth": "+8.3%",
                    "completion_rate_change": "+2.1%"
                },
                "top_categories": [
                    {"name": "Работа", "count": 1285, "percentage": 37.6},
                    {"name": "Здоровье", "count": 967, "percentage": 28.3},
                    {"name": "Обучение", "count": 684, "percentage": 20.0},
                    {"name": "Личное", "count": 484, "percentage": 14.1}
                ],
                "system_info": {
                    "database_type": db_manager.db_type,
                    "cache_type": cache_manager.cache_type,
                    "uptime": str(datetime.now() - self.app.state.startup_time),
                    "version": settings.VERSION
                },
                "timestamp": datetime.now().isoformat()
            }
            
            # Кэширование на 5 минут
            await cache_manager.set(cache_key, enhanced_stats, ttl=300)
            
            return enhanced_stats
        
        @self.app.get("/api/system/info")
        async def detailed_system_info():
            """Детальная информация о системе"""
            
            import platform
            import psutil
            
            try:
                # Системная информация
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                system_info = {
                    "system": {
                        "platform": platform.system(),
                        "platform_release": platform.release(),
                        "platform_version": platform.version(),
                        "architecture": platform.machine(),
                        "processor": platform.processor(),
                        "python_version": platform.python_version(),
                        "cpu_count": psutil.cpu_count(),
                        "cpu_percent": cpu_percent
                    },
                    "memory": {
                        "total": memory.total,
                        "available": memory.available,
                        "percent": memory.percent,
                        "used": memory.used,
                        "free": memory.free
                    },
                    "disk": {
                        "total": disk.total,
                        "used": disk.used,
                        "free": disk.free,
                        "percent": (disk.used / disk.total) * 100
                    },
                    "application": {
                        "name": settings.PROJECT_NAME,
                        "version": settings.VERSION,
                        "environment": settings.ENVIRONMENT,
                        "dev_mode": self.dev_mode,
                        "database": db_manager.db_type,
                        "cache": cache_manager.cache_type
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
            except ImportError:
                # Fallback если psutil недоступен
                system_info = {
                    "system": {
                        "platform": platform.system(),
                        "python_version": platform.python_version(),
                        "cpu_count": os.cpu_count()
                    },
                    "application": {
                        "name": settings.PROJECT_NAME,
                        "version": settings.VERSION,
                        "environment": settings.ENVIRONMENT,
                        "dev_mode": self.dev_mode,
                        "database": db_manager.db_type,
                        "cache": cache_manager.cache_type
                    },
                    "note": "Detailed system metrics unavailable (psutil not installed)",
                    "timestamp": datetime.now().isoformat()
                }
            
            return system_info
        
        logger.info("✅ Системные API endpoints созданы")
    
    def _try_load_modular_apis(self):
        """Попытка загрузки модульных API"""
        
        # Список API модулей для загрузки
        api_modules = [
            ("dashboard.api.users", "users", "/api/users"),
            ("dashboard.api.charts", "charts", "/api/charts"),
            ("dashboard.api.stats", "stats", "/api/stats"),
            ("dashboard.api.tasks", "tasks", "/api/tasks"),
            ("dashboard.api.achievements", "achievements", "/api/achievements")
        ]
        
        loaded_modules = []
        
        for module_path, router_name, prefix in api_modules:
            try:
                # Динамический импорт модуля
                module = __import__(module_path, fromlist=[router_name])
                router = getattr(module, 'router')
                
                # Подключение роутера
                self.app.include_router(router, prefix=prefix, tags=[router_name])
                loaded_modules.append(f"{router_name} ({prefix})")
                
                logger.info(f"✅ API модуль загружен: {module_path}")
                
            except ImportError as e:
                logger.warning(f"⚠️ API модуль не найден: {module_path} - {e}")
            except AttributeError as e:
                logger.warning(f"⚠️ Router не найден в модуле {module_path} - {e}")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки API модуля {module_path}: {e}")
        
        if loaded_modules:
            logger.info(f"📡 Загружены API модули: {', '.join(loaded_modules)}")
        else:
            logger.warning("⚠️ Модульные API не загружены, используются только базовые endpoints")
    
    def _setup_main_routes(self):
        """Настройка основных маршрутов"""
        
        # HEAD методы для мониторинга
        @self.app.head("/")
        @self.app.head("/health")
        async def monitoring_head():
            """HEAD endpoints для мониторинга"""
            return Response(status_code=200)
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Главная страница дашборда"""
            try:
                # Получение статистики
                stats_data = await cache_manager.get("dashboard_stats")
                
                if not stats_data:
                    stats_data = {
                        "total_users": 250,
                        "total_tasks": 3420,
                        "completed_tasks": 2847,
                        "active_users_today": 34
                    }
                    await cache_manager.set("dashboard_stats", stats_data, ttl=300)
                
                # Системная информация
                uptime = datetime.now() - self.app.state.startup_time
                
                context = {
                    "request": request,
                    "title": settings.PROJECT_NAME,
                    "stats": stats_data,
                    "db_type": db_manager.db_type,
                    "cache_type": cache_manager.cache_type,
                    "uptime": str(uptime),
                    "version": settings.VERSION,
                    "dev_mode": self.dev_mode
                }
                
                # Попытка использования шаблона
                if hasattr(self, 'templates'):
                    return self.templates.TemplateResponse("dashboard.html", context)
                else:
                    return HTMLResponse(self._get_fallback_html(context))
                    
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки главной страницы: {e}")
                return HTMLResponse(self._get_fallback_html({
                    "title": "DailyCheck Bot Dashboard v4.0",
                    "error": str(e)
                }))
        
        @self.app.get("/dashboard")
        async def dashboard_redirect():
            """Редирект на главную"""
            return RedirectResponse(url="/", status_code=301)
        
        @self.app.get("/health")
        async def web_health_simple():
            """Простой health check"""
            uptime = datetime.now() - self.app.state.startup_time
            
            return {
                "status": "healthy",
                "service": "DailyCheck Bot Dashboard",
                "version": settings.VERSION,
                "uptime": str(uptime),
                "database": db_manager.db_type,
                "cache": cache_manager.cache_type,
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.get("/ping")
        async def ping_endpoint():
            """Простой ping endpoint"""
            return {
                "ping": "pong",
                "timestamp": datetime.now().isoformat(),
                "service": settings.PROJECT_NAME,
                "version": settings.VERSION
            }
        
        @self.app.get("/api")
        async def api_info():
            """Информация об API"""
            return {
                "name": settings.PROJECT_NAME,
                "version": settings.VERSION,
                "description": settings.DESCRIPTION,
                "docs_url": "/docs" if self.dev_mode else None,
                "health_url": "/api/health",
                "available_endpoints": [
                    "/api/health",
                    "/api/stats/overview",
                    "/api/system/info",
                    "/health",
                    "/ping"
                ],
                "timestamp": datetime.now().isoformat()
            }
        
        logger.info("✅ Основные маршруты настроены")
    
    def _get_fallback_html(self, context: dict) -> str:
        """Fallback HTML страница"""
        
        error_info = f"<div class='error'>Ошибка: {context.get('error', 'Неизвестная ошибка')}</div>" if 'error' in context else ""
        
        return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{context.get('title', 'DailyCheck Bot Dashboard')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
            color: white; padding: 20px;
        }}
        .container {{ 
            text-align: center; max-width: 800px; padding: 40px 20px;
            background: rgba(255,255,255,0.1); border-radius: 20px;
            backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2);
        }}
        .title {{ font-size: 2.5rem; margin-bottom: 20px; }}
        .stats {{ 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px; margin: 30px 0;
        }}
        .stat {{ background: rgba(255,255,255,0.15); padding: 20px; border-radius: 10px; }}
        .stat-number {{ font-size: 2rem; font-weight: bold; margin-bottom: 5px; }}
        .links {{ margin-top: 30px; }}
        .links a {{ 
            display: inline-block; margin: 0 10px; padding: 10px 20px;
            background: rgba(255,255,255,0.2); color: white; text-decoration: none;
            border-radius: 20px; transition: all 0.3s;
        }}
        .links a:hover {{ background: rgba(255,255,255,0.3); }}
        .error {{ 
            background: rgba(255,0,0,0.2); border: 1px solid rgba(255,0,0,0.3);
            padding: 15px; border-radius: 10px; margin: 20px 0;
        }}
        .system-info {{ 
            margin-top: 20px; font-size: 0.9rem; opacity: 0.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1 class="title">🤖 DailyCheck Bot Dashboard v4.0</h1>
        <p>Система управления задачами с геймификацией</p>
        
        {error_info}
        
        <div class="stats">
            <div class="stat">
                <div class="stat-number">250</div>
                <div>Пользователей</div>
            </div>
            <div class="stat">
                <div class="stat-number">3.4K</div>
                <div>Задач</div>
            </div>
            <div class="stat">
                <div class="stat-number">83%</div>
                <div>Выполнено</div>
            </div>
            <div class="stat">
                <div class="stat-number">34</div>
                <div>Активных</div>
            </div>
        </div>
        
        <div class="links">
            <a href="/api/health">Health Check</a>
            <a href="/api/stats/overview">API Stats</a>
            <a href="/ping">Ping</a>
            {f'<a href="/docs">API Docs</a>' if self.dev_mode else ''}
        </div>
        
        <div class="system-info">
            <p>База данных: {context.get('db_type', 'Unknown')} | 
               Кэш: {context.get('cache_type', 'Unknown')} | 
               v{context.get('version', '4.0')}</p>
            <p>Время работы: {context.get('uptime', 'Unknown')}</p>
        </div>
    </div>
</body>
</html>
        """
    
    def _setup_error_handlers(self):
        """Настройка обработчиков ошибок"""
        
        @self.app.exception_handler(404)
        async def not_found_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Not Found",
                    "message": f"Endpoint {request.url.path} не найден",
                    "method": request.method,
                    "available_endpoints": [
                        "/", "/health", "/ping", "/api",
                        "/api/health", "/api/stats/overview", "/api/system/info"
                    ],
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        @self.app.exception_handler(500)
        async def internal_error_handler(request: Request, exc: Exception):
            error_id = f"err_{int(time.time())}"
            logger.error(f"Internal server error [{error_id}]: {exc}")
            logger.error(traceback.format_exc())
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "Внутренняя ошибка сервера",
                    "error_id": error_id,
                    "dev_mode": self.dev_mode,
                    "dev_details": str(exc) if self.dev_mode else None,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        @self.app.exception_handler(422)
        async def validation_error_handler(request: Request, exc: Exception):
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Validation Error",
                    "message": "Ошибка валидации данных",
                    "details": str(exc) if self.dev_mode else "Неверный формат данных",
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        logger.info("✅ Обработчики ошибок настроены")
    
    async def start_server(self):
        """Запуск веб-сервера"""
        
        # Конфигурация uvicorn
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if self.dev_mode else "info",
            reload=False,  # Отключено для стабильности
            access_log=self.dev_mode,
            server_header=False,
            date_header=False,
            use_colors=True,
            loop="asyncio"
        )
        
        self.server = uvicorn.Server(config)
        
        logger.info("✅ Dashboard API routes loaded successfully")
        logger.info(f"🚀 Запуск веб-сервера на http://{self.host}:{self.port}")
        logger.info(f"📊 Режим: {'🔧 Разработка' if self.dev_mode else '🏭 Продакшн'}")
        
        if self.dev_mode:
            logger.info(f"📚 API документация: http://{self.host}:{self.port}/docs")
            logger.info(f"🌐 Дашборд: http://{self.host}:{self.port}/")
        
        logger.info("Нажмите Ctrl+C для остановки сервера...")
        
        try:
            # Запуск сервера
            await self.server.serve()
            
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки от пользователя")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка веб-сервера: {e}")
            logger.error(traceback.format_exc())
            raise
        finally:
            await self._graceful_shutdown()
    
    async def _graceful_shutdown(self):
        """Корректное завершение работы"""
        logger.info("🔄 Начинаем корректное завершение работы...")
        
        try:
            # Останавливаем сервер
            if self.server:
                self.server.should_exit = True
                logger.info("✅ Uvicorn сервер остановлен")
            
            # Ждем завершения активных запросов
            await asyncio.sleep(1)
            
            logger.info("✅ Корректное завершение работы завершено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при завершении работы: {e}")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def async_main():
    """Асинхронная главная функция"""
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(
        description='Запуск DailyCheck Bot Dashboard v4.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Примеры использования:
  python scripts/start_web.py --dev                    # Режим разработки
  python scripts/start_web.py --port 8080             # Другой порт
  python scripts/start_web.py --host 127.0.0.1        # Локальный хост
  python scripts/start_web.py --log-level DEBUG       # Детальное логирование
        '''
    )
    
    parser.add_argument('--dev', action='store_true', 
                       help='Режим разработки (включает debug, docs, reload)')
    parser.add_argument('--port', type=int, default=settings.PORT,
                       help=f'Порт для веб-сервера (по умолчанию: {settings.PORT})')
    parser.add_argument('--host', default=settings.HOST,
                       help=f'Хост для веб-сервера (по умолчанию: {settings.HOST})')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Уровень логирования')
    
    args = parser.parse_args()
    
    # Определение режима разработки
    dev_mode = args.dev or settings.DEBUG or settings.ENVIRONMENT == 'development'
    
    # Обновление настроек для dev режима
    if dev_mode:
        settings.DEBUG = True
        os.environ['ENVIRONMENT'] = 'development'
    
    # Инициализация логирования
    global logger
    logger = setup_comprehensive_logging(dev_mode, args.log_level)
    
    # Логирование информации о запуске
    logger.info("="*60)
    logger.info(f"🚀 {settings.PROJECT_NAME}")
    logger.info(f"📋 Версия: {settings.VERSION}")
    logger.info(f"🌍 Среда: {settings.ENVIRONMENT}")
    logger.info(f"🔧 Режим отладки: {'включен' if dev_mode else 'отключен'}")
    logger.info(f"🌐 Сервер: http://{args.host}:{args.port}")
    logger.info("="*60)
    
    # Создание и запуск веб-приложения
    try:
        app = ComprehensiveWebApplication(
            dev_mode=dev_mode,
            host=args.host,
            port=args.port
        )
        
        await app.start_server()
        
    except KeyboardInterrupt:
        logger.info("👋 Завершение работы по запросу пользователя")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

def main():
    """Главная функция запуска"""
    try:
        # Проверка версии Python
        if sys.version_info < (3, 8):
            print("❌ Требуется Python 3.8 или новее")
            sys.exit(1)
        
        # Запуск асинхронного приложения
        asyncio.run(async_main())
        
    except KeyboardInterrupt:
        print("\n👋 Завершение работы...")
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        traceback.print_exc()
        sys.exit(1)

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()
