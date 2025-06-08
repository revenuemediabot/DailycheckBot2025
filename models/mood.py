# models/mood.py

from dataclasses import dataclass
from typing import Optional
from models.enums import MoodLevel

@dataclass
class MoodEntry:
    date: str
    level: MoodLevel
    note: Optional[str] = None
