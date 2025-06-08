# models/user.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from models.task import TaskData
from models.habit import Habit
from models.mood import MoodEntry
from models.focus import FocusSession

@dataclass
class UserSettings:
    theme: str = "default"
    notifications: bool = True
    onboarding_passed: bool = False
    ai_mode: bool = True
    dry_mode: bool = False

@dataclass
class DailyStats:
    date: str
    tasks_done: int = 0
    habits_done: int = 0
    mood: Optional[str] = None
    streak: int = 0
    xp: int = 0

@dataclass
class DailyData:
    date: str
    tasks: List[TaskData] = field(default_factory=list)
    habits: List[Habit] = field(default_factory=list)
    mood: Optional[MoodEntry] = None
    focus_sessions: List[FocusSession] = field(default_factory=list)
