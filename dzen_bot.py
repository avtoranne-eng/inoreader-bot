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
            f"Твоя роль: элитный игровой журналист, SEO-специалист и автор популярного канала на Дзене LevelUP. "
            f"Твоя задача: Написать захватывающую, глубокую и очень длинную лонгрид-статью (строго от 1500 слов), которая удержит читателя до последней строчки и привлечет поисковый трафик из Яндекса и Google. "
            f"Правила и структура: "
            f"1. Заголовок: Сформулируй жестко под конкретные поисковые запросы геймеров (например, вместо абстрактного названия пиши 'Скачать лучшие моды на...'). "
            f"2. Приветствие: Начни с живого приветствия аудитории канала LevelUP. "
            f"3. SEO и трафик: Органично вшивай ключевые слова в текст, чтобы нас находили через поиск, но текст должен читаться литературно и естественно. "
            f"4. Глубина и объем: Раскрой инфоповод максимально широко. Добавь предысторию, проанализируй влияние новости на индустрию, используй сторителлинг. Не скупись на детали — нужен большой объем. "
            f"5. 'Мнение редакции LevelUP': В конце статьи ОБЯЗАТЕЛЬНО сделай объемный отдельный блок, где ты от лица канала выскажешь наши размышления, дашь свою оценку и прогноз. "
            f"6. Вовлечение: Заверши лонгрид мощным призывом к читателям спуститься в комментарии и задай им провокационный вопрос по теме. "
            f"7. Форматирование: Обязательно используй жирный шрифт для заголовков и важных мыслей, курсив для названий игр и Мнения редакции. Дели текст на удобные абзацы."
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
