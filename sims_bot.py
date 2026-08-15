import os
import time
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

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
MAX_MODS_PER_RUN = 10
MAX_PAGES = 50

BLACKLIST = [
    '/tags/', '/popular', '/bookmarks', '/downloads', '/packs', 
    '/login', '/creators', '/user', '/rules', '/feedback', 
    '/registration', '/auth', '/search', '/engine', 'javascript:', '#',
    '/pdn', '/copyright', '/contacts', '/about', '/faq'
]

def get_processed():
    if not os.path.exists(PROCESSED_FILE): return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def mark_processed(mod_id):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(mod_id + "\n")

def send_to_telegram(title, img_url, file_path):
    caption = f"🔥 {title}"
    
    if img_url:
        req_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
        try:
            img_resp = requests.get(img_url, headers=HEADERS, stream=True, timeout=15)
            if img_resp.status_code == 200:
                with open("temp_img.jpg", 'wb') as f:
                    for chunk in img_resp.iter_content(1024):
                        f.write(chunk)
                with open("temp_img.jpg", 'rb') as f:
                    requests.post(req_url, data={"chat_id": TG_CHAT_ID, "caption": caption}, files={"photo": f}, timeout=20)
                if os.path.exists("temp_img.jpg"):
                    os.remove("temp_img.jpg")
                time.sleep(2)
        except Exception as e:
            print(f"Ошибка отправки фото: {e}", flush=True)
            
    if file_path and os.path.exists(file_path):
        url_doc = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
        try:
            with open(file_path, 'rb') as f:
                requests.post(url_doc, data={"chat_id": TG_CHAT_ID}, files={"document": f}, timeout=60)
            os.remove(file_path)
        except Exception as e:
            print(f"Ошибка отправки файла: {e}", flush=True)

def extract_image(soup):
    og = soup.find('meta', property='og:image')
    if og and og.get('content') and 'logo' not in og['content'].lower():
        return og['content']
        
    for img in soup.find_all('img'):
        for attr in ['data-src', 'data-original', 'data-lazy-src', 'src']:
            src = img.get(attr, '')
            if src and ('uploads' in src.lower() or 'post' in src.lower()):
                if not any(x in src.lower() for x in ['logo', 'icon', 'avatar', 'rating', 'stars', 'banner']):
                    return src
                    
    for a in soup.find_all('a', href=True):
        href = a['href']
        if any(href.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            if 'uploads' in href.lower():
                return href
    return None

def main():
    if not TG_TOKEN or not TG_CHAT_ID:
        print("Отсутствуют ключи Telegram!", flush=True)
        return

    processed = get_processed()
    count = 0
    
    for category in CATEGORY_URLS:
        if count >= MAX_MODS_PER_RUN:
            break
            
        current_page_url = category
        print(f"--- Раздел: {category} ---", flush=True)
        
        for page in range(1, MAX_PAGES + 1):
            if count >= MAX_MODS_PER_RUN:
                break
                
            try:
                resp = requests.get(current_page_url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    break
                    
                soup = BeautifulSoup(resp.text, 'html.parser')
                mod_links = []
                
                for a in soup.find_all('a', href=True):
                    href = a.get('href', '')
                    full_url = urljoin(current_page_url, href)
                        
                    if not full_url.startswith("https://sims4pack.ru/"):
                        continue
                        
                    if any(bad in full_url.lower() for bad in BLACKLIST):
                        continue
                        
                    # Жесткое правило: это должен быть мод! (в ссылке есть /mods/ или цифры)
                    if '/mods/' not in full_url.lower() and not re.search(r'/\d+-', full_url):
                        continue
                        
                    if full_url not in mod_links:
                        mod_links.append(full_url)
                
                # --- УМНЫЙ ПОИСК СЛЕДУЮЩЕЙ СТРАНИЦЫ ---
                next_page_url = None
                for a in soup.find_all('a', href=True):
                    text = a.text.strip()
                    if text == str(page + 1): # Ищет кнопку с цифрой следующей страницы
                        next_page_url = urljoin(resp.url, a.get('href'))
                        break
                
                if not next_page_url:
                    for a in soup.find_all('a', href=True):
                        text = a.text.strip().lower()
                        if 'вперед' in text or 'далее' in text or '»' in text:
                            next_page_url = urljoin(resp.url, a.get('href'))
                            break
                # --------------------------------------

                if mod_links:
                    for link in mod_links:
                        if count >= MAX_MODS_PER_RUN:
                            break
                        if link in processed:
                            continue

                        print(f"Скачиваю [Стр. {page}]: {link}", flush=True)
                        
                        try:
                            mod_resp = requests.get(link, headers=HEADERS, timeout=15)
                            if mod_resp.status_code != 200:
                                continue
                                
                            mod_soup = BeautifulSoup(mod_resp.text, 'html.parser')
                            
                            title_tag = mod_soup.find('h1')
                            title = title_tag.text.strip() if title_tag else "Мод для The Sims 4"
                            
                            img_url = extract_image(mod_soup)
                            if img_url:
                                img_url = urljoin(link, img_url)

                            download_link = None
                            for a in mod_soup.find_all('a', href=True):
                                href_a = a.get('href', '')
                                text_a = a.text.strip().lower()
                                classes_a = " ".join(a.get('class', [])).lower()
                                
                                full_dl = urljoin(link, href_a)
                                
                                if full_dl.rstrip('/').endswith('/downloads'):
                                    continue
                                    
                                if 'download' in classes_a or 'download' in href_a.lower() or 'скачать' in text_a:
                                    download_link = full_dl
                                    break
                            
                            if download_link:
                                file_resp = requests.get(download_link, headers=HEADERS, stream=True, timeout=30)
                                if file_resp.status_code == 200:
                                    
                                    content_type = file_resp.headers.get('Content-Type', '').lower()
                                    if 'text/html' in content_type:
                                        continue
                                    
                                    filename = "mod.package"
                                    if "Content-Disposition" in file_resp.headers:
                                        cd = file_resp.headers["Content-Disposition"]
                                        if "filename=" in cd:
                                            filename = cd.split("filename=")[-1].strip('"').strip("'")
                                    
                                    with open(filename, 'wb') as f:
                                        for chunk in file_resp.iter_content(chunk_size=8192):
                                            f.write(chunk)
                                    
                                    send_to_telegram(title, img_url, filename)
                                    mark_processed(link)
                                    processed.append(link)
                                    
                                    count += 1
                                    time.sleep(5)
                                    
                        except Exception as e:
                            print(f"Ошибка при обработке {link}: {e}", flush=True)
                
                # Если следующей страницы нет - выходим из цикла страниц
                if not next_page_url:
                    break
                    
                current_page_url = next_page_url
                        
            except Exception as e:
                print(f"Ошибка раздела {current_page_url}: {e}", flush=True)
                break

if __name__ == "__main__":
    main()
