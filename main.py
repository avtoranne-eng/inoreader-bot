import os
import time
import feedparser
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
API_KEY = os.environ.get("GEMINI_API_KEY")
VK_TOKEN = os.environ.get("VK_TOKEN")

# Очистка ID группы от букв и лишних символов
RAW_VK_GROUP_ID = str(os.environ.get("VK_GROUP_ID", ""))
VK_GROUP_ID = ''.join(filter(str.isdigit, RAW_VK_GROUP_ID))

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-3.5-flash-lite")

RSS_URL = "https://avtoranne.raindrop.page/novosti-level-up-74004813/feed"
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
    """Умный поиск обложки: сначала в RSS, затем на сайте-источнике"""
    image_url = None
    
    # 1. Проверяем сам RSS-поток
    if 'media_content' in article and len(article.media_content) > 0:
        for media in article.media_content:
            if 'url' in media: 
                image_url = media['url']
                break
                
    if not image_url and 'links' in article:
        for link in article.links:
            if 'image' in link.get('type', ''): 
                image_url = link.href
                break
                
    if not image_url and 'description' in article:
        soup = BeautifulSoup(article.description, 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not src: continue
            src_lower = src.lower()
            if any(bad in src_lower for bad in ['logo', 'icon', 'avatar', 'pixel', 'tracker', 'button']): continue
            if img.get('width') == '1' or img.get('height') == '1': continue
            image_url = src
            break

    # 2. Если RSS пустой — идем на сам сайт и забираем главную обложку!
    if not image_url and hasattr(article, 'link'):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(article.link, headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Ищем официальную обложку статьи (тег OpenGraph)
                og_img = soup.find('meta', property='og:image')
                if og_img and og_img.get('content'):
                    image_url = og_img['content']
        except Exception as e:
            print(f"Не удалось вытянуть картинку с сайта: {e}")

    return image_url

def upload_photo_to_vk(image_url):
    if not image_url or not VK_TOKEN or not VK_GROUP_ID: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        img_response = requests.get(image_url, headers=headers, stream=True, timeout=15)
        if img_response.status_code != 200: return None
        
        server_url = f"https://api.vk.com/method/photos.getWallUploadServer?group_id={VK_GROUP_ID}&access_token={VK_TOKEN}&v={VK_API_VERSION}"
        upload_url = requests.get(server_url).json().get('response', {}).get('upload_url')
        if not upload_url: return None
        
        files = {'photo': ('image.jpg', img_response.content, 'image/jpeg')}
        upload_result = requests.post(upload_url, files=files).json()
        
        save_url = f"https://api.vk.com/method/photos.saveWallPhoto?group_id={VK_GROUP_ID}&photo={upload_result['photo']}&server={upload_result['server']}&hash={upload_result['hash']}&access_token={VK_TOKEN}&v={VK_API_VERSION}"
        save_result = requests.get(save_url).json()
        
        photo_info = save_result.get('response', [{}])[0]
        return f"photo{photo_info.get('owner_id')}_{photo_info.get('id')}"
    except Exception as e:
        print(f"Ошибка загрузки фото в ВК: {e}")
        return None

def post_to_vk_scheduled(text, attachment, post_index):
    if not VK_TOKEN or not VK_GROUP_ID: return False
    
    # --- НАСТРОЙКИ РАСПИСАНИЯ ---
    START_DELAY_HOURS = 1 # Через сколько часов выйдет ПЕРВЫЙ пост (сейчас: 1 час)
    GAP_BETWEEN_POSTS = 1 # Разница между следующими постами (сейчас: 1 час)
    # ----------------------------

    offset_hours = START_DELAY_HOURS + (post_index * GAP_BETWEEN_POSTS) 
    publish_time = int(time.time()) + (offset_hours * 3600) 
    
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
        print(f"Пост улетел в отложку! Выйдет через {offset_hours} час(ов).")
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
        
        raw_html = article.get('description', '')
        clean_text = BeautifulSoup(raw_html, "html.parser").get_text(separator=" ", strip=True)
        clean_text = clean_text[:3000]
        
        prompt = f"Твоя роль: экспертный игровой журналист, игровой блогер, контент-мейкер и строгий литературный редактор. Задача: Напиши максимально развернутый, глубокий и подробный лонгрид для ВКонтакте, детально анализируя каждый аспект новости. Правила: - Придумай мощный SEO-заголовок под конкретные поисковые запросы геймеров. - Абсолютная грамотность: текст должен быть идеальным. Никаких орфографических, пунктуационных, речевых или стилистических ошибок. Внимательно следи за правильным согласованием окончаний и падежей. - Поскольку стандартное разделение на абзацы и жирный шрифт недоступны, активно и структурированно используй эмодзи для визуального разделения логических блоков, списков и выделения важных мыслей. Эмодзи — твой единственный инструмент форматирования текста. - Текст должен быть без воды, написан живым языком. - В конце статьи напиши призыв подписчиков к комментариям. - В самом конце текста, с новой строки, обязательно напиши 7-8 релевантных хештега для ВК. Первым и обязательным всегда должен стоять тег #LevelupNews. Новость: {title}. Текст: {clean_text}"

        try:
            response = model.generate_content(prompt)
            generated_text = response.text
            
            image_url = extract_image_url(article)
            attachment = upload_photo_to_vk(image_url)
            
            success = post_to_vk_scheduled(generated_text, attachment, count)
            
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
