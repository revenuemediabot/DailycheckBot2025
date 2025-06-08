#!/usr/bin/env python3

import os
import sys
import logging

# Исправление event loop конфликтов
try:
    import nest_asyncio
    nest_asyncio.apply()
    print("✅ nest_asyncio применен")
except ImportError:
    print("⚠️ nest_asyncio недоступен")

# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Переменные окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден!")
    sys.exit(1)

logger.info(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")
if OPENAI_API_KEY:
    logger.info(f"✅ OpenAI: {OPENAI_API_KEY[:10]}...")

# HTTP сервер
import threading
import http.server
import socketserver
import json

def start_health_server():
    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = {
                "status": "ok",
                "service": "dailycheck-bot",
                "version": "4.0",
                "message": "Bot is running!"
            }
            self.wfile.write(json.dumps(data).encode())
        
        def log_message(self, format, *args):
            pass
    
    def run_server():
        try:
            with socketserver.TCPServer(("", PORT), HealthHandler) as httpd:
                logger.info(f"✅ Health server на порту {PORT}")
                httpd.serve_forever()
        except Exception as e:
            logger.error(f"HTTP server ошибка: {e}")
    
    threading.Thread(target=run_server, daemon=True).start()

# Telegram импорты
try:
    from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters
    from telegram import Update
    from telegram.ext import ContextTypes
    logger.info("✅ Telegram библиотеки импортированы")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта Telegram: {e}")
    sys.exit(1)

# Обработчики команд
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"🚀 Привет, {user.first_name}!\n\n"
        f"Я DailyCheck Bot - ваш AI помощник для продуктивности!\n\n"
        f"📖 Команды:\n"
        f"/start - начать работу\n"
        f"/help - подробная справка\n"
        f"/ping - проверка работы\n"
        f"/ai <текст> - AI помощь\n\n"
        f"💬 Или просто напишите мне что-нибудь!"
    )
    await update.message.reply_text(welcome_text)
    logger.info(f"Команда /start от пользователя {user.id}")

# Замените функцию help_command на эту версию (обычный текст):

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📚 DailyCheck Bot - Справка\n\n"
        "🤖 AI Функции:\n"
        "• Просто напишите сообщение\n"
        "• Используйте /ai <ваш вопрос>\n"
        "• Спрашивайте о продуктивности\n\n"
        "🔧 Команды:\n"
        "/start - главное меню\n"
        "/help - эта справка\n"
        "/ping - проверка бота\n"
        "/ai <текст> - прямой запрос к AI\n\n"
        "💡 Примеры вопросов:\n"
        "• Как лучше планировать день?\n"
        "• Помоги с мотивацией\n"
        "• Создай список задач на завтра\n"
        "• Как бороться с прокрастинацией?"
    )
    await update.message.reply_text(help_text)  # Используем reply_text вместо reply_html

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ping_text = (
        "🏓 <b>Понг!</b>\n\n"
        f"✅ Бот работает отлично\n"
        f"🤖 AI: {'включен' if OPENAI_API_KEY else 'выключен'}\n"
        f"🌐 Сервер: активен\n"
        f"⚡ Готов к работе!"
    )
    await update.message.reply_html(ping_text)

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "💭 Использование: /ai <ваш вопрос>\n"
            "Пример: /ai Как лучше организовать рабочий день?"
        )
        return
    
    user_text = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    response = await generate_ai_response(user_text)
    await update.message.reply_text(response)

# AI функции
async def generate_ai_response(text: str) -> str:
    if not OPENAI_API_KEY:
        return (
            f"🤖 AI временно недоступен (не настроен OPENAI_API_KEY).\n\n"
            f"Но я запомнил ваш вопрос: '{text}'\n\n"
            f"💡 Пока что могу предложить базовые советы по продуктивности!"
        )
    
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        system_prompt = (
            "Ты полезный AI-ассистент для продуктивности и планирования. "
            "Отвечай конкретно, полезно и с энтузиазмом. "
            "Используй эмодзи для наглядности. "
            "Давай практические советы."
        )
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=400,
            temperature=0.7
        )
        
        return f"🤖 {response.choices[0].message.content.strip()}"
        
    except Exception as e:
        logger.error(f"AI ошибка: {e}")
        return (
            f"⚠️ Произошла ошибка с AI сервисом.\n\n"
            f"Ваш запрос: '{text}'\n\n"
            f"🔄 Попробуйте еще раз через минуту!"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user = update.effective_user
    
    logger.info(f"Сообщение от {user.id} (@{user.username}): {user_text[:50]}...")
    
    # Показываем "печатает"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        response = await generate_ai_response(user_text)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await update.message.reply_text(
            "😅 Упс! Что-то пошло не так.\n"
            "Попробуйте еще раз или используйте команды."
        )

# Основная функция
# Добавьте в начало функции main() (после логирования):

def main():
    logger.info("🚀 Запуск DailyCheck Bot v4.0...")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Платформа: {sys.platform}")
    
    # Добавьте эту паузу для избежания конфликтов
    import time
    logger.info("⏳ Ожидание завершения предыдущих экземпляров...")
    time.sleep(10)  # 10 секунд пауза
    
    try:
        # Запуск HTTP сервера
        start_health_server()
        
        # Создание Telegram приложения с дополнительными параметрами
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # ... остальной код без изменений ...
        
        logger.info("🎯 Запуск polling...")
        
        # Запуск с повторными попытками
        max_retries = 3
        for attempt in range(max_retries):
            try:
                app.run_polling(drop_pending_updates=True)
                break  # Успешный запуск
            except Exception as e:
                if "Conflict" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"⚠️ Конфликт (попытка {attempt + 1}/{max_retries}), повторная попытка через 15 сек...")
                    time.sleep(15)
                else:
                    raise
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
