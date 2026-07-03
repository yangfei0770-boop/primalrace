#!/usr/bin/env python3
"""Post freshly published commentary to Bluesky.

cron_pipeline.py writes the ids of newly published articles to .new_ids
(one id per line). This script — run as a separate workflow step AFTER the
git push, so the permalinks are live by the time followers click — reads
that file, posts each article to Bluesky, then clears the file.

Env:
  BLUESKY_HANDLE        e.g. yangfei0770.bsky.social
  BLUESKY_APP_PASSWORD  app password from Settings → App Passwords
  BSKY_MAX_POSTS        cap per run (default 5, avoid flooding followers)

Missing credentials → exits 0 silently, so the pipeline never breaks on this.
"""
import html as html_mod
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

from db import connect

NEWS_DIR = Path(__file__).parent
NEW_IDS_FILE = NEWS_DIR / ".new_ids"
SITE = "https://www.howtoraiseiq.com"
PDS = "https://bsky.social"
MAX_POSTS = int(os.environ.get("BSKY_MAX_POSTS", "5"))


def login(handle: str, app_password: str) -> dict:
    r = requests.post(
        f"{PDS}/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": app_password},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


MAX_THUMB_BYTES = 950_000  # bsky blob cap is ~1MB
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _upload_blob(session: dict, data: bytes, mime: str) -> dict | None:
    try:
        r = requests.post(
            f"{PDS}/xrpc/com.atproto.repo.uploadBlob",
            headers={"Authorization": f"Bearer {session['accessJwt']}",
                     "Content-Type": mime},
            data=data,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["blob"]
    except Exception as e:
        print(f"[bsky] blob upload failed: {e}", file=sys.stderr)
        return None


def upload_default_thumb(session: dict) -> dict | None:
    """Upload og.png once per run — the fallback card image."""
    og = NEWS_DIR.parent / "og.png"
    if not og.exists():
        return None
    return _upload_blob(session, og.read_bytes(), "image/png")


def fetch_article_thumb(session: dict, article_url: str) -> dict | None:
    """Try to pull the source article's own og:image and upload it.
    Any failure → None (caller falls back to the book cover)."""
    if not article_url.startswith("http"):
        return None
    try:
        page = requests.get(article_url, timeout=15,
                            headers={"User-Agent": UA})
        page.raise_for_status()
        m = (re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', page.text)
             or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', page.text)
             or re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)', page.text))
        if not m:
            return None
        img_url = urljoin(article_url, html_mod.unescape(m.group(1)))
        img = requests.get(img_url, timeout=15, headers={"User-Agent": UA})
        img.raise_for_status()
        mime = (img.headers.get("Content-Type") or "").split(";")[0].strip()
        if mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            return None
        if len(img.content) > MAX_THUMB_BYTES:
            return None
        return _upload_blob(session, img.content, mime)
    except Exception:
        return None


def build_post(title: str, axiom: str, title_en: str, axiom_en: str,
               url: str, thumb: dict | None) -> dict:
    """Bilingual post + link preview card (external embed).

    The card carries the permalink, so the text stays clean: zh block,
    then en block. Bluesky caps posts at 300 graphemes — trim the English
    parts first if we run over; the Chinese original always survives.
    If the thumb is unavailable, fall back to a visible link with a facet.
    """
    zh = title.strip()
    if axiom.strip():
        zh += "\n" + axiom.strip()

    en_parts = [p for p in (title_en.strip(), axiom_en.strip()) if p]
    budget = 294 - len(zh)
    en = "\n".join(en_parts)
    if en and len(en) > budget:
        en = en_parts[0]
        if len(en) > budget:
            en = en[:max(0, budget - 1)] + "…" if budget > 10 else ""

    text = zh + ("\n\n" + en if en else "")
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "langs": ["zh", "en"],
        "embed": {
            "$type": "app.bsky.embed.external",
            "external": {
                "uri": url,
                "title": title.strip() or "breaking news · 费扬",
                "description": (axiom.strip() or
                                "用《原初种族》的框架读新闻 · The Primal Race"),
                **({"thumb": thumb} if thumb else {}),
            },
        },
    }
    return record


def main():
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        print("[bsky] no credentials — skipping")
        return

    if not NEW_IDS_FILE.exists():
        print("[bsky] no .new_ids file — nothing to post")
        return
    ids = [int(ln) for ln in NEW_IDS_FILE.read_text().split() if ln.strip().isdigit()]
    if not ids:
        print("[bsky] .new_ids empty — nothing to post")
        return

    with connect() as conn:
        rows = conn.execute(
            f"SELECT id, title, axiom, title_en, axiom_en, url FROM articles "
            f"WHERE published = 1 AND id IN ({','.join('?' * len(ids))}) "
            f"ORDER BY id",
            ids,
        ).fetchall()

    if not rows:
        NEW_IDS_FILE.unlink(missing_ok=True)
        print("[bsky] ids not found/published — cleared")
        return

    try:
        session = login(handle, password)
    except Exception as e:
        print(f"[bsky] login failed: {e}", file=sys.stderr)
        return  # keep .new_ids so next run retries

    default_thumb = upload_default_thumb(session)
    posted = 0
    for r in rows[:MAX_POSTS]:
        thumb = fetch_article_thumb(session, r["url"] or "") or default_thumb
        record = build_post(r["title"] or "", r["axiom"] or "",
                            r["title_en"] or "", r["axiom_en"] or "",
                            f"{SITE}/news/p/{r['id']}", thumb)
        try:
            resp = requests.post(
                f"{PDS}/xrpc/com.atproto.repo.createRecord",
                headers={"Authorization": f"Bearer {session['accessJwt']}"},
                json={"repo": session["did"],
                      "collection": "app.bsky.feed.post",
                      "record": record},
                timeout=30,
            )
            resp.raise_for_status()
            posted += 1
            print(f"[bsky] posted #{r['id']}: {r['title']}")
            time.sleep(2)  # be gentle with the rate limit
        except Exception as e:
            print(f"[bsky] post #{r['id']} failed: {e}", file=sys.stderr)

    NEW_IDS_FILE.unlink(missing_ok=True)
    skipped = max(0, len(rows) - MAX_POSTS)
    print(f"[bsky] done — {posted} posted"
          + (f", {skipped} skipped (over BSKY_MAX_POSTS cap)" if skipped else ""))


if __name__ == "__main__":
    main()
