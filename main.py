import os
import time
import feedparser
import google.generativeai as genai

# Настройка клиента для Gemini
API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# Твоя модель
MODEL_NAME = "gemini-3.5-flash-lite"
model = genai.GenerativeModel(MODEL_NAME)

RSS_URL = "https://www.inoreader.com/stream/user/1003745790/tag/user-favorites"
PROCESSED_FILE = "processed.txt"
POSTS_DIR = "posts"

# Создаем папку, если ее нет
os.makedirs(POSTS_DIR, exist_ok=True)

def get_processed_titles():
    if not os.path.exists(PROCESSED_FILE): return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def add_to_processed_list(title):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(title + "\n")

def main():
    feed = feedparser.parse(RSS_URL)
    processed = get_processed_titles()
    
    count = 0
    for article in feed.entries:
        title = article.title
        if title in processed: continue
            
        print(f"Обрабатываю: {title}")
        safe_filename = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()[:50]
        
        # Твой оригинальный промпт
        # Обновленный промпт с правилами грамматики
                prompt = (
            f"Твоя роль: экспертный игровой журналист, контент-мейкер и строгий литературный редактор. "
            f"Твоя задача: написать развернутый лонгрид для ВКонтакте по новости. "
            f"Пиши пост строго по этому шаблону:\n\n"
            f"1. ЗАГОЛОВОК: Придумай мощный SEO-заголовок под запросы геймеров. ВЕСЬ ЗАГОЛОВОК ПИШИ ИСКЛЮЧИТЕЛЬНО ЗАГЛАВНЫМИ БУКВАМИ.\n"
            f"2. ОСНОВНОЙ ТЕКСТ: Детально проанализируй новость. ПИШИ СТРОГО ОБЫЧНЫМ ШРИФТОМ (не заглавными буквами!). Текст должен быть идеальным по грамотности, живым и без воды.\n"
            f"3. ОФОРМЛЕНИЕ: Активно используй эмодзи для визуального разделения логических блоков и списков. Это твой единственный способ выделять важные мысли.\n"
            f"4. КОНЦОВКА: Напиши живой призыв к комментариям. Затем, с новой строки, добавь 7-8 хештегов (первый обязательно #LevelupNews).\n\n"
            f"Новость: {title}. Текст: {article.get('description', '')}"
        )
        
        try:
            # Генерация через модель Gemini
            response = model.generate_content(prompt)
            
            # Сохраняем в файл
            with open(f"{POSTS_DIR}/{safe_filename}.md", "w", encoding="utf-8") as f:
                f.write(response.text)
            
            add_to_processed_list(title)
            print("Успех!")
            count += 1
            if count >= 3: break 
            time.sleep(15)
        except Exception as e:
            print(f"Ошибка при работе с Gemini: {e}")
            break

if __name__ == "__main__":
    main()
