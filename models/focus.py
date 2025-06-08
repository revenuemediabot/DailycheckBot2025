# models/focus.py

from dataclasses import dataclass
from typing import Optional
from models.enums import FocusType

@dataclass
class FocusSession:
    start_time: str
    end_time: Optional[str] = None
    focus_type: FocusType = FocusType.WORK
    note: Optional[str] = None
