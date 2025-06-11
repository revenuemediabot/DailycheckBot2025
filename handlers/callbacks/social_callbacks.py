# ==========================================
# handlers/callbacks/social_callbacks.py
# ==========================================

"""
Social features callback handlers
Обработчики коллбеков социальных функций
"""

from aiogram import types
from aiogram.types import CallbackQuery

from ..utils import log_action, update_user_activity, get_user_data, add_xp
from services.social_service import SocialService
from ui.keyboards import get_main_menu_keyboard, get_friends_keyboard
from ui.messages import format_success_message
from ui.themes import get_user_theme

async def handle_friend_accept(callback: CallbackQuery) -> None:
    """
    Обработчик принятия запроса в друзья
    Формат callback: accept_friend_{friend_id}
    """
    user_id = callback.from_user.id
    friend_id = callback.data.split('_', 2)[2]
    
    # Обновляем активность
    await update_user_activity(user_id)
    
    # Логируем действие
    await log_action(user_id, "friend_accept", {"friend_id": friend_id})
    
    # Получаем тему пользователя
    theme = await get_user_theme(user_id)
    
    # Принимаем запрос
    social_service = SocialService()
    result = await social_service.accept_friend_request(user_id, friend_id)
    
    if result['success']:
        # Добавляем XP за новую дружбу
        xp_result = await add_xp(user_id, 15)
        
        success_text = format_success_message(
            f"👥 <b>Новый друг добавлен!</b>\n\n"
            f"Теперь вы друзья с {result['friend_name']}\n\n"
            f"⚡ +15 XP за расширение социальных связей"
        )
        
        if xp_result['level_up']:
            success_text += f"\n\n🎉 Новый уровень: {xp_result['new_level']}"
        
        await callback.answer("✅ Запрос принят", show_alert=False)
        
        # Обновляем список друзей
        friends = await social_service.get_friends(user_id)
        pending_requests = await social_service.get_pending_requests(user_id)
        
        friends_text = f"{theme.get('friends_emoji', '👥')} <b>Список друзей обновлен</b>\n\n"
        
        if friends:
            for i, friend in enumerate(friends[-3:], 1):  # Показываем последних 3
                status = "🟢" if friend.get('online') else "⚫"
                friends_text += f"{i}. {status} <b>{friend['name']}</b>\n"
                friends_text += f"   📊 Уровень: {friend.get('level', 1)}\n\n"
        
        friends_text += f"<b>📈 Всего друзей:</b> {len(friends)}"
        
        try:
            await callback.message.edit_text(
                friends_text,
                reply_markup=get_friends_keyboard(friends, pending_requests, theme),
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    else:
        await callback.answer(
            f"❌ Не удалось принять запрос: {result['error']}", 
            show_alert=True
        )

async def handle_friend_decline(callback: CallbackQuery) -> None:
    """
    Обработчик отклонения запроса в друзья
    Формат callback: decline_friend_{friend_id}
    """
    user_id = callback.from_user.id
    friend_id = callback.data.split('_', 2)[2]
    
    # Обновляем активность
    await update_user_activity(user_id)
    
    # Логируем действие
    await log_action(user_id, "friend_decline", {"friend_id": friend_id})
    
    # Получаем тему пользователя
    theme = await get_user_theme(user_id)
    
    # Отклоняем запрос
    social_service = SocialService()
    result = await social_service.decline_friend_request(user_id, friend_id)
    
    if result['success']:
        await callback.answer("❌ Запрос отклонен", show_alert=False)
        
        # Обновляем список запросов
        friends = await social_service.get_friends(user_id)
        pending_requests = await social_service.get_pending_requests(user_id)
        
        try:
            await callback.message.edit_reply_markup(
                reply_markup=get_friends_keyboard(friends, pending_requests, theme)
            )
        except Exception:
            pass
    
    else:
        await callback.answer(
            f"❌ Не удалось отклонить запрос: {result['error']}", 
            show_alert=True
        )

async def handle_view_friend_stats(callback: CallbackQuery) -> None:
    """
    Обработчик просмотра статистики друга
    Формат callback: friend_stats_{friend_id}
    """
    user_id = callback.from_user.id
    friend_id = callback.data.split('_', 2)[2]
    
    # Обновляем активность
    await update_user_activity(user_id)
    
    # Логируем действие
    await log_action(user_id, "view_friend_stats", {"friend_id": friend_id})
    
    # Получаем тему пользователя
    theme = await get_user_theme(user_id)
    
    # Получаем статистику друга
    social_service = SocialService()
    friend_stats = await social_service.get_friend_stats(user_id, friend_id)
    
    if not friend_stats:
        await callback.answer("❌ Статистика недоступна", show_alert=True)
        return
    
    # Формируем статистику
    stats_text = f"{theme.get('stats_emoji', '📊')} <b>Статистика друга</b>\n\n"
    stats_text += f"👤 <b>{friend_stats['name']}</b>\n\n"
    
    # Уровень и XP
    level = friend_stats.get('level', 1)
    xp = friend_stats.get('xp', 0)
    
    level_names = [
        "🌱 Новичок", "🌿 Ученик", "🍃 Практикант", "🌳 Энтузиаст",
        "🎯 Целеустремленный", "⭐ Звезда", "🚀 Ракета", "💎 Алмаз",
        "👑 Король", "🦅 Орел", "🔥 Огонь", "⚡ Молния",
        "🌟 Супернова", "🏆 Чемпион", "🎖️ Легенда", "👹 Божественный"
    ]
    
    level_name = level_names[min(level - 1, len(level_names) - 1)]
    
    stats_text += f"<b>{level_name}</b> (уровень {level})\n"
    stats_text += f"⚡ XP: {xp}\n"
    stats_text += f"🔥 Серия: {friend_stats.get('streak', 0)} дней\n\n"
    
    # Задачи
    stats_text += f"<b>📝 Задачи:</b>\n"
    stats_text += f"• Всего: {friend_stats.get('total_tasks', 0)}\n"
    stats_text += f"• Выполнено: {friend_stats.get('completed_tasks', 0)}\n"
    
    completion_rate = 0
    if friend_stats.get('total_tasks', 0) > 0:
        completion_rate = (friend_stats.get('completed_tasks', 0) / friend_stats.get('total_tasks', 1)) * 100
    
    stats_text += f"• Процент: {completion_rate:.1f}%\n\n"
    
    # Достижения
    achievements_count = len(friend_stats.get('achievements', []))
    stats_text += f"<b>🏆 Достижения:</b> {achievements_count}/10\n\n"
    
    # Сравнение с пользователем
    user_data = await get_user_data(user_id)
    user_level = user_data.get('level', 1)
    user_xp = user_data.get('xp', 0)
    
    stats_text += f"<b>⚖️ Сравнение с вами:</b>\n"
    
    if level > user_level:
        stats_text += f"🔺 На {level - user_level} уровней выше\n"
    elif level < user_level:
        stats_text += f"🔻 На {user_level - level} уровней ниже\n"
    else:
        stats_text += f"🟰 Одинаковый уровень\n"
    
    xp_diff = xp - user_xp
    if xp_diff > 0:
        stats_text += f"⚡ На {xp_diff} XP больше\n"
    elif xp_diff < 0:
        stats_text += f"⚡ На {abs(xp_diff)} XP меньше\n"
    else:
        stats_text += f"⚡ Одинаковое количество XP\n"
    
    from ui.keyboards import get_friend_stats_keyboard
    
    try:
        await callback.message.edit_text(
            stats_text,
            reply_markup=get_friend_stats_keyboard(friend_id, theme),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            stats_text,
            reply_markup=get_friend_stats_keyboard(friend_id, theme),
            parse_mode="HTML"
        )
    
    await callback.answer()

async def handle_send_motivation(callback: CallbackQuery) -> None:
    """
    Обработчик отправки мотивации друзьям
    Формат callback: send_motivation_{friend_id}
    """
    user_id = callback.from_user.id
    friend_id = callback.data.split('_', 2)[2]
    
    # Обновляем активность
    await update_user_activity(user_id)
    
    # Логируем действие
    await log_action(user_id, "send_motivation", {"friend_id": friend_id})
    
    # Отправляем мотивацию
    social_service = SocialService()
    result = await social_service.send_motivation_to_friend(user_id, friend_id)
    
    if result['success']:
        await callback.answer(
            f"💪 Мотивация отправлена {result['friend_name']}!", 
            show_alert=True
        )
    else:
        await callback.answer(
            f"❌ Не удалось отправить мотивацию", 
            show_alert=True
        )

async def handle_challenge_friend(callback: CallbackQuery) -> None:
    """
    Обработчик вызова друга на соревнование
    Формат callback: challenge_{friend_id}
    """
    user_id = callback.from_user.id
    friend_id = callback.data.split('_', 1)[1]
    
    # Обновляем активность
    await update_user_activity(user_id)
    
    # Логируем действие
    await log_action(user_id, "challenge_friend", {"friend_id": friend_id})
    
    await callback.answer(
        "🏁 Функция соревнований будет добавлена в следующем обновлении!", 
        show_alert=True
    )
