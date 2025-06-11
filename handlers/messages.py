# handlers/messages.py

from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from telegram import Update

# --- Вспомогательная функция для user_state ---
def get_state(context):
    return context.user_data.get('user_state', 'idle')

def set_state(context, state):
    context.user_data['user_state'] = state

# --- Команда для добавления задачи ---
async def add_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_state(context, 'add_task')
    await update.message.reply_text("Введите текст задачи для добавления (или /cancel для отмены):")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_state(context, 'idle')
    await update.message.reply_text("Действие отменено.")

# --- Универсальный обработчик текста ---
async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    state = get_state(context)

    if state == 'add_task':
        # Здесь логика добавления задачи в БД
        # save_task(update.effective_user.id, user_text)
        set_state(context, 'idle')
        await update.message.reply_text(f"Задача добавлена: {user_text}")
        return

    elif state == 'ai_chat':
        # Логика отправки в AI
        response = f"AI ассистент: '{user_text}' (ответ-бота будет здесь)"
        await update.message.reply_text(response)
        return

    else:
        # Обычный режим, можно добавить подсказку или игнорировать
        await update.message.reply_text("Используйте кнопки или команды для управления ботом.")

def register_message_handlers(application: Application):
    """Регистрирует обработчики"""
    # Команда добавления задачи
    application.add_handler(CommandHandler("addtask", add_task_start))
    application.add_handler(CommandHandler("cancel", cancel))
    # Универсальный обработчик текста
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_message))
