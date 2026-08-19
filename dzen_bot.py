import os
import time
import feedparser
import re
import google.generativeai as genai

# --- НАСТРОЙКИ ---
RSS_URL = "https://bg.raindrop.io/rss/public/74027356" # Прямая RSS-ссылка
PROCESSED_FILE = "processed_dzen.txt"
OUTPUT_DIR = "dzen_articles"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
POSTS_PER_RUN = 1 # <--- ЛИМИТ СТАТЕЙ ЗА ОДИН ЗАПУСК

# Создаем папку для статей, если её нет
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
    # Убираем запрещенные символы из названия файла
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
        print("Лента Дзена пуста или недоступна.")
        return

    count = 0 # Счетчик написанных статей

    for entry in feed.entries:
        link = entry.link
        if link in processed:
            continue
            
        title = entry.title
        clean_text = entry.description if hasattr(entry, 'description') else "Текст новости отсутствует."
        
        print(f"📝 Пишем лонгрид для Дзена: {title}")
        
        # --- ПРОМПТ ДЛЯ ДЗЕНА ---
        prompt = (
            f"Твоя роль: элитный игровой журналист, SEO-специалист и автор популярного канала на Дзене LevelUP. "
            f"Твоя задача: Написать захватывающую, глубокую и очень длинную лонгрид-статью (строго от 700 слов), которая удержит читателя до последней строчки и привлечет поисковый трафик из Яндекса и Google. "
            f"Правила и структура: "
            f"1. Заголовок: Сформулируй жестко под конкретные поисковые запросы геймеров (например, вместо абстрактного названия пиши 'Скачать лучшие моды на...'). "
            f"2. Приветствие: Начни с живого приветствия аудитории канала LevelUP. "
            f"3. SEO и трафик: Органично вшивай ключевые слова в текст, чтобы нас находили через поиск, но текст должен читаться литературно и естественно. "
            f"4. Глубина и объем: Раскрой инфоповод максимально широко. Добавь предысторию, проанализируй влияние новости на индустрию, используй сторителлинг. Не скупись на детали — нужен большой объем. "
            f"5. 'Мнение редакции LevelUP': В конце статьи ОБЯЗАТЕЛЬНО сделай объемный отдельный блок, где ты от лица канала выскажешь наши размышления, дашь свою оценку и прогноз. "
            f"6. Вовлечение: Заверши лонгрид мощным призывом к читателям спуститься в комментарии и задай им провокационный вопрос по теме. "
            f"7. Форматирование: Обязательно используй Markdown (**жирный текст** для заголовков и важных мыслей, *курсив* для названий игр, > для цитат или мнения редакции). Дели текст на удобные абзацы."
            f"\n\nНовость: {title}\nТекст: {clean_text}"
        )
        
        article_text = generate_text_from_ai(prompt)
        
        if article_text:
            safe_title = clean_filename(title)
            filepath = os.path.join(OUTPUT_DIR, f"{safe_title}.md")
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(article_text)
                
            print(f"✅ Статья сохранена: {filepath}")
            add_to_processed(link)
            count += 1
            
            if count >= POSTS_PER_RUN:
                print(f"🛑 Достигнут лимит {POSTS_PER_RUN} статей за один запуск. Идем отдыхать.")
                break
                
            time.sleep(5) 

if __name__ == "__main__":
    main()
