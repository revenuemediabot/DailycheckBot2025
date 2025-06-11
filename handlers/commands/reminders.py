"""
Reminders and timers commands
Команды напоминаний и таймеров
"""

from aiogram import types
from aiogram.types import Message

from ..states import state_manager, UserState
from ..utils import log_action, update_user_activity
from services.reminder_service import ReminderService
from services.timer_service import TimerService
from ui.keyboards import get_main_menu_keyboard
from ui.themes import get_user_theme

async def remind_command(message: Message) -> None:
    """Команда /remind - создать напоминание"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "remind_command")
    
    theme = await get_user_theme(user_id)
    
    command_args = message.text.split(' ', 1)
    
    if len(command_args) > 1:
        reminder_text = command_args[1].strip()
        
        reminder_service = ReminderService()
        success = await reminder_service.parse_and_create_reminder(user_id, reminder_text)
        
        if success:
            await message.answer(
                f"⏰ Напоминание установлено!",
                reply_markup=get_main_menu_keyboard(theme),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Не удалось создать напоминание. Проверьте формат.",
                reply_markup=get_main_menu_keyboard(theme),
                parse_mode="HTML"
            )
        return
    
    state_manager.set_state(user_id, UserState.SETTING_REMINDER)
    
    await message.answer(
        f"⏰ <b>Создание напоминания</b>\n\n"
        f"Введите текст напоминания и время:\n\n"
        f"<b>Примеры:</b>\n"
        f"• Позвонить врачу в 15:00\n"
        f"• Встреча завтра в 10:30\n"
        f"• Купить продукты через 2 часа\n\n"
        f"<i>Для отмены используйте /cancel</i>",
        reply_markup=None,
        parse_mode="HTML"
    )

async def timer_command(message: Message) -> None:
    """Команда /timer - установить таймер"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "timer_command")
    
    theme = await get_user_theme(user_id)
    
    command_args = message.text.split(' ', 1)
    
    if len(command_args) > 1:
        timer_text = command_args[1].strip()
        
        timer_service = TimerService()
        success = await timer_service.parse_and_create_timer(user_id, timer_text)
        
        if success:
            await message.answer(
                f"⏱️ Таймер запущен!",
                reply_markup=get_main_menu_keyboard(theme),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Не удалось запустить таймер. Проверьте формат.",
                reply_markup=get_main_menu_keyboard(theme),
                parse_mode="HTML"
            )
        return
    
    state_manager.set_state(user_id, UserState.SETTING_TIMER)
    
    await message.answer(
        f"⏱️ <b>Установка таймера</b>\n\n"
        f"Введите время для таймера:\n\n"
        f"<b>Примеры:</b>\n"
        f"• 25 минут (помодоро)\n"
        f"• 1 час\n"
        f"• 30 секунд\n"
        f"• 2 часа 30 минут\n\n"
        f"<i>Для отмены используйте /cancel</i>",
        reply_markup=None,
        parse_mode="HTML"
    )
