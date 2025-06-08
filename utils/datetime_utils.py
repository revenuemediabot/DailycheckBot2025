from datetime import datetime, timedelta
import pytz

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

def now_moscow():
    return datetime.now(MOSCOW_TZ)

def format_date(dt: datetime, fmt: str = "%d.%m.%Y") -> str:
    return dt.strftime(fmt)

def today_str() -> str:
    return now_moscow().strftime("%Y-%m-%d")

def add_days(dt: datetime, days: int) -> datetime:
    return dt + timedelta(days=days)

def parse_date(date_str: str, fmt: str = "%Y-%m-%d") -> datetime:
    return datetime.strptime(date_str, fmt)
