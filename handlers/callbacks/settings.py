# ==========================================
# handlers/callbacks/settings_callbacks.py
# ==========================================

"""
Settings-related callback handlers
Обработчики коллбеков настроек
"""

from aiogram import types
from aiogram.types import CallbackQuery

from ..utils import log_action, update_user_activity, get_user_data, save_user_data
from ui.keyboards import get_main_menu_keyboard, get_settings_keyboard, get_theme_keyboard
from ui.messages import format_success_message
from ui.themes import get_user_theme, THEMES

async def handle_theme_select(callback: CallbackQuery) -> None:
    """
    Обработчик выбора темы
    Формат callback: theme_{theme_name}
    """
    user_id = callback.from_user.id
    theme_name = callback.data.split('_', 1)[1]
    
    # Обновляем активность
    await update_user_activity(user_id)
    
    # Логируем действие
    await log_action(user_id, "theme_select", {"theme": theme_name})
    
    # Проверяем, что тема существует
    if theme_name not in THEMES:
        await callback.answer("❌ Неизвестная тема", show_alert=True)
        return
    
    # Сохраняем новую тему
    await save_user_data(user_id, {'theme': theme_name})
    
    # Получаем новую тему
    new_theme = await get_user_theme(user_id)
    
    success_text = format_success_message(
        f"🎨 Тема изменена на: <b>{theme_name}</b>\n\n"
        f"Новое оформление применено ко всем сообщениям!"
    )
    
    try:
        await callback.message.edit_text(
            success_text,
            reply_markup=get_main_menu_keyboard(new_theme),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            success_text,
            reply_markup=get_main_menu_keyboard(new_theme),
            parse_mode="HTML"
        )
    
    await callback.answer(f"✅ Тема изменена: {theme_name}")

async def handle_notification_toggle(callback: CallbackQuery) -> None:
    """
    Обработчик переключения уведомлений
    """
    user_id = callback.from_user.id
    
    # Обновляем активность
    await update_user_activity(user_id)
    
    # Логируем действие
    await log_action(user_id, "notification_toggle")
    
    # Получаем текущие настройки
    user_data = await get_user_data(user_id)
    current_notifications = user_data.get('notifications', True)
    
    # Переключаем уведомления
    new_notifications = not current_notifications
    await save_user_data(user_id, {'notifications': new_notifications})
    
    # Получаем тему пользователя
    theme = await get_user_theme(user_id)
    
    status_text = "включены" if new_notifications else "выключены"
    emoji = "🔔" if new_notifications else "🔕"
    
    # Обновляем меню настроек
    user_data = await get_user_data(user_id)
    settings_text = f"{theme.get('settings_emoji', '⚙️')} <b>Настройки обновлены</b>\n\n"
    settings_text += f"{emoji} Уведомления: <b>{status_text}</b>\n\n"
    
    if new_notifications:
        settings_text += f"Вы будете получать:\n"
        settings_text += f"• Напоминания о задачах\n"
        settings_text += f"• Уведомления о достижениях\n"
        settings_text += f"• Мотивационные сообщения\n"
    else:
        settings_text += f"Уведомления отключены.\n"
        settings_text += f"Включите их снова для получения напоминаний."
    
    try:
        await callback.message.edit_text(
            settings_text,
            reply_markup=get_settings_keyboard(theme),
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    await callback.answer(f"{emoji} Уведомления {status_text}")

async def handle_language_select(callback: CallbackQuery) -> None:
    """
    Обработчик выбора языка
    Формат callback: lang_{language_code}
    """
    user_id = callback.from_user.id
    language = callback.data.split('_', 1)[1]
    
    # Обновляем активность
    await update_user_activity(user_id)
    
    # Логируем действие
    await log_action(user_id, "language_select", {"language": language})
    
    # Сохраняем язык
    await save_user_data(user_id, {'language': language})
    
    # Получаем тему пользователя
    theme = await get_user_theme(user_id)
    
    language_names = {
        'ru': 'Русский',
        'en': 'English',
        'es': 'Español',
        'fr': 'Français',
        'de': 'Deutsch'
    }
    
    language_name = language_names.get(language, language)
    
    await callback.answer(f"🌐 Язык изменен: {language_name}")
    
    # Пока что показываем уведомление (полная локализация будет позже)
    info_text = f"🌐 <b>Язык интерфейса</b>\n\n"
    info_text += f"Выбранный язык: <b>{language_name}</b>\n\n"
    info_text += f"<i>Примечание: Полная локализация будет добавлена в следующих обновлениях. "
    info_text += f"Пока что бот работает на русском языке.</i>"
    
    try:
        await callback.message.edit_text(
            info_text,
            reply_markup=get_main_menu_keyboard(theme),
            parse_mode="HTML"
        )
    except Exception:
        pass

async def handle_privacy_toggle(callback: CallbackQuery) -> None:
    """
    Обработчик переключения настроек приватности
    Формат callback: privacy_{setting}
    """
    user_id = callback.from_user.id
    privacy_setting = callback.data.split('_', 1)[1]
    
    # Обновляем активность
    await update_user_activity(user_id)
    
    # Логируем действие
    await log_action(user_id, "privacy_toggle", {"setting": privacy_setting})
    
    # Получаем текущие настройки
    user_data = await get_user_data(user_id)
    
    if privacy_setting == "profile":
        current_value = user_data.get('public_profile', True)
        new_value = not current_value
        await save_user_data(user_id, {'public_profile': new_value})
        
        status = "открытый" if new_value else "приватный"
        await callback.answer(f"👤 Профиль: {status}")
        
    elif privacy_setting == "stats":
        current_value = user_data.get('share_stats', True)
        new_value = not current_value
        await save_user_data(user_id, {'share_stats': new_value})
        
        status = "открытая" if new_value else "приватная"
        await callback.answer(f"📊 Статистика: {status}")
    
    # Обновляем меню настроек
    theme = await get_user_theme(user_id)
    user_data = await get_user_data(user_id)
    
    # Здесь можно обновить интерфейс настроек
    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(theme)
    )
