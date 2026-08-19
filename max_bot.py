import os
import re
import feedparser
import google.generativeai as genai
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ КЛЮЧЕЙ ---
API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-3.5-flash-lite")

RSS_URL = "https://avtoranne.raindrop.page/novosti-level-up-74004813/feed"

# Папка для Макса и отдельный файл памяти
MAX_FOLDER = "Посты Макс"
PROCESSED_FILE = "processed_max.txt"

def ensure_max_folder_exists():
    if not os.path.exists(MAX_FOLDER):
        os.makedirs(MAX_FOLDER)

def get_processed_titles():
    if not os.path.exists(PROCESSED_FILE): return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def add_to_processed_list(title):
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(title + "\n")

def sanitize_filename(title):
    """Очищает заголовок от запрещенных символов для создания безопасного имени файла"""
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    return safe_title[:70].strip()

def main():
    ensure_max_folder_exists()
    feed = feedparser.parse(RSS_URL)
    processed = get_processed_titles()

    count = 0
    for article in feed.entries:
        title = article.title
        if title in processed: continue

        print(f"\n--- Пишем дерзкий пост для Макса: {title} ---")
        
        raw_html = article.get('description', '')
        clean_text = BeautifulSoup(raw_html, "html.parser").get_text(separator=" ", strip=True)
        clean_text = clean_text[:3000]
        
        # --- ПРОМПТ ДЛЯ МАКСА ---
        prompt = (
            f"Твоя роль: острый на язык, бескомпромиссный игровой журналист канала Level UP. "
            f"Твоя задача: Написать емкий, динамичный, но при этом максимально развернутый и провокационный пост по новости. "
            f"КРИТИЧЕСКОЕ ПРАВИЛО: Объем готового текста должен быть около 3000-3500 символов. Пиши развернуто, используй лимит платформы по максимуму, но строго не превышай 3800 символов. "
            f"Правила и структура: "
            f"1. Напиши хлесткий, цепляющий заголовок. "
            f"2. Выдели суть инфоповода, а затем глубоко погрузись в детали. Добавь сарказм, иронию, сравни с конкурентами. "
            f"3. Блок 'Вердикт Level UP': Добавь развернутое, жесткое и честное мнение от лица канала на несколько абзацев. "
            f"4. Визуал: Используй 5-7 смысловых эмодзи для структуры. Разделяй текст на удобные абзацы для чтения с телефона. "
            f"5. В конце задай подписчикам острый вопрос, чтобы спровоцировать спор. "
            f"6. В самом конце добавь 4-5 актуальных хештегов. "
            f"7. Форматирование: Используй стандартный Markdown (**жирный текст**). Выделяй только ключевые тезисы."
            f"\n\nНовость: {title}\nТекст: {clean_text}"
        )

        try:
            response = model.generate_content(prompt)
            generated_text = response.text
            
            # Формируем имя файла и сохраняем пост
            filename = f"{sanitize_filename(title)}.txt"
            filepath = os.path.join(MAX_FOLDER, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(generated_text)
                
            print(f"✅ Пост успешно сохранен в файл: {filepath}")
            
            add_to_processed_list(title)
            count += 1
            
            # Делаем только 1 пост за запуск для крона
            if count >= 1: break 
            
        except Exception as e:
            print(f"❌ Критическая ошибка генерации: {e}")
            break

if __name__ == "__main__":
    main()
