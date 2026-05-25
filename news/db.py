"""SQLite layer for news commentary."""
import os
import sqlite3
from pathlib import Path

# NEWS_DB env var lets Railway point this at a mounted volume.
DB_PATH = Path(os.environ.get("NEWS_DB", Path(__file__).parent / "news.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  url           TEXT UNIQUE NOT NULL,
  source        TEXT,
  source_title  TEXT,
  raw_text      TEXT,
  fetched_at    TEXT NOT NULL,

  title         TEXT,
  axiom         TEXT,
  body          TEXT,
  title_en      TEXT,
  axiom_en      TEXT,
  body_en       TEXT,
  tag           TEXT,
  violence_layer TEXT,
  your_edits    TEXT,
  published     INTEGER NOT NULL DEFAULT 0,

  model         TEXT,
  input_tokens  INTEGER,
  cache_read_tokens INTEGER,
  cache_create_tokens INTEGER,
  output_tokens INTEGER,
  generated_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_published_at
  ON articles(published, generated_at DESC);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


if __name__ == "__main__":
    with connect() as c:
        print("schema ready at", DB_PATH)
        print("tables:", [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")])
