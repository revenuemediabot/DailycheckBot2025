# services/ai/client.py

import openai
import logging
from config import OPENAI_API_KEY

# Инициализация клиента OpenAI
def get_openai_client():
    if not OPENAI_API_KEY:
        logging.warning("OpenAI API ключ не найден! AI отключён.")
        return None
    openai.api_key = OPENAI_API_KEY
    return openai
