# models/habit.py

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import date

@dataclass
class Habit:
    id: int
    title: str
    streak: int = 0
    last_completed: Optional[str] = None  # дата в формате YYYY-MM-DD
    calendar: List[str] = field(default_factory=list)  # список дней, когда привычка выполнена
