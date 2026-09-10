import os
import time
import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from deep_translator import GoogleTranslator

TG_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
NEXUS_API_KEY = os.environ.get("NEXUS_API_KEY")

CATEGORY_URLS = [
    "https://www.nexusmods.com/mods"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'apikey': NEXUS_API_KEY
}

PROCESSED_FILE = "nexus_processed.txt"
MAX_MODS_PER_RUN = 5
MAX_PAGES = 50000

BLACKLIST = [
    '/users/', '/about/', '/games/', '/news/', '/forum/', 
    '/support/', 'javascript:', '#'
]

def get_processed():
    if not os.path.exists(PROCESSED_FILE): 
        # Создаем пустой файл, чтобы GitHub Actions не падал с ошибкой
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
        print(f"Ошибка перевода: {e}")
        return text

def send_to_telegram(game_name, title, version, img_url, txt_path, file_path, source_url):
    caption = f"🎮 <b>Игра: {game_name.upper()}</b>\n🔥 <b>{title} (v.{version})</b>\n\n📄 <i>Инструкция на русском в файле.</i>"

    # 1. Фото
    if img_url:
        req_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
        try:
            img_resp = requests.get(img_url, stream=True, timeout=15)
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
            print(f"Ошибка отправки фото: {e}")

    # 2. Инструкция (TXT)
    if txt_path and os.path.exists(txt_path):
        url_doc = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
        try:
            with open(txt_path, 'rb') as f:
                requests.post(url_doc, data={"chat_id": TG_CHAT_ID}, files={"document": f}, timeout=30)
        except Exception as e:
            print(f"Ошибка отправки инструкции: {e}")
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
                print(f"Ошибка отправки файла: {e}")
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)

    # 4. Если скачивание не удалось или файл огромный
    if not file_sent:
        url_msg = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        links_text = (
            f"📦 <b>Файл превысил лимит 50 МБ или недоступен для автоскачивания.</b>\n\n"
            f"🔗 <a href='{source_url}?tab=files'>Скачать вручную со страницы мода</a>"
        )
        try:
            requests.post(url_msg, data={"chat_id": TG_CHAT_ID, "text": links_text, "parse_mode": "HTML"}, timeout=15)
        except Exception as e:
            print(f"Ошибка отправки фоллбека: {e}")

def main():
    if not TG_TOKEN or not TG_CHAT_ID or not NEXUS_API_KEY:
        print("Отсутствуют ключи Telegram или Nexus API!")
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
            
            print(f"👀 Проверяю страницу {page}...", flush=True)

            try:
                # Парсим общую страницу Нексуса как обычный сайт
                resp = requests.get(current_page_url, headers={'User-Agent': HEADERS['User-Agent']}, timeout=15)
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')
                mod_links = []

                for a in soup.find_all('a', href=True):
                    full_url = urljoin(current_page_url, a.get('href', ''))
                    
                    if not full_url.startswith("https://www.nexusmods.com/"):
                        continue
                    if any(bad in full_url.lower() for bad in BLACKLIST):
                        continue
                        
                    # Вытаскиваем игру и ID мода из ссылки
                    match = re.match(r'https://www\.nexusmods\.com/([^/]+)/mods/(\d+)', full_url.split('?')[0])
                    if match:
                        clean_url = full_url.split('?')[0]
                        if clean_url not in mod_links:
                            mod_links.append((clean_url, match.group(1), match.group(2)))

                # Поиск следующей страницы
                next_page_url = None
                for a in soup.find_all('a', href=True):
                    text = a.text.strip()
                    if text == str(page + 1) or 'next' in text.lower() or '»' in text: 
                        next_page_url = urljoin(resp.url, a.get('href'))
                        break

                if mod_links:
                    for link_data in mod_links:
                        if count >= MAX_MODS_PER_RUN:
                            break
                            
                        clean_url, game_domain, mod_id = link_data
                        process_id = f"{game_domain}_{mod_id}"
                        
                        if process_id in processed:
                            continue

                        print(f"Обрабатываю: {game_domain} - мод {mod_id}", flush=True)

                        try:
                            # 1. Запрашиваем инфу о моде через API Нексуса
                            mod_detail_url = f"https://api.nexusmods.com/v1/games/{game_domain}/mods/{mod_id}.json"
                            detail_resp = requests.get(mod_detail_url, headers=HEADERS)
                            if detail_resp.status_code != 200:
                                continue
                                
                            mod_data = detail_resp.json()
                            title = mod_data.get('name', 'Mod')
                            version = mod_data.get('version', '1.0')
                            picture_url = mod_data.get('picture_url')
                            
                            # Перевод инструкции
                            raw_desc = mod_data.get('description', '')
                            clean_desc = clean_html(raw_desc)
                            translated_desc = translate_text(clean_desc)
                            
                            safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
                            txt_filename = f"Инструкция - {safe_title}.txt"
                            with open(txt_filename, "w", encoding="utf-8") as f:
                                f.write(translated_desc)
                                
                            # 2. Пытаемся забрать файл через API
                            files_url = f"https://api.nexusmods.com/v1/games/{game_domain}/mods/{mod_id}/files.json"
                            files_resp = requests.get(files_url, headers=HEADERS)
                            file_path = None
                            
                            if files_resp.status_code == 200:
                                files_data = files_resp.json().get('files', [])
                                if files_data:
                                    main_file = next((f for f in files_data if f['category_id'] == 1), files_data[0])
                                    file_id = main_file['file_id']
                                    file_name = main_file.get('file_name', f"{safe_title}.zip")
                                    
                                    dl_link_url = f"https://api.nexusmods.com/v1/games/{game_domain}/mods/{mod_id}/files/{file_id}/download_link.json"
                                    dl_resp = requests.get(dl_link_url, headers=HEADERS)
                                    
                                    if dl_resp.status_code == 200:
                                        links = dl_resp.json()
                                        if links:
                                            direct_url = links[0]['URI']
                                            file_req = requests.get(direct_url, stream=True, timeout=60)
                                            if file_req.status_code == 200:
                                                file_path = file_name
                                                with open(file_path, 'wb') as f:
                                                    for chunk in file_req.iter_content(8192):
                                                        f.write(chunk)

                            # Отправляем в Телеграм
                            send_to_telegram(game_domain, title, version, picture_url, txt_filename, file_path, clean_url)
                            
                            mark_processed(process_id)
                            processed.append(process_id)
                            count += 1
                            time.sleep(5) 
                            
                        except Exception as e:
                            print(f"Ошибка при обработке {clean_url}: {e}", flush=True)

                if not next_page_url:
                    break

                current_page_url = next_page_url

            except Exception as e:
                print(f"Ошибка раздела {current_page_url}: {e}", flush=True)
                break

if __name__ == "__main__":
    main()
