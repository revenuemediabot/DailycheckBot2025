"""
Сервис управления таймерами
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger('dailycheck')

class TimerService:
    """Сервис для управления пользовательскими таймерами"""
    
    def __init__(self, bot_application):
        self.bot_application = bot_application
        self.active_timers: Dict[int, asyncio.Task] = {}
    
    async def start_timer(self, user_id: int, duration: int, timer_name: str, 
                         is_pomodoro: bool = False) -> bool:
        """Запуск таймера для пользователя"""
        try:
            # Останавливаем предыдущий таймер если есть
            await self.stop_timer(user_id)
            
            # Создаем новый таймер
            timer_task = asyncio.create_task(
                self._timer_worker(user_id, duration, timer_name, is_pomodoro)
            )
            
            self.active_timers[user_id] = timer_task
            
            logger.info(f"⏰ Запущен таймер для пользователя {user_id}: {timer_name} ({duration} мин)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска таймера: {e}")
            return False
    
    async def stop_timer(self, user_id: int) -> bool:
        """Остановка таймера пользователя"""
        if user_id in self.active_timers:
            try:
                self.active_timers[user_id].cancel()
                del self.active_timers[user_id]
                
                logger.info(f"⏹️ Остановлен таймер для пользователя {user_id}")
                return True
            except Exception as e:
                logger.error(f"❌ Ошибка остановки таймера: {e}")
        
        return False
    
    def is_timer_active(self, user_id: int) -> bool:
        """Проверка активности таймера"""
        return user_id in self.active_timers and not self.active_timers[user_id].done()
    
    def get_timer_info(self, user_id: int) -> Optional[Dict]:
        """Получение информации о таймере"""
        if self.is_timer_active(user_id):
            # В реальной реализации можно добавить больше информации
            return {
                "active": True,
                "user_id": user_id
            }
        return None
    
    async def _timer_worker(self, user_id: int, duration: int, timer_name: str, is_pomodoro: bool):
        """Рабочий процесс таймера"""
        try:
            # Ждем указанное время
            await asyncio.sleep(duration * 60)  # Переводим в секунды
            
            # Отправляем уведомление о завершении
            message = f"⏰ **Таймер завершен!**\n\n{timer_name} ({duration} мин) закончился.\n\nВремя отдохнуть или перейти к следующей задаче! 💪"
            
            try:
                await self.bot_application.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"❌ Ошибка отправки уведомления таймера: {e}")
            
            # Обновляем статистику если это помодоро
            if is_pomodoro:
                from database import DatabaseManager
                # Здесь нужно передать экземпляр DB
                # В реальной реализации это будет инжектиться
                pass
            
        except asyncio.CancelledError:
            logger.debug(f"⏹️ Таймер пользователя {user_id} отменен")
        except Exception as e:
            logger.error(f"❌ Ошибка в таймере: {e}")
        finally:
            # Удаляем из активных таймеров
            if user_id in self.active_timers:
                del self.active_timers[user_id]
    
    async def cleanup_all_timers(self):
        """Очистка всех активных таймеров при остановке"""
        for user_id in list(self.active_timers.keys()):
            await self.stop_timer(user_id)
        
        logger.info("🧹 Все таймеры очищены")
