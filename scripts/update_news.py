import json
import urllib.request
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
