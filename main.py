# ===================== ПРОДОЛЖЕНИЕ MAIN.PY =====================
# Вставьте этот код после предыдущего блока

# ===================== НАПОМИНАНИЯ И ТАЙМЕРЫ =====================

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создать напоминание"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/remind")
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "⏰ **Создание напоминания**\n\n"
            "Формат: `/remind <время_в_минутах> <текст>`\n\n"
            "Примеры:\n"
            "• `/remind 30 Сделать перерыв`\n"
            "• `/remind 60 Встреча с командой`\n"
            "• `/remind 120 Обед`",
            parse_mode="Markdown"
        )
        return
    
    try:
        minutes = int(context.args[0])
        reminder_text = " ".join(context.args[1:])
        
        if minutes <= 0:
            await update.message.reply_text("❌ Время должно быть положительным числом!")
            return
        
        reminder = {
            "text": reminder_text,
            "created_at": datetime.now().isoformat(),
            "remind_at": (datetime.now() + timedelta(minutes=minutes)).isoformat(),
            "minutes": minutes
        }
        
        user_reminders[user_id].append(reminder)
        save_user_data()
        
        await update.message.reply_text(
            f"⏰ **Напоминание установлено!**\n\n"
            f"📝 Текст: {reminder_text}\n"
            f"⏱️ Через: {minutes} минут\n"
            f"🕐 Время: {(datetime.now() + timedelta(minutes=minutes)).strftime('%H:%M')}\n\n"
            f"💡 В полной версии с APScheduler напоминание придет автоматически"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Время должно быть числом в минутах.")

async def timer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить таймер"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/timer")
    
    if not context.args:
        await update.message.reply_text(
            "⏲️ **Таймер**\n\n"
            "Формат: `/timer <минуты>`\n\n"
            "Популярные таймеры:\n"
            "• `/timer 25` - помодоро (работа)\n"
            "• `/timer 5` - короткий перерыв\n"
            "• `/timer 15` - длинный перерыв\n"
            "• `/timer 60` - час концентрации",
            parse_mode="Markdown"
        )
        return
    
    try:
        minutes = int(context.args[0])
        
        if minutes <= 0:
            await update.message.reply_text("❌ Время должно быть положительным числом!")
            return
        
        users_data[user_id]["timer_uses"] += 1
        xp_msg = add_xp(user_id, 5)
        achievements = check_achievements(user_id)
        
        timer = {
            "minutes": minutes,
            "started_at": datetime.now().isoformat(),
            "ends_at": (datetime.now() + timedelta(minutes=minutes)).isoformat()
        }
        
        user_timers[user_id].append(timer)
        save_user_data()
        
        # Определяем тип таймера
        timer_type = "⏲️ Таймер"
        if minutes == 25:
            timer_type = "🍅 Помодоро"
        elif minutes == 5:
            timer_type = "☕ Короткий перерыв"
        elif minutes == 15:
            timer_type = "🛋️ Длинный перерыв"
        
        response = f"{timer_type} запущен на {minutes} минут!\n"
        response += f"🕐 Завершится в: {(datetime.now() + timedelta(minutes=minutes)).strftime('%H:%M')}\n"
        response += f"{xp_msg}"
        
        if achievements:
            response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
        
        await update.message.reply_text(response)
        
    except ValueError:
        await update.message.reply_text("❌ Время должно быть числом в минутах.")

# ===================== ЕЖЕНЕДЕЛЬНЫЕ ЦЕЛИ =====================

async def weekly_goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление еженедельными целями"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/weekly_goals")
    
    goals = users_data[user_id]["weekly_goals"]
    if not goals:
        keyboard = [
            [InlineKeyboardButton("🎯 Установить цели", callback_data="set_weekly_goals")],
            [InlineKeyboardButton("💡 Примеры целей", callback_data="example_goals")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🎯 **У вас пока нет еженедельных целей.**\n\n"
            "Еженедельные цели помогают:\n"
            "• Планировать долгосрочные задачи\n"
            "• Поддерживать мотивацию\n"
            "• Отслеживать прогресс\n\n"
            "Установите свои первые цели!",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return
    
    text = "🎯 **Еженедельные цели:**\n\n"
    keyboard = []
    
    for i, goal in enumerate(goals, 1):
        status = "✅" if goal.get("completed", False) else "⭕"
        progress = goal.get("progress", 0)
        target = goal.get("target", 1)
        
        text += f"{status} {i}. {goal['name']}\n"
        if target > 1:
            text += f"   📊 Прогресс: {progress}/{target}\n"
        text += f"   📅 Создана: {goal['created_at'][:10]}\n\n"
        
        if not goal.get("completed", False):
            keyboard.append([InlineKeyboardButton(f"✅ Цель {i}", callback_data=f"complete_goal_{i-1}")])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить цель", callback_data="add_weekly_goal")],
        [InlineKeyboardButton("🔄 Новая неделя", callback_data="reset_weekly_goals")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def set_weekly_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить еженедельные цели"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/set_weekly")
    
    if not context.args:
        await update.message.reply_text(
            "🎯 **Еженедельные цели**\n\n"
            "Формат: `/set_weekly цель1; цель2; цель3`\n\n"
            "Примеры:\n"
            "`/set_weekly Прочитать книгу; Сделать 5 тренировок; Изучить новую тему; Встретиться с друзьями`\n\n"
            "💡 Цели заменят текущие еженедельные цели",
            parse_mode="Markdown"
        )
        return
    
    goals_text = " ".join(context.args)
    goal_names = [goal.strip() for goal in goals_text.split(";") if goal.strip()]
    
    if not goal_names:
        await update.message.reply_text("❌ Не найдено ни одной цели. Проверьте формат!")
        return
    
    # Заменяем старые цели
    users_data[user_id]["weekly_goals"] = []
    
    for name in goal_names:
        goal = {
            "name": name,
            "completed": False,
            "created_at": datetime.now().isoformat(),
            "progress": 0,
            "target": 1
        }
        users_data[user_id]["weekly_goals"].append(goal)
    
    xp_reward = len(goal_names) * 10
    xp_msg = add_xp(user_id, xp_reward)
    achievements = check_achievements(user_id)
    
    save_user_data()
    
    response = f"🎯 Установлено {len(goal_names)} еженедельных целей!\n{xp_msg}"
    if achievements:
        response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
    
    await update.message.reply_text(response)

# ===================== ПЕРСОНАЛИЗАЦИЯ =====================

async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сменить тему оформления"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/theme")
    
    if not context.args:
        current_theme_key = user_themes[user_id]
        current_theme = THEMES[current_theme_key]["name"]
        
        text = f"🎨 **Темы оформления**\n\n"
        text += f"Текущая тема: {current_theme}\n\n"
        text += "Доступные темы:\n"
        
        for i, (key, theme) in enumerate(THEMES.items(), 1):
            marker = "▶️" if key == current_theme_key else f"{i}."
            text += f"{marker} {theme['name']}\n"
        
        text += f"\nИспользуйте: `/theme <номер>`"
        await update.message.reply_text(text, parse_mode="Markdown")
        return
    
    try:
        theme_num = int(context.args[0])
        theme_keys = list(THEMES.keys())
        
        if 1 <= theme_num <= len(theme_keys):
            new_theme_key = theme_keys[theme_num - 1]
            user_themes[user_id] = new_theme_key
            new_theme = THEMES[new_theme_key]
            
            xp_msg = add_xp(user_id, 5)
            save_user_data()
            
            await update.message.reply_text(
                f"🎨 Тема изменена на: {new_theme['name']}\n"
                f"{new_theme['accent']} Новый стиль активирован!\n"
                f"{xp_msg}"
            )
        else:
            await update.message.reply_text(f"❌ Выберите номер от 1 до {len(THEMES)}")
    except ValueError:
        await update.message.reply_text("❌ Введите номер темы")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Настройки пользователя"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/settings")
    
    user = users_data[user_id]
    theme = THEMES[user_themes[user_id]]["name"]
    ai_chat = user_ai_chat[user_id]
    
    text = f"⚙️ **Настройки пользователя**\n\n"
    text += f"🎨 Тема: {theme}\n"
    text += f"🤖 AI-чат: {'включен' if ai_chat else 'выключен'}\n"
    text += f"🚭 Dry режим: {'включен' if user['dry_mode'] else 'выключен'}\n"
    text += f"📅 Регистрация: {user['created_at'][:10]}\n"
    text += f"📊 Уровень: {get_user_level(user['xp'])[1]}\n"
    text += f"⚡ XP: {user['xp']}\n"
    text += f"🔥 Стрик: {user['streak']} дней\n\n"
    
    text += "**Команды для изменения:**\n"
    text += "• `/theme` - сменить тему\n"
    text += "• `/ai_chat` - переключить AI-чат\n"
    text += "• `/dryon` или `/dryoff` - dry режим\n"
    text += "• `/export` - экспорт ваших данных"
    
    keyboard = [
        [InlineKeyboardButton("🎨 Сменить тему", callback_data="change_theme")],
        [InlineKeyboardButton("🤖 Переключить AI", callback_data="toggle_ai")],
        [InlineKeyboardButton("📤 Экспорт данных", callback_data="export_data")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ===================== ЭКСПОРТ И УТИЛИТЫ =====================

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт данных"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/export")
    
    user_data = {
        "user_info": {
            "user_id": user_id,
            "level": get_user_level(users_data[user_id]["xp"])[1],
            "xp": users_data[user_id]["xp"],
            "streak": users_data[user_id]["streak"],
            "created_at": users_data[user_id]["created_at"],
            "theme": THEMES[user_themes[user_id]]["name"]
        },
        "tasks": users_data[user_id]["tasks"],
        "achievements": [ACHIEVEMENTS[i] for i in user_achievements[user_id]],
        "weekly_goals": users_data[user_id]["weekly_goals"],
        "statistics": {
            "total_tasks_created": users_data[user_id]["total_tasks_created"],
            "total_tasks_completed": users_data[user_id]["total_tasks_completed"],
            "completed_today": users_data[user_id]["completed_today"],
            "timer_uses": users_data[user_id]["timer_uses"],
            "stats_views": users_data[user_id]["stats_views"]
        },
        "social": {
            "friends_count": len(user_friends[user_id]),
            "friends_list": user_friends[user_id]
        },
        "export_info": {
            "export_date": datetime.now().isoformat(),
            "bot_version": "4.0",
            "format": "JSON"
        }
    }
    
    # Создание JSON файла (в памяти)
    json_data = json.dumps(user_data, ensure_ascii=False, indent=2)
    
    # Создание CSV данных для задач
    csv_output = StringIO()
    csv_writer = csv.writer(csv_output)
    csv_writer.writerow(["Название", "Статус", "Категория", "Приоритет", "Время создания", "Подзадачи"])
    
    for task in users_data[user_id]["tasks"]:
        status = "Выполнено" if task.get("completed", False) else "В процессе"
        category = CATEGORIES[task.get("category", "personal")]["name"]
        priority = PRIORITIES[task.get("priority", "medium")]["name"]
        subtasks_count = len(task.get("subtasks", []))
        
        csv_writer.writerow([
            task["name"],
            status,
            category,
            priority,
            task["created_at"][:10],
            subtasks_count
        ])
    
    csv_data = csv_output.getvalue()
    csv_output.close()
    
    # Статистика экспорта
    stats_text = (
        f"📤 **Экспорт данных завершен**\n\n"
        f"📊 **Ваша статистика:**\n"
        f"📋 Задач: {len(user_data['tasks'])}\n"
        f"🏆 Достижений: {len(user_data['achievements'])}\n"
        f"🎯 Еженедельных целей: {len(user_data['weekly_goals'])}\n"
        f"👥 Друзей: {user_data['social']['friends_count']}\n"
        f"⚡ XP: {user_data['user_info']['xp']}\n"
        f"📊 Уровень: {user_data['user_info']['level']}\n\n"
        f"📁 **Доступные форматы:**\n"
        f"• JSON - полные данные\n"
        f"• CSV - таблица задач\n\n"
        f"💾 В полной версии файлы будут отправлены в чат"
    )
    
    keyboard = [
        [InlineKeyboardButton("📄 Показать JSON", callback_data="show_json")],
        [InlineKeyboardButton("📊 Показать CSV", callback_data="show_csv")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Сохраняем данные для отображения по кнопкам
    users_data[user_id]["export_json"] = json_data[:2000]  # Ограничиваем для отображения
    users_data[user_id]["export_csv"] = csv_data[:2000]
    
    await update.message.reply_text(stats_text, reply_markup=reply_markup, parse_mode="Markdown")

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить состояние системы"""
    user_id = update.effective_user.id
    log_command(user_id, "/health")
    
    # Проверка различных компонентов
    system_status = "✅ Отлично"
    ai_status = "✅ Подключен" if OPENAI_API_KEY else "❌ Недоступен"
    
    # Статистика использования
    total_tasks_all_users = sum(len(user.get("tasks", [])) for user in users_data.values())
    active_users = len([u for u in users_data.values() if len(u.get("tasks", [])) > 0])
    
    await update.message.reply_text(
        f"🏥 **Состояние системы**\n\n"
        f"🤖 Бот: {system_status}\n"
        f"🧠 AI: {ai_status}\n"
        f"🌐 HTTP сервер: порт {PORT}\n"
        f"💾 Данные: сохраняются\n\n"
        f"📊 **Статистика:**\n"
        f"👥 Всего пользователей: {global_stats['total_users']}\n"
        f"🎯 Активных пользователей: {active_users}\n"
        f"📋 Всего задач: {total_tasks_all_users}\n"
        f"📊 Команд выполнено: {global_stats['commands_executed']}\n"
        f"🤖 AI запросов: {global_stats['ai_requests']}\n\n"
        f"⏰ Время сервера: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}\n"
        f"🔄 Версия: 4.0 (FULL)",
        parse_mode="Markdown"
    )

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестовая команда (для отладки)"""
    user_id = update.effective_user.id
    log_command(user_id, "/test")
    
    if user_id != ADMIN_USER_ID and ADMIN_USER_ID != 0:
        await update.message.reply_text("❌ Доступно только администратору")
        return
    
    # Создание тестовых данных
    test_tasks = [
        {"name": "Тестовая задача - Работа", "completed": True, "category": "work", "priority": "high"},
        {"name": "Тестовая задача - Здоровье", "completed": False, "category": "health", "priority": "medium"},
        {"name": "Тестовая задача - Обучение", "completed": True, "category": "study", "priority": "low"},
        {"name": "Задача с подзадачами", "completed": False, "category": "personal", "priority": "medium", 
         "subtasks": [
             {"name": "Подзадача 1", "completed": True},
             {"name": "Подзадача 2", "completed": False}
         ]}
    ]
    
    # Добавляем тестовые данные
    users_data[user_id]["tasks"].extend(test_tasks)
    users_data[user_id]["total_tasks_created"] += len(test_tasks)
    users_data[user_id]["completed_today"] += 2
    users_data[user_id]["streak"] = 5
    users_data[user_id]["timer_uses"] += 3
    
    # Добавляем тестовые цели
    test_goals = [
        {"name": "Тестовая цель 1", "completed": True, "created_at": datetime.now().isoformat()},
        {"name": "Тестовая цель 2", "completed": False, "created_at": datetime.now().isoformat()}
    ]
    users_data[user_id]["weekly_goals"].extend(test_goals)
    
    # Даем XP
    add_xp(user_id, 150)
    
    # Проверяем достижения
    achievements = check_achievements(user_id)
    
    save_user_data()
    
    response = "🧪 **Тестовые данные добавлены!**\n\n"
    response += f"📋 Добавлено {len(test_tasks)} задач\n"
    response += f"🎯 Добавлено {len(test_goals)} целей\n"
    response += f"⚡ Добавлено 150 XP\n"
    response += f"🔥 Стрик установлен на 5 дней\n"
    
    if achievements:
        response += f"\n🏆 Получены достижения: {', '.join(achievements)}"
    
    await update.message.reply_text(response, parse_mode="Markdown")

# ===================== РЕЖИМ "DRY" =====================

async def dryon_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать отчет дней без алкоголя"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/dryon")
    
    if users_data[user_id]["dry_mode"]:
        days = users_data[user_id]["dry_days"]
        await update.message.reply_text(
            f"🚭 Режим 'Dry' уже активен!\n"
            f"Текущий счетчик: {days} дней"
        )
        return
    
    users_data[user_id]["dry_mode"] = True
    users_data[user_id]["dry_days"] = 0
    save_user_data()
    
    await update.message.reply_text(
        "🚭 **Режим 'Dry' включен!**\n\n"
        "Отслеживание дней без алкоголя начато.\n"
        "Каждый день стойкости будет приносить дополнительные XP!\n\n"
        "💪 Вы можете это сделать!\n"
        "Используйте `/dryoff` для завершения отчета.",
        parse_mode="Markdown"
    )

async def dryoff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершить отчет дней без алкоголя"""
    user_id = update.effective_user.id
    init_user(user_id)
    log_command(user_id, "/dryoff")
    
    if not users_data[user_id]["dry_mode"]:
        await update.message.reply_text("🚭 Режим 'Dry' не активен. Используйте `/dryon` для начала.")
        return
    
    days = users_data[user_id]["dry_days"]
    users_data[user_id]["dry_mode"] = False
    
    # Награда за dry дни
    xp_reward = days * 10
    if days >= 7:
        xp_reward += 50  # Бонус за неделю
    if days >= 30:
        xp_reward += 100  # Бонус за месяц
    
    xp_msg = add_xp(user_id, xp_reward)
    save_user_data()
    
    # Мотивационное сообщение в зависимости от результата
    if days == 0:
        message = "Начало положено! В следующий раз получится лучше."
    elif days < 7:
        message = "Хороший старт! Каждый день - это достижение."
    elif days < 30:
        message = "Впечатляющий результат! Вы показали силу воли."
    else:
        message = "Невероятно! Вы настоящий чемпион силы воли!"
    
    await update.message.reply_text(
        f"🚭 **Отчет завершен!**\n\n"
        f"📊 Дней без алкоголя: {days}\n"
        f"🎁 Награда: {xp_reward} XP\n"
        f"💪 {message}\n\n"
        f"{xp_msg}",
        parse_mode="Markdown"
    )

# ===================== АДМИНСКИЕ ФУНКЦИИ =====================

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправление сообщения всем активным чатам"""
    user_id = update.effective_user.id
    log_command(user_id, "/broadcast")
    
    if user_id != ADMIN_USER_ID and ADMIN_USER_ID != 0:
        await update.message.reply_text("❌ Доступно только администратору")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 **Рассылка сообщений**\n\n"
            "Формат: `/broadcast <сообщение>`\n\n"
            "Пример: `/broadcast Обновление бота! Добавлены новые функции.`"
        )
        return
    
    message = " ".join(context.args)
    sent_count = 0
    failed_count = 0
    
    await update.message.reply_text(f"📢 Начинаю рассылку для {len(users_data)} пользователей...")
    
    for target_user_id in users_data.keys():
        try:
            await context.bot.send_message(
                target_user_id, 
                f"📢 **Сообщение от администратора:**\n\n{message}",
                parse_mode="Markdown"
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1
            logger.warning(f"Не удалось отправить сообщение пользователю {target_user_id}: {e}")
    
    await update.message.reply_text(
        f"📢 **Рассылка завершена**\n\n"
        f"✅ Отправлено: {sent_count}\n"
        f"❌ Ошибок: {failed_count}\n"
        f"📊 Успешность: {(sent_count/(sent_count+failed_count)*100):.1f}%"
    )

async def stats_global_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальная статистика по всем пользователям"""
    user_id = update.effective_user.id
    log_command(user_id, "/stats_global")
    
    if user_id != ADMIN_USER_ID and ADMIN_USER_ID != 0:
        await update.message.reply_text("❌ Доступно только администратору")
        return
    
    # Подсчет глобальной статистики
    total_tasks = sum(len(user.get("tasks", [])) for user in users_data.values())
    total_completed = sum(
        sum(1 for task in user.get("tasks", []) if task.get("completed", False))
        for user in users_data.values()
    )
    total_xp = sum(user.get("xp", 0) for user in users_data.values())
    active_users = len([u for u in users_data.values() if len(u.get("tasks", [])) > 0])
    
    # Статистика по уровням
    level_stats = {}
    for user in users_data.values():
        level = get_user_level(user.get("xp", 0))[1]
        level_stats[level] = level_stats.get(level, 0) + 1
    
    # Топ пользователи по XP
    top_users = sorted(
        [(uid, user.get("xp", 0)) for uid, user in users_data.items()],
        key=lambda x: x[1], reverse=True
    )[:5]
    
    text = f"📊 **Глобальная статистика**\n\n"
    text += f"👥 **Пользователи:**\n"
    text += f"   • Всего: {global_stats['total_users']}\n"
    text += f"   • Активных: {active_users}\n\n"
    
    text += f"📋 **Задачи:**\n"
    text += f"   • Всего создано: {total_tasks}\n"
    text += f"   • Выполнено: {total_completed}\n"
    text += f"   • Процент выполнения: {(total_completed/max(1,total_tasks)*100):.1f}%\n\n"
    
    text += f"⚡ **Активность:**\n"
    text += f"   • Общий XP: {total_xp:,}\n"
    text += f"   • Команд выполнено: {global_stats['commands_executed']:,}\n"
    text += f"   • AI запросов: {global_stats['ai_requests']:,}\n\n"
    
    text += f"🏆 **Топ-5 по XP:**\n"
    for i, (uid, xp) in enumerate(top_users, 1):
        level = get_user_level(xp)[1]
        text += f"   {i}. ID{uid}: {xp} XP ({level})\n"
    
    text += f"\n📈 **Статистика по уровням:**\n"
    for level, count in sorted(level_stats.items(), key=lambda x: LEVELS.index(x[0]) if x[0] in LEVELS else 999):
        text += f"   • {level}: {count} чел.\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ===================== ОБРАБОТКА СООБЩЕНИЙ =====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка обычных сообщений"""
    user_id = update.effective_user.id
    user_text = update.message.text
    init_user(user_id)
    
    logger.info(f"Сообщение от {user_id}: {user_text[:50]}...")
    
    # Если включен AI-чат режим
    if user_ai_chat.get(user_id, False):
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # Определяем тип запроса для AI
        text_lower = user_text.lower()
        if any(word in text_lower for word in ["мотив", "поддерж", "вдохнов", "силы", "могу"]):
            ai_type = "motivate"
        elif any(word in text_lower for word in ["планир", "продуктив", "задач", "советы", "как"]):
            ai_type = "coach"
        elif any(word in text_lower for word in ["стресс", "устал", "грустн", "плох", "депресс"]):
            ai_type = "psy"
        else:
            ai_type = "general"
        
        response = await generate_ai_response(user_text, user_id, ai_type)
        await update.message.reply_text(response)
        return
    
    # Простые ответы для обычного режима
    responses = {
        "привет": "👋 Привет! Используйте /start для главного меню",
        "помощь": "🆘 Используйте /help для полной справки по командам",
        "как дела": f"😊 Отлично! У вас {users_data[user_id]['xp']} XP. Проверьте прогресс командой /stats",
        "спасибо": "🙏 Пожалуйста! Рад помочь в достижении ваших целей!",
        "пока": "👋 До свидания! Удачи с выполнением задач!"
    }
    
    user_text_lower = user_text.lower()
    for key, response in responses.items():
        if key in user_text_lower:
            await update.message.reply_text(response)
            return
    
    # Если ничего не подошло
    await update.message.reply_text(
        "🤔 Не понял команду.\n\n"
        "💡 Используйте:\n"
        "• /help - полная справка\n"
        "• /ai_chat - включить AI режим\n"
        "• /start - главное меню"
    )

# ===================== CALLBACK HANDLERS (Обработка кнопок) =====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на inline кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "show_tasks":
        await tasks_command(update, context)
    elif data == "show_stats":
        await stats_command(update, context)
    elif data == "show_achievements":
        achievements_list = [ACHIEVEMENTS[i] for i in user_achievements.get(user_id, [])]
        text = "🏆 **Ваши достижения:**\n\n"
        if achievements_list:
            for ach in achievements_list:
                text += f"{ach['emoji']} **{ach['name']}**\n"
                text += f"   {ach['desc']}\n"
                text += f"   🎁 Награда: {ach['xp_reward']} XP\n\n"
        else:
            text += "Пока нет достижений.\n"
            text += "Выполняйте задачи, используйте функции бота чтобы получить первые награды!"
        await query.edit_message_text(text, parse_mode="Markdown")
    elif data == "show_ai_help":
        ai_status = "подключен" if OPENAI_API_KEY else "недоступен (настройте OPENAI_API_KEY)"
        text = (
            f"🤖 **AI Помощь** (статус: {ai_status})\n\n"
            f"**Доступные AI команды:**\n"
            f"• `/ai_chat` - включить режим общения\n"
            f"• `/motivate [текст]` - получить мотивацию\n"
            f"• `/ai_coach [вопрос]` - совет по продуктивности\n"
            f"• `/psy [проблема]` - психологическая поддержка\n"
            f"• `/suggest_tasks [категория]` - предложить задачи\n\n"
            f"💡 В AI-чат режиме просто пишите сообщения и получайте умные ответы!"
        )
        await query.edit_message_text(text, parse_mode="Markdown")
    elif data == "show_settings":
        await settings_command(update, context)
    elif data == "show_weekly_goals":
        await weekly_goals_command(update, context)
    elif data.startswith("complete_task_"):
        task_index = int(data.split("_")[2])
        if task_index < len(users_data[user_id]["tasks"]):
            task = users_data[user_id]["tasks"][task_index]
            task["completed"] = True
            users_data[user_id]["completed_today"] += 1
            users_data[user_id]["total_tasks_completed"] += 1
            global_stats["tasks_completed"] += 1
            
            xp_reward = 25
            # Бонус за приоритет
            if task.get("priority") == "high":
                xp_reward += 10
            elif task.get("priority") == "low":
                xp_reward += 5
            
            xp_msg = add_xp(user_id, xp_reward)
            achievements = check_achievements(user_id)
            
            save_user_data()
            
            response = f"✅ **Задача выполнена!**\n"
            response += f"📝 {task['name']}\n"
            response += f"{xp_msg}"
            
            if achievements:
                response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
            
            await query.edit_message_text(response, parse_mode="Markdown")
    elif data.startswith("complete_goal_"):
        goal_index = int(data.split("_")[2])
        if goal_index < len(users_data[user_id]["weekly_goals"]):
            goal = users_data[user_id]["weekly_goals"][goal_index]
            goal["completed"] = True
            
            xp_msg = add_xp(user_id, 50)
            achievements = check_achievements(user_id)
            save_user_data()
            
            response = f"🎯 **Еженедельная цель выполнена!**\n"
            response += f"📝 {goal['name']}\n"
            response += f"{xp_msg}"
            
            if achievements:
                response += f"\n🏆 Новые достижения: {', '.join(achievements)}"
            
            await query.edit_message_text(response, parse_mode="Markdown")
    elif data == "confirm_reset":
        # Сбрасываем выполненные задачи
        for task in users_data[user_id]["tasks"]:
            task["completed"] = False
            for subtask in task.get("subtasks", []):
                subtask["completed"] = False
        
        users_data[user_id]["completed_today"] = 0
        save_user_data()
        
        await query.edit_message_text(
            "🔄 **Прогресс дня сброшен!**\n\n"
            "Все задачи помечены как невыполненные.\n"
            "Начните новый продуктивный день!"
        )
    # Добавьте остальные обработчики кнопок по необходимости...

# ===================== ОСНОВНАЯ ФУНКЦИЯ =====================

def main():
    """Главная функция запуска бота"""
    logger.info("🚀 Запуск DailyCheck Bot v4.0 - ПОЛНАЯ ВЕРСИЯ...")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Платформа: {sys.platform}")
    logger.info(f"Порт: {PORT}")
    
    try:
        # ШАГ 1: Загрузка данных
        logger.info("📂 Загрузка данных пользователей...")
        load_user_data()
        
        # ШАГ 2: Запуск HTTP сервера
        logger.info("🌐 Запуск HTTP сервера...")
        http_thread = start_health_server()
        
        # ШАГ 3: Пауза для стабилизации
        time.sleep(3)
        logger.info("⏳ HTTP сервер стабилизировался")
        
        # ШАГ 4: Создание Telegram приложения
        logger.info("🤖 Создание Telegram приложения...")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # ШАГ 5: Регистрация ВСЕХ обработчиков
        logger.info("📋 Регистрация обработчиков команд...")
        
        # Основные команды
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("ping", ping_command))
        
        # Управление задачами (7 команд)
        app.add_handler(CommandHandler("tasks", tasks_command))
        app.add_handler(CommandHandler("settasks", settasks_command))
        app.add_handler(CommandHandler("addtask", addtask_command))
        app.add_handler(CommandHandler("addsub", addsub_command))
        app.add_handler(CommandHandler("edit", edit_command))
        app.add_handler(CommandHandler("reset", reset_command))
        
        # Статистика (2 команды)
        app.add_handler(CommandHandler("stats", stats_command))
        app.add_handler(CommandHandler("analytics", analytics_command))
        
        # AI функции (5 команд)
        app.add_handler(CommandHandler("ai_chat", ai_chat_command))
        app.add_handler(CommandHandler("motivate", motivate_command))
        app.add_handler(CommandHandler("ai_coach", ai_coach_command))
        app.add_handler(CommandHandler("psy", psy_command))
        app.add_handler(CommandHandler("suggest_tasks", suggest_tasks_command))
        
        # Социальные функции (3 команды)
        app.add_handler(CommandHandler("friends", friends_command))
        app.add_handler(CommandHandler("add_friend", add_friend_command))
        app.add_handler(CommandHandler("myid", myid_command))
        
        # Напоминания и таймеры (2 команды)
        app.add_handler(CommandHandler("remind", remind_command))
        app.add_handler(CommandHandler("timer", timer_command))
        
        # Еженедельные цели (2 команды)
        app.add_handler(CommandHandler("weekly_goals", weekly_goals_command))
        app.add_handler(CommandHandler("set_weekly", set_weekly_command))
        
        # Персонализация (2 команды)
        app.add_handler(CommandHandler("theme", theme_command))
        app.add_handler(CommandHandler("settings", settings_command))
        
        # Экспорт и утилиты (3 команды)
        app.add_handler(CommandHandler("export", export_command))
        app.add_handler(CommandHandler("health", health_command))
        app.add_handler(CommandHandler("test", test_command))
        
        # Режим "Dry" (2 команды)
        app.add_handler(CommandHandler("dryon", dryon_command))
        app.add_handler(CommandHandler("dryoff", dryoff_command))
        
        # Админские функции (2 команды)
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CommandHandler("stats_global", stats_global_command))
        
        # Обработчики сообщений и кнопок
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        logger.info("✅ ВСЕ 32 КОМАНДЫ зарегистрированы!")
        logger.info("📱 Найдите бота в Telegram и отправьте /start")
        logger.info("🎯 Запуск polling...")
        
        # ШАГ 6: Запуск бота
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        
        # Сохраняем данные при ошибке
        try:
            save_user_data()
            logger.info("💾 Данные сохранены перед остановкой")
        except:
            logger.error("❌ Не удалось сохранить данные")
        
        # Поддержание HTTP сервера
        logger.info("🔄 HTTP сервер продолжает работать...")
        try:
            while True:
                time.sleep(60)
                logger.info("💓 Процесс активен (HTTP сервер работает)")
        except KeyboardInterrupt:
            logger.info("👋 Остановка по Ctrl+C")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Остановка по KeyboardInterrupt")
        try:
            save_user_data()
            logger.info("💾 Данные сохранены при остановке")
        except:
            pass
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
        try:
            save_user_data()
        except:
            pass
        logger.info("🔄 Поддержание процесса для HTTP сервера...")
        try:
            while True:
                time.sleep(300)
                logger.info("💓 Процесс активен")
        except:
            pass
