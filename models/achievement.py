# models/achievement.py

from dataclasses import dataclass, field
from typing import List

@dataclass
class Achievement:
    id: int
    name: str
    description: str
    unlocked: bool = False
    unlock_date: Optional[str] = None

@dataclass
class Badge:
    name: str
    icon: str
    description: str
    achieved: bool = False
