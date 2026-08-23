import os
import time
import json
import requests
import urllib.parse
import re

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
TG_DA_BOT_TOKEN = os.environ.get("TG_DA_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
DA_CLIENT_ID = os.environ.get("DA_CLIENT_ID")
DA_CLIENT_SECRET = os.environ.get("DA_CLIENT_SECRET")

# --- ТВОИ ПРЯМЫЕ ССЫЛКИ НА ПОИСК ---
GAMES = {
    "Detroit become human": "https://www.deviantart.com/search?q=Detroit+become+human",
    "DBH": "https://www.deviantart.com/search?q=DBH",
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
    if response.status_code != 200:
        print(f"⚠️ Ошибка отправки в ТГ: {response.text}")
    return response.status_code == 200

def extract_query(search_url):
    try:
        query_part = search_url.split("q=")[1].split("&")[0]
        return urllib.parse.unquote_plus(query_part)
    except IndexError:
        return ""

def generate_tag(search_query):
    return re.sub(r'[^a-zA-Z0-9]', '', search_query).lower()

def get_image_url(item):
    # Умный поиск картинки: пробуем все варианты, включая комиксы
    if "content" in item and "src" in item["content"]:
        return item["content"]["src"]
    if "preview" in item and "src" in item["preview"]:
        return item["preview"]["src"]
    if "thumbs" in item and len(item["thumbs"]) > 0:
        return item["thumbs"][-1]["src"] # Берем самый крупный thumbnail
    return None

def main():
    if not DA_CLIENT_ID or not DA_CLIENT_SECRET:
        print("❌ Error: DA API keys not found in Secrets!")
        return

    token = get_da_token()
    if not token:
        print("❌ Ошибка авторизации в DeviantArt")
        return

    processed = get_processed_links()
    offsets = load_json(OFFSETS_FILE)
    headers = {"Authorization": f"Bearer {token}"}
    
    # API 1: Для свежих артов (строгая хронология по хэштегам)
    api_tags_url = "https://www.deviantart.com/api/v1/oauth2/browse/tags"
    # API 2: Для архива (умный текстовый поиск по самым популярным артам за всё время)
    api_popular_url = "https://www.deviantart.com/api/v1/oauth2/browse/popular"

    for game_name, search_url in GAMES.items():
        search_query = extract_query(search_url)
        tag_name = generate_tag(search_query)
        
        if not search_query:
            continue
            
        print(f"\n--- Обработка категории: {game_name} (Запрос: '{search_query}') ---")
        count = 0
        
        # --- ЭТАП 1: ПРОВЕРКА СВЕЖИХ АРТОВ (Хэштеги) ---
        print("🔍 Ищем свежие арты...")
        params_new = {"tag": tag_name, "offset": 0, "limit": 50, "mature_content": "true"}
        
        try:
            res_new = requests.get(api_tags_url, headers=headers, params=params_new, timeout=15)
            if res_new.status_code == 200:
                results_new = res_new.json().get("results", [])
                for item in results_new:
                    art_link = item.get("url")
                    if not art_link or art_link in processed: 
                        continue

                    image_url = get_image_url(item)
                    if not image_url:
                        continue
                        
                    title = item.get("title", "No title")
                    author = item.get("author", {}).get("username", "Unknown author")
                    
                    print(f"Новинка! Отправляем: {title}")
                    caption = f"<b>{title}</b>\nAuthor: {author}\n\n<a href='{art_link}'>Original on DeviantArt</a>"
                    
                    if send_photo_to_telegram(image_url, caption):
                        add_to_processed_list(art_link)
                        processed.append(art_link)
                        count += 1
                        time.sleep(DELAY_SECONDS)
                        if count >= POSTS_PER_GAME:
                            break
            else:
                print(f"❌ Ошибка API (новинки): {res_new.status_code}")
        except Exception as e:
            print(f"❌ Системная ошибка (новинки): {e}")

        # --- ЭТАП 2: УМНЫЙ ПОИСК ПО АРХИВУ (Популярное + Текст) ---
        pages_dug = 0
        while count < POSTS_PER_GAME and pages_dug < 5:
            current_offset = offsets.get(game_name, 0)
            if current_offset == 0:
                # Начинаем собирать сливки прямо с первой страницы популярного
                current_offset = 0 
                
            print(f"Не хватило {POSTS_PER_GAME - count} артов. Идем в популярный архив на позицию {current_offset}...")
            
            # Тот самый волшебный запрос, который имитирует строку поиска сайта!
            params_archive = {
                "q": search_query, 
                "offset": current_offset, 
                "limit": 50, 
                "mature_content": "true",
                "timerange": "alltime"
            }
            
            try:
                res_archive = requests.get(api_popular_url, headers=headers, params=params_archive, timeout=15)
                if res_archive.status_code == 200:
                    results_archive = res_archive.json().get("results", [])
                    if not results_archive:
                        print("Архив пуст, больше артов по этому запросу нет.")
                        break
                        
                    items_checked = 0
                    for item in results_archive:
                        items_checked += 1
                        art_link = item.get("url")
                        
                        if not art_link or art_link in processed: 
                            continue

                        image_url = get_image_url(item)
                        if not image_url:
                            continue
                            
                        title = item.get("title", "No title")
                        author = item.get("author", {}).get("username", "Unknown author")
                        
                        print(f"Из архива! Отправляем: {title}")
                        caption = f"<b>{title}</b>\nAuthor: {author}\n\n<a href='{art_link}'>Original on DeviantArt</a>"
                        
                        if send_photo_to_telegram(image_url, caption):
                            add_to_processed_list(art_link)
                            processed.append(art_link)
                            count += 1
                            time.sleep(DELAY_SECONDS)
                            if count >= POSTS_PER_GAME:
                                break
                                
                    offsets[game_name] = current_offset + items_checked
                else:
                    print(f"❌ Ошибка API (архив): Код {res_archive.status_code} - {res_archive.text}")
                    break
            except Exception as e:
                print(f"❌ Системная ошибка при поиске в архиве: {e}")
                break
                
            pages_dug += 1

    save_json(OFFSETS_FILE, offsets)

if __name__ == "__main__":
    main()
