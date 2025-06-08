import os
from dotenv import load_dotenv
from pathlib import Path

# Загрузка .env
load_dotenv()

# === Переменные окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
PSY_SYSTEM_PROMPT = os.getenv("PSY_SYSTEM_PROMPT")
WATCHDOG_SECONDS = int(os.getenv("WATCHDOG_SECONDS", "600"))
PORT = int(os.getenv("PORT", "8080"))

# === Пути и директории ===
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
LOCKS_DIR = BASE_DIR / ".locks"
EXPORTS_DIR = BASE_DIR / "exports"

# Создаём директории при запуске (если нет)
for _dir in [LOGS_DIR, DATA_DIR, LOCKS_DIR, EXPORTS_DIR]:
    _dir.mkdir(exist_ok=True)

# === Process lock (файл-блокировка) ===
PROCESS_LOCK_FILE = LOCKS_DIR / "dailycheck_bot.lock"

# === Валидаторы и вспомогательные функции (можно отдельно вынести в utils) ===
def is_config_valid():
    return BOT_TOKEN is not None

if not is_config_valid():
    raise RuntimeError("❌ BOT_TOKEN is required in .env file")

# Пример экспорта для дальнейшего импорта:
__all__ = [
    "BOT_TOKEN", "ADMIN_USER_ID", "OPENAI_API_KEY", "GOOGLE_SHEET_ID", 
    "PSY_SYSTEM_PROMPT", "WATCHDOG_SECONDS", "PORT",
    "BASE_DIR", "LOGS_DIR", "DATA_DIR", "LOCKS_DIR", "EXPORTS_DIR", "PROCESS_LOCK_FILE"
]
