# main.py - Минимальная рабочая версия
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import asyncio
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Импорт зависимостей с обработкой ошибок
try:
    from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters
    from telegram import Update
    from telegram.ext import ContextTypes
except ImportError as e:
    logger.error(f"Ошибка импорта Telegram библиотек: {e}")
    sys.exit(1)

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv не установлен")

# Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
    sys.exit(1)

# Базовые обработчики команд
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n"
        "Я — DailyCheck Bot для трекинга задач и привычек.\n"
        "Используй /help для списка команд."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = (
        "🛠 <b>Доступные команды:</b>\n"
        "/start — начать работу\n"
        "/help — справка\n"
        "/health — проверка работы бота\n"
        "/echo — повторить сообщение\n"
        "\n📧 Для получения полного функционала настройте OpenAI API ключ"
    )
    await update.message.reply_html(help_text)

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /health для проверки"""
    await update.message.reply_text("✅ Бот работает нормально!")

async def echo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /echo"""
    if context.args:
        text = " ".join(context.args)
        await update.message.reply_text(f"Эхо: {text}")
    else:
        await update.message.reply_text("Использование: /echo <текст>")

# AI обработчик (опционально)
async def ai_response(user_text: str) -> str:
    """Простой AI ответ"""
    if not OPENAI_API_KEY:
        return "🤖 AI временно недоступен. Настройте OPENAI_API_KEY для полного функционала."
    
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты полезный ассистент для продуктивности."},
                {"role": "user", "content": user_text}
            ],
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        return "⚠️ Ошибка при обращении к AI. Попробуйте позже."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик обычных сообщений"""
    user_text = update.message.text
    
    # Показываем индикатор печати
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Получаем ответ
    response = await ai_response(user_text)
    await update.message.reply_text(response)

# Health check сервер
async def start_health_server():
    """Простой health check"""
    try:
        from aiohttp import web
        
        async def health_handler(request):
            return web.json_response({
                "status": "ok",
                "message": "DailyCheck Bot работает!",
                "version": "4.0"
            })
        
        app = web.Application()
        app.router.add_get('/health', health_handler)
        app.router.add_get('/', health_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        logger.info(f"✅ Health server запущен на порту {PORT}")
        
    except ImportError:
        logger.warning("aiohttp недоступен, health server отключен")
    except Exception as e:
        logger.error(f"Ошибка health server: {e}")

class DailyCheckBot:
    def __init__(self):
        self.application = None
    
    async def start(self):
        """Запуск бота"""
        try:
            logger.info("🚀 Запуск DailyCheck Bot v4.0...")
            
            # Создание приложения
            self.application = ApplicationBuilder().token(BOT_TOKEN).build()
            
            # Регистрация обработчиков
            self.application.add_handler(CommandHandler("start", start_command))
            self.application.add_handler(CommandHandler("help", help_command))
            self.application.add_handler(CommandHandler("health", health_command))
            self.application.add_handler(CommandHandler("echo", echo_command))
            
            # AI чат для обычных сообщений
            self.application.add_handler(
                MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
            )
            
            # Запуск health сервера
            await start_health_server()
            
            # Запуск бота
            logger.info("✅ Бот готов к работе!")
            await self.application.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            raise

async def main():
    """Главная функция"""
    bot = DailyCheckBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("👋 Остановка по Ctrl+C")
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")

if __name__ == "__main__":
    print("🚀 Запуск DailyCheck Bot...")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 До свидания!")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")

# =================================================================
# .env (создайте этот файл в корне проекта)
# =================================================================
"""
# Скопируйте эти переменные в файл .env
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
OPENAI_API_KEY=YOUR_OPENAI_API_KEY_HERE
PORT=8080
"""

# =================================================================
# requirements.txt (обновленная минимальная версия)
# =================================================================
"""
python-telegram-bot==20.7
python-dotenv
openai
aiohttp
"""
