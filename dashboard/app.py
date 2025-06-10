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
from pathlib import Path
from contextlib import asynccontextmanager

# Добавляем пути для импорта модулей
sys.path.append(str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Локальные импорты
from dashboard.config import settings
from dashboard.core.data_manager import DataManager
from dashboard.api import users, tasks, stats, charts
from dashboard.dependencies import get_data_manager
from shared.models import HealthCheck

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
data_manager: DataManager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global data_manager
    
    # Startup
    logger.info("🚀 Запуск DailyCheck Web Dashboard...")
    
    try:
        # Инициализация менеджера данных
        data_manager = DataManager(settings.DATA_DIR)
        await data_manager.initialize()
        
        logger.info(f"📊 Загружено пользователей: {await data_manager.get_users_count()}")
        logger.info(f"📝 Загружено задач: {await data_manager.get_tasks_count()}")
        logger.info("✅ Dashboard готов к работе")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Остановка Dashboard...")
    if data_manager:
        await data_manager.cleanup()

# Создание FastAPI приложения
app = FastAPI(
    title="DailyCheck Dashboard",
    description="Веб-дашборд для анализа данных Telegram бота",
    version="1.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Статические файлы
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Шаблоны
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Подключение API роутеров
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(stats.router, prefix="/api/stats", tags=["statistics"])
app.include_router(charts.router, prefix="/api/charts", tags=["charts"])

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
        raise HTTPException(status_code=500, detail="Ошибка сервера")

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
                "users": users_data
            }
        )
    except Exception as e:
        logger.error(f"Ошибка загрузки страницы пользователей: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

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
                "tasks": tasks_data
            }
        )
    except Exception as e:
        logger.error(f"Ошибка загрузки страницы задач: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

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
                "analytics": analytics_data
            }
        )
    except Exception as e:
        logger.error(f"Ошибка загрузки страницы аналитики: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

# ===== СЛУЖЕБНЫЕ МАРШРУТЫ =====

@app.get("/health")
async def health_check():
    """Health check для Render"""
    try:
        dm = data_manager
        if not dm:
            raise Exception("DataManager не инициализирован")
        
        # Проверяем доступность данных
        users_count = await dm.get_users_count()
        
        return JSONResponse(
            content={
                "status": "healthy",
                "service": "dashboard",
                "version": "1.0.0",
                "timestamp": str(Path(__file__).stat().st_mtime),
                "data": {
                    "users_count": users_count,
                    "data_dir": str(settings.DATA_DIR),
                    "debug_mode": settings.DEBUG
                }
            },
            status_code=200
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={
                "status": "unhealthy",
                "service": "dashboard",
                "error": str(e)
            },
            status_code=503
        )

@app.get("/api/info")
async def api_info():
    """Информация об API"""
    return {
        "name": "DailyCheck Dashboard API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "endpoints": {
            "users": "/api/users",
            "tasks": "/api/tasks", 
            "stats": "/api/stats",
            "charts": "/api/charts"
        }
    }

# ===== ОБРАБОТЧИКИ ОШИБОК =====

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Обработчик 404 ошибок"""
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={"detail": "API endpoint not found"}
        )
    
    return templates.TemplateResponse(
        "errors/404.html",
        {"request": request, "title": "Страница не найдена"},
        status_code=404
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    """Обработчик 500 ошибок"""
    logger.error(f"Internal server error: {exc}")
    
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    return templates.TemplateResponse(
        "errors/500.html",
        {"request": request, "title": "Ошибка сервера"},
        status_code=500
    )

# ===== ЗАПУСК ПРИЛОЖЕНИЯ =====

def run_dashboard():
    """Запуск дашборда"""
    logger.info(f"🌐 Запуск Dashboard на {settings.DASHBOARD_HOST}:{settings.DASHBOARD_PORT}")
    logger.info(f"📊 Данные бота: {settings.DATA_DIR}")
    logger.info(f"🔧 Режим отладки: {settings.DEBUG}")
    
    uvicorn.run(
        "dashboard.app:app",
        host=settings.DASHBOARD_HOST,
        port=settings.DASHBOARD_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=settings.DEBUG
    )

if __name__ == "__main__":
    run_dashboard(
