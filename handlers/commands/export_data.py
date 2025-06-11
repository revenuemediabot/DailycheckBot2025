"""
Data export commands
Команды экспорта данных
"""

from aiogram import types
from aiogram.types import Message, BufferedInputFile
import json
import csv
import io

from ..utils import log_action, update_user_activity, get_user_data
from services.export_service import ExportService
from ui.keyboards import get_main_menu_keyboard
from ui.themes import get_user_theme

async def export_command(message: Message) -> None:
    """Команда /export - экспорт данных"""
    user_id = message.from_user.id
    
    await update_user_activity(user_id)
    await log_action(user_id, "export_command")
    
    theme = await get_user_theme(user_id)
    
    # Получаем данные для экспорта
    export_service = ExportService()
    user_data = await export_service.get_user_export_data(user_id)
    
    if not user_data:
        await message.answer(
            f"❌ Нет данных для экспорта.",
            reply_markup=get_main_menu_keyboard(theme),
            parse_mode="HTML"
        )
        return
    
    # Создаем JSON файл
    json_data = json.dumps(user_data, ensure_ascii=False, indent=2)
    json_file = BufferedInputFile(
        json_data.encode('utf-8'),
        filename=f"dailycheck_export_{user_id}.json"
    )
    
    await message.answer_document(
        json_file,
        caption=f"📊 <b>Экспорт ваших данных</b>\n\n"
               f"Файл содержит:\n"
               f"• Все ваши задачи\n"
               f"• Статистику и прогресс\n"
               f"• Достижения и цели\n"
               f"• Настройки профиля\n\n"
               f"<i>Данные в формате JSON</i>",
        reply_markup=get_main_menu_keyboard(theme),
        parse_mode="HTML"
    )
