# Auto Radar — PWA с новыми объявлениями

Скрапер (Python + Playwright) собирает новые объявления с **autoplius.lt** и **autogidas.lt**,
пишет их в `docs/listings.json`, а PWA из `docs/` показывает всё в одной ленте (GitHub Pages).

## Запуск локально
```bash
./run_local.sh            # собрать объявления (откроется окно браузера — это нужно для Cloudflare)
./run_local.sh --push     # собрать и запушить в GitHub
cd docs && python3 -m http.server 8000   # посмотреть PWA
```

## Выкладка на GitHub
1. Создать репозиторий, `git remote add origin ...`, `git push -u origin main`.
2. Settings → Pages → Source: *Deploy from a branch*, ветка `main`, папка `/docs`.
3. Открыть сайт на телефоне → «Добавить на экран» — это и есть PWA.
4. `.github/workflows/scrape.yml` можно запустить вручную (Actions → Run workflow).
   Сайты блокируют IP GitHub (проверено), поэтому по расписанию запускайте `./run_local.sh --push` с Mac по cron/launchd.

## Настройка поисков
`scraper/config.json` — впишите свои URL фильтров (марка, цена, год) с сайтов.

## Facebook Marketplace
Автоматически не парсится (логин + запрет в ToS + бан аккаунта). В ленте показываются ссылки на сохранённые
поиски из `facebook_searches` — открываются в Facebook одним тапом.

## Известные ограничения
- autogidas: страница 2 пока не собирается (нужно уточнить пагинацию), берётся только первая.
- Селекторы привязаны к текущей вёрстке сайтов; при редизайне правятся в `scraper/scrape.py`.

## Telegram-уведомления
1. В Telegram напишите @BotFather → `/newbot` → получите токен.
2. Напишите своему боту любое сообщение, затем откройте `https://api.telegram.org/bot<TOKEN>/getUpdates` и найдите `chat.id`.
3. Локально: создайте файл `.env` (в git не попадает):
   ```
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_CHAT_ID=...
   ```
4. В GitHub: Settings → Secrets and variables → Actions → добавьте те же два секрета.
Уведомления приходят только о новых объявлениях (первый запуск молчит, чтобы не засыпать вас).
