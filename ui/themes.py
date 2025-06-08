# ui/themes.py

THEMES = {
    "default": {
        "emoji": "🎯",
        "color": "#2C3E50",
        "name": "Default"
    },
    "dark": {
        "emoji": "🌑",
        "color": "#111111",
        "name": "Dark"
    },
    "pink": {
        "emoji": "🌸",
        "color": "#E91E63",
        "name": "Pink"
    },
    "blue": {
        "emoji": "🌊",
        "color": "#2196F3",
        "name": "Blue"
    }
}

def get_theme(theme_name: str):
    return THEMES.get(theme_name, THEMES["default"])
