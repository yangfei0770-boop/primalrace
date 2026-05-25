# Deploy: Vercel (static frontend) + GitHub Actions (daily cron)

零成本部署。GitHub Actions 每天跑 cron 生成评论 → commit → Vercel 自动 deploy。

```
Bluesky 新闻账号
      ↓
[GitHub Actions, daily 01:00 UTC]
      ↓
crawl → generate (Ollama Cloud) → render → commit
      ↓
   GitHub repo
      ↓
[Vercel auto-deploy]
      ↓
howtoraiseiq.com  +  /news/
```

## A. Vercel 部署（5 分钟）

1. https://vercel.com/new → 用 GitHub 登录 → **Import** `yangfei0770-boop/primalrace`
2. Framework Preset: **Other** · Root Directory: `./` · Build/Output 留空
3. **Deploy**
4. 验证 `*.vercel.app` 临时域名能打开根页和 `/news/`

### 自定义域名

Vercel 项目 → **Settings → Domains** → Add `howtoraiseiq.com` 和 `www.howtoraiseiq.com`。

如果 nameservers 还在 GoDaddy，按 Vercel 提示在 GoDaddy DNS 加：

| Type  | Name | Value                  |
|-------|------|------------------------|
| A     | @    | `76.76.21.21`          |
| CNAME | www  | `cname.vercel-dns.com` |

如果把 nameservers 切到 Vercel，不用加任何 DNS record——Vercel 自动管。

## B. GitHub Actions 配置（2 分钟）

### 1. 加 Secret

GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**：

```
Name:  OLLAMA_API_KEY
Value: <你的 Ollama Cloud key>
```

### 2. 验证 workflow

Actions tab → **Daily news commentary** → 右上角 **Run workflow** 手动触发一次。

跑完 ~3-5 分钟，应该看到：
- crawl 拿到新 URL
- generate 写入 news.db
- render 刷新 news/index.html
- commit + push（如果有 diff）

Vercel 检测到 push 后秒级 redeploy。

## C. 调度

默认 `0 1 * * *`（每天 UTC 01:00）。改时间编辑 `.github/workflows/cron.yml` 的 cron 表达式。

## D. 本地试跑

```bash
cd news
SKIP_CRAWL=1 SKIP_PUSH=1 python3 cron_pipeline.py
```

或者只跑生成 + 渲染（不抓 Bluesky）：

```bash
cd news
python3 generate.py "<某条新闻 URL>"
python3 render.py
```

## E. 数据持久化

`news/news.db` 是 git 跟踪的——每次 GitHub Actions 跑完 commit 回 repo。
本地 clone 下来就有完整数据，rollback 也能回到任何一天的状态。

文件大概每天涨 5-10KB。半年后可以 squash history 控制 repo 大小。
