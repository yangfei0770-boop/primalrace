#!/usr/bin/env python3
"""Translate Chinese commentaries to English for rows missing body_en.

Uses a much lighter system prompt than generate.py — no book corpus needed,
just style instructions for translation.

Usage:
  python3 backfill_translation.py           # translate all missing
  python3 backfill_translation.py 5 7 9     # specific ids
  python3 backfill_translation.py --force   # retranslate even if body_en exists
"""
import argparse
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from db import connect                              # noqa: E402
from llm import generate as llm_generate, provider_label  # noqa: E402


TRANSLATION_SYSTEM = [{
    "type": "text",
    "text": """You are translating news commentary written by 费扬 (Yang Fei),
author of《原初种族》(The Primal Race).

His English voice: sharp, axiomatic, no hedging, mixes concept-terms with the
narrative. PRESERVE these terms untranslated (they are his vocabulary):
- complicity / complicit / co-conspirator
- meta-violence
- masculine / feminine  (used in the framework sense, not biological)
- Primal Race
- Violence Triangle (Galtung)
- scam  (used pejoratively for institutional dishonesty)
- narrative weaponization
- direct / structural / cultural violence (Galtung's three layers)

Translate the THREE Chinese fields below into English. Rules:
- Don't add a translator's note. No preamble.
- Don't soften the original's anger, judgment, or sarcasm.
- Match paragraph breaks (use \\n\\n between paragraphs).
- Use English rhythm — don't translate sentence-by-sentence.
- Keep the closing line punchy. Don't summarize.

Output strict JSON with these keys ONLY:
{
  "title_en": "≤14-word English title — same edge",
  "axiom_en": "≤25-word English axiom — same one-line punch",
  "body_en":  "English body — same structure, same sharpness"
}

Only the JSON. No code fences. No preamble."""
}]


def _strip_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def translate_row(row) -> dict:
    user_msg = (
        f"Article topic: {row['source_title']}\n"
        f"Source URL: {row['url']}\n\n"
        f"--- 中文标题 ---\n{row['title']}\n\n"
        f"--- 中文 axiom ---\n{row['axiom']}\n\n"
        f"--- 中文 body ---\n{row['body']}"
    )
    result = llm_generate(TRANSLATION_SYSTEM, user_msg, max_tokens=1800)
    text = _strip_fence(result["text"])
    parsed = json.loads(text)
    return {
        "title_en": parsed.get("title_en", "").strip(),
        "axiom_en": parsed.get("axiom_en", "").strip(),
        "body_en":  parsed.get("body_en", "").strip(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", type=int, help="specific article ids")
    ap.add_argument("--force", action="store_true",
                    help="retranslate even if body_en already exists")
    args = ap.parse_args()

    where = "title IS NOT NULL AND title != ''"
    if not args.force:
        where += " AND (body_en IS NULL OR body_en = '')"
    if args.ids:
        placeholders = ",".join("?" * len(args.ids))
        where += f" AND id IN ({placeholders})"
        params = args.ids
    else:
        params = []

    with connect() as c:
        rows = list(c.execute(
            f"SELECT id, url, source_title, title, axiom, body "
            f"FROM articles WHERE {where} ORDER BY id", params
        ))

    if not rows:
        print("nothing to translate")
        return

    print(f"translating {len(rows)} rows via {provider_label()}")
    for r in rows:
        try:
            print(f"  #{r['id']:>2} '{r['title'][:32]}...'", end=" ", flush=True)
            t = translate_row(r)
            with connect() as c:
                c.execute(
                    "UPDATE articles SET title_en=?, axiom_en=?, body_en=? WHERE id=?",
                    (t["title_en"], t["axiom_en"], t["body_en"], r["id"]),
                )
            print(f"→ '{t['title_en'][:48]}'")
        except Exception as e:
            print(f"FAILED: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
