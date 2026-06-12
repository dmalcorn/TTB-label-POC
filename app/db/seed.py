"""Seed the mock COLA corpus from the committed fixtures.

Stdlib only (``csv``, ``json``, ``sqlite3``) — no OpenCV/imaging dependency at
runtime. Reads ``fixtures/ground_truth.csv`` (produced by the dev-time
``fixtures/generate.py``) and inserts, per row, the ``submissions`` APPLICATION
fields, its ``label_images`` rows (from the row's JSON image manifest), and one
``SEEDED`` ``audit_events`` row.

Transactional and idempotent: a re-run clears and reloads the corpus in a single
transaction (no duplicates) — the reset-friendly basis Epic 6's ``POST /reset``
calls. The Ground Truth (``gt_*``) columns stay in the CSV for the Epic-5
benchmark; the seed writes only APPLICATION values to ``submissions``.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from app.config import get_settings
from app.db.connection import get_connection, init_db

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
MAX_IMAGES = 10

# APPLICATION columns written to `submissions` (subset of the CSV; gt_*/design
# columns are NOT stored — they live in the CSV for the benchmark).
_SUBMISSION_COLUMNS = [
    "ttb_id",
    "serial_number",
    "beverage_type",
    "source_of_product",
    "application_type",
    "brand_name",
    "fanciful_name",
    "class_type_designation",
    "applicant_name_address",
    "mailing_address",
    "plant_registry_no",
    "alcohol_content",
    "net_contents",
    "grape_varietal",
    "wine_appellation",
    "wine_vintage",
    "formula_id",
    "phone",
    "email",
    "application_date",
    "submitted_at",
]


def _nullify(value: str | None) -> str | None:
    """Empty CSV cells become NULL so enum CHECK constraints aren't tripped by ''."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def _insert_submission(conn: sqlite3.Connection, row: dict) -> int:
    cols = [*_SUBMISSION_COLUMNS, "status"]
    values = [_nullify(row.get(c)) for c in _SUBMISSION_COLUMNS] + ["RECEIVED"]
    placeholders = ", ".join("?" for _ in cols)
    cur = conn.execute(
        f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})",
        values,
    )
    return int(cur.lastrowid)


def _insert_label_images(conn: sqlite3.Connection, submission_id: int, images: list[dict]) -> None:
    if len(images) > MAX_IMAGES:
        raise ValueError(
            f"submission has {len(images)} images; the maximum is {MAX_IMAGES} "
            "(docs/image-handling.md §1)"
        )
    for img in images:
        if not isinstance(img, dict) or "filename" not in img:
            raise ValueError(
                f"image manifest entry must be an object with a 'filename'; got {img!r}"
            )
        conn.execute(
            "INSERT INTO label_images "
            "(submission_id, image_role, position, filename, mime_type, "
            " width_px, height_px, file_size_bytes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                submission_id,
                img.get("role"),
                img.get("position"),
                img["filename"],
                img.get("mime_type"),
                img.get("width_px"),
                img.get("height_px"),
                img.get("file_size_bytes"),
            ),
        )


def _parse_image_manifest(raw: str | None, ttb_id: str | None) -> list[dict]:
    """Parse a row's ``images`` JSON manifest, failing with the row's ttb_id."""
    try:
        images = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"row ttb_id={ttb_id!r}: malformed images JSON: {exc}") from exc
    if not isinstance(images, list):
        raise ValueError(
            f"row ttb_id={ttb_id!r}: images JSON must be an array, got {type(images).__name__}"
        )
    return images


def seed(db_path: str | Path, fixtures_dir: str | Path = FIXTURES_DIR) -> int:
    """Load the fixture corpus into the database. Returns the submission count.

    Idempotent: clears `submissions` (FK cascade clears `label_images` /
    `audit_events`) then reloads, all in one transaction.
    """
    csv_path = Path(fixtures_dir) / "ground_truth.csv"
    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    conn = get_connection(db_path)
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM submissions")  # cascades to children
        for row in rows:
            submission_id = _insert_submission(conn, row)
            images = _parse_image_manifest(row.get("images"), row.get("ttb_id"))
            _insert_label_images(conn, submission_id, images)
            conn.execute(
                "INSERT INTO audit_events (submission_id, event_type, actor, to_status, note) "
                "VALUES (?, 'SEEDED', 'system:seed', 'RECEIVED', ?)",
                (submission_id, f"seeded {row.get('scenario', '')}".strip()),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return len(rows)


def main() -> None:
    """`python -m app.db.seed` — init the configured DB then seed it."""
    db_path = get_settings().database_path
    init_db(db_path)
    count = seed(db_path)
    print(f"Seeded {count} submissions into {db_path}")


if __name__ == "__main__":
    main()
