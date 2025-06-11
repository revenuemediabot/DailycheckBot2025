# handlers/commands/tasks.py

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

# Импорты сервисов
from services.task_service import get_task_service, TaskService, Task, AchievementSystem
from services.data_service import get_data_service, DataService

logger = logging.getLogger(__name__)

# Константы для ConversationHandler
WAITING_TASK_TITLE, WAITING_TASK_PRIORITY, WAITING_TASK_DEADLINE = range(3)
EDIT_TASK_SELECT, EDIT_TASK_FIELD, EDIT_TASK_VALUE = range(3, 6)

class TaskHandlers:
    """Класс для обработки команд управления задачами с полной интеграцией сервисов"""
    
    def __init__(self):
        self.task_service = get_task_service()
        self.data_service = get_data_service()
        logger.info("✅ TaskHandlers инициализирован с сервисами")
    
    async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список задач пользователя"""
        try:
            user_id = update.effective_user.id
            
            # Получаем задачи пользователя через сервис
            tasks = await self.task_service.get_user_tasks(user_id, status_filter="active")
            
            if not tasks:
                await update.message.reply_text(
                    "📝 **У вас пока нет активных задач!**\n\n"
                    "Создайте первую задачу:\n"
                    "• Кнопка '➕ Добавить задачу'\n"
                    "• Команда `/add`\n"
                    "• Быстро: `/addtask Название задачи`",
                    parse_mode='Markdown'
                )
                return
            
            # Формируем красивый список задач
            message = f"📋 **Ваши активные задачи ({len(tasks)}):**\n\n"
            
            # Подсчитываем выполненные сегодня
            completed_today = len([t for t in tasks if t.is_completed_today()])
            completion_percentage = (completed_today / len(tasks)) * 100
            
            message += f"📊 **Прогресс сегодня:** {completed_today}/{len(tasks)} ({completion_percentage:.0f}%)\n\n"
            
            # Группируем по приоритету
            high_priority = [t for t in tasks if t.priority == "high"]
            medium_priority = [t for t in tasks if t.priority == "medium"]
            low_priority = [t for t in tasks if t.priority == "low"]
            
            for priority_group, emoji, title in [
                (high_priority, "🔴", "Высокий приоритет"),
                (medium_priority, "🟡", "Средний приоритет"),
                (low_priority, "🟢", "Низкий приоритет")
            ]:
                if priority_group:
                    message += f"{emoji} **{title}:**\n"
                    for task in priority_group[:5]:  # Показываем первые 5 в каждой группе
                        status = "✅" if task.is_completed_today() else "⭕"
                        streak_info = f" 🔥{task.current_streak}" if task.current_streak > 0 else ""
                        message += f"{status} `{task.task_id[:8]}` {task.title[:30]}{streak_info}\n"
                    
                    if len(priority_group) > 5:
                        message += f"... и еще {len(priority_group) - 5}\n"
                    message += "\n"
            
            # Добавляем кнопки управления
            keyboard = [
                [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task_dialog")],
                [InlineKeyboardButton("✏️ Редактировать", callback_data="edit_tasks_menu"),
                 InlineKeyboardButton("📊 Статистика", callback_data="task_stats_detailed")],
                [InlineKeyboardButton("🔄 Обновить", callback_data="tasks_refresh")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Ошибка в tasks_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при получении списка задач.")
    
    async def addtask_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавить новую задачу"""
        try:
            user_id = update.effective_user.id
            
            # Получаем текст задачи из аргументов команды
            if context.args:
                task_title = " ".join(context.args)
                
                if len(task_title) > 100:
                    await update.message.reply_text("❌ Название задачи слишком длинное (максимум 100 символов).")
                    return
                
                if len(task_title) < 3:
                    await update.message.reply_text("❌ Название задачи слишком короткое (минимум 3 символа).")
                    return
                
                # Создаем задачу через сервис
                task_id = await self.task_service.create_task(
                    user_id=user_id,
                    title=task_title,
                    category="personal",
                    priority="medium"
                )
                
                if task_id:
                    # Получаем созданную задачу для отображения
                    task = await self.task_service.get_task(user_id, task_id)
                    
                    # Предлагаем настроить дополнительные параметры
                    keyboard = [
                        [InlineKeyboardButton("🔴 Высокий приоритет", callback_data=f"set_priority_high_{task_id}"),
                         InlineKeyboardButton("🟡 Средний", callback_data=f"set_priority_medium_{task_id}"),
                         InlineKeyboardButton("🟢 Низкий", callback_data=f"set_priority_low_{task_id}")],
                        [InlineKeyboardButton("💼 Категория", callback_data=f"set_category_{task_id}"),
                         InlineKeyboardButton("⏱️ Время", callback_data=f"set_time_{task_id}")],
                        [InlineKeyboardButton("✅ Готово", callback_data="close_menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"✅ **Задача создана!**\n\n"
                        f"📝 {task_title}\n"
                        f"🆔 ID: `{task_id[:8]}`\n"
                        f"🟡 Приоритет: средний\n"
                        f"📂 Категория: личное\n\n"
                        f"💡 Хотите настроить дополнительные параметры?",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text("❌ Ошибка создания задачи.")
                
            else:
                # Начинаем диалог добавления задачи
                await update.message.reply_text(
                    "📝 **Добавление новой задачи**\n\n"
                    "💡 **Быстро:** `/addtask Название задачи`\n\n"
                    "Или введите название задачи для детальной настройки:"
                )
                return WAITING_TASK_TITLE
                
        except Exception as e:
            logger.error(f"❌ Ошибка в addtask_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при добавлении задачи.")
    
    async def settasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Быстрая настройка списка задач"""
        try:
            user_id = update.effective_user.id
            
            if not context.args:
                await update.message.reply_text(
                    "📋 **Быстрая настройка задач**\n\n"
                    "**Формат:** `/settasks задача1; задача2; задача3`\n\n"
                    "**Пример:** \n"
                    "`/settasks Выпить воду; Сделать зарядку; Прочитать книгу`\n\n"
                    "Все задачи будут добавлены со средним приоритетом в категории 'личное'.",
                    parse_mode='Markdown'
                )
                return
            
            # Парсим задачи из аргументов
            tasks_text = " ".join(context.args)
            task_titles = [title.strip() for title in tasks_text.split(';') if title.strip()]
            
            if not task_titles:
                await update.message.reply_text("❌ Не удалось распознать задачи. Проверьте формат.")
                return
            
            # Ограничиваем количество задач
            if len(task_titles) > 10:
                task_titles = task_titles[:10]
                await update.message.reply_text("⚠️ Ограничено до 10 задач за раз.")
            
            # Создаем задачи через сервис
            created_task_ids = await self.task_service.bulk_create_tasks(
                user_id=user_id,
                task_titles=task_titles,
                default_category="personal"
            )
            
            if created_task_ids:
                # Формируем ответ
                message = f"✅ **Создано {len(created_task_ids)} задач:**\n\n"
                
                for i, (task_id, title) in enumerate(zip(created_task_ids, task_titles), 1):
                    message += f"{i}. `{task_id[:8]}` {title}\n"
                
                message += f"\n💡 Используйте /tasks для просмотра и управления."
                
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Не удалось создать задачи.")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в settasks_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при создании задач.")
    
    async def edit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Редактирование задач"""
        try:
            user_id = update.effective_user.id
            
            # Получаем задачи пользователя
            tasks = await self.task_service.get_user_tasks(user_id, status_filter="active")
            
            if not tasks:
                await update.message.reply_text(
                    "📝 **У вас нет активных задач для редактирования.**\n\n"
                    "Создайте задачи с помощью:\n"
                    "• /add - детальное создание\n"
                    "• /addtask - быстрое создание"
                )
                return
            
            # Создаем клавиатуру с задачами
            keyboard = []
            for task in tasks[:10]:  # Показываем первые 10 задач
                status = "✅" if task.is_completed_today() else "⭕"
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(task.priority, "🟡")
                
                button_text = f"{status} {priority_emoji} {task.title[:25]}"
                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f"edit_task_{task.task_id}"
                )])
            
            if len(tasks) > 10:
                keyboard.append([InlineKeyboardButton(f"... и еще {len(tasks) - 10} задач", callback_data="show_more_tasks")])
            
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="close_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✏️ **Выберите задачу для редактирования:**\n\n"
                f"📊 Всего активных задач: {len(tasks)}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка в edit_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при загрузке задач для редактирования.")
    
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сброс всех задач"""
        try:
            user_id = update.effective_user.id
            
            # Получаем количество задач
            tasks = await self.task_service.get_user_tasks(user_id)
            task_count = len(tasks)
            
            if task_count == 0:
                await update.message.reply_text("📝 У вас нет задач для сброса.")
                return
            
            # Подтверждение действия
            keyboard = [
                [InlineKeyboardButton("📦 Архивировать все", callback_data=f"confirm_archive_{user_id}")],
                [InlineKeyboardButton("🗑️ Удалить все", callback_data=f"confirm_delete_{user_id}")],
                [InlineKeyboardButton("❌ Отмена", callback_data="close_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"⚠️ **Внимание!**\n\n"
                f"У вас {task_count} задач.\n\n"
                f"**Архивирование** - задачи будут скрыты, но сохранены\n"
                f"**Удаление** - задачи будут удалены навсегда\n\n"
                f"Что вы хотите сделать?",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка в reset_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка.")
    
    async def addsub_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавить подзадачу"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "📝 **Добавление подзадачи**\n\n"
                    "**Формат:** `/addsub [ID_задачи] [название_подзадачи]`\n\n"
                    "**Пример:** `/addsub abc123 Купить хлеб`\n\n"
                    "💡 ID задачи можно узнать в /tasks"
                )
                return
            
            if len(context.args) < 2:
                await update.message.reply_text("❌ Укажите ID задачи и название подзадачи.")
                return
            
            user_id = update.effective_user.id
            task_id_input = context.args[0]
            subtask_title = " ".join(context.args[1:])
            
            # Ищем задачу по частичному ID
            all_tasks = await self.task_service.get_user_tasks(user_id)
            matching_task = None
            
            for task in all_tasks:
                if task.task_id.startswith(task_id_input) or task_id_input in task.task_id:
                    matching_task = task
                    break
            
            if not matching_task:
                await update.message.reply_text(
                    f"❌ Задача с ID `{task_id_input}` не найдена.\n\n"
                    f"Используйте /tasks для просмотра актуальных ID.",
                    parse_mode='Markdown'
                )
                return
            
            # Создаем подзадачу через сервис
            subtask_id = await self.task_service.add_subtask(
                user_id=user_id,
                task_id=matching_task.task_id,
                subtitle=subtask_title
            )
            
            if subtask_id:
                await update.message.reply_text(
                    f"✅ **Подзадача добавлена!**\n\n"
                    f"📝 {subtask_title}\n"
                    f"🔗 К задаче: {matching_task.title}\n"
                    f"🆔 ID подзадачи: `{subtask_id[:8]}`\n\n"
                    f"💡 Управляйте подзадачами через детальный просмотр задачи в /tasks",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Ошибка при добавлении подзадачи.")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в addsub_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при добавлении подзадачи.")
    
    async def complete_task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отметить задачу как выполненную"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "✅ **Завершение задачи**\n\n"
                    "**Формат:** `/complete [ID_задачи]`\n\n"
                    "**Пример:** `/complete abc123`\n\n"
                    "💡 ID задачи можно узнать в /tasks"
                )
                return
            
            user_id = update.effective_user.id
            task_id_input = context.args[0]
            
            # Ищем задачу по частичному ID
            all_tasks = await self.task_service.get_user_tasks(user_id)
            matching_task = None
            
            for task in all_tasks:
                if task.task_id.startswith(task_id_input) or task_id_input in task.task_id:
                    matching_task = task
                    break
            
            if not matching_task:
                await update.message.reply_text(
                    f"❌ Задача с ID `{task_id_input}` не найдена.",
                    parse_mode='Markdown'
                )
                return
            
            # Проверяем, не выполнена ли уже
            if matching_task.is_completed_today():
                await update.message.reply_text(
                    f"✅ Задача '{matching_task.title}' уже выполнена сегодня!\n\n"
                    f"🔥 Текущий streak: {matching_task.current_streak} дней"
                )
                return
            
            # Выполняем задачу через сервис
            success = await self.task_service.complete_task(
                user_id=user_id,
                task_id=matching_task.task_id
            )
            
            if success:
                # Получаем обновленную задачу для отображения
                updated_task = await self.task_service.get_task(user_id, matching_task.task_id)
                
                await update.message.reply_text(
                    f"🎉 **Поздравляем!**\n\n"
                    f"✅ {updated_task.title}\n"
                    f"🔥 Streak: {updated_task.current_streak} дней\n"
                    f"⭐ +{updated_task.xp_value} XP\n\n"
                    f"💪 Отличная работа! Продолжайте в том же духе!",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Ошибка при завершении задачи.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в complete_task_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при завершении задачи.")
    
    # ===== ОБРАБОТЧИКИ ДЛЯ CONVERSATIONHANDLER =====
    
    async def handle_task_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка названия новой задачи"""
        try:
            task_title = update.message.text.strip()
            
            if len(task_title) > 100:
                await update.message.reply_text(
                    "❌ Название задачи слишком длинное (максимум 100 символов).\n"
                    "Введите более короткое название:"
                )
                return WAITING_TASK_TITLE
            
            if len(task_title) < 3:
                await update.message.reply_text(
                    "❌ Название задачи слишком короткое (минимум 3 символа).\n"
                    "Попробуйте еще раз:"
                )
                return WAITING_TASK_TITLE
            
            # Сохраняем название в контексте
            context.user_data['new_task_title'] = task_title
            
            # Просим выбрать приоритет
            keyboard = [
                [InlineKeyboardButton("🔴 Высокий", callback_data="priority_high")],
                [InlineKeyboardButton("🟡 Средний", callback_data="priority_medium")],
                [InlineKeyboardButton("🟢 Низкий", callback_data="priority_low")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"📝 **Задача:** {task_title}\n\n"
                f"Выберите приоритет:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return WAITING_TASK_PRIORITY
            
        except Exception as e:
            logger.error(f"❌ Ошибка в handle_task_title: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте еще раз.")
            return ConversationHandler.END
    
    # ===== CALLBACK ОБРАБОТЧИКИ ДЛЯ КНОПОК =====
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки"""
        try:
            query = update.callback_query
            await query.answer()
            
            data = query.data
            user_id = update.effective_user.id
            
            if data == "close_menu":
                await query.edit_message_text("✅ Меню закрыто.")
                
            elif data.startswith("set_priority_"):
                await self._handle_priority_change(query, data, user_id)
                
            elif data.startswith("edit_task_"):
                await self._handle_task_edit(query, data, user_id)
                
            elif data.startswith("confirm_archive_"):
                await self._handle_archive_confirm(query, user_id)
                
            elif data.startswith("confirm_delete_"):
                await self._handle_delete_confirm(query, user_id)
                
            elif data == "tasks_refresh":
                await self._handle_tasks_refresh(query, user_id)
                
            elif data == "task_stats_detailed":
                await self._handle_task_stats(query, user_id)
                
        except Exception as e:
            logger.error(f"❌ Ошибка в handle_callback_query: {e}")
            await query.edit_message_text("❌ Произошла ошибка.")
    
    async def _handle_priority_change(self, query, data: str, user_id: int):
        """Обработка изменения приоритета"""
        try:
            parts = data.split("_")
            priority = parts[2]  # high, medium, low
            task_id = parts[3]
            
            success = await self.task_service.update_task(
                user_id=user_id,
                task_id=task_id,
                priority=priority
            )
            
            if success:
                priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                priority_names = {"high": "высокий", "medium": "средний", "low": "низкий"}
                
                await query.edit_message_text(
                    f"✅ **Приоритет изменен!**\n\n"
                    f"🎯 Новый приоритет: {priority_emoji[priority]} {priority_names[priority]}",
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text("❌ Ошибка изменения приоритета.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка изменения приоритета: {e}")
            await query.edit_message_text("❌ Произошла ошибка.")
    
    async def _handle_task_edit(self, query, data: str, user_id: int):
        """Обработка редактирования задачи"""
        try:
            task_id = data.replace("edit_task_", "")
            
            # Получаем задачу
            task = await self.task_service.get_task(user_id, task_id)
            if not task:
                await query.edit_message_text("❌ Задача не найдена.")
                return
            
            # Показываем меню редактирования
            await self._show_edit_task_menu(query, task, user_id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка редактирования задачи: {e}")
            await query.edit_message_text("❌ Произошла ошибка.")
    
    async def _show_edit_task_menu(self, query, task: Task, user_id: int):
        """Показать меню редактирования конкретной задачи"""
        try:
            status = "✅ Выполнена сегодня" if task.is_completed_today() else "⭕ Не выполнена сегодня"
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            category_emoji = {
                "work": "💼", "health": "🏃", "learning": "📚",
                "personal": "👤", "finance": "💰"
            }
            
            keyboard = [
                [InlineKeyboardButton("🎯 Изменить приоритет", callback_data=f"edit_priority_{task.task_id}")],
                [InlineKeyboardButton("📂 Изменить категорию", callback_data=f"edit_category_{task.task_id}")],
                [InlineKeyboardButton("➕ Добавить подзадачу", callback_data=f"add_subtask_{task.task_id}")],
                [InlineKeyboardButton("✅ Выполнить" if not task.is_completed_today() else "❌ Отменить выполнение", 
                                    callback_data=f"toggle_complete_{task.task_id}")],
                [InlineKeyboardButton("📊 Статистика", callback_data=f"task_stats_{task.task_id}")],
                [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_task_{task.task_id}")],
                [InlineKeyboardButton("⬅️ Назад к списку", callback_data="back_to_tasks")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = f"✏️ **Редактирование задачи:**\n\n"
            message += f"📝 **Название:** {task.title}\n"
            message += f"🎯 **Приоритет:** {priority_emoji.get(task.priority, '🟡')} {task.priority}\n"
            message += f"📂 **Категория:** {category_emoji.get(task.category, '📋')} {task.category}\n"
            message += f"📊 **Статус:** {status}\n"
            message += f"🔥 **Streak:** {task.current_streak} дней\n"
            message += f"📅 **Создана:** {datetime.fromisoformat(task.created_at).strftime('%d.%m.%Y')}\n"
            
            if task.subtasks:
                message += f"📋 **Подзадачи:** {task.subtasks_completed_count}/{task.subtasks_total_count}\n"
            
            if task.tags:
                message += f"🏷️ **Теги:** {', '.join(task.tags)}\n"
            
            message += f"\nВыберите действие:"
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа меню редактирования: {e}")
            await query.edit_message_text("❌ Произошла ошибка.")
    
    async def _handle_archive_confirm(self, query, user_id: int):
        """Обработка подтверждения архивирования"""
        try:
            success = await self.task_service.reset_user_tasks(user_id, archive=True)
            
            if success:
                await query.edit_message_text(
                    "📦 **Все задачи архивированы!**\n\n"
                    "Задачи скрыты, но сохранены.\n"
                    "Создавайте новые задачи для продолжения работы!"
                )
            else:
                await query.edit_message_text("❌ Ошибка архивирования задач.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка архивирования: {e}")
            await query.edit_message_text("❌ Произошла ошибка.")
    
    async def _handle_delete_confirm(self, query, user_id: int):
        """Обработка подтверждения удаления"""
        try:
            success = await self.task_service.reset_user_tasks(user_id, archive=False)
            
            if success:
                await query.edit_message_text(
                    "🗑️ **Все задачи удалены!**\n\n"
                    "Начните заново с создания новых задач.\n"
                    "Используйте /add или /addtask для создания."
                )
            else:
                await query.edit_message_text("❌ Ошибка удаления задач.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка удаления: {e}")
            await query.edit_message_text("❌ Произошла ошибка.")
    
    async def _handle_tasks_refresh(self, query, user_id: int):
        """Обработка обновления списка задач"""
        try:
            # Имитируем команду /tasks
            # Создаем объект Update для переиспользования логики
            fake_update = type('Update', (), {
                'effective_user': type('User', (), {'id': user_id})(),
                'message': type('Message', (), {
                    'reply_text': lambda text, **kwargs: query.edit_message_text(text, **kwargs)
                })()
            })()
            
            await self.tasks_command(fake_update, None)
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления списка: {e}")
            await query.edit_message_text("❌ Ошибка обновления списка задач.")
    
    async def _handle_task_stats(self, query, user_id: int):
        """Обработка показа статистики задач"""
        try:
            stats = await self.task_service.get_user_task_stats(user_id)
            
            if not stats:
                await query.edit_message_text("📊 Нет данных для статистики.")
                return
            
            message = f"📊 **Детальная статистика задач:**\n\n"
            
            # Общая статистика
            message += f"📈 **Общее:**\n"
            message += f"• Всего задач: {stats['total_tasks']}\n"
            message += f"• Активных: {stats['active_tasks']}\n"
            message += f"• Выполнено сегодня: {stats['completed_today']}\n"
            message += f"• Процент выполнения: {stats['completion_rate_today']:.1f}%\n\n"
            
            # Streak статистика
            if 'streaks' in stats:
                streaks = stats['streaks']
                message += f"🔥 **Streak'и:**\n"
                message += f"• Максимальный: {streaks['max']} дней\n"
                message += f"• Средний: {streaks['average']:.1f} дней\n"
                message += f"• Задач со streak: {streaks['total_with_streak']}\n\n"
            
            # Статистика по категориям
            if 'by_category' in stats:
                message += f"📂 **По категориям:**\n"
                category_emoji = {
                    "work": "💼", "health": "🏃", "learning": "📚",
                    "personal": "👤", "finance": "💰"
                }
                
                for category, cat_stats in stats['by_category'].items():
                    emoji = category_emoji.get(category, "📋")
                    rate = (cat_stats['completed_today'] / cat_stats['active'] * 100) if cat_stats['active'] > 0 else 0
                    message += f"• {emoji} {category}: {cat_stats['completed_today']}/{cat_stats['active']} ({rate:.0f}%)\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад к задачам", callback_data="tasks_refresh")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа статистики: {e}")
            await query.edit_message_text("❌ Ошибка загрузки статистики.")


# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====

# Создаем глобальный экземпляр обработчиков
task_handlers = TaskHandlers()

# ===== ФУНКЦИИ ДЛ�Я РЕГИСТРАЦИИ (ОБРАТНАЯ СОВМЕСТИМОСТЬ) =====

async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await task_handlers.tasks_command(update, context)

async def addtask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await task_handlers.addtask_command(update, context)

async def settasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await task_handlers.settasks_command(update, context)

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await task_handlers.edit_command(update, context)

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await task_handlers.reset_command(update, context)

async def addsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await task_handlers.addsub_command(update, context)

async def complete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await task_handlers.complete_task_command(update, context)

def register_task_handlers(application: Application):
    """
    Регистрация ПОЛНЫХ обработчиков задач с интеграцией сервисов
    
    ✅ ПОЛНЫЙ ФУНКЦИОНАЛ:
    - Создание, редактирование, удаление задач
    - Выполнение задач с XP и streak'ами  
    - Подзадачи и категории
    - Интерактивные меню
    - Статистика и аналитика
    - Массовые операции
    """
    try:
        logger.info("🔧 Регистрация ПОЛНЫХ task handlers с сервисами...")
        
        # Основные команды
        application.add_handler(CommandHandler("tasks", tasks_command))
        application.add_handler(CommandHandler("addtask", addtask_command))
        application.add_handler(CommandHandler("settasks", settasks_command))
        application.add_handler(CommandHandler("edit", edit_command))
        application.add_handler(CommandHandler("reset", reset_command))
        application.add_handler(CommandHandler("addsub", addsub_command))
        application.add_handler(CommandHandler("complete", complete_task_command))
        
        # Обработчик callback кнопок
        application.add_handler(CallbackQueryHandler(task_handlers.handle_callback_query))
        
        # ConversationHandler для добавления задач в диалоге
        conversation_handler = ConversationHandler(
            entry_points=[CommandHandler("addtask", addtask_command)],
            states={
                WAITING_TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_handlers.handle_task_title)],
                WAITING_TASK_PRIORITY: [CallbackQueryHandler(task_handlers.handle_callback_query)],
            },
            fallbacks=[CommandHandler("cancel", lambda update, context: ConversationHandler.END)]
        )
        
        application.add_handler(conversation_handler)
        
        logger.info("✅ ПОЛНЫЕ task handlers зарегистрированы успешно!")
        logger.info("🎯 Доступные команды: /tasks, /addtask, /settasks, /edit, /reset, /addsub, /complete")
        
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации task handlers: {e}")
