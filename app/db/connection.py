"""SQLite connection layer and schema initialization.

The single low-level data-access entry point. Every connection enforces the
PRAGMAs `database-schema.md` ("Connection setup") requires:

- ``PRAGMA foreign_keys = ON`` is per-connection and OFF by default in SQLite —
  set on EVERY connection or ``ON DELETE CASCADE`` and FK validity go silently
  inert (orphan rows become possible).
- ``PRAGMA journal_mode = WAL`` persists on the database file — set once in
  :func:`init_db`. WAL lets readers run concurrently with a single writer (it
  does NOT allow two simultaneous writers — those still serialize). A
  per-connection ``busy_timeout`` absorbs that brief serialization so the
  Epic-2 pipeline's writers (OCR job + analysis job) wait instead of failing
  fast with ``SQLITE_BUSY``/"database is locked".

Raw SQL is confined to ``app/db/`` (this module, ``schema.sql``, and
``repositories.py``) — no other module issues SQL (architecture Data boundary).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# How long a connection waits for a held write lock before raising
# ``SQLITE_BUSY``. WAL serializes writers; this lets the Epic-2 OCR + analysis
# jobs queue briefly instead of failing fast.
_BUSY_TIMEOUT_MS = 5000


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with FK enforcement and a snake_case row factory.

    Columns are exposed by name via ``sqlite3.Row`` (column names are already
    snake_case in the schema, so no translation is needed). A ``busy_timeout``
    is set so a connection waits for a held write lock instead of raising
    ``SQLITE_BUSY`` immediately (WAL still serializes writers).
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    return conn


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Context-managed connection that always closes (and commits on clean exit)."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str | Path) -> None:
    """Create the database (and parent dir) and apply the schema. Idempotent.

    Establishes WAL mode on the file, then runs ``schema.sql`` (which uses
    ``CREATE … IF NOT EXISTS``, so re-running is safe). Local file work only —
    no network, so this is safe at app startup and under ``--network none``.
    """
    path = Path(db_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(path)
    try:
        # WAL persists on the file; setting it on every init is harmless.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
