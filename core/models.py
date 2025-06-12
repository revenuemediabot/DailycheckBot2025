#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Bot v4.0 - Core Data Models
Модели данных с валидацией и типизацией

Автор: AI Assistant
Версия: 4.0.1
Дата: 2025-06-12
"""

import uuid
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Union, Any, ClassVar
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# ===== ENUMS =====

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

class NotificationType(Enum):
    """Типы уведомлений"""
    REMINDER = "reminder"
    ACHIEVEMENT = "achievement"
    DAILY_SUMMARY = "daily_summary"
    STREAK_MILESTONE = "streak_milestone"

# ===== VALIDATION HELPERS =====

class ValidationError(Exception):
    """Ошибка валидации данных"""
    pass

def validate_text(text: str, min_length: int = 1, max_length: int = 1000, field_name: str = "text") -> str:
    """Валидация текстовых полей"""
    if not isinstance(text, str):
        raise ValidationError(f"{field_name} должен быть строкой")
    
    text = text.strip()
    if len(text) < min_length:
        raise ValidationError(f"{field_name} должен содержать минимум {min_length} символов")
    
    if len(text) > max_length:
        raise ValidationError(f"{field_name} должен содержать максимум {max_length} символов")
    
    return text

def validate_enum_value(value: str, enum_class: type, field_name: str = "value") -> str:
    """Валидация значений enum"""
    try:
        enum_class(value)
        return value
    except ValueError:
        valid_values = [e.value for e in enum_class]
        raise ValidationError(f"{field_name} должен быть одним из: {valid_values}")

# ===== CORE MODELS =====

@dataclass
class TaskCompletion:
    """Запись о выполнении задачи"""
    date: str  # ISO формат даты (YYYY-MM-DD)
    completed: bool
    note: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    time_spent: Optional[int] = None  # в минутах
    satisfaction_rating: Optional[int] = None  # 1-5
    
    def __post_init__(self):
        """Валидация после создания объекта"""
        # Валидация даты
        try:
            date.fromisoformat(self.date)
        except ValueError:
            raise ValidationError(f"Неверный формат даты: {self.date}")
        
        # Валидация времени
        if self.time_spent is not None:
            if not isinstance(self.time_spent, int) or self.time_spent < 0:
                raise ValidationError("time_spent должен быть положительным числом")
        
        # Валидация рейтинга
        if self.satisfaction_rating is not None:
            if not isinstance(self.satisfaction_rating, int) or not 1 <= self.satisfaction_rating <= 5:
                raise ValidationError("satisfaction_rating должен быть от 1 до 5")
        
        # Валидация заметки
        if self.note is not None:
            self.note = validate_text(self.note, min_length=0, max_length=500, field_name="note")
    
    @property
    def completion_date(self) -> date:
        """Дата выполнения как объект date"""
        return date.fromisoformat(self.date)
    
    @property
    def completion_datetime(self) -> datetime:
        """Время выполнения как объект datetime"""
        return datetime.fromisoformat(self.timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskCompletion":
        return cls(**data)
    
    @classmethod
    def create_for_today(cls, completed: bool = True, note: Optional[str] = None, 
                        time_spent: Optional[int] = None) -> "TaskCompletion":
        """Создание записи для сегодняшнего дня"""
        return cls(
            date=date.today().isoformat(),
            completed=completed,
            note=note,
            time_spent=time_spent
        )

@dataclass
class Subtask:
    """Подзадача"""
    subtask_id: str
    title: str
    completed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    description: Optional[str] = None
    estimated_time: Optional[int] = None  # в минутах
    
    def __post_init__(self):
        """Валидация после создания объекта"""
        self.title = validate_text(self.title, min_length=3, max_length=200, field_name="title")
        
        if self.description is not None:
            self.description = validate_text(self.description, min_length=0, max_length=500, field_name="description")
        
        if self.estimated_time is not None:
            if not isinstance(self.estimated_time, int) or self.estimated_time <= 0:
                raise ValidationError("estimated_time должен быть положительным числом")
    
    def toggle_completion(self) -> bool:
        """Переключить статус выполнения"""
        self.completed = not self.completed
        return self.completed
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subtask":
        return cls(**data)
    
    @classmethod
    def create(cls, title: str, description: Optional[str] = None) -> "Subtask":
        """Создание новой подзадачи"""
        return cls(
            subtask_id=str(uuid.uuid4()),
            title=title,
            description=description
        )

@dataclass
class Task:
    """Модель задачи с расширенным функционалом"""
    task_id: str
    user_id: int
    title: str
    description: Optional[str] = None
    category: str = TaskCategory.PERSONAL.value
    priority: str = TaskPriority.MEDIUM.value
    status: str = TaskStatus.ACTIVE.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completions: List[TaskCompletion] = field(default_factory=list)
    subtasks: List[Subtask] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    is_daily: bool = True
    reminder_time: Optional[str] = None
    estimated_time: Optional[int] = None  # в минутах
    difficulty: int = 1  # 1-5
    color: Optional[str] = None  # HEX цвет для UI
    icon: Optional[str] = None  # Emoji иконка
    
    # Metadata
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())
    archived_at: Optional[str] = None
    
    def __post_init__(self):
        """Валидация после создания объекта"""
        self.title = validate_text(self.title, min_length=3, max_length=200, field_name="title")
        
        if self.description is not None:
            self.description = validate_text(self.description, min_length=0, max_length=1000, field_name="description")
        
        self.category = validate_enum_value(self.category, TaskCategory, "category")
        self.priority = validate_enum_value(self.priority, TaskPriority, "priority")
        self.status = validate_enum_value(self.status, TaskStatus, "status")
        
        if not isinstance(self.difficulty, int) or not 1 <= self.difficulty <= 5:
            raise ValidationError("difficulty должен быть от 1 до 5")
        
        if self.estimated_time is not None:
            if not isinstance(self.estimated_time, int) or self.estimated_time <= 0:
                raise ValidationError("estimated_time должен быть положительным числом")
        
        # Валидация тегов
        validated_tags = []
        for tag in self.tags:
            if isinstance(tag, str):
                tag = tag.strip()
                if len(tag) > 0 and len(tag) <= 30:
                    validated_tags.append(tag)
        self.tags = validated_tags[:10]  # Максимум 10 тегов
        
        # Обновление времени модификации
        self.last_modified = datetime.now().isoformat()
    
    # ===== PROPERTIES =====
    
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
    def longest_streak(self) -> int:
        """Самая длинная серия выполнения"""
        if not self.completions:
            return 0
        
        completed_dates = sorted([
            date.fromisoformat(c.date) for c in self.completions 
            if c.completed
        ])
        
        if not completed_dates:
            return 0
        
        max_streak = 1
        current_streak = 1
        
        for i in range(1, len(completed_dates)):
            if completed_dates[i] == completed_dates[i-1] + timedelta(days=1):
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        
        return max_streak
    
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
    def completion_rate_all_time(self) -> float:
        """Общий процент выполнения"""
        if not self.completions:
            return 0.0
        
        total_days = (datetime.now() - datetime.fromisoformat(self.created_at)).days + 1
        completed_days = len([c for c in self.completions if c.completed])
        
        return (completed_days / total_days) * 100 if total_days > 0 else 0.0
    
    @property
    def subtasks_completed_count(self) -> int:
        """Количество выполненных подзадач"""
        return sum(1 for subtask in self.subtasks if subtask.completed)
    
    @property
    def subtasks_total_count(self) -> int:
        """Общее количество подзадач"""
        return len(self.subtasks)
    
    @property
    def subtasks_completion_rate(self) -> float:
        """Процент выполнения подзадач"""
        if not self.subtasks:
            return 100.0
        return (self.subtasks_completed_count / self.subtasks_total_count) * 100
    
    @property
    def xp_value(self) -> int:
        """XP за выполнение задачи"""
        base_xp = {
            TaskPriority.LOW.value: 15,
            TaskPriority.MEDIUM.value: 25,
            TaskPriority.HIGH.value: 40
        }.get(self.priority, 25)
        
        difficulty_multiplier = self.difficulty * 0.2 + 0.8
        streak_bonus = min(self.current_streak * 3, 75)
        
        # Бонус за подзадачи
        subtask_bonus = self.subtasks_completed_count * 5
        
        return int(base_xp * difficulty_multiplier + streak_bonus + subtask_bonus)
    
    @property
    def total_time_spent(self) -> int:
        """Общее время, потраченное на задачу (в минутах)"""
        return sum(
            c.time_spent for c in self.completions 
            if c.time_spent is not None
        )
    
    @property
    def average_completion_time(self) -> float:
        """Среднее время выполнения (в минутах)"""
        times = [c.time_spent for c in self.completions if c.time_spent is not None]
        return sum(times) / len(times) if times else 0.0
    
    @property
    def days_since_creation(self) -> int:
        """Дней с момента создания"""
        return (datetime.now() - datetime.fromisoformat(self.created_at)).days
    
    @property
    def is_overdue(self) -> bool:
        """Задача просрочена (не выполнена сегодня)"""
        return not self.is_completed_today() and self.status == TaskStatus.ACTIVE.value
    
    @property
    def category_emoji(self) -> str:
        """Emoji для категории"""
        category_emojis = {
            TaskCategory.WORK.value: "💼",
            TaskCategory.HEALTH.value: "🏃",
            TaskCategory.LEARNING.value: "📚",
            TaskCategory.PERSONAL.value: "👤",
            TaskCategory.FINANCE.value: "💰"
        }
        return category_emojis.get(self.category, "📋")
    
    @property
    def priority_emoji(self) -> str:
        """Emoji для приоритета"""
        priority_emojis = {
            TaskPriority.LOW.value: "🔵",
            TaskPriority.MEDIUM.value: "🟡",
            TaskPriority.HIGH.value: "🔴"
        }
        return priority_emojis.get(self.priority, "🟡")
    
    # ===== METHODS =====
    
    def is_completed_today(self) -> bool:
        """Проверка выполнения задачи сегодня"""
        today = date.today().isoformat()
        return any(c.date == today and c.completed for c in self.completions)
    
    def is_completed_on_date(self, check_date: Union[date, str]) -> bool:
        """Проверка выполнения задачи в определенную дату"""
        if isinstance(check_date, date):
            check_date = check_date.isoformat()
        
        return any(c.date == check_date and c.completed for c in self.completions)
    
    def mark_completed(self, note: Optional[str] = None, time_spent: Optional[int] = None,
                      satisfaction_rating: Optional[int] = None) -> bool:
        """Отметить задачу как выполненную на сегодня"""
        today = date.today().isoformat()
        
        # Проверяем, не выполнена ли уже сегодня
        for completion in self.completions:
            if completion.date == today:
                completion.completed = True
                completion.note = note
                completion.time_spent = time_spent
                completion.satisfaction_rating = satisfaction_rating
                completion.timestamp = datetime.now().isoformat()
                self.last_modified = datetime.now().isoformat()
                return True
        
        # Добавляем новую запись
        try:
            completion = TaskCompletion(
                date=today,
                completed=True,
                note=note,
                time_spent=time_spent,
                satisfaction_rating=satisfaction_rating
            )
            self.completions.append(completion)
            self.last_modified = datetime.now().isoformat()
            return True
        except ValidationError as e:
            logger.error(f"Ошибка при создании записи о выполнении: {e}")
            return False
    
    def mark_uncompleted(self) -> bool:
        """Отменить выполнение задачи на сегодня"""
        today = date.today().isoformat()
        
        for completion in self.completions:
            if completion.date == today:
                completion.completed = False
                completion.timestamp = datetime.now().isoformat()
                self.last_modified = datetime.now().isoformat()
                return True
        
        return False
    
    def add_subtask(self, title: str, description: Optional[str] = None) -> str:
        """Добавить подзадачу"""
        try:
            subtask = Subtask.create(title, description)
            self.subtasks.append(subtask)
            self.last_modified = datetime.now().isoformat()
            return subtask.subtask_id
        except ValidationError as e:
            logger.error(f"Ошибка при создании подзадачи: {e}")
            return ""
    
    def remove_subtask(self, subtask_id: str) -> bool:
        """Удалить подзадачу"""
        initial_count = len(self.subtasks)
        self.subtasks = [s for s in self.subtasks if s.subtask_id != subtask_id]
        
        if len(self.subtasks) < initial_count:
            self.last_modified = datetime.now().isoformat()
            return True
        return False
    
    def toggle_subtask(self, subtask_id: str) -> bool:
        """Переключить статус подзадачи"""
        for subtask in self.subtasks:
            if subtask.subtask_id == subtask_id:
                subtask.toggle_completion()
                self.last_modified = datetime.now().isoformat()
                return True
        return False
    
    def add_tag(self, tag: str) -> bool:
        """Добавить тег"""
        tag = tag.strip()
        if len(tag) > 0 and len(tag) <= 30 and tag not in self.tags and len(self.tags) < 10:
            self.tags.append(tag)
            self.last_modified = datetime.now().isoformat()
            return True
        return False
    
    def remove_tag(self, tag: str) -> bool:
        """Удалить тег"""
        if tag in self.tags:
            self.tags.remove(tag)
            self.last_modified = datetime.now().isoformat()
            return True
        return False
    
    def update_priority(self, priority: str) -> bool:
        """Обновить приоритет"""
        try:
            self.priority = validate_enum_value(priority, TaskPriority, "priority")
            self.last_modified = datetime.now().isoformat()
            return True
        except ValidationError:
            return False
    
    def update_category(self, category: str) -> bool:
        """Обновить категорию"""
        try:
            self.category = validate_enum_value(category, TaskCategory, "category")
            self.last_modified = datetime.now().isoformat()
            return True
        except ValidationError:
            return False
    
    def pause(self) -> bool:
        """Приостановить задачу"""
        if self.status == TaskStatus.ACTIVE.value:
            self.status = TaskStatus.PAUSED.value
            self.last_modified = datetime.now().isoformat()
            return True
        return False
    
    def resume(self) -> bool:
        """Возобновить задачу"""
        if self.status == TaskStatus.PAUSED.value:
            self.status = TaskStatus.ACTIVE.value
            self.last_modified = datetime.now().isoformat()
            return True
        return False
    
    def archive(self) -> bool:
        """Архивировать задачу"""
        if self.status in [TaskStatus.ACTIVE.value, TaskStatus.PAUSED.value]:
            self.status = TaskStatus.ARCHIVED.value
            self.archived_at = datetime.now().isoformat()
            self.last_modified = datetime.now().isoformat()
            return True
        return False
    
    def get_completion_history(self, days: int = 30) -> List[TaskCompletion]:
        """Получить историю выполнения за последние N дней"""
        cutoff_date = date.today() - timedelta(days=days)
        return [
            c for c in self.completions
            if date.fromisoformat(c.date) >= cutoff_date
        ]
    
    def get_completion_streak_dates(self) -> List[date]:
        """Получить даты текущего streak'а"""
        if not self.completions:
            return []
        
        completed_dates = sorted([
            date.fromisoformat(c.date) for c in self.completions 
            if c.completed
        ], reverse=True)
        
        if not completed_dates:
            return []
        
        streak_dates = []
        current_date = date.today()
        
        for comp_date in completed_dates:
            if comp_date == current_date:
                streak_dates.append(comp_date)
                current_date = date.fromordinal(current_date.toordinal() - 1)
            else:
                break
        
        return list(reversed(streak_dates))
    
    # ===== SERIALIZATION =====
    
    def to_dict(self) -> Dict[str, Any]:
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
            "difficulty": self.difficulty,
            "color": self.color,
            "icon": self.icon,
            "last_modified": self.last_modified,
            "archived_at": self.archived_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Десериализация из словаря"""
        try:
            task = cls(
                task_id=data["task_id"],
                user_id=data["user_id"],
                title=data["title"],
                description=data.get("description"),
                category=data.get("category", TaskCategory.PERSONAL.value),
                priority=data.get("priority", TaskPriority.MEDIUM.value),
                status=data.get("status", TaskStatus.ACTIVE.value),
                created_at=data.get("created_at", datetime.now().isoformat()),
                tags=data.get("tags", []),
                is_daily=data.get("is_daily", True),
                reminder_time=data.get("reminder_time"),
                estimated_time=data.get("estimated_time"),
                difficulty=data.get("difficulty", 1),
                color=data.get("color"),
                icon=data.get("icon"),
                last_modified=data.get("last_modified", datetime.now().isoformat()),
                archived_at=data.get("archived_at")
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
        except Exception as e:
            logger.error(f"Ошибка десериализации задачи: {e}")
            raise ValidationError(f"Не удалось загрузить задачу: {e}")
    
    @classmethod
    def create(cls, user_id: int, title: str, description: Optional[str] = None,
              category: str = TaskCategory.PERSONAL.value, 
              priority: str = TaskPriority.MEDIUM.value,
              difficulty: int = 1, tags: Optional[List[str]] = None) -> "Task":
        """Создание новой задачи"""
        return cls(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            description=description,
            category=category,
            priority=priority,
            difficulty=difficulty,
            tags=tags or []
        )

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
    last_triggered: Optional[str] = None
    times_triggered: int = 0
    
    def __post_init__(self):
        """Валидация после создания объекта"""
        self.title = validate_text(self.title, min_length=1, max_length=100, field_name="title")
        self.message = validate_text(self.message, min_length=1, max_length=500, field_name="message")
    
    def trigger(self):
        """Отметить напоминание как сработавшее"""
        self.last_triggered = datetime.now().isoformat()
        self.times_triggered += 1
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reminder":
        return cls(**data)
    
    @classmethod
    def create(cls, user_id: int, title: str, message: str, trigger_time: str,
              is_recurring: bool = False) -> "Reminder":
        """Создание нового напоминания"""
        return cls(
            reminder_id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            message=message,
            trigger_time=trigger_time,
            is_recurring=is_recurring
        )

@dataclass
class Friend:
    """Модель друга"""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_blocked: bool = False
    friendship_level: int = 1  # 1-5 уровень дружбы
    last_interaction: Optional[str] = None
    
    def __post_init__(self):
        """Валидация после создания объекта"""
        if self.user_id <= 0:
            raise ValidationError("user_id должен быть положительным числом")
        
        if not isinstance(self.friendship_level, int) or not 1 <= self.friendship_level <= 5:
            self.friendship_level = 1
    
    @property
    def display_name(self) -> str:
        """Отображаемое имя друга"""
        if self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"Пользователь {self.user_id}"
    
    def update_interaction(self):
        """Обновить время последнего взаимодействия"""
        self.last_interaction = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Friend":
        return cls(**data)

# ===== ПРОДОЛЖЕНИЕ core/models.py (Part 2/2) =====

@dataclass
class UserSettings:
    """Расширенные настройки пользователя"""
    timezone: str = "UTC"
    language: str = "ru"
    theme: str = UserTheme.CLASSIC.value
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
    
    # Новые настройки
    compact_view: bool = False
    dark_mode: bool = False
    auto_complete_subtasks: bool = True
    weekly_goal_reminder: bool = True
    achievement_notifications: bool = True
    friend_activity_notifications: bool = True
    data_export_format: str = "json"  # json, csv, both
    privacy_level: str = "friends"  # public, friends, private
    
    def __post_init__(self):
        """Валидация после создания объекта"""
        # Валидация темы
        try:
            UserTheme(self.theme)
        except ValueError:
            self.theme = UserTheme.CLASSIC.value
        
        # Валидация времени
        try:
            time_parts = self.daily_reminder_time.split(':')
            if len(time_parts) != 2:
                raise ValueError
            hour, minute = int(time_parts[0]), int(time_parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except ValueError:
            self.daily_reminder_time = "09:00"
        
        # Валидация продолжительности Pomodoro
        if not isinstance(self.pomodoro_duration, int) or not 5 <= self.pomodoro_duration <= 60:
            self.pomodoro_duration = 25
        
        if not isinstance(self.short_break_duration, int) or not 1 <= self.short_break_duration <= 30:
            self.short_break_duration = 5
        
        if not isinstance(self.long_break_duration, int) or not 5 <= self.long_break_duration <= 60:
            self.long_break_duration = 15
        
        # Валидация формата экспорта
        if self.data_export_format not in ["json", "csv", "both"]:
            self.data_export_format = "json"
        
        # Валидация уровня приватности
        if self.privacy_level not in ["public", "friends", "private"]:
            self.privacy_level = "friends"
    
    def update_pomodoro_settings(self, work: int, short_break: int, long_break: int) -> bool:
        """Обновление настроек Pomodoro"""
        try:
            if 5 <= work <= 60 and 1 <= short_break <= 30 and 5 <= long_break <= 60:
                self.pomodoro_duration = work
                self.short_break_duration = short_break
                self.long_break_duration = long_break
                return True
        except (TypeError, ValueError):
            pass
        return False
    
    def toggle_feature(self, feature: str) -> bool:
        """Переключение булевых настроек"""
        feature_map = {
            'reminder_enabled': 'reminder_enabled',
            'weekly_stats': 'weekly_stats',
            'motivational_messages': 'motivational_messages',
            'notification_sound': 'notification_sound',
            'auto_archive_completed': 'auto_archive_completed',
            'ai_chat_enabled': 'ai_chat_enabled',
            'show_xp': 'show_xp',
            'show_streaks': 'show_streaks',
            'dry_mode_enabled': 'dry_mode_enabled',
            'compact_view': 'compact_view',
            'dark_mode': 'dark_mode',
            'auto_complete_subtasks': 'auto_complete_subtasks',
            'weekly_goal_reminder': 'weekly_goal_reminder',
            'achievement_notifications': 'achievement_notifications',
            'friend_activity_notifications': 'friend_activity_notifications'
        }
        
        if feature in feature_map:
            current_value = getattr(self, feature_map[feature])
            setattr(self, feature_map[feature], not current_value)
            return True
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserSettings":
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
    
    # Новая статистика
    tasks_by_category: Dict[str, int] = field(default_factory=dict)
    tasks_by_priority: Dict[str, int] = field(default_factory=dict)
    average_completion_time: float = 0.0  # в минутах
    most_productive_hour: int = 9  # час дня
    total_focus_time: int = 0  # общее время фокуса в минутах
    days_active: int = 0  # дней активности
    perfect_days: int = 0  # дней с выполненными всеми задачами
    social_interactions: int = 0  # взаимодействий с друзьями
    
    # XP constants
    XP_MULTIPLIERS: ClassVar[Dict[str, float]] = {
        'base': 1.0,
        'streak_bonus': 0.1,
        'difficulty_bonus': 0.2,
        'category_bonus': 0.05,
        'perfect_day_bonus': 2.0
    }
    
    def __post_init__(self):
        """Валидация после создания объекта"""
        # Ensure non-negative values
        self.total_tasks = max(0, self.total_tasks)
        self.completed_tasks = max(0, self.completed_tasks)
        self.current_streak = max(0, self.current_streak)
        self.longest_streak = max(0, self.longest_streak)
        self.total_xp = max(0, self.total_xp)
        self.level = max(1, self.level)
        self.tasks_completed_today = max(0, self.tasks_completed_today)
        self.daily_xp_earned = max(0, self.daily_xp_earned)
        self.weekly_goal = max(1, self.weekly_goal)
        self.monthly_goal = max(1, self.monthly_goal)
        self.dry_days = max(0, self.dry_days)
        self.total_pomodoros = max(0, self.total_pomodoros)
        
        # Validate time of day
        if self.preferred_time_of_day not in ["morning", "afternoon", "evening"]:
            self.preferred_time_of_day = "morning"
        
        # Validate hour
        if not 0 <= self.most_productive_hour <= 23:
            self.most_productive_hour = 9
        
        # Initialize category and priority dicts if empty
        if not self.tasks_by_category:
            self.tasks_by_category = {category.value: 0 for category in TaskCategory}
        
        if not self.tasks_by_priority:
            self.tasks_by_priority = {priority.value: 0 for priority in TaskPriority}
    
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
        
        return (current_progress / level_xp_range) * 100 if level_xp_range > 0 else 0.0
    
    @property
    def xp_to_next_level(self) -> int:
        """XP до следующего уровня"""
        return max(0, self.xp_for_level(self.level + 1) - self.total_xp)
    
    @property
    def average_xp_per_day(self) -> float:
        """Среднее XP в день"""
        days = max(1, self.days_since_registration)
        return self.total_xp / days
    
    @property
    def productivity_score(self) -> float:
        """Оценка продуктивности (0-100)"""
        factors = []
        
        # Completion rate factor (40%)
        factors.append(self.completion_rate * 0.4)
        
        # Streak factor (30%)
        max_possible_streak = min(30, self.days_since_registration)
        if max_possible_streak > 0:
            streak_score = (self.current_streak / max_possible_streak) * 100
            factors.append(min(100, streak_score) * 0.3)
        
        # Activity factor (20%)
        if self.days_since_registration > 0:
            activity_score = (self.days_active / self.days_since_registration) * 100
            factors.append(min(100, activity_score) * 0.2)
        
        # Perfect days factor (10%)
        if self.days_active > 0:
            perfect_score = (self.perfect_days / self.days_active) * 100
            factors.append(min(100, perfect_score) * 0.1)
        
        return sum(factors)
    
    @staticmethod
    def xp_for_level(level: int) -> int:
        """Необходимый XP для достижения уровня"""
        if level <= 1:
            return 0
        return int(100 * (level - 1) * 1.5)
    
    def add_xp(self, xp: int, reason: str = "task_completion") -> bool:
        """Добавить XP и проверить повышение уровня"""
        if xp <= 0:
            return False
        
        old_level = self.level
        self.total_xp += xp
        self.daily_xp_earned += xp
        
        # Проверяем повышение уровня
        while self.total_xp >= self.xp_for_level(self.level + 1):
            self.level += 1
        
        # Обновляем статистику по причинам
        if reason == "task_completion":
            self.completed_tasks += 1
        
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
    
    def update_category_stats(self, category: str, increment: int = 1):
        """Обновить статистику по категориям"""
        if category in self.tasks_by_category:
            self.tasks_by_category[category] += increment
        else:
            self.tasks_by_category[category] = increment
    
    def update_priority_stats(self, priority: str, increment: int = 1):
        """Обновить статистику по приоритетам"""
        if priority in self.tasks_by_priority:
            self.tasks_by_priority[priority] += increment
        else:
            self.tasks_by_priority[priority] = increment
    
    def reset_daily_stats(self):
        """Сброс ежедневной статистики"""
        self.tasks_completed_today = 0
        self.daily_xp_earned = 0
    
    def add_pomodoro(self, minutes: int = 25):
        """Добавить завершенный помодоро"""
        self.total_pomodoros += 1
        self.total_focus_time += minutes
    
    def update_productive_hour(self, hour: int):
        """Обновить самый продуктивный час"""
        if 0 <= hour <= 23:
            self.most_productive_hour = hour
    
    def get_weekly_progress(self) -> Dict[str, Any]:
        """Получить прогресс за неделю"""
        # This would need to be calculated based on actual task data
        # For now, return a basic structure
        return {
            "completed": self.tasks_completed_today,  # This should be weekly completed
            "goal": self.weekly_goal,
            "percentage": (self.tasks_completed_today / self.weekly_goal) * 100 if self.weekly_goal > 0 else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserStats":
        return cls(**data)

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
    ai_chat_history: List[Dict[str, Any]] = field(default_factory=list)
    weekly_goals: Dict[str, int] = field(default_factory=dict)  # {"2025-W23": 7}
    
    # Новые поля
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_seen: Optional[str] = None
    is_premium: bool = False
    premium_expires: Optional[str] = None
    subscription_type: str = "free"  # free, basic, premium
    preferences: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Валидация после создания объекта"""
        if self.user_id <= 0:
            raise ValidationError("user_id должен быть положительным числом")
        
        # Инициализация статистики если не задана
        if not hasattr(self.stats, 'registration_date') or not self.stats.registration_date:
            self.stats.registration_date = self.created_at
        
        # Валидация заметок
        if len(self.notes) > 5000:
            self.notes = self.notes[:5000]
        
        # Ограничение истории AI чата
        if len(self.ai_chat_history) > 50:
            self.ai_chat_history = self.ai_chat_history[-50:]
    
    @property
    def display_name(self) -> str:
        """Отображаемое имя пользователя"""
        if self.first_name:
            name = self.first_name
            if self.last_name:
                name += f" {self.last_name}"
            return name
        elif self.username:
            return f"@{self.username}"
        else:
            return f"Пользователь {self.user_id}"
    
    @property
    def active_tasks(self) -> Dict[str, Task]:
        """Активные задачи"""
        return {k: v for k, v in self.tasks.items() if v.status == TaskStatus.ACTIVE.value}
    
    @property
    def paused_tasks(self) -> Dict[str, Task]:
        """Приостановленные задачи"""
        return {k: v for k, v in self.tasks.items() if v.status == TaskStatus.PAUSED.value}
    
    @property
    def archived_tasks(self) -> Dict[str, Task]:
        """Архивные задачи"""
        return {k: v for k, v in self.tasks.items() if v.status == TaskStatus.ARCHIVED.value}
    
    @property
    def completed_tasks_today(self) -> List[Task]:
        """Задачи, выполненные сегодня"""
        return [task for task in self.tasks.values() if task.is_completed_today()]
    
    @property
    def overdue_tasks(self) -> List[Task]:
        """Просроченные задачи"""
        return [task for task in self.active_tasks.values() if task.is_overdue]
    
    @property
    def current_week_key(self) -> str:
        """Ключ текущей недели в формате YYYY-WXX"""
        today = date.today()
        year, week, _ = today.isocalendar()
        return f"{year}-W{week:02d}"
    
    @property
    def total_streak_days(self) -> int:
        """Общие дни streak'ов по всем задачам"""
        return sum(task.current_streak for task in self.active_tasks.values())
    
    @property
    def max_current_streak(self) -> int:
        """Максимальный текущий streak среди всех задач"""
        streaks = [task.current_streak for task in self.active_tasks.values()]
        return max(streaks) if streaks else 0
    
    @property
    def completion_rate_today(self) -> float:
        """Процент выполнения задач сегодня"""
        active_count = len(self.active_tasks)
        if active_count == 0:
            return 100.0
        
        completed_count = len(self.completed_tasks_today)
        return (completed_count / active_count) * 100
    
    @property
    def is_active_today(self) -> bool:
        """Пользователь был активен сегодня"""
        if not self.last_seen:
            return False
        
        try:
            last_seen_date = datetime.fromisoformat(self.last_seen).date()
            return last_seen_date == date.today()
        except:
            return False
    
    def update_activity(self):
        """Обновить время последней активности"""
        self.last_seen = datetime.now().isoformat()
        self.stats.last_activity = self.last_seen
        
        # Обновляем дни активности
        if not self.is_active_today:
            self.stats.days_active += 1
    
    def add_task(self, title: str, description: Optional[str] = None, 
                category: str = TaskCategory.PERSONAL.value,
                priority: str = TaskPriority.MEDIUM.value,
                difficulty: int = 1, tags: Optional[List[str]] = None) -> str:
        """Добавить новую задачу"""
        try:
            task = Task.create(
                user_id=self.user_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                difficulty=difficulty,
                tags=tags
            )
            
            self.tasks[task.task_id] = task
            self.stats.total_tasks += 1
            self.stats.update_category_stats(category)
            self.stats.update_priority_stats(priority)
            
            return task.task_id
        except ValidationError as e:
            logger.error(f"Ошибка создания задачи: {e}")
            return ""
    
    def remove_task(self, task_id: str) -> bool:
        """Удалить задачу"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            
            # Уменьшаем счетчики статистики
            self.stats.total_tasks = max(0, self.stats.total_tasks - 1)
            if task.is_completed_today():
                self.stats.completed_tasks = max(0, self.stats.completed_tasks - 1)
            
            # Обновляем статистику категорий
            self.stats.update_category_stats(task.category, -1)
            self.stats.update_priority_stats(task.priority, -1)
            
            del self.tasks[task_id]
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Получить задачу по ID"""
        return self.tasks.get(task_id)
    
    def add_friend(self, friend_user_id: int, username: Optional[str] = None,
                  first_name: Optional[str] = None) -> bool:
        """Добавить друга"""
        if friend_user_id == self.user_id:
            return False  # Нельзя добавить себя
        
        if any(f.user_id == friend_user_id for f in self.friends):
            return False  # Уже в друзьях
        
        try:
            friend = Friend(
                user_id=friend_user_id,
                username=username,
                first_name=first_name
            )
            self.friends.append(friend)
            self.stats.social_interactions += 1
            return True
        except ValidationError:
            return False
    
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
        try:
            reminder = Reminder.create(
                user_id=self.user_id,
                title=title,
                message=message,
                trigger_time=trigger_time,
                is_recurring=is_recurring
            )
            self.reminders.append(reminder)
            return reminder.reminder_id
        except ValidationError:
            return ""
    
    def remove_reminder(self, reminder_id: str) -> bool:
        """Удалить напоминание"""
        initial_count = len(self.reminders)
        self.reminders = [r for r in self.reminders if r.reminder_id != reminder_id]
        return len(self.reminders) < initial_count
    
    def add_achievement(self, achievement_id: str) -> bool:
        """Добавить достижение"""
        if achievement_id not in self.achievements:
            self.achievements.append(achievement_id)
            return True
        return False
    
    def has_achievement(self, achievement_id: str) -> bool:
        """Проверить наличие достижения"""
        return achievement_id in self.achievements
    
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
    
    def set_weekly_goal(self, goal: int, week_key: Optional[str] = None) -> bool:
        """Установить цель на неделю"""
        if goal <= 0:
            return False
        
        if not week_key:
            week_key = self.current_week_key
        
        self.weekly_goals[week_key] = goal
        return True
    
    def update_ai_chat_history(self, user_message: str, ai_response: str):
        """Обновить историю AI чата"""
        self.ai_chat_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        self.ai_chat_history.append({
            "role": "assistant", 
            "content": ai_response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Ограничиваем историю последними 50 сообщениями
        if len(self.ai_chat_history) > 50:
            self.ai_chat_history = self.ai_chat_history[-50:]
    
    def clear_ai_chat_history(self):
        """Очистить историю AI чата"""
        self.ai_chat_history.clear()
    
    def check_perfect_day(self) -> bool:
        """Проверить, был ли день идеальным (все задачи выполнены)"""
        active_tasks = list(self.active_tasks.values())
        if not active_tasks:
            return False
        
        completed_today = len(self.completed_tasks_today)
        if completed_today == len(active_tasks):
            self.stats.perfect_days += 1
            return True
        return False
    
    def update_preferred_time(self):
        """Обновить предпочитаемое время активности"""
        current_hour = datetime.now().hour
        
        if 5 <= current_hour < 12:
            time_period = "morning"
        elif 12 <= current_hour < 18:
            time_period = "afternoon"
        else:
            time_period = "evening"
        
        self.stats.preferred_time_of_day = time_period
        self.stats.update_productive_hour(current_hour)
    
    def to_dict(self) -> Dict[str, Any]:
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
            "weekly_goals": self.weekly_goals,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "is_premium": self.is_premium,
            "premium_expires": self.premium_expires,
            "subscription_type": self.subscription_type,
            "preferences": self.preferences
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        """Десериализация из словаря"""
        try:
            user = cls(
                user_id=data["user_id"],
                username=data.get("username"),
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                notes=data.get("notes", ""),
                ai_chat_history=data.get("ai_chat_history", []),
                weekly_goals=data.get("weekly_goals", {}),
                created_at=data.get("created_at", datetime.now().isoformat()),
                last_seen=data.get("last_seen"),
                is_premium=data.get("is_premium", False),
                premium_expires=data.get("premium_expires"),
                subscription_type=data.get("subscription_type", "free"),
                preferences=data.get("preferences", {})
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
        except Exception as e:
            logger.error(f"Ошибка десериализации пользователя: {e}")
            raise ValidationError(f"Не удалось загрузить пользователя: {e}")
    
    @classmethod
    def create(cls, user_id: int, username: Optional[str] = None,
              first_name: Optional[str] = None, last_name: Optional[str] = None) -> "User":
        """Создание нового пользователя"""
        return cls(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )

# ===== EXPORT =====

__all__ = [
    # Enums
    'TaskStatus', 'TaskPriority', 'TaskCategory', 'UserTheme', 'AIRequestType', 'NotificationType',
    
    # Exceptions
    'ValidationError',
    
    # Validation functions
    'validate_text', 'validate_enum_value',
    
    # Models
    'TaskCompletion', 'Subtask', 'Task', 'Reminder', 'Friend', 'UserSettings', 'UserStats', 'User'
]
