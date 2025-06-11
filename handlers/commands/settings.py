"""
Settings and personalization commands
Команды настроек и персонализации
"""

from aiogram import types
from aiogram.types import Message

from ..utils import log_action, update_user_activity, get_user_data, save_user_data
from ui.keyboards import get_main_menu_keyboard, get_theme_keyboard, get_settings_keyboard
from ui.themes import get_user_theme, THEMES
from ui.messages import format_success_message

async def theme_command(message: Message) -> None:
    """Команда /theme - сменить тему оформления"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "theme_command")
    
    theme = await get_user_theme(user_id)
    
    await message.answer(
        f"🎨 <b>Выбор темы оформления</b>\n\n"
        f"Выберите тему которая вам нравится:",
        reply_markup=get_theme_keyboard(),
        parse_mode="HTML"
    )

async def settings_command(message: Message) -> None:
    """Команда /settings - настройки пользователя"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "settings_command")
    
    theme = await get_user_theme(user_id)
    user_data = await get_user_data(user_id)
    
    settings_text = f"{theme.get('settings_emoji', '⚙️')} <b>Настройки</b>\n\n"
    settings_text += f"<b>Текущие настройки:</b>\n"
    settings_text += f"• Тема: {user_data.get('theme', 'default')}\n"
    settings_text += f"• Уведомления: {'Включены' if user_data.get('notifications', True) else 'Выключены'}\n"
    settings_text += f"• Язык: {user_data.get('language', 'ru')}\n"
    settings_text += f"• AI чат: {'Включен' if user_data.get('ai_chat_enabled', False) else 'Выключен'}\n"
    
    await message.answer(
        settings_text,
        reply_markup=get_settings_keyboard(theme),
        parse_mode="HTML"
    )
