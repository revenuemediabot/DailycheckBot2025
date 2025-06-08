# handlers/commands/admin.py

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Админ-рассылка начата.")

async def stats_global_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Глобальная статистика:")

def register_admin_handlers(application: Application):
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("stats_global", stats_global_command))
