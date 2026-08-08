import os
import feedparser
from google import genai

# 1. Подключаемся к Gemini через новый клиент
API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# 2. ВСТАВЬ СВОЮ ССЫЛКУ ИЗ INOREADER МЕЖДУ КАВЫЧКАМИ НИЖЕ:
RSS_URL = "https://www.inoreader.com/stream/user/1003745790/tag/user-favorites"

# 3. Наш жесткий системный промпт (инструкция)
SYSTEM_PROMPT = """
Твоя роль: экспертный игровой журналист и контент-мейкер.
Задача: Напиши качественный пост для ВКонтакте по предоставленной новости.
Правила:
- Придумай мощный SEO-заголовок под конкретные поисковые запросы геймеров.
- Поскольку стандартное разделение на абзацы и жирный шрифт недоступны, активно и структурированно используй эмодзи для визуального разделения логических блоков, списков и выделения важных мыслей. Эмодзи — твой единственный инструмент форматирования текста.
- Текст должен быть без воды, написан живым языком.
- В самом конце текста, с новой строки, обязательно напиши 7-8 релевантных хештега для ВК. Первым и обязательным всегда должен стоять тег #LevelupNews.
"""

def main():
    print("Запуск конвейера новостей...")
    
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries:
        print("Новых статей в Inoreader пока нет.")
        return

    latest_article = feed.entries[0]
    title = latest_article.title
    description = latest_article.get('description', '')
    
    print(f"Найдена новость: {title}")
    print("Передаю на обработку...")

    prompt = f"{SYSTEM_PROMPT}\n\nНовость для обработки:\nЗаголовок: {title}\nТекст: {description}"
    
    # Отправляем задачу через новую библиотеку
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=prompt
    )
    
    print("\n--- ГОТОВЫЙ ПОСТ ---")
    print(response.text)
    print("--------------------")
    print("Задача выполнена успешно!")

if __name__ == "__main__":
    main()
