import os
import time
import json
import requests

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
TG_DA_BOT_TOKEN = os.environ.get("TG_DA_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
DA_CLIENT_ID = os.environ.get("DA_CLIENT_ID")
DA_CLIENT_SECRET = os.environ.get("DA_CLIENT_SECRET")

# --- ТВОИ ПРЯМЫЕ ССЫЛКИ НА ПОИСК ---
GAMES = {
    "Detroit become human": "https://www.deviantart.com/search?q=Detroit+become+human",
    "Resident evil": "https://www.deviantart.com/search?q=Resident+evil"
}

OFFSETS_FILE = "offsets.json"
PROCESSED_FILE = "processed_arts.txt"
POSTS_PER_GAME = 10   
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
        print(f"DA Auth Error: {response.text}")
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
        print("Telegram keys not found!")
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
        print(f"Telegram Error: {response.text}")
        return False

def main():
    if not DA_CLIENT_ID or not DA_CLIENT_SECRET:
        print("Error: DA API keys not found in Secrets!")
        return

    token = get_da_token()
    if not token:
        return

    processed = get_processed_links()
    offsets = load_json(OFFSETS_FILE)

    headers = {"Authorization": f"Bearer {token}"}

    for game_name, search_url in GAMES.items():
        # Достаем поисковый запрос из твоей ссылки (например: detroitbecomehuman)
        query_part = search_url.split("q=")[1]
        tag_name = query_part.replace("+", "").lower()
        
        current_offset = offsets.get(game_name, 0)
        print(f"Search API: {game_name} | Tag: {tag_name} | Offset: {current_offset}")
        
        api_url = "https://www.deviantart.com/api/v1/oauth2/browse/tags"
        params = {
            "tag": tag_name,
            "offset": current_offset,
            "limit": 50,
            "mature_content": "true"
        }
        
        try:
            response = requests.get(api_url, headers=headers, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"API Error: Code {response.status_code} - {response.text}")
                continue
                
            data = response.json()
            results = data.get("results", [])
            
        except Exception as e:
            print(f"Network Error: {e}")
            continue
            
        if not results:
            print(f"End of archive reached for {game_name}")
            continue

        count = 0
        items_checked = 0 
        
        for item in results:
            items_checked += 1
            art_link = item.get("url")
            
            if not art_link or art_link in processed: 
                continue

            title = item.get("title", "No title")
            author_info = item.get("author", {})
            author = author_info.get("username", "Unknown author")
            
            image_url = None
            content = item.get("content")
            if content and "src" in content:
                image_url = content["src"]
            
            if not image_url:
                preview = item.get("preview")
                if preview and "src" in preview:
                    image_url = preview["src"]
                    
            if not image_url:
                print(f"Skip: no direct image for '{title}'")
                continue
                
            print(f"Sending to Telegram: {title}")
            caption = f"<b>{title}</b>\nAuthor: {author}\n\n<a href='{art_link}'>Original on DeviantArt</a>"
            
            if send_photo_to_telegram(image_url, caption):
                add_to_processed_list(art_link)
                count += 1
                
                if count >= POSTS_PER_GAME:
                    print(f"Collected {POSTS_PER_GAME} arts for {game_name}.")
                    break
                    
                print(f"Waiting {DELAY_SECONDS} sec...")
                time.sleep(DELAY_SECONDS)
        
        offsets[game_name] = current_offset + items_checked

    save_json(OFFSETS_FILE, offsets)

if __name__ == "__main__":
    main()
