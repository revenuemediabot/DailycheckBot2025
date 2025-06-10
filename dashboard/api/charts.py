from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from ..core.data_manager import DataManager
from ..dependencies import get_data_manager

router = APIRouter(prefix="/api/charts", tags=["charts"])

@router.get("/user-activity")
async def get_user_activity_chart(
    days: int = Query(30, ge=7, le=365, description="Количество дней для отображения"),
    data_manager: DataManager = Depends(get_data_manager)
):
    """Данные для графика активности пользователей"""
    
    activity_data = data_manager.get_daily_activity(days)
    
    return {
        "labels": [item["date"] for item in activity_data],
        "datasets": [
            {
                "label": "Новые пользователи",
                "data": [item["new_users"] for item in activity_data],
                "borderColor": "#3B82F6",
                "backgroundColor": "rgba(59, 130, 246, 0.1)",
                "tension": 0.4,
                "fill": True
            },
            {
                "label": "Активные пользователи",
                "data": [item["active_users"] for item in activity_data],
                "borderColor": "#10B981",
                "backgroundColor": "rgba(16, 185, 129, 0.1)",
                "tension": 0.4,
                "fill": True
            }
        ],
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Активность пользователей"
                },
                "legend": {
                    "position": "top"
                }
            },
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "ticks": {
                        "stepSize": 1
                    }
                }
            }
        }
    }

@router.get("/task-completion")
async def get_task_completion_chart(
    days: int = Query(30, ge=7, le=365, description="Количество дней для отображения"),
    data_manager: DataManager = Depends(get_data_manager)
):
    """Данные для графика выполнения задач"""
    
    activity_data = data_manager.get_daily_activity(days)
    
    # Вычисляем скользящее среднее для тренда
    moving_average = []
    window_size = 7  # 7-дневное скользящее среднее
    
    for i in range(len(activity_data)):
        if i < window_size - 1:
            moving_average.append(None)
        else:
            avg = sum(activity_data[j]["completed_tasks"] for j in range(i - window_size + 1, i + 1)) / window_size
            moving_average.append(round(avg, 1))
    
    return {
        "labels": [item["date"] for item in activity_data],
        "datasets": [
            {
                "label": "Выполненные задачи",
                "data": [item["completed_tasks"] for item in activity_data],
                "borderColor": "#F59E0B",
                "backgroundColor": "rgba(245, 158, 11, 0.1)",
                "tension": 0.4,
                "fill": True,
                "type": "line"
            },
            {
                "label": "Тренд (7 дней)",
                "data": moving_average,
                "borderColor": "#EF4444",
                "backgroundColor": "transparent",
                "borderWidth": 2,
                "borderDash": [5, 5],
                "tension": 0.4,
                "pointRadius": 0,
                "type": "line"
            }
        ],
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Выполнение задач по дням"
                },
                "legend": {
                    "position": "top"
                }
            },
            "scales": {
                "y": {
                    "beginAtZero": True
                }
            }
        }
    }

@router.get("/level-distribution")
async def get_level_distribution_chart(
    data_manager: DataManager = Depends(get_data_manager)
):
    """Данные для диаграммы распределения уровней пользователей"""
    
    users_stats = data_manager.get_users_stats()
    user_levels = users_stats["user_levels"]
    
    if not user_levels:
        return {
            "labels": [],
            "datasets": [],
            "message": "Нет данных о пользователях"
        }
    
    # Сортируем уровни
    sorted_levels = sorted(user_levels.keys())
    
    # Цвета для уровней
    colors = [
        "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", 
        "#9966FF", "#FF9F40", "#FF6384", "#C9CBCF",
        "#4BC0C0", "#36A2EB", "#FF6384", "#FFCE56"
    ]
    
    return {
        "labels": [f"Уровень {level}" for level in sorted_levels],
        "datasets": [
            {
                "data": [user_levels[level] for level in sorted_levels],
                "backgroundColor": colors[:len(sorted_levels)],
                "borderWidth": 2,
                "borderColor": "#fff"
            }
        ],
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Распределение пользователей по уровням"
                },
                "legend": {
                    "position": "right"
                }
            }
        }
    }

@router.get("/task-categories")
async def get_task_categories_chart(
    data_manager: DataManager = Depends(get_data_manager)
):
    """Данные для диаграммы категорий задач"""
    
    tasks_stats = data_manager.get_tasks_stats()
    categories = tasks_stats["task_categories"]
    
    if not categories:
        return {
            "labels": [],
            "datasets": [],
            "message": "Нет данных о категориях задач"
        }
    
    # Сортируем по популярности
    sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)
    
    colors = [
        "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", 
        "#9966FF", "#FF9F40", "#FF6384", "#C9CBCF"
    ]
    
    return {
        "labels": [cat[0] for cat in sorted_categories],
        "datasets": [
            {
                "label": "Количество задач",
                "data": [cat[1] for cat in sorted_categories],
                "backgroundColor": colors[:len(sorted_categories)],
                "borderColor": colors[:len(sorted_categories)],
                "borderWidth": 1
            }
        ],
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Распределение задач по категориям"
                }
            },
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "ticks": {
                        "stepSize": 1
                    }
                }
            }
        }
    }

@router.get("/xp-trends")
async def get_xp_trends_chart(
    days: int = Query(30, ge=7, le=365, description="Количество дней для отображения"),
    data_manager: DataManager = Depends(get_data_manager)
):
    """Данные для графика трендов XP"""
    
    all_users = data_manager.get_all_users()
    
    # Собираем данные по XP по дням
    daily_xp = defaultdict(int)
    cumulative_xp = defaultdict(int)
    
    for user_data in all_users.values():
        completed_tasks = user_data.get('completed_tasks', [])
        for task in completed_tasks:
            if isinstance(task, dict):
                completed_at = task.get('completed_at')
                xp_reward = task.get('xp_reward', 0)
                if completed_at:
                    try:
                        date = datetime.fromisoformat(completed_at).date().isoformat()
                        daily_xp[date] += xp_reward
                    except:
                        pass
    
    # Генерируем данные за последние N дней
    now = datetime.now()
    dates = []
    daily_values = []
    cumulative_total = 0
    cumulative_values = []
    
    for i in range(days):
        date = (now - timedelta(days=days-1-i)).date().isoformat()
        dates.append(date)
        
        day_xp = daily_xp.get(date, 0)
        daily_values.append(day_xp)
        
        cumulative_total += day_xp
        cumulative_values.append(cumulative_total)
    
    return {
        "labels": dates,
        "datasets": [
            {
                "label": "XP за день",
                "data": daily_values,
                "borderColor": "#8B5CF6",
                "backgroundColor": "rgba(139, 92, 246, 0.1)",
                "tension": 0.4,
                "fill": True,
                "yAxisID": "y"
            },
            {
                "label": "Накопительно XP",
                "data": cumulative_values,
                "borderColor": "#F59E0B",
                "backgroundColor": "transparent",
                "tension": 0.4,
                "borderWidth": 2,
                "yAxisID": "y1"
            }
        ],
        "options": {
            "responsive": True,
            "interaction": {
                "mode": "index",
                "intersect": False
            },
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Тренды заработанного XP"
                }
            },
            "scales": {
                "y": {
                    "type": "linear",
                    "display": True,
                    "position": "left",
                    "beginAtZero": True,
                    "title": {
                        "display": True,
                        "text": "XP за день"
                    }
                },
                "y1": {
                    "type": "linear",
                    "display": True,
                    "position": "right",
                    "beginAtZero": True,
                    "title": {
                        "display": True,
                        "text": "Накопительно XP"
                    },
                    "grid": {
                        "drawOnChartArea": False
                    }
                }
            }
        }
    }

@router.get("/user-engagement")
async def get_user_engagement_chart(
    data_manager: DataManager = Depends(get_data_manager)
):
    """Данные для диаграммы вовлеченности пользователей"""
    
    all_users = data_manager.get_all_users()
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    
    engagement_levels = {
        "Очень активные": 0,      # 10+ задач в неделю
        "Активные": 0,            # 3-9 задач в неделю
        "Умеренные": 0,           # 1-2 задачи в неделю
        "Неактивные": 0           # 0 задач в неделю
    }
    
    for user_data in all_users.values():
        completed_tasks = user_data.get('completed_tasks', [])
        weekly_tasks = 0
        
        for task in completed_tasks:
            if isinstance(task, dict):
                completed_at = task.get('completed_at')
                if completed_at:
                    try:
                        completed_datetime = datetime.fromisoformat(completed_at)
                        if completed_datetime >= week_ago:
                            weekly_tasks += 1
                    except:
                        pass
        
        if weekly_tasks >= 10:
            engagement_levels["Очень активные"] += 1
        elif weekly_tasks >= 3:
            engagement_levels["Активные"] += 1
        elif weekly_tasks >= 1:
            engagement_levels["Умеренные"] += 1
        else:
            engagement_levels["Неактивные"] += 1
    
    return {
        "labels": list(engagement_levels.keys()),
        "datasets": [
            {
                "data": list(engagement_levels.values()),
                "backgroundColor": [
                    "#10B981",  # Очень активные - зеленый
                    "#3B82F6",  # Активные - синий
                    "#F59E0B",  # Умеренные - желтый
                    "#EF4444"   # Неактивные - красный
                ],
                "borderWidth": 2,
                "borderColor": "#fff"
            }
        ],
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Уровни вовлеченности пользователей (за неделю)"
                },
                "legend": {
                    "position": "bottom"
                }
            }
        }
    }

@router.get("/completion-by-difficulty")
async def get_completion_by_difficulty_chart(
    data_manager: DataManager = Depends(get_data_manager)
):
    """Данные для графика выполнения задач по сложности"""
    
    all_users = data_manager.get_all_users()
    all_tasks = data_manager.get_all_tasks()
    
    difficulty_completion = {
        "easy": 0,
        "medium": 0,
        "hard": 0
    }
    
    difficulty_total = {
        "easy": 0,
        "medium": 0,
        "hard": 0
    }
    
    # Подсчитываем общее количество задач по сложности
    for task_data in all_tasks.values():
        difficulty = task_data.get('difficulty', 'medium')
        if difficulty in difficulty_total:
            difficulty_total[difficulty] += 1
    
    # Подсчитываем выполненные задачи по сложности
    for user_data in all_users.values():
        completed_tasks = user_data.get('completed_tasks', [])
        for task in completed_tasks:
            if isinstance(task, dict):
                task_id = task.get('task_id')
                if task_id in all_tasks:
                    difficulty = all_tasks[task_id].get('difficulty', 'medium')
                    if difficulty in difficulty_completion:
                        difficulty_completion[difficulty] += 1
    
    # Вычисляем проценты выполнения
    completion_rates = {}
    for difficulty in difficulty_completion:
        total = difficulty_total[difficulty]
        completed = difficulty_completion[difficulty]
        completion_rates[difficulty] = (completed / max(total, 1)) * 100
    
    difficulty_labels = {
        "easy": "Легкие",
        "medium": "Средние",
        "hard": "Сложные"
    }
    
    return {
        "labels": [difficulty_labels[d] for d in ["easy", "medium", "hard"]],
        "datasets": [
            {
                "label": "Выполнено",
                "data": [difficulty_completion[d] for d in ["easy", "medium", "hard"]],
                "backgroundColor": ["#10B981", "#F59E0B", "#EF4444"],
                "borderColor": ["#059669", "#D97706", "#DC2626"],
                "borderWidth": 1
            },
            {
                "label": "Всего задач",
                "data": [difficulty_total[d] for d in ["easy", "medium", "hard"]],
                "backgroundColor": ["rgba(16, 185, 129, 0.3)", "rgba(245, 158, 11, 0.3)", "rgba(239, 68, 68, 0.3)"],
                "borderColor": ["#059669", "#D97706", "#DC2626"],
                "borderWidth": 1
            }
        ],
        "options": {
            "responsive": True,
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Выполнение задач по уровню сложности"
                }
            },
            "scales": {
                "y": {
                    "beginAtZero": True
                }
            }
        }
    }

@router.get("/monthly-trends")
async def get_monthly_trends_chart(
    months: int = Query(12, ge=3, le=24, description="Количество месяцев для отображения"),
    data_manager: DataManager = Depends(get_data_manager)
):
    """Данные для графика месячных трендов"""
    
    all_users = data_manager.get_all_users()
    now = datetime.now()
    
    # Генерируем месяцы
    monthly_data = {}
    for i in range(months):
        month_date = now.replace(day=1) - timedelta(days=32 * i)
        month_key = month_date.strftime('%Y-%m')
        monthly_data[month_key] = {
            "new_users": 0,
            "completed_tasks": 0,
            "xp_earned": 0
        }
    
    # Анализируем данные пользователей
    for user_data in all_users.values():
        # Новые пользователи
        join_date = user_data.get('join_date')
        if join_date:
            try:
                join_month = datetime.fromisoformat(join_date).strftime('%Y-%m')
                if join_month in monthly_data:
                    monthly_data[join_month]["new_users"] += 1
            except:
                pass
        
        # Выполненные задачи и XP
        completed_tasks = user_data.get('completed_tasks', [])
        for task in completed_tasks:
            if isinstance(task, dict):
                completed_at = task.get('completed_at')
                if completed_at:
                    try:
                        completed_month = datetime.fromisoformat(completed_at).strftime('%Y-%m')
                        if completed_month in monthly_data:
                            monthly_data[completed_month]["completed_tasks"] += 1
                            monthly_data[completed_month]["xp_earned"] += task.get('xp_reward', 0)
                    except:
                        pass
    
    # Сортируем по месяцам
    sorted_months = sorted(monthly_data.keys())
    
    return {
        "labels": sorted_months,
        "datasets": [
            {
                "label": "Новые пользователи",
                "data": [monthly_data[month]["new_users"] for month in sorted_months],
                "borderColor": "#3B82F6",
                "backgroundColor": "rgba(59, 130, 246, 0.1)",
                "tension": 0.4,
                "yAxisID": "y"
            },
            {
                "label": "Выполненные задачи",
                "data": [monthly_data[month]["completed_tasks"] for month in sorted_months],
                "borderColor": "#10B981",
                "backgroundColor": "rgba(16, 185, 129, 0.1)",
                "tension": 0.4,
                "yAxisID": "y"
            },
            {
                "label": "Заработанный XP",
                "data": [monthly_data[month]["xp_earned"] for month in sorted_months],
                "borderColor": "#F59E0B",
                "backgroundColor": "rgba(245, 158, 11, 0.1)",
                "tension": 0.4,
                "yAxisID": "y1"
            }
        ],
        "options": {
            "responsive": True,
            "interaction": {
                "mode": "index",
                "intersect": False
            },
            "plugins": {
                "title": {
                    "display": True,
                    "text": "Месячные тренды активности"
                }
            },
            "scales": {
                "y": {
                    "type": "linear",
                    "display": True,
                    "position": "left",
                    "beginAtZero": True
                },
                "y1": {
                    "type": "linear",
                    "display": True,
                    "position": "right",
                    "beginAtZero": True,
                    "grid": {
                        "drawOnChartArea": False
                    }
                }
            }
        }
    }

@router.get("/real-time")
async def get_real_time_metrics(
    data_manager: DataManager = Depends(get_data_manager)
):
    """Данные для real-time метрик"""
    
    all_users = data_manager.get_all_users()
    now = datetime.now()
    
    # Метрики за последние часы
    hourly_activity = defaultdict(int)
    recent_completions = []
    
    for user_data in all_users.values():
        completed_tasks = user_data.get('completed_tasks', [])
        for task in completed_tasks:
            if isinstance(task, dict):
                completed_at = task.get('completed_at')
                if completed_at:
                    try:
                        completed_datetime = datetime.fromisoformat(completed_at)
                        hours_ago = (now - completed_datetime).total_seconds() / 3600
                        
                        if hours_ago <= 24:  # Последние 24 часа
                            hour_key = int(hours_ago)
                            hourly_activity[hour_key] += 1
                            
                            if hours_ago <= 1:  # Последний час
                                recent_completions.append({
                                    "task_title": task.get('title', 'Unknown'),
                                    "user": user_data.get('username', 'Unknown'),
                                    "xp": task.get('xp_reward', 0),
                                    "time_ago": f"{int(hours_ago * 60)} мин назад"
                                })
                    except:
                        pass
    
    # Активность по часам (последние 24 часа)
    hours_labels = []
    hours_data = []
    
    for i in range(24):
        hour_time = now - timedelta(hours=i)
        hours_labels.append(hour_time.strftime('%H:00'))
        hours_data.append(hourly_activity.get(i, 0))
    
    hours_labels.reverse()
    hours_data.reverse()
    
    return {
        "hourly_chart": {
            "labels": hours_labels,
            "datasets": [
                {
                    "label": "Выполнено задач",
                    "data": hours_data,
                    "borderColor": "#8B5CF6",
                    "backgroundColor": "rgba(139, 92, 246, 0.1)",
                    "tension": 0.4,
                    "fill": True
                }
            ],
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": "Активность за последние 24 часа"
                    }
                },
                "scales": {
                    "y": {
                        "beginAtZero": True
                    }
                }
            }
        },
        "recent_activity": recent_completions[:10],
        "current_metrics": {
            "active_now": len([u for u in all_users.values() 
                             if u.get('last_activity') and 
                             (now - datetime.fromisoformat(u['last_activity'])).total_seconds() < 300]),  # 5 минут
            "tasks_last_hour": sum(1 for completion in recent_completions),
            "total_users": len(all_users)
        }
    }
