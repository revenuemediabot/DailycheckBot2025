# handlers/commands/settings.py

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Настройки профиля:")

async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выберите тему оформления:")

async def onboarding_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добро пожаловать в вводный туториал!")

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Установить напоминание:")

def register_settings_handlers(application: Application):
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("theme", theme_command))
    application.add_handler(CommandHandler("onboarding", onboarding_command))
    application.add_handler(CommandHandler("remind", remind_command))
