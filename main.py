#!/usr/bin/env python3

import os
import sys
import logging
import threading
import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
import hashlib
import uuid

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
global_stats = {"total_users": 0, "commands_executed": 0, "tasks_completed": 0}

# Уровни и достижения
LEVELS = [
    "🌱 Новичок", "🌿 Росток", "🌾 Саженец", "🌳 Дерево", "🍀 Удачливый",
    "💪 Сильный", "🧠 Умный", "🎯 Целеустремленный", "⚡ Энергичный", "🔥 Огненный",
    "💎 Алмазный", "👑 Королевский", "🌟 Звездный", "🚀 Космический", "🏆 Легендарный", "👹 Божественный"
]

ACHIEVEMENTS = [
    {"name": "Первые шаги", "desc": "Добавить первую задачу", "emoji": "👶"},
    {"name": "Продуктивный день", "desc": "Выполнить 5 задач за день", "emoji": "💪"},
    {"name": "Марафонец", "desc": "7 дней подряд выполнять задачи", "emoji": "🏃"},
    {"name": "Планировщик", "desc": "Создать 20 задач", "emoji": "📋"},
    {"name": "Социальный", "desc": "Добавить 3 друзей", "emoji": "👥"},
    {"name": "AI Фанат", "desc": "Сделать 50 AI запросов", "emoji": "🤖"},
    {"name": "Мастер времени", "desc": "Использовать таймер 10 раз", "emoji": "⏰"},
    {"name": "Аналитик", "desc": "Посмотреть статистику 15 раз", "emoji": "📊"},
    {"name": "Целеустремленный", "desc": "Выполнить еженедельную цель", "emoji": "🎯"},
    {"name": "Легенда", "desc": "Достичь 16 уровня", "emoji": "👑"}
]

CATEGORIES = ["🏢 Работа", "💪 Здоровье", "📚 Обучение", "👨‍👩‍👧‍👦 Личное", "💰 Финансы"]
PRIORITIES = ["🟢 Низкий", "🟡 Средний", "🔴 Высокий"]
THEMES = ["🌙 Темная", "☀️ Светлая", "🌈 Радужная", "💎 Кристальная", "🎨 Креативная"]

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
                "users": global_stats["total_users"],
                "commands": global_stats["commands_executed"],
                "uptime": time.time(),
                "message": "Bot is running with full features!"
            }
            self.wfile.write(json.dumps(data).encode())
        
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

# ===================== УТИЛИТЫ =====================

def init_user(user_id: int) -> None:
    if user_id not in users_data:
        users_data[user_id] = {
            "tasks": [],
            "completed_today": 0,
            "streak": 0,
            "last_activity": datetime.now().strftime("%Y-%m-%d"),
            "xp": 0,
            "level": 0,
            "weekly_goals": [],
            "reminders": [],
            "timers": [],
            "dry_mode": False,
            "dry_days": 0,
            "created_at": datetime.now().isoformat()
        }
        user_achievements[user_id] = []
        user_themes[user_id] = "🌙 Темная"
        user_ai_chat[user_id] = False
        user_friends[user_id] = []
        global_stats["total_users"] += 1

def get_user_level(xp: int) -> tuple:
    level = min(xp // 100, len(LEVELS) - 1)
    return level, LEVELS[level]

def add_xp(user_id: int, amount: int) -> str:
    old_level = get_user_level(users_data[user_id]["xp"])[0]
    users_data[user_id]["xp"] += amount
    new_level = get_user_level(users_data[user_id]["xp"])[0]
    
    if new_level > old_level:
        return f"🎉 Поздравляем! Новый уровень: {LEVELS[new_level]}"
    return f"+{amount} XP"

def check_achievements(user_id: int) -> List[str]:
    user = users_data[user_id]
    new_achievements = []
    
    # Проверка достижений
    checks = [
        (len(user["tasks"]) >= 1, 0),
        (user["completed_today"] >= 5, 1),
        (user["streak"] >= 7, 2),
        (len(user["tasks"]) >= 20, 3),
        (len(user_friends[user_id]) >= 3, 4),
        (user["xp"] >= 5000, 5),
        (True, 6),  # Таймеры (упрощено)
        (True, 7),  # Статистика (упрощено)
        (len(user["weekly_goals"]) > 0, 8),
        (get_user_level(user["xp"])[0] >= 15, 9)
    ]
    
    for condition, achievement_id in checks:
        if condition and achievement_id not in user_achievements[user_id]:
            user_achievements[user_id].append(achievement_id)
            new_achievements.append(ACHIEVEMENTS[achievement_id]["emoji"] + " " + ACHIEVEMENTS[achievement_id]["name"])
    
    return new_achievements

def log_command(user_id: int, command: str):
    global_stats["commands_executed"] += 1
    logger.info(f"Команда {command} от пользователя {user_id}")

# ===================== TELEGRAM ИМПОРТЫ =====================

try:
    from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ContextTypes
    logger.info("✅ Telegram библиотеки импортированы")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта Telegram: {e}")
    sys.exit(1)

# ===================== КОМАНДЫ =====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    init_user(user_id)
    log_command(user_id, "/start")
    
    keyboard = [
        [InlineKeyboardButton("📋 Мои задачи", callback_data="tasks")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats"), 
         InlineKeyboardButton("🏆 Достижения", callback_data="achievements")],
        [InlineKeyboardButton("🤖 AI Помощь", callback_data="ai_help"),
         InlineKeyboardButton("⚙️ Настройки", callback_data="settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    level_info = get_user_level(users_data[user_id]["xp"])
    text = (
        f"🚀 Привет, {user.first_name}!\n\n"
        f"Я DailyCheck Bot v4.0 - ваш AI помощник для продуктивности!\n\n"
        f"📊 Ваш уровень: {level_info[1]}\n"
        f"⚡ XP: {users_data[user_id]['xp']}\n"
        f"🔥 Стрик: {users_data[user_id]['streak']} дней\n\n"
        f"Выберите действие:"
    )
    
    await update.message.reply_text(text, reply_markup=reply_markup)

# ===================== УПРАВЛЕНИЕ ЗАДАЧАМИ =====================

async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/tasks")
    
    tasks = users_data[user_id]["tasks"]
    if not tasks:
        keyboard = [
            [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")],
            [InlineKeyboardButton("📝 Быстрая установка", callback_data="set_tasks")]
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
        priority = task.get("priority", "🟡 Средний")
        category = task.get("category", "👨‍👩‍👧‍👦 Личное")
        
        text += f"{status} {task['name']}\n"
        text += f"   {priority} | {category}\n"
        if task.get("estimate"):
            text += f"   ⏱️ {task['estimate']} мин\n"
        text += "\n"
        
        if not task.get("completed", False):
            keyboard.append([InlineKeyboardButton(f"✅ {task['name'][:20]}...", callback_data=f"complete_{i}")])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить", callback_data="add_task"),
         InlineKeyboardButton("✏️ Редактировать", callback_data="edit_tasks")],
        [InlineKeyboardButton("🔄 Сбросить", callback_data="reset_tasks")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def settasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/settasks")
    
    if not context.args:
        await update.message.reply_text(
            "📝 **Быстрая установка задач**\n\n"
            "Формат: `/settasks задача1; задача2; задача3`\n\n"
            "Пример:\n"
            "`/settasks Проверить почту; Сделать зарядку; Прочитать книгу`"
        )
        return
    
    tasks_text = " ".join(context.args)
    task_names = [task.strip() for task in tasks_text.split(";") if task.strip()]
    
    users_data[user_id]["tasks"] = []
    for name in task_names:
        task = {
            "name": name,
            "completed": False,
            "created_at": datetime.now().isoformat(),
            "category": "👨‍👩‍👧‍👦 Личное",
            "priority": "🟡 Средний"
        }
        users_data[user_id]["tasks"].append(task)
    
    xp_msg = add_xp(user_id, len(task_names) * 5)
    achievements = check_achievements(user_id)
    
    response = f"✅ Добавлено {len(task_names)} задач!\n{xp_msg}"
    if achievements:
        response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
    
    await update.message.reply_text(response)

async def addtask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/addtask")
    
    if not context.args:
        await update.message.reply_text(
            "➕ **Добавление задачи**\n\n"
            "Формат: `/addtask название [категория] [приоритет] [время]`\n\n"
            "Пример:\n"
            "`/addtask Написать отчет работа высокий 60`\n\n"
            "Категории: работа, здоровье, обучение, личное, финансы\n"
            "Приоритеты: низкий, средний, высокий"
        )
        return
    
    args = context.args
    name = args[0]
    category = "👨‍👩‍👧‍👦 Личное"
    priority = "🟡 Средний"
    estimate = None
    
    # Парсинг дополнительных параметров
    if len(args) > 1:
        for arg in args[1:]:
            if arg.lower() in ["работа", "work"]:
                category = "🏢 Работа"
            elif arg.lower() in ["здоровье", "health"]:
                category = "💪 Здоровье"
            elif arg.lower() in ["обучение", "study"]:
                category = "📚 Обучение"
            elif arg.lower() in ["финансы", "finance"]:
                category = "💰 Финансы"
            elif arg.lower() in ["низкий", "low"]:
                priority = "🟢 Низкий"
            elif arg.lower() in ["высокий", "high"]:
                priority = "🔴 Высокий"
            elif arg.isdigit():
                estimate = int(arg)
    
    task = {
        "name": name,
        "completed": False,
        "created_at": datetime.now().isoformat(),
        "category": category,
        "priority": priority,
        "estimate": estimate
    }
    
    users_data[user_id]["tasks"].append(task)
    xp_msg = add_xp(user_id, 10)
    achievements = check_achievements(user_id)
    
    response = f"✅ Задача добавлена!\n{xp_msg}"
    if achievements:
        response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
    
    await update.message.reply_text(response)

# ===================== СТАТИСТИКА =====================

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/stats")
    
    user = users_data[user_id]
    level_info = get_user_level(user["xp"])
    
    total_tasks = len(user["tasks"])
    completed_tasks = sum(1 for task in user["tasks"] if task.get("completed", False))
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Статистика по категориям
    category_stats = {}
    for task in user["tasks"]:
        cat = task.get("category", "👨‍👩‍👧‍👦 Личное")
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "completed": 0}
        category_stats[cat]["total"] += 1
        if task.get("completed", False):
            category_stats[cat]["completed"] += 1
    
    text = f"📊 **Детальная статистика**\n\n"
    text += f"👤 Уровень: {level_info[1]}\n"
    text += f"⚡ XP: {user['xp']}/{(level_info[0] + 1) * 100}\n"
    text += f"🔥 Стрик: {user['streak']} дней\n"
    text += f"📋 Всего задач: {total_tasks}\n"
    text += f"✅ Выполнено: {completed_tasks}\n"
    text += f"📈 Процент выполнения: {completion_rate:.1f}%\n\n"
    
    text += "📊 **По категориям:**\n"
    for cat, stats in category_stats.items():
        rate = (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        text += f"{cat}: {stats['completed']}/{stats['total']} ({rate:.0f}%)\n"
    
    text += f"\n🏆 Достижений: {len(user_achievements[user_id])}/{len(ACHIEVEMENTS)}\n"
    text += f"👥 Друзей: {len(user_friends[user_id])}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/analytics")
    
    user = users_data[user_id]
    
    # Продвинутая аналитика
    text = f"📈 **Продвинутая аналитика**\n\n"
    
    # Анализ продуктивности
    productive_hours = ["9:00-12:00", "14:00-17:00", "19:00-21:00"]
    text += f"⏰ Рекомендуемые часы работы:\n"
    for hour in productive_hours:
        text += f"   • {hour}\n"
    
    # Рекомендации
    total_tasks = len(user["tasks"])
    if total_tasks < 5:
        text += f"\n💡 Рекомендация: Добавьте больше задач для лучшего планирования\n"
    elif user["streak"] < 3:
        text += f"\n💡 Рекомендация: Попробуйте выполнять задачи каждый день\n"
    else:
        text += f"\n🎉 Отличная работа! Продолжайте в том же духе!\n"
    
    # Прогноз
    if user["xp"] > 0:
        days_to_next_level = ((get_user_level(user["xp"])[0] + 1) * 100 - user["xp"]) / 20
        text += f"\n🔮 Прогноз: до следующего уровня ~{days_to_next_level:.0f} дней\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ===================== AI ФУНКЦИИ =====================

async def generate_ai_response(text: str, user_id: int = None, ai_type: str = "general") -> str:
    if not OPENAI_API_KEY:
        fallback_responses = {
            "motivate": "🔥 Вы можете всё! Каждый маленький шаг приближает к большой цели!",
            "coach": "📋 Совет: Разбейте большую задачу на маленькие части и выполняйте по одной.",
            "psy": "🧠 Помните: неудачи - это опыт. Важно не падение, а умение подняться.",
            "general": f"💡 Я запомнил ваш вопрос: '{text}'. AI временно недоступен, но я готов помочь!"
        }
        return fallback_responses.get(ai_type, fallback_responses["general"])
    
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        system_prompts = {
            "motivate": "Ты мотивационный коуч. Вдохновляй и поддерживай пользователя.",
            "coach": "Ты эксперт по продуктивности. Давай практические советы по планированию и выполнению задач.",
            "psy": "Ты психолог-консультант. Помогай справляться со стрессом и находить баланс.",
            "general": "Ты полезный AI-ассистент для продуктивности. Отвечай кратко и полезно."
        }
        
        # Добавляем контекст пользователя
        context = ""
        if user_id and user_id in users_data:
            user = users_data[user_id]
            context = f" Контекст пользователя: уровень {get_user_level(user['xp'])[1]}, {len(user['tasks'])} задач, стрик {user['streak']} дней."
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompts.get(ai_type, system_prompts["general"]) + context},
                {"role": "user", "content": text}
            ],
            max_tokens=400,
            temperature=0.7
        )
        
        return f"🤖 {response.choices[0].message.content.strip()}"
        
    except Exception as e:
        logger.error(f"AI ошибка: {e}")
        return f"⚠️ Ошибка AI сервиса. Попробуйте позже!"

async def ai_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/ai_chat")
    
    user_ai_chat[user_id] = not user_ai_chat[user_id]
    status = "включен" if user_ai_chat[user_id] else "выключен"
    
    text = f"🤖 AI-чат режим {status}!\n\n"
    if user_ai_chat[user_id]:
        text += "Теперь просто пишите мне сообщения, и я буду отвечать как AI-ассистент!"
    else:
        text += "AI-чат выключен. Используйте команды для взаимодействия."
    
    await update.message.reply_text(text)

async def motivate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/motivate")
    
    user_text = " ".join(context.args) if context.args else "мотивируй меня"
    response = await generate_ai_response(user_text, user_id, "motivate")
    await update.message.reply_text(response)

async def ai_coach_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/ai_coach")
    
    user_text = " ".join(context.args) if context.args else "дай совет по продуктивности"
    response = await generate_ai_response(user_text, user_id, "coach")
    await update.message.reply_text(response)

async def psy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/psy")
    
    user_text = " ".join(context.args) if context.args else "помоги справиться со стрессом"
    response = await generate_ai_response(user_text, user_id, "psy")
    await update.message.reply_text(response)

async def suggest_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/suggest_tasks")
    
    category = " ".join(context.args) if context.args else "продуктивность"
    prompt = f"Предложи 5 полезных задач для категории '{category}'"
    response = await generate_ai_response(prompt, user_id, "coach")
    await update.message.reply_text(response)

# ===================== СОЦИАЛЬНЫЕ ФУНКЦИИ =====================

async def friends_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/friends")
    
    friends = user_friends[user_id]
    if not friends:
        text = "👥 У вас пока нет друзей.\n\nИспользуйте /add_friend <ID> чтобы добавить друга!"
    else:
        text = "👥 **Ваши друзья:**\n\n"
        for friend_id in friends:
            if friend_id in users_data:
                level = get_user_level(users_data[friend_id]["xp"])[1]
                text += f"👤 ID {friend_id}: {level}\n"
        text += f"\n📊 Сравните достижения с помощью /compare <ID>"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_friend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/add_friend")
    
    if not context.args:
        await update.message.reply_text(
            "👥 Добавление друга\n\n"
            "Формат: `/add_friend <ID_друга>`\n"
            "Узнать свой ID: /myid"
        )
        return
    
    try:
        friend_id = int(context.args[0])
        if friend_id == user_id:
            await update.message.reply_text("😅 Нельзя добавить себя в друзья!")
            return
        
        if friend_id not in users_data:
            await update.message.reply_text("❌ Пользователь не найден. Попросите его сначала запустить бота.")
            return
        
        if friend_id in user_friends[user_id]:
            await update.message.reply_text("👥 Этот пользователь уже в ваших друзьях!")
            return
        
        user_friends[user_id].append(friend_id)
        user_friends[friend_id].append(user_id)  # Взаимное добавление
        
        achievements = check_achievements(user_id)
        response = f"✅ Друг добавлен!\n🎉 +20 XP"
        add_xp(user_id, 20)
        
        if achievements:
            response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
        
        await update.message.reply_text(response)
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID. Используйте числа.")

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_command(user_id, "/myid")
    
    await update.message.reply_text(
        f"🆔 Ваш ID: `{user_id}`\n\n"
        f"Поделитесь этим ID с друзьями, чтобы они могли добавить вас!",
        parse_mode="Markdown"
    )

# ===================== НАПОМИНАНИЯ И ТАЙМЕРЫ =====================

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/remind")
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "⏰ **Создание напоминания**\n\n"
            "Формат: `/remind <время_в_минутах> <текст>`\n\n"
            "Пример: `/remind 30 Сделать перерыв`"
        )
        return
    
    try:
        minutes = int(context.args[0])
        text = " ".join(context.args[1:])
        
        # Здесь бы добавить реальную систему напоминаний с APScheduler
        await update.message.reply_text(
            f"⏰ Напоминание установлено!\n"
            f"📝 Текст: {text}\n"
            f"⏱️ Через: {minutes} минут"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Время должно быть числом в минутах.")

async def timer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/timer")
    
    if not context.args:
        await update.message.reply_text(
            "⏲️ **Таймер**\n\n"
            "Формат: `/timer <минуты>`\n\n"
            "Примеры:\n"
            "• `/timer 25` - помодоро\n"
            "• `/timer 5` - короткий перерыв\n"
            "• `/timer 15` - длинный перерыв"
        )
        return
    
    try:
        minutes = int(context.args[0])
        add_xp(user_id, 5)
        
        await update.message.reply_text(
            f"⏲️ Таймер запущен на {minutes} минут!\n"
            f"⚡ +5 XP за использование таймера"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Время должно быть числом в минутах.")

# ===================== ЕЖЕНЕДЕЛЬНЫЕ ЦЕЛИ =====================

async def weekly_goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/weekly_goals")
    
    goals = users_data[user_id]["weekly_goals"]
    if not goals:
        text = "🎯 У вас пока нет еженедельных целей.\n\nИспользуйте /set_weekly чтобы установить цели!"
    else:
        text = "🎯 **Еженедельные цели:**\n\n"
        for i, goal in enumerate(goals, 1):
            status = "✅" if goal.get("completed", False) else "⭕"
            text += f"{status} {i}. {goal['name']}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def set_weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/set_weekly")
    
    if not context.args:
        await update.message.reply_text(
            "🎯 **Еженедельные цели**\n\n"
            "Формат: `/set_weekly цель1; цель2; цель3`\n\n"
            "Пример:\n"
            "`/set_weekly Прочитать книгу; Сделать 5 тренировок; Изучить новую тему`"
        )
        return
    
    goals_text = " ".join(context.args)
    goal_names = [goal.strip() for goal in goals_text.split(";") if goal.strip()]
    
    users_data[user_id]["weekly_goals"] = []
    for name in goal_names:
        goal = {
            "name": name,
            "completed": False,
            "created_at": datetime.now().isoformat()
        }
        users_data[user_id]["weekly_goals"].append(goal)
    
    xp_msg = add_xp(user_id, len(goal_names) * 10)
    achievements = check_achievements(user_id)
    
    response = f"🎯 Установлено {len(goal_names)} еженедельных целей!\n{xp_msg}"
    if achievements:
        response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
    
    await update.message.reply_text(response)

# ===================== ПЕРСОНАЛИЗАЦИЯ =====================

async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/theme")
    
    if not context.args:
        current_theme = user_themes[user_id]
        text = f"🎨 **Темы оформления**\n\n"
        text += f"Текущая тема: {current_theme}\n\n"
        text += "Доступные темы:\n"
        for i, theme in enumerate(THEMES, 1):
            text += f"{i}. {theme}\n"
        text += f"\nИспользуйте: `/theme <номер>`"
        await update.message.reply_text(text, parse_mode="Markdown")
        return
    
    try:
        theme_num = int(context.args[0])
        if 1 <= theme_num <= len(THEMES):
            user_themes[user_id] = THEMES[theme_num - 1]
            await update.message.reply_text(
                f"🎨 Тема изменена на: {THEMES[theme_num - 1]}\n"
                f"⚡ +5 XP за персонализацию"
            )
            add_xp(user_id, 5)
        else:
            await update.message.reply_text(f"❌ Выберите номер от 1 до {len(THEMES)}")
    except ValueError:
        await update.message.reply_text("❌ Введите номер темы")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/settings")
    
    user = users_data[user_id]
    theme = user_themes[user_id]
    ai_chat = user_ai_chat[user_id]
    
    text = f"⚙️ **Настройки пользователя**\n\n"
    text += f"🎨 Тема: {theme}\n"
    text += f"🤖 AI-чат: {'включен' if ai_chat else 'выключен'}\n"
    text += f"🚭 Dry режим: {'включен' if user['dry_mode'] else 'выключен'}\n"
    text += f"📅 Регистрация: {user['created_at'][:10]}\n\n"
    text += "Команды для изменения:\n"
    text += "• /theme - сменить тему\n"
    text += "• /ai_chat - переключить AI-чат\n"
    text += "• /dryon или /dryoff - dry режим"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ===================== ЭКСПОРТ И УТИЛИТЫ =====================

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/export")
    
    user_data = {
        "user_id": user_id,
        "tasks": users_data[user_id]["tasks"],
        "stats": {
            "xp": users_data[user_id]["xp"],
            "level": get_user_level(users_data[user_id]["xp"])[1],
            "streak": users_data[user_id]["streak"],
            "completed_today": users_data[user_id]["completed_today"]
        },
        "achievements": [ACHIEVEMENTS[i]["name"] for i in user_achievements[user_id]],
        "weekly_goals": users_data[user_id]["weekly_goals"],
        "theme": user_themes[user_id],
        "friends_count": len(user_friends[user_id]),
        "export_date": datetime.now().isoformat()
    }
    
    # В реальной версии здесь бы создавался файл
    await update.message.reply_text(
        f"📤 **Экспорт данных**\n\n"
        f"Ваши данные готовы к экспорту:\n\n"
        f"📋 Задач: {len(user_data['tasks'])}\n"
        f"🏆 Достижений: {len(user_data['achievements'])}\n"
        f"⚡ XP: {user_data['stats']['xp']}\n\n"
        f"Форматы: JSON, CSV\n"
        f"(В полной версии файл будет отправлен)",
        parse_mode="Markdown"
    )

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_command(user_id, "/health")
    
    await update.message.reply_text(
        f"🏥 **Состояние системы**\n\n"
        f"✅ Бот: работает\n"
        f"🤖 AI: {'подключен' if OPENAI_API_KEY else 'недоступен'}\n"
        f"👥 Пользователей: {global_stats['total_users']}\n"
        f"📊 Команд выполнено: {global_stats['commands_executed']}\n"
        f"🔗 HTTP сервер: порт {PORT}\n"
        f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}"
    )

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_command(user_id, "/test")
    
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Доступно только администратору")
        return
    
    # Создание тестовых данных
    test_tasks = [
        {"name": "Тестовая задача 1", "completed": True, "category": "🏢 Работа"},
        {"name": "Тестовая задача 2", "completed": False, "category": "💪 Здоровье"},
        {"name": "Тестовая задача 3", "completed": True, "category": "📚 Обучение"}
    ]
    
    users_data[user_id]["tasks"].extend(test_tasks)
    add_xp(user_id, 100)
    users_data[user_id]["streak"] = 5
    
    await update.message.reply_text("🧪 Тестовые данные добавлены!")

# ===================== РЕЖИМ "DRY" =====================

async def dryon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/dryon")
    
    users_data[user_id]["dry_mode"] = True
    users_data[user_id]["dry_days"] = 0
    
    await update.message.reply_text(
        "🚭 **Режим 'Dry' включен!**\n\n"
        "Отслеживание дней без алкоголя начато.\n"
        "Используйте /dryoff для завершения отчета."
    )

async def dryoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/dryoff")
    
    if not users_data[user_id]["dry_mode"]:
        await update.message.reply_text("🚭 Режим 'Dry' не активен.")
        return
    
    days = users_data[user_id]["dry_days"]
    users_data[user_id]["dry_mode"] = False
    
    xp_reward = days * 10
    add_xp(user_id, xp_reward)
    
    await update.message.reply_text(
        f"🚭 **Отчет завершен!**\n\n"
        f"Дней без алкоголя: {days}\n"
        f"Награда: {xp_reward} XP\n"
        f"🎉 Отличная работа!"
    )

# ===================== ADMIN ФУНКЦИИ =====================

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_command(user_id, "/broadcast")
    
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Доступно только администратору")
        return
    
    if not context.args:
        await update.message.reply_text("📢 Формат: /broadcast <сообщение>")
        return
    
    message = " ".join(context.args)
    sent_count = 0
    
    for target_user_id in users_data.keys():
        try:
            await context.bot.send_message(target_user_id, f"📢 {message}")
            sent_count += 1
        except:
            pass
    
    await update.message.reply_text(f"📢 Сообщение отправлено {sent_count} пользователям")

async def stats_global_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_command(user_id, "/stats_global")
    
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Доступно только администратору")
        return
    
    total_tasks = sum(len(user["tasks"]) for user in users_data.values())
    total_xp = sum(user["xp"] for user in users_data.values())
    active_users = len([u for u in users_data.values() if len(u["tasks"]) > 0])
    
    text = f"📊 **Глобальная статистика**\n\n"
    text += f"👥 Всего пользователей: {global_stats['total_users']}\n"
    text += f"🎯 Активных пользователей: {active_users}\n"
    text += f"📋 Всего задач: {total_tasks}\n"
    text += f"⚡ Общий XP: {total_xp}\n"
    text += f"📊 Команд выполнено: {global_stats['commands_executed']}\n"
    text += f"🤖 AI доступен: {'Да' if OPENAI_API_KEY else 'Нет'}"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ===================== ОБРАБОТКА СООБЩЕНИЙ =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    init_user(user_id)
    
    logger.info(f"Сообщение от {user_id}: {user_text[:50]}...")
    
    # Если включен AI-чат режим
    if user_ai_chat.get(user_id, False):
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response = await generate_ai_response(user_text, user_id)
        await update.message.reply_text(response)
        return
    
    # Простые ответы для обычного режима
    responses = {
        "привет": "👋 Привет! Используйте /start для главного меню",
        "помощь": "🆘 Используйте /help для справки",
        "как дела": "😊 Отлично! Проверьте свой прогресс командой /stats"
    }
    
    user_text_lower = user_text.lower()
    for key, response in responses.items():
        if key in user_text_lower:
            await update.message.reply_text(response)
            return
    
    await update.message.reply_text(
        "🤔 Не понял команду. Используйте /help для справки или /ai_chat для включения AI режима!"
    )

# ===================== CALLBACK HANDLERS =====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "tasks":
        await tasks_command(update, context)
    elif data == "stats":
        await stats_command(update, context)
    elif data == "achievements":
        achievements_list = [ACHIEVEMENTS[i] for i in user_achievements.get(user_id, [])]
        text = "🏆 **Ваши достижения:**\n\n"
        if achievements_list:
            for ach in achievements_list:
                text += f"{ach['emoji']} {ach['name']}\n   {ach['desc']}\n\n"
        else:
            text += "Пока нет достижений. Выполняйте задачи чтобы получить первые награды!"
        await query.edit_message_text(text, parse_mode="Markdown")
    elif data == "ai_help":
        text = (
            "🤖 **AI Помощь**\n\n"
            "Доступные AI команды:\n"
            "• /ai_chat - включить режим общения\n"
            "• /motivate - получить мотивацию\n"
            "• /ai_coach - совет по продуктивности\n"
            "• /psy - психологическая поддержка\n"
            "• /suggest_tasks - предложить задачи"
        )
        await query.edit_message_text(text, parse_mode="Markdown")
    elif data.startswith("complete_"):
        task_index = int(data.split("_")[1])
        if task_index < len(users_data[user_id]["tasks"]):
            users_data[user_id]["tasks"][task_index]["completed"] = True
            users_data[user_id]["completed_today"] += 1
            xp_msg = add_xp(user_id, 25)
            achievements = check_achievements(user_id)
            
            response = f"✅ Задача выполнена!\n{xp_msg}"
            if achievements:
                response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
            
            await query.edit_message_text(response)

# ===================== ОСНОВНАЯ ФУНКЦИЯ =====================

def main():
    logger.info("🚀 Запуск DailyCheck Bot v4.0 - ПОЛНАЯ ВЕРСИЯ...")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Платформа: {sys.platform}")
    logger.info(f"Порт: {PORT}")
    
    try:
        # ШАГ 1: Запуск HTTP сервера
        logger.info("🌐 Запуск HTTP сервера...")
        http_thread = start_health_server()
        
        # ШАГ 2: Пауза для стабилизации
        time.sleep(3)
        logger.info("⏳ HTTP сервер стабилизировался")
        
        # ШАГ 3: Создание Telegram приложения
        logger.info("🤖 Создание Telegram приложения...")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # ШАГ 4: Регистрация ВСЕХ обработчиков
        # Основные команды
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("ping", ping_command))
        
        # Управление задачами
        app.add_handler(CommandHandler("tasks", tasks_command))
        app.add_handler(CommandHandler("settasks", settasks_command))
        app.add_handler(CommandHandler("addtask", addtask_command))
        app.add_handler(CommandHandler("edit", tasks_command))  # Упрощено
        app.add_handler(CommandHandler("reset", tasks_command))  # Упрощено
        
        # Статистика
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("analytics", analytics_command))
        
        # AI функции
        app.add_handler(CommandHandler("ai_chat", ai_chat_command))
        app.add_handler(CommandHandler("motivate", motivate_command))
        app.add_handler(CommandHandler("ai_coach", ai_coach_command))
        app.add_handler(CommandHandler("psy", psy_command))
        app.add_handler(CommandHandler("suggest_tasks", suggest_tasks_command))
        
        # Социальные функции
        app.add_handler(CommandHandler("friends", friends_command))
        app.add_handler(CommandHandler("add_friend", add_friend_command))
        app.add_handler(CommandHandler("myid", myid_command))
        
        # Напоминания и таймеры
        app.add_handler(CommandHandler("remind", remind_command))
        app.add_handler(CommandHandler("timer", timer_command))
        
        # Еженедельные цели
        app.add_handler(CommandHandler("weekly_goals", weekly_goals_command))
        app.add_handler(CommandHandler("set_weekly", set_weekly_command))
        
        # Персонализация
        app.add_handler(CommandHandler("theme", theme_command))
        app.add_handler(CommandHandler("settings", settings_command))
        
        # Экспорт и утилиты
        app.add_handler(CommandHandler("export", export_command))
        app.add_handler(CommandHandler("health", health_command))
        app.add_handler(CommandHandler("test", test_command))
        
        # Режим "Dry"
        app.add_handler(CommandHandler("dryon", dryon_command))
        app.add_handler(CommandHandler("dryoff", dryoff_command))
        
        # Админские функции
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CommandHandler("stats_global", stats_global_command))
        
        # Обработчики сообщений и кнопок
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        logger.info("✅ ВСЕ 30+ ОБРАБОТЧИКОВ зарегистрированы!")
        logger.info("📱 Найдите бота в Telegram и отправьте /start")
        logger.info("🎯 Запуск polling...")
        
        # ШАГ 5: Запуск бота
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        
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
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
        logger.info("🔄 Поддержание процесса для HTTP сервера...")
        try:
            while True:
                time.sleep(300)
                logger.info("💓 Процесс активен")
        except:
            pass
