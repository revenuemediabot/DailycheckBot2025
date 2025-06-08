# handlers/commands/mood.py

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

async def mood_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отметьте ваше текущее настроение:")

async def moodstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ваша статистика настроения:")

def register_mood_handlers(application: Application):
    application.add_handler(CommandHandler("mood", mood_command))
    application.add_handler(CommandHandler("moodstats", moodstats_command))
