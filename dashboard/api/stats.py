from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
from collections import defaultdict

from ..core.data_manager import DataManager
from ..dependencies import get_data_manager

router = APIRouter(prefix="/api/stats", tags=["statistics"])

@router.get("/overview", response_model=Dict[str, Any])
async def get_overview_stats(
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить общую статистику для главной страницы дашборда
    """
    try:
        overview = data_manager.get_overview_stats()
        
        # Добавляем KPI метрики
        kpi_metrics = _calculate_kpi_metrics(data_manager)
        overview["kpi_metrics"] = kpi_metrics
        
        # Добавляем тренды
        trends = _calculate_trends(data_manager)
        overview["trends"] = trends
        
        return overview
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения общей статистики: {str(e)}")

def _calculate_kpi_metrics(data_manager: DataManager) -> Dict[str, Any]:
    """Вычислить ключевые показатели эффективности"""
    users = data_manager.get_all_users()
    tasks = data_manager.get_all_tasks()
    
    # Основные KPI
    total_users = len(users)
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks.values() if t.get("status") == "completed"])
    total_points = sum(u.get("points", 0) for u in users.values())
    
    # Активность за последние 24 часа
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    
    active_users_24h = 0
    new_users_24h = 0
    completed_tasks_24h = 0
    
    for user in users.values():
        if user.get("last_activity"):
            try:
                last_activity = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00'))
                if last_activity >= yesterday:
                    active_users_24h += 1
            except:
                pass
        
        if user.get("created_at"):
            try:
                created = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00'))
                if created >= yesterday:
                    new_users_24h += 1
            except:
                pass
    
    for task in tasks.values():
        if task.get("completed_at"):
            try:
                completed = datetime.fromisoformat(task["completed_at"].replace('Z', '+00:00'))
                if completed >= yesterday:
                    completed_tasks_24h += 1
            except:
                pass
    
    # Показатели эффективности
    completion_rate = (completed_tasks / max(total_tasks, 1)) * 100
    avg_points_per_user = total_points / max(total_users, 1)
    user_engagement = (active_users_24h / max(total_users, 1)) * 100
    
    return {
        "total_users": total_users,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "total_points": total_points,
        "active_users_24h": active_users_24h,
        "new_users_24h": new_users_24h,
        "completed_tasks_24h": completed_tasks_24h,
        "completion_rate": round(completion_rate, 2),
        "avg_points_per_user": round(avg_points_per_user, 2),
        "user_engagement_rate": round(user_engagement, 2)
    }

def _calculate_trends(data_manager: DataManager) -> Dict[str, Any]:
    """Вычислить тренды для различных метрик"""
    daily_stats = data_manager.get_daily_stats(30)
    
    if len(daily_stats) < 2:
        return {"error": "Недостаточно данных для расчета трендов"}
    
    dates = sorted(daily_stats.keys())
    
    # Тренды пользователей
    users_trend = _calculate_trend([daily_stats[date]["new_users"] for date in dates])
    
    # Тренды задач
    tasks_trend = _calculate_trend([daily_stats[date]["completed_tasks"] for date in dates])
    
    # Тренды очков
    points_trend = _calculate_trend([daily_stats[date]["points_earned"] for date in dates])
    
    # Тренды активности
    activity_trend = _calculate_trend([daily_stats[date]["active_users"] for date in dates])
    
    return {
        "users": users_trend,
        "tasks": tasks_trend,
        "points": points_trend,
        "activity": activity_trend,
        "period_days": len(dates)
    }

def _calculate_trend(values: List[int]) -> Dict[str, Any]:
    """Вычислить тренд для списка значений"""
    if len(values) < 2:
        return {"direction": "stable", "percentage": 0, "absolute": 0}
    
    # Сравниваем последние 7 дней с предыдущими 7 днями
    if len(values) >= 14:
        recent_avg = sum(values[-7:]) / 7
        previous_avg = sum(values[-14:-7]) / 7
    else:
        recent_avg = sum(values[len(values)//2:]) / max(len(values)//2, 1)
        previous_avg = sum(values[:len(values)//2]) / max(len(values)//2, 1)
    
    if previous_avg == 0:
        if recent_avg > 0:
            return {"direction": "up", "percentage": 100, "absolute": recent_avg}
        else:
            return {"direction": "stable", "percentage": 0, "absolute": 0}
    
    percentage_change = ((recent_avg - previous_avg) / previous_avg) * 100
    absolute_change = recent_avg - previous_avg
    
    if percentage_change > 5:
        direction = "up"
    elif percentage_change < -5:
        direction = "down"
    else:
        direction = "stable"
    
    return {
        "direction": direction,
        "percentage": round(percentage_change, 2),
        "absolute": round(absolute_change, 2),
        "recent_avg": round(recent_avg, 2),
        "previous_avg": round(previous_avg, 2)
    }

@router.get("/daily", response_model=Dict[str, Any])
async def get_daily_stats(
    days: int = Query(30, ge=1, le=365),
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить дневную статистику за указанный период
    """
    try:
        daily_stats = data_manager.get_daily_stats(days)
        
        # Вычисляем агрегированные показатели
        total_new_users = sum(day["new_users"] for day in daily_stats.values())
        total_completed_tasks = sum(day["completed_tasks"] for day in daily_stats.values())
        total_points_earned = sum(day["points_earned"] for day in daily_stats.values())
        avg_active_users = sum(day["active_users"] for day in daily_stats.values()) / max(len(daily_stats), 1)
        
        # Находим дни с максимальными показателями
        max_users_day = max(daily_stats.items(), key=lambda x: x[1]["new_users"])
        max_tasks_day = max(daily_stats.items(), key=lambda x: x[1]["completed_tasks"])
        max_points_day = max(daily_stats.items(), key=lambda x: x[1]["points_earned"])
        
        return {
            "daily_stats": daily_stats,
            "period": {
                "days": days,
                "start_date": min(daily_stats.keys()) if daily_stats else None,
                "end_date": max(daily_stats.keys()) if daily_stats else None
            },
            "summary": {
                "total_new_users": total_new_users,
                "total_completed_tasks": total_completed_tasks,
                "total_points_earned": total_points_earned,
                "avg_active_users": round(avg_active_users, 2),
                "avg_new_users_per_day": round(total_new_users / max(days, 1), 2),
                "avg_tasks_per_day": round(total_completed_tasks / max(days, 1), 2),
                "avg_points_per_day": round(total_points_earned / max(days, 1), 2)
            },
            "peaks": {
                "max_users_day": {
                    "date": max_users_day[0],
                    "count": max_users_day[1]["new_users"]
                },
                "max_tasks_day": {
                    "date": max_tasks_day[0],
                    "count": max_tasks_day[1]["completed_tasks"]
                },
                "max_points_day": {
                    "date": max_points_day[0],
                    "count": max_points_day[1]["points_earned"]
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения дневной статистики: {str(e)}")

@router.get("/performance", response_model=Dict[str, Any])
async def get_performance_stats(
    period: str = Query("month", regex="^(week|month|quarter|year)$"),
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить статистику производительности за период
    """
    try:
        # Определяем период
        period_days = {
            "week": 7,
            "month": 30,
            "quarter": 90,
            "year": 365
        }
        
        days = period_days[period]
        users = data_manager.get_all_users()
        tasks = data_manager.get_all_tasks()
        
        # Фильтруем данные по периоду
        cutoff_date = datetime.now() - timedelta(days=days)
        
        period_users = {}
        period_tasks = {}
        
        for user_id, user in users.items():
            if user.get("created_at"):
                try:
                    created = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00'))
                    if created >= cutoff_date:
                        period_users[user_id] = user
                except:
                    pass
        
        for task_id, task in tasks.items():
            if task.get("created_at"):
                try:
                    created = datetime.fromisoformat(task["created_at"].replace('Z', '+00:00'))
                    if created >= cutoff_date:
                        period_tasks[task_id] = task
                except:
                    pass
        
        # Анализ производительности
        performance_analysis = _analyze_performance(period_users, period_tasks, days)
        
        # Сравнение с предыдущим периодом
        prev_cutoff_date = cutoff_date - timedelta(days=days)
        comparison = _compare_periods(users, tasks, cutoff_date, prev_cutoff_date, days)
        
        return {
            "period": period,
            "days": days,
            "date_range": {
                "start": cutoff_date.date().isoformat(),
                "end": datetime.now().date().isoformat()
            },
            "performance": performance_analysis,
            "comparison": comparison,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики производительности: {str(e)}")

def _analyze_performance(users: Dict, tasks: Dict, days: int) -> Dict[str, Any]:
    """Анализ производительности за период"""
    
    # Основные метрики
    total_users = len(users)
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks.values() if t.get("status") == "completed"])
    
    # Активность пользователей
    active_users = len([u for u in users.values() if _is_user_active_in_period(u, days)])
    user_retention = (active_users / max(total_users, 1)) * 100
    
    # Производительность задач
    task_completion_rate = (completed_tasks / max(total_tasks, 1)) * 100
    avg_tasks_per_user = total_tasks / max(total_users, 1)
    
    # Время выполнения задач
    completion_times = []
    for task in tasks.values():
        if task.get("created_at") and task.get("completed_at"):
            try:
                created = datetime.fromisoformat(task["created_at"].replace('Z', '+00:00'))
                completed = datetime.fromisoformat(task["completed_at"].replace('Z', '+00:00'))
                completion_time = (completed - created).total_seconds() / 3600  # в часах
                completion_times.append(completion_time)
            except:
                pass
    
    avg_completion_time = sum(completion_times) / max(len(completion_times), 1)
    
    # Распределение по категориям
    category_performance = defaultdict(lambda: {"total": 0, "completed": 0})
    for task in tasks.values():
        category = task.get("category", "other")
        category_performance[category]["total"] += 1
        if task.get("status") == "completed":
            category_performance[category]["completed"] += 1
    
    # Добавляем процент завершения для каждой категории
    for category in category_performance:
        total = category_performance[category]["total"]
        completed = category_performance[category]["completed"]
        category_performance[category]["completion_rate"] = (completed / max(total, 1)) * 100
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "retention_rate": round(user_retention, 2)
        },
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "completion_rate": round(task_completion_rate, 2),
            "avg_per_user": round(avg_tasks_per_user, 2),
            "avg_completion_time_hours": round(avg_completion_time, 2)
        },
        "categories": dict(category_performance),
        "efficiency_score": round((task_completion_rate + user_retention) / 2, 2)
    }

def _is_user_active_in_period(user: Dict, days: int) -> bool:
    """Проверить активность пользователя в периоде"""
    if not user.get("last_activity"):
        return False
    
    try:
        last_activity = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00'))
        cutoff = datetime.now() - timedelta(days=days)
        return last_activity >= cutoff
    except:
        return False

def _compare_periods(users: Dict, tasks: Dict, current_start: datetime, prev_start: datetime, days: int) -> Dict[str, Any]:
    """Сравнить текущий период с предыдущим"""
    
    # Данные текущего периода
    current_users = {}
    current_tasks = {}
    
    for user_id, user in users.items():
        if user.get("created_at"):
            try:
                created = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00'))
                if created >= current_start:
                    current_users[user_id] = user
            except:
                pass
    
    for task_id, task in tasks.items():
        if task.get("created_at"):
            try:
                created = datetime.fromisoformat(task["created_at"].replace('Z', '+00:00'))
                if created >= current_start:
                    current_tasks[task_id] = task
            except:
                pass
    
    # Данные предыдущего периода
    prev_users = {}
    prev_tasks = {}
    
    for user_id, user in users.items():
        if user.get("created_at"):
            try:
                created = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00'))
                if prev_start <= created < current_start:
                    prev_users[user_id] = user
            except:
                pass
    
    for task_id, task in tasks.items():
        if task.get("created_at"):
            try:
                created = datetime.fromisoformat(task["created_at"].replace('Z', '+00:00'))
                if prev_start <= created < current_start:
                    prev_tasks[task_id] = task
            except:
                pass
    
    # Вычисляем изменения
    users_change = len(current_users) - len(prev_users)
    tasks_change = len(current_tasks) - len(prev_tasks)
    
    current_completed = len([t for t in current_tasks.values() if t.get("status") == "completed"])
    prev_completed = len([t for t in prev_tasks.values() if t.get("status") == "completed"])
    completed_change = current_completed - prev_completed
    
    return {
        "current_period": {
            "users": len(current_users),
            "tasks": len(current_tasks),
            "completed_tasks": current_completed
        },
        "previous_period": {
            "users": len(prev_users),
            "tasks": len(prev_tasks),
            "completed_tasks": prev_completed
        },
        "changes": {
            "users": users_change,
            "tasks": tasks_change,
            "completed_tasks": completed_change
        },
        "percentage_changes": {
            "users": ((users_change / max(len(prev_users), 1)) * 100) if prev_users else 0,
            "tasks": ((tasks_change / max(len(prev_tasks), 1)) * 100) if prev_tasks else 0,
            "completed_tasks": ((completed_change / max(prev_completed, 1)) * 100) if prev_completed else 0
        }
    }

@router.get("/engagement", response_model=Dict[str, Any])
async def get_engagement_stats(
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить статистику вовлеченности пользователей
    """
    try:
        users = data_manager.get_all_users()
        tasks = data_manager.get_all_tasks()
        
        # Анализ активности пользователей
        engagement_analysis = _analyze_user_engagement(users, tasks)
        
        # Сегментация пользователей
        user_segments = _segment_users(users, tasks)
        
        # Когортный анализ
        cohort_analysis = _perform_cohort_analysis(users)
        
        return {
            "engagement_metrics": engagement_analysis,
            "user_segments": user_segments,
            "cohort_analysis": cohort_analysis,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики вовлеченности: {str(e)}")

def _analyze_user_engagement(users: Dict, tasks: Dict) -> Dict[str, Any]:
    """Анализ вовлеченности пользователей"""
    
    total_users = len(users)
    
    # Активность по периодам
    now = datetime.now()
    active_1d = 0
    active_7d = 0
    active_30d = 0
    
    for user in users.values():
        if user.get("last_activity"):
            try:
                last_activity = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00'))
                days_since = (now - last_activity).days
                
                if days_since <= 1:
                    active_1d += 1
                if days_since <= 7:
                    active_7d += 1
                if days_since <= 30:
                    active_30d += 1
            except:
                pass
    
    # Распределение пользователей по активности
    activity_distribution = {
        "very_active": 0,    # > 10 задач или активность каждый день
        "active": 0,         # 5-10 задач или активность 3-6 раз в неделю
        "moderate": 0,       # 1-4 задачи или активность 1-2 раза в неделю
        "inactive": 0        # 0 задач или нет активности больше недели
    }
    
    for user_id, user in users.items():
        user_tasks = [t for t in tasks.values() if t.get("assigned_to") == user_id]
        completed_tasks = len([t for t in user_tasks if t.get("status") == "completed"])
        
        last_activity_days = 999
        if user.get("last_activity"):
            try:
                last_activity = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00'))
                last_activity_days = (now - last_activity).days
            except:
                pass
        
        if completed_tasks > 10 or last_activity_days <= 1:
            activity_distribution["very_active"] += 1
        elif completed_tasks >= 5 or last_activity_days <= 3:
            activity_distribution["active"] += 1
        elif completed_tasks >= 1 or last_activity_days <= 7:
            activity_distribution["moderate"] += 1
        else:
            activity_distribution["inactive"] += 1
    
    # Средние показатели
    avg_tasks_per_user = len(tasks) / max(total_users, 1)
    avg_session_frequency = active_7d / max(total_users, 1) * 7  # сессий в неделю
    
    return {
        "daily_active_users": active_1d,
        "weekly_active_users": active_7d,
        "monthly_active_users": active_30d,
        "retention_rates": {
            "daily": (active_1d / max(total_users, 1)) * 100,
            "weekly": (active_7d / max(total_users, 1)) * 100,
            "monthly": (active_30d / max(total_users, 1)) * 100
        },
        "activity_distribution": activity_distribution,
        "engagement_score": round(((active_7d / max(total_users, 1)) * 100 + avg_tasks_per_user * 10) / 2, 2),
        "avg_tasks_per_user": round(avg_tasks_per_user, 2),
        "avg_session_frequency": round(avg_session_frequency, 2)
    }

def _segment_users(users: Dict, tasks: Dict) -> Dict[str, Any]:
    """Сегментация пользователей"""
    
    segments = {
        "champions": [],      # Высокие очки + недавняя активность
        "loyal_users": [],    # Старые пользователи + регулярная активность
        "potential_loyalists": [],  # Новые пользователи + высокая активность
        "new_users": [],      # Недавно зарегистрированные
        "at_risk": [],        # Ранее активные, но сейчас неактивные
        "hibernating": []     # Давно неактивные
    }
    
    now = datetime.now()
    
    for user_id, user in users.items():
        points = user.get("points", 0)
        created_days_ago = 999
        last_activity_days_ago = 999
        
        if user.get("created_at"):
            try:
                created = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00'))
                created_days_ago = (now - created).days
            except:
                pass
        
        if user.get("last_activity"):
            try:
                last_activity = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00'))
                last_activity_days_ago = (now - last_activity).days
            except:
                pass
        
        user_info = {
            "user_id": user_id,
            "username": user.get("username", "Unknown"),
            "points": points,
            "level": user.get("level", 1),
            "created_days_ago": created_days_ago,
            "last_activity_days_ago": last_activity_days_ago
        }
        
        # Логика сегментации
        if points >= 1000 and last_activity_days_ago <= 7:
            segments["champions"].append(user_info)
        elif created_days_ago >= 30 and last_activity_days_ago <= 14:
            segments["loyal_users"].append(user_info)
        elif created_days_ago <= 30 and last_activity_days_ago <= 7:
            segments["potential_loyalists"].append(user_info)
        elif created_days_ago <= 7:
            segments["new_users"].append(user_info)
        elif 7 < last_activity_days_ago <= 30 and points > 100:
            segments["at_risk"].append(user_info)
        else:
            segments["hibernating"].append(user_info)
    
    # Добавляем размеры сегментов
    segment_sizes = {name: len(users_list) for name, users_list in segments.items()}
    
    return {
        "segments": segments,
        "segment_sizes": segment_sizes,
        "total_users": len(users)
    }

def _perform_cohort_analysis(users: Dict) -> Dict[str, Any]:
    """Когортный анализ пользователей"""
    
    # Группируем пользователей по месяцам регистрации
    cohorts = defaultdict(list)
    
    for user_id, user in users.items():
        if user.get("created_at"):
            try:
                created = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00'))
                cohort_month = created.strftime('%Y-%m')
                cohorts[cohort_month].append({
                    "user_id": user_id,
                    "created_at": created,
                    "last_activity": user.get("last_activity")
                })
            except:
                pass
    
    # Анализ удержания для каждой когорты
    cohort_analysis = {}
    
    for cohort_month, cohort_users in cohorts.items():
        if not cohort_users:
            continue
        
        cohort_size = len(cohort_users)
        retention_data = {}
        
        # Проверяем удержание на разных периодах
        for period_months in [1, 3, 6, 12]:
            active_users = 0
            
            for user in cohort_users:
                if user.get("last_activity"):
                    try:
                        last_activity = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00'))
                        period_cutoff = user["created_at"] + timedelta(days=period_months * 30)
                        
                        if last_activity >= period_cutoff:
                            active_users += 1
                    except:
                        pass
            
            retention_rate = (active_users / cohort_size) * 100 if cohort_size > 0 else 0
            retention_data[f"{period_months}_month"] = {
                "active_users": active_users,
                "retention_rate": round(retention_rate, 2)
            }
        
        cohort_analysis[cohort_month] = {
            "cohort_size": cohort_size,
            "retention": retention_data
        }
    
    return {
        "cohorts": cohort_analysis,
        "total_cohorts": len(cohorts)
    }

@router.get("/export", response_model=Dict[str, Any])
async def export_stats(
    format: str = Query("json", regex="^(json|csv)$"),
    stats_type: str = Query("overview", regex="^(overview|daily|performance|engagement)$"),
    period: Optional[str] = Query("month", regex="^(week|month|quarter|year)$"),
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Экспорт статистических данных
    """
    try:
        # Получаем данные в зависимости от типа
        if stats_type == "overview":
            data = data_manager.get_overview_stats()
        elif stats_type == "daily":
            data = data_manager.get_daily_stats(30)
        elif stats_type == "performance":
            period_days = {"week": 7, "month": 30, "quarter": 90, "year": 365}
            days = period_days.get(period, 30)
            data = _analyze_performance(
                data_manager.get_all_users(),
                data_manager.get_all_tasks(),
                days
            )
        elif stats_type == "engagement":
            data = _analyze_user_engagement(
                data_manager.get_all_users(),
                data_manager.get_all_tasks()
            )
        
        return {
            "format": format,
            "stats_type": stats_type,
            "period": period,
            "data": data,
            "exported_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта статистики: {str(e)}")
