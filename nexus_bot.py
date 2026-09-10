import os
import time
import requests
import re
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

TG_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
NEXUS_API_KEY = os.environ.get("NEXUS_API_KEY")

# Список игр (берется из ссылки, например nexusmods.com/residentevil42023)
# Можешь добавлять сюда любые игры!
GAMES = [
    "residentevil42023", 
    "dragonageinquisition", 
    "detroitbecomehuman", 
    "neverwinter",
    "skyrimspecialedition", 
    "skyrim",
    "oblivion",
    "witcher2",
    "witcher",
    "fallout3",
    "starfield",
    "mountandblade2bannerlord",
    "morrowind",
    "monsterhunterworld",
    "bladeandsorcery",
    "dragonage",
    "dragonage2",
    "reddeadredemption2",
    "stellarblade",
    "eldenring",
    "oblivionremastered",
    "neverwinter2",
    "masseffectlegendaryedition",
    "masseffect",
    "masseffect2",
    "masseffect3",
    "starwarsbattlefront22017",
    "kingdomcomedeliverance",
    "residentevil22019",
    "stalker2heartofchornobyl",
    "hogwartslegacy",
    "sekiro",
    "residentevil32020",
    "devilmaycry5",
    "dragonsdogma2",
    "residentevilrequiem",
    "darksouls",
    "crimsondesert",
    "masseffectandromeda",
    "fallout76",
    "supermarketsimulator",
    "darksoulsremastered",
    "blackmythwukong",
    "residentevilvillage",
    "darksouls2",
    "gta4",
    "inzoi",
    "gta5",
    "dragonagetheveilguard",
    "wuchangfallenfeathers",
    "citiesskylines",
    "citiesskylines2",
    "fallout4",
    "newvegas",
    "cyberpunk2077", 
    "stardewvalley", 
    "baldursgate3",
    "witcher3"
]

HEADERS = {
    'accept': 'application/json',
    'apikey': NEXUS_API_KEY
}

PROCESSED_FILE = "nexus_processed.txt"
MAX_MODS_PER_RUN = 10 # Лимит за 1 запуск, чтобы не злить API

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

    # 4. Если скачать через API не удалось (нет Premium) или файл большой
    if not file_sent:
        url_msg = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        links_text = (
            f"📦 <b>Файл не загружен (превышен лимит ТГ или требуется Premium на Nexus).</b>\n\n"
            f"🔗 <a href='{source_url}?tab=files'>Скачать вручную со страницы мода</a>"
        )
        try:
            requests.post(url_msg, data={"chat_id": TG_CHAT_ID, "text": links_text, "parse_mode": "HTML"}, timeout=15)
        except Exception as e:
            print(f"Ошибка отправки фоллбека: {e}", flush=True)

def main():
    if not TG_TOKEN or not NEXUS_API_KEY:
        print("Отсутствуют ключи API!", flush=True)
        return

    processed = get_processed()
    count = 0

    for game in GAMES:
        if count >= MAX_MODS_PER_RUN:
            break
            
        print(f"\n--- Проверяю новинки: {game} ---", flush=True)
        
        # Запрашиваем 10 последних модов для конкретной игры
        api_url = f"https://api.nexusmods.com/v1/games/{game}/mods/latest_added.json"
        
        try:
            resp = requests.get(api_url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"API не отдал {game}. Код: {resp.status_code}", flush=True)
                continue
                
            mods = resp.json()
            
            for mod in mods:
                if count >= MAX_MODS_PER_RUN:
                    break
                    
                mod_id = str(mod['mod_id'])
                process_id = f"{game}_{mod_id}"
                
                if process_id in processed:
                    continue
                    
                print(f"Обрабатываю: {game} - {mod['name']}", flush=True)
                
                try:
                    # 1. Получаем полные данные о моде
                    detail_url = f"https://api.nexusmods.com/v1/games/{game}/mods/{mod_id}.json"
                    detail_resp = requests.get(detail_url, headers=HEADERS, timeout=15)
                    if detail_resp.status_code != 200:
                        continue
                        
                    mod_data = detail_resp.json()
                    title = mod_data.get('name', 'Mod')
                    version = mod_data.get('version', '1.0')
                    picture_url = mod_data.get('picture_url')
                    source_url = f"https://www.nexusmods.com/{game}/mods/{mod_id}"
                    
                    # Создаем txt-инструкцию с переводом
                    raw_desc = mod_data.get('description', '')
                    clean_desc = clean_html(raw_desc)
                    translated_desc = translate_text(clean_desc)
                    
                    safe_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
                    txt_filename = f"Инструкция - {safe_title}.txt"
                    with open(txt_filename, "w", encoding="utf-8") as f:
                        f.write(translated_desc)
                        
                    # 2. Ищем файл для скачивания
                    files_url = f"https://api.nexusmods.com/v1/games/{game}/mods/{mod_id}/files.json"
                    files_resp = requests.get(files_url, headers=HEADERS, timeout=15)
                    file_path = None
                    
                    if files_resp.status_code == 200:
                        files_data = files_resp.json().get('files', [])
                        if files_data:
                            main_file = next((f for f in files_data if f['category_id'] == 1), files_data[0])
                            file_id = main_file['file_id']
                            file_name = main_file.get('file_name', f"{safe_title}.zip")
                            
                            # Пробуем достать прямую ссылку
                            dl_link_url = f"https://api.nexusmods.com/v1/games/{game}/mods/{mod_id}/files/{file_id}/download_link.json"
                            dl_resp = requests.get(dl_link_url, headers=HEADERS, timeout=15)
                            
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

                    # Отправляем весь пакет в ТГ
                    send_to_telegram(game, title, version, picture_url, txt_filename, file_path, source_url)
                    
                    mark_processed(process_id)
                    processed.append(process_id)
                    count += 1
                    
                    time.sleep(3) # Пауза, чтобы сервер Нексуса не злился
                    
                except Exception as e:
                    print(f"Ошибка при сборе мода {mod_id}: {e}", flush=True)
                    
        except Exception as e:
            print(f"Ошибка игры {game}: {e}", flush=True)

if __name__ == "__main__":
    main()
