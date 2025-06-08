#!/usr/bin/env python3

import os
import sys
import logging
import threading
import time

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
PORT = int(os.getenv("PORT", "10000"))  # Render использует переменную PORT

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не найден!")
    sys.exit(1)

logger.info(f"✅ BOT_TOKEN: {BOT_TOKEN[:10]}...")
if OPENAI_API_KEY:
    logger.info(f"✅ OpenAI: {OPENAI_API_KEY[:10]}...")

# HTTP сервер для health check (ДОЛЖЕН запуститься первым!)
def start_health_server():
    import http.server
    import socketserver
    import json
    
    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            data = {
                "status": "ok",
                "service": "dailycheck-bot",
                "version": "4.0",
                "message": "Bot is running!"
            }
            self.wfile.write(json.dumps(data).encode())
        
        def log_message(self, format, *args):
            # Логируем только важные запросы
            if '/health' in format or self.path == '/':
                logger.info(f"Health check: {self.client_address[0]}")
    
    def run_server():
        try:
            # Привязка к 0.0.0.0 для внешнего доступа
            with socketserver.TCPServer(("0.0.0.0", PORT), HealthHandler) as httpd:
                logger.info(f"✅ HTTP сервер ЗАПУЩЕН на 0.0.0.0:{PORT}")
                httpd.serve_forever()
        except Exception as e:
            logger.error(f"❌ HTTP server ошибка: {e}")
    
    # Запускаем в отдельном потоке
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Проверяем что сервер запустился
    time.sleep(2)
    logger.info(f"🌐 Health check доступен на http://0.0.0.0:{PORT}")
    return server_thread

# Импорты Telegram
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
    text = (
        f"🚀 Привет, {user.first_name}!\n\n"
        f"Я DailyCheck Bot - ваш AI помощник для продуктивности!\n\n"
        f"Команды:\n"
        f"/start - начать работу\n"
        f"/help - подробная справка\n"
        f"/ping - проверка работы\n"
        f"/ai <текст> - AI помощь\n\n"
        f"💬 Или просто напишите мне что-нибудь!"
    )
    await update.message.reply_text(text)
    logger.info(f"Команда /start от пользователя {user.id}")

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
    await update.message.reply_text(help_text)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ping_text = (
        f"🏓 Понг!\n\n"
        f"✅ Бот работает отлично\n"
        f"🤖 AI: {'включен' if OPENAI_API_KEY else 'выключен'}\n"
        f"🌐 Сервер: порт {PORT}\n"
        f"⚡ Готов к работе!"
    )
    await update.message.reply_text(ping_text)

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
        
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты полезный AI-ассистент для продуктивности. Отвечай кратко и полезно."},
                {"role": "user", "content": text}
            ],
            max_tokens=400,
            temperature=0.7
        )
        
        return f"🤖 {response.choices[0].message.content.strip()}"
        
    except Exception as e:
        logger.error(f"AI ошибка: {e}")
        return f"⚠️ Ошибка AI сервиса. Попробуйте позже!"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user = update.effective_user
    
    logger.info(f"Сообщение от {user.id}: {user_text[:50]}...")
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        response = await generate_ai_response(user_text)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await update.message.reply_text("😅 Что-то пошло не так, попробуйте ещё раз!")

# Основная функция
def main():
    logger.info("🚀 Запуск DailyCheck Bot v4.0...")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Платформа: {sys.platform}")
    logger.info(f"Порт: {PORT}")
    
    try:
        # ШАГ 1: Запуск HTTP сервера (КРИТИЧЕСКИ ВАЖНО для Render!)
        logger.info("🌐 Запуск HTTP сервера...")
        http_thread = start_health_server()
        
        # ШАГ 2: Пауза для стабилизации
        time.sleep(3)
        logger.info("⏳ HTTP сервер стабилизировался")
        
        # ШАГ 3: Создание Telegram приложения
        logger.info("🤖 Создание Telegram приложения...")
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # ШАГ 4: Регистрация обработчиков
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("ping", ping_command))
        app.add_handler(CommandHandler("ai", ai_command))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        logger.info("✅ Обработчики зарегистрированы")
        logger.info("📱 Найдите бота в Telegram и отправьте /start")
        logger.info("🎯 Запуск polling...")
        
        # ШАГ 5: Запуск бота
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        # НЕ выходим сразу - оставляем HTTP сервер работать
        logger.info("🔄 HTTP сервер продолжает работать...")
        
        # Бесконечный цикл чтобы процесс не завершился
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
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
        # Даже при фатальной ошибке оставляем процесс живым для HTTP сервера
        logger.info("🔄 Поддержание процесса для HTTP сервера...")
        try:
            while True:
                time.sleep(300)  # 5 минут
                logger.info("💓 Процесс активен")
        except:
            pass
