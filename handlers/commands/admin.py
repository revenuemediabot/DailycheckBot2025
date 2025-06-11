"""
Admin commands
Админские команды
"""

from aiogram import types
from aiogram.types import Message

from ..states import state_manager, UserState
from ..utils import log_action, update_user_activity, check_admin_permissions, get_all_users
from services.broadcast_service import BroadcastService
from services.analytics_service import AnalyticsService
from ui.keyboards import get_main_menu_keyboard
from ui.themes import get_user_theme
from ui.messages import format_error_message

async def broadcast_command(message: Message) -> None:
    """Команда /broadcast - рассылка всем пользователям"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "broadcast_command")
    
    theme = await get_user_theme(user_id)
    
    # Проверяем права админа
    if not await check_admin_permissions(user_id):
        await message.answer(
            format_error_message("❌ У вас нет прав для выполнения этой команды."),
            reply_markup=get_main_menu_keyboard(theme),
            parse_mode="HTML"
        )
        return
    
    command_args = message.text.split(' ', 1)
    
    if len(command_args) > 1:
        broadcast_text = command_args[1].strip()
        
        broadcast_service = BroadcastService()
        sent_count = await broadcast_service.send_broadcast(broadcast_text)
        
        await message.answer(
            f"📢 <b>Рассылка завершена</b>\n\n"
            f"Отправлено: {sent_count} пользователям",
            reply_markup=get_main_menu_keyboard(theme),
            parse_mode="HTML"
        )
        return
    
    # Интерактивная рассылка
    state_manager.set_state(user_id, UserState.BROADCAST_ADMIN)
    
    await message.answer(
        f"📢 <b>Создание рассылки</b>\n\n"
        f"Введите текст для рассылки всем пользователям:\n\n"
        f"<i>Для отмены используйте /cancel</i>",
        reply_markup=None,
        parse_mode="HTML"
    )

async def stats_global_command(message: Message) -> None:
    """Команда /stats_global - глобальная статистика"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "stats_global_command")
    
    theme = await get_user_theme(user_id)
    
    # Проверяем права админа
    if not await check_admin_permissions(user_id):
        await message.answer(
            format_error_message("❌ У вас нет прав для выполнения этой команды."),
            reply_markup=get_main_menu_keyboard(theme),
            parse_mode="HTML"
        )
        return
    
    # Получаем глобальную статистику
    analytics_service = AnalyticsService()
    global_stats = await analytics_service.get_global_statistics()
    
    stats_text = f"🌍 <b>Глобальная статистика</b>\n\n"
    
    if global_stats:
        stats_text += f"👥 <b>Пользователи:</b>\n"
        stats_text += f"• Всего: {global_stats.get('total_users', 0)}\n"
        stats_text += f"• Активные (сегодня): {global_stats.get('active_today', 0)}\n"
        stats_text += f"• Активные (неделя): {global_stats.get('active_week', 0)}\n\n"
        
        stats_text += f"📝 <b>Задачи:</b>\n"
        stats_text += f"• Всего создано: {global_stats.get('total_tasks', 0)}\n"
        stats_text += f"• Выполнено: {global_stats.get('completed_tasks', 0)}\n"
        stats_text += f"• За сегодня: {global_stats.get('tasks_today', 0)}\n\n"
        
        stats_text += f"🏆 <b>Достижения:</b>\n"
        stats_text += f"• Всего выдано: {global_stats.get('total_achievements', 0)}\n\n"
        
        stats_text += f"📊 <b>Система:</b>\n"
        stats_text += f"• Команд обработано: {global_stats.get('commands_processed', 0)}\n"
        stats_text += f"• Ошибок: {global_stats.get('errors_count', 0)}\n"
    else:
        stats_text += "Нет данных для отображения"
    
    await message.answer(
        stats_text,
        reply_markup=get_main_menu_keyboard(theme),
        parse_mode="HTML"
    )
