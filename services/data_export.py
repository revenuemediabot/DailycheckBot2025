# services/data_export.py

import json
import csv
from pathlib import Path

def export_to_json(user_id: int, data: dict, export_dir: Path):
    filename = export_dir / f"user_{user_id}_export.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filename

def export_to_csv(user_id: int, data: list, export_dir: Path):
    filename = export_dir / f"user_{user_id}_export.csv"
    if not data:
        return None
    keys = data[0].keys()
    with open(filename, "w", newline="", encoding="utf-8") as f:
        dict_writer = csv.DictWriter(f, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data)
    return filename
