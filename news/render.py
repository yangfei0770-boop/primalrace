#!/usr/bin/env python3
"""Render published commentary from news.db to news/index.html.

Style mirrors blog/index.html — same palette, same paper texture, serif type.
Only published=1 rows are rendered (use admin.py to publish).

Usage:
  python3 render.py            # only published items
  python3 render.py --drafts   # include drafts (for local preview)
"""
import argparse
import html
import re
from datetime import datetime
from pathlib import Path

from db import connect

OUT = Path(__file__).parent / "index.html"

TAG_LABELS = {
    "china_tech":    "中国科技",
    "gender":        "性别",
    "international": "国际",
    "philosophy":    "哲学",
    "tech":          "科技",
    "good_news":     "好消息",
    "other":         "其他",
}

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>breaking news · 费扬</title>
<script defer src="/_vercel/insights/script.js"></script>
<script defer src="/_vercel/speed-insights/script.js"></script>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --ink: #1a1109;
  --paper: #f5f0e8;
  --accent: #8b1a1a;
  --accent-light: #b52020;
  --muted: #6b5c47;
  --border: #c9bfad;
}}
html, body {{ min-height: 100%; }}
body {{
  background: var(--paper);
  color: var(--ink);
  font-family: "Georgia", "Noto Serif SC", "Source Han Serif CN", serif;
  padding: 2.5rem 1.2rem 4rem;
  line-height: 1.75;
}}
body::before {{
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background: repeating-linear-gradient(0deg,
    transparent, transparent 28px,
    rgba(0,0,0,0.025) 28px, rgba(0,0,0,0.025) 29px);
}}
.wrap {{ max-width: 720px; margin: 0 auto; position: relative; z-index: 1; }}

header.masthead {{
  text-align: center;
  border-bottom: 1px solid var(--border);
  border-top: 5px solid var(--accent);
  padding: 2.2rem 0 1.4rem;
  margin-bottom: 2.4rem;
  background: rgba(255,253,248,0.6);
}}
.masthead .ornament {{
  color: var(--accent); font-size: 1.1rem;
  letter-spacing: 0.4em; display: block; margin-bottom: 0.8rem;
}}
.masthead h1 {{
  font-size: 2.4rem; font-weight: 700;
  letter-spacing: 0.12em; line-height: 1.1;
}}
.masthead .subtitle {{
  font-size: 0.85rem; letter-spacing: 0.22em;
  text-transform: uppercase; color: var(--muted);
  margin-top: 0.4rem;
}}
.masthead .byline {{
  font-size: 0.82rem; color: var(--muted);
  margin-top: 1rem; font-style: italic;
}}
.masthead .byline a {{ color: var(--accent); text-decoration: none; }}
.masthead .byline a:hover {{ text-decoration: underline; }}

article {{
  background: rgba(255,253,248,0.92);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  padding: 2rem 2.2rem 1.8rem;
  margin-bottom: 2rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 4px 16px rgba(0,0,0,0.04);
}}
article.draft {{ border-left-color: var(--muted); opacity: 0.78; }}
article h2 {{
  font-size: 1.55rem; line-height: 1.35;
  margin-bottom: 0.55rem; color: var(--ink);
  letter-spacing: 0.02em;
}}
.meta {{
  font-size: 0.78rem; color: var(--muted);
  letter-spacing: 0.05em; margin-bottom: 1.2rem;
  display: flex; flex-wrap: wrap; gap: 0.8rem;
  border-bottom: 1px dashed var(--border);
  padding-bottom: 0.8rem;
}}
.meta .tag {{
  background: var(--accent); color: #fff;
  padding: 0.08rem 0.55rem; letter-spacing: 0.08em;
  font-size: 0.72rem;
}}
.meta .tag.good_news {{ background: #2d6a3e; }}
article.good_news {{ border-left-color: #2d6a3e; }}
article.good_news .axiom {{ color: #2d6a3e; border-left-color: #2d6a3e; }}
.meta .layer {{
  color: var(--accent); font-style: italic;
}}
.meta .source a {{ color: var(--muted); text-decoration: none; }}
.meta .source a:hover {{ color: var(--accent); text-decoration: underline; }}

.axiom {{
  font-size: 1.05rem; font-style: italic;
  color: var(--accent);
  border-left: 2px solid var(--accent);
  padding-left: 0.9rem; margin-bottom: 1.2rem;
  line-height: 1.55;
}}
.body p {{
  margin-bottom: 1rem; text-align: justify;
  text-indent: 2em;
  font-size: 1.02rem;
}}
.body p:last-child {{ margin-bottom: 0; }}
.body.lang-en p {{ text-indent: 0; }}

/* language toggle */
.lang-switch {{
  position: fixed; top: 1rem; right: 1.2rem; z-index: 10;
  background: rgba(255,253,248,0.95);
  border: 1px solid var(--border);
  font-family: inherit; font-size: 0.8rem;
  letter-spacing: 0.12em;
}}
.lang-switch button {{
  background: transparent; border: none; cursor: pointer;
  padding: 0.45rem 0.85rem; font: inherit; color: var(--muted);
  border-right: 1px solid var(--border);
}}
.lang-switch button:last-child {{ border-right: none; }}
.lang-switch button.active {{ background: var(--accent); color: #fff; }}
body[data-lang="zh"] .lang-en {{ display: none; }}
body[data-lang="en"] .lang-zh {{ display: none; }}
body[data-lang="en"] .meta .layer {{ font-style: italic; }}
.no-translation {{
  font-size: 0.85rem; color: var(--muted);
  font-style: italic; padding: 0.6rem 0;
}}

.draft-badge {{
  display: inline-block; background: var(--muted); color: #fff;
  font-size: 0.7rem; letter-spacing: 0.1em;
  padding: 0.1rem 0.5rem; margin-left: 0.6rem;
  vertical-align: middle;
}}

footer.foot {{
  text-align: center; margin-top: 3.5rem;
  font-size: 0.78rem; color: var(--muted);
  letter-spacing: 0.18em;
}}
footer.foot a {{ color: var(--accent); text-decoration: none; }}

@media (max-width: 560px) {{
  body {{ padding: 1.6rem 0.9rem 3rem; }}
  .masthead h1 {{ font-size: 1.8rem; }}
  article {{ padding: 1.4rem 1.2rem; }}
  article h2 {{ font-size: 1.3rem; }}
}}
</style>
</head>
<body data-lang="zh">

<div class="lang-switch">
  <button data-set="zh" class="active">中文</button>
  <button data-set="en">EN</button>
</div>

<div class="wrap">

<header class="masthead">
  <span class="ornament">✦ &nbsp; ✦ &nbsp; ✦</span>
  <h1>breaking news</h1>
  <div class="subtitle">News, read through The Primal Race</div>
  <div class="byline">
    by 费扬 &nbsp;·&nbsp; 数据 Claude &nbsp;·&nbsp;
    <a href="../">回到《原初种族》</a>
  </div>
</header>

{articles}

<footer class="foot">
  ― &nbsp; ― &nbsp; ―<br>
  共 {count} 条 &nbsp;·&nbsp; 更新于 {updated}
</footer>

</div>

<script>
(function() {{
  var key = 'breaking-news-lang';
  var saved = localStorage.getItem(key) || 'zh';
  setLang(saved);
  document.querySelectorAll('.lang-switch button').forEach(function(b) {{
    b.addEventListener('click', function() {{
      setLang(b.dataset.set);
      localStorage.setItem(key, b.dataset.set);
    }});
  }});
  function setLang(l) {{
    document.body.dataset.lang = l;
    document.querySelectorAll('.lang-switch button').forEach(function(b) {{
      b.classList.toggle('active', b.dataset.set === l);
    }});
  }}
}})();
</script>
</body>
</html>
"""

ARTICLE_TEMPLATE = """<article class="{article_cls}" id="a{id}">
  <h2><span class="lang-zh">{title}</span><span class="lang-en">{title_en}</span>{draft_badge}</h2>
  <div class="meta">
    <span class="tag {tag_class}">{tag}</span>
    <span class="layer">{layer}</span>
    <span class="source">{source_link}</span>
    <span class="date">{date}</span>
  </div>
  {axiom_block_zh}
  {axiom_block_en}
  <div class="body lang-zh">{body}</div>
  {body_en_block}
</article>"""


def render_body(text: str) -> str:
    """Markdown-ish paragraph splitting + escaping."""
    paras = re.split(r"\n\s*\n", text.strip())
    return "\n  ".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>"
                       for p in paras if p.strip())


def render_layer(raw: str) -> str:
    if not raw:
        return ""
    labels = {
        "direct": "直接层",
        "structural": "结构层",
        "cultural": "文化层",
        "meta": "元暴力",
    }
    parts = [labels.get(p.strip(), p.strip()) for p in raw.split(",") if p.strip()]
    return " · ".join(parts)


def render_source(url: str, source: str) -> str:
    s = html.escape(source or "未知")
    if url.startswith("http"):
        return f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{s} ↗</a>'
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts", action="store_true", help="include unpublished drafts")
    args = ap.parse_args()

    where = "" if args.drafts else "WHERE published = 1"
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM articles {where} "
            f"ORDER BY published DESC, generated_at DESC"
        ).fetchall()

    parts = []
    for r in rows:
        is_draft = not r["published"]
        date = (r["generated_at"] or "")[:10]
        axiom = (r["axiom"] or "").strip()
        axiom_en = (r["axiom_en"] or "").strip()
        body_text = (r["your_edits"] or r["body"] or "").strip()
        body_en = (r["body_en"] or "").strip()
        title_en = (r["title_en"] or "").strip()

        # English fallback: if missing, show a hint instead
        if body_en:
            body_en_html = f'<div class="body lang-en">{render_body(body_en)}</div>'
        else:
            body_en_html = ('<div class="body lang-en"><p class="no-translation">'
                            '(English translation pending — run backfill_translation.py)</p></div>')
        if not title_en:
            title_en = html.escape(r["title"] or "(untitled)")  # fallback to zh

        tag_raw = (r["tag"] or "other").strip()
        article_classes = []
        if is_draft:
            article_classes.append("draft")
        if tag_raw == "good_news":
            article_classes.append("good_news")
        parts.append(ARTICLE_TEMPLATE.format(
            id=r["id"],
            article_cls=" ".join(article_classes),
            draft_badge='<span class="draft-badge">DRAFT</span>' if is_draft else "",
            title=html.escape(r["title"] or "(untitled)"),
            title_en=html.escape(title_en),
            tag=TAG_LABELS.get(tag_raw, tag_raw or "—"),
            tag_class=tag_raw,
            layer=render_layer(r["violence_layer"] or ""),
            source_link=render_source(r["url"] or "", r["source"] or ""),
            date=date,
            axiom_block_zh=f'<div class="axiom lang-zh">{html.escape(axiom)}</div>' if axiom else "",
            axiom_block_en=f'<div class="axiom lang-en">{html.escape(axiom_en)}</div>' if axiom_en else "",
            body=render_body(body_text) if body_text else "<p><em>(no body)</em></p>",
            body_en_block=body_en_html,
        ))

    html_out = PAGE_TEMPLATE.format(
        articles="\n".join(parts) if parts
                else '<article><div class="body"><p>暂无评论。</p></div></article>',
        count=len(rows),
        updated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    OUT.write_text(html_out, encoding="utf-8")
    print(f"wrote {OUT}  ({len(rows)} articles, drafts_included={args.drafts})")


if __name__ == "__main__":
    main()
