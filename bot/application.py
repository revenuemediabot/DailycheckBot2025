from telegram.ext import Application, ApplicationBuilder
from bot.middleware import setup_middlewares
import logging

def build_application(token: str) -> Application:
    # Создание Application
    application = (
        ApplicationBuilder()
        .token(token)
        .concurrent_updates(True)  # если нужен параллелизм
        .build()
    )

    # Подключение middlewares (anti-flood, логгеры и т.д.)
    setup_middlewares(application)

    # Можно добавить ещё кастомные настройки (rate limiter, scheduler и пр.)

    return application
