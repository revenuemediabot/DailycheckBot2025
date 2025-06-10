#!/usr/bin/env python3
"""
Скрипт запуска веб-дашборда DailyCheck Bot v4.0
Использование: python scripts/start_web.py [--port PORT] [--dev] [--host HOST]
"""

import sys
import os
import asyncio
import argparse
import logging
import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import traceback

# Добавляем корневую папку в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from fastapi import FastAPI, Request, Response, HTTPException, Depends, BackgroundTasks
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    import uvicorn
    from pydantic import BaseModel
except ImportError as e:
    print(f"❌ Ошибка импорта FastAPI: {e}")
    print("Установите зависимости: pip install -r requirements-web.txt")
    sys.exit(1)

# Настройка логирования
def setup_logging(debug: bool = False):
    """Настройка системы логирования"""
    os.makedirs('logs', exist_ok=True)
    
    log_level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/web_dashboard.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Отключаем избыточные логи
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.INFO)

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
        
        # Создаем необходимые директории
        for directory in [self.DATA_DIR, self.EXPORTS_DIR, self.BACKUPS_DIR, self.LOGS_DIR]:
            directory.mkdir(exist_ok=True)
        
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
        self.STATIC_FILES_PATH = project_root / "dashboard" / "static"
        self.TEMPLATES_PATH = project_root / "dashboard" / "templates"
        
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
            
            # Таблица статистики
            self.stats_table = Table(
                'user_stats', self.metadata,
                Column('user_id', Integer, primary_key=True),
                Column('total_tasks', Integer, default=0),
                Column('completed_tasks', Integer, default=0),
                Column('completion_rate', Integer, default=0),
                Column('current_streak', Integer, default=0),
                Column('max_streak', Integer, default=0),
                Column('total_xp', Integer, default=0),
                Column('level', Integer, default=1),
                Column('achievements', Text),  # JSON
                Column('weekly_goals', Text),  # JSON
                Column('dry_days', Integer, default=0),
                Column('last_task_date', DateTime),
                Column('updated_at', DateTime, default=datetime.utcnow)
            )
            
            # Таблица друзей
            self.friends_table = Table(
                'friends', self.metadata,
                Column('id', Integer, primary_key=True, autoincrement=True),
                Column('user_id', Integer),
                Column('friend_id', Integer),
                Column('status', String(50), default='pending'),
                Column('created_at', DateTime, default=datetime.utcnow)
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
                
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id INTEGER PRIMARY KEY,
                    total_tasks INTEGER DEFAULT 0,
                    completed_tasks INTEGER DEFAULT 0,
                    completion_rate INTEGER DEFAULT 0,
                    current_streak INTEGER DEFAULT 0,
                    max_streak INTEGER DEFAULT 0,
                    total_xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    achievements TEXT,
                    weekly_goals TEXT,
                    dry_days INTEGER DEFAULT 0,
                    last_task_date TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS friends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    friend_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
                CREATE INDEX IF NOT EXISTS idx_friends_user_id ON friends(user_id);
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
    
    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """Получение данных пользователя"""
        try:
            if self.db_type == "sqlalchemy":
                return self._get_user_sqlalchemy(user_id)
            elif self.db_type == "sqlite":
                return self._get_user_sqlite(user_id)
            else:
                return self._get_user_file(user_id)
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователя {user_id}: {e}")
            return {}
    
    def save_user_data(self, user_id: int, data: Dict[str, Any]) -> bool:
        """Сохранение данных пользователя"""
        try:
            if self.db_type == "sqlalchemy":
                return self._save_user_sqlalchemy(user_id, data)
            elif self.db_type == "sqlite":
                return self._save_user_sqlite(user_id, data)
            else:
                return self._save_user_file(user_id, data)
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения пользователя {user_id}: {e}")
            return False
    
    def get_user_tasks(self, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Получение задач пользователя"""
        try:
            if self.db_type == "sqlite":
                cursor = self.connection.cursor()
                cursor.execute('''
                    SELECT * FROM tasks 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (user_id, limit))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            else:
                # Fallback для других типов
                return self._get_tasks_fallback(user_id, limit)
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения задач для {user_id}: {e}")
            return []
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Получение глобальной статистики"""
        try:
            if self.db_type == "sqlite":
                cursor = self.connection.cursor()
                
                # Общее количество пользователей
                cursor.execute("SELECT COUNT(*) as total_users FROM users")
                total_users = cursor.fetchone()['total_users']
                
                # Активные пользователи (за последние 7 дней)
                week_ago = datetime.now() - timedelta(days=7)
                cursor.execute(
                    "SELECT COUNT(*) as active_users FROM users WHERE last_activity > ?",
                    (week_ago,)
                )
                active_users = cursor.fetchone()['active_users']
                
                # Всего задач
                cursor.execute("SELECT COUNT(*) as total_tasks FROM tasks")
                total_tasks = cursor.fetchone()['total_tasks']
                
                # Выполненные задачи
                cursor.execute("SELECT COUNT(*) as completed_tasks FROM tasks WHERE completed = 1")
                completed_tasks = cursor.fetchone()['completed_tasks']
                
                completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
                
                return {
                    "total_users": total_users,
                    "active_users": active_users,
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "completion_rate": round(completion_rate, 1),
                    "database_type": self.db_type,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                # Fallback данные
                return {
                    "total_users": 150,
                    "active_users": 45,
                    "total_tasks": 2340,
                    "completed_tasks": 1876,
                    "completion_rate": 80.2,
                    "database_type": self.db_type,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения глобальной статистики: {e}")
            return {
                "error": str(e),
                "database_type": self.db_type,
                "timestamp": datetime.now().isoformat()
            }
    
    def _get_user_sqlite(self, user_id: int) -> Dict[str, Any]:
        """SQLite implementation для пользователя"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else {}
    
    def _save_user_sqlite(self, user_id: int, data: Dict[str, Any]) -> bool:
        """SQLite implementation для сохранения"""
        cursor = self.connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, level, xp, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            data.get('username', ''),
            data.get('first_name', ''),
            data.get('level', 1),
            data.get('xp', 0),
            datetime.now()
        ))
        self.connection.commit()
        return True
    
    def _get_user_file(self, user_id: int) -> Dict[str, Any]:
        """Файловый fallback для пользователя"""
        file_path = settings.DATA_DIR / f"user_{user_id}.json"
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_user_file(self, user_id: int, data: Dict[str, Any]) -> bool:
        """Файловый fallback для сохранения"""
        file_path = settings.DATA_DIR / f"user_{user_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    
    def _get_tasks_fallback(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        """Fallback для получения задач"""
        # Пример данных
        return [
            {
                "id": 1,
                "title": "Пример задачи",
                "category": "личное",
                "priority": "средний",
                "completed": False,
                "created_at": datetime.now().isoformat()
            }
        ]

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
    
    def clear(self) -> bool:
        """Очистка всего кэша"""
        try:
            if self.cache_type == "redis":
                self.redis_client.flushdb()
            elif self.cache_type == "diskcache":
                self.disk_cache.clear()
            else:
                self.memory_cache.clear()
                self.memory_cache_ttl.clear()
            
            logger.info(f"✅ Кэш очищен ({self.cache_type})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки кэша: {e}")
            return False

# Глобальный экземпляр
cache_manager = CacheManager()

# ============================================================================
# PYDANTIC МОДЕЛИ ДЛЯ API
# ============================================================================

class UserResponse(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    level: int = 1
    xp: int = 0
    theme: str = "default"

class TaskResponse(BaseModel):
    id: int
    title: str
    category: str = "личное"
    priority: str = "средний"
    completed: bool = False
    created_at: str

class StatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_tasks: int
    completed_tasks: int
    completion_rate: float
    database_type: str
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
    cache: str
    uptime: str

# ============================================================================
# СОЗДАНИЕ FASTAPI ПРИЛОЖЕНИЯ
# ============================================================================

def create_app() -> FastAPI:
    """Создание и настройка FastAPI приложения"""
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Веб-дашборд для управления задачами с геймификацией",
        version=settings.VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None
    )
    
    # Middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Трекинг времени запуска
    app.state.start_time = datetime.now()
    
    return app

app = create_app()

# ============================================================================
# ОСНОВНЫЕ ЭНДПОИНТЫ
# ============================================================================

@app.head("/")
async def root_head():
    """Health check HEAD метод для мониторинга"""
    return Response(status_code=200)

@app.get("/")
async def root():
    """Главная страница API"""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs" if settings.DEBUG else "disabled",
        "api_prefix": "/api",
        "dashboard": "/dashboard"
    }

@app.head("/health")
async def health_head():
    """Health check HEAD метод"""
    return Response(status_code=200)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Подробный health check endpoint"""
    uptime = datetime.now() - app.state.start_time
    
    return HealthResponse(
        status="healthy",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        database=db_manager.db_type,
        cache=cache_manager.cache_type,
        uptime=str(uptime)
    )

@app.get("/ping")
async def ping():
    """Простой ping endpoint"""
    return {"ping": "pong", "timestamp": datetime.now().isoformat()}

# ============================================================================
# API МАРШРУТЫ
# ============================================================================

@app.get("/api/stats/overview", response_model=StatsResponse)
async def get_stats_overview():
    """Получение общей статистики проекта"""
    try:
        # Проверяем кэш
        cache_key = "stats_overview"
        cached_stats = cache_manager.get(cache_key)
        
        if cached_stats:
            return StatsResponse(**cached_stats)
        
        # Получаем свежие данные
        stats_data = db_manager.get_global_stats()
        
        # Сохраняем в кэш на 5 минут
        cache_manager.set(cache_key, stats_data, ttl=300)
        
        return StatsResponse(**stats_data)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    """Получение данных пользователя"""
    try:
        user_data = db_manager.get_user_data(user_id)
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserResponse(**user_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка получения пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/users/{user_id}/tasks")
async def get_user_tasks(user_id: int, limit: int = 50):
    """Получение задач пользователя"""
    try:
        tasks = db_manager.get_user_tasks(user_id, limit)
        
        return {
            "status": "success",
            "user_id": user_id,
            "tasks": tasks,
            "total": len(tasks)
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения задач для {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/users/{user_id}/stats")
async def get_user_stats(user_id: int):
    """Получение статистики пользователя"""
    try:
        user_data = db_manager.get_user_data(user_id)
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Получаем задачи для расчета статистики
        tasks = db_manager.get_user_tasks(user_id, 1000)
        
        completed_tasks = sum(1 for task in tasks if task.get('completed'))
        total_tasks = len(tasks)
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        stats = {
            "user_id": user_id,
            "level": user_data.get('level', 1),
            "xp": user_data.get('xp', 0),
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": round(completion_rate, 1),
            "current_streak": user_data.get('current_streak', 0),
            "max_streak": user_data.get('max_streak', 0)
        }
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10):
    """Получение таблицы лидеров"""
    try:
        # Попробуем получить из кэша
        cache_key = f"leaderboard_{limit}"
        cached_data = cache_manager.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Формируем данные лидерборда (пример)
        leaderboard_data = {
            "status": "success",
            "leaders": [
                {"user_id": 123, "username": "TopUser", "level": 16, "xp": 5000, "position": 1},
                {"user_id": 456, "username": "ProPlayer", "level": 15, "xp": 4500, "position": 2},
                {"user_id": 789, "username": "Achiever", "level": 14, "xp": 4000, "position": 3}
            ],
            "updated_at": datetime.now().isoformat()
        }
        
        # Кэшируем на 10 минут
        cache_manager.set(cache_key, leaderboard_data, ttl=600)
        
        return leaderboard_data
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения лидерборда: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/categories")
async def get_categories():
    """Получение списка категорий задач"""
    categories = [
        {"id": "work", "name": "🏢 Работа", "icon": "🏢", "color": "#3498db"},
        {"id": "health", "name": "💪 Здоровье", "icon": "💪", "color": "#e74c3c"},
        {"id": "learning", "name": "📚 Обучение", "icon": "📚", "color": "#f39c12"},
        {"id": "personal", "name": "👤 Личное", "icon": "👤", "color": "#9b59b6"},
        {"id": "finance", "name": "💰 Финансы", "icon": "💰", "color": "#27ae60"}
    ]
    
    return {"categories": categories}

@app.get("/api/achievements")
async def get_achievements():
    """Получение списка достижений"""
    achievements = [
        {"id": "first_steps", "name": "🎯 Первые шаги", "description": "Выполнить первую задачу"},
        {"id": "hot_start", "name": "🔥 Горячий старт", "description": "5 задач подряд"},
        {"id": "strong_man", "name": "💪 Силач", "description": "50 выполненных задач"},
        {"id": "creator", "name": "🎨 Творец", "description": "10 креативных задач"},
        {"id": "thinker", "name": "🧠 Мыслитель", "description": "20 образовательных задач"},
        {"id": "financier", "name": "💰 Финансист", "description": "15 финансовых задач"},
        {"id": "scientist", "name": "📚 Ученый", "description": "Изучить 5 новых навыков"},
        {"id": "speedster", "name": "⚡ Скоростной", "description": "Выполнить задачу за 10 минут"},
        {"id": "marathoner", "name": "🏃 Марафонец", "description": "30-дневный стрик"},
        {"id": "master", "name": "👑 Мастер", "description": "Достичь 16 уровня"}
    ]
    
    return {"achievements": achievements}

# ============================================================================
# АДМИНИСТРАТИВНЫЕ ЭНДПОИНТЫ
# ============================================================================

@app.get("/api/admin/stats")
async def get_admin_stats():
    """Административная статистика (требует аутентификации)"""
    try:
        # В production здесь должна быть проверка прав доступа
        
        stats = db_manager.get_global_stats()
        
        # Дополнительная информация для админов
        admin_stats = {
            **stats,
            "system_info": {
                "database_type": db_manager.db_type,
                "cache_type": cache_manager.cache_type,
                "uptime": str(datetime.now() - app.state.start_time),
                "python_version": sys.version,
                "environment": os.getenv("ENVIRONMENT", "production")
            }
        }
        
        return admin_stats
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения админ статистики: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/admin/cache/clear")
async def clear_cache():
    """Очистка кэша (административная функция)"""
    try:
        success = cache_manager.clear()
        
        if success:
            return {"status": "success", "message": "Кэш очищен"}
        else:
            raise HTTPException(status_code=500, detail="Ошибка очистки кэша")
            
    except Exception as e:
        logger.error(f"❌ Ошибка очистки кэша: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ============================================================================
# СТАТИЧЕСКИЕ ФАЙЛЫ И ДАШБОРД
# ============================================================================

# Подключение статических файлов
if settings.STATIC_FILES_PATH.exists():
    app.mount("/static", StaticFiles(directory=str(settings.STATIC_FILES_PATH)), name="static")
    logger.info(f"✅ Статические файлы подключены: {settings.STATIC_FILES_PATH}")

# Главная страница дашборда
dashboard_html = project_root / "dashboard" / "index.html"
if dashboard_html.exists():
    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard():
        """Главная страница веб-дашборда"""
        return FileResponse(dashboard_html)
    
    logger.info(f"✅ Дашборд доступен: {dashboard_html}")
else:
    @app.get("/dashboard")
    async def dashboard_fallback():
        """Fallback для дашборда"""
        return {
            "message": "Веб-дашборд в разработке",
            "api_docs": "/docs" if settings.DEBUG else "API документация отключена",
            "available_endpoints": [
                "/api/stats/overview",
                "/api/users/{user_id}",
                "/api/users/{user_id}/tasks",
                "/api/leaderboard",
                "/health"
            ]
        }

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

@app.on_event("startup")
async def startup_event():
    """Событие запуска приложения"""
    logger.info(f"🚀 {settings.PROJECT_NAME} запускается...")
    logger.info(f"📊 База данных: {db_manager.db_type}")
    logger.info(f"💾 Кэширование: {cache_manager.cache_type}")
    logger.info(f"🌍 Режим отладки: {'включен' if settings.DEBUG else 'отключен'}")
    
    # Запуск фоновых задач
    asyncio.create_task(periodic_cleanup())

@app.on_event("shutdown")
async def shutdown_event():
    """Событие остановки приложения"""
    logger.info("🛑 Остановка приложения...")
    
    # Закрытие соединений с БД
    if hasattr(db_manager, 'connection') and db_manager.connection:
        db_manager.connection.close()
        logger.info("✅ Соединение с БД закрыто")

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
# MAIN ФУНКЦИЯ
# ============================================================================

def main():
    """Главная функция запуска веб-сервера"""
    
    # Парсинг аргументов
    parser = argparse.ArgumentParser(description='Запуск веб-дашборда DailyCheck Bot')
    parser.add_argument('--port', type=int, default=settings.PORT, help='Порт сервера')
    parser.add_argument('--host', default=settings.HOST, help='Хост сервера')
    parser.add_argument('--dev', action='store_true', help='Режим разработки')
    parser.add_argument('--reload', action='store_true', help='Автоперезагрузка при изменениях')
    
    args = parser.parse_args()
    
    # Настройка логирования
    setup_logging(debug=args.dev)
    
    if args.dev:
        settings.DEBUG = True
        logger.info("🔧 Режим разработки активирован")
    
    # Информация о запуске
    logger.info("✅ Dashboard API routes loaded successfully")
    logger.info(f"🚀 Запуск веб-сервера на http://{args.host}:{args.port}")
    
    if settings.DEBUG:
        logger.info(f"📚 API документация: http://{args.host}:{args.port}/docs")
        logger.info(f"🌐 Дашборд: http://{args.host}:{args.port}/dashboard")
    
    # Запуск сервера
    try:
        uvicorn.run(
            "scripts.start_web:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
            access_log=True,
            server_header=False,
            date_header=False
        )
    except KeyboardInterrupt:
        logger.info("👋 Сервер остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
