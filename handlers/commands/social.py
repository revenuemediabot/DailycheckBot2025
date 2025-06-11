"""
Social features commands
Команды социальных функций
"""

from aiogram import types
from aiogram.types import Message

from ..states import state_manager, UserState
from ..utils import log_action, update_user_activity, get_user_data
from services.social_service import SocialService
from ui.keyboards import get_main_menu_keyboard, get_friends_keyboard
from ui.themes import get_user_theme

async def friends_command(message: Message) -> None:
    """Команда /friends - список друзей"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "friends_command")
    
    theme = await get_user_theme(user_id)
    social_service = SocialService()
    
    friends = await social_service.get_friends(user_id)
    
    friends_text = f"{theme.get('friends_emoji', '👥')} <b>Ваши друзья</b>\n\n"
    
    if not friends:
        friends_text += "У вас пока нет друзей.\n\n"
        friends_text += "Добавляйте друзей чтобы:\n"
        friends_text += "• Сравнивать прогресс\n"
        friends_text += "• Мотивировать друг друга\n"
        friends_text += "• Участвовать в челленджах\n\n"
        friends_text += "<i>Используйте /add_friend для добавления</i>"
    else:
        for friend in friends:
            status = "🟢" if friend.get('online') else "⚫"
            friends_text += f"{status} <b>{friend['name']}</b>\n"
            friends_text += f"   Уровень: {friend.get('level', 1)}\n"
            friends_text += f"   XP: {friend.get('xp', 0)}\n\n"
    
    await message.answer(
        friends_text,
        reply_markup=get_friends_keyboard(friends, theme),
        parse_mode="HTML"
    )

async def add_friend_command(message: Message) -> None:
    """Команда /add_friend - добавить друга"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "add_friend_command")
    
    theme = await get_user_theme(user_id)
    
    command_args = message.text.split(' ', 1)
    
    if len(command_args) > 1:
        friend_input = command_args[1].strip()
        
        social_service = SocialService()
        success = await social_service.add_friend_by_input(user_id, friend_input)
        
        if success:
            await message.answer(
                f"✅ Запрос на добавление в друзья отправлен!",
                reply_markup=get_main_menu_keyboard(theme),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Не удалось найти пользователя или отправить запрос.",
                reply_markup=get_main_menu_keyboard(theme),
                parse_mode="HTML"
            )
        return
    
    # Интерактивное добавление
    state_manager.set_state(user_id, UserState.ADDING_FRIEND)
    
    await message.answer(
        f"{theme.get('add_friend_emoji', '➕')} <b>Добавление друга</b>\n\n"
        f"Введите ID пользователя или @username:\n\n"
        f"<i>Для отмены используйте /cancel</i>",
        reply_markup=None,
        parse_mode="HTML"
    )

async def myid_command(message: Message) -> None:
    """Команда /myid - узнать свой ID"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "myid_command")
    
    theme = await get_user_theme(user_id)
    
    await message.answer(
        f"{theme.get('id_emoji', '🆔')} <b>Ваш ID</b>\n\n"
        f"<code>{user_id}</code>\n\n"
        f"Поделитесь этим ID с друзьями, чтобы они могли вас добавить!",
        reply_markup=get_main_menu_keyboard(theme),
        parse_mode="HTML"
    )
