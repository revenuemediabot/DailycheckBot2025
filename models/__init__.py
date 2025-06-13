#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Bot v4.0 - Models Package
Data models and enums for the DailyCheck Bot

Author: AI Assistant  
Version: 4.0.0
Date: 2025-06-13
"""

from .enums import (
    TaskStatus,
    TaskPriority, 
    TaskCategory,
    UserTheme,
    AIRequestType
)

from .task import (
    TaskCompletion,
    Subtask,
    Task
)

from .user import (
    UserSettings,
    UserStats,
    User
)

from .social import (
    Reminder,
    Friend
)

__all__ = [
    # Enums
    'TaskStatus',
    'TaskPriority',
    'TaskCategory', 
    'UserTheme',
    'AIRequestType',
    
    # Task models
    'TaskCompletion',
    'Subtask',
    'Task',
    
    # User models
    'UserSettings',
    'UserStats', 
    'User',
    
    # Social models
    'Reminder',
    'Friend'
]
