#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Bot v4.0 - Enhanced Configuration
Централизованная конфигурация с валидацией

Автор: AI Assistant
Версия: 4.0.1
Дата: 2025-06-12
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

class Environment(Enum):
    """Среды выполнения"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(Enum):
    """Уровни логирования"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

@dataclass
class DatabaseConfig:
    """Конфигурация базы данных"""
    path: Path
    backup_dir: Path
    backup_interval_hours: int = 6
    max_backups: int = 10
    auto_backup: bool = True

@dataclass
class AIConfig:
    """Конфигурация AI сервисов"""
    openai_api_key: Optional[str]
    openai_model: str = "gpt-3.5-turbo"
    openai_max_tokens: int = 1000
    ai_chat_enabled: bool = False  # По умолчанию выключен
    fallback_enabled: bool = True
    request_timeout: int = 30

@dataclass
class TelegramConfig:
    """Конфигурация Telegram бота"""
    bot_token: str
    admin_user_id: int
    webhook_url: Optional[str] = None
    use_webhook: bool = False
    max_connections: int = 40
    allowed_updates: list = None

@dataclass
class ServerConfig:
    """Конфигурация сервера"""
    host: str = "0.0.0.0"
    port: int = 8080
    debug_mode: bool = False
    health_check_enabled: bool = True

@dataclass
class IntegrationsConfig:
    """Конфигурация интеграций"""
    google_sheet_id: Optional[str] = None
    google_credentials_file: Optional[str] = None
    google_enabled: bool = False

@dataclass
class SecurityConfig:
    """Конфигурация безопасности"""
    secret_key: str
    rate_limit_per_minute: int = 30
    max_users_cache: int = 1000
    session_timeout_hours: int = 24

class BotConfig:
    """Главный класс конфигурации"""
    
    def __init__(self):
        self.environment = Environment(os.getenv('ENVIRONMENT', 'development'))
        self._load_config()
        self._validate_config()
        self._ensure_directories()
    
    def _load_config(self):
        """Загрузка конфигурации из переменных окружения"""
        
        # Обязательные параметры
        self.telegram = TelegramConfig(
            bot_token=self._get_required_env('BOT_TOKEN'),
            admin_user_id=int(self._get_required_env('ADMIN_USER_ID')),
            webhook_url=os.getenv('WEBHOOK_URL'),
            use_webhook=os.getenv('USE_WEBHOOK', 'false').lower() == 'true',
            allowed_updates=['message', 'callback_query', 'inline_query']
        )
        
        # Директории
        self.data_dir = Path(os.getenv('DATA_DIR', 'data'))
        self.export_dir = Path(os.getenv('EXPORT_DIR', 'exports'))
        self.backup_dir = Path(os.getenv('BACKUP_DIR', 'backups'))
        self.log_dir = Path(os.getenv('LOG_DIR', 'logs'))
        
        # База данных
        self.database = DatabaseConfig(
            path=self.data_dir / "users_data.json",
            backup_dir=self.backup_dir,
            backup_interval_hours=int(os.getenv('BACKUP_INTERVAL_HOURS', 6)),
            max_backups=int(os.getenv('MAX_BACKUPS', 10)),
            auto_backup=os.getenv('AUTO_BACKUP', 'true').lower() == 'true'
        )
        
        # AI конфигурация
        openai_key = os.getenv('OPENAI_API_KEY')
        self.ai = AIConfig(
            openai_api_key=openai_key if openai_key and openai_key != self.telegram.bot_token else None,
            openai_model=os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo'),
            openai_max_tokens=int(os.getenv('OPENAI_MAX_TOKENS', 1000)),
            ai_chat_enabled=os.getenv('AI_CHAT_ENABLED', 'false').lower() == 'true',
            request_timeout=int(os.getenv('AI_TIMEOUT', 30))
        )
        
        # Сервер
        self.server = ServerConfig(
            host=os.getenv('HOST', '0.0.0.0'),
            port=int(os.getenv('PORT', 8080)),
            debug_mode=os.getenv('DEBUG_MODE', 'false').lower() == 'true',
            health_check_enabled=os.getenv('HEALTH_CHECK', 'true').lower() == 'true'
        )
        
        # Интеграции
        self.integrations = IntegrationsConfig(
            google_sheet_id=os.getenv('GOOGLE_SHEET_ID'),
            google_credentials_file=os.getenv('GOOGLE_CREDENTIALS_FILE', 'service_account.json'),
            google_enabled=bool(os.getenv('GOOGLE_SHEET_ID'))
        )
        
        # Безопасность
        self.security = SecurityConfig(
            secret_key=os.getenv('SECRET_KEY', 'dailycheck-bot-secret-key-2025'),
            rate_limit_per_minute=int(os.getenv('RATE_LIMIT', 30)),
            max_users_cache=int(os.getenv('MAX_USERS_CACHE', 1000)),
            session_timeout_hours=int(os.getenv('SESSION_TIMEOUT', 24))
        )
        
        # Логирование
        self.log_level = LogLevel(os.getenv('LOG_LEVEL', 'INFO'))
        self.log_to_file = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
        self.log_format = os.getenv(
            'LOG_FORMAT',
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        
        # Производительность
        self.max_workers = int(os.getenv('MAX_WORKERS', 4))
        self.cache_ttl_seconds = int(os.getenv('CACHE_TTL', 3600))
        
        # Функциональность
        self.features = {
            'ai_enabled': bool(self.ai.openai_api_key),
            'google_sheets': self.integrations.google_enabled,
            'analytics': os.getenv('ANALYTICS_ENABLED', 'true').lower() == 'true',
            'export': os.getenv('EXPORT_ENABLED', 'true').lower() == 'true',
            'social': os.getenv('SOCIAL_ENABLED', 'true').lower() == 'true',
            'gamification': os.getenv('GAMIFICATION_ENABLED', 'true').lower() == 'true',
            'notifications': os.getenv('NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
        }
    
    def _get_required_env(self, key: str) -> str:
        """Получение обязательной переменной окружения"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Обязательная переменная окружения {key} не найдена!")
        return value
    
    def _validate_config(self):
        """Валидация конфигурации"""
        errors = []
        
        # Проверка токена
        if not self.telegram.bot_token.startswith(('bot', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
            errors.append("BOT_TOKEN имеет неверный формат")
        
        # Проверка AI ключа
        if self.ai.openai_api_key:
            if self.ai.openai_api_key == self.telegram.bot_token:
                self.ai.openai_api_key = None
                self.ai.ai_chat_enabled = False
                logging.warning("⚠️ OPENAI_API_KEY совпадает с BOT_TOKEN - AI функции отключены")
        
        # Проверка портов
        if not 1024 <= self.server.port <= 65535:
            errors.append(f"Порт {self.server.port} вне допустимого диапазона (1024-65535)")
        
        # Проверка ID администратора
        if self.telegram.admin_user_id <= 0:
            errors.append("ADMIN_USER_ID должен быть положительным числом")
        
        if errors:
            raise ValueError("Ошибки конфигурации:\n" + "\n".join(f"• {error}" for error in errors))
    
    def _ensure_directories(self):
        """Создание необходимых директорий"""
        directories = [
            self.data_dir,
            self.export_dir,
            self.backup_dir,
            self.log_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Получение конфигурации логирования"""
        handlers = ['console']
        if self.log_to_file:
            handlers.append('file')
        
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    'format': self.log_format,
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': self.log_level.value,
                    'formatter': 'default',
                    'stream': sys.stdout
                },
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': self.log_level.value,
                    'formatter': 'default',
                    'filename': self.log_dir / f"bot_{self.environment.value}.log",
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 5,
                    'encoding': 'utf-8'
                }
            },
            'loggers': {
                '': {
                    'level': self.log_level.value,
                    'handlers': handlers,
                    'propagate': False
                },
                'httpx': {
                    'level': 'WARNING',
                    'handlers': handlers,
                    'propagate': False
                },
                'telegram': {
                    'level': 'WARNING',
                    'handlers': handlers,
                    'propagate': False
                },
                'urllib3': {
                    'level': 'WARNING',
                    'handlers': handlers,
                    'propagate': False
                }
            }
        }
    
    def is_development(self) -> bool:
        """Проверка режима разработки"""
        return self.environment == Environment.DEVELOPMENT
    
    def is_production(self) -> bool:
        """Проверка продакшн режима"""
        return self.environment == Environment.PRODUCTION
    
    def get_database_url(self) -> str:
        """Получение URL базы данных"""
        return f"file://{self.database.path.absolute()}"
    
    def get_feature_status(self) -> Dict[str, bool]:
        """Получение статуса функций"""
        return self.features.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация конфигурации в словарь"""
        return {
            'environment': self.environment.value,
            'telegram': {
                'bot_token': self.telegram.bot_token[:10] + "...",  # Скрываем токен
                'admin_user_id': self.telegram.admin_user_id,
                'use_webhook': self.telegram.use_webhook
            },
            'server': {
                'host': self.server.host,
                'port': self.server.port,
                'debug_mode': self.server.debug_mode
            },
            'features': self.features,
            'ai_enabled': bool(self.ai.openai_api_key),
            'database_path': str(self.database.path),
            'log_level': self.log_level.value
        }

# Глобальный экземпляр конфигурации
config = BotConfig()

# Для обратной совместимости
class BotConfigCompat:
    """Класс совместимости с оригинальной конфигурацией"""
    
    @property
    def BOT_TOKEN(self):
        return config.telegram.bot_token
    
    @property
    def OPENAI_API_KEY(self):
        return config.ai.openai_api_key
    
    @property
    def ADMIN_USER_ID(self):
        return config.telegram.admin_user_id
    
    @property
    def PORT(self):
        return config.server.port
    
    @property
    def HOST(self):
        return config.server.host
    
    @property
    def WEBHOOK_URL(self):
        return config.telegram.webhook_url
    
    @property
    def DATA_DIR(self):
        return config.data_dir
    
    @property
    def EXPORT_DIR(self):
        return config.export_dir
    
    @property
    def BACKUP_DIR(self):
        return config.backup_dir
    
    @property
    def LOG_DIR(self):
        return config.log_dir
    
    @property
    def OPENAI_MODEL(self):
        return config.ai.openai_model
    
    @property
    def OPENAI_MAX_TOKENS(self):
        return config.ai.openai_max_tokens
    
    @property
    def AI_CHAT_ENABLED(self):
        return config.ai.ai_chat_enabled
    
    @property
    def GOOGLE_SHEET_ID(self):
        return config.integrations.google_sheet_id
    
    @property
    def GOOGLE_CREDENTIALS_FILE(self):
        return config.integrations.google_credentials_file
    
    @property
    def MAX_USERS_CACHE(self):
        return config.security.max_users_cache
    
    @property
    def BACKUP_INTERVAL_HOURS(self):
        return config.database.backup_interval_hours
    
    @property
    def LOG_LEVEL(self):
        return config.log_level.value
    
    @property
    def DEBUG_MODE(self):
        return config.server.debug_mode
    
    @classmethod
    def ensure_directories(cls):
        """Создание необходимых директорий"""
        config._ensure_directories()

# Создаем экземпляр для обратной совместимости
BotConfig = BotConfigCompat()

# Экспорт для использования в других модулях
__all__ = [
    'config',
    'BotConfig',
    'Environment',
    'LogLevel',
    'DatabaseConfig',
    'AIConfig',
    'TelegramConfig',
    'ServerConfig',
    'IntegrationsConfig',
    'SecurityConfig'
]
