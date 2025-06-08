# handlers/commands/basic.py

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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
        "/start — перезапустить бота\n"
        "/help — справка\n"
        "/tasks — список задач\n"
        "/addtask — добавить задачу\n"
        # ...другие команды, по необходимости
    )
    await update.message.reply_html(help_text)

def register_basic_handlers(application: Application):
    """Регистрирует базовые команды бота"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    # Можно добавить ещё тестовые команды, если нужно
