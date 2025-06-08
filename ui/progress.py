# ui/progress.py

def progress_bar(percent: int, length: int = 12):
    """Генерирует текстовый progress bar (emoji/блоки)"""
    done = int(length * percent // 100)
    todo = length - done
    return "🟩" * done + "⬜️" * todo + f" {percent}%"

def xp_bar(xp: int, xp_next: int):
    percent = min(int(xp / xp_next * 100), 100)
    return f"Опыт: {xp}/{xp_next}\n" + progress_bar(percent)

def tasks_progress_bar(done: int, total: int):
    percent = int((done / total) * 100) if total else 0
    return progress_bar(percent)

def streak_emoji(streak: int):
    if streak >= 30:
        return "🏆"
    elif streak >= 7:
        return "🔥"
    elif streak >= 3:
        return "✨"
    else:
        return "🔹"
