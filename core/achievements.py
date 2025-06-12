#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Bot v4.0 - Enhanced Achievement System
Расширенная система достижений с прогрессом и уведомлениями

Автор: AI Assistant
Версия: 4.0.1
Дата: 2025-06-12
"""

import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Union, Any, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import logging

# Импорты из нашего проекта
from core.models import User, Task, TaskCategory, TaskPriority, ValidationError

logger = logging.getLogger(__name__)

# ===== ENUMS =====

class AchievementCategory(Enum):
    """Категории достижений"""
    PRODUCTIVITY = "productivity"
    STREAKS = "streaks"
    SOCIAL = "social"
    MILESTONES = "milestones"
    SPECIAL = "special"
    SEASONAL = "seasonal"
    CHALLENGES = "challenges"

class AchievementRarity(Enum):
    """Редкость достижений"""
    COMMON = "common"          # 90% пользователей могут получить
    UNCOMMON = "uncommon"      # 50% пользователей могут получить
    RARE = "rare"              # 20% пользователей могут получить
    EPIC = "epic"              # 5% пользователей могут получить
    LEGENDARY = "legendary"    # 1% пользователей могут получить

class AchievementType(Enum):
    """Типы достижений"""
    INSTANT = "instant"        # Проверяется мгновенно
    CUMULATIVE = "cumulative"  # Накопительное (прогресс)
    STREAK = "streak"          # Последовательное выполнение
    TIME_BASED = "time_based"  # Основано на времени
    CONDITIONAL = "conditional" # Сложные условия

# ===== DATA CLASSES =====

@dataclass
class AchievementProgress:
    """Прогресс выполнения достижения"""
    achievement_id: str
    user_id: int
    current_progress: int = 0
    max_progress: int = 100
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    completed: bool = False
    completed_at: Optional[str] = None
    
    @property
    def progress_percentage(self) -> float:
        """Процент выполнения"""
        if self.max_progress == 0:
            return 100.0
        return min(100.0, (self.current_progress / self.max_progress) * 100)
    
    @property
    def is_complete(self) -> bool:
        """Достижение завершено"""
        return self.completed or self.current_progress >= self.max_progress
    
    def update_progress(self, new_progress: int) -> bool:
        """Обновить прогресс"""
        old_progress = self.current_progress
        self.current_progress = max(0, min(self.max_progress, new_progress))
        self.last_updated = datetime.now().isoformat()
        
        # Проверяем завершение
        if not self.completed and self.current_progress >= self.max_progress:
            self.completed = True
            self.completed_at = datetime.now().isoformat()
            return True  # Достижение было завершено
        
        return self.current_progress != old_progress  # Прогресс изменился
    
    def add_progress(self, increment: int) -> bool:
        """Добавить к прогрессу"""
        return self.update_progress(self.current_progress + increment)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'achievement_id': self.achievement_id,
            'user_id': self.user_id,
            'current_progress': self.current_progress,
            'max_progress': self.max_progress,
            'started_at': self.started_at,
            'last_updated': self.last_updated,
            'completed': self.completed,
            'completed_at': self.completed_at,
            'progress_percentage': self.progress_percentage
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AchievementProgress":
        return cls(**data)

@dataclass
class AchievementDefinition:
    """Определение достижения"""
    achievement_id: str
    title: str
    description: str
    icon: str
    category: AchievementCategory
    rarity: AchievementRarity
    achievement_type: AchievementType
    xp_reward: int
    max_progress: int = 1
    hidden: bool = False  # Скрытое достижение
    prerequisites: List[str] = field(default_factory=list)  # ID других достижений
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Метаданные для сложных достижений
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def rarity_emoji(self) -> str:
        """Emoji для редкости"""
        rarity_emojis = {
            AchievementRarity.COMMON: "⚪",
            AchievementRarity.UNCOMMON: "🟢",
            AchievementRarity.RARE: "🔵",
            AchievementRarity.EPIC: "🟣",
            AchievementRarity.LEGENDARY: "🟡"
        }
        return rarity_emojis.get(self.rarity, "⚪")
    
    @property
    def category_emoji(self) -> str:
        """Emoji для категории"""
        category_emojis = {
            AchievementCategory.PRODUCTIVITY: "💼",
            AchievementCategory.STREAKS: "🔥",
            AchievementCategory.SOCIAL: "👥",
            AchievementCategory.MILESTONES: "🏆",
            AchievementCategory.SPECIAL: "⭐",
            AchievementCategory.SEASONAL: "🗓️",
            AchievementCategory.CHALLENGES: "⚔️"
        }
        return category_emojis.get(self.category, "🏅")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'achievement_id': self.achievement_id,
            'title': self.title,
            'description': self.description,
            'icon': self.icon,
            'category': self.category.value,
            'rarity': self.rarity.value,
            'achievement_type': self.achievement_type.value,
            'xp_reward': self.xp_reward,
            'max_progress': self.max_progress,
            'hidden': self.hidden,
            'prerequisites': self.prerequisites,
            'tags': self.tags,
            'created_at': self.created_at,
            'metadata': self.metadata
        }

# ===== ACHIEVEMENT CHECKERS =====

class AchievementChecker(ABC):
    """Базовый класс для проверки достижений"""
    
    @abstractmethod
    def check(self, user: User, context: Dict[str, Any] = None) -> bool:
        """Проверить условие достижения"""
        pass
    
    @abstractmethod
    def get_progress(self, user: User, context: Dict[str, Any] = None) -> Tuple[int, int]:
        """Получить прогресс (текущий, максимальный)"""
        pass

class SimpleCountChecker(AchievementChecker):
    """Проверка простого подсчета"""
    
    def __init__(self, target_count: int, value_getter: Callable[[User], int]):
        self.target_count = target_count
        self.value_getter = value_getter
    
    def check(self, user: User, context: Dict[str, Any] = None) -> bool:
        return self.value_getter(user) >= self.target_count
    
    def get_progress(self, user: User, context: Dict[str, Any] = None) -> Tuple[int, int]:
        current = min(self.target_count, self.value_getter(user))
        return current, self.target_count

class StreakChecker(AchievementChecker):
    """Проверка streak'ов"""
    
    def __init__(self, target_streak: int, streak_getter: Callable[[User], int]):
        self.target_streak = target_streak
        self.streak_getter = streak_getter
    
    def check(self, user: User, context: Dict[str, Any] = None) -> bool:
        return self.streak_getter(user) >= self.target_streak
    
    def get_progress(self, user: User, context: Dict[str, Any] = None) -> Tuple[int, int]:
        current = min(self.target_streak, self.streak_getter(user))
        return current, self.target_streak

class TimeBasedChecker(AchievementChecker):
    """Проверка на основе времени"""
    
    def __init__(self, days_required: int, condition_checker: Callable[[User, date], bool]):
        self.days_required = days_required
        self.condition_checker = condition_checker
    
    def check(self, user: User, context: Dict[str, Any] = None) -> bool:
        current_date = date.today()
        consecutive_days = 0
        
        for i in range(self.days_required * 2):  # Проверяем больший период
            check_date = current_date - timedelta(days=i)
            if self.condition_checker(user, check_date):
                consecutive_days += 1
                if consecutive_days >= self.days_required:
                    return True
            else:
                consecutive_days = 0
        
        return False
    
    def get_progress(self, user: User, context: Dict[str, Any] = None) -> Tuple[int, int]:
        current_date = date.today()
        consecutive_days = 0
        max_consecutive = 0
        
        for i in range(self.days_required * 2):
            check_date = current_date - timedelta(days=i)
            if self.condition_checker(user, check_date):
                consecutive_days += 1
                max_consecutive = max(max_consecutive, consecutive_days)
            else:
                consecutive_days = 0
        
        return min(max_consecutive, self.days_required), self.days_required

class ConditionalChecker(AchievementChecker):
    """Проверка сложных условий"""
    
    def __init__(self, condition_func: Callable[[User, Dict[str, Any]], bool],
                 progress_func: Optional[Callable[[User, Dict[str, Any]], Tuple[int, int]]] = None):
        self.condition_func = condition_func
        self.progress_func = progress_func
    
    def check(self, user: User, context: Dict[str, Any] = None) -> bool:
        return self.condition_func(user, context or {})
    
    def get_progress(self, user: User, context: Dict[str, Any] = None) -> Tuple[int, int]:
        if self.progress_func:
            return self.progress_func(user, context or {})
        return (1 if self.check(user, context) else 0, 1)

# ===== ACHIEVEMENT REGISTRY =====

class AchievementRegistry:
    """Реестр всех достижений"""
    
    def __init__(self):
        self.achievements: Dict[str, AchievementDefinition] = {}
        self.checkers: Dict[str, AchievementChecker] = {}
        self._load_default_achievements()
    
    def register_achievement(self, definition: AchievementDefinition, 
                           checker: AchievementChecker) -> None:
        """Зарегистрировать достижение"""
        self.achievements[definition.achievement_id] = definition
        self.checkers[definition.achievement_id] = checker
        logger.debug(f"Registered achievement: {definition.achievement_id}")
    
    def get_achievement(self, achievement_id: str) -> Optional[AchievementDefinition]:
        """Получить определение достижения"""
        return self.achievements.get(achievement_id)
    
    def get_checker(self, achievement_id: str) -> Optional[AchievementChecker]:
        """Получить проверщик достижения"""
        return self.checkers.get(achievement_id)
    
    def get_all_achievements(self) -> List[AchievementDefinition]:
        """Получить все достижения"""
        return list(self.achievements.values())
    
    def get_achievements_by_category(self, category: AchievementCategory) -> List[AchievementDefinition]:
        """Получить достижения по категории"""
        return [ach for ach in self.achievements.values() if ach.category == category]
    
    def get_achievements_by_rarity(self, rarity: AchievementRarity) -> List[AchievementDefinition]:
        """Получить достижения по редкости"""
        return [ach for ach in self.achievements.values() if ach.rarity == rarity]
    
    def get_visible_achievements(self) -> List[AchievementDefinition]:
        """Получить видимые достижения"""
        return [ach for ach in self.achievements.values() if not ach.hidden]
    
    def _load_default_achievements(self):
        """Загрузка стандартных достижений"""
        
        # ===== PRODUCTIVITY ACHIEVEMENTS =====
        
        # Базовые достижения по количеству задач
        self.register_achievement(
            AchievementDefinition(
                achievement_id="first_task",
                title="Первые шаги",
                description="Создайте свою первую задачу",
                icon="🎯",
                category=AchievementCategory.PRODUCTIVITY,
                rarity=AchievementRarity.COMMON,
                achievement_type=AchievementType.INSTANT,
                xp_reward=50
            ),
            SimpleCountChecker(1, lambda user: len(user.tasks))
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="tasks_10",
                title="Продуктивный",
                description="Выполните 10 задач",
                icon="📈",
                category=AchievementCategory.PRODUCTIVITY,
                rarity=AchievementRarity.COMMON,
                achievement_type=AchievementType.CUMULATIVE,
                xp_reward=100,
                max_progress=10
            ),
            SimpleCountChecker(10, lambda user: user.stats.completed_tasks)
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="tasks_50",
                title="Энтузиаст",
                description="Выполните 50 задач",
                icon="🏆",
                category=AchievementCategory.PRODUCTIVITY,
                rarity=AchievementRarity.UNCOMMON,
                achievement_type=AchievementType.CUMULATIVE,
                xp_reward=250,
                max_progress=50
            ),
            SimpleCountChecker(50, lambda user: user.stats.completed_tasks)
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="tasks_100",
                title="Чемпион",
                description="Выполните 100 задач",
                icon="🌟",
                category=AchievementCategory.PRODUCTIVITY,
                rarity=AchievementRarity.RARE,
                achievement_type=AchievementType.CUMULATIVE,
                xp_reward=500,
                max_progress=100
            ),
            SimpleCountChecker(100, lambda user: user.stats.completed_tasks)
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="tasks_500",
                title="Мастер продуктивности",
                description="Выполните 500 задач",
                icon="⭐",
                category=AchievementCategory.PRODUCTIVITY,
                rarity=AchievementRarity.EPIC,
                achievement_type=AchievementType.CUMULATIVE,
                xp_reward=1000,
                max_progress=500
            ),
            SimpleCountChecker(500, lambda user: user.stats.completed_tasks)
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="tasks_1000",
                title="Легенда продуктивности",
                description="Выполните 1000 задач",
                icon="👑",
                category=AchievementCategory.PRODUCTIVITY,
                rarity=AchievementRarity.LEGENDARY,
                achievement_type=AchievementType.CUMULATIVE,
                xp_reward=2000,
                max_progress=1000
            ),
            SimpleCountChecker(1000, lambda user: user.stats.completed_tasks)
        )
        
        # ===== STREAK ACHIEVEMENTS =====
        
        def get_max_streak(user: User) -> int:
            return max([task.current_streak for task in user.active_tasks.values()] + [0])
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="streak_3",
                title="Начинающий",
                description="Поддерживайте streak 3 дня",
                icon="🔥",
                category=AchievementCategory.STREAKS,
                rarity=AchievementRarity.COMMON,
                achievement_type=AchievementType.STREAK,
                xp_reward=100,
                max_progress=3
            ),
            StreakChecker(3, get_max_streak)
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="streak_7",
                title="Неделя силы",
                description="Поддерживайте streak 7 дней",
                icon="💪",
                category=AchievementCategory.STREAKS,
                rarity=AchievementRarity.UNCOMMON,
                achievement_type=AchievementType.STREAK,
                xp_reward=200,
                max_progress=7
            ),
            StreakChecker(7, get_max_streak)
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="streak_30",
                title="Мастер привычек",
                description="Поддерживайте streak 30 дней",
                icon="💎",
                category=AchievementCategory.STREAKS,
                rarity=AchievementRarity.RARE,
                achievement_type=AchievementType.STREAK,
                xp_reward=500,
                max_progress=30
            ),
            StreakChecker(30, get_max_streak)
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="streak_100",
                title="Легенда",
                description="Поддерживайте streak 100 дней",
                icon="👑",
                category=AchievementCategory.STREAKS,
                rarity=AchievementRarity.EPIC,
                achievement_type=AchievementType.STREAK,
                xp_reward=1000,
                max_progress=100
            ),
            StreakChecker(100, get_max_streak)
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="streak_365",
                title="Годовой воин",
                description="Поддерживайте streak 365 дней",
                icon="🏆",
                category=AchievementCategory.STREAKS,
                rarity=AchievementRarity.LEGENDARY,
                achievement_type=AchievementType.STREAK,
                xp_reward=3000,
                max_progress=365
            ),
            StreakChecker(365, get_max_streak)
        )
        
        # ===== LEVEL ACHIEVEMENTS =====
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="level_5",
                title="Растущий",
                description="Достигните 5 уровня",
                icon="⬆️",
                category=AchievementCategory.MILESTONES,
                rarity=AchievementRarity.COMMON,
                achievement_type=AchievementType.INSTANT,
                xp_reward=200
            ),
            SimpleCountChecker(5, lambda user: user.stats.level)
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="level_10",
                title="Опытный",
                description="Достигните 10 уровня",
                icon="🚀",
                category=AchievementCategory.MILESTONES,
                rarity=AchievementRarity.UNCOMMON,
                achievement_type=AchievementType.INSTANT,
                xp_reward=500
            ),
            SimpleCountChecker(10, lambda user: user.stats.level)
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="level_20",
                title="Эксперт",
                description="Достигните 20 уровня",
                icon="💫",
                category=AchievementCategory.MILESTONES,
                rarity=AchievementRarity.RARE,
                achievement_type=AchievementType.INSTANT,
                xp_reward=1000
            ),
            SimpleCountChecker(20, lambda user: user.stats.level)
        )
        
        # ===== SOCIAL ACHIEVEMENTS =====
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="social_butterfly",
                title="Общительный",
                description="Добавьте 5 друзей",
                icon="👥",
                category=AchievementCategory.SOCIAL,
                rarity=AchievementRarity.UNCOMMON,
                achievement_type=AchievementType.CUMULATIVE,
                xp_reward=150,
                max_progress=5
            ),
            SimpleCountChecker(5, lambda user: len(user.friends))
        )
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="social_network",
                title="Сетевик",
                description="Добавьте 10 друзей",
                icon="🌐",
                category=AchievementCategory.SOCIAL,
                rarity=AchievementRarity.RARE,
                achievement_type=AchievementType.CUMULATIVE,
                xp_reward=300,
                max_progress=10
            ),
            SimpleCountChecker(10, lambda user: len(user.friends))
        )
        
        # ===== SPECIAL ACHIEVEMENTS =====
        
        def check_perfect_week(user: User, context: Dict[str, Any] = None) -> bool:
            """Проверка идеальной недели"""
            if not user.tasks:
                return False
            
            today = date.today()
            active_tasks = [task for task in user.tasks.values() if task.status == "active"]
            
            if not active_tasks:
                return False
            
            # Проверяем последние 7 дней
            for i in range(7):
                check_date = today - timedelta(days=i)
                
                # Все активные задачи должны быть выполнены в этот день
                for task in active_tasks:
                    if not task.is_completed_on_date(check_date):
                        return False
            
            return True
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="perfect_week",
                title="Идеальная неделя",
                description="Выполните все задачи 7 дней подряд",
                icon="✨",
                category=AchievementCategory.SPECIAL,
                rarity=AchievementRarity.RARE,
                achievement_type=AchievementType.CONDITIONAL,
                xp_reward=300
            ),
            ConditionalChecker(check_perfect_week)
        )
        
        def check_early_bird(user: User, context: Dict[str, Any] = None) -> bool:
            """Проверка ранней пташки"""
            early_count = 0
            for task in user.tasks.values():
                for completion in task.completions:
                    if completion.completed:
                        try:
                            timestamp = datetime.fromisoformat(completion.timestamp)
                            if timestamp.hour < 9:
                                early_count += 1
                        except:
                            continue
            return early_count >= 10
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="early_bird",
                title="Ранняя пташка",
                description="Выполните 10 задач до 9 утра",
                icon="🌅",
                category=AchievementCategory.SPECIAL,
                rarity=AchievementRarity.UNCOMMON,
                achievement_type=AchievementType.CUMULATIVE,
                xp_reward=200,
                max_progress=10
            ),
            ConditionalChecker(
                check_early_bird,
                lambda user, context: (min(10, sum(1 for task in user.tasks.values() 
                                                 for completion in task.completions 
                                                 if completion.completed and 
                                                 datetime.fromisoformat(completion.timestamp).hour < 9)), 10)
            )
        )
        
        def check_night_owl(user: User, context: Dict[str, Any] = None) -> bool:
            """Проверка совы"""
            late_count = 0
            for task in user.tasks.values():
                for completion in task.completions:
                    if completion.completed:
                        try:
                            timestamp = datetime.fromisoformat(completion.timestamp)
                            if timestamp.hour >= 22:
                                late_count += 1
                        except:
                            continue
            return late_count >= 10
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="night_owl",
                title="Сова",
                description="Выполните 10 задач после 22:00",
                icon="🦉",
                category=AchievementCategory.SPECIAL,
                rarity=AchievementRarity.UNCOMMON,
                achievement_type=AchievementType.CUMULATIVE,
                xp_reward=200,
                max_progress=10
            ),
            ConditionalChecker(
                check_night_owl,
                lambda user, context: (min(10, sum(1 for task in user.tasks.values() 
                                                 for completion in task.completions 
                                                 if completion.completed and 
                                                 datetime.fromisoformat(completion.timestamp).hour >= 22)), 10)
            )
        )
        
        # ===== CATEGORY ACHIEVEMENTS =====
        
        for category in TaskCategory:
            category_name = category.value
            
            def make_category_checker(cat):
                def check_category_tasks(user: User) -> int:
                    return sum(1 for task in user.tasks.values() 
                             if task.category == cat and 
                             any(c.completed for c in task.completions))
                return check_category_tasks
            
            category_emojis = {
                "work": "💼",
                "health": "🏃",
                "learning": "📚",
                "personal": "👤",
                "finance": "💰"
            }
            
            self.register_achievement(
                AchievementDefinition(
                    achievement_id=f"category_{category_name}_10",
                    title=f"Специалист: {category_name.title()}",
                    description=f"Выполните 10 задач в категории '{category_name}'",
                    icon=category_emojis.get(category_name, "📋"),
                    category=AchievementCategory.PRODUCTIVITY,
                    rarity=AchievementRarity.COMMON,
                    achievement_type=AchievementType.CUMULATIVE,
                    xp_reward=150,
                    max_progress=10,
                    tags=[f"category_{category_name}"]
                ),
                SimpleCountChecker(10, make_category_checker(category_name))
            )
        
        # ===== SEASONAL ACHIEVEMENTS =====
        
        def check_new_year_resolution(user: User, context: Dict[str, Any] = None) -> bool:
            """Новогоднее решение - выполнить задачу 1 января"""
            today = date.today()
            if today.month == 1 and today.day == 1:
                return len(user.completed_tasks_today) > 0
            
            # Проверяем прошлые 1 января
            for task in user.tasks.values():
                for completion in task.completions:
                    if completion.completed:
                        comp_date = date.fromisoformat(completion.date)
                        if comp_date.month == 1 and comp_date.day == 1:
                            return True
            return False
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="new_year_resolution",
                title="Новогоднее решение",
                description="Выполните задачу 1 января",
                icon="🎆",
                category=AchievementCategory.SEASONAL,
                rarity=AchievementRarity.UNCOMMON,
                achievement_type=AchievementType.CONDITIONAL,
                xp_reward=250,
                hidden=True
            ),
            ConditionalChecker(check_new_year_resolution)
        )
        
        # ===== CHALLENGE ACHIEVEMENTS =====
        
        def check_marathon_challenge(user: User, context: Dict[str, Any] = None) -> bool:
            """Марафон - выполнить задачи 30 дней подряд"""
            if not user.tasks:
                return False
            
            today = date.today()
            consecutive_days = 0
            
            for i in range(60):  # Проверяем последние 60 дней
                check_date = today - timedelta(days=i)
                
                # Проверяем, есть ли выполненные задачи в этот день
                has_completed_tasks = any(
                    any(c.completed and c.date == check_date.isoformat() for c in task.completions)
                    for task in user.tasks.values()
                )
                
                if has_completed_tasks:
                    consecutive_days += 1
                    if consecutive_days >= 30:
                        return True
                else:
                    consecutive_days = 0
            
            return False
        
        self.register_achievement(
            AchievementDefinition(
                achievement_id="marathon_challenge",
                title="Марафонец",
                description="Выполняйте задачи 30 дней подряд",
                icon="🏃‍♂️",
                category=AchievementCategory.CHALLENGES,
                rarity=AchievementRarity.EPIC,
                achievement_type=AchievementType.CONDITIONAL,
                xp_reward=800
            ),
            ConditionalChecker(check_marathon_challenge)
        )
# ===== ПРОДОЛЖЕНИЕ core/achievements.py (Part 2/2) =====

# ===== ACHIEVEMENT MANAGER =====

class AchievementManager:
    """Менеджер системы достижений"""
    
    def __init__(self):
        self.registry = AchievementRegistry()
        self.user_progress: Dict[int, Dict[str, AchievementProgress]] = {}
        self.notification_callbacks: List[Callable] = []
        
        # Кэш для оптимизации
        self._last_check_cache: Dict[int, float] = {}
        self._achievement_cache: Dict[str, AchievementDefinition] = {}
        
        logger.info("Achievement Manager initialized")
    
    def add_notification_callback(self, callback: Callable) -> None:
        """Добавить callback для уведомлений о достижениях"""
        self.notification_callbacks.append(callback)
    
    async def check_achievements(self, user: User, context: Dict[str, Any] = None) -> List[str]:
        """Проверка новых достижений пользователя"""
        new_achievements = []
        context = context or {}
        
        try:
            # Получаем прогресс пользователя
            if user.user_id not in self.user_progress:
                self.user_progress[user.user_id] = {}
            
            user_progress = self.user_progress[user.user_id]
            
            # Проверяем каждое достижение
            for achievement_id, definition in self.registry.achievements.items():
                # Пропускаем уже полученные достижения
                if achievement_id in user.achievements:
                    continue
                
                # Проверяем предварительные условия
                if not self._check_prerequisites(user, definition):
                    continue
                
                # Получаем проверщик
                checker = self.registry.get_checker(achievement_id)
                if not checker:
                    continue
                
                try:
                    # Проверяем достижение
                    is_completed = checker.check(user, context)
                    current_progress, max_progress = checker.get_progress(user, context)
                    
                    # Обновляем прогресс
                    if achievement_id not in user_progress:
                        user_progress[achievement_id] = AchievementProgress(
                            achievement_id=achievement_id,
                            user_id=user.user_id,
                            max_progress=max_progress
                        )
                    
                    progress = user_progress[achievement_id]
                    progress_updated = progress.update_progress(current_progress)
                    
                    # Проверяем завершение
                    if is_completed and not progress.completed:
                        progress.completed = True
                        progress.completed_at = datetime.now().isoformat()
                        
                        # Добавляем достижение пользователю
                        user.add_achievement(achievement_id)
                        new_achievements.append(achievement_id)
                        
                        # Начисляем XP
                        xp_reward = definition.xp_reward
                        level_up = user.stats.add_xp(xp_reward, "achievement")
                        
                        logger.info(f"🏆 User {user.user_id} earned achievement: {achievement_id} (+{xp_reward} XP)")
                        
                        # Отправляем уведомления
                        await self._send_achievement_notification(user, definition, level_up)
                
                except Exception as e:
                    logger.error(f"Error checking achievement {achievement_id}: {e}")
            
            return new_achievements
            
        except Exception as e:
            logger.error(f"Error in check_achievements for user {user.user_id}: {e}")
            return []
    
    def _check_prerequisites(self, user: User, definition: AchievementDefinition) -> bool:
        """Проверка предварительных условий"""
        for prereq_id in definition.prerequisites:
            if prereq_id not in user.achievements:
                return False
        return True
    
    async def _send_achievement_notification(self, user: User, definition: AchievementDefinition, 
                                           level_up: bool = False) -> None:
        """Отправка уведомления о получении достижения"""
        for callback in self.notification_callbacks:
            try:
                await callback(user, definition, level_up)
            except Exception as e:
                logger.error(f"Achievement notification callback failed: {e}")
    
    def get_user_progress(self, user_id: int, achievement_id: Optional[str] = None) -> Union[Dict[str, AchievementProgress], Optional[AchievementProgress]]:
        """Получить прогресс пользователя"""
        if user_id not in self.user_progress:
            return {} if achievement_id is None else None
        
        user_progress = self.user_progress[user_id]
        
        if achievement_id:
            return user_progress.get(achievement_id)
        
        return user_progress
    
    def get_achievement_statistics(self) -> Dict[str, Any]:
        """Получить статистику достижений"""
        total_achievements = len(self.registry.achievements)
        total_users = len(self.user_progress)
        
        # Статистика по редкости
        rarity_stats = {}
        for rarity in AchievementRarity:
            achievements = self.registry.get_achievements_by_rarity(rarity)
            rarity_stats[rarity.value] = {
                'total': len(achievements),
                'earned_count': 0,
                'unique_earners': set()
            }
        
        # Подсчитываем заработанные достижения
        achievement_earners = {}
        for user_id, progress_dict in self.user_progress.items():
            for achievement_id, progress in progress_dict.items():
                if progress.completed:
                    if achievement_id not in achievement_earners:
                        achievement_earners[achievement_id] = 0
                    achievement_earners[achievement_id] += 1
                    
                    # Обновляем статистику по редкости
                    definition = self.registry.get_achievement(achievement_id)
                    if definition:
                        rarity_stats[definition.rarity.value]['earned_count'] += 1
                        rarity_stats[definition.rarity.value]['unique_earners'].add(user_id)
        
        # Преобразуем sets в counts
        for rarity_data in rarity_stats.values():
            rarity_data['unique_earners'] = len(rarity_data['unique_earners'])
        
        # Самые популярные достижения
        popular_achievements = sorted(
            achievement_earners.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Самые редкие достижения
        rare_achievements = [
            (achievement_id, count) for achievement_id, count in achievement_earners.items()
            if count <= max(1, total_users * 0.05)  # Менее 5% пользователей
        ]
        
        return {
            'total_achievements': total_achievements,
            'total_users_with_progress': total_users,
            'rarity_statistics': rarity_stats,
            'popular_achievements': popular_achievements,
            'rare_achievements': rare_achievements,
            'completion_rate': len(achievement_earners) / total_achievements if total_achievements > 0 else 0
        }
    
    def get_leaderboard(self, achievement_id: Optional[str] = None, 
                       category: Optional[AchievementCategory] = None,
                       limit: int = 10) -> List[Dict[str, Any]]:
        """Получить таблицу лидеров"""
        user_scores = {}
        
        # Подсчитываем очки для каждого пользователя
        for user_id, progress_dict in self.user_progress.items():
            score = 0
            achievement_count = 0
            
            for prog_achievement_id, progress in progress_dict.items():
                if not progress.completed:
                    continue
                
                definition = self.registry.get_achievement(prog_achievement_id)
                if not definition:
                    continue
                
                # Фильтрация по конкретному достижению
                if achievement_id and prog_achievement_id != achievement_id:
                    continue
                
                # Фильтрация по категории
                if category and definition.category != category:
                    continue
                
                # Начисляем очки на основе редкости
                rarity_multiplier = {
                    AchievementRarity.COMMON: 1,
                    AchievementRarity.UNCOMMON: 2,
                    AchievementRarity.RARE: 3,
                    AchievementRarity.EPIC: 5,
                    AchievementRarity.LEGENDARY: 10
                }.get(definition.rarity, 1)
                
                score += definition.xp_reward * rarity_multiplier
                achievement_count += 1
            
            if score > 0:
                user_scores[user_id] = {
                    'user_id': user_id,
                    'score': score,
                    'achievement_count': achievement_count
                }
        
        # Сортируем и ограничиваем
        leaderboard = sorted(
            user_scores.values(),
            key=lambda x: (x['score'], x['achievement_count']),
            reverse=True
        )
        
        return leaderboard[:limit]
    
    def get_achievements_summary(self, user: User) -> Dict[str, Any]:
        """Получить сводку достижений пользователя"""
        user_achievements = set(user.achievements)
        all_achievements = self.registry.get_visible_achievements()
        
        # Статистика по категориям
        category_stats = {}
        for category in AchievementCategory:
            category_achievements = self.registry.get_achievements_by_category(category)
            earned = sum(1 for ach in category_achievements if ach.achievement_id in user_achievements)
            total = len(category_achievements)
            
            category_stats[category.value] = {
                'earned': earned,
                'total': total,
                'percentage': (earned / total * 100) if total > 0 else 0
            }
        
        # Статистика по редкости
        rarity_stats = {}
        for rarity in AchievementRarity:
            rarity_achievements = self.registry.get_achievements_by_rarity(rarity)
            earned = sum(1 for ach in rarity_achievements if ach.achievement_id in user_achievements)
            total = len(rarity_achievements)
            
            rarity_stats[rarity.value] = {
                'earned': earned,
                'total': total,
                'percentage': (earned / total * 100) if total > 0 else 0
            }
        
        # Прогресс незавершенных достижений
        in_progress = []
        if user.user_id in self.user_progress:
            for achievement_id, progress in self.user_progress[user.user_id].items():
                if not progress.completed and progress.current_progress > 0:
                    definition = self.registry.get_achievement(achievement_id)
                    if definition and not definition.hidden:
                        in_progress.append({
                            'achievement_id': achievement_id,
                            'title': definition.title,
                            'progress': progress.current_progress,
                            'max_progress': progress.max_progress,
                            'percentage': progress.progress_percentage
                        })
        
        # Сортируем по проценту выполнения
        in_progress.sort(key=lambda x: x['percentage'], reverse=True)
        
        # Рекомендации (ближайшие к завершению)
        recommendations = in_progress[:5]
        
        return {
            'total_earned': len(user_achievements),
            'total_available': len(all_achievements),
            'completion_percentage': (len(user_achievements) / len(all_achievements) * 100) if all_achievements else 0,
            'category_stats': category_stats,
            'rarity_stats': rarity_stats,
            'in_progress': in_progress,
            'recommendations': recommendations
        }
    
    def format_achievement_message(self, achievement_id: str, user: User, level_up: bool = False) -> str:
        """Форматирование сообщения о достижении"""
        definition = self.registry.get_achievement(achievement_id)
        if not definition:
            return "🏆 **Новое достижение получено!**"
        
        message = f"""🏆 **Новое достижение!**

{definition.icon} **{definition.title}**
{definition.description}

{definition.rarity_emoji} Редкость: {definition.rarity.value.title()}
{definition.category_emoji} Категория: {definition.category.value.title()}
💫 +{definition.xp_reward} XP"""
        
        if level_up:
            message += f"\n🆙 **Уровень повышен до {user.stats.level}!**"
            message += f"\n⭐ {user.stats.get_level_title()}"
        
        # Добавляем прогресс до следующего уровня
        message += f"\n📊 Прогресс: {user.stats.level_progress:.1f}% до следующего уровня"
        
        return message
    
    def format_achievements_list(self, user: User, category: Optional[AchievementCategory] = None,
                               show_hidden: bool = False) -> str:
        """Форматирование списка достижений"""
        user_achievements = set(user.achievements)
        
        if category:
            achievements = self.registry.get_achievements_by_category(category)
            title = f"🏆 **Достижения: {category.value.title()}**"
        else:
            achievements = self.registry.get_all_achievements()
            title = "🏆 **Все достижения**"
        
        if not show_hidden:
            achievements = [ach for ach in achievements if not ach.hidden]
        
        earned_count = sum(1 for ach in achievements if ach.achievement_id in user_achievements)
        total_count = len(achievements)
        
        message = f"{title}\n\n📊 Прогресс: {earned_count}/{total_count} ({(earned_count/total_count*100):.1f}%)\n\n"
        
        # Группируем по статусу
        earned_achievements = []
        available_achievements = []
        
        for achievement in achievements:
            if achievement.achievement_id in user_achievements:
                earned_achievements.append(achievement)
            else:
                available_achievements.append(achievement)
        
        # Полученные достижения
        if earned_achievements:
            message += "✅ **Получено:**\n"
            for ach in sorted(earned_achievements, key=lambda x: x.rarity.value):
                message += f"{ach.rarity_emoji} {ach.icon} {ach.title}\n"
            message += "\n"
        
        # Доступные достижения (первые 8)
        if available_achievements:
            message += "🎯 **Доступно:**\n"
            
            # Показываем ближайшие к завершению
            progress_data = []
            if user.user_id in self.user_progress:
                for ach in available_achievements:
                    progress = self.user_progress[user.user_id].get(ach.achievement_id)
                    if progress and progress.current_progress > 0:
                        progress_data.append((ach, progress.progress_percentage))
                    else:
                        progress_data.append((ach, 0))
            
            # Сортируем по прогрессу
            progress_data.sort(key=lambda x: x[1], reverse=True)
            
            for ach, progress_pct in progress_data[:8]:
                progress_info = f" ({progress_pct:.0f}%)" if progress_pct > 0 else ""
                message += f"{ach.rarity_emoji} {ach.icon} {ach.title}{progress_info}\n"
                message += f"   {ach.description}\n\n"
            
            if len(available_achievements) > 8:
                message += f"... и еще {len(available_achievements) - 8} достижений"
        
        return message
    
    def export_user_achievements(self, user: User) -> Dict[str, Any]:
        """Экспорт достижений пользователя"""
        earned_achievements = []
        progress_data = []
        
        for achievement_id in user.achievements:
            definition = self.registry.get_achievement(achievement_id)
            if definition:
                earned_achievements.append({
                    'achievement_id': achievement_id,
                    'title': definition.title,
                    'description': definition.description,
                    'category': definition.category.value,
                    'rarity': definition.rarity.value,
                    'xp_reward': definition.xp_reward,
                    'earned_at': None  # TODO: добавить время получения
                })
        
        if user.user_id in self.user_progress:
            for achievement_id, progress in self.user_progress[user.user_id].items():
                definition = self.registry.get_achievement(achievement_id)
                if definition:
                    progress_data.append({
                        'achievement_id': achievement_id,
                        'title': definition.title,
                        'current_progress': progress.current_progress,
                        'max_progress': progress.max_progress,
                        'percentage': progress.progress_percentage,
                        'completed': progress.completed,
                        'started_at': progress.started_at,
                        'completed_at': progress.completed_at
                    })
        
        summary = self.get_achievements_summary(user)
        
        return {
            'user_id': user.user_id,
            'export_date': datetime.now().isoformat(),
            'summary': summary,
            'earned_achievements': earned_achievements,
            'progress_data': progress_data
        }

# ===== NOTIFICATION SYSTEM =====

class AchievementNotificationManager:
    """Менеджер уведомлений о достижениях"""
    
    def __init__(self):
        self.notification_queue: List[Dict[str, Any]] = []
        self.batch_notifications: Dict[int, List[str]] = {}  # user_id -> achievement_ids
        self.batch_timeout = 5.0  # секунд
        
    async def queue_notification(self, user: User, achievement_id: str, level_up: bool = False) -> None:
        """Добавить уведомление в очередь"""
        notification = {
            'user': user,
            'achievement_id': achievement_id,
            'level_up': level_up,
            'timestamp': time.time()
        }
        
        self.notification_queue.append(notification)
        
        # Если это пакетное уведомление, добавляем в пакет
        if user.user_id not in self.batch_notifications:
            self.batch_notifications[user.user_id] = []
            
            # Запускаем таймер для отправки пакета
            asyncio.create_task(self._send_batch_after_timeout(user.user_id))
        
        self.batch_notifications[user.user_id].append(achievement_id)
    
    async def _send_batch_after_timeout(self, user_id: int) -> None:
        """Отправить пакет уведомлений после таймаута"""
        await asyncio.sleep(self.batch_timeout)
        
        if user_id in self.batch_notifications:
            achievement_ids = self.batch_notifications.pop(user_id)
            
            # Найдем соответствующие уведомления
            notifications = [
                notif for notif in self.notification_queue
                if notif['user'].user_id == user_id and notif['achievement_id'] in achievement_ids
            ]
            
            if notifications:
                await self._send_batch_notification(notifications)
                
                # Удаляем отправленные уведомления из очереди
                for notif in notifications:
                    if notif in self.notification_queue:
                        self.notification_queue.remove(notif)
    
    async def _send_batch_notification(self, notifications: List[Dict[str, Any]]) -> None:
        """Отправить пакетное уведомление"""
        if not notifications:
            return
        
        user = notifications[0]['user']
        
        if len(notifications) == 1:
            # Одиночное уведомление
            await self._send_single_notification(notifications[0])
        else:
            # Пакетное уведомление
            achievement_titles = []
            total_xp = 0
            level_up = any(notif['level_up'] for notif in notifications)
            
            # Собираем информацию
            for notif in notifications:
                # Здесь нужно получить definition из registry
                # achievement_titles.append(definition.title)
                # total_xp += definition.xp_reward
                pass
            
            message = f"🎉 **Получено {len(notifications)} достижений!**\n\n"
            message += "🏆 " + "\n🏆 ".join(achievement_titles)
            message += f"\n\n💫 Общий XP: +{total_xp}"
            
            if level_up:
                message += f"\n🆙 **Уровень повышен до {user.stats.level}!**"
            
            # Здесь должна быть отправка сообщения пользователю
            logger.info(f"Batch achievement notification for user {user.user_id}: {len(notifications)} achievements")
    
    async def _send_single_notification(self, notification: Dict[str, Any]) -> None:
        """Отправить одиночное уведомление"""
        user = notification['user']
        achievement_id = notification['achievement_id']
        level_up = notification['level_up']
        
        # Здесь должна быть отправка сообщения пользователю
        logger.info(f"Single achievement notification for user {user.user_id}: {achievement_id}")

# ===== CONVENIENCE FUNCTIONS =====

def create_achievement_manager() -> AchievementManager:
    """Создать менеджер достижений"""
    return AchievementManager()

async def check_user_achievements(user: User, manager: Optional[AchievementManager] = None,
                                context: Dict[str, Any] = None) -> List[str]:
    """Быстрая проверка достижений пользователя"""
    if not manager:
        manager = create_achievement_manager()
    
    return await manager.check_achievements(user, context)

def format_achievement_for_display(achievement_id: str, user: User, 
                                 manager: Optional[AchievementManager] = None) -> str:
    """Форматирование достижения для отображения"""
    if not manager:
        manager = create_achievement_manager()
    
    return manager.format_achievement_message(achievement_id, user)

# ===== EXPORT =====

__all__ = [
    # Enums
    'AchievementCategory',
    'AchievementRarity', 
    'AchievementType',
    
    # Data classes
    'AchievementProgress',
    'AchievementDefinition',
    
    # Checkers
    'AchievementChecker',
    'SimpleCountChecker',
    'StreakChecker',
    'TimeBasedChecker',
    'ConditionalChecker',
    
    # Core components
    'AchievementRegistry',
    'AchievementManager',
    'AchievementNotificationManager',
    
    # Convenience functions
    'create_achievement_manager',
    'check_user_achievements',
    'format_achievement_for_display'
]
