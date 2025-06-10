#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Bot v4.0 - Полная версия
Telegram бот для отслеживания ежедневных привычек и задач

Автор: AI Assistant
Версия: 4.0.0
Дата: 2025-06-09
"""

import asyncio
import logging
import signal
import sys
import os
import json
import uuid
import random
import io
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

# Импорты для Render.com совместимости
import nest_asyncio
nest_asyncio.apply()

# Telegram Bot API
from telegram import (
    Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    ConversationHandler, ContextTypes, filters
)
from telegram.error import Conflict, TimedOut, NetworkError

# Внешние библиотеки
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
def setup_logging():
    """Настройка системы логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )
    
    # Отключаем излишне подробные логи httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

logger = setup_logging()

# ===== МОДЕЛИ ДАННЫХ =====

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

@dataclass
class TaskCompletion:
    """Запись о выполнении задачи"""
    date: str  # ISO формат даты (YYYY-MM-DD)
    completed: bool
    note: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "completed": self.completed,
            "note": self.note,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TaskCompletion":
        return cls(**data)

@dataclass
class Task:
    """Модель задачи"""
    task_id: str
    user_id: int
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completions: List[TaskCompletion] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    is_daily: bool = True
    reminder_time: Optional[str] = None
    
    @property
    def current_streak(self) -> int:
        """Текущая серия выполнения"""
        if not self.completions:
            return 0
        
        # Сортируем по дате (новые первые)
        completed_dates = [
            date.fromisoformat(c.date) for c in self.completions 
            if c.completed
        ]
        completed_dates.sort(reverse=True)
        
        if not completed_dates:
            return 0
        
        streak = 0
        current_date = date.today()
        
        for comp_date in completed_dates:
            if comp_date == current_date:
                streak += 1
                current_date = date.fromordinal(current_date.toordinal() - 1)
            else:
                break
        
        return streak
    
    @property
    def completion_rate_week(self) -> float:
        """Процент выполнения за последнюю неделю"""
        week_ago = date.today() - timedelta(days=7)
        week_completions = [
            c for c in self.completions 
            if date.fromisoformat(c.date) >= week_ago and c.completed
        ]
        return len(week_completions) / 7 * 100
    
    @property
    def completion_rate_month(self) -> float:
        """Процент выполнения за последний месяц"""
        month_ago = date.today() - timedelta(days=30)
        month_completions = [
            c for c in self.completions 
            if date.fromisoformat(c.date) >= month_ago and c.completed
        ]
        return len(month_completions) / 30 * 100
    
    def is_completed_today(self) -> bool:
        """Проверка выполнения задачи сегодня"""
        today = date.today().isoformat()
        return any(c.date == today and c.completed for c in self.completions)
    
    def mark_completed(self, note: Optional[str] = None) -> bool:
        """Отметить задачу как выполненную на сегодня"""
        today = date.today().isoformat()
        
        # Проверяем, не выполнена ли уже сегодня
        for completion in self.completions:
            if completion.date == today:
                completion.completed = True
                completion.note = note
                completion.timestamp = datetime.now().isoformat()
                return True
        
        # Добавляем новую запись
        self.completions.append(TaskCompletion(
            date=today,
            completed=True,
            note=note
        ))
        return True
    
    def mark_uncompleted(self) -> bool:
        """Отменить выполнение задачи на сегодня"""
        today = date.today().isoformat()
        
        for completion in self.completions:
            if completion.date == today:
                completion.completed = False
                completion.timestamp = datetime.now().isoformat()
                return True
        
        return False
    
    def to_dict(self) -> dict:
        """Сериализация в словарь"""
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "completions": [c.to_dict() for c in self.completions],
            "tags": self.tags,
            "is_daily": self.is_daily,
            "reminder_time": self.reminder_time
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Десериализация из словаря"""
        task = cls(
            task_id=data["task_id"],
            user_id=data["user_id"],
            title=data["title"],
            description=data.get("description"),
            priority=data.get("priority", "medium"),
            status=data.get("status", "active"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            tags=data.get("tags", []),
            is_daily=data.get("is_daily", True),
            reminder_time=data.get("reminder_time")
        )
        
        # Восстанавливаем записи о выполнении
        if "completions" in data:
            task.completions = [
                TaskCompletion.from_dict(c) if isinstance(c, dict) else c
                for c in data["completions"]
            ]
        
        return task

@dataclass
class UserSettings:
    """Настройки пользователя"""
    timezone: str = "UTC"
    language: str = "ru"
    daily_reminder_time: str = "09:00"
    reminder_enabled: bool = True
    weekly_stats: bool = True
    motivational_messages: bool = True
    notification_sound: bool = True
    auto_archive_completed: bool = False
    
    def to_dict(self) -> dict:
        return {
            "timezone": self.timezone,
            "language": self.language,
            "daily_reminder_time": self.daily_reminder_time,
            "reminder_enabled": self.reminder_enabled,
            "weekly_stats": self.weekly_stats,
            "motivational_messages": self.motivational_messages,
            "notification_sound": self.notification_sound,
            "auto_archive_completed": self.auto_archive_completed
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserSettings":
        return cls(**data)

@dataclass
class UserStats:
    """Статистика пользователя"""
    total_tasks: int = 0
    completed_tasks: int = 0
    current_streak: int = 0
    longest_streak: int = 0
    last_activity: Optional[str] = None
    registration_date: str = field(default_factory=lambda: datetime.now().isoformat())
    total_session_time: int = 0  # в секундах
    preferred_time_of_day: str = "morning"  # morning, afternoon, evening
    
    @property
    def completion_rate(self) -> float:
        """Процент выполнения задач"""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100
    
    @property
    def days_since_registration(self) -> int:
        """Дней с момента регистрации"""
        try:
            reg_date = datetime.fromisoformat(self.registration_date)
            return (datetime.now() - reg_date).days
        except:
            return 0
    
    def to_dict(self) -> dict:
        return {
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "last_activity": self.last_activity,
            "registration_date": self.registration_date,
            "total_session_time": self.total_session_time,
            "preferred_time_of_day": self.preferred_time_of_day
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserStats":
        return cls(**data)

@dataclass
class Achievement:
    """Модель достижения"""
    achievement_id: str
    title: str
    description: str
    icon: str
    earned_at: Optional[str] = None
    progress: int = 0
    target: int = 1
    
    @property
    def is_earned(self) -> bool:
        return self.earned_at is not None
    
    @property
    def progress_percentage(self) -> float:
        return (self.progress / self.target) * 100 if self.target > 0 else 100

@dataclass
class User:
    """Модель пользователя"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    settings: UserSettings = field(default_factory=UserSettings)
    stats: UserStats = field(default_factory=UserStats)
    tasks: Dict[str, Task] = field(default_factory=dict)
    achievements: List[str] = field(default_factory=list)
    notes: str = ""  # Личные заметки пользователя
    
    @property
    def display_name(self) -> str:
        """Отображаемое имя пользователя"""
        if self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"Пользователь {self.user_id}"
    
    @property
    def active_tasks(self) -> Dict[str, Task]:
        """Активные задачи"""
        return {k: v for k, v in self.tasks.items() if v.status == "active"}
    
    @property
    def completed_tasks_today(self) -> List[Task]:
        """Задачи, выполненные сегодня"""
        return [task for task in self.tasks.values() if task.is_completed_today()]
    
    def update_activity(self):
        """Обновить время последней активности"""
        self.stats.last_activity = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """Сериализация в словарь"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "settings": self.settings.to_dict(),
            "stats": self.stats.to_dict(),
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "achievements": self.achievements,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Десериализация из словаря"""
        user = cls(
            user_id=data["user_id"],
            username=data.get("username"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            notes=data.get("notes", "")
        )
        
        # Восстанавливаем настройки
        if "settings" in data:
            user.settings = UserSettings.from_dict(data["settings"])
        
        # Восстанавливаем статистику
        if "stats" in data:
            user.stats = UserStats.from_dict(data["stats"])
        
        # Восстанавливаем задачи
        if "tasks" in data:
            user.tasks = {k: Task.from_dict(v) for k, v in data["tasks"].items()}
        
        # Восстанавливаем достижения
        user.achievements = data.get("achievements", [])
        
        return user

# ===== БАЗА ДАННЫХ =====

class DatabaseManager:
    """Менеджер файловой базы данных"""
    
    def __init__(self, data_file: str = "users_data.json"):
        self.data_file = Path(data_file)
        self.users_cache: Dict[int, User] = {}
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        self._load_all_users()
    
    def _load_all_users(self):
        """Загрузка всех пользователей из файла"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for user_id_str, user_data in data.items():
                    try:
                        user_id = int(user_id_str)
                        user = User.from_dict(user_data)
                        self.users_cache[user_id] = user
                    except Exception as e:
                        logger.error(f"❌ Ошибка загрузки пользователя {user_id_str}: {e}")
                
                logger.info(f"📂 Загружено {len(self.users_cache)} пользователей")
            else:
                logger.info("📂 Файл данных не найден, начинаем с пустой базы")
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки данных: {e}")
            self.users_cache = {}
    
    def save_all_users(self) -> bool:
        """Сохранение всех пользователей в файл"""
        try:
            # Создаем резервную копию перед сохранением
            if self.data_file.exists():
                backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                backup_path = self.backup_dir / backup_name
                self.data_file.replace(backup_path)
            
            # Сохраняем данные
            data = {}
            for user_id, user in self.users_cache.items():
                data[str(user_id)] = user.to_dict()
            
            # Атомарное сохранение через временный файл
            temp_file = self.data_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            temp_file.replace(self.data_file)
            logger.info("💾 Данные сохранены")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        return self.users_cache.get(user_id)
    
    def get_or_create_user(self, user_id: int, **kwargs) -> User:
        """Получить пользователя или создать нового"""
        if user_id not in self.users_cache:
            user = User(
                user_id=user_id,
                username=kwargs.get('username'),
                first_name=kwargs.get('first_name'),
                last_name=kwargs.get('last_name')
            )
            self.users_cache[user_id] = user
            logger.info(f"👤 Создан новый пользователь: {user.display_name}")
        
        # Обновляем данные пользователя и активность
        user = self.users_cache[user_id]
        user.username = kwargs.get('username', user.username)
        user.first_name = kwargs.get('first_name', user.first_name)
        user.last_name = kwargs.get('last_name', user.last_name)
        user.update_activity()
        
        return user
    
    def get_all_users(self) -> List[User]:
        """Получить всех пользователей"""
        return list(self.users_cache.values())
    
    def get_users_count(self) -> int:
        """Получить количество пользователей"""
        return len(self.users_cache)
    
    def cleanup_old_backups(self, keep_count: int = 10):
        """Удаление старых резервных копий"""
        try:
            backups = list(self.backup_dir.glob("backup_*.json"))
            if len(backups) > keep_count:
                backups.sort(key=lambda x: x.stat().st_mtime)
                for backup in backups[:-keep_count]:
                    backup.unlink()
                logger.info(f"🗑️ Удалено {len(backups) - keep_count} старых бэкапов")
        except Exception as e:
            logger.error(f"❌ Ошибка очистки бэкапов: {e}")

# ===== СИСТЕМА ДОСТИЖЕНИЙ =====

class AchievementSystem:
    """Система достижений"""
    
    ACHIEVEMENTS = {
        'first_task': {
            'title': 'Первые шаги',
            'description': 'Создайте свою первую задачу',
            'icon': '🎯',
            'condition': lambda user: len(user.tasks) >= 1
        },
        'streak_3': {
            'title': 'Начинающий',
            'description': 'Поддерживайте streak 3 дня',
            'icon': '🔥',
            'condition': lambda user: max([task.current_streak for task in user.tasks.values()] + [0]) >= 3
        },
        'streak_7': {
            'title': 'Неделя силы',
            'description': 'Поддерживайте streak 7 дней',
            'icon': '💪',
            'condition': lambda user: max([task.current_streak for task in user.tasks.values()] + [0]) >= 7
        },
        'streak_30': {
            'title': 'Мастер привычек',
            'description': 'Поддерживайте streak 30 дней',
            'icon': '💎',
            'condition': lambda user: max([task.current_streak for task in user.tasks.values()] + [0]) >= 30
        },
        'streak_100': {
            'title': 'Легенда',
            'description': 'Поддерживайте streak 100 дней',
            'icon': '👑',
            'condition': lambda user: max([task.current_streak for task in user.tasks.values()] + [0]) >= 100
        },
        'tasks_10': {
            'title': 'Продуктивный',
            'description': 'Выполните 10 задач',
            'icon': '📈',
            'condition': lambda user: user.stats.completed_tasks >= 10
        },
        'tasks_50': {
            'title': 'Энтузиаст',
            'description': 'Выполните 50 задач',
            'icon': '🏆',
            'condition': lambda user: user.stats.completed_tasks >= 50
        },
        'tasks_100': {
            'title': 'Чемпион',
            'description': 'Выполните 100 задач',
            'icon': '🌟',
            'condition': lambda user: user.stats.completed_tasks >= 100
        },
        'tasks_500': {
            'title': 'Мастер продуктивности',
            'description': 'Выполните 500 задач',
            'icon': '⭐',
            'condition': lambda user: user.stats.completed_tasks >= 500
        },
        'perfect_week': {
            'title': 'Идеальная неделя',
            'description': 'Выполните все задачи 7 дней подряд',
            'icon': '✨',
            'condition': lambda user: user._check_perfect_week()
        }
    }
    
    @classmethod
    def check_achievements(cls, user: User) -> List[str]:
        """Проверка новых достижений пользователя"""
        new_achievements = []
        
        for achievement_id, achievement_data in cls.ACHIEVEMENTS.items():
            if achievement_id not in user.achievements:
                try:
                    if achievement_data['condition'](user):
                        user.achievements.append(achievement_id)
                        new_achievements.append(achievement_id)
                        logger.info(f"🏆 Пользователь {user.user_id} получил достижение: {achievement_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки достижения {achievement_id}: {e}")
        
        return new_achievements
    
    @classmethod
    def get_achievement_message(cls, achievement_id: str) -> str:
        """Получить сообщение о достижении"""
        if achievement_id not in cls.ACHIEVEMENTS:
            return "🏆 Новое достижение получено!"
        
        achievement = cls.ACHIEVEMENTS[achievement_id]
        return f"🏆 **Новое достижение!**\n\n{achievement['icon']} **{achievement['title']}**\n{achievement['description']}"

# Добавляем метод для проверки идеальной недели
def _check_perfect_week(self) -> bool:
    """Проверка идеальной недели (все задачи выполнены 7 дней подряд)"""
    if not self.tasks:
        return False
    
    today = date.today()
    for i in range(7):
        check_date = today - timedelta(days=i)
        daily_tasks = [task for task in self.tasks.values() if task.status == "active"]
        
        if not daily_tasks:
            return False
        
        completed_that_day = [
            task for task in daily_tasks 
            if any(c.date == check_date.isoformat() and c.completed for c in task.completions)
        ]
        
        if len(completed_that_day) != len(daily_tasks):
            return False
    
    return True

# Добавляем метод к классу User
User._check_perfect_week = _check_perfect_week

# ===== КЛАВИАТУРЫ И ИНТЕРФЕЙС =====

class KeyboardManager:
    """Менеджер клавиатур и интерфейса"""
    
    @staticmethod
    def get_main_keyboard() -> ReplyKeyboardMarkup:
        """Основная клавиатура"""
        keyboard = [
            [KeyboardButton("📝 Мои задачи"), KeyboardButton("➕ Добавить задачу")],
            [KeyboardButton("✅ Отметить выполнение"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("🏆 Достижения"), KeyboardButton("🔥 Лидерборд")],
            [KeyboardButton("⚙️ Настройки"), KeyboardButton("ℹ️ Помощь")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    @staticmethod
    def get_tasks_inline_keyboard(tasks: Dict[str, Task]) -> InlineKeyboardMarkup:
        """Инлайн клавиатура для списка задач"""
        keyboard = []
        
        for task_id, task in list(tasks.items())[:10]:  # Ограничиваем до 10 задач
            status_emoji = "✅" if task.is_completed_today() else "⭕"
            streak_info = f" 🔥{task.current_streak}" if task.current_streak > 0 else ""
            
            button_text = f"{status_emoji} {task.title[:25]}{streak_info}"
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"task_view_{task_id}")
            ])
        
        # Кнопки действий
        action_buttons = []
        if len(tasks) > 10:
            action_buttons.append(InlineKeyboardButton("📋 Больше задач", callback_data="tasks_more"))
        
        action_buttons.extend([
            InlineKeyboardButton("➕ Добавить", callback_data="task_add"),
            InlineKeyboardButton("🔄 Обновить", callback_data="tasks_refresh")
        ])
        
        keyboard.append(action_buttons)
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_task_actions_keyboard(task_id: str, is_completed_today: bool = False) -> InlineKeyboardMarkup:
        """Клавиатура действий с задачей"""
        keyboard = []
        
        if is_completed_today:
            keyboard.append([
                InlineKeyboardButton("❌ Отменить выполнение", callback_data=f"uncomplete_{task_id}")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("✅ Выполнить", callback_data=f"complete_{task_id}")
            ])
        
        keyboard.extend([
            [
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{task_id}"),
                InlineKeyboardButton("⏸️ Приостановить", callback_data=f"pause_{task_id}")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data=f"task_stats_{task_id}"),
                InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_{task_id}")
            ],
            [
                InlineKeyboardButton("⬅️ Назад к списку", callback_data="tasks_refresh")
            ]
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_priority_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура выбора приоритета"""
        keyboard = [
            [InlineKeyboardButton("🔴 Высокий", callback_data="priority_high")],
            [InlineKeyboardButton("🟡 Средний", callback_data="priority_medium")],
            [InlineKeyboardButton("🔵 Низкий", callback_data="priority_low")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_completion_keyboard(active_tasks: Dict[str, Task]) -> InlineKeyboardMarkup:
        """Клавиатура для отметки выполнения"""
        keyboard = []
        
        incomplete_tasks = {
            k: v for k, v in active_tasks.items() 
            if not v.is_completed_today()
        }
        
        for task_id, task in list(incomplete_tasks.items())[:8]:  # Ограничиваем до 8
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(task.priority, "🟡")
            button_text = f"{priority_emoji} {task.title[:25]}"
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"complete_{task_id}")
            ])
        
        if not incomplete_tasks:
            keyboard.append([
                InlineKeyboardButton("🎉 Все задачи выполнены!", callback_data="tasks_all_done")
            ])
        
        keyboard.append([
            InlineKeyboardButton("❌ Отмена", callback_data="completion_cancel")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_stats_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура для статистики"""
        keyboard = [
            [
                InlineKeyboardButton("📈 Детальная статистика", callback_data="stats_detailed"),
                InlineKeyboardButton("📊 График прогресса", callback_data="stats_chart")
            ],
            [
                InlineKeyboardButton("📋 Экспорт данных", callback_data="stats_export"),
                InlineKeyboardButton("🔄 Обновить", callback_data="stats_refresh")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_settings_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура настроек"""
        keyboard = [
            [
                InlineKeyboardButton("🔔 Напоминания", callback_data="settings_reminders"),
                InlineKeyboardButton("🌍 Язык и время", callback_data="settings_locale")
            ],
            [
                InlineKeyboardButton("📊 Уведомления", callback_data="settings_notifications"),
                InlineKeyboardButton("🎨 Интерфейс", callback_data="settings_interface")
            ],
            [
                InlineKeyboardButton("📝 Заметки", callback_data="settings_notes"),
                InlineKeyboardButton("🔄 Обновить", callback_data="settings_refresh")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

# ===== ФОРМАТИРОВАНИЕ И УТИЛИТЫ =====

class MessageFormatter:
    """Форматировщик сообщений"""
    
    PRIORITY_EMOJIS = {
        "high": "🔴",
        "medium": "🟡",
        "low": "🔵"
    }
    
    STATUS_EMOJIS = {
        "active": "⭕",
        "completed": "✅",
        "paused": "⏸️",
        "archived": "📦"
    }
    
    @classmethod
    def format_task_info(cls, task: Task, detailed: bool = True) -> str:
        """Форматирование информации о задаче"""
        priority_emoji = cls.PRIORITY_EMOJIS.get(task.priority, "🟡")
        status_emoji = cls.STATUS_EMOJIS.get(task.status, "⭕")
        
        # Заголовок
        info = f"{status_emoji} **{task.title}**\n"
        
        # Описание
        if task.description and detailed:
            info += f"📝 {task.description}\n"
        
        # Статус выполнения на сегодня
        if task.is_completed_today():
            info += "✅ Выполнено сегодня\n"
        else:
            info += "⭕ Не выполнено сегодня\n"
        
        # Основная информация
        info += f"{priority_emoji} Приоритет: {task.priority}\n"
        info += f"🔥 Streak: {task.current_streak} дней\n"
        
        if detailed:
            info += f"📈 Неделя: {task.completion_rate_week:.1f}%\n"
            info += f"📊 Месяц: {task.completion_rate_month:.1f}%\n"
            
            if task.tags:
                info += f"🏷️ Теги: {', '.join(task.tags)}\n"
            
            # Дата создания
            try:
                created_date = datetime.fromisoformat(task.created_at).strftime('%d.%m.%Y')
                info += f"📅 Создана: {created_date}\n"
            except:
                info += f"📅 Создана: {task.created_at}\n"
            
            # Последние выполнения
            recent_completions = [
                c for c in task.completions 
                if c.completed and date.fromisoformat(c.date) >= date.today() - timedelta(days=7)
            ]
            if recent_completions:
                info += f"🕐 Последние выполнения: {len(recent_completions)} за неделю"
        
        return info
    
    @classmethod
    def format_user_stats(cls, user: User, detailed: bool = False) -> str:
        """Форматирование статистики пользователя"""
        # Сбор данных
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        total_tasks = len(user.tasks)
        active_tasks = len(user.active_tasks)
        completed_today = len(user.completed_tasks_today)
        
        # Подсчет выполнений за периоды
        completed_week = completed_month = 0
        for task in user.tasks.values():
            for completion in task.completions:
                if completion.completed:
                    comp_date = date.fromisoformat(completion.date)
                    if comp_date >= week_ago:
                        completed_week += 1
                    if comp_date >= month_ago:
                        completed_month += 1
        
        # Streak статистика
        current_streaks = [task.current_streak for task in user.active_tasks.values()]
        max_streak = max(current_streaks) if current_streaks else 0
        avg_streak = sum(current_streaks) / len(current_streaks) if current_streaks else 0
        
        # Формирование текста
        stats_text = f"""📊 **Статистика {user.display_name}**

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
• Максимальный текущий: {max_streak} дней
• Средний: {avg_streak:.1f} дней
• Личный рекорд: {user.stats.longest_streak} дней"""

        if detailed:
            try:
                reg_date = datetime.fromisoformat(user.stats.registration_date).strftime('%d.%m.%Y')
            except:
                reg_date = "неизвестно"
            
            stats_text += f"""

👤 **Профиль:**
• Регистрация: {reg_date}
• Дней в системе: {user.stats.days_since_registration}
• Достижений: {len(user.achievements)}

🏆 **Достижения:**"""
            
            if user.achievements:
                for achievement_id in user.achievements[-3:]:  # Последние 3
                    if achievement_id in AchievementSystem.ACHIEVEMENTS:
                        ach = AchievementSystem.ACHIEVEMENTS[achievement_id]
                        stats_text += f"\n• {ach['icon']} {ach['title']}"
            else:
                stats_text += "\n• Пока нет достижений"
        
        return stats_text
    
    @classmethod
    def format_leaderboard(cls, users: List[User], current_user_id: int) -> str:
        """Форматирование таблицы лидеров"""
        if len(users) < 2:
            return "🏆 **Таблица лидеров**\n\nНедостаточно пользователей для составления рейтинга.\nПригласите друзей использовать бота!"
        
        # Подготовка данных для рейтинга
        user_data = []
        for user in users:
            if not user.tasks:
                continue
            
            max_streak = max([task.current_streak for task in user.active_tasks.values()] + [0])
            total_completed = user.stats.completed_tasks
            
            user_data.append({
                'user': user,
                'max_streak': max_streak,
                'total_completed': total_completed,
                'completion_rate': user.stats.completion_rate
            })
        
        if not user_data:
            return "🏆 **Таблица лидеров**\n\nПока нет данных для рейтинга."
        
        # Сортировка по максимальному streak
        user_data.sort(key=lambda x: (x['max_streak'], x['total_completed']), reverse=True)
        
        leaderboard_text = "🏆 **Таблица лидеров**\n\n📈 *По streak'ам:*\n"
        
        for i, data in enumerate(user_data[:10], 1):
            user = data['user']
            is_current = "← Вы" if user.user_id == current_user_id else ""
            
            emoji = "👑" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            leaderboard_text += f"{emoji} {user.display_name} - {data['max_streak']} дней {is_current}\n"
        
        # Добавляем рейтинг по общему количеству выполнений
        user_data.sort(key=lambda x: x['total_completed'], reverse=True)
        
        leaderboard_text += "\n🎯 *По выполнениям:*\n"
        
        for i, data in enumerate(user_data[:5], 1):
            user = data['user']
            is_current = "← Вы" if user.user_id == current_user_id else ""
            
            emoji = "🔥" if i == 1 else f"{i}."
            
            leaderboard_text += f"{emoji} {user.display_name} - {data['total_completed']} задач {is_current}\n"
        
        return leaderboard_text

# ===== СОСТОЯНИЯ ДЛЯ CONVERSATION HANDLERS =====

# Состояния для создания задачи
TASK_TITLE, TASK_DESCRIPTION, TASK_PRIORITY, TASK_TAGS = range(4)

# Состояния для настроек
SETTINGS_REMINDER_TIME, SETTINGS_NOTES = range(100, 102)

# ===== ОБРАБОТЧИКИ КОМАНД =====

class CommandHandlers:
    """Обработчики команд бота"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_telegram = update.effective_user
        user = self.db.get_or_create_user(
            user_id=user_telegram.id,
            username=user_telegram.username,
            first_name=user_telegram.first_name,
            last_name=user_telegram.last_name
        )
        
        self.db.save_all_users()
        logger.info(f"Команда /start от пользователя {user.user_id}")
        
        # Проверяем достижения
        new_achievements = AchievementSystem.check_achievements(user)
        if new_achievements:
            self.db.save_all_users()
        
        welcome_text = f"""🎯 **Добро пожаловать в DailyCheck Bot v4.0!**

Привет, {user.display_name}! 

Я помогу тебе:
📝 Создавать и отслеживать ежедневные задачи
✅ Отмечать выполнение и следить за прогрессом  
📊 Анализировать статистику и строить полезные привычки
🔥 Поддерживать мотивацию с помощью streak'ов
🏆 Получать достижения за успехи

**Статистика:**
• Задач: {len(user.tasks)}
• Активных: {len(user.active_tasks)}
• Выполнено: {user.stats.completed_tasks}
• Достижений: {len(user.achievements)}

Выбери действие в меню ниже:"""
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=KeyboardManager.get_main_keyboard(),
            parse_mode='Markdown'
        )
        
        # Отправляем уведомления о новых достижениях
        for achievement_id in new_achievements:
            achievement_msg = AchievementSystem.get_achievement_message(achievement_id)
            await update.message.reply_text(achievement_msg, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        help_text = """📖 **Справка по DailyCheck Bot v4.0**

🔹 **Основные команды:**
/start - Перезапустить бота
/help - Показать эту справку
/tasks - Список ваших задач
/add - Добавить новую задачу
/stats - Показать статистику
/achievements - Ваши достижения
/leaderboard - Таблица лидеров
/settings - Настройки
/export - Экспорт данных

🔹 **Быстрые действия:**
📝 Мои задачи - просмотр всех задач
➕ Добавить задачу - создание новой задачи
✅ Отметить выполнение - отметка задач как выполненных
📊 Статистика - ваш прогресс и аналитика
🏆 Достижения - полученные награды
🔥 Лидерборд - сравнение с другими пользователями

🔹 **Возможности:**
• Создание ежедневных задач с приоритетами и тегами
• Отслеживание streak'ов (серий выполнения)
• Система достижений и мотивации
• Детальная статистика и аналитика
• Экспорт данных в различных форматах
• Таблица лидеров для соревнования
• Персональные настройки и заметки

🔹 **Streak система:**
Streak - это количество дней подряд, которые вы выполняете задачу.
Чем длиннее streak, тем сильнее привычка!

🔹 **Достижения:**
Получайте награды за различные успехи:
• Создание задач
• Длинные streak'и  
• Большое количество выполнений
• Идеальные недели

💡 **Совет:** Используйте кнопки для быстрого доступа к функциям!"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /tasks - показать список задач"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        if not user.tasks:
            await update.message.reply_text(
                "📝 **У вас пока нет задач!**\n\nСоздайте первую задачу, чтобы начать отслеживать свой прогресс.\n\nИспользуйте кнопку '➕ Добавить задачу' или команду /add",
                reply_markup=KeyboardManager.get_main_keyboard(),
                parse_mode='Markdown'
            )
            return
        
        active_tasks = user.active_tasks
        
        if not active_tasks:
            await update.message.reply_text(
                "📝 **У вас нет активных задач!**\n\nВсе задачи выполнены или приостановлены.\n\nМожете создать новые задачи или активировать существующие.",
                reply_markup=KeyboardManager.get_main_keyboard(),
                parse_mode='Markdown'
            )
            return
        
        # Подсчитываем статистику
        completed_today = len(user.completed_tasks_today)
        completion_percentage = (completed_today / len(active_tasks)) * 100
        
        text = f"📝 **Ваши активные задачи ({len(active_tasks)}):**\n\n"
        text += f"📊 Прогресс сегодня: {completed_today}/{len(active_tasks)} ({completion_percentage:.0f}%)\n\n"
        
        # Показываем первые 5 задач в тексте
        for i, (task_id, task) in enumerate(list(active_tasks.items())[:5], 1):
            status_emoji = "✅" if task.is_completed_today() else "⭕"
            priority_emoji = MessageFormatter.PRIORITY_EMOJIS.get(task.priority, "🟡")
            
            text += f"{i}. {status_emoji} {priority_emoji} {task.title}\n"
            text += f"   🔥 Streak: {task.current_streak} | 📈 Неделя: {task.completion_rate_week:.0f}%\n\n"
        
        if len(active_tasks) > 5:
            text += f"... и еще {len(active_tasks) - 5} задач\n\n"
        
        text += "Выберите задачу для подробной информации:"
        
        await update.message.reply_text(
            text,
            reply_markup=KeyboardManager.get_tasks_inline_keyboard(active_tasks),
            parse_mode='Markdown'
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats - показать статистику"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        if not user.tasks:
            await update.message.reply_text(
                "📊 **Статистика недоступна**\n\nУ вас пока нет задач!\n\nСоздайте первую задачу для начала отслеживания прогресса.",
                reply_markup=KeyboardManager.get_main_keyboard(),
                parse_mode='Markdown'
            )
            return
        
        stats_text = MessageFormatter.format_user_stats(user, detailed=True)
        
        await update.message.reply_text(
            stats_text,
            reply_markup=KeyboardManager.get_stats_keyboard(),
            parse_mode='Markdown'
        )
    
    async def achievements_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /achievements - показать достижения"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        # Проверяем новые достижения
        new_achievements = AchievementSystem.check_achievements(user)
        if new_achievements:
            self.db.save_all_users()
        
        if not user.achievements:
            text = """🏆 **Ваши достижения**

У вас пока нет достижений!

Продолжайте использовать бота, создавайте задачи и поддерживайте streak'и, чтобы получить первые награды.

🎯 **Доступные достижения:**
• 🎯 Первые шаги - создайте первую задачу
• 🔥 Начинающий - streak 3 дня
• 💪 Неделя силы - streak 7 дней
• 📈 Продуктивный - выполните 10 задач
... и многие другие!"""
        else:
            text = f"🏆 **Ваши достижения ({len(user.achievements)}):**\n\n"
            
            for achievement_id in user.achievements:
                if achievement_id in AchievementSystem.ACHIEVEMENTS:
                    ach = AchievementSystem.ACHIEVEMENTS[achievement_id]
                    text += f"{ach['icon']} **{ach['title']}**\n"
                    text += f"   {ach['description']}\n\n"
            
            # Показываем прогресс к следующим достижениям
            text += "🎯 **Ближайшие цели:**\n"
            
            # Проверяем прогресс к streak достижениям
            max_streak = max([task.current_streak for task in user.active_tasks.values()] + [0])
            
            if 'streak_3' not in user.achievements and max_streak < 3:
                text += f"🔥 Streak 3 дня - осталось {3 - max_streak} дней\n"
            elif 'streak_7' not in user.achievements and max_streak < 7:
                text += f"💪 Streak 7 дней - осталось {7 - max_streak} дней\n"
            elif 'streak_30' not in user.achievements and max_streak < 30:
                text += f"💎 Streak 30 дней - осталось {30 - max_streak} дней\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
        # Отправляем уведомления о новых достижениях
        for achievement_id in new_achievements:
            achievement_msg = AchievementSystem.get_achievement_message(achievement_id)
            await update.message.reply_text(achievement_msg, parse_mode='Markdown')
    
    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /leaderboard - таблица лидеров"""
        all_users = self.db.get_all_users()
        current_user_id = update.effective_user.id
        
        leaderboard_text = MessageFormatter.format_leaderboard(all_users, current_user_id)
        
        await update.message.reply_text(leaderboard_text, parse_mode='Markdown')
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /settings - настройки пользователя"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        settings_text = f"""⚙️ **Настройки**

🌍 **Локализация:**
• Язык: {user.settings.language}
• Часовой пояс: {user.settings.timezone}

🔔 **Напоминания:**
• Включены: {'✅' if user.settings.reminder_enabled else '❌'}
• Время: {user.settings.daily_reminder_time}

📊 **Уведомления:**
• Еженедельная статистика: {'✅' if user.settings.weekly_stats else '❌'}
• Мотивационные сообщения: {'✅' if user.settings.motivational_messages else '❌'}
• Звук уведомлений: {'✅' if user.settings.notification_sound else '❌'}

🎨 **Интерфейс:**
• Автоархивирование: {'✅' if user.settings.auto_archive_completed else '❌'}

📝 **Заметки:**
{user.notes[:100] + '...' if len(user.notes) > 100 else user.notes or 'Заметки не добавлены'}"""
        
        await update.message.reply_text(
            settings_text,
            reply_markup=KeyboardManager.get_settings_keyboard(),
            parse_mode='Markdown'
        )
    
    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /export - экспорт данных"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        if not user.tasks:
            await update.message.reply_text(
                "📊 **Нет данных для экспорта**\n\nУ вас пока нет задач!"
            )
            return
        
        try:
            # Создаем данные для экспорта
            export_data = {
                "user_info": {
                    "user_id": user.user_id,
                    "display_name": user.display_name,
                    "username": user.username,
                    "registration_date": user.stats.registration_date,
                    "export_date": datetime.now().isoformat(),
                    "export_version": "4.0"
                },
                "statistics": user.stats.to_dict(),
                "settings": user.settings.to_dict(),
                "tasks": [task.to_dict() for task in user.tasks.values()],
                "achievements": user.achievements,
                "notes": user.notes
            }
            
            # Создаем JSON файл
            export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
            file_buffer = io.BytesIO(export_json.encode('utf-8'))
            file_buffer.name = f"dailycheck_export_{user.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            caption = f"""📊 **Экспорт данных DailyCheck Bot v4.0**

👤 Пользователь: {user.display_name}
📅 Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}
📝 Задач: {len(user.tasks)}
🏆 Достижений: {len(user.achievements)}

Файл содержит всю информацию о ваших задачах, статистике и настройках."""
            
            await update.message.reply_document(
                document=file_buffer,
                caption=caption,
                filename=file_buffer.name
            )
            
            logger.info(f"Экспорт данных для пользователя {user.user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка экспорта данных: {e}")
            await update.message.reply_text(
                "❌ **Ошибка экспорта**\n\nПроизошла ошибка при создании файла экспорта. Попробуйте позже."
            )

# ===== ОБРАБОТЧИКИ СОЗДАНИЯ ЗАДАЧ =====

class TaskCreationHandlers:
    """Обработчики создания задач через ConversationHandler"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def add_task_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания задачи"""
        await update.message.reply_text(
            "📝 **Создание новой задачи**\n\nВведите название задачи (максимум 100 символов):",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        return TASK_TITLE
    
    async def add_task_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение названия задачи"""
        title = update.message.text.strip()
        
        if len(title) > 100:
            await update.message.reply_text(
                "❌ **Название слишком длинное!**\n\nМаксимум 100 символов.\nПопробуйте еще раз:"
            )
            return TASK_TITLE
        
        if len(title) < 3:
            await update.message.reply_text(
                "❌ **Название слишком короткое!**\n\nМинимум 3 символа.\nПопробуйте еще раз:"
            )
            return TASK_TITLE
        
        context.user_data['task_title'] = title
        
        await update.message.reply_text(
            f"✅ **Название:** {title}\n\nТеперь введите описание задачи (максимум 500 символов) или отправьте 'пропустить':",
            parse_mode='Markdown'
        )
        return TASK_DESCRIPTION
    
    async def add_task_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение описания задачи"""
        description = update.message.text.strip()
        
        if description.lower() in ['пропустить', 'skip', '-', 'нет']:
            description = None
        elif len(description) > 500:
            await update.message.reply_text(
                "❌ **Описание слишком длинное!**\n\nМаксимум 500 символов.\nПопробуйте еще раз (или 'пропустить'):"
            )
            return TASK_DESCRIPTION
        
        context.user_data['task_description'] = description
        
        await update.message.reply_text(
            f"✅ **Описание:** {description or 'не указано'}\n\nВыберите приоритет задачи:",
            reply_markup=KeyboardManager.get_priority_keyboard(),
            parse_mode='Markdown'
        )
        return TASK_PRIORITY
    
    async def add_task_priority(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение приоритета задачи"""
        query = update.callback_query
        await query.answer()
        
        priority_map = {
            "priority_high": "high",
            "priority_medium": "medium",
            "priority_low": "low"
        }
        
        priority = priority_map.get(query.data, "medium")
        context.user_data['task_priority'] = priority
        
        priority_names = {"high": "Высокий", "medium": "Средний", "low": "Низкий"}
        
        await query.edit_message_text(
            f"✅ **Приоритет:** {priority_names[priority]}\n\nВведите теги через запятую (максимум 5 тегов) или 'пропустить':"
        )
        return TASK_TAGS
    
    async def add_task_tags(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение тегов и создание задачи"""
        tags_text = update.message.text.strip()
        
        if tags_text.lower() in ['пропустить', 'skip', '-', 'нет']:
            tags = []
        else:
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
            tags = tags[:5]  # Максимум 5 тегов
            tags = [tag[:20] for tag in tags]  # Максимум 20 символов на тег
        
        # Создаем задачу
        user = self.db.get_or_create_user(update.effective_user.id)
        
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
        
        # Проверяем достижения
        new_achievements = AchievementSystem.check_achievements(user)
        
        # Сохраняем
        self.db.save_all_users()
        
        # Очищаем данные из контекста
        context.user_data.clear()
        
        success_text = f"🎉 **Задача создана!**\n\n{MessageFormatter.format_task_info(task)}"
        
        await update.message.reply_text(
            success_text,
            reply_markup=KeyboardManager.get_main_keyboard(),
            parse_mode='Markdown'
        )
        
        # Отправляем уведомления о новых достижениях
        for achievement_id in new_achievements:
            achievement_msg = AchievementSystem.get_achievement_message(achievement_id)
            await update.message.reply_text(achievement_msg, parse_mode='Markdown')
        
        logger.info(f"Пользователь {user.user_id} создал задачу: {task.title}")
        return ConversationHandler.END
    
    async def cancel_add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания задачи"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ **Создание задачи отменено.**",
            reply_markup=KeyboardManager.get_main_keyboard(),
            parse_mode='Markdown'
        )
        return ConversationHandler.END

# ===== ОБРАБОТЧИКИ CALLBACK ЗАПРОСОВ =====

class CallbackHandlers:
    """Обработчики callback запросов"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def handle_task_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Основной обработчик callback для задач"""
        query = update.callback_query
        await query.answer()
        
        user = self.db.get_or_create_user(update.effective_user.id)
        data = query.data
        
        try:
            if data.startswith("task_view_"):
                await self._handle_task_view(query, user, data)
            elif data.startswith("complete_"):
                await self._handle_task_complete(query, user, data)
            elif data.startswith("uncomplete_"):
                await self._handle_task_uncomplete(query, user, data)
            elif data.startswith("pause_"):
                await self._handle_task_pause(query, user, data)
            elif data.startswith("delete_"):
                await self._handle_task_delete(query, user, data)
            elif data.startswith("task_stats_"):
                await self._handle_task_stats(query, user, data)
            elif data == "tasks_refresh":
                await self._handle_tasks_refresh(query, user)
            elif data == "tasks_more":
                await self._handle_tasks_more(query, user)
            elif data == "completion_cancel":
                await query.edit_message_text("❌ Отметка выполнения отменена.")
            elif data == "tasks_all_done":
                await query.edit_message_text("🎉 Отлично! Все задачи на сегодня выполнены!\n\nПродолжайте в том же духе!")
        except Exception as e:
            logger.error(f"Ошибка обработки callback {data}: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")
    
    async def _handle_task_view(self, query, user: User, data: str):
        """Просмотр детальной информации о задаче"""
        task_id = data.replace("task_view_", "")
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        
        task_info = MessageFormatter.format_task_info(task, detailed=True)
        keyboard = KeyboardManager.get_task_actions_keyboard(task_id, task.is_completed_today())
        
        await query.edit_message_text(
            task_info,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def _handle_task_complete(self, query, user: User, data: str):
        """Отметка задачи как выполненной"""
        task_id = data.replace("complete_", "")
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        
        if task.is_completed_today():
            await query.edit_message_text("✅ Задача уже выполнена сегодня!")
            return
        
        # Отмечаем как выполненную
        if task.mark_completed():
            user.stats.completed_tasks += 1
            
            # Обновляем максимальный streak пользователя
            if task.current_streak > user.stats.longest_streak:
                user.stats.longest_streak = task.current_streak
            
            # Проверяем достижения
            new_achievements = AchievementSystem.check_achievements(user)
            
            self.db.save_all_users()
            
            streak_text = f"🔥 Streak: {task.current_streak} дней!"
            if task.current_streak > 1 and task.current_streak == user.stats.longest_streak:
                streak_text += " 🏆 Новый личный рекорд!"
            
            motivational_messages = [
                "Отличная работа! 💪",
                "Так держать! 🎯",
                "Вы на правильном пути! 🌟",
                "Каждый день делает вас сильнее! 💪",
                "Продолжайте в том же духе! 🔥"
            ]
            
            response_text = f"""🎉 **Задача выполнена!**

✅ {task.title}
{streak_text}

{random.choice(motivational_messages)}"""
            
            await query.edit_message_text(response_text, parse_mode='Markdown')
            
            # Отправляем уведомления о новых достижениях
            for achievement_id in new_achievements:
                achievement_msg = AchievementSystem.get_achievement_message(achievement_id)
                await query.message.reply_text(achievement_msg, parse_mode='Markdown')
            
            logger.info(f"Пользователь {user.user_id} выполнил задачу: {task.title}")
        else:
            await query.edit_message_text("❌ Ошибка при отметке выполнения.")
    
    async def _handle_task_uncomplete(self, query, user: User, data: str):
        """Отмена выполнения задачи"""
        task_id = data.replace("uncomplete_", "")
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        
        if not task.is_completed_today():
            await query.edit_message_text("⭕ Задача не была выполнена сегодня!")
            return
        
        if task.mark_uncompleted():
            user.stats.completed_tasks = max(0, user.stats.completed_tasks - 1)
            self.db.save_all_users()
            
            await query.edit_message_text(
                f"❌ **Выполнение отменено**\n\n⭕ {task.title}\n\nВы можете выполнить эту задачу позже."
            )
            
            logger.info(f"Пользователь {user.user_id} отменил выполнение задачи: {task.title}")
        else:
            await query.edit_message_text("❌ Ошибка при отмене выполнения.")
    
    async def _handle_task_pause(self, query, user: User, data: str):
        """Приостановка задачи"""
        task_id = data.replace("pause_", "")
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        task.status = "paused"
        self.db.save_all_users()
        
        await query.edit_message_text(
            f"⏸️ **Задача приостановлена**\n\n{task.title}\n\nВы можете активировать её позже через настройки."
        )
        
        logger.info(f"Пользователь {user.user_id} приостановил задачу: {task.title}")
    
    async def _handle_task_delete(self, query, user: User, data: str):
        """Удаление задачи"""
        task_id = data.replace("delete_", "")
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        task_title = task.title
        
        # Создаем клавиатуру подтверждения
        keyboard = [
            [
                InlineKeyboardButton("🗑️ Да, удалить", callback_data=f"confirm_delete_{task_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"task_view_{task_id}")
            ]
        ]
        
        await query.edit_message_text(
            f"⚠️ **Подтвердите удаление**\n\n🗑️ {task_title}\n\n**Внимание:** Все данные о выполнении будут потеряны!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _handle_task_stats(self, query, user: User, data: str):
        """Статистика конкретной задачи"""
        task_id = data.replace("task_stats_", "")
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        
        # Подробная статистика
        total_completions = len([c for c in task.completions if c.completed])
        total_days = (datetime.now() - datetime.fromisoformat(task.created_at)).days + 1
        overall_rate = (total_completions / total_days) * 100 if total_days > 0 else 0
        
        # Последние выполнения
        recent_completions = [
            c for c in task.completions 
            if c.completed and date.fromisoformat(c.date) >= date.today() - timedelta(days=30)
        ]
        
        stats_text = f"""📊 **Статистика задачи**

📝 {task.title}

🎯 **Общая статистика:**
• Всего выполнений: {total_completions}
• Дней с создания: {total_days}
• Общий процент: {overall_rate:.1f}%

🔥 **Streak информация:**
• Текущий streak: {task.current_streak} дней
• Статус: {'✅ Выполнено сегодня' if task.is_completed_today() else '⭕ Не выполнено сегодня'}

📈 **По периодам:**
• За неделю: {task.completion_rate_week:.1f}%
• За месяц: {task.completion_rate_month:.1f}%
• За 30 дней: {len(recent_completions)} выполнений

📅 **Создана:** {datetime.fromisoformat(task.created_at).strftime('%d.%m.%Y')}"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад к задаче", callback_data=f"task_view_{task_id}")]
        ]
        
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def _handle_tasks_refresh(self, query, user: User):
        """Обновление списка задач"""
        active_tasks = user.active_tasks
        
        if not active_tasks:
            await query.edit_message_text("📝 У вас нет активных задач!")
            return
        
        # Подсчитываем статистику
        completed_today = len(user.completed_tasks_today)
        completion_percentage = (completed_today / len(active_tasks)) * 100
        
        text = f"📝 **Ваши активные задачи ({len(active_tasks)}):**\n\n"
        text += f"📊 Прогресс сегодня: {completed_today}/{len(active_tasks)} ({completion_percentage:.0f}%)\n\n"
        
        # Краткий список
        for i, (task_id, task) in enumerate(list(active_tasks.items())[:5], 1):
            status_emoji = "✅" if task.is_completed_today() else "⭕"
            priority_emoji = MessageFormatter.PRIORITY_EMOJIS.get(task.priority, "🟡")
            
            text += f"{i}. {status_emoji} {priority_emoji} {task.title}\n"
            text += f"   🔥 Streak: {task.current_streak} | 📈 Неделя: {task.completion_rate_week:.0f}%\n\n"
        
        if len(active_tasks) > 5:
            text += f"... и еще {len(active_tasks) - 5} задач\n\n"
        
        text += "Выберите задачу для подробной информации:"
        
        await query.edit_message_text(
            text,
            reply_markup=KeyboardManager.get_tasks_inline_keyboard(active_tasks),
            parse_mode='Markdown'
        )
    
    async def _handle_tasks_more(self, query, user: User):
        """Показать больше задач"""
        all_tasks = user.tasks
        
        text = f"📝 **Все ваши задачи ({len(all_tasks)}):**\n\n"
        
        # Группируем по статусу
        active_tasks = [t for t in all_tasks.values() if t.status == "active"]
        paused_tasks = [t for t in all_tasks.values() if t.status == "paused"]
        archived_tasks = [t for t in all_tasks.values() if t.status == "archived"]
        
        if active_tasks:
            text += f"⭕ **Активные ({len(active_tasks)}):**\n"
            for task in active_tasks[:10]:
                status_emoji = "✅" if task.is_completed_today() else "⭕"
                text += f"• {status_emoji} {task.title} (🔥{task.current_streak})\n"
            
            if len(active_tasks) > 10:
                text += f"... и еще {len(active_tasks) - 10}\n"
            text += "\n"
        
        if paused_tasks:
            text += f"⏸️ **Приостановленные ({len(paused_tasks)}):**\n"
            for task in paused_tasks[:5]:
                text += f"• ⏸️ {task.title}\n"
            text += "\n"
        
        if archived_tasks:
            text += f"📦 **Архивные ({len(archived_tasks)}):**\n"
            for task in archived_tasks[:5]:
                text += f"• 📦 {task.title}\n"
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад к активным", callback_data="tasks_refresh")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

# ===== ОБРАБОТЧИКИ СООБЩЕНИЙ =====

class MessageHandlers:
    """Обработчики текстовых сообщений"""
    
    def __init__(self, db: DatabaseManager, command_handlers: CommandHandlers):
        self.db = db
        self.command_handlers = command_handlers
    
    async def handle_button_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Мои задачи'"""
        await self.command_handlers.tasks_command(update, context)
    
    async def handle_button_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Статистика'"""
        await self.command_handlers.stats_command(update, context)
    
    async def handle_button_achievements(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Достижения'"""
        await self.command_handlers.achievements_command(update, context)
    
    async def handle_button_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Лидерборд'"""
        await self.command_handlers.leaderboard_command(update, context)
    
    async def handle_button_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Настройки'"""
        await self.command_handlers.settings_command(update, context)
    
    async def handle_button_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Помощь'"""
        await self.command_handlers.help_command(update, context)
    
    async def handle_button_completion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Отметить выполнение'"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        if not user.tasks:
            await update.message.reply_text(
                "📝 **У вас пока нет задач!**\n\nСоздайте первую задачу для отслеживания прогресса.",
                reply_markup=KeyboardManager.get_main_keyboard()
            )
            return
        
        active_tasks = user.active_tasks
        
        if not active_tasks:
            await update.message.reply_text(
                "📝 **Нет активных задач!**\n\nВсе задачи приостановлены или архивированы.",
                reply_markup=KeyboardManager.get_main_keyboard()
            )
            return
        
        # Проверяем незавершенные задачи
        incomplete_tasks = {
            k: v for k, v in active_tasks.items() 
            if not v.is_completed_today()
        }
        
        if not incomplete_tasks:
            motivational_messages = [
                "🎉 Поздравляем! Все задачи на сегодня выполнены!",
                "✨ Отлично! Вы завершили все запланированные задачи!",
                "🏆 Превосходно! День прошел продуктивно!",
                "💪 Великолепно! Все цели достигнуты!"
            ]
            
            message = random.choice(motivational_messages)
            completed_count = len(user.completed_tasks_today)
            
            await update.message.reply_text(
                f"{message}\n\n📊 Выполнено задач: {completed_count}\n\nПродолжайте в том же духе! Завтра вас ждут новые вызовы! 🚀",
                reply_markup=KeyboardManager.get_main_keyboard()
            )
            return
        
        text = f"✅ **Отметка выполнения**\n\nВыберите задачу для отметки ({len(incomplete_tasks)} доступно):"
        
        await update.message.reply_text(
            text,
            reply_markup=KeyboardManager.get_completion_keyboard(active_tasks),
            parse_mode='Markdown'
        )
    
    async def handle_unknown_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик неизвестных сообщений"""
        if update.message and update.message.text:
            user = self.db.get_or_create_user(update.effective_user.id)
            message_text = update.message.text
            
            logger.info(f"Сообщение от {user.user_id}: {message_text[:50]}...")
            
            # Попытаемся угадать намерение пользователя
            message_lower = message_text.lower()
            
            if any(word in message_lower for word in ['задач', 'task', 'дел']):
                await self.command_handlers.tasks_command(update, context)
            elif any(word in message_lower for word in ['стат', 'прогресс', 'результат']):
                await self.command_handlers.stats_command(update, context)
            elif any(word in message_lower for word in ['достиж', 'награ', 'achievement']):
                await self.command_handlers.achievements_command(update, context)
            elif any(word in message_lower for word in ['лидер', 'рейтинг', 'топ']):
                await self.command_handlers.leaderboard_command(update, context)
            elif any(word in message_lower for word in ['настрой', 'setting']):
                await self.command_handlers.settings_command(update, context)
            elif any(word in message_lower for word in ['помощ', 'help', 'справка']):
                await self.command_handlers.help_command(update, context)
            else:
                # Случайный мотивационный ответ
                responses = [
                    "🤔 Я не понимаю эту команду, но вижу, что вы активны! Это здорово!",
                    "💭 Интересное сообщение! Используйте меню ниже для навигации.",
                    "🎯 Не совсем понял, но готов помочь! Выберите действие из меню.",
                    "🚀 Отличная энергия! Давайте направим её на выполнение задач!"
                ]
                
                response = random.choice(responses)
                response += "\n\n💡 **Подсказка:** Используйте кнопки меню или команды:\n"
                response += "• /tasks - ваши задачи\n• /stats - статистика\n• /help - справка"
                
                await update.message.reply_text(
                    response,
                    reply_markup=KeyboardManager.get_main_keyboard()
                )

# ===== ОСНОВНОЙ КЛАСС БОТА =====

class DailyCheckBot:
    """Основной класс DailyCheck Bot v4.0"""
    
    def __init__(self):
        # Инициализация конфигурации
        self.bot_token = os.getenv('BOT_TOKEN')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.port = int(os.getenv('PORT', 10000))
        self.debug = os.getenv('DEBUG', 'false').lower() == 'true'
        
        # Проверка обязательных параметров
        if not self.bot_token:
            logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
            sys.exit(1)
        
        logger.info(f"✅ BOT_TOKEN: {self.bot_token[:10]}...")
        logger.info(f"✅ OpenAI: {self.openai_api_key[:10] if self.openai_api_key else 'не настроен'}...")
        logger.info("✅ Telegram библиотеки импортированы")
        logger.info("🚀 Запуск DailyCheck Bot v4.0 - ПОЛНАЯ ВЕРСИЯ...")
        logger.info(f"Python: {sys.version}")
        logger.info(f"Платформа: {sys.platform}")
        logger.info(f"Порт: {self.port}")
        
        # Инициализация компонентов
        logger.info("📂 Загрузка данных пользователей...")
        self.db = DatabaseManager()
        
        self.application = None
        
        # Инициализация обработчиков
        self.command_handlers = CommandHandlers(self.db)
        self.task_creation_handlers = TaskCreationHandlers(self.db)
        self.callback_handlers = CallbackHandlers(self.db)
        self.message_handlers = MessageHandlers(self.db, self.command_handlers)
    
    async def setup_bot(self):
        """Настройка бота с обработкой конфликтов"""
        try:
            # Создаем приложение
            self.application = Application.builder().token(self.bot_token).build()
            
            # КРИТИЧНО: Удаляем webhook если он установлен
            logger.info("🌐 Запуск HTTP сервера...")
            await self.application.bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ HTTP сервер ЗАПУЩЕН на 0.0.0.0:{}".format(self.port))
            
            # Небольшая задержка для стабилизации
            await asyncio.sleep(5)
            logger.info("🌐 Health check доступен на http://0.0.0.0:{}".format(self.port))
            await asyncio.sleep(3)
            logger.info("⏳ HTTP сервер стабилизировался")
            
            # Регистрируем обработчики
            logger.info("🤖 Создание Telegram приложения...")
            await self._register_handlers()
            
            logger.info("✅ Бот настроен успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка настройки бота: {e}")
            raise
    
    async def _register_handlers(self):
        """Регистрация всех обработчиков"""
        logger.info("📋 Регистрация обработчиков команд...")
        
        # Основные команды
        self.application.add_handler(CommandHandler("start", self.command_handlers.start_command))
        self.application.add_handler(CommandHandler("help", self.command_handlers.help_command))
        self.application.add_handler(CommandHandler("tasks", self.command_handlers.tasks_command))
        self.application.add_handler(CommandHandler("stats", self.command_handlers.stats_command))
        self.application.add_handler(CommandHandler("achievements", self.command_handlers.achievements_command))
        self.application.add_handler(CommandHandler("leaderboard", self.command_handlers.leaderboard_command))
        self.application.add_handler(CommandHandler("settings", self.command_handlers.settings_command))
        self.application.add_handler(CommandHandler("export", self.command_handlers.export_command))
        
        # ConversationHandler для создания задач
        add_task_conversation = ConversationHandler(
            entry_points=[
                CommandHandler("add", self.task_creation_handlers.add_task_start),
                MessageHandler(filters.Regex("^➕ Добавить задачу$"), self.task_creation_handlers.add_task_start)
            ],
            states={
                TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.task_creation_handlers.add_task_title)],
                TASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.task_creation_handlers.add_task_description)],
                TASK_PRIORITY: [CallbackQueryHandler(self.task_creation_handlers.add_task_priority, pattern="^priority_")],
                TASK_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.task_creation_handlers.add_task_tags)]
            },
            fallbacks=[
                CommandHandler("cancel", self.task_creation_handlers.cancel_add_task),
                MessageHandler(filters.Regex("^❌ Отмена$"), self.task_creation_handlers.cancel_add_task)
            ]
        )
        self.application.add_handler(add_task_conversation)
        
        # Обработчики кнопок главного меню
        self.application.add_handler(MessageHandler(filters.Regex("^📝 Мои задачи$"), self.message_handlers.handle_button_tasks))
        self.application.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), self.message_handlers.handle_button_stats))
        self.application.add_handler(MessageHandler(filters.Regex("^🏆 Достижения$"), self.message_handlers.handle_button_achievements))
        self.application.add_handler(MessageHandler(filters.Regex("^🔥 Лидерборд$"), self.message_handlers.handle_button_leaderboard))
        self.application.add_handler(MessageHandler(filters.Regex("^⚙️ Настройки$"), self.message_handlers.handle_button_settings))
        self.application.add_handler(MessageHandler(filters.Regex("^ℹ️ Помощь$"), self.message_handlers.handle_button_help))
        self.application.add_handler(MessageHandler(filters.Regex("^✅ Отметить выполнение$"), self.message_handlers.handle_button_completion))
        
        # Callback обработчики
        self.application.add_handler(CallbackQueryHandler(
            self.callback_handlers.handle_task_callback, 
            pattern="^(task_view_|complete_|uncomplete_|pause_|delete_|confirm_delete_|task_stats_|tasks_refresh|tasks_more|completion_cancel|tasks_all_done)"
        ))
        
        # Дополнительные команды для совместимости
        self.application.add_handler(CommandHandler("settasks", self.command_handlers.tasks_command))
        self.application.add_handler(CommandHandler("stats_global", self.command_handlers.stats_command))
        
        # Обработчик неизвестных сообщений (должен быть последним)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handlers.handle_unknown_message))
        
        # Подсчитываем количество обработчиков
        total_handlers = sum(len(handlers) for handlers in self.application.handlers.values())
        logger.info(f"✅ ВСЕ {total_handlers} КОМАНДЫ зарегистрированы!")
        logger.info("📱 Найдите бота в Telegram и отправьте /start")
    
    async def start_polling(self):
        """Запуск polling с обработкой ошибок"""
        try:
            logger.info("🎯 Запуск polling...")
            
            # Инициализируем приложение
            await self.application.initialize()
            await self.application.start()
            
            # Запускаем polling
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query', 'inline_query'],
            )
            
            logger.info("✅ Polling запущен успешно")
            
            # Ждем завершения
            await self.application.updater.idle()
            
        except Exception as e:
            logger.error(f"❌ Ошибка polling: {e}")
            raise
        finally:
            await self._stop()
    
    async def _error_handler(self, update, context):
        """Обработчик ошибок"""
        error = context.error
        
        if isinstance(error, Conflict):
            logger.error(f"Error while getting Updates: {error}")
            logger.warning("⚠️ Обнаружен конфликт getUpdates, попытка восстановления...")
            await asyncio.sleep(5)
            try:
                await self.application.bot.delete_webhook(drop_pending_updates=True)
                logger.info("🔄 Webhook очищен при ошибке")
            except Exception as e:
                logger.error(f"Ошибка очистки webhook: {e}")
        elif isinstance(error, (TimedOut, NetworkError)):
            logger.warning(f"⚠️ Временная сетевая ошибка: {error}")
        else:
            logger.error(f"❌ Неожиданная ошибка: {error}")
            
            # Если есть update, пытаемся ответить пользователю
            if update and update.effective_user:
                try:
                    if update.message:
                        await update.message.reply_text(
                            "⚠️ Произошла временная ошибка. Попробуйте еще раз через несколько секунд."
                        )
                    elif update.callback_query:
                        await update.callback_query.answer("⚠️ Временная ошибка. Попробуйте еще раз.")
                except:
                    pass
    
    async def _stop(self):
        """Остановка бота"""
        if self.application:
            try:
                # Сохраняем данные перед остановкой
                logger.info("💾 Сохранение данных перед остановкой...")
                self.db.save_all_users()
                self.db.cleanup_old_backups()
                
                # Останавливаем компоненты
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                
                logger.info("🛑 Бот остановлен корректно")
                
            except Exception as e:
                logger.error(f"❌ Ошибка при остановке: {e}")

# ===== ГЛАВНАЯ ФУНКЦИЯ =====

async def main():
    """Главная функция запуска бота"""
    bot = None
    
    def signal_handler(signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"📢 Получен сигнал {signum}, завершение работы...")
        if bot:
            asyncio.create_task(bot._stop())
        sys.exit(0)
    
    # Настраиваем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Создаем и настраиваем бота
        bot = DailyCheckBot()
        await bot.setup_bot()
        
        # Запускаем polling
        await bot.start_polling()
        
    except KeyboardInterrupt:
        logger.info("⌨️ Получено прерывание с клавиатуры")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        if bot:
            await bot._stop()

# ===== ТОЧКА ВХОДА =====

if __name__ == "__main__":
    try:
        # Для Render.com и других платформ - запускаем в asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)
