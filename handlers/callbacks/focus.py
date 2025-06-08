# handlers/callbacks/focus.py

from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram import Update

async def focus_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # TODO: Включить фокус-режим (Deep Work/Study/Exercise)
    await query.edit_message_text("Фокус-режим активирован!")

async def focus_end_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # TODO: Завершить фокус-режим
    await query.edit_message_text("Фокус-режим завершён.")

async def focus_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Показать статистику по фокусу
    await query.answer()
    await query.edit_message_text("Статистика фокус-сессий:")

def register_focus_callbacks(application: Application):
    application.add_handler(CallbackQueryHandler(focus_start_callback, pattern="^focus_start$"))
    application.add_handler(CallbackQueryHandler(focus_end_callback, pattern="^focus_end$"))
    application.add_handler(CallbackQueryHandler(focus_stats_callback, pattern="^focus_stats$"))
