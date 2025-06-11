# handlers/commands/tasks.py

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

# Импорты моделей и сервисов (адаптировать под реальную структуру)
try:
    from models.task import Task
    from models.user import User
    from services.task_service import TaskService
    from services.data_service import DataService
    from shared.config import Config
except ImportError as e:
    logging.warning(f"Import error: {e}. Using fallback imports.")
    # Fallback для случая отсутствия модулей
    Task = None
    User = None
    TaskService = None
    DataService = None
    Config = None

logger = logging.getLogger(__name__)

# Константы для ConversationHandler
WAITING_TASK_TITLE, WAITING_TASK_PRIORITY, WAITING_TASK_DEADLINE = range(3)
EDIT_TASK_SELECT, EDIT_TASK_FIELD, EDIT_TASK_VALUE = range(3, 6)

class TaskHandlers:
    """Класс для обработки команд управления задачами"""
    
    def __init__(self):
        self.task_service = TaskService() if TaskService else None
        self.data_service = DataService() if DataService else None
    
    async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список задач пользователя"""
        try:
            user_id = update.effective_user.id
            
            if not self.task_service:
                await update.message.reply_text("⚠️ Сервис задач временно недоступен.")
                return
            
            # Получаем задачи пользователя
            tasks = await self.task_service.get_user_tasks(user_id)
            
            if not tasks:
                await update.message.reply_text(
                    "📝 У вас пока нет задач.\n\n"
                    "Добавьте первую задачу: /addtask [название задачи]"
                )
                return
            
            # Формируем красивый список задач
            message = "📋 **Ваши задачи:**\n\n"
            
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
                    for task in priority_group:
                        status = "✅" if task.completed else "⭕"
                        deadline_str = ""
                        if task.deadline:
                            deadline_str = f" (до {task.deadline.strftime('%d.%m')})"
                        message += f"{status} {task.id}. {task.title}{deadline_str}\n"
                    message += "\n"
            
            # Добавляем кнопки управления
            keyboard = [
                [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")],
                [InlineKeyboardButton("✏️ Редактировать", callback_data="edit_tasks"),
                 InlineKeyboardButton("🗑 Сбросить все", callback_data="reset_tasks")],
                [InlineKeyboardButton("📊 Статистика", callback_data="task_stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in tasks_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при получении списка задач.")
    
    async def addtask_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавить новую задачу"""
        try:
            user_id = update.effective_user.id
            
            if not self.task_service:
                await update.message.reply_text("⚠️ Сервис задач временно недоступен.")
                return
            
            # Получаем текст задачи из аргументов команды
            if context.args:
                task_title = " ".join(context.args)
                
                # Создаем задачу с базовыми параметрами
                task = Task(
                    title=task_title,
                    user_id=user_id,
                    priority="medium",
                    created_at=datetime.now()
                )
                
                # Сохраняем задачу
                task_id = await self.task_service.create_task(task)
                
                # Предлагаем настроить дополнительные параметры
                keyboard = [
                    [InlineKeyboardButton("🔴 Высокий приоритет", callback_data=f"set_priority_high_{task_id}"),
                     InlineKeyboardButton("🟡 Средний", callback_data=f"set_priority_medium_{task_id}"),
                     InlineKeyboardButton("🟢 Низкий", callback_data=f"set_priority_low_{task_id}")],
                    [InlineKeyboardButton("📅 Установить дедлайн", callback_data=f"set_deadline_{task_id}")],
                    [InlineKeyboardButton("✅ Готово", callback_data="close_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ **Задача добавлена:**\n"
                    f"📝 {task_title}\n"
                    f"🆔 ID: {task_id}\n"
                    f"🟡 Приоритет: средний\n\n"
                    f"Хотите настроить дополнительные параметры?",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
            else:
                # Начинаем диалог добавления задачи
                await update.message.reply_text(
                    "📝 **Добавление новой задачи**\n\n"
                    "Введите название задачи или отправьте /cancel для отмены:"
                )
                return WAITING_TASK_TITLE
                
        except Exception as e:
            logger.error(f"Error in addtask_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при добавлении задачи.")
    
    async def settasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Быстрая настройка списка задач"""
        try:
            user_id = update.effective_user.id
            
            if not context.args:
                await update.message.reply_text(
                    "📋 **Быстрая настройка задач**\n\n"
                    "Формат: `/settasks задача1; задача2; задача3`\n"
                    "Пример: `/settasks Купить молоко; Сделать домашку; Позвонить маме`\n\n"
                    "Все задачи будут добавлены со средним приоритетом."
                )
                return
            
            # Парсим задачи из аргументов
            tasks_text = " ".join(context.args)
            task_titles = [title.strip() for title in tasks_text.split(';') if title.strip()]
            
            if not task_titles:
                await update.message.reply_text("❌ Не удалось распознать задачи. Проверьте формат.")
                return
            
            if not self.task_service:
                await update.message.reply_text("⚠️ Сервис задач временно недоступен.")
                return
            
            # Создаем задачи
            created_tasks = []
            for title in task_titles:
                task = Task(
                    title=title,
                    user_id=user_id,
                    priority="medium",
                    created_at=datetime.now()
                )
                task_id = await self.task_service.create_task(task)
                created_tasks.append((task_id, title))
            
            # Формируем ответ
            message = f"✅ **Добавлено {len(created_tasks)} задач:**\n\n"
            for task_id, title in created_tasks:
                message += f"📝 {task_id}. {title}\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in settasks_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при настройке задач.")
    
    async def edit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Редактирование задач"""
        try:
            user_id = update.effective_user.id
            
            if not self.task_service:
                await update.message.reply_text("⚠️ Сервис задач временно недоступен.")
                return
            
            # Получаем задачи пользователя
            tasks = await self.task_service.get_user_tasks(user_id)
            
            if not tasks:
                await update.message.reply_text("📝 У вас нет задач для редактирования.")
                return
            
            # Создаем клавиатуру с задачами
            keyboard = []
            for task in tasks[:10]:  # Показываем первые 10 задач
                status = "✅" if task.completed else "⭕"
                keyboard.append([InlineKeyboardButton(
                    f"{status} {task.title}",
                    callback_data=f"edit_task_{task.id}"
                )])
            
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="close_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "✏️ **Выберите задачу для редактирования:**",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in edit_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при загрузке задач для редактирования.")
    
    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сброс всех задач"""
        try:
            user_id = update.effective_user.id
            
            # Подтверждение действия
            keyboard = [
                [InlineKeyboardButton("✅ Да, удалить все", callback_data=f"confirm_reset_{user_id}")],
                [InlineKeyboardButton("❌ Отмена", callback_data="close_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "⚠️ **Внимание!**\n\n"
                "Вы уверены, что хотите удалить ВСЕ задачи?\n"
                "Это действие нельзя отменить!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in reset_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка.")
    
    async def addsub_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавить подзадачу"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "📝 **Добавление подзадачи**\n\n"
                    "Формат: `/addsub [ID задачи] [название подзадачи]`\n"
                    "Пример: `/addsub 1 Купить хлеб`"
                )
                return
            
            if len(context.args) < 2:
                await update.message.reply_text("❌ Укажите ID задачи и название подзадачи.")
                return
            
            task_id = context.args[0]
            subtask_title = " ".join(context.args[1:])
            user_id = update.effective_user.id
            
            if not self.task_service:
                await update.message.reply_text("⚠️ Сервис задач временно недоступен.")
                return
            
            # Проверяем существование основной задачи
            main_task = await self.task_service.get_task(task_id, user_id)
            if not main_task:
                await update.message.reply_text("❌ Задача с указанным ID не найдена.")
                return
            
            # Создаем подзадачу
            subtask = Task(
                title=subtask_title,
                user_id=user_id,
                parent_id=task_id,
                priority=main_task.priority,
                created_at=datetime.now()
            )
            
            subtask_id = await self.task_service.create_task(subtask)
            
            await update.message.reply_text(
                f"✅ **Подзадача добавлена:**\n"
                f"📝 {subtask_title}\n"
                f"🔗 К задаче: {main_task.title}\n"
                f"🆔 ID подзадачи: {subtask_id}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in addsub_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при добавлении подзадачи.")
    
    async def complete_task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отметить задачу как выполненную"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "✅ **Завершение задачи**\n\n"
                    "Формат: `/complete [ID задачи]`\n"
                    "Пример: `/complete 1`"
                )
                return
            
            task_id = context.args[0]
            user_id = update.effective_user.id
            
            if not self.task_service:
                await update.message.reply_text("⚠️ Сервис задач временно недоступен.")
                return
            
            success = await self.task_service.complete_task(task_id, user_id)
            
            if success:
                task = await self.task_service.get_task(task_id, user_id)
                await update.message.reply_text(
                    f"🎉 **Поздравляем!**\n\n"
                    f"Задача '{task.title}' выполнена!\n"
                    f"✅ Отличная работа!"
                )
            else:
                await update.message.reply_text("❌ Задача не найдена или уже выполнена.")
                
        except Exception as e:
            logger.error(f"Error in complete_task_command: {e}")
            await update.message.reply_text("❌ Произошла ошибка при завершении задачи.")
    
    # Обработчики для ConversationHandler
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
            logger.error(f"Error in handle_task_title: {e}")
            await update.message.reply_text("❌ Произошла ошибка. Попробуйте еще раз.")
            return ConversationHandler.END
    
    # Callback обработчики для кнопок
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
                parts = data.split("_")
                priority = parts[2]
                task_id = parts[3]
                
                if self.task_service:
                    await self.task_service.update_task_priority(task_id, user_id, priority)
                    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                    await query.edit_message_text(
                        f"✅ Приоритет задачи изменен на {priority_emoji[priority]} {priority}"
                    )
                
            elif data.startswith("edit_task_"):
                task_id = data.split("_")[2]
                # Показываем меню редактирования конкретной задачи
                await self.show_edit_task_menu(query, task_id, user_id)
                
            elif data.startswith("confirm_reset_"):
                if self.task_service:
                    await self.task_service.reset_user_tasks(user_id)
                    await query.edit_message_text("✅ Все задачи удалены.")
                
        except Exception as e:
            logger.error(f"Error in handle_callback_query: {e}")
            await query.edit_message_text("❌ Произошла ошибка.")
    
    async def show_edit_task_menu(self, query, task_id: str, user_id: int):
        """Показать меню редактирования конкретной задачи"""
        try:
            if not self.task_service:
                await query.edit_message_text("⚠️ Сервис задач временно недоступен.")
                return
            
            task = await self.task_service.get_task(task_id, user_id)
            if not task:
                await query.edit_message_text("❌ Задача не найдена.")
                return
            
            status = "✅ Выполнена" if task.completed else "⭕ Не выполнена"
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            
            keyboard = [
                [InlineKeyboardButton("✏️ Изменить название", callback_data=f"edit_title_{task_id}")],
                [InlineKeyboardButton("🎯 Изменить приоритет", callback_data=f"edit_priority_{task_id}")],
                [InlineKeyboardButton("📅 Изменить дедлайн", callback_data=f"edit_deadline_{task_id}")],
                [InlineKeyboardButton("✅ Отметить выполненной" if not task.completed else "⭕ Отметить невыполненной", 
                                    callback_data=f"toggle_complete_{task_id}")],
                [InlineKeyboardButton("🗑 Удалить задачу", callback_data=f"delete_task_{task_id}")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_tasks")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✏️ **Редактирование задачи {task_id}:**\n\n"
                f"📝 **Название:** {task.title}\n"
                f"🎯 **Приоритет:** {priority_emoji.get(task.priority, '🟡')} {task.priority}\n"
                f"📊 **Статус:** {status}\n"
                f"📅 **Создана:** {task.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"{'📅 **Дедлайн:** ' + task.deadline.strftime('%d.%m.%Y') if task.deadline else ''}\n\n"
                f"Выберите действие:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in show_edit_task_menu: {e}")
            await query.edit_message_text("❌ Произошла ошибка.")


# Создаем экземпляр обработчиков
task_handlers = TaskHandlers()

# Функции для регистрации (обратная совместимость)
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
    """Регистрация всех обработчиков задач"""
    try:
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
        
        logger.info("Task handlers registered successfully")
        
    except Exception as e:
        logger.error(f"Error registering task handlers: {e}")
