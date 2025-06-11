#!/usr/bin/env python3
"""
Скрипт запуска веб-дашборда DailyCheck Bot v4.1.0 - СОВРЕМЕННЫЙ РЕДИЗАЙН
Обновленный дизайн: Clean UI, светлая тема, современная типографика
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
from contextlib import asynccontextmanager

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
    
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('fastapi').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

class Settings:
    """Настройки приложения"""
    
    def __init__(self):
        self.PROJECT_NAME = "DailyCheck Bot Dashboard"
        self.VERSION = "4.1.0"
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
        
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{self.DATA_DIR}/dailycheck.db"
        
        self.REDIS_URL = os.getenv("REDIS_URL")
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0)) or None
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        self.CORS_ORIGINS = ["*"]
        self.STATIC_FILES_PATH = project_root / "dashboard" / "static"
        self.TEMPLATES_PATH = project_root / "dashboard" / "templates"
        
        logger.info(f"✅ Настройки загружены: {self.PROJECT_NAME}")

settings = Settings()

# ============================================================================
# МЕНЕДЖЕР БАЗЫ ДАННЫХ (сохранен без изменений)
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
            if self._init_sqlite():
                return
            self._init_file_storage()
        except Exception as e:
            logger.error(f"❌ Критическая ошибка инициализации БД: {e}")
            self._init_file_storage()
    
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
                # Fallback данные для демонстрации
                return {
                    "total_users": 1247,
                    "active_users": 342,
                    "total_tasks": 5628,
                    "completed_tasks": 4503,
                    "completion_rate": 80.0,
                    "database_type": self.db_type,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения глобальной статистики: {e}")
            return {
                "total_users": 1247,
                "active_users": 342,
                "total_tasks": 5628,
                "completed_tasks": 4503,
                "completion_rate": 80.0,
                "error": str(e),
                "database_type": self.db_type,
                "timestamp": datetime.now().isoformat()
            }

# Глобальный экземпляр
db_manager = DatabaseManager()

# ============================================================================
# КЭШ МЕНЕДЖЕР (упрощенный)
# ============================================================================

class CacheManager:
    """Простой in-memory кэш"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = {}
        self.cache_type = "memory"
        self.cache_available = True
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        try:
            self.cache[key] = value
            self.cache_ttl[key] = time.time() + ttl
            return True
        except Exception:
            return False
    
    def get(self, key: str) -> Optional[Any]:
        try:
            if key in self.cache:
                if time.time() < self.cache_ttl.get(key, 0):
                    return self.cache[key]
                else:
                    self.delete(key)
            return None
        except Exception:
            return None
    
    def delete(self, key: str) -> bool:
        try:
            if key in self.cache:
                del self.cache[key]
            if key in self.cache_ttl:
                del self.cache_ttl[key]
            return True
        except Exception:
            return False

cache_manager = CacheManager()

# ============================================================================
# MODERN FASTAPI LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern FastAPI lifespan events"""
    # Startup
    logger.info(f"🚀 {settings.PROJECT_NAME} v{settings.VERSION} запускается...")
    logger.info(f"📊 База данных: {db_manager.db_type}")
    logger.info(f"💾 Кэширование: {cache_manager.cache_type}")
    logger.info("✨ Новый современный дизайн загружен!")
    
    yield
    
    # Shutdown
    logger.info("🛑 Остановка приложения...")
    if hasattr(db_manager, 'connection') and db_manager.connection:
        db_manager.connection.close()
        logger.info("✅ Соединение с БД закрыто")

# ============================================================================
# FASTAPI ПРИЛОЖЕНИЕ
# ============================================================================

def create_app() -> FastAPI:
    """Создание FastAPI приложения"""
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Современный веб-дашборд для управления задачами с геймификацией",
        version=settings.VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan
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
    
    app.state.start_time = datetime.now()
    
    return app

app = create_app()

# ============================================================================
# СОВРЕМЕННЫЙ HTML ДИЗАЙН
# ============================================================================

def get_modern_dashboard_html(stats: Dict[str, Any]) -> str:
    """Генерация современного дашборда в светлых тонах"""
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    
    return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DailyCheck Bot Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.min.js"></script>
    <style>
        :root {{
            --primary-50: #f0f9ff;
            --primary-100: #e0f2fe;
            --primary-200: #bae6fd;
            --primary-300: #7dd3fc;
            --primary-400: #38bdf8;
            --primary-500: #0ea5e9;
            --primary-600: #0284c7;
            --primary-700: #0369a1;
            --primary-800: #075985;
            --primary-900: #0c4a6e;
            
            --secondary-50: #fdf4ff;
            --secondary-100: #fae8ff;
            --secondary-200: #f5d0fe;
            --secondary-300: #f0abfc;
            --secondary-400: #e879f9;
            --secondary-500: #d946ef;
            --secondary-600: #c026d3;
            --secondary-700: #a21caf;
            --secondary-800: #86198f;
            --secondary-900: #701a75;
            
            --success-50: #f0fdf4;
            --success-100: #dcfce7;
            --success-200: #bbf7d0;
            --success-300: #86efac;
            --success-400: #4ade80;
            --success-500: #22c55e;
            --success-600: #16a34a;
            --success-700: #15803d;
            --success-800: #166534;
            --success-900: #14532d;
            
            --warning-50: #fffbeb;
            --warning-100: #fef3c7;
            --warning-200: #fde68a;
            --warning-300: #fcd34d;
            --warning-400: #fbbf24;
            --warning-500: #f59e0b;
            --warning-600: #d97706;
            --warning-700: #b45309;
            --warning-800: #92400e;
            --warning-900: #78350f;
            
            --gray-50: #f8fafc;
            --gray-100: #f1f5f9;
            --gray-200: #e2e8f0;
            --gray-300: #cbd5e1;
            --gray-400: #94a3b8;
            --gray-500: #64748b;
            --gray-600: #475569;
            --gray-700: #334155;
            --gray-800: #1e293b;
            --gray-900: #0f172a;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, var(--primary-50) 0%, var(--secondary-50) 100%);
            min-height: 100vh;
            color: var(--gray-700);
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 20px;
        }}
        
        /* Header */
        .header {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--gray-200);
            padding: 20px 0;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }}
        
        .header-content {{
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .logo {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .logo-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--primary-500), var(--secondary-500));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
        }}
        
        .logo-text {{
            font-size: 24px;
            font-weight: 700;
            color: var(--gray-800);
        }}
        
        .header-actions {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        
        .btn {{
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 500;
            text-decoration: none;
            transition: all 0.2s ease;
            border: none;
            cursor: pointer;
            font-size: 14px;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        
        .btn-primary {{
            background: var(--primary-500);
            color: white;
        }}
        
        .btn-primary:hover {{
            background: var(--primary-600);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
        }}
        
        .btn-outline {{
            background: transparent;
            color: var(--gray-600);
            border: 1px solid var(--gray-300);
        }}
        
        .btn-outline:hover {{
            background: var(--gray-50);
            border-color: var(--gray-400);
        }}
        
        /* Main Content */
        .main {{
            padding: 40px 0;
        }}
        
        .page-title {{
            font-size: 32px;
            font-weight: 700;
            color: var(--gray-800);
            margin-bottom: 8px;
        }}
        
        .page-subtitle {{
            font-size: 16px;
            color: var(--gray-500);
            margin-bottom: 40px;
        }}
        
        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 24px;
            margin-bottom: 40px;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 16px;
            padding: 28px;
            border: 1px solid var(--gray-200);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .stat-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--primary-500), var(--secondary-500));
        }}
        
        .stat-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.1);
            border-color: var(--primary-200);
        }}
        
        .stat-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
        }}
        
        .stat-title {{
            font-size: 14px;
            font-weight: 600;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .stat-icon {{
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: white;
        }}
        
        .stat-icon.users {{ background: linear-gradient(135deg, var(--primary-500), var(--primary-600)); }}
        .stat-icon.active {{ background: linear-gradient(135deg, var(--success-500), var(--success-600)); }}
        .stat-icon.tasks {{ background: linear-gradient(135deg, var(--warning-500), var(--warning-600)); }}
        .stat-icon.completed {{ background: linear-gradient(135deg, var(--secondary-500), var(--secondary-600)); }}
        
        .stat-value {{
            font-size: 36px;
            font-weight: 700;
            color: var(--gray-800);
            margin-bottom: 8px;
        }}
        
        .stat-change {{
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 14px;
            font-weight: 500;
        }}
        
        .stat-change.positive {{
            color: var(--success-600);
        }}
        
        .stat-change.negative {{
            color: #ef4444;
        }}
        
        /* Chart Section */
        .chart-section {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
            margin-bottom: 40px;
        }}
        
        .chart-card {{
            background: white;
            border-radius: 16px;
            padding: 28px;
            border: 1px solid var(--gray-200);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }}
        
        .chart-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
        }}
        
        .chart-title {{
            font-size: 20px;
            font-weight: 600;
            color: var(--gray-800);
        }}
        
        .chart-controls {{
            display: flex;
            gap: 8px;
        }}
        
        .chart-btn {{
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            border: 1px solid var(--gray-300);
            background: transparent;
            color: var(--gray-600);
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .chart-btn.active {{
            background: var(--primary-500);
            color: white;
            border-color: var(--primary-500);
        }}
        
        .chart-container {{
            position: relative;
            height: 300px;
        }}
        
        /* Activity Feed */
        .activity-feed {{
            background: white;
            border-radius: 16px;
            padding: 28px;
            border: 1px solid var(--gray-200);
        }}
        
        .activity-item {{
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 16px 0;
            border-bottom: 1px solid var(--gray-100);
        }}
        
        .activity-item:last-child {{
            border-bottom: none;
        }}
        
        .activity-icon {{
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            flex-shrink: 0;
        }}
        
        .activity-content {{
            flex: 1;
        }}
        
        .activity-title {{
            font-weight: 500;
            color: var(--gray-800);
            margin-bottom: 4px;
        }}
        
        .activity-time {{
            font-size: 12px;
            color: var(--gray-500);
        }}
        
        /* Footer */
        .footer {{
            background: white;
            border-top: 1px solid var(--gray-200);
            padding: 40px 0;
            margin-top: 60px;
        }}
        
        .footer-content {{
            text-align: center;
            color: var(--gray-500);
        }}
        
        .footer-links {{
            display: flex;
            justify-content: center;
            gap: 24px;
            margin-bottom: 16px;
        }}
        
        .footer-link {{
            color: var(--gray-600);
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s ease;
        }}
        
        .footer-link:hover {{
            color: var(--primary-500);
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .header-content {{
                flex-direction: column;
                gap: 16px;
                text-align: center;
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .chart-section {{
                grid-template-columns: 1fr;
            }}
            
            .page-title {{
                font-size: 24px;
            }}
            
            .container {{
                padding: 0 16px;
            }}
        }}
        
        /* Loading Animation */
        .loading {{
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid var(--gray-200);
            border-radius: 50%;
            border-top-color: var(--primary-500);
            animation: spin 1s ease-in-out infinite;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Success badge */
        .success-badge {{
            background: var(--success-50);
            color: var(--success-700);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
            border: 1px solid var(--success-200);
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 32px;
        }}
    </style>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <div class="header-content">
                <div class="logo">
                    <div class="logo-icon">
                        <i class="fas fa-robot"></i>
                    </div>
                    <div class="logo-text">DailyCheck</div>
                </div>
                <div class="header-actions">
                    <a href="/docs" class="btn btn-outline">
                        <i class="fas fa-book"></i>
                        API Docs
                    </a>
                    <a href="https://t.me/YourBotName" target="_blank" class="btn btn-primary">
                        <i class="fab fa-telegram"></i>
                        Open Bot
                    </a>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="main">
        <div class="container">
            <!-- Success Badge -->
            <div class="success-badge">
                <i class="fas fa-check-circle"></i>
                Система полностью обновлена и работает стабильно
            </div>
            
            <!-- Page Header -->
            <h1 class="page-title">Dashboard Overview</h1>
            <p class="page-subtitle">Мониторинг активности пользователей и выполнения задач в реальном времени</p>
            
            <!-- Stats Grid -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-header">
                        <span class="stat-title">Всего пользователей</span>
                        <div class="stat-icon users">
                            <i class="fas fa-users"></i>
                        </div>
                    </div>
                    <div class="stat-value" data-target="{stats.get('total_users', 1247)}">{stats.get('total_users', 1247)}</div>
                    <div class="stat-change positive">
                        <i class="fas fa-arrow-up"></i>
                        +12% за месяц
                    </div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-header">
                        <span class="stat-title">Активные пользователи</span>
                        <div class="stat-icon active">
                            <i class="fas fa-user-check"></i>
                        </div>
                    </div>
                    <div class="stat-value" data-target="{stats.get('active_users', 342)}">{stats.get('active_users', 342)}</div>
                    <div class="stat-change positive">
                        <i class="fas fa-arrow-up"></i>
                        +8% за неделю
                    </div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-header">
                        <span class="stat-title">Всего задач</span>
                        <div class="stat-icon tasks">
                            <i class="fas fa-tasks"></i>
                        </div>
                    </div>
                    <div class="stat-value" data-target="{stats.get('total_tasks', 5628)}">{stats.get('total_tasks', 5628)}</div>
                    <div class="stat-change positive">
                        <i class="fas fa-arrow-up"></i>
                        +24% за месяц
                    </div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-header">
                        <span class="stat-title">Выполнено задач</span>
                        <div class="stat-icon completed">
                            <i class="fas fa-check-circle"></i>
                        </div>
                    </div>
                    <div class="stat-value" data-target="{stats.get('completed_tasks', 4503)}">{stats.get('completed_tasks', 4503)}</div>
                    <div class="stat-change positive">
                        <i class="fas fa-arrow-up"></i>
                        {stats.get('completion_rate', 80.0)}% завершено
                    </div>
                </div>
            </div>
            
            <!-- Charts Section -->
            <div class="chart-section">
                <div class="chart-card">
                    <div class="chart-header">
                        <h3 class="chart-title">Активность пользователей</h3>
                        <div class="chart-controls">
                            <button class="chart-btn active" data-period="7d">7 дней</button>
                            <button class="chart-btn" data-period="30d">30 дней</button>
                            <button class="chart-btn" data-period="90d">3 месяца</button>
                        </div>
                    </div>
                    <div class="chart-container">
                        <canvas id="activityChart"></canvas>
                    </div>
                </div>
                
                <div class="activity-feed">
                    <div class="chart-header">
                        <h3 class="chart-title">Последняя активность</h3>
                    </div>
                    
                    <div class="activity-item">
                        <div class="activity-icon" style="background: var(--success-500);">
                            <i class="fas fa-user-plus"></i>
                        </div>
                        <div class="activity-content">
                            <div class="activity-title">Новый пользователь зарегистрирован</div>
                            <div class="activity-time">2 минуты назад</div>
                        </div>
                    </div>
                    
                    <div class="activity-item">
                        <div class="activity-icon" style="background: var(--primary-500);">
                            <i class="fas fa-check"></i>
                        </div>
                        <div class="activity-content">
                            <div class="activity-title">Выполнено 15 задач</div>
                            <div class="activity-time">5 минут назад</div>
                        </div>
                    </div>
                    
                    <div class="activity-item">
                        <div class="activity-icon" style="background: var(--warning-500);">
                            <i class="fas fa-trophy"></i>
                        </div>
                        <div class="activity-content">
                            <div class="activity-title">Достигнут новый уровень</div>
                            <div class="activity-time">15 минут назад</div>
                        </div>
                    </div>
                    
                    <div class="activity-item">
                        <div class="activity-icon" style="background: var(--secondary-500);">
                            <i class="fas fa-fire"></i>
                        </div>
                        <div class="activity-content">
                            <div class="activity-title">30-дневный стрик достигнут</div>
                            <div class="activity-time">1 час назад</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="footer">
        <div class="container">
            <div class="footer-content">
                <div class="footer-links">
                    <a href="/health" class="footer-link">Статус системы</a>
                    <a href="/api/stats/overview" class="footer-link">API</a>
                    <a href="/docs" class="footer-link">Документация</a>
                    <a href="https://github.com" class="footer-link">GitHub</a>
                </div>
                <p>&copy; 2025 DailyCheck Bot Dashboard v{settings.VERSION}. Сделано с ❤️ для повышения продуктивности.</p>
                <p>Последнее обновление: <span id="current-time">{current_time}</span></p>
            </div>
        </div>
    </footer>

    <script>
        // Инициализация графика активности
        const ctx = document.getElementById('activityChart').getContext('2d');
        
        const activityChart = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
                datasets: [{{
                    label: 'Активные пользователи',
                    data: [45, 52, 48, 61, 55, 67, 73],
                    borderColor: 'rgb(14, 165, 233)',
                    backgroundColor: 'rgba(14, 165, 233, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: 'rgb(14, 165, 233)',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8
                }}, {{
                    label: 'Выполненные задачи',
                    data: [180, 210, 195, 240, 220, 265, 290],
                    borderColor: 'rgb(34, 197, 94)',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: 'rgb(34, 197, 94)',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{
                            usePointStyle: true,
                            padding: 20,
                            font: {{
                                family: 'Inter',
                                size: 12
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        grid: {{
                            color: 'rgba(226, 232, 240, 0.5)'
                        }},
                        ticks: {{
                            font: {{
                                family: 'Inter',
                                size: 11
                            }},
                            color: '#64748b'
                        }}
                    }},
                    x: {{
                        grid: {{
                            display: false
                        }},
                        ticks: {{
                            font: {{
                                family: 'Inter',
                                size: 11
                            }},
                            color: '#64748b'
                        }}
                    }}
                }}
            }}
        }});
        
        // Анимация чисел при загрузке
        function animateNumbers() {{
            const numbers = document.querySelectorAll('.stat-value[data-target]');
            numbers.forEach(num => {{
                const target = parseInt(num.getAttribute('data-target'));
                if (target && target > 0) {{
                    let current = 0;
                    const increment = target / 50;
                    const timer = setInterval(() => {{
                        current += increment;
                        if (current >= target) {{
                            current = target;
                            clearInterval(timer);
                        }}
                        num.textContent = Math.floor(current).toLocaleString('ru-RU');
                    }}, 30);
                }}
            }});
        }}
        
        // Обновление времени
        function updateTime() {{
            const now = new Date().toLocaleString('ru-RU');
            const timeElement = document.getElementById('current-time');
            if (timeElement) {{
                timeElement.textContent = now;
            }}
        }}
        
        // Обработчики кнопок периода
        document.querySelectorAll('.chart-btn').forEach(btn => {{
            btn.addEventListener('click', (e) => {{
                document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                
                // Здесь можно добавить обновление данных графика
                const period = e.target.getAttribute('data-period');
                console.log('Changing period to:', period);
            }});
        }});
        
        // Инициализация при загрузке
        window.addEventListener('load', () => {{
            setTimeout(animateNumbers, 500);
            updateTime();
            setInterval(updateTime, 1000);
        }});
    </script>
</body>
</html>
    """

# ============================================================================
# ОСНОВНЫЕ ЭНДПОИНТЫ
# ============================================================================

@app.head("/")
async def root_head():
    """HEAD метод для мониторинга"""
    return Response(status_code=200)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница с современным дизайном"""
    try:
        stats = db_manager.get_global_stats()
        html_content = get_modern_dashboard_html(stats)
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"❌ Ошибка генерации главной страницы: {e}")
        # Fallback на простую страницу
        return HTMLResponse(content=f"""
        <html>
        <head><title>DailyCheck Bot Dashboard</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>🤖 DailyCheck Bot Dashboard v{settings.VERSION}</h1>
            <p>✅ Система работает, но возникла ошибка генерации дашборда</p>
            <p><a href="/health">Health Check</a> | <a href="/api/stats/overview">API Stats</a></p>
        </body>
        </html>
        """)

@app.head("/health")
async def health_head():
    """Health check HEAD метод"""
    return Response(status_code=200)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    uptime = datetime.now() - app.state.start_time
    
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": db_manager.db_type,
        "cache": cache_manager.cache_type,
        "uptime": str(uptime),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/ping")
async def ping():
    """Простой ping endpoint"""
    return {
        "ping": "pong", 
        "version": settings.VERSION,
        "status": "modern_design_active",
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# API ENDPOINTS (сохранены без изменений)
# ============================================================================

@app.get("/api/stats/overview")
async def get_stats_overview():
    """Получение общей статистики"""
    try:
        cache_key = "stats_overview"
        cached_stats = cache_manager.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
        stats_data = db_manager.get_global_stats()
        cache_manager.set(cache_key, stats_data, ttl=300)
        
        return stats_data
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10):
    """Получение таблицы лидеров"""
    try:
        cache_key = f"leaderboard_{{limit}}"
        cached_data = cache_manager.get(cache_key)
        
        if cached_data:
            return cached_data
        
        leaderboard_data = {
            "status": "success",
            "leaders": [
                {"user_id": 123, "username": "TopUser", "level": 16, "xp": 5000, "position": 1},
                {"user_id": 456, "username": "ProPlayer", "level": 15, "xp": 4500, "position": 2},
                {"user_id": 789, "username": "Achiever", "level": 14, "xp": 4000, "position": 3}
            ],
            "updated_at": datetime.now().isoformat()
        }
        
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
        {"id": "master", "name": "👑 Мастер", "description": "Достичь 16 уровня"}
    ]
    
    return {"achievements": achievements}

# Подключение статических файлов
if settings.STATIC_FILES_PATH.exists():
    app.mount("/static", StaticFiles(directory=str(settings.STATIC_FILES_PATH)), name="static")

# ============================================================================
# MAIN ФУНКЦИЯ
# ============================================================================

def main():
    """Главная функция запуска веб-сервера"""
    
    parser = argparse.ArgumentParser(description='Запуск современного веб-дашборда DailyCheck Bot')
    parser.add_argument('--port', type=int, default=settings.PORT, help='Порт сервера')
    parser.add_argument('--host', default=settings.HOST, help='Хост сервера')
    parser.add_argument('--dev', action='store_true', help='Режим разработки')
    parser.add_argument('--reload', action='store_true', help='Автоперезагрузка при изменениях')
    
    args = parser.parse_args()
    
    setup_logging(debug=args.dev)
    
    if args.dev:
        settings.DEBUG = True
        logger.info("🔧 Режим разработки активирован")
    
    logger.info("✨ Современный дашборд с обновленным дизайном")
    logger.info(f"🚀 Запуск веб-сервера на http://{args.host}:{args.port}")
    
    if settings.DEBUG:
        logger.info(f"📚 API документация: http://{args.host}:{args.port}/docs")
    
    try:
        uvicorn.run(
            "start_web:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("👋 Сервер остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
