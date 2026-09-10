import os
import time
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from deep_translator import GoogleTranslator

# Ключи для AnnaModsBot
TG_TOKEN = "TG_MODS_BOT_TOKEN"
TG_CHAT_ID = "TG_CHAT_ID"

CATEGORY_URLS = [
    "https://modgames.net/load/"
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
PROCESSED_FILE = "modgames_processed.txt"
MAX_MODS_PER_RUN = 2
MAX_PAGES = 50000

BLACKLIST = [
    '/tags/', '/search/', '/panel/', '/index/', '/register/', 
    '/faq/', '/rules/', '/user/', '/forum/', 'javascript:', '#'
]

def get_processed():
    if not os.path.exists(PROCESSED_FILE): 
        open(PROCESSED_FILE, 'w').close() 
        return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def mark_processed(mod_id):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(mod_id + "\n")

def translate_text(text):
    if not text or len(text) < 10: return text
    try:
        return GoogleTranslator(source='auto', target='ru').translate(text[:4500])
    except:
        return text

def send_to_telegram(game_name, title, img_url, txt_path, file_path, source_url, download_url):
    caption = f"🎮 <b>Игра: {game_name.upper()}</b>\n🔥 <b>{title}</b>\n\n📄 <i>Инструкция в файле.</i>"

    if img_url:
        req_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
        try:
            img_resp = requests.get(img_url, headers=HEADERS, stream=True, timeout=15)
            if img_resp.status_code == 200:
                with open("temp_img.jpg", 'wb') as f:
                    for chunk in img_resp.iter_content(1024):
                        f.write(chunk)
                with open("temp_img.jpg", 'rb') as f:
                    requests.post(req_url, data={"chat_id": TG_CHAT_ID, "caption": caption, "parse_mode": "HTML"}, files={"photo": f}, timeout=20)
                if os.path.exists("temp_img.jpg"):
                    os.remove("temp_img.jpg")
                time.sleep(2)
        except Exception as e:
            print(f"Ошибка отправки фото: {e}", flush=True)

    if txt_path and os.path.exists(txt_path):
        url_doc = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
        try:
            with open(txt_path, 'rb') as f:
                requests.post(url_doc, data={"chat_id": TG_CHAT_ID}, files={"document": f}, timeout=30)
        except Exception as e:
            print(f"Ошибка отправки инструкции: {e}", flush=True)
        finally:
            if os.path.exists(txt_path):
                os.remove(txt_path)
        time.sleep(2)

    file_sent = False
    if file_path and os.path.exists(file_path):
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb < 49:
            url_doc = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
            try:
                with open(file_path, 'rb') as f:
                    doc_resp = requests.post(url_doc, data={"chat_id": TG_CHAT_ID}, files={"document": f}, timeout=300)
                if doc_resp.status_code == 200 and doc_resp.json().get("ok"):
                    file_sent = True
            except Exception as e:
                print(f"Ошибка отправки файла: {e}", flush=True)
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)

    if not file_sent:
        url_msg = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        links_text = (
            f"📦 <b>Архив превысил 50 МБ (лимит Telegram).</b>\n\n"
            f"📥 <a href='{download_url}'>Скачать по прямой ссылке</a>\n"
            f"🔗 <a href='{source_url}'>Оригинальная страница мода</a>"
        )
        try:
            requests.post(url_msg, data={"chat_id": TG_CHAT_ID, "text": links_text, "parse_mode": "HTML"}, timeout=15)
        except Exception as e:
            print(f"Ошибка отправки фоллбека: {e}", flush=True)

def main():
    processed = get_processed()
    count = 0

    for category in CATEGORY_URLS:
        if count >= MAX_MODS_PER_RUN:
            break

        print(f"--- Раздел: {category} ---", flush=True)

        for page in range(1, MAX_PAGES + 1):
            if count >= MAX_MODS_PER_RUN:
                break
            
            current_page_url = category if page == 1 else f"{category}?page{page}"
            print(f"👀 Проверяю страницу {page}...", flush=True)

            try:
                resp = requests.get(current_page_url, headers=HEADERS, timeout=15)
                print(f"Ответ сайта: {resp.status_code}", flush=True)
                
                if resp.status_code != 200:
                    print("Сайт недоступен или блокирует запросы.", flush=True)
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')
                mod_links = []

                for a in soup.find_all('a', href=True):
                    full_url = urljoin(current_page_url, a.get('href', ''))
                    
                    if not full_url.startswith("https://modgames.net/load/"):
                        continue
                    if any(bad in full_url.lower() for bad in BLACKLIST):
                        continue
                    
                    if re.search(r'\d+$', full_url) and full_url not in mod_links:
                        mod_links.append(full_url)

                if mod_links:
                    for link in mod_links:
                        if count >= MAX_MODS_PER_RUN:
                            break
                        
                        if link in processed:
                            continue

                        print(f"Обрабатываю мод: {link}", flush=True)

                        try:
                            mod_resp = requests.get(link, headers=HEADERS, timeout=15)
                            mod_soup = BeautifulSoup(mod_resp.text, 'html.parser')
                            
                            title_tag = mod_soup.find('h1')
                            title = title_tag.text.strip() if title_tag else "ModGames Mod"
                            
                            game_name = "ИГРА НЕ ОПРЕДЕЛЕНА"
                            breadcrumbs = mod_soup.find('div', class_='eTitle')
                            if not breadcrumbs:
                                breadcrumbs = mod_soup.find('span', class_='cats')
                            
                            if breadcrumbs:
                                links_in_bc = breadcrumbs.find_all('a')
                                if len(links_in_bc) > 1:
                                    game_name = links_in_bc[1].text.strip()
                                elif len(links_in_bc) == 1:
                                    game_name = links_in_bc[0].text.strip()

                            desc_div = mod_soup.find('div', class_=re.compile(r'eMessage|eText'))
                            raw_desc = desc_div.text.strip() if desc_div else "Описание отсутствует."
                            translated_desc = translate_text(raw_desc)
                            
                            safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
                            txt_filename = f"Инструкция - {safe_title}.txt"
                            with open(txt_filename, "w", encoding="utf-8") as f:
                                f.write(translated_desc)
                                
                            img_url = None
                            img_tag = mod_soup.find('img', class_='eMessageImg')
                            if img_tag and 'src' in img_tag.attrs:
                                img_url = urljoin(link, img_tag['src'])
                            else:
                                for img in mod_soup.find_all('img'):
                                    src = img.get('src', '')
                                    if '/uploads/' in src.lower() and not 'logo' in src.lower():
                                        img_url = urljoin(link, src)
                                        break
                            
                            download_link = None
                            for a in mod_soup.find_all('a', href=True):
                                text_a = a.text.strip().lower()
                                if 'скачать' in text_a or 'download' in text_a or '/go?' in a['href']:
                                    download_link = urljoin(link, a['href'])
                                    break
                                    
                            file_path = None
                            if download_link:
                                file_resp = requests.get(download_link, headers=HEADERS, stream=True, timeout=30)
                                if file_resp.status_code == 200:
                                    content_type = file_resp.headers.get('Content-Type', '').lower()
                                    if 'text/html' not in content_type:
                                        filename = f"{safe_title}.archive"
                                        if "Content-Disposition" in file_resp.headers:
                                            cd = file_resp.headers["Content-Disposition"]
                                            if "filename=" in cd:
                                                filename = cd.split("filename=")[-1].strip('"').strip("'")
                                        else:
                                            if '.7z' in download_link: filename = f"{safe_title}.7z"
                                            elif '.rar' in download_link: filename = f"{safe_title}.rar"
                                            elif '.zip' in download_link: filename = f"{safe_title}.zip"
                                            
                                        file_path = filename
                                        with open(filename, 'wb') as f:
                                            for chunk in file_resp.iter_content(8192):
                                                f.write(chunk)
                            
                            send_to_telegram(game_name, title, img_url, txt_filename, file_path, link, download_link)
                            
                            mark_processed(link)
                            processed.append(link)
                            count += 1
                            time.sleep(5) 
                            
                        except Exception as e:
                            print(f"Ошибка при обработке {link}: {e}", flush=True)

            except Exception as e:
                print(f"Ошибка раздела {current_page_url}: {e}", flush=True)
                break

if __name__ == "__main__":
    main()
