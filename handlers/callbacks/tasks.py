# handlers/callbacks/tasks.py

from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from telegram import Update

async def tasks_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # TODO: Логика показа задач
    await query.edit_message_text("Ваши задачи (список, кнопки-управления):")

async def task_complete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Завершить задачу по ID
    await query.answer("Задача выполнена! 🎉", show_alert=True)

async def task_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Редактирование задачи
    await query.answer()
    await query.edit_message_text("Редактирование задачи...")

async def task_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Удаление задачи
    await query.answer("Задача удалена.", show_alert=True)

async def subtask_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # TODO: Добавить подзадачу
    await query.answer()
    await query.edit_message_text("Добавление подзадачи...")

def register_tasks_callbacks(application: Application):
    application.add_handler(CallbackQueryHandler(tasks_list_callback, pattern="^tasks_list$"))
    application.add_handler(CallbackQueryHandler(task_complete_callback, pattern="^task_complete:"))
    application.add_handler(CallbackQueryHandler(task_edit_callback, pattern="^task_edit:"))
    application.add_handler(CallbackQueryHandler(task_delete_callback, pattern="^task_delete:"))
    application.add_handler(CallbackQueryHandler(subtask_add_callback, pattern="^subtask_add:"))
