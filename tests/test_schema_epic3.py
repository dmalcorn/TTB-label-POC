"""Epic-3 schema: field_comparisons + checklist_items + v_field_comparisons (Story 3.1, AC3).

Story 3.1 creates the two analysis-job target tables (written later by 3.2/3.3)
plus the derived ``v_field_comparisons`` view, exactly per database-schema.md
§1.5/§1.6. These tests assert the tables/view exist, the CHECK enums and the
at-most-one-source constraint hold, the indexes are present, the view derives
``extracted_source``, and ``init_db`` stays idempotent.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.db.connection import connect, init_db


def _make_db(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO submissions (ttb_id, beverage_type, status) VALUES (?, ?, ?)",
        ("26001000000001", "DISTILLED_SPIRITS", "RECEIVED"),
    )
    conn.commit()
    assert cur.lastrowid is not None  # guaranteed by a successful INSERT
    return cur.lastrowid


# ── AC3: tables + view exist ─────────────────────────────────────────────────


def test_field_comparisons_and_checklist_items_created(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert {"field_comparisons", "checklist_items"} <= names


def test_v_field_comparisons_view_created(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        views = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'").fetchall()
        }
    assert "v_field_comparisons" in views


def test_expected_indexes_present(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        indexes = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
    assert "idx_field_comparisons_submission" in indexes
    assert "idx_checklist_items_submission" in indexes


# ── field_comparisons column / CHECK contract ────────────────────────────────


def test_field_comparisons_columns(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(field_comparisons)")}
    assert cols == {
        "id",
        "submission_id",
        "field_key",
        "application_value",
        "extracted_value",
        "source_ocr_result_id",
        "source_llm_result_id",
        "match_status",
        "similarity",
        "created_at",
    }


def test_match_status_check_enum_enforced(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO field_comparisons (submission_id, field_key, match_status) "
                "VALUES (?, ?, ?)",
                (sub_id, "brand_name", "BOGUS"),
            )


def test_similarity_range_check_enforced(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO field_comparisons (submission_id, field_key, similarity) "
                "VALUES (?, ?, ?)",
                (sub_id, "brand_name", 1.5),
            )


def test_at_most_one_source_check_enforced(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        # Both source FKs set at once must be rejected (the at-most-one-source CHECK).
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO field_comparisons "
                "(submission_id, field_key, source_ocr_result_id, source_llm_result_id) "
                "VALUES (?, ?, ?, ?)",
                (sub_id, "brand_name", 1, 1),
            )


# ── checklist_items column / CHECK contract ──────────────────────────────────


def test_checklist_items_columns(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(checklist_items)")}
    assert cols == {
        "id",
        "submission_id",
        "check_key",
        "label",
        "cfr_citation",
        "check_type",
        "verdict",
        "detail",
        "field_comparison_id",
        "created_at",
    }


def test_check_type_check_enum_enforced(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO checklist_items (submission_id, check_key, check_type) "
                "VALUES (?, ?, ?)",
                (sub_id, "government_warning", "BOGUS"),
            )


def test_verdict_check_enum_allows_na_per_check(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        # NA is a legal per-check verdict (the input domain); reject anything else.
        for ok in ("PASS", "REVIEW", "FAIL", "NA"):
            conn.execute(
                "INSERT INTO checklist_items (submission_id, check_key, verdict) VALUES (?, ?, ?)",
                (sub_id, "government_warning", ok),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO checklist_items (submission_id, check_key, verdict) VALUES (?, ?, ?)",
                (sub_id, "government_warning", "BOGUS"),
            )


# ── the view derives extracted_source ────────────────────────────────────────


def test_view_derives_extracted_source_for_ocr(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        img = conn.execute(
            "INSERT INTO label_images (submission_id, position, filename) VALUES (?, ?, ?)",
            (sub_id, 1, "front.jpg"),
        ).lastrowid
        ocr_id = conn.execute(
            "INSERT INTO ocr_results (label_image_id, submission_id, engine_name) VALUES (?, ?, ?)",
            (img, sub_id, "tesseract"),
        ).lastrowid
        conn.execute(
            "INSERT INTO field_comparisons (submission_id, field_key, source_ocr_result_id) "
            "VALUES (?, ?, ?)",
            (sub_id, "brand_name", ocr_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT extracted_source FROM v_field_comparisons WHERE submission_id = ?",
            (sub_id,),
        ).fetchone()
    assert row["extracted_source"] == "ocr:tesseract"


def test_view_extracted_source_null_when_no_source(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        conn.execute(
            "INSERT INTO field_comparisons (submission_id, field_key, match_status) "
            "VALUES (?, ?, ?)",
            (sub_id, "brand_name", "MISSING"),
        )
        conn.commit()
        row = conn.execute(
            "SELECT extracted_source FROM v_field_comparisons WHERE submission_id = ?",
            (sub_id,),
        ).fetchone()
    assert row["extracted_source"] is None


# ── idempotence ──────────────────────────────────────────────────────────────


def test_init_db_idempotent_with_new_tables(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    init_db(db_path)  # re-init must not raise (CREATE … IF NOT EXISTS)
    with connect(db_path) as conn:
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert {"field_comparisons", "checklist_items"} <= names
