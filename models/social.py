# models/social.py

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Friend:
    user_id: int
    username: str
    since: str  # дата добавления

@dataclass
class Challenge:
    id: int
    title: str
    description: str
    participants: List[int] = field(default_factory=list)
    completed_by: List[int] = field(default_factory=list)
    active: bool = True

@dataclass
class TeamChallenge:
    id: int
    title: str
    team_members: List[int]
    progress: dict = field(default_factory=dict)
    finished: bool = False
