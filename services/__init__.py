# services/__init__.py

"""
Модуль сервисов DailyCheck Bot v4.0

Этот модуль содержит все сервисы для работы с данными и бизнес-логикой бота.
"""

import logging
from typing import Optional

from .data_service import DataService, get_data_service, initialize_data_service, close_data_service
from .task_service import TaskService, get_task_service, initialize_task_service

logger = logging.getLogger(__name__)

class ServiceManager:
    """
    Менеджер для управления всеми сервисами бота
    
    Обеспечивает:
    - Правильную инициализацию сервисов в нужном порядке
    - Управление зависимостями между сервисами
    - Корректное закрытие всех сервисов
    """
    
    def __init__(self):
        self.data_service: Optional[DataService] = None
        self.task_service: Optional[TaskService] = None
        self.initialized = False
    
    def initialize_services(self, data_file: str = None) -> bool:
        """Инициализация всех сервисов"""
        try:
            logger.info("🔧 Инициализация сервисов DailyCheck Bot...")
            
            # 1. Инициализируем сервис данных (базовый)
            logger.info("📂 Инициализация DataService...")
            self.data_service = initialize_data_service(data_file)
            
            # 2. Инициализируем сервис задач (зависит от DataService)
            logger.info("📝 Инициализация TaskService...")
            self.task_service = initialize_task_service(self.data_service)
            
            self.initialized = True
            logger.info("✅ Все сервисы инициализированы успешно!")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации сервисов: {e}")
            self.close_services()
            return False
    
    def get_services_info(self) -> dict:
        """Получить информацию о состоянии сервисов"""
        info = {
            "initialized": self.initialized,
            "services": {}
        }
        
        if self.data_service:
            info["services"]["data_service"] = {
                "status": "active",
                "users_count": self.data_service.get_users_count(),
                "metrics": self.data_service.get_service_metrics()
            }
        
        if self.task_service:
            info["services"]["task_service"] = {
                "status": "active"
            }
        
        return info
    
    def health_check(self) -> dict:
        """Проверка состояния всех сервисов"""
        health = {
            "status": "healthy",
            "services": {}
        }
        
        if self.data_service:
            health["services"]["data_service"] = self.data_service.health_check()
        
        if self.task_service:
            health["services"]["task_service"] = {"status": "healthy"}
        
        # Определяем общий статус
        service_statuses = [s.get("status", "unknown") for s in health["services"].values()]
        if "error" in service_statuses:
            health["status"] = "error"
        elif "warning" in service_statuses:
            health["status"] = "warning"
        
        return health
    
    def close_services(self):
        """Закрытие всех сервисов"""
        try:
            logger.info("🛑 Закрытие сервисов...")
            
            # Закрываем в обратном порядке инициализации
            if self.task_service:
                logger.info("📝 Закрытие TaskService...")
                # TaskService не требует специального закрытия
                self.task_service = None
            
            if self.data_service:
                logger.info("📂 Закрытие DataService...")
                close_data_service()
                self.data_service = None
            
            self.initialized = False
            logger.info("✅ Все сервисы закрыты")
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия сервисов: {e}")
    
    def __enter__(self):
        """Context manager вход"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager выход"""
        self.close_services()

# Глобальный экземпляр менеджера сервисов
_service_manager = None

def get_service_manager() -> ServiceManager:
    """Получить глобальный менеджер сервисов"""
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager

def initialize_all_services(data_file: str = None) -> bool:
    """Инициализация всех сервисов"""
    manager = get_service_manager()
    return manager.initialize_services(data_file)

def close_all_services():
    """Закрытие всех сервисов"""
    global _service_manager
    if _service_manager:
        _service_manager.close_services()
        _service_manager = None

def get_services_health() -> dict:
    """Получить состояние всех сервисов"""
    manager = get_service_manager()
    return manager.health_check()

# Экспорты для удобства
__all__ = [
    'DataService',
    'TaskService', 
    'ServiceManager',
    'get_data_service',
    'get_task_service',
    'get_service_manager',
    'initialize_all_services',
    'close_all_services',
    'get_services_health'
]
