# handlers/messages.py

from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram import Update

async def ai_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI-чат: ловит любые не-командные сообщения"""
    user_text = update.message.text
    # Здесь должна быть интеграция с AI/фоллбеком
    response = f"AI ассистент: '{user_text}' (ответ-бота будет здесь)"
    await update.message.reply_text(response)

def register_message_handlers(application: Application):
    """Регистрирует AI чат-обработчик"""
    application.add_handler(
        MessageHandler(filters.TEXT & (~filters.COMMAND), ai_chat_message)
    )
