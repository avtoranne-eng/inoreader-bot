import os
import time
import feedparser
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
API_KEY = os.environ.get("GEMINI_API_KEY")
VK_TOKEN = os.environ.get("VK_TOKEN") # Используй обычный ключ группы!

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

def post_to_vk_scheduled(text, article_link, post_index):
    if not VK_TOKEN or not VK_GROUP_ID: return False
    
    # --- ТВОИ НАСТРОЙКИ ВРЕМЕНИ (Всё на месте!) ---
    START_DELAY_HOURS = 24  # Первый пост улетит на завтра
    GAP_BETWEEN_POSTS = 0.5 # Разница ровно 30 минут
    # ----------------------------------------------

    offset_hours = START_DELAY_HOURS + (post_index * GAP_BETWEEN_POSTS) 
    publish_time = int(time.time()) + int(offset_hours * 3600) 
    
    post_url = f"https://api.vk.com/method/wall.post"
    params = {
        "owner_id": f"-{VK_GROUP_ID}",
        "message": text,
        "publish_date": publish_time,
        "attachments": article_link, # 👈 Отдаем ВК ссылку, он сам вытянет обложку!
        "access_token": VK_TOKEN,
        "v": VK_API_VERSION
    }
        
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
            
            # Берем оригинальную ссылку на новость из Raindrop
            article_link = article.link
            
            # Отправляем текст и ссылку в ВК
            success = post_to_vk_scheduled(generated_text, article_link, count)
            
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
