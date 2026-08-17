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

# Папка для Дзена и отдельный файл памяти
DZEN_FOLDER = "Посты Дзен"
PROCESSED_FILE = "processed_dzen.txt"

def ensure_dzen_folder_exists():
    if not os.path.exists(DZEN_FOLDER):
        os.makedirs(DZEN_FOLDER)

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
    # Обрезаем слишком длинные названия
    return safe_title[:70].strip()

def main():
    ensure_dzen_folder_exists()
    feed = feedparser.parse(RSS_URL)
    processed = get_processed_titles()

    count = 0
    for article in feed.entries:
        title = article.title
        if title in processed: continue

        print(f"\n--- Пишем статью для Дзена: {title} ---")
        
        raw_html = article.get('description', '')
        clean_text = BeautifulSoup(raw_html, "html.parser").get_text(separator=" ", strip=True)
        clean_text = clean_text[:3000]
        
        # --- ПРОМПТ ДЛЯ ДЗЕНА ---
        prompt = (
            f"Твоя роль: элитный игровой журналист, автор популярного канала на Дзене Level UP. "
            f"Твоя задача: Написать захватывающую, глубокую и длинную статью по игровой новости, которая удержит читателя до самой последней строчки (максимальное дочитывание). "
            f"Правила и структура: "
            f"1. Придумай интригующий, кликабельный заголовок, который не нарушает правила платформы (без откровенного кликбейта), но заставляет нажать на статью. "
            f"2. Обязательно начни с классного, живого приветствия аудитории канала Level UP. "
            f"3. Текст должен быть качественным, грамотным, с глубокой аналитикой или долей ностальгии. Пиши литературно, используй сторителлинг. "
            f"4. Активно используй форматирование: разбивай текст на небольшие удобные абзацы, используй жирный шрифт для выделения главных мыслей и курсив. "
            f"5. В конце статьи ОБЯЗАТЕЛЬНО сделай отдельный блок 'Мнение редакции Level UP', где ты от лица канала выскажешь наши размышления, покреативишь и дашь свою оценку. "
            f"6. Заверши статью мощным призывом к читателям спуститься в комментарии и высказать свое мнение, задай им конкретный вопрос по теме. "
            f"\n\nНовость: {title}\nТекст: {clean_text}"
        )

        try:
            response = model.generate_content(prompt)
            generated_text = response.text
            
            # Формируем имя файла и сохраняем статью
            filename = f"{sanitize_filename(title)}.txt"
            filepath = os.path.join(DZEN_FOLDER, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(generated_text)
                
            print(f"✅ Статья успешно сохранена в файл: {filepath}")
            
            add_to_processed_list(title)
            count += 1
            
            # Поскольку расписание внешнее (cron), делаем только 1 статью за запуск и останавливаемся
            if count >= 1: break 
            
        except Exception as e:
            print(f"❌ Критическая ошибка генерации: {e}")
            break

if __name__ == "__main__":
    main()
