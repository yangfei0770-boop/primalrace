#!/usr/bin/env python3
"""Lightweight admin for news.db — list / publish / unpublish / edit / delete.

Workflow:
  python3 admin.py list                   # all rows (drafts first)
  python3 admin.py show 5                 # full text of row 5
  python3 admin.py publish 5 7 9          # mark rows as published
  python3 admin.py unpublish 5
  python3 admin.py delete 5               # remove a row
  python3 admin.py edit 5                 # open body in $EDITOR; saved to your_edits
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from db import connect


def cmd_list(args):
    where = ""
    if args and args[0] == "--published":
        where = "WHERE published = 1"
    elif args and args[0] == "--drafts":
        where = "WHERE published = 0"
    with connect() as conn:
        rows = conn.execute(
            f"SELECT id, published, tag, title, source, generated_at "
            f"FROM articles {where} "
            f"ORDER BY published ASC, generated_at DESC"
        ).fetchall()
    if not rows:
        print("(empty)")
        return
    for r in rows:
        flag = "✓" if r["published"] else "·"
        date = (r["generated_at"] or "")[:10]
        print(f"{flag} #{r['id']:<3} [{r['tag'] or '—':<13}] {date} "
              f"{(r['title'] or '(untitled)')[:50]:<50}  ← {r['source'] or ''}")


def cmd_show(args):
    if not args:
        sys.exit("usage: admin.py show <id>")
    with connect() as conn:
        r = conn.execute(
            "SELECT * FROM articles WHERE id=?", (int(args[0]),)
        ).fetchone()
    if not r:
        sys.exit("not found")
    print(f"#{r['id']}  published={bool(r['published'])}  tag={r['tag']}  layer={r['violence_layer']}")
    print(f"url: {r['url']}")
    print(f"source: {r['source']} — {r['source_title']}")
    print(f"model: {r['model']}  in={r['input_tokens']} cache_r={r['cache_read_tokens']} "
          f"cache_w={r['cache_create_tokens']} out={r['output_tokens']}")
    print()
    print(f"## {r['title']}")
    if r["axiom"]:
        print(f"\n> {r['axiom']}\n")
    body = r["your_edits"] or r["body"]
    print(body or "(no body)")
    if r["your_edits"]:
        print("\n[your_edits is overriding the original body]")


def _flip(args, flag):
    if not args:
        sys.exit("need at least one id")
    ids = [int(a) for a in args]
    with connect() as conn:
        conn.executemany(
            "UPDATE articles SET published=? WHERE id=?",
            [(flag, i) for i in ids],
        )
    print(f"{'published' if flag else 'unpublished'}: {ids}")


def cmd_publish(args):    _flip(args, 1)
def cmd_unpublish(args):  _flip(args, 0)


def cmd_delete(args):
    if not args:
        sys.exit("need id")
    ids = [int(a) for a in args]
    with connect() as conn:
        conn.executemany("DELETE FROM articles WHERE id=?", [(i,) for i in ids])
    print(f"deleted: {ids}")


def cmd_edit(args):
    if not args:
        sys.exit("need id")
    aid = int(args[0])
    with connect() as conn:
        r = conn.execute(
            "SELECT title, axiom, body, your_edits FROM articles WHERE id=?", (aid,)
        ).fetchone()
    if not r:
        sys.exit("not found")
    current = r["your_edits"] or r["body"] or ""
    header = f"# {r['title']}\n# axiom: {r['axiom']}\n# (lines starting with # are stripped on save)\n\n"
    with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(header + current)
        path = f.name
    editor = os.environ.get("EDITOR", "vi")
    subprocess.call([editor, path])
    edited = Path(path).read_text(encoding="utf-8")
    edited = "\n".join(ln for ln in edited.splitlines() if not ln.startswith("#")).strip()
    Path(path).unlink(missing_ok=True)
    if not edited:
        print("empty — nothing saved")
        return
    with connect() as conn:
        conn.execute("UPDATE articles SET your_edits=? WHERE id=?", (edited, aid))
    print(f"saved your_edits for #{aid} ({len(edited)} chars)")


CMDS = {
    "list": cmd_list, "show": cmd_show,
    "publish": cmd_publish, "unpublish": cmd_unpublish,
    "delete": cmd_delete, "edit": cmd_edit,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        sys.exit(1)
    CMDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
