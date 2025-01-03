from dotenv import load_dotenv
import os

# Загружаем переменные окружения из .env файла
load_dotenv()

# Bot settings
TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Database settings
DB_PATH = "bot_database.db"

# Limits
DAILY_INVITE_LIMIT = int(os.getenv("DAILY_INVITE_LIMIT", 50))
INVITE_DELAY = int(os.getenv("INVITE_DELAY", 3))
DECLINE_WAIT_DAYS = int(os.getenv("DECLINE_WAIT_DAYS", 30))

# Debug settings
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Лимиты для пользователей
FREE_TIER_LIMITS = {
    "groups_per_day": 5,
    "users_per_group": 1000,
    "invites_per_day": 50
}

PREMIUM_TIER_LIMITS = {
    "groups_per_day": 20,
    "users_per_group": 5000,
    "invites_per_day": 200
}

# Добавьте в config.py
ADMIN_IDS = [666679197]  # Замените на реальный ID админа

# Проверка обязательных переменных
def check_env():
    required_vars = ["BOT_TOKEN", "API_ID", "API_HASH"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}\n"
            f"Please check your .env file"
        )

# Вызываем проверку при импорте конфига
check_env()
