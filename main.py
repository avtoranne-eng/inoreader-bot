import os
import time
import feedparser
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
API_KEY = os.environ.get("GEMINI_API_KEY")
VK_TOKEN = os.environ.get("VK_TOKEN")

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
    image_url = None
    
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

    if not image_url and hasattr(article, 'link'):
        try:
            print(f"🔍 Ищу картинку на сайте: {article.link}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            resp = requests.get(article.link, headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                og_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
                if og_img and og_img.get('content'):
                    image_url = og_img['content']
            else:
                print(f"⚠️ Сайт не пустил бота (Код {resp.status_code})")
        except Exception as e:
            print(f"⚠️ Ошибка доступа к сайту: {e}")

    print(f"🎯 Итоговая ссылка на фото: {image_url}")
    return image_url

def upload_photo_to_vk(image_url):
    if not image_url or not VK_TOKEN or not VK_GROUP_ID: return None
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        img_response = requests.get(image_url, headers=headers, stream=True, timeout=15)
        
        if img_response.status_code != 200:
            print(f"❌ Не удалось скачать картинку (Код {img_response.status_code})")
            return None
        
        server_url = f"https://api.vk.com/method/photos.getWallUploadServer?group_id={VK_GROUP_ID}&access_token={VK_TOKEN}&v={VK_API_VERSION}"
        server_resp = requests.get(server_url).json()
        upload_url = server_resp.get('response', {}).get('upload_url')
        
        if not upload_url:
            print(f"❌ ВК не выдал сервер. Ответ ВК: {server_resp}")
            return None
        
        files = {'photo': ('image.jpg', img_response.content, 'image/jpeg')}
        upload_result = requests.post(upload_url, files=files).json()
        
        if not upload_result.get('photo') or upload_result.get('photo') == '[]':
            print(f"❌ ВК не принял файл: {upload_result}")
            return None
            
        save_params = {
            'group_id': VK_GROUP_ID,
            'photo': upload_result['photo'],
            'server': upload_result['server'],
            'hash': upload_result['hash'],
            'access_token': VK_TOKEN,
            'v': VK_API_VERSION
        }
        save_result = requests.post("https://api.vk.com/method/photos.saveWallPhoto", data=save_params).json()
        
        if 'response' in save_result and len(save_result['response']) > 0:
            photo_info = save_result['response'][0]
            attachment = f"photo{photo_info.get('owner_id')}_{photo_info.get('id')}"
            print(f"✅ Картинка успешно загружена в ВК: {attachment}")
            return attachment
        else:
            print(f"❌ Ошибка сохранения картинки в ВК: {save_result}")
            return None

    except Exception as e:
        print(f"❌ Критическая ошибка в блоке загрузки фото: {e}")
        return None

def post_to_vk_scheduled(text, attachment, post_index):
    if not VK_TOKEN or not VK_GROUP_ID: return False
    
    START_DELAY_HOURS = 24 
    GAP_BETWEEN_POSTS = 0.5 

    offset_hours = START_DELAY_HOURS + (post_index * GAP_BETWEEN_POSTS) 
    publish_time = int(time.time()) + int(offset_hours * 3600) 
    
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
        print(f"✅ Пост улетел в отложку! Выйдет через {offset_hours} час(ов).")
        return True
    else:
        print(f"❌ Ошибка публикации в ВК: {response}")
        return False

def main():
    feed = feedparser.parse(RSS_URL)
    processed = get_processed_titles()

    count = 0
    for article in feed.entries:
        title = article.title
        if title in processed: continue

        print(f"\n--- Обрабатываю: {title} ---")
        
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
            print(f"❌ Критическая ошибка генерации: {e}")
            break

if __name__ == "__main__":
    main()
