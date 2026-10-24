#!/usr/bin/env python3
"""Собирает RSS-ленты и пишет news.json. Только стандартная библиотека."""
import json, re, html, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

def gn(q):
    """Лента Google News по запросу (запасной вариант, когда у сайта нет своего RSS)."""
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:2d")
            + "&hl=ru&gl=RU&ceid=RU:ru")


SOURCES = [
    # Общероссийские (родная лента, при сбое — Google News по сайту)
    {"id": "rbc",  "name": "РБК",         "urls": ["https://rssexport.rbc.ru/rbcnews/news/30/full.rss", gn("site:rbc.ru")]},
    {"id": "tass", "name": "ТАСС",        "urls": ["https://tass.ru/rss/v2.xml", gn("site:tass.ru")]},
    {"id": "ria",  "name": "РИА Новости", "urls": ["https://ria.ru/export/rss2/archive/index.xml", gn("site:ria.ru")]},
    {"id": "lenta", "name": "Лента.ру",   "urls": ["https://lenta.ru/rss/news", gn("site:lenta.ru")]},
    {"id": "kom",  "name": "Коммерсантъ", "urls": ["https://www.kommersant.ru/RSS/news.xml", gn("site:kommersant.ru")]},
    {"id": "iz",   "name": "Известия",    "urls": ["https://iz.ru/xml/rss/all.xml", gn("site:iz.ru")]},
    {"id": "intf", "name": "Интерфакс",   "urls": ["https://www.interfax.ru/rss.asp", gn("site:interfax.ru")]},
    {"id": "ved",  "name": "Ведомости",   "urls": ["https://www.vedomosti.ru/rss/news", gn("site:vedomosti.ru")]},
    {"id": "gaz",  "name": "Газета.ру",   "urls": ["https://www.gazeta.ru/export/rss/lenta.xml", gn("site:gazeta.ru")]},
    {"id": "rt",   "name": "RT",          "urls": ["https://russian.rt.com/rss", gn("site:russian.rt.com")]},
    {"id": "bbc",  "name": "BBC Русская служба", "urls": ["https://feeds.bbci.co.uk/russian/rss.xml"]},
    {"id": "dzen", "name": "Дзен",        "urls": ["https://dzen.ru/news/rss"]},
    # Петербург
    {"id": "fon",  "name": "Фонтанка",    "urls": ["https://www.fontanka.ru/fontanka.rss",
                                                    "https://www.fontanka.ru/rss.xml",
                                                    gn("site:fontanka.ru")]},
    {"id": "n78",  "name": "78.ru",       "urls": [gn("site:78.ru")]},
    {"id": "moika", "name": "Мойка78",    "urls": [gn("site:moika78.ru")]},
    {"id": "spbd", "name": "Петербургский дневник", "urls": [gn("site:spbdnevnik.ru")]},
    {"id": "rosb", "name": "Росбалт",     "urls": ["https://www.rosbalt.ru/feed/", gn("site:rosbalt.ru")]},
    {"id": "neva", "name": "Neva.Today",  "urls": [gn("site:neva.today")]},
    # Спорт
    {"id": "champ", "name": "Чемпионат",  "urls": ["https://www.championat.com/rss/news/", gn("site:championat.com")]},
    {"id": "sports", "name": "Sports.ru", "urls": ["https://www.sports.ru/rss/all_news.xml", gn("site:sports.ru")]},
]
PER_SOURCE = 60
TOTAL_MAX = 700  # максимум новостей в news.json
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
        if "news.google.com" in url:
            title = re.sub(r"\s+-\s+[^-]{2,40}$", "", title)
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


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_rates(old):
    """USD/EUR (ЦБ РФ), Brent и BTC. v — текущее значение, p — предыдущее (для индикатора роста/падения)."""
    rates = dict(old)  # если что-то не загрузилось — остаётся прошлое значение

    try:
        v = get_json("https://www.cbr-xml-daily.ru/daily_json.js")["Valute"]
        for key, code in (("usd", "USD"), ("eur", "EUR")):
            rates[key] = {"v": v[code]["Value"], "p": v[code]["Previous"]}
        print("OK   курсы ЦБ")
    except Exception as e:
        print(f"FAIL курсы ЦБ: {e}")

    try:
        j = get_json("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true")["bitcoin"]
        rates["btc"] = {"v": j["usd"], "p": j["usd"] / (1 + (j.get("usd_24h_change") or 0) / 100)}
        print("OK   BTC (CoinGecko)")
    except Exception as e:
        print(f"     BTC CoinGecko: {e}")
        try:
            j = get_json("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT")
            rates["btc"] = {"v": float(j["lastPrice"]), "p": float(j["openPrice"])}
            print("OK   BTC (Binance)")
        except Exception as e2:
            print(f"FAIL BTC: {e2}")

    try:
        j = get_json("https://query1.finance.yahoo.com/v8/finance/chart/BZ=F?range=5d&interval=1d")["chart"]["result"][0]
        closes = [c for c in j["indicators"]["quote"][0]["close"] if c is not None]
        v = j["meta"].get("regularMarketPrice") or closes[-1]
        rates["brent"] = {"v": v, "p": closes[-2] if len(closes) > 1 else v}
        print("OK   Brent (Yahoo)")
    except Exception as e:
        print(f"     Brent Yahoo: {e}")
        try:
            req = urllib.request.Request("https://stooq.com/q/l/?s=cb.f&f=sd2t2ohlcv&h&e=csv", headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                row = r.read().decode("utf-8").strip().splitlines()[1].split(",")
            rates["brent"] = {"v": float(row[6]), "p": float(row[3])}  # закрытие и открытие дня
            print("OK   Brent (Stooq)")
        except Exception as e2:
            print(f"FAIL Brent: {e2}")

    return rates


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
    # убираем дубли по заголовку, свежие сначала
    seen, uniq = set(), []
    for x in sorted(items, key=lambda x: x["t"], reverse=True):
        k = re.sub(r"\W+", "", x["title"].lower())
        if k and k not in seen:
            seen.add(k)
            uniq.append(x)
    items = uniq[:TOTAL_MAX]
    json.dump({"updated": datetime.now(timezone.utc).isoformat(), "items": items},
              open("news.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    try:
        old_rates = json.load(open("rates.json", encoding="utf-8")).get("rates", {})
    except Exception:
        old_rates = {}
    json.dump({"updated": datetime.now(timezone.utc).isoformat(), "rates": fetch_rates(old_rates)},
              open("rates.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
