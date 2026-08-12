import os
import time
import requests
from bs4 import BeautifulSoup

TG_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")

# Ссылка на нужный раздел (можно менять на прически, мебель и т.д.)
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
    # 1. Отправляем картинку с названием
    if img_url:
        caption = f"🔥 {title}"
        req_url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
        requests.post(req_url, data={"chat_id": TG_CHAT_ID, "photo": img_url, "caption": caption})
        time.sleep(2) # Пауза, чтобы сообщения не перемешались

    # 2. Отправляем сам файл
    if file_path and os.path.exists(file_path):
        url_doc = f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument"
        with open(file_path, 'rb') as f:
            requests.post(url_doc, data={"chat_id": TG_CHAT_ID}, files={"document": f})
        os.remove(file_path) # Удаляем файл с сервера GitHub, чтобы не засорять память

def main():
    if not TG_TOKEN or not TG_CHAT_ID:
        print("Отсутствуют ключи Telegram!")
        return

    processed = get_processed()
    response = requests.get(CATEGORY_URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Ищем блоки с модами (обычно на таких сайтах это теги article или div с классом item)
    mods = soup.find_all('a', href=True)
    
    count = 0
    for mod in mods:
        link = mod['href']
        
        # Фильтруем только ссылки на сами моды
        if not link.startswith("https://sims4pack.ru/") or link == CATEGORY_URL:
            continue
            
        if link in processed:
            continue

        print(f"Обрабатываю мод: {link}")
        
        try:
            # Заходим на страницу мода
            mod_page = requests.get(link, headers=HEADERS)
            mod_soup = BeautifulSoup(mod_page.text, 'html.parser')
            
            # Достаем название и картинку
            title_tag = mod_soup.find('h1')
            title = title_tag.text.strip() if title_tag else "Мод для The Sims 4"
            
            img_tag = mod_soup.find('img')
            img_url = img_tag['src'] if img_tag else None
            if img_url and not img_url.startswith('http'):
                img_url = f"https://sims4pack.ru{img_url}"

            # Ищем ссылку на скачивание файла (кнопка "Скачать")
            download_link = None
            for a in mod_soup.find_all('a', href=True):
                if 'download' in a.get('class', []) or 'Скачать' in a.text:
                    download_link = a['href']
                    break
            
            if download_link:
                if not download_link.startswith('http'):
                    download_link = f"https://sims4pack.ru{download_link}"
                
                # Скачиваем файл на сервер GitHub
                file_response = requests.get(download_link, headers=HEADERS, stream=True)
                
                # Пытаемся вытащить оригинальное название файла
                filename = "mod.package"
                if "Content-Disposition" in file_response.headers:
                    filename = file_response.headers["Content-Disposition"].split("filename=")[-1].strip('"')
                
                with open(filename, 'wb') as f:
                    for chunk in file_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Отправляем добро в Телеграм
                send_to_telegram(title, img_url, filename)
                mark_processed(link)
                
                count += 1
                if count >= 10: # Общий лимит за один запуск изменен на 10
                    break
                time.sleep(10)
                
        except Exception as e:
            print(f"Ошибка при обработке {link}: {e}")

if __name__ == "__main__":
    main()
