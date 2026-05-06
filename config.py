import os
from dotenv import load_dotenv

# Принудительная подгрузка .env окружения
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PROXY = os.getenv("PROXY")
TWITTER_AUTH_TOKEN = os.getenv("TWITTER_AUTH_TOKEN")
TWITTER_CT0 = os.getenv("TWITTER_CT0")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("Критическая Ошибка: Переменные BOT_TOKEN и CHAT_ID должны быть заполнены в .env")