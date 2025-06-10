#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Web Dashboard - FastAPI Application
Веб-дашборд для Telegram бота с аналитикой и графиками

Автор: AI Assistant
Версия: 1.0.0
Дата: 2025-06-10
"""

import os
import sys
import logging
import time
import json
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

# Добавляем пути для импорта модулей
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.security import HTTPBearer
import uvicorn

# Локальные импорты с обработкой ошибок
try:
    from dashboard.config import settings
except ImportError:
    # Создаем базовые настройки если config не найден
    class Settings:
        DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
        LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        DATA_DIR = Path(os.getenv('DATA_DIR', './data'))
        DASHBOARD_HOST = os.getenv('HOST', '0.0.0.0')
        DASHBOARD_PORT = int(os.getenv('PORT', 8000))
        ALLOWED_ORIGINS = ["*"]
        ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
        
        # Создаем директорию данных
        def __post_init__(self):
            self.DATA_DIR.mkdir(exist_ok=True)
    
    settings = Settings()

try:
    from dashboard.core.data_manager import DataManager
except ImportError:
    # Заглушка для DataManager
    class DataManager:
        def __init__(self, data_dir):
            self.data_dir = Path(data_dir)
            self.data_dir.mkdir(exist_ok=True)
        
        async def initialize(self):
            logger.info("🔧 DataManager заглушка инициализирована")
        
        async def cleanup(self):
            logger.info("🧹 DataManager заглушка очищена")
        
        async def get_users_count(self):
            return 0
        
        async def get_tasks_count(self):
            return 0
        
        async def get_total_completions(self):
            return 0
        
        async def get_active_users_count(self, days=1):
            return 0
        
        async def get_users_summary(self):
            return {"total": 0, "active": 0, "new": 0}
        
        async def get_tasks_summary(self):
            return {"total": 0, "completed": 0, "pending": 0}
        
        async def get_analytics_summary(self):
            return {"engagement": 0, "retention": 0, "growth": 0}

try:
    from dashboard.dependencies import get_data_manager
except ImportError:
    async def get_data_manager():
        global data_manager
        return data_manager

# Попытка импорта API роутеров
api_routers_available = True
try:
    from dashboard.api import users, tasks, stats, charts
except ImportError:
    api_routers_available = False
    logger.warning("⚠️ API роутеры не найдены, используем базовые endpoints")

# Модели для API
try:
    from shared.models import HealthCheck
except ImportError:
    from pydantic import BaseModel
    
    class HealthCheck(BaseModel):
        status: str
        service: str
        version: str
        timestamp: float

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/dashboard.log', encoding='utf-8') if Path('logs').exists() else logging.NullHandler()
    ]
)
logger = logging.getLogger(__name__)

# Глобальные переменные
data_manager: DataManager = None
app_start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global data_manager, app_start_time
    
    # Startup
    logger.info("🚀 Запуск DailyCheck Web Dashboard...")
    app_start_time = time.time()
    
    try:
        # Создаем необходимые директории
        required_dirs = [
            settings.DATA_DIR,
            Path('logs'),
            Path('temp'),
            Path('static'),
            Path('dashboard/templates')
        ]
        
        for directory in required_dirs:
            directory.mkdir(exist_ok=True)
        
        # Инициализация менеджера данных
        data_manager = DataManager(settings.DATA_DIR)
        await data_manager.initialize()
        
        # Получаем статистику
        users_count = await data_manager.get_users_count()
        tasks_count = await data_manager.get_tasks_count()
        
        logger.info(f"📊 Загружено пользователей: {users_count}")
        logger.info(f"📝 Загружено задач: {tasks_count}")
        logger.info(f"🌐 Dashboard доступен на: http://{settings.DASHBOARD_HOST}:{settings.DASHBOARD_PORT}")
        logger.info("✅ Dashboard готов к работе")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        # Не прерываем запуск, работаем с базовой функциональностью
    
    yield
    
    # Shutdown
    logger.info("🛑 Остановка Dashboard...")
    try:
        if data_manager:
            await data_manager.cleanup()
        logger.info("✅ Ресурсы очищены")
    except Exception as e:
        logger.error(f"❌ Ошибка при остановке: {e}")

# Создание FastAPI приложения
app = FastAPI(
    title="DailyCheck Dashboard",
    description="Веб-дашборд для анализа данных Telegram бота с аналитикой и графиками",
    version="1.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

# ===== MIDDLEWARE =====

# Trusted Host middleware (безопасность)
if not settings.DEBUG:
    allowed_hosts = ["*"]  # В продакшене указать конкретные домены
    if hasattr(settings, 'ALLOWED_HOSTS'):
        allowed_hosts = settings.ALLOWED_HOSTS
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, 'ALLOWED_ORIGINS', ["*"]),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Middleware для логирования и метрик
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Middleware для логирования запросов и сбора метрик"""
    start_time = time.time()
    
    # Получаем информацию о запросе
    client_ip = request.headers.get("X-Forwarded-For", request.client.host)
    user_agent = request.headers.get("User-Agent", "Unknown")
    
    try:
        response = await call_next(request)
        
        # Вычисляем время обработки
        process_time = time.time() - start_time
        
        # Логируем запрос
        logger.info(
            f"{request.method} {request.url.path} "
            f"- {response.status_code} "
            f"- {process_time:.3f}s "
            f"- {client_ip}"
        )
        
        # Добавляем заголовки
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = str(hash(f"{client_ip}{start_time}"))
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"❌ Ошибка обработки запроса: {e} ({process_time:.3f}s)")
        
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": str(hash(f"{client_ip}{start_time}"))}
        )

# ===== СТАТИЧЕСКИЕ ФАЙЛЫ И ШАБЛОНЫ =====

# Статические файлы
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"✅ Статические файлы: {static_dir}")
else:
    # Создаем базовую структуру статических файлов
    static_dir.mkdir(exist_ok=True)
    (static_dir / "css").mkdir(exist_ok=True)
    (static_dir / "js").mkdir(exist_ok=True)
    (static_dir / "img").mkdir(exist_ok=True)
    logger.warning(f"⚠️ Создана базовая структура статических файлов: {static_dir}")

# Шаблоны
templates_dir = Path(__file__).parent / "templates"
if templates_dir.exists():
    templates = Jinja2Templates(directory=str(templates_dir))
    logger.info(f"✅ Шаблоны: {templates_dir}")
else:
    templates_dir.mkdir(exist_ok=True)
    # Создаем базовый шаблон
    create_basic_templates(templates_dir)
    templates = Jinja2Templates(directory=str(templates_dir))
    logger.info(f"✅ Созданы базовые шаблоны: {templates_dir}")

def create_basic_templates(templates_dir: Path):
    """Создание базовых шаблонов"""
    
    # Базовый шаблон
    base_template = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}DailyCheck Dashboard{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🤖</text></svg>">
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Navigation -->
    <nav class="bg-white shadow-sm border-b">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <h1 class="text-xl font-bold text-gray-900">🤖 DailyCheck</h1>
                    </div>
                    <div class="hidden md:ml-6 md:flex md:space-x-8">
                        <a href="/" class="text-gray-900 hover:text-blue-600 px-3 py-2 text-sm font-medium">Главная</a>
                        <a href="/users" class="text-gray-500 hover:text-blue-600 px-3 py-2 text-sm font-medium">Пользователи</a>
                        <a href="/tasks" class="text-gray-500 hover:text-blue-600 px-3 py-2 text-sm font-medium">Задачи</a>
                        <a href="/analytics" class="text-gray-500 hover:text-blue-600 px-3 py-2 text-sm font-medium">Аналитика</a>
                    </div>
                </div>
                <div class="flex items-center">
                    <span class="text-sm text-gray-500">
                        {% if debug %}🔧 Dev{% else %}🚀 Prod{% endif %}
                    </span>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {% block content %}{% endblock %}
    </main>

    <!-- Scripts -->
    {% block scripts %}{% endblock %}
</body>
</html>
    """
    
    # Главная страница
    dashboard_template = """
{% extends "base.html" %}

{% block content %}
<div class="px-4 py-6 sm:px-0">
    <!-- Заголовок -->
    <div class="mb-8">
        <h2 class="text-2xl font-bold text-gray-900">Обзор системы</h2>
        <p class="mt-1 text-gray-600">Статистика и метрики Telegram бота</p>
    </div>

    <!-- Статистические карточки -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div class="bg-white overflow-hidden shadow rounded-lg">
            <div class="p-5">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                            <span class="text-white text-sm">👥</span>
                        </div>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-medium text-gray-500 truncate">Пользователи</dt>
                            <dd class="text-lg font-medium text-gray-900">{{ stats.users_count or 0 }}</dd>
                        </dl>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="bg-white overflow-hidden shadow rounded-lg">
            <div class="p-5">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <div class="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                            <span class="text-white text-sm">📝</span>
                        </div>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-medium text-gray-500 truncate">Задачи</dt>
                            <dd class="text-lg font-medium text-gray-900">{{ stats.tasks_count or 0 }}</dd>
                        </dl>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="bg-white overflow-hidden shadow rounded-lg">
            <div class="p-5">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <div class="w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center">
                            <span class="text-white text-sm">✅</span>
                        </div>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-medium text-gray-500 truncate">Выполнено</dt>
                            <dd class="text-lg font-medium text-gray-900">{{ stats.total_completions or 0 }}</dd>
                        </dl>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="bg-white overflow-hidden shadow rounded-lg">
            <div class="p-5">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <div class="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center">
                            <span class="text-white text-sm">📊</span>
                        </div>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                        <dl>
                            <dt class="text-sm font-medium text-gray-500 truncate">Активные сегодня</dt>
                            <dd class="text-lg font-medium text-gray-900">{{ stats.active_users_today or 0 }}</dd>
                        </dl>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Графики и дополнительная информация -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Статус системы -->
        <div class="bg-white shadow rounded-lg p-6">
            <h3 class="text-lg font-medium text-gray-900 mb-4">Статус системы</h3>
            <div class="space-y-3">
                <div class="flex items-center">
                    <div class="w-3 h-3 bg-green-500 rounded-full mr-3"></div>
                    <span class="text-sm text-gray-700">Веб-сервер: Активен</span>
                </div>
                <div class="flex items-center">
                    <div class="w-3 h-3 bg-green-500 rounded-full mr-3"></div>
                    <span class="text-sm text-gray-700">База данных: Подключена</span>
                </div>
                <div class="flex items-center">
                    <div class="w-3 h-3 bg-yellow-500 rounded-full mr-3"></div>
                    <span class="text-sm text-gray-700">API: Базовый режим</span>
                </div>
            </div>
        </div>

        <!-- Быстрые действия -->
        <div class="bg-white shadow rounded-lg p-6">
            <h3 class="text-lg font-medium text-gray-900 mb-4">Быстрые действия</h3>
            <div class="space-y-3">
                <a href="/api/health" class="block w-full bg-blue-50 hover:bg-blue-100 text-blue-700 font-medium py-2 px-4 rounded-lg text-center transition">
                    Проверить состояние API
                </a>
                <a href="/api/stats/overview" class="block w-full bg-green-50 hover:bg-green-100 text-green-700 font-medium py-2 px-4 rounded-lg text-center transition">
                    Получить статистику
                </a>
                {% if debug %}
                <a href="/docs" class="block w-full bg-purple-50 hover:bg-purple-100 text-purple-700 font-medium py-2 px-4 rounded-lg text-center transition">
                    API Документация
                </a>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
    """
    
    # Сохраняем шаблоны
    (templates_dir / "base.html").write_text(base_template.strip(), encoding='utf-8')
    (templates_dir / "dashboard.html").write_text(dashboard_template.strip(), encoding='utf-8')

# ===== ПОДКЛЮЧЕНИЕ API РОУТЕРОВ =====

if api_routers_available:
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(stats.router, prefix="/api/stats", tags=["statistics"])
    app.include_router(charts.router, prefix="/api/charts", tags=["charts"])
    logger.info("✅ API роутеры подключены")
else:
    # Создаем базовые API endpoints
    @app.get("/api/users/summary")
    async def users_summary():
        return {"total": 0, "active": 0, "new_today": 0}
    
    @app.get("/api/tasks/summary")
    async def tasks_summary():
        return {"total": 0, "completed": 0, "pending": 0}
    
    logger.info("✅ Базовые API endpoints созданы")

# ===== ОСНОВНЫЕ МАРШРУТЫ =====

@app.get("/", response_class=HTMLResponse)
async def dashboard_home(
    request: Request,
    dm: DataManager = Depends(get_data_manager)
):
    """Главная страница дашборда"""
    try:
        # Базовая статистика для главной страницы
        stats_data = {
            "users_count": await dm.get_users_count(),
            "tasks_count": await dm.get_tasks_count(),
            "total_completions": await dm.get_total_completions(),
            "active_users_today": await dm.get_active_users_count(days=1)
        }
        
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "title": "DailyCheck Dashboard",
                "stats": stats_data,
                "debug": settings.DEBUG
            }
        )
    except Exception as e:
        logger.error(f"Ошибка загрузки главной страницы: {e}")
        # Возвращаем страницу с базовыми данными
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "title": "DailyCheck Dashboard",
                "stats": {
                    "users_count": 0,
                    "tasks_count": 0,
                    "total_completions": 0,
                    "active_users_today": 0
                },
                "debug": settings.DEBUG,
                "error": str(e)
            }
        )

@app.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    dm: DataManager = Depends(get_data_manager)
):
    """Страница пользователей"""
    try:
        users_data = await dm.get_users_summary()
        
        return templates.TemplateResponse(
            "users.html",
            {
                "request": request,
                "title": "Пользователи - DailyCheck Dashboard",
                "users": users_data,
                "debug": settings.DEBUG
            }
        )
    except Exception as e:
        logger.error(f"Ошибка загрузки страницы пользователей: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Ошибка загрузки данных пользователей"}
        )

@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(
    request: Request,
    dm: DataManager = Depends(get_data_manager)
):
    """Страница задач"""
    try:
        tasks_data = await dm.get_tasks_summary()
        
        return templates.TemplateResponse(
            "tasks.html",
            {
                "request": request,
                "title": "Задачи - DailyCheck Dashboard",
                "tasks": tasks_data,
                "debug": settings.DEBUG
            }
        )
    except Exception as e:
        logger.error(f"Ошибка загрузки страницы задач: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Ошибка загрузки данных задач"}
        )

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(
    request: Request,
    dm: DataManager = Depends(get_data_manager)
):
    """Страница аналитики"""
    try:
        analytics_data = await dm.get_analytics_summary()
        
        return templates.TemplateResponse(
            "analytics.html",
            {
                "request": request,
                "title": "Аналитика - DailyCheck Dashboard",
                "analytics": analytics_data,
                "debug": settings.DEBUG
            }
        )
    except Exception as e:
        logger.error(f"Ошибка загрузки страницы аналитики: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Ошибка загрузки аналитических данных"}
        )

# ===== СЛУЖЕБНЫЕ МАРШРУТЫ =====

@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check для Render и мониторинга"""
    try:
        dm = data_manager
        if not dm:
            raise Exception("DataManager не инициализирован")
        
        # Проверяем доступность данных
        users_count = await dm.get_users_count()
        uptime = time.time() - app_start_time
        
        return HealthCheck(
            status="healthy",
            service="dashboard",
            version="1.0.0",
            timestamp=time.time(),
            data={
                "users_count": users_count,
                "data_dir": str(settings.DATA_DIR),
                "debug_mode": settings.DEBUG,
                "uptime_seconds": uptime
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "dashboard",
                "error": str(e),
                "timestamp": time.time()
            }
        )

@app.get("/api/info")
async def api_info():
    """Информация об API"""
    return {
        "name": "DailyCheck Dashboard API",
        "version": "1.0.0",
        "environment": getattr(settings, 'ENVIRONMENT', 'production'),
        "debug": settings.DEBUG,
        "uptime": time.time() - app_start_time,
        "endpoints": {
            "users": "/api/users",
            "tasks": "/api/tasks", 
            "stats": "/api/stats",
            "charts": "/api/charts"
        },
        "features": {
            "api_routers": api_routers_available,
            "data_manager": data_manager is not None,
            "templates": templates_dir.exists()
        }
    }

@app.get("/api/system/status")
async def system_status():
    """Детальный статус системы"""
    try:
        import psutil
        import platform
        
        # Системная информация
        system_info = {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        }
    except ImportError:
        system_info = {
            "platform": "unknown",
            "python_version": "unknown",
            "cpu_count": os.cpu_count(),
            "memory_usage": None,
            "disk_usage": None
        }
    
    return {
        "status": "operational",
        "uptime": time.time() - app_start_time,
        "timestamp": time.time(),
        "system": system_info,
        "application": {
            "debug": settings.DEBUG,
            "data_dir": str(settings.DATA_DIR),
            "components": {
                "data_manager": data_manager is not None,
                "api_routers": api_routers_available,
                "templates": templates_dir.exists()
            }
        }
    }

@app.get("/ping")
async def ping():
    """Простой ping endpoint"""
    return {
        "message": "pong", 
        "timestamp": time.time(),
        "service": "dashboard"
    }

# Редиректы
@app.get("/dashboard")
async def dashboard_redirect():
    """Редирект на главную"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=301)

# ===== СТАТИЧЕСКИЕ ФАЙЛЫ МАРШРУТЫ =====

@app.get("/favicon.ico")
async def favicon():
    """Иконка сайта"""
    favicon_path = static_dir / "img" / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    else:
        # Возвращаем emoji иконку
        return JSONResponse({"message": "🤖"})

@app.get("/robots.txt")
async def robots():
    """Robots.txt для поисковиков"""
    return JSONResponse(
        content="User-agent: *\nDisallow: /api/\nAllow: /",
        media_type="text/plain"
    )

# ===== ФОНОВЫЕ ЗАДАЧИ =====

@app.post("/api/tasks/background")
async def create_background_task(background_tasks: BackgroundTasks):
    """Создание фоновой задачи (пример)"""
    def sample_task():
        import time
        time.sleep(5)
        logger.info("Фоновая задача выполнена")
    
    background_tasks.add_task(sample_task)
    return {"message": "Фоновая задача запущена"}

# ===== ОБРАБОТЧИКИ ОШИБОК =====

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Обработчик 404 ошибок"""
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={
                "detail": "API endpoint not found",
                "path": str(request.url.path),
                "method": request.method
            }
        )
    
    # Для веб-страниц возвращаем HTML
    try:
        return templates.TemplateResponse(
            "errors/404.html",
            {"request": request, "title": "Страница не найдена"},
            status_code=404
        )
    except:
        return JSONResponse(
            status_code=404,
            content={"detail": "Page not found"}
        )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    """Обработчик 500 ошибок"""
    logger.error(f"Internal server error: {exc}")
    
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "debug": settings.DEBUG
            }
        )
    
    try:
        return templates.TemplateResponse(
            "errors/500.html",
            {"request": request, "title": "Ошибка сервера"},
            status_code=500
        )
    except:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Обработчик HTTP исключений"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code
        }
    )

# ===== ЗАПУСК ПРИЛОЖЕНИЯ =====

def create_app() -> FastAPI:
    """Фабрика для создания приложения"""
    return app

def run_dashboard(
    host: str = None,
    port: int = None,
    dev: bool = None,
    reload: bool = None
):
    """Запуск дашборда"""
    
    # Используем настройки по умолчанию если не переданы
    host = host or settings.DASHBOARD_HOST
    port = port or settings.DASHBOARD_PORT
    dev = dev if dev is not None else settings.DEBUG
    reload = reload if reload is not None else dev
    
    logger.info(f"🌐 Запуск Dashboard на http://{host}:{port}")
    logger.info(f"📊 Данные бота: {settings.DATA_DIR}")
    logger.info(f"🔧 Режим отладки: {dev}")
    logger.info(f"🔄 Автоперезагрузка: {reload}")
    
    try:
        uvicorn.run(
            "dashboard.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level="debug" if dev else "info",
            access_log=dev,
            server_header=False,
            date_header=False
        )
    except KeyboardInterrupt:
        logger.info("👋 Dashboard остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска Dashboard: {e}")
        raise

if __name__ == "__main__":
    # Запуск напрямую
    import argparse
    
    parser = argparse.ArgumentParser(description='Запуск DailyCheck Dashboard')
    parser.add_argument('--host', default=settings.DASHBOARD_HOST, help='Host для запуска')
    parser.add_argument('--port', type=int, default=settings.DASHBOARD_PORT, help='Port для запуска')
    parser.add_argument('--dev', action='store_true', help='Режим разработки')
    parser.add_argument('--reload', action='store_true', help='Автоперезагрузка')
    
    args = parser.parse_args()
    
    run_dashboard(
        host=args.host,
        port=args.port, 
        dev=args.dev,
        reload=args.reload
    )
