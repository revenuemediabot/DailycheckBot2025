from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Главное меню
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Задачи", callback_data="tasks_list"),
         InlineKeyboardButton("💡 Привычки", callback_data="habits_list")],
        [InlineKeyboardButton("🙂 Настроение", callback_data="mood_select"),
         InlineKeyboardButton("🏆 Достижения", callback_data="achievements_list")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats_menu"),
         InlineKeyboardButton("⚙️ Настройки", callback_data="settings_menu")],
        [InlineKeyboardButton("⚡ Быстрые действия", callback_data="quick_action:menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Клавиатура задач (пример)
def tasks_keyboard(tasks):
    keyboard = []
    for task in tasks:
        row = [
            InlineKeyboardButton(f"{'✅' if task['completed'] else '⬜️'} {task['title']}", callback_data=f"task_complete:{task['id']}"),
            InlineKeyboardButton("✏️", callback_data=f"task_edit:{task['id']}"),
            InlineKeyboardButton("🗑", callback_data=f"task_delete:{task['id']}")
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("➕ Добавить задачу", callback_data="addtask")])
    return InlineKeyboardMarkup(keyboard)

# Клавиатура привычек
def habits_keyboard(habits):
    keyboard = []
    for habit in habits:
        row = [
            InlineKeyboardButton(f"{habit['title']} ({habit['streak']}🔥)", callback_data=f"habit_complete:{habit['id']}"),
            InlineKeyboardButton("📆", callback_data=f"habit_streak:{habit['id']}")
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("➕ Добавить привычку", callback_data="addhabit")])
    return InlineKeyboardMarkup(keyboard)

# Клавиатура настроения (эмоции)
def mood_keyboard():
    moods = [
        ("😞", "bad"), ("😐", "normal"), ("🙂", "good"),
        ("😃", "great"), ("🤩", "awesome")
    ]
    keyboard = [[InlineKeyboardButton(emoji, callback_data=f"mood_set:{code}")]
                for emoji, code in moods]
    return InlineKeyboardMarkup(keyboard)

# Настройки профиля
def settings_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎨 Тема", callback_data="settings_theme")],
        [InlineKeyboardButton("⏰ Напоминания", callback_data="settings_reminders")],
        [InlineKeyboardButton("🤖 AI", callback_data="settings_ai")],
        [InlineKeyboardButton("📤 Экспорт", callback_data="export")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Быстрые действия
def quick_actions_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Выполнить задачу", callback_data="quick_action:done_task")],
        [InlineKeyboardButton("💡 Добавить привычку", callback_data="quick_action:add_habit")],
        [InlineKeyboardButton("🔥 Мотивация", callback_data="quick_motivation")],
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)
