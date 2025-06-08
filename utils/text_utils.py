import html
import re

def escape_html(text: str) -> str:
    return html.escape(text)

def truncate(text: str, max_len: int = 64) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"

def clean_markdown(text: str) -> str:
    # Очищает спецсимволы для MarkdownV2
    chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f"[{re.escape(chars)}]", "", text)

def bold(text: str) -> str:
    return f"<b>{escape_html(text)}</b>"

def italic(text: str) -> str:
    return f"<i>{escape_html(text)}</i>"
