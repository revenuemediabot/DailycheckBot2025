# handlers/callbacks/quick_actions.py

from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram import Update

async def quick_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # TODO: Реализация быстрых действий (например: “Выполнить задачу”, “Добавить привычку”)
    await query.edit_message_text("Быстрое действие выполнено!")

async def quick_motivation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # TODO: Быстрая мотивация
    await query.edit_message_text("Мотивация дня: Ты справишься!")

def register_quick_actions_callbacks(application: Application):
    application.add_handler(CallbackQueryHandler(quick_action_callback, pattern="^quick_action:"))
    application.add_handler(CallbackQueryHandler(quick_motivation_callback, pattern="^quick_motivation$"))
