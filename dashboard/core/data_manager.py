import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
from pathlib import Path

class DataManager:
    """Менеджер для работы с JSON файлами данных бота"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.users_file = self.data_dir / "users.json"
        self.tasks_file = self.data_dir / "tasks.json"
        self.stats_file = self.data_dir / "stats.json"
        
        # Создаем директорию если её нет
        self.data_dir.mkdir(exist_ok=True)
        
        # Инициализируем файлы если их нет
        self._init_files()
    
    def _init_files(self):
        """Инициализация JSON файлов если они не существуют"""
        if not self.users_file.exists():
            self._save_json(self.users_file, {})
        
        if not self.tasks_file.exists():
            self._save_json(self.tasks_file, {})
            
        if not self.stats_file.exists():
            self._save_json(self.stats_file, {
                "total_users": 0,
                "active_users": 0,
                "completed_tasks": 0,
                "total_points": 0,
                "daily_stats": {}
            })
    
    def _load_json(self, file_path: Path) -> Dict:
        """Загрузка данных из JSON файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_json(self, file_path: Path, data: Dict):
        """Сохранение данных в JSON файл"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # === РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ===
    
    def get_all_users(self) -> Dict:
        """Получить всех пользователей"""
        return self._load_json(self.users_file)
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Получить конкретного пользователя"""
        users = self.get_all_users()
        return users.get(str(user_id))
    
    def get_users_stats(self) -> Dict:
        """Получить статистику пользователей"""
        users = self.get_all_users()
        
        total_users = len(users)
        active_users = len([u for u in users.values() 
                           if self._is_user_active(u)])
        
        # Топ пользователи по очкам
        top_users = sorted(
            [(uid, user.get('points', 0), user.get('username', 'Unknown')) 
             for uid, user in users.items()],
            key=lambda x: x[1], reverse=True
        )[:10]
        
        # Распределение по уровням
        levels_distribution = {}
        for user in users.values():
            level = user.get('level', 1)
            levels_distribution[level] = levels_distribution.get(level, 0) + 1
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "top_users": top_users,
            "levels_distribution": levels_distribution,
            "avg_points": sum(u.get('points', 0) for u in users.values()) / max(total_users, 1)
        }
    
    def _is_user_active(self, user: Dict) -> bool:
        """Проверить активность пользователя (активность за последние 7 дней)"""
        last_activity = user.get('last_activity')
        if not last_activity:
            return False
        
        try:
            last_date = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
            return (datetime.now() - last_date).days <= 7
        except:
            return False
    
    # === РАБОТА С ЗАДАЧАМИ ===
    
    def get_all_tasks(self) -> Dict:
        """Получить все задачи"""
        return self._load_json(self.tasks_file)
    
    def get_tasks_stats(self) -> Dict:
        """Получить статистику задач"""
        tasks = self.get_all_tasks()
        
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks.values() 
                              if t.get('status') == 'completed'])
        
        # Статистика по категориям
        categories_stats = {}
        difficulty_stats = {}
        
        for task in tasks.values():
            category = task.get('category', 'other')
            difficulty = task.get('difficulty', 'medium')
            
            categories_stats[category] = categories_stats.get(category, 0) + 1
            difficulty_stats[difficulty] = difficulty_stats.get(difficulty, 0) + 1
        
        # Последние выполненные задачи
        recent_completed = []
        for task_id, task in tasks.items():
            if task.get('status') == 'completed' and task.get('completed_at'):
                recent_completed.append({
                    'id': task_id,
                    'title': task.get('title', 'Unknown'),
                    'completed_at': task.get('completed_at'),
                    'user_id': task.get('assigned_to'),
                    'points': task.get('points', 0)
                })
        
        recent_completed.sort(key=lambda x: x['completed_at'], reverse=True)
        
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_rate": (completed_tasks / max(total_tasks, 1)) * 100,
            "categories_stats": categories_stats,
            "difficulty_stats": difficulty_stats,
            "recent_completed": recent_completed[:10]
        }
    
    # === РАБОТА СО СТАТИСТИКОЙ ===
    
    def get_daily_stats(self, days: int = 30) -> Dict:
        """Получить дневную статистику за последние N дней"""
        stats = self._load_json(self.stats_file)
        daily_stats = stats.get('daily_stats', {})
        
        # Генерируем статистику за последние дни
        result = {}
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            result[date] = daily_stats.get(date, {
                'new_users': 0,
                'completed_tasks': 0,
                'points_earned': 0,
                'active_users': 0
            })
        
        return dict(sorted(result.items()))
    
    def update_daily_stats(self, date: str = None, **kwargs):
        """Обновить дневную статистику"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        stats = self._load_json(self.stats_file)
        
        if 'daily_stats' not in stats:
            stats['daily_stats'] = {}
        
        if date not in stats['daily_stats']:
            stats['daily_stats'][date] = {
                'new_users': 0,
                'completed_tasks': 0,
                'points_earned': 0,
                'active_users': 0
            }
        
        # Обновляем статистику
        for key, value in kwargs.items():
            if key in stats['daily_stats'][date]:
                stats['daily_stats'][date][key] += value
        
        self._save_json(self.stats_file, stats)
    
    def get_overview_stats(self) -> Dict:
        """Получить общую статистику для дашборда"""
        users_stats = self.get_users_stats()
        tasks_stats = self.get_tasks_stats()
        
        # Последняя активность
        users = self.get_all_users()
        last_activities = []
        
        for user_id, user in users.items():
            if user.get('last_activity'):
                last_activities.append({
                    'user_id': user_id,
                    'username': user.get('username', 'Unknown'),
                    'last_activity': user.get('last_activity'),
                    'points': user.get('points', 0),
                    'level': user.get('level', 1)
                })
        
        last_activities.sort(key=lambda x: x['last_activity'], reverse=True)
        
        return {
            "users": users_stats,
            "tasks": tasks_stats,
            "recent_activity": last_activities[:10],
            "system_info": {
                "data_files": {
                    "users": self.users_file.exists(),
                    "tasks": self.tasks_file.exists(),
                    "stats": self.stats_file.exists()
                },
                "last_update": datetime.now().isoformat()
            }
        }
    
    # === РАБОТА С ГЕЙМИФИКАЦИЕЙ ===
    
    def get_leaderboard(self, limit: int = 20) -> List[Dict]:
        """Получить таблицу лидеров"""
        users = self.get_all_users()
        
        leaderboard = []
        for user_id, user in users.items():
            leaderboard.append({
                'user_id': user_id,
                'username': user.get('username', 'Unknown'),
                'points': user.get('points', 0),
                'level': user.get('level', 1),
                'completed_tasks': user.get('completed_tasks', 0),
                'streak': user.get('streak', 0),
                'last_activity': user.get('last_activity'),
                'achievements': user.get('achievements', [])
            })
        
        # Сортируем по очкам
        leaderboard.sort(key=lambda x: x['points'], reverse=True)
        
        # Добавляем позиции
        for i, user in enumerate(leaderboard[:limit]):
            user['position'] = i + 1
        
        return leaderboard[:limit]
    
    def get_achievements_stats(self) -> Dict:
        """Получить статистику по достижениям"""
        users = self.get_all_users()
        
        all_achievements = {}
        for user in users.values():
            for achievement in user.get('achievements', []):
                achievement_id = achievement.get('id', achievement)
                if achievement_id not in all_achievements:
                    all_achievements[achievement_id] = {
                        'count': 0,
                        'users': []
                    }
                all_achievements[achievement_id]['count'] += 1
                all_achievements[achievement_id]['users'].append(user.get('username', 'Unknown'))
        
        return all_achievements
    
    # === РАБОТА С ЭКСПОРТОМ/ИМПОРТОМ ===
    
    def export_data(self) -> Dict:
        """Экспорт всех данных"""
        return {
            'users': self.get_all_users(),
            'tasks': self.get_all_tasks(),
            'stats': self._load_json(self.stats_file),
            'export_date': datetime.now().isoformat()
        }
    
    def backup_data(self, backup_dir: str = "backups"):
        """Создать резервную копию данных"""
        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_path / f"backup_{timestamp}.json"
        
        backup_data = self.export_data()
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return backup_file
