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
        prompt = f"Твоя роль: экспертный игровой журналист и контент-мейкер. Задача: Напиши максимально развернутый, глубокий и подробный лонгрид для ВКонтакте, детально анализируя каждый аспект новости. Правила: - Придумай мощный SEO-заголовок под конкретные поисковые запросы геймеров. - Поскольку стандартное разделение на абзацы и жирный шрифт недоступны, активно и структурированно используй эмодзи для визуального разделения логических блоков, списков и выделения важных мыслей. Эмодзи — твой единственный инструмент форматирования текста. - Текст должен быть без воды, написан живым языком. - В самом конце текста, с новой строки, обязательно напиши 7-8 релевантных хештега для ВК. Первым и обязательным всегда должен стоять тег #LevelupNews. Новость: {title}. Текст: {article.get('description', '')}"
        
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
