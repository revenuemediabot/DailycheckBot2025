# handlers/callbacks/mood.py

from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram import Update

async def mood_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # TODO: Выбор настроения (эмодзи, шкала)
    await query.edit_message_text("Выберите своё настроение:")

async def mood_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Показать график/статистику по настроению
    await query.answer()
    await query.edit_message_text("Ваша статистика по настроению:")

def register_mood_callbacks(application: Application):
    application.add_handler(CallbackQueryHandler(mood_select_callback, pattern="^mood_select$"))
    application.add_handler(CallbackQueryHandler(mood_stats_callback, pattern="^mood_stats$"))
