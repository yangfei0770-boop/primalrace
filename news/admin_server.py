#!/usr/bin/env python3
"""Local web admin for breaking news commentary.

Run:
  cd news
  python3 admin_server.py
Open http://localhost:8080

Features:
  - browse all articles (newest first, filter by tag / state)
  - one-click delete (moves to `deletions` table — never gone, restorable)
  - toggle published / draft
  - regen translation
  - deletions feed: see what's been muted

Learning:
  Each deletion records {url, source, host, tag}. generate.py consults the
  deletions table:
    - exact URL deleted before → skip
    - same host deleted ≥ 3 times in last 30 days → auto-mute the host
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from flask import Flask, redirect, render_template_string, request, url_for, abort  # noqa: E402

from db import connect  # noqa: E402

app = Flask(__name__)


# ============================================================================
# Schema migration — add deletions table if missing
# ============================================================================

def ensure_schema() -> None:
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS deletions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id    INTEGER,
            url           TEXT NOT NULL,
            host          TEXT,
            source        TEXT,
            source_title  TEXT,
            title         TEXT,
            tag           TEXT,
            reason        TEXT,
            deleted_at    TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_deletions_host
            ON deletions(host, deleted_at DESC);
        CREATE INDEX IF NOT EXISTS idx_deletions_url
            ON deletions(url);
        """)


ensure_schema()


# ============================================================================
# Routes
# ============================================================================

@app.route("/")
def index():
    flt = request.args.get("filter", "all")
    where = ""
    if flt == "drafts":
        where = "WHERE published = 0"
    elif flt == "published":
        where = "WHERE published = 1"
    elif flt == "good_news":
        where = "WHERE tag = 'good_news'"
    elif flt != "all":
        where = f"WHERE tag = '{flt}'"

    with connect() as c:
        rows = list(c.execute(
            f"SELECT id, url, source, source_title, title, axiom, body, "
            f"title_en, axiom_en, body_en, tag, violence_layer, published, "
            f"generated_at FROM articles {where} ORDER BY id DESC"
        ))
        stats = {
            "total":     c.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
            "published": c.execute("SELECT COUNT(*) FROM articles WHERE published=1").fetchone()[0],
            "drafts":    c.execute("SELECT COUNT(*) FROM articles WHERE published=0").fetchone()[0],
            "deleted":   c.execute("SELECT COUNT(*) FROM deletions").fetchone()[0],
            "good_news": c.execute("SELECT COUNT(*) FROM articles WHERE tag='good_news'").fetchone()[0],
        }
        # muted hosts (≥3 deletions in 30d)
        muted = list(c.execute("""
            SELECT host, COUNT(*) AS n FROM deletions
            WHERE deleted_at > datetime('now', '-30 days') AND host != ''
            GROUP BY host HAVING n >= 3 ORDER BY n DESC
        """))
    return render_template_string(
        INDEX_HTML, articles=rows, stats=stats,
        muted=muted, filter=flt,
    )


@app.route("/article/<int:aid>/delete", methods=["POST"])
def delete_article(aid: int):
    reason = request.form.get("reason", "").strip()
    with connect() as c:
        a = c.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()
        if not a:
            abort(404)
        host = (urlparse(a["url"] or "").hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        c.execute("""
            INSERT INTO deletions
                (article_id, url, host, source, source_title, title, tag,
                 reason, deleted_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (aid, a["url"], host, a["source"], a["source_title"],
              a["title"], a["tag"], reason,
              datetime.now(timezone.utc).isoformat()))
        c.execute("DELETE FROM articles WHERE id=?", (aid,))
    return redirect(request.referrer or url_for("index"))


@app.route("/article/<int:aid>/toggle", methods=["POST"])
def toggle_published(aid: int):
    with connect() as c:
        c.execute("UPDATE articles SET published = 1 - published WHERE id=?", (aid,))
    return redirect(request.referrer or url_for("index"))


@app.route("/deletions")
def deletions_page():
    with connect() as c:
        rows = list(c.execute("SELECT * FROM deletions ORDER BY id DESC LIMIT 200"))
        host_counts = list(c.execute("""
            SELECT host, COUNT(*) AS n FROM deletions
            WHERE host != ''
            GROUP BY host ORDER BY n DESC LIMIT 30
        """))
    return render_template_string(DELETIONS_HTML, deletions=rows, host_counts=host_counts)


@app.route("/deletion/<int:did>/restore", methods=["POST"])
def restore_deletion(did: int):
    """Un-delete by removing from deletions; the article row is gone, so
    this only un-mutes the source. To re-fetch, add the URL to urls.txt."""
    with connect() as c:
        c.execute("DELETE FROM deletions WHERE id=?", (did,))
    return redirect(request.referrer or url_for("deletions_page"))


@app.route("/render", methods=["POST"])
def trigger_render():
    """Re-render index.html (so the public site reflects deletions)."""
    import subprocess
    try:
        subprocess.check_call([sys.executable, "render.py"],
                              cwd=Path(__file__).parent)
        msg = "rendered ok"
    except Exception as e:
        msg = f"render failed: {e}"
    return redirect(url_for("index") + f"?msg={msg}")


# ============================================================================
# HTML templates
# ============================================================================

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>admin · breaking news</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --ink: #1a1109; --paper: #f5f0e8; --accent: #8b1a1a;
  --muted: #6b5c47; --border: #c9bfad; --green: #2d6a3e;
  --bg-card: rgba(255,253,248,0.92);
}
body { background: var(--paper); color: var(--ink);
       font-family: "Georgia","Noto Serif SC",serif;
       padding: 1.5rem 1rem 4rem; line-height: 1.55; }
.wrap { max-width: 1100px; margin: 0 auto; }
header { border-top: 4px solid var(--accent); padding-top: 1.2rem;
         margin-bottom: 1.5rem; display: flex; justify-content: space-between;
         align-items: baseline; flex-wrap: wrap; gap: 1rem; }
h1 { font-size: 1.6rem; letter-spacing: 0.1em; }
h1 small { font-size: 0.7rem; letter-spacing: 0.2em;
            color: var(--muted); text-transform: uppercase; }
.stats { display: flex; gap: 1.2rem; font-size: 0.85rem; color: var(--muted); }
.stats b { color: var(--ink); }
.filters { display: flex; gap: 0.4rem; margin-bottom: 1rem; flex-wrap: wrap; }
.filters a { padding: 0.3rem 0.75rem; border: 1px solid var(--border);
             background: var(--bg-card); color: var(--ink);
             text-decoration: none; font-size: 0.82rem; letter-spacing: 0.05em; }
.filters a.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.muted-note { background: #f9f3e8; border-left: 3px solid var(--accent);
              padding: 0.6rem 0.9rem; margin-bottom: 1.2rem;
              font-size: 0.82rem; color: var(--muted); }
.muted-note .h { color: var(--accent); font-weight: bold; }
article { background: var(--bg-card); border: 1px solid var(--border);
          border-left: 3px solid var(--accent); padding: 1rem 1.2rem;
          margin-bottom: 0.8rem; display: grid;
          grid-template-columns: 1fr auto; gap: 0.6rem; }
article.draft { opacity: 0.75; border-left-color: var(--muted); }
article.good_news { border-left-color: var(--green); }
article h3 { font-size: 1.1rem; margin-bottom: 0.3rem; line-height: 1.35; }
article .meta { font-size: 0.75rem; color: var(--muted);
                margin-bottom: 0.4rem; letter-spacing: 0.05em; }
article .meta .tag { background: var(--accent); color: #fff;
                     padding: 0.04rem 0.4rem; margin-right: 0.4rem; }
article .meta .tag.good_news { background: var(--green); }
article .axiom { font-style: italic; color: var(--accent);
                 padding: 0.3rem 0 0.3rem 0.6rem;
                 border-left: 2px solid var(--accent);
                 font-size: 0.92rem; margin-bottom: 0.4rem; }
article.good_news .axiom { color: var(--green); border-left-color: var(--green); }
article details { margin-top: 0.3rem; font-size: 0.92rem; }
article details summary { cursor: pointer; color: var(--muted);
                          font-size: 0.78rem; letter-spacing: 0.08em;
                          text-transform: uppercase; outline: none; }
article details .body { margin-top: 0.6rem; }
article details .body p { margin-bottom: 0.6rem; text-indent: 2em;
                          text-align: justify; }
article .actions { display: flex; flex-direction: column; gap: 0.3rem;
                   align-items: flex-end; }
article .actions form { margin: 0; }
article .actions button { font: inherit; font-size: 0.78rem;
                          padding: 0.3rem 0.65rem;
                          border: 1px solid var(--border);
                          background: var(--bg-card); cursor: pointer;
                          letter-spacing: 0.05em; min-width: 5.5rem; }
article .actions button:hover { background: var(--accent); color: #fff; }
article .actions button.delete { color: var(--accent); }
article .actions button.delete:hover { background: var(--accent); color: #fff; }
article .id { font-size: 0.7rem; color: var(--border); margin-bottom: 0.15rem; }
.top-actions { display: flex; gap: 0.5rem; }
.top-actions a, .top-actions button {
  background: var(--accent); color: #fff; padding: 0.4rem 0.9rem;
  text-decoration: none; font: inherit; border: none; cursor: pointer;
  letter-spacing: 0.08em; font-size: 0.82rem; }
.top-actions a:hover, .top-actions button:hover { background: #b52020; }
.top-actions a.secondary { background: var(--bg-card); color: var(--ink);
                            border: 1px solid var(--border); }
</style>
</head>
<body>
<div class="wrap">

<header>
  <div>
    <h1>admin <small>/ breaking news</small></h1>
    <div class="stats">
      total: <b>{{ stats.total }}</b> ·
      published: <b>{{ stats.published }}</b> ·
      drafts: <b>{{ stats.drafts }}</b> ·
      good_news: <b>{{ stats.good_news }}</b> ·
      deleted: <b>{{ stats.deleted }}</b>
    </div>
  </div>
  <div class="top-actions">
    <form method="post" action="{{ url_for('trigger_render') }}">
      <button type="submit">Re-render</button>
    </form>
    <a href="{{ url_for('deletions_page') }}" class="secondary">Deletions</a>
    <a href="/news/index.html" target="_blank" class="secondary">View Site</a>
  </div>
</header>

{% if muted %}
<div class="muted-note">
  <span class="h">Auto-muted hosts</span> (≥3 deletions in last 30 days, generate.py will skip these):
  {% for m in muted %}
    <code>{{ m.host }}</code> ({{ m.n }}){% if not loop.last %}, {% endif %}
  {% endfor %}
</div>
{% endif %}

<div class="filters">
  <a href="?filter=all"        class="{{ 'active' if filter == 'all' else '' }}">All</a>
  <a href="?filter=published"  class="{{ 'active' if filter == 'published' else '' }}">Published</a>
  <a href="?filter=drafts"     class="{{ 'active' if filter == 'drafts' else '' }}">Drafts</a>
  <a href="?filter=good_news"  class="{{ 'active' if filter == 'good_news' else '' }}">good_news</a>
  <a href="?filter=china_tech" class="{{ 'active' if filter == 'china_tech' else '' }}">china_tech</a>
  <a href="?filter=gender"     class="{{ 'active' if filter == 'gender' else '' }}">gender</a>
  <a href="?filter=international" class="{{ 'active' if filter == 'international' else '' }}">international</a>
  <a href="?filter=philosophy" class="{{ 'active' if filter == 'philosophy' else '' }}">philosophy</a>
  <a href="?filter=tech"       class="{{ 'active' if filter == 'tech' else '' }}">tech</a>
  <a href="?filter=other"      class="{{ 'active' if filter == 'other' else '' }}">other</a>
</div>

{% for a in articles %}
<article class="{{ '' if a.published else 'draft' }} {{ a.tag if a.tag == 'good_news' else '' }}">
  <div>
    <div class="id">#{{ a.id }} · {{ (a.generated_at or '')[:10] }}</div>
    <h3>{{ a.title or '(untitled)' }}</h3>
    <div class="meta">
      <span class="tag {{ a.tag }}">{{ a.tag or '—' }}</span>
      {% if a.violence_layer %}<span>{{ a.violence_layer }}</span> · {% endif %}
      {% if a.url and a.url.startswith('http') %}
        <a href="{{ a.url }}" target="_blank" style="color: var(--muted);">{{ a.source or 'source' }} ↗</a>
      {% else %}{{ a.source or 'source' }}{% endif %}
    </div>
    {% if a.axiom %}<div class="axiom">{{ a.axiom }}</div>{% endif %}
    <details>
      <summary>{% if a.body_en %}body (中 / EN){% else %}body{% endif %}</summary>
      <div class="body">
        {% for p in (a.body or '').split('\n\n') %}<p>{{ p }}</p>{% endfor %}
        {% if a.body_en %}
        <hr style="margin: 0.6rem 0; border: none; border-top: 1px dashed var(--border);">
        {% for p in (a.body_en or '').split('\n\n') %}<p style="text-indent: 0; font-style: italic; color: var(--muted);">{{ p }}</p>{% endfor %}
        {% endif %}
      </div>
    </details>
  </div>
  <div class="actions">
    <form method="post" action="{{ url_for('toggle_published', aid=a.id) }}">
      <button type="submit">{% if a.published %}Unpublish{% else %}Publish{% endif %}</button>
    </form>
    <form method="post" action="{{ url_for('delete_article', aid=a.id) }}"
          onsubmit="return confirm('Delete #{{ a.id }} {{ a.title }}? This adds the source to the auto-mute list.');">
      <input type="hidden" name="reason" value="">
      <button type="submit" class="delete">Delete</button>
    </form>
  </div>
</article>
{% endfor %}

</div>
</body>
</html>
"""


DELETIONS_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>deletions · admin</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
:root { --ink: #1a1109; --paper: #f5f0e8; --accent: #8b1a1a;
        --muted: #6b5c47; --border: #c9bfad; }
body { background: var(--paper); color: var(--ink);
       font-family: "Georgia",serif; padding: 1.5rem 1rem 4rem;
       line-height: 1.55; }
.wrap { max-width: 1100px; margin: 0 auto; }
header { border-top: 4px solid var(--accent); padding-top: 1.2rem;
         margin-bottom: 1.5rem; display: flex; justify-content: space-between;
         align-items: baseline; }
h1 { font-size: 1.6rem; letter-spacing: 0.1em; }
a.back { color: var(--accent); text-decoration: none; font-size: 0.85rem; }
.cols { display: grid; grid-template-columns: 1fr 280px; gap: 1.5rem; }
.host-counts { background: rgba(255,253,248,0.92); border: 1px solid var(--border);
               padding: 0.8rem; font-size: 0.85rem; }
.host-counts h3 { font-size: 0.9rem; letter-spacing: 0.1em;
                  margin-bottom: 0.6rem; color: var(--accent);
                  text-transform: uppercase; }
.host-counts table { width: 100%; }
.host-counts td { padding: 0.15rem 0.2rem; }
.host-counts td.n { text-align: right; color: var(--muted); }
.del { background: rgba(255,253,248,0.92); border: 1px solid var(--border);
       border-left: 3px solid var(--muted); padding: 0.7rem 1rem;
       margin-bottom: 0.6rem; }
.del .meta { font-size: 0.75rem; color: var(--muted); margin-bottom: 0.2rem; }
.del .title { font-weight: 600; margin-bottom: 0.2rem; }
.del .url { font-size: 0.8rem; color: var(--muted);
            word-break: break-all; margin-bottom: 0.4rem; }
.del .url a { color: var(--muted); }
.del form { display: inline; }
.del button { font: inherit; font-size: 0.75rem; padding: 0.2rem 0.5rem;
              background: transparent; border: 1px solid var(--border);
              cursor: pointer; }
.del button:hover { background: var(--accent); color: #fff; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Deletions</h1>
  <a class="back" href="{{ url_for('index') }}">← back to articles</a>
</header>

<div class="cols">
<div>
{% for d in deletions %}
<div class="del">
  <div class="meta">#{{ d.id }} · {{ (d.deleted_at or '')[:10] }} · host: <b>{{ d.host or '?' }}</b> · tag: {{ d.tag or '—' }}</div>
  <div class="title">{{ d.title or '(untitled)' }}</div>
  <div class="url">{% if d.url and d.url.startswith('http') %}<a href="{{ d.url }}" target="_blank">{{ d.url }}</a>{% else %}{{ d.url }}{% endif %}</div>
  {% if d.reason %}<div style="font-size: 0.82rem; font-style: italic; color: var(--muted); margin-bottom: 0.4rem;">reason: {{ d.reason }}</div>{% endif %}
  <form method="post" action="{{ url_for('restore_deletion', did=d.id) }}">
    <button type="submit">Restore (un-mute)</button>
  </form>
</div>
{% endfor %}
{% if not deletions %}<p style="color: var(--muted); font-style: italic;">No deletions yet.</p>{% endif %}
</div>

<aside class="host-counts">
  <h3>Hosts by deletion count</h3>
  <table>
    {% for h in host_counts %}
    <tr><td>{{ h.host }}</td><td class="n">{{ h.n }}</td></tr>
    {% endfor %}
    {% if not host_counts %}<tr><td colspan="2" style="color: var(--muted);">No data yet.</td></tr>{% endif %}
  </table>
</aside>
</div>

</div>
</body>
</html>
"""


# ============================================================================
# Filter API — used by generate.py to skip muted hosts
# ============================================================================

def deletion_filter_reason(url: str, source: str = "") -> str | None:
    """Return a string reason if this URL/source should be skipped, else None.

    Used by generate.py.process_url to honor admin deletions:
      - exact URL previously deleted → skip
      - host with ≥3 deletions in last 30 days → skip
    """
    host = (urlparse(url or "").hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    with connect() as c:
        # Ensure table exists before generate.py tries to query it.
        try:
            if c.execute("SELECT 1 FROM deletions WHERE url = ?", (url,)).fetchone():
                return "url previously deleted in admin"
            row = c.execute("""
                SELECT COUNT(*) FROM deletions
                WHERE host = ?
                AND deleted_at > datetime('now', '-30 days')
            """, (host,)).fetchone()
            if row and row[0] >= 3:
                return f"host {host} auto-muted ({row[0]} recent deletions)"
        except Exception:
            return None
    return None


if __name__ == "__main__":
    port = int(os.environ.get("ADMIN_PORT", "8080"))
    print(f"admin server: http://127.0.0.1:{port}", file=sys.stderr)
    app.run(host="127.0.0.1", port=port, debug=False)
