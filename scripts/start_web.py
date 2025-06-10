#!/usr/bin/env python3
"""
Скрипт запуска веб-дашборда
Использование: python scripts/start_web.py [--dev] [--port PORT] [--host HOST]
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Добавляем корневую папку в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.responses import HTMLResponse
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Установите зависимости: pip install -r requirements-web.txt")
    sys.exit(1)

# Настройка логирования (только в stdout для продакшена)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def create_app():
    """Создание FastAPI приложения"""
    
    app = FastAPI(
        title="Telegram Bot Dashboard",
        description="Веб-дашборд для управления Telegram ботом",
        version="1.0.0"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Gzip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": "web_dashboard",
            "message": "Dashboard is running!",
            "version": "1.0.0"
        }
    
    # Root endpoint с простым HTML
    @app.get("/", response_class=HTMLResponse)
    async def root():
        html_content = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 Telegram Bot Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .gradient-bg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .pulse-dot {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body class="bg-gray-50">
    <div class="min-h-screen flex items-center justify-center">
        <div class="max-w-4xl mx-auto p-8">
            <!-- Header -->
            <div class="text-center mb-8">
                <h1 class="text-4xl font-bold text-gray-800 mb-4">🤖 Telegram Bot Dashboard</h1>
                <div class="flex items-center justify-center space-x-2 mb-6">
                    <div class="pulse-dot w-3 h-3 bg-green-500 rounded-full"></div>
                    <span class="text-green-600 font-medium">Система запущена и работает</span>
                </div>
            </div>
            
            <!-- Main Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
                <!-- API Status -->
                <div class="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-semibold text-gray-800">API Status</h3>
                        <div class="w-3 h-3 bg-green-500 rounded-full"></div>
                    </div>
                    <p class="text-gray-600">FastAPI сервер активен</p>
                    <p class="text-sm text-gray-500 mt-2">Все endpoints доступны</p>
                </div>
                
                <!-- Dashboard -->
                <div class="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-semibold text-gray-800">Dashboard</h3>
                        <div class="w-3 h-3 bg-blue-500 rounded-full"></div>
                    </div>
                    <p class="text-gray-600">Веб-интерфейс готов</p>
                    <p class="text-sm text-gray-500 mt-2">Управление ботом</p>
                </div>
                
                <!-- Database -->
                <div class="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-semibold text-gray-800">Data</h3>
                        <div class="w-3 h-3 bg-purple-500 rounded-full"></div>
                    </div>
                    <p class="text-gray-600">JSON база данных</p>
                    <p class="text-sm text-gray-500 mt-2">Пользователи и задачи</p>
                </div>
            </div>
            
            <!-- API Endpoints -->
            <div class="bg-white rounded-xl shadow-lg p-6 border border-gray-100 mb-8">
                <h3 class="text-xl font-semibold text-gray-800 mb-4">🔗 Доступные API Endpoints</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="space-y-3">
                        <div class="flex items-center space-x-3">
                            <span class="w-2 h-2 bg-green-500 rounded-full"></span>
                            <a href="/health" class="text-blue-600 hover:underline font-mono text-sm">GET /health</a>
                            <span class="text-gray-500 text-xs">Статус системы</span>
                        </div>
                        <div class="flex items-center space-x-3">
                            <span class="w-2 h-2 bg-green-500 rounded-full"></span>
                            <a href="/api/stats/overview" class="text-blue-600 hover:underline font-mono text-sm">GET /api/stats/overview</a>
                            <span class="text-gray-500 text-xs">Общая статистика</span>
                        </div>
                        <div class="flex items-center space-x-3">
                            <span class="w-2 h-2 bg-green-500 rounded-full"></span>
                            <a href="/api/users" class="text-blue-600 hover:underline font-mono text-sm">GET /api/users</a>
                            <span class="text-gray-500 text-xs">Список пользователей</span>
                        </div>
                    </div>
                    <div class="space-y-3">
                        <div class="flex items-center space-x-3">
                            <span class="w-2 h-2 bg-green-500 rounded-full"></span>
                            <a href="/api/tasks" class="text-blue-600 hover:underline font-mono text-sm">GET /api/tasks</a>
                            <span class="text-gray-500 text-xs">Список задач</span>
                        </div>
                        <div class="flex items-center space-x-3">
                            <span class="w-2 h-2 bg-green-500 rounded-full"></span>
                            <a href="/api/charts/user-activity" class="text-blue-600 hover:underline font-mono text-sm">GET /api/charts/*</a>
                            <span class="text-gray-500 text-xs">Данные графиков</span>
                        </div>
                        <div class="flex items-center space-x-3">
                            <span class="w-2 h-2 bg-blue-500 rounded-full"></span>
                            <a href="/docs" class="text-blue-600 hover:underline font-mono text-sm">GET /docs</a>
                            <span class="text-gray-500 text-xs">API документация</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Stats Preview -->
            <div class="bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl shadow-lg p-6 text-white mb-8">
                <h3 class="text-xl font-semibold mb-4">📊 Быстрая статистика</h3>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="text-center">
                        <div class="text-2xl font-bold" id="user-count">-</div>
                        <div class="text-sm opacity-80">Пользователей</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold" id="task-count">-</div>
                        <div class="text-sm opacity-80">Задач</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold" id="completion-rate">-</div>
                        <div class="text-sm opacity-80">% Выполнений</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold" id="active-users">-</div>
                        <div class="text-sm opacity-80">Активных</div>
                    </div>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="text-center text-gray-500 text-sm">
                <p>🚀 Telegram Bot Dashboard v1.0.0</p>
                <p class="mt-1">Система управления ботом работает корректно</p>
            </div>
        </div>
    </div>
    
    <script>
        // Загружаем статистику
        async function loadStats() {
            try {
                const response = await fetch('/api/stats/overview');
                if (response.ok) {
                    const data = await response.json();
                    document.getElementById('user-count').textContent = data.users?.total || 0;
                    document.getElementById('task-count').textContent = data.tasks?.total || 0;
                    document.getElementById('completion-rate').textContent = Math.round(data.tasks?.completion_rate || 0);
                    document.getElementById('active-users').textContent = data.users?.active || 0;
                }
            } catch (error) {
                console.log('Статистика загрузится после настройки API');
            }
        }
        
        // Загружаем при открытии страницы
        loadStats();
        
        // Обновляем каждые 30 секунд
        setInterval(loadStats, 30000);
    </script>
</body>
</html>
        """
        return HTMLResponse(content=html_content)
    
    # Базовые API endpoints
    @app.get("/api/stats/overview")
    async def basic_stats():
        return {
            "users": {
                "total": 0,
                "active": 0,
                "new_today": 0,
                "new_week": 0
            },
            "tasks": {
                "total": 0,
                "completed": 0,
                "completion_rate": 0,
                "completed_24h": 0
            },
            "engagement": {
                "daily_active_rate": 0,
                "task_completion_rate": 0,
                "user_retention": 0
            }
        }
    
    @app.get("/api/users")
    async def basic_users():
        return []
    
    @app.get("/api/tasks")
    async def basic_tasks():
        return []
    
    # Try to import dashboard routes
    try:
        sys.path.append(str(project_root / "dashboard"))
        from dashboard.api.users import router as users_router
        from dashboard.api.tasks import router as tasks_router
        from dashboard.api.stats import router as stats_router
        from dashboard.api.charts import router as charts_router
        
        # Include routers
        app.include_router(users_router)
        app.include_router(tasks_router)
        app.include_router(stats_router)
        app.include_router(charts_router)
        
        logger.info("✅ Dashboard API routes loaded successfully")
        
    except ImportError as e:
        logger.warning(f"⚠️ Dashboard API routes not loaded: {e}")
        logger.info("Using basic endpoints only")
    
    return app

def main():
    """Главная функция запуска"""
    parser = argparse.ArgumentParser(description='Запуск веб-дашборда')
    parser.add_argument('--dev', action='store_true', help='Режим разработки')
    parser.add_argument('--port', type=int, default=8000, help='Порт для веб-сервера')
    parser.add_argument('--host', default="0.0.0.0", help='Хост для веб-сервера')
    
    args = parser.parse_args()
    
    # Определяем порт из переменной окружения PORT (для Render)
    port = int(os.getenv('PORT', args.port))
    
    # Создаем приложение
    app = create_app()
    
    logger.info(f"🚀 Запуск веб-сервера на http://{args.host}:{port}")
    
    # Запускаем сервер
    uvicorn.run(
        app,
        host=args.host,
        port=port,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()
