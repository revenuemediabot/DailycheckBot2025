# handlers/commands/focus.py

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

async def focus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Фокус-режим активирован.")

async def endfocus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Фокус-режим завершён.")

async def timer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Таймер запущен.")

def register_focus_handlers(application: Application):
    application.add_handler(CommandHandler("focus", focus_command))
    application.add_handler(CommandHandler("endfocus", endfocus_command))
    application.add_handler(CommandHandler("timer", timer_command))
