# Deploy to Railway

## 1. 推到 GitHub

```bash
cd /Users/yang/Desktop/blog
git add news/ .gitignore
git commit -m "Add breaking news app"
git push origin main
```

## 2. 在 Railway 创建项目

1. 打开 [railway.app/new](https://railway.app/new)
2. **Deploy from GitHub repo** → 选 `yangfei0770-boop/primalrace`
3. Railway 自动探测 `news/Dockerfile`
4. 在 **Settings → Service** 设：
   - **Root Directory**: `news`
   - **Build Command**: 留空（Dockerfile 接管）
   - **Start Command**: 留空（Dockerfile 的 ENTRYPOINT 接管）

## 3. 配置环境变量

**Settings → Variables**：

| Key              | Value                                       |
|------------------|---------------------------------------------|
| `PROVIDER`       | `ollama`                                    |
| `OLLAMA_BASE_URL`| `https://ollama.com`                        |
| `OLLAMA_API_KEY` | `<你的 Ollama Cloud key>`                   |
| `OLLAMA_MODEL`   | `gemma4:31b-cloud`                          |
| `PUBLISH_NEW`    | `1`                                         |
| `NEWS_DB`        | `/app/data/news.db`                         |

> `PORT` 是 Railway 自动注入的，不要手动设。

## 4. 添加持久 Volume

**Settings → Volumes**：
- **Mount path**: `/app/data`
- **Size**: 1 GB 就够（每条评论 < 5KB）

这样 news.db 在 redeploy 后不丢；首次启动时 `entrypoint.sh` 会从镜像里
的 `seed.db` 拷过来。

## 5. 部署 + 拿到 URL

Railway 自动构建并给你一个 `*.up.railway.app` 域名。点 **View** 验证。
浏览器右上有 中文/EN 切换。

## 6. 加每日 cron 服务（可选但推荐）

在同一个 Railway project 里 **+ New → Empty Service → Connect 同一个 repo**：

- **Root Directory**: `news`
- **Cron Schedule**: `0 1 * * *`（每天 UTC 01:00，对应北京时间 09:00）
- **Start Command**: `python cron_pipeline.py`
- 共享同一份环境变量 + Volume
- 共享同一份 Volume 是关键 —— web service 和 cron service 都要挂到 `/app/data`

每天会自动：
1. 从 Bluesky 抓最新新闻 URL
2. 生成中英双语评论
3. 重渲染 index.html（web service 下次启动会再渲染一次；或者重启 web service）

## 7. 自定义域名 howtoraiseiq.com/news

两种做法：

**A. 子域名（最简单）** — 把 `news.howtoraiseiq.com` 指向 Railway：
1. Railway **Settings → Networking → Custom Domain** → 输入 `news.howtoraiseiq.com`
2. 在你的 DNS 提供商加一条 CNAME 指向 Railway 给的目标

**B. 子路径 `/news`（更复杂）** — 需要在 howtoraiseiq.com 的反向代理（Nginx /
Cloudflare Workers）里把 `/news` 路径转发到 Railway URL。如果 howtoraiseiq.com
本身就在 Cloudflare 上，用 Cloudflare Workers 最快。

## 故障排查

```bash
# 看实时日志
railway logs              # 装 CLI 后

# 或者在 Railway 后台 → Deployments → 点最新一次 → View logs

# DB 状态检查（在 Railway shell 里）
python -c "from db import connect; print(list(connect().execute('SELECT COUNT(*) FROM articles')))"
```

如果首次部署没有看到 42 条种子评论，检查：
- Volume 挂载路径是 `/app/data`
- `seed.db` 文件在镜像里存在（`docker run ... ls -la /app/seed.db`）
- entrypoint.sh 有执行权限（Dockerfile 的 `chmod +x` 应该处理了）
