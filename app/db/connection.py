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

# Columns added to a table AFTER that table was first created in an earlier
# story's schema. ``CREATE TABLE IF NOT EXISTS`` does NOT alter an existing
# table, so on a persistent Volume whose DB predates the addition the column is
# simply missing — and any later DDL that references it (e.g. an index) fails at
# startup with "no such column". This ledger is the plain-DDL upgrade path for a
# project with no migration framework: :func:`init_db` ALTERs in any missing
# entry before replaying ``schema.sql``, keeping startup idempotent across
# schema growth. **Append an entry whenever a story adds a column to a table that
# an earlier story already created.** (New tables need nothing here — the
# ``CREATE TABLE IF NOT EXISTS`` in ``schema.sql`` makes them with all columns.)
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    # Story 2.3 — local OpenCV preprocessing outputs on label_images (created 1.2).
    ("label_images", "enhanced_path", "enhanced_path TEXT"),
    ("label_images", "binarized_path", "binarized_path TEXT"),
    ("label_images", "preprocess_log", "preprocess_log TEXT"),
    (
        "label_images",
        "preprocess_ms",
        "preprocess_ms INTEGER CHECK (preprocess_ms IS NULL OR preprocess_ms >= 0)",
    ),
    ("label_images", "preprocessed_at", "preprocessed_at TIMESTAMP"),
    # Story 2.4 — image-variant discriminator on ocr_results (created 2.1).
    (
        "ocr_results",
        "image_variant",
        "image_variant TEXT NOT NULL DEFAULT 'ORIGINAL' "
        "CHECK (image_variant IN ('ORIGINAL','ENHANCED','BINARIZED'))",
    ),
    # Country-of-origin card — the filed origin (origin_code) on submissions (created 1.2);
    # the country_of_origin check compares it for IMPORTED, auto-passes DOMESTIC. Added so a
    # pre-existing Volume DB (e.g. Railway) gains the column on the next deploy WITHOUT a
    # reseed — the seed-if-empty guard stays dormant on a non-empty DB.
    ("submissions", "country_of_origin", "country_of_origin TEXT"),
)


def _apply_added_columns(conn: sqlite3.Connection) -> None:
    """Idempotently ``ALTER TABLE … ADD COLUMN`` any :data:`_ADDED_COLUMNS` entry
    missing from an already-existing table, BEFORE ``schema.sql`` is replayed (so
    indexes referencing a newly added column succeed on a pre-existing Volume DB).

    On a fresh DB the tables do not exist yet — ``schema.sql`` creates them WITH
    the column — so every check here is a harmless no-op. SQLite ``ADD COLUMN``
    permits a ``NOT NULL`` column when it carries a non-NULL ``DEFAULT``, and
    permits ``CHECK`` constraints; both hold for the entries above. Table/column
    names come only from the constant ledger, never user input.
    """
    for table, column, column_ddl in _ADDED_COLUMNS:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        if table_exists is None:
            continue
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_ddl}")


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

    Establishes WAL mode on the file, applies any pending column additions to
    pre-existing tables (:func:`_apply_added_columns` — the no-framework upgrade
    path for a persistent Volume), then runs ``schema.sql`` (which uses ``CREATE …
    IF NOT EXISTS``, so re-running is safe). Local file work only — no network, so
    this is safe at app startup and under ``--network none``.
    """
    path = Path(db_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(path)
    try:
        # WAL persists on the file; setting it on every init is harmless.
        conn.execute("PRAGMA journal_mode = WAL")
        # Backfill columns added to existing tables BEFORE replaying the schema,
        # so the schema's indexes on those columns don't hit "no such column" on
        # a Volume DB that predates the addition.
        _apply_added_columns(conn)
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
