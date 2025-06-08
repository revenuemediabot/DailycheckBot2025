# handlers/messages.py

from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram import Update

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    # Заглушка: заменить на вызов AI/сервисов/логики
    response = f"Вы написали: {text}\n(Тут будет AI-ответ 👨‍💻)"

    await update.message.reply_text(response)

def register_message_handlers(application: Application):
    """Регистрирует обработчик текстовых сообщений"""
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), handle_ai_chat)
    )
