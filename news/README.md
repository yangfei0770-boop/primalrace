# breaking news

新闻评论站，自动从 Bluesky 抓主流媒体新闻，用 Gemma 4 31B（Ollama Cloud）按
《原初种族》(The Primal Race) 的哲学框架与费扬本人的写作风格生成中英双语评论。

部署目标：Railway → howtoraiseiq.com/news

## 文件结构

```
news/
├── serve.py              # Web server (binds $PORT)
├── entrypoint.sh         # Railway entrypoint — seeds db + renders + serves
├── Dockerfile            # Python 3.12-slim
├── railway.json          # Railway config
├── requirements.txt
├── .env                  # API keys (gitignored)
├── .env.example
│
├── db.py                 # SQLite layer (NEWS_DB env can override path)
├── llm.py                # provider abstraction (anthropic | ollama)
├── prompts/system.py     # 4-layer system prompt + book corpus
│
├── crawlers/bluesky.py   # Pull from accounts.txt → urls.txt
├── generate.py           # URL → fetch → LLM → row in db
├── render.py             # db → index.html (bilingual toggle)
├── admin.py              # list / show / publish / unpublish / edit / delete
├── backfill_translation.py  # zh-only rows → fill English
│
├── cron_pipeline.py      # crawl → generate → render (for daily cron)
│
├── accounts.txt          # Bluesky news handles
├── urls.txt              # Crawled URLs queue
└── seed.db               # Initial commentary set (for first-boot)
```

## Railway 部署

详见 [DEPLOY.md](DEPLOY.md)。
