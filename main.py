#!/usr/bin/env python3

import os
import sys
import logging
import threading
import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import hashlib
import uuid
import random
import csv
from io import StringIO

# Исправление event loop конфликтов
try:
    import nest_asyncio
    nest_asyncio.apply()
    print("✅ nest_asyncio применен")
except ImportError:
    print("⚠️ nest_asyncio недоступен")

# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Переменные окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден!")
    sys.exit(1)

logger.info(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")
if OPENAI_API_KEY:
    logger.info(f"✅ OpenAI: {OPENAI_API_KEY[:10]}...")

# ===================== СТРУКТУРЫ ДАННЫХ =====================

# Глобальные данные пользователей
users_data = {}
user_achievements = {}
user_themes = {}
user_ai_chat = {}
user_friends = {}
user_timers = {}
user_reminders = {}
global_stats = {"total_users": 0, "commands_executed": 0, "tasks_completed": 0, "ai_requests": 0}

# Уровни и достижения
LEVELS = [
    "🌱 Новичок", "🌿 Росток", "🌾 Саженец", "🌳 Дерево", "🍀 Удачливый",
    "💪 Сильный", "🧠 Умный", "🎯 Целеустремленный", "⚡ Энергичный", "🔥 Огненный",
    "💎 Алмазный", "👑 Королевский", "🌟 Звездный", "🚀 Космический", "🏆 Легендарный", "👹 Божественный"
]

ACHIEVEMENTS = [
    {"name": "Первые шаги", "desc": "Добавить первую задачу", "emoji": "👶", "xp_reward": 10},
    {"name": "Продуктивный день", "desc": "Выполнить 5 задач за день", "emoji": "💪", "xp_reward": 50},
    {"name": "Марафонец", "desc": "7 дней подряд выполнять задачи", "emoji": "🏃", "xp_reward": 100},
    {"name": "Планировщик", "desc": "Создать 20 задач", "emoji": "📋", "xp_reward": 75},
    {"name": "Социальный", "desc": "Добавить 3 друзей", "emoji": "👥", "xp_reward": 60},
    {"name": "AI Фанат", "desc": "Сделать 50 AI запросов", "emoji": "🤖", "xp_reward": 80},
    {"name": "Мастер времени", "desc": "Использовать таймер 10 раз", "emoji": "⏰", "xp_reward": 40},
    {"name": "Аналитик", "desc": "Посмотреть статистику 15 раз", "emoji": "📊", "xp_reward": 30},
    {"name": "Целеустремленный", "desc": "Выполнить еженедельную цель", "emoji": "🎯", "xp_reward": 90},
    {"name": "Легенда", "desc": "Достичь 16 уровня", "emoji": "👑", "xp_reward": 200}
]

CATEGORIES = {
    "work": {"name": "🏢 Работа", "emoji": "🏢"},
    "health": {"name": "💪 Здоровье", "emoji": "💪"},
    "study": {"name": "📚 Обучение", "emoji": "📚"},
    "personal": {"name": "👨‍👩‍👧‍👦 Личное", "emoji": "👨‍👩‍👧‍👦"},
    "finance": {"name": "💰 Финансы", "emoji": "💰"}
}

PRIORITIES = {
    "low": {"name": "🟢 Низкий", "emoji": "🟢", "value": 1},
    "medium": {"name": "🟡 Средний", "emoji": "🟡", "value": 2},
    "high": {"name": "🔴 Высокий", "emoji": "🔴", "value": 3}
}

THEMES = {
    "dark": {"name": "🌙 Темная", "emoji": "🌙", "accent": "⭐"},
    "light": {"name": "☀️ Светлая", "emoji": "☀️", "accent": "🌟"},
    "rainbow": {"name": "🌈 Радужная", "emoji": "🌈", "accent": "✨"},
    "crystal": {"name": "💎 Кристальная", "emoji": "💎", "accent": "💫"},
    "creative": {"name": "🎨 Креативная", "emoji": "🎨", "accent": "🎭"}
}

# ===================== HTTP СЕРВЕР =====================

def start_health_server():
    import http.server
    import socketserver
    
    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            data = {
                "status": "ok",
                "service": "dailycheck-bot",
                "version": "4.0",
                "features": "FULL",
                "users": global_stats["total_users"],
                "commands": global_stats["commands_executed"],
                "tasks_completed": global_stats["tasks_completed"],
                "ai_requests": global_stats["ai_requests"],
                "uptime": time.time(),
                "total_commands": 32,
                "message": "Bot is running with ALL features!"
            }
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
        
        def log_message(self, format, *args):
            if '/health' in format or self.path == '/':
                logger.info(f"Health check: {self.client_address[0]}")
    
    def run_server():
        try:
            with socketserver.TCPServer(("0.0.0.0", PORT), HealthHandler) as httpd:
                logger.info(f"✅ HTTP сервер ЗАПУЩЕН на 0.0.0.0:{PORT}")
                httpd.serve_forever()
        except Exception as e:
            logger.error(f"❌ HTTP server ошибка: {e}")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)
    logger.info(f"🌐 Health check доступен на http://0.0.0.0:{PORT}")
    return server_thread

# ===================== УТИЛИТЫ И СОХРАНЕНИЕ ДАННЫХ =====================

def save_user_data():
    """Сохранение данных пользователей в файлы"""
    try:
        os.makedirs('data', exist_ok=True)
        
        all_data = {
            'users_data': users_data,
            'user_achievements': user_achievements,
            'user_themes': user_themes,
            'user_ai_chat': user_ai_chat,
            'user_friends': user_friends,
            'user_timers': user_timers,
            'user_reminders': user_reminders,
            'global_stats': global_stats,
            'last_saved': datetime.now().isoformat()
        }
        
        with open('data/bot_data.json', 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info("💾 Данные сохранены")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения данных: {e}")

def load_user_data():
    """Загрузка данных пользователей из файлов"""
    try:
        with open('data/bot_data.json', 'r', encoding='utf-8') as f:
            all_data = json.load(f)
            
        global users_data, user_achievements, user_themes, user_ai_chat, user_friends
        global user_timers, user_reminders, global_stats
        
        users_data.update(all_data.get('users_data', {}))
        user_achievements.update(all_data.get('user_achievements', {}))
        user_themes.update(all_data.get('user_themes', {}))
        user_ai_chat.update(all_data.get('user_ai_chat', {}))
        user_friends.update(all_data.get('user_friends', {}))
        user_timers.update(all_data.get('user_timers', {}))
        user_reminders.update(all_data.get('user_reminders', {}))
        global_stats.update(all_data.get('global_stats', {}))
        
        logger.info(f"📂 Загружены данные для {len(users_data)} пользователей")
    except FileNotFoundError:
        logger.info("📂 Файл данных не найден, начинаем с пустой базы")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки данных: {e}")

def init_user(user_id: int) -> None:
    """Инициализация нового пользователя"""
    if user_id not in users_data:
        users_data[user_id] = {
            "tasks": [],
            "completed_today": 0,
            "streak": 0,
            "last_activity": datetime.now().strftime("%Y-%m-%d"),
            "xp": 0,
            "level": 0,
            "weekly_goals": [],
            "dry_mode": False,
            "dry_days": 0,
            "created_at": datetime.now().isoformat(),
            "stats_views": 0,
            "timer_uses": 0,
            "total_tasks_created": 0,
            "total_tasks_completed": 0
        }
        user_achievements[user_id] = []
        user_themes[user_id] = "dark"
        user_ai_chat[user_id] = False
        user_friends[user_id] = []
        user_timers[user_id] = []
        user_reminders[user_id] = []
        global_stats["total_users"] += 1
        save_user_data()

def get_user_level(xp: int) -> Tuple[int, str]:
    """Получить уровень пользователя по XP"""
    level = min(xp // 100, len(LEVELS) - 1)
    return level, LEVELS[level]

def add_xp(user_id: int, amount: int) -> str:
    """Добавить XP пользователю и проверить новый уровень"""
    old_level = get_user_level(users_data[user_id]["xp"])[0]
    users_data[user_id]["xp"] += amount
    new_level = get_user_level(users_data[user_id]["xp"])[0]
    
    if new_level > old_level:
        return f"🎉 Поздравляем! Новый уровень: {LEVELS[new_level]}"
    return f"+{amount} XP"

def check_achievements(user_id: int) -> List[str]:
    """Проверка достижений пользователя"""
    user = users_data[user_id]
    new_achievements = []
    
    # Проверка условий для достижений
    checks = [
        (user["total_tasks_created"] >= 1, 0),  # Первые шаги
        (user["completed_today"] >= 5, 1),      # Продуктивный день
        (user["streak"] >= 7, 2),               # Марафонец
        (user["total_tasks_created"] >= 20, 3), # Планировщик
        (len(user_friends[user_id]) >= 3, 4),   # Социальный
        (global_stats.get("ai_requests", 0) >= 50, 5),  # AI Фанат
        (user["timer_uses"] >= 10, 6),          # Мастер времени
        (user["stats_views"] >= 15, 7),         # Аналитик
        (len(user["weekly_goals"]) > 0, 8),     # Целеустремленный
        (get_user_level(user["xp"])[0] >= 15, 9) # Легенда
    ]
    
    for condition, achievement_id in checks:
        if condition and achievement_id not in user_achievements[user_id]:
            user_achievements[user_id].append(achievement_id)
            achievement = ACHIEVEMENTS[achievement_id]
            add_xp(user_id, achievement["xp_reward"])
            new_achievements.append(f"{achievement['emoji']} {achievement['name']}")
    
    return new_achievements

def log_command(user_id: int, command: str):
    """Логирование команд"""
    global_stats["commands_executed"] += 1
    logger.info(f"Команда {command} от пользователя {user_id}")

# ===================== TELEGRAM ИМПОРТЫ =====================

try:
    from telegram.ext import (Application, ApplicationBuilder, CommandHandler, 
                             MessageHandler, filters, CallbackQueryHandler)
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ContextTypes
    logger.info("✅ Telegram библиотеки импортированы")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта Telegram: {e}")
    sys.exit(1)

# ===================== ОСНОВНЫЕ КОМАНДЫ =====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню и интерактивный список задач"""
    user = update.effective_user
    user_id = user.id
    init_user(user_id)
    log_command(user_id, "/start")
    
    # Получаем данные пользователя
    user_data = users_data[user_id]
    theme = THEMES[user_themes[user_id]]
    level_info = get_user_level(user_data["xp"])
    
    # Время суток для приветствия
    current_hour = datetime.now().hour
    if 5 <= current_hour < 12:
        greeting = "🌅 Доброе утро"
    elif 12 <= current_hour < 17:
        greeting = "☀️ Добрый день"
    elif 17 <= current_hour < 22:
        greeting = "🌆 Добрый вечер"
    else:
        greeting = "🌙 Доброй ночи"
    
    # Интерактивная клавиатура
    keyboard = [
        [InlineKeyboardButton(f"📋 Мои задачи ({len(user_data['tasks'])})", callback_data="show_tasks")],
        [InlineKeyboardButton(f"📊 Статистика", callback_data="show_stats"), 
         InlineKeyboardButton(f"🏆 Достижения ({len(user_achievements[user_id])})", callback_data="show_achievements")],
        [InlineKeyboardButton(f"🤖 AI Помощь", callback_data="show_ai_help"),
         InlineKeyboardButton(f"⚙️ Настройки", callback_data="show_settings")],
        [InlineKeyboardButton(f"{theme['accent']} Случайная задача", callback_data="random_task"),
         InlineKeyboardButton(f"🎯 Цели недели", callback_data="show_weekly_goals")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Основной текст
    text = (
        f"{greeting}, {user.first_name}!\n\n"
        f"🤖 DailyCheck Bot v4.0 - ваш AI помощник!\n\n"
        f"📊 Уровень: {level_info[1]}\n"
        f"⚡ XP: {user_data['xp']}\n"
        f"🔥 Стрик: {user_data['streak']} дней\n"
        f"✅ Сегодня выполнено: {user_data['completed_today']}\n\n"
        f"🎨 Тема: {theme['name']}\n\n"
        f"Выберите действие:"
    )
    
    await update.message.reply_text(text, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Полная справка по всем командам"""
    help_text = """
📚 **DailyCheck Bot v4.0 - Полная справка**

🔸 **Управление задачами:**
• `/start` - Главное меню и интерактивный список задач
• `/tasks` - Быстрый доступ к задачам
• `/edit` - Редактировать список задач
• `/settasks задача1; задача2` - Быстро установить список задач
• `/addtask название [категория] [приоритет] [время]` - Добавить задачу
• `/addsub <номер> подзадача` - Добавить подзадачу
• `/reset` - Сбросить прогресс дня

🔸 **AI-функции:**
• `/ai_chat` - Включить/выключить AI-чат режим
• `/motivate [текст]` - Получить мотивационное сообщение
• `/ai_coach [вопрос]` - Персональный AI-коуч
• `/psy [проблема]` - Консультация с AI-психологом
• `/suggest_tasks [категория]` - AI предложит задачи

🔸 **Статистика и аналитика:**
• `/stats` - Детальная статистика
• `/analytics` - Продвинутая аналитика
• `/weekly_goals` - Еженедельные цели
• `/set_weekly цель1; цель2` - Установить цели

🔸 **Социальные функции:**
• `/friends` - Список друзей
• `/add_friend <ID>` - Добавить друга
• `/myid` - Узнать свой ID

🔸 **Утилиты:**
• `/timer <минуты>` - Установить таймер
• `/remind <минуты> <текст>` - Создать напоминание
• `/export` - Экспорт данных
• `/theme [номер]` - Сменить тему оформления
• `/settings` - Настройки пользователя

🔸 **Специальные режимы:**
• `/dryon` - Начать отчет дней без алкоголя
• `/dryoff` - Завершить отчет дней без алкоголя

🔸 **Системные:**
• `/health` - Состояние системы
• `/ping` - Проверка работы бота
• `/test` - Тестовая команда (админ)

🔸 **Администрирование:**
• `/broadcast <сообщение>` - Рассылка всем пользователям
• `/stats_global` - Глобальная статистика

💡 **Подсказки:**
- Включите AI-чат режим (`/ai_chat`) для свободного общения
- Используйте кнопки в `/start` для быстрой навигации
- Добавляйте друзей для соревнований и мотивации
- Устанавливайте еженедельные цели для лучших результатов

🎮 **Геймификация:**
- Получайте XP за выполнение задач
- Открывайте новые достижения
- Соревнуйтесь с друзьями
- Поднимайтесь по уровням от Новичка до Божественного!
"""
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка работы бота"""
    ping_text = (
        f"🏓 Понг!\n\n"
        f"✅ Бот: работает отлично\n"
        f"🤖 AI: {'подключен' if OPENAI_API_KEY else 'недоступен'}\n"
        f"👥 Пользователей: {global_stats['total_users']}\n"
        f"📊 Команд выполнено: {global_stats['commands_executed']}\n"
        f"🌐 Сервер: порт {PORT}\n"
        f"⚡ Готов к работе!"
    )
    await update.message.reply_text(ping_text)

# ===================== УПРАВЛЕНИЕ ЗАДАЧАМИ =====================

async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрый доступ к задачам"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/tasks")
    
    tasks = users_data[user_id]["tasks"]
    if not tasks:
        keyboard = [
            [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task_dialog")],
            [InlineKeyboardButton("📝 Быстрая установка", callback_data="quick_setup")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📋 У вас пока нет задач.\n\n"
            "Добавьте первую задачу и начните путь к продуктивности!",
            reply_markup=reply_markup
        )
        return
    
    text = "📋 **Ваши задачи:**\n\n"
    keyboard = []
    
    for i, task in enumerate(tasks):
        status = "✅" if task.get("completed", False) else "⭕"
        priority_emoji = PRIORITIES[task.get("priority", "medium")]["emoji"]
        category_emoji = CATEGORIES[task.get("category", "personal")]["emoji"]
        
        text += f"{status} {i+1}. {task['name']}\n"
        text += f"   {category_emoji} {priority_emoji}"
        if task.get("estimate"):
            text += f" ⏱️ {task['estimate']} мин"
        
        # Подзадачи
        if task.get("subtasks"):
            text += f"\n   📝 Подзадачи ({len(task['subtasks'])}):"
            for j, subtask in enumerate(task["subtasks"]):
                sub_status = "✅" if subtask.get("completed", False) else "⭕"
                text += f"\n      {sub_status} {j+1}. {subtask['name']}"
        
        text += "\n\n"
        
        # Кнопки для незавершенных задач
        if not task.get("completed", False):
            keyboard.append([InlineKeyboardButton(f"✅ Задача {i+1}", callback_data=f"complete_task_{i}")])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить", callback_data="add_task_dialog"),
         InlineKeyboardButton("✏️ Редактировать", callback_data="edit_tasks")],
        [InlineKeyboardButton("🔄 Сбросить день", callback_data="reset_day")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def settasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстро установить список задач через точку с запятой"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/settasks")
    
    if not context.args:
        await update.message.reply_text(
            "📝 **Быстрая установка задач**\n\n"
            "Формат: `/settasks задача1; задача2; задача3`\n\n"
            "Пример:\n"
            "`/settasks Проверить почту; Сделать зарядку; Прочитать 20 страниц книги`\n\n"
            "💡 Задачи будут добавлены с категорией 'Личное' и средним приоритетом"
        )
        return
    
    tasks_text = " ".join(context.args)
    task_names = [task.strip() for task in tasks_text.split(";") if task.strip()]
    
    if not task_names:
        await update.message.reply_text("❌ Не найдено ни одной задачи. Проверьте формат!")
        return
    
    # Очищаем старые задачи
    users_data[user_id]["tasks"] = []
    
    # Добавляем новые задачи
    for name in task_names:
        task = {
            "name": name,
            "completed": False,
            "created_at": datetime.now().isoformat(),
            "category": "personal",
            "priority": "medium",
            "subtasks": []
        }
        users_data[user_id]["tasks"].append(task)
        users_data[user_id]["total_tasks_created"] += 1
    
    xp_reward = len(task_names) * 5
    xp_msg = add_xp(user_id, xp_reward)
    achievements = check_achievements(user_id)
    
    save_user_data()
    
    response = f"✅ Добавлено {len(task_names)} задач!\n{xp_msg}"
    if achievements:
        response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
    
    await update.message.reply_text(response)

async def addtask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить задачу с параметрами"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/addtask")
    
    if not context.args:
        categories_text = "\n".join([f"• {key} - {cat['name']}" for key, cat in CATEGORIES.items()])
        priorities_text = "\n".join([f"• {key} - {pri['name']}" for key, pri in PRIORITIES.items()])
        
        await update.message.reply_text(
            f"➕ **Добавление задачи**\n\n"
            f"Формат: `/addtask название [категория] [приоритет] [время]`\n\n"
            f"Пример:\n"
            f"`/addtask Написать отчет work high 60`\n\n"
            f"📋 Категории:\n{categories_text}\n\n"
            f"🎯 Приоритеты:\n{priorities_text}",
            parse_mode="Markdown"
        )
        return
    
    args = context.args
    name = args[0]
    category = "personal"
    priority = "medium"
    estimate = None
    
    # Парсинг дополнительных параметров
    if len(args) > 1:
        for arg in args[1:]:
            if arg.lower() in CATEGORIES:
                category = arg.lower()
            elif arg.lower() in PRIORITIES:
                priority = arg.lower()
            elif arg.isdigit():
                estimate = int(arg)
    
    task = {
        "name": name,
        "completed": False,
        "created_at": datetime.now().isoformat(),
        "category": category,
        "priority": priority,
        "estimate": estimate,
        "subtasks": []
    }
    
    users_data[user_id]["tasks"].append(task)
    users_data[user_id]["total_tasks_created"] += 1
    
    xp_msg = add_xp(user_id, 10)
    achievements = check_achievements(user_id)
    
    save_user_data()
    
    cat_info = CATEGORIES[category]["name"]
    pri_info = PRIORITIES[priority]["name"]
    
    response = f"✅ Задача добавлена!\n"
    response += f"📝 {name}\n"
    response += f"📂 {cat_info}\n"
    response += f"🎯 {pri_info}\n"
    if estimate:
        response += f"⏱️ {estimate} минут\n"
    response += f"\n{xp_msg}"
    
    if achievements:
        response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
    
    await update.message.reply_text(response)

async def addsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить подзадачу к существующей задаче"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/addsub")
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "📝 **Добавление подзадачи**\n\n"
            "Формат: `/addsub <номер_задачи> <название_подзадачи>`\n\n"
            "Пример: `/addsub 1 Собрать материалы`\n\n"
            "Используйте `/tasks` чтобы посмотреть номера задач"
        )
        return
    
    try:
        task_number = int(context.args[0]) - 1
        subtask_name = " ".join(context.args[1:])
        
        if task_number < 0 or task_number >= len(users_data[user_id]["tasks"]):
            await update.message.reply_text("❌ Неверный номер задачи!")
            return
        
        subtask = {
            "name": subtask_name,
            "completed": False,
            "created_at": datetime.now().isoformat()
        }
        
        users_data[user_id]["tasks"][task_number]["subtasks"].append(subtask)
        
        xp_msg = add_xp(user_id, 5)
        save_user_data()
        
        task_name = users_data[user_id]["tasks"][task_number]["name"]
        response = f"✅ Подзадача добавлена!\n"
        response += f"📝 {subtask_name}\n"
        response += f"📋 К задаче: {task_name}\n"
        response += f"{xp_msg}"
        
        await update.message.reply_text(response)
        
    except ValueError:
        await update.message.reply_text("❌ Номер задачи должен быть числом!")

async def edit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактировать список задач"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/edit")
    
    tasks = users_data[user_id]["tasks"]
    if not tasks:
        await update.message.reply_text("📋 Нет задач для редактирования. Добавьте задачи командой `/addtask`")
        return
    
    keyboard = []
    for i, task in enumerate(tasks):
        status = "✅" if task.get("completed", False) else "⭕"
        keyboard.append([InlineKeyboardButton(
            f"{status} {i+1}. {task['name'][:30]}...", 
            callback_data=f"edit_task_{i}"
        )])
    
    keyboard.append([InlineKeyboardButton("🗑️ Удалить все задачи", callback_data="delete_all_tasks")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✏️ **Редактирование задач**\n\nВыберите задачу для изменения:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбросить прогресс дня"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/reset")
    
    keyboard = [
        [InlineKeyboardButton("✅ Да, сбросить", callback_data="confirm_reset")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_reset")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔄 **Сброс прогресса дня**\n\n"
        "Это действие:\n"
        "• Пометит все задачи как невыполненные\n"
        "• Сбросит счетчик выполненных задач за день\n"
        "• НЕ удалит ваши задачи\n\n"
        "Вы уверены?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ===================== СТАТИСТИКА И АНАЛИТИКА =====================

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Детальная статистика"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/stats")
    
    users_data[user_id]["stats_views"] += 1
    user = users_data[user_id]
    level_info = get_user_level(user["xp"])
    
    total_tasks = len(user["tasks"])
    completed_tasks = sum(1 for task in user["tasks"] if task.get("completed", False))
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Статистика по категориям
    category_stats = {}
    for task in user["tasks"]:
        cat_key = task.get("category", "personal")
        cat_name = CATEGORIES[cat_key]["name"]
        if cat_name not in category_stats:
            category_stats[cat_name] = {"total": 0, "completed": 0}
        category_stats[cat_name]["total"] += 1
        if task.get("completed", False):
            category_stats[cat_name]["completed"] += 1
    
    # Статистика по приоритетам
    priority_stats = {}
    for task in user["tasks"]:
        pri_key = task.get("priority", "medium")
        pri_name = PRIORITIES[pri_key]["name"]
        if pri_name not in priority_stats:
            priority_stats[pri_name] = {"total": 0, "completed": 0}
        priority_stats[pri_name]["total"] += 1
        if task.get("completed", False):
            priority_stats[pri_name]["completed"] += 1
    
    text = f"📊 **Детальная статистика**\n\n"
    text += f"👤 Уровень: {level_info[1]}\n"
    text += f"⚡ XP: {user['xp']}/{(level_info[0] + 1) * 100}\n"
    text += f"🔥 Стрик: {user['streak']} дней\n"
    text += f"📋 Всего задач: {total_tasks}\n"
    text += f"✅ Выполнено: {completed_tasks}\n"
    text += f"📈 Процент выполнения: {completion_rate:.1f}%\n\n"
    
    if category_stats:
        text += "📊 **По категориям:**\n"
        for cat, stats in category_stats.items():
            rate = (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            text += f"{cat}: {stats['completed']}/{stats['total']} ({rate:.0f}%)\n"
        text += "\n"
    
    if priority_stats:
        text += "🎯 **По приоритетам:**\n"
        for pri, stats in priority_stats.items():
            rate = (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            text += f"{pri}: {stats['completed']}/{stats['total']} ({rate:.0f}%)\n"
        text += "\n"
    
    text += f"🏆 Достижений: {len(user_achievements[user_id])}/{len(ACHIEVEMENTS)}\n"
    text += f"👥 Друзей: {len(user_friends[user_id])}\n"
    text += f"⏰ Использовано таймеров: {user['timer_uses']}\n"
    text += f"📊 Просмотров статистики: {user['stats_views']}\n"
    
    achievements = check_achievements(user_id)
    if achievements:
        text += f"\n🏆 Новые достижения: {', '.join(achievements)}"
    
    save_user_data()
    await update.message.reply_text(text, parse_mode="Markdown")

async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Продвинутая аналитика"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/analytics")
    
    user = users_data[user_id]
    
    # Анализ продуктивности
    text = f"📈 **Продвинутая аналитика**\n\n"
    
    # Рекомендуемые часы работы
    productive_hours = ["9:00-12:00", "14:00-17:00", "19:00-21:00"]
    text += f"⏰ **Рекомендуемые часы работы:**\n"
    for hour in productive_hours:
        text += f"   • {hour}\n"
    
    # Анализ XP роста
    xp_per_day = user["xp"] / max(1, (datetime.now() - datetime.fromisoformat(user["created_at"])).days)
    text += f"\n📊 **Анализ роста:**\n"
    text += f"   • Средний XP в день: {xp_per_day:.1f}\n"
    
    # Прогноз следующего уровня
    current_level = get_user_level(user["xp"])[0]
    next_level_xp = (current_level + 1) * 100
    xp_needed = next_level_xp - user["xp"]
    days_to_next_level = xp_needed / max(1, xp_per_day)
    
    text += f"   • XP до следующего уровня: {xp_needed}\n"
    text += f"   • Прогноз достижения: ~{days_to_next_level:.0f} дней\n"
    
    # Рекомендации
    total_tasks = len(user["tasks"])
    text += f"\n💡 **Персональные рекомендации:**\n"
    
    if total_tasks == 0:
        text += f"   • Добавьте первые задачи для начала планирования\n"
    elif total_tasks < 5:
        text += f"   • Добавьте больше задач для лучшего планирования\n"
    elif user["streak"] < 3:
        text += f"   • Попробуйте выполнять задачи каждый день\n"
    elif user["completed_today"] == 0:
        text += f"   • Начните день с выполнения простой задачи\n"
    else:
        text += f"   • Отличная работа! Продолжайте в том же духе!\n"
    
    # AI рекомендации (если доступно)
    if OPENAI_API_KEY:
        text += f"   • Используйте `/ai_coach` для персональных советов\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ===================== AI ФУНКЦИИ =====================

async def generate_ai_response(text: str, user_id: int = None, ai_type: str = "general") -> str:
    """Генерация AI ответов с fallback"""
    global_stats["ai_requests"] += 1
    
    if not OPENAI_API_KEY:
        fallback_responses = {
            "motivate": [
                "🔥 Вы можете всё! Каждый маленький шаг приближает к большой цели!",
                "💪 Сегодня отличный день для достижений!",
                "🌟 Ваш потенциал безграничен! Продолжайте двигаться вперед!",
                "🚀 Каждое завершенное дело - это победа! Празднуйте свои успехи!"
            ],
            "coach": [
                "📋 Совет: Разбейте большую задачу на маленькие части и выполняйте по одной.",
                "⏰ Используйте технику помодоро: 25 минут работы + 5 минут отдыха.",
                "🎯 Начинайте день с самой важной задачи, пока энергия на пике.",
                "📝 Записывайте все идеи и задачи, чтобы не держать их в голове."
            ],
            "psy": [
                "🧠 Помните: неудачи - это опыт. Важно не падение, а умение подняться.",
                "🌱 Стресс - это нормально. Важно найти здоровые способы с ним справляться.",
                "💚 Будьте добры к себе. Самокритика должна быть конструктивной.",
                "🔄 Изменения требуют времени. Будьте терпеливы к своему прогрессу."
            ],
            "general": [
                f"💡 Я запомнил ваш вопрос: '{text}'. AI временно недоступен, но я готов помочь!",
                "🤖 AI сервис недоступен, но вы можете использовать другие команды бота!",
                "⚙️ Настройте OPENAI_API_KEY для полноценной работы AI функций."
            ]
        }
        return random.choice(fallback_responses.get(ai_type, fallback_responses["general"]))
    
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        system_prompts = {
            "motivate": "Ты мотивационный коуч. Вдохновляй и поддерживай пользователя. Отвечай эмоционально и энергично.",
            "coach": "Ты эксперт по продуктивности. Давай конкретные практические советы по планированию и выполнению задач.",
            "psy": "Ты психолог-консультант. Помогай справляться со стрессом, находить баланс и решать эмоциональные проблемы.",
            "general": "Ты полезный AI-ассистент для продуктивности. Отвечай кратко, полезно и дружелюбно."
        }
        
        # Добавляем контекст пользователя
        context = ""
        if user_id and user_id in users_data:
            user = users_data[user_id]
            level_name = get_user_level(user['xp'])[1]
            context = f" Контекст пользователя: уровень {level_name}, {user['xp']} XP, {len(user['tasks'])} задач, стрик {user['streak']} дней, выполнено сегодня {user['completed_today']}."
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompts.get(ai_type, system_prompts["general"]) + context},
                {"role": "user", "content": text}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return f"🤖 {response.choices[0].message.content.strip()}"
        
    except Exception as e:
        logger.error(f"AI ошибка: {e}")
        return f"⚠️ Ошибка AI сервиса. Попробуйте позже!"

async def ai_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включить/выключить AI-чат режим"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/ai_chat")
    
    user_ai_chat[user_id] = not user_ai_chat[user_id]
    status = "включен" if user_ai_chat[user_id] else "выключен"
    
    text = f"🤖 **AI-чат режим {status}!**\n\n"
    if user_ai_chat[user_id]:
        text += "Теперь просто пишите мне сообщения, и я буду отвечать как AI-ассистент!\n\n"
        text += "💡 **Примеры запросов:**\n"
        text += "• \"Мотивируй меня\" - получите поддержку\n"
        text += "• \"Как планировать день?\" - советы по продуктивности\n"
        text += "• \"Устал от работы\" - психологическая поддержка\n"
        text += "• \"Какие задачи добавить?\" - предложения задач\n"
        text += "• \"Как дела?\" - анализ прогресса"
    else:
        text += "AI-чат выключен. Используйте команды для взаимодействия."
    
    save_user_data()
    await update.message.reply_text(text, parse_mode="Markdown")

async def motivate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить мотивационное сообщение"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/motivate")
    
    user_text = " ".join(context.args) if context.args else "мотивируй меня на продуктивный день"
    response = await generate_ai_response(user_text, user_id, "motivate")
    
    # Добавляем персонализированную мотивацию
    user = users_data[user_id]
    level_name = get_user_level(user['xp'])[1]
    
    motivation_bonus = f"\n\n⚡ Ваш уровень {level_name} говорит о ваших способностях!"
    if user['streak'] > 0:
        motivation_bonus += f"\n🔥 Стрик {user['streak']} дней - впечатляющий результат!"
    
    await update.message.reply_text(response + motivation_bonus)

async def ai_coach_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Персональный AI-коуч"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/ai_coach")
    
    user_text = " ".join(context.args) if context.args else "дай персональный совет по продуктивности"
    response = await generate_ai_response(user_text, user_id, "coach")
    await update.message.reply_text(response)

async def psy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Консультация с AI-психологом"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/psy")
    
    user_text = " ".join(context.args) if context.args else "помоги справиться со стрессом и найти баланс"
    response = await generate_ai_response(user_text, user_id, "psy")
    await update.message.reply_text(response)

async def suggest_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI предложит задачи"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/suggest_tasks")
    
    category = " ".join(context.args) if context.args else "продуктивность"
    prompt = f"Предложи 5 полезных и конкретных задач для категории '{category}'"
    response = await generate_ai_response(prompt, user_id, "coach")
    await update.message.reply_text(response)

# ===================== СОЦИАЛЬНЫЕ ФУНКЦИИ =====================

async def friends_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список друзей"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/friends")
    
    friends = user_friends[user_id]
    if not friends:
        text = "👥 **У вас пока нет друзей.**\n\n"
        text += "Используйте `/add_friend <ID>` чтобы добавить друга!\n"
        text += "Узнать свой ID: `/myid`"
    else:
        text = "👥 **Ваши друзья:**\n\n"
        for i, friend_id in enumerate(friends, 1):
            if friend_id in users_data:
                friend_data = users_data[friend_id]
                level = get_user_level(friend_data["xp"])[1]
                streak = friend_data["streak"]
                text += f"{i}. ID {friend_id}\n"
                text += f"   📊 {level} ({friend_data['xp']} XP)\n"
                text += f"   🔥 Стрик: {streak} дней\n\n"
        
        text += f"📊 Сравните достижения с помощью `/compare <ID>`"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_friend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить друга"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/add_friend")
    
    if not context.args:
        await update.message.reply_text(
            "👥 **Добавление друга**\n\n"
            "Формат: `/add_friend <ID_друга>`\n\n"
            "Узнать свой ID: `/myid`\n"
            "Друзья смогут видеть ваши достижения и соревноваться с вами!"
        )
        return
    
    try:
        friend_id = int(context.args[0])
        
        if friend_id == user_id:
            await update.message.reply_text("😅 Нельзя добавить себя в друзья!")
            return
        
        if friend_id not in users_data:
            await update.message.reply_text(
                "❌ Пользователь не найден.\n"
                "Попросите его сначала запустить бота командой /start"
            )
            return
        
        if friend_id in user_friends[user_id]:
            await update.message.reply_text("👥 Этот пользователь уже в ваших друзьях!")
            return
        
        # Взаимное добавление в друзья
        user_friends[user_id].append(friend_id)
        user_friends[friend_id].append(user_id)
        
        xp_msg = add_xp(user_id, 20)
        achievements = check_achievements(user_id)
        
        save_user_data()
        
        friend_level = get_user_level(users_data[friend_id]["xp"])[1]
        response = f"✅ Друг добавлен!\n"
        response += f"👤 ID {friend_id} ({friend_level})\n"
        response += f"{xp_msg}\n"
        
        if achievements:
            response += f"🏆 Новые достижения: {', '.join(achievements)}"
        
        await update.message.reply_text(response)
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID. Используйте числа.")

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Узнать свой ID"""
    user_id = update.effective_user.id
    user = update.effective_user
    log_command(user_id, "/myid")
    
    level_info = get_user_level(users_data.get(user_id, {}).get("xp", 0))
    
    await update.message.reply_text(
        f"🆔 **Ваша информация**\n\n"
        f"👤 Имя: {user.first_name}\n"
        f"🆔 ID: `{user_id}`\n"
        f"📊 Уровень: {level_info[1]}\n\n"
        f"Поделитесь этим ID с друзьями, чтобы они могли добавить вас!",
        parse_mode="Markdown"
    )

# ===================== НАПОМИНАНИЯ И ТАЙМЕРЫ =====================

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создать напоминание"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/remind")
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "⏰ **Создание напоминания**\n\n"
            "Формат: `/remind <время_в_минутах> <текст>`\n\n"
            "Примеры:\n"
            "• `/remind 30 Сделать перерыв`\n"
            "• `/remind 60 Встреча с командой`\n"
            "• `/remind 120 Обед`",
            parse_mode="Markdown"
        )
        return
    
    try:
        minutes = int(context.args[0])
        reminder_text = " ".join(context.args[1:])
        
        if minutes <= 0:
            await update.message.reply_text("❌ Время должно быть положительным числом!")
            return
        
        reminder = {
            "text": reminder_text,
            "created_at": datetime.now().isoformat(),
            "remind_at": (datetime.now() + timedelta(minutes=minutes)).isoformat(),
            "minutes": minutes
        }
        
        user_reminders[user_id].append(reminder)
        save_user_data()
        
        await update.message.reply_text(
            f"⏰ **Напоминание установлено!**\n\n"
            f"📝 Текст: {reminder_text}\n"
            f"⏱️ Через: {minutes} минут\n"
            f"🕐 Время: {(datetime.now() + timedelta(minutes=minutes)).strftime('%H:%M')}\n\n"
            f"💡 В полной версии с APScheduler напоминание придет автоматически"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Время должно быть числом в минутах.")

async def timer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить таймер"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/timer")
    
    if not context.args:
        await update.message.reply_text(
            "⏲️ **Таймер**\n\n"
            "Формат: `/timer <минуты>`\n\n"
            "Популярные таймеры:\n"
            "• `/timer 25` - помодоро (работа)\n"
            "• `/timer 5` - короткий перерыв\n"
            "• `/timer 15` - длинный перерыв\n"
            "• `/timer 60` - час концентрации",
            parse_mode="Markdown"
        )
        return
    
    try:
        minutes = int(context.args[0])
        
        if minutes <= 0:
            await update.message.reply_text("❌ Время должно быть положительным числом!")
            return
        
        users_data[user_id]["timer_uses"] += 1
        xp_msg = add_xp(user_id, 5)
        achievements = check_achievements(user_id)
        
        timer = {
            "minutes": minutes,
            "started_at": datetime.now().isoformat(),
            "ends_at": (datetime.now() + timedelta(minutes=minutes)).isoformat()
        }
        
        user_timers[user_id].append(timer)
        save_user_data()
        
        # Определяем тип таймера
        timer_type = "⏲️ Таймер"
        if minutes == 25:
            timer_type = "🍅 Помодоро"
        elif minutes == 5:
            timer_type = "☕ Короткий перерыв"
        elif minutes == 15:
            timer_type = "🛋️ Длинный перерыв"
        
        response = f"{timer_type} запущен на {minutes} минут!\n"
        response += f"🕐 Завершится в: {(datetime.now() + timedelta(minutes=minutes)).strftime('%H:%M')}\n"
        response += f"{xp_msg}"
        
        if achievements:
            response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
        
        await update.message.reply_text(response)
        
    except ValueError:
        await update.message.reply_text("❌ Время должно быть числом в минутах.")

# ===================== ЕЖЕНЕДЕЛЬНЫЕ ЦЕЛИ =====================

async def weekly_goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление еженедельными целями"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/weekly_goals")
    
    goals = users_data[user_id]["weekly_goals"]
    if not goals:
        keyboard = [
            [InlineKeyboardButton("🎯 Установить цели", callback_data="set_weekly_goals")],
            [InlineKeyboardButton("💡 Примеры целей", callback_data="example_goals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎯 **У вас пока нет еженедельных целей.**\n\n"
            "Еженедельные цели помогают:\n"
            "• Планировать долгосрочные задачи\n"
            "• Поддерживать мотивацию\n"
            "• Отслеживать прогресс\n\n"
            "Установите свои первые цели!",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    text = "🎯 **Еженедельные цели:**\n\n"
    keyboard = []
    
    for i, goal in enumerate(goals, 1):
        status = "✅" if goal.get("completed", False) else "⭕"
        progress = goal.get("progress", 0)
        target = goal.get("target", 1)
        
        text += f"{status} {i}. {goal['name']}\n"
        if target > 1:
            text += f"   📊 Прогресс: {progress}/{target}\n"
        text += f"   📅 Создана: {goal['created_at'][:10]}\n\n"
        
        if not goal.get("completed", False):
            keyboard.append([InlineKeyboardButton(f"✅ Цель {i}", callback_data=f"complete_goal_{i-1}")])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить цель", callback_data="add_weekly_goal")],
        [InlineKeyboardButton("🔄 Новая неделя", callback_data="reset_weekly_goals")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def set_weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить еженедельные цели"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/set_weekly")
    
    if not context.args:
        await update.message.reply_text(
            "🎯 **Еженедельные цели**\n\n"
            "Формат: `/set_weekly цель1; цель2; цель3`\n\n"
            "Примеры:\n"
            "`/set_weekly Прочитать книгу; Сделать 5 тренировок; Изучить новую тему; Встретиться с друзьями`\n\n"
            "💡 Цели заменят текущие еженедельные цели",
            parse_mode="Markdown"
        )
        return
    
    goals_text = " ".join(context.args)
    goal_names = [goal.strip() for goal in goals_text.split(";") if goal.strip()]
    
    if not goal_names:
        await update.message.reply_text("❌ Не найдено ни одной цели. Проверьте формат!")
        return
    
    # Заменяем старые цели
    users_data[user_id]["weekly_goals"] = []
    
    for name in goal_names:
        goal = {
            "name": name,
            "completed": False,
            "created_at": datetime.now().isoformat(),
            "progress": 0,
            "target": 1
        }
        users_data[user_id]["weekly_goals"].append(goal)
    
    xp_reward = len(goal_names) * 10
    xp_msg = add_xp(user_id, xp_reward)
    achievements = check_achievements(user_id)
    
    save_user_data()
    
    response = f"🎯 Установлено {len(goal_names)} еженедельных целей!\n{xp_msg}"
    if achievements:
        response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
    
    await update.message.reply_text(response)

# ===================== ПЕРСОНАЛИЗАЦИЯ =====================

async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сменить тему оформления"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/theme")
    
    if not context.args:
        current_theme_key = user_themes[user_id]
        current_theme = THEMES[current_theme_key]["name"]
        
        text = f"🎨 **Темы оформления**\n\n"
        text += f"Текущая тема: {current_theme}\n\n"
        text += "Доступные темы:\n"
        
        for i, (key, theme) in enumerate(THEMES.items(), 1):
            marker = "▶️" if key == current_theme_key else f"{i}."
            text += f"{marker} {theme['name']}\n"
        
        text += f"\nИспользуйте: `/theme <номер>`"
        await update.message.reply_text(text, parse_mode="Markdown")
        return
    
    try:
        theme_num = int(context.args[0])
        theme_keys = list(THEMES.keys())
        
        if 1 <= theme_num <= len(theme_keys):
            new_theme_key = theme_keys[theme_num - 1]
            user_themes[user_id] = new_theme_key
            new_theme = THEMES[new_theme_key]
            
            xp_msg = add_xp(user_id, 5)
            save_user_data()
            
            await update.message.reply_text(
                f"🎨 Тема изменена на: {new_theme['name']}\n"
                f"{new_theme['accent']} Новый стиль активирован!\n"
                f"{xp_msg}"
            )
        else:
            await update.message.reply_text(f"❌ Выберите номер от 1 до {len(THEMES)}")
    except ValueError:
        await update.message.reply_text("❌ Введите номер темы")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки пользователя"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/settings")
    
    user = users_data[user_id]
    theme = THEMES[user_themes[user_id]]["name"]
    ai_chat = user_ai_chat[user_id]
    
    text = f"⚙️ **Настройки пользователя**\n\n"
    text += f"🎨 Тема: {theme}\n"
    text += f"🤖 AI-чат: {'включен' if ai_chat else 'выключен'}\n"
    text += f"🚭 Dry режим: {'включен' if user['dry_mode'] else 'выключен'}\n"
    text += f"📅 Регистрация: {user['created_at'][:10]}\n"
    text += f"📊 Уровень: {get_user_level(user['xp'])[1]}\n"
    text += f"⚡ XP: {user['xp']}\n"
    text += f"🔥 Стрик: {user['streak']} дней\n\n"
    
    text += "**Команды для изменения:**\n"
    text += "• `/theme` - сменить тему\n"
    text += "• `/ai_chat` - переключить AI-чат\n"
    text += "• `/dryon` или `/dryoff` - dry режим\n"
    text += "• `/export` - экспорт ваших данных"
    
    keyboard = [
        [InlineKeyboardButton("🎨 Сменить тему", callback_data="change_theme")],
        [InlineKeyboardButton("🤖 Переключить AI", callback_data="toggle_ai")],
        [InlineKeyboardButton("📤 Экспорт данных", callback_data="export_data")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ===================== ЭКСПОРТ И УТИЛИТЫ =====================

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт данных"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/export")
    
    user_data = {
        "user_info": {
            "user_id": user_id,
            "level": get_user_level(users_data[user_id]["xp"])[1],
            "xp": users_data[user_id]["xp"],
            "streak": users_data[user_id]["streak"],
            "created_at": users_data[user_id]["created_at"],
            "theme": THEMES[user_themes[user_id]]["name"]
        },
        "tasks": users_data[user_id]["tasks"],
        "achievements": [ACHIEVEMENTS[i] for i in user_achievements[user_id]],
        "weekly_goals": users_data[user_id]["weekly_goals"],
        "statistics": {
            "total_tasks_created": users_data[user_id]["total_tasks_created"],
            "total_tasks_completed": users_data[user_id]["total_tasks_completed"],
            "completed_today": users_data[user_id]["completed_today"],
            "timer_uses": users_data[user_id]["timer_uses"],
            "stats_views": users_data[user_id]["stats_views"]
        },
        "social": {
            "friends_count": len(user_friends[user_id]),
            "friends_list": user_friends[user_id]
        },
        "export_info": {
            "export_date": datetime.now().isoformat(),
            "bot_version": "4.0",
            "format": "JSON"
        }
    }
    
    # Создание JSON файла (в памяти)
    json_data = json.dumps(user_data, ensure_ascii=False, indent=2)
    
    # Создание CSV данных для задач
    csv_output = StringIO()
    csv_writer = csv.writer(csv_output)
    csv_writer.writerow(["Название", "Статус", "Категория", "Приоритет", "Время создания", "Подзадачи"])
    
    for task in users_data[user_id]["tasks"]:
        status = "Выполнено" if task.get("completed", False) else "В процессе"
        category = CATEGORIES[task.get("category", "personal")]["name"]
        priority = PRIORITIES[task.get("priority", "medium")]["name"]
        subtasks_count = len(task.get("subtasks", []))
        
        csv_writer.writerow([
            task["name"],
            status,
            category,
            priority,
            task["created_at"][:10],
            subtasks_count
        ])
    
    csv_data = csv_output.getvalue()
    csv_output.close()
    
    # Статистика экспорта
    stats_text = (
        f"📤 **Экспорт данных завершен**\n\n"
        f"📊 **Ваша статистика:**\n"
        f"📋 Задач: {len(user_data['tasks'])}\n"
        f"🏆 Достижений: {len(user_data['achievements'])}\n"
        f"🎯 Еженедельных целей: {len(user_data['weekly_goals'])}\n"
        f"👥 Друзей: {user_data['social']['friends_count']}\n"
        f"⚡ XP: {user_data['user_info']['xp']}\n"
        f"📊 Уровень: {user_data['user_info']['level']}\n\n"
        f"📁 **Доступные форматы:**\n"
        f"• JSON - полные данные\n"
        f"• CSV - таблица задач\n\n"
        f"💾 В полной версии файлы будут отправлены в чат"
    )
    
    keyboard = [
        [InlineKeyboardButton("📄 Показать JSON", callback_data="show_json")],
        [InlineKeyboardButton("📊 Показать CSV", callback_data="show_csv")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Сохраняем данные для отображения по кнопкам
    users_data[user_id]["export_json"] = json_data[:2000]  # Ограничиваем для отображения
    users_data[user_id]["export_csv"] = csv_data[:2000]
    
    await update.message.reply_text(stats_text, reply_markup=reply_markup, parse_mode="Markdown")

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить состояние системы"""
    user_id = update.effective_user.id
    log_command(user_id, "/health")
    
    # Проверка различных компонентов
    system_status = "✅ Отлично"
    ai_status = "✅ Подключен" if OPENAI_API_KEY else "❌ Недоступен"
    
    # Статистика использования
    total_tasks_all_users = sum(len(user.get("tasks", [])) for user in users_data.values())
    active_users = len([u for u in users_data.values() if len(u.get("tasks", [])) > 0])
    
    await update.message.reply_text(
        f"🏥 **Состояние системы**\n\n"
        f"🤖 Бот: {system_status}\n"
        f"🧠 AI: {ai_status}\n"
        f"🌐 HTTP сервер: порт {PORT}\n"
        f"💾 Данные: сохраняются\n\n"
        f"📊 **Статистика:**\n"
        f"👥 Всего пользователей: {global_stats['total_users']}\n"
        f"🎯 Активных пользователей: {active_users}\n"
        f"📋 Всего задач: {total_tasks_all_users}\n"
        f"📊 Команд выполнено: {global_stats['commands_executed']}\n"
        f"🤖 AI запросов: {global_stats['ai_requests']}\n\n"
        f"⏰ Время сервера: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}\n"
        f"🔄 Версия: 4.0 (FULL)",
        parse_mode="Markdown"
    )

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда (для отладки)"""
    user_id = update.effective_user.id
    log_command(user_id, "/test")
    
    if user_id != ADMIN_USER_ID and ADMIN_USER_ID != 0:
        await update.message.reply_text("❌ Доступно только администратору")
        return
    
    # Создание тестовых данных
    test_tasks = [
        {"name": "Тестовая задача - Работа", "completed": True, "category": "work", "priority": "high"},
        {"name": "Тестовая задача - Здоровье", "completed": False, "category": "health", "priority": "medium"},
        {"name": "Тестовая задача - Обучение", "completed": True, "category": "study", "priority": "low"},
        {"name": "Задача с подзадачами", "completed": False, "category": "personal", "priority": "medium", 
         "subtasks": [
             {"name": "Подзадача 1", "completed": True},
             {"name": "Подзадача 2", "completed": False}
         ]}
    ]
    
    # Добавляем тестовые данные
    users_data[user_id]["tasks"].extend(test_tasks)
    users_data[user_id]["total_tasks_created"] += len(test_tasks)
    users_data[user_id]["completed_today"] += 2
    users_data[user_id]["streak"] = 5
    users_data[user_id]["timer_uses"] += 3
    
    # Добавляем тестовые цели
    test_goals = [
        {"name": "Тестовая цель 1", "completed": True, "created_at": datetime.now().isoformat()},
        {"name": "Тестовая цель 2", "completed": False, "created_at": datetime.now().isoformat()}
    ]
    users_data[user_id]["weekly_goals"].extend(test_goals)
    
    # Даем XP
    add_xp(user_id, 150)
    
    # Проверяем достижения
    achievements = check_achievements(user_id)
    
    save_user_data()
    
    response = "🧪 **Тестовые данные добавлены!**\n\n"
    response += f"📋 Добавлено {len(test_tasks)} задач\n"
    response += f"🎯 Добавлено {len(test_goals)} целей\n"
    response += f"⚡ Добавлено 150 XP\n"
    response += f"🔥 Стрик установлен на 5 дней\n"
    
    if achievements:
        response += f"\n🏆 Получены достижения: {', '.join(achievements)}"
    
    await update.message.reply_text(response, parse_mode="Markdown")

# ===================== РЕЖИМ "DRY" =====================

async def dryon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать отчет дней без алкоголя"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/dryon")
    
    if users_data[user_id]["dry_mode"]:
        days = users_data[user_id]["dry_days"]
        await update.message.reply_text(
            f"🚭 Режим 'Dry' уже активен!\n"
            f"Текущий счетчик: {days} дней"
        )
        return
    
    users_data[user_id]["dry_mode"] = True
    users_data[user_id]["dry_days"] = 0
    save_user_data()
    
    await update.message.reply_text(
        "🚭 **Режим 'Dry' включен!**\n\n"
        "Отслеживание дней без алкоголя начато.\n"
        "Каждый день стойкости будет приносить дополнительные XP!\n\n"
        "💪 Вы можете это сделать!\n"
        "Используйте `/dryoff` для завершения отчета.",
        parse_mode="Markdown"
    )

async def dryoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершить отчет дней без алкоголя"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/dryoff")
    
    if not users_data[user_id]["dry_mode"]:
        await update.message.reply_text("🚭 Режим 'Dry' не активен. Используйте `/dryon` для начала.")
        return
    
    days = users_data[user_id]["dry_days"]
    users_data[user_id]["dry_mode"] = False
    
    # Награда за dry дни
    xp_reward = days * 10
    if days >= 7:
        xp_reward += 50  # Бонус за неделю
    if days >= 30:
        xp_reward += 100  # Бонус за месяц
    
    xp_msg = add_xp(user_id, xp_reward)
    save_user_data()
    
    # Мотивационное сообщение в зависимости от результата
    if days == 0:
        message = "Начало положено! В следующий раз получится лучше."
    elif days < 7:
        message = "Хороший старт! Каждый день - это достижение."
    elif days < 30:
        message = "Впечатляющий результат! Вы показали силу воли."
    else:
        message = "Невероятно! Вы настоящий чемпион силы воли!"
    
    await update.message.reply_text(
        f"🚭 **Отчет завершен!**\n\n"
        f"📊 Дней без алкоголя: {days}\n"
        f"🎁 Награда: {xp_reward} XP\n"
        f"💪 {message}\n\n"
        f"{xp_msg}",
        parse_mode="Markdown"
    )

# ===================== АДМИНСКИЕ ФУНКЦИИ =====================

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправление сообщения всем активным чатам"""
    user_id = update.effective_user.id
    log_command(user_id, "/broadcast")
    
    if user_id != ADMIN_USER_ID and ADMIN_USER_ID != 0:
        await update.message.reply_text("❌ Доступно только администратору")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 **Рассылка сообщений**\n\n"
            "Формат: `/broadcast <сообщение>`\n\n"
            "Пример: `/broadcast Обновление бота! Добавлены новые функции.`"
        )
        return
    
    message = " ".join(context.args)
    sent_count = 0
    failed_count = 0
    
    await update.message.reply_text(f"📢 Начинаю рассылку для {len(users_data)} пользователей...")
    
    for target_user_id in users_data.keys():
        try:
            await context.bot.send_message(
                target_user_id, 
                f"📢 **Сообщение от администратора:**\n\n{message}",
                parse_mode="Markdown"
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.warning(f"Не удалось отправить сообщение пользователю {target_user_id}: {e}")
    
    await update.message.reply_text(
        f"📢 **Рассылка завершена**\n\n"
        f"✅ Отправлено: {sent_count}\n"
        f"❌ Ошибок: {failed_count}\n"
        f"📊 Успешность: {(sent_count/(sent_count+failed_count)*100):.1f}%"
    )

async def stats_global_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальная статистика по всем пользователям"""
    user_id = update.effective_user.id
    log_command(user_id, "/stats_global")
    
    if user_id != ADMIN_USER_ID and ADMIN_USER_ID != 0:
        await update.message.reply_text("❌ Доступно только администратору")
        return
    
    # Подсчет глобальной статистики
    total_tasks = sum(len(user.get("tasks", [])) for user in users_data.values())
    total_completed = sum(
        sum(1 for task in user.get("tasks", []) if task.get("completed", False))
        for user in users_data.values()
    )
    total_xp = sum(user.get("xp", 0) for user in users_data.values())
    active_users = len([u for u in users_data.values() if len(u.get("tasks", [])) > 0])
    
    # Статистика по уровням
    level_stats = {}
    for user in users_data.values():
        level = get_user_level(user.get("xp", 0))[1]
        level_stats[level] = level_stats.get(level, 0) + 1
    
    # Топ пользователи по XP
    top_users = sorted(
        [(uid, user.get("xp", 0)) for uid, user in users_data.items()],
        key=lambda x: x[1], reverse=True
    )[:5]
    
    text = f"📊 **Глобальная статистика**\n\n"
    text += f"👥 **Пользователи:**\n"
    text += f"   • Всего: {global_stats['total_users']}\n"
    text += f"   • Активных: {active_users}\n\n"
    
    text += f"📋 **Задачи:**\n"
    text += f"   • Всего создано: {total_tasks}\n"
    text += f"   • Выполнено: {total_completed}\n"
    text += f"   • Процент выполнения: {(total_completed/max(1,total_tasks)*100):.1f}%\n\n"
    
    text += f"⚡ **Активность:**\n"
    text += f"   • Общий XP: {total_xp:,}\n"
    text += f"   • Команд выполнено: {global_stats['commands_executed']:,}\n"
    text += f"   • AI запросов: {global_stats['ai_requests']:,}\n\n"
    
    text += f"🏆 **Топ-5 по XP:**\n"
    for i, (uid, xp) in enumerate(top_users, 1):
        level = get_user_level(xp)[1]
        text += f"   {i}. ID{uid}: {xp} XP ({level})\n"
    
    text += f"\n📈 **Статистика по уровням:**\n"
    for level, count in sorted(level_stats.items(), key=lambda x: LEVELS.index(x[0]) if x[0] in LEVELS else 999):
        text += f"   • {level}: {count} чел.\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ===================== ОБРАБОТКА СООБЩЕНИЙ =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка обычных сообщений"""
    user_id = update.effective_user.id
    user_text = update.message.text
    init_user(user_id)
    
    logger.info(f"Сообщение от {user_id}: {user_text[:50]}...")
    
    # Если включен AI-чат режим
    if user_ai_chat.get(user_id, False):
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # Определяем тип запроса для AI
        text_lower = user_text.lower()
        if any(word in text_lower for word in ["мотив", "поддерж", "вдохнов", "силы", "могу"]):
            ai_type = "motivate"
        elif any(word in text_lower for word in ["планир", "продуктив", "задач", "советы", "как"]):
            ai_type = "coach"
        elif any(word in text_lower for word in ["стресс", "устал", "грустн", "плох", "депресс"]):
            ai_type = "psy"
        else:
            ai_type = "general"
        
        response = await generate_ai_response(user_text, user_id, ai_type)
        await update.message.reply_text(response)
        return
    
    # Простые ответы для обычного режима
    responses = {
        "привет": "👋 Привет! Используйте /start для главного меню",
        "помощь": "🆘 Используйте /help для полной справки по командам",
        "как дела": f"😊 Отлично! У вас {users_data[user_id]['xp']} XP. Проверьте прогресс командой /stats",
        "спасибо": "🙏 Пожалуйста! Рад помочь в достижении ваших целей!",
        "пока": "👋 До свидания! Удачи с выполнением задач!"
    }
    
    user_text_lower = user_text.lower()
    for key, response in responses.items():
        if key in user_text_lower:
            await update.message.reply_text(response)
            return
    
    # Если ничего не подошло
    await update.message.reply_text(
        "🤔 Не понял команду.\n\n"
        "💡 Используйте:\n"
        "• /help - полная справка\n"
        "• /ai_chat - включить AI режим\n"
        "• /start - главное меню"
    )

# ===================== CALLBACK HANDLERS (Обработка кнопок) =====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на inline кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "show_tasks":
        await show_tasks_callback(query, context)
    elif data == "show_stats":
        await show_stats_callback(query, context)
    elif data == "show_achievements":
        achievements_list = [ACHIEVEMENTS[i] for i in user_achievements.get(user_id, [])]
        text = "🏆 **Ваши достижения:**\n\n"
        if achievements_list:
            for ach in achievements_list:
                text += f"{ach['emoji']} **{ach['name']}**\n"
                text += f"   {ach['desc']}\n"
                text += f"   🎁 Награда: {ach['xp_reward']} XP\n\n"
        else:
            text += "Пока нет достижений.\n"
            text += "Выполняйте задачи, используйте функции бота чтобы получить первые награды!"
        await query.edit_message_text(text, parse_mode="Markdown")
    elif data == "show_ai_help":
        ai_status = "подключен" if OPENAI_API_KEY else "недоступен (настройте OPENAI_API_KEY)"
        text = (
            f"🤖 **AI Помощь** (статус: {ai_status})\n\n"
            f"**Доступные AI команды:**\n"
            f"• `/ai_chat` - включить режим общения\n"
            f"• `/motivate [текст]` - получить мотивацию\n"
            f"• `/ai_coach [вопрос]` - совет по продуктивности\n"
            f"• `/psy [проблема]` - психологическая поддержка\n"
            f"• `/suggest_tasks [категория]` - предложить задачи\n\n"
            f"💡 В AI-чат режиме просто пишите сообщения и получайте умные ответы!"
        )
        await query.edit_message_text(text, parse_mode="Markdown")
    elif data == "show_settings":
        await show_settings_callback(query, context)
    elif data == "show_weekly_goals":
        await show_weekly_goals_callback(query, context)
    elif data.startswith("complete_task_"):
        task_index = int(data.split("_")[2])
        if task_index < len(users_data[user_id]["tasks"]):
            task = users_data[user_id]["tasks"][task_index]
            task["completed"] = True
            users_data[user_id]["completed_today"] += 1
            users_data[user_id]["total_tasks_completed"] += 1
            global_stats["tasks_completed"] += 1
            
            xp_reward = 25
            # Бонус за приоритет
            if task.get("priority") == "high":
                xp_reward += 10
            elif task.get("priority") == "low":
                xp_reward += 5
            
            xp_msg = add_xp(user_id, xp_reward)
            achievements = check_achievements(user_id)
            
            save_user_data()
            
            response = f"✅ **Задача выполнена!**\n"
            response += f"📝 {task['name']}\n"
            response += f"{xp_msg}"
            
            if achievements:
                response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
            
            await query.edit_message_text(response, parse_mode="Markdown")
    elif data.startswith("complete_goal_"):
        goal_index = int(data.split("_")[2])
        if goal_index < len(users_data[user_id]["weekly_goals"]):
            goal = users_data[user_id]["weekly_goals"][goal_index]
            goal["completed"] = True
            
            xp_msg = add_xp(user_id, 50)
            achievements = check_achievements(user_id)
            save_user_data()
            
            response = f"🎯 **Еженедельная цель выполнена!**\n"
            response += f"📝 {goal['name']}\n"
            response += f"{xp_msg}"
            
            if achievements:
                response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
            
            await query.edit_message_text(response, parse_mode="Markdown")
    elif data == "confirm_reset":
        # Сбрасываем выполненные задачи
        for task in users_data[user_id]["tasks"]:
            task["completed"] = False
            for subtask in task.get("subtasks", []):
                subtask["completed"] = False
        
        users_data[user_id]["completed_today"] = 0
        save_user_data()
        
        await query.edit_message_text(
            "🔄 **Прогресс дня сброшен!**\n\n"
            "Все задачи помечены как невыполненные.\n"
            "Начните новый продуктивный день!"
        )

# Отдельные функции для callback'ов
async def show_tasks_callback(query, context):
    """Показать задачи через callback"""
    user_id = query.from_user.id
    init_user(user_id)
    log_command(user_id, "callback_tasks")
    
    tasks = users_data[user_id]["tasks"]
    if not tasks:
        keyboard = [
            [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task_dialog")],
            [InlineKeyboardButton("📝 Быстрая установка", callback_data="quick_setup")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📋 У вас пока нет задач.\n\n"
            "Добавьте первую задачу и начните путь к продуктивности!",
            reply_markup=reply_markup
        )
        return
    
    text = "📋 **Ваши задачи:**\n\n"
    keyboard = []
    
    for i, task in enumerate(tasks):
        status = "✅" if task.get("completed", False) else "⭕"
        priority_emoji = PRIORITIES[task.get("priority", "medium")]["emoji"]
        category_emoji = CATEGORIES[task.get("category", "personal")]["emoji"]
        
        text += f"{status} {i+1}. {task['name']}\n"
        text += f"   {category_emoji} {priority_emoji}"
        if task.get("estimate"):
            text += f" ⏱️ {task['estimate']} мин"
        
        # Подзадачи
        if task.get("subtasks"):
            text += f"\n   📝 Подзадачи ({len(task['subtasks'])}):"
            for j, subtask in enumerate(task["subtasks"]):
                sub_status = "✅" if subtask.get("completed", False) else "⭕"
                text += f"\n      {sub_status} {j+1}. {subtask['name']}"
        
        text += "\n\n"
        
        # Кнопки для незавершенных задач
        if not task.get("completed", False):
            keyboard.append([InlineKeyboardButton(f"✅ Задача {i+1}", callback_data=f"complete_task_{i}")])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить", callback_data="add_task_dialog"),
         InlineKeyboardButton("✏️ Редактировать", callback_data="edit_tasks")],
        [InlineKeyboardButton("🔄 Сбросить день", callback_data="reset_day")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_stats_callback(query, context):
    """Показать статистику через callback"""
    user_id = query.from_user.id
    init_user(user_id)
    log_command(user_id, "callback_stats")
    
    users_data[user_id]["stats_views"] += 1
    user = users_data[user_id]
    level_info = get_user_level(user["xp"])
    
    total_tasks = len(user["tasks"])
    completed_tasks = sum(1 for task in user["tasks"] if task.get("completed", False))
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    text = f"📊 **Детальная статистика**\n\n"
    text += f"👤 Уровень: {level_info[1]}\n"
    text += f"⚡ XP: {user['xp']}/{(level_info[0] + 1) * 100}\n"
    text += f"🔥 Стрик: {user['streak']} дней\n"
    text += f"📋 Всего задач: {total_tasks}\n"
    text += f"✅ Выполнено: {completed_tasks}\n"
    text += f"📈 Процент выполнения: {completion_rate:.1f}%\n\n"
    text += f"🏆 Достижений: {len(user_achievements[user_id])}/{len(ACHIEVEMENTS)}\n"
    text += f"👥 Друзей: {len(user_friends[user_id])}\n"
    
    achievements = check_achievements(user_id)
    if achievements:
        text += f"\n🏆 Новые достижения: {', '.join(achievements)}"
    
    save_user_data()
    await query.edit_message_text(text, parse_mode="Markdown")

async def show_settings_callback(query, context):
    """Показать настройки через callback"""
    user_id = query.from_user.id
    init_user(user_id)
    
    user = users_data[user_id]
    theme = THEMES[user_themes[user_id]]["name"]
    ai_chat = user_ai_chat[user_id]
    
    text = f"⚙️ **Настройки пользователя**\n\n"
    text += f"🎨 Тема: {theme}\n"
    text += f"🤖 AI-чат: {'включен' if ai_chat else 'выключен'}\n"
    text += f"🚭 Dry режим: {'включен' if user['dry_mode'] else 'выключен'}\n"
    text += f"📅 Регистрация: {user['created_at'][:10]}\n"
    text += f"📊 Уровень: {get_user_level(user['xp'])[1]}\n"
    text += f"⚡ XP: {user['xp']}\n"
    text += f"🔥 Стрик: {user['streak']} дней\n\n"
    
    text += "**Команды для изменения:**\n"
    text += "• `/theme` - сменить тему\n"
    text += "• `/ai_chat` - переключить AI-чат\n"
    text += "• `/dryon` или `/dryoff` - dry режим\n"
    text += "• `/export` - экспорт ваших данных"
    
    keyboard = [
        [InlineKeyboardButton("🎨 Сменить тему", callback_data="change_theme")],
        [InlineKeyboardButton("🤖 Переключить AI", callback_data="toggle_ai")],
        [InlineKeyboardButton("📤 Экспорт данных", callback_data="export_data")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_weekly_goals_callback(query, context):
    """Показать еженедельные цели через callback"""
    user_id = query.from_user.id
    init_user(user_id)
    
    goals = users_data[user_id]["weekly_goals"]
    if not goals:
        keyboard = [
            [InlineKeyboardButton("🎯 Установить цели", callback_data="set_weekly_goals")],
            [InlineKeyboardButton("💡 Примеры целей", callback_data="example_goals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎯 **У вас пока нет еженедельных целей.**\n\n"
            "Еженедельные цели помогают:\n"
            "• Планировать долгосрочные задачи\n"
            "• Поддерживать мотивацию\n"
            "• Отслеживать прогресс\n\n"
            "Установите свои первые цели!",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    text = "🎯 **Еженедельные цели:**\n\n"
    keyboard = []
    
    for i, goal in enumerate(goals, 1):
        status = "✅" if goal.get("completed", False) else "⭕"
        progress = goal.get("progress", 0)
        target = goal.get("target", 1)
        
        text += f"{status} {i}. {goal['name']}\n"
        if target > 1:
            text += f"   📊 Прогресс: {progress}/{target}\n"
        text += f"   📅 Создана: {goal['created_at'][:10]}\n\n"
        
        if not goal.get("completed", False):
            keyboard.append([InlineKeyboardButton(f"✅ Цель {i}", callback_data=f"complete_goal_{i-1}")])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить цель", callback_data="add_weekly_goal")],
        [InlineKeyboardButton("🔄 Новая неделя", callback_data="reset_weekly_goals")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ===================== ОСНОВНАЯ ФУНКЦИЯ =====================

def main():
    """Главная функция запуска бота"""
    logger.info("🚀 Запуск DailyCheck Bot v4.0 - ПОЛНАЯ ВЕРСИЯ...")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Платформа: {sys.platform}")
    logger.info(f"Порт: {PORT}")
    
    try:
        # ШАГ 1: Загрузка данных
        logger.info("📂 Загрузка данных пользователей...")
        load_user_data()
        
        # ШАГ 2: Запуск HTTP сервера
        logger.info("🌐 Запуск HTTP сервера...")
        http_thread = start_health_server()
        
        # ШАГ 3: Пауза для стабилизации
        time.sleep(3)
        logger.info("⏳ HTTP сервер стабилизировался")
        
        # ШАГ 4: Создание Telegram приложения
        logger.info("🤖 Создание Telegram приложения...")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # ШАГ 5: Регистрация ВСЕХ обработчиков
        logger.info("📋 Регистрация обработчиков команд...")
        
        # Основные команды
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("ping", ping_command))
        
        # Управление задачами (7 команд)
        app.add_handler(CommandHandler("tasks", tasks_command))
        app.add_handler(CommandHandler("settasks", settasks_command))
        app.add_handler(CommandHandler("addtask", addtask_command))
        app.add_handler(CommandHandler("addsub", addsub_command))
        app.add_handler(CommandHandler("edit", edit_command))
        app.add_handler(CommandHandler("reset", reset_command))
        
        # Статистика (2 команды)
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("analytics", analytics_command))
        
        # AI функции (5 команд)
        app.add_handler(CommandHandler("ai_chat", ai_chat_command))
        app.add_handler(CommandHandler("motivate", motivate_command))
        app.add_handler(CommandHandler("ai_coach", ai_coach_command))
        app.add_handler(CommandHandler("psy", psy_command))
        app.add_handler(CommandHandler("suggest_tasks", suggest_tasks_command))
        
        # Социальные функции (3 команды)
        app.add_handler(CommandHandler("friends", friends_command))
        app.add_handler(CommandHandler("add_friend", add_friend_command))
        app.add_handler(CommandHandler("myid", myid_command))
        
        # Напоминания и таймеры (2 команды)
        app.add_handler(CommandHandler("remind", remind_command))
        app.add_handler(CommandHandler("timer", timer_command))
        
        # Еженедельные цели (2 команды)
        app.add_handler(CommandHandler("weekly_goals", weekly_goals_command))
        app.add_handler(CommandHandler("set_weekly", set_weekly_command))
        
        # Персонализация (2 команды)
        app.add_handler(CommandHandler("theme", theme_command))
        app.add_handler(CommandHandler("settings", settings_command))
        
        # Экспорт и утилиты (3 команды)
        app.add_handler(CommandHandler("export", export_command))
        app.add_handler(CommandHandler("health", health_command))
        app.add_handler(CommandHandler("test", test_command))
        
        # Режим "Dry" (2 команды)
        app.add_handler(CommandHandler("dryon", dryon_command))
        app.add_handler(CommandHandler("dryoff", dryoff_command))
        
        # Админские функции (2 команды)
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CommandHandler("stats_global", stats_global_command))
        
        # Обработчики сообщений и кнопок
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        logger.info("✅ ВСЕ 32 КОМАНДЫ зарегистрированы!")
        logger.info("📱 Найдите бота в Telegram и отправьте /start")
        logger.info("🎯 Запуск polling...")
        
        # ШАГ 6: Запуск бота
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        
        # Сохраняем данные при ошибке
        try:
            save_user_data()
            logger.info("💾 Данные сохранены перед остановкой")
        except:
            logger.error("❌ Не удалось сохранить данные")
        
        # Поддержание HTTP сервера
        logger.info("🔄 HTTP сервер продолжает работать...")
        try:
            while True:
                time.sleep(60)
                logger.info("💓 Процесс активен (HTTP сервер работает)")
        except KeyboardInterrupt:
            logger.info("👋 Остановка по Ctrl+C")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Остановка по KeyboardInterrupt")
        try:
            save_user_data()
            logger.info("💾 Данные сохранены при остановке")
        except:
            pass
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
        try:
            save_user_data()
        except:
            pass
        logger.info("🔄 Поддержание процесса для HTTP сервера...")
        try:
            while True:
                time.sleep(300)
                logger.info("💓 Процесс активен")
        except:
            pass
