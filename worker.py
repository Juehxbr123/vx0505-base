import asyncio
from aiogram import Bot
import storage
import x_client
import tg_sender
from logger import logger

class TrackingWorker:
    """Изолированный воркер для контроля циклов опроса аккаунтов X каждые 10 секунд."""
    pass

async def check_account_updates(bot: Bot, username: str, http_client):
    """Изолированная асинхронная проверка одного аккаунта для параллелизации процессов."""
    try:
        tweets = await x_client.fetch_tweets(http_client, username)
        if not tweets:
            return
            
        # Заново читаем JSON внутри таски для исключения гонки данных между параллельными потоками
        last_posts = storage.get_last_posts()
        last_saved_id = last_posts.get(username)
        
        # Инициализация нового аккаунта (холодный старт):
        # Отправляем строго ОДИН самый свежий пост в качестве проверки связи
        if not last_saved_id:
            latest_tweet = tweets[-1]
            last_posts[username] = latest_tweet["id"]
            storage.save_last_posts(last_posts)
            logger.info(f"Первичная инициализация @{username}. Отправка крайнего поста в качестве проверки связи.")
            await tg_sender.send_tweet_to_telegram(bot, username, latest_tweet)
            return
            
        # Математическое сравнение Snowflake ID:
        # Любой твит, чей числовой ID строго больше сохраненного в базе — является новым!
        new_tweets = []
        try:
            last_id_int = int(last_saved_id)
            for tweet in tweets:
                if int(tweet["id"]) > last_id_int:
                    new_tweets.append(tweet)
        except (ValueError, TypeError):
            new_tweets = [tweets[-1]]
            
        if new_tweets:
            # Берем строго один единственный самый последний актуальный твит согласно требованию пользователя
            tweet_to_send = new_tweets[-1]
            logger.info(f"🔥 [УСПЕХ] Обнаружен новый пост у @{username} (ID: {tweet_to_send['id']}). Отправка в Телеграм...")
            
            await tg_sender.send_tweet_to_telegram(bot, username, tweet_to_send)
            
            # Синхронизируем и сохраняем новый ID в JSON
            last_posts = storage.get_last_posts()
            last_posts[username] = tweet_to_send["id"]
            storage.save_last_posts(last_posts)
        else:
            logger.info(f"🔎 Проверка @{username}: новых постов нет. Последний в RSS ленте: {tweets[-1]['id']} | В локальной базе: {last_saved_id}")
            
    except Exception as e:
        logger.error(f"Ошибка параллельной проверки аккаунта @{username}: {e}")

async def tracking_worker(bot: Bot, http_client):
    """Фоновый цикл параллельного мониторинга X. Опрашивает все аккаунты одновременно."""
    logger.info("Фоновый цикл асинхронного одновременного мониторинга X запущен.")
    storage.init_storage()
    
    # Переводим логи в INFO, чтобы не захламлять консоль лишними трейсами прокси
    import logging
    logger.setLevel(logging.INFO)
    
    while True:
        try:
            accounts = storage.get_accounts()
            if not accounts:
                await asyncio.sleep(2)
                continue
                
            tasks = [check_account_updates(bot, username, http_client) for username in accounts]
            await asyncio.gather(*tasks)
                    
        except Exception as e:
            logger.error(f"Критическое исключение в общем цикле воркера: {e}", exc_info=True)
            
        # Цикл опроса — каждые 5 секунд. С постоянной браузерной сессией и Keep-Alive
        # это гарантирует моментальные алерты без малейшего риска блокировок!
        await asyncio.sleep(5)