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
from typing import Optional, Dict, Any, Generator, AsyncGenerator
from functools import lru_cache
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from dashboard.config import settings
from dashboard.core.data_manager import DataManager
from dashboard.core.statistics import StatisticsCalculator
from dashboard.core.analytics import AnalyticsEngine

logger = logging.getLogger(__name__)

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====

# Менеджер данных (синглтон)
_data_manager: Optional[DataManager] = None

# Калькулятор статистики (синглтон)
_statistics_calculator: Optional[StatisticsCalculator] = None

# Аналитический движок (синглтон)  
_analytics_engine: Optional[AnalyticsEngine] = None

# Redis клиент (опционально)
_redis_client: Optional[redis.Redis] = None

# База данных (опционально)
_db_engine = None
_db_session_factory = None

# ===== ИНИЦИАЛИЗАЦИЯ КОМПОНЕНТОВ =====

async def init_data_manager() -> DataManager:
    """Инициализация менеджера данных"""
    global _data_manager
    
    if _data_manager is None:
        logger.info("🔄 Инициализация DataManager...")
        _data_manager = DataManager(settings.DATA_DIR)
        await _data_manager.initialize()
        logger.info("✅ DataManager инициализирован")
    
    return _data_manager

async def init_statistics_calculator() -> StatisticsCalculator:
    """Инициализация калькулятора статистики"""
    global _statistics_calculator
    
    if _statistics_calculator is None:
        logger.info("🔄 Инициализация StatisticsCalculator...")
        data_manager = await get_data_manager()
        _statistics_calculator = StatisticsCalculator(data_manager)
        await _statistics_calculator.initialize()
        logger.info("✅ StatisticsCalculator инициализирован")
    
    return _statistics_calculator

async def init_analytics_engine() -> AnalyticsEngine:
    """Инициализация аналитического движка"""
    global _analytics_engine
    
    if _analytics_engine is None:
        logger.info("🔄 Инициализация AnalyticsEngine...")
        data_manager = await get_data_manager()
        stats_calculator = await get_statistics_calculator()
        _analytics_engine = AnalyticsEngine(data_manager, stats_calculator)
        await _analytics_engine.initialize()
        logger.info("✅ AnalyticsEngine инициализирован")
    
    return _analytics_engine

async def init_redis() -> Optional[redis.Redis]:
    """Инициализация Redis для кэширования"""
    global _redis_client
    
    if settings.REDIS_URL and _redis_client is None:
        try:
            logger.info("🔄 Подключение к Redis...")
            _redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=10
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
    
    if settings.DATABASE_URL and _db_engine is None:
        try:
            logger.info("🔄 Инициализация базы данных...")
            
            _db_engine = create_async_engine(
                settings.DATABASE_URL,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                echo=settings.DEBUG
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
    if _data_manager is None:
        return await init_data_manager()
    return _data_manager

async def get_statistics_calculator() -> StatisticsCalculator:
    """Получить экземпляр StatisticsCalculator"""
    if _statistics_calculator is None:
        return await init_statistics_calculator()
    return _statistics_calculator

async def get_analytics_engine() -> AnalyticsEngine:
    """Получить экземпляр AnalyticsEngine"""
    if _analytics_engine is None:
        return await init_analytics_engine()
    return _analytics_engine

async def get_redis() -> Optional[redis.Redis]:
    """Получить Redis клиент"""
    if settings.REDIS_URL and _redis_client is None:
        return await init_redis()
    return _redis_client

async def get_db_session() -> Optional[AsyncSession]:
    """Получить сессию базы данных"""
    if _db_session_factory is None:
        await init_database()
    
    if _db_session_factory:
        async with _db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    else:
        yield None

# ===== КЭШИРОВАНИЕ =====

class CacheManager:
    """Менеджер кэширования данных"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = settings.CACHE_TTL
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        if not settings.CACHE_ENABLED:
            return None
        
        # Сначала пробуем Redis
        if self.redis:
            try:
                import json
                value = await self.redis.get(key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Ошибка чтения из Redis: {e}")
        
        # Fallback на память
        if key in self.memory_cache:
            cache_item = self.memory_cache[key]
            if time.time() - cache_item['timestamp'] < self.cache_ttl:
                return cache_item['data']
            else:
                del self.memory_cache[key]
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Сохранить значение в кэш"""
        if not settings.CACHE_ENABLED:
            return
        
        ttl = ttl or self.cache_ttl
        
        # Сохраняем в Redis
        if self.redis:
            try:
                import json
                await self.redis.setex(key, ttl, json.dumps(value, default=str))
            except Exception as e:
                logger.warning(f"Ошибка записи в Redis: {e}")
        
        # Сохраняем в память
        self.memory_cache[key] = {
            'data': value,
            'timestamp': time.time()
        }
        
        # Очистка старого кэша в памяти
        await self._cleanup_memory_cache()
    
    async def delete(self, key: str) -> None:
        """Удалить значение из кэша"""
        if self.redis:
            try:
                await self.redis.delete(key)
            except Exception as e:
                logger.warning(f"Ошибка удаления из Redis: {e}")
        
        if key in self.memory_cache:
            del self.memory_cache[key]
    
    async def clear(self) -> None:
        """Очистить весь кэш"""
        if self.redis:
            try:
                await self.redis.flushdb()
            except Exception as e:
                logger.warning(f"Ошибка очистки Redis: {e}")
        
        self.memory_cache.clear()
    
    async def _cleanup_memory_cache(self) -> None:
        """Очистка устаревшего кэша в памяти"""
        current_time = time.time()
        expired_keys = [
            key for key, item in self.memory_cache.items()
            if current_time - item['timestamp'] > self.cache_ttl
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]

# Глобальный кэш менеджер
_cache_manager: Optional[CacheManager] = None

async def get_cache_manager() -> CacheManager:
    """Получить менеджер кэширования"""
    global _cache_manager
    
    if _cache_manager is None:
        redis_client = await get_redis()
        _cache_manager = CacheManager(redis_client)
    
    return _cache_manager

# ===== АВТОРИЗАЦИЯ =====

security = HTTPBearer(auto_error=False)

class TelegramAuth:
    """Авторизация через Telegram Web App"""
    
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.admin_ids = settings.ADMIN_USER_IDS
    
    async def verify_telegram_data(self, init_data: str) -> Optional[Dict[str, Any]]:
        """Проверка данных Telegram Web App"""
        # TODO: Реализовать проверку подписи Telegram
        # Пока заглушка для будущей реализации
        if not self.bot_token:
            return None
        
        try:
            # Здесь будет реальная проверка hash и данных от Telegram
            # return parse_and_verify_telegram_data(init_data, self.bot_token)
            return {"user_id": 123456, "username": "test_user"}
        except Exception as e:
            logger.error(f"Ошибка проверки Telegram данных: {e}")
            return None
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка прав администратора"""
        return user_id in self.admin_ids

telegram_auth = TelegramAuth()

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Dict[str, Any]]:
    """Получить текущего пользователя (для будущей авторизации)"""
    if not credentials:
        return None
    
    # Попытка проверки Telegram данных
    user_data = await telegram_auth.verify_telegram_data(credentials.credentials)
    return user_data

async def require_auth(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Требовать авторизации"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация"
        )
    return current_user

async def require_admin(
    current_user: Dict[str, Any] = Depends(require_auth)
) -> Dict[str, Any]:
    """Требовать права администратора"""
    user_id = current_user.get("user_id")
    if not user_id or not telegram_auth.is_admin(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора"
        )
    return current_user

# ===== RATE LIMITING =====

class RateLimiter:
    """Простой rate limiter в памяти"""
    
    def __init__(self):
        self.requests: Dict[str, list] = {}
        self.limits = self._parse_limit(settings.API_RATE_LIMIT)
    
    def _parse_limit(self, limit_str: str) -> Dict[str, int]:
        """Парсинг строки лимита (например, '100/minute')"""
        try:
            count, period = limit_str.split('/')
            return {
                'count': int(count),
                'period': {'second': 1, 'minute': 60, 'hour': 3600}.get(period, 60)
            }
        except:
            return {'count': 100, 'period': 60}
    
    async def is_allowed(self, client_id: str) -> bool:
        """Проверка лимита запросов"""
        current_time = time.time()
        
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # Удаляем старые запросы
        cutoff_time = current_time - self.limits['period']
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff_time
        ]
        
        # Проверяем лимит
        if len(self.requests[client_id]) >= self.limits['count']:
            return False
        
        # Добавляем текущий запрос
        self.requests[client_id].append(current_time)
        return True

rate_limiter = RateLimiter()

async def check_rate_limit(request: Request):
    """Middleware для проверки rate limit"""
    client_ip = request.client.host
    
    if not await rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Превышен лимит запросов"
        )

# ===== МОНИТОРИНГ И МЕТРИКИ =====

class MetricsCollector:
    """Сборщик метрик приложения"""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            'requests_total': 0,
            'requests_by_endpoint': {},
            'response_times': [],
            'errors_total': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self.start_time = time.time()
    
    def record_request(self, endpoint: str, response_time: float, status_code: int):
        """Записать метрику запроса"""
        self.metrics['requests_total'] += 1
        
        if endpoint not in self.metrics['requests_by_endpoint']:
            self.metrics['requests_by_endpoint'][endpoint] = 0
        self.metrics['requests_by_endpoint'][endpoint] += 1
        
        self.metrics['response_times'].append(response_time)
        
        if status_code >= 400:
            self.metrics['errors_total'] += 1
    
    def record_cache_hit(self):
        """Записать попадание в кэш"""
        self.metrics['cache_hits'] += 1
    
    def record_cache_miss(self):
        """Записать промах кэша"""
        self.metrics['cache_misses'] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить все метрики"""
        uptime = time.time() - self.start_time
        avg_response_time = (
            sum(self.metrics['response_times']) / len(self.metrics['response_times'])
            if self.metrics['response_times'] else 0
        )
        
        cache_hit_rate = (
            self.metrics['cache_hits'] / 
            (self.metrics['cache_hits'] + self.metrics['cache_misses'])
            if (self.metrics['cache_hits'] + self.metrics['cache_misses']) > 0 else 0
        )
        
        return {
            **self.metrics,
            'uptime_seconds': uptime,
            'avg_response_time': avg_response_time,
            'cache_hit_rate': cache_hit_rate
        }

metrics_collector = MetricsCollector()

async def get_metrics_collector() -> MetricsCollector:
    """Получить сборщик метрик"""
    return metrics_collector

# ===== КОНТЕКСТНЫЕ МЕНЕДЖЕРЫ =====

@asynccontextmanager
async def get_components() -> AsyncGenerator[Dict[str, Any], None]:
    """Контекстный менеджер для получения всех компонентов"""
    components = {
        'data_manager': await get_data_manager(),
        'statistics': await get_statistics_calculator(),
        'analytics': await get_analytics_engine(),
        'cache': await get_cache_manager(),
        'metrics': await get_metrics_collector()
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
    
    return request.client.host

def get_user_agent(request: Request) -> str:
    """Получить User-Agent клиента"""
    return request.headers.get("User-Agent", "Unknown")

async def log_request(request: Request, response_time: float, status_code: int):
    """Логирование запроса"""
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    logger.info(
        f"{request.method} {request.url.path} "
        f"- {status_code} - {response_time:.3f}s "
        f"- {client_ip} - {user_agent}"
    )
    
    # Записываем метрики
    metrics_collector.record_request(
        request.url.path, 
        response_time, 
        status_code
    )

# ===== ОЧИСТКА РЕСУРСОВ =====

async def cleanup_resources():
    """Очистка ресурсов при остановке приложения"""
    global _data_manager, _statistics_calculator, _analytics_engine, _redis_client, _db_engine
    
    logger.info("🧹 Очистка ресурсов...")
    
    try:
        # Закрываем компоненты
        if _data_manager:
            await _data_manager.cleanup()
        
        if _statistics_calculator:
            await _statistics_calculator.cleanup()
        
        if _analytics_engine:
            await _analytics_engine.cleanup()
        
        # Закрываем Redis
        if _redis_client:
            await _redis_client.close()
        
        # Закрываем БД
        if _db_engine:
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
