import os
import time
import feedparser
import requests
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
TG_DA_BOT_TOKEN = os.environ.get("TG_DA_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

# --- СПИСОК ИГР ---
RSS_URLS = [
    "https://backend.deviantart.com/rss.xml?q=Detroit+become+human",
    "https://backend.deviantart.com/rss.xml?q=Resident+evil"
]

PROCESSED_FILE = "processed_arts.txt"
POSTS_PER_GAME = 5   
DELAY_SECONDS = 15   

def get_processed_links():
    if not os.path.exists(PROCESSED_FILE): return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def add_to_processed_list(link):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def send_photo_to_telegram(image_url, caption):
    """Отправляет картинку в Telegram"""
    if not TG_DA_BOT_TOKEN or not TG_CHAT_ID:
        print("❌ Ошибка: Ключи Telegram не найдены в Secrets!")
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
        print(f"❌ Ошибка Telegram (возможно неверный формат): {response.text}")
        return False

def main():
    processed = get_processed_links()

    for url in RSS_URLS:
        game_name = url.split('=')[-1].replace('+', ' ')
        print(f"\n🔍 Ищем арты по запросу: {game_name}")
        
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"❌ Ошибка чтения ленты для {game_name}: {e}")
            continue
            
        count = 0
        
        for entry in feed.entries:
            art_link = entry.link
            if art_link in processed: continue

            title = entry.title
            author = entry.author if hasattr(entry, 'author') else "Неизвестный автор"
            
            # --- ТРЕХУРОВНЕВЫЙ ПОИСК КАРТИНКИ ---
            image_url = None
            
            # 1. Проверяем основной контент
            if 'media_content' in entry and len(entry.media_content) > 0:
                image_url = entry.media_content[0].get('url')
                
            # 2. Проверяем миниатюры
            if not image_url and 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
                image_url = entry.media_thumbnail[0].get('url')
                
            # 3. Парсим само описание (защита от пикселей-трекеров)
            if not image_url and hasattr(entry, 'description'):
                soup = BeautifulSoup(entry.description, 'html.parser')
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    if not src: continue
                    # Отсекаем невидимые пиксели и аватарки
                    if img.get('width') == '1' or img.get('height') == '1': continue
                    if 'avatar' in src.lower(): continue
                    
                    image_url = src
                    break
                    
            if not image_url:
                print(f"⚠️ Пропуск: нет валидной картинки для '{title}'")
                continue
                
            print(f"🖼 Отправляем: {title}")
            caption = f"🎨 <b>{title}</b>\n👤 Автор: {author}\n\n🔗 <a href='{art_link}'>Оригинал на DeviantArt</a>"
            
            # Если Телеграм всё-таки подавится ссылкой, скрипт не упадет, а просто пойдет дальше
            if send_photo_to_telegram(image_url, caption):
                add_to_processed_list(art_link)
                count += 1
                
                if count >= POSTS_PER_GAME:
                    print(f"🛑 Собрали {POSTS_PER_GAME} артов для {game_name}.")
                    break
                    
                print(f"⏳ Ждем {DELAY_SECONDS} сек...")
                time.sleep(DELAY_SECONDS)

if __name__ == "__main__":
    main()
