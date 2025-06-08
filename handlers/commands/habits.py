# handlers/commands/habits.py

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

async def habits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ваши привычки:")

async def addhabit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привычка добавлена!")

async def completehabit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привычка отмечена как выполненная.")

def register_habit_handlers(application: Application):
    application.add_handler(CommandHandler("habits", habits_command))
    application.add_handler(CommandHandler("addhabit", addhabit_command))
    application.add_handler(CommandHandler("completehabit", completehabit_command))
