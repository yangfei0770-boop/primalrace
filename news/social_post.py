#!/usr/bin/env python3
"""Post freshly published commentary to all social platforms.

Runs as a workflow step AFTER the git push (permalinks live by then).
Reads article ids from .new_ids, posts to Bluesky + Twitter/X, then
clears the file. Platforms with missing credentials are skipped silently
so the pipeline never breaks on this step.

Env:
  BLUESKY_HANDLE, BLUESKY_APP_PASSWORD      (Bluesky)
  TWITTER_API_KEY, TWITTER_API_SECRET,
  TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET  (X — OAuth 1.0a user context)
  SOCIAL_MAX_POSTS   cap per run per platform (default 5)
"""
import os
import sys
import time
from pathlib import Path

import requests

from db import connect
from bsky_post import (SITE, build_post, fetch_article_thumb, login,
                       upload_default_thumb, PDS)

NEWS_DIR = Path(__file__).parent
NEW_IDS_FILE = NEWS_DIR / ".new_ids"
MAX_POSTS = int(os.environ.get("SOCIAL_MAX_POSTS",
                               os.environ.get("BSKY_MAX_POSTS", "5")))


# ---------------------------------------------------------------- Bluesky

def post_bluesky(rows) -> None:
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        print("[bsky] no credentials — skipping")
        return
    try:
        session = login(handle, password)
    except Exception as e:
        print(f"[bsky] login failed: {e}", file=sys.stderr)
        return

    default_thumb = upload_default_thumb(session)
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
            print(f"[bsky] posted #{r['id']}: {r['title']}")
            time.sleep(2)
        except Exception as e:
            print(f"[bsky] post #{r['id']} failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------- Twitter/X

def tweet_text(r) -> str:
    """English-first, Chinese if it fits. 280-char cap; a URL counts as 23."""
    url = f"{SITE}/news/p/{r['id']}"
    en = (r["title_en"] or r["title"] or "").strip()
    axiom_en = (r["axiom_en"] or "").strip()
    if axiom_en:
        en += "\n" + axiom_en

    budget = 275 - 23 - 4  # t.co link + joints
    zh_parts = [p for p in ((r["title"] or "").strip(),
                            (r["axiom"] or "").strip()) if p]
    zh = "\n".join(zh_parts)
    if len(en) > budget:
        en = en[:budget - 1] + "…"
        zh = ""
    elif zh and len(en) + 2 + len(zh) > budget:
        zh = zh_parts[0]
        if len(en) + 2 + len(zh) > budget:
            zh = ""

    text = en + ("\n\n" + zh if zh else "")
    return text + "\n\n" + url


def post_twitter(rows) -> None:
    """Two auth modes:
    - TWITTER_OAUTH2_ACCESS_TOKEN (new console.x.com — user token with
      tweet.write scope) → plain Bearer auth
    - legacy OAuth 1.0a four-key set → signed requests
    """
    oauth2_token = os.environ.get("TWITTER_OAUTH2_ACCESS_TOKEN", "").strip()
    key = os.environ.get("TWITTER_API_KEY", "").strip()
    secret = os.environ.get("TWITTER_API_SECRET", "").strip()
    token = os.environ.get("TWITTER_ACCESS_TOKEN", "").strip()
    token_secret = os.environ.get("TWITTER_ACCESS_SECRET", "").strip()

    auth = None
    headers = {}
    if oauth2_token:
        headers = {"Authorization": f"Bearer {oauth2_token}"}
    elif all((key, secret, token, token_secret)):
        try:
            from requests_oauthlib import OAuth1
        except ImportError:
            print("[x] requests-oauthlib not installed — skipping", file=sys.stderr)
            return
        auth = OAuth1(key, secret, token, token_secret)
    else:
        print("[x] no credentials — skipping")
        return

    for r in rows[:MAX_POSTS]:
        try:
            resp = requests.post(
                "https://api.x.com/2/tweets",
                auth=auth,
                headers=headers,
                json={"text": tweet_text(r)},
                timeout=30,
            )
            resp.raise_for_status()
            print(f"[x] posted #{r['id']}: {r['title']}")
            time.sleep(2)
        except Exception as e:
            detail = ""
            if hasattr(e, "response") and e.response is not None:
                detail = f" — {e.response.text[:200]}"
            print(f"[x] post #{r['id']} failed: {e}{detail}", file=sys.stderr)


# ---------------------------------------------------------------- main

def main():
    if not NEW_IDS_FILE.exists():
        print("[social] no .new_ids file — nothing to post")
        return
    ids = [int(ln) for ln in NEW_IDS_FILE.read_text().split()
           if ln.strip().isdigit()]
    if not ids:
        NEW_IDS_FILE.unlink(missing_ok=True)
        print("[social] .new_ids empty — nothing to post")
        return

    with connect() as conn:
        rows = conn.execute(
            f"SELECT id, title, axiom, title_en, axiom_en, url FROM articles "
            f"WHERE published = 1 AND id IN ({','.join('?' * len(ids))}) "
            f"ORDER BY id",
            ids,
        ).fetchall()

    if rows:
        post_bluesky(rows)
        post_twitter(rows)
        skipped = max(0, len(rows) - MAX_POSTS)
        if skipped:
            print(f"[social] {skipped} skipped (over cap)")
    NEW_IDS_FILE.unlink(missing_ok=True)
    print("[social] done")


if __name__ == "__main__":
    main()
