# handlers/commands/social.py

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

async def friends_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ваши друзья:")

async def add_friend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Друг добавлен!")

async def challenges_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Список челленджей:")

async def create_challenge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Челлендж создан.")

def register_social_handlers(application: Application):
    application.add_handler(CommandHandler("friends", friends_command))
    application.add_handler(CommandHandler("add_friend", add_friend_command))
    application.add_handler(CommandHandler("challenges", challenges_command))
    application.add_handler(CommandHandler("create_challenge", create_challenge_command))
