#!/usr/bin/env python3
"""One-shot pipeline — Bluesky crawl → generate commentary → render HTML.

Steps:
  1. Crawl Bluesky using queries.txt, append new URLs to urls.txt
  2. For each URL in urls.txt not yet in news.db, fetch + generate commentary
  3. Re-render news/index.html

Wired to Railway cron:
  cron: '0 1 * * *'         # daily 01:00 UTC
  startCommand: python cron_pipeline.py

PUBLISH_NEW=1 in .env auto-publishes new rows (no manual review).
SKIP_CRAWL=1 skips the Bluesky step (useful for local testing).
"""
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from db import connect                                # noqa: E402
from generate import process_url, _check_env         # noqa: E402

URLS_FILE = Path(__file__).parent / "urls.txt"
AUTO_PUBLISH = os.environ.get("PUBLISH_NEW", "0") == "1"
SKIP_CRAWL = os.environ.get("SKIP_CRAWL", "0") == "1"


def crawl_bluesky() -> None:
    """Run the Bluesky crawler as a subprocess so any crash here doesn't kill
    the whole pipeline (we still want to process whatever's already in urls.txt)."""
    print("=== [1/3] Bluesky crawl ===")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "crawlers.bluesky"],
            cwd=Path(__file__).parent,
        )
    except subprocess.CalledProcessError as e:
        print(f"  [warn] crawl failed (exit {e.returncode}); continuing", file=sys.stderr)


def main():
    _check_env()

    if SKIP_CRAWL:
        print("[skip-crawl] SKIP_CRAWL=1")
    else:
        crawl_bluesky()

    print("\n=== [2/3] Generate commentary ===")

    if not URLS_FILE.exists():
        print("no urls.txt — nothing to generate")
    else:
        urls = [
            ln.strip() for ln in URLS_FILE.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        print(f"{len(urls)} URLs in queue")

        new_ids = []
        for url in urls:
            try:
                with connect() as conn:
                    existed = conn.execute(
                        "SELECT id FROM articles WHERE url=?", (url,)
                    ).fetchone()
                before = existed["id"] if existed else None
                aid = process_url(url)
                if aid != before:
                    new_ids.append(aid)
            except Exception as e:
                print(f"  [error] {url}: {e}", file=sys.stderr)

        if AUTO_PUBLISH and new_ids:
            with connect() as conn:
                conn.executemany(
                    "UPDATE articles SET published=1 WHERE id=?",
                    [(i,) for i in new_ids],
                )
            print(f"auto-published: {new_ids}")

    print("\n=== [3/3] Render ===")
    subprocess.check_call([sys.executable, "render.py"], cwd=Path(__file__).parent)
    print("done.")


if __name__ == "__main__":
    main()
