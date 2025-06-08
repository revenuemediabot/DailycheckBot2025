# models/enums.py

from enum import Enum, auto

class TaskCategory(Enum):
    WORK = "Работа"
    HEALTH = "Здоровье"
    LEARNING = "Образование"
    SOCIAL = "Социальное"
    PERSONAL = "Личное"
    OTHER = "Другое"

class TaskPriority(Enum):
    LOW = "Низкий"
    MEDIUM = "Средний"
    HIGH = "Высокий"

class MoodLevel(Enum):
    BAD = "😞 Плохо"
    NORMAL = "😐 Обычно"
    GOOD = "🙂 Хорошо"
    GREAT = "😃 Отлично"
    AWESOME = "🤩 Супер"

class FocusType(Enum):
    WORK = "Работа"
    STUDY = "Учёба"
    EXERCISE = "Тренировка"
    CUSTOM = "Свое"

class ThemeName(Enum):
    DEFAULT = "default"
    DARK = "dark"
    PINK = "pink"
    BLUE = "blue"

class StreakType(Enum):
    TASKS = auto()
    HABITS = auto()
    MOOD = auto()
