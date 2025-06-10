from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json

from ..core.data_manager import DataManager
from ..dependencies import get_data_manager

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("/", response_model=Dict[str, Any])
async def get_all_users(
    data_manager: DataManager = Depends(get_data_manager),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None),
    sort_by: str = Query("points", regex="^(points|level|username|last_activity|created_at)$"),
    order: str = Query("desc", regex="^(asc|desc)$")
):
    """
    Получить список всех пользователей с пагинацией и фильтрацией
    """
    try:
        users = data_manager.get_all_users()
        users_list = []
        
        for user_id, user_data in users.items():
            user_info = {
                "user_id": user_id,
                "username": user_data.get("username", "Unknown"),
                "first_name": user_data.get("first_name", ""),
                "last_name": user_data.get("last_name", ""),
                "points": user_data.get("points", 0),
                "level": user_data.get("level", 1),
                "created_at": user_data.get("created_at"),
                "last_activity": user_data.get("last_activity"),
                "completed_tasks": user_data.get("completed_tasks", 0),
                "streak": user_data.get("streak", 0),
                "status": "active" if data_manager._is_user_active(user_data) else "inactive",
                "achievements_count": len(user_data.get("achievements", []))
            }
            users_list.append(user_info)
        
        # Фильтрация по поиску
        if search:
            search_lower = search.lower()
            users_list = [
                user for user in users_list 
                if search_lower in user["username"].lower() or 
                   search_lower in user.get("first_name", "").lower() or
                   search_lower in user.get("last_name", "").lower()
            ]
        
        # Сортировка
        reverse = order == "desc"
        users_list.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
        
        # Пагинация
        total = len(users_list)
        start = (page - 1) * limit
        end = start + limit
        paginated_users = users_list[start:end]
        
        return {
            "users": paginated_users,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            },
            "filters": {
                "search": search,
                "sort_by": sort_by,
                "order": order
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения пользователей: {str(e)}")

@router.get("/{user_id}", response_model=Dict[str, Any])
async def get_user(
    user_id: str,
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить детальную информацию о конкретном пользователе
    """
    try:
        user = data_manager.get_user(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Получаем дополнительную информацию
        tasks = data_manager.get_all_tasks()
        user_tasks = {
            task_id: task for task_id, task in tasks.items()
            if task.get("assigned_to") == user_id
        }
        
        completed_tasks = [
            task for task in user_tasks.values()
            if task.get("status") == "completed"
        ]
        
        pending_tasks = [
            task for task in user_tasks.values()
            if task.get("status") in ["pending", "in_progress"]
        ]
        
        # Статистика активности по дням
        activity_stats = {}
        for task in completed_tasks:
            if task.get("completed_at"):
                try:
                    date = datetime.fromisoformat(task["completed_at"].replace('Z', '+00:00')).date()
                    date_str = date.strftime('%Y-%m-%d')
                    if date_str not in activity_stats:
                        activity_stats[date_str] = {"tasks": 0, "points": 0}
                    activity_stats[date_str]["tasks"] += 1
                    activity_stats[date_str]["points"] += task.get("points", 0)
                except:
                    continue
        
        user_detail = {
            "user_id": user_id,
            "username": user.get("username", "Unknown"),
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "points": user.get("points", 0),
            "level": user.get("level", 1),
            "created_at": user.get("created_at"),
            "last_activity": user.get("last_activity"),
            "streak": user.get("streak", 0),
            "settings": user.get("settings", {}),
            "achievements": user.get("achievements", []),
            "statistics": {
                "total_tasks": len(user_tasks),
                "completed_tasks": len(completed_tasks),
                "pending_tasks": len(pending_tasks),
                "completion_rate": (len(completed_tasks) / max(len(user_tasks), 1)) * 100,
                "total_points_earned": sum(task.get("points", 0) for task in completed_tasks),
                "avg_points_per_task": sum(task.get("points", 0) for task in completed_tasks) / max(len(completed_tasks), 1)
            },
            "recent_activity": sorted([
                {
                    "task_id": task_id,
                    "title": task.get("title", ""),
                    "completed_at": task.get("completed_at"),
                    "points": task.get("points", 0),
                    "category": task.get("category", "other")
                }
                for task_id, task in user_tasks.items()
                if task.get("status") == "completed" and task.get("completed_at")
            ], key=lambda x: x["completed_at"], reverse=True)[:10],
            "activity_timeline": dict(sorted(activity_stats.items()))
        }
        
        return user_detail
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения пользователя: {str(e)}")

@router.get("/stats/overview", response_model=Dict[str, Any])
async def get_users_overview_stats(
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить общую статистику по пользователям
    """
    try:
        stats = data_manager.get_users_stats()
        
        # Дополнительная статистика
        users = data_manager.get_all_users()
        
        # Статистика регистраций по дням (последние 30 дней)
        registration_stats = {}
        for user in users.values():
            if user.get("created_at"):
                try:
                    date = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00')).date()
                    if (datetime.now().date() - date).days <= 30:
                        date_str = date.strftime('%Y-%m-%d')
                        registration_stats[date_str] = registration_stats.get(date_str, 0) + 1
                except:
                    continue
        
        # Статистика активности по дням
        activity_stats = {}
        for user in users.values():
            if user.get("last_activity"):
                try:
                    date = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00')).date()
                    if (datetime.now().date() - date).days <= 30:
                        date_str = date.strftime('%Y-%m-%d')
                        activity_stats[date_str] = activity_stats.get(date_str, 0) + 1
                except:
                    continue
        
        # Статистика по языкам
        language_stats = {}
        for user in users.values():
            lang = user.get("language_code", "unknown")
            language_stats[lang] = language_stats.get(lang, 0) + 1
        
        return {
            **stats,
            "trends": {
                "registrations_30d": dict(sorted(registration_stats.items())),
                "activity_30d": dict(sorted(activity_stats.items())),
                "language_distribution": language_stats
            },
            "growth_metrics": {
                "new_users_today": len([
                    u for u in users.values()
                    if u.get("created_at") and 
                    datetime.fromisoformat(u["created_at"].replace('Z', '+00:00')).date() == datetime.now().date()
                ]),
                "active_users_today": len([
                    u for u in users.values()
                    if u.get("last_activity") and 
                    datetime.fromisoformat(u["last_activity"].replace('Z', '+00:00')).date() == datetime.now().date()
                ])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")

@router.get("/leaderboard/", response_model=Dict[str, Any])
async def get_leaderboard(
    limit: int = Query(20, ge=1, le=100),
    period: str = Query("all", regex="^(all|week|month)$"),
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить таблицу лидеров
    """
    try:
        leaderboard = data_manager.get_leaderboard(limit)
        
        # Фильтрация по периоду
        if period != "all":
            cutoff_date = datetime.now()
            if period == "week":
                cutoff_date -= timedelta(days=7)
            elif period == "month":
                cutoff_date -= timedelta(days=30)
            
            # Фильтруем пользователей по активности в периоде
            filtered_leaderboard = []
            for user in leaderboard:
                if user.get("last_activity"):
                    try:
                        last_activity = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00'))
                        if last_activity >= cutoff_date:
                            filtered_leaderboard.append(user)
                    except:
                        continue
            
            leaderboard = filtered_leaderboard
        
        return {
            "leaderboard": leaderboard,
            "period": period,
            "total_users": len(leaderboard),
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения таблицы лидеров: {str(e)}")

@router.get("/achievements/stats", response_model=Dict[str, Any])
async def get_achievements_stats(
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить статистику по достижениям
    """
    try:
        achievements_stats = data_manager.get_achievements_stats()
        
        # Обогащаем данными о достижениях
        enriched_stats = {}
        achievement_names = {
            "first_task": "Первое задание",
            "task_master": "Мастер заданий",
            "week_streak": "Недельная серия",
            "month_streak": "Месячная серия",
            "early_bird": "Ранняя пташка",
            "night_owl": "Сова",
            "speed_runner": "Спидранер",
            "perfectionist": "Перфекционист",
            "social_butterfly": "Социальная бабочка",
            "helper": "Помощник"
        }
        
        for achievement_id, stats in achievements_stats.items():
            enriched_stats[achievement_id] = {
                **stats,
                "name": achievement_names.get(achievement_id, achievement_id.replace("_", " ").title()),
                "percentage": (stats["count"] / max(len(data_manager.get_all_users()), 1)) * 100
            }
        
        # Самые популярные достижения
        popular_achievements = sorted(
            enriched_stats.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:10]
        
        # Самые редкие достижения
        rare_achievements = sorted(
            enriched_stats.items(),
            key=lambda x: x[1]["count"]
        )[:5]
        
        return {
            "all_achievements": enriched_stats,
            "popular_achievements": popular_achievements,
            "rare_achievements": rare_achievements,
            "total_achievements": len(enriched_stats),
            "total_earned": sum(stats["count"] for stats in enriched_stats.values())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики достижений: {str(e)}")

@router.get("/activity/timeline", response_model=Dict[str, Any])
async def get_activity_timeline(
    user_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить временную линию активности пользователей
    """
    try:
        users = data_manager.get_all_users()
        tasks = data_manager.get_all_tasks()
        
        # Если указан конкретный пользователь
        if user_id:
            if user_id not in users:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
            users = {user_id: users[user_id]}
        
        # Генерируем timeline за указанный период
        timeline = {}
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        # Инициализируем все дни
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            timeline[date_str] = {
                "date": date_str,
                "active_users": 0,
                "completed_tasks": 0,
                "points_earned": 0,
                "new_users": 0,
                "activities": []
            }
            current_date += timedelta(days=1)
        
        # Заполняем данными
        for user_id, user in users.items():
            # Регистрация пользователя
            if user.get("created_at"):
                try:
                    reg_date = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00')).date()
                    if start_date <= reg_date <= end_date:
                        date_str = reg_date.strftime('%Y-%m-%d')
                        timeline[date_str]["new_users"] += 1
                        timeline[date_str]["activities"].append({
                            "type": "registration",
                            "user_id": user_id,
                            "username": user.get("username", "Unknown"),
                            "timestamp": user["created_at"]
                        })
                except:
                    pass
            
            # Активность пользователя
            if user.get("last_activity"):
                try:
                    activity_date = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00')).date()
                    if start_date <= activity_date <= end_date:
                        date_str = activity_date.strftime('%Y-%m-%d')
                        timeline[date_str]["active_users"] += 1
                except:
                    pass
        
        # Добавляем данные о задачах
        for task_id, task in tasks.items():
            if task.get("status") == "completed" and task.get("completed_at"):
                try:
                    completed_date = datetime.fromisoformat(task["completed_at"].replace('Z', '+00:00')).date()
                    if start_date <= completed_date <= end_date:
                        date_str = completed_date.strftime('%Y-%m-%d')
                        timeline[date_str]["completed_tasks"] += 1
                        timeline[date_str]["points_earned"] += task.get("points", 0)
                        
                        # Добавляем в активности если пользователь в нашем списке
                        if not user_id or task.get("assigned_to") == user_id:
                            timeline[date_str]["activities"].append({
                                "type": "task_completed",
                                "task_id": task_id,
                                "task_title": task.get("title", "Unknown"),
                                "user_id": task.get("assigned_to"),
                                "points": task.get("points", 0),
                                "timestamp": task["completed_at"]
                            })
                except:
                    pass
        
        # Сортируем активности в каждом дне по времени
        for day_data in timeline.values():
            day_data["activities"].sort(key=lambda x: x["timestamp"], reverse=True)
        
        return {
            "timeline": dict(sorted(timeline.items())),
            "period": {
                "start_date": start_date.strftime('%Y-%m-%d'),
                "end_date": end_date.strftime('%Y-%m-%d'),
                "days": days
            },
            "summary": {
                "total_active_users": sum(day["active_users"] for day in timeline.values()),
                "total_completed_tasks": sum(day["completed_tasks"] for day in timeline.values()),
                "total_points_earned": sum(day["points_earned"] for day in timeline.values()),
                "total_new_users": sum(day["new_users"] for day in timeline.values())
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения timeline: {str(e)}")

@router.get("/export/", response_model=Dict[str, Any])
async def export_users_data(
    format: str = Query("json", regex="^(json|csv)$"),
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Экспорт данных пользователей
    """
    try:
        users = data_manager.get_all_users()
        
        if format == "json":
            return {
                "format": "json",
                "data": users,
                "exported_at": datetime.now().isoformat(),
                "total_users": len(users)
            }
        
        elif format == "csv":
            # Преобразуем в CSV формат
            csv_data = []
            for user_id, user in users.items():
                csv_data.append({
                    "user_id": user_id,
                    "username": user.get("username", ""),
                    "first_name": user.get("first_name", ""),
                    "last_name": user.get("last_name", ""),
                    "points": user.get("points", 0),
                    "level": user.get("level", 1),
                    "created_at": user.get("created_at", ""),
                    "last_activity": user.get("last_activity", ""),
                    "completed_tasks": user.get("completed_tasks", 0),
                    "streak": user.get("streak", 0),
                    "achievements_count": len(user.get("achievements", []))
                })
            
            return {
                "format": "csv",
                "data": csv_data,
                "exported_at": datetime.now().isoformat(),
                "total_users": len(csv_data)
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта: {str(e)}")
