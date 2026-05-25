#!/bin/sh
# Single-service Railway entrypoint:
#   1. Seed news.db on first boot (from /app/news/seed.db if present)
#   2. Re-render news/index.html from the persistent db
#   3. Serve the entire blog/ directory (book page + /news/ + PDF) on $PORT
set -e

mkdir -p /app/data

if [ ! -f /app/data/news.db ] && [ -f /app/news/seed.db ]; then
  echo "[entrypoint] seeding /app/data/news.db from /app/news/seed.db"
  cp /app/news/seed.db /app/data/news.db
fi

# Make sure schema exists (no-op if already created), then render
cd /app/news
python -c "from db import connect; connect().close()"
python render.py || echo "[entrypoint] render failed; serving stale index.html"

# Serve from blog root so / serves the book and /news/ serves commentary
cd /app
exec python serve.py
