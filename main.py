#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Bot v4.0 - Полная модульная версия
Telegram бот для отслеживания ежедневных привычек и задач с AI-ассистентом

Автор: AI Assistant  
Версия: 4.0.0
Дата: 2025-06-10
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
import time
import threading
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import traceback

# Импорты для совместимости с различными платформами
import nest_asyncio
nest_asyncio.apply()

# Telegram Bot API - современная версия
from telegram import (
    Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    BotCommand, MenuButton, MenuButtonCommands, WebAppInfo
)
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)
from telegram.error import Conflict, TimedOut, NetworkError, TelegramError

# HTTP сервер для health checks
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver

# Внешние библиотеки
try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

# ===== КОНСТАНТЫ И КОНФИГУРАЦИЯ =====

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
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG').upper()  # Временно включаем DEBUG
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'true').lower() == 'true'  # Временно включаем DEBUG
    
    # Создаем директории
    @classmethod
    def ensure_directories(cls):
        """Создание необходимых директорий"""
        for directory in [cls.DATA_DIR, cls.EXPORT_DIR, cls.BACKUP_DIR, cls.LOG_DIR]:
            directory.mkdir(exist_ok=True)

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====

def setup_logging():
    """Настройка продвинутой системы логирования"""
    BotConfig.ensure_directories()
    
    # Настройка форматтера
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Основной логгер
    logger = logging.getLogger('dailycheck')
    
    # Устанавливаем уровень логирования
    if BotConfig.DEBUG_MODE:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(getattr(logging, BotConfig.LOG_LEVEL))
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый обработчик с ротацией
    log_file = BotConfig.LOG_DIR / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Отключаем излишне подробные логи внешних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logger

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

@dataclass
class TaskCompletion:
    """Запись о выполнении задачи"""
    date: str  # ISO формат даты (YYYY-MM-DD)
    completed: bool
    note: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    time_spent: Optional[int] = None  # в минутах
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "TaskCompletion":
        return cls(**data)

@dataclass 
class Subtask:
    """Подзадача"""
    subtask_id: str
    title: str
    completed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Subtask":
        return cls(**data)

@dataclass
class Task:
    """Модель задачи с расширенным функционалом"""
    task_id: str
    user_id: int
    title: str
    description: Optional[str] = None
    category: str = "personal"
    priority: str = "medium"
    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completions: List[TaskCompletion] = field(default_factory=list)
    subtasks: List[Subtask] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    is_daily: bool = True
    reminder_time: Optional[str] = None
    estimated_time: Optional[int] = None  # в минутах
    difficulty: int = 1  # 1-5
    
    @property
    def current_streak(self) -> int:
        """Текущая серия выполнения"""
        if not self.completions:
            return 0
        
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
    
    @property
    def subtasks_completed_count(self) -> int:
        """Количество выполненных подзадач"""
        return sum(1 for subtask in self.subtasks if subtask.completed)
    
    @property
    def subtasks_total_count(self) -> int:
        """Общее количество подзадач"""
        return len(self.subtasks)
    
    @property
    def xp_value(self) -> int:
        """XP за выполнение задачи"""
        base_xp = {"low": 10, "medium": 20, "high": 30}.get(self.priority, 20)
        difficulty_multiplier = self.difficulty * 0.2 + 0.8
        streak_bonus = min(self.current_streak * 2, 50)
        return int(base_xp * difficulty_multiplier + streak_bonus)
    
    def is_completed_today(self) -> bool:
        """Проверка выполнения задачи сегодня"""
        today = date.today().isoformat()
        return any(c.date == today and c.completed for c in self.completions)
    
    def mark_completed(self, note: Optional[str] = None, time_spent: Optional[int] = None) -> bool:
        """Отметить задачу как выполненную на сегодня"""
        today = date.today().isoformat()
        
        # Проверяем, не выполнена ли уже сегодня
        for completion in self.completions:
            if completion.date == today:
                completion.completed = True
                completion.note = note
                completion.time_spent = time_spent
                completion.timestamp = datetime.now().isoformat()
                return True
        
        # Добавляем новую запись
        self.completions.append(TaskCompletion(
            date=today,
            completed=True,
            note=note,
            time_spent=time_spent
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
    
    def add_subtask(self, title: str) -> str:
        """Добавить подзадачу"""
        subtask = Subtask(
            subtask_id=str(uuid.uuid4()),
            title=title
        )
        self.subtasks.append(subtask)
        return subtask.subtask_id
    
    def toggle_subtask(self, subtask_id: str) -> bool:
        """Переключить статус подзадачи"""
        for subtask in self.subtasks:
            if subtask.subtask_id == subtask_id:
                subtask.completed = not subtask.completed
                return True
        return False
    
    def to_dict(self) -> dict:
        """Сериализация в словарь"""
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "completions": [c.to_dict() for c in self.completions],
            "subtasks": [s.to_dict() for s in self.subtasks],
            "tags": self.tags,
            "is_daily": self.is_daily,
            "reminder_time": self.reminder_time,
            "estimated_time": self.estimated_time,
            "difficulty": self.difficulty
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Десериализация из словаря"""
        task = cls(
            task_id=data["task_id"],
            user_id=data["user_id"],
            title=data["title"],
            description=data.get("description"),
            category=data.get("category", "personal"),
            priority=data.get("priority", "medium"),
            status=data.get("status", "active"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            tags=data.get("tags", []),
            is_daily=data.get("is_daily", True),
            reminder_time=data.get("reminder_time"),
            estimated_time=data.get("estimated_time"),
            difficulty=data.get("difficulty", 1)
        )
        
        # Восстанавливаем записи о выполнении
        if "completions" in data:
            task.completions = [
                TaskCompletion.from_dict(c) if isinstance(c, dict) else c
                for c in data["completions"]
            ]
        
        # Восстанавливаем подзадачи
        if "subtasks" in data:
            task.subtasks = [
                Subtask.from_dict(s) if isinstance(s, dict) else s
                for s in data["subtasks"]
            ]
        
        return task

@dataclass
class Reminder:
    """Модель напоминания"""
    reminder_id: str
    user_id: int
    title: str
    message: str
    trigger_time: str  # ISO format или cron expression
    is_recurring: bool = False
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Reminder":
        return cls(**data)

@dataclass
class Friend:
    """Модель друга"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Friend":
        return cls(**data)

@dataclass
class UserSettings:
    """Расширенные настройки пользователя"""
    timezone: str = "UTC"
    language: str = "ru"
    theme: str = "classic"
    daily_reminder_time: str = "09:00"
    reminder_enabled: bool = True
    weekly_stats: bool = True
    motivational_messages: bool = True
    notification_sound: bool = True
    auto_archive_completed: bool = False
    ai_chat_enabled: bool = False  # По умолчанию выключен!
    show_xp: bool = True
    show_streaks: bool = True
    dry_mode_enabled: bool = False  # Режим "трезвости"
    pomodoro_duration: int = 25  # минут
    short_break_duration: int = 5  # минут
    long_break_duration: int = 15  # минут
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserSettings":
        return cls(**data)

@dataclass
class UserStats:
    """Расширенная статистика пользователя"""
    total_tasks: int = 0
    completed_tasks: int = 0
    current_streak: int = 0
    longest_streak: int = 0
    total_xp: int = 0
    level: int = 1
    last_activity: Optional[str] = None
    registration_date: str = field(default_factory=lambda: datetime.now().isoformat())
    total_session_time: int = 0  # в секундах
    preferred_time_of_day: str = "morning"  # morning, afternoon, evening
    tasks_completed_today: int = 0
    daily_xp_earned: int = 0
    weekly_goal: int = 7  # задач в неделю
    monthly_goal: int = 30  # задач в месяц
    dry_days: int = 0  # дни без алкоголя
    total_pomodoros: int = 0  # количество помодоро
    
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
    
    @property
    def level_progress(self) -> float:
        """Прогресс до следующего уровня (0-100%)"""
        current_level_xp = self.xp_for_level(self.level)
        next_level_xp = self.xp_for_level(self.level + 1)
        
        if self.total_xp >= next_level_xp:
            return 100.0
        
        level_xp_range = next_level_xp - current_level_xp
        current_progress = self.total_xp - current_level_xp
        
        return (current_progress / level_xp_range) * 100
    
    @staticmethod
    def xp_for_level(level: int) -> int:
        """Необходимый XP для достижения уровня"""
        if level <= 1:
            return 0
        return int(100 * (level - 1) * 1.5)
    
    def add_xp(self, xp: int) -> bool:
        """Добавить XP и проверить повышение уровня"""
        old_level = self.level
        self.total_xp += xp
        self.daily_xp_earned += xp
        
        # Проверяем повышение уровня
        while self.total_xp >= self.xp_for_level(self.level + 1):
            self.level += 1
        
        return self.level > old_level  # Возвращаем True если уровень повысился
    
    def get_level_title(self) -> str:
        """Получить название уровня"""
        titles = {
            1: "🌱 Новичок",
            2: "🌿 Начинающий", 
            3: "🌳 Ученик",
            4: "⚡ Активист",
            5: "💪 Энтузиаст",
            6: "🎯 Целеустремленный",
            7: "🔥 Мотивированный", 
            8: "⭐ Продвинутый",
            9: "💎 Эксперт",
            10: "🏆 Мастер",
            11: "👑 Гуру",
            12: "🌟 Легенда",
            13: "⚡ Супергерой",
            14: "🚀 Чемпион",
            15: "💫 Божество",
            16: "🌌 Вселенная"
        }
        return titles.get(min(self.level, 16), f"🌌 Уровень {self.level}")
    
    def to_dict(self) -> dict:
        return asdict(self)
    
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
    xp_reward: int = 50
    
    @property
    def is_earned(self) -> bool:
        return self.earned_at is not None
    
    @property
    def progress_percentage(self) -> float:
        return (self.progress / self.target) * 100 if self.target > 0 else 100

@dataclass
class User:
    """Модель пользователя с расширенным функционалом"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    settings: UserSettings = field(default_factory=UserSettings)
    stats: UserStats = field(default_factory=UserStats)
    tasks: Dict[str, Task] = field(default_factory=dict)
    achievements: List[str] = field(default_factory=list)
    friends: List[Friend] = field(default_factory=list)
    reminders: List[Reminder] = field(default_factory=list)
    notes: str = ""  # Личные заметки пользователя
    ai_chat_history: List[Dict] = field(default_factory=list)
    weekly_goals: Dict[str, int] = field(default_factory=dict)  # {"2025-W23": 7}
    
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
    
    @property
    def current_week_key(self) -> str:
        """Ключ текущей недели в формате YYYY-WXX"""
        today = date.today()
        year, week, _ = today.isocalendar()
        return f"{year}-W{week:02d}"
    
    def update_activity(self):
        """Обновить время последней активности"""
        self.stats.last_activity = datetime.now().isoformat()
    
    def add_friend(self, friend_user_id: int, username: Optional[str] = None, 
                   first_name: Optional[str] = None) -> bool:
        """Добавить друга"""
        if any(f.user_id == friend_user_id for f in self.friends):
            return False  # Уже в друзьях
        
        friend = Friend(
            user_id=friend_user_id,
            username=username,
            first_name=first_name
        )
        self.friends.append(friend)
        return True
    
    def remove_friend(self, friend_user_id: int) -> bool:
        """Удалить друга"""
        initial_count = len(self.friends)
        self.friends = [f for f in self.friends if f.user_id != friend_user_id]
        return len(self.friends) < initial_count
    
    def get_friend(self, friend_user_id: int) -> Optional[Friend]:
        """Получить друга по ID"""
        return next((f for f in self.friends if f.user_id == friend_user_id), None)
    
    def add_reminder(self, title: str, message: str, trigger_time: str, 
                     is_recurring: bool = False) -> str:
        """Добавить напоминание"""
        reminder = Reminder(
            reminder_id=str(uuid.uuid4()),
            user_id=self.user_id,
            title=title,
            message=message,
            trigger_time=trigger_time,
            is_recurring=is_recurring
        )
        self.reminders.append(reminder)
        return reminder.reminder_id
    
    def get_week_progress(self, week_key: Optional[str] = None) -> Dict[str, Any]:
        """Получить прогресс за неделю"""
        if not week_key:
            week_key = self.current_week_key
        
        # Подсчитываем выполненные задачи за неделю
        year, week = week_key.split('-W')
        year, week = int(year), int(week)
        
        # Получаем даты недели
        jan4 = date(year, 1, 4)
        week_start = jan4 + timedelta(days=7*(week-1) - jan4.weekday())
        week_end = week_start + timedelta(days=6)
        
        completed_this_week = 0
        for task in self.tasks.values():
            for completion in task.completions:
                if completion.completed:
                    comp_date = date.fromisoformat(completion.date)
                    if week_start <= comp_date <= week_end:
                        completed_this_week += 1
        
        goal = self.weekly_goals.get(week_key, self.stats.weekly_goal)
        
        return {
            "week_key": week_key,
            "completed": completed_this_week,
            "goal": goal,
            "progress_percentage": (completed_this_week / goal * 100) if goal > 0 else 0,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat()
        }
    
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
            "friends": [f.to_dict() for f in self.friends],
            "reminders": [r.to_dict() for r in self.reminders],
            "notes": self.notes,
            "ai_chat_history": self.ai_chat_history,
            "weekly_goals": self.weekly_goals
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Десериализация из словаря"""
        user = cls(
            user_id=data["user_id"],
            username=data.get("username"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            notes=data.get("notes", ""),
            ai_chat_history=data.get("ai_chat_history", []),
            weekly_goals=data.get("weekly_goals", {})
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
        
        # Восстанавливаем друзей
        if "friends" in data:
            user.friends = [Friend.from_dict(f) for f in data["friends"]]
        
        # Восстанавливаем напоминания  
        if "reminders" in data:
            user.reminders = [Reminder.from_dict(r) for r in data["reminders"]]
        
        return user

# ===== БАЗА ДАННЫХ =====

class DatabaseManager:
    """Менеджер файловой базы данных с улучшенной производительностью"""
    
    def __init__(self, data_file: str = "users_data.json"):
        self.data_file = BotConfig.DATA_DIR / data_file
        self.users_cache: Dict[int, User] = {}
        self.cache_lock = threading.RLock()
        self.last_save_time = time.time()
        self.pending_saves = set()
        
        BotConfig.ensure_directories()
        self._load_all_users()
        
        # Запускаем фоновое сохранение
        if SCHEDULER_AVAILABLE:
            self.scheduler = AsyncIOScheduler()
            self.scheduler.add_job(
                self._periodic_save,
                IntervalTrigger(minutes=5),
                id='periodic_save'
            )
            self.scheduler.start()
    
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
    
    async def _periodic_save(self):
        """Периодическое сохранение изменений"""
        if self.pending_saves:
            await self.save_all_users_async()
    
    def save_all_users(self) -> bool:
        """Синхронное сохранение всех пользователей в файл"""
        try:
            with self.cache_lock:
                # Создаем резервную копию перед сохранением
                if self.data_file.exists():
                    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    backup_path = BotConfig.BACKUP_DIR / backup_name
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
                self.last_save_time = time.time()
                self.pending_saves.clear()
                
                logger.info("💾 Данные сохранены")
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
            return False
    
    async def save_all_users_async(self) -> bool:
        """Асинхронное сохранение"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.save_all_users)
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        with self.cache_lock:
            return self.users_cache.get(user_id)
    
    def get_or_create_user(self, user_id: int, **kwargs) -> User:
        """Получить пользователя или создать нового"""
        with self.cache_lock:
            if user_id not in self.users_cache:
                user = User(
                    user_id=user_id,
                    username=kwargs.get('username'),
                    first_name=kwargs.get('first_name'),
                    last_name=kwargs.get('last_name')
                )
                self.users_cache[user_id] = user
                self.pending_saves.add(user_id)
                logger.info(f"👤 Создан новый пользователь: {user.display_name}")
            
            # Обновляем данные пользователя и активность
            user = self.users_cache[user_id]
            user.username = kwargs.get('username', user.username)
            user.first_name = kwargs.get('first_name', user.first_name)
            user.last_name = kwargs.get('last_name', user.last_name)
            user.update_activity()
            self.pending_saves.add(user_id)
            
            return user
    
    def save_user(self, user: User):
        """Отметить пользователя для сохранения"""
        with self.cache_lock:
            self.pending_saves.add(user.user_id)
    
    def get_all_users(self) -> List[User]:
        """Получить всех пользователей"""
        with self.cache_lock:
            return list(self.users_cache.values())
    
    def get_users_count(self) -> int:
        """Получить количество пользователей"""
        return len(self.users_cache)
    
    def cleanup_old_backups(self, keep_count: int = 10):
        """Удаление старых резервных копий"""
        try:
            backups = list(BotConfig.BACKUP_DIR.glob("backup_*.json"))
            if len(backups) > keep_count:
                backups.sort(key=lambda x: x.stat().st_mtime)
                for backup in backups[:-keep_count]:
                    backup.unlink()
                logger.info(f"🗑️ Удалено {len(backups) - keep_count} старых бэкапов")
        except Exception as e:
            logger.error(f"❌ Ошибка очистки бэкапов: {e}")
    
    def export_user_data(self, user_id: int, format: str = "json") -> Optional[bytes]:
        """Экспорт данных пользователя"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        try:
            if format.lower() == "json":
                data = user.to_dict()
                export_data = {
                    "export_info": {
                        "format": "json",
                        "version": "4.0",
                        "exported_at": datetime.now().isoformat(),
                        "user_id": user_id
                    },
                    "user_data": data
                }
                return json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8')
            
            elif format.lower() == "csv" and PANDAS_AVAILABLE:
                # Экспорт задач в CSV
                tasks_data = []
                for task in user.tasks.values():
                    for completion in task.completions:
                        tasks_data.append({
                            "task_id": task.task_id,
                            "title": task.title,
                            "category": task.category,
                            "priority": task.priority,
                            "date": completion.date,
                            "completed": completion.completed,
                            "time_spent": completion.time_spent,
                            "note": completion.note
                        })
                
                if tasks_data:
                    df = pd.DataFrame(tasks_data)
                    return df.to_csv(index=False).encode('utf-8')
                else:
                    return "task_id,title,category,priority,date,completed,time_spent,note\n".encode('utf-8')
            
        except Exception as e:
            logger.error(f"❌ Ошибка экспорта данных: {e}")
            return None
        
        return None

# ===== СИСТЕМА ДОСТИЖЕНИЙ =====

class AchievementSystem:
    """Расширенная система достижений"""
    
    ACHIEVEMENTS = {
        'first_task': {
            'title': 'Первые шаги',
            'description': 'Создайте свою первую задачу',
            'icon': '🎯',
            'xp_reward': 50,
            'condition': lambda user: len(user.tasks) >= 1
        },
        'streak_3': {
            'title': 'Начинающий',
            'description': 'Поддерживайте streak 3 дня',
            'icon': '🔥',
            'xp_reward': 100,
            'condition': lambda user: max([task.current_streak for task in user.tasks.values()] + [0]) >= 3
        },
        'streak_7': {
            'title': 'Неделя силы',
            'description': 'Поддерживайте streak 7 дней',
            'icon': '💪',
            'xp_reward': 200,
            'condition': lambda user: max([task.current_streak for task in user.tasks.values()] + [0]) >= 7
        },
        'streak_30': {
            'title': 'Мастер привычек',
            'description': 'Поддерживайте streak 30 дней',
            'icon': '💎',
            'xp_reward': 500,
            'condition': lambda user: max([task.current_streak for task in user.tasks.values()] + [0]) >= 30
        },
        'streak_100': {
            'title': 'Легенда',
            'description': 'Поддерживайте streak 100 дней',
            'icon': '👑',
            'xp_reward': 1000,
            'condition': lambda user: max([task.current_streak for task in user.tasks.values()] + [0]) >= 100
        },
        'tasks_10': {
            'title': 'Продуктивный',
            'description': 'Выполните 10 задач',
            'icon': '📈',
            'xp_reward': 100,
            'condition': lambda user: user.stats.completed_tasks >= 10
        },
        'tasks_50': {
            'title': 'Энтузиаст',
            'description': 'Выполните 50 задач',
            'icon': '🏆',
            'xp_reward': 250,
            'condition': lambda user: user.stats.completed_tasks >= 50
        },
        'tasks_100': {
            'title': 'Чемпион',
            'description': 'Выполните 100 задач',
            'icon': '🌟',
            'xp_reward': 500,
            'condition': lambda user: user.stats.completed_tasks >= 100
        },
        'tasks_500': {
            'title': 'Мастер продуктивности',
            'description': 'Выполните 500 задач',
            'icon': '⭐',
            'xp_reward': 1000,
            'condition': lambda user: user.stats.completed_tasks >= 500
        },
        'level_5': {
            'title': 'Растущий',
            'description': 'Достигните 5 уровня',
            'icon': '⬆️',
            'xp_reward': 200,
            'condition': lambda user: user.stats.level >= 5
        },
        'level_10': {
            'title': 'Опытный',
            'description': 'Достигните 10 уровня',
            'icon': '🚀',
            'xp_reward': 500,
            'condition': lambda user: user.stats.level >= 10
        },
        'social_butterfly': {
            'title': 'Общительный',
            'description': 'Добавьте 5 друзей',
            'icon': '👥',
            'xp_reward': 150,
            'condition': lambda user: len(user.friends) >= 5
        },
        'perfect_week': {
            'title': 'Идеальная неделя',
            'description': 'Выполните все задачи 7 дней подряд',
            'icon': '✨',
            'xp_reward': 300,
            'condition': lambda user: user._check_perfect_week()
        },
        'early_bird': {
            'title': 'Ранняя пташка',
            'description': 'Выполните 10 задач до 9 утра',
            'icon': '🌅',
            'xp_reward': 200,
            'condition': lambda user: user._check_early_completions()
        },
        'night_owl': {
            'title': 'Сова',
            'description': 'Выполните 10 задач после 22:00',
            'icon': '🦉',
            'xp_reward': 200,
            'condition': lambda user: user._check_late_completions()
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
                        
                        # Добавляем XP за достижение
                        xp_reward = achievement_data.get('xp_reward', 50)
                        level_up = user.stats.add_xp(xp_reward)
                        
                        logger.info(f"🏆 Пользователь {user.user_id} получил достижение: {achievement_id} (+{xp_reward} XP)")
                        
                        if level_up:
                            logger.info(f"🆙 Пользователь {user.user_id} повысил уровень до {user.stats.level}")
                            
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки достижения {achievement_id}: {e}")
        
        return new_achievements
    
    @classmethod
    def get_achievement_message(cls, achievement_id: str, user: User) -> str:
        """Получить сообщение о достижении"""
        if achievement_id not in cls.ACHIEVEMENTS:
            return "🏆 Новое достижение получено!"
        
        achievement = cls.ACHIEVEMENTS[achievement_id]
        xp_reward = achievement.get('xp_reward', 50)
        
        message = f"""🏆 **Новое достижение!**

{achievement['icon']} **{achievement['title']}**
{achievement['description']}

💫 +{xp_reward} XP
⭐ Уровень: {user.stats.level} ({user.stats.get_level_title()})
📊 Прогресс: {user.stats.level_progress:.1f}%"""
        
        return message
    
    @classmethod
    def get_achievements_list(cls, user: User) -> str:
        """Получить список всех достижений"""
        earned = len(user.achievements)
        total = len(cls.ACHIEVEMENTS)
        
        message = f"🏆 **Достижения ({earned}/{total})**\n\n"
        
        # Полученные достижения
        if user.achievements:
            message += "✅ **Получено:**\n"
            for achievement_id in user.achievements:
                if achievement_id in cls.ACHIEVEMENTS:
                    ach = cls.ACHIEVEMENTS[achievement_id]
                    message += f"{ach['icon']} {ach['title']}\n"
            message += "\n"
        
        # Доступные достижения
        available = []
        for achievement_id, ach in cls.ACHIEVEMENTS.items():
            if achievement_id not in user.achievements:
                available.append((achievement_id, ach))
        
        if available:
            message += "🎯 **Доступно:**\n"
            for achievement_id, ach in available[:5]:  # Показываем первые 5
                message += f"{ach['icon']} {ach['title']} - {ach['description']}\n"
            
            if len(available) > 5:
                message += f"... и еще {len(available) - 5}"
        
        return message

# Добавляем методы для проверки специальных условий
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

def _check_early_completions(self) -> bool:
    """Проверка выполнения задач рано утром"""
    early_count = 0
    for task in self.tasks.values():
        for completion in task.completions:
            if completion.completed:
                try:
                    timestamp = datetime.fromisoformat(completion.timestamp)
                    if timestamp.hour < 9:
                        early_count += 1
                except:
                    continue
    return early_count >= 10

def _check_late_completions(self) -> bool:
    """Проверка выполнения задач поздно вечером"""
    late_count = 0
    for task in self.tasks.values():
        for completion in task.completions:
            if completion.completed:
                try:
                    timestamp = datetime.fromisoformat(completion.timestamp)
                    if timestamp.hour >= 22:
                        late_count += 1
                except:
                    continue
    return late_count >= 10

# Добавляем методы к классу User
User._check_perfect_week = _check_perfect_week
User._check_early_completions = _check_early_completions
User._check_late_completions = _check_late_completions

# ===== AI СЕРВИСЫ =====

class AIService:
    """Сервис для работы с OpenAI API"""
    
    def __init__(self):
        self.client = None
        self.enabled = OPENAI_AVAILABLE and BotConfig.OPENAI_API_KEY
        
        # Проверяем, что API ключ не равен BOT_TOKEN
        if self.enabled and BotConfig.OPENAI_API_KEY == BotConfig.BOT_TOKEN:
            logger.warning("⚠️ OPENAI_API_KEY совпадает с BOT_TOKEN - AI функции отключены")
            self.enabled = False
        
        if self.enabled:
            try:
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(api_key=BotConfig.OPENAI_API_KEY)
                logger.info("🤖 AI сервис инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации AI: {e}")
                self.enabled = False
        else:
            if not BotConfig.OPENAI_API_KEY:
                logger.warning("⚠️ AI сервис отключен (нет OPENAI_API_KEY)")
            elif BotConfig.OPENAI_API_KEY == BotConfig.BOT_TOKEN:
                logger.warning("⚠️ AI сервис отключен (OPENAI_API_KEY = BOT_TOKEN)")
            else:
                logger.warning("⚠️ AI сервис отключен (OpenAI недоступен)")
    
    def classify_request(self, message: str, user: User) -> AIRequestType:
        """Классификация типа запроса пользователя"""
        message_lower = message.lower()
        
        # Мотивационные запросы
        motivation_keywords = [
            'мотива', 'поддержка', 'вдохнови', 'устал', 'лень', 'не хочу',
            'сил нет', 'помоги', 'motivation', 'inspire', 'support'
        ]
        
        # Коучинг по продуктивности
        coaching_keywords = [
            'план', 'цел', 'продуктивн', 'задач', 'организ', 'время',
            'планиров', 'productivity', 'goal', 'planning', 'time'
        ]
        
        # Психологическая поддержка
        psychology_keywords = [
            'стресс', 'тревог', 'депресс', 'грустно', 'одинок', 'страх',
            'психолог', 'emotion', 'stress', 'anxiety', 'sad'
        ]
        
        # Анализ прогресса
        analysis_keywords = [
            'прогресс', 'статистика', 'анализ', 'результат', 'достижен',
            'analysis', 'progress', 'stats', 'achievement'
        ]
        
        for keyword in motivation_keywords:
            if keyword in message_lower:
                return AIRequestType.MOTIVATION
        
        for keyword in coaching_keywords:
            if keyword in message_lower:
                return AIRequestType.COACHING
        
        for keyword in psychology_keywords:
            if keyword in message_lower:
                return AIRequestType.PSYCHOLOGY
        
        for keyword in analysis_keywords:
            if keyword in message_lower:
                return AIRequestType.ANALYSIS
        
        return AIRequestType.GENERAL
    
    async def generate_response(self, message: str, user: User, 
                              request_type: AIRequestType = None) -> str:
        """Генерация ответа с учетом контекста пользователя"""
        if not self.enabled:
            return self._get_fallback_response(message, user, request_type)
        
        try:
            if not request_type:
                request_type = self.classify_request(message, user)
            
            # Формируем контекст пользователя
            user_context = self._build_user_context(user)
            
            # Выбираем system prompt в зависимости от типа запроса
            system_prompt = self._get_system_prompt(request_type, user_context)
            
            # Формируем историю сообщений
            messages = [{"role": "system", "content": system_prompt}]
            
            # Добавляем последние сообщения из истории
            for msg in user.ai_chat_history[-5:]:  # Последние 5 сообщений
                messages.append(msg)
            
            messages.append({"role": "user", "content": message})
            
            # Отправляем запрос к OpenAI
            response = await self.client.chat.completions.create(
                model=BotConfig.OPENAI_MODEL,
                messages=messages,
                max_tokens=BotConfig.OPENAI_MAX_TOKENS,
                temperature=0.7,
                timeout=30
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Сохраняем в историю чата
            user.ai_chat_history.append({"role": "user", "content": message})
            user.ai_chat_history.append({"role": "assistant", "content": ai_response})
            
            # Ограничиваем историю
            if len(user.ai_chat_history) > 20:
                user.ai_chat_history = user.ai_chat_history[-20:]
            
            return ai_response
            
        except Exception as e:
            logger.error(f"❌ Ошибка AI запроса: {e}")
            return self._get_fallback_response(message, user, request_type)
    
    def _build_user_context(self, user: User) -> str:
        """Построение контекста пользователя"""
        completed_today = len(user.completed_tasks_today)
        active_tasks = len(user.active_tasks)
        
        max_streak = max([task.current_streak for task in user.active_tasks.values()] + [0])
        
        week_progress = user.get_week_progress()
        
        context = f"""Информация о пользователе:
- Имя: {user.display_name}
- Уровень: {user.stats.level} ({user.stats.get_level_title()})
- Общий XP: {user.stats.total_xp}
- Выполнено задач всего: {user.stats.completed_tasks}
- Активных задач: {active_tasks}
- Выполнено сегодня: {completed_today}
- Максимальный streak: {max_streak} дней
- Прогресс недели: {week_progress['completed']}/{week_progress['goal']} задач
- Дней с регистрации: {user.stats.days_since_registration}"""
        
        if user.tasks:
            context += "\n\nПримеры текущих задач:"
            for i, task in enumerate(list(user.active_tasks.values())[:3]):
                status = "✅" if task.is_completed_today() else "⭕"
                context += f"\n- {status} {task.title} (streak: {task.current_streak})"
        
        return context
    
    def _get_system_prompt(self, request_type: AIRequestType, user_context: str) -> str:
        """Получение system prompt в зависимости от типа запроса"""
        base_prompt = f"""Ты - AI-ассистент DailyCheck Bot, помогаешь пользователям с ежедневными задачами и привычками.

{user_context}

Отвечай на русском языке, будь дружелюбным и поддерживающим. Используй эмодзи для лучшего восприятия."""
        
        if request_type == AIRequestType.MOTIVATION:
            return base_prompt + """

Твоя роль - МОТИВАТОР:
- Вдохновляй пользователя на выполнение задач
- Подчеркивай уже достигнутые успехи
- Давай конкретные советы по преодолению лени
- Используй позитивный настрой
- Напоминай о долгосрочных целях"""
        
        elif request_type == AIRequestType.COACHING:
            return base_prompt + """

Твоя роль - КОУЧ ПО ПРОДУКТИВНОСТИ:
- Помогай планировать день и неделю
- Давай советы по организации времени
- Предлагай техники продуктивности (Pomodoro, GTD, etc.)
- Анализируй текущие задачи и предлагай оптимизацию
- Помогай ставить реалистичные цели"""
        
        elif request_type == AIRequestType.PSYCHOLOGY:
            return base_prompt + """

Твоя роль - ПСИХОЛОГИЧЕСКИЙ ПОДДЕРЖИВАЮЩИЙ ПОМОЩНИК:
- Проявляй эмпатию и понимание
- Помогай справляться со стрессом и тревогой
- Предлагай техники релаксации и mindfulness
- Поддерживай ментальное здоровье
- НЕ давай медицинских советов, направляй к специалистам при серьезных проблемах"""
        
        elif request_type == AIRequestType.ANALYSIS:
            return base_prompt + """

Твоя роль - АНАЛИТИК ПРОГРЕССА:
- Анализируй статистику и прогресс пользователя
- Выявляй паттерны в выполнении задач
- Предлагай способы улучшения результатов
- Указывай на сильные стороны и зоны роста
- Давай рекомендации на основе данных"""
        
        else:  # GENERAL
            return base_prompt + """

Отвечай как дружелюбный помощник:
- Помогай с вопросами о боте и его функциях
- Поддерживай общение о задачах и привычках
- Предлагай полезные советы по продуктивности
- Будь позитивным и мотивирующим"""
    
    def _get_fallback_response(self, message: str, user: User, 
                             request_type: AIRequestType = None) -> str:
        """Резервные ответы когда AI недоступен"""
        if not request_type:
            request_type = self.classify_request(message, user)
        
        completed_today = len(user.completed_tasks_today)
        active_tasks = len(user.active_tasks)
        max_streak = max([task.current_streak for task in user.active_tasks.values()] + [0])
        
        if request_type == AIRequestType.MOTIVATION:
            responses = [
                f"💪 {user.display_name}, ты уже выполнил {completed_today} задач сегодня! Это отличный результат!",
                f"🔥 Твой максимальный streak {max_streak} дней показывает, что ты способен на многое!",
                f"⭐ Уровень {user.stats.level} ({user.stats.get_level_title()}) - это результат твоей упорной работы!",
                f"🎯 У тебя есть {active_tasks} активных задач. Каждая выполненная - шаг к цели!"
            ]
        elif request_type == AIRequestType.COACHING:
            responses = [
                "📋 Попробуй технику Pomodoro: 25 минут работы, 5 минут отдыха. Это поможет сосредоточиться!",
                "🎯 Начни с самой важной задачи утром, когда энергии больше всего.",
                "📝 Планируй день с вечера - это экономит время и снижает стресс утром.",
                "⏰ Устанавливай конкретные временные рамки для каждой задачи."
            ]
        elif request_type == AIRequestType.PSYCHOLOGY:
            responses = [
                "🤗 Помни: прогресс важнее совершенства. Каждый шаг имеет значение.",
                "🌱 Стресс - это нормально. Важно найти здоровые способы с ним справляться.",
                "💙 Ты делаешь все возможное, и этого достаточно. Будь добрее к себе.",
                "🧘 Попробуй технику глубокого дыхания: вдох на 4 счета, задержка на 4, выдох на 6."
            ]
        elif request_type == AIRequestType.ANALYSIS:
            week_progress = user.get_week_progress()
            responses = [
                f"📊 За эту неделю ты выполнил {week_progress['completed']} из {week_progress['goal']} задач.",
                f"📈 Твой completion rate: {user.stats.completion_rate:.1f}% - продолжай в том же духе!",
                f"🏆 У тебя {len(user.achievements)} достижений из {len(AchievementSystem.ACHIEVEMENTS)} возможных.",
                f"⏱️ В среднем ты активен {user.stats.days_since_registration} дней - отличная привычка!"
            ]
        else:
            responses = [
                f"👋 Привет, {user.display_name}! Как дела с задачами?",
                "🤖 Я здесь, чтобы помочь тебе с организацией дня и мотивацией!",
                "✨ Используй /help чтобы узнать все мои возможности.",
                "🎯 Готов помочь с планированием и выполнением задач!"
            ]
        
        return random.choice(responses)
    
    async def suggest_tasks(self, user: User, category: str = None) -> List[str]:
        """Предложение задач на основе AI"""
        if not self.enabled:
            return self._get_fallback_task_suggestions(category)
        
        try:
            user_context = self._build_user_context(user)
            category_filter = f" в категории '{category}'" if category else ""
            
            prompt = f"""На основе информации о пользователе предложи 5 подходящих ежедневных задач{category_filter}.

{user_context}

Требования:
- Задачи должны быть конкретными и выполнимыми
- Учитывай текущий уровень пользователя
- Предлагай разнообразные задачи
- Каждая задача в одну строку
- Без нумерации и дополнительных символов"""
            
            response = await self.client.chat.completions.create(
                model=BotConfig.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.8
            )
            
            suggestions = response.choices[0].message.content.strip().split('\n')
            return [s.strip() for s in suggestions if s.strip()][:5]
            
        except Exception as e:
            logger.error(f"❌ Ошибка AI предложений задач: {e}")
            return self._get_fallback_task_suggestions(category)
    
    def _get_fallback_task_suggestions(self, category: str = None) -> List[str]:
        """Резервные предложения задач"""
        suggestions = {
            "health": [
                "Выпить 8 стаканов воды",
                "Сделать 10-минутную зарядку",
                "Пройти 10,000 шагов",
                "Съесть порцию овощей",
                "Спать 8 часов"
            ],
            "work": [
                "Проверить и ответить на важные письма",
                "Выполнить приоритетную рабочую задачу",
                "Провести планирование на следующий день",
                "Изучить новый профессиональный материал",
                "Организовать рабочее место"
            ],
            "learning": [
                "Прочитать 20 страниц книги",
                "Изучить новые слова иностранного языка",
                "Посмотреть образовательное видео",
                "Решить задачи по математике",
                "Написать краткий конспект"
            ],
            "personal": [
                "Провести время с семьей/друзьями",
                "Медитировать 10 минут",
                "Записать 3 вещи, за которые благодарен",
                "Убрать в одной комнате",
                "Послушать любимую музыку"
            ],
            "finance": [
                "Проверить банковские счета",
                "Записать все расходы за день",
                "Отложить деньги в копилку",
                "Изучить инвестиционную статью",
                "Проанализировать месячный бюджет"
            ]
        }
        
        if category and category in suggestions:
            return suggestions[category]
        
        # Возвращаем случайные задачи из разных категорий
        all_tasks = []
        for tasks in suggestions.values():
            all_tasks.extend(tasks)
        
        return random.sample(all_tasks, 5)

# ===== КЛАВИАТУРЫ И ИНТЕРФЕЙС =====

class ThemeManager:
    """Менеджер тем оформления"""
    
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
    
    @classmethod
    def get_theme(cls, theme_name: str) -> Dict[str, str]:
        """Получить тему по имени"""
        try:
            theme_enum = UserTheme(theme_name)
            return cls.THEMES[theme_enum]
        except (ValueError, KeyError):
            return cls.THEMES[UserTheme.CLASSIC]
    
    @classmethod
    def get_themes_keyboard(cls) -> InlineKeyboardMarkup:
        """Клавиатура выбора темы"""
        keyboard = []
        for theme_enum, theme_data in cls.THEMES.items():
            keyboard.append([
                InlineKeyboardButton(
                    theme_data["name"], 
                    callback_data=f"theme_{theme_enum.value}"
                )
            ])
        return InlineKeyboardMarkup(keyboard)

class KeyboardManager:
    """Менеджер клавиатур и интерфейса с поддержкой тем"""
    
    @staticmethod
    def get_main_keyboard() -> ReplyKeyboardMarkup:
        """Основная клавиатура"""
        keyboard = [
            [KeyboardButton("📝 Мои задачи"), KeyboardButton("➕ Добавить задачу")],
            [KeyboardButton("✅ Отметить выполнение"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("🏆 Достижения"), KeyboardButton("👥 Друзья")],
            [KeyboardButton("🤖 AI Чат"), KeyboardButton("⏰ Таймер")],
            [KeyboardButton("⚙️ Настройки"), KeyboardButton("ℹ️ Помощь")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    @staticmethod
    def get_tasks_inline_keyboard(tasks: Dict[str, Task], user: User) -> InlineKeyboardMarkup:
        """Инлайн клавиатура для списка задач с темой"""
        theme = ThemeManager.get_theme(user.settings.theme)
        keyboard = []
        
        for task_id, task in list(tasks.items())[:10]:  # Ограничиваем до 10 задач
            status_emoji = theme["task_completed"] if task.is_completed_today() else theme["task_pending"]
            streak_info = f" {theme['streak_icon']}{task.current_streak}" if task.current_streak > 0 else ""
            
            button_text = f"{status_emoji} {task.title[:20]}{streak_info}"
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"task_view_{task_id}")
            ])
        
        # Кнопки действий
        action_buttons = []
        if len(tasks) > 10:
            action_buttons.append(InlineKeyboardButton("📋 Больше", callback_data="tasks_more"))
        
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
                InlineKeyboardButton("⏰ С таймером", callback_data=f"complete_timer_{task_id}"),
                InlineKeyboardButton("📝 С заметкой", callback_data=f"complete_note_{task_id}")
            ],
            [
                InlineKeyboardButton("➕ Подзадача", callback_data=f"add_subtask_{task_id}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{task_id}")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data=f"task_stats_{task_id}"),
                InlineKeyboardButton("⏸️ Приостановить", callback_data=f"pause_{task_id}")
            ],
            [
                InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_{task_id}"),
                InlineKeyboardButton("⬅️ Назад", callback_data="tasks_refresh")
            ]
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_category_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура выбора категории"""
        keyboard = [
            [InlineKeyboardButton("💼 Работа", callback_data="category_work")],
            [InlineKeyboardButton("🏃 Здоровье", callback_data="category_health")],
            [InlineKeyboardButton("📚 Обучение", callback_data="category_learning")],
            [InlineKeyboardButton("👤 Личное", callback_data="category_personal")],
            [InlineKeyboardButton("💰 Финансы", callback_data="category_finance")]
        ]
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
    def get_completion_keyboard(active_tasks: Dict[str, Task], user: User) -> InlineKeyboardMarkup:
        """Клавиатура для отметки выполнения с темой"""
        theme = ThemeManager.get_theme(user.settings.theme)
        keyboard = []
        
        incomplete_tasks = {
            k: v for k, v in active_tasks.items() 
            if not v.is_completed_today()
        }
        
        for task_id, task in list(incomplete_tasks.items())[:8]:  # Ограничиваем до 8
            priority_emoji = {
                "high": theme["priority_high"], 
                "medium": theme["priority_medium"], 
                "low": theme["priority_low"]
            }.get(task.priority, theme["priority_medium"])
            
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
    def get_ai_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура для AI функций"""
        keyboard = [
            [
                InlineKeyboardButton("💪 Мотивация", callback_data="ai_motivation"),
                InlineKeyboardButton("🎯 Коучинг", callback_data="ai_coaching")
            ],
            [
                InlineKeyboardButton("🧠 Психолог", callback_data="ai_psychology"),
                InlineKeyboardButton("📊 Анализ", callback_data="ai_analysis")
            ],
            [
                InlineKeyboardButton("💡 Предложить задачи", callback_data="ai_suggest_tasks"),
                InlineKeyboardButton("🔄 Новый запрос", callback_data="ai_new_request")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_friends_keyboard(user: User) -> InlineKeyboardMarkup:
        """Клавиатура для управления друзьями"""
        keyboard = [
            [
                InlineKeyboardButton(f"👥 Мои друзья ({len(user.friends)})", callback_data="friends_list"),
                InlineKeyboardButton("➕ Добавить", callback_data="friends_add")
            ],
            [
                InlineKeyboardButton("🏆 Сравнить достижения", callback_data="friends_compare"),
                InlineKeyboardButton("📊 Лидерборд друзей", callback_data="friends_leaderboard")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_timer_keyboard() -> InlineKeyboardMarkup:
        """Клавиатура для таймеров"""
        keyboard = [
            [
                InlineKeyboardButton("🍅 Помодоро (25 мин)", callback_data="timer_pomodoro"),
                InlineKeyboardButton("☕ Короткий перерыв (5 мин)", callback_data="timer_short_break")
            ],
            [
                InlineKeyboardButton("🛀 Длинный перерыв (15 мин)", callback_data="timer_long_break"),
                InlineKeyboardButton("⏰ Свой таймер", callback_data="timer_custom")
            ],
            [
                InlineKeyboardButton("⏹️ Остановить таймер", callback_data="timer_stop")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

# ===== ФОРМАТИРОВАНИЕ И УТИЛИТЫ =====

class MessageFormatter:
    """Форматировщик сообщений с поддержкой тем"""
    
    @classmethod
    def format_task_info(cls, task: Task, user: User, detailed: bool = True) -> str:
        """Форматирование информации о задаче с темой"""
        theme = ThemeManager.get_theme(user.settings.theme)
        
        priority_emoji = {
            "high": theme["priority_high"],
            "medium": theme["priority_medium"], 
            "low": theme["priority_low"]
        }.get(task.priority, theme["priority_medium"])
        
        status_emoji = theme["task_completed"] if task.is_completed_today() else theme["task_pending"]
        
        # Заголовок
        info = f"{status_emoji} **{task.title}**\n"
        
        # Описание
        if task.description and detailed:
            info += f"📝 {task.description}\n"
        
        # Категория
        category_emojis = {
            "work": "💼", "health": "🏃", "learning": "📚", 
            "personal": "👤", "finance": "💰"
        }
        category_emoji = category_emojis.get(task.category, "📋")
        info += f"{category_emoji} Категория: {task.category}\n"
        
        # Статус выполнения на сегодня
        if task.is_completed_today():
            info += f"✅ Выполнено сегодня\n"
        else:
            info += f"⭕ Не выполнено сегодня\n"
        
        # Основная информация
        info += f"{priority_emoji} Приоритет: {task.priority}\n"
        info += f"{theme['streak_icon']} Streak: {task.current_streak} дней\n"
        
        # Подзадачи
        if task.subtasks:
            completed_subtasks = task.subtasks_completed_count
            total_subtasks = task.subtasks_total_count
            info += f"📋 Подзадачи: {completed_subtasks}/{total_subtasks}\n"
        
        # XP информация
        if user.settings.show_xp:
            info += f"{theme['xp_icon']} XP за выполнение: {task.xp_value}\n"
        
        if detailed:
            info += f"📈 Неделя: {task.completion_rate_week:.1f}%\n"
            info += f"📊 Месяц: {task.completion_rate_month:.1f}%\n"
            
            if task.estimated_time:
                info += f"⏱️ Время: ~{task.estimated_time} мин\n"
            
            if task.difficulty > 1:
                difficulty_stars = "⭐" * task.difficulty
                info += f"🎯 Сложность: {difficulty_stars}\n"
            
            if task.tags:
                info += f"🏷️ Теги: {', '.join(task.tags)}\n"
            
            # Дата создания
            try:
                created_date = datetime.fromisoformat(task.created_at).strftime('%d.%m.%Y')
                info += f"📅 Создана: {created_date}\n"
            except:
                info += f"📅 Создана: {task.created_at}\n"
        
        return info
    
    @classmethod
    def format_user_stats(cls, user: User, detailed: bool = False) -> str:
        """Форматирование статистики пользователя с темой"""
        theme = ThemeManager.get_theme(user.settings.theme)
        
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
        
        # Недельный прогресс
        week_progress = user.get_week_progress()
        
        # Формирование текста
        stats_text = f"""📊 **Статистика {user.display_name}**

{theme['level_icon']} **Уровень {user.stats.level}** - {user.stats.get_level_title()}
{theme['xp_icon']} XP: {user.stats.total_xp} ({user.stats.level_progress:.1f}% до след. уровня)

🎯 **Общее:**
• Всего задач: {total_tasks}
• Активных: {active_tasks}
• Выполнено всего: {user.stats.completed_tasks}
• Процент выполнения: {user.stats.completion_rate:.1f}%

📅 **За периоды:**
• Сегодня: {completed_today} задач
• За неделю: {completed_week} выполнений  
• За месяц: {completed_month} выполнений

{theme['streak_icon']} **Streak'и:**
• Максимальный текущий: {max_streak} дней
• Средний: {avg_streak:.1f} дней
• Личный рекорд: {user.stats.longest_streak} дней

📈 **Недельная цель:**
• Прогресс: {week_progress['completed']}/{week_progress['goal']} задач
• Выполнено: {week_progress['progress_percentage']:.1f}%"""

        if user.settings.dry_mode_enabled and user.stats.dry_days > 0:
            stats_text += f"\n\n🚭 **Режим трезвости:** {user.stats.dry_days} дней"

        if detailed:
            try:
                reg_date = datetime.fromisoformat(user.stats.registration_date).strftime('%d.%m.%Y')
            except:
                reg_date = "неизвестно"
            
            stats_text += f"""

👤 **Профиль:**
• Регистрация: {reg_date}
• Дней в системе: {user.stats.days_since_registration}
• Друзей: {len(user.friends)}
• Достижений: {len(user.achievements)}/{len(AchievementSystem.ACHIEVEMENTS)}

🏆 **Последние достижения:**"""
            
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
                'level': user.stats.level,
                'total_xp': user.stats.total_xp
            })
        
        if not user_data:
            return "🏆 **Таблица лидеров**\n\nПока нет данных для рейтинга."
        
        # Сортировка по уровню и XP
        user_data.sort(key=lambda x: (x['level'], x['total_xp']), reverse=True)
        
        leaderboard_text = "🏆 **Таблица лидеров**\n\n👑 *По уровням:*\n"
        
        for i, data in enumerate(user_data[:10], 1):
            user = data['user']
            is_current = "← Вы" if user.user_id == current_user_id else ""
            
            emoji = "👑" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            leaderboard_text += f"{emoji} {user.display_name} - Ур.{data['level']} ({data['total_xp']} XP) {is_current}\n"
        
        # Добавляем рейтинг по streak'ам
        user_data.sort(key=lambda x: x['max_streak'], reverse=True)
        
        leaderboard_text += f"\n{ThemeManager.get_theme('classic')['streak_icon']} *По streak'ам:*\n"
        
        for i, data in enumerate(user_data[:5], 1):
            user = data['user']
            is_current = "← Вы" if user.user_id == current_user_id else ""
            
            emoji = "🔥" if i == 1 else f"{i}."
            
            leaderboard_text += f"{emoji} {user.display_name} - {data['max_streak']} дней {is_current}\n"
        
        return leaderboard_text

# ===== HTTP СЕРВЕР ДЛЯ HEALTH CHECKS =====

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Обработчик health check запросов"""
    
    def __init__(self, *args, db_manager=None, **kwargs):
        self.db_manager = db_manager
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Обработка GET запросов"""
        if self.path == '/health':
            self.send_health_response()
        elif self.path == '/metrics':
            self.send_metrics_response()
        else:
            self.send_error(404, "Not Found")
    
    def send_health_response(self):
        """Отправка health check ответа"""
        try:
            health_data = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "4.0.0",
                "uptime": time.time() - getattr(self.server, 'start_time', time.time()),
                "users_count": self.db_manager.get_users_count() if self.db_manager else 0,
                "ai_enabled": BotConfig.AI_CHAT_ENABLED and OPENAI_AVAILABLE
            }
            
            if PSUTIL_AVAILABLE:
                process = psutil.Process()
                health_data.update({
                    "memory_usage": process.memory_info().rss / 1024 / 1024,  # MB
                    "cpu_percent": process.cpu_percent()
                })
            
            response = json.dumps(health_data, indent=2)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Health check failed: {str(e)}")
    
    def send_metrics_response(self):
        """Отправка метрик в формате Prometheus"""
        try:
            metrics = []
            
            if self.db_manager:
                users_count = self.db_manager.get_users_count()
                metrics.append(f"dailycheck_users_total {users_count}")
                
                # Подсчитываем метрики по пользователям
                total_tasks = 0
                total_completed = 0
                total_active = 0
                
                for user in self.db_manager.get_all_users():
                    total_tasks += len(user.tasks)
                    total_completed += user.stats.completed_tasks
                    total_active += len(user.active_tasks)
                
                metrics.extend([
                    f"dailycheck_tasks_total {total_tasks}",
                    f"dailycheck_tasks_completed_total {total_completed}",
                    f"dailycheck_tasks_active_total {total_active}"
                ])
            
            if PSUTIL_AVAILABLE:
                process = psutil.Process()
                metrics.extend([
                    f"dailycheck_memory_usage_bytes {process.memory_info().rss}",
                    f"dailycheck_cpu_usage_percent {process.cpu_percent()}"
                ])
            
            response = '\n'.join(metrics) + '\n'
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Metrics failed: {str(e)}")
    
    def log_message(self, format, *args):
        """Отключаем стандартное логирование HTTP сервера"""
        pass

def create_health_server(port: int, db_manager: DatabaseManager):
    """Создание HTTP сервера для health checks"""
    handler = lambda *args, **kwargs: HealthCheckHandler(*args, db_manager=db_manager, **kwargs)
    
    server = HTTPServer(('0.0.0.0', port), handler)
    server.start_time = time.time()
    
    return server

# ===== ОСНОВНОЙ КЛАСС БОТА =====

class DailyCheckBot:
    """Основной класс DailyCheck Bot v4.0 с полным функционалом"""
    
    def __init__(self):
        # Проверка обязательных параметров
        if not BotConfig.BOT_TOKEN:
            logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
            sys.exit(1)
        
        logger.info(f"✅ BOT_TOKEN: {BotConfig.BOT_TOKEN[:10]}...")
        logger.info(f"✅ OpenAI: {BotConfig.OPENAI_API_KEY[:10] if BotConfig.OPENAI_API_KEY else 'не настроен'}...")
        logger.info("✅ Telegram библиотеки импортированы")
        logger.info("🚀 Запуск DailyCheck Bot v4.0 - ПОЛНАЯ ВЕРСИЯ...")
        logger.info(f"Python: {sys.version}")
        logger.info(f"Платформа: {sys.platform}")
        logger.info(f"Порт: {BotConfig.PORT}")
        
        # Инициализация компонентов
        logger.info("📂 Загрузка данных пользователей...")
        self.db = DatabaseManager()
        
        # AI сервис
        self.ai_service = AIService()
        
        # HTTP сервер для health checks
        self.http_server = None
        
        # Telegram Application
        self.application = None
        
        # Флаг для graceful shutdown
        self.shutdown_event = asyncio.Event()
        
        # Активные таймеры пользователей
        self.active_timers: Dict[int, asyncio.Task] = {}
    
    async def setup_bot(self):
        """Настройка бота"""
        try:
            # Создаем Application
            self.application = (
                ApplicationBuilder()
                .token(BotConfig.BOT_TOKEN)
                .build()
            )
            
            # Запускаем HTTP сервер в отдельном потоке
            self._start_http_server()
            
            # Регистрируем обработчики
            await self._register_handlers()
            
            # Настраиваем команды бота
            await self._setup_bot_commands()
            
            logger.info("✅ Бот настроен успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка настройки бота: {e}")
            raise
    
    def _start_http_server(self):
        """Запуск HTTP сервера в отдельном потоке"""
        try:
            self.http_server = create_health_server(BotConfig.PORT, self.db)
            
            def run_server():
                logger.info(f"🌐 HTTP сервер запущен на порту {BotConfig.PORT}")
                self.http_server.serve_forever()
            
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска HTTP сервера: {e}")
    
    async def _setup_bot_commands(self):
        """Настройка команд бота в меню"""
        commands = [
            BotCommand("start", "🚀 Главное меню"),
            BotCommand("tasks", "📝 Мои задачи"),
            BotCommand("add", "➕ Добавить задачу"),
            BotCommand("stats", "📊 Статистика"),
            BotCommand("achievements", "🏆 Достижения"),
            BotCommand("friends", "👥 Друзья"),
            BotCommand("ai_chat", "🤖 AI Чат"),
            BotCommand("timer", "⏰ Таймер"),
            BotCommand("remind", "🔔 Напоминание"),
            BotCommand("theme", "🎨 Тема"),
            BotCommand("export", "📤 Экспорт данных"),
            BotCommand("settings", "⚙️ Настройки"),
            BotCommand("help", "ℹ️ Справка")
        ]
        
        try:
            await self.application.bot.set_my_commands(commands)
            logger.info("✅ Команды бота настроены")
        except Exception as e:
            logger.error(f"❌ Ошибка настройки команд: {e}")
    
    async def _register_handlers(self):
        """Регистрация всех обработчиков"""
        logger.info("📋 Регистрация обработчиков команд...")
        
        # Основные команды
        logger.debug("Регистрируем основные команды...")
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("tasks", self.tasks_command))
        self.application.add_handler(CommandHandler("add", self.add_task_start))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("achievements", self.achievements_command))
        self.application.add_handler(CommandHandler("friends", self.friends_command))
        self.application.add_handler(CommandHandler("export", self.export_command))
        self.application.add_handler(CommandHandler("settings", self.settings_command))
        
        # AI команды
        logger.debug("Регистрируем AI команды...")
        self.application.add_handler(CommandHandler("ai_chat", self.ai_chat_command))
        self.application.add_handler(CommandHandler("motivate", self.ai_motivate_command))
        self.application.add_handler(CommandHandler("ai_coach", self.ai_coach_command))
        self.application.add_handler(CommandHandler("psy", self.ai_psychology_command))
        self.application.add_handler(CommandHandler("suggest_tasks", self.ai_suggest_tasks_command))
        
        # Утилиты
        logger.debug("Регистрируем утилиты...")
        self.application.add_handler(CommandHandler("timer", self.timer_command))
        self.application.add_handler(CommandHandler("remind", self.remind_command))
        self.application.add_handler(CommandHandler("theme", self.theme_command))
        self.application.add_handler(CommandHandler("myid", self.myid_command))
        
        # Команды для друзей
        self.application.add_handler(CommandHandler("add_friend", self.add_friend_command))
        
        # Быстрые команды
        logger.debug("Регистрируем быстрые команды...")
        self.application.add_handler(CommandHandler("settasks", self.settasks_command))
        self.application.add_handler(CommandHandler("weekly_goals", self.weekly_goals_command))
        self.application.add_handler(CommandHandler("analytics", self.analytics_command))
        
        # Обработчики кнопок главного меню
        logger.debug("Регистрируем обработчики кнопок...")
        self.application.add_handler(MessageHandler(filters.Regex("^📝 Мои задачи$"), self.tasks_command))
        self.application.add_handler(MessageHandler(filters.Regex("^➕ Добавить задачу$"), self.add_task_start))
        self.application.add_handler(MessageHandler(filters.Regex("^✅ Отметить выполнение$"), self.completion_button_handler))
        self.application.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), self.stats_command))
        self.application.add_handler(MessageHandler(filters.Regex("^🏆 Достижения$"), self.achievements_command))
        self.application.add_handler(MessageHandler(filters.Regex("^👥 Друзья$"), self.friends_command))
        self.application.add_handler(MessageHandler(filters.Regex("^🤖 AI Чат$"), self.ai_chat_command))
        self.application.add_handler(MessageHandler(filters.Regex("^⏰ Таймер$"), self.timer_command))
        self.application.add_handler(MessageHandler(filters.Regex("^⚙️ Настройки$"), self.settings_command))
        self.application.add_handler(MessageHandler(filters.Regex("^ℹ️ Справка$"), self.help_command))
        
        # Создание задач через ConversationHandler (ВАЖНО: до AI чата!)
        logger.debug("Регистрируем ConversationHandler'ы...")
        self._register_task_creation_handlers()
        
        # Callback обработчики
        logger.debug("Регистрируем callback обработчики...")
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        
        # AI чат (ВАЖНО: в группе 2 - низкий приоритет!)
        logger.debug("Регистрируем AI чат обработчик...")
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            self.handle_ai_chat_message
        ), group=2)
        
        # Общий обработчик сообщений (последний - группа 3)
        logger.debug("Регистрируем общий обработчик...")
        self.application.add_handler(MessageHandler(filters.ALL, self.handle_unknown_message), group=3)
        
        # Обработчик ошибок
        logger.debug("Регистрируем обработчик ошибок...")
        self.application.add_error_handler(self.error_handler)
        
        total_handlers = sum(len(handlers) for handlers in self.application.handlers.values())
        logger.info(f"✅ ВСЕ {total_handlers} ОБРАБОТЧИКОВ зарегистрированы!")
        logger.info("📱 Найдите бота в Telegram и отправьте /start")
    
    # ===== СОСТОЯНИЯ ДЛЯ CONVERSATION HANDLERS =====
    TASK_TITLE, TASK_DESCRIPTION, TASK_CATEGORY, TASK_PRIORITY, TASK_DIFFICULTY, TASK_TAGS = range(6)
    FRIEND_ID, REMINDER_TIME, REMINDER_MESSAGE = range(100, 103)
    
    def _register_task_creation_handlers(self):
        """Регистрация ConversationHandler для создания задач"""
        task_creation_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex("^➕ Добавить задачу$"), self.add_task_start),
                CommandHandler("add", self.add_task_start)
            ],
            states={
                self.TASK_TITLE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                        self.add_task_title
                    )
                ],
                self.TASK_DESCRIPTION: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                        self.add_task_description
                    )
                ],
                self.TASK_CATEGORY: [
                    CallbackQueryHandler(self.add_task_category, pattern="^category_")
                ],
                self.TASK_PRIORITY: [
                    CallbackQueryHandler(self.add_task_priority, pattern="^priority_")
                ],
                self.TASK_DIFFICULTY: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                        self.add_task_difficulty
                    )
                ],
                self.TASK_TAGS: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                        self.add_task_tags
                    )
                ]
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_conversation),
                MessageHandler(filters.Regex("^❌ Отмена$"), self.cancel_conversation)
            ],
            name="task_creation",
            persistent=False,
            allow_reentry=True,
            per_message=False,
            per_chat=True,
            per_user=True
        )
        # Регистрируем в группе 0 (высший приоритет)
        self.application.add_handler(task_creation_handler, group=0)
        logger.info("✅ ConversationHandler для создания задач зарегистрирован (группа 0)")
        
        # Добавление друга
        add_friend_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex("👥 Добавление друга"), self.add_friend_start)
            ],
            states={
                self.FRIEND_ID: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                        self.add_friend_id
                    )
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)],
            name="add_friend",
            persistent=False,
            per_message=False,
            per_chat=True,
            per_user=True
        )
        self.application.add_handler(add_friend_handler, group=0)
        
        # Создание напоминания
        reminder_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex("🔔 Создание напоминания"), self.remind_message_start)
            ],
            states={
                self.REMINDER_MESSAGE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                        self.remind_message
                    )
                ],
                self.REMINDER_TIME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
                        self.remind_time
                    )
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel_conversation)],
            name="reminder",
            persistent=False,
            per_message=False,
            per_chat=True,
            per_user=True
        )
        self.application.add_handler(reminder_handler, group=0)
    
    # ===== ОСНОВНЫЕ КОМАНДЫ =====
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_telegram = update.effective_user
        user = self.db.get_or_create_user(
            user_id=user_telegram.id,
            username=user_telegram.username,
            first_name=user_telegram.first_name,
            last_name=user_telegram.last_name
        )
        
        # Проверяем достижения
        new_achievements = AchievementSystem.check_achievements(user)
        if new_achievements:
            self.db.save_user(user)
        
        # Сбрасываем счетчики на новый день
        self._reset_daily_stats(user)
        
        theme = ThemeManager.get_theme(user.settings.theme)
        
        welcome_text = f"""🎯 **Добро пожаловать в DailyCheck Bot v4.0!**

Привет, {user.display_name}! 

{theme['level_icon']} **Уровень {user.stats.level}** - {user.stats.get_level_title()}
{theme['xp_icon']} XP: {user.stats.total_xp}

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
• Активных задач: {len(user.active_tasks)}
• Выполнено всего: {user.stats.completed_tasks}
• Друзей: {len(user.friends)}
• Достижений: {len(user.achievements)}/{len(AchievementSystem.ACHIEVEMENTS)}

Выберите действие в меню ниже:"""
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=KeyboardManager.get_main_keyboard(),
            parse_mode='Markdown'
        )
        
        # Отправляем уведомления о новых достижениях
        for achievement_id in new_achievements:
            achievement_msg = AchievementSystem.get_achievement_message(achievement_id, user)
            await update.message.reply_text(achievement_msg, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        help_text = """📖 Справка по DailyCheck Bot v4.0

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
        
        await update.message.reply_text(help_text)
    
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
        theme = ThemeManager.get_theme(user.settings.theme)
        
        text = f"📝 **Ваши активные задачи ({len(active_tasks)}):**\n\n"
        text += f"📊 Прогресс сегодня: {completed_today}/{len(active_tasks)} ({completion_percentage:.0f}%)\n\n"
        
        # Показываем первые 5 задач в тексте
        for i, (task_id, task) in enumerate(list(active_tasks.items())[:5], 1):
            status_emoji = theme["task_completed"] if task.is_completed_today() else theme["task_pending"]
            priority_emoji = {
                "high": theme["priority_high"],
                "medium": theme["priority_medium"],
                "low": theme["priority_low"]
            }.get(task.priority, theme["priority_medium"])
            
            text += f"{i}. {status_emoji} {priority_emoji} {task.title}\n"
            text += f"   {theme['streak_icon']} Streak: {task.current_streak} | 📈 Неделя: {task.completion_rate_week:.0f}%\n\n"
        
        if len(active_tasks) > 5:
            text += f"... и еще {len(active_tasks) - 5} задач\n\n"
        
        text += "Выберите задачу для подробной информации:"
        
        await update.message.reply_text(
            text,
            reply_markup=KeyboardManager.get_tasks_inline_keyboard(active_tasks, user),
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
        
        keyboard = [
            [
                InlineKeyboardButton("📈 Аналитика", callback_data="analytics_detailed"),
                InlineKeyboardButton("📊 График", callback_data="analytics_chart")
            ],
            [
                InlineKeyboardButton("📋 Экспорт", callback_data="export_json"),
                InlineKeyboardButton("🔄 Обновить", callback_data="stats_refresh")
            ]
        ]
        
        await update.message.reply_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def achievements_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /achievements - показать достижения"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        # Проверяем новые достижения
        new_achievements = AchievementSystem.check_achievements(user)
        if new_achievements:
            self.db.save_user(user)
        
        achievements_text = AchievementSystem.get_achievements_list(user)
        
        await update.message.reply_text(achievements_text, parse_mode='Markdown')
        
        # Отправляем уведомления о новых достижениях
        for achievement_id in new_achievements:
            achievement_msg = AchievementSystem.get_achievement_message(achievement_id, user)
            await update.message.reply_text(achievement_msg, parse_mode='Markdown')
    
    async def friends_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /friends - управление друзьями"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        friends_text = f"""👥 **Друзья ({len(user.friends)}):**

🆔 **Ваш ID:** `{user.user_id}`
📋 Поделитесь этим ID с друзьями для добавления

💡 **Добавить друга:** /add_friend

"""
        
        if user.friends:
            friends_text += "👥 **Ваши друзья:**\n"
            for friend in user.friends:
                friend_name = friend.first_name or f"@{friend.username}" if friend.username else f"ID {friend.user_id}"
                friends_text += f"• {friend_name}\n"
        else:
            friends_text += "Пока нет друзей. Добавьте первого!"
        
        await update.message.reply_text(
            friends_text,
            reply_markup=KeyboardManager.get_friends_keyboard(user),
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
        
        # Отправляем JSON экспорт
        json_data = self.db.export_user_data(user.user_id, "json")
        if json_data:
            file_buffer = io.BytesIO(json_data)
            file_buffer.name = f"dailycheck_export_{user.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            caption = f"""📊 **Экспорт данных DailyCheck Bot v4.0**

👤 Пользователь: {user.display_name}
📅 Дата экспорта: {datetime.now().strftime('%d.%m.%Y %H:%M')}
📝 Задач: {len(user.tasks)}
🏆 Достижений: {len(user.achievements)}
⭐ Уровень: {user.stats.level}
💫 XP: {user.stats.total_xp}

Файл содержит всю информацию о ваших задачах, статистике и настройках."""
            
            await update.message.reply_document(
                document=file_buffer,
                caption=caption,
                filename=file_buffer.name
            )
        
        # Отправляем CSV экспорт если доступен pandas
        if PANDAS_AVAILABLE:
            csv_data = self.db.export_user_data(user.user_id, "csv")
            if csv_data:
                csv_buffer = io.BytesIO(csv_data)
                csv_buffer.name = f"dailycheck_tasks_{user.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                await update.message.reply_document(
                    document=csv_buffer,
                    caption="📊 **CSV данные ваших задач**",
                    filename=csv_buffer.name
                )
        
        logger.info(f"Экспорт данных для пользователя {user.user_id}")
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /settings - настройки пользователя"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        settings_text = f"""⚙️ **Настройки**

🌍 **Локализация:**
• Язык: {user.settings.language}
• Часовой пояс: {user.settings.timezone}

🎨 **Интерфейс:**
• Тема: {ThemeManager.get_theme(user.settings.theme)['name']}
• Показывать XP: {'✅' if user.settings.show_xp else '❌'}
• Показывать streak'и: {'✅' if user.settings.show_streaks else '❌'}

🔔 **Напоминания:**
• Включены: {'✅' if user.settings.reminder_enabled else '❌'}
• Время: {user.settings.daily_reminder_time}

📊 **Уведомления:**
• Еженедельная статистика: {'✅' if user.settings.weekly_stats else '❌'}
• Мотивационные сообщения: {'✅' if user.settings.motivational_messages else '❌'}
• Звук уведомлений: {'✅' if user.settings.notification_sound else '❌'}

🤖 **AI функции:**
• AI-чат включен: {'✅' if user.settings.ai_chat_enabled else '❌'}

🚭 **Специальные режимы:**
• Режим "трезвости": {'✅' if user.settings.dry_mode_enabled else '❌'}
• Дней без алкоголя: {user.stats.dry_days}

⏰ **Таймеры (Pomodoro):**
• Рабочее время: {user.settings.pomodoro_duration} мин
• Короткий перерыв: {user.settings.short_break_duration} мин  
• Длинный перерыв: {user.settings.long_break_duration} мин

📝 **Заметки:**
{user.notes[:200] + '...' if len(user.notes) > 200 else user.notes or 'Заметки не добавлены'}"""
        
        keyboard = [
            [
                InlineKeyboardButton("🎨 Тема", callback_data="settings_theme"),
                InlineKeyboardButton("🔔 Напоминания", callback_data="settings_reminders")
            ],
            [
                InlineKeyboardButton("🤖 AI настройки", callback_data="settings_ai"),
                InlineKeyboardButton("⏰ Таймеры", callback_data="settings_timers")
            ],
            [
                InlineKeyboardButton("🚭 Режим трезвости", callback_data="settings_dry_mode"),
                InlineKeyboardButton("📝 Заметки", callback_data="settings_notes")
            ],
            [
                InlineKeyboardButton("🔄 Обновить", callback_data="settings_refresh")
            ]
        ]
        
        await update.message.reply_text(
            settings_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ===== AI КОМАНДЫ =====
    
    async def ai_chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /ai_chat - включить/выключить AI чат"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        user.settings.ai_chat_enabled = not user.settings.ai_chat_enabled
        self.db.save_user(user)
        
        status = "включен" if user.settings.ai_chat_enabled else "выключен"
        
        if user.settings.ai_chat_enabled:
            message = f"""🤖 **AI-чат {status}!**

Теперь вы можете писать мне обычные сообщения, и я буду отвечать как умный ассистент:

💪 **Мотивация:** "Мотивируй меня", "Не хочу делать задачи"
🎯 **Коучинг:** "Как планировать день?", "Помоги с продуктивностью"  
🧠 **Психология:** "Устал от работы", "Чувствую стресс"
📊 **Анализ:** "Как мои дела?", "Проанализируй прогресс"

Попробуйте написать что-нибудь!"""
        else:
            message = f"🤖 **AI-чат {status}**\n\nТеперь бот будет отвечать только на команды."
        
        await update.message.reply_text(
            message,
            reply_markup=KeyboardManager.get_ai_keyboard() if user.settings.ai_chat_enabled else None,
            parse_mode='Markdown'
        )
    
    async def ai_motivate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /motivate - получить мотивацию"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        motivation_message = await self.ai_service.generate_response(
            "Мотивируй меня выполнять задачи и быть продуктивным",
            user,
            AIRequestType.MOTIVATION
        )
        
        await update.message.reply_text(
            f"💪 **Персональная мотивация:**\n\n{motivation_message}",
            parse_mode='Markdown'
        )
    
    async def ai_coach_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /ai_coach - персональный коуч"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        coaching_message = await self.ai_service.generate_response(
            "Дай советы по продуктивности и планированию дня на основе моих задач",
            user,
            AIRequestType.COACHING
        )
        
        await update.message.reply_text(
            f"🎯 **Персональный коуч:**\n\n{coaching_message}",
            parse_mode='Markdown'
        )
    
    async def ai_psychology_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /psy - психологическая поддержка"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        psychology_message = await self.ai_service.generate_response(
            "Окажи психологическую поддержку и помоги справиться со стрессом",
            user,
            AIRequestType.PSYCHOLOGY
        )
        
        await update.message.reply_text(
            f"🧠 **Психологическая поддержка:**\n\n{psychology_message}",
            parse_mode='Markdown'
        )
    
    async def ai_suggest_tasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /suggest_tasks - AI предложит задачи"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        suggested_tasks = await self.ai_service.suggest_tasks(user)
        
        suggestion_text = "💡 **AI предлагает следующие задачи:**\n\n"
        
        for i, task in enumerate(suggested_tasks, 1):
            suggestion_text += f"{i}. {task}\n"
        
        suggestion_text += "\nВыберите задачи для добавления:"
        
        keyboard = []
        for i, task in enumerate(suggested_tasks):
            keyboard.append([
                InlineKeyboardButton(f"➕ {task[:40]}", callback_data=f"add_suggested_{i}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Новые предложения", callback_data="ai_suggest_new"),
            InlineKeyboardButton("❌ Отмена", callback_data="ai_suggest_cancel")
        ])
        
        context.user_data['suggested_tasks'] = suggested_tasks
        
        await update.message.reply_text(
            suggestion_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ===== УТИЛИТАРНЫЕ КОМАНДЫ =====
    
    async def timer_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /timer - установить таймер"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        timer_text = f"""⏰ **Управление таймерами**

🍅 **Pomodoro техника:**
• Рабочее время: {user.settings.pomodoro_duration} мин
• Короткий перерыв: {user.settings.short_break_duration} мин
• Длинный перерыв: {user.settings.long_break_duration} мин

📊 **Статистика:**
• Всего помодоро: {user.stats.total_pomodoros}

Выберите тип таймера:"""
        
        # Проверяем активный таймер
        if user.user_id in self.active_timers:
            timer_text += "\n\n⏱️ **У вас есть активный таймер!**"
        
        await update.message.reply_text(
            timer_text,
            reply_markup=KeyboardManager.get_timer_keyboard(),
            parse_mode='Markdown'
        )
    
    async def theme_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /theme - сменить тему"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        current_theme = ThemeManager.get_theme(user.settings.theme)
        
        theme_text = f"""🎨 **Темы оформления**

📱 **Текущая тема:** {current_theme['name']}

Выберите новую тему для персонализации интерфейса:"""
        
        await update.message.reply_text(
            theme_text,
            reply_markup=ThemeManager.get_themes_keyboard(),
            parse_mode='Markdown'
        )
    
    async def myid_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /myid - узнать свой ID"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        id_text = f"""🆔 **Ваши данные:**

• ID: `{user_id}`
• Username: @{username if username else 'не указан'}

💡 Поделитесь своим ID с друзьями, чтобы они могли добавить вас через /add_friend"""
        
        await update.message.reply_text(id_text, parse_mode='Markdown')
    
    async def remind_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /remind - создать напоминание"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        if context.args:
            # Быстрое создание напоминания из аргументов
            # Формат: /remind 09:30 Выпить воду
            try:
                time_arg = context.args[0]
                message_arg = ' '.join(context.args[1:]) if len(context.args) > 1 else "Напоминание"
                
                # Проверяем формат времени
                time_parts = time_arg.split(':')
                if len(time_parts) == 2:
                    hour, minute = int(time_parts[0]), int(time_parts[1])
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        reminder_id = user.add_reminder(
                            title="Напоминание",
                            message=message_arg,
                            trigger_time=time_arg,
                            is_recurring=True
                        )
                        
                        self.db.save_user(user)
                        
                        await update.message.reply_text(
                            f"✅ **Напоминание создано!**\n\n🕐 Время: {time_arg}\n📝 Сообщение: {message_arg}\n\nВы будете получать это напоминание каждый день.",
                            reply_markup=KeyboardManager.get_main_keyboard()
                        )
                        return
            except (ValueError, IndexError):
                pass
        
        # Запускаем ConversationHandler для детального создания
        await update.message.reply_text(
            "🔔 **Создание напоминания**\n\n💡 **Быстрый формат:** `/remind 09:30 Выпить воду`\n\nИли введите текст напоминания:",
            parse_mode='Markdown'
        )
    
    async def add_friend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /add_friend - добавить друга"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        if context.args:
            # Быстрое добавление друга из аргументов
            try:
                friend_id = int(context.args[0])
                
                if friend_id == user.user_id:
                    await update.message.reply_text("❌ Нельзя добавить самого себя в друзья!")
                    return
                
                # Проверяем, существует ли пользователь
                friend = self.db.get_user(friend_id)
                if not friend:
                    await update.message.reply_text("❌ Пользователь с таким ID не найден!")
                    return
                
                # Добавляем друга
                if user.add_friend(friend_id, friend.username, friend.first_name):
                    self.db.save_user(user)
                    
                    friend_name = friend.display_name
                    await update.message.reply_text(
                        f"✅ **Друг добавлен!**\n\n👤 {friend_name} теперь в вашем списке друзей.",
                        reply_markup=KeyboardManager.get_main_keyboard()
                    )
                else:
                    await update.message.reply_text("❌ Этот пользователь уже в списке ваших друзей!")
                return
                    
            except (ValueError, IndexError):
                await update.message.reply_text("❌ Неверный формат ID! Используйте: `/add_friend 123456789`")
                return
        
        # Запускаем ConversationHandler для ввода ID
        await update.message.reply_text(
            "👥 **Добавление друга**\n\n💡 **Быстрый формат:** `/add_friend 123456789`\n\nИли введите ID пользователя:"
        )
    
    # ===== БЫСТРЫЕ КОМАНДЫ =====
    
    async def settasks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /settasks - быстро создать несколько задач"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        if context.args:
            # Создаем задачи из аргументов команды
            task_titles = ' '.join(context.args).split(',')
            created_count = 0
            
            for title in task_titles:
                title = title.strip()
                if len(title) >= 3:
                    task = Task(
                        task_id=str(uuid.uuid4()),
                        user_id=user.user_id,
                        title=title,
                        category="personal",
                        priority="medium"
                    )
                    user.tasks[task.task_id] = task
                    user.stats.total_tasks += 1
                    created_count += 1
            
            if created_count > 0:
                # Проверяем достижения
                new_achievements = AchievementSystem.check_achievements(user)
                self.db.save_user(user)
                
                success_text = f"✅ **Создано {created_count} задач!**\n\nИспользуйте /tasks для просмотра."
                
                await update.message.reply_text(success_text, parse_mode='Markdown')
                
                # Отправляем уведомления о достижениях
                for achievement_id in new_achievements:
                    achievement_msg = AchievementSystem.get_achievement_message(achievement_id, user)
                    await update.message.reply_text(achievement_msg, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Не удалось создать задачи. Проверьте формат.")
        else:
            help_text = """📝 **Быстрое создание задач**

**Формат:** `/settasks задача1, задача2, задача3`

**Пример:** 
`/settasks Выпить воду, Сделать зарядку, Прочитать книгу`

Задачи будут созданы с приоритетом "средний" в категории "личное"."""
            
            await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def weekly_goals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /weekly_goals - еженедельные цели"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        week_progress = user.get_week_progress()
        
        goals_text = f"""🎯 **Еженедельные цели**

📅 **Текущая неделя:**
• Выполнено: {week_progress['completed']} задач
• Цель: {week_progress['goal']} задач
• Прогресс: {week_progress['progress_percentage']:.1f}%

📊 **Статистика:**"""
        
        # Показываем прогресс последних 4 недель
        current_date = date.today()
        for i in range(4):
            week_date = current_date - timedelta(weeks=i)
            year, week_num, _ = week_date.isocalendar()
            week_key = f"{year}-W{week_num:02d}"
            
            if i == 0:
                week_data = week_progress
                goals_text += f"\n• {week_key} (текущая): {week_data['completed']}/{week_data['goal']}"
            else:
                week_data = user.get_week_progress(week_key)
                goals_text += f"\n• {week_key}: {week_data['completed']}/{week_data['goal']}"
        
        keyboard = [
            [
                InlineKeyboardButton("🎯 Изменить цель", callback_data="weekly_goal_change"),
                InlineKeyboardButton("📊 Детальная статистика", callback_data="weekly_goal_stats")
            ]
        ]
        
        await update.message.reply_text(
            goals_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def analytics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /analytics - продвинутая аналитика"""
        user = self.db.get_or_create_user(update.effective_user.id)
        
        if not user.tasks:
            await update.message.reply_text(
                "📊 **Аналитика недоступна**\n\nСоздайте задачи для получения аналитики.",
                parse_mode='Markdown'
            )
            return
        
        # Анализ по категориям
        category_stats = {}
        for task in user.tasks.values():
            if task.category not in category_stats:
                category_stats[task.category] = {'total': 0, 'completed': 0}
            
            category_stats[task.category]['total'] += 1
            if any(c.completed for c in task.completions):
                category_stats[task.category]['completed'] += 1
        
        # Анализ по времени выполнения
        completion_times = {}
        for task in user.tasks.values():
            for completion in task.completions:
                if completion.completed:
                    try:
                        hour = datetime.fromisoformat(completion.timestamp).hour
                        time_period = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
                        completion_times[time_period] = completion_times.get(time_period, 0) + 1
                    except:
                        continue
        
        analytics_text = f"""📊 **Продвинутая аналитика**

📈 **По категориям:**"""
        
        category_emojis = {
            "work": "💼", "health": "🏃", "learning": "📚",
            "personal": "👤", "finance": "💰"
        }
        
        for category, stats in category_stats.items():
            emoji = category_emojis.get(category, "📋")
            rate = (stats['completed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            analytics_text += f"\n• {emoji} {category}: {stats['completed']}/{stats['total']} ({rate:.1f}%)"
        
        analytics_text += f"\n\n🕐 **По времени выполнения:**"
        
        time_emojis = {"morning": "🌅", "afternoon": "☀️", "evening": "🌙"}
        for time_period, count in completion_times.items():
            emoji = time_emojis.get(time_period, "🕐")
            analytics_text += f"\n• {emoji} {time_period}: {count} задач"
        
        # Анализ streak'ов
        all_streaks = [task.current_streak for task in user.active_tasks.values()]
        if all_streaks:
            avg_streak = sum(all_streaks) / len(all_streaks)
            max_streak = max(all_streaks)
            analytics_text += f"\n\n🔥 **Streak анализ:**"
            analytics_text += f"\n• Средний streak: {avg_streak:.1f} дней"
            analytics_text += f"\n• Максимальный: {max_streak} дней"
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Экспорт аналитики", callback_data="analytics_export"),
                InlineKeyboardButton("🔄 Обновить", callback_data="analytics_refresh")
            ]
        ]
        
        await update.message.reply_text(
            analytics_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ===== CONVERSATION HANDLERS =====
    
    async def add_task_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания задачи"""
        logger.info(f"Пользователь {update.effective_user.id} начал создание задачи")
        
        await update.message.reply_text(
            "📝 **Создание новой задачи**\n\nВведите название задачи (максимум 100 символов):",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        return self.TASK_TITLE
    
    async def add_task_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение названия задачи"""
        title = update.message.text.strip()
        
        logger.info(f"Пользователь {update.effective_user.id} ввел название задачи: {title}")
        
        if len(title) > 100:
            await update.message.reply_text(
                "❌ **Название слишком длинное!**\n\nМаксимум 100 символов.\nПопробуйте еще раз:",
                parse_mode='Markdown'
            )
            return self.TASK_TITLE
        
        if len(title) < 3:
            await update.message.reply_text(
                "❌ **Название слишком короткое!**\n\nМинимум 3 символа.\nПопробуйте еще раз:",
                parse_mode='Markdown'
            )
            return self.TASK_TITLE
        
        context.user_data['task_title'] = title
        
        await update.message.reply_text(
            f"✅ **Название:** {title}\n\nТеперь введите описание задачи (максимум 500 символов) или отправьте 'пропустить':",
            parse_mode='Markdown'
        )
        return self.TASK_DESCRIPTION
    
    async def add_task_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение описания задачи"""
        description = update.message.text.strip()
        
        logger.info(f"Пользователь {update.effective_user.id} ввел описание: {description[:50]}...")
        
        if description.lower() in ['пропустить', 'skip', '-', 'нет']:
            description = None
        elif len(description) > 500:
            await update.message.reply_text(
                "❌ **Описание слишком длинное!**\n\nМаксимум 500 символов.\nПопробуйте еще раз (или 'пропустить'):",
                parse_mode='Markdown'
            )
            return self.TASK_DESCRIPTION
        
        context.user_data['task_description'] = description
        
        await update.message.reply_text(
            f"✅ **Описание:** {description or 'не указано'}\n\nВыберите категорию задачи:",
            reply_markup=KeyboardManager.get_category_keyboard(),
            parse_mode='Markdown'
        )
        return self.TASK_CATEGORY
    
    async def add_task_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение категории задачи"""
        query = update.callback_query
        await query.answer()
        
        category_map = {
            "category_work": "work",
            "category_health": "health", 
            "category_learning": "learning",
            "category_personal": "personal",
            "category_finance": "finance"
        }
        
        category = category_map.get(query.data, "personal")
        context.user_data['task_category'] = category
        
        category_names = {
            "work": "Работа", "health": "Здоровье", "learning": "Обучение",
            "personal": "Личное", "finance": "Финансы"
        }
        
        await query.edit_message_text(
            f"✅ **Категория:** {category_names[category]}\n\nВыберите приоритет задачи:",
            reply_markup=KeyboardManager.get_priority_keyboard()
        )
        return self.TASK_PRIORITY
    
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
            f"✅ **Приоритет:** {priority_names[priority]}\n\nВведите сложность задачи (1-5, где 1 - очень легко, 5 - очень сложно) или 'пропустить':"
        )
        return self.TASK_DIFFICULTY
    
    async def add_task_difficulty(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение сложности задачи"""
        difficulty_text = update.message.text.strip()
        
        if difficulty_text.lower() in ['пропустить', 'skip', '-', 'нет']:
            difficulty = 1
        else:
            try:
                difficulty = int(difficulty_text)
                if difficulty < 1 or difficulty > 5:
                    await update.message.reply_text(
                        "❌ **Неверная сложность!**\n\nВведите число от 1 до 5 (или 'пропустить'):"
                    )
                    return self.TASK_DIFFICULTY
            except ValueError:
                await update.message.reply_text(
                    "❌ **Неверный формат!**\n\nВведите число от 1 до 5 (или 'пропустить'):"
                )
                return self.TASK_DIFFICULTY
        
        context.user_data['task_difficulty'] = difficulty
        
        await update.message.reply_text(
            f"✅ **Сложность:** {difficulty}/5\n\nВведите теги через запятую (максимум 5 тегов) или 'пропустить':"
        )
        return self.TASK_TAGS
    
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
            category=context.user_data['task_category'],
            priority=context.user_data['task_priority'],
            difficulty=context.user_data['task_difficulty'],
            tags=tags
        )
        
        # Добавляем задачу пользователю
        user.tasks[task.task_id] = task
        user.stats.total_tasks += 1
        
        # Проверяем достижения
        new_achievements = AchievementSystem.check_achievements(user)
        
        # Сохраняем
        self.db.save_user(user)
        
        # Очищаем данные из контекста
        context.user_data.clear()
        
        success_text = f"🎉 **Задача создана!**\n\n{MessageFormatter.format_task_info(task, user)}"
        
        await update.message.reply_text(
            success_text,
            reply_markup=KeyboardManager.get_main_keyboard(),
            parse_mode='Markdown'
        )
        
        # Отправляем уведомления о новых достижениях
        for achievement_id in new_achievements:
            achievement_msg = AchievementSystem.get_achievement_message(achievement_id, user)
            await update.message.reply_text(achievement_msg, parse_mode='Markdown')
        
        logger.info(f"Пользователь {user.user_id} создал задачу: {task.title}")
        return ConversationHandler.END
    
    async def add_friend_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало добавления друга"""
        await update.message.reply_text(
            "👥 **Добавление друга**\n\nВведите ID пользователя, которого хотите добавить в друзья:"
        )
        return self.FRIEND_ID
    
    async def add_friend_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ID друга"""
        try:
            friend_id = int(update.message.text.strip())
            user = self.db.get_or_create_user(update.effective_user.id)
            
            if friend_id == user.user_id:
                await update.message.reply_text("❌ Нельзя добавить самого себя в друзья!")
                return ConversationHandler.END
            
            # Проверяем, существует ли пользователь
            friend = self.db.get_user(friend_id)
            if not friend:
                await update.message.reply_text("❌ Пользователь с таким ID не найден!")
                return ConversationHandler.END
            
            # Добавляем друга
            if user.add_friend(friend_id, friend.username, friend.first_name):
                self.db.save_user(user)
                
                friend_name = friend.display_name
                await update.message.reply_text(
                    f"✅ **Друг добавлен!**\n\n👤 {friend_name} теперь в вашем списке друзей.",
                    reply_markup=KeyboardManager.get_main_keyboard()
                )
            else:
                await update.message.reply_text("❌ Этот пользователь уже в списке ваших друзей!")
            
        except ValueError:
            await update.message.reply_text("❌ Неверный формат ID! Введите числовой ID.")
            return self.FRIEND_ID
        
        return ConversationHandler.END
    
    async def remind_message_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания напоминания через ConversationHandler"""
        await update.message.reply_text(
            "🔔 **Создание напоминания**\n\nВведите текст напоминания:"
        )
        return self.REMINDER_MESSAGE
    
    async def remind_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение текста напоминания"""
        message = update.message.text.strip()
        context.user_data['reminder_message'] = message
        
        await update.message.reply_text(
            f"✅ **Сообщение:** {message}\n\nВведите время напоминания в формате ЧЧ:ММ (например: 09:30):"
        )
        return self.REMINDER_TIME
    
    async def remind_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение времени напоминания"""
        time_text = update.message.text.strip()
        
        try:
            # Проверяем формат времени
            time_parts = time_text.split(':')
            if len(time_parts) != 2:
                raise ValueError
            
            hour, minute = int(time_parts[0]), int(time_parts[1])
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError
            
            user = self.db.get_or_create_user(update.effective_user.id)
            
            reminder_message = context.user_data['reminder_message']
            
            reminder_id = user.add_reminder(
                title="Напоминание",
                message=reminder_message,
                trigger_time=time_text,
                is_recurring=True
            )
            
            self.db.save_user(user)
            context.user_data.clear()
            
            await update.message.reply_text(
                f"✅ **Напоминание создано!**\n\n🕐 Время: {time_text}\n📝 Сообщение: {reminder_message}\n\nВы будете получать это напоминание каждый день.",
                reply_markup=KeyboardManager.get_main_keyboard()
            )
            
        except ValueError:
            await update.message.reply_text(
                "❌ **Неверный формат времени!**\n\nВведите время в формате ЧЧ:ММ (например: 09:30):"
            )
            return self.REMINDER_TIME
        
        return ConversationHandler.END
    
    async def add_friend_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало добавления друга через ConversationHandler"""
        await update.message.reply_text(
            "👥 **Добавление друга**\n\nВведите ID пользователя, которого хотите добавить в друзья:"
        )
        return self.FRIEND_ID
    
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена диалога"""
        logger.info(f"Пользователь {update.effective_user.id} отменил диалог")
        context.user_data.clear()
        
        await update.message.reply_text(
            "❌ **Операция отменена.**",
            reply_markup=KeyboardManager.get_main_keyboard()
        )
        return ConversationHandler.END
    
    # ===== ОБРАБОТЧИКИ CALLBACK ЗАПРОСОВ =====
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главный обработчик callback запросов"""
        query = update.callback_query
        await query.answer()
        
        user = self.db.get_or_create_user(update.effective_user.id)
        data = query.data
        
        try:
            # Задачи
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
            elif data.startswith("confirm_delete_"):
                await self._handle_task_delete_confirm(query, user, data)
            elif data.startswith("task_stats_"):
                await self._handle_task_stats(query, user, data)
            elif data.startswith("add_subtask_"):
                await self._handle_add_subtask(query, user, data)
            elif data == "tasks_refresh":
                await self._handle_tasks_refresh(query, user)
            elif data == "tasks_more":
                await self._handle_tasks_more(query, user)
                
            # AI функции
            elif data.startswith("ai_"):
                await self._handle_ai_callback(query, user, data)
                
            # Темы
            elif data.startswith("theme_"):
                await self._handle_theme_change(query, user, data)
                
            # Таймеры
            elif data.startswith("timer_"):
                await self._handle_timer_callback(query, user, data)
                
            # Друзья
            elif data.startswith("friends_"):
                await self._handle_friends_callback(query, user, data)
                
            # Настройки
            elif data.startswith("settings_"):
                await self._handle_settings_callback(query, user, data)
                
            # Общие действия
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
        task_info = MessageFormatter.format_task_info(task, user, detailed=True)
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
            user.stats.tasks_completed_today += 1
            
            # Добавляем XP
            xp_earned = task.xp_value
            level_up = user.stats.add_xp(xp_earned)
            
            # Обновляем максимальный streak пользователя
            if task.current_streak > user.stats.longest_streak:
                user.stats.longest_streak = task.current_streak
            
            # Проверяем достижения
            new_achievements = AchievementSystem.check_achievements(user)
            
            self.db.save_user(user)
            
            theme = ThemeManager.get_theme(user.settings.theme)
            streak_text = f"{theme['streak_icon']} Streak: {task.current_streak} дней!"
            
            if task.current_streak > 1 and task.current_streak == user.stats.longest_streak:
                streak_text += " 🏆 Новый личный рекорд!"
            
            xp_text = f"\n{theme['xp_icon']} +{xp_earned} XP"
            if level_up:
                xp_text += f" | 🆙 Уровень {user.stats.level}!"
            
            motivational_messages = [
                "Отличная работа! 💪",
                "Так держать! 🎯", 
                "Вы на правильном пути! 🌟",
                "Каждый день делает вас сильнее! 💪",
                "Продолжайте в том же духе! 🔥"
            ]
            
            response_text = f"""🎉 **Задача выполнена!**

✅ {task.title}
{streak_text}{xp_text}

{random.choice(motivational_messages)}"""
            
            await query.edit_message_text(response_text, parse_mode='Markdown')
            
            # Отправляем уведомления о новых достижениях
            for achievement_id in new_achievements:
                achievement_msg = AchievementSystem.get_achievement_message(achievement_id, user)
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
            user.stats.tasks_completed_today = max(0, user.stats.tasks_completed_today - 1)
            
            # Отнимаем XP
            xp_lost = task.xp_value
            user.stats.total_xp = max(0, user.stats.total_xp - xp_lost)
            user.stats.daily_xp_earned = max(0, user.stats.daily_xp_earned - xp_lost)
            
            self.db.save_user(user)
            
            await query.edit_message_text(
                f"❌ **Выполнение отменено**\n\n⭕ {task.title}\n\n-{xp_lost} XP\n\nВы можете выполнить эту задачу позже."
            )
            
            logger.info(f"Пользователь {user.user_id} отменил выполнение задачи: {task.title}")
        else:
            await query.edit_message_text("❌ Ошибка при отмене выполнения.")
    
    async def _handle_task_delete_confirm(self, query, user: User, data: str):
        """Подтверждение удаления задачи"""
        task_id = data.replace("confirm_delete_", "")
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        task_title = task.title
        
        # Удаляем задачу
        del user.tasks[task_id]
        user.stats.total_tasks = max(0, user.stats.total_tasks - 1)
        
        self.db.save_user(user)
        
        await query.edit_message_text(
            f"🗑️ **Задача удалена**\n\n{task_title}\n\nВсе данные о выполнении были удалены."
        )
        
        logger.info(f"Пользователь {user.user_id} удалил задачу: {task_title}")
    
    async def _handle_task_delete(self, query, user: User, data: str):
        """Удаление задачи с подтверждением"""
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
    
    async def _handle_task_pause(self, query, user: User, data: str):
        """Приостановка задачи"""
        task_id = data.replace("pause_", "")
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        task.status = "paused"
        self.db.save_user(user)
        
        await query.edit_message_text(
            f"⏸️ **Задача приостановлена**\n\n{task.title}\n\nВы можете активировать её позже через настройки."
        )
        
        logger.info(f"Пользователь {user.user_id} приостановил задачу: {task.title}")
    
    async def _handle_add_subtask(self, query, user: User, data: str):
        """Добавление подзадачи"""
        task_id = data.replace("add_subtask_", "")
        
        if task_id not in user.tasks:
            await query.edit_message_text("❌ Задача не найдена!")
            return
        
        task = user.tasks[task_id]
        
        # Простое добавление подзадачи (в реальной реализации можно через ConversationHandler)
        subtask_title = f"Подзадача {len(task.subtasks) + 1}"
        subtask_id = task.add_subtask(subtask_title)
        
        self.db.save_user(user)
        
        await query.edit_message_text(
            f"✅ **Подзадача добавлена!**\n\n📋 {task.title}\n➕ {subtask_title}\n\nВсего подзадач: {len(task.subtasks)}"
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
        
        theme = ThemeManager.get_theme(user.settings.theme)
        
        stats_text = f"""📊 **Статистика задачи**

📝 {task.title}

🎯 **Общая статистика:**
• Всего выполнений: {total_completions}
• Дней с создания: {total_days}
• Общий процент: {overall_rate:.1f}%

{theme['streak_icon']} **Streak информация:**
• Текущий streak: {task.current_streak} дней
• Статус: {'✅ Выполнено сегодня' if task.is_completed_today() else '⭕ Не выполнено сегодня'}

📈 **По периодам:**
• За неделю: {task.completion_rate_week:.1f}%
• За месяц: {task.completion_rate_month:.1f}%
• За 30 дней: {len(recent_completions)} выполнений

📅 **Создана:** {datetime.fromisoformat(task.created_at).strftime('%d.%m.%Y')}

{theme['xp_icon']} **XP за выполнение:** {task.xp_value}"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад к задаче", callback_data=f"task_view_{task_id}")]
        ]
        
        await query.edit_message_text(
            stats_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
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
        
        theme = ThemeManager.get_theme(user.settings.theme)
        
        if active_tasks:
            text += f"⭕ **Активные ({len(active_tasks)}):**\n"
            for task in active_tasks[:10]:
                status_emoji = theme["task_completed"] if task.is_completed_today() else theme["task_pending"]
                text += f"• {status_emoji} {task.title} ({theme['streak_icon']}{task.current_streak})\n"
            
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
    
    async def _handle_friends_callback(self, query, user: User, data: str):
        """Обработка действий с друзьями"""
        if data == "friends_list":
            if not user.friends:
                await query.edit_message_text("👥 У вас пока нет друзей!\n\nДобавьте первого командой /add_friend")
                return
            
            friends_text = f"👥 **Ваши друзья ({len(user.friends)}):**\n\n"
            
            for friend in user.friends:
                friend_user = self.db.get_user(friend.user_id)
                if friend_user:
                    friends_text += f"• {friend_user.display_name} (Ур.{friend_user.stats.level})\n"
                else:
                    friend_name = friend.first_name or f"@{friend.username}" if friend.username else f"ID {friend.user_id}"
                    friends_text += f"• {friend_name}\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад", callback_data="friends_main")]
            ]
            
            await query.edit_message_text(
                friends_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "friends_compare":
            if not user.friends:
                await query.edit_message_text("👥 Добавьте друзей для сравнения достижений!")
                return
            
            compare_text = f"🏆 **Сравнение достижений**\n\n**Вы:** {len(user.achievements)} достижений\n\n"
            
            for friend in user.friends[:5]:  # Первые 5 друзей
                friend_user = self.db.get_user(friend.user_id)
                if friend_user:
                    compare_text += f"• {friend_user.display_name}: {len(friend_user.achievements)} достижений\n"
            
            await query.edit_message_text(compare_text, parse_mode='Markdown')
        
        elif data == "friends_leaderboard":
            friends_users = []
            for friend in user.friends:
                friend_user = self.db.get_user(friend.user_id)
                if friend_user:
                    friends_users.append(friend_user)
            
            if not friends_users:
                await query.edit_message_text("👥 Нет данных о друзьях для составления рейтинга.")
                return
            
            # Добавляем себя в список
            friends_users.append(user)
            
            leaderboard_text = MessageFormatter.format_leaderboard(friends_users, user.user_id)
            
            await query.edit_message_text(leaderboard_text, parse_mode='Markdown')
    
    async def _handle_settings_callback(self, query, user: User, data: str):
        """Обработка настроек"""
        if data == "settings_theme":
            current_theme = ThemeManager.get_theme(user.settings.theme)
            
            theme_text = f"""🎨 **Смена темы**

📱 **Текущая тема:** {current_theme['name']}

Выберите новую тему:"""
            
            await query.edit_message_text(
                theme_text,
                reply_markup=ThemeManager.get_themes_keyboard(),
                parse_mode='Markdown'
            )
        
        elif data == "settings_ai":
            ai_text = f"""🤖 **AI настройки**

• AI-чат: {'✅ Включен' if user.settings.ai_chat_enabled else '❌ Выключен'}

AI-чат позволяет общаться с ботом как с умным ассистентом. Бот будет понимать ваши сообщения и отвечать персональными советами."""
            
            keyboard = [
                [InlineKeyboardButton(
                    "❌ Выключить AI" if user.settings.ai_chat_enabled else "✅ Включить AI",
                    callback_data="toggle_ai_chat"
                )],
                [InlineKeyboardButton("⬅️ Назад", callback_data="settings_refresh")]
            ]
            
            await query.edit_message_text(
                ai_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "settings_dry_mode":
            dry_text = f"""🚭 **Режим "трезвости"**

• Статус: {'✅ Включен' if user.settings.dry_mode_enabled else '❌ Выключен'}
• Дней без алкоголя: {user.stats.dry_days}

Этот режим помогает отслеживать дни без употребления алкоголя."""
            
            keyboard = [
                [InlineKeyboardButton(
                    "❌ Выключить режим" if user.settings.dry_mode_enabled else "✅ Включить режим",
                    callback_data="toggle_dry_mode"
                )],
                [InlineKeyboardButton("🔄 Сбросить счетчик", callback_data="reset_dry_counter")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="settings_refresh")]
            ]
            
            await query.edit_message_text(
                dry_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "toggle_ai_chat":
            user.settings.ai_chat_enabled = not user.settings.ai_chat_enabled
            self.db.save_user(user)
            
            status = "включен" if user.settings.ai_chat_enabled else "выключен"
            await query.edit_message_text(f"🤖 AI-чат {status}!")
        
        elif data == "toggle_dry_mode":
            user.settings.dry_mode_enabled = not user.settings.dry_mode_enabled
            if user.settings.dry_mode_enabled and user.stats.dry_days == 0:
                user.stats.dry_days = 1  # Начинаем с первого дня
            self.db.save_user(user)
            
            status = "включен" if user.settings.dry_mode_enabled else "выключен"
            await query.edit_message_text(f"🚭 Режим трезвости {status}!")
        
        elif data == "reset_dry_counter":
            user.stats.dry_days = 0
            self.db.save_user(user)
            await query.edit_message_text("🔄 Счетчик дней трезвости сброшен.")
        
        elif data == "settings_refresh":
            # Обновляем настройки
            await self.settings_command(
                type('Update', (), {'effective_user': type('User', (), {'id': user.user_id})()})(),
                None
            )
        
        # Сохраняем изменения
        self.db.save_user(user)
    
    async def _handle_tasks_refresh(self, query, user: User):
        """Обновление списка задач"""
        active_tasks = user.active_tasks
        
        if not active_tasks:
            await query.edit_message_text("📝 У вас нет активных задач!")
            return
        
        completed_today = len(user.completed_tasks_today)
        completion_percentage = (completed_today / len(active_tasks)) * 100
        theme = ThemeManager.get_theme(user.settings.theme)
        
        text = f"📝 **Ваши активные задачи ({len(active_tasks)}):**\n\n"
        text += f"📊 Прогресс сегодня: {completed_today}/{len(active_tasks)} ({completion_percentage:.0f}%)\n\n"
        
        # Краткий список
        for i, (task_id, task) in enumerate(list(active_tasks.items())[:5], 1):
            status_emoji = theme["task_completed"] if task.is_completed_today() else theme["task_pending"]
            priority_emoji = {
                "high": theme["priority_high"],
                "medium": theme["priority_medium"], 
                "low": theme["priority_low"]
            }.get(task.priority, theme["priority_medium"])
            
            text += f"{i}. {status_emoji} {priority_emoji} {task.title}\n"
            text += f"   {theme['streak_icon']} Streak: {task.current_streak} | 📈 Неделя: {task.completion_rate_week:.0f}%\n\n"
        
        if len(active_tasks) > 5:
            text += f"... и еще {len(active_tasks) - 5} задач\n\n"
        
        text += "Выберите задачу для подробной информации:"
        
        await query.edit_message_text(
            text,
            reply_markup=KeyboardManager.get_tasks_inline_keyboard(active_tasks, user),
            parse_mode='Markdown'
        )
        """Обновление списка задач"""
        active_tasks = user.active_tasks
        
        if not active_tasks:
            await query.edit_message_text("📝 У вас нет активных задач!")
            return
        
        completed_today = len(user.completed_tasks_today)
        completion_percentage = (completed_today / len(active_tasks)) * 100
        theme = ThemeManager.get_theme(user.settings.theme)
        
        text = f"📝 **Ваши активные задачи ({len(active_tasks)}):**\n\n"
        text += f"📊 Прогресс сегодня: {completed_today}/{len(active_tasks)} ({completion_percentage:.0f}%)\n\n"
        
        # Краткий список
        for i, (task_id, task) in enumerate(list(active_tasks.items())[:5], 1):
            status_emoji = theme["task_completed"] if task.is_completed_today() else theme["task_pending"]
            priority_emoji = {
                "high": theme["priority_high"],
                "medium": theme["priority_medium"], 
                "low": theme["priority_low"]
            }.get(task.priority, theme["priority_medium"])
            
            text += f"{i}. {status_emoji} {priority_emoji} {task.title}\n"
            text += f"   {theme['streak_icon']} Streak: {task.current_streak} | 📈 Неделя: {task.completion_rate_week:.0f}%\n\n"
        
        if len(active_tasks) > 5:
            text += f"... и еще {len(active_tasks) - 5} задач\n\n"
        
        text += "Выберите задачу для подробной информации:"
        
        await query.edit_message_text(
            text,
            reply_markup=KeyboardManager.get_tasks_inline_keyboard(active_tasks, user),
            parse_mode='Markdown'
        )
    
    # ===== AI ОБРАБОТЧИКИ =====
    
    async def handle_ai_chat_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщений в AI чате"""
        if not update.message or not update.message.text:
            return
        
        # КРИТИЧНО: Проверяем, не находится ли пользователь в диалоге
        user_id = update.effective_user.id
        
        # Проверяем активные ConversationHandler'ы
        if context.user_data:
            logger.debug(f"AI-чат: Пропускаем для пользователя {user_id} - активный диалог. Context: {context.user_data.keys()}")
            return
        
        # Дополнительная проверка через application handlers
        for handler_group in self.application.handlers.values():
            for handler in handler_group:
                if isinstance(handler, ConversationHandler):
                    # Проверяем, есть ли пользователь в состоянии диалога
                    conversation_key = (user_id, user_id)  # (chat_id, user_id)
                    if hasattr(handler, 'conversations') and conversation_key in handler.conversations:
                        logger.debug(f"AI-чат: Пропускаем для пользователя {user_id} - активный ConversationHandler {handler.name}")
                        return
        
        user = self.db.get_or_create_user(user_id)
        
        # Проверяем, включен ли AI чат
        if not user.settings.ai_chat_enabled:
            logger.debug(f"AI-чат отключен для пользователя {user_id}")
            return  # Пропускаем сообщение
        
        message_text = update.message.text
        logger.info(f"AI-чат сообщение от {user.user_id}: {message_text[:50]}...")
        
        # Показываем что бот печатает
        await update.message.chat.send_action('typing')
        
        # Генерируем ответ
        response = await self.ai_service.generate_response(message_text, user)
        
        # Отправляем ответ с кнопками AI функций
        try:
            await update.message.reply_text(
                response,
                reply_markup=KeyboardManager.get_ai_keyboard()
            )
        except Exception as e:
            # Fallback без Markdown если есть проблемы с форматированием
            await update.message.reply_text(response)
            logger.warning(f"Проблема с Markdown в AI ответе: {e}")
        
        # Сохраняем пользователя
        self.db.save_user(user)
    
    async def _handle_ai_callback(self, query, user: User, data: str):
        """Обработка AI callback'ов"""
        if data == "ai_motivation":
            message = await self.ai_service.generate_response(
                "Мотивируй меня выполнять задачи", user, AIRequestType.MOTIVATION
            )
            await query.edit_message_text(
                f"💪 **Мотивация:**\n\n{message}",
                reply_markup=KeyboardManager.get_ai_keyboard(),
                parse_mode='Markdown'
            )
        
        elif data == "ai_coaching":
            message = await self.ai_service.generate_response(
                "Дай советы по продуктивности", user, AIRequestType.COACHING
            )
            await query.edit_message_text(
                f"🎯 **Коучинг:**\n\n{message}",
                reply_markup=KeyboardManager.get_ai_keyboard(),
                parse_mode='Markdown'
            )
        
        elif data == "ai_psychology":
            message = await self.ai_service.generate_response(
                "Окажи психологическую поддержку", user, AIRequestType.PSYCHOLOGY
            )
            await query.edit_message_text(
                f"🧠 **Поддержка:**\n\n{message}",
                reply_markup=KeyboardManager.get_ai_keyboard(),
                parse_mode='Markdown'
            )
        
        elif data == "ai_analysis":
            message = await self.ai_service.generate_response(
                "Проанализируй мой прогресс", user, AIRequestType.ANALYSIS
            )
            await query.edit_message_text(
                f"📊 **Анализ:**\n\n{message}",
                reply_markup=KeyboardManager.get_ai_keyboard(),
                parse_mode='Markdown'
            )
        
        elif data == "ai_suggest_tasks":
            suggested_tasks = await self.ai_service.suggest_tasks(user)
            suggestion_text = "💡 **AI предлагает задачи:**\n\n"
            
            keyboard = []
            for i, task in enumerate(suggested_tasks):
                suggestion_text += f"{i+1}. {task}\n"
                keyboard.append([
                    InlineKeyboardButton(f"➕ {task[:40]}", callback_data=f"add_suggested_{i}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("🔄 Обновить", callback_data="ai_suggest_tasks")
            ])
            
            # Сохраняем предложения в контексте
            if hasattr(query, 'message') and hasattr(query.message, 'chat'):
                # В callback context недоступен, используем временное хранение
                setattr(user, '_temp_suggested_tasks', suggested_tasks)
                self.db.save_user(user)
            
            await query.edit_message_text(
                suggestion_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        # Сохраняем изменения в пользователе
        self.db.save_user(user)
    
    # ===== УТИЛИТАРНЫЕ МЕТОДЫ =====
    
    def _reset_daily_stats(self, user: User):
        """Сброс ежедневной статистики"""
        today = date.today().isoformat()
        last_activity_date = None
        
        if user.stats.last_activity:
            try:
                last_activity_date = datetime.fromisoformat(user.stats.last_activity).date().isoformat()
            except:
                pass
        
        # Если последняя активность была не сегодня, сбрасываем дневные счетчики
        if last_activity_date != today:
            user.stats.tasks_completed_today = 0
            user.stats.daily_xp_earned = 0
            
            # Увеличиваем счетчик дней трезвости если включен режим
            if user.settings.dry_mode_enabled:
                user.stats.dry_days += 1
    
    async def _handle_timer_callback(self, query, user: User, data: str):
        """Обработка таймеров"""
        if data == "timer_pomodoro":
            await self._start_timer(query, user, user.settings.pomodoro_duration, "🍅 Помодоро")
        elif data == "timer_short_break":
            await self._start_timer(query, user, user.settings.short_break_duration, "☕ Короткий перерыв")
        elif data == "timer_long_break":
            await self._start_timer(query, user, user.settings.long_break_duration, "🛀 Длинный перерыв")
        elif data == "timer_stop":
            await self._stop_timer(query, user)
    
    async def _start_timer(self, query, user: User, duration: int, timer_name: str):
        """Запуск таймера"""
        # Останавливаем предыдущий таймер если есть
        if user.user_id in self.active_timers:
            self.active_timers[user.user_id].cancel()
        
        # Создаем новый таймер
        async def timer_finished():
            await asyncio.sleep(duration * 60)  # Переводим в секунды
            
            # Уведомляем о завершении
            try:
                await self.application.bot.send_message(
                    user.user_id,
                    f"⏰ **Таймер завершен!**\n\n{timer_name} ({duration} мин) закончился.\n\nВремя отдохнуть или перейти к следующей задаче! 💪"
                )
                
                # Увеличиваем счетчик помодоро
                if "Помодоро" in timer_name:
                    user.stats.total_pomodoros += 1
                    self.db.save_user(user)
                
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления таймера: {e}")
            finally:
                # Удаляем из активных таймеров
                if user.user_id in self.active_timers:
                    del self.active_timers[user.user_id]
        
        # Запускаем таймер
        self.active_timers[user.user_id] = asyncio.create_task(timer_finished())
        
        await query.edit_message_text(
            f"⏰ **Таймер запущен!**\n\n{timer_name}: {duration} минут\n\nВы получите уведомление по окончании.\n\nУдачной работы! 💪"
        )
    
    async def _stop_timer(self, query, user: User):
        """Остановка таймера"""
        if user.user_id in self.active_timers:
            self.active_timers[user.user_id].cancel()
            del self.active_timers[user.user_id]
            
            await query.edit_message_text("⏹️ **Таймер остановлен**\n\nВы можете запустить новый таймер когда будете готовы.")
        else:
            await query.edit_message_text("❌ У вас нет активного таймера.")
    
    async def _handle_theme_change(self, query, user: User, data: str):
        """Смена темы оформления"""
        theme_name = data.replace("theme_", "")
        
        try:
            # Проверяем валидность темы
            theme_enum = UserTheme(theme_name)
            user.settings.theme = theme_name
            self.db.save_user(user)
            
            theme_data = ThemeManager.get_theme(theme_name)
            
            await query.edit_message_text(
                f"🎨 **Тема изменена!**\n\nВыбрана тема: {theme_data['name']}\n\nИзменения применятся во всех новых сообщениях."
            )
            
        except ValueError:
            await query.edit_message_text("❌ Неизвестная тема!")
    
    async def completion_button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            completed_count = len(user.completed_tasks_today)
            theme = ThemeManager.get_theme(user.settings.theme)
            
            motivational_messages = [
                "🎉 Поздравляем! Все задачи на сегодня выполнены!",
                "✨ Отлично! Вы завершили все запланированные задачи!",
                "🏆 Превосходно! День прошел продуктивно!",
                "💪 Великолепно! Все цели достигнуты!"
            ]
            
            message = random.choice(motivational_messages)
            
            await update.message.reply_text(
                f"{message}\n\n📊 Выполнено задач: {completed_count}\n{theme['xp_icon']} XP за сегодня: {user.stats.daily_xp_earned}\n\nПродолжайте в том же духе! Завтра вас ждут новые вызовы! 🚀",
                reply_markup=KeyboardManager.get_main_keyboard()
            )
            return
        
        text = f"✅ **Отметка выполнения**\n\nВыберите задачу для отметки ({len(incomplete_tasks)} доступно):"
        
        await update.message.reply_text(
            text,
            reply_markup=KeyboardManager.get_completion_keyboard(active_tasks, user),
            parse_mode='Markdown'
        )
    
    async def handle_unknown_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик неизвестных сообщений"""
        if update.message and update.message.text:
            # ВАЖНО: Если идет диалог ConversationHandler - не обрабатываем
            if context.user_data:
                logger.debug(f"Пропускаем неизвестное сообщение для пользователя {update.effective_user.id} - идет диалог")
                return
            
            user = self.db.get_or_create_user(update.effective_user.id)
            message_text = update.message.text
            
            logger.info(f"Неизвестное сообщение от {user.user_id}: {message_text[:50]}...")
            
            # Случайный дружелюбный ответ
            responses = [
                "🤔 Не совсем понял, но вижу, что вы активны! Это здорово!",
                "💭 Интересное сообщение! Используйте меню ниже для навигации.",
                "🎯 Готов помочь! Выберите действие из меню.",
                "🚀 Отличная энергия! Давайте направим её на выполнение задач!"
            ]
            
            response = random.choice(responses)
            response += f"\n\n💡 **Подсказка:** Включите AI-чат командой /ai_chat для общения со мной!\n\nИли используйте команды:\n• /tasks - ваши задачи\n• /stats - статистика\n• /help - справка"
            
            await update.message.reply_text(
                response,
                reply_markup=KeyboardManager.get_main_keyboard()
            )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        error = context.error
        
        logger.error(f"Ошибка при обработке обновления: {error}")
        logger.error(f"Трейсбек: {traceback.format_exc()}")
        
        # Пытаемся ответить пользователю о временной ошибке
        if update and update.effective_user:
            try:
                if update.message:
                    await update.message.reply_text(
                        "⚠️ Произошла временная ошибка. Попробуйте еще раз через несколько секунд."
                    )
                elif update.callback_query:
                    await update.callback_query.answer("⚠️ Временная ошибка. Попробуйте еще раз.")
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение об ошибке: {e}")
    
    # ===== МЕТОДЫ ЗАПУСКА =====
    
    async def start_polling(self):
        """Запуск бота через polling"""
        try:
            logger.info("🎯 Запуск polling...")
            
            # Инициализируем приложение
            await self.application.initialize()
            await self.application.start()
            
            # Удаляем webhook на всякий случай
            await self.application.bot.delete_webhook(drop_pending_updates=True)
            
            # Запускаем polling
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query']
            )
            
            logger.info("✅ Polling запущен успешно")
            
            # Ждем сигнала остановки
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"❌ Ошибка polling: {e}")
            raise
        finally:
            await self._stop()
    
    async def _stop(self):
        """Остановка бота"""
        logger.info("🛑 Начинаем остановку бота...")
        
        try:
            # Останавливаем все активные таймеры
            for timer_task in self.active_timers.values():
                timer_task.cancel()
            self.active_timers.clear()
            
            # Сохраняем данные
            logger.info("💾 Сохранение данных перед остановкой...")
            await self.db.save_all_users_async()
            self.db.cleanup_old_backups()
            
            # Останавливаем Telegram приложение
            if self.application:
                if hasattr(self.application, 'updater') and self.application.updater.running:
                    await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            # Останавливаем HTTP сервер
            if self.http_server:
                self.http_server.shutdown()
            
            logger.info("🛑 Бот остановлен корректно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке: {e}")
    
    def stop(self):
        """Инициирование остановки бота"""
        self.shutdown_event.set()

# ===== ГЛАВНАЯ ФУНКЦИЯ =====

async def main():
    """Главная функция запуска бота"""
    bot = None
    
    def signal_handler(signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"📢 Получен сигнал {signum}, завершение работы...")
        if bot:
            bot.stop()
        sys.exit(0)
    
    # Настраиваем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Проверяем аргументы командной строки
        if len(sys.argv) > 1:
            if sys.argv[1] == "--validate":
                logger.info("🔍 Проверка целостности данных...")
                db = DatabaseManager()
                users = db.get_all_users()
                logger.info(f"✅ Загружено {len(users)} пользователей")
                
                total_tasks = sum(len(user.tasks) for user in users)
                total_completed = sum(user.stats.completed_tasks for user in users)
                logger.info(f"📊 Всего задач: {total_tasks}, выполнено: {total_completed}")
                return
            
            elif sys.argv[1] == "--test-data" and len(sys.argv) > 2:
                logger.info("🧪 Создание тестовых данных...")
                try:
                    chat_id = int(sys.argv[2])
                    db = DatabaseManager()
                    
                    # Создаем тестового пользователя
                    test_user = db.get_or_create_user(
                        user_id=chat_id,
                        username="testuser",
                        first_name="Тест",
                        last_name="Пользователь"
                    )
                    
                    # Добавляем тестовые задачи
                    test_tasks = [
                        ("Выпить воду", "health", "medium"),
                        ("Сделать зарядку", "health", "high"), 
                        ("Прочитать книгу", "learning", "low"),
                        ("Проверить почту", "work", "medium"),
                        ("Медитировать", "personal", "low")
                    ]
                    
                    for title, category, priority in test_tasks:
                        task = Task(
                            task_id=str(uuid.uuid4()),
                            user_id=test_user.user_id,
                            title=title,
                            category=category,
                            priority=priority
                        )
                        test_user.tasks[task.task_id] = task
                        test_user.stats.total_tasks += 1
                    
                    # Добавляем тестовые достижения и XP
                    test_user.stats.total_xp = 250
                    test_user.stats.level = 3
                    test_user.stats.completed_tasks = 15
                    test_user.achievements = ['first_task', 'tasks_10']
                    
                    db.save_all_users()
                    logger.info(f"✅ Созданы тестовые данные для пользователя {chat_id}")
                    return
                    
                except ValueError:
                    logger.error("❌ Неверный формат chat_id")
                    return
        
        # Создаем и настраиваем бота
        bot = DailyCheckBot()
        await bot.setup_bot()
        
        # Запускаем polling
        await bot.start_polling()
        
    except KeyboardInterrupt:
        logger.info("⌨️ Получено прерывание с клавиатуры")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.error(f"Трейсбек: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        if bot:
            await bot._stop()

# ===== ТОЧКА ВХОДА =====

if __name__ == "__main__":
    try:
        # Проверяем версию Python
        if sys.version_info < (3, 8):
            logger.error("❌ Требуется Python 3.8 или выше")
            sys.exit(1)
        
        logger.info("🚀 Запуск DailyCheck Bot v4.0...")
        logger.info(f"🐍 Python {sys.version}")
        logger.info(f"🖥️ Платформа: {sys.platform}")
        
        # Запускаем бота
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        logger.error(f"Трейсбек: {traceback.format_exc()}")
        sys.exit(1)
