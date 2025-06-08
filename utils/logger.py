import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logger(log_file: str = "bot.log", max_bytes: int = 10_000_000, backup_count: int = 5):
    Path(log_file).parent.mkdir(exist_ok=True, parents=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
