# handlers/commands/system.py

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Экспорт данных (JSON/CSV) начат...")

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Health check: Всё работает!")

async def dryon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Режим 'Dry' включён.")

async def dryoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Режим 'Dry' выключен.")

def register_system_handlers(application: Application):
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("dryon", dryon_command))
    application.add_handler(CommandHandler("dryoff", dryoff_command))
