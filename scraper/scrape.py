"""Собирает новые объявления с autoplius.lt и autogidas.lt и сливает их в docs/listings.json.

Оба сайта закрыты защитой от ботов, поэтому используется настоящий браузер (Playwright).
Запуск:  python scraper/scrape.py [--headed]
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scraper" / "config.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "listings.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


# ---------- парсеры страниц (выполняются в браузере) ----------

JS_AUTOPLIUS = """() => [...document.querySelectorAll('a.announcement-item')].map(a => ({
  url: a.href,
  title: a.querySelector('.announcement-title')?.innerText,
  price: a.querySelector('.announcement-pricing-info strong')?.innerText,
  params: [...a.querySelectorAll('.announcement-parameters span')].map(s => s.innerText),
  image: a.querySelector('img.js-gallery-main-photo')?.src,
  posted: a.querySelector('.badge-new')?.innerText,
}))"""

JS_AUTOGIDAS = """() => [...document.querySelectorAll('.article-item')].map(d => {
  const a = d.querySelector('a.item-link');
  return a && {
    url: a.href,
    title: d.querySelector('.item-title')?.innerText,
    price: d.querySelector('.item-price')?.innerText,
    params: [...d.querySelectorAll('.parameter-value')].map(s => s.innerText),
    image: d.querySelector('img.js-image')?.src,
    posted: d.querySelector('.badge')?.dataset.badge,
  };
}).filter(Boolean)"""


def page_url(url, n):
    if n == 1:
        return url
    p = urlparse(url)
    q = dict(parse_qsl(p.query, keep_blank_values=True))
    q["page_nr" if "autoplius" in p.netloc else "page"] = str(n)
    return urlunparse(p._replace(query=urlencode(q)))


def normalize(source, raw, search_name):
    url = raw["url"]
    m = re.search(r"(\d{6,})\.html", url)
    if not m:
        return None
    params = [clean(p) for p in raw.get("params", []) if clean(p) and not re.fullmatch(r"\d{1,2}|VIN", clean(p))]
    location = next((p for p in reversed(params) if re.search(r"Lietuva|^[A-ZŠŽČĄĘĖĮŲŪ][a-ząčęėįšųūž]+( r\.| sav\.)?$", p)), "")
    return {
        "id": f"{source}-{m.group(1)}",
        "source": source,
        "search": search_name,
        "url": url,
        "title": clean(raw.get("title")),
        "price": clean(raw.get("price")),
        "params": params,
        "location": location,
        "image": raw.get("image") or "",
        "posted": clean(raw.get("posted")),
    }


def wait_for_listings(page, selector, timeout=45):
    """Ждём, пока исчезнет Cloudflare-проверка и появятся объявления."""
    end = time.time() + timeout
    while time.time() < end:
        if page.query_selector(selector):
            return True
        time.sleep(1)
    return False


def scrape_source(ctx, source, js, selector):
    found = []
    page = ctx.new_page()
    for search in CONFIG["sources"].get(source, []):
        for n in range(1, CONFIG["max_pages"] + 1):
            url = page_url(search["url"], n)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                if not wait_for_listings(page, selector):
                    print(f"[{source}] нет объявлений (блокировка?): {url}")
                    break
                page.wait_for_timeout(1500)
                for raw in page.evaluate(js):
                    item = normalize(source, raw, search["name"])
                    if item:
                        found.append(item)
                print(f"[{source}] {search['name']} стр.{n}: всего {len(found)}")
            except Exception as e:  # один сбой не должен ронять весь запуск
                print(f"[{source}] ошибка {url}: {e}")
                break
    page.close()
    return found


def load_env():
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def notify_telegram(items):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat and items):
        return
    def send(text):
        data = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "false"}).encode()
        try:
            urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=20)
        except Exception as e:
            print("telegram: ошибка", e)
    for i in items[:10]:
        send(f"🚗 {i['title']} — {i['price']}\n{' · '.join(i['params'][:5])}\n[{i['source']}] {i['url']}")
    if len(items) > 10:
        send(f"…и ещё {len(items) - 10} новых объявлений в приложении")


def main():
    load_env()
    headed = "--headed" in sys.argv
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    old = {}
    if OUT.exists():
        try:
            old = {i["id"]: i for i in json.loads(OUT.read_text(encoding="utf-8"))["listings"]}
        except Exception:
            pass

    fresh = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="lt-LT", viewport={"width": 1366, "height": 900})
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        fresh += scrape_source(ctx, "autoplius", JS_AUTOPLIUS, "a.announcement-item")
        fresh += scrape_source(ctx, "autogidas", JS_AUTOGIDAS, ".article-item")
        browser.close()

    new_count, new_items, first_run = 0, [], not old
    for item in fresh:
        if item["id"] in old:
            first = old[item["id"]]["first_seen"]
        else:
            first, new_count = now, new_count + 1
            new_items.append(item)
        item["first_seen"] = first
        old[item["id"]] = item

    listings = sorted(old.values(), key=lambda i: i["first_seen"], reverse=True)[: CONFIG["keep_listings"]]
    data = {
        "updated": now,
        "facebook_searches": CONFIG.get("facebook_searches", []),
        "listings": listings,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    if not first_run:  # при первом запуске не спамим всей базой
        notify_telegram(new_items)
    print(f"Готово: собрано {len(fresh)}, новых {new_count}, всего в базе {len(listings)}")
    if not fresh:
        sys.exit(1)


if __name__ == "__main__":
    main()
