#!/usr/bin/env python3
"""
Users API для DailyCheck Bot Dashboard v4.0
Полный набор эндпоинтов для управления пользователями, лидерборда и экспорта
"""

import sys
import os
import logging
import json
import sqlite3
import random
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Optional, Dict, Any
import traceback

# Добавляем корневую папку в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from fastapi import APIRouter, HTTPException, Depends, Query, Response
    from pydantic import BaseModel
except ImportError as e:
    print(f"❌ Ошибка импорта FastAPI: {e}")
    raise

logger = logging.getLogger(__name__)

# ============================================================================
# USERS DATA MANAGER
# ============================================================================

class UsersDataManager:
    """Менеджер данных для пользователей с fallback стратегиями"""
    
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        
        # Попытка подключения к SQLite
        self.db_path = self.data_dir / "dailycheck.db"
        self.db_available = self._check_database()
        
        # Инициализация с тестовыми данными если БД недоступна
        if not self.db_available:
            self._init_sample_data()
    
    def _check_database(self) -> bool:
        """Проверка доступности базы данных"""
        try:
            if self.db_path.exists():
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                conn.close()
                
                if tables:
                    logger.info("✅ База данных доступна для пользователей")
                    return True
            
            logger.warning("⚠️ База данных недоступна, используем тестовые данные для пользователей")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки БД для пользователей: {e}")
            return False
    
    def _init_sample_data(self):
        """Инициализация тестовых данных"""
        self.sample_users = self._generate_sample_users()
        self.sample_tasks = self._generate_sample_tasks()
        self.sample_achievements = self._generate_achievements_data()
        logger.info("👥 Тестовые данные для пользователей сгенерированы")
    
    def _generate_sample_users(self) -> Dict[str, Dict[str, Any]]:
        """Генерация тестовых пользователей"""
        users = {}
        levels = [1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        languages = ["ru", "en", "de", "fr", "es"]
        themes = ["default", "dark", "blue", "green", "purple"]
        
        first_names = ["Александр", "Мария", "Иван", "Анна", "Петр", "Елена", "Дмитрий", "Ольга", 
                      "Сергей", "Татьяна", "Андрей", "Наталья", "Михаил", "Ирина", "Владимир"]
        last_names = ["Иванов", "Петров", "Сидоров", "Козлов", "Волков", "Смирнов", "Попов", 
                     "Соколов", "Лебедев", "Новиков", "Морозов", "Васильев", "Федоров"]
        
        for i in range(250):  # Больше пользователей для демонстрации
            user_id = f"user_{3000 + i}"
            join_days_ago = random.randint(1, 400)
            join_date = datetime.now() - timedelta(days=join_days_ago)
            
            # Последняя активность
            last_activity_hours_ago = random.randint(0, 240)  # До 10 дней
            last_activity = datetime.now() - timedelta(hours=last_activity_hours_ago)
            
            # Генерируем достижения
            achievements = []
            if random.random() < 0.8:  # 80% имеют хотя бы одно достижение
                available_achievements = ["first_task", "task_master", "week_streak", "month_streak", 
                                        "early_bird", "night_owl", "speed_runner", "perfectionist"]
                num_achievements = random.randint(1, min(5, len(available_achievements)))
                achievements = random.sample(available_achievements, num_achievements)
            
            users[user_id] = {
                "user_id": user_id,
                "username": f"user_{i}",
                "first_name": random.choice(first_names),
                "last_name": random.choice(last_names),
                "level": random.choice(levels),
                "xp": random.randint(0, 5000),
                "points": random.randint(0, 2500),
                "theme": random.choice(themes),
                "language_code": random.choice(languages),
                "created_at": join_date.isoformat(),
                "last_activity": last_activity.isoformat(),
                "completed_tasks": random.randint(0, 200),
                "streak": random.randint(0, 45),
                "achievements": achievements,
                "settings": {
                    "notifications": random.choice([True, False]),
                    "ai_enabled": random.choice([True, False]),
                    "theme": random.choice(themes),
                    "timezone": random.choice(["UTC", "Europe/Moscow", "America/New_York"])
                }
            }
        
        return users
    
    def _generate_sample_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Генерация тестовых задач для пользователей"""
        tasks = {}
        categories = ["работа", "здоровье", "обучение", "личное", "финансы"]
        priorities = ["низкий", "средний", "высокий"]
        statuses = ["pending", "in_progress", "completed", "cancelled"]
        
        for i in range(1500):  # Много задач для реалистичности
            task_id = f"user_task_{i}"
            
            # Случайная дата создания
            created_days_ago = random.randint(0, 120)
            created_date = datetime.now() - timedelta(days=created_days_ago)
            
            status = random.choice(statuses)
            completed_at = None
            
            if status == "completed":
                # Случайное время выполнения от создания
                completion_hours = random.randint(1, 96)
                completed_at = created_date + timedelta(hours=completion_hours)
            
            # Назначаем задачу случайному пользователю
            assigned_to = f"user_{3000 + random.randint(0, 249)}"
            
            tasks[task_id] = {
                "id": task_id,
                "title": f"Пользовательская задача {i+1}",
                "description": f"Описание задачи {i+1}",
                "category": random.choice(categories),
                "priority": random.choice(priorities),
                "status": status,
                "assigned_to": assigned_to,
                "created_at": created_date.isoformat(),
                "completed_at": completed_at.isoformat() if completed_at else None,
                "points": random.randint(15, 75),
                "estimated_hours": random.randint(1, 8),
                "actual_hours": random.randint(1, 12) if status == "completed" else None
            }
        
        return tasks
    
    def _generate_achievements_data(self) -> Dict[str, Dict[str, Any]]:
        """Генерация данных о достижениях"""
        achievements = {
            "first_task": {"name": "Первое задание", "description": "Выполнил первую задачу", "count": 0},
            "task_master": {"name": "Мастер заданий", "description": "Выполнил 100 задач", "count": 0},
            "week_streak": {"name": "Недельная серия", "description": "7 дней подряд", "count": 0},
            "month_streak": {"name": "Месячная серия", "description": "30 дней подряд", "count": 0},
            "early_bird": {"name": "Ранняя пташка", "description": "Выполнение задач до 8 утра", "count": 0},
            "night_owl": {"name": "Сова", "description": "Выполнение задач после 22:00", "count": 0},
            "speed_runner": {"name": "Спидранер", "description": "Быстрое выполнение задач", "count": 0},
            "perfectionist": {"name": "Перфекционист", "description": "100% выполнение", "count": 0},
            "social_butterfly": {"name": "Социальная бабочка", "description": "Активность в сообществе", "count": 0},
            "helper": {"name": "Помощник", "description": "Помощь другим пользователям", "count": 0}
        }
        
        # Подсчитываем количество каждого достижения
        for user in self.sample_users.values():
            for achievement in user.get("achievements", []):
                if achievement in achievements:
                    achievements[achievement]["count"] += 1
        
        return achievements
    
    def get_all_users(self) -> Dict[str, Dict[str, Any]]:
        """Получение всех пользователей"""
        if self.db_available:
            return self._get_users_from_db()
        else:
            return self.sample_users
    
    def _get_users_from_db(self) -> Dict[str, Dict[str, Any]]:
        """Получение пользователей из БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM users")
            users_data = cursor.fetchall()
            
            users = {}
            for row in users_data:
                user_dict = dict(row)
                user_id = str(user_dict['user_id'])
                
                # Добавляем дополнительные поля для совместимости
                if 'points' not in user_dict:
                    user_dict['points'] = user_dict.get('xp', 0) // 5
                
                if 'completed_tasks' not in user_dict:
                    # Считаем выполненные задачи
                    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND completed = 1", (user_dict['user_id'],))
                    completed_count = cursor.fetchone()[0]
                    user_dict['completed_tasks'] = completed_count
                
                if 'streak' not in user_dict:
                    user_dict['streak'] = random.randint(0, 30)
                
                if 'achievements' not in user_dict:
                    user_dict['achievements'] = []
                
                if 'settings' not in user_dict:
                    user_dict['settings'] = {
                        "notifications": True,
                        "ai_enabled": False,
                        "theme": user_dict.get("theme", "default"),
                        "timezone": "UTC"
                    }
                
                users[user_id] = user_dict
            
            conn.close()
            return users
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователей из БД: {e}")
            return self.sample_users
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получение конкретного пользователя"""
        users = self.get_all_users()
        return users.get(user_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Получение всех задач"""
        if self.db_available:
            return self._get_tasks_from_db()
        else:
            return self.sample_tasks
    
    def _get_tasks_from_db(self) -> Dict[str, Dict[str, Any]]:
        """Получение задач из БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM tasks")
            tasks_data = cursor.fetchall()
            
            tasks = {}
            for row in tasks_data:
                task_dict = dict(row)
                task_id = str(task_dict.get('id', task_dict.get('task_id', '')))
                
                # Преобразуем статус для совместимости
                if task_dict.get('completed'):
                    task_dict['status'] = 'completed'
                else:
                    task_dict['status'] = 'pending'
                
                # Добавляем поле assigned_to если его нет
                if 'assigned_to' not in task_dict:
                    task_dict['assigned_to'] = str(task_dict.get('user_id', ''))
                
                # Добавляем поле points если его нет
                if 'points' not in task_dict:
                    task_dict['points'] = 25
                
                tasks[task_id] = task_dict
            
            conn.close()
            return tasks
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения задач из БД: {e}")
            return self.sample_tasks
    
    def get_users_stats(self) -> Dict[str, Any]:
        """Получение статистики пользователей"""
        users = self.get_all_users()
        tasks = self.get_all_tasks()
        
        total_users = len(users)
        
        # Подсчет по уровням
        user_levels = defaultdict(int)
        for user in users.values():
            user_levels[user.get('level', 1)] += 1
        
        # Подсчет активных пользователей
        now = datetime.now()
        active_users = {
            "today": 0,
            "week": 0,
            "month": 0
        }
        
        for user in users.values():
            if user.get("last_activity"):
                try:
                    last_activity = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00'))
                    days_since = (now - last_activity).days
                    
                    if days_since == 0:
                        active_users["today"] += 1
                    if days_since <= 7:
                        active_users["week"] += 1
                    if days_since <= 30:
                        active_users["month"] += 1
                except:
                    pass
        
        return {
            "total_users": total_users,
            "user_levels": dict(user_levels),
            "active_users": active_users,
            "avg_level": sum(u.get('level', 1) for u in users.values()) / max(total_users, 1),
            "avg_points": sum(u.get('points', 0) for u in users.values()) / max(total_users, 1),
            "top_level": max((u.get('level', 1) for u in users.values()), default=1)
        }
    
    def get_leaderboard(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Получение таблицы лидеров"""
        users = self.get_all_users()
        
        # Сортируем по очкам, затем по уровню
        sorted_users = sorted(
            users.values(),
            key=lambda x: (x.get('points', 0), x.get('level', 1)),
            reverse=True
        )
        
        leaderboard = []
        for i, user in enumerate(sorted_users[:limit]):
            leaderboard.append({
                "position": i + 1,
                "user_id": user.get("user_id"),
                "username": user.get("username", "Unknown"),
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name", ""),
                "points": user.get("points", 0),
                "level": user.get("level", 1),
                "completed_tasks": user.get("completed_tasks", 0),
                "streak": user.get("streak", 0),
                "last_activity": user.get("last_activity")
            })
        
        return leaderboard
    
    def get_achievements_stats(self) -> Dict[str, Dict[str, Any]]:
        """Получение статистики достижений"""
        if self.db_available:
            return self._get_achievements_from_db()
        else:
            return self.sample_achievements
    
    def _get_achievements_from_db(self) -> Dict[str, Dict[str, Any]]:
        """Получение статистики достижений из БД"""
        try:
            # Пока нет таблицы достижений в БД, используем тестовые данные
            return self.sample_achievements
        except Exception as e:
            logger.error(f"❌ Ошибка получения достижений из БД: {e}")
            return self.sample_achievements
    
    def _is_user_active(self, user_data: Dict[str, Any]) -> bool:
        """Проверка активности пользователя"""
        if not user_data.get("last_activity"):
            return False
        
        try:
            last_activity = datetime.fromisoformat(user_data["last_activity"].replace('Z', '+00:00'))
            days_since = (datetime.now() - last_activity).days
            return days_since <= 7  # Активен если был онлайн последние 7 дней
        except:
            return False

# Глобальный экземпляр менеджера данных
users_data_manager = UsersDataManager()

# ============================================================================
# DEPENDENCY FUNCTIONS
# ============================================================================

def get_data_manager() -> UsersDataManager:
    """Dependency для получения менеджера данных"""
    return users_data_manager

# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter(prefix="/api/users", tags=["users"])

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class UserResponse(BaseModel):
    user_id: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    points: int = 0
    level: int = 1
    completed_tasks: int = 0
    streak: int = 0
    status: str = "inactive"

class UserDetailResponse(BaseModel):
    user_id: str
    username: str
    points: int
    level: int
    statistics: Dict[str, Any]
    recent_activity: List[Dict[str, Any]]

# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/", response_model=Dict[str, Any])
async def get_all_users(
    data_manager: UsersDataManager = Depends(get_data_manager),
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
        if sort_by == "last_activity":
            # Специальная обработка для дат
            users_list.sort(
                key=lambda x: datetime.fromisoformat(x.get(sort_by, "1970-01-01T00:00:00").replace('Z', '+00:00')) if x.get(sort_by) else datetime.min,
                reverse=reverse
            )
        else:
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
        logger.error(f"❌ Ошибка получения пользователей: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения пользователей: {str(e)}")

@router.get("/{user_id}", response_model=Dict[str, Any])
async def get_user(
    user_id: str,
    data_manager: UsersDataManager = Depends(get_data_manager)
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
        logger.error(f"❌ Ошибка получения пользователя {user_id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения пользователя: {str(e)}")

@router.get("/stats/overview", response_model=Dict[str, Any])
async def get_users_overview_stats(
    data_manager: UsersDataManager = Depends(get_data_manager)
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
        logger.error(f"❌ Ошибка получения статистики пользователей: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")

@router.get("/leaderboard/", response_model=Dict[str, Any])
async def get_leaderboard(
    limit: int = Query(20, ge=1, le=100),
    period: str = Query("all", regex="^(all|week|month)$"),
    data_manager: UsersDataManager = Depends(get_data_manager)
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
        logger.error(f"❌ Ошибка получения таблицы лидеров: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения таблицы лидеров: {str(e)}")

@router.get("/achievements/stats", response_model=Dict[str, Any])
async def get_achievements_stats(
    data_manager: UsersDataManager = Depends(get_data_manager)
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
        
        total_users = len(data_manager.get_all_users())
        
        for achievement_id, stats in achievements_stats.items():
            count = stats.get("count", 0)
            enriched_stats[achievement_id] = {
                **stats,
                "name": achievement_names.get(achievement_id, achievement_id.replace("_", " ").title()),
                "percentage": (count / max(total_users, 1)) * 100
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
        logger.error(f"❌ Ошибка получения статистики достижений: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики достижений: {str(e)}")

@router.get("/activity/timeline", response_model=Dict[str, Any])
async def get_activity_timeline(
    user_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    data_manager: UsersDataManager = Depends(get_data_manager)
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
        for user_id_key, user in users.items():
            # Регистрация пользователя
            if user.get("created_at"):
                try:
                    reg_date = datetime.fromisoformat(user["created_at"].replace('Z', '+00:00')).date()
                    if start_date <= reg_date <= end_date:
                        date_str = reg_date.strftime('%Y-%m-%d')
                        timeline[date_str]["new_users"] += 1
                        timeline[date_str]["activities"].append({
                            "type": "registration",
                            "user_id": user_id_key,
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
        logger.error(f"❌ Ошибка получения timeline: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения timeline: {str(e)}")

@router.get("/export/", response_model=Dict[str, Any])
async def export_users_data(
    format: str = Query("json", regex="^(json|csv)$"),
    data_manager: UsersDataManager = Depends(get_data_manager)
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
        logger.error(f"❌ Ошибка экспорта пользователей: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта: {str(e)}")

# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ENDPOINTS
# ============================================================================

@router.get("/health/", response_model=Dict[str, Any])
async def get_users_health():
    """Health check для системы пользователей"""
    
    try:
        return {
            "status": "healthy",
            "endpoints_available": [
                "get_all_users",
                "get_user", 
                "stats/overview",
                "leaderboard",
                "achievements/stats",
                "activity/timeline",
                "export"
            ],
            "database_status": users_data_manager.db_available,
            "data_source": "database" if users_data_manager.db_available else "sample_data",
            "total_endpoints": 7,
            "features_available": [
                "pagination",
                "search",
                "sorting",
                "leaderboards",
                "achievements",
                "timeline",
                "export"
            ],
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Ошибка health check пользователей: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/summary/", response_model=Dict[str, Any])
async def get_users_summary(
    data_manager: UsersDataManager = Depends(get_data_manager)
):
    """Краткая сводка пользователей"""
    
    try:
        users = data_manager.get_all_users()
        stats = data_manager.get_users_stats()
        leaderboard = data_manager.get_leaderboard(5)  # Топ-5
        
        return {
            "quick_stats": {
                "total_users": len(users),
                "active_users_week": stats["active_users"]["week"],
                "top_level": stats["top_level"],
                "avg_points": round(stats["avg_points"], 1)
            },
            "top_users": leaderboard[:3],  # Топ-3
            "activity_status": {
                "very_active": len([u for u in users.values() if data_manager._is_user_active(u)]),
                "inactive": len(users) - len([u for u in users.values() if data_manager._is_user_active(u)])
            },
            "recent_registrations": len([
                u for u in users.values()
                if u.get("created_at") and 
                (datetime.now() - datetime.fromisoformat(u["created_at"].replace('Z', '+00:00'))).days <= 7
            ]),
            "data_source": "database" if data_manager.db_available else "sample_data",
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения сводки пользователей: {e}")
        raise HTTPException(status_code=500, detail="Ошибка генерации сводки")
