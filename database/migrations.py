# database/migrations.py

import os
import json
from pathlib import Path

DATA_DIR = Path("data")  # Вынести в config.py

def migrate_all_users(migration_fn):
    """
    Применяет функцию migration_fn(data: dict) для всех пользователей.
    """
    for file in DATA_DIR.glob("user_*.json"):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = migration_fn(data)
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# Пример миграции: добавление поля 'xp' если его нет
def add_xp_field(data):
    if 'xp' not in data:
        data['xp'] = 0
    return data

# Запуск миграции (вызывать отдельно при необходимости)
# migrate_all_users(add_xp_field)
