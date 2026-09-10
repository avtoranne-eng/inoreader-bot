import os
import time
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from deep_translator import GoogleTranslator

# Жестко прописанные ключи для AnnaModsBot (чтобы GitHub больше не путал ботов!)
TG_TOKEN = "8959400925:AAFbq64yiwvbickUdQbNg5NYe7RKH7up4oQ"
TG_CHAT_ID = "5277534829"

# Главная страница свежих модов на ModDB
CATEGORY_URLS = [
    "https://www.moddb.com/mods"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
}

PROCESSED_FILE = "moddb_processed.txt"
MAX_MODS_PER_RUN = 2  # Оптимально, чтобы не словить временный бан по IP
MAX_PAGES = 50000

def get_processed():
    if not os.path.exists(PROCESSED_FILE): 
        open(PROCESSED_FILE, 'w').close() 
        return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def mark_processed(mod_id):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(mod_id + "\n")

def clean_html(raw_html):
    if not raw_html: return "Описание отсутствует."
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator="\n").strip()
    return re.sub(r'\n\s*\n', '\n\n', text)

def translate_text(text):
    if not text or len(text) < 10: return text
    try:
        return GoogleTranslator(source='en', target='ru').translate(text[:4500])
    except Exception as e:
        print(f"Ошибка перевода: {e}", flush=True)
        return text

def send_to_telegram(game_name, title, img_url, txt_path, file_path, source_url, download_fallback_url):
    caption = f"🎮 <b>Игра: {game_name.upper()}</b>\n🔥 <b>{title}</b>\n\n📄 <i>Инструкция на русском в файле.</i>"

    # 1. Фото
    if img_url:
        req_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
        try:
            img_resp = requests.get(img_url, stream=True, headers=HEADERS, timeout=15)
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

    # 2. Инструкция (TXT)
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

    # 3. Файл мода
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

    # 4. Фоллбек (если файл слишком большой или его нет)
    if not file_sent:
        url_msg = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        links_text = (
            f"📦 <b>Архив превысил 50 МБ (лимит Telegram).</b>\n\n"
            f"📥 <a href='{download_fallback_url}'>Скачать со страницы загрузки</a>\n"
            f"🔗 <a href='{source_url}'>Оригинальная страница мода</a>"
        )
        try:
            requests.post(url_msg, data={"chat_id": TG_CHAT_ID, "text": links_text, "parse_mode": "HTML"}, timeout=15)
        except Exception as e:
            print(f"Ошибка отправки фоллбека: {e}", flush=True)

# Хитрый парсер для пробития зеркал скачивания ModDB
def extract_moddb_file(mod_url, safe_title):
    downloads_url = f"{mod_url}/downloads"
    try:
        # Идем во вкладку Downloads
        resp = requests.get(downloads_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Ищем первую ссылку на скачивание файла
        file_link = soup.find('a', href=re.compile(r'^/downloads/'))
        if not file_link:
            return None, downloads_url
            
        file_page_url = urljoin("https://www.moddb.com", file_link['href'])
        
        # Идем на страницу самого файла
        file_resp = requests.get(file_page_url, headers=HEADERS, timeout=15)
        file_soup = BeautifulSoup(file_resp.text, 'html.parser')
        
        # Ищем красную кнопку "DOWNLOAD NOW"
        dl_btn = file_soup.find('a', id='downloadbutton') or file_soup.find('a', href=re.compile(r'/downloads/start/'))
        if not dl_btn:
            return None, file_page_url
            
        start_url = urljoin("https://www.moddb.com", dl_btn['href'])
        
        # ModDB хитро редиректит на зеркало. Идем по ссылке с allow_redirects=True
        mirror_resp = requests.get(start_url, headers=HEADERS, allow_redirects=True, timeout=15)
        mirror_soup = BeautifulSoup(mirror_resp.text, 'html.parser')
        
        # На странице зеркала ищем финальную прямую ссылку на .zip/.rar/.7z
        direct_url = None
        for a in mirror_soup.find_all('a', href=True):
            if 'button.moddb.com/download' in a['href'] or any(ext in a['href'].lower() for ext in ['.zip', '.rar', '.7z', '.exe', '.pak']):
                direct_url = a['href']
                break
                
        if not direct_url:
            return None, file_page_url
            
        # Качаем файл!
        file_req = requests.get(direct_url, stream=True, headers=HEADERS, timeout=60)
        if file_req.status_code == 200:
            filename = f"{safe_title}.archive"
            if "Content-Disposition" in file_req.headers:
                cd = file_req.headers["Content-Disposition"]
                if "filename=" in cd:
                    filename = cd.split("filename=")[-1].strip('"').strip("'")
            else:
                # Пытаемся угадать расширение
                if '.zip' in direct_url: filename = f"{safe_title}.zip"
                elif '.rar' in direct_url: filename = f"{safe_title}.rar"
                elif '.7z' in direct_url: filename = f"{safe_title}.7z"
                
            with open(filename, 'wb') as f:
                for chunk in file_req.iter_content(8192):
                    f.write(chunk)
            return filename, file_page_url
            
    except Exception as e:
        print(f"Ошибка при поиске файла: {e}")
        
    return None, downloads_url

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
            
            # Навигация по страницам ModDB
            current_page_url = category if page == 1 else f"{category}/page/{page}"
            print(f"👀 Проверяю страницу {page}...", flush=True)

            try:
                resp = requests.get(current_page_url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')
                mod_links = []

                # Собираем ссылки на моды
                for a in soup.find_all('a', href=re.compile(r'^/mods/[^/]+$')):
                    if 'class' in a.attrs and 'image' in a['class']: 
                        continue # Пропускаем картинки, чтобы не дублировать ссылки
                    
                    full_url = urljoin("https://www.moddb.com", a['href'])
                    if full_url not in mod_links:
                        mod_links.append(full_url)

                if mod_links:
                    for link in mod_links:
                        if count >= MAX_MODS_PER_RUN:
                            break
                        
                        if link in processed:
                            continue

                        print(f"Обрабатываю мод: {link}", flush=True)

                        try:
                            # 1. Заходим на страницу мода
                            mod_resp = requests.get(link, headers=HEADERS, timeout=15)
                            mod_soup = BeautifulSoup(mod_resp.text, 'html.parser')
                            
                            # Вытягиваем название мода
                            title_meta = mod_soup.find('meta', property='og:title')
                            title = title_meta['content'].replace(' mod for', ' |').strip() if title_meta else "ModDB Mod"
                            
                            # Вытягиваем название игры (обычно в хлебных крошках)
                            game_name = "Unknown Game"
                            breadcrumbs = mod_soup.find('div', class_='breadcrumbs')
                            if breadcrumbs:
                                game_link = breadcrumbs.find('a', href=re.compile(r'^/games/'))
                                if game_link:
                                    game_name = game_link.text.strip()
                                    
                            # Описание
                            desc_meta = mod_soup.find('meta', property='og:description')
                            raw_desc = desc_meta['content'] if desc_meta else "Описание отсутствует."
                            translated_desc = translate_text(raw_desc)
                            
                            safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
                            txt_filename = f"Инструкция - {safe_title}.txt"
                            with open(txt_filename, "w", encoding="utf-8") as f:
                                f.write(translated_desc)
                                
                            # Картинка
                            img_meta = mod_soup.find('meta', property='og:image')
                            img_url = img_meta['content'] if img_meta else None
                            
                            # 2. Вытаскиваем сам файл через нашу функцию-парсер
                            file_path, download_fallback_url = extract_moddb_file(link, safe_title)
                            
                            # Отправляем в Телеграм
                            send_to_telegram(game_name, title, img_url, txt_filename, file_path, link, download_fallback_url)
                            
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
