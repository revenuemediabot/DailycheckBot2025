# services/ai/responses.py

from services.ai.client import get_openai_client
from services.ai.prompts import (
    MOTIVATION_PROMPT,
    PSYCHOLOGIST_PROMPT,
    COACH_PROMPT,
    SUGGEST_TASKS_PROMPT,
    DEFAULT_SYSTEM_PROMPT
)
import logging

def generate_ai_response(prompt: str, user_message: str) -> str:
    client = get_openai_client()
    if client is None:
        return ai_fallback(user_message)

    try:
        response = client.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=256,
            temperature=0.9,
        )
        return response.choices[0].message["content"].strip()
    except Exception as e:
        logging.warning(f"AI error: {e}")
        return ai_fallback(user_message)

def ai_fallback(user_message: str) -> str:
    """Фоллбек, если нет доступа к AI"""
    return (
        "⚡️ AI временно недоступен.\n"
        "Попробуйте позже или сформулируйте вопрос по-другому!\n"
        f"Ваш запрос: {user_message}"
    )
