# handlers/commands/basic.py

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name or 'друг'}! 👋\n"
        "Я — твой ассистент для трекинга задач и привычек.\n"
        "Введи /help для списка команд."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🛠 <b>Доступные команды</b>:\n"
        "/start — главное меню\n"
        "/help — справка\n"
        "/myid — узнать свой Telegram ID\n"
        "/tasks — задачи\n"
        "/habits — привычки\n"
        "/mood — настроение\n"
        "/focus — фокус-режим\n"
        "/ai_chat — AI-чат\n"
        "/motivate — мотивация\n"
        "/stats — статистика\n"
        "/settings — настройки\n"
        "/export — экспорт данных\n"
        "— и многое другое!"
    )
    await update.message.reply_html(help_text)

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Ваш Telegram ID: <code>{user.id}</code>", parse_mode="HTML"
    )

def register_basic_handlers(application: Application):
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myid", myid_command))
