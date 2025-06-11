"""
Сервис уведомлений
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Dict, List, Optional

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

from models import User, Reminder

logger = logging.getLogger('dailycheck')

class NotificationService:
    """Сервис для управления уведомлениями и напоминаниями"""
    
    def __init__(self, bot_application, db_manager):
        self.bot_application = bot_application
        self.db_manager = db_manager
        self.scheduler = None
        
        if SCHEDULER_AVAILABLE:
            self.scheduler = AsyncIOScheduler()
            self.setup_default_notifications()
            self.scheduler.start()
            logger.info("📅 Сервис уведомлений запущен")
        else:
            logger.warning("⚠️ APScheduler недоступен - уведомления отключены")
    
    def setup_default_notifications(self):
        """Настройка стандартных уведомлений"""
        if not self.scheduler:
            return
        
        # Ежедневные напоминания в 9 утра
        self.scheduler.add_job(
            self.send_daily_reminders,
            CronTrigger(hour=9, minute=0),
            id='daily_reminders',
            replace_existing=True
        )
        
        # Еженедельная статистика по воскресеньям в 20:00
        self.scheduler.add_job(
            self.send_weekly_stats,
            CronTrigger(day_of_week=6, hour=20, minute=0),  # Sunday
            id='weekly_stats',
            replace_existing=True
        )
        
        # Проверка индивидуальных напоминаний каждые 5 минут
        self.scheduler.add_job(
            self.check_user_reminders,
            'interval',
            minutes=5,
            id='user_reminders',
            replace_existing=True
        )
    
    async def send_daily_reminders(self):
        """Отправка ежедневных напоминаний"""
        try:
            users = self.db_manager.get_all_users()
            
            for user in users:
                if not user.settings.reminder_enabled:
                    continue
                
                # Проверяем время пользователя (упрощенная версия)
                reminder_time = user.settings.daily_reminder_time
                current_time = datetime.now().strftime('%H:%M')
                
                if reminder_time == current_time:
                    await self._send_daily_reminder_to_user(user)
                    
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ежедневных напоминаний: {e}")
    
    async def _send_daily_reminder_to_user(self, user: User):
        """Отправка ежедневного напоминания конкретному пользователю"""
        try:
            incomplete_tasks = [
                task for task in user.active_tasks.values() 
                if not task.is_completed_today()
            ]
            
            if not incomplete_tasks:
                message = f"🌅 Доброе утро, {user.display_name}!\n\n✅ Все задачи на вчера выполнены! Отличная работа!\n\nГотовы к новому продуктивному дню? 💪"
            else:
                message = f"🌅 Доброе утро, {user.display_name}!\n\n📋 У вас {len(incomplete_tasks)} активных задач на сегодня:\n\n"
                
                for i, task in enumerate(incomplete_tasks[:3], 1):
                    message += f"{i}. {task.title}\n"
                
                if len(incomplete_tasks) > 3:
                    message += f"... и еще {len(incomplete_tasks) - 3}\n"
                
                message += "\nУдачного дня! 🚀"
            
            await self.bot_application.bot.send_message(
                chat_id=user.user_id,
                text=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминания пользователю {user.user_id}: {e}")
    
    async def send_weekly_stats(self):
        """Отправка еженедельной статистики"""
        try:
            users = self.db_manager.get_all_users()
            
            for user in users:
                if not user.settings.weekly_stats:
                    continue
                
                await self._send_weekly_stats_to_user(user)
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки еженедельной статистики: {e}")
    
    async def _send_weekly_stats_to_user(self, user: User):
        """Отправка еженедельной статистики конкретному пользователю"""
        try:
            week_progress = user.get_week_progress()
            
            message = f"""📊 **Еженедельная статистика**

Привет, {user.display_name}! Подводим итоги недели:

🎯 **Выполнение задач:**
• Выполнено: {week_progress['completed']} из {week_progress['goal']}
• Прогресс: {week_progress['progress_percentage']:.1f}%

⭐ **Общая статистика:**
• Уровень: {user.stats.level} ({user.stats.get_level_title()})
• Общий XP: {user.stats.total_xp}
• Всего выполнено: {user.stats.completed_tasks} задач

🔥 **Streak'и:**"""
            
            # Добавляем информацию о streak'ах
            active_streaks = [task.current_streak for task in user.active_tasks.values()]
            if active_streaks:
                max_streak = max(active_streaks)
                avg_streak = sum(active_streaks) / len(active_streaks)
                message += f"\n• Максимальный: {max_streak} дней\n• Средний: {avg_streak:.1f} дней"
            
            # Мотивационное сообщение
            if week_progress['progress_percentage'] >= 100:
                message += "\n\n🎉 **Поздравляем!** Вы выполнили недельную цель!"
            elif week_progress['progress_percentage'] >= 70:
                message += "\n\n💪 **Отличная работа!** Вы близки к цели!"
            else:
                message += "\n\n🚀 **Новая неделя - новые возможности!** Вперед к целям!"
            
            await self.bot_application.bot.send_message(
                chat_id=user.user_id,
                text=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки статистики пользователю {user.user_id}: {e}")
    
    async def check_user_reminders(self):
        """Проверка пользовательских напоминаний"""
        try:
            users = self.db_manager.get_all_users()
            current_time = datetime.now().strftime('%H:%M')
            
            for user in users:
                for reminder in user.reminders:
                    if not reminder.is_active:
                        continue
                    
                    # Простая проверка времени (в реальной версии нужна более сложная логика)
                    if reminder.trigger_time == current_time:
                        await self._send_user_reminder(user, reminder)
                        
        except Exception as e:
            logger.error(f"❌ Ошибка проверки пользовательских напоминаний: {e}")
    
    async def _send_user_reminder(self, user: User, reminder: Reminder):
        """Отправка пользовательского напоминания"""
        try:
            message = f"🔔 **Напоминание**\n\n📝 {reminder.title}\n\n{reminder.message}"
            
            await self.bot_application.bot.send_message(
                chat_id=user.user_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"📤 Отправлено напоминание пользователю {user.user_id}: {reminder.title}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминания: {e}")
    
    async def add_user_reminder(self, user: User, title: str, message: str, 
                              trigger_time: str, is_recurring: bool = False) -> bool:
        """Добавление пользовательского напоминания"""
        try:
            reminder_id = user.add_reminder(title, message, trigger_time, is_recurring)
            self.db_manager.save_user(user)
            
            logger.info(f"➕ Добавлено напоминание для пользователя {user.user_id}: {title}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления напоминания: {e}")
            return False
    
    async def send_achievement_notification(self, user: User, achievement_id: str):
        """Отправка уведомления о достижении"""
        try:
            from models import AchievementSystem
            message = AchievementSystem.get_achievement_message(achievement_id, user)
            
            await self.bot_application.bot.send_message(
                chat_id=user.user_id,
                text=message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о достижении: {e}")
    
    async def send_motivational_message(self, user: User):
        """Отправка мотивационного сообщения"""
        if not user.settings.motivational_messages:
            return
        
        try:
            messages = [
                f"💪 {user.display_name}, помни: каждый маленький шаг приближает к большой цели!",
                f"🌟 Ты уже на уровне {user.stats.level}! Продолжай двигаться вперед!",
                f"🔥 Твои достижения говорят сами за себя - ты способен на многое!",
                f"🎯 Сегодня отличный день для новых свершений!",
                f"⭐ Каждая выполненная задача делает тебя сильнее!"
            ]
            
            import random
            message = random.choice(messages)
            
            await self.bot_application.bot.send_message(
                chat_id=user.user_id,
                text=message
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки мотивационного сообщения: {e}")
    
    def shutdown(self):
        """Остановка сервиса уведомлений"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("📅 Сервис уведомлений остановлен")

if __name__ == "__main__":
    # Тестирование сервисов
    print("🧪 Тестирование сервисов")
    
    # Тест AI сервиса
    ai_service = AIService()
    print(f"🤖 AI сервис: {'✅ включен' if ai_service.enabled else '❌ отключен'}")
    
    # Тест классификации
    from models import User, UserSettings, UserStats
    test_user = User(user_id=123, first_name="Тест")
    
    request_type = ai_service.classify_request("Мотивируй меня", test_user)
    print(f"🎯 Классификация запроса: {request_type}")
    
    # Тест fallback ответов
    response = ai_service._get_fallback_response("Помоги с мотивацией", test_user)
    print(f"💬 Fallback ответ: {response[:50]}...")
    
    print("✅ Тестирование завершено")
