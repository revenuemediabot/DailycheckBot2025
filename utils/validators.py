def is_valid_username(username: str) -> bool:
    return username.startswith('@') and 5 <= len(username) <= 32

def is_valid_task_title(title: str) -> bool:
    return 1 <= len(title) <= 100

def is_valid_date(date_str: str) -> bool:
    import re
    return bool(re.match(r"\d{4}-\d{2}-\d{2}", date_str))
