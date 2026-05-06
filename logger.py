import logging
import sys
from logging.handlers import RotatingFileHandler

# Комплексная конфигурация потоков вывода (Файл c авто-ротацией + Терминал)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler("bot.log", maxBytes=5*1024*1024, backupCount=2, encoding="utf-8")
    ]
)

logger = logging.getLogger("X-Telegram-Relay")