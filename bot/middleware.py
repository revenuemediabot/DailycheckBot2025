from telegram.ext import Application, BaseMiddleware, ContextTypes, Update
from telegram import Message
import logging
import asyncio

# === Кастомный anti-flood middleware ===

class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, rate_limit_seconds=2):
        super().__init__()
        self.rate_limit_seconds = rate_limit_seconds
        self.user_timestamps = {}

    async def __call__(self, update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler):
        user_id = None
        if update.effective_user:
            user_id = update.effective_user.id
        now = asyncio.get_event_loop().time()

        if user_id:
            last = self.user_timestamps.get(user_id, 0)
            if now - last < self.rate_limit_seconds:
                # Пропускаем обработчик, можно отправить предупреждение
                logging.info(f"User {user_id} is flooding, skipping update")
                return  # просто не вызываем next_handler (или можно отправить предупреждение)
            self.user_timestamps[user_id] = now

        return await next_handler(update, context)

# === Подключение middlewares к Application ===

def setup_middlewares(application: Application):
    # Добавляем антифлуд
    application.add_middleware(AntiFloodMiddleware(rate_limit_seconds=2))
    # Можно добавить еще middlewares, например логгер, валидацию и т.д.
