# handlers/router.py

from telegram.ext import Application

# Импорт всех нужных обработчиков (команды, callbacks, сообщения)
from handlers.commands.basic import register_basic_handlers
from handlers.commands.tasks import register_task_handlers
from handlers.commands.mood import register_mood_handlers
from handlers.commands.focus import register_focus_handlers
# ... и так далее для других команд

from handlers.callbacks.main_menu import register_main_menu_callbacks
from handlers.callbacks.tasks import register_tasks_callbacks
# ... и так далее для других callbacks

from handlers.messages import register_message_handlers

def register_handlers(application: Application):
    """Подключает все обработчики в Application"""
    register_basic_handlers(application)
    register_task_handlers(application)
    register_mood_handlers(application)
    register_focus_handlers(application)
    # ... все остальные register_*_handlers

    register_main_menu_callbacks(application)
    register_tasks_callbacks(application)
    # ... остальные callbacks

    register_message_handlers(application)
