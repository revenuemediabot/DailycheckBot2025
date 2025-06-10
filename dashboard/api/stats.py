#!/usr/bin/env python3
"""
Statistics API для DailyCheck Bot Dashboard v4.0
Полный набор эндпоинтов для статистики, аналитики и экспорта данных
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
# STATS DATA MANAGER
# ============================================================================

class StatsDataManager:
    """Менеджер данных для статистики с fallback стратегиями"""
    
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
                    logger.info("✅ База данных доступна для статистики")
                    return True
            
            logger.warning("⚠️ База данных недоступна, используем тестовые данные для статистики")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки БД для статистики: {e}")
            return False
    
    def _init_sample_data(self):
        """Инициализация тестовых данных"""
        self.sample_users = self._generate_sample_users()
        self.sample_tasks = self._generate_sample_tasks()
        self.sample_daily_stats = self._generate_daily_stats()
        logger.info("📊 Тестовые данные для статистики сгенерированы")
    
    def _generate_sample_users(self) -> Dict[int, Dict[str, Any]]:
        """Генерация тестовых пользователей для статистики"""
        users = {}
        levels = [1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        
        for i in range(200):  # Больше пользователей для статистики
            user_id = 2000 + i
            join_days_ago = random.randint(1, 365)
            join_date = datetime.now() - timedelta(days=join_days_ago)
            
            # Последняя активность
            last_activity_hours_ago = random.randint(0, 168 * 4)  # До 4 недель
            last_activity = datetime.now() - timedelta(hours=last_activity_hours_ago)
            
            users[user_id] = {
                "user_id": user_id,
                "username": f"stat_user_{i}",
                "first_name": f"StatUser{i}",
                "level": random.choice(levels),
                "xp": random.randint(0, 5000),
                "points": random.randint(0, 2000),
                "theme": random.choice(["default", "dark", "blue", "green", "purple"]),
                "created_at": join_date.isoformat(),
                "last_activity": last_activity.isoformat(),
                "tasks_completed": random.randint(0, 150),
                "streak_days": random.randint(0, 30)
            }
        
        return users
    
    def _generate_sample_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Генерация тестовых задач для статистики"""
        tasks = {}
        categories = ["работа", "здоровье", "обучение", "личное", "финансы"]
        priorities = ["низкий", "средний", "высокий"]
        statuses = ["pending", "in_progress", "completed", "cancelled"]
        
        for i in range(1000):  # Больше задач для статистики
            task_id = f"stat_task_{i}"
            
            # Случайная дата создания
            created_days_ago = random.randint(0, 90)
            created_date = datetime.now() - timedelta(days=created_days_ago)
            
            status = random.choice(statuses)
            completed_at = None
            
            if status == "completed":
                # Случайное время выполнения от создания
                completion_hours = random.randint(1, 72)
                completed_at = created_date + timedelta(hours=completion_hours)
            
            # Назначаем задачу случайному пользователю
            assigned_to = 2000 + random.randint(0, 199)
            
            tasks[task_id] = {
                "id": task_id,
                "title": f"Статистическая задача {i+1}",
                "description": f"Описание задачи {i+1}",
                "category": random.choice(categories),
                "priority": random.choice(priorities),
                "status": status,
                "assigned_to": assigned_to,
                "created_at": created_date.isoformat(),
                "completed_at": completed_at.isoformat() if completed_at else None,
                "points_reward": random.randint(10, 50),
                "estimated_hours": random.randint(1, 8),
                "actual_hours": random.randint(1, 12) if status == "completed" else None
            }
        
        return tasks
    
    def _generate_daily_stats(self) -> Dict[str, Dict[str, int]]:
        """Генерация дневной статистики"""
        daily_stats = {}
        
        for i in range(90):  # 90 дней статистики
            date = datetime.now() - timedelta(days=89-i)
            date_str = date.strftime('%Y-%m-%d')
            
            # Генерируем случайные, но реалистичные данные
            base_users = max(1, 50 - i // 3)  # Рост пользователей со временем
            base_tasks = max(10, 100 - i // 2)  # Рост активности
            
            daily_stats[date_str] = {
                "new_users": random.randint(max(0, base_users - 10), base_users + 15),
                "active_users": random.randint(base_users // 2, base_users * 2),
                "completed_tasks": random.randint(max(5, base_tasks - 20), base_tasks + 30),
                "points_earned": random.randint(500, 2500),
                "total_users": base_users * 5,  # Накопительное количество
                "total_tasks": base_tasks * 10   # Накопительное количество
            }
        
        return daily_stats
    
    def get_all_users(self) -> Dict[int, Dict[str, Any]]:
        """Получение всех пользователей"""
        if self.db_available:
            return self._get_users_from_db()
        else:
            return self.sample_users
    
    def _get_users_from_db(self) -> Dict[int, Dict[str, Any]]:
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
                user_id = user_dict['user_id']
                
                # Добавляем дополнительные поля для статистики
                if 'points' not in user_dict:
                    user_dict['points'] = user_dict.get('xp', 0) // 5
                
                users[user_id] = user_dict
            
            conn.close()
            return users
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения пользователей из БД: {e}")
            return self.sample_users
    
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
                    task_dict['assigned_to'] = task_dict.get('user_id')
                
                # Добавляем поле points_reward если его нет
                if 'points_reward' not in task_dict:
                    task_dict['points_reward'] = 25
                
                tasks[task_id] = task_dict
            
            conn.close()
            return tasks
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения задач из БД: {e}")
            return self.sample_tasks
    
    def get_daily_stats(self, days: int = 30) -> Dict[str, Dict[str, int]]:
        """Получение дневной статистики"""
        if self.db_available:
            return self._get_daily_stats_from_db(days)
        else:
            # Возвращаем последние N дней из тестовых данных
            sorted_dates = sorted(self.sample_daily_stats.keys())
            return {date: self.sample_daily_stats[date] for date in sorted_dates[-days:]}
    
    def _get_daily_stats_from_db(self, days: int) -> Dict[str, Dict[str, int]]:
        """Получение дневной статистики из БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            daily_stats = {}
            
            for i in range(days):
                date = datetime.now() - timedelta(days=days-1-i)
                date_str = date.strftime('%Y-%m-%d')
                
                # Новые пользователи
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM users 
                    WHERE DATE(created_at) = ?
                """, (date_str,))
                new_users = cursor.fetchone()['count']
                
                # Активные пользователи (с активностью в этот день)
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as count 
                    FROM tasks 
                    WHERE DATE(created_at) = ? OR DATE(completed_at) = ?
                """, (date_str, date_str))
                active_users = cursor.fetchone()['count']
                
                # Выполненные задачи
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM tasks 
                    WHERE DATE(completed_at) = ? AND completed = 1
                """, (date_str,))
                completed_tasks = cursor.fetchone()['count']
                
                # Всего пользователей на дату
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM users 
                    WHERE DATE(created_at) <= ?
                """, (date_str,))
                total_users = cursor.fetchone()['count']
                
                # Всего задач на дату
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM tasks 
                    WHERE DATE(created_at) <= ?
                """, (date_str,))
                total_tasks = cursor.fetchone()['count']
                
                daily_stats[date_str] = {
                    "new_users": new_users,
                    "active_users": active_users,
                    "completed_tasks": completed_tasks,
                    "points_earned": completed_tasks * 25,  # Примерный расчет
                    "total_users": total_users,
                    "total_tasks": total_tasks
                }
            
            conn.close()
            return daily_stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения дневной статистики из БД: {e}")
            return self._get_daily_stats_fallback(days)
    
    def _get_daily_stats_fallback(self, days: int) -> Dict[str, Dict[str, int]]:
        """Fallback для дневной статистики"""
        daily_stats = {}
        
        for i in range(days):
            date = datetime.now() - timedelta(days=days-1-i)
            date_str = date.strftime('%Y-%m-%d')
            
            daily_stats[date_str] = {
                "new_users": random.randint(1, 10),
                "active_users": random.randint(15, 45),
                "completed_tasks": random.randint(20, 80),
                "points_earned": random.randint(500, 2000),
                "total_users": 100 + i * 2,
                "total_tasks": 500 + i * 10
            }
        
        return daily_stats
    
    def get_overview_stats(self) -> Dict[str, Any]:
        """Получение общей статистики"""
        users = self.get_all_users()
        tasks = self.get_all_tasks()
        
        total_users = len(users)
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks.values() if t.get("status") == "completed"])
        total_points = sum(u.get("points", 0) for u in users.values())
        
        # Активность за последние 24 часа
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        active_users_24h = 0
        for user in users.values():
            if user.get("last_activity"):
                try:
                    last_activity = datetime.fromisoformat(user["last_activity"].replace('Z', '+00:00'))
                    if last_activity >= yesterday:
                        active_users_24h += 1
                except:
                    pass
        
        return {
            "total_users": total_users,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "total_points": total_points,
            "active_users_24h": active_users_24h,
            "completion_rate": (completed_tasks / max(total_tasks, 1)) * 100,
            "avg_points_per_user": total_points / max(total_users, 1),
            "engagement_rate": (active_users_24h / max(total_users, 1)) * 100
        }

# Глобальный экземпляр менеджера данных
stats_data_manager = StatsDataManager()

# ============================================================================
# DEPENDENCY FUNCTIONS
# ============================================================================

def get_data_manager() -> StatsDataManager:
    """Dependency для получения менеджера данных"""
    return stats_data_manager

# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter(prefix="/api/stats", tags=["statistics"])

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class OverviewStatsResponse(BaseModel):
    total_users: int
    total_tasks: int
    completed_tasks: int
    total_points: int
    kpi_metrics: Dict[str, Any]
    trends: Dict[str, Any]

class DailyStatsResponse(BaseModel):
    daily_stats: Dict[str, Dict[str, int]]
    period: Dict[str, Any]
    summary: Dict[str, Any]
    peaks: Dict[str, Any]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _calculate_kpi_metrics(data_manager: StatsDataManager) -> Dict[str, Any]:
    """Вычислить ключевые показатели эффективности"""
    try:
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
    
    except Exception as e:
        logger.error(f"❌ Ошибка расчета KPI метрик: {e}")
        return {
            "total_users": 0,
            "total_tasks": 0,
            "completed_tasks": 0,
            "total_points": 0,
            "active_users_24h": 0,
            "new_users_24h": 0,
            "completed_tasks_24h": 0,
            "completion_rate": 0,
            "avg_points_per_user": 0,
            "user_engagement_rate": 0
        }

def _calculate_trends(data_manager: StatsDataManager) -> Dict[str, Any]:
    """Вычислить тренды для различных метрик"""
    try:
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
    
    except Exception as e:
        logger.error(f"❌ Ошибка расчета трендов: {e}")
        return {"error": f"Ошибка расчета трендов: {str(e)}"}

def _calculate_trend(values: List[int]) -> Dict[str, Any]:
    """Вычислить тренд для списка значений"""
    try:
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
    
    except Exception as e:
        logger.error(f"❌ Ошибка расчета тренда: {e}")
        return {"direction": "stable", "percentage": 0, "absolute": 0}

def _analyze_performance(users: Dict, tasks: Dict, days: int) -> Dict[str, Any]:
    """Анализ производительности за период"""
    try:
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
    
    except Exception as e:
        logger.error(f"❌ Ошибка анализа производительности: {e}")
        return {
            "users": {"total": 0, "active": 0, "retention_rate": 0},
            "tasks": {"total": 0, "completed": 0, "completion_rate": 0, "avg_per_user": 0, "avg_completion_time_hours": 0},
            "categories": {},
            "efficiency_score": 0
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
    try:
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
    
    except Exception as e:
        logger.error(f"❌ Ошибка сравнения периодов: {e}")
        return {
            "current_period": {"users": 0, "tasks": 0, "completed_tasks": 0},
            "previous_period": {"users": 0, "tasks": 0, "completed_tasks": 0},
            "changes": {"users": 0, "tasks": 0, "completed_tasks": 0},
            "percentage_changes": {"users": 0, "tasks": 0, "completed_tasks": 0}
        }

def _analyze_user_engagement(users: Dict, tasks: Dict) -> Dict[str, Any]:
    """Анализ вовлеченности пользователей"""
    try:
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
    
    except Exception as e:
        logger.error(f"❌ Ошибка анализа вовлеченности: {e}")
        return {
            "daily_active_users": 0,
            "weekly_active_users": 0,
            "monthly_active_users": 0,
            "retention_rates": {"daily": 0, "weekly": 0, "monthly": 0},
            "activity_distribution": {"very_active": 0, "active": 0, "moderate": 0, "inactive": 0},
            "engagement_score": 0,
            "avg_tasks_per_user": 0,
            "avg_session_frequency": 0
        }

def _segment_users(users: Dict, tasks: Dict) -> Dict[str, Any]:
    """Сегментация пользователей"""
    try:
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
    
    except Exception as e:
        logger.error(f"❌ Ошибка сегментации пользователей: {e}")
        return {
            "segments": {"champions": [], "loyal_users": [], "potential_loyalists": [], "new_users": [], "at_risk": [], "hibernating": []},
            "segment_sizes": {"champions": 0, "loyal_users": 0, "potential_loyalists": 0, "new_users": 0, "at_risk": 0, "hibernating": 0},
            "total_users": 0
        }

def _perform_cohort_analysis(users: Dict) -> Dict[str, Any]:
    """Когортный анализ пользователей"""
    try:
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
    
    except Exception as e:
        logger.error(f"❌ Ошибка когортного анализа: {e}")
        return {"cohorts": {}, "total_cohorts": 0}

# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.get("/overview", response_model=Dict[str, Any])
async def get_overview_stats(
    data_manager: StatsDataManager = Depends(get_data_manager)
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
        logger.error(f"❌ Ошибка получения общей статистики: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения общей статистики: {str(e)}")

@router.get("/daily", response_model=Dict[str, Any])
async def get_daily_stats(
    days: int = Query(30, ge=1, le=365),
    data_manager: StatsDataManager = Depends(get_data_manager)
):
    """
    Получить дневную статистику за указанный период
    """
    try:
        daily_stats = data_manager.get_daily_stats(days)
        
        if not daily_stats:
            return {
                "daily_stats": {},
                "period": {"days": days, "start_date": None, "end_date": None},
                "summary": {},
                "peaks": {}
            }
        
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
        logger.error(f"❌ Ошибка получения дневной статистики: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения дневной статистики: {str(e)}")

@router.get("/performance", response_model=Dict[str, Any])
async def get_performance_stats(
    period: str = Query("month", regex="^(week|month|quarter|year)$"),
    data_manager: StatsDataManager = Depends(get_data_manager)
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
        logger.error(f"❌ Ошибка получения статистики производительности: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики производительности: {str(e)}")

@router.get("/engagement", response_model=Dict[str, Any])
async def get_engagement_stats(
    data_manager: StatsDataManager = Depends(get_data_manager)
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
        logger.error(f"❌ Ошибка получения статистики вовлеченности: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики вовлеченности: {str(e)}")

@router.get("/export", response_model=Dict[str, Any])
async def export_stats(
    format: str = Query("json", regex="^(json|csv)$"),
    stats_type: str = Query("overview", regex="^(overview|daily|performance|engagement)$"),
    period: Optional[str] = Query("month", regex="^(week|month|quarter|year)$"),
    data_manager: StatsDataManager = Depends(get_data_manager)
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
        else:
            data = {}
        
        return {
            "format": format,
            "stats_type": stats_type,
            "period": period,
            "data": data,
            "exported_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка экспорта статистики: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта статистики: {str(e)}")

# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ENDPOINTS
# ============================================================================

@router.get("/health", response_model=Dict[str, Any])
async def get_stats_health():
    """Health check для системы статистики"""
    
    try:
        return {
            "status": "healthy",
            "endpoints_available": [
                "overview",
                "daily", 
                "performance",
                "engagement",
                "export"
            ],
            "database_status": stats_data_manager.db_available,
            "data_source": "database" if stats_data_manager.db_available else "sample_data",
            "total_endpoints": 5,
            "calculations_available": [
                "kpi_metrics",
                "trends",
                "performance_analysis",
                "user_segmentation",
                "cohort_analysis"
            ],
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Ошибка health check статистики: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/summary", response_model=Dict[str, Any])
async def get_stats_summary(
    data_manager: StatsDataManager = Depends(get_data_manager)
):
    """Краткая сводка всех статистик"""
    
    try:
        # Базовые данные
        overview = data_manager.get_overview_stats()
        daily_stats = data_manager.get_daily_stats(7)  # Последние 7 дней
        users = data_manager.get_all_users()
        tasks = data_manager.get_all_tasks()
        
        # Быстрые расчеты
        kpi = _calculate_kpi_metrics(data_manager)
        trends = _calculate_trends(data_manager)
        engagement = _analyze_user_engagement(users, tasks)
        
        return {
            "quick_stats": {
                "total_users": overview.get("total_users", 0),
                "total_tasks": overview.get("total_tasks", 0),
                "completion_rate": overview.get("completion_rate", 0),
                "active_users_24h": kpi.get("active_users_24h", 0),
                "engagement_score": engagement.get("engagement_score", 0)
            },
            "recent_trends": {
                "users_trend": trends.get("users", {}).get("direction", "stable"),
                "tasks_trend": trends.get("tasks", {}).get("direction", "stable"),
                "activity_trend": trends.get("activity", {}).get("direction", "stable")
            },
            "top_insights": [
                f"Всего пользователей: {overview.get('total_users', 0)}",
                f"Завершено задач: {overview.get('completed_tasks', 0)}",
                f"Активных за сутки: {kpi.get('active_users_24h', 0)}",
                f"Рейтинг вовлеченности: {engagement.get('engagement_score', 0)}"
            ],
            "data_source": "database" if data_manager.db_available else "sample_data",
            "generated_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения сводки статистики: {e}")
        raise HTTPException(status_code=500, detail="Ошибка генерации сводки")
