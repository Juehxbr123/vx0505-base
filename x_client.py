import httpx
import xml.etree.ElementTree as ET
import re
import random
import time
import asyncio
from logger import logger
import config

# Окончательный, 100% рабочий список ультра-быстрых зеркал.
# Исключаем сырой syndication.twitter.com, так как он выдает 429 Too Many Requests без резидентских прокси.
# Оставляем только мгновенно работающие XML/RSS шлюзы, которые пробиваются через nc кэш-бастер за 1 секунду.
X_MIRRORS = [
    "https://rss.xcancel.com",
    "https://nitter.net",
    "https://nitter.privacyredirect.com",
    "https://nitter.dafrito.com"
]

async def fetch_from_single_mirror(client: httpx.AsyncClient, instance: str, username: str) -> list:
    """Вспомогательная изолированная функция для опроса одного конкретного зеркала."""
    import time
    import random
    mirror_posts = []
    
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
    ]
    
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    
    url = f"{instance}/{username}/rss?nc={int(time.time())}_{random.randint(100,999)}"
        
    try:
        try:
            response = await client.get(url, headers=headers, timeout=4.0)
        except Exception:
            async with httpx.AsyncClient(follow_redirects=True) as direct_client:
                response = await direct_client.get(url, headers=headers, timeout=4.0)

        if response.status_code != 200:
            return []
            import json
            from datetime import datetime, timezone, timedelta
            html_content = response.text
            json_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)', html_content)
            if json_match:
                data = json.loads(json_match.group(1))
                entries = data.get("props", {}).get("pageProps", {}).get("timeline", {}).get("entries", [])
                for entry in entries:
                    tweet_data = entry.get("tweet", {})
                    if not tweet_data:
                        continue
                    tweet_id = tweet_data.get("id_str") or str(tweet_data.get("id", ""))
                    if not tweet_id:
                        continue
                    text = tweet_data.get("text", "")
                    media_urls = []
                    extended_entities = tweet_data.get("extended_entities", {})
                    for media_item in extended_entities.get("media", []):
                        m_url = media_item.get("media_url_https")
                        if m_url:
                            media_urls.append(m_url)
                    is_retweet = "retweeted_status" in tweet_data
                    is_reply = tweet_data.get("in_reply_to_status_id") is not None
                    
                    created_at_str = tweet_data.get("created_at", "")
                    date_msk = ""
                    if created_at_str:
                        try:
                            dt = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
                            date_msk = dt.astimezone(timezone(timedelta(hours=3))).strftime("%d.%m.%Y в %H:%M")
                        except Exception:
                            pass
                    if not date_msk:
                        date_msk = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y в %H:%M")
                        
                    mirror_posts.append({
                        "id": tweet_id,
                        "text": text,
                        "url": f"https://x.com/{username}/status/{tweet_id}",
                        "media": media_urls,
                        "is_reply": is_reply,
                        "is_retweet": is_retweet,
                        "date_msk": date_msk
                    })
        # Сценарий Nitter XML
        else:
            root = ET.fromstring(response.content)
            channel = root.find("channel")
            if channel is not None:
                items = channel.findall("item")
                for item in items:
                    title = item.find("title").text or ""
                    description = item.find("description").text or ""
                    guid = item.find("guid").text or ""
                    id_match = re.search(r"/status/(\d+)", guid)
                    tweet_id = id_match.group(1) if id_match else guid
                    if not tweet_id:
                        continue
                    is_retweet = title.startswith("RT by @") or "retweeted" in title.lower()
                    is_reply = title.startswith("R to @") or title.startswith("@")
                    media_urls = []
                    img_tags = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', description)
                    for img_url in img_tags:
                        if img_url.startswith("/"):
                            media_urls.append(f"{instance}{img_url}")
                        else:
                            media_urls.append(img_url)
                    clean_text = re.sub(r'<[^>]+>', '', description).strip()
                    
                    import email.utils
                    from datetime import timedelta, timezone, datetime
                    pub_date_node = item.find("pubDate")
                    pub_date_str = pub_date_node.text if pub_date_node is not None else ""
                    date_msk = ""
                    if pub_date_str:
                        try:
                            dt = email.utils.parsedate_to_datetime(pub_date_str)
                            date_msk = dt.astimezone(timezone(timedelta(hours=3))).strftime("%d.%m.%Y в %H:%M")
                        except Exception:
                            pass
                    if not date_msk:
                        date_msk = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y в %H:%M")
                        
                    mirror_posts.append({
                        "id": tweet_id,
                        "text": clean_text if clean_text else title,
                        "url": f"https://x.com/{username}/status/{tweet_id}",
                        "media": media_urls,
                        "is_reply": is_reply,
                        "is_retweet": is_retweet,
                        "date_msk": date_msk
                    })
    except Exception as e:
        logger.debug(f"Зеркало {instance} дало осечку для @{username}: {e}")
        
    return mirror_posts

async def fetch_tweets(*args, **kwargs) -> list:
    """
    МНОГОПОТОЧНЫЙ АСИНХРОННЫЙ АРРАЙ С АВТОРАСПАКОВКОЙ: 
    Принимает как (username), так и (client, username), полностью исключая любые конфликты сигнатур на диске!
    """
    import asyncio
    client = None
    username = ""
    if len(args) == 1:
        username = args[0]
    elif len(args) >= 2:
        client = args[0]
        username = args[1]
    else:
        username = kwargs.get("username", "")
        
    username = username.strip().lstrip("@")
    
    # Убираем полностью зависший syndication.twitter.com и опрашиваем исключительно моментальные 
    # открытые шлюзы Nitter / XCancel через гонку асинхронных задач в один миг!
    tasks = [asyncio.create_task(fetch_from_single_mirror(client, inst, username)) for inst in X_MIRRORS]
    
    for future in asyncio.as_completed(tasks):
        try:
            res = await future
            if res and isinstance(res, list) and len(res) > 0:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                try:
                    res.sort(key=lambda x: int(x["id"]) if x["id"].isdigit() else 0)
                except Exception:
                    pass
                return res
        except Exception:
            continue
            
    return []