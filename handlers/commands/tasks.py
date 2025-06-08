# handlers/commands/tasks.py

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ваш список задач...")

async def addtask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добавлена новая задача!")

async def settasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Список задач обновлён.")

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Редактирование задач...")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Список задач сброшен.")

async def addsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Подзадача добавлена.")

def register_task_handlers(application: Application):
    application.add_handler(CommandHandler("tasks", tasks_command))
    application.add_handler(CommandHandler("addtask", addtask_command))
    application.add_handler(CommandHandler("settasks", settasks_command))
    application.add_handler(CommandHandler("edit", edit_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("addsub", addsub_command))
