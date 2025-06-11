# services/task_service.py

import asyncio
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# Импортируем сервис данных
from services.data_service import get_data_service, DataService

logger = logging.getLogger(__name__)

# ===== ЕНУМЫ И КОНСТАНТЫ =====

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

# ===== МОДЕЛИ ДАННЫХ =====

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
    """Модель задачи с полным функционалом"""
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
    
    def update_field(self, field: str, value: Any) -> bool:
        """Обновить поле задачи"""
        if hasattr(self, field):
            setattr(self, field, value)
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

# ===== СИСТЕМА ДОСТИЖЕНИЙ =====

class AchievementSystem:
    """Расширенная система достижений для задач"""
    
    ACHIEVEMENTS = {
        'first_task': {
            'title': 'Первые шаги',
            'description': 'Создайте свою первую задачу',
            'icon': '🎯',
            'xp_reward': 50,
            'condition': lambda user_data: len(user_data.get("tasks", {})) >= 1
        },
        'streak_3': {
            'title': 'Начинающий',
            'description': 'Поддерживайте streak 3 дня',
            'icon': '🔥',
            'xp_reward': 100,
            'condition': lambda user_data: TaskService.get_max_streak_from_user_data(user_data) >= 3
        },
        'streak_7': {
            'title': 'Неделя силы',
            'description': 'Поддерживайте streak 7 дней',
            'icon': '💪',
            'xp_reward': 200,
            'condition': lambda user_data: TaskService.get_max_streak_from_user_data(user_data) >= 7
        },
        'streak_30': {
            'title': 'Мастер привычек',
            'description': 'Поддерживайте streak 30 дней',
            'icon': '💎',
            'xp_reward': 500,
            'condition': lambda user_data: TaskService.get_max_streak_from_user_data(user_data) >= 30
        },
        'streak_100': {
            'title': 'Легенда',
            'description': 'Поддерживайте streak 100 дней',
            'icon': '👑',
            'xp_reward': 1000,
            'condition': lambda user_data: TaskService.get_max_streak_from_user_data(user_data) >= 100
        },
        'tasks_10': {
            'title': 'Продуктивный',
            'description': 'Выполните 10 задач',
            'icon': '📈',
            'xp_reward': 100,
            'condition': lambda user_data: user_data.get("stats", {}).get("completed_tasks", 0) >= 10
        },
        'tasks_50': {
            'title': 'Энтузиаст',
            'description': 'Выполните 50 задач',
            'icon': '🏆',
            'xp_reward': 250,
            'condition': lambda user_data: user_data.get("stats", {}).get("completed_tasks", 0) >= 50
        },
        'tasks_100': {
            'title': 'Чемпион',
            'description': 'Выполните 100 задач',
            'icon': '🌟',
            'xp_reward': 500,
            'condition': lambda user_data: user_data.get("stats", {}).get("completed_tasks", 0) >= 100
        },
        'tasks_500': {
            'title': 'Мастер продуктивности',
            'description': 'Выполните 500 задач',
            'icon': '⭐',
            'xp_reward': 1000,
            'condition': lambda user_data: user_data.get("stats", {}).get("completed_tasks", 0) >= 500
        },
        'all_categories': {
            'title': 'Универсал',
            'description': 'Создайте задачи во всех категориях',
            'icon': '🌈',
            'xp_reward': 200,
            'condition': lambda user_data: TaskService.check_all_categories_used(user_data)
        },
        'perfect_week': {
            'title': 'Идеальная неделя',
            'description': 'Выполните все задачи 7 дней подряд',
            'icon': '✨',
            'xp_reward': 300,
            'condition': lambda user_data: TaskService.check_perfect_week(user_data)
        },
        'subtask_master': {
            'title': 'Мастер планирования',
            'description': 'Создайте 10 подзадач',
            'icon': '📋',
            'xp_reward': 150,
            'condition': lambda user_data: TaskService.count_total_subtasks(user_data) >= 10
        },
        'tag_organizer': {
            'title': 'Организатор',
            'description': 'Используйте 5 разных тегов',
            'icon': '🏷️',
            'xp_reward': 100,
            'condition': lambda user_data: TaskService.count_unique_tags(user_data) >= 5
        }
    }
    
    @classmethod
    def check_achievements(cls, user_data: Dict) -> List[str]:
        """Проверка новых достижений пользователя"""
        new_achievements = []
        user_achievements = user_data.get("achievements", [])
        
        for achievement_id, achievement_data in cls.ACHIEVEMENTS.items():
            if achievement_id not in user_achievements:
                try:
                    if achievement_data['condition'](user_data):
                        user_achievements.append(achievement_id)
                        new_achievements.append(achievement_id)
                        
                        # Добавляем XP за достижение
                        xp_reward = achievement_data.get('xp_reward', 50)
                        stats = user_data.setdefault("stats", {})
                        stats["total_xp"] = stats.get("total_xp", 0) + xp_reward
                        stats["daily_xp_earned"] = stats.get("daily_xp_earned", 0) + xp_reward
                        
                        # Пересчитываем уровень
                        TaskService._update_user_level(stats)
                        
                        logger.info(f"🏆 Пользователь {user_data.get('user_id')} получил достижение: {achievement_id} (+{xp_reward} XP)")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки достижения {achievement_id}: {e}")
        
        # Обновляем список достижений в данных пользователя
        user_data["achievements"] = user_achievements
        
        return new_achievements
    
    @classmethod
    def get_achievement_info(cls, achievement_id: str) -> Optional[Dict]:
        """Получить информацию о достижении"""
        return cls.ACHIEVEMENTS.get(achievement_id)
    
    @classmethod
    def get_achievements_progress(cls, user_data: Dict) -> Dict[str, Dict]:
        """Получить прогресс по всем достижениям"""
        progress = {}
        user_achievements = user_data.get("achievements", [])
        
        for achievement_id, achievement_data in cls.ACHIEVEMENTS.items():
            is_earned = achievement_id in user_achievements
            
            # Пытаемся определить прогресс для некоторых достижений
            current_progress = 0
            target = 1
            
            if "tasks_" in achievement_id:
                target = int(achievement_id.split("_")[1])
                current_progress = user_data.get("stats", {}).get("completed_tasks", 0)
            elif "streak_" in achievement_id:
                target = int(achievement_id.split("_")[1])
                current_progress = TaskService.get_max_streak_from_user_data(user_data)
            
            progress[achievement_id] = {
                "title": achievement_data["title"],
                "description": achievement_data["description"],
                "icon": achievement_data["icon"],
                "xp_reward": achievement_data["xp_reward"],
                "is_earned": is_earned,
                "progress": min(current_progress, target),
                "target": target,
                "progress_percentage": min((current_progress / target) * 100, 100) if target > 0 else 100
            }
        
        return progress

# ===== ОСНОВНОЙ СЕРВИС ЗАДАЧ =====

class TaskService:
    """
    Полный сервис для работы с задачами пользователей
    
    Возможности:
    - Создание, обновление, удаление задач
    - Управление выполнением и streak'ами
    - Работа с подзадачами и тегами
    - Система достижений и XP
    - Аналитика и статистика
    - Фильтрация и поиск задач
    """
    
    def __init__(self, data_service: DataService = None):
        self.data_service = data_service or get_data_service()
        logger.info("✅ TaskService инициализирован")
    
    # ===== ОСНОВНЫЕ МЕТОДЫ CRUD =====
    
    async def create_task(self, user_id: int, title: str, **kwargs) -> str:
        """Создать новую задачу"""
        try:
            # Получаем данные пользователя
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                user_data = self._create_empty_user_data(user_id)
            
            # Создаем задачу
            task = Task(
                task_id=str(uuid.uuid4()),
                user_id=user_id,
                title=title,
                description=kwargs.get("description"),
                category=kwargs.get("category", "personal"),
                priority=kwargs.get("priority", "medium"),
                difficulty=kwargs.get("difficulty", 1),
                estimated_time=kwargs.get("estimated_time"),
                tags=kwargs.get("tags", []),
                is_daily=kwargs.get("is_daily", True)
            )
            
            # Добавляем в данные пользователя
            tasks = user_data.setdefault("tasks", {})
            tasks[task.task_id] = task.to_dict()
            
            # Обновляем статистику
            stats = user_data.setdefault("stats", {})
            stats["total_tasks"] = stats.get("total_tasks", 0) + 1
            
            # Проверяем достижения
            new_achievements = AchievementSystem.check_achievements(user_data)
            
            # Сохраняем
            self.data_service.save_user_data(user_id, user_data)
            
            logger.info(f"✅ Создана задача {task.task_id} для пользователя {user_id}: {title}")
            
            return task.task_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания задачи для пользователя {user_id}: {e}")
            raise
    
    async def get_task(self, user_id: int, task_id: str) -> Optional[Task]:
        """Получить задачу по ID"""
        try:
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                return None
            
            tasks = user_data.get("tasks", {})
            task_data = tasks.get(task_id)
            
            if task_data:
                return Task.from_dict(task_data)
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения задачи {task_id} для пользователя {user_id}: {e}")
            return None
    
    async def get_user_tasks(self, user_id: int, status_filter: str = None) -> List[Task]:
        """Получить все задачи пользователя с фильтрацией"""
        try:
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                return []
            
            tasks = user_data.get("tasks", {})
            task_objects = []
            
            for task_data in tasks.values():
                task = Task.from_dict(task_data)
                
                # Применяем фильтр статуса
                if status_filter and task.status != status_filter:
                    continue
                
                task_objects.append(task)
            
            # Сортируем по приоритету и дате создания
            priority_order = {"high": 3, "medium": 2, "low": 1}
            task_objects.sort(
                key=lambda t: (
                    priority_order.get(t.priority, 2),
                    datetime.fromisoformat(t.created_at)
                ),
                reverse=True
            )
            
            return task_objects
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения задач пользователя {user_id}: {e}")
            return []
    
    async def update_task(self, user_id: int, task_id: str, **updates) -> bool:
        """Обновить задачу"""
        try:
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                return False
            
            tasks = user_data.get("tasks", {})
            if task_id not in tasks:
                return False
            
            task_data = tasks[task_id]
            
            # Обновляем поля
            for field, value in updates.items():
                if field in task_data:
                    task_data[field] = value
            
            # Сохраняем изменения
            self.data_service.save_user_data(user_id, user_data)
            
            logger.info(f"✅ Задача {task_id} обновлена для пользователя {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления задачи {task_id} для пользователя {user_id}: {e}")
            return False
    
    async def delete_task(self, user_id: int, task_id: str) -> bool:
        """Удалить задачу"""
        try:
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                return False
            
            tasks = user_data.get("tasks", {})
            if task_id not in tasks:
                return False
            
            # Удаляем задачу
            del tasks[task_id]
            
            # Обновляем статистику
            stats = user_data.setdefault("stats", {})
            stats["total_tasks"] = max(0, stats.get("total_tasks", 0) - 1)
            
            # Сохраняем изменения
            self.data_service.save_user_data(user_id, user_data)
            
            logger.info(f"🗑️ Задача {task_id} удалена для пользователя {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления задачи {task_id} для пользователя {user_id}: {e}")
            return False
    
    # ===== ВЫПОЛНЕНИЕ ЗАДАЧ =====
    
    async def complete_task(self, user_id: int, task_id: str, note: str = None, time_spent: int = None) -> bool:
        """Отметить задачу как выполненную"""
        try:
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                return False
            
            tasks = user_data.get("tasks", {})
            if task_id not in tasks:
                return False
            
            task_data = tasks[task_id]
            task = Task.from_dict(task_data)
            
            # Проверяем, не выполнена ли уже сегодня
            if task.is_completed_today():
                return False
            
            # Отмечаем как выполненную
            if task.mark_completed(note, time_spent):
                # Обновляем данные в хранилище
                tasks[task_id] = task.to_dict()
                
                # Обновляем статистику пользователя
                stats = user_data.setdefault("stats", {})
                stats["completed_tasks"] = stats.get("completed_tasks", 0) + 1
                stats["tasks_completed_today"] = stats.get("tasks_completed_today", 0) + 1
                
                # Добавляем XP
                xp_earned = task.xp_value
                stats["total_xp"] = stats.get("total_xp", 0) + xp_earned
                stats["daily_xp_earned"] = stats.get("daily_xp_earned", 0) + xp_earned
                
                # Обновляем уровень
                self._update_user_level(stats)
                
                # Обновляем максимальный streak
                current_streak = task.current_streak
                if current_streak > stats.get("longest_streak", 0):
                    stats["longest_streak"] = current_streak
                
                # Проверяем достижения
                new_achievements = AchievementSystem.check_achievements(user_data)
                
                # Сохраняем изменения
                self.data_service.save_user_data(user_id, user_data)
                
                logger.info(f"✅ Задача {task_id} выполнена пользователем {user_id} (+{xp_earned} XP, streak: {current_streak})")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения задачи {task_id} для пользователя {user_id}: {e}")
            return False
    
    async def uncomplete_task(self, user_id: int, task_id: str) -> bool:
        """Отменить выполнение задачи"""
        try:
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                return False
            
            tasks = user_data.get("tasks", {})
            if task_id not in tasks:
                return False
            
            task_data = tasks[task_id]
            task = Task.from_dict(task_data)
            
            # Проверяем, выполнена ли сегодня
            if not task.is_completed_today():
                return False
            
            # Отменяем выполнение
            if task.mark_uncompleted():
                # Обновляем данные в хранилище
                tasks[task_id] = task.to_dict()
                
                # Обновляем статистику пользователя
                stats = user_data.setdefault("stats", {})
                stats["completed_tasks"] = max(0, stats.get("completed_tasks", 0) - 1)
                stats["tasks_completed_today"] = max(0, stats.get("tasks_completed_today", 0) - 1)
                
                # Отнимаем XP
                xp_lost = task.xp_value
                stats["total_xp"] = max(0, stats.get("total_xp", 0) - xp_lost)
                stats["daily_xp_earned"] = max(0, stats.get("daily_xp_earned", 0) - xp_lost)
                
                # Пересчитываем уровень
                self._update_user_level(stats)
                
                # Сохраняем изменения
                self.data_service.save_user_data(user_id, user_data)
                
                logger.info(f"❌ Выполнение задачи {task_id} отменено для пользователя {user_id} (-{xp_lost} XP)")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка отмены выполнения задачи {task_id} для пользователя {user_id}: {e}")
            return False
    
    # ===== ПОДЗАДАЧИ =====
    
    async def add_subtask(self, user_id: int, task_id: str, subtitle: str) -> Optional[str]:
        """Добавить подзадачу"""
        try:
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                return None
            
            tasks = user_data.get("tasks", {})
            if task_id not in tasks:
                return None
            
            task_data = tasks[task_id]
            task = Task.from_dict(task_data)
            
            # Добавляем подзадачу
            subtask_id = task.add_subtask(subtitle)
            
            # Обновляем данные в хранилище
            tasks[task_id] = task.to_dict()
            
            # Сохраняем изменения
            self.data_service.save_user_data(user_id, user_data)
            
            logger.info(f"✅ Подзадача {subtask_id} добавлена к задаче {task_id} для пользователя {user_id}")
            return subtask_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления подзадачи для задачи {task_id} пользователя {user_id}: {e}")
            return None
    
    async def toggle_subtask(self, user_id: int, task_id: str, subtask_id: str) -> bool:
        """Переключить статус подзадачи"""
        try:
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                return False
            
            tasks = user_data.get("tasks", {})
            if task_id not in tasks:
                return False
            
            task_data = tasks[task_id]
            task = Task.from_dict(task_data)
            
            # Переключаем подзадачу
            if task.toggle_subtask(subtask_id):
                # Обновляем данные в хранилище
                tasks[task_id] = task.to_dict()
                
                # Сохраняем изменения
                self.data_service.save_user_data(user_id, user_data)
                
                logger.info(f"✅ Подзадача {subtask_id} переключена для задачи {task_id} пользователя {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка переключения подзадачи {subtask_id} для задачи {task_id} пользователя {user_id}: {e}")
            return False
    
    # ===== ПОИСК И ФИЛЬТРАЦИЯ =====
    
    async def search_tasks(self, user_id: int, query: str, filters: Dict = None) -> List[Task]:
        """Поиск задач по запросу и фильтрам"""
        try:
            all_tasks = await self.get_user_tasks(user_id)
            
            if not query and not filters:
                return all_tasks
            
            results = []
            query_lower = query.lower() if query else ""
            
            for task in all_tasks:
                match = True
                
                # Поиск по тексту
                if query:
                    text_match = (
                        query_lower in task.title.lower() or
                        (task.description and query_lower in task.description.lower()) or
                        any(query_lower in tag.lower() for tag in task.tags)
                    )
                    if not text_match:
                        match = False
                
                # Применяем фильтры
                if filters and match:
                    if "category" in filters and task.category != filters["category"]:
                        match = False
                    
                    if "priority" in filters and task.priority != filters["priority"]:
                        match = False
                    
                    if "status" in filters and task.status != filters["status"]:
                        match = False
                    
                    if "completed_today" in filters:
                        is_completed = task.is_completed_today()
                        if filters["completed_today"] != is_completed:
                            match = False
                    
                    if "min_streak" in filters and task.current_streak < filters["min_streak"]:
                        match = False
                    
                    if "has_subtasks" in filters:
                        has_subtasks = len(task.subtasks) > 0
                        if filters["has_subtasks"] != has_subtasks:
                            match = False
                
                if match:
                    results.append(task)
            
            logger.info(f"🔍 Найдено {len(results)} задач для пользователя {user_id} по запросу '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска задач для пользователя {user_id}: {e}")
            return []
    
    async def get_tasks_by_category(self, user_id: int) -> Dict[str, List[Task]]:
        """Получить задачи сгруппированные по категориям"""
        try:
            all_tasks = await self.get_user_tasks(user_id)
            
            categories = {}
            for task in all_tasks:
                category = task.category
                if category not in categories:
                    categories[category] = []
                categories[category].append(task)
            
            return categories
            
        except Exception as e:
            logger.error(f"❌ Ошибка группировки задач по категориям для пользователя {user_id}: {e}")
            return {}
    
    async def get_tasks_by_priority(self, user_id: int) -> Dict[str, List[Task]]:
        """Получить задачи сгруппированные по приоритету"""
        try:
            all_tasks = await self.get_user_tasks(user_id)
            
            priorities = {"high": [], "medium": [], "low": []}
            for task in all_tasks:
                priority = task.priority
                if priority in priorities:
                    priorities[priority].append(task)
            
            return priorities
            
        except Exception as e:
            logger.error(f"❌ Ошибка группировки задач по приоритету для пользователя {user_id}: {e}")
            return {}
    
    # ===== СТАТИСТИКА И АНАЛИТИКА =====
    
    async def get_user_task_stats(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику задач пользователя"""
        try:
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                return {}
            
            all_tasks = await self.get_user_tasks(user_id)
            active_tasks = [t for t in all_tasks if t.status == "active"]
            
            # Базовая статистика
            stats = {
                "total_tasks": len(all_tasks),
                "active_tasks": len(active_tasks),
                "completed_today": len([t for t in active_tasks if t.is_completed_today()]),
                "paused_tasks": len([t for t in all_tasks if t.status == "paused"]),
                "archived_tasks": len([t for t in all_tasks if t.status == "archived"])
            }
            
            # Статистика по категориям
            stats["by_category"] = {}
            for task in all_tasks:
                category = task.category
                if category not in stats["by_category"]:
                    stats["by_category"][category] = {"total": 0, "active": 0, "completed_today": 0}
                
                stats["by_category"][category]["total"] += 1
                if task.status == "active":
                    stats["by_category"][category]["active"] += 1
                    if task.is_completed_today():
                        stats["by_category"][category]["completed_today"] += 1
            
            # Статистика по приоритетам
            stats["by_priority"] = {}
            for priority in ["high", "medium", "low"]:
                priority_tasks = [t for t in active_tasks if t.priority == priority]
                stats["by_priority"][priority] = {
                    "total": len(priority_tasks),
                    "completed_today": len([t for t in priority_tasks if t.is_completed_today()])
                }
            
            # Статистика streak'ов
            streaks = [task.current_streak for task in active_tasks]
            if streaks:
                stats["streaks"] = {
                    "max": max(streaks),
                    "average": sum(streaks) / len(streaks),
                    "total_with_streak": len([s for s in streaks if s > 0])
                }
            else:
                stats["streaks"] = {"max": 0, "average": 0, "total_with_streak": 0}
            
            # Процент выполнения
            if active_tasks:
                stats["completion_rate_today"] = (stats["completed_today"] / len(active_tasks)) * 100
            else:
                stats["completion_rate_today"] = 0
            
            # Статистика подзадач
            total_subtasks = sum(len(task.subtasks) for task in all_tasks)
            completed_subtasks = sum(task.subtasks_completed_count for task in all_tasks)
            
            stats["subtasks"] = {
                "total": total_subtasks,
                "completed": completed_subtasks,
                "completion_rate": (completed_subtasks / total_subtasks * 100) if total_subtasks > 0 else 0
            }
            
            # Тренды за последние дни
            stats["weekly_trend"] = self._calculate_weekly_trend(all_tasks)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики задач для пользователя {user_id}: {e}")
            return {}
    
    def _calculate_weekly_trend(self, tasks: List[Task]) -> List[Dict]:
        """Рассчитать тренд выполнения за неделю"""
        try:
            trend = []
            today = date.today()
            
            for i in range(7):
                check_date = today - timedelta(days=i)
                check_date_str = check_date.isoformat()
                
                completed_count = 0
                total_active = 0
                
                for task in tasks:
                    # Проверяем, была ли задача активна в этот день
                    created_date = datetime.fromisoformat(task.created_at).date()
                    if created_date <= check_date:
                        total_active += 1
                        
                        # Проверяем выполнение
                        for completion in task.completions:
                            if completion.date == check_date_str and completion.completed:
                                completed_count += 1
                                break
                
                completion_rate = (completed_count / total_active * 100) if total_active > 0 else 0
                
                trend.append({
                    "date": check_date_str,
                    "completed": completed_count,
                    "total_active": total_active,
                    "completion_rate": completion_rate
                })
            
            return list(reversed(trend))  # От старых к новым
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета тренда: {e}")
            return []
    
    # ===== МАССОВЫЕ ОПЕРАЦИИ =====
    
    async def bulk_create_tasks(self, user_id: int, task_titles: List[str], default_category: str = "personal") -> List[str]:
        """Массовое создание задач"""
        try:
            created_task_ids = []
            
            for title in task_titles:
                if title.strip():
                    task_id = await self.create_task(
                        user_id=user_id,
                        title=title.strip(),
                        category=default_category
                    )
                    if task_id:
                        created_task_ids.append(task_id)
            
            logger.info(f"✅ Создано {len(created_task_ids)} задач для пользователя {user_id}")
            return created_task_ids
            
        except Exception as e:
            logger.error(f"❌ Ошибка массового создания задач для пользователя {user_id}: {e}")
            return []
    
    async def bulk_update_tasks(self, user_id: int, updates: Dict[str, Dict]) -> Dict[str, bool]:
        """Массовое обновление задач"""
        try:
            results = {}
            
            for task_id, update_data in updates.items():
                success = await self.update_task(user_id, task_id, **update_data)
                results[task_id] = success
            
            successful_updates = sum(1 for success in results.values() if success)
            logger.info(f"✅ Обновлено {successful_updates}/{len(updates)} задач для пользователя {user_id}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Ошибка массового обновления задач для пользователя {user_id}: {e}")
            return {}
    
    async def reset_user_tasks(self, user_id: int, archive: bool = True) -> bool:
        """Сброс всех задач пользователя"""
        try:
            user_data = self.data_service.get_user_data(user_id)
            if not user_data:
                return False
            
            if archive:
                # Архивируем вместо удаления
                tasks = user_data.get("tasks", {})
                for task_data in tasks.values():
                    task_data["status"] = "archived"
            else:
                # Полное удаление
                user_data["tasks"] = {}
                
                # Сбрасываем статистику
                stats = user_data.setdefault("stats", {})
                stats["total_tasks"] = 0
                stats["tasks_completed_today"] = 0
            
            # Сохраняем изменения
            self.data_service.save_user_data(user_id, user_data)
            
            action = "архивированы" if archive else "удалены"
            logger.info(f"🔄 Все задачи пользователя {user_id} {action}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сброса задач пользователя {user_id}: {e}")
            return False
    
    # ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====
    
    def _create_empty_user_data(self, user_id: int) -> Dict:
        """Создать пустые данные пользователя"""
        return {
            "user_id": user_id,
            "tasks": {},
            "stats": {
                "total_tasks": 0,
                "completed_tasks": 0,
                "current_streak": 0,
                "longest_streak": 0,
                "total_xp": 0,
                "level": 1,
                "tasks_completed_today": 0,
                "daily_xp_earned": 0,
                "registration_date": datetime.now().isoformat()
            },
            "achievements": [],
            "settings": {}
        }
    
    @staticmethod
    def _update_user_level(stats: Dict):
        """Обновить уровень пользователя на основе XP"""
        total_xp = stats.get("total_xp", 0)
        current_level = stats.get("level", 1)
        
        # Формула: level = floor(sqrt(total_xp / 100)) + 1
        import math
        new_level = math.floor(math.sqrt(total_xp / 100)) + 1
        new_level = max(1, new_level)  # Минимум 1 уровень
        
        if new_level != current_level:
            stats["level"] = new_level
            logger.info(f"🆙 Пользователь повысил уровень: {current_level} → {new_level}")
    
    @staticmethod
    def get_max_streak_from_user_data(user_data: Dict) -> int:
        """Получить максимальный streak из данных пользователя"""
        max_streak = 0
        tasks = user_data.get("tasks", {})
        
        for task_data in tasks.values():
            if task_data.get("status") == "active":
                task = Task.from_dict(task_data)
                if task.current_streak > max_streak:
                    max_streak = task.current_streak
        
        return max_streak
    
    @staticmethod
    def check_all_categories_used(user_data: Dict) -> bool:
        """Проверить использование всех категорий"""
        tasks = user_data.get("tasks", {})
        categories_used = set()
        
        for task_data in tasks.values():
            categories_used.add(task_data.get("category", "personal"))
        
        all_categories = {"work", "health", "learning", "personal", "finance"}
        return all_categories.issubset(categories_used)
    
    @staticmethod
    def check_perfect_week(user_data: Dict) -> bool:
        """Проверить идеальную неделю"""
        tasks = user_data.get("tasks", {})
        if not tasks:
            return False
        
        today = date.today()
        
        for i in range(7):
            check_date = today - timedelta(days=i)
            check_date_str = check_date.isoformat()
            
            daily_tasks = []
            daily_completed = []
            
            for task_data in tasks.values():
                if task_data.get("status") == "active":
                    # Проверяем, была ли задача активна в этот день
                    created_date = datetime.fromisoformat(task_data.get("created_at", "")).date()
                    if created_date <= check_date:
                        daily_tasks.append(task_data)
                        
                        # Проверяем выполнение
                        completions = task_data.get("completions", [])
                        for completion in completions:
                            if completion.get("date") == check_date_str and completion.get("completed"):
                                daily_completed.append(task_data)
                                break
            
            # Если в какой-то день не все задачи выполнены
            if len(daily_completed) != len(daily_tasks) or len(daily_tasks) == 0:
                return False
        
        return True
    
    @staticmethod
    def count_total_subtasks(user_data: Dict) -> int:
        """Подсчитать общее количество подзадач"""
        tasks = user_data.get("tasks", {})
        total_subtasks = 0
        
        for task_data in tasks.values():
            subtasks = task_data.get("subtasks", [])
            total_subtasks += len(subtasks)
        
        return total_subtasks
    
    @staticmethod
    def count_unique_tags(user_data: Dict) -> int:
        """Подсчитать количество уникальных тегов"""
        tasks = user_data.get("tasks", {})
        unique_tags = set()
        
        for task_data in tasks.values():
            tags = task_data.get("tags", [])
            unique_tags.update(tags)
        
        return len(unique_tags)

# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====

# Создаем глобальный экземпляр для использования в других модулях
_global_task_service = None

def get_task_service() -> TaskService:
    """Получить глобальный экземпляр TaskService"""
    global _global_task_service
    if _global_task_service is None:
        _global_task_service = TaskService()
    return _global_task_service

def initialize_task_service(data_service: DataService = None) -> TaskService:
    """Инициализация глобального TaskService"""
    global _global_task_service
    _global_task_service = TaskService(data_service)
    return _global_task_service
