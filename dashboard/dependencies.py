#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailycheckBot2025 - Dashboard Dependencies
Зависимости, middleware и провайдеры для FastAPI приложения

Автор: AI Assistant
Версия: 1.0.0
Дата: 2025-06-10
"""

import asyncio
import time
import logging
import os
import sys
import hashlib
import json
import secrets
from typing import Optional, Dict, Any, Generator, AsyncGenerator, List, Union
from functools import lru_cache, wraps
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

# Настройка логирования
logger = logging.getLogger(__name__)

# Попытка импорта Redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
    RedisType = redis.Redis
except ImportError:
    REDIS_AVAILABLE = False
    RedisType = type(None)  # Используем type(None) вместо None для типизации
    redis = None
    logger.warning("⚠️ Redis не доступен, используем in-memory кэш")

# Попытка импорта SQLAlchemy
try:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from sqlalchemy.orm import sessionmaker
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    AsyncSession = type(None)  # Используем type(None) для типизации
    logger.warning("⚠️ SQLAlchemy не доступен, база данных отключена")

from fastapi import Depends, HTTPException, Request, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Попытка импорта собственных модулей
try:
    from dashboard.config import settings
except ImportError:
    # Создаем базовые настройки
    class Settings:
        DATA_DIR = Path('./data')
        REDIS_URL = os.getenv('REDIS_URL')
        DATABASE_URL = os.getenv('DATABASE_URL')
        TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        ADMIN_USER_IDS = [int(x) for x in os.getenv('ADMIN_USER_IDS', '').split(',') if x.strip()]
        CACHE_ENABLED = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'
        CACHE_TTL = int(os.getenv('CACHE_TTL', '300'))
        API_RATE_LIMIT = os.getenv('API_RATE_LIMIT', '100/minute')
        DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))
        DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '20'))
        DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
        ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
        SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))
    
    settings = Settings()

# Попытка импорта core модулей
try:
    from dashboard.core.data_manager import DataManager
except ImportError:
    # Заглушка для DataManager
    class DataManager:
        def __init__(self, data_dir):
            self.data_dir = Path(data_dir)
            self.data_dir.mkdir(exist_ok=True)
        
        async def initialize(self):
            pass
        
        async def cleanup(self):
            pass
        
        async def get_users_count(self):
            return 0
        
        async def get_tasks_count(self):
            return 0

try:
    from dashboard.core.statistics import StatisticsCalculator
except ImportError:
    class StatisticsCalculator:
        def __init__(self, data_manager):
            self.data_manager = data_manager
        
        async def initialize(self):
            pass
        
        async def cleanup(self):
            pass

try:
    from dashboard.core.analytics import AnalyticsEngine
except ImportError:
    class AnalyticsEngine:
        def __init__(self, data_manager, stats_calculator):
            self.data_manager = data_manager
            self.stats_calculator = stats_calculator
        
        async def initialize(self):
            pass
        
        async def cleanup(self):
            pass

logger = logging.getLogger(__name__)

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====

# Синглтоны компонентов
_data_manager: Optional[DataManager] = None
_statistics_calculator: Optional[StatisticsCalculator] = None
_analytics_engine: Optional[AnalyticsEngine] = None
_redis_client: Optional[RedisType] = None
_db_engine = None
_db_session_factory = None

# Состояние инициализации
_initialized = False
_initialization_lock = asyncio.Lock()

# ===== ИНИЦИАЛИЗАЦИЯ КОМПОНЕНТОВ =====

async def ensure_initialized():
    """Гарантирует, что все компоненты инициализированы"""
    global _initialized
    
    if _initialized:
        return
    
    async with _initialization_lock:
        if _initialized:
            return
        
        logger.info("🔄 Инициализация компонентов dashboard...")
        
        # Инициализируем компоненты по порядку
        await init_data_manager()
        await init_redis()
        await init_database()
        await init_statistics_calculator()
        await init_analytics_engine()
        
        _initialized = True
        logger.info("✅ Компоненты dashboard инициализированы")

async def init_data_manager() -> DataManager:
    """Инициализация менеджера данных"""
    global _data_manager
    
    if _data_manager is None:
        logger.info("🔄 Инициализация DataManager...")
        try:
            _data_manager = DataManager(settings.DATA_DIR)
            await _data_manager.initialize()
            logger.info("✅ DataManager инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации DataManager: {e}")
            raise
    
    return _data_manager

async def init_statistics_calculator() -> StatisticsCalculator:
    """Инициализация калькулятора статистики"""
    global _statistics_calculator
    
    if _statistics_calculator is None:
        logger.info("🔄 Инициализация StatisticsCalculator...")
        try:
            data_manager = await get_data_manager()
            _statistics_calculator = StatisticsCalculator(data_manager)
            await _statistics_calculator.initialize()
            logger.info("✅ StatisticsCalculator инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации StatisticsCalculator: {e}")
            raise
    
    return _statistics_calculator

async def init_analytics_engine() -> AnalyticsEngine:
    """Инициализация аналитического движка"""
    global _analytics_engine
    
    if _analytics_engine is None:
        logger.info("🔄 Инициализация AnalyticsEngine...")
        try:
            data_manager = await get_data_manager()
            stats_calculator = await get_statistics_calculator()
            _analytics_engine = AnalyticsEngine(data_manager, stats_calculator)
            await _analytics_engine.initialize()
            logger.info("✅ AnalyticsEngine инициализирован")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации AnalyticsEngine: {e}")
            raise
    
    return _analytics_engine

async def init_redis() -> Optional[RedisType]:
    """Инициализация Redis для кэширования"""
    global _redis_client
    
    if not REDIS_AVAILABLE or not settings.REDIS_URL:
        return None
    
    if _redis_client is None:
        try:
            logger.info("🔄 Подключение к Redis...")
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Проверяем соединение
            await _redis_client.ping()
            logger.info("✅ Redis подключен")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось подключиться к Redis: {e}")
            _redis_client = None
    
    return _redis_client

async def init_database() -> Optional[AsyncSession]:
    """Инициализация базы данных (опционально)"""
    global _db_engine, _db_session_factory
    
    if not SQLALCHEMY_AVAILABLE or not settings.DATABASE_URL:
        return None
    
    if _db_engine is None:
        try:
            logger.info("🔄 Инициализация базы данных...")
            
            _db_engine = create_async_engine(
                settings.DATABASE_URL,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                echo=settings.DEBUG,
                future=True
            )
            
            _db_session_factory = async_sessionmaker(
                _db_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info("✅ База данных инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            _db_engine = None
            _db_session_factory = None
    
    return _db_session_factory

# ===== ПРОВАЙДЕРЫ ЗАВИСИМОСТЕЙ =====

async def get_data_manager() -> DataManager:
    """Получить экземпляр DataManager"""
    await ensure_initialized()
    if _data_manager is None:
        raise HTTPException(
            status_code=503,
            detail="DataManager не инициализирован"
        )
    return _data_manager

async def get_statistics_calculator() -> StatisticsCalculator:
    """Получить экземпляр StatisticsCalculator"""
    await ensure_initialized()
    if _statistics_calculator is None:
        raise HTTPException(
            status_code=503,
            detail="StatisticsCalculator не инициализирован"
        )
    return _statistics_calculator

async def get_analytics_engine() -> AnalyticsEngine:
    """Получить экземпляр AnalyticsEngine"""
    await ensure_initialized()
    if _analytics_engine is None:
        raise HTTPException(
            status_code=503,
            detail="AnalyticsEngine не инициализирован"
        )
    return _analytics_engine

async def get_redis() -> Optional[RedisType]:
    """Получить Redis клиент"""
    await ensure_initialized()
    return _redis_client

async def get_db_session():
    """Получить сессию базы данных"""
    await ensure_initialized()
    
    if not _db_session_factory:
        yield None
        return
    
    async with _db_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# ===== КЭШИРОВАНИЕ =====

class InMemoryCache:
    """Простой кэш в памяти"""
    
    def __init__(self, default_ttl: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        if key not in self.cache:
            return None
        
        item = self.cache[key]
        if time.time() - item['timestamp'] > item['ttl']:
            del self.cache[key]
            return None
        
        return item['data']
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Сохранить значение в кэш"""
        self.cache[key] = {
            'data': value,
            'timestamp': time.time(),
            'ttl': ttl or self.default_ttl
        }
    
    async def delete(self, key: str) -> None:
        """Удалить значение из кэша"""
        if key in self.cache:
            del self.cache[key]
    
    async def clear(self) -> None:
        """Очистить весь кэш"""
        self.cache.clear()
    
    async def cleanup(self) -> None:
        """Очистка устаревших записей"""
        current_time = time.time()
        expired_keys = [
            key for key, item in self.cache.items()
            if current_time - item['timestamp'] > item['ttl']
        ]
        
        for key in expired_keys:
            del self.cache[key]

class CacheManager:
    """Менеджер кэширования данных"""
    
    def __init__(self, redis_client: Optional[RedisType] = None):
        self.redis = redis_client
        self.memory_cache = InMemoryCache(settings.CACHE_TTL)
        self.cache_ttl = settings.CACHE_TTL
        self.enabled = settings.CACHE_ENABLED
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        if not self.enabled:
            return None
        
        # Сначала пробуем Redis
        if self.redis:
            try:
                value = await self.redis.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Ошибка чтения из Redis: {e}")
        
        # Fallback на память
        return await self.memory_cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Сохранить значение в кэш"""
        if not self.enabled:
            return
        
        ttl = ttl or self.cache_ttl
        
        # Сохраняем в Redis
        if self.redis:
            try:
                serialized_value = json.dumps(value, default=str, ensure_ascii=False)
                await self.redis.setex(key, ttl, serialized_value)
            except Exception as e:
                logger.warning(f"Ошибка записи в Redis: {e}")
        
        # Сохраняем в память
        await self.memory_cache.set(key, value, ttl)
    
    async def delete(self, key: str) -> None:
        """Удалить значение из кэша"""
        if self.redis:
            try:
                await self.redis.delete(key)
            except Exception as e:
                logger.warning(f"Ошибка удаления из Redis: {e}")
        
        await self.memory_cache.delete(key)
    
    async def clear(self) -> None:
        """Очистить весь кэш"""
        if self.redis:
            try:
                await self.redis.flushdb()
            except Exception as e:
                logger.warning(f"Ошибка очистки Redis: {e}")
        
        await self.memory_cache.clear()
    
    async def cleanup(self) -> None:
        """Периодическая очистка кэша"""
        await self.memory_cache.cleanup()
    
    def cache_key(self, *args, **kwargs) -> str:
        """Генерация ключа кэша"""
        key_data = {
            'args': args,
            'kwargs': kwargs,
            'timestamp': int(time.time() / 60)  # Обновляем каждую минуту
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()

# Глобальный кэш менеджер
_cache_manager: Optional[CacheManager] = None

async def get_cache_manager() -> CacheManager:
    """Получить менеджер кэширования"""
    global _cache_manager
    
    if _cache_manager is None:
        redis_client = await get_redis()
        _cache_manager = CacheManager(redis_client)
    
    return _cache_manager

def cached(ttl: int = 300, key_prefix: str = ""):
    """Декоратор для кэширования результатов функций"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = await get_cache_manager()
            
            # Генерируем ключ кэша
            cache_key = f"{key_prefix}:{func.__name__}:{cache.cache_key(*args, **kwargs)}"
            
            # Пробуем получить из кэша
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Выполняем функцию и кэшируем результат
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator

# ===== АВТОРИЗАЦИЯ =====

security = HTTPBearer(auto_error=False)

class TelegramAuth:
    """Авторизация через Telegram Web App"""
    
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.admin_ids = settings.ADMIN_USER_IDS
        self.secret_key = settings.SECRET_KEY
    
    def verify_telegram_hash(self, init_data: str) -> bool:
        """Проверка подписи данных Telegram Web App"""
        if not self.bot_token:
            return False
        
        try:
            import hmac
            
            # Парсим данные
            data_dict = {}
            for item in init_data.split('&'):
                key, value = item.split('=', 1)
                data_dict[key] = value
            
            # Извлекаем hash
            received_hash = data_dict.pop('hash', '')
            
            # Создаем строку для проверки
            check_string = '&'.join([f"{k}={v}" for k, v in sorted(data_dict.items())])
            
            # Вычисляем hash
            secret_key = hmac.new(
                "WebAppData".encode(),
                self.bot_token.encode(),
                hashlib.sha256
            ).digest()
            
            calculated_hash = hmac.new(
                secret_key,
                check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return calculated_hash == received_hash
            
        except Exception as e:
            logger.error(f"Ошибка проверки Telegram hash: {e}")
            return False
    
    async def verify_telegram_data(self, init_data: str) -> Optional[Dict[str, Any]]:
        """Проверка данных Telegram Web App"""
        if not self.verify_telegram_hash(init_data):
            return None
        
        try:
            # Парсим данные пользователя
            data_dict = {}
            for item in init_data.split('&'):
                key, value = item.split('=', 1)
                data_dict[key] = value
            
            user_data = json.loads(data_dict.get('user', '{}'))
            
            return {
                'user_id': user_data.get('id'),
                'username': user_data.get('username'),
                'first_name': user_data.get('first_name'),
                'last_name': user_data.get('last_name'),
                'is_admin': user_data.get('id') in self.admin_ids
            }
            
        except Exception as e:
            logger.error(f"Ошибка парсинга Telegram данных: {e}")
            return None
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка прав администратора"""
        return user_id in self.admin_ids
    
    def create_session_token(self, user_data: Dict[str, Any]) -> str:
        """Создание токена сессии"""
        import jwt
        
        payload = {
            'user_id': user_data['user_id'],
            'username': user_data.get('username'),
            'is_admin': user_data.get('is_admin', False),
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow()
        }
        
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def verify_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Проверка токена сессии"""
        try:
            import jwt
            
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
            
        except Exception as e:
            logger.error(f"Ошибка проверки токена: {e}")
            return None

telegram_auth = TelegramAuth()

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """Получить текущего пользователя"""
    if not credentials:
        return None
    
    token = credentials.credentials
    
    # Проверяем токен сессии
    user_data = telegram_auth.verify_session_token(token)
    if user_data:
        return user_data
    
    # Проверяем Telegram данные
    user_data = await telegram_auth.verify_telegram_data(token)
    return user_data

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """Получить пользователя (опционально)"""
    try:
        return await get_current_user(credentials)
    except:
        return None

async def require_auth(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Требовать авторизации"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user

async def require_admin(
    current_user: Dict[str, Any] = Depends(require_auth)
) -> Dict[str, Any]:
    """Требовать права администратора"""
    if not current_user.get('is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора"
        )
    return current_user

# ===== RATE LIMITING =====

class RateLimiter:
    """Rate limiter с поддержкой Redis и памяти"""
    
    def __init__(self, redis_client: Optional[RedisType] = None):
        self.redis = redis_client
        self.memory_store: Dict[str, List[float]] = {}
        self.limits = self._parse_limit(settings.API_RATE_LIMIT)
    
    def _parse_limit(self, limit_str: str) -> Dict[str, int]:
        """Парсинг строки лимита"""
        try:
            count, period = limit_str.split('/')
            period_seconds = {
                'second': 1,
                'minute': 60,
                'hour': 3600,
                'day': 86400
            }.get(period, 60)
            
            return {'count': int(count), 'period': period_seconds}
        except Exception:
            return {'count': 100, 'period': 60}
    
    async def is_allowed(self, client_id: str, limit_override: Optional[Dict[str, int]] = None) -> bool:
        """Проверка лимита запросов"""
        limits = limit_override or self.limits
        current_time = time.time()
        
        # Пробуем Redis
        if self.redis:
            try:
                return await self._check_redis_limit(client_id, current_time, limits)
            except Exception as e:
                logger.warning(f"Ошибка проверки лимита в Redis: {e}")
        
        # Fallback на память
        return await self._check_memory_limit(client_id, current_time, limits)
    
    async def _check_redis_limit(self, client_id: str, current_time: float, limits: Dict[str, int]) -> bool:
        """Проверка лимита в Redis"""
        key = f"rate_limit:{client_id}"
        
        # Используем sliding window
        await self.redis.zremrangebyscore(key, 0, current_time - limits['period'])
        
        current_count = await self.redis.zcard(key)
        
        if current_count >= limits['count']:
            return False
        
        # Добавляем текущий запрос
        await self.redis.zadd(key, {str(current_time): current_time})
        await self.redis.expire(key, limits['period'])
        
        return True
    
    async def _check_memory_limit(self, client_id: str, current_time: float, limits: Dict[str, int]) -> bool:
        """Проверка лимита в памяти"""
        if client_id not in self.memory_store:
            self.memory_store[client_id] = []
        
        # Удаляем старые записи
        cutoff_time = current_time - limits['period']
        self.memory_store[client_id] = [
            req_time for req_time in self.memory_store[client_id]
            if req_time > cutoff_time
        ]
        
        # Проверяем лимит
        if len(self.memory_store[client_id]) >= limits['count']:
            return False
        
        # Добавляем текущий запрос
        self.memory_store[client_id].append(current_time)
        return True
    
    async def get_remaining(self, client_id: str) -> int:
        """Получить оставшееся количество запросов"""
        current_time = time.time()
        
        if self.redis:
            try:
                key = f"rate_limit:{client_id}"
                await self.redis.zremrangebyscore(key, 0, current_time - self.limits['period'])
                current_count = await self.redis.zcard(key)
                return max(0, self.limits['count'] - current_count)
            except Exception:
                pass
        
        # Fallback на память
        if client_id in self.memory_store:
            cutoff_time = current_time - self.limits['period']
            current_requests = [
                req_time for req_time in self.memory_store[client_id]
                if req_time > cutoff_time
            ]
            return max(0, self.limits['count'] - len(current_requests))
        
        return self.limits['count']

# Глобальный rate limiter
_rate_limiter: Optional[RateLimiter] = None

async def get_rate_limiter() -> RateLimiter:
    """Получить rate limiter"""
    global _rate_limiter
    
    if _rate_limiter is None:
        redis_client = await get_redis()
        _rate_limiter = RateLimiter(redis_client)
    
    return _rate_limiter

async def check_rate_limit(
    request: Request,
    rate_limiter: RateLimiter = Depends(get_rate_limiter)
) -> None:
    """Middleware для проверки rate limit"""
    client_ip = get_client_ip(request)
    
    if not await rate_limiter.is_allowed(client_ip):
        remaining = await rate_limiter.get_remaining(client_ip)
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Превышен лимит запросов",
            headers={
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(time.time() + 60)),
                "Retry-After": "60"
            }
        )

# ===== МОНИТОРИНГ И МЕТРИКИ =====

class MetricsCollector:
    """Сборщик метрик приложения"""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            'requests_total': 0,
            'requests_by_endpoint': {},
            'requests_by_method': {},
            'response_times': [],
            'errors_total': 0,
            'errors_by_status': {},
            'cache_hits': 0,
            'cache_misses': 0,
            'active_connections': 0,
            'db_queries': 0
        }
        self.start_time = time.time()
        self._lock = asyncio.Lock()
    
    async def record_request(self, method: str, endpoint: str, response_time: float, status_code: int):
        """Записать метрику запроса"""
        async with self._lock:
            self.metrics['requests_total'] += 1
            
            # По endpoint
            if endpoint not in self.metrics['requests_by_endpoint']:
                self.metrics['requests_by_endpoint'][endpoint] = 0
            self.metrics['requests_by_endpoint'][endpoint] += 1
            
            # По методу
            if method not in self.metrics['requests_by_method']:
                self.metrics['requests_by_method'][method] = 0
            self.metrics['requests_by_method'][method] += 1
            
            # Время ответа
            self.metrics['response_times'].append(response_time)
            
            # Ошибки
            if status_code >= 400:
                self.metrics['errors_total'] += 1
                if status_code not in self.metrics['errors_by_status']:
                    self.metrics['errors_by_status'][status_code] = 0
                self.metrics['errors_by_status'][status_code] += 1
            
            # Ограничиваем количество времен ответа
            if len(self.metrics['response_times']) > 1000:
                self.metrics['response_times'] = self.metrics['response_times'][-1000:]
    
    async def record_cache_hit(self):
        """Записать попадание в кэш"""
        async with self._lock:
            self.metrics['cache_hits'] += 1
    
    async def record_cache_miss(self):
        """Записать промах кэша"""
        async with self._lock:
            self.metrics['cache_misses'] += 1
    
    async def record_db_query(self):
        """Записать запрос к БД"""
        async with self._lock:
            self.metrics['db_queries'] += 1
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Получить все метрики"""
        async with self._lock:
            uptime = time.time() - self.start_time
            
            # Статистика времени ответа
            response_times = self.metrics['response_times']
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            # Статистика кэша
            total_cache_requests = self.metrics['cache_hits'] + self.metrics['cache_misses']
            cache_hit_rate = (
                self.metrics['cache_hits'] / total_cache_requests
                if total_cache_requests > 0 else 0
            )
            
            # Статистика ошибок
            error_rate = (
                self.metrics['errors_total'] / self.metrics['requests_total']
                if self.metrics['requests_total'] > 0 else 0
            )
            
            return {
                **self.metrics,
                'uptime_seconds': uptime,
                'avg_response_time': avg_response_time,
                'cache_hit_rate': cache_hit_rate,
                'error_rate': error_rate,
                'requests_per_second': self.metrics['requests_total'] / uptime if uptime > 0 else 0
            }
    
    async def reset_metrics(self):
        """Сброс метрик"""
        async with self._lock:
            self.metrics = {
                'requests_total': 0,
                'requests_by_endpoint': {},
                'requests_by_method': {},
                'response_times': [],
                'errors_total': 0,
                'errors_by_status': {},
                'cache_hits': 0,
                'cache_misses': 0,
                'active_connections': 0,
                'db_queries': 0
            }
            self.start_time = time.time()

# Глобальный сборщик метрик
_metrics_collector: Optional[MetricsCollector] = None

async def get_metrics_collector() -> MetricsCollector:
    """Получить сборщик метрик"""
    global _metrics_collector
    
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    
    return _metrics_collector

# ===== КОНТЕКСТНЫЕ МЕНЕДЖЕРЫ =====

@asynccontextmanager
async def get_components() -> AsyncGenerator[Dict[str, Any], None]:
    """Контекстный менеджер для получения всех компонентов"""
    await ensure_initialized()
    
    components = {
        'data_manager': await get_data_manager(),
        'statistics': await get_statistics_calculator(),
        'analytics': await get_analytics_engine(),
        'cache': await get_cache_manager(),
        'metrics': await get_metrics_collector(),
        'rate_limiter': await get_rate_limiter()
    }
    
    try:
        yield components
    finally:
        # Cleanup если нужно
        pass

# ===== УТИЛИТЫ =====

def get_client_ip(request: Request) -> str:
    """Получить IP адрес клиента"""
    # Проверяем заголовки прокси
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    if cf_connecting_ip:
        return cf_connecting_ip
    
    return request.client.host

def get_user_agent(request: Request) -> str:
    """Получить User-Agent клиента"""
    return request.headers.get("User-Agent", "Unknown")

def get_request_info(request: Request) -> Dict[str, Any]:
    """Получить информацию о запросе"""
    return {
        'method': request.method,
        'url': str(request.url),
        'path': request.url.path,
        'query_params': dict(request.query_params),
        'headers': dict(request.headers),
        'client_ip': get_client_ip(request),
        'user_agent': get_user_agent(request),
        'timestamp': time.time()
    }

async def log_request(request: Request, response_time: float, status_code: int):
    """Логирование запроса"""
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    logger.info(
        f"{request.method} {request.url.path} "
        f"- {status_code} - {response_time:.3f}s "
        f"- {client_ip} - {user_agent[:50]}..."
    )
    
    # Записываем метрики
    metrics = await get_metrics_collector()
    await metrics.record_request(
        request.method,
        request.url.path,
        response_time,
        status_code
    )

# ===== ФОНОВЫЕ ЗАДАЧИ =====

class BackgroundTaskManager:
    """Менеджер фоновых задач"""
    
    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.running = False
    
    async def start(self):
        """Запуск фоновых задач"""
        if self.running:
            return
        
        self.running = True
        logger.info("🔄 Запуск фоновых задач...")
        
        # Задача очистки кэша
        self.tasks['cache_cleanup'] = asyncio.create_task(self._cache_cleanup_task())
        
        # Задача очистки метрик
        self.tasks['metrics_cleanup'] = asyncio.create_task(self._metrics_cleanup_task())
        
        logger.info("✅ Фоновые задачи запущены")
    
    async def stop(self):
        """Остановка фоновых задач"""
        if not self.running:
            return
        
        self.running = False
        logger.info("🛑 Остановка фоновых задач...")
        
        for name, task in self.tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.tasks.clear()
        logger.info("✅ Фоновые задачи остановлены")
    
    async def _cache_cleanup_task(self):
        """Задача очистки кэша"""
        while self.running:
            try:
                await asyncio.sleep(300)  # Каждые 5 минут
                
                cache = await get_cache_manager()
                await cache.cleanup()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в задаче очистки кэша: {e}")
    
    async def _metrics_cleanup_task(self):
        """Задача очистки метрик"""
        while self.running:
            try:
                await asyncio.sleep(3600)  # Каждый час
                
                metrics = await get_metrics_collector()
                # Можно добавить логику сохранения метрик в БД
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в задаче очистки метрик: {e}")

# Глобальный менеджер фоновых задач
_background_task_manager: Optional[BackgroundTaskManager] = None

async def get_background_task_manager() -> BackgroundTaskManager:
    """Получить менеджер фоновых задач"""
    global _background_task_manager
    
    if _background_task_manager is None:
        _background_task_manager = BackgroundTaskManager()
    
    return _background_task_manager

# ===== ОЧИСТКА РЕСУРСОВ =====

async def cleanup_resources():
    """Очистка ресурсов при остановке приложения"""
    global _data_manager, _statistics_calculator, _analytics_engine, _redis_client, _db_engine
    global _cache_manager, _rate_limiter, _metrics_collector, _background_task_manager
    
    logger.info("🧹 Очистка ресурсов...")
    
    try:
        # Останавливаем фоновые задачи
        if _background_task_manager:
            await _background_task_manager.stop()
        
        # Закрываем компоненты
        if _data_manager:
            await _data_manager.cleanup()
        
        if _statistics_calculator:
            await _statistics_calculator.cleanup()
        
        if _analytics_engine:
            await _analytics_engine.cleanup()
        
        # Очищаем кэш
        if _cache_manager:
            await _cache_manager.clear()
        
        # Закрываем Redis
        if _redis_client and REDIS_AVAILABLE:
            await _redis_client.close()
        
        # Закрываем БД
        if _db_engine and SQLALCHEMY_AVAILABLE:
            await _db_engine.dispose()
        
        logger.info("✅ Ресурсы очищены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке ресурсов: {e}")

# ===== ВСПОМОГАТЕЛЬНЫЕ ЗАВИСИМОСТИ =====

@lru_cache()
def get_settings():
    """Получить настройки (кэшированные)"""
    return settings

def get_logger(name: str = __name__):
    """Получить логгер с настройками"""
    return logging.getLogger(name)

def require_api_key(api_key: str = None):
    """Требовать API ключ (для будущего использования)"""
    def dependency(request: Request):
        key = request.headers.get("X-API-Key") or api_key
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API ключ обязателен"
            )
        return key
    return dependency

# ===== ВАЛИДАЦИЯ =====

def validate_request_size(max_size: int = 1024 * 1024):  # 1MB по умолчанию
    """Валидация размера запроса"""
    async def dependency(request: Request):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Размер запроса превышает {max_size} байт"
            )
        return True
    return dependency

# ===== ИНИЦИАЛИЗАЦИЯ ПРИ ИМПОРТЕ =====

async def startup_dependencies():
    """Запуск зависимостей"""
    await ensure_initialized()
    
    # Запускаем фоновые задачи
    task_manager = await get_background_task_manager()
    await task_manager.start()

async def shutdown_dependencies():
    """Остановка зависимостей"""
    await cleanup_resources()
