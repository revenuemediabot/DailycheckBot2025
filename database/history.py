# database/history.py

from pathlib import Path
import json
from typing import List, Dict, Any

HISTORY_DIR = Path("data/history")  # Лучше вынести в config.py

def _history_file(user_id: int) -> Path:
    return HISTORY_DIR / f"user_{user_id}_history.json"

def append_history(user_id: int, entry: Dict[str, Any]) -> None:
    HISTORY_DIR.mkdir(exist_ok=True, parents=True)
    path = _history_file(user_id)
    history = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def get_history(user_id: int) -> List[Dict[str, Any]]:
    path = _history_file(user_id)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
