import os
import time
import json
import requests

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
TG_DA_BOT_TOKEN = os.environ.get("TG_DA_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
DA_CLIENT_ID = os.environ.get("DA_CLIENT_ID")
DA_CLIENT_SECRET = os.environ.get("DA_CLIENT_SECRET")

# --- БАЗА ИГР (формат тегов для официального API) ---
GAMES = {
    "Detroit become human": "detroitbecomehuman",
    "Resident evil": "residentevil"
}

OFFSETS_FILE = "offsets.json"
PROCESSED_FILE = "processed_arts.txt"
POSTS_PER_GAME = 5   
DELAY_SECONDS = 15   

def get_da_token():
    """Получает официальный токен доступа от DeviantArt API"""
    url = "https://www.deviantart.com/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": DA_CLIENT_ID,
        "client_secret": DA_CLIENT_SECRET
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"❌ Ошибка авторизации в DeviantArt API: {response.text}")
        return None

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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
    if not DA_CLIENT_ID or not DA_CLIENT_SECRET:
        print("❌ Ошибка: Ключи DA_CLIENT_ID или DA_CLIENT_SECRET не найдены в Secrets!")
        return

    token = get_da_token()
    if not token:
        return

    processed = get_processed_links()
    offsets = load_json(OFFSETS_FILE)

    headers = {"Authorization": f"Bearer {token}"}

    for game_name, tag in GAMES.items():
        current_offset = offsets.get(game_name, 0)
        print(f"\n🔍 Запрос к API (тег: {tag}): {game_name} (Сдвиг: {current_offset})")
        
        # Исправленный официальный эндпоинт для работы с тегами
        search_url = "https://www.deviantart.com/api/v1/oauth2/browse/tag"
        params = {
            "tag": tag,
            "offset": current_offset,
            "limit": 24,
            "mature_content": "true"
        }
        
        try:
            response = requests.get(search_url, headers=headers, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"❌ Ошибка API DeviantArt: Код {response.status_code} - {response.text}")
                continue
                
            data = response.json()
            results = data.get("results", [])
            
        except Exception as e:
            print(f"❌ Ошибка сети: {e}")
            continue
            
        if not results:
            print(f"⚠️ Достигнут конец архива для {game_name}!")
            continue

        count = 0
        items_checked = 0 
        
        for item in results:
            items_checked += 1
            art_link = item.get("url")
            
            if not art_link or art_link in processed: 
                continue

            title = item.get("title", "Без названия")
            author_info = item.get("author", {})
            author = author_info.get("username", "Неизвестный автор")
            
            image_url = None
            content = item.get("content")
            if content and "src" in content:
                image_url = content["src"]
            
            if not image_url:
                preview = item.get("preview")
                if preview and "src" in preview:
                    image_url = preview["src"]
                    
            if not image_url:
                print(f"⚠️ Пропуск: нет прямой картинки для '{title}'")
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

    save_json(OFFSETS_FILE, offsets)

if __name__ == "__main__":
    main()
