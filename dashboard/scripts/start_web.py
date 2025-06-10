#!/usr/bin/env python3
"""
Скрипт запуска веб-дашборда
Использование: python scripts/start_web.py [--dev] [--port PORT] [--host HOST]
"""

import sys
import os
import argparse
import logging
import signal
import asyncio
from pathlib import Path
from typing import Optional

# Добавляем корневую папку в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import uvicorn
    from fastapi import FastAPI, Request, Response
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.responses import JSONResponse
    import asyncio
    import time
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Установите зависимости: pip install -r requirements-web.txt")
    sys.exit(1)

# Настройка логирования
def setup_logging(dev_mode: bool = False):
    """Настройка системы логирования"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_level = logging.DEBUG if dev_mode else logging.INFO
    
    # Создаем папку для логов
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Настраиваем обработчики
    handlers = [
        logging.FileHandler(log_dir / 'web.log', encoding='utf-8'),
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
        self.static_dir = self.project_root / "static"
        self.templates_dir = self.dashboard_dir / "templates"
        
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
            self.project_root / 'data',
            self.project_root / 'temp'
        ]
        
        for directory in directories:
            Path(directory).mkdir(exist_ok=True)
        
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
        
        # Создаем основное приложение
        self.app = FastAPI(
            title="Telegram Bot Dashboard",
            description="Веб-дашборд для управления Telegram ботом и аналитики",
            version="1.0.0",
            docs_url="/docs" if self.dev_mode else None,
            redoc_url="/redoc" if self.dev_mode else None,
            openapi_url="/openapi.json" if self.dev_mode else None,
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
        
        # Обработчики ошибок
        self.setup_error_handlers()
        
        logger.info("✅ FastAPI приложение настроено")
    
    def setup_middleware(self):
        """Настройка middleware"""
        
        # Trusted Host middleware (для безопасности)
        if not self.dev_mode:
            self.app.add_middleware(
                TrustedHostMiddleware,
                allowed_hosts=["*"]  # В продакшене указать конкретные домены
            )
        
        # CORS middleware
        allowed_origins = ["*"] if self.dev_mode else [
            "https://yourdomain.com",
            "https://*.render.com",
            "https://dashboard-5q28.onrender.com"
        ]
        
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
        
        # Gzip compression
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)
        
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
            client_ip = request.headers.get("X-Forwarded-For", request.client.host)
            
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
    <title>{% block title %}Bot Dashboard{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</head>
<body class="bg-gray-100">
    <nav class="bg-white shadow-lg">
        <div class="max-w-7xl mx-auto px-4">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <h1 class="text-xl font-bold">🤖 Bot Dashboard</h1>
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
            <h2 class="text-lg font-medium text-gray-900 mb-4">Статистика бота</h2>
            
            <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div class="bg-blue-50 overflow-hidden shadow rounded-lg">
                    <div class="p-5">
                        <div class="flex items-center">
                            <div class="ml-5 w-0 flex-1">
                                <dl>
                                    <dt class="text-sm font-medium text-gray-500 truncate">Пользователи</dt>
                                    <dd class="text-lg font-medium text-gray-900">{{ stats.users_count or 0 }}</dd>
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
                                    <dd class="text-lg font-medium text-gray-900">{{ stats.tasks_count or 0 }}</dd>
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
                                    <dd class="text-lg font-medium text-gray-900">{{ stats.total_completions or 0 }}</dd>
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
                                    <dd class="text-lg font-medium text-gray-900">{{ stats.active_users_today or 0 }}</dd>
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
            # Импортируем роутеры из dashboard
            from dashboard.api.users import router as users_router
            from dashboard.api.tasks import router as tasks_router
            from dashboard.api.stats import router as stats_router
            from dashboard.api.charts import router as charts_router
            
            # Подключаем роутеры
            self.app.include_router(users_router, prefix="/api/users", tags=["users"])
            self.app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"])
            self.app.include_router(stats_router, prefix="/api/stats", tags=["stats"])
            self.app.include_router(charts_router, prefix="/api/charts", tags=["charts"])
            
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
                "dev_mode": self.dev_mode,
                "timestamp": time.time()
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
                    "daily_active_rate": 0.0,
                    "task_completion_rate": 0.0,
                    "user_retention": 0.0
                }
            }
        
        @self.app.get("/api/system/info")
        async def system_info():
            import platform
            import psutil
            
            return {
                "system": {
                    "platform": platform.system(),
                    "python_version": platform.python_version(),
                    "cpu_count": os.cpu_count(),
                    "memory_usage": psutil.virtual_memory().percent if 'psutil' in sys.modules else None
                },
                "app": {
                    "dev_mode": self.dev_mode,
                    "host": self.host,
                    "port": self.port
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
                        {
                            "request": request,
                            "stats": {
                                "users_count": 0,
                                "tasks_count": 0,
                                "total_completions": 0,
                                "active_users_today": 0
                            }
                        }
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
                "timestamp": time.time(),
                "uptime": time.time() - self.start_time if hasattr(self, 'start_time') else 0
            }
        
        @self.app.get("/ping")
        async def ping():
            """Простой ping endpoint"""
            return {"message": "pong"}
        
        logger.info("✅ Основные маршруты настроены")
    
    def get_basic_dashboard_html(self):
        """Базовый HTML для дашборда если шаблон не найден"""
        return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <div class="bg-white rounded-lg shadow-lg p-6">
            <h1 class="text-3xl font-bold text-gray-800 mb-4">🤖 Bot Dashboard</h1>
            
            <div class="bg-green-50 border border-green-200 rounded-lg p-4 mb-6">
                <p class="text-green-700">
                    <strong>✅ Статус:</strong> Веб-дашборд запущен и работает!
                </p>
                <p class="text-green-600 text-sm mt-2">
                    Режим: {'Разработка' if self.dev_mode else 'Продакшн'} | 
                    Адрес: {self.host}:{self.port}
                </p>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <h3 class="font-semibold text-blue-800">API Status</h3>
                    <p class="text-blue-600">✅ Активен</p>
                </div>
                
                <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <h3 class="font-semibold text-yellow-800">Шаблоны</h3>
                    <p class="text-yellow-600">🔄 Базовые</p>
                </div>
                
                <div class="bg-purple-50 border border-purple-200 rounded-lg p-4">
                    <h3 class="font-semibold text-purple-800">Данные</h3>
                    <p class="text-purple-600">⏳ Инициализация...</p>
                </div>
            </div>
            
            <div class="bg-white border rounded-lg p-6">
                <h2 class="text-xl font-semibold mb-4">🔗 API Endpoints:</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <h3 class="font-medium text-gray-700 mb-2">Основные:</h3>
                        <ul class="space-y-1 text-sm">
                            <li><a href="/api/health" class="text-blue-600 hover:underline">/api/health</a> - Проверка состояния</li>
                            <li><a href="/api/stats/overview" class="text-blue-600 hover:underline">/api/stats/overview</a> - Общая статистика</li>
                            <li><a href="/api/system/info" class="text-blue-600 hover:underline">/api/system/info</a> - Информация о системе</li>
                        </ul>
                    </div>
                    <div>
                        <h3 class="font-medium text-gray-700 mb-2">Документация:</h3>
                        <ul class="space-y-1 text-sm">
                            {"<li><a href='/docs' class='text-blue-600 hover:underline'>/docs</a> - API документация</li>" if self.dev_mode else "<li class='text-gray-400'>Документация отключена в продакшне</li>"}
                            <li><a href="/ping" class="text-blue-600 hover:underline">/ping</a> - Ping test</li>
                        </ul>
                    </div>
                </div>
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
            self.start_time = time.time()
            
            # Инициализация подключений к базе данных, кэшу и т.д.
            try:
                # Проверяем доступность системных ресурсов
                await self.check_system_resources()
                
                # Инициализация внешних сервисов
                await self.initialize_external_services()
                
                logger.info("✅ Инициализация завершена")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации: {e}")
        
        @self.app.on_event("shutdown")
        async def shutdown_event():
            logger.info("🛑 Веб-дашборд останавливается...")
            
            # Закрытие подключений и очистка ресурсов
            try:
                await self.cleanup_resources()
                logger.info("✅ Очистка ресурсов завершена")
            except Exception as e:
                logger.error(f"❌ Ошибка при остановке: {e}")
        
        logger.info("✅ Обработчики событий настроены")
    
    async def check_system_resources(self):
        """Проверка системных ресурсов"""
        try:
            # Проверяем доступность папок
            required_dirs = [self.project_root, self.dashboard_dir]
            for directory in required_dirs:
                if not directory.exists():
                    logger.warning(f"⚠️ Папка не найдена: {directory}")
            
            # Проверяем доступное место на диске
            import shutil
            total, used, free = shutil.disk_usage(self.project_root)
            free_gb = free // (1024**3)
            
            if free_gb < 1:  # Меньше 1 ГБ
                logger.warning(f"⚠️ Мало свободного места: {free_gb} ГБ")
            
            logger.info(f"💾 Свободно места: {free_gb} ГБ")
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки ресурсов: {e}")
    
    async def initialize_external_services(self):
        """Инициализация внешних сервисов"""
        try:
            # Здесь можно добавить инициализацию:
            # - Подключение к базе данных
            # - Инициализация Redis/кэша  
            # - Проверка внешних API
            # - Настройка мониторинга
            
            logger.info("🔧 Внешние сервисы инициализированы")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации сервисов: {e}")
    
    async def cleanup_resources(self):
        """Очистка ресурсов"""
        try:
            # Здесь можно добавить очистку:
            # - Закрытие подключений к БД
            # - Сохранение состояния
            # - Остановка фоновых задач
            
            logger.info("🧹 Ресурсы очищены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки ресурсов: {e}")
    
    def setup_error_handlers(self):
        """Настройка обработчиков ошибок"""
        
        @self.app.exception_handler(404)
        async def not_found_handler(request: Request, exc):
            return JSONResponse(
                status_code=404,
                content={
                    "detail": "Endpoint not found",
                    "path": str(request.url.path),
                    "method": request.method
                }
            )
        
        @self.app.exception_handler(500)
        async def internal_error_handler(request: Request, exc):
            logger.error(f"Internal server error: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "dev_mode": self.dev_mode
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
        
        logger.info(f"🌐 Запуск веб-сервера на http://{self.host}:{self.port}")
        logger.info(f"📊 Режим: {'Разработка' if self.dev_mode else 'Продакшн'}")
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

async def async_main():
    """Асинхронная главная функция"""
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Запуск веб-дашборда')
    parser.add_argument('--dev', action='store_true', help='Режим разработки')
    parser.add_argument('--port', type=int, default=8000, help='Порт для веб-сервера')
    parser.add_argument('--host', default="0.0.0.0", help='Хост для веб-сервера')
    parser.add_argument('--reload', action='store_true', help='Автоперезагрузка при изменениях')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help='Уровень логирования')
    
    args = parser.parse_args()
    
    # Определяем режим разработки
    dev_mode = args.dev or args.reload or os.getenv('ENVIRONMENT') == 'development'
    
    # Настраиваем логирование
    setup_logging(dev_mode)
    
    if dev_mode:
        os.environ['ENVIRONMENT'] = 'development'
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
