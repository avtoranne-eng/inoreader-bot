import os
import time
import feedparser
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
API_KEY = os.environ.get("GEMINI_API_KEY")
VK_TOKEN = os.environ.get("VK_TOKEN") # Обычный ключ группы

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
    """Ищем картинку, чтобы вывести ссылку в лог для ручного скачивания"""
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
        except Exception:
            pass

    return image_url

def post_to_vk_scheduled(text):
    if not VK_TOKEN or not VK_GROUP_ID: return False
    
    # --- НАСТРОЙКА ВРЕМЕНИ ---
    START_DELAY_HOURS = 24  # Пост выйдет ровно через 24 часа
    # -------------------------

    publish_time = int(time.time()) + int(START_DELAY_HOURS * 3600) 
    
    post_url = f"https://api.vk.com/method/wall.post"
    params = {
        "owner_id": f"-{VK_GROUP_ID}",
        "message": text,
        "publish_date": publish_time,
        "access_token": VK_TOKEN,
        "v": VK_API_VERSION
    }
        
    response = requests.post(post_url, data=params).json()
    if 'response' in response:
        print(f"✅ Пост улетел в отложку! Выйдет через {START_DELAY_HOURS} час(ов).")
        return True
    else:
        print(f"❌ Ошибка публикации в ВК: {response}")
        return False

def main():
    # --- Защита от обрыва связи с сервером ---
    max_retries = 3
    feed = None
    for attempt in range(max_retries):
        try:
            feed = feedparser.parse(RSS_URL)
            # Проверяем, нет ли скрытой ошибки сервера
            if hasattr(feed, 'status') and feed.status not in [200, 301, 302]:
                raise Exception(f"Ошибка сервера: {feed.status}")
            break # Если всё ок, выходим из цикла попыток
        except Exception as e:
            print(f"⚠️ Попытка {attempt + 1} не удалась: {e}")
            if attempt < max_retries - 1:
                print("Ждем 10 секунд и пробуем снова...")
                time.sleep(10)
            else:
                print("❌ Сервер Raindrop не отвечает после 3 попыток. Скрипт остановлен.")
                return

    if not feed or not feed.entries:
        print("Нет новостей для обработки.")
        return
    # -----------------------------------------

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
            # --- Броня для API Gemini ---
            max_gen_retries = 3
            generated_text = None
            
            for gen_attempt in range(max_gen_retries):
                try:
                    response = model.generate_content(prompt)
                    generated_text = response.text
                    break # Если текст сгенерирован успешно, выходим из цикла попыток
                except Exception as e:
                    if "429" in str(e) or "Quota" in str(e):
                        print(f"⚠️ API Google перегружен (попытка {gen_attempt + 1}/{max_gen_retries}). Ждем 20 секунд...")
                        time.sleep(20)
                    else:
                        raise e # Если ошибка критическая и другая, пробрасываем её дальше
            
            if not generated_text:
                raise Exception("Не удалось сгенерировать текст после 3 попыток.")
            # -----------------------------
            
            # Находим картинку и выводим ссылку в консоль
            image_url = extract_image_url(article)
            if image_url:
                print(f"🖼 ССЫЛКА НА КАРТИНКУ ДЛЯ СКАЧИВАНИЯ: {image_url}")
            else:
                print("⚠️ Картинку найти не удалось.")
            
            # Публикуем текст в отложку
            success = post_to_vk_scheduled(generated_text)
            
            if success:
                add_to_processed_list(title)
                count += 1
                # Останавливаем скрипт после ОДНОГО успешного поста
                if count >= 1: break 
        except Exception as e:
            print(f"❌ Критическая ошибка генерации: {e}")
            break

if __name__ == "__main__":
    main()
