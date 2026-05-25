# Deploy: Vercel (frontend) + Railway (cron worker)

## Architecture

```
       Bluesky news accounts
              ↓
      [Railway cron, daily]
              ↓
   crawl → generate → render → git push
              ↓
         GitHub repo
              ↓
   [Vercel auto-deploy on push]
              ↓
   howtoraiseiq.com + /news  (CDN edge)
```

Railway only runs the daily worker. Vercel serves all HTTP traffic.

## A. Vercel (frontend)

1. https://vercel.com/new → **Import** `yangfei0770-boop/primalrace`
2. Framework Preset: **Other** · Root: `./` · Build/Output: empty
3. Deploy → get a `*.vercel.app` URL, verify root + `/news/` work
4. **Settings → Domains** → Add `howtoraiseiq.com` and `www.howtoraiseiq.com`
5. Vercel shows DNS records to add. Use **option 2 (A + CNAME)** unless
   you've switched nameservers to Vercel.

### If you stay on GoDaddy's nameservers

In GoDaddy DNS:

| Type  | Name | Value                  |
|-------|------|------------------------|
| A     | @    | `76.76.21.21`          |
| CNAME | www  | `cname.vercel-dns.com` |

(Delete any old Railway-pointing CNAME/A/TXT records first.)

### If you switch nameservers to Vercel

GoDaddy → Domain → Nameservers → custom → `ns1.vercel-dns.com`,
`ns2.vercel-dns.com`. Vercel auto-creates A/CNAME for any domain attached to
a project. No record copying needed.

## B. Railway (cron worker)

The single Railway service runs `python cron_pipeline.py` on schedule.
It writes commentary into the volume-mounted `news.db`, then commits the
re-rendered `news/index.html` to the GitHub repo, which triggers Vercel.

### Settings

| Field                  | Value                              |
|------------------------|------------------------------------|
| Root Directory         | `/` (repo root)                    |
| Dockerfile             | auto-detected (`Dockerfile`)       |
| **Custom Start Command** | (leave empty — Dockerfile ENTRYPOINT runs cron_pipeline.py) |
| **Cron Schedule**      | `0 1 * * *` (daily 01:00 UTC ≈ 09:00 北京) |
| Healthcheck            | (leave empty — cron services don't need one) |
| Restart Policy         | `Never`                            |

### Volume

Mount path: `/app/data` · Size: 1 GB

### Environment Variables

| Key                | Value                                       |
|--------------------|---------------------------------------------|
| `PROVIDER`         | `ollama`                                    |
| `OLLAMA_BASE_URL`  | `https://ollama.com`                        |
| `OLLAMA_API_KEY`   | `<your Ollama Cloud key>`                   |
| `OLLAMA_MODEL`     | `gemma4:31b-cloud`                          |
| `NEWS_DB`          | `/app/data/news.db`                         |
| `PUBLISH_NEW`      | `1`                                         |
| `GITHUB_TOKEN`     | `<your PAT with `repo` scope>`              |
| `GITHUB_REPO`      | `yangfei0770-boop/primalrace`               |
| `GIT_USER_EMAIL`   | `bot@howtoraiseiq.com`                      |
| `GIT_USER_NAME`    | `breaking-news-bot`                         |

### One-time test

In Railway service → **Deployments → trigger redeploy now** — bypasses
the cron schedule. Watch logs:
- `[1/4] Bluesky crawl` → URLs appended to urls.txt
- `[2/4] Generate commentary` → new rows in db
- `[3/4] Render` → news/index.html rewritten
- `[4/4] Push to GitHub` → commit appears in repo
- Vercel picks it up automatically — site refreshes

### Local dry-run (no push)

```bash
cd news
SKIP_PUSH=1 SKIP_CRAWL=1 python3 cron_pipeline.py
```

## C. Cleanup if you migrated from the old all-on-Railway setup

If you previously had Railway serving the site:

1. Railway service → Settings → **Networking** → remove any
   `*.howtoraiseiq.com` custom domains
2. Settings → **Deploy** → set Cron Schedule + Restart Policy as above
3. Delete the old Railway-generated `*.up.railway.app` from any place it's
   linked (it'll still work but isn't the public URL anymore)
