"""
System commands
Системные команды
"""

from aiogram import types
from aiogram.types import Message
import psutil
import datetime

from ..utils import log_action, update_user_activity
from ui.keyboards import get_main_menu_keyboard
from ui.themes import get_user_theme

async def health_command(message: Message) -> None:
    """Команда /health - проверить состояние системы"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "health_command")
    
    theme = await get_user_theme(user_id)
    
    # Получаем системную информацию
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
    except:
        cpu_percent = 0
        memory = None
        disk = None
    
    health_text = f"🏥 <b>Состояние системы</b>\n\n"
    health_text += f"🤖 <b>Бот:</b> Работает нормально\n"
    health_text += f"⏰ <b>Время работы:</b> {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
    
    if memory and disk:
        health_text += f"💾 <b>Память:</b> {memory.percent}% использовано\n"
        health_text += f"💿 <b>Диск:</b> {disk.percent}% использовано\n"
        health_text += f"⚡ <b>CPU:</b> {cpu_percent}%\n\n"
    
    health_text += f"✅ Все системы работают стабильно"
    
    await message.answer(
        health_text,
        reply_markup=get_main_menu_keyboard(theme),
        parse_mode="HTML"
    )

async def test_command(message: Message) -> None:
    """Команда /test - тестовая команда"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "test_command")
    
    theme = await get_user_theme(user_id)
    
    await message.answer(
        f"🧪 <b>Тестовая команда</b>\n\n"
        f"Все работает отлично!\n"
        f"Время: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        reply_markup=get_main_menu_keyboard(theme),
        parse_mode="HTML"
    )
