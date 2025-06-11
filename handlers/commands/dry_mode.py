"""
Dry mode commands (sobriety tracking)
Команды режима трезвости
"""

from aiogram import types
from aiogram.types import Message
from datetime import datetime

from ..utils import log_action, update_user_activity, get_user_data, save_user_data
from ui.keyboards import get_main_menu_keyboard
from ui.themes import get_user_theme
from ui.messages import format_success_message

async def dryon_command(message: Message) -> None:
    """Команда /dryon - начать отчет дней без алкоголя"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "dryon_command")
    
    theme = await get_user_theme(user_id)
    user_data = await get_user_data(user_id)
    
    dry_mode = user_data.get('dry_mode', {})
    
    if dry_mode.get('active', False):
        # Уже активен
        days_count = dry_mode.get('days_count', 0)
        start_date = dry_mode.get('start_date', '')
        
        await message.answer(
            f"🚫🍺 <b>Dry режим уже активен</b>\n\n"
            f"Дней без алкоголя: <b>{days_count}</b>\n"
            f"Начало: {start_date}\n\n"
            f"Продолжайте в том же духе! 💪",
            reply_markup=get_main_menu_keyboard(theme),
            parse_mode="HTML"
        )
    else:
        # Активируем режим
        dry_data = {
            'active': True,
            'start_date': datetime.now().strftime('%d.%m.%Y'),
            'days_count': 1
        }
        
        await save_user_data(user_id, {'dry_mode': dry_data})
        
        await message.answer(
            format_success_message(
                f"🚫🍺 <b>Dry режим активирован!</b>\n\n"
                f"Отличное решение! Я буду отслеживать ваши дни без алкоголя.\n\n"
                f"<b>День 1</b> начался сегодня!\n\n"
                f"💪 Вы можете это сделать!"
            ),
            reply_markup=get_main_menu_keyboard(theme),
            parse_mode="HTML"
        )

async def dryoff_command(message: Message) -> None:
    """Команда /dryoff - завершить отчет дней без алкоголя"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "dryoff_command")
    
    theme = await get_user_theme(user_id)
    user_data = await get_user_data(user_id)
    
    dry_mode = user_data.get('dry_mode', {})
    
    if not dry_mode.get('active', False):
        await message.answer(
            f"ℹ️ Dry режим не активен.\n\n"
            f"Используйте /dryon для начала отслеживания.",
            reply_markup=get_main_menu_keyboard(theme),
            parse_mode="HTML"
        )
    else:
        days_count = dry_mode.get('days_count', 0)
        
        # Деактивируем режим
        dry_data = {
            'active': False,
            'start_date': None,
            'days_count': 0,
            'last_session_days': days_count,
            'last_session_date': datetime.now().strftime('%d.%m.%Y')
        }
        
        await save_user_data(user_id, {'dry_mode': dry_data})
        
        await message.answer(
            f"🚫🍺 <b>Dry режим завершен</b>\n\n"
            f"Ваш результат: <b>{days_count} дней</b>\n\n"
            f"{'Отличная работа! 🎉' if days_count >= 7 else 'Хорошее начало! 👍'}\n\n"
            f"Статистика сохранена.",
            reply_markup=get_main_menu_keyboard(theme),
            parse_mode="HTML"
        )
