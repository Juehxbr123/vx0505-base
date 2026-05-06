from aiogram import Bot
from aiogram.utils.media_group import MediaGroupBuilder
from logger import logger
import config

async def send_tweet_to_telegram(bot: Bot, username: str, tweet: dict):
    """
    Выполняет форматирование и трансляцию контента в целевой Telegram канал/чат.
    Обрабатывает текстовую разметку и медиа-альбомы.
    """
    try:
        # Установка наглядного префикса типа публикации
        if tweet["is_retweet"]:
            prefix = f"🔄 <b>Ретвит от @{username}</b>"
        elif tweet["is_reply"]:
            prefix = f"💬 <b>Ответ @{username}</b>"
        else:
            prefix = f"📝 <b>Новый пост @{username}</b>"
        
        # Сборка финального HTML сообщения с указанием времени публикации по МСК
        message_text = (
            f"{prefix}\n\n"
            f"{tweet['text']}\n\n"
            f"📅 <b>Время поста:</b> {tweet.get('date_msk', 'Не указано')} (МСК)\n"
            f"🔗 <a href='{tweet['url']}'>Ссылка на оригинальный пост</a>"
        )
        
        chat_id = config.CHAT_ID
        media = tweet.get("media", [])
        
        # Сценарий 1: Чисто текстовый твит
        if not media:
            await bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode="HTML",
                disable_web_page_preview=False
            )
            logger.info(f"Отправлен текстовый твит {tweet['id']} пользователя @{username}")
            return

        # Сценарий 2: Пост с одним медиафайлом (картинка / GIF)
        if len(media) == 1:
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=media[0],
                    caption=message_text[:1024],  # Лимит Telegram на подписи к файлам
                    parse_mode="HTML"
                )
                logger.info(f"Отправлен твит с медиа {tweet['id']} пользователя @{username}")
            except Exception as media_err:
                logger.error(f"Сбой отправки фото, резервный запуск текста: {media_err}")
                await bot.send_message(chat_id=chat_id, text=message_text, parse_mode="HTML")
                
        # Сценарий 3: Пост с группой картинок (Альбом / Media Group)
        else:
            media_group = MediaGroupBuilder(caption=message_text[:1024])
            # Ограничение API Telegram на вложения внутри альбома - до 10 штук
            for item_url in media[:10]:
                media_group.add_photo(media=item_url)
                
            try:
                await bot.send_media_group(chat_id=chat_id, media=media_group.build())
                logger.info(f"Отправлен твит-альбом {tweet['id']} пользователя @{username}")
            except Exception as album_err:
                logger.error(f"Сбой отправки альбома, падение на отправку текста: {album_err}")
                await bot.send_message(chat_id=chat_id, text=message_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка в модуле tg_sender для @{username}, ID твита {tweet.get('id')}: {e}")