#!/usr/bin/env python3
"""
Скрипт запуска Telegram бота
Использование: python scripts/start_bot.py [--dev] [--webhook] [--port PORT]
"""

import sys
import os
import asyncio
import argparse
import logging
from pathlib import Path

# Добавляем корневую папку в Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from telegram import Bot
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
    import uvicorn
    from fastapi import FastAPI
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("Установите зависимости: pip install -r requirements.txt")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class BotStarter:
    def __init__(self):
        self.app = None
        self.webhook_app = None
        self.bot_token = os.getenv('BOT_TOKEN')
        self.webhook_url = os.getenv('WEBHOOK_URL')
        self.webhook_port = int(os.getenv('WEBHOOK_PORT', 8443))
        self.webhook_path = '/webhook'
        
        if not self.bot_token:
            logger.error("❌ BOT_TOKEN не найден в переменных окружения")
            sys.exit(1)
    
    def setup_handlers(self):
        """Настройка handlers для бота"""
        try:
            # Импортируем handlers из основного проекта
            from handlers.commands import (
                start_command, help_command, profile_command, 
                tasks_command, leaderboard_command, settings_command
            )
            from handlers.tasks import (
                task_list_handler, task_complete_handler, 
                task_rating_handler, task_search_handler
            )
            from handlers.callbacks import (
                button_callback_handler, pagination_callback_handler
            )
            from handlers.admin import (
                admin_stats_handler, admin_users_handler, 
                admin_tasks_handler, admin_broadcast_handler
            )
            
            # Команды
            self.app.add_handler(CommandHandler("start", start_command))
            self.app.add_handler(CommandHandler("help", help_command))
            self.app.add_handler(CommandHandler("profile", profile_command))
            self.app.add_handler(CommandHandler("tasks", tasks_command))
            self.app.add_handler(CommandHandler("leaderboard", leaderboard_command))
            self.app.add_handler(CommandHandler("settings", settings_command))
            
            # Админские команды
            self.app.add_handler(CommandHandler("admin_stats", admin_stats_handler))
            self.app.add_handler(CommandHandler("admin_users", admin_users_handler))
            self.app.add_handler(CommandHandler("admin_tasks", admin_tasks_handler))
            self.app.add_handler(CommandHandler("broadcast", admin_broadcast_handler))
            
            # Callback handlers
            self.app.add_handler(CallbackQueryHandler(button_callback_handler))
            
            # Message handlers
            self.app.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND, 
                task_search_handler
            ))
            
            logger.info("✅ Handlers настроены успешно")
            
        except ImportError as e:
            logger.warning(f"⚠️ Некоторые handlers не найдены: {e}")
            logger.info("Используем базовые handlers...")
            
            # Базовые handlers если основные не найдены
            self.setup_basic_handlers()
    
    def setup_basic_handlers(self):
        """Базовые handlers для тестирования"""
        
        async def start(update, context):
            await update.message.reply_text(
                "🤖 Привет! Я TaskBot для выполнения задач.\n"
                "Используй /help для получения справки."
            )
        
        async def help_command(update, context):
            help_text = """
🔧 **Доступные команды:**

/start - Начать работу с ботом
/help - Показать эту справку
/profile - Мой профиль
/tasks - Список задач
/leaderboard - Таблица лидеров
/settings - Настройки

🚀 **Статус:** Бот запущен и работает!
            """
            await update.message.reply_text(help_text, parse_mode='Markdown')
        
        async def echo(update, context):
            await update.message.reply_text(
                f"Вы написали: {update.message.text}\n"
                "Используйте /help для получения списка команд."
            )
        
        # Добавляем базовые handlers
        self.app.add_handler(CommandHandler("start", start))
        self.app.add_handler(CommandHandler("help", help_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
        
        logger.info("✅ Базовые handlers настроены")
    
    async def setup_bot_application(self):
        """Настройка Telegram bot application"""
        try:
            # Создаем application
            builder = Application.builder()
            builder.token(self.bot_token)
            
            # Настройка для разработки/продакшена
            if os.getenv('ENVIRONMENT') == 'development':
                builder.read_timeout(30)
                builder.write_timeout(30)
                builder.connect_timeout(30)
                builder.pool_timeout(30)
            
            self.app = builder.build()
            
            # Настраиваем handlers
            self.setup_handlers()
            
            # Инициализируем бота
            await self.app.initialize()
            
            logger.info("✅ Bot application настроен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка настройки bot application: {e}")
            raise
    
    def setup_webhook_app(self):
        """Настройка FastAPI приложения для webhook"""
        from fastapi import FastAPI, Request, HTTPException
        
        webhook_app = FastAPI(title="Telegram Bot Webhook")
        
        @webhook_app.post(self.webhook_path)
        async def webhook_handler(request: Request):
            try:
                # Получаем данные от Telegram
                data = await request.json()
                
                # Обрабатываем update
                await self.app.process_update(data)
                
                return {"status": "ok"}
                
            except Exception as e:
                logger.error(f"Ошибка обработки webhook: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @webhook_app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "bot_username": self.app.bot.username if self.app and self.app.bot else None,
                "webhook_url": self.webhook_url
            }
        
        self.webhook_app = webhook_app
        logger.info("✅ Webhook app настроен")
    
    async def set_webhook(self):
        """Установка webhook"""
        if not self.webhook_url:
            logger.error("❌ WEBHOOK_URL не найден в переменных окружения")
            return False
        
        try:
            webhook_full_url = f"{self.webhook_url.rstrip('/')}{self.webhook_path}"
            
            await self.app.bot.set_webhook(
                url=webhook_full_url,
                drop_pending_updates=True
            )
            
            logger.info(f"✅ Webhook установлен: {webhook_full_url}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки webhook: {e}")
            return False
    
    async def remove_webhook(self):
        """Удаление webhook"""
        try:
            await self.app.bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook удален")
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления webhook: {e}")
    
    async def start_polling(self):
        """Запуск в режиме polling"""
        try:
            logger.info("🚀 Запуск бота в режиме polling...")
            
            await self.setup_bot_application()
            
            # Удаляем webhook если он был установлен
            await self.remove_webhook()
            
            # Запускаем polling
            await self.app.start()
            await self.app.updater.start_polling(
                poll_interval=1.0,
                timeout=20,
                bootstrap_retries=-1,
                read_timeout=20,
                write_timeout=20,
                connect_timeout=20,
                pool_timeout=20
            )
            
            logger.info("✅ Bot запущен в режиме polling")
            logger.info("Нажмите Ctrl+C для остановки...")
            
            # Ждем остановки
            await self.app.updater.idle()
            
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки...")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска polling: {e}")
            raise
        finally:
            await self.app.stop()
            await self.app.shutdown()
            logger.info("✅ Bot остановлен")
    
    async def start_webhook(self, port: int):
        """Запуск в режиме webhook"""
        try:
            logger.info(f"🚀 Запуск бота в режиме webhook на порту {port}...")
            
            await self.setup_bot_application()
            self.setup_webhook_app()
            
            # Устанавливаем webhook
            if not await self.set_webhook():
                raise Exception("Не удалось установить webhook")
            
            # Запускаем FastAPI сервер
            config = uvicorn.Config(
                self.webhook_app,
                host="0.0.0.0",
                port=port,
                log_level="info",
                access_log=False
            )
            
            server = uvicorn.Server(config)
            
            logger.info(f"✅ Webhook сервер запущен на порту {port}")
            logger.info("Нажмите Ctrl+C для остановки...")
            
            await server.serve()
            
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки...")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска webhook: {e}")
            raise
        finally:
            if self.app:
                await self.remove_webhook()
                await self.app.stop()
                await self.app.shutdown()
            logger.info("✅ Webhook сервер остановлен")

def main():
    """Главная функция запуска"""
    
    # Создаем папку для логов
    os.makedirs('logs', exist_ok=True)
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Запуск Telegram бота')
    parser.add_argument('--dev', action='store_true', help='Режим разработки')
    parser.add_argument('--webhook', action='store_true', help='Запуск в режиме webhook')
    parser.add_argument('--port', type=int, default=8443, help='Порт для webhook (по умолчанию 8443)')
    parser.add_argument('--polling', action='store_true', help='Принудительный запуск в режиме polling')
    
    args = parser.parse_args()
    
    # Настройка переменных окружения для разработки
    if args.dev:
        os.environ['ENVIRONMENT'] = 'development'
        logging.getLogger().setLevel(logging.DEBUG)
        logger.info("🔧 Режим разработки активирован")
    
    # Определяем режим запуска
    use_webhook = args.webhook and not args.polling
    
    if 'RENDER' in os.environ or 'HEROKU' in os.environ:
        use_webhook = True
        logger.info("🌐 Обнаружена продакшен среда, используем webhook")
    
    # Создаем starter
    starter = BotStarter()
    
    # Запускаем бота
    try:
        if use_webhook:
            asyncio.run(starter.start_webhook(args.port))
        else:
            asyncio.run(starter.start_polling())
            
    except KeyboardInterrupt:
        logger.info("👋 Пока!")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
