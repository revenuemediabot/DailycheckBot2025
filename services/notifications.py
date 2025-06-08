# services/notifications.py

from telegram.ext import Application

async def send_notification(application: Application, user_id: int, text: str):
    try:
        await application.bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        print(f"Ошибка отправки уведомления {user_id}: {e}")

def notify_streak(application: Application, user_id: int, streak: int):
    text = f"🔥 Поздравляем! У вас {streak} дней подряд выполненных задач."
    # Обычно вызывается через schedule или при изменении streak
    application.create_task(send_notification(application, user_id, text))
