# ===== handlers/utils.py =====
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
import logging
from datetime import datetime

from database import DatabaseManager
from models.user import User

logger = logging.getLogger(__name__)

# Клавиатуры
def get_main_keyboard():
    """Основная клавиатура"""
    keyboard = [
        [KeyboardButton("📝 Мои задачи"), KeyboardButton("➕ Добавить задачу")],
        [KeyboardButton("✅ Отметить выполнение"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("ℹ️ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_tasks_inline_keyboard(tasks: dict):
    """Инлайн клавиатура для списка задач"""
    keyboard = []
    
    for task_id, task in tasks.items():
        status_emoji = "✅" if task.status.value == "completed" else "⭕"
        keyboard.append([
            InlineKeyboardButton(
                f"{status_emoji} {task.title}",
                callback_data=f"task_view_{task_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("➕ Добавить задачу", callback_data="task_add"),
        InlineKeyboardButton("🔄 Обновить", callback_data="tasks_refresh")
    ])
    
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """Команда /start"""
    user_telegram = update.effective_user
    user = db.get_or_create_user(
        user_id=user_telegram.id,
        username=user_telegram.username,
        first_name=user_telegram.first_name,
        last_name=user_telegram.last_name
    )
    
    # Обновляем последнюю активность
    user.stats.last_activity = datetime.now()
    db.save_user(user)
    
    welcome_text = f"""🎯 Добро пожаловать в DailyCheck Bot v4.0!

Привет, {user.first_name or user.username or 'друг'}! 

Я помогу тебе:
📝 Создавать и отслеживать ежедневные задачи
✅ Отмечать выполнение и следить за прогрессом  
📊 Анализировать статистику и строить полезные привычки
🔥 Поддерживать мотивацию с помощью streak'ов

Выбери действие в меню ниже или используй кнопки:"""
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """📖 Справка по DailyCheck Bot v4.0

🔹 **Основные команды:**
/start - Перезапустить бота
/help - Показать эту справку
/tasks - Список ваших задач
/add - Добавить новую задачу
/stats - Показать статистику
/settings - Настройки

🔹 **Быстрые действия:**
📝 Мои задачи - просмотр всех задач
➕ Добавить задачу - создание новой задачи
✅ Отметить выполнение - отметка задач как выполненных
📊 Статистика - ваш прогресс и аналитика

🔹 **Возможности:**
• Создание ежедневных задач с приоритетами
• Отслеживание streak'ов (серий выполнения)
• Автоматические напоминания
• Детальная статистика и экспорт данных
• Достижения и мотивационные сообщения

💡 **Совет:** Используйте кнопки для быстрого доступа к функциям!"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных команд"""
    await update.message.reply_text(
        "🤔 Я не знаю такой команды. Используйте /help для списка доступных команд.",
        reply_markup=get_main_keyboard()
    )

def format_task_info(task) -> str:
    """Форматирование информации о задаче"""
    priority_emojis = {
        "low": "🔵",
        "medium": "🟡", 
        "high": "🔴"
    }
    
    status_emojis = {
        "active": "⭕",
        "completed": "✅",
        "paused": "⏸️",
        "archived": "📦"
    }
    
    info = f"{status_emojis.get(task.status.value, '⭕')} **{task.title}**\n"
    
    if task.description:
        info += f"📝 {task.description}\n"
    
    info += f"{priority_emojis.get(task.priority.value, '🟡')} Приоритет: {task.priority.value}\n"
    info += f"🔥 Streak: {task.current_streak} дней\n"
    info += f"📈 Выполнение за неделю: {task.completion_rate_week:.1f}%\n"
    
    if task.tags:
        info += f"🏷️ Теги: {', '.join(task.tags)}\n"
    
    info += f"📅 Создана: {task.created_at.strftime('%d.%m.%Y')}"
    
    return info

# ===== handlers/tasks.py =====
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler
import uuid
from datetime import date, datetime
import logging

from database import DatabaseManager
from models.task import Task, TaskPriority, TaskStatus
from models.user import User
from .utils import get_main_keyboard, get_tasks_inline_keyboard, format_task_info

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
TASK_TITLE, TASK_DESCRIPTION, TASK_PRIORITY, TASK_TAGS = range(4)

async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """Команда /tasks - показать список задач"""
    user = db.get_or_create_user(update.effective_user.id)
    
    if not user.tasks:
        await update.message.reply_text(
            "📝 У вас пока нет задач!\n\nИспользуйте кнопку '➕ Добавить задачу' или команду /add для создания первой задачи.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Фильтруем активные задачи
    active_tasks = {k: v for k, v in user.tasks.items() if v.status == TaskStatus.ACTIVE}
    
    if not active_tasks:
        await update.message.reply_text(
            "📝 У вас нет активных задач!\n\nВсе задачи выполнены или приостановлены.",
            reply_markup=get_main_keyboard()
        )
        return
    
    text = f"📝 **Ваши активные задачи ({len(active_tasks)}):**\n\n"
    
    for i, (task_id, task) in enumerate(active_tasks.items(), 1):
        status_emoji = "✅" if any(c.date == date.today() and c.completed for c in task.completions) else "⭕"
        text += f"{i}. {status_emoji} {task.title}\n"
        text += f"   🔥 Streak: {task.current_streak} | 📈 Неделя: {task.completion_rate_week:.0f}%\n\n"
    
    text += "Выберите задачу для подробной информации:"
    
    await update.message.reply_text(
        text,
        reply_markup=get_tasks_inline_keyboard(active_tasks),
        parse_mode='Markdown'
    )

async def add_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления новой задачи"""
    await update.message.reply_text(
        "📝 **Создание новой задачи**\n\nВведите название задачи:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='Markdown'
    )
    return TASK_TITLE

async def add_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение названия задачи"""
    title = update.message.text.strip()
    
    if len(title) > 100:
        await update.message.reply_text(
            "❌ Название слишком длинное! Максимум 100 символов.\nВведите название еще раз:"
        )
        return TASK_TITLE
    
    context.user_data['task_title'] = title
    
    await update.message.reply_text(
        f"✅ Название: **{title}**\n\nТеперь введите описание задачи (или отправьте 'пропустить'):",
        parse_mode='Markdown'
    )
    return TASK_DESCRIPTION

async def add_task_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение описания задачи"""
    description = update.message.text.strip()
    
    if description.lower() in ['пропустить', 'skip', '-']:
        description = None
    elif len(description) > 500:
        await update.message.reply_text(
            "❌ Описание слишком длинное! Максимум 500 символов.\nВведите описание еще раз (или 'пропустить'):"
        )
        return TASK_DESCRIPTION
    
    context.user_data['task_description'] = description
    
    # Клавиатура для выбора приоритета
    keyboard = [
        [InlineKeyboardButton("🔴 Высокий", callback_data="priority_high")],
        [InlineKeyboardButton("🟡 Средний", callback_data="priority_medium")],
        [InlineKeyboardButton("🔵 Низкий", callback_data="priority_low")]
    ]
    
    await update.message.reply_text(
        f"✅ Описание: {description or 'не указано'}\n\nВыберите приоритет задачи:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TASK_PRIORITY

async def add_task_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение приоритета задачи"""
    query = update.callback_query
    await query.answer()
    
    priority_map = {
        "priority_high": TaskPriority.HIGH,
        "priority_medium": TaskPriority.MEDIUM,
        "priority_low": TaskPriority.LOW
    }
    
    priority = priority_map.get(query.data, TaskPriority.MEDIUM)
    context.user_data['task_priority'] = priority
    
    await query.edit_message_text(
        f"✅ Приоритет: {priority.value}\n\nВведите теги через запятую (или 'пропустить'):"
    )
    return TASK_TAGS

async def add_task_tags(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """Получение тегов и создание задачи"""
    tags_text = update.message.text.strip()
    
    if tags_text.lower() in ['пропустить', 'skip', '-']:
        tags = []
    else:
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
        tags = tags[:5]  # Максимум 5 тегов
    
    # Создаем задачу
    user = db.get_or_create_user(update.effective_user.id)
    
    task = Task(
        task_id=str(uuid.uuid4()),
        user_id=user.user_id,
        title=context.user_data['task_title'],
        description=context.user_data.get('task_description'),
        priority=context.user_data['task_priority'],
        tags=tags
    )
    
    # Добавляем задачу пользователю
    user.tasks[task.task_id] = task
    user.stats.total_tasks += 1
    
    # Сохраняем
    db.save_user(user)
    
    # Очищаем данные из контекста
    context.user_data.clear()
    
    success_text = f"🎉 **Задача создана!**\n\n{format_task_info(task)}"
    
    await update.message.reply_text(
        success_text,
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

async def cancel_add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена добавления задачи"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Создание задачи отменено.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def complete_task_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """Меню отметки выполнения задач"""
    user = db.get_or_create_user(update.effective_user.id)
    
    if not user.tasks:
        await update.message.reply_text(
            "📝 У вас пока нет задач для выполнения!",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Фильтруем активные задачи, не выполненные сегодня
    today = date.today()
    available_tasks = {}
    
    for task_id, task in user.tasks.items():
        if task.status == TaskStatus.ACTIVE:
            # Проверяем, не выполнена ли уже сегодня
            completed_today = any(c.date == today and c.completed for c in task.completions)
            if not completed_today:
                available_tasks[task_id] = task
    
    if not available_tasks:
        await update.message.reply_text(
            "🎉 Отлично! Все активные задачи на сегодня уже выполнены!",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Создаем клавиатуру для выбора задач
    keyboard = []
    for task_id, task in available_tasks.items():
        keyboard.append([
            InlineKeyboardButton(
                f"✅ {task.title}",
                callback_data=f"complete_{task_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("❌ Отмена", callback_data="complete_cancel")
    ])
    
    await update.message.reply_text(
        f"✅ **Отметка выполнения**\n\nВыберите задачу для отметки ({len(available_tasks)} доступно):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """Обработчик callback для задач"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = db.get_or_create_user(update.effective_user.id)
    
    if data.startswith("complete_"):
        task_id = data.replace("complete_", "")
        
        if task_id == "cancel":
            await query.edit_message_text(
                "❌ Отметка выполнения отменена.",
                reply_markup=None
            )
            return
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        
        # Отмечаем как выполненную
        if task.mark_completed():
            user.stats.completed_tasks += 1
            db.save_user(user)
            
            streak_text = f"🔥 Streak: {task.current_streak} дней!"
            if task.current_streak > user.stats.longest_streak:
                user.stats.longest_streak = task.current_streak
                db.save_user(user)
                streak_text += " 🏆 Новый рекорд!"
            
            await query.edit_message_text(
                f"🎉 **Задача выполнена!**\n\n"
                f"✅ {task.title}\n"
                f"{streak_text}\n\n"
                f"Продолжайте в том же духе! 💪"
            )
        else:
            await query.edit_message_text("❌ Ошибка при отметке выполнения.")
    
    elif data.startswith("task_view_"):
        task_id = data.replace("task_view_", "")
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        
        # Создаем клавиатуру для действий с задачей
        keyboard = [
            [InlineKeyboardButton("✅ Выполнить", callback_data=f"complete_{task_id}")],
            [InlineKeyboardButton("⏸️ Приостановить", callback_data=f"pause_{task_id}")],
            [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_{task_id}")],
            [InlineKeyboardButton("⬅️ Назад к списку", callback_data="tasks_refresh")]
        ]
        
        await query.edit_message_text(
            format_task_info(task),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif data == "tasks_refresh":
        # Обновляем список задач
        active_tasks = {k: v for k, v in user.tasks.items() if v.status == TaskStatus.ACTIVE}
        
        if not active_tasks:
            await query.edit_message_text("📝 У вас нет активных задач!")
            return
        
        text = f"📝 **Ваши активные задачи ({len(active_tasks)}):**\n\n"
        
        for i, (task_id, task) in enumerate(active_tasks.items(), 1):
            status_emoji = "✅" if any(c.date == date.today() and c.completed for c in task.completions) else "⭕"
            text += f"{i}. {status_emoji} {task.title}\n"
            text += f"   🔥 Streak: {task.current_streak} | 📈 Неделя: {task.completion_rate_week:.0f}%\n\n"
        
        text += "Выберите задачу для подробной информации:"
        
        await query.edit_message_text(
            text,
            reply_markup=get_tasks_inline_keyboard(active_tasks),
            parse_mode='Markdown'
        )

def setup_task_handlers(app, db, config):
    """Настройка обработчиков для задач"""
    
    # ConversationHandler для добавления задач
    add_task_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_task_start),
            MessageHandler(filters.Regex("^➕ Добавить задачу$"), add_task_start)
        ],
        states={
            TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_title)],
            TASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_description)],
            TASK_PRIORITY: [CallbackQueryHandler(add_task_priority, pattern="^priority_")],
            TASK_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                     lambda u, c: add_task_tags(u, c, db))]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_add_task),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_add_task)
        ]
    )
    
    app.add_handler(add_task_handler)
    
    # Остальные обработчики
    app.add_handler(CommandHandler("tasks", lambda u, c: tasks_command(u, c, db)))
    app.add_handler(MessageHandler(filters.Regex("^📝 Мои задачи$"), lambda u, c: tasks_command(u, c, db)))
    app.add_handler(MessageHandler(filters.Regex("^✅ Отметить выполнение$"), lambda u, c: complete_task_menu(u, c, db)))
    
    # Callback обработчики
    app.add_handler(CallbackQueryHandler(lambda u, c: handle_task_callback(u, c, db), pattern="^(complete_|task_view_|tasks_refresh|pause_|delete_)"))

# ===== handlers/stats.py =====
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from datetime import date, datetime, timedelta
import io
import json

from database import DatabaseManager
from .utils import get_main_keyboard

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """Команда /stats - показать статистику"""
    user = db.get_or_create_user(update.effective_user.id)
    
    if not user.tasks:
        await update.message.reply_text(
            "📊 Статистика недоступна - у вас нет задач!\n\nСоздайте первую задачу для начала отслеживания прогресса.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Собираем статистику
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    total_tasks = len(user.tasks)
    active_tasks = len([t for t in user.tasks.values() if t.status.value == "active"])
    
    # Статистика выполнения
    completed_today = 0
    completed_week = 0
    completed_month = 0
    
    for task in user.tasks.values():
        for completion in task.completions:
            if completion.completed:
                if completion.date == today:
                    completed_today += 1
                if completion.date >= week_ago:
                    completed_week += 1
                if completion.date >= month_ago:
                    completed_month += 1
    
    # Текущие streak'и
    current_streaks = [task.current_streak for task in user.tasks.values() if task.status.value == "active"]
    max_streak = max(current_streaks) if current_streaks else 0
    avg_streak = sum(current_streaks) / len(current_streaks) if current_streaks else 0
    
    # Форматируем статистику
    stats_text = f"""📊 **Ваша статистика**

🎯 **Общее:**
• Всего задач: {total_tasks}
• Активных: {active_tasks}
• Выполнено всего: {user.stats.completed_tasks}
• Процент выполнения: {user.stats.completion_rate:.1f}%

📅 **За периоды:**
• Сегодня: {completed_today} задач
• За неделю: {completed_week} выполнений
• За месяц: {completed_month} выполнений

🔥 **Streak'и:**
• Максимальный: {max_streak} дней
• Средний: {avg_streak:.1f} дней
• Рекорд: {user.stats.longest_streak} дней

👤 **Профиль:**
• Регистрация: {user.stats.registration_date.strftime('%d.%m.%Y')}
• Дней в системе: {(datetime.now() - user.stats.registration_date).days}"""
    
    # Клавиатура для дополнительных действий
    keyboard = [
        [InlineKeyboardButton("📈 Детальная статистика", callback_data="stats_detailed")],
        [InlineKeyboardButton("📊 Экспорт данных", callback_data="stats_export")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="stats_refresh")]
    ]
    
    await update.message.reply_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """Обработчик callback для статистики"""
    query = update.callback_query
    await query.answer()
    
    user = db.get_or_create_user(update.effective_user.id)
    
    if query.data == "stats_detailed":
        # Детальная статистика по задачам
        if not user.tasks:
            await query.edit_message_text("❌ Нет данных для детальной статистики!")
            return
        
        detailed_text = "📈 **Детальная статистика по задачам:**\n\n"
        
        for i, (task_id, task) in enumerate(user.tasks.items(), 1):
            if task.status.value == "active":
                detailed_text += f"{i}. **{task.title}**\n"
                detailed_text += f"   🔥 Streak: {task.current_streak} дней\n"
                detailed_text += f"   📈 Неделя: {task.completion_rate_week:.1f}%\n"
                detailed_text += f"   📅 Создана: {task.created_at.strftime('%d.%m.%Y')}\n\n"
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="stats_refresh")]]
        
        await query.edit_message_text(
            detailed_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif query.data == "stats_export":
        # Экспорт данных
        export_data = {
            "user_info": {
                "user_id": user.user_id,
                "username": user.username,
                "registration_date": user.stats.registration_date.isoformat(),
                "export_date": datetime.now().isoformat()
            },
            "statistics": user.stats.__dict__,
            "tasks": [task.to_dict() for task in user.tasks.values()],
            "achievements": user.achievements
        }
        
        # Создаем файл
        export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
        file_buffer = io.BytesIO(export_json.encode('utf-8'))
        file_buffer.name = f"dailycheck_export_{user.user_id}_{datetime.now().strftime('%Y%m%d')}.json"
        
        await query.message.reply_document(
            document=file_buffer,
            caption="📊 Экспорт ваших данных из DailyCheck Bot",
            filename=file_buffer.name
        )
        
        await query.edit_message_text(
            "✅ Данные экспортированы!\n\nФайл содержит всю информацию о ваших задачах и статистике.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад к статистике", callback_data="stats_refresh")
            ]])
        )
    
    elif query.data == "stats_refresh":
        # Обновляем статистику (повторяем логику из stats_command)
        await stats_command(query, context, db)

def setup_stats_handlers(app, db, config):
    """Настройка обработчиков для статистики"""
    app.add_handler(CommandHandler("stats", lambda u, c: stats_command(u, c, db)))
    app.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), lambda u, c: stats_command(u, c, db)))
    app.add_handler(CallbackQueryHandler(lambda u, c: handle_stats_callback(u, c, db), pattern="^stats_"))

# ===== handlers/settings.py =====
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from database import DatabaseManager
from .utils import get_main_keyboard

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """Команда /settings - настройки пользователя"""
    user = db.get_or_create_user(update.effective_user.id)
    
    settings_text = f"""⚙️ **Настройки**

🌍 **Локализация:**
• Язык: {user.settings.language}
• Часовой пояс: {user.settings.timezone}

🔔 **Напоминания:**
• Включены: {'✅' if user.settings.reminder_enabled else '❌'}
• Время: {user.settings.daily_reminder_time}

📊 **Уведомления:**
• Еженедельная статистика: {'✅' if user.settings.weekly_stats else '❌'}
• Мотивационные сообщения: {'✅' if user.settings.motivational_messages else '❌'}"""
    
    keyboard = [
        [InlineKeyboardButton("🔔 Напоминания", callback_data="settings_reminders")],
        [InlineKeyboardButton("🌍 Язык и время", callback_data="settings_locale")],
        [InlineKeyboardButton("📊 Уведомления", callback_data="settings_notifications")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="settings_refresh")]
    ]
    
    await update.message.reply_text(
        settings_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """Обработчик callback для настроек"""
    query = update.callback_query
    await query.answer()
    
    user = db.get_or_create_user(update.effective_user.id)
    
    if query.data == "settings_reminders":
        keyboard = [
            [InlineKeyboardButton(
                f"🔔 {'Выключить' if user.settings.reminder_enabled else 'Включить'} напоминания",
                callback_data="toggle_reminders"
            )],
            [InlineKeyboardButton("⏰ Изменить время", callback_data="change_time")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="settings_refresh")]
        ]
        
        await query.edit_message_text(
            f"🔔 **Настройки напоминаний**\n\n"
            f"Статус: {'✅ Включены' if user.settings.reminder_enabled else '❌ Выключены'}\n"
            f"Время: {user.settings.daily_reminder_time}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif query.data == "toggle_reminders":
        user.settings.reminder_enabled = not user.settings.reminder_enabled
        db.save_user(user)
        
        await query.edit_message_text(
            f"✅ Напоминания {'включены' if user.settings.reminder_enabled else 'выключены'}!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад к настройкам", callback_data="settings_refresh")
            ]])
        )

def setup_settings_handlers(app, db, config):
    """Настройка обработчиков для настроек"""
    app.add_handler(CommandHandler("settings", lambda u, c: settings_command(u, c, db)))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Настройки$"), lambda u, c: settings_command(u, c, db)))
    app.add_handler(CallbackQueryHandler(lambda u, c: handle_settings_callback(u, c, db), pattern="^settings_|^toggle_|^change_"))

# ===== handlers/admin.py =====
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import os
import shutil
from datetime import datetime

from database import DatabaseManager

def is_admin(user_id: int, config) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in config.ADMIN_IDS

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager, config):
    """Команда /admin - панель администратора"""
    if not is_admin(update.effective_user.id, config):
        await update.message.reply_text("❌ У вас нет прав администратора!")
        return
    
    all_users = db.get_all_users()
    total_tasks = sum(len(user.tasks) for user in all_users)
    active_users = len([user for user in all_users if user.stats.last_activity and 
                       (datetime.now() - user.stats.last_activity).days <= 7])
    
    admin_text = f"""🔧 **Панель администратора**

📊 **Статистика системы:**
• Всего пользователей: {len(all_users)}
• Активных за неделю: {active_users}
• Всего задач: {total_tasks}
• Средне задач на пользователя: {total_tasks / len(all_users) if all_users else 0:.1f}

💾 **Система:**
• Размер данных: {get_directory_size(config.DATA_DIR)} MB
• Последний бэкап: {get_last_backup_time(config.BACKUPS_DIR)}"""
    
    keyboard = [
        [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton("💾 Создать бэкап", callback_data="admin_backup")],
        [InlineKeyboardButton("📊 Детальная статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📨 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_refresh")]
    ]
    
    await update.message.reply_text(
        admin_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

def get_directory_size(path) -> float:
    """Получить размер директории в MB"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                total_size += os.path.getsize(file_path)
        return round(total_size / (1024 * 1024), 2)
    except:
        return 0.0

def get_last_backup_time(backup_dir) -> str:
    """Получить время последнего бэкапа"""
    try:
        backups = [f for f in os.listdir(backup_dir) if f.startswith('backup_')]
        if not backups:
            return "Нет бэкапов"
        
        latest_backup = max(backups, key=lambda x: os.path.getctime(os.path.join(backup_dir, x)))
        backup_time = datetime.fromtimestamp(os.path.getctime(os.path.join(backup_dir, latest_backup)))
        return backup_time.strftime('%d.%m.%Y %H:%M')
    except:
        return "Неизвестно"

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager, config):
    """Обработчик callback для админки"""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id, config):
        await query.edit_message_text("❌ У вас нет прав администратора!")
        return
    
    if query.data == "admin_backup":
        try:
            backup_path = db.backup_data()
            await query.edit_message_text(
                f"✅ Бэкап создан успешно!\n\nПуть: {backup_path}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Назад", callback_data="admin_refresh")
                ]])
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Ошибка создания бэкапа: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Назад", callback_data="admin_refresh")
                ]])
            )
    
    elif query.data == "admin_users":
        all_users = db.get_all_users()
        
        if not all_users:
            await query.edit_message_text("👥 Пользователей не найдено!")
            return
        
        users_text = "👥 **Список пользователей (последние 10):**\n\n"
        
        # Сортируем по последней активности
        sorted_users = sorted(all_users, 
                            key=lambda x: x.stats.last_activity or datetime.min, 
                            reverse=True)[:10]
        
        for i, user in enumerate(sorted_users, 1):
            username = user.username or f"ID{user.user_id}"
            last_activity = user.stats.last_activity.strftime('%d.%m.%Y') if user.stats.last_activity else "Никогда"
            users_text += f"{i}. @{username}\n"
            users_text += f"   📅 Активность: {last_activity}\n"
            users_text += f"   📝 Задач: {len(user.tasks)}\n\n"
        
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="admin_refresh")]]
        
        await query.edit_message_text(
            users_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

def setup_admin_handlers(app, db, config):
    """Настройка обработчиков для админки"""
    app.add_handler(CommandHandler("admin", lambda u, c: admin_command(u, c, db, config)))
    app.add_handler(CallbackQueryHandler(lambda u, c: handle_admin_callback(u, c, db, config), pattern="^admin_"))

# ===== handlers/social.py =====
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from datetime import date, timedelta

from database import DatabaseManager

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """Команда /leaderboard - таблица лидеров"""
    all_users = db.get_all_users()
    
    if len(all_users) < 2:
        await update.message.reply_text(
            "🏆 Недостаточно пользователей для таблицы лидеров!\n\nПригласите друзей использовать бота!"
        )
        return
    
    # Считаем статистику для лидерборда
    user_stats = []
    
    for user in all_users:
        if not user.tasks:
            continue
            
        # Считаем streak'и
        current_streaks = [task.current_streak for task in user.tasks.values() 
                          if task.status.value == "active"]
        max_streak = max(current_streaks) if current_streaks else 0
        
        # Выполнения за неделю
        week_ago = date.today() - timedelta(days=7)
        week_completions = 0
        
        for task in user.tasks.values():
            for completion in task.completions:
                if completion.date >= week_ago and completion.completed:
                    week_completions += 1
        
        user_stats.append({
            'user': user,
            'max_streak': max_streak,
            'week_completions': week_completions,
            'total_completed': user.stats.completed_tasks,
            'completion_rate': user.stats.completion_rate
        })
    
    # Сортируем по максимальному streak'у
    user_stats.sort(key=lambda x: x['max_streak'], reverse=True)
    
    leaderboard_text = "🏆 **Таблица лидеров**\n\n"
    leaderboard_text += "📈 *По максимальному streak'у:*\n"
    
    current_user_id = update.effective_user.id
    
    for i, stats in enumerate(user_stats[:10], 1):
        user = stats['user']
        username = user.username or f"Пользователь {user.user_id}"
        
        emoji = "👑" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        is_current = "← Вы" if user.user_id == current_user_id else ""
        
        leaderboard_text += f"{emoji} @{username} - {stats['max_streak']} дней {is_current}\n"
    
    # Добавляем статистику по выполнениям за неделю
    user_stats.sort(key=lambda x: x['week_completions'], reverse=True)
    
    leaderboard_text += "\n📅 *По выполнениям за неделю:*\n"
    
    for i, stats in enumerate(user_stats[:5], 1):
        user = stats['user']
        username = user.username or f"Пользователь {user.user_id}"
        
        emoji = "🔥" if i == 1 else f"{i}."
        is_current = "← Вы" if user.user_id == current_user_id else ""
        
        leaderboard_text += f"{emoji} @{username} - {stats['week_completions']} выполнений {is_current}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="leaderboard_refresh")],
        [InlineKeyboardButton("📊 Моя позиция", callback_data="my_position")]
    ]
    
    await update.message.reply_text(
        leaderboard_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

def setup_social_handlers(app, db, config):
    """Настройка обработчиков для социальных функций"""
    app.add_handler(CommandHandler("leaderboard", lambda u, c: leaderboard_command(u, c, db)))

# ===== handlers/ai_functions.py =====
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
import random

from database import DatabaseManager

# Мотивационные сообщения
MOTIVATIONAL_MESSAGES = [
    "🔥 Отличная работа! Продолжайте в том же духе!",
    "💪 Каждый день делает вас сильнее!",
    "🌟 Вы на правильном пути к своим целям!",
    "🎯 Постоянство - ключ к успеху!",
    "⭐ Маленькие шаги ведут к большим результатам!",
    "🚀 Ваш прогресс впечатляет!",
    "💎 Привычки формируют вашу жизнь!",
    "🏆 Вы чемпион своей жизни!",
    "🌈 Каждый выполненный день - это победа!",
    "⚡ Энергия успеха с вами!"
]

ACHIEVEMENT_MESSAGES = {
    'first_task': "🎉 Первая задача создана! Начало пути к лучшей версии себя!",
    'streak_7': "🔥 Неделя выполнения! Привычка начинает формироваться!",
    'streak_30': "💎 30 дней streak! Вы официально создали привычку!",
    'streak_100': "👑 100 дней! Вы настоящий мастер самодисциплины!",
    'tasks_10': "📈 10 задач выполнено! Отличный прогресс!",
    'tasks_50': "🏆 50 выполнений! Вы серьезно настроены на успех!",
    'tasks_100': "🌟 100 выполнений! Легенда продуктивности!"
}

async def get_ai_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE, db: DatabaseManager):
    """AI предложения для улучшения продуктивности"""
    user = db.get_or_create_user(update.effective_user.id)
    
    if not user.tasks:
        suggestion = """🤖 **AI Совет**

Начните с малого! Рекомендую создать 2-3 простые ежедневные задачи:

1. 📚 Читать 10 минут в день
2. 💧 Выпивать 2 литра воды
3. 🚶 Прогулка 15 минут

Простые привычки легче поддерживать и они создают основу для более сложных целей!"""
    else:
        # Анализируем задачи пользователя
        active_tasks = [t for t in user.tasks.values() if t.status.value == "active"]
        avg_streak = sum(t.current_streak for t in active_tasks) / len(active_tasks) if active_tasks else 0
        
        if avg_streak < 3:
            suggestion = """🤖 **AI Совет**

Замечаю, что streak'и еще небольшие. Несколько советов:

• 🎯 Фокусируйтесь на 1-2 задачах максимум
• ⏰ Выполняйте задачи в одно и то же время
• 🔔 Включите напоминания в настройках
• 📝 Начинайте с самой простой задачи дня

Постоянство важнее интенсивности!"""
        elif avg_streak < 7:
            suggestion = """🤖 **AI Совет**

Отличное начало! Несколько идей для укрепления привычек:

• 🏆 Награждайте себя за каждые 7 дней streak'а
• 📊 Регулярно проверяйте статистику для мотивации  
• 🔄 Добавьте разнообразие в существующие задачи
• 👥 Поделитесь прогрессом с друзьями

Вы на пути к формированию устойчивых привычек!"""
        else:
            suggestion = """🤖 **AI Совет**

Впечатляющие результаты! Время для роста:

• 📈 Рассмотрите возможность усложнения задач
• 🎯 Добавьте новую привычку в смежной области
• 📝 Ведите заметки о своих успехах
• 🌟 Станьте примером для других пользователей

Вы мастер привычек! 👑"""
    
    await update.message.reply_text(suggestion, parse_mode='Markdown')

async def motivational_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка мотивационного сообщения"""
    message = random.choice(MOTIVATIONAL_MESSAGES)
    await update.message.reply_text(message)

def check_achievements(user, db: DatabaseManager) -> list:
    """Проверка новых достижений пользователя"""
    new_achievements = []
    
    # Первая задача
    if len(user.tasks) == 1 and 'first_task' not in user.achievements:
        user.achievements.append('first_task')
        new_achievements.append(ACHIEVEMENT_MESSAGES['first_task'])
    
    # Streak достижения
    max_streak = max([task.current_streak for task in user.tasks.values() 
                     if task.status.value == "active"], default=0)
    
    if max_streak >= 7 and 'streak_7' not in user.achievements:
        user.achievements.append('streak_7')
        new_achievements.append(ACHIEVEMENT_MESSAGES['streak_7'])
    
    if max_streak >= 30 and 'streak_30' not in user.achievements:
        user.achievements.append('streak_30')
        new_achievements.append(ACHIEVEMENT_MESSAGES['streak_30'])
    
    if max_streak >= 100 and 'streak_100' not in user.achievements:
        user.achievements.append('streak_100')
        new_achievements.append(ACHIEVEMENT_MESSAGES['streak_100'])
    
    # Достижения по количеству выполнений
    total_completed = user.stats.completed_tasks
    
    if total_completed >= 10 and 'tasks_10' not in user.achievements:
        user.achievements.append('tasks_10')
        new_achievements.append(ACHIEVEMENT_MESSAGES['tasks_10'])
    
    if total_completed >= 50 and 'tasks_50' not in user.achievements:
        user.achievements.append('tasks_50')
        new_achievements.append(ACHIEVEMENT_MESSAGES['tasks_50'])
    
    if total_completed >= 100 and 'tasks_100' not in user.achievements:
        user.achievements.append('tasks_100')
        new_achievements.append(ACHIEVEMENT_MESSAGES['tasks_100'])
    
    if new_achievements:
        db.save_user(user)
    
    return new_achievements

def setup_ai_handlers(app, db, config):
    """Настройка обработчиков для AI функций"""
    app.add_handler(CommandHandler("suggest", lambda u, c: get_ai_suggestion(u, c, db)))
    app.add_handler(CommandHandler("motivate", motivational_message))

# ===== handlers/reminders.py =====
import asyncio
import schedule
import time
from datetime import datetime, time as dt_time
from telegram.ext import ContextTypes
import threading
import logging

from database import DatabaseManager
from .ai_functions import check_achievements, MOTIVATIONAL_MESSAGES
import random

logger = logging.getLogger(__name__)

class ReminderSystem:
    """Система напоминаний и автоматических уведомлений"""
    
    def __init__(self, app, db: DatabaseManager):
        self.app = app
        self.db = db
        self.scheduler_thread = None
        self.running = False
    
    def start(self):
        """Запуск системы напоминаний"""
        if self.running:
            return
        
        self.running = True
        
        # Настраиваем расписание
        schedule.every().day.at("09:00").do(self._send_daily_reminders)
        schedule.every().day.at("21:00").do(self._send_evening_summary)
        schedule.every().sunday.at("10:00").do(self._send_weekly_stats)
        schedule.every().hour.do(self._check_achievements)
        
        # Запускаем планировщик в отдельном потоке
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("Система напоминаний запущена")
    
    def stop(self):
        """Остановка системы напоминаний"""
        self.running = False
        schedule.clear()
        logger.info("Система напоминаний остановлена")
    
    def _run_scheduler(self):
        """Запуск планировщика в отдельном потоке"""
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту
    
    async def _send_daily_reminders(self):
        """Отправка ежедневных напоминаний"""
        try:
            all_users = self.db.get_all_users()
            
            for user in all_users:
                if not user.settings.reminder_enabled:
                    continue
                
                # Проверяем активные задачи
                active_tasks = [t for t in user.tasks.values() if t.status.value == "active"]
                
                if not active_tasks:
                    continue
                
                # Формируем напоминание
                reminder_text = f"🌅 **Доброе утро!**\n\n"
                reminder_text += f"У вас {len(active_tasks)} активных задач на сегодня:\n\n"
                
                for i, task in enumerate(active_tasks[:5], 1):
                    reminder_text += f"{i}. {task.title}\n"
                
                if len(active_tasks) > 5:
                    reminder_text += f"... и еще {len(active_tasks) - 5} задач\n"
                
                reminder_text += f"\n💪 Продуктивного дня!"
                
                # Отправляем напоминание
                await self.app.bot.send_message(
                    chat_id=user.user_id,
                    text=reminder_text,
                    parse_mode='Markdown'
                )
                
                # Небольшая пауза между отправками
                await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Ошибка отправки ежедневных напоминаний: {e}")
    
    async def _send_evening_summary(self):
        """Отправка вечерней сводки"""
        try:
            all_users = self.db.get_all_users()
            today = datetime.now().date()
            
            for user in all_users:
                if not user.settings.reminder_enabled:
                    continue
                
                # Считаем выполненные сегодня задачи
                completed_today = 0
                total_active = 0
                
                for task in user.tasks.values():
                    if task.status.value == "active":
                        total_active += 1
                        for completion in task.completions:
                            if completion.date == today and completion.completed:
                                completed_today += 1
                                break
                
                if total_active == 0:
                    continue
                
                # Формируем сводку
                completion_rate = (completed_today / total_active) * 100
                
                if completion_rate == 100:
                    emoji = "🏆"
                    message = "Идеальный день!"
                elif completion_rate >= 80:
                    emoji = "🔥"
                    message = "Отличный результат!"
                elif completion_rate >= 60:
                    emoji = "👍"
                    message = "Хороший прогресс!"
                elif completion_rate >= 40:
                    emoji = "📈"
                    message = "Есть над чем поработать"
                else:
                    emoji = "💪"
                    message = "Завтра новый день!"
                
                summary_text = f"🌆 **Итоги дня**\n\n"
                summary_text += f"{emoji} {message}\n\n"
                summary_text += f"Выполнено: {completed_today}/{total_active} задач ({completion_rate:.0f}%)\n\n"
                
                if completion_rate > 0:
                    summary_text += f"{random.choice(MOTIVATIONAL_MESSAGES)}"
                else:
                    summary_text += "Помните: каждый день - новая возможность! 🌟"
                
                await self.app.bot.send_message(
                    chat_id=user.user_id,
                    text=summary_text,
                    parse_mode='Markdown'
                )
                
                await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Ошибка отправки вечерней сводки: {e}")
    
    async def _send_weekly_stats(self):
        """Отправка еженедельной статистики"""
        try:
            all_users = self.db.get_all_users()
            
            for user in all_users:
                if not user.settings.weekly_stats:
                    continue
                
                # Считаем статистику за неделю
                week_completions = 0
                today = datetime.now().date()
                week_start = today - datetime.timedelta(days=7)
                
                for task in user.tasks.values():
                    for completion in task.completions:
                        if completion.date >= week_start and completion.completed:
                            week_completions += 1
                
                # Считаем streak'и
                current_streaks = [task.current_streak for task in user.tasks.values() 
                                 if task.status.value == "active"]
                max_streak = max(current_streaks) if current_streaks else 0
                avg_streak = sum(current_streaks) / len(current_streaks) if current_streaks else 0
                
                stats_text = f"📊 **Статистика за неделю**\n\n"
                stats_text += f"✅ Выполнений: {week_completions}\n"
                stats_text += f"🔥 Максимальный streak: {max_streak} дней\n"
                stats_text += f"📈 Средний streak: {avg_streak:.1f} дней\n\n"
                
                if week_completions > 0:
                    stats_text += "🎯 Отличная работа на этой неделе!\n"
                    stats_text += "Продолжайте поддерживать темп! 💪"
                else:
                    stats_text += "💡 Новая неделя - новые возможности!\n"
                    stats_text += "Начните с малого и постепенно наращивайте темп! 🌟"
                
                await self.app.bot.send_message(
                    chat_id=user.user_id,
                    text=stats_text,
                    parse_mode='Markdown'
                )
                
                await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Ошибка отправки еженедельной статистики: {e}")
    
    async def _check_achievements(self):
        """Проверка и отправка новых достижений"""
        try:
            all_users = self.db.get_all_users()
            
            for user in all_users:
                if not user.settings.motivational_messages:
                    continue
                
                # Проверяем новые достижения
                new_achievements = check_achievements(user, self.db)
                
                # Отправляем уведомления о новых достижениях
                for achievement in new_achievements:
                    await self.app.bot.send_message(
                        chat_id=user.user_id,
                        text=f"🏆 **Новое достижение!**\n\n{achievement}",
                        parse_mode='Markdown'
                    )
                    await asyncio.sleep(0.5)
        
        except Exception as e:
            logger.error(f"Ошибка проверки достижений: {e}")

# Глобальная переменная для системы напоминаний
reminder_system = None

def setup_reminder_system(app, db):
    """Настройка системы напоминаний"""
    global reminder_system
    reminder_system = ReminderSystem(app, db)
    reminder_system.start()
    return reminder_system

def stop_reminder_system():
    """Остановка системы напоминаний"""
    global reminder_system
    if reminder_system:
        reminder_system.stop()

# ===== Обновление main.py для интеграции напоминаний =====
# Добавить в класс DailyCheckBot:

async def setup_with_reminders(self):
    """Настройка бота с системой напоминаний"""
    await self.setup()
    
    # Настраиваем систему напоминаний
    from handlers.reminders import setup_reminder_system
    self.reminder_system = setup_reminder_system(self.application, self.db)

async def stop_with_reminders(self):
    """Остановка бота с системой напоминаний"""
    from handlers.reminders import stop_reminder_system
    stop_reminder_system()
    await self.stop()

# ===== Обновление requirements.txt =====
# Добавить в requirements.txt:
# schedule==1.2.0

# ===== Дополнительные модели для достижений =====
# models/achievement.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass 
class Achievement:
    """Модель достижения"""
    achievement_id: str
    title: str
    description: str
    icon: str
    condition: str  # Условие получения
    earned_at: Optional[datetime] = None
    
    @property
    def is_earned(self) -> bool:
        return self.earned_at is not None

# Предустановленные достижения
ACHIEVEMENTS_DATA = {
    'first_task': Achievement(
        achievement_id='first_task',
        title='Первые шаги',
        description='Создайте свою первую задачу',
        icon='🎯',
        condition='Создать 1 задачу'
    ),
    'streak_7': Achievement(
        achievement_id='streak_7', 
        title='Неделя силы',
        description='Поддерживайте streak 7 дней',
        icon='🔥',
        condition='Достичь streak 7 дней'
    ),
    'streak_30': Achievement(
        achievement_id='streak_30',
        title='Мастер привычек',
        description='Поддерживайте streak 30 дней',
        icon='💎',
        condition='Достичь streak 30 дней'
    ),
    'streak_100': Achievement(
        achievement_id='streak_100',
        title='Легенда',
        description='Поддерживайте streak 100 дней',
        icon='👑',
        condition='Достичь streak 100 дней'
    ),
    'tasks_10': Achievement(
        achievement_id='tasks_10',
        title='Начинающий',
        description='Выполните 10 задач',
        icon='📈',
        condition='Выполнить 10 задач'
    ),
    'tasks_50': Achievement(
        achievement_id='tasks_50',
        title='Энтузиаст',
        description='Выполните 50 задач',
        icon='🏆',
        condition='Выполнить 50 задач'
    ),
    'tasks_100': Achievement(
        achievement_id='tasks_100',
        title='Чемпион',
        description='Выполните 100 задач',
        icon='🌟',
        condition='Выполнить 100 задач'
    )
}
