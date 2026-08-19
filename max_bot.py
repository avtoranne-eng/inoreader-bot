import os
import time
import feedparser
import re
import google.generativeai as genai

# --- НАСТРОЙКИ ---
RSS_URL = "https://avtoranne.raindrop.page/max-74027357/feed"
PROCESSED_FILE = "processed_max.txt"
OUTPUT_DIR = "max_posts"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Создаем папку для постов, если её нет
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_processed_links():
    if not os.path.exists(PROCESSED_FILE):
        return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def add_to_processed(link):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")

def clean_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", title)[:50].strip()

def generate_text_from_ai(prompt):
    if not GEMINI_API_KEY:
        print("❌ Ошибка: Ключ GEMINI_API_KEY не найден!")
        return None
        
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-3.5-flash-lite")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"❌ Ошибка при обращении к нейросети: {e}")
        return None

def main():
    processed = get_processed_links()
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries:
        print("Лента Макса пуста или недоступна.")
        return

    for entry in feed.entries:
        link = entry.link
        if link in processed:
            continue
            
        title = entry.title
        clean_text = entry.description if hasattr(entry, 'description') else "Текст новости отсутствует."
        
        print(f"🔥 Пишем пост для Макса: {title}")
        
        # --- ПРОМПТ ДЛЯ МАКСА ---
        prompt = (
            f"Твоя роль: острый на язык, бескомпромиссный игровой журналист канала Level UP. "
            f"Твоя задача: Написать емкий, динамичный и провокационный пост по новости. "
            f"КРИТИЧЕСКОЕ ПРАВИЛО: Объем готового текста должен быть строго от 3500 до 4000 символов (включая пробелы). Используй лимит по максимуму, но не смей превышать эту цифру! "
            f"Правила и структура: "
            f"1. Напиши хлесткий, цепляющий заголовок без воды. "
            f"2. Выдели самую суть инфоповода максимально коротко, а затем погрузись в детали с долей иронии и сарказма. "
            f"3. Блок 'Вердикт Level UP': Добавь жесткое, честное мнение от лица канала, без прикрас. "
            f"4. Визуал: Используй 4-5 смысловых эмодзи для структуры. Текст должен быть плотным и легко читаться с телефона. "
            f"5. Вовлечение: В конце задай подписчикам острый вопрос, чтобы спровоцировать активность в комментариях. "
            f"6. Форматирование: Используй стандартный Markdown (**жирный текст** для выделения ключевых тезисов). "
            f"\n\nНовость: {title}\nТекст: {clean_text}"
        )
        
        article_text = generate_text_from_ai(prompt)
        
        if article_text:
            safe_title = clean_filename(title)
            filepath = os.path.join(OUTPUT_DIR, f"{safe_title}.md")
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(article_text)
                
            print(f"✅ Пост сохранен: {filepath}")
            add_to_processed(link)
            time.sleep(5) 

if __name__ == "__main__":
    main()
