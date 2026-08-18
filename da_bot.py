import os
import time
import json
import feedparser
import requests
import urllib.parse
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
TG_DA_BOT_TOKEN = os.environ.get("TG_DA_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

# --- БАЗА ИГР ---
GAMES = {
    "Detroit become human": "https://backend.deviantart.com/rss.xml?q=Detroit+become+human",
    "Resident evil": "https://backend.deviantart.com/rss.xml?q=Resident+evil"
}

OFFSETS_FILE = "offsets.json"
PROCESSED_FILE = "processed_arts.txt"
POSTS_PER_GAME = 5   
DELAY_SECONDS = 15   

def load_offsets():
    if os.path.exists(OFFSETS_FILE):
        with open(OFFSETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_offsets(offsets):
    with open(OFFSETS_FILE, "w", encoding="utf-8") as f:
        json.dump(offsets, f, ensure_ascii=False, indent=4)

def get_processed_links():
    if not os.path.exists(PROCESSED_FILE): return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def add_to_processed_list(link):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def send_photo_to_telegram(image_url, caption):
    if not TG_DA_BOT_TOKEN or not TG_CHAT_ID:
        print("❌ Ошибка: Ключи Telegram не найдены!")
        return False
        
    url = f"https://api.telegram.org/bot{TG_DA_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": TG_CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return True
    else:
        print(f"❌ Ошибка Telegram: {response.text}")
        return False

def main():
    processed = get_processed_links()
    offsets = load_offsets()

    for game_name, base_url in GAMES.items():
        current_offset = offsets.get(game_name, 0)
        target_url = f"{base_url}&offset={current_offset}"
        
        print(f"\n🔍 Ищем арты по: {game_name} (Сдвиг: {current_offset})")
        
        try:
            # 🔥 ИСПОЛЬЗУЕМ PROXY-МОСТ 🔥
            # Кодируем нашу ссылку, чтобы безопасно передать её через AllOrigins
            encoded_url = urllib.parse.quote(target_url, safe="")
            proxy_url = f"https://api.allorigins.win/raw?url={encoded_url}"
            
            # Стучимся не напрямую в DeviantArt, а просим AllOrigins скачать для нас XML
            response = requests.get(proxy_url, timeout=20)
            
            if response.status_code != 200:
                print(f"❌ Прокси-сервер не смог пробиться. Код: {response.status_code}")
                continue
                
            feed = feedparser.parse(response.content)
            
        except Exception as e:
            print(f"❌ Ошибка сети: {e}")
            continue
            
        if not feed.entries:
            print(f"⚠️ Достигнут конец архива (или пустой ответ) для {game_name}!")
            continue

        count = 0
        items_checked = 0 
        
        for entry in feed.entries:
            items_checked += 1
            art_link = entry.link
            
            if art_link in processed: 
                continue

            title = entry.title
            author = entry.author if hasattr(entry, 'author') else "Неизвестный автор"
            
            image_url = None
            if 'media_content' in entry and len(entry.media_content) > 0:
                image_url = entry.media_content[0].get('url')
            if not image_url and 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
                image_url = entry.media_thumbnail[0].get('url')
            if not image_url and hasattr(entry, 'description'):
                soup = BeautifulSoup(entry.description, 'html.parser')
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    if not src or img.get('width') == '1' or img.get('height') == '1': continue
                    if 'avatar' in src.lower(): continue
                    image_url = src
                    break
                    
            if not image_url:
                print(f"⚠️ Пропуск: нет валидной картинки для '{title}'")
                continue
                
            print(f"🖼 Отправляем: {title}")
            caption = f"🎨 <b>{title}</b>\n👤 Автор: {author}\n\n🔗 <a href='{art_link}'>Оригинал на DeviantArt</a>"
            
            if send_photo_to_telegram(image_url, caption):
                add_to_processed_list(art_link)
                count += 1
                
                if count >= POSTS_PER_GAME:
                    print(f"🛑 Собрали {POSTS_PER_GAME} артов для {game_name}.")
                    break
                    
                print(f"⏳ Ждем {DELAY_SECONDS} сек...")
                time.sleep(DELAY_SECONDS)
        
        offsets[game_name] = current_offset + items_checked

    save_offsets(offsets)

if __name__ == "__main__":
    main()
