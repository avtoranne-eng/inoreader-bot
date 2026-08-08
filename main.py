import os
import time
import json
import io
import feedparser
from google import genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

def get_processed_titles(drive_service):
    # Ищем файл processed.txt в нашей папке
    query = f"name = 'processed.txt' and '{FOLDER_ID}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields='files(id)').execute()
    files = results.get('files', [])
    
    if not files:
        return [] # Файла еще нет, список пуст
    
    file_id = files[0]['id']
    content = drive_service.files().get_media(fileId=file_id).execute().decode('utf-8')
    return content.splitlines()

def add_to_processed_list(drive_service, title):
    # Ищем файл, чтобы получить его ID
    query = f"name = 'processed.txt' and '{FOLDER_ID}' in parents and trashed = false"
    results = drive_service.files().list(q=query, fields='files(id)').execute()
    files = results.get('files', [])
    
    # Если файла нет — создаем его
    if not files:
        file_metadata = {'name': 'processed.txt', 'parents': [FOLDER_ID]}
        file = drive_service.files().create(body=file_metadata, media_body=io.BytesIO(title.encode('utf-8'))).execute()
    else:
        file_id = files[0]['id']
        # Читаем старый контент
        old_content = drive_service.files().get_media(fileId=file_id).execute().decode('utf-8')
        new_content = old_content + "\n" + title
        # Обновляем файл
        drive_service.files().update(fileId=file_id, media_body=io.BytesIO(new_content.encode('utf-8'))).execute()

# 1. Подключаемся к Gemini
API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# 2. Настройки Google Drive
CREDS_JSON = os.environ.get("GDRIVE_CREDENTIALS")
FOLDER_ID = "1qclCDO_KL7io9tbYMqsSWrlOKn6aqA59"

# 3. ВСТАВЬ СВОЮ ССЫЛКУ ИЗ INOREADER МЕЖДУ КАВЫЧКАМИ НИЖЕ:
RSS_URL = "https://www.inoreader.com/stream/user/1003745790/tag/user-favorites"

def authenticate_google():
    creds_json = os.environ.get("GDRIVE_CREDENTIALS")
    
    if not creds_json:
        print("КРИТИЧЕСКАЯ ОШИБКА: Переменная GDRIVE_CREDENTIALS не передана в код!")
        return None, None
    
    # Проверка структуры JSON (не выводим данные, просто проверяем длину)
    print(f"Секрет получен, длина JSON: {len(creds_json)} символов.")
    
    try:
        creds_info = json.loads(creds_json)
        scopes = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
        
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        print("Аутентификация успешно создана.")
        return drive_service, docs_service
    except Exception as e:
        print(f"Ошибка парсинга JSON или создания сервиса: {e}")
        return None, None

def create_google_doc(drive_service, docs_service, title, content):
    # Создаем пустой документ
    file_metadata = {
        'name': title,
        'mimeType': 'application/vnd.google-apps.document',
        'parents': [FOLDER_ID]
    }
    doc = drive_service.files().create(body=file_metadata, fields='id').execute()
    doc_id = doc.get('id')
    
    # Записываем сгенерированный текст в документ
def check_file_exists(drive_service, title):
    # Сначала безопасно обрабатываем заголовок
    safe_title = title.replace("'", "\\'")
    # А потом спокойно вставляем в запрос
    query = f"name = '{safe_title}' and '{FOLDER_ID}' in parents and trashed = false"
    
    results = drive_service.files().list(q=query, fields='files(id, name)').execute()
    return len(results.get('files', [])) > 0

def main():
    print("Запуск конвейера новостей...")
    
    drive_service, docs_service = authenticate_google()
    if not drive_service: return
        
    feed = feedparser.parse(RSS_URL)
    if not feed.entries: return

    # Получаем список того, что уже было сделано
    processed_titles = get_processed_titles(drive_service)
    
    print(f"Найдено новостей в RSS: {len(feed.entries)}")
    
    count = 0

    for article in feed.entries:
        title = article.title
        
        if count >= 3: break # За 1 запуск обрабатываем не более 3х новостей, чтобы не спамить
        
        if check_file_exists(drive_service, title):
            print(f"Пропускаю (уже было): {title}")
            continue
            
        print(f"Обрабатываю: {title}")
        prompt = f"Твоя роль: экспертный игровой журналист и контент-мейкер. Задача: Напиши максимально развернутый, глубокий и подробный лонгрид для ВКонтакте, детально анализируя каждый аспект новости. Правила: - Придумай мощный SEO-заголовок под конкретные поисковые запросы геймеров. - Поскольку стандартное разделение на абзацы и жирный шрифт недоступны, активно и структурированно используй эмодзи для визуального разделения логических блоков, списков и выделения важных мыслей. Эмодзи — твой единственный инструмент форматирования текста. - Текст должен быть без воды, написан живым языком. - В самом конце текста, с новой строки, обязательно напиши 7-8 релевантных хештега для ВК. Первым и обязательным всегда должен стоять тег #LevelupNews. Новость: {title}. Текст: {article.get('description', '')}"
        
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=prompt
            )
            create_google_doc(drive_service, docs_service, article.title, response.text)
            
            # Записываем в лог, что успешно обработали
            add_to_processed_list(drive_service, article.title)
            
            count += 1
            time.sleep(15) 
        except Exception as e:
            print(f"Ошибка при обработке {article.title}: {e}")
            if "429" in str(e): break

    print("Все новости успешно обработаны!")

if __name__ == "__main__":
    main()
