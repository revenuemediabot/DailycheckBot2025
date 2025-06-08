#!/usr/bin/env python3

import os
import sys
import logging
import asyncio
import threading
import signal
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Переменные окружения
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден!")
    sys.exit(1)

logger.info(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")
if OPENAI_API_KEY:
    logger.info(f"🤖 OpenAI: {OPENAI_API_KEY[:10]}...")

# Импорты Telegram
try:
    from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters
    from telegram import Update
    from telegram.ext import ContextTypes
except ImportError as e:
    logger.error(f"Ошибка импорта telegram: {e}")
    sys.exit(1)

# Глобальные переменные
app = None
http_server = None
running = True

# === ОБРАБОТЧИКИ КОМАНД ===

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🚀 Привет, {user.first_name}!\n\n"
        f"Я DailyCheck Bot - твой ассистент для продуктивности.\n\n"
        f"Команды:\n"
        f"/start - главное меню\n"
        f"/help - справка\n"
        f"/health - проверка бота\n\n"
        f"💬 Просто пиши мне - я отвечу через AI!"
    )
    logger.info(f"Старт от пользователя {user.id}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 <b>DailyCheck Bot - справка</b>\n\n"
        "🔧 <b>Команды:</b>\n"
        "/start - начать работу\n"
        "/help - эта справка\n"
        "/health - проверка работы\n\n"
        "🤖 <b>AI-функции:</b>\n"
        "• Просто напишите сообщение\n"
        "• Бот ответит через ChatGPT\n"
        "• Задавайте вопросы о продуктивности\n\n"
        "💡 <b>Примеры:</b>\n"
        "• 'Как лучше планировать день?'\n"
        "• 'Помоги с мотивацией'\n"
        "• 'Создай список задач'"
    )
    await update.message.reply_html(help_text)

async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Бот работает отлично!\n"
        f"🤖 AI: {'включен' if OPENAI_API_KEY else 'выключен'}\n"
        f"🔗 HTTP: работает на порту {PORT}"
    )

# === AI ОБРАБОТЧИК ===

async def generate_ai_response(user_text: str, user_name: str = "друг") -> str:
    """Генерация AI ответа"""
    if not OPENAI_API_KEY:
        return (
            f"🤖 Привет! AI временно недоступен.\n"
            f"Но я всё равно рад нашему общению!\n\n"
            f"Вы написали: '{user_text}'"
        )
    
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        system_prompt = (
            "Ты полезный AI-ассистент для продуктивности и планирования. "
            "Отвечай дружелюбно, кратко и по делу. "
            "Помогай с задачами, мотивацией и организацией времени. "
            "Используй эмодзи для наглядности."
        )
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Ошибка AI: {e}")
        return (
            f"⚠️ Произошла ошибка с AI.\n"
            f"Но я запомнил ваше сообщение: '{user_text}'\n"
            f"Попробуйте ещё раз через минуту!"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_text = update.message.text
    user = update.effective_user
    
    logger.info(f"Сообщение от {user.id} (@{user.username}): {user_text[:50]}...")
    
    # Показываем "печатает"
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, 
        action="typing"
    )
    
    # Генерируем ответ
    try:
        response = await generate_ai_response(user_text, user.first_name)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await update.message.reply_text(
            "😅 Что-то пошло не так, но я стараюсь! Попробуйте ещё раз."
        )

# === HTTP СЕРВЕР ===

def start_http_server():
    """Запуск простого HTTP сервера для health check"""
    import http.server
    import socketserver
    import json
    
    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path in ['/', '/health']:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response_data = {
                    "status": "ok",
                    "service": "dailycheck-bot",
                    "version": "4.0",
                    "ai_enabled": bool(OPENAI_API_KEY),
                    "message": "DailyCheck Bot работает!"
                }
                
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            # Отключаем HTTP логи
            pass
    
    def run_server():
        try:
            with socketserver.TCPServer(("", PORT), HealthHandler) as httpd:
                logger.info(f"✅ HTTP сервер запущен на порту {PORT}")
                httpd.serve_forever()
        except Exception as e:
            logger.error(f"Ошибка HTTP сервера: {e}")
    
    # Запускаем в отдельном потоке
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    return server_thread

# === ОСНОВНАЯ ЛОГИКА ===

def create_bot_application():
    """Создание приложения бота"""
    global app
    
    try:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Регистрируем обработчики
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("health", health_command))
        
        # AI чат
        app.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
        )
        
        logger.info("✅ Приложение создано")
        return app
        
    except Exception as e:
        logger.error(f"Ошибка создания приложения: {e}")
        raise

async def run_bot():
    """Запуск бота"""
    global running
    
    try:
        logger.info("🚀 Запуск DailyCheck Bot v4.0...")
        
        # HTTP сервер
        http_thread = start_http_server()
        
        # Создание бота
        application = create_bot_application()
        
        logger.info("✅ Бот готов к работе!")
        logger.info("📱 Найдите своего бота в Telegram и отправьте /start")
        
        # Запуск polling
        await application.run_polling(
            drop_pending_updates=True,
            stop_signals=[]  # Отключаем автоматическую обработку сигналов
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в run_bot: {e}")
        running = False
        raise

def signal_handler(signum, frame):
    """Обработчик сигналов остановки"""
    global running
    logger.info(f"Получен сигнал {signum}. Остановка...")
    running = False

# === ТОЧКА ВХОДА ===

def main():
    """Главная функция"""
    global running
    
    # Настройка обработчиков сигналов
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Информация о системе
    logger.info(f"Python: {sys.version}")
    logger.info(f"Платформа: {sys.platform}")
    logger.info(f"Директория: {os.getcwd()}")
    
    try:
        # Запуск бота
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("👋 Остановка по Ctrl+C")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)
    finally:
        logger.info("🛑 Бот остановлен")

if __name__ == "__main__":
    print("🚀 DailyCheck Bot запускается...")
    
    # Проверка версии Python
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8+")
        sys.exit(1)
    
    main()
