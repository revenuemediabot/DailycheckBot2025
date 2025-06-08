# handlers/callbacks/achievements.py

from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram import Update

async def achievements_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # TODO: Показать список ачивок, их статус (разблокировано/нет)
    await query.edit_message_text("Ваши достижения:")

async def achievement_share_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Шаринг ачивки (сделать пост)
    await query.answer("Достижение опубликовано!", show_alert=True)

def register_achievements_callbacks(application: Application):
    application.add_handler(CallbackQueryHandler(achievements_list_callback, pattern="^achievements_list$"))
    application.add_handler(CallbackQueryHandler(achievement_share_callback, pattern="^achievement_share:"))
