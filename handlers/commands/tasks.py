# handlers/commands/tasks.py

async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...логика показа задач
    await update.message.reply_text("Здесь будет список задач 📋")

def register_task_handlers(application: Application):
    application.add_handler(CommandHandler("tasks", tasks_command))
    # ...другие команды по задачам
