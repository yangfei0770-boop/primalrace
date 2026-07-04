#!/usr/bin/env python3
"""One-off A/B: generate commentary for the same article with the current
provider config and print the result. The compare.yml workflow runs this
twice (once per provider) so the outputs land side by side in the log.

Uses the most recent published article's raw_text from news.db — no network
fetch, so both providers see the exact same input.
"""
import json
import sys

from db import connect
from generate import generate_commentary


def main():
    with connect() as conn:
        r = conn.execute(
            "SELECT url, source, source_title, raw_text FROM articles "
            "WHERE published = 1 AND raw_text IS NOT NULL AND LENGTH(raw_text) > 500 "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not r:
        print("no article with raw_text found", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print(f"INPUT ARTICLE: {r['source_title']}")
    print(f"SOURCE: {r['source']}  |  {r['url']}")
    print(f"RAW TEXT: {len(r['raw_text'])} chars")
    print("=" * 70)

    out = generate_commentary(dict(r))
    print(f"\nMODEL: {out['model']}")
    print(f"TOKENS: in={out['input_tokens']} out={out['output_tokens']}")
    print(f"TAG: {out['tag']}  |  LAYER: {out['violence_layer']}")
    print("\n----- 标题 -----\n" + out["title"])
    print("\n----- AXIOM -----\n" + out["axiom"])
    print("\n----- 正文 -----\n" + out["body"])
    print("\n----- TITLE EN -----\n" + out["title_en"])
    print("\n----- AXIOM EN -----\n" + out["axiom_en"])
    print("\n----- BODY EN -----\n" + out["body_en"])
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
