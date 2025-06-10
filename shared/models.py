from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

# Базовые перечисления
class TaskDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium" 
    HARD = "hard"

class TaskStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class UserRole(str, Enum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"

class NotificationType(str, Enum):
    TASK_COMPLETED = "task_completed"
    LEVEL_UP = "level_up"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    DAILY_REMINDER = "daily_reminder"
    SYSTEM_MESSAGE = "system_message"

# Базовые модели пользователей
class UserBase(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: str = "ru"
    is_bot: bool = False
    
    @validator('username')
    def validate_username(cls, v):
        if v and len(v) < 3:
            raise ValueError('Username должен быть не менее 3 символов')
        return v

class UserPreferences(BaseModel):
    language: str = "ru"
    notifications: bool = True
    daily_reminders: bool = True
    reminder_time: str = "09:00"  # HH:MM format
    timezone: str = "UTC"
    theme: str = "light"  # light, dark
    weekly_report: bool = True

class UserAchievement(BaseModel):
    achievement_id: str
    title: str
    description: str
    icon: str
    earned_at: datetime
    xp_bonus: int = 0
    
class UserStreak(BaseModel):
    current_streak: int = 0
    longest_streak: int = 0
    last_activity_date: Optional[str] = None
    streak_frozen: bool = False  # Заморозка стрика

class CompletedTask(BaseModel):
    task_id: str
    title: str
    category: str
    difficulty: TaskDifficulty
    xp_reward: int
    completed_at: datetime
    completion_time: Optional[int] = None  # время выполнения в секундах
    rating: Optional[int] = Field(None, ge=1, le=5)  # оценка задачи пользователем
    notes: Optional[str] = None

class UserStats(BaseModel):
    total_xp: int = 0
    current_level: int = 1
    tasks_completed: int = 0
    days_active: int = 0
    avg_tasks_per_day: float = 0.0
    favorite_category: Optional[str] = None
    total_time_spent: int = 0  # в секундах
    
class User(UserBase):
    user_id: str
    telegram_id: int
    level: int = 1
    xp: int = 0
    role: UserRole = UserRole.USER
    is_active: bool = True
    is_premium: bool = False
    
    # Временные данные
    join_date: datetime
    last_activity: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    # Геймификация
    completed_tasks: List[CompletedTask] = []
    achievements: List[UserAchievement] = []
    streak: UserStreak = UserStreak()
    daily_tasks_completed: int = 0
    weekly_tasks_completed: int = 0
    monthly_tasks_completed: int = 0
    
    # Настройки и предпочтения
    preferences: UserPreferences = UserPreferences()
    
    # Статистика
    stats: UserStats = UserStats()
    
    # Дополнительные данные
    referral_code: Optional[str] = None
    referred_by: Optional[str] = None
    custom_data: Dict[str, Any] = {}

# Базовые модели задач
class TaskBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    category: str = Field(..., min_length=2, max_length=50)
    difficulty: TaskDifficulty = TaskDifficulty.MEDIUM
    xp_reward: int = Field(10, ge=1, le=10000)
    
    @validator('title')
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError('Название задачи не может быть пустым')
        return v.strip()

class TaskRequirement(BaseModel):
    requirement_id: str
    description: str
    is_mandatory: bool = True
    verification_type: str = "manual"  # manual, automatic, file_upload, url_check

class TaskHint(BaseModel):
    hint_id: str
    content: str
    unlock_condition: Optional[str] = None  # условие для разблокировки подсказки
    xp_cost: int = 0  # стоимость подсказки в XP

class TaskReward(BaseModel):
    xp: int
    bonus_xp: int = 0
    items: List[str] = []  # виртуальные предметы
    achievement_id: Optional[str] = None
    
class Task(TaskBase):
    task_id: str
    is_active: bool = True
    is_featured: bool = False
    is_daily: bool = False
    is_weekly: bool = False
    
    # Временные ограничения
    time_limit: Optional[int] = None  # в минутах
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None
    
    # Зависимости и требования
    prerequisites: List[str] = []  # task_ids которые нужно выполнить
    requirements: List[TaskRequirement] = []
    hints: List[TaskHint] = []
    
    # Награды
    rewards: TaskReward = TaskReward(xp=10)
    
    # Метаданные
    tags: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    
    # Статистика
    completion_count: int = 0
    average_completion_time: Optional[float] = None
    success_rate: float = 100.0
    average_rating: Optional[float] = None
    
    # Дополнительные данные
    resources: List[str] = []  # ссылки на ресурсы
    examples: List[str] = []
    custom_data: Dict[str, Any] = {}

# Модели для системы уведомлений
class Notification(BaseModel):
    notification_id: str
    user_id: str
    type: NotificationType
    title: str
    message: str
    
    # Данные уведомления
    data: Dict[str, Any] = {}
    
    # Статус
    is_read: bool = False
    is_sent: bool = False
    
    # Временные метки
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    
    # Метаданные
    priority: int = 1  # 1-низкий, 2-средний, 3-высокий
    expires_at: Optional[datetime] = None

# Модели для аналитики
class DailyStats(BaseModel):
    date: str  # YYYY-MM-DD
    new_users: int = 0
    active_users: int = 0
    completed_tasks: int = 0
    total_xp_earned: int = 0
    avg_session_time: float = 0.0

class CategoryStats(BaseModel):
    category: str
    total_tasks: int
    completed_tasks: int
    completion_rate: float
    avg_xp_reward: float
    avg_completion_time: Optional[float] = None

class UserEngagement(BaseModel):
    user_id: str
    engagement_score: float  # 0-100
    last_active: datetime
    session_count: int
    avg_session_duration: float
    task_completion_rate: float
    streak_length: int

# Модели для системных настроек
class SystemSettings(BaseModel):
    # Базовые настройки
    bot_name: str = "TaskBot"
    bot_description: str = "Бот для выполнения задач"
    default_language: str = "ru"
    timezone: str = "UTC"
    
    # Геймификация
    xp_multiplier: float = 1.0
    level_up_threshold: int = 1000  # XP нужно для повышения уровня
    daily_task_limit: int = 10
    streak_bonus_multiplier: float = 1.2
    
    # Лимиты
    max_tasks_per_user: int = 1000
    max_notifications_per_day: int = 5
    task_time_limit_default: int = 60  # минут
    
    # Модерация
    auto_approve_tasks: bool = True
    require_task_verification: bool = False
    min_user_level_for_suggestions: int = 5
    
    # Интеграции
    enable_analytics: bool = True
    enable_notifications: bool = True
    enable_webhooks: bool = False
    
    # Дополнительные настройки
    custom_settings: Dict[str, Any] = {}

# Модели для API ответов
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[List[str]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
class PaginatedResponse(APIResponse):
    page: int = 1
    per_page: int = 20
    total: int = 0
    pages: int = 0

class UserListResponse(PaginatedResponse):
    data: List[User]

class TaskListResponse(PaginatedResponse):
    data: List[Task]

# Модели для создания/обновления
class CreateUserRequest(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: str = "ru"
    referral_code: Optional[str] = None

class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    preferences: Optional[UserPreferences] = None
    custom_data: Optional[Dict[str, Any]] = None

class CreateTaskRequest(TaskBase):
    prerequisites: List[str] = []
    requirements: List[TaskRequirement] = []
    hints: List[TaskHint] = []
    tags: List[str] = []
    resources: List[str] = []
    time_limit: Optional[int] = None
    available_from: Optional[datetime] = None
    available_until: Optional[datetime] = None

class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[TaskDifficulty] = None
    xp_reward: Optional[int] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    tags: Optional[List[str]] = None
    time_limit: Optional[int] = None

class CompleteTaskRequest(BaseModel):
    task_id: str
    completion_time: Optional[int] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None
    proof_urls: List[str] = []  # ссылки на доказательства выполнения

# Модели для экспорта данных
class UserExport(BaseModel):
    user_id: str
    username: Optional[str]
    level: int
    xp: int
    tasks_completed: int
    join_date: datetime
    last_activity: Optional[datetime]
    total_time_spent: int
    achievements_count: int
    current_streak: int

class TaskExport(BaseModel):
    task_id: str
    title: str
    category: str
    difficulty: TaskDifficulty
    xp_reward: int
    completion_count: int
    average_rating: Optional[float]
    created_at: datetime
    is_active: bool

# Модели для интеграций
class WebhookEvent(BaseModel):
    event_type: str
    event_id: str
    timestamp: datetime
    user_id: Optional[str] = None
    data: Dict[str, Any]

class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[Dict[str, Any]] = None
    callback_query: Optional[Dict[str, Any]] = None
    inline_query: Optional[Dict[str, Any]] = None

# Специальные модели для отчетов
class UserReport(BaseModel):
    user_id: str
    username: Optional[str]
    reporting_period: str  # daily, weekly, monthly
    
    # Статистика активности
    tasks_completed: int
    xp_earned: int
    time_spent: int
    days_active: int
    
    # Прогресс
    level_at_start: int
    level_at_end: int
    achievements_earned: int
    streak_data: UserStreak
    
    # Анализ категорий
    category_breakdown: Dict[str, int]
    favorite_difficulty: TaskDifficulty
    
    # Сравнение с другими
    rank_by_xp: int
    rank_by_tasks: int
    percentile: float

class SystemReport(BaseModel):
    report_period: str
    generated_at: datetime
    
    # Общая статистика
    total_users: int
    active_users: int
    new_users: int
    
    # Активность
    total_tasks_completed: int
    total_xp_distributed: int
    avg_tasks_per_user: float
    
    # Популярные категории
    top_categories: List[CategoryStats]
    
    # Тренды
    user_growth_rate: float
    task_completion_rate: float
    user_retention_rate: float
    
    # Геймификация
    avg_user_level: float
    total_achievements_earned: int
    longest_current_streak: int

# Константы и конфигурация
class GameConfig:
    # XP и уровни
    BASE_XP_PER_LEVEL = 1000
    XP_MULTIPLIER_PER_LEVEL = 1.1
    MAX_LEVEL = 100
    
    # Награды за сложность
    DIFFICULTY_MULTIPLIERS = {
        TaskDifficulty.EASY: 0.8,
        TaskDifficulty.MEDIUM: 1.0,
        TaskDifficulty.HARD: 1.5
    }
    
    # Бонусы за стрики
    STREAK_BONUSES = {
        7: 1.1,   # +10% за 7 дней
        14: 1.2,  # +20% за 14 дней
        30: 1.3,  # +30% за 30 дней
        60: 1.5,  # +50% за 60 дней
        100: 2.0  # +100% за 100 дней
    }
    
    # Достижения
    ACHIEVEMENT_THRESHOLDS = {
        'first_task': 1,
        'task_master': 10,
        'task_expert': 50,
        'task_legend': 100,
        'week_warrior': 7,  # 7 дней подряд
        'month_master': 30,  # 30 дней подряд
        'category_specialist': 25,  # 25 задач в одной категории
        'speed_demon': 1,  # задача за 5 минут
        'perfectionist': 10,  # 10 задач с оценкой 5
    }

# Утилитарные функции для валидации
def calculate_xp_for_level(level: int) -> int:
    """Вычисляет необходимое XP для достижения уровня"""
    if level <= 1:
        return 0
    
    total_xp = 0
    for l in range(2, level + 1):
        total_xp += int(GameConfig.BASE_XP_PER_LEVEL * (GameConfig.XP_MULTIPLIER_PER_LEVEL ** (l - 2)))
    
    return total_xp

def calculate_level_from_xp(xp: int) -> int:
    """Вычисляет уровень по количеству XP"""
    level = 1
    while level < GameConfig.MAX_LEVEL:
        required_xp = calculate_xp_for_level(level + 1)
        if xp < required_xp:
            break
        level += 1
    
    return level

def get_difficulty_multiplier(difficulty: TaskDifficulty) -> float:
    """Получает множитель XP для сложности задачи"""
    return GameConfig.DIFFICULTY_MULTIPLIERS.get(difficulty, 1.0)

def get_streak_multiplier(streak_days: int) -> float:
    """Получает множитель XP за стрик"""
    multiplier = 1.0
    for threshold, bonus in sorted(GameConfig.STREAK_BONUSES.items()):
        if streak_days >= threshold:
            multiplier = bonus
        else:
            break
    return multiplier
