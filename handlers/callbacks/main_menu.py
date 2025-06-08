# handlers/callbacks/main_menu.py

from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram import Update

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Здесь должна быть логика показа главного меню
    await query.edit_message_text("Главное меню:\n1️⃣ Задачи\n2️⃣ Привычки\n3️⃣ Настроение\n4️⃣ Статистика\n5️⃣ Социальные функции\n6️⃣ Настройки\n7️⃣ Достижения\n8️⃣ Быстрые действия")

def register_main_menu_callbacks(application: Application):
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
