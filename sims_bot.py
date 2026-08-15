import os
import time
import requests
import re
from bs4 import BeautifulSoup

TG_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

CATEGORY_URLS = [
    "https://sims4pack.ru/tags/cas-i-ekran-zagruzki/",
    "https://sims4pack.ru/tags/aksessuary/",
    "https://sims4pack.ru/tags/vnesnost/",
    "https://sims4pack.ru/tags/gameplay/",
    "https://sims4pack.ru/tags/interer/",
    "https://sims4pack.ru/tags/obuv/",
    "https://sims4pack.ru/tags/obustroistvo-dvora/",
    "https://sims4pack.ru/tags/odezda/",
    "https://sims4pack.ru/tags/persy/",
    "https://sims4pack.ru/tags/pitomcy-i-zivotnye/",
    "https://sims4pack.ru/tags/priceski/",
    "https://sims4pack.ru/tags/programmy/",
    "https://sims4pack.ru/tags/stroitelstvo/",
    "https://sims4pack.ru/tags/transport/",
    "https://sims4pack.ru/tags/uvleceniia-i-navyki/"
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
PROCESSED_FILE = "sims_processed.txt"

def get_processed():
    if not os.path.exists(PROCESSED_FILE): return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def mark_processed(mod_id):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(mod_id + "\n")

def send_to_telegram(title, img_url, file_path):
    caption = f"🔥 {title}"
    
    # 1. Скачиваем и отправляем картинку ЛОКАЛЬНО (обход защиты сайта)
    if img_url:
        req_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
        try:
            img_resp = requests.get(img_url, headers=HEADERS, stream=True)
            if img_resp.status_code == 200:
                with open("temp_img.jpg", 'wb') as f:
                    for chunk in img_resp.iter_content(1024):
                        f.write(chunk)
                with open("temp_img.jpg", 'rb') as f:
                    requests.post(req_url, data={"chat_id": TG_CHAT_ID, "caption": caption}, files={"photo": f})
                os.remove("temp_img.jpg")
                time.sleep(2)
        except Exception as e:
            print(f"Не удалось отправить фото: {e}")
            
    # 2. Отправляем сам файл мода
    if file_path and os.path.exists(file_path):
        url_doc = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
        try:
            with open(file_path, 'rb') as f:
                requests.post(url_doc, data={"chat_id": TG_CHAT_ID}, files={"document": f})
            os.remove(file_path)
        except Exception as e:
            print(f"Не удалось отправить файл: {e}")

def main():
    if not TG_TOKEN or not TG_CHAT_ID:
        print("Отсутствуют ключи Telegram!")
        return

    processed = get_processed()
    count = 0
    
    for category in CATEGORY_URLS:
        if count >= 10:
            break
            
        try:
            response = requests.get(category, headers=HEADERS)
            soup = BeautifulSoup(response.text, 'html.parser')
            mods = soup.find_all('a', href=True)
            
            for mod in mods:
                if count >= 10:
                    break
                    
                link = mod.get('href', '')
                
                # --- УМНАЯ СКЛЕЙКА ССЫЛОК ---
                # Если ссылка начинается с /, доклеиваем адрес сайта
                if link.startswith('/'):
                    link = f"https://sims4pack.ru{link}"
                
                if not link.startswith("https://sims4pack.ru/"):
                    continue
                
                if not re.search(r'/\d+-', link):
                    continue
                    
                if link in processed:
                    continue

                print(f"Обрабатываю мод: {link}")
                
                try:
                    mod_page = requests.get(link, headers=HEADERS)
                    mod_soup = BeautifulSoup(mod_page.text, 'html.parser')
                    
                    title_tag = mod_soup.find('h1')
                    title = title_tag.text.strip() if title_tag else "Мод для The Sims 4"
                    
                    img_url = None
                    
                    og_img = mod_soup.find('meta', property='og:image')
                    if og_img and og_img.get('content'):
                        img_url = og_img['content']
                    
                    if not img_url:
                        for img in mod_soup.find_all('img'):
                            src = img.get('src', '')
                            if 'uploads' in src.lower():
                                img_url = src
                                break
                                
                    if not img_url and title_tag and title_tag.parent:
                        fallback_img = title_tag.parent.find('img')
                        if fallback_img and fallback_img.get('src'):
                            img_url = fallback_img['src']
                            
                    if not img_url:
                        for img in mod_soup.find_all('img'):
                            src = img.get('src', '')
                            if src and not any(x in src.lower() for x in ['logo', 'icon', 'avatar', 'rating', 'stars']):
                                img_url = src
                                break

                    # Доклеиваем домен к картинке, если нужно
                    if img_url and img_url.startswith('/'):
                        img_url = f"https://sims4pack.ru{img_url}"

                    download_link = None
                    for a in mod_soup.find_all('a', href=True):
                        if 'download' in a.get('class', []) or 'Скачать' in a.text:
                            download_link = a.get('href', '')
                            break
                    
                    if download_link:
                        if download_link.startswith('/'):
                            download_link = f"https://sims4pack.ru{download_link}"
                        
                        file_response = requests.get(download_link, headers=HEADERS, stream=True)
                        
                        filename = "mod.package"
                        if "Content-Disposition" in file_response.headers:
                            filename = file_response.headers["Content-Disposition"].split("filename=")[-1].strip('"')
                        
                        with open(filename, 'wb') as f:
                            for chunk in file_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        send_to_telegram(title, img_url, filename)
                        mark_processed(link)
                        
                        count += 1
                        time.sleep(5) 
                        
                except Exception as e:
                    print(f"Ошибка при обработке {link}: {e}")
        except Exception as e:
            print(f"Ошибка доступа к разделу {category}: {e}")

if __name__ == "__main__":
    main()
