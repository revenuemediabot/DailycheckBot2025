from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from ..core.data_manager import DataManager
from ..dependencies import get_data_manager

router = APIRouter(prefix="/api/stats", tags=["statistics"])

@router.get("/overview")
async def get_overview_stats(
    data_manager: DataManager = Depends(get_data_manager)
):
    """Получить общую статистику системы"""
    
    users_stats = data_manager.get_users_stats()
    tasks_stats = data_manager.get_tasks_stats()
    
    # Дополнительная статистика
    all_users = data_manager.get_all_users()
    all_tasks = data_manager.get_all_tasks()
    
    # Активность за последние 24 часа
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    
    active_24h = 0
    new_24h = 0
    completed_24h = 0
    
    for user_data in all_users.values():
        # Активность за 24 часа
        last_activity = user_data.get('last_activity')
        if last_activity:
            try:
                last_date = datetime.fromisoformat(last_activity)
                if last_date >= yesterday:
                    active_24h += 1
            except:
                pass
        
        # Новые пользователи за 24 часа
        join_date = user_data.get('join_date')
        if join_date:
            try:
                join_datetime = datetime.fromisoformat(join_date)
                if join_datetime >= yesterday:
                    new_24h += 1
            except:
                pass
        
        # Выполненные задачи за 24 часа
        completed_tasks = user_data.get('completed_tasks', [])
        for task in completed_tasks:
            if isinstance(task, dict):
                completed_at = task.get('completed_at')
                if completed_at:
                    try:
                        completed_datetime = datetime.fromisoformat(completed_at)
                        if completed_datetime >= yesterday:
                            completed_24h += 1
                    except:
                        pass
    
    return {
        "users": {
            "total": users_stats["total_users"],
            "active": users_stats["active_users"],
            "new_today": users_stats["new_users_today"],
            "new_week": users_stats["new_users_week"],
            "active_24h": active_24h,
            "new_24h": new_24h,
            "avg_level": round(users_stats["avg_level"], 2)
        },
        "tasks": {
            "total": tasks_stats["total_tasks"],
            "completed": tasks_stats["completed_tasks"],
            "completion_rate": round(tasks_stats["completion_rate"], 2),
            "completed_24h": completed_24h,
            "avg_per_user": round(tasks_stats["avg_tasks_per_user"], 2)
        },
        "engagement": {
            "daily_active_rate": round((active_24h / max(users_stats["total_users"], 1)) * 100, 2),
            "task_completion_rate": round(tasks_stats["completion_rate"], 2),
            "user_retention": round((users_stats["active_users"] / max(users_stats["total_users"], 1)) * 100, 2)
        }
    }

@router.get("/users")
async def get_users_stats(
    period: str = Query("week", description="Период: day, week, month, year"),
    data_manager: DataManager = Depends(get_data_manager)
):
    """Получить детальную статистику по пользователям"""
    
    users_stats = data_manager.get_users_stats()
    
    # Определяем период для анализа
    period_days = {
        "day": 1,
        "week": 7,
        "month": 30,
        "year": 365
    }
    
    days = period_days.get(period, 7)
