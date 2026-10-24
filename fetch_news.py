#!/usr/bin/env python3
"""Собирает RSS-ленты и пишет news.json. Только стандартная библиотека."""
import json, re, html, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

GN = "https://news.google.com/rss/search?q=site:fontanka.ru+when:2d&hl=ru&gl=RU&ceid=RU:ru"
SOURCES = [
    {"id": "rbc",  "name": "РБК",      "urls": ["https://rssexport.rbc.ru/rbcnews/news/30/full.rss"]},
    # Фонтанка: пробуем официальные ленты, в крайнем случае — Google News по сайту
    {"id": "fon",  "name": "Фонтанка", "urls": ["https://www.fontanka.ru/fontanka.rss",
                                                "https://www.fontanka.ru/rss.xml", GN]},
    {"id": "rt",   "name": "RT",       "urls": ["https://russian.rt.com/rss"]},
    {"id": "dzen", "name": "Дзен",     "urls": ["https://dzen.ru/news/rss"]},
]
PER_SOURCE = 30
NS = {"media": "http://search.yahoo.com/mrss/"}
UA = {"User-Agent": "Mozilla/5.0 (compatible; TrueNewsBot/1.0)"}


def clean(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]*>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def find_img(it):
    enc = it.find("enclosure")
    if enc is not None:
        u, t = enc.get("url", ""), enc.get("type", "")
        if t.startswith("image") or re.search(r"\.(jpe?g|png|webp)(\?|$)", u, re.I):
            return u
    for tag in ("media:content", "media:thumbnail"):
        el = it.find(tag, NS)
        if el is not None and el.get("url"):
            return el.get("url")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', html.unescape(it.findtext("description") or ""))
    return m.group(1) if m else ""


def parse_date(s):
    try:
        d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def fetch_url(src, url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        root = ET.fromstring(r.read())
    out = []
    for it in root.iter("item"):
        title = clean(it.findtext("title"))
        # у Google News в конце заголовка « - Название сайта»
        title = re.sub(r"\s+-\s+Фонтанка(\.ру)?$", "", title)
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        tags = [clean(c.text) for c in it.findall("category") if c.text]
        out.append({
            "id": src["id"], "src": src["name"], "title": title, "link": link,
            "text": clean(it.findtext("description"))[:300],
            "img": find_img(it),
            "tags": tags[:6],
            "t": parse_date(it.findtext("pubDate")).isoformat(),
        })
        if len(out) >= PER_SOURCE:
            break
    if not out:
        raise ValueError("пустая лента")
    return out


def fetch(src):
    last = None
    for url in src["urls"]:
        try:
            return fetch_url(src, url)
        except Exception as e:
            last = e
            print(f"     {src['name']}: {url} -> {e}")
    raise last


def main():
    try:
        old = json.load(open("news.json", encoding="utf-8")).get("items", [])
    except Exception:
        old = []
    items = []
    for s in SOURCES:
        try:
            got = fetch(s)
            print(f"OK   {s['name']}: {len(got)}")
        except Exception as e:
            got = [x for x in old if x.get("id") == s["id"]]  # оставляем прошлые
            print(f"FAIL {s['name']}: {e} (оставлено {len(got)})")
        items += got
    items.sort(key=lambda x: x["t"], reverse=True)
    json.dump({"updated": datetime.now(timezone.utc).isoformat(), "items": items},
              open("news.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
