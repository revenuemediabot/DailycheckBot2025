#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailycheckBot2025 - Dashboard Configuration
Конфигурация веб-дашборда с настройками для разных сред

Автор: AI Assistant
Версия: 1.0.0
Дата: 2025-06-10
"""

import os
import secrets
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseSettings, Field, validator, root_validator
import logging

class DashboardSettings(BaseSettings):
    """Настройки веб-дашборда DailycheckBot2025"""
    
    # ===== ОСНОВНЫЕ НАСТРОЙКИ =====
    
    APP_NAME: str = Field(
        default="DailycheckBot2025 Dashboard",
        description="Название приложения"
    )
    
    VERSION: str = Field(
        default="1.0.0",
        description="Версия дашборда"
    )
    
    ENVIRONMENT: str = Field(
        default="development", 
        description="Среда выполнения (development/production/testing)"
    )
    
    DEBUG: bool = Field(
        default=True,
        description="Режим отладки"
    )
    
    SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Секретный ключ для сессий и JWT"
    )
    
    # ===== СЕТЕВЫЕ НАСТРОЙКИ =====
    
    DASHBOARD_HOST: str = Field(
        default="0.0.0.0",
        description="Хост для запуска дашборда"
    )
    
    DASHBOARD_PORT: int = Field(
        default=8000,
        description="Порт для запуска дашборда"
    )
    
    BASE_URL: Optional[str] = Field(
        default=None,
        description="Базовый URL дашборда (для продакшена)"
    )
    
    # ===== CORS НАСТРОЙКИ =====
    
    ALLOWED_ORIGINS: List[str] = Field(
        default=["*"],
        description="Разрешенные источники для CORS"
    )
    
    ALLOWED_METHODS: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Разрешенные HTTP методы"
    )
    
    ALLOWED_HEADERS: List[str] = Field(
        default=["*"],
        description="Разрешенные заголовки"
    )
    
    ALLOW_CREDENTIALS: bool = Field(
        default=True,
        description="Разрешить передачу cookies и авторизационных заголовков"
    )
    
    # ===== ПУТИ И ФАЙЛЫ =====
    
    PROJECT_ROOT: Path = Field(
        default=Path(__file__).parent.parent,
        description="Корневая папка проекта"
    )
    
    DATA_DIR: Path = Field(
        default=Path("bot"),
        description="Директория с данными бота"
    )
    
    STATIC_DIR: Path = Field(
        default=Path("dashboard/static"),
        description="Директория статических файлов"
    )
    
    TEMPLATES_DIR: Path = Field(
        default=Path("dashboard/templates"),
        description="Директория шаблонов"
    )
    
    LOGS_DIR: Path = Field(
        default=Path("logs"),
        description="Директория логов"
    )
    
    # ===== ФАЙЛЫ ДАННЫХ БОТА =====
    
    BOT_DATA_FILES: Dict[str, str] = Field(
        default={
            "users": "users_data.json",
            "tasks": "tasks.json",
            "achievements": "achievements.json",
            "stats": "bot_stats.json",
            "settings": "bot_settings.json"
        },
        description="Имена файлов данных бота"
    )
    
    # ===== ЛОГИРОВАНИЕ =====
    
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Уровень логирования (DEBUG/INFO/WARNING/ERROR/CRITICAL)"
    )
    
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Формат логов"
    )
    
    LOG_DATE_FORMAT: str = Field(
        default="%Y-%m-%d %H:%M:%S",
        description="Формат даты в логах"
    )
    
    # ===== TELEGRAM ИНТЕГРАЦИЯ =====
    
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Токен Telegram бота (для интеграции)"
    )
    
    TELEGRAM_BOT_USERNAME: Optional[str] = Field(
        default=None,
        description="Username Telegram бота для авторизации"
    )
    
    TELEGRAM_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="URL вебхука Telegram"
    )
    
    WEBAPP_URL: Optional[str] = Field(
        default=None,
        description="URL веб-приложения для Telegram Web App"
    )
    
    # ===== БЕЗОПАСНОСТЬ =====
    
    SESSION_TIMEOUT: int = Field(
        default=3600,
        description="Таймаут сессии в секундах (1 час)"
    )
    
    API_RATE_LIMIT: str = Field(
        default="100/minute",
        description="Лимит запросов к API"
    )
    
    MAX_CONTENT_LENGTH: int = Field(
        default=16 * 1024 * 1024,  # 16MB
        description="Максимальный размер загружаемого контента"
    )
    
    ADMIN_USER_IDS: List[int] = Field(
        default=[],
        description="ID пользователей с правами администратора"
    )
    
    # ===== КЭШИРОВАНИЕ =====
    
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="URL Redis для кэширования"
    )
    
    CACHE_TTL: int = Field(
        default=300,
        description="TTL кэша в секундах (5 минут)"
    )
    
    CACHE_ENABLED: bool = Field(
        default=True,
        description="Включить кэширование"
    )
    
    # ===== БАЗА ДАННЫХ (опционально) =====
    
    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="URL базы данных PostgreSQL (если используется вместо JSON)"
    )
    
    DB_POOL_SIZE: int = Field(
        default=5,
        description="Размер пула соединений БД"
    )
    
    DB_MAX_OVERFLOW: int = Field(
        default=10,
        description="Максимальное количество дополнительных соединений"
    )
    
    # ===== МОНИТОРИНГ И МЕТРИКИ =====
    
    METRICS_ENABLED: bool = Field(
        default=True,
        description="Включить сбор метрик"
    )
    
    HEALTH_CHECK_INTERVAL: int = Field(
        default=60,
        description="Интервал health check в секундах"
    )
    
    SENTRY_DSN: Optional[str] = Field(
        default=None,
        description="DSN для Sentry (мониторинг ошибок)"
    )
    
    # ===== ГРАФИКИ И АНАЛИТИКА =====
    
    CHART_COLORS: Dict[str, str] = Field(
        default={
            "primary": "#3b82f6",
            "secondary": "#6b7280",
            "success": "#10b981",
            "warning": "#f59e0b",
            "danger": "#ef4444",
            "info": "#06b6d4",
            "purple": "#8b5cf6",
            "pink": "#ec4899",
            "indigo": "#6366f1",
            "teal": "#14b8a6"
        },
        description="Цветовая палитра для графиков"
    )
    
    CHART_GRADIENTS: List[str] = Field(
        default=[
            "#3b82f6", "#06b6d4", "#10b981", "#f59e0b", 
            "#ec4899", "#8b5cf6", "#ef4444", "#6366f1"
        ],
        description="Градиентные цвета для графиков"
    )
    
    MAX_CHART_POINTS: int = Field(
        default=100,
        description="Максимальное количество точек на графике"
    )
    
    DEFAULT_TIME_RANGE: int = Field(
        default=30,
        description="Диапазон времени по умолчанию (дни)"
    )
    
    CHART_ANIMATION_DURATION: int = Field(
        default=750,
        description="Длительность анимации графиков (мс)"
    )
    
    # ===== API НАСТРОЙКИ =====
    
    API_V1_PREFIX: str = Field(
        default="/api/v1",
        description="Префикс API версии 1"
    )
    
    DOCS_URL: Optional[str] = Field(
        default="/api/docs",
        description="URL документации API (None для отключения)"
    )
    
    REDOC_URL: Optional[str] = Field(
        default="/api/redoc",
        description="URL ReDoc документации (None для отключения)"
    )
    
    OPENAPI_URL: Optional[str] = Field(
        default="/api/openapi.json",
        description="URL OpenAPI схемы (None для отключения)"
    )
    
    # ===== ПАГИНАЦИЯ =====
    
    DEFAULT_PAGE_SIZE: int = Field(
        default=20,
        description="Размер страницы по умолчанию"
    )
    
    MAX_PAGE_SIZE: int = Field(
        default=100,
        description="Максимальный размер страницы"
    )
    
    # ===== ЭКСПОРТ ДАННЫХ =====
    
    EXPORT_FORMATS: List[str] = Field(
        default=["json", "csv", "xlsx"],
        description="Поддерживаемые форматы экспорта"
    )
    
    MAX_EXPORT_RECORDS: int = Field(
        default=10000,
        description="Максимальное количество записей для экспорта"
    )
    
    # ===== ВАЛИДАТОРЫ =====
    
    @validator('ENVIRONMENT')
    def validate_environment(cls, v):
        """Валидация среды выполнения"""
        allowed_envs = ['development', 'production', 'testing', 'staging']
        if v.lower() not in allowed_envs:
            raise ValueError(f"ENVIRONMENT must be one of {allowed_envs}")
        return v.lower()
    
    @validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        """Валидация уровня логирования"""
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed_levels:
            raise ValueError(f"LOG_LEVEL must be one of {allowed_levels}")
        return v.upper()
    
    @validator('DASHBOARD_PORT')
    def validate_port(cls, v):
        """Валидация порта"""
        if not 1 <= v <= 65535:
            raise ValueError("DASHBOARD_PORT must be between 1 and 65535")
        return v
    
    @validator('DATA_DIR')
    def validate_data_dir(cls, v):
        """Валидация директории данных"""
        if isinstance(v, str):
            v = Path(v)
        
        # В продакшене директория должна существовать
        if os.getenv('ENVIRONMENT', '').lower() == 'production':
            if not v.exists():
                raise ValueError(f"Data directory {v} does not exist in production")
        
        return v
    
    @validator('ALLOWED_ORIGINS')
    def validate_origins(cls, v):
        """Валидация CORS origins"""
        if isinstance(v, str):
            # Если передана строка, разделяем по запятой
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    @validator('ADMIN_USER_IDS')
    def validate_admin_ids(cls, v):
        """Валидация ID администраторов"""
        if isinstance(v, str):
            # Если передана строка, разделяем по запятой
            try:
                return [int(uid.strip()) for uid in v.split(',') if uid.strip()]
            except ValueError:
                raise ValueError("ADMIN_USER_IDS must be comma-separated integers")
        return v
    
    @root_validator
    def validate_production_settings(cls, values):
        """Валидация настроек для продакшена"""
        env = values.get('ENVIRONMENT', '').lower()
        
        if env == 'production':
            # В продакшене отключаем DEBUG
            values['DEBUG'] = False
            
            # В продакшене должен быть установлен SECRET_KEY
            if values.get('SECRET_KEY') == secrets.token_urlsafe(32):
                # Генерируем новый ключ для продакшена
                values['SECRET_KEY'] = secrets.token_urlsafe(32)
            
            # В продакшене отключаем документацию API
            if values.get('DEBUG') is False:
                values['DOCS_URL'] = None
                values['REDOC_URL'] = None
        
        return values
    
    # ===== МЕТОДЫ КОНФИГУРАЦИИ =====
    
    @property
    def is_production(self) -> bool:
        """Проверка продакшен среды"""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Проверка среды разработки"""
        return self.ENVIRONMENT == "development"
    
    @property
    def is_testing(self) -> bool:
        """Проверка тестовой среды"""
        return self.ENVIRONMENT == "testing"
    
    def get_data_file_path(self, file_type: str) -> Path:
        """Получить полный путь к файлу данных бота"""
        if file_type not in self.BOT_DATA_FILES:
            raise ValueError(f"Unknown data file type: {file_type}. Available: {list(self.BOT_DATA_FILES.keys())}")
        
        filename = self.BOT_DATA_FILES[file_type]
        return self.DATA_DIR / filename
    
    def get_chart_color(self, color_name: str) -> str:
        """Получить цвет для графика"""
        return self.CHART_COLORS.get(color_name, self.CHART_COLORS["primary"])
    
    def get_gradient_colors(self, count: int = None) -> List[str]:
        """Получить градиентные цвета для графиков"""
        if count is None:
            return self.CHART_GRADIENTS
        
        # Циклически повторяем цвета если нужно больше
        colors = []
        for i in range(count):
            colors.append(self.CHART_GRADIENTS[i % len(self.CHART_GRADIENTS)])
        return colors
    
    def get_full_url(self, path: str = "") -> str:
        """Получить полный URL"""
        if self.BASE_URL:
            return f"{self.BASE_URL.rstrip('/')}/{path.lstrip('/')}"
        else:
            return f"http://{self.DASHBOARD_HOST}:{self.DASHBOARD_PORT}/{path.lstrip('/')}"
    
    def setup_logging(self) -> None:
        """Настройка логирования"""
        # Создаем директорию логов если её нет
        self.LOGS_DIR.mkdir(exist_ok=True)
        
        # Настройка основного логгера
        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL),
            format=self.LOG_FORMAT,
            datefmt=self.LOG_DATE_FORMAT,
            handlers=[
                logging.StreamHandler(),  # Вывод в консоль
                logging.FileHandler(
                    self.LOGS_DIR / "dashboard.log",
                    encoding='utf-8'
                )
            ]
        )
        
        # Настройка логгеров внешних библиотек
        if not self.DEBUG:
            logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
            logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        allow_population_by_field_name = True

# ===== СОЗДАНИЕ ЭКЗЕМПЛЯРА НАСТРОЕК =====

settings = DashboardSettings()

# ===== КОНСТАНТЫ И КОНФИГУРАЦИОННЫЕ ДАННЫЕ =====

# Категории задач с метаданными
TASK_CATEGORIES = {
    "work": {
        "name": "Работа",
        "name_en": "Work",
        "icon": "💼",
        "color": "#3b82f6",
        "description": "Рабочие задачи и проекты"
    },
    "health": {
        "name": "Здоровье",
        "name_en": "Health",
        "icon": "🏃",
        "color": "#10b981",
        "description": "Здоровье и физическая активность"
    },
    "learning": {
        "name": "Обучение",
        "name_en": "Learning",
        "icon": "📚",
        "color": "#8b5cf6",
        "description": "Образование и развитие навыков"
    },
    "personal": {
        "name": "Личное",
        "name_en": "Personal",
        "icon": "👤",
        "color": "#ec4899",
        "description": "Личные дела и хобби"
    },
    "finance": {
        "name": "Финансы",
        "name_en": "Finance",
        "icon": "💰",
        "color": "#f59e0b",
        "description": "Финансовое планирование"
    },
    "social": {
        "name": "Социальное",
        "name_en": "Social",
        "icon": "👥",
        "color": "#06b6d4",
        "description": "Общение и социальные активности"
    }
}

# Приоритеты задач
TASK_PRIORITIES = {
    "low": {
        "name": "Низкий",
        "name_en": "Low",
        "icon": "🔵",
        "color": "#06b6d4",
        "weight": 1
    },
    "medium": {
        "name": "Средний",
        "name_en": "Medium",
        "icon": "🟡",
        "color": "#f59e0b",
        "weight": 2
    },
    "high": {
        "name": "Высокий",
        "name_en": "High",
        "icon": "🔴",
        "color": "#ef4444",
        "weight": 3
    },
    "urgent": {
        "name": "Срочный",
        "name_en": "Urgent",
        "icon": "🚨",
        "color": "#dc2626",
        "weight": 4
    }
}

# Статусы задач
TASK_STATUSES = {
    "active": {
        "name": "Активная",
        "name_en": "Active",
        "icon": "✅",
        "color": "#10b981"
    },
    "paused": {
        "name": "Приостановлена",
        "name_en": "Paused",
        "icon": "⏸️",
        "color": "#f59e0b"
    },
    "completed": {
        "name": "Завершена",
        "name_en": "Completed",
        "icon": "🏆",
        "color": "#8b5cf6"
    },
    "archived": {
        "name": "Архивная",
        "name_en": "Archived",
        "icon": "📦",
        "color": "#6b7280"
    },
    "cancelled": {
        "name": "Отменена",
        "name_en": "Cancelled",
        "icon": "❌",
        "color": "#ef4444"
    }
}

# Уровни пользователей
USER_LEVELS = {
    1: {"title": "🌱 Новичок", "title_en": "🌱 Beginner", "min_xp": 0, "color": "#10b981"},
    2: {"title": "🌿 Начинающий", "title_en": "🌿 Novice", "min_xp": 100, "color": "#10b981"},
    3: {"title": "🌳 Ученик", "title_en": "🌳 Learner", "min_xp": 300, "color": "#06b6d4"},
    4: {"title": "⚡ Активист", "title_en": "⚡ Activist", "min_xp": 600, "color": "#3b82f6"},
    5: {"title": "💪 Энтузиаст", "title_en": "💪 Enthusiast", "min_xp": 1000, "color": "#8b5cf6"},
    6: {"title": "🎯 Целеустремленный", "title_en": "🎯 Focused", "min_xp": 1500, "color": "#ec4899"},
    7: {"title": "🔥 Мотивированный", "title_en": "🔥 Motivated", "min_xp": 2200, "color": "#f59e0b"},
    8: {"title": "⭐ Продвинутый", "title_en": "⭐ Advanced", "min_xp": 3000, "color": "#f97316"},
    9: {"title": "💎 Эксперт", "title_en": "💎 Expert", "min_xp": 4000, "color": "#84cc16"},
    10: {"title": "🏆 Мастер", "title_en": "🏆 Master", "min_xp": 5500, "color": "#eab308"},
    11: {"title": "👑 Гуру", "title_en": "👑 Guru", "min_xp": 7500, "color": "#a855f7"},
    12: {"title": "🌟 Легенда", "title_en": "🌟 Legend", "min_xp": 10000, "color": "#e11d48"},
    13: {"title": "⚡ Супергерой", "title_en": "⚡ Superhero", "min_xp": 15000, "color": "#0ea5e9"},
    14: {"title": "🚀 Чемпион", "title_en": "🚀 Champion", "min_xp": 20000, "color": "#06b6d4"},
    15: {"title": "💫 Божество", "title_en": "💫 Deity", "min_xp": 30000, "color": "#8b5cf6"}
}

# Достижения
ACHIEVEMENTS = {
    "first_task": {
        "title": "Первые шаги",
        "title_en": "First Steps",
        "description": "Создайте свою первую задачу",
        "description_en": "Create your first task",
        "icon": "🎯",
        "xp_reward": 50,
        "category": "basic"
    },
    "streak_3": {
        "title": "Начало серии",
        "title_en": "Streak Start",
        "description": "Поддерживайте streak 3 дня",
        "description_en": "Maintain a 3-day streak",
        "icon": "🔥",
        "xp_reward": 100,
        "category": "streak"
    },
    "streak_7": {
        "title": "Неделя силы",
        "title_en": "Week of Power",
        "description": "Поддерживайте streak 7 дней",
        "description_en": "Maintain a 7-day streak",
        "icon": "💪",
        "xp_reward": 200,
        "category": "streak"
    },
    "streak_30": {
        "title": "Месячный марафон",
        "title_en": "Monthly Marathon",
        "description": "Поддерживайте streak 30 дней",
        "description_en": "Maintain a 30-day streak",
        "icon": "🏃",
        "xp_reward": 500,
        "category": "streak"
    },
    "tasks_100": {
        "title": "Чемпион",
        "title_en": "Champion",
        "description": "Выполните 100 задач",
        "description_en": "Complete 100 tasks",
        "icon": "🌟",
        "xp_reward": 500,
        "category": "completion"
    }
}

# API лимиты
API_LIMITS = {
    "max_users_per_request": 100,
    "max_tasks_per_request": 200,
    "max_date_range_days": 365,
    "default_page_size": 20,
    "max_page_size": 100,
    "max_export_records": 10000
}

# Время жизни кэша для разных типов данных
CACHE_TTL_SETTINGS = {
    "users_list": 300,      # 5 минут
    "user_details": 180,    # 3 минуты
    "tasks_list": 240,      # 4 минуты
    "statistics": 600,      # 10 минут
    "charts_data": 300,     # 5 минут
    "achievements": 3600    # 1 час
}

# Конфигурация Chart.js
CHART_CONFIG = {
    "default_animation": {
        "duration": 750,
        "easing": "easeInOutQuart"
    },
    "responsive_options": {
        "responsive": True,
        "maintainAspectRatio": False
    },
    "font_family": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "grid_color": "#e5e7eb",
    "grid_color_dark": "#374151"
}

# Настройки уведомлений
NOTIFICATION_SETTINGS = {
    "toast_duration": 5000,  # 5 секунд
    "max_notifications": 5,
    "auto_hide": True,
    "position": "top-right"
}

# Функция инициализации настроек
def init_settings() -> DashboardSettings:
    """Инициализация и валидация настроек"""
    try:
        # Настройка логирования
        settings.setup_logging()
        
        # Создание необходимых директорий
        settings.DATA_DIR.mkdir(exist_ok=True)
        settings.LOGS_DIR.mkdir(exist_ok=True)
        settings.STATIC_DIR.mkdir(exist_ok=True)
        settings.TEMPLATES_DIR.mkdir(exist_ok=True)
        
        logger = logging.getLogger(__name__)
        logger.info(f"✅ Dashboard settings initialized for {settings.ENVIRONMENT} environment")
        logger.info(f"📊 Data directory: {settings.DATA_DIR}")
        logger.info(f"🌐 Dashboard URL: {settings.get_full_url()}")
        
        return settings
        
    except Exception as e:
        print(f"❌ Error initializing dashboard settings: {e}")
        raise

# Инициализация при импорте модуля
if __name__ != "__main__":
    settings = init_settings()
