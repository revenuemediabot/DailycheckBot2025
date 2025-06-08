# handlers/callbacks/settings.py

from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram import Update

async def settings_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # TODO: Главное меню настроек
    await query.edit_message_text("Настройки профиля:\n1️⃣ Тема\n2️⃣ Уведомления\n3️⃣ AI\n4️⃣ Экспорт\n5️⃣ Приватность")

async def settings_theme_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Сменить тему
    await query.answer()
    await query.edit_message_text("Выберите новую тему оформления:")

async def settings_reminders_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Управление напоминаниями
    await query.answer()
    await query.edit_message_text("Ваши напоминания:")

def register_settings_callbacks(application: Application):
    application.add_handler(CallbackQueryHandler(settings_menu_callback, pattern="^settings_menu$"))
    application.add_handler(CallbackQueryHandler(settings_theme_callback, pattern="^settings_theme$"))
    application.add_handler(CallbackQueryHandler(settings_reminders_callback, pattern="^settings_reminders$"))
