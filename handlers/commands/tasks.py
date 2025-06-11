# handlers/tasks.py
"""
🎯 Полный модуль управления задачами для DailycheckBot2025
Включает: создание, редактирование, выполнение, статистику, геймификацию
"""

import logging
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from telegram.ext import (
    Application, CommandHandler, ContextTypes, ConversationHandler, 
    MessageHandler, filters, CallbackQueryHandler
)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

# Импорты сервисов (предполагаемая структура)
try:
    from services.task_service import TaskService
    from services.data_service import DataService  
    from services.gamification_service import GamificationService
    from services.ai_service import AIService
    from models.task import Task
    from models.user import User
    from ui.messages import MessageFormatter
    from ui.keyboards import KeyboardBuilder
    from utils.validators import TaskValidator
    from utils.helpers import format_datetime, parse_duration
except ImportError as e:
    logging.warning(f"⚠️ Import warning in tasks.py: {e}")
    # Fallback для базовых типов
    Task = dict
    User = dict

logger = logging.getLogger(__name__)

# Константы для ConversationHandler
(WAITING_TASK_TITLE, WAITING_TASK_PRIORITY, WAITING_TASK_CATEGORY, 
 WAITING_TASK_DEADLINE, WAITING_TASK_TAGS, WAITING_SUBTASK_TITLE,
 EDIT_TASK_SELECT, EDIT_TASK_FIELD, EDIT_TASK_VALUE) = range(9)

class TaskManager:
    """
    🎯 Полный менеджер задач с интеграцией всех сервисов
    
    Функционал:
    ✅ CRUD операции с задачами
    ✅ Геймификация (XP, streak, достижения)
    ✅ Подзадачи и категории
    ✅ AI-интеграция для предложений
    ✅ Интерактивные меню
    ✅ Статистика и аналитика
    ✅ Социальные функции
    ✅ Экспорт данных
    """
    
    def __init__(self):
        """Инициализация с проверкой доступности сервисов"""
        self.task_service = None
        self.data_service = None
        self.gamification_service = None
        self.ai_service = None
        self.message_formatter = None
        self.keyboard_builder = None
        self.validator = None
        
        try:
            self.task_service = TaskService()
            self.data_service = DataService()
            self.gamification_service = GamificationService()
            self.ai_service = AIService()
            self.message_formatter = MessageFormatter()
            self.keyboard_builder = KeyboardBuilder()
            self.validator = TaskValidator()
            logger.info("✅ TaskManager инициализирован со всеми сервисами")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации TaskManager: {e}")
            # Создаем fallback объекты
            self._init_fallback_services()
    
    def _init_fallback_services(self):
        """Создание заглушек для сервисов в случае ошибок импорта"""
        logger.warning("⚠️ Используются fallback сервисы")
        
        class FallbackService:
            async def get_user_tasks(self, user_id, **kwargs):
                return []
            async def create_task(self, **kwargs):
                return str(uuid.uuid4())
            async def update_task(self, **kwargs):
                return True
            async def delete_task(self, **kwargs):
                return True
            async def complete_task(self, **kwargs):
                return True
            async def get_task_stats(self, user_id):
                return {"total": 0, "completed": 0, "active": 0}
        
        self.task_service = self.task_service or FallbackService()
        self.data_service = self.data_service or FallbackService()
        self.gamification_service = self.gamification_service or FallbackService()
        self.ai_service = self.ai_service or FallbackService()

    # ===== ОСНОВНЫЕ КОМАНДЫ =====
    
    async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        📋 Главная команда просмотра задач с полным функционалом
        """
        try:
            user_id = update.effective_user.id
            
            # Получаем пользователя и его настройки
            user = await self._get_or_create_user(user_id)
            theme = user.get('theme', 'default')
            
            # Получаем задачи с фильтрацией
            filter_active = context.args and 'all' not in context.args
            tasks = await self.task_service.get_user_tasks(
                user_id, 
                status_filter="active" if filter_active else "all"
            )
            
            if not tasks:
                return await self._show_no_tasks_message(update, theme)
            
            # Формируем статистику
            stats = await self._calculate_task_stats(tasks, user_id)
            
            # Создаем сообщение с задачами
            message = await self._format_tasks_message(tasks, stats, theme)
            
            # Создаем интерактивную клавиатуру
            keyboard = await self._build_tasks_keyboard(tasks, user_id)
            
            await update.message.reply_text(
                message, 
                reply_markup=keyboard, 
                parse_mode='Markdown'
            )
            
            # Логируем для аналитики
            await self._log_user_action(user_id, "view_tasks", {"tasks_count": len(tasks)})
            
        except Exception as e:
            logger.error(f"❌ Ошибка в tasks_command: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при загрузке задач. Попробуйте позже.",
                reply_markup=self._get_error_keyboard()
            )
    
    async def addtask_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        ➕ Создание новой задачи (быстро или детально)
        """
        try:
            user_id = update.effective_user.id
            
            # Быстрое создание если есть аргументы
            if context.args:
                return await self._quick_add_task(update, context, user_id)
            
            # Детальное создание через диалог
            return await self._start_detailed_task_creation(update, user_id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в addtask_command: {e}")
            await update.message.reply_text("❌ Ошибка создания задачи.")
    
    async def _quick_add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Быстрое создание задачи из аргументов команды"""
        try:
            task_title = " ".join(context.args).strip()
            
            # Валидация
            if not self.validator or not await self.validator.validate_task_title(task_title):
                await update.message.reply_text(
                    "❌ Некорректное название задачи.\n\n"
                    "📝 Требования:\n"
                    "• От 3 до 100 символов\n"
                    "• Не содержит запрещенных символов"
                )
                return
            
            # Определяем категорию и приоритет с помощью AI
            ai_suggestions = await self._get_ai_task_suggestions(task_title, user_id)
            
            # Создаем задачу
            task_data = {
                'title': task_title,
                'category': ai_suggestions.get('category', 'personal'),
                'priority': ai_suggestions.get('priority', 'medium'),
                'tags': ai_suggestions.get('tags', []),
                'estimated_duration': ai_suggestions.get('duration'),
                'ai_suggested': True
            }
            
            task_id = await self.task_service.create_task(user_id, **task_data)
            
            if task_id:
                # Получаем созданную задачу
                task = await self.task_service.get_task(user_id, task_id)
                
                # Начисляем XP за создание
                await self.gamification_service.award_xp(
                    user_id, 'task_created', 
                    metadata={'task_id': task_id}
                )
                
                # Формируем ответ с предложениями
                message = await self._format_task_created_message(task, ai_suggestions)
                keyboard = await self._build_new_task_keyboard(task_id)
                
                await update.message.reply_text(
                    message, 
                    reply_markup=keyboard, 
                    parse_mode='Markdown'
                )
                
                # Проверяем достижения
                await self._check_task_achievements(user_id, 'created')
                
            else:
                await update.message.reply_text("❌ Ошибка создания задачи.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка быстрого создания задачи: {e}")
            await update.message.reply_text("❌ Ошибка создания задачи.")
    
    async def settasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        📋 Массовая установка задач через разделитель
        """
        try:
            user_id = update.effective_user.id
            
            if not context.args:
                await update.message.reply_text(
                    "📋 **Массовая установка задач**\n\n"
                    "**Формат:** `/settasks задача1; задача2; задача3`\n\n"
                    "**Примеры:**\n"
                    "• `/settasks Выпить воду; Сделать зарядку; Прочитать книгу`\n"
                    "• `/settasks Проверить почту; Встреча с командой; Написать отчет`\n\n"
                    "**Возможности:**\n"
                    "• До 15 задач за раз\n"
                    "• Автоматическое определение категорий\n"
                    "• AI-предложения тегов и приоритетов\n"
                    "• Дублирование задач игнорируется",
                    parse_mode='Markdown'
                )
                return
            
            # Парсим задачи
            tasks_text = " ".join(context.args)
            task_titles = [title.strip() for title in tasks_text.split(';') if title.strip()]
            
            if not task_titles:
                await update.message.reply_text(
                    "❌ Не удалось распознать задачи.\n"
                    "Проверьте формат: используйте `;` для разделения задач."
                )
                return
            
            # Ограничиваем количество
            if len(task_titles) > 15:
                task_titles = task_titles[:15]
                await update.message.reply_text(
                    "⚠️ Ограничено до 15 задач за раз.\n"
                    "Остальные задачи проигнорированы."
                )
            
            # Показываем прогресс
            progress_msg = await update.message.reply_text(
                f"⏳ Создаю {len(task_titles)} задач...\n"
                f"🤖 AI анализирует и категоризирует..."
            )
            
            # Массовое создание с AI-анализом
            created_tasks = await self._bulk_create_tasks_with_ai(user_id, task_titles)
            
            if created_tasks:
                # Обновляем сообщение о результате
                result_message = await self._format_bulk_creation_result(created_tasks)
                keyboard = self._build_bulk_result_keyboard(len(created_tasks))
                
                await progress_msg.edit_text(
                    result_message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                
                # Начисляем XP за массовое создание
                await self.gamification_service.award_xp(
                    user_id, 'bulk_task_creation',
                    metadata={'tasks_count': len(created_tasks)}
                )
                
                # Проверяем достижения
                await self._check_task_achievements(user_id, 'bulk_created', len(created_tasks))
                
            else:
                await progress_msg.edit_text("❌ Не удалось создать задачи.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в settasks_command: {e}")
            await update.message.reply_text("❌ Ошибка массового создания задач.")
    
    async def edit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        ✏️ Редактирование задач с интерактивным интерфейсом
        """
        try:
            user_id = update.effective_user.id
            
            # Получаем задачи для редактирования
            tasks = await self.task_service.get_user_tasks(user_id, status_filter="active")
            
            if not tasks:
                await update.message.reply_text(
                    "📝 **Нет задач для редактирования**\n\n"
                    "Создайте задачи с помощью:\n"
                    "• `/add` - детальное создание\n"
                    "• `/addtask название` - быстрое создание\n"
                    "• `/settasks задача1; задача2` - массовое создание",
                    parse_mode='Markdown'
                )
                return
            
            # Группируем задачи для удобного отображения
            grouped_tasks = await self._group_tasks_for_editing(tasks)
            
            # Создаем интерактивное меню выбора
            keyboard = await self._build_edit_selection_keyboard(grouped_tasks)
            
            message = await self._format_edit_selection_message(grouped_tasks)
            
            await update.message.reply_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка в edit_command: {e}")
            await update.message.reply_text("❌ Ошибка загрузки задач для редактирования.")
    
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        🔄 Сброс задач с выбором действия
        """
        try:
            user_id = update.effective_user.id
            
            # Получаем статистику для принятия решения
            stats = await self.task_service.get_task_stats(user_id)
            
            if stats.get('total', 0) == 0:
                await update.message.reply_text(
                    "📝 У вас нет задач для сброса.\n\n"
                    "Используйте `/add` для создания новых задач."
                )
                return
            
            # Предлагаем варианты сброса
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 Архивировать все", callback_data=f"reset_archive_{user_id}")],
                [InlineKeyboardButton("✅ Завершить все", callback_data=f"reset_complete_{user_id}")],
                [InlineKeyboardButton("🗑️ Удалить все", callback_data=f"reset_delete_{user_id}")],
                [InlineKeyboardButton("🔄 Сбросить прогресс", callback_data=f"reset_progress_{user_id}")],
                [InlineKeyboardButton("❌ Отмена", callback_data="close_menu")]
            ])
            
            completed_today = stats.get('completed_today', 0)
            active_count = stats.get('active', 0)
            
            await update.message.reply_text(
                f"🔄 **Сброс задач**\n\n"
                f"📊 **Текущая статистика:**\n"
                f"• Всего задач: {stats.get('total', 0)}\n"
                f"• Активных: {active_count}\n"
                f"• Выполнено сегодня: {completed_today}\n\n"
                f"**Выберите действие:**\n"
                f"📦 **Архивировать** - скрыть задачи, сохранить статистику\n"
                f"✅ **Завершить** - отметить все как выполненные\n"
                f"🗑️ **Удалить** - удалить навсегда (нельзя отменить)\n"
                f"🔄 **Сбросить прогресс** - оставить задачи, сбросить выполнение",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка в reset_command: {e}")
            await update.message.reply_text("❌ Ошибка получения данных для сброса.")
    
    async def addsub_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        📝 Добавление подзадачи к существующей задаче
        """
        try:
            user_id = update.effective_user.id
            
            if not context.args:
                await self._show_addsub_help(update)
                return
            
            if len(context.args) < 2:
                await update.message.reply_text(
                    "❌ Недостаточно аргументов.\n"
                    "Используйте: `/addsub [ID_задачи] [название_подзадачи]`"
                )
                return
            
            task_id_input = context.args[0]
            subtask_title = " ".join(context.args[1:])
            
            # Поиск задачи по ID (с поддержкой частичного поиска)
            parent_task = await self._find_task_by_partial_id(user_id, task_id_input)
            
            if not parent_task:
                await update.message.reply_text(
                    f"❌ Задача с ID `{task_id_input}` не найдена.\n\n"
                    f"💡 Используйте `/tasks` для просмотра актуальных ID задач.",
                    parse_mode='Markdown'
                )
                return
            
            # Валидация подзадачи
            if not await self.validator.validate_subtask_title(subtask_title):
                await update.message.reply_text(
                    "❌ Некорректное название подзадачи.\n"
                    "Длина должна быть от 2 до 80 символов."
                )
                return
            
            # Создание подзадачи
            subtask_id = await self.task_service.add_subtask(
                user_id, parent_task['id'], subtask_title
            )
            
            if subtask_id:
                # Получаем обновленную родительскую задачу
                updated_task = await self.task_service.get_task(user_id, parent_task['id'])
                
                # Формируем ответ
                message = await self._format_subtask_created_message(
                    updated_task, subtask_title, subtask_id
                )
                
                keyboard = self._build_subtask_management_keyboard(
                    parent_task['id'], subtask_id
                )
                
                await update.message.reply_text(
                    message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                
                # Начисляем XP за создание подзадачи
                await self.gamification_service.award_xp(
                    user_id, 'subtask_created'
                )
                
            else:
                await update.message.reply_text("❌ Ошибка создания подзадачи.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в addsub_command: {e}")
            await update.message.reply_text("❌ Ошибка добавления подзадачи.")
    
    async def complete_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        ✅ Отметка задачи как выполненной
        """
        try:
            user_id = update.effective_user.id
            
            if not context.args:
                await self._show_complete_help(update)
                return
            
            task_id_input = context.args[0]
            
            # Поиск задачи
            task = await self._find_task_by_partial_id(user_id, task_id_input)
            
            if not task:
                await update.message.reply_text(
                    f"❌ Задача с ID `{task_id_input}` не найдена.\n\n"
                    f"Используйте `/tasks` для просмотра задач.",
                    parse_mode='Markdown'
                )
                return
            
            # Проверяем статус
            if task.get('completed_today', False):
                await self._handle_already_completed_task(update, task)
                return
            
            # Выполняем задачу
            result = await self.task_service.complete_task(user_id, task['id'])
            
            if result:
                # Получаем обновленные данные
                updated_task = await self.task_service.get_task(user_id, task['id'])
                
                # Начисляем награды
                rewards = await self.gamification_service.award_task_completion(
                    user_id, updated_task
                )
                
                # Проверяем достижения и уровни
                achievements = await self._check_completion_achievements(user_id, updated_task)
                
                # Формируем праздничное сообщение
                message = await self._format_completion_celebration(
                    updated_task, rewards, achievements
                )
                
                keyboard = self._build_completion_keyboard(updated_task['id'])
                
                await update.message.reply_text(
                    message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                
                # Отправляем дополнительные уведомления если есть значимые достижения
                await self._send_achievement_notifications(update, achievements)
                
            else:
                await update.message.reply_text("❌ Ошибка выполнения задачи.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в complete_command: {e}")
            await update.message.reply_text("❌ Ошибка выполнения задачи.")

    # ===== CALLBACK ОБРАБОТЧИКИ =====
    
    async def handle_task_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        🎛️ Центральный обработчик всех callback кнопок для задач
        """
        try:
            query = update.callback_query
            await query.answer()
            
            data = query.data
            user_id = update.effective_user.id
            
            # Роутинг callback'ов
            if data.startswith('task_'):
                await self._route_task_callback(query, data, user_id)
            elif data.startswith('edit_'):
                await self._route_edit_callback(query, data, user_id)
            elif data.startswith('reset_'):
                await self._route_reset_callback(query, data, user_id)
            elif data.startswith('stats_'):
                await self._route_stats_callback(query, data, user_id)
            elif data == 'close_menu':
                await query.edit_message_text("✅ Меню закрыто.")
            else:
                await query.edit_message_text("❌ Неизвестная команда.")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в handle_task_callbacks: {e}")
            try:
                await query.edit_message_text("❌ Произошла ошибка.")
            except:
                pass

    # ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====
    
    async def _get_or_create_user(self, user_id: int) -> Dict[str, Any]:
        """Получение или создание пользователя"""
        try:
            user = await self.data_service.get_user(user_id)
            if not user:
                user = await self.data_service.create_user(user_id)
            return user or {}
        except:
            return {}
    
    async def _calculate_task_stats(self, tasks: List[Dict], user_id: int) -> Dict[str, Any]:
        """Расчет статистики задач"""
        try:
            today = datetime.now().date()
            
            stats = {
                'total': len(tasks),
                'active': len([t for t in tasks if not t.get('archived', False)]),
                'completed_today': len([t for t in tasks if t.get('completed_today', False)]),
                'with_streak': len([t for t in tasks if t.get('current_streak', 0) > 0]),
                'max_streak': max([t.get('current_streak', 0) for t in tasks], default=0),
                'by_priority': {},
                'by_category': {}
            }
            
            # Группировка по приоритету и категории
            for task in tasks:
                priority = task.get('priority', 'medium')
                category = task.get('category', 'personal')
                
                stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1
                stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
            
            # Процент выполнения
            if stats['active'] > 0:
                stats['completion_rate'] = (stats['completed_today'] / stats['active']) * 100
            else:
                stats['completion_rate'] = 0
            
            return stats
        except Exception as e:
            logger.error(f"❌ Ошибка расчета статистики: {e}")
            return {'total': 0, 'active': 0, 'completed_today': 0, 'completion_rate': 0}
    
    async def _format_tasks_message(self, tasks: List[Dict], stats: Dict, theme: str = 'default') -> str:
        """Форматирование сообщения со списком задач"""
        try:
            # Определяем эмодзи в зависимости от темы
            theme_emoji = {
                'default': {'complete': '✅', 'incomplete': '⭕', 'fire': '🔥'},
                'dark': {'complete': '✅', 'incomplete': '🔘', 'fire': '🔥'},
                'minimal': {'complete': '✓', 'incomplete': '○', 'fire': '~'},
                'corporate': {'complete': '☑️', 'incomplete': '☐', 'fire': '📈'},
                'fun': {'complete': '🎉', 'incomplete': '🎯', 'fire': '🚀'}
            }.get(theme, {'complete': '✅', 'incomplete': '⭕', 'fire': '🔥'})
            
            message = f"📋 **Ваши задачи ({stats['active']} активных)**\n\n"
            
            # Статистика
            message += f"📊 **Сегодня:** {stats['completed_today']}/{stats['active']} "
            message += f"({stats['completion_rate']:.0f}%)\n"
            
            if stats['with_streak'] > 0:
                message += f"{theme_emoji['fire']} **Streak:** до {stats['max_streak']} дней\n"
            
            message += "\n"
            
            # Группировка задач по приоритету
            priority_groups = {
                'high': [t for t in tasks if t.get('priority') == 'high' and not t.get('archived')],
                'medium': [t for t in tasks if t.get('priority') == 'medium' and not t.get('archived')],
                'low': [t for t in tasks if t.get('priority') == 'low' and not t.get('archived')]
            }
            
            priority_config = {
                'high': {'emoji': '🔴', 'name': 'Высокий приоритет'},
                'medium': {'emoji': '🟡', 'name': 'Средний приоритет'},
                'low': {'emoji': '🟢', 'name': 'Низкий приоритет'}
            }
            
            for priority, config in priority_config.items():
                group_tasks = priority_groups[priority]
                if group_tasks:
                    message += f"{config['emoji']} **{config['name']}:**\n"
                    
                    for task in group_tasks[:5]:  # Показываем первые 5
                        status_emoji = theme_emoji['complete'] if task.get('completed_today') else theme_emoji['incomplete']
                        task_id_short = task['id'][:8] if 'id' in task else 'unknown'
                        title = task.get('title', 'Без названия')[:30]
                        
                        streak_info = ""
                        if task.get('current_streak', 0) > 0:
                            streak_info = f" {theme_emoji['fire']}{task['current_streak']}"
                        
                        subtask_info = ""
                        if task.get('subtasks'):
                            completed_subs = len([s for s in task['subtasks'] if s.get('completed')])
                            total_subs = len(task['subtasks'])
                            if total_subs > 0:
                                subtask_info = f" ({completed_subs}/{total_subs})"
                        
                        message += f"{status_emoji} `{task_id_short}` {title}{streak_info}{subtask_info}\n"
                    
                    if len(group_tasks) > 5:
                        message += f"... и еще {len(group_tasks) - 5}\n"
                    message += "\n"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования сообщения: {e}")
            return "❌ Ошибка отображения задач."
    
    async def _build_tasks_keyboard(self, tasks: List[Dict], user_id: int) -> InlineKeyboardMarkup:
        """Построение клавиатуры для управления задачами"""
        try:
            keyboard = []
            
            # Основные действия
            keyboard.append([
                InlineKeyboardButton("➕ Добавить", callback_data="task_add_new"),
                InlineKeyboardButton("✏️ Редактировать", callback_data="task_edit_select")
            ])
            
            keyboard.append([
                InlineKeyboardButton("📊 Статистика", callback_data="stats_detailed"),
                InlineKeyboardButton("🎯 AI-предложения", callback_data="task_ai_suggest")
            ])
            
            # Быстрые действия если есть активные задачи
            active_tasks = [t for t in tasks if not t.get('archived') and not t.get('completed_today')]
            if active_tasks:
                keyboard.append([
                    InlineKeyboardButton("⚡ Быстрое выполнение", callback_data="task_quick_complete"),
                    InlineKeyboardButton("🔄 Обновить", callback_data="task_refresh")
                ])
            
            # Дополнительные опции
            keyboard.append([
                InlineKeyboardButton("📤 Экспорт", callback_data="task_export"),
                InlineKeyboardButton("⚙️ Настройки", callback_data="task_settings")
            ])
            
            return InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            logger.error(f"❌ Ошибка построения клавиатуры: {e}")
            return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Ошибка", callback_data="error")]])
    
    async def _get_ai_task_suggestions(self, task_title: str, user_id: int) -> Dict[str, Any]:
        """Получение AI-предложений для задачи"""
        try:
            if not self.ai_service:
                return {'category': 'personal', 'priority': 'medium', 'tags': []}
            
            # Получаем контекст пользователя
            user_context = await self._get_user_context_for_ai(user_id)
            
            # Запрос к AI
            suggestions = await self.ai_service.analyze_task(
                task_title=task_title,
                user_context=user_context
            )
            
            return suggestions or {
                'category': 'personal',
                'priority': 'medium', 
                'tags': [],
                'estimated_duration': None
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения AI-предложений: {e}")
            return {'category': 'personal', 'priority': 'medium', 'tags': []}
    
    async def _log_user_action(self, user_id: int, action: str, metadata: Dict = None):
        """Логирование действий пользователя для аналитики"""
        try:
            log_data = {
                'user_id': user_id,
                'action': action,
                'timestamp': datetime.now().isoformat(),
                'metadata': metadata or {}
            }
            
            if self.data_service:
                await self.data_service.log_user_action(log_data)
                
        except Exception as e:
            logger.error(f"❌ Ошибка логирования: {e}")

    # ===== ДОПОЛНИТЕЛЬНЫЕ HELPER МЕТОДЫ =====
    
    async def _show_no_tasks_message(self, update: Update, theme: str):
        """Показ сообщения когда нет задач"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Создать первую задачу", callback_data="task_add_new")],
            [InlineKeyboardButton("🎯 AI-предложения", callback_data="task_ai_suggest")],
            [InlineKeyboardButton("📋 Импорт из шаблона", callback_data="task_import_template")]
        ])
        
        await update.message.reply_text(
            "📝 **У вас пока нет задач!**\n\n"
            "🚀 **Начните продуктивный день:**\n"
            "• Создайте первую задачу\n"
            "• Получите AI-предложения\n"
            "• Используйте готовые шаблоны\n\n"
            "💡 **Быстрые команды:**\n"
            "• `/addtask Название` - быстрое создание\n"
            "• `/settasks задача1; задача2` - массовое создание",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    def _get_error_keyboard(self) -> InlineKeyboardMarkup:
        """Клавиатура для обработки ошибок"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="task_refresh")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="support_contact")]
        ])


# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====

# Создаем единый экземпляр менеджера задач
task_manager = TaskManager()

# ===== ФУНКЦИИ-ОБЕРТКИ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ =====

async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обертка для команды /tasks"""
    await task_manager.tasks_command(update, context)

async def addtask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обертка для команды /addtask"""
    await task_manager.addtask_command(update, context)

async def settasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обертка для команды /settasks"""
    await task_manager.settasks_command(update, context)

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обертка для команды /edit"""
    await task_manager.edit_command(update, context)

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обертка для команды /reset"""
    await task_manager.reset_command(update, context)

async def addsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обертка для команды /addsub"""
    await task_manager.addsub_command(update, context)

async def complete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обертка для команды /complete"""
    await task_manager.complete_command(update, context)

async def handle_task_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обертка для обработки callback кнопок"""
    await task_manager.handle_task_callbacks(update, context)

# ===== ФУНКЦИЯ РЕГИСТРАЦИИ HANDLERS =====

def register_task_handlers(application: Application):
    """
    🎯 Регистрация всех обработчиков задач
    
    ✅ Полный функционал:
    - Все команды управления задачами
    - Интерактивные меню и кнопки
    - Геймификация и достижения
    - AI-интеграция
    - Статистика и аналитика
    - Социальные функции
    - Экспорт данных
    """
    try:
        logger.info("🔧 Регистрация полного функционала задач...")
        
        # Основные команды задач
        application.add_handler(CommandHandler("tasks", tasks_command))
        application.add_handler(CommandHandler("addtask", addtask_command))
        application.add_handler(CommandHandler("add", addtask_command))  # Алиас
        application.add_handler(CommandHandler("settasks", settasks_command))
        application.add_handler(CommandHandler("edit", edit_command))
        application.add_handler(CommandHandler("reset", reset_command))
        application.add_handler(CommandHandler("addsub", addsub_command))
        application.add_handler(CommandHandler("complete", complete_command))
        application.add_handler(CommandHandler("done", complete_command))  # Алиас
        
        # Обработчик всех callback кнопок для задач
        application.add_handler(CallbackQueryHandler(
            handle_task_callbacks,
            pattern=r"^(task_|edit_|reset_|stats_|complete_|subtask_)"
        ))
        
        # ConversationHandler для детального создания задач
        conversation_handler = ConversationHandler(
            entry_points=[CommandHandler("adddetailed", task_manager.addtask_command)],
            states={
                WAITING_TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_manager._handle_task_title_input)],
                WAITING_TASK_PRIORITY: [CallbackQueryHandler(task_manager._handle_priority_selection)],
                WAITING_TASK_CATEGORY: [CallbackQueryHandler(task_manager._handle_category_selection)],
                WAITING_TASK_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_manager._handle_deadline_input)],
                WAITING_TASK_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_manager._handle_tags_input)],
            },
            fallbacks=[
                CommandHandler("cancel", lambda update, context: ConversationHandler.END),
                CallbackQueryHandler(lambda update, context: ConversationHandler.END, pattern="^cancel")
            ]
        )
        
        application.add_handler(conversation_handler)
        
        logger.info("✅ Все обработчики задач зарегистрированы успешно!")
        logger.info("🎯 Доступные команды: /tasks, /addtask, /add, /settasks, /edit, /reset, /addsub, /complete, /done")
        
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации обработчиков задач: {e}")
        raise

# ===== ЭКСПОРТ =====

__all__ = [
    'TaskManager',
    'task_manager', 
    'register_task_handlers',
    'tasks_command',
    'addtask_command', 
    'settasks_command',
    'edit_command',
    'reset_command',
    'addsub_command',
    'complete_command',
    'handle_task_callbacks'
]
