import os
import json
from logger import logger

DATA_DIR = "data"
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
LAST_POSTS_FILE = os.path.join(DATA_DIR, "last_posts.json")

def init_storage():
    """Атомарная инициализация структуры директорий и пустых кэш-файлов."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=4)
    if not os.path.exists(LAST_POSTS_FILE):
        with open(LAST_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)

def get_accounts() -> list:
    """Извлекает массив отслеживаемых юзернеймов."""
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {ACCOUNTS_FILE}: {e}")
        return []

def add_account(username: str) -> bool:
    """Добавляет имя в json файл без дублирования."""
    username = username.lower().strip().lstrip("@")
    accounts = get_accounts()
    if username in accounts:
        return False
    accounts.append(username)
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Ошибка записи аккаунта {username}: {e}")
        return False

def delete_account(username: str) -> bool:
    """Удаляет имя из мониторинга и подчищает его последний зафиксированный ID."""
    username = username.lower().strip().lstrip("@")
    accounts = get_accounts()
    if username not in accounts:
        return False
    accounts.remove(username)
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(accounts, f, ensure_ascii=False, indent=4)
            
        # Удаляем исторические маркеры дублей
        last_posts = get_last_posts()
        if username in last_posts:
            del last_posts[username]
            save_last_posts(last_posts)
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления аккаунта {username}: {e}")
        return False

def get_last_posts() -> dict:
    """Получает словарь соответствия username -> last_tweet_id."""
    try:
        with open(LAST_POSTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {LAST_POSTS_FILE}: {e}")
        return {}

def save_last_posts(data: dict):
    """Перезаписывает кэш-файл последней обработанной информации."""
    try:
        with open(LAST_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Ошибка сохранения {LAST_POSTS_FILE}: {e}")