from datetime import date

def welcome_message(user):
    return (
        f"Привет, {user.first_name or 'друг'}! 👋\n"
        "Я помогу тебе отслеживать задачи, привычки, настроение и успехи.\n"
        "Используй /help для справки."
    )

def tasks_list_message(tasks):
    if not tasks:
        return "У вас пока нет задач. Добавьте первую!"
    lines = []
    for idx, task in enumerate(tasks, 1):
        status = "✅" if task['completed'] else "⬜️"
        lines.append(f"{idx}. {status} {task['title']}")
    return "<b>Ваши задачи:</b>\n" + "\n".join(lines)

def habits_list_message(habits):
    if not habits:
        return "Вы не добавили привычки. Начните прямо сейчас!"
    return "<b>Ваши привычки:</b>\n" + "\n".join(
        [f"{idx+1}. {habit['title']} ({habit['streak']}🔥)" for idx, habit in enumerate(habits)]
    )

def mood_message(mood, note=None):
    msg = f"Текущее настроение: <b>{mood}</b>"
    if note:
        msg += f"\nКомментарий: {note}"
    return msg

def progress_message(progress: int, total: int):
    percent = int((progress / total) * 100) if total else 0
    return f"Прогресс: {progress} из {total} задач выполнено ({percent}%)"

def motivation_message(text):
    return f"🚀 <b>Мотивация дня:</b>\n{text}"

def streak_message(streak):
    return f"🔥 Ваш стрик: <b>{streak}</b> дней подряд!"

def analytics_message(data):
    # data — словарь с аналитикой
    return (
        f"📊 <b>Статистика:</b>\n"
        f"Выполнено задач: {data.get('tasks_done', 0)}\n"
        f"Привычки: {data.get('habits_done', 0)}\n"
        f"Стрик: {data.get('streak', 0)} дней\n"
        f"XP: {data.get('xp', 0)}"
    )
