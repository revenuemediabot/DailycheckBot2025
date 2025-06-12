#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Bot v4.0 - Complete Configuration Management
Полная конфигурация со всеми настройками из оригинального main.py

Author: AI Assistant  
Version: 4.0.0
Date: 2025-06-12
Исправленная версия с правильными путями и полным функционалом
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import json

# Проверка доступности библиотек
try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

class BotConfig:
    """Полная конфигурация бота с сохранением всех настроек из оригинала"""
    
    # ===== ОСНОВНЫЕ НАСТРОЙКИ =====
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))
    
    # ===== СЕТЕВЫЕ НАСТРОЙКИ =====
    PORT = int(os.getenv('PORT', 8080))
    HOST = os.getenv('HOST', '0.0.0.0')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
    
    # ===== ФАЙЛОВАЯ СИСТЕМА =====
    DATA_DIR = Path(os.getenv('DATA_DIR', 'data'))
    EXPORT_DIR = Path(os.getenv('EXPORT_DIR', 'exports'))
    BACKUP_DIR = Path(os.getenv('BACKUP_DIR', 'backups'))
    LOG_DIR = Path(os.getenv('LOG_DIR', 'logs'))
    
    # ===== AI НАСТРОЙКИ =====
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    OPENAI_MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', 1000))
    AI_CHAT_ENABLED = os.getenv('AI_CHAT_ENABLED', 'true').lower() == 'true'
    
    # ===== GOOGLE SHEETS =====
    GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '')
    GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'service_account.json')
    
    # ===== ПРОИЗВОДИТЕЛЬНОСТЬ =====
    MAX_USERS_CACHE = int(os.getenv('MAX_USERS_CACHE', 1000))
    BACKUP_INTERVAL_HOURS = int(os.getenv('BACKUP_INTERVAL_HOURS', 6))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    
    # ===== БАЗА ДАННЫХ =====
    DATABASE_URL = os.getenv('DATABASE_URL', '')
    USE_SQLITE = os.getenv('USE_SQLITE', 'true').lower() == 'true'
    DATABASE_BACKUP_ENABLED = os.getenv('DATABASE_BACKUP_ENABLED', 'true').lower() == 'true'
    
    # ===== БЕЗОПАСНОСТЬ =====
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '')
    RATE_LIMIT_ENABLED = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    
    # ===== ВЕАБ-ДАШБОРД =====
    ENABLE_WEB_DASHBOARD = os.getenv('ENABLE_WEB_DASHBOARD', 'true').lower() == 'true'
    WEB_PORT = int(os.getenv('WEB_PORT', 8081))
    WEB_HOST = os.getenv('WEB_HOST', '0.0.0.0')
    DASHBOARD_SECRET_KEY = os.getenv('DASHBOARD_SECRET_KEY', 'dashboard-secret-key')
    
    # ===== ФЛАГИ ФУНКЦИЙ =====
    ENABLE_ANALYTICS = os.getenv('ENABLE_ANALYTICS', 'true').lower() == 'true'
    ENABLE_SOCIAL_FEATURES = os.getenv('ENABLE_SOCIAL_FEATURES', 'true').lower() == 'true'
    ENABLE_NOTIFICATIONS = os.getenv('ENABLE_NOTIFICATIONS', 'true').lower() == 'true'
    ENABLE_GAMIFICATION = os.getenv('ENABLE_GAMIFICATION', 'true').lower() == 'true'
    ENABLE_ACHIEVEMENTS = os.getenv('ENABLE_ACHIEVEMENTS', 'true').lower() == 'true'
    ENABLE_FRIENDS_SYSTEM = os.getenv('ENABLE_FRIENDS_SYSTEM', 'true').lower() == 'true'
    ENABLE_REMINDERS = os.getenv('ENABLE_REMINDERS', 'true').lower() == 'true'
    ENABLE_TIMERS = os.getenv('ENABLE_TIMERS', 'true').lower() == 'true'
    ENABLE_THEMES = os.getenv('ENABLE_THEMES', 'true').lower() == 'true'
    ENABLE_EXPORT = os.getenv('ENABLE_EXPORT', 'true').lower() == 'true'
    ENABLE_AI_SUGGESTIONS = os.getenv('ENABLE_AI_SUGGESTIONS', 'true').lower() == 'true'
    ENABLE_CONVERSATION_HANDLERS = os.getenv('ENABLE_CONVERSATION_HANDLERS', 'true').lower() == 'true'
    
    # ===== ОГРАНИЧЕНИЯ =====
    RATE_LIMIT_MESSAGES = int(os.getenv('RATE_LIMIT_MESSAGES', 30))
    RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', 60))
    MAX_TASKS_PER_USER = int(os.getenv('MAX_TASKS_PER_USER', 100))
    MAX_FRIENDS_PER_USER = int(os.getenv('MAX_FRIENDS_PER_USER', 50))
    MAX_REMINDERS_PER_USER = int(os.getenv('MAX_REMINDERS_PER_USER', 20))
    MAX_DAILY_AI_REQUESTS = int(os.getenv('MAX_DAILY_AI_REQUESTS', 50))
    
    # ===== МОНИТОРИНГ =====
    HEALTH_CHECK_PORT = int(os.getenv('HEALTH_CHECK_PORT', 8082))
    METRICS_ENABLED = os.getenv('METRICS_ENABLED', 'true').lower() == 'true'
    PROMETHEUS_ENABLED = os.getenv('PROMETHEUS_ENABLED', 'false').lower() == 'true'
    SENTRY_DSN = os.getenv('SENTRY_DSN', '')
    
    # ===== ЛОКАЛИЗАЦИЯ =====
    DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'ru')
    SUPPORTED_LANGUAGES = os.getenv('SUPPORTED_LANGUAGES', 'ru,en').split(',')
    TIMEZONE = os.getenv('TIMEZONE', 'UTC')
    
    # ===== ИНТЕГРАЦИИ =====
    REDIS_URL = os.getenv('REDIS_URL', '')
    REDIS_ENABLED = bool(os.getenv('REDIS_URL', ''))
    TELEGRAM_API_SERVER = os.getenv('TELEGRAM_API_SERVER', 'https://api.telegram.org')
    
    # ===== РАЗРАБОТКА И ОТЛАДКА =====
    TESTING_MODE = os.getenv('TESTING_MODE', 'false').lower() == 'true'
    VERBOSE_LOGGING = os.getenv('VERBOSE_LOGGING', 'false').lower() == 'true'
    PROFILING_ENABLED = os.getenv('PROFILING_ENABLED', 'false').lower() == 'true'
    
    # ===== УВЕДОМЛЕНИЯ =====
    NOTIFICATION_CHANNELS = os.getenv('NOTIFICATION_CHANNELS', 'telegram').split(',')
    EMAIL_ENABLED = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
    EMAIL_SMTP_HOST = os.getenv('EMAIL_SMTP_HOST', '')
    EMAIL_SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', 587))
    EMAIL_USERNAME = os.getenv('EMAIL_USERNAME', '')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
    
    # ===== BACKUP И АРХИВАЦИЯ =====
    AUTO_BACKUP_ENABLED = os.getenv('AUTO_BACKUP_ENABLED', 'true').lower() == 'true'
    BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', 30))
    COMPRESSION_ENABLED = os.getenv('COMPRESSION_ENABLED', 'true').lower() == 'true'
    
    # ===== СИСТЕМНЫЕ ЛИМИТЫ =====
    MAX_MESSAGE_LENGTH = int(os.getenv('MAX_MESSAGE_LENGTH', 4096))
    MAX_CALLBACK_DATA_LENGTH = int(os.getenv('MAX_CALLBACK_DATA_LENGTH', 64))
    MAX_INLINE_KEYBOARD_BUTTONS = int(os.getenv('MAX_INLINE_KEYBOARD_BUTTONS', 100))
    
    # ===== AI КОНФИГУРАЦИЯ =====
    AI_TEMPERATURE = float(os.getenv('AI_TEMPERATURE', 0.7))
    AI_MAX_CONTEXT_LENGTH = int(os.getenv('AI_MAX_CONTEXT_LENGTH', 8000))
    AI_FALLBACK_ENABLED = os.getenv('AI_FALLBACK_ENABLED', 'true').lower() == 'true'
    AI_RATE_LIMIT_ENABLED = os.getenv('AI_RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    
    # ===== ГЕЙМИФИКАЦИЯ =====
    XP_MULTIPLIER = float(os.getenv('XP_MULTIPLIER', 1.0))
    LEVEL_XP_BASE = int(os.getenv('LEVEL_XP_BASE', 100))
    LEVEL_XP_MULTIPLIER = float(os.getenv('LEVEL_XP_MULTIPLIER', 1.5))
    ACHIEVEMENT_BONUS_XP = int(os.getenv('ACHIEVEMENT_BONUS_XP', 50))
    STREAK_BONUS_ENABLED = os.getenv('STREAK_BONUS_ENABLED', 'true').lower() == 'true'
    STREAK_BONUS_MULTIPLIER = float(os.getenv('STREAK_BONUS_MULTIPLIER', 0.1))
    
    # ===== СОЦИАЛЬНЫЕ ФУНКЦИИ =====
    FRIEND_REQUESTS_ENABLED = os.getenv('FRIEND_REQUESTS_ENABLED', 'true').lower() == 'true'
    LEADERBOARDS_ENABLED = os.getenv('LEADERBOARDS_ENABLED', 'true').lower() == 'true'
    SOCIAL_SHARING_ENABLED = os.getenv('SOCIAL_SHARING_ENABLED', 'true').lower() == 'true'
    
    # ===== ТАЙМЕРЫ И НАПОМИНАНИЯ =====
    POMODORO_DURATION = int(os.getenv('POMODORO_DURATION', 25))
    SHORT_BREAK_DURATION = int(os.getenv('SHORT_BREAK_DURATION', 5))
    LONG_BREAK_DURATION = int(os.getenv('LONG_BREAK_DURATION', 15))
    MAX_ACTIVE_TIMERS = int(os.getenv('MAX_ACTIVE_TIMERS', 5))
    
    # ===== ЭКСПОРТ ДАННЫХ =====
    EXPORT_FORMATS = os.getenv('EXPORT_FORMATS', 'json,csv').split(',')
    EXPORT_INCLUDE_HISTORY = os.getenv('EXPORT_INCLUDE_HISTORY', 'true').lower() == 'true'
    EXPORT_INCLUDE_ANALYTICS = os.getenv('EXPORT_INCLUDE_ANALYTICS', 'true').lower() == 'true'
    
    # Создаем директории
    @classmethod
    def ensure_directories(cls):
        """Создание необходимых директорий с полной проверкой"""
        directories = [
            cls.DATA_DIR,
            cls.EXPORT_DIR,
            cls.BACKUP_DIR,
            cls.LOG_DIR,
            cls.DATA_DIR / 'users',
            cls.DATA_DIR / 'tasks',
            cls.DATA_DIR / 'analytics',
            cls.BACKUP_DIR / 'daily',
            cls.BACKUP_DIR / 'weekly',
            cls.LOG_DIR / 'archives'
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"⚠️ Не удалось создать директорию {directory}: {e}")
    
    @classmethod
    def validate_configuration(cls) -> List[str]:
        """Полная валидация конфигурации"""
        errors = []
        warnings = []
        
        # Обязательные параметры
        if not cls.BOT_TOKEN:
            errors.append("❌ BOT_TOKEN не найден в переменных окружения!")
        elif len(cls.BOT_TOKEN) < 40:
            errors.append("❌ BOT_TOKEN слишком короткий - проверьте корректность токена")
        
        if cls.ADMIN_USER_ID == 0:
            warnings.append("⚠️ ADMIN_USER_ID не установлен - админские функции недоступны")
        
        # AI конфигурация
        if not cls.OPENAI_API_KEY and cls.AI_CHAT_ENABLED:
            warnings.append("⚠️ OPENAI_API_KEY не установлен - AI функции будут ограничены")
        
        if cls.OPENAI_API_KEY == cls.BOT_TOKEN:
            errors.append("❌ OPENAI_API_KEY не может совпадать с BOT_TOKEN")
        
        # Проверка портов
        if not (1024 <= cls.PORT <= 65535):
            errors.append(f"❌ Неверный PORT: {cls.PORT} (должен быть 1024-65535)")
        
        if not (1024 <= cls.WEB_PORT <= 65535):
            errors.append(f"❌ Неверный WEB_PORT: {cls.WEB_PORT} (должен быть 1024-65535)")
        
        if cls.PORT == cls.WEB_PORT:
            errors.append("❌ PORT и WEB_PORT не могут совпадать")
        
        # Проверка лимитов
        if cls.MAX_TASKS_PER_USER < 1:
            errors.append("❌ MAX_TASKS_PER_USER должен быть больше 0")
        
        if cls.RATE_LIMIT_MESSAGES < 1:
            errors.append("❌ RATE_LIMIT_MESSAGES должен быть больше 0")
        
        # Проверка AI параметров
        if not (0.0 <= cls.AI_TEMPERATURE <= 2.0):
            errors.append("❌ AI_TEMPERATURE должен быть между 0.0 и 2.0")
        
        if cls.OPENAI_MAX_TOKENS < 10:
            errors.append("❌ OPENAI_MAX_TOKENS слишком мал")
        
        # Вывод результатов
        for error in errors:
            print(error)
        
        for warning in warnings:
            print(warning)
        
        return errors
    
    @classmethod
    def get_feature_status(cls) -> Dict[str, bool]:
        """Получить статус всех функций"""
        return {
            'openai_available': OPENAI_AVAILABLE and bool(cls.OPENAI_API_KEY),
            'pandas_available': PANDAS_AVAILABLE,
            'psutil_available': PSUTIL_AVAILABLE,
            'scheduler_available': SCHEDULER_AVAILABLE,
            'redis_available': cls.REDIS_ENABLED,
            'web_dashboard': cls.ENABLE_WEB_DASHBOARD,
            'analytics': cls.ENABLE_ANALYTICS,
            'social_features': cls.ENABLE_SOCIAL_FEATURES,
            'gamification': cls.ENABLE_GAMIFICATION,
            'achievements': cls.ENABLE_ACHIEVEMENTS,
            'ai_chat': cls.AI_CHAT_ENABLED,
            'notifications': cls.ENABLE_NOTIFICATIONS,
            'reminders': cls.ENABLE_REMINDERS,
            'timers': cls.ENABLE_TIMERS,
            'themes': cls.ENABLE_THEMES,
            'export': cls.ENABLE_EXPORT,
            'friends_system': cls.ENABLE_FRIENDS_SYSTEM,
            'conversation_handlers': cls.ENABLE_CONVERSATION_HANDLERS
        }
    
    @classmethod
    def print_startup_info(cls):
        """Вывод информации о запуске"""
        print("🚀 DailyCheck Bot v4.0 - ПОЛНАЯ ВЕРСИЯ")
        print("=" * 50)
        print(f"✅ BOT_TOKEN: {cls.BOT_TOKEN[:10]}..." if cls.BOT_TOKEN else "❌ BOT_TOKEN не найден")
        print(f"✅ OpenAI: {cls.OPENAI_API_KEY[:10] if cls.OPENAI_API_KEY else 'не настроен'}...")
        print(f"🔧 Порт бота: {cls.PORT}")
        print(f"🌐 Порт веб-дашборда: {cls.WEB_PORT}")
        print(f"🤖 AI чат: {'включен' if cls.AI_CHAT_ENABLED else 'выключен'}")
        print(f"📊 Аналитика: {'включена' if cls.ENABLE_ANALYTICS else 'выключена'}")
        print(f"👥 Социальные функции: {'включены' if cls.ENABLE_SOCIAL_FEATURES else 'выключены'}")
        print(f"🎮 Геймификация: {'включена' if cls.ENABLE_GAMIFICATION else 'выключена'}")
        print(f"📝 Макс. задач на пользователя: {cls.MAX_TASKS_PER_USER}")
        print(f"⚡ Лимит сообщений: {cls.RATE_LIMIT_MESSAGES}/{cls.RATE_LIMIT_WINDOW}с")
        print(f"🗂️ Директория данных: {cls.DATA_DIR}")
        print(f"📈 Режим отладки: {'включен' if cls.DEBUG_MODE else 'выключен'}")
        
        # Статус библиотек
        print("\n📚 Статус библиотек:")
        print(f"   OpenAI: {'✅' if OPENAI_AVAILABLE else '❌'}")
        print(f"   Pandas: {'✅' if PANDAS_AVAILABLE else '❌'}")
        print(f"   Psutil: {'✅' if PSUTIL_AVAILABLE else '❌'}")
        print(f"   Scheduler: {'✅' if SCHEDULER_AVAILABLE else '❌'}")
        
        print("=" * 50)

# Проверка окружения
class Environment:
    """Определение окружения запуска"""
    
    @staticmethod
    def is_render() -> bool:
        return bool(os.getenv('RENDER'))
    
    @staticmethod
    def is_heroku() -> bool:
        return bool(os.getenv('DYNO'))
    
    @staticmethod
    def is_docker() -> bool:
        return bool(os.getenv('DOCKER_CONTAINER')) or Path('/.dockerenv').exists()
    
    @staticmethod
    def is_railway() -> bool:
        return bool(os.getenv('RAILWAY_ENVIRONMENT'))
    
    @staticmethod
    def is_github_actions() -> bool:
        return bool(os.getenv('GITHUB_ACTIONS'))
    
    @staticmethod
    def get_platform() -> str:
        if Environment.is_render():
            return "render"
        elif Environment.is_heroku():
            return "heroku"
        elif Environment.is_docker():
            return "docker"
        elif Environment.is_railway():
            return "railway"
        elif Environment.is_github_actions():
            return "github_actions"
        else:
            return "local"
    
    @staticmethod
    def is_production() -> bool:
        env = os.getenv('ENVIRONMENT', '').lower()
        return env in ['production', 'prod'] or Environment.is_render() or Environment.is_heroku()
    
    @staticmethod
    def is_development() -> bool:
        return not Environment.is_production()

def setup_logging():
    """Настройка продвинутой системы логирования с сохранением всех настроек"""
    BotConfig.ensure_directories()
    
    # Настройка форматтера
    detailed_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Основной логгер
    logger = logging.getLogger('dailycheck')
    
    # Устанавливаем уровень логирования
    if BotConfig.DEBUG_MODE or BotConfig.VERBOSE_LOGGING:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(getattr(logging, BotConfig.LOG_LEVEL))
    
    # Очищаем существующие обработчики
    logger.handlers.clear()
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(detailed_formatter if BotConfig.DEBUG_MODE else simple_formatter)
    logger.addHandler(console_handler)
    
    # Файловый обработчик с ротацией
    try:
        log_file = BotConfig.LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"⚠️ Не удалось настроить файловое логирование: {e}")
    
    # Обработчик ошибок
    if BotConfig.LOG_LEVEL == 'DEBUG':
        error_file = BotConfig.LOG_DIR / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)
    
    # Настройка уровней для внешних библиотек
    external_loggers = {
        "httpx": logging.WARNING,
        "telegram": logging.WARNING,
        "urllib3": logging.WARNING,
        "openai": logging.WARNING,
        "aiohttp": logging.WARNING,
        "asyncio": logging.WARNING
    }
    
    for logger_name, level in external_loggers.items():
        logging.getLogger(logger_name).setLevel(level)
    
    return logger

# Экспорт основных компонентов
__all__ = [
    'BotConfig',
    'Environment', 
    'setup_logging',
    'OPENAI_AVAILABLE',
    'PANDAS_AVAILABLE', 
    'PSUTIL_AVAILABLE',
    'SCHEDULER_AVAILABLE'
]
