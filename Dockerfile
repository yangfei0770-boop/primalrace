FROM python:3.12-slim

WORKDIR /app

# system deps for lxml / trafilatura, plus git for the cron's push step
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libxml2-dev libxslt1-dev git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# install Python deps from news/ requirements first (better layer caching)
COPY news/requirements.txt /app/news/requirements.txt
RUN pip install --no-cache-dir -r /app/news/requirements.txt

# copy everything (respects .dockerignore)
COPY . /app

RUN chmod +x /app/entrypoint.sh

# news.db lives on a Railway-mounted volume so it survives redeploys.
# Configure Volume mount at /app/data in the Railway dashboard.
ENV NEWS_DB=/app/data/news.db

ENTRYPOINT ["/app/entrypoint.sh"]
