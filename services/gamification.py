# services/gamification.py

LEVELS = [
    "Новичок", "Начинающий", "Исследователь", "Планировщик",
    "Гуру задач", "Лидер", "Наставник", "Пример для подражания",
    "Чемпион", "Вдохновитель", "Эксперт", "Тренер", "Легенда",
    "Герой дня", "Король продуктивности", "Железный человек"
]

ACHIEVEMENTS = [
    {"id": 1, "name": "Первая задача", "desc": "Выполните первую задачу"},
    {"id": 2, "name": "Семидневный стрик", "desc": "7 дней без пропусков"},
    {"id": 3, "name": "Гуру привычек", "desc": "10 привычек подряд"},
    # ... остальные ачивки
]

def get_level(xp: int) -> str:
    level_index = min(xp // 100, len(LEVELS) - 1)
    return LEVELS[level_index]

def check_achievement(user_data) -> list:
    # TODO: Проверить ачивки пользователя по его данным, вернуть список новых достижений
    return []

def add_xp(user_data, amount: int) -> None:
    user_data["xp"] = user_data.get("xp", 0) + amount
