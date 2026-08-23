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
    "Detroit become human deviations": "https://www.deviantart.com/search/deviations?q=detroit+become+human",
    "DBH": "https://www.deviantart.com/search?q=DBH",
    "Detroit: become human": "https://www.deviantart.com/search?q=Detroit%3A+become+human",
    "Resident evil": "https://www.deviantart.com/search?q=Resident+evil"
}

OFFSETS_FILE = "offsets.json"
PROCESSED_FILE = "processed_arts.txt"
POSTS_PER_GAME = 10   
DELAY_SECONDS = 15   

def get_da_token():
    url = "https://www.deviantart.com/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": DA_CLIENT_ID,
        "client_secret": DA_CLIENT_SECRET
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
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
        return False
        
    url = f"https://api.telegram.org/bot{TG_DA_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": TG_CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    
    response = requests.post(url, data=data)
    return response.status_code == 200

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
    api_url = "https://www.deviantart.com/api/v1/oauth2/browse/tags"

    for game_name, search_url in GAMES.items():
        query_part = search_url.split("q=")[1]
        tag_name = query_part.replace("+", "").lower()
        print(f"\n--- Обработка категории: {game_name} ---")
        
        count = 0
        
        # --- ЭТАП 1: ПРОВЕРКА НОВИНОК (offset = 0) ---
        print("🔍 Ищем свежие арты...")
        params_new = {"tag": tag_name, "offset": 0, "limit": 50, "mature_content": "true"}
        
        try:
            res_new = requests.get(api_url, headers=headers, params=params_new, timeout=15)
            if res_new.status_code == 200:
                results_new = res_new.json().get("results", [])
                
                for item in results_new:
                    art_link = item.get("url")
                    if not art_link or art_link in processed: 
                        continue

                    title = item.get("title", "No title")
                    author = item.get("author", {}).get("username", "Unknown author")
                    
                    image_url = None
                    if "content" in item and "src" in item["content"]:
                        image_url = item["content"]["src"]
                    elif "preview" in item and "src" in item["preview"]:
                        image_url = item["preview"]["src"]
                        
                    if not image_url:
                        continue
                        
                    print(f"Новинка! Отправляем: {title}")
                    caption = f"<b>{title}</b>\nAuthor: {author}\n\n<a href='{art_link}'>Original on DeviantArt</a>"
                    
                    if send_photo_to_telegram(image_url, caption):
                        add_to_processed_list(art_link)
                        count += 1
                        time.sleep(DELAY_SECONDS)
                        
                        if count >= POSTS_PER_GAME:
                            break
        except Exception as e:
            print(f"Ошибка при поиске новинок: {e}")

        # --- ЭТАП 2: КОПАЕМ АРХИВ, ЕСЛИ НОВИНОК НЕ ХВАТИЛО ---
        if count < POSTS_PER_GAME:
            current_offset = offsets.get(game_name, 0)
            if current_offset == 0:
                current_offset = 50 # Если мы только что смотрели 0, сдвигаемся
                
            print(f"Не хватило {POSTS_PER_GAME - count} артов. Идем в архив на позицию {current_offset}...")
            params_archive = {"tag": tag_name, "offset": current_offset, "limit": 50, "mature_content": "true"}
            
            try:
                res_archive = requests.get(api_url, headers=headers, params=params_archive, timeout=15)
                if res_archive.status_code == 200:
                    results_archive = res_archive.json().get("results", [])
                    items_checked = 0
                    
                    for item in results_archive:
                        items_checked += 1
                        art_link = item.get("url")
                        
                        if not art_link or art_link in processed: 
                            continue

                        title = item.get("title", "No title")
                        author = item.get("author", {}).get("username", "Unknown author")
                        
                        image_url = None
                        if "content" in item and "src" in item["content"]:
                            image_url = item["content"]["src"]
                        elif "preview" in item and "src" in item["preview"]:
                            image_url = item["preview"]["src"]
                            
                        if not image_url:
                            continue
                            
                        print(f"Из архива! Отправляем: {title}")
                        caption = f"<b>{title}</b>\nAuthor: {author}\n\n<a href='{art_link}'>Original on DeviantArt</a>"
                        
                        if send_photo_to_telegram(image_url, caption):
                            add_to_processed_list(art_link)
                            count += 1
                            time.sleep(DELAY_SECONDS)
                            
                            if count >= POSTS_PER_GAME:
                                break
                                
                    # Сохраняем сдвиг только если реально ходили в архив
                    offsets[game_name] = current_offset + items_checked
            except Exception as e:
                print(f"Ошибка при поиске в архиве: {e}")

    save_json(OFFSETS_FILE, offsets)

if __name__ == "__main__":
    main()
