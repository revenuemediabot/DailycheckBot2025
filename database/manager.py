# database/manager.py

import json
from pathlib import Path
from typing import Optional, Dict, Any

DATA_DIR = Path("data")  # Лучше вынести в config.py

def _user_file(user_id: int) -> Path:
    return DATA_DIR / f"user_{user_id}.json"

def load_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    path = _user_file(user_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_user_data(user_id: int, data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with open(_user_file(user_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_user_data(user_id: int, update: Dict[str, Any]) -> None:
    data = load_user_data(user_id) or {}
    data.update(update)
    save_user_data(user_id, data)

def delete_user_data(user_id: int) -> None:
    file = _user_file(user_id)
    if file.exists():
        file.unlink()
