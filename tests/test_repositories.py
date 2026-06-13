"""Schema + connection + typed-read-layer tests (Story 1.2, AC-1..AC-4)."""

from __future__ import annotations

import sqlite3

import pytest

from app.db import repositories as repo
from app.db.connection import connect, get_connection, init_db


def _make_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26001000000001",
        "beverage_type": "DISTILLED_SPIRITS",
        "brand_name": "Stone's Throw",
        "alcohol_content": "45% Alc./Vol.",
        "net_contents": "750 mL",
        "status": "RECEIVED",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    return int(cur.lastrowid)


def _insert_label_image(conn: sqlite3.Connection, submission_id: int, **overrides) -> int:
    cols = {
        "submission_id": submission_id,
        "image_role": "BRAND",
        "position": 1,
        "filename": "front.jpg",
        "mime_type": "image/jpeg",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO label_images ({', '.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    return int(cur.lastrowid)


# ── AC-1 / AC-2: init, tables, PRAGMAs ───────────────────────────────────────


def test_init_creates_tables(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert {"submissions", "label_images"} <= names


def test_deferred_tables_not_created(tmp_path):
    """Scope guard: tables still deferred to later stories must not exist yet.

    ``ocr_results`` / ``llm_results`` moved out of this guard in Story 2.1, which
    creates them; ``field_comparisons`` / ``checklist_items`` are created in
    Epic 3 (Story 3.1).
    """
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    for deferred in ("field_comparisons", "checklist_items", "review_progress"):
        assert deferred not in names


def test_wal_mode_enabled(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_foreign_keys_on_per_connection(tmp_path):
    db_path = _make_db(tmp_path)
    conn = get_connection(db_path)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_init_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    init_db(db_path)  # must not raise
    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 0


# ── AC-3: typed read layer ───────────────────────────────────────────────────


def test_get_submission_round_trips_as_pydantic(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        sub = repo.get_submission(conn, sub_id)
    assert isinstance(sub, repo.Submission)
    assert sub.ttb_id == "26001000000001"
    assert sub.beverage_type == "DISTILLED_SPIRITS"
    assert sub.brand_name == "Stone's Throw"
    assert sub.status == "RECEIVED"
    assert sub.disposition is None


def test_get_submission_by_ttb_id(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        _insert_submission(conn, ttb_id="26001000000099")
        sub = repo.get_submission_by_ttb_id(conn, "26001000000099")
    assert sub is not None
    assert sub.ttb_id == "26001000000099"


def test_get_submission_missing_returns_none(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        assert repo.get_submission(conn, 9999) is None


def test_list_label_images_ordered(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        _insert_label_image(conn, sub_id, position=2, filename="back.jpg", image_role="BACK")
        _insert_label_image(conn, sub_id, position=1, filename="front.jpg", image_role="BRAND")
        images = repo.list_label_images(conn, sub_id)
    assert [i.position for i in images] == [1, 2]
    assert all(isinstance(i, repo.LabelImage) for i in images)
    assert images[0].filename == "front.jpg"


# ── AC-4: schema invariants ──────────────────────────────────────────────────


def test_invalid_status_rejected(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            _insert_submission(conn, status="BOGUS")


def test_invalid_beverage_type_rejected(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            _insert_submission(conn, beverage_type="SODA")


def test_position_over_ten_rejected(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_label_image(conn, sub_id, position=11)


def test_decided_requires_disposition_and_decided_at(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            _insert_submission(conn, status="DECIDED")  # no disposition/decided_at


def test_disposition_forbidden_on_non_decided(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            _insert_submission(conn, status="RECEIVED", disposition="APPROVED")


def test_decided_row_with_disposition_allowed(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(
            conn,
            status="DECIDED",
            disposition="APPROVED",
            decided_at="2026-06-02T09:00:00Z",
        )
        sub = repo.get_submission(conn, sub_id)
    assert sub is not None
    assert sub.status == "DECIDED"
    assert sub.disposition == "APPROVED"


def test_delete_submission_cascades_to_label_images(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        _insert_label_image(conn, sub_id)
        assert len(repo.list_label_images(conn, sub_id)) == 1
        conn.execute("DELETE FROM submissions WHERE id = ?", (sub_id,))
        conn.commit()
        assert repo.list_label_images(conn, sub_id) == []


# ── Read boundary: enum columns validate as Literal (review P4) ───────────────

_VALID_SUBMISSION_ROW = {
    "id": 1,
    "ttb_id": "26001000000001",
    "beverage_type": "DISTILLED_SPIRITS",
    "status": "RECEIVED",
    "created_at": "2026-06-01T12:00:00Z",
    "updated_at": "2026-06-01T12:00:00Z",
}


def test_read_model_accepts_valid_enums():
    sub = repo.Submission.model_validate(_VALID_SUBMISSION_ROW)
    assert sub.beverage_type == "DISTILLED_SPIRITS"
    assert sub.status == "RECEIVED"


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("beverage_type", "CIDER"),
        ("status", "ARCHIVED"),
        ("engine_verdict", "MAYBE"),
        ("disposition", "PENDING"),
    ],
)
def test_read_model_rejects_out_of_vocab_enum(field: str, bad_value: str):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        repo.Submission.model_validate({**_VALID_SUBMISSION_ROW, field: bad_value})


# ── Volume upgrade: init_db backfills columns added to pre-existing tables ─────
# (Story 2.4 deploy fix.) A persistent Volume DB created by an earlier story is
# missing later columns; `CREATE TABLE IF NOT EXISTS` won't add them, so init_db
# must ALTER them in before the schema's indexes reference them — else startup
# dies with "no such column: image_variant".


def _make_legacy_db(tmp_path):
    """A DB shaped like a pre-2.3/2.4 Volume: `label_images` without the OpenCV
    columns and `ocr_results` without `image_variant`, each carrying only the
    columns the schema's indexes reference."""
    db_path = tmp_path / "legacy.db"
    conn = get_connection(db_path)
    conn.executescript(
        """
        CREATE TABLE label_images (
            id INTEGER PRIMARY KEY,
            submission_id INTEGER,
            filename TEXT NOT NULL
        );
        CREATE TABLE ocr_results (
            id INTEGER PRIMARY KEY,
            label_image_id INTEGER,
            submission_id INTEGER,
            engine_name TEXT NOT NULL
        );
        """
    )
    conn.execute("INSERT INTO ocr_results (engine_name) VALUES ('tesseract')")
    conn.commit()
    conn.close()
    return db_path


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_init_db_backfills_columns_on_legacy_volume_db(tmp_path):
    db_path = _make_legacy_db(tmp_path)

    init_db(db_path)  # must NOT raise "no such column: image_variant"

    with connect(db_path) as conn:
        assert "image_variant" in _columns(conn, "ocr_results")
        assert {
            "enhanced_path",
            "binarized_path",
            "preprocess_log",
            "preprocess_ms",
            "preprocessed_at",
        } <= _columns(conn, "label_images")
        # the index that referenced the new column now builds
        idx = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'idx_ocr_results_variant'"
        ).fetchone()
        assert idx is not None
        # the pre-existing row picks up the NOT NULL default
        row = conn.execute("SELECT image_variant FROM ocr_results").fetchone()
        assert row["image_variant"] == "ORIGINAL"


def test_init_db_backfill_is_idempotent(tmp_path):
    db_path = _make_legacy_db(tmp_path)
    init_db(db_path)
    init_db(db_path)  # second run: column already present, must be a no-op (no raise)
    with connect(db_path) as conn:
        assert "image_variant" in _columns(conn, "ocr_results")
