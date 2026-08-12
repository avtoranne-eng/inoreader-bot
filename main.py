import os
import time
import re
import feedparser
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
API_KEY = os.environ.get("GEMINI_API_KEY")
VK_TOKEN = os.environ.get("VK_TOKEN")
VK_GROUP_ID = os.environ.get("VK_GROUP_ID")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-3.5-flash-lite")

RSS_URL = "https://www.inoreader.com/stream/user/1003745790/tag/user-favorites"
PROCESSED_FILE = "processed.txt"
VK_API_VERSION = "5.131"

def get_processed_titles():
    if not os.path.exists(PROCESSED_FILE): return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def add_to_processed_list(title):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(title + "\n")

def extract_image_url(article):
    """Пытаемся найти картинку в новости"""
    if 'media_content' in article and len(article.media_content) > 0:
        return article.media_content[0]['url']
    if 'links' in article:
        for link in article.links:
            if 'image' in link.get('type', ''):
                return link.href
    if 'description' in article:
        soup = BeautifulSoup(article.description, 'html.parser')
        img = soup.find('img')
        if img and img.get('src'):
            return img['src']
    return None

def upload_photo_to_vk(image_url):
    """Скачиваем фото и загружаем на сервер ВК"""
    if not image_url or not VK_TOKEN or not VK_GROUP_ID:
        return None
    
    try:
        # Скачиваем картинку
        img_response = requests.get(image_url, stream=True)
        if img_response.status_code != 200: return None
        
        # Получаем сервер для загрузки
        server_url = f"https://api.vk.com/method/photos.getWallUploadServer?group_id={VK_GROUP_ID}&access_token={VK_TOKEN}&v={VK_API_VERSION}"
        upload_url = requests.get(server_url).json().get('response', {}).get('upload_url')
        if not upload_url: return None
        
        # Загружаем файл
        files = {'photo': ('image.jpg', img_response.content, 'image/jpeg')}
        upload_result = requests.post(upload_url, files=files).json()
        
        # Сохраняем фото в группе
        save_url = f"https://api.vk.com/method/photos.saveWallPhoto?group_id={VK_GROUP_ID}&photo={upload_result['photo']}&server={upload_result['server']}&hash={upload_result['hash']}&access_token={VK_TOKEN}&v={VK_API_VERSION}"
        save_result = requests.get(save_url).json()
        
        photo_info = save_result.get('response', [{}])[0]
        return f"photo{photo_info.get('owner_id')}_{photo_info.get('id')}"
    except Exception as e:
        print(f"Ошибка загрузки фото в ВК: {e}")
        return None

def post_to_vk_scheduled(text, attachment):
    """Отправляем пост в отложку ВК на 24 часа вперед"""
    if not VK_TOKEN or not VK_GROUP_ID: return False
    
    # Время публикации: текущее время + 24 часа (86400 секунд)
    publish_time = int(time.time()) + 86400 
    
    post_url = f"https://api.vk.com/method/wall.post"
    params = {
        "owner_id": f"-{VK_GROUP_ID}",
        "message": text,
        "publish_date": publish_time,
        "access_token": VK_TOKEN,
        "v": VK_API_VERSION
    }
    if attachment:
        params["attachments"] = attachment
        
    response = requests.post(post_url, data=params).json()
    if 'response' in response:
        print("Пост успешно улетел в отложку ВК!")
        return True
    else:
        print(f"Ошибка публикации в ВК: {response}")
        return False

def main():
    feed = feedparser.parse(RSS_URL)
    processed = get_processed_titles()

    count = 0
    for article in feed.entries:
        title = article.title
        if title in processed: continue

        print(f"Обрабатываю: {title}")
        
        # Тот самый правильный промпт для красивого текста
        prompt = f"Твоя роль: экспертный игровой журналист, игровой блогер, контент-мейкер и строгий литературный редактор. Задача: Напиши максимально развернутый, глубокий и подробный лонгрид для ВКонтакте, детально анализируя каждый аспект новости. Правила: - Придумай мощный SEO-заголовок под конкретные поисковые запросы геймеров. - Абсолютная грамотность: текст должен быть идеальным. Никаких орфографических, пунктуационных, речевых или стилистических ошибок. Внимательно следи за правильным согласованием окончаний и падежей. - Поскольку стандартное разделение на абзацы и жирный шрифт недоступны, активно и структурированно используй эмодзи для визуального разделения логических блоков, списков и выделения важных мыслей. Эмодзи — твой единственный инструмент форматирования текста. - Текст должен быть без воды, написан живым языком. - В конце статьи напиши призыв подписчиков к комментариям. - В самом конце текста, с новой строки, обязательно напиши 7-8 релевантных хештега для ВК. Первым и обязательным всегда должен стоять тег #LevelupNews. Новость: {title}. Текст: {article.get('description', '')}"

        try:
            # 1. Генерируем текст
            response = model.generate_content(prompt)
            generated_text = response.text
            
            # 2. Ищем и загружаем картинку в ВК
            image_url = extract_image_url(article)
            attachment = upload_photo_to_vk(image_url)
            
            # 3. Отправляем в ВК в отложку
            success = post_to_vk_scheduled(generated_text, attachment)
            
            if success:
                add_to_processed_list(title)
                count += 1
                if count >= 2: break 
                time.sleep(15)
        except Exception as e:
            print(f"Критическая ошибка: {e}")
            break

if __name__ == "__main__":
    main()
