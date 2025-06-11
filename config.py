#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Bot v4.0 - Конфигурация проекта
Централизованные настройки и константы

Автор: AI Assistant  
Версия: 4.0.0
Дата: 2025-06-10
"""

import os
import sys
from pathlib import Path
from enum import Enum
from typing import Dict, Any

class BotConfig:
    """Конфигурация бота"""
    
    # Основные настройки
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))
    
    # Сетевые настройки
    PORT = int(os.getenv('PORT', 8080))
    HOST = os.getenv('HOST', '0.0.0.0')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
    
    # Файловая система
    DATA_DIR = Path(os.getenv('DATA_DIR', 'data'))
    EXPORT_DIR = Path(os.getenv('EXPORT_DIR', 'exports'))
    BACKUP_DIR = Path(os.getenv('BACKUP_DIR', 'backups'))
    LOG_DIR = Path(os.getenv('LOG_DIR', 'logs'))
    
    # AI настройки
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    OPENAI_MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', 1000))
    AI_CHAT_ENABLED = os.getenv('AI_CHAT_ENABLED', 'true').lower() == 'true'
    
    # Google Sheets
    GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '')
    GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'service_account.json')
    
    # Производительность
    MAX_USERS_CACHE = int(os.getenv('MAX_USERS_CACHE', 1000))
    BACKUP_INTERVAL_HOURS = int(os.getenv('BACKUP_INTERVAL_HOURS', 6))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    
    # Dashboard настройки
    DASHBOARD_SECRET_KEY = os.getenv('DASHBOARD_SECRET_KEY', 'your-secret-key-here')
    DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', 8081))
    DASHBOARD_HOST = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    
    # Создаем директории
    @classmethod
    def ensure_directories(cls):
        """Создание необходимых директорий"""
        for directory in [cls.DATA_DIR, cls.EXPORT_DIR, cls.BACKUP_DIR, cls.LOG_DIR]:
            directory.mkdir(exist_ok=True)
    
    @classmethod
    def validate_config(cls) -> bool:
        """Валидация конфигурации"""
        if not cls.BOT_TOKEN:
            print("❌ BOT_TOKEN не найден в переменных окружения!")
            return False
        
        if cls.OPENAI_API_KEY == cls.BOT_TOKEN:
            print("⚠️ OPENAI_API_KEY совпадает с BOT_TOKEN - AI функции будут отключены")
        
        return True
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """Получить все настройки в виде словаря"""
        return {
            'bot_token_set': bool(cls.BOT_TOKEN),
            'openai_key_set': bool(cls.OPENAI_API_KEY),
            'admin_user_id': cls.ADMIN_USER_ID,
            'port': cls.PORT,
            'host': cls.HOST,
            'debug_mode': cls.DEBUG_MODE,
            'ai_chat_enabled': cls.AI_CHAT_ENABLED,
            'data_dir': str(cls.DATA_DIR),
            'log_level': cls.LOG_LEVEL
        }

class TaskStatus(Enum):
    """Статусы задач"""
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ARCHIVED = "archived"

class TaskPriority(Enum):
    """Приоритеты задач"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class TaskCategory(Enum):
    """Категории задач"""
    WORK = "work"
    HEALTH = "health"
    LEARNING = "learning"
    PERSONAL = "personal"
    FINANCE = "finance"

class UserTheme(Enum):
    """Темы оформления"""
    CLASSIC = "classic"
    DARK = "dark"
    NATURE = "nature"
    MINIMAL = "minimal"
    COLORFUL = "colorful"

class AIRequestType(Enum):
    """Типы AI запросов"""
    MOTIVATION = "motivation"
    COACHING = "coaching" 
    PSYCHOLOGY = "psychology"
    ANALYSIS = "analysis"
    GENERAL = "general"

# Константы геймификации
class GameConstants:
    """Константы геймификации"""
    
    # XP за различные действия
    XP_TASK_COMPLETE = 20
    XP_STREAK_BONUS = 5  # за каждый день streak'а
    XP_ACHIEVEMENT = 50
    XP_DAILY_LOGIN = 5
    
    # Уровни
    MAX_LEVEL = 16
    XP_PER_LEVEL_BASE = 100
    XP_LEVEL_MULTIPLIER = 1.5
    
    # Streak'и
    STREAK_BONUS_THRESHOLD = 3  # с какого streak'а начинается бонус
    MAX_STREAK_BONUS = 50
    
    @staticmethod
    def xp_for_level(level: int) -> int:
        """Необходимый XP для достижения уровня"""
        if level <= 1:
            return 0
        return int(GameConstants.XP_PER_LEVEL_BASE * (level - 1) * GameConstants.XP_LEVEL_MULTIPLIER)

# Сообщения бота
class Messages:
    """Константы сообщений"""
    
    WELCOME = """🎯 **Добро пожаловать в DailyCheck Bot v4.0!**

Привет, {user_name}! 

{level_icon} **Уровень {level}** - {level_title}
{xp_icon} XP: {total_xp}

🚀 **Возможности:**
📝 Создание и отслеживание задач с подзадачами
✅ Отметка выполнения с XP и streak'ами
📊 Детальная аналитика и статистика  
🏆 Система достижений и уровней
🤖 AI-ассистент для мотивации и коучинга
👥 Добавление друзей и соревнования
⏰ Таймеры и напоминания
🎨 Персонализация тем оформления

**Ваша статистика:**
• Активных задач: {active_tasks}
• Выполнено всего: {completed_tasks}
• Друзей: {friends_count}
• Достижений: {achievements_count}/{total_achievements}

Выберите действие в меню ниже:"""

    HELP = """📖 Справка по DailyCheck Bot v4.0

🔹 Основные команды:
/start - Главное меню
/tasks - Список ваших задач
/add - Добавить новую задачу  
/stats - Показать статистику
/achievements - Ваши достижения
/friends - Управление друзьями
/export - Экспорт данных

🔹 AI функции:
/ai_chat - Включить/выключить AI-чат
/motivate - Получить мотивацию
/ai_coach - Персональный коуч
/psy - Психологическая поддержка
/suggest_tasks - AI предложит задачи

🔹 Утилиты:
/timer - Установить таймер (Pomodoro и др.)
/remind - Создать напоминание
/theme - Сменить тему оформления
/myid - Узнать свой ID

🔹 Быстрые команды:
/settasks - Быстро создать несколько задач
/weekly_goals - Еженедельные цели
/analytics - Продвинутая аналитика

🔹 Система XP и уровней:
• Выполняйте задачи и получайте XP
• Повышайте уровень и открывайте достижения
• Соревнуйтесь с друзьями в лидерборде

🔹 AI-чат режим:
После /ai_chat пишите боту обычные сообщения:
• "Мотивируй меня" → поддержка
• "Как планировать день?" → советы
• "Устал от работы" → психологическая помощь

💡 Совет: Используйте кнопки для быстрого доступа!"""

# Темы оформления
class ThemeConfig:
    """Конфигурация тем оформления"""
    
    THEMES = {
        UserTheme.CLASSIC: {
            "name": "🎭 Классическая",
            "task_completed": "✅",
            "task_pending": "⭕",
            "priority_high": "🔴",
            "priority_medium": "🟡", 
            "priority_low": "🔵",
            "xp_icon": "⭐",
            "level_icon": "📊",
            "streak_icon": "🔥"
        },
        UserTheme.DARK: {
            "name": "🌙 Тёмная",
            "task_completed": "☑️",
            "task_pending": "⚫",
            "priority_high": "🟥",
            "priority_medium": "🟨",
            "priority_low": "🟦", 
            "xp_icon": "💫",
            "level_icon": "📈",
            "streak_icon": "🔥"
        },
        UserTheme.NATURE: {
            "name": "🌿 Природная",
            "task_completed": "🌟",
            "task_pending": "🌑",
            "priority_high": "🌹",
            "priority_medium": "🌻",
            "priority_low": "🌿",
            "xp_icon": "🍃",
            "level_icon": "🌱",
            "streak_icon": "🔥"
        },
        UserTheme.MINIMAL: {
            "name": "⚪ Минимал",
            "task_completed": "✓",
            "task_pending": "○",
            "priority_high": "●",
            "priority_medium": "◐",
            "priority_low": "○",
            "xp_icon": "◆",
            "level_icon": "▲",
            "streak_icon": "▶"
        },
        UserTheme.COLORFUL: {
            "name": "🌈 Яркая",
            "task_completed": "🎉",
            "task_pending": "💭",
            "priority_high": "💥",
            "priority_medium": "⚡",
            "priority_low": "💫",
            "xp_icon": "🎆",
            "level_icon": "🚀",
            "streak_icon": "🔥"
        }
    }

# Проверяем наличие необходимых библиотек
def check_dependencies():
    """Проверка зависимостей"""
    dependencies = {
        'telegram': 'python-telegram-bot',
        'openai': 'openai',
        'pandas': 'pandas',
        'psutil': 'psutil',
        'apscheduler': 'APScheduler'
    }
    
    missing = []
    available = {}
    
    for module, package in dependencies.items():
        try:
            __import__(module)
            available[module] = True
        except ImportError:
            available[module] = False
            missing.append(package)
    
    return available, missing

# Инициализация при импорте
BotConfig.ensure_directories()

if __name__ == "__main__":
    # Тестирование конфигурации
    print("🔧 Проверка конфигурации DailyCheck Bot v4.0")
    print(f"Python: {sys.version}")
    print(f"Платформа: {sys.platform}")
    
    # Проверяем конфигурацию
    if BotConfig.validate_config():
        print("✅ Конфигурация корректна")
    else:
        print("❌ Ошибки в конфигурации")
        sys.exit(1)
    
    # Проверяем зависимости
    available, missing = check_dependencies()
    
    print("\n📦 Статус зависимостей:")
    for module, status in available.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {module}")
    
    if missing:
        print(f"\n⚠️ Отсутствующие пакеты: {', '.join(missing)}")
        print("Установите командой: pip install " + " ".join(missing))
    else:
        print("\n🎉 Все зависимости доступны!")
    
    # Показываем конфигурацию
    print(f"\n⚙️ Текущие настройки:")
    config = BotConfig.get_config_dict()
    for key, value in config.items():
        print(f"• {key}: {value}")
