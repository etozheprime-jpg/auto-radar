#!/usr/bin/env bash
# Локальный запуск (домашний IP обходит защиту сайтов лучше, чем GitHub Actions)
set -e
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv; .venv/bin/pip install -r scraper/requirements.txt; .venv/bin/playwright install chromium; }
.venv/bin/python scraper/scrape.py --headed
if [ "$1" = "--push" ]; then git add docs/listings.json && (git diff --staged --quiet || git commit -m "data: update listings" && git push); fi
