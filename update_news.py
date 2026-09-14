import json
import urllib.request
import os
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


SOURCES = [
    {
        "name": "РБК",
        "url": "https://news.google.com/rss/search?q="
               + urllib.parse.quote("site:rbc.ru when:1d")
               + "&hl=ru&gl=RU&ceid=RU:ru"
    },
    {
        "name": "Фонтанка",
        "url": "https://news.google.com/rss/search?q="
               + urllib.parse.quote("site:fontanka.ru when:1d")
               + "&hl=ru&gl=RU&ceid=RU:ru"
    },
    {
        "name": "RT",
        "url": "https://news.google.com/rss/search?q="
               + urllib.parse.quote("site:rt.com Russia when:1d")
               + "&hl=ru&gl=RU&ceid=RU:ru"
    },
    {
        "name": "ТАСС",
        "url": "https://news.google.com/rss/search?q="
               + urllib.parse.quote("site:tass.ru when:1d")
               + "&hl=ru&gl=RU&ceid=RU:ru"
    },
    {
        "name": "РИА Новости",
        "url": "https://news.google.com/rss/search?q="
               + urllib.parse.quote("site:ria.ru when:1d")
               + "&hl=ru&gl=RU&ceid=RU:ru"
    }
]


def get_text(element, tag):
    found = element.find(tag)
    if found is not None and found.text:
        return found.text.strip()
    return ""


def load_rss(source):
    request = urllib.request.Request(
        source["url"],
        headers={
            "User-Agent": "Mozilla/5.0 TrueNewsBot/1.0"
        }
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        data = response.read()

    root = ET.fromstring(data)
    result = []

    for item in root.findall(".//item"):
        title = get_text(item, "title")
        link = get_text(item, "link")
        description = get_text(item, "description")
        pub_date = get_text(item, "pubDate")

        if not title or not link:
            continue

        result.append({
            "title": title,
            "link": link,
            "description": description,
            "source": source["name"],
            "pub": pub_date
        })

    return result



def generate_ai_article(item):
    """Generate an article through Hugging Face Inference Providers."""
    api_key = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not api_key:
        print("HF_TOKEN не задан — ИИ-статья пропущена")
        return ""

    prompt = (
        "Напиши на русском нейтральную информационную статью для новостного сайта TrueNews. "
        "Используй только факты из заголовка и описания. Ничего не выдумывай; если данных мало, "
        "так и напиши. Верни только HTML-фрагмент без markdown и без тегов html/body. "
        "Используй теги p, h3, ul, li. Структура: Что произошло, Контекст, Почему это важно, "
        "Что известно сейчас, Что дальше. Объём примерно 250–450 слов.\n\n"
        f"Заголовок: {item.get('title', '')}\n"
        f"Описание: {item.get('description', '')}\n"
        f"Источник: {item.get('source', '')}\n"
    )

    # Hugging Face Router is OpenAI-compatible. The selected model may change;
    # the second model is a fallback if the first one is temporarily unavailable.
    models = [
        "Qwen/Qwen2.5-7B-Instruct:fastest",
        "meta-llama/Llama-3.1-8B-Instruct:fastest",
    ]

    last_error = None
    for model in models:
        try:
            data = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": "Ты редактор новостного сайта TrueNews."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 900,
                "stream": False,
            }, ensure_ascii=False).encode("utf-8")

            req = urllib.request.Request(
                "https://router.huggingface.co/v1/chat/completions",
                data=data,
                headers={
                    "Authorization": "Bearer " + api_key,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as response:
                result = json.loads(response.read().decode("utf-8"))

            content = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if content:
                return content.strip()
            last_error = "пустой ответ модели"
        except Exception as error:
            last_error = error
            print(f"Модель {model}: ошибка: {error}")

    print(f"Hugging Face: не удалось создать статью: {last_error}")
    return ""

def main():
    all_news = []

    for source in SOURCES:
        try:
            news = load_rss(source)
            all_news.extend(news)
            print(f'{source["name"]}: получено {len(news)} новостей')
        except Exception as error:
            print(f'{source["name"]}: ошибка: {error}')

    # Убираем дубликаты
    unique = {}
    for item in all_news:
        key = item["title"].strip().lower()

        if key and key not in unique:
            unique[key] = item

    all_news = list(unique.values())

    # Самые свежие сначала
    all_news.sort(
        key=lambda x: x.get("pub", ""),
        reverse=True
    )

    # Оставляем максимум 40 новостей
    all_news = all_news[:40]

    for index, item in enumerate(all_news, 1):
        try:
            item["ai_article"] = generate_ai_article(item)
            print(f"ИИ-статья {index}/{len(all_news)} готова")
        except Exception as error:
            item["ai_article"] = ""
            print(f"ИИ-статья {index}: ошибка: {error}")

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "count": len(all_news),
        "news": all_news
    }

    output_file = Path("news.json")

    output_file.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print()
    print(f"TrueNews: сохранено {len(all_news)} новостей")
    print(f"Файл: {output_file}")


if __name__ == "__main__":
    main()
