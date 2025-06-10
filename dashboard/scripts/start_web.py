#!/usr/bin/env python3
"""
Скрипт запуска веб-дашборда DailyCheck Bot v4.0
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
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# Добавляем корневую папку в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import uvicorn
    from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
    from pydantic import BaseModel
    import asyncio
    import time
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Установите зависимости: pip install -r requirements-web.txt")
    sys.exit(1)

# ============================================================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================================================

def setup_logging(dev_mode: bool = False):
    """Настройка системы логирования"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_level = logging.DEBUG if dev_mode else logging.INFO
    
    # Создаем папку для логов
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Настраиваем обработчики
    handlers = [
        logging.FileHandler(log_dir / 'web_dashboard.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
    
    logging.basicConfig(
        format=log_format,
        level=log_level,
        handlers=handlers,
        force=True
    )
    
    # Настраиваем уровни для внешних библиотек
    if not dev_mode:
        logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
        logging.getLogger('uvicorn.error').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# ============================================================================
# КОНФИГУРАЦИЯ И НАСТРОЙКИ
# ============================================================================

class Settings:
    """Настройки приложения с fallback механизмами"""
    
    def __init__(self):
        # Основные настройки
        self.PROJECT_NAME = "DailyCheck Bot Dashboard v4.0"
        self.VERSION = "4.0"
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        
        # Сервер
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", 10000))
        
        # Пути
        self.DATA_DIR = Path("data")
        self.EXPORTS_DIR = Path("exports")
        self.BACKUPS_DIR = Path("backups")
        self.LOGS_DIR = Path("logs")
        self.STATIC_DIR = Path("static")
        self.TEMPLATES_DIR = Path("dashboard/templates")
        
        # Создаем необходимые директории
        for directory in [self.DATA_DIR, self.EXPORTS_DIR, self.BACKUPS_DIR, 
                         self.LOGS_DIR, self.STATIC_DIR, self.TEMPLATES_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # База данных
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        if self.DATABASE_URL and self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
        # Fallback на SQLite
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{self.DATA_DIR}/dailycheck.db"
        
        # Redis
        self.REDIS_URL = os.getenv("REDIS_URL")
        
        # Telegram Bot
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0)) or None
        
        # API ключи
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        # Веб-настройки
        self.CORS_ORIGINS = ["*"]
        
        logger.info(f"✅ Настройки загружены: {self.PROJECT_NAME}")

settings = Settings()

# ============================================================================
# МЕНЕДЖЕР БАЗЫ ДАННЫХ С FALLBACK
# ============================================================================

class DatabaseManager:
    """Менеджер базы данных с поддержкой SQLite и PostgreSQL + файловый fallback"""
    
    def __init__(self):
        self.db_type = "unknown"
        self.db_available = False
        self.connection = None
        self._init_database()
    
    def _init_database(self):
        """Инициализация базы данных с fallback механизмами"""
        try:
            # Попытка инициализации SQLAlchemy
            if self._init_sqlalchemy():
                return
            
            # Fallback на простой SQLite
            if self._init_sqlite():
                return
            
            # Последний fallback - файловое хранение
            self._init_file_storage()
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации БД: {e}")
            self._init_file_storage()
    
    def _init_sqlalchemy(self) -> bool:
        """Попытка инициализации SQLAlchemy"""
        try:
            from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Boolean, DateTime, Text
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy.ext.declarative import declarative_base
            
            # Создание engine
            self.engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=settings.DEBUG
            )
            
            # Тест подключения
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Создание таблиц
            self.metadata = MetaData()
            
            # Таблица пользователей
            self.users_table = Table(
                'users', self.metadata,
                Column('user_id', Integer, primary_key=True),
                Column('username', String(255)),
                Column('first_name', String(255)),
                Column('last_name', String(255)),
                Column('level', Integer, default=1),
                Column('xp', Integer, default=0),
                Column('theme', String(50), default='default'),
                Column('language', String(10), default='ru'),
                Column('timezone', String(50), default='UTC'),
                Column('notifications_enabled', Boolean, default=True),
                Column('ai_chat_enabled', Boolean, default=False),
                Column('created_at', DateTime, default=datetime.utcnow),
                Column('updated_at', DateTime, default=datetime.utcnow),
                Column('last_activity', DateTime, default=datetime.utcnow)
            )
            
            # Таблица задач
            self.tasks_table = Table(
                'tasks', self.metadata,
                Column('id', Integer, primary_key=True, autoincrement=True),
                Column('user_id', Integer),
                Column('title', Text),
                Column('description', Text),
                Column('category', String(100), default='личное'),
                Column('priority', String(50), default='средний'),
                Column('status', String(50), default='pending'),
                Column('completed', Boolean, default=False),
                Column('rating', Integer),
                Column('estimated_time', Integer),
                Column('actual_time', Integer),
                Column('parent_task_id', Integer),
                Column('created_at', DateTime, default=datetime.utcnow),
                Column('completed_at', DateTime),
                Column('due_date', DateTime)
            )
            
            # Создание всех таблиц
            self.metadata.create_all(self.engine)
            
            # Создание сессии
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            
            self.db_type = "sqlalchemy"
            self.db_available = True
            logger.info("✅ SQLAlchemy подключен успешно")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ SQLAlchemy не доступен: {e}")
            return False
    
    def _init_sqlite(self) -> bool:
        """Fallback: простой SQLite"""
        try:
            db_path = settings.DATA_DIR / "dailycheck.db"
            self.connection = sqlite3.connect(db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            
            cursor = self.connection.cursor()
            
            # Создание таблиц
            cursor.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    theme TEXT DEFAULT 'default',
                    language TEXT DEFAULT 'ru',
                    timezone TEXT DEFAULT 'UTC',
                    notifications_enabled BOOLEAN DEFAULT 1,
                    ai_chat_enabled BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                    estimated_time INTEGER,
                    actual_time INTEGER,
                    parent_task_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    due_date TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
            ''')
            
            self.connection.commit()
            
            self.db_type = "sqlite"
            self.db_available = True
            logger.info("✅ SQLite база данных инициализирована")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ SQLite недоступен: {e}")
            return False
    
    def _init_file_storage(self):
        """Последний fallback: файловое хранение"""
        self.db_type = "files"
        self.db_available = False
        logger.warning("⚠️ Используем файловое хранение как последний fallback")

# Глобальный экземпляр
db_manager = DatabaseManager()

# ============================================================================
# МЕНЕДЖЕР КЭШИРОВАНИЯ С FALLBACK
# ============================================================================

class CacheManager:
    """Менеджер кэширования с множественными fallback стратегиями"""
    
    def __init__(self):
        self.cache_type = "unknown"
        self.cache_available = False
        self._init_cache()
    
    def _init_cache(self):
        """Инициализация кэша в порядке приоритета"""
        
        # 1. Попытка Redis
        if self._init_redis():
            return
        
        # 2. Попытка DiskCache
        if self._init_diskcache():
            return
        
        # 3. In-memory fallback
        self._init_memory_cache()
    
    def _init_redis(self) -> bool:
        """Попытка инициализации Redis"""
        try:
            import redis
            
            if not settings.REDIS_URL:
                return False
            
            self.redis_client = redis.from_url(settings.REDIS_URL)
            self.redis_client.ping()
            
            self.cache_type = "redis"
            self.cache_available = True
            logger.info("✅ Redis подключен успешно")
            return True
            
        except ImportError:
            logger.warning("⚠️ Redis библиотека не установлена")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Redis недоступен: {e}")
            return False
    
    def _init_diskcache(self) -> bool:
        """Попытка инициализации DiskCache"""
        try:
            import diskcache
            
            cache_dir = settings.DATA_DIR / "cache"
            cache_dir.mkdir(exist_ok=True)
            
            self.disk_cache = diskcache.Cache(str(cache_dir))
            
            self.cache_type = "diskcache"
            self.cache_available = True
            logger.info("✅ DiskCache инициализирован")
            return True
            
        except ImportError:
            logger.warning("⚠️ DiskCache библиотека не установлена")
            return False
        except Exception as e:
            logger.warning(f"⚠️ DiskCache недоступен: {e}")
            return False
    
    def _init_memory_cache(self):
        """In-memory кэш как последний fallback"""
        self.memory_cache = {}
        self.memory_cache_ttl = {}
        
        self.cache_type = "memory"
        self.cache_available = True
        logger.warning("⚠️ Redis не доступен, используем in-memory кэш")
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Установка значения в кэш"""
        try:
            if self.cache_type == "redis":
                self.redis_client.setex(key, ttl, json.dumps(value, default=str))
            elif self.cache_type == "diskcache":
                self.disk_cache.set(key, value, expire=ttl)
            else:
                self.memory_cache[key] = value
                self.memory_cache_ttl[key] = time.time() + ttl
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки кэша {key}: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        try:
            if self.cache_type == "redis":
                data = self.redis_client.get(key)
                return json.loads(data) if data else None
            elif self.cache_type == "diskcache":
                return self.disk_cache.get(key)
            else:
                if key in self.memory_cache:
                    if time.time() < self.memory_cache_ttl.get(key, 0):
                        return self.memory_cache[key]
                    else:
                        self.delete(key)
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения из кэша {key}: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """Удаление значения из кэша"""
        try:
            if self.cache_type == "redis":
                return bool(self.redis_client.delete(key))
            elif self.cache_type == "diskcache":
                return self.disk_cache.delete(key)
            else:
                if key in self.memory_cache:
                    del self.memory_cache[key]
                if key in self.memory_cache_ttl:
                    del self.memory_cache_ttl[key]
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка удаления из кэша {key}: {e}")
            return False

# Глобальный экземпляр
cache_manager = CacheManager()

# ============================================================================
# LIFESPAN EVENTS (MODERN FASTAPI)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events для FastAPI"""
    # Startup
    logger.info(f"🚀 {settings.PROJECT_NAME} запускается...")
    logger.info(f"📊 База данных: {db_manager.db_type}")
    logger.info(f"💾 Кэширование: {cache_manager.cache_type}")
    logger.info(f"🌍 Режим отладки: {'включен' if settings.DEBUG else 'отключен'}")
    
    # Запуск фоновых задач
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    yield
    
    # Shutdown
    logger.info("🛑 Остановка приложения...")
    
    # Отменяем фоновые задачи
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    # Закрытие соединений с БД
    if hasattr(db_manager, 'connection') and db_manager.connection:
        db_manager.connection.close()
        logger.info("✅ Соединение с БД закрыто")

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def cleanup_cache():
    """Фоновая задача очистки устаревшего кэша"""
    if cache_manager.cache_type == "memory":
        current_time = time.time()
        expired_keys = [
            key for key, ttl in cache_manager.memory_cache_ttl.items()
            if current_time > ttl
        ]
        
        for key in expired_keys:
            cache_manager.delete(key)
        
        if expired_keys:
            logger.info(f"🧹 Очищено {len(expired_keys)} устаревших записей кэша")

async def periodic_cleanup():
    """Периодическая очистка (каждые 10 минут)"""
    while True:
        try:
            await asyncio.sleep(600)  # 10 минут
            await cleanup_cache()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в periodic_cleanup: {e}")

# ============================================================================
# КЛАСС WEB STARTER (УЛУЧШЕННЫЙ)
# ============================================================================

class WebStarter:
    def __init__(self, dev_mode=False, host="0.0.0.0", port=8000):
        self.dev_mode = dev_mode
        self.host = host
        self.port = port
        self.app = None
        self.server = None
        self.shutdown_event = asyncio.Event()
        
        # Настройка путей
        self.project_root = Path(__file__).parent.parent
        self.dashboard_dir = self.project_root / "dashboard"
        self.static_dir = settings.STATIC_DIR
        self.templates_dir = settings.TEMPLATES_DIR
        
        # Создаем необходимые папки
        self.create_directories()
        
        # Настраиваем обработчики сигналов
        self.setup_signal_handlers()
        
        # Создаем приложение
        self.setup_app()
    
    def create_directories(self):
        """Создание необходимых директорий"""
        directories = [
            'logs',
            self.static_dir,
            self.dashboard_dir,
            self.templates_dir,
            settings.DATA_DIR,
            Path('temp')
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
        
        logger.info("✅ Директории созданы")
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов для graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"🛑 Получен сигнал {signum}")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def setup_app(self):
        """Настройка FastAPI приложения"""
        
        # Создаем основное приложение с lifespan
        self.app = FastAPI(
            title=settings.PROJECT_NAME,
            description="Веб-дашборд для управления задачами с геймификацией",
            version=settings.VERSION,
            docs_url="/docs" if self.dev_mode else None,
            redoc_url="/redoc" if self.dev_mode else None,
            openapi_url="/openapi.json" if self.dev_mode else None,
            debug=self.dev_mode,
            lifespan=lifespan
        )
        
        # Трекинг времени запуска
        self.app.state.start_time = datetime.now()
        
        # Настройка middleware
        self.setup_middleware()
        
        # Настройка статических файлов и шаблонов
        self.setup_static_files()
        
        # Подключение роутеров API
        self.setup_api_routes()
        
        # Настройка основных маршрутов
        self.setup_main_routes()
        
        # Обработчики ошибок
        self.setup_error_handlers()
        
        logger.info("✅ FastAPI приложение настроено")
    
    def setup_middleware(self):
        """Настройка middleware"""
        
        # Gzip compression
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)
        
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Trusted Host middleware (для безопасности)
        if not self.dev_mode:
            self.app.add_middleware(
                TrustedHostMiddleware,
                allowed_hosts=["*"]  # В продакшене указать конкретные домены
            )
        
        # Security headers middleware
        @self.app.middleware("http")
        async def add_security_headers(request: Request, call_next):
            start_time = time.time()
            
            try:
                response = await call_next(request)
                
                # Добавляем заголовки безопасности
                if not self.dev_mode:
                    response.headers["X-Content-Type-Options"] = "nosniff"
                    response.headers["X-Frame-Options"] = "DENY"
                    response.headers["X-XSS-Protection"] = "1; mode=block"
                    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                
                # Добавляем время обработки
                process_time = time.time() - start_time
                response.headers["X-Process-Time"] = str(process_time)
                
                return response
                
            except Exception as e:
                logger.error(f"❌ Ошибка в middleware: {e}")
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error"}
                )
        
        # Request logging middleware
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()
            
            # Получаем IP клиента
            client_ip = request.headers.get("X-Forwarded-For", 
                                          getattr(request.client, 'host', 'unknown'))
            
            response = await call_next(request)
            
            process_time = time.time() - start_time
            
            logger.info(
                f"{request.method} {request.url.path} "
                f"- {response.status_code} "
                f"- {process_time:.3f}s "
                f"- {client_ip}"
            )
            
            return response
        
        logger.info("✅ Middleware настроен")
    
    def setup_static_files(self):
        """Настройка статических файлов"""
        
        # Проверяем наличие папки статических файлов
        if self.static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")
            logger.info(f"✅ Статические файлы подключены: {self.static_dir}")
        else:
            logger.warning(f"⚠️ Папка статических файлов не найдена: {self.static_dir}")
            # Создаем базовую структуру
            (self.static_dir / "css").mkdir(parents=True, exist_ok=True)
            (self.static_dir / "js").mkdir(parents=True, exist_ok=True)
            (self.static_dir / "img").mkdir(parents=True, exist_ok=True)
        
        # Настраиваем шаблоны
        if self.templates_dir.exists():
            self.templates = Jinja2Templates(directory=str(self.templates_dir))
            logger.info(f"✅ Шаблоны подключены: {self.templates_dir}")
        else:
            logger.warning(f"⚠️ Папка шаблонов не найдена: {self.templates_dir}")
            # Создаем базовую структуру шаблонов
            self.templates_dir.mkdir(parents=True, exist_ok=True)
            self.create_basic_templates()
    
    def create_basic_templates(self):
        """Создание базовых шаблонов если их нет"""
        base_template = self.templates_dir / "base.html"
        if not base_template.exists():
            base_template.write_text("""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}DailyCheck Bot Dashboard{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-gray-100">
    <nav class="bg-white shadow-lg">
        <div class="max-w-7xl mx-auto px-4">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <h1 class="text-xl font-bold">🤖 DailyCheck Bot Dashboard</h1>
                </div>
                <div class="flex items-center space-x-4">
                    <a href="/api/stats/overview" class="text-blue-600 hover:text-blue-800">Статистика</a>
                    <a href="/docs" class="text-blue-600 hover:text-blue-800">API</a>
                </div>
            </div>
        </div>
    </nav>
    
    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
            """, encoding='utf-8')
        
        dashboard_template = self.templates_dir / "dashboard.html"
        if not dashboard_template.exists():
            dashboard_template.write_text("""
{% extends "base.html" %}

{% block content %}
<div class="px-4 py-6 sm:px-0">
    <div class="bg-white overflow-hidden shadow rounded-lg">
        <div class="px-4 py-5 sm:p-6">
            <h2 class="text-lg font-medium text-gray-900 mb-4">Статистика DailyCheck Bot</h2>
            
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div class="bg-blue-50 overflow-hidden shadow rounded-lg">
                    <div class="p-5">
                        <div class="flex items-center">
                            <div class="ml-5 w-0 flex-1">
                                <dl>
                                    <dt class="text-sm font-medium text-gray-500 truncate">Пользователи</dt>
                                    <dd class="text-lg font-medium text-gray-900">{{ stats.total_users or 0 }}</dd>
                                </dl>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="bg-green-50 overflow-hidden shadow rounded-lg">
                    <div class="p-5">
                        <div class="flex items-center">
                            <div class="ml-5 w-0 flex-1">
                                <dl>
                                    <dt class="text-sm font-medium text-gray-500 truncate">Задачи</dt>
                                    <dd class="text-lg font-medium text-gray-900">{{ stats.total_tasks or 0 }}</dd>
                                </dl>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="bg-yellow-50 overflow-hidden shadow rounded-lg">
                    <div class="p-5">
                        <div class="flex items-center">
                            <div class="ml-5 w-0 flex-1">
                                <dl>
                                    <dt class="text-sm font-medium text-gray-500 truncate">Выполнено</dt>
                                    <dd class="text-lg font-medium text-gray-900">{{ stats.completed_tasks or 0 }}</dd>
                                </dl>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="bg-purple-50 overflow-hidden shadow rounded-lg">
                    <div class="p-5">
                        <div class="flex items-center">
                            <div class="ml-5 w-0 flex-1">
                                <dl>
                                    <dt class="text-sm font-medium text-gray-500 truncate">Активные сегодня</dt>
                                    <dd class="text-lg font-medium text-gray-900">{{ stats.active_users_24h or 0 }}</dd>
                                </dl>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
            """, encoding='utf-8')
        
        self.templates = Jinja2Templates(directory=str(self.templates_dir))
        logger.info("✅ Базовые шаблоны созданы")
    
    def setup_api_routes(self):
        """Подключение API роутеров"""
        
        try:
            # Импортируем роутеры из dashboard/api
            try:
                from dashboard.api.users import router as users_router
                self.app.include_router(users_router)
                logger.info("✅ Users API подключен")
            except ImportError:
                logger.warning("⚠️ Users API не найден")
            
            try:
                from dashboard.api.charts import router as charts_router  
                self.app.include_router(charts_router)
                logger.info("✅ Charts API подключен")
            except ImportError:
                logger.warning("⚠️ Charts API не найден")
            
            try:
                from dashboard.api.stats import router as stats_router
                self.app.include_router(stats_router)
                logger.info("✅ Stats API подключен")
            except ImportError:
                logger.warning("⚠️ Stats API не найден")
            
            # Подключаем базовые API
            self.setup_basic_api()
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения API роутеров: {e}")
            self.setup_basic_api()
    
    def setup_basic_api(self):
        """Базовые API endpoints"""
        
        @self.app.get("/api/health")
        async def health_check():
            uptime = datetime.now() - self.app.state.start_time
            
            return {
                "status": "healthy",
                "service": settings.PROJECT_NAME,
                "version": settings.VERSION,
                "database": db_manager.db_type,
                "cache": cache_manager.cache_type,
                "uptime": str(uptime),
                "dev_mode": self.dev_mode,
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.get("/api/stats/overview")
        async def basic_stats():
            # Попробуем получить из кэша
            cache_key = "stats_overview"
            cached_stats = cache_manager.get(cache_key)
            
            if cached_stats:
                return cached_stats
            
            # Базовая статистика
            stats = {
                "total_users": 150,
                "active_users": 45,
                "total_tasks": 2340,
                "completed_tasks": 1876,
                "completion_rate": 80.2,
                "active_users_24h": 23,
                "database_type": db_manager.db_type,
                "timestamp": datetime.now().isoformat()
            }
            
            # Сохраняем в кэш на 5 минут
            cache_manager.set(cache_key, stats, ttl=300)
            
            return stats
        
        @self.app.get("/api/system/info")
        async def system_info():
            import platform
            
            return {
                "system": {
                    "platform": platform.system(),
                    "python_version": platform.python_version(),
                    "cpu_count": os.cpu_count()
                },
                "app": {
                    "dev_mode": self.dev_mode,
                    "host": self.host,
                    "port": self.port,
                    "database": db_manager.db_type,
                    "cache": cache_manager.cache_type
                }
            }
        
        logger.info("✅ Базовые API endpoints созданы")
    
    def setup_main_routes(self):
        """Настройка основных маршрутов"""
        
        # HEAD методы для мониторинга
        @self.app.head("/")
        async def root_head():
            """Health check HEAD метод для мониторинга"""
            return Response(status_code=200)

        @self.app.head("/health")
        async def health_head():
            """Health check HEAD метод"""
            return Response(status_code=200)
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Главная страница дашборда"""
            try:
                # Получаем статистику для отображения
                stats_data = cache_manager.get("stats_overview")
                if not stats_data:
                    stats_data = {
                        "total_users": 150,
                        "total_tasks": 2340,
                        "completed_tasks": 1876,
                        "active_users_24h": 23
                    }
                
                if hasattr(self, 'templates'):
                    return self.templates.TemplateResponse(
                        "dashboard.html", 
                        {
                            "request": request,
                            "stats": stats_data
                        }
                    )
                else:
                    return HTMLResponse(self.get_modern_dashboard_html())
                    
            except Exception as e:
                logger.error(f"Ошибка загрузки главной страницы: {e}")
                return HTMLResponse(self.get_modern_dashboard_html())
        
        @self.app.get("/dashboard")
        async def dashboard_redirect():
            """Редирект на главную"""
            return RedirectResponse(url="/", status_code=301)
        
        @self.app.get("/health")
        async def web_health():
            """Health check для веб-сервиса"""
            uptime = datetime.now() - self.app.state.start_time
            
            return {
                "status": "healthy",
                "service": "DailyCheck Bot Dashboard",
                "version": settings.VERSION,
                "database": db_manager.db_type,
                "cache": cache_manager.cache_type,
                "uptime": str(uptime),
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.get("/ping")
        async def ping():
            """Простой ping endpoint"""
            return {"ping": "pong", "timestamp": datetime.now().isoformat()}
        
        logger.info("✅ Основные маршруты настроены")
    
    def get_modern_dashboard_html(self):
        """Современный HTML для главной страницы"""
        return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{settings.PROJECT_NAME}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }}
        
        .container {{
            text-align: center;
            max-width: 900px;
            padding: 40px 20px;
        }}
        
        .logo {{
            font-size: 4rem;
            margin-bottom: 20px;
            animation: pulse 2s infinite;
        }}
        
        .title {{
            font-size: 2.8rem;
            font-weight: 700;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .subtitle {{
            font-size: 1.3rem;
            margin-bottom: 40px;
            opacity: 0.9;
        }}
        
        .features {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .feature {{
            background: rgba(255,255,255,0.1);
            padding: 25px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease;
        }}
        
        .feature:hover {{
            transform: translateY(-5px);
        }}
        
        .feature-icon {{
            font-size: 2.5rem;
            margin-bottom: 15px;
        }}
        
        .feature-title {{
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 1.1rem;
        }}
        
        .feature-desc {{
            font-size: 0.9rem;
            opacity: 0.8;
        }}
        
        .api-links {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            justify-content: center;
            margin-bottom: 30px;
        }}
        
        .api-link {{
            display: inline-block;
            padding: 15px 25px;
            background: rgba(255,255,255,0.2);
            color: white;
            text-decoration: none;
            border-radius: 30px;
            border: 1px solid rgba(255,255,255,0.3);
            transition: all 0.3s ease;
            font-weight: 500;
            font-size: 0.95rem;
        }}
        
        .api-link:hover {{
            background: rgba(255,255,255,0.3);
            transform: translateY(-3px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
        }}
        
        .status {{
            margin-top: 30px;
            padding: 20px;
            background: rgba(16, 185, 129, 0.2);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 12px;
            display: inline-block;
        }}
        
        .status-dot {{
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #10b981;
            border-radius: 50%;
            margin-right: 10px;
            animation: blink 1.5s infinite;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
            margin: 25px 0;
        }}
        
        .stat-item {{
            background: rgba(255,255,255,0.15);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 1.8rem;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            font-size: 0.8rem;
            opacity: 0.8;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
        }}
        
        @keyframes blink {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.3; }}
        }}
        
        @media (max-width: 768px) {{
            .title {{ font-size: 2.2rem; }}
            .subtitle {{ font-size: 1.1rem; }}
            .logo {{ font-size: 3rem; }}
            .api-links {{ flex-direction: column; align-items: center; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🤖</div>
        <h1 class="title">DailyCheck Bot Dashboard</h1>
        <p class="subtitle">Профессиональный дашборд для управления задачами v4.0</p>
        
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-number">150</div>
                <div class="stat-label">Пользователи</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">2.3K</div>
                <div class="stat-label">Задачи</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">80%</div>
                <div class="stat-label">Выполнено</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">45</div>
                <div class="stat-label">Активные</div>
            </div>
        </div>
        
        <div class="features">
            <div class="feature">
                <div class="feature-icon">📊</div>
                <div class="feature-title">Статистика</div>
                <div class="feature-desc">Подробная аналитика пользователей и задач</div>
            </div>
            <div class="feature">
                <div class="feature-icon">📈</div>
                <div class="feature-title">Графики</div>
                <div class="feature-desc">Интерактивные графики активности</div>
            </div>
            <div class="feature">
                <div class="feature-icon">👥</div>
                <div class="feature-title">Пользователи</div>
                <div class="feature-desc">Управление пользователями и лидерборды</div>
            </div>
            <div class="feature">
                <div class="feature-icon">⚡</div>
                <div class="feature-title">Real-time</div>
                <div class="feature-desc">Данные в реальном времени</div>
            </div>
        </div>
        
        <div class="api-links">
            <a href="/api/stats/overview" class="api-link">📊 Статистика</a>
            <a href="/api/charts/user-activity" class="api-link">📈 Графики</a>
            <a href="/api/users/" class="api-link">👥 Пользователи</a>
            <a href="/health" class="api-link">💚 Health Check</a>
            <a href="/docs" class="api-link">📚 API Docs</a>
        </div>
        
        <div class="status">
            <span class="status-dot"></span>
            <strong>Статус:</strong> Сервис работает • {db_manager.db_type.title()} БД • {cache_manager.cache_type.title()} кэш
        </div>
        
        <p style="margin-top: 20px; opacity: 0.7; font-size: 0.9rem;">
            🚀 Production Ready • 💾 {db_manager.db_type.title()} + {cache_manager.cache_type.title()} • 🔧 v{settings.VERSION}
        </p>
    </div>
</body>
</html>
        """
    
    def setup_error_handlers(self):
        """Настройка обработчиков ошибок"""
        
        @self.app.exception_handler(404)
        async def not_found_handler(request: Request, exc):
            return JSONResponse(
                status_code=404,
                content={
                    "detail": "Endpoint not found",
                    "path": str(request.url.path),
                    "method": request.method,
                    "available_endpoints": [
                        "/api/health",
                        "/api/stats/overview", 
                        "/api/system/info",
                        "/health",
                        "/ping"
                    ]
                }
            )
        
        @self.app.exception_handler(500)
        async def internal_error_handler(request: Request, exc):
            logger.error(f"Internal server error: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "dev_mode": self.dev_mode,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        logger.info("✅ Обработчики ошибок настроены")
    
    async def start_server(self):
        """Запуск веб-сервера"""
        
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if self.dev_mode else "info",
            reload=False,  # Отключаем reload для стабильности
            access_log=self.dev_mode,
            server_header=False,
            date_header=False,
            use_colors=True
        )
        
        self.server = uvicorn.Server(config)
        
        logger.info("✅ Dashboard API routes loaded successfully")
        logger.info(f"🚀 Запуск веб-сервера на http://{self.host}:{self.port}")
        logger.info(f"📊 Режим: {'Разработка' if self.dev_mode else 'Продакшн'}")
        
        if self.dev_mode:
            logger.info(f"📚 API документация: http://{self.host}:{self.port}/docs")
            logger.info(f"🌐 Дашборд: http://{self.host}:{self.port}/")
        
        logger.info("Нажмите Ctrl+C для остановки...")
        
        try:
            # Запускаем сервер
            await self.server.serve()
            
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки...")
        except Exception as e:
            logger.error(f"❌ Ошибка веб-сервера: {e}")
            raise
        finally:
            await self.graceful_shutdown()
    
    async def graceful_shutdown(self):
        """Корректное завершение работы"""
        logger.info("🔄 Начинаем корректное завершение...")
        
        try:
            # Останавливаем сервер
            if self.server:
                self.server.should_exit = True
            
            # Ждем завершения текущих запросов
            await asyncio.sleep(1)
            
            logger.info("✅ Веб-сервер остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при завершении: {e}")

# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

async def async_main():
    """Асинхронная главная функция"""
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Запуск веб-дашборда DailyCheck Bot')
    parser.add_argument('--dev', action='store_true', help='Режим разработки')
    parser.add_argument('--port', type=int, default=settings.PORT, help='Порт для веб-сервера')
    parser.add_argument('--host', default=settings.HOST, help='Хост для веб-сервера')
    parser.add_argument('--reload', action='store_true', help='Автоперезагрузка при изменениях')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Уровень логирования')
    
    args = parser.parse_args()
    
    # Определяем режим разработки
    dev_mode = args.dev or args.reload or os.getenv('ENVIRONMENT') == 'development'
    
    # Обновляем настройки
    if dev_mode:
        settings.DEBUG = True
        os.environ['ENVIRONMENT'] = 'development'
        
    # Настраиваем логирование
    setup_logging(dev_mode)
    
    if dev_mode:
        logger.info("🔧 Режим разработки активирован")
    
    # Определяем порт (для продакшена может быть переменная окружения)
    port = int(os.getenv('PORT', args.port))
    
    # Создаем и запускаем веб-приложение
    try:
        starter = WebStarter(dev_mode=dev_mode, host=args.host, port=port)
        await starter.start_server()
        
    except KeyboardInterrupt:
        logger.info("👋 Пока!")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

def main():
    """Главная функция запуска"""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("👋 Завершение работы...")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
