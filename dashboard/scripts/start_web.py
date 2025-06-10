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
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    import asyncio
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Установите зависимости: pip install -r requirements-web.txt")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/web.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class WebStarter:
    def __init__(self, dev_mode=False):
        self.dev_mode = dev_mode
        self.app = None
        
        # Настройка путей
        self.project_root = Path(__file__).parent.parent
        self.dashboard_dir = self.project_root / "dashboard"
        self.static_dir = self.project_root / "static"
        self.templates_dir = self.dashboard_dir / "templates"
        
        # Создаем необходимые папки
        os.makedirs('logs', exist_ok=True)
        os.makedirs(self.static_dir, exist_ok=True)
        
        self.setup_app()
    
    def setup_app(self):
        """Настройка FastAPI приложения"""
        
        # Создаем основное приложение
        self.app = FastAPI(
            title="Telegram Bot Dashboard",
            description="Веб-дашборд для управления Telegram ботом и аналитики",
            version="1.0.0",
            docs_url="/docs" if self.dev_mode else None,
            redoc_url="/redoc" if self.dev_mode else None,
            debug=self.dev_mode
        )
        
        # Настройка middleware
        self.setup_middleware()
        
        # Настройка статических файлов и шаблонов
        self.setup_static_files()
        
        # Подключение роутеров API
        self.setup_api_routes()
        
        # Настройка основных маршрутов
        self.setup_main_routes()
        
        # Обработчики событий
        self.setup_event_handlers()
        
        logger.info("✅ FastAPI приложение настроено")
    
    def setup_middleware(self):
        """Настройка middleware"""
        
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"] if self.dev_mode else [
                "https://yourdomain.com",  # Замените на ваш домен
                "https://*.render.com"
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Gzip compression
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)
        
        # Security headers middleware
        @self.app.middleware("http")
        async def add_security_headers(request, call_next):
            response = await call_next(request)
            
            if not self.dev_mode:
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["X-XSS-Protection"] = "1; mode=block"
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
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
        
        # Настраиваем шаблоны
        if self.templates_dir.exists():
            self.templates = Jinja2Templates(directory=str(self.templates_dir))
            logger.info(f"✅ Шаблоны подключены: {self.templates_dir}")
        else:
            logger.warning(f"⚠️ Папка шаблонов не найдена: {self.templates_dir}")
    
    def setup_api_routes(self):
        """Подключение API роутеров"""
        
        try:
            # Импортируем роутеры из dashboard
            from dashboard.api.users import router as users_router
            from dashboard.api.tasks import router as tasks_router
            from dashboard.api.stats import router as stats_router
            from dashboard.api.charts import router as charts_router
            
            # Подключаем роутеры
            self.app.include_router(users_router)
            self.app.include_router(tasks_router)
            self.app.include_router(stats_router)
            self.app.include_router(charts_router)
            
            logger.info("✅ API роутеры подключены")
            
        except ImportError as e:
            logger.error(f"❌ Ошибка подключения API роутеров: {e}")
            logger.info("Создаем базовые API endpoints...")
            self.setup_basic_api()
    
    def setup_basic_api(self):
        """Базовые API endpoints для тестирования"""
        
        @self.app.get("/api/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": "dashboard",
                "version": "1.0.0",
                "dev_mode": self.dev_mode
            }
        
        @self.app.get("/api/stats/overview")
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
        
        logger.info("✅ Базовые API endpoints созданы")
    
    def setup_main_routes(self):
        """Настройка основных маршрутов"""
        
        from fastapi import Request
        from fastapi.responses import HTMLResponse, RedirectResponse
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Главная страница дашборда"""
            try:
                if hasattr(self, 'templates'):
                    return self.templates.TemplateResponse(
                        "dashboard.html", 
                        {"request": request}
                    )
                else:
                    return HTMLResponse(self.get_basic_dashboard_html())
            except Exception as e:
                logger.error(f"Ошибка загрузки шаблона: {e}")
                return HTMLResponse(self.get_basic_dashboard_html())
        
        @self.app.get("/dashboard")
        async def dashboard_redirect():
            """Редирект на главную"""
            return RedirectResponse(url="/", status_code=301)
        
        @self.app.get("/health")
        async def web_health():
            """Health check для веб-сервиса"""
            return {
                "status": "healthy",
                "service": "web_dashboard",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        
        logger.info("✅ Основные маршруты настроены")
    
    def get_basic_dashboard_html(self):
        """Базовый HTML для дашборда если шаблон не найден"""
        return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <div class="bg-white rounded-lg shadow-lg p-6">
            <h1 class="text-3xl font-bold text-gray-800 mb-4">🤖 Bot Dashboard</h1>
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                <p class="text-blue-700">
                    <strong>Статус:</strong> Веб-дашборд запущен и работает!
                </p>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="bg-green-50 border border-green-200 rounded-lg p-4">
                    <h3 class="font-semibold text-green-800">API Status</h3>
                    <p class="text-green-600">Активен</p>
                </div>
                
                <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <h3 class="font-semibold text-yellow-800">Шаблоны</h3>
                    <p class="text-yellow-600">Загрузка...</p>
                </div>
                
                <div class="bg-purple-50 border border-purple-200 rounded-lg p-4">
                    <h3 class="font-semibold text-purple-800">Данные</h3>
                    <p class="text-purple-600">Инициализация...</p>
                </div>
            </div>
            
            <div class="mt-8">
                <h2 class="text-xl font-semibold mb-4">API Endpoints:</h2>
                <ul class="space-y-2">
                    <li><a href="/api/health" class="text-blue-600 hover:underline">/api/health</a> - Проверка состояния</li>
                    <li><a href="/api/stats/overview" class="text-blue-600 hover:underline">/api/stats/overview</a> - Общая статистика</li>
                    <li><a href="/docs" class="text-blue-600 hover:underline">/docs</a> - API документация (только в dev режиме)</li>
                </ul>
            </div>
        </div>
    </div>
</body>
</html>
        """
    
    def setup_event_handlers(self):
        """Настройка обработчиков событий"""
        
        @self.app.on_event("startup")
        async def startup_event():
            logger.info("🚀 Веб-дашборд запускается...")
            
            # Инициализация подключений к базе данных, кэшу и т.д.
            try:
                # Здесь можно добавить инициализацию внешних сервисов
                logger.info("✅ Инициализация завершена")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации: {e}")
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            logger.info("🛑 Веб-дашборд останавливается...")
            
            # Закрытие подключений и очистка ресурсов
            try:
                # Здесь можно добавить очистку ресурсов
                logger.info("✅ Очистка ресурсов завершена")
            except Exception as e:
                logger.error(f"❌ Ошибка при остановке: {e}")
        
        logger.info("✅ Обработчики событий настроены")
    
    async def start_server(self, host="0.0.0.0", port=8000):
        """Запуск веб-сервера"""
        
        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="debug" if self.dev_mode else "info",
            reload=self.dev_mode,
            access_log=True,
            server_header=False,
            date_header=False
        )
        
        server = uvicorn.Server(config)
        
        logger.info(f"🌐 Запуск веб-сервера на http://{host}:{port}")
        logger.info("Нажмите Ctrl+C для остановки...")
        
        try:
            await server.serve()
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки...")
        except Exception as e:
            logger.error(f"❌ Ошибка веб-сервера: {e}")
            raise
        finally:
            logger.info("✅ Веб-сервер остановлен")

def main():
    """Главная функция запуска"""
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Запуск веб-дашборда')
    parser.add_argument('--dev', action='store_true', help='Режим разработки')
    parser.add_argument('--port', type=int, default=8000, help='Порт для веб-сервера')
    parser.add_argument('--host', default="0.0.0.0", help='Хост для веб-сервера')
    parser.add_argument('--reload', action='store_true', help='Автоперезагрузка при изменениях')
    
    args = parser.parse_args()
    
    # Определяем режим разработки
    dev_mode = args.dev or args.reload or os.getenv('ENVIRONMENT') == 'development'
    
    if dev_mode:
        os.environ['ENVIRONMENT'] = 'development'
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🔧 Режим разработки активирован")
    
    # Определяем порт (для продакшена может быть переменная окружения)
    port = int(os.getenv('PORT', args.port))
    
    # Создаем и запускаем веб-приложение
    try:
        starter = WebStarter(dev_mode=dev_mode)
        asyncio.run(starter.start_server(host=args.host, port=port))
        
    except KeyboardInterrupt:
        logger.info("👋 Пока!")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
