#!/bin/sh
# Railway cron entrypoint (NOT a web service — Vercel serves the site).
#
# Each scheduled tick:
#   1. Seed /app/data/news.db on first boot (from /app/news/seed.db)
#   2. Run cron_pipeline.py — Bluesky crawl → generate → render → git push
#   3. Exit (Railway will re-invoke on the next cron tick)
set -e

mkdir -p /app/data

if [ ! -f /app/data/news.db ] && [ -f /app/news/seed.db ]; then
  echo "[entrypoint] seeding /app/data/news.db from /app/news/seed.db"
  cp /app/news/seed.db /app/data/news.db
fi

cd /app/news
exec python cron_pipeline.py
