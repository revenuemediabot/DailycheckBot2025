# services/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.start()

def schedule_daily_reset(callback, hour: int = 0, minute: int = 0):
    scheduler.add_job(callback, 'cron', hour=hour, minute=minute)

def schedule_reminder(user_id: int, message: str, when):
    # TODO: Реализация постановки напоминания для пользователя
    pass
