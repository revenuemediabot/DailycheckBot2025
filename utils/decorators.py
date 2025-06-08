import functools
import logging
import asyncio

def retry_on_exception(retries=3, delay=2):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(1, retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logging.warning(f"Попытка {attempt}: {e}")
                    if attempt < retries:
                        await asyncio.sleep(delay)
            raise Exception("Все попытки не удались.")
        return wrapper
    return decorator

def admin_only(func):
    @functools.wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        admin_ids = context.bot_data.get("ADMIN_IDS", [])
        user_id = update.effective_user.id
        if user_id not in admin_ids:
            await update.message.reply_text("⛔️ Команда только для администратора.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
