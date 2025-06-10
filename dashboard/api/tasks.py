from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json

from ..core.data_manager import DataManager
from ..dependencies import get_data_manager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.get("/", response_model=Dict[str, Any])
async def get_all_tasks(
    data_manager: DataManager = Depends(get_data_manager),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    status: Optional[str] = Query(None, regex="^(pending|in_progress|completed|cancelled)$"),
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None, regex="^(easy|medium|hard)$"),
    assigned_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at", regex="^(created_at|completed_at|points|title|difficulty)$"),
    order: str = Query("desc", regex="^(asc|desc)$")
):
    """
    Получить список всех задач с фильтрацией и пагинацией
    """
    try:
        tasks = data_manager.get_all_tasks()
        tasks_list = []
        
        for task_id, task_data in tasks.items():
            task_info = {
                "task_id": task_id,
                "title": task_data.get("title", ""),
                "description": task_data.get("description", ""),
                "category": task_data.get("category", "other"),
                "difficulty": task_data.get("difficulty", "medium"),
                "points": task_data.get("points", 0),
                "status": task_data.get("status", "pending"),
                "assigned_to": task_data.get("assigned_to"),
                "created_at": task_data.get("created_at"),
                "started_at": task_data.get("started_at"),
                "completed_at": task_data.get("completed_at"),
                "deadline": task_data.get("deadline"),
                "priority": task_data.get("priority", "normal"),
                "tags": task_data.get("tags", []),
                "estimated_time": task_data.get("estimated_time"),
                "actual_time": task_data.get("actual_time")
            }
            tasks_list.append(task_info)
        
        # Применяем фильтры
        if status:
            tasks_list = [task for task in tasks_list if task["status"] == status]
        
        if category:
            tasks_list = [task for task in tasks_list if task["category"] == category]
        
        if difficulty:
            tasks_list = [task for task in tasks_list if task["difficulty"] == difficulty]
        
        if assigned_to:
            tasks_list = [task for task in tasks_list if task["assigned_to"] == assigned_to]
        
        if search:
            search_lower = search.lower()
            tasks_list = [
                task for task in tasks_list 
                if search_lower in task["title"].lower() or 
                   search_lower in task.get("description", "").lower() or
                   any(search_lower in tag.lower() for tag in task.get("tags", []))
            ]
        
        # Сортировка
        reverse = order == "desc"
        if sort_by in ["created_at", "completed_at", "started_at", "deadline"]:
            # Сортировка по дате
            tasks_list.sort(
                key=lambda x: datetime.fromisoformat(x[sort_by].replace('Z', '+00:00')) 
                if x.get(sort_by) else datetime.min, 
                reverse=reverse
            )
        else:
            # Сортировка по другим полям
            tasks_list.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)
        
        # Пагинация
        total = len(tasks_list)
        start = (page - 1) * limit
        end = start + limit
        paginated_tasks = tasks_list[start:end]
        
        return {
            "tasks": paginated_tasks,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            },
            "filters": {
                "status": status,
                "category": category,
                "difficulty": difficulty,
                "assigned_to": assigned_to,
                "search": search,
                "sort_by": sort_by,
                "order": order
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения задач: {str(e)}")

@router.get("/{task_id}", response_model=Dict[str, Any])
async def get_task(
    task_id: str,
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить детальную информацию о конкретной задаче
    """
    try:
        tasks = data_manager.get_all_tasks()
        
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        
        task = tasks[task_id]
        
        # Получаем информацию о пользователе, если задача назначена
        assigned_user = None
        if task.get("assigned_to"):
            user = data_manager.get_user(task["assigned_to"])
            if user:
                assigned_user = {
                    "user_id": task["assigned_to"],
                    "username": user.get("username", "Unknown"),
                    "first_name": user.get("first_name", ""),
                    "last_name": user.get("last_name", ""),
                    "level": user.get("level", 1),
                    "points": user.get("points", 0)
                }
        
        # Вычисляем метрики времени
        time_metrics = {}
        if task.get("created_at"):
            created = datetime.fromisoformat(task["created_at"].replace('Z', '+00:00'))
            now = datetime.now()
            
            time_metrics["age_days"] = (now - created).days
            
            if task.get("started_at"):
                started = datetime.fromisoformat(task["started_at"].replace('Z', '+00:00'))
                time_metrics["time_to_start_hours"] = (started - created).total_seconds() / 3600
                
                if task.get("completed_at"):
                    completed = datetime.fromisoformat(task["completed_at"].replace('Z', '+00:00'))
                    time_metrics["completion_time_hours"] = (completed - started).total_seconds() / 3600
                    time_metrics["total_time_hours"] = (completed - created).total_seconds() / 3600
            
            if task.get("deadline"):
                deadline = datetime.fromisoformat(task["deadline"].replace('Z', '+00:00'))
                if task.get("completed_at"):
                    completed = datetime.fromisoformat(task["completed_at"].replace('Z', '+00:00'))
                    time_metrics["completed_before_deadline"] = completed <= deadline
                    time_metrics["deadline_difference_hours"] = (deadline - completed).total_seconds() / 3600
                else:
                    time_metrics["time_until_deadline_hours"] = (deadline - now).total_seconds() / 3600
                    time_metrics["is_overdue"] = now > deadline
        
        # Похожие задачи (по категории и сложности)
        similar_tasks = []
        for tid, t in tasks.items():
            if (tid != task_id and 
                t.get("category") == task.get("category") and 
                t.get("difficulty") == task.get("difficulty")):
                similar_tasks.append({
                    "task_id": tid,
                    "title": t.get("title", ""),
                    "status": t.get("status", "pending"),
                    "points": t.get("points", 0),
                    "created_at": t.get("created_at")
                })
        
        similar_tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        task_detail = {
            **task,
            "task_id": task_id,
            "assigned_user": assigned_user,
            "time_metrics": time_metrics,
            "similar_tasks": similar_tasks[:5],
            "progress_percentage": self._calculate_progress_percentage(task),
            "estimated_completion": self._estimate_completion_date(task, time_metrics)
        }
        
        return task_detail
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения задачи: {str(e)}")

def _calculate_progress_percentage(task: Dict) -> int:
    """Вычислить процент выполнения задачи"""
    status = task.get("status", "pending")
    
    if status == "completed":
        return 100
    elif status == "in_progress":
        # Если есть подзадачи или чекпоинты
        subtasks = task.get("subtasks", [])
        if subtasks:
            completed_subtasks = len([st for st in subtasks if st.get("completed")])
            return int((completed_subtasks / len(subtasks)) * 100)
        return 50  # По умолчанию для задач в процессе
    elif status == "cancelled":
        return 0
    else:
        return 0

def _estimate_completion_date(task: Dict, time_metrics: Dict) -> Optional[str]:
    """Оценить дату завершения задачи"""
    if task.get("status") == "completed":
        return task.get("completed_at")
    
    if task.get("deadline"):
        return task.get("deadline")
    
    # Простая оценка на основе сложности
    difficulty_hours = {
        "easy": 2,
        "medium": 8,
        "hard": 24
    }
    
    estimated_hours = difficulty_hours.get(task.get("difficulty", "medium"), 8)
    
    if task.get("started_at"):
        start_date = datetime.fromisoformat(task["started_at"].replace('Z', '+00:00'))
    else:
        start_date = datetime.now()
    
    estimated_completion = start_date + timedelta(hours=estimated_hours)
    return estimated_completion.isoformat()

@router.get("/stats/overview", response_model=Dict[str, Any])
async def get_tasks_overview_stats(
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить общую статистику по задачам
    """
    try:
        stats = data_manager.get_tasks_stats()
        tasks = data_manager.get_all_tasks()
        
        # Дополнительная статистика
        status_distribution = {}
        priority_distribution = {}
        time_analysis = {
            "overdue_tasks": 0,
            "due_today": 0,
            "due_this_week": 0,
            "avg_completion_time_hours": 0,
            "total_estimated_time": 0,
            "total_actual_time": 0
        }
        
        completion_times = []
        now = datetime.now()
        
        for task in tasks.values():
            # Статистика по статусам
            status = task.get("status", "pending")
            status_distribution[status] = status_distribution.get(status, 0) + 1
            
            # Статистика по приоритетам
            priority = task.get("priority", "normal")
            priority_distribution[priority] = priority_distribution.get(priority, 0) + 1
            
            # Анализ времени
            if task.get("deadline"):
                try:
                    deadline = datetime.fromisoformat(task["deadline"].replace('Z', '+00:00'))
                    if deadline < now and status != "completed":
                        time_analysis["overdue_tasks"] += 1
                    elif deadline.date() == now.date():
                        time_analysis["due_today"] += 1
                    elif (deadline - now).days <= 7:
                        time_analysis["due_this_week"] += 1
                except:
                    pass
            
            # Время выполнения
            if task.get("created_at") and task.get("completed_at"):
                try:
                    created = datetime.fromisoformat(task["created_at"].replace('Z', '+00:00'))
                    completed = datetime.fromisoformat(task["completed_at"].replace('Z', '+00:00'))
                    completion_time = (completed - created).total_seconds() / 3600
                    completion_times.append(completion_time)
                except:
                    pass
            
            # Суммарное время
            if task.get("estimated_time"):
                time_analysis["total_estimated_time"] += task["estimated_time"]
            if task.get("actual_time"):
                time_analysis["total_actual_time"] += task["actual_time"]
        
        if completion_times:
            time_analysis["avg_completion_time_hours"] = sum(completion_times) / len(completion_times)
        
        # Производительность по дням недели
        weekday_performance = {i: {"completed": 0, "created": 0} for i in range(7)}
        
        for task in tasks.values():
            if task.get("created_at"):
                try:
                    created_date = datetime.fromisoformat(task["created_at"].replace('Z', '+00:00'))
                    weekday_performance[created_date.weekday()]["created"] += 1
                except:
                    pass
            
            if task.get("completed_at"):
                try:
                    completed_date = datetime.fromisoformat(task["completed_at"].replace('Z', '+00:00'))
                    weekday_performance[completed_date.weekday()]["completed"] += 1
                except:
                    pass
        
        # Преобразуем в удобный формат
        weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        weekday_stats = {
            weekday_names[i]: weekday_performance[i] 
            for i in range(7)
        }
        
        return {
            **stats,
            "distributions": {
                "status": status_distribution,
                "priority": priority_distribution,
                "weekday_performance": weekday_stats
            },
            "time_analysis": time_analysis,
            "efficiency_metrics": {
                "completion_rate_7d": self._calculate_completion_rate(tasks, 7),
                "completion_rate_30d": self._calculate_completion_rate(tasks, 30),
                "avg_points_per_task": stats.get("total_tasks", 0) and 
                    sum(task.get("points", 0) for task in tasks.values()) / stats["total_tasks"] or 0,
                "tasks_per_user": self._calculate_tasks_per_user_stats(tasks, data_manager)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики задач: {str(e)}")

def _calculate_completion_rate(tasks: Dict, days: int) -> float:
    """Вычислить процент завершения задач за период"""
    cutoff_date = datetime.now() - timedelta(days=days)
    
    period_tasks = [
        task for task in tasks.values()
        if task.get("created_at") and 
        datetime.fromisoformat(task["created_at"].replace('Z', '+00:00')) >= cutoff_date
    ]
    
    if not period_tasks:
        return 0.0
    
    completed_tasks = [
        task for task in period_tasks
        if task.get("status") == "completed"
    ]
    
    return (len(completed_tasks) / len(period_tasks)) * 100

def _calculate_tasks_per_user_stats(tasks: Dict, data_manager: DataManager) -> Dict:
    """Вычислить статистику задач на пользователя"""
    users = data_manager.get_all_users()
    user_task_counts = {}
    
    for task in tasks.values():
        user_id = task.get("assigned_to")
        if user_id:
            if user_id not in user_task_counts:
                user_task_counts[user_id] = {"total": 0, "completed": 0}
            user_task_counts[user_id]["total"] += 1
            if task.get("status") == "completed":
                user_task_counts[user_id]["completed"] += 1
    
    if not user_task_counts:
        return {"avg_tasks_per_user": 0, "max_tasks_per_user": 0, "min_tasks_per_user": 0}
    
    task_counts = [counts["total"] for counts in user_task_counts.values()]
    
    return {
        "avg_tasks_per_user": sum(task_counts) / len(task_counts),
        "max_tasks_per_user": max(task_counts),
        "min_tasks_per_user": min(task_counts),
        "users_with_tasks": len(user_task_counts),
        "total_users": len(users)
    }

@router.get("/categories/stats", response_model=Dict[str, Any])
async def get_categories_stats(
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить статистику по категориям задач
    """
    try:
        tasks = data_manager.get_all_tasks()
        
        category_stats = {}
        
        for task in tasks.values():
            category = task.get("category", "other")
            
            if category not in category_stats:
                category_stats[category] = {
                    "total": 0,
                    "completed": 0,
                    "in_progress": 0,
                    "pending": 0,
                    "cancelled": 0,
                    "total_points": 0,
                    "avg_points": 0,
                    "difficulties": {"easy": 0, "medium": 0, "hard": 0},
                    "avg_completion_time": 0,
                    "completion_times": []
                }
            
            stats = category_stats[category]
            stats["total"] += 1
            
            status = task.get("status", "pending")
            stats[status] = stats.get(status, 0) + 1
            
            points = task.get("points", 0)
            stats["total_points"] += points
            
            difficulty = task.get("difficulty", "medium")
            stats["difficulties"][difficulty] += 1
            
            # Время выполнения
            if task.get("created_at") and task.get("completed_at"):
                try:
                    created = datetime.fromisoformat(task["created_at"].replace('Z', '+00:00'))
                    completed = datetime.fromisoformat(task["completed_at"].replace('Z', '+00:00'))
                    completion_time = (completed - created).total_seconds() / 3600
                    stats["completion_times"].append(completion_time)
                except:
                    pass
        
        # Вычисляем средние значения
        for category, stats in category_stats.items():
            if stats["total"] > 0:
                stats["avg_points"] = stats["total_points"] / stats["total"]
                stats["completion_rate"] = (stats["completed"] / stats["total"]) * 100
                
                if stats["completion_times"]:
                    stats["avg_completion_time"] = sum(stats["completion_times"]) / len(stats["completion_times"])
                
                # Удаляем временный список
                del stats["completion_times"]
        
        # Сортируем по популярности
        sorted_categories = sorted(
            category_stats.items(),
            key=lambda x: x[1]["total"],
            reverse=True
        )
        
        return {
            "categories": dict(sorted_categories),
            "total_categories": len(category_stats),
            "most_popular": sorted_categories[0] if sorted_categories else None,
            "highest_completion_rate": max(
                category_stats.items(),
                key=lambda x: x[1].get("completion_rate", 0)
            ) if category_stats else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики категорий: {str(e)}")

@router.get("/timeline/", response_model=Dict[str, Any])
async def get_tasks_timeline(
    days: int = Query(30, ge=1, le=365),
    category: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Получить временную линию создания и выполнения задач
    """
    try:
        tasks = data_manager.get_all_tasks()
        
        # Фильтрация задач
        filtered_tasks = tasks
        if category:
            filtered_tasks = {
                tid: task for tid, task in filtered_tasks.items()
                if task.get("category") == category
            }
        
        if assigned_to:
            filtered_tasks = {
                tid: task for tid, task in filtered_tasks.items()
                if task.get("assigned_to") == assigned_to
            }
        
        # Генерируем timeline
        timeline = {}
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        # Инициализируем все дни
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            timeline[date_str] = {
                "date": date_str,
                "created": 0,
                "completed": 0,
                "started": 0,
                "cancelled": 0,
                "points_earned": 0,
                "tasks": []
            }
            current_date += timedelta(days=1)
        
        # Заполняем данными
        for task_id, task in filtered_tasks.items():
            # Создание задачи
            if task.get("created_at"):
                try:
                    created_date = datetime.fromisoformat(task["created_at"].replace('Z', '+00:00')).date()
                    if start_date <= created_date <= end_date:
                        date_str = created_date.strftime('%Y-%m-%d')
                        timeline[date_str]["created"] += 1
                        timeline[date_str]["tasks"].append({
                            "task_id": task_id,
                            "title": task.get("title", ""),
                            "event": "created",
                            "timestamp": task["created_at"],
                            "points": task.get("points", 0)
                        })
                except:
                    pass
            
            # Начало выполнения
            if task.get("started_at"):
                try:
                    started_date = datetime.fromisoformat(task["started_at"].replace('Z', '+00:00')).date()
                    if start_date <= started_date <= end_date:
                        date_str = started_date.strftime('%Y-%m-%d')
                        timeline[date_str]["started"] += 1
                        timeline[date_str]["tasks"].append({
                            "task_id": task_id,
                            "title": task.get("title", ""),
                            "event": "started",
                            "timestamp": task["started_at"],
                            "points": task.get("points", 0)
                        })
                except:
                    pass
            
            # Завершение задачи
            if task.get("completed_at"):
                try:
                    completed_date = datetime.fromisoformat(task["completed_at"].replace('Z', '+00:00')).date()
                    if start_date <= completed_date <= end_date:
                        date_str = completed_date.strftime('%Y-%m-%d')
                        timeline[date_str]["completed"] += 1
                        timeline[date_str]["points_earned"] += task.get("points", 0)
                        timeline[date_str]["tasks"].append({
                            "task_id": task_id,
                            "title": task.get("title", ""),
                            "event": "completed",
                            "timestamp": task["completed_at"],
                            "points": task.get("points", 0)
                        })
                except:
                    pass
        
        # Сортируем события в каждом дне
        for day_data in timeline.values():
            day_data["tasks"].sort(key=lambda x: x["timestamp"])
        
        return {
            "timeline": dict(sorted(timeline.items())),
            "period": {
                "start_date": start_date.strftime('%Y-%m-%d'),
                "end_date": end_date.strftime('%Y-%m-%d'),
                "days": days
            },
            "filters": {
                "category": category,
                "assigned_to": assigned_to
            },
            "summary": {
                "total_created": sum(day["created"] for day in timeline.values()),
                "total_completed": sum(day["completed"] for day in timeline.values()),
                "total_started": sum(day["started"] for day in timeline.values()),
                "total_points_earned": sum(day["points_earned"] for day in timeline.values())
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения timeline задач: {str(e)}")

@router.get("/export/", response_model=Dict[str, Any])
async def export_tasks_data(
    format: str = Query("json", regex="^(json|csv)$"),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    data_manager: DataManager = Depends(get_data_manager)
):
    """
    Экспорт данных задач
    """
    try:
        tasks = data_manager.get_all_tasks()
        
        # Применяем фильтры
        if status:
            tasks = {tid: task for tid, task in tasks.items() if task.get("status") == status}
        
        if category:
            tasks = {tid: task for tid, task in tasks.items() if task.get("category") == category}
        
        if format == "json":
            return {
                "format": "json",
                "data": tasks,
                "exported_at": datetime.now().isoformat(),
                "total_tasks": len(tasks),
                "filters": {"status": status, "category": category}
            }
        
        elif format == "csv":
            # Преобразуем в CSV формат
            csv_data = []
            for task_id, task in tasks.items():
                csv_data.append({
                    "task_id": task_id,
                    "title": task.get("title", ""),
                    "description": task.get("description", ""),
                    "category": task.get("category", ""),
                    "difficulty": task.get("difficulty", ""),
                    "points": task.get("points", 0),
                    "status": task.get("status", ""),
                    "assigned_to": task.get("assigned_to", ""),
                    "created_at": task.get("created_at", ""),
                    "started_at": task.get("started_at", ""),
                    "completed_at": task.get("completed_at", ""),
                    "deadline": task.get("deadline", ""),
                    "priority": task.get("priority", ""),
                    "estimated_time": task.get("estimated_time", ""),
                    "actual_time": task.get("actual_time", "")
                })
            
            return {
                "format": "csv",
                "data": csv_data,
                "exported_at": datetime.now().isoformat(),
                "total_tasks": len(csv_data),
                "filters": {"status": status, "category": category}
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта задач: {str(e)}")
