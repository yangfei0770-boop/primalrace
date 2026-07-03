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
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

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


def build_post(title: str, axiom: str, title_en: str, axiom_en: str,
               url: str) -> dict:
    """Bilingual post: zh block, en block, then a short display link
    (rich-text facet points at the full permalink).

    Bluesky caps posts at 300 graphemes — trim the English parts first
    if we run over, the Chinese original always survives intact.
    """
    link_text = url.replace("https://", "").replace("http://", "")

    zh = title.strip()
    if axiom.strip():
        zh += "\n" + axiom.strip()

    en_parts = [p for p in (title_en.strip(), axiom_en.strip()) if p]
    budget = 296 - len(zh) - len(link_text) - 4  # 4 = the two "\n\n" joints
    en = "\n".join(en_parts)
    if en and len(en) > budget:
        en = en_parts[0]  # drop the EN axiom, keep the EN title
        if len(en) > budget:
            en = en[:max(0, budget - 1)] + "…" if budget > 10 else ""

    text = zh + ("\n\n" + en if en else "")
    link_start = len(text.encode("utf-8")) + 2
    text = text + "\n\n" + link_text
    link_end = len(text.encode("utf-8"))
    return {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "langs": ["zh", "en"],
        "facets": [{
            "index": {"byteStart": link_start, "byteEnd": link_end},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
        }],
    }


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
            f"SELECT id, title, axiom, title_en, axiom_en FROM articles "
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

    posted = 0
    for r in rows[:MAX_POSTS]:
        record = build_post(r["title"] or "", r["axiom"] or "",
                            r["title_en"] or "", r["axiom_en"] or "",
                            f"{SITE}/news/p/{r['id']}")
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
