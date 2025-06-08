# handlers/callbacks/habits.py

from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram import Update

async def habits_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # TODO: Показать привычки (список)
    await query.edit_message_text("Ваши привычки:")

async def habit_complete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Отметить привычку выполненной
    await query.answer("Привычка выполнена!", show_alert=True)

async def habit_streak_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Показать календарь стриков
    await query.answer()
    await query.edit_message_text("Ваш стрик по привычке:")

def register_habits_callbacks(application: Application):
    application.add_handler(CallbackQueryHandler(habits_list_callback, pattern="^habits_list$"))
    application.add_handler(CallbackQueryHandler(habit_complete_callback, pattern="^habit_complete:"))
    application.add_handler(CallbackQueryHandler(habit_streak_callback, pattern="^habit_streak:"))
