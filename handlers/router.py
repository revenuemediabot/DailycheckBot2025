# handlers/router.py

from telegram.ext import Application

# Команды
from handlers.commands.basic import register_basic_handlers
from handlers.commands.tasks import register_task_handlers
from handlers.commands.habits import register_habit_handlers
from handlers.commands.mood import register_mood_handlers
from handlers.commands.focus import register_focus_handlers
from handlers.commands.ai import register_ai_handlers
from handlers.commands.social import register_social_handlers
from handlers.commands.analytics import register_analytics_handlers
from handlers.commands.settings import register_settings_handlers
from handlers.commands.system import register_system_handlers
from handlers.commands.admin import register_admin_handlers

# Callback-обработчики
from handlers.callbacks.main_menu import register_main_menu_callbacks
from handlers.callbacks.tasks import register_tasks_callbacks
from handlers.callbacks.habits import register_habits_callbacks
from handlers.callbacks.mood import register_mood_callbacks
from handlers.callbacks.focus import register_focus_callbacks
from handlers.callbacks.achievements import register_achievements_callbacks
from handlers.callbacks.settings import register_settings_callbacks
from handlers.callbacks.quick_actions import register_quick_actions_callbacks

# AI-чат и fallback-сообщения
from handlers.messages import register_message_handlers

def register_handlers(application: Application):
    # Команды
    register_basic_handlers(application)
    register_task_handlers(application)
    register_habit_handlers(application)
    register_mood_handlers(application)
    register_focus_handlers(application)
    register_ai_handlers(application)
    register_social_handlers(application)
    register_analytics_handlers(application)
    register_settings_handlers(application)
    register_system_handlers(application)
    register_admin_handlers(application)

    # Callback-обработчики
    register_main_menu_callbacks(application)
    register_tasks_callbacks(application)
    register_habits_callbacks(application)
    register_mood_callbacks(application)
    register_focus_callbacks(application)
    register_achievements_callbacks(application)
    register_settings_callbacks(application)
    register_quick_actions_callbacks(application)

    # Обработка обычных сообщений (AI chat)
    register_message_handlers(application)
