# models/task.py

from dataclasses import dataclass, field
from typing import Optional, List
from models.enums import TaskCategory, TaskPriority

@dataclass
class SubTask:
    title: str
    completed: bool = False

@dataclass
class TaskData:
    id: int
    title: str
    category: TaskCategory = TaskCategory.OTHER
    priority: TaskPriority = TaskPriority.MEDIUM
    due: Optional[str] = None  # ISO дата или None
    completed: bool = False
    subtasks: List[SubTask] = field(default_factory=list)
