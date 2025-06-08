# models/analytics.py

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class AnalyticsData:
    dates: List[str] = field(default_factory=list)
    tasks_done: List[int] = field(default_factory=list)
    habits_done: List[int] = field(default_factory=list)
    mood_history: List[str] = field(default_factory=list)
    streaks: List[int] = field(default_factory=list)
    xp: List[int] = field(default_factory=list)

@dataclass
class ReflectionEntry:
    date: str
    positives: str
    improvements: str
    notes: Optional[str] = None
