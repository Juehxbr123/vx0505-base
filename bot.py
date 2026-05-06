import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.client.default import DefaultBotProperties
import config
import storage
from worker import tracking_worker
from logger import logger

# Инициализация Бота и Диспетчера событий
# Настройка SOCKS5/HTTP прокси, если он передан в .env файле
bot_kwargs = {"token": config.BOT_TOKEN, "default": DefaultBotProperties(parse_mode="HTML")}
if config.PROXY:
    from aiogram.client.session.aiohttp import AiohttpSession
    session = AiohttpSession(proxy=config.PROXY)
    bot_kwargs["session"] = session

bot = Bot(**bot_kwargs)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Приветственное сообщение и список доступных команд управления."""
    await message.answer(
        "👋 <b>Привет! Я бот-ретранслятор из X (Twitter) в Telegram!</b>\n\n"
        "🔧 <b>Команды управления:</b>\n"
        "/list — Показать список отслеживаемых аккаунтов\n"
        "/add @username — Добавить аккаунт на отслеживание\n"
        "/delete username — Удалить аккаунт из списка\n\n"
        "💡 Все новые посты, ретвиты и ответы будут автоматически пересылаться в указанный канал каждые 10 секунд!"
    )

@dp.message(Command("list"))
async def cmd_list(message: types.Message):
    """Выводит актуальный упорядоченный список всех отслеживаемых аккаунтов."""
    accounts = storage.get_accounts()
    if not accounts:
        await message.answer("📁 Список отслеживаемых аккаунтов пуст.")
        return
        
    text = "📋 <b>Отслеживаемые аккаунты ({}/50):</b>\n\n".format(len(accounts))
    for idx, acc in enumerate(accounts, 1):
        text += f"{idx}. <a href='https://x.com/{acc}'>@{acc}</a>\n"
    await message.answer(text, disable_web_page_preview=True)

@dp.message(Command("add"))
async def cmd_add(message: types.Message, command: CommandObject):
    """Добавляет новый аккаунт X в локальный стэк с проверкой лимита в 50 позиций."""
    if not command.args:
        await message.answer("⚠️ Пожалуйста, укажите username. Пример: <code>/add @elonmusk</code>")
        return
        
    username = command.args.strip().lstrip("@")
    accounts = storage.get_accounts()
    
    if len(accounts) >= 50:
        await message.answer("🚫 Достигнут жесткий лимит в 50 отслеживаемых аккаунтов.")
        return
        
    success = storage.add_account(username)
    if success:
        await message.answer(f"✅ Аккаунт <b>@{username}</b> успешно добавлен в список отслеживания!")
        logger.info(f"Аккаунт @{username} добавлен в отслеживание через TG команду.")
    else:
        await message.answer(f"ℹ️ Аккаунт <b>@{username}</b> уже присутствует в списке.")

@dp.message(Command("delete"))
async def cmd_delete(message: types.Message, command: CommandObject):
    """Исключает аккаунт X из мониторинга и очищает кэш последних постов."""
    if not command.args:
        await message.answer("⚠️ Пожалуйста, укажите username. Пример: <code>/delete elonmusk</code>")
        return
        
    username = command.args.strip().lstrip("@")
    success = storage.delete_account(username)
    
    if success:
        await message.answer(f"🗑️ Аккаунт <b>@{username}</b> успешно удален из отслеживания.")
        logger.info(f"Аккаунт @{username} удален из мониторинга через TG команду.")
    else:
        await message.answer(f"❌ Аккаунт <b>@{username}</b> не найден в списке мониторинга.")

async def main():
    import httpx
    # Гарантируем создание необходимых JSON-файлов при холодном пуске
    storage.init_storage()
    
    logger.info("Запуск Telegram Бота и фонового асинхронного воркера...")
    
    # Сверхгениальный апгрейд: создаем ОДИН единый глобальный постоянный HTTPX клиент для всего приложения.
    # Это сохраняет куки (guest_id), держит постоянное TCP-соединение (Keep-Alive), убирает ошибку SOCKS failure
    # и полностью ликвидирует лимиты 429, имитируя стабильную сессию реального браузера.
    proxies = config.PROXY if config.PROXY else None
    
    # Подгружаем куки авторизации аккаунта-пустышки, если они заполнены в .env
    cookies = {}
    if getattr(config, "TWITTER_AUTH_TOKEN", None) and getattr(config, "TWITTER_CT0", None):
        cookies = {"auth_token": config.TWITTER_AUTH_TOKEN, "ct0": config.TWITTER_CT0}
        
    async with httpx.AsyncClient(proxies=proxies, cookies=cookies, follow_redirects=True) as http_client:
        # Передаем постоянный клиент в фоновый воркер
        asyncio.create_task(tracking_worker(bot, http_client))
        
        # Сброс возможных зависших вебхуков и старт бесконечного пуллинга
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Работа бота завершена пользователем.")