import os
import time
import json
import feedparser
from google import genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

# 1. Подключаемся к Gemini
API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# 2. Настройки Google Drive
CREDS_JSON = os.environ.get("GDRIVE_CREDENTIALS")
FOLDER_ID = "1qclCDO_KL7io9tbYMqsSWrlOKn6aqA59"

# 3. ВСТАВЬ СВОЮ ССЫЛКУ ИЗ INOREADER МЕЖДУ КАВЫЧКАМИ НИЖЕ:
RSS_URL = "https://www.inoreader.com/stream/user/1003745790/tag/user-favorites"

# 4. Наш жесткий системный промпт (инструкция)
SYSTEM_PROMPT = """
Твоя роль: экспертный игровой журналист и контент-мейкер.
Задача: Напиши максимально развернутый, глубокий и подробный лонгрид для ВКонтакте, детально анализируя каждый аспект новости.
Правила:
- Придумай мощный SEO-заголовок под конкретные поисковые запросы геймеров.
- Поскольку стандартное разделение на абзацы и жирный шрифт недоступны, активно и структурированно используй эмодзи для визуального разделения логических блоков, списков и выделения важных мыслей. Эмодзи — твой единственный инструмент форматирования текста.
- Текст должен быть без воды, написан живым языком.
- В самом конце текста, с новой строки, обязательно напиши 7-8 релевантных хештега для ВК. Первым и обязательным всегда должен стоять тег #LevelupNews.
"""

def authenticate_google():
    if not CREDS_JSON:
        print("Ошибка: Секрет GDRIVE_CREDENTIALS не найден!")
        return None, None
        
    creds_info = json.loads(CREDS_JSON)
    scopes = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
    
    drive_service = build('drive', 'v3', credentials=creds)
    docs_service = build('docs', 'v1', credentials=creds)
    return drive_service, docs_service

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
    requests = [{'insertText': {'location': {'index': 1}, 'text': content}}]
    docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
    print(f"Документ '{title}' успешно сохранен на Диске!")

def main():
    print("Запуск конвейера новостей...")
    
    drive_service, docs_service = authenticate_google()
    if not drive_service:
        return
        
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("Новых статей в Inoreader пока нет.")
        return

    print(f"Найдено новостей для обработки: {len(feed.entries)}\n")
    
    # Счетчик для того, чтобы не превысить лимит в 20 запросов/день
    counter = 0
    for article in feed.entries:
        if counter >= 2: # Обрабатываем только по 2 новости за 1 запуск (чтобы укладываться в лимиты)
            print("Лимит запросов на этот запуск достигнут.")
            break
            
        title = article.title
        description = article.get('description', '')
        
        print(f"Обрабатываю новость: {title}")
        prompt = f"{SYSTEM_PROMPT}\n\nНовость для обработки:\nЗаголовок: {title}\nТекст: {description}"
        
        try:
            response = client.models.generate_content(
                model='gemini-1.5-flash', # Исправлено название модели
                contents=prompt
            )
            print("Пост сгенерирован, переносим в Google Документ...")
            create_google_doc(drive_service, docs_service, title, response.text)
            counter += 1
            
        except Exception as e:
            print(f"Ошибка при обработке {title}: {e}")
            if "429" in str(e): 
                print("Достигнут лимит API, останавливаюсь.")
                break
        
        print("Пауза 15 секунд...\n")
        time.sleep(15) # Увеличили паузу, чтобы API Диска не "ругалось"

    print("Все новости успешно обработаны!")

if __name__ == "__main__":
    main()
