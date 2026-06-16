"""The ``country_of_origin`` evaluator — the import/domestic Country-of-origin card.

DOMESTIC ⇒ auto-PASS, label side reads "Not imported" (we trust source_of_product, never
hunt for the state). IMPORTED ⇒ field-match the filed country against the label OCR;
located ⇒ PASS, missing/garbled ⇒ REVIEW (defer, never a false reject). Either branch
writes a ``field_comparisons`` row so it renders as a card.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.engine import checks
from app.engine import run_checks as rc
from app.engine.checks.country_of_origin import country_of_origin
from app.engine.rulesets import Check


def _make_db(tmp_path) -> Path:
    db_path = tmp_path / "coo.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26001000000001",
        "beverage_type": "DISTILLED_SPIRITS",
        "brand_name": "Stone's Throw",
        "source_of_product": "IMPORTED",
        "country_of_origin": "Scotland",
        "status": "PROCESSING",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_label_image(conn: sqlite3.Connection, sid: int) -> int:
    cur = conn.execute(
        "INSERT INTO label_images (submission_id, filename, position) VALUES (?, 'f.png', 1)",
        (sid,),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_ocr(conn: sqlite3.Connection, sid: int, img: int, text: str) -> None:
    conn.execute(
        "INSERT INTO ocr_results (label_image_id, submission_id, engine_name, extracted_text, "
        " confidence, ran_on_cpu, image_variant, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (img, sid, "tesseract", text, 0.95, True, "ORIGINAL", "OK"),
    )
    conn.commit()


def _check() -> Check:
    return Check(
        check_key="country_of_origin",
        label="Country of origin",
        check_type="FIELD_MATCH",
        cfr_citation="19 CFR 134.11",
        source_date="2022-01-08",
        strategy="country_of_origin",
        field_key="country_of_origin",
    )


def _ctx(conn, sid) -> checks.CheckContext:
    s = repo.get_submission(conn, sid)
    assert s is not None
    return checks.CheckContext(
        conn=conn, submission=s, ocr_text=repo.get_submission_ocr_text(conn, sid), scratch={}
    )


def _comparison(conn, sid):
    return conn.execute(
        "SELECT * FROM field_comparisons WHERE submission_id = ? ORDER BY id DESC LIMIT 1",
        (sid,),
    ).fetchone()


def test_domestic_auto_passes_with_not_imported(tmp_path):
    """DOMESTIC ⇒ auto-PASS; card shows the filed state on top, 'Not imported' below — and
    we do NOT require the state word on the label."""
    db = _make_db(tmp_path)
    with connect(db) as conn:
        sid = _insert_submission(
            conn,
            beverage_type="MALT_BEVERAGE",
            source_of_product="DOMESTIC",
            country_of_origin="Massachusetts",
        )
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "LEGBITER\nALE\n12 FL OZ")  # no 'Massachusetts' on label
        result = country_of_origin(_check(), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)
    assert result.verdict == "PASS"
    assert row["application_value"] == "Massachusetts"
    assert row["extracted_value"] == "Not imported"
    assert row["match_status"] == "MATCH"


def test_imported_country_on_label_passes(tmp_path):
    """IMPORTED with the country on the label ⇒ field-match MATCH/PASS."""
    db = _make_db(tmp_path)
    with connect(db) as conn:
        sid = _insert_submission(conn, source_of_product="IMPORTED", country_of_origin="Scotland")
        img = _insert_label_image(conn, sid)
        _insert_ocr(
            conn, sid, img, "THE PEDDLER\nSingle Malt Scotch Whisky\nProduct of Scotland\n750 mL"
        )
        result = country_of_origin(_check(), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)
    assert result.verdict == "PASS"
    assert row["application_value"] == "Scotland"
    assert row["match_status"] == "MATCH"


def test_imported_country_absent_defers_to_review_not_fail(tmp_path):
    """IMPORTED but the country isn't legible on the label ⇒ REVIEW (defer), never a FAIL —
    OCR on imported artwork is unreliable."""
    db = _make_db(tmp_path)
    with connect(db) as conn:
        sid = _insert_submission(conn, source_of_product="IMPORTED", country_of_origin="Scotland")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "THE PEDDLER\nSingle Malt Whisky\n750 mL")  # no 'Scotland'
        result = country_of_origin(_check(), _ctx(conn, sid))
    assert result.verdict == "REVIEW"


def test_integration_through_run_checks_renders_a_card(tmp_path):
    """End-to-end: run_checks writes a country_of_origin field_comparison + a FIELD_MATCH
    checklist row linked to it — i.e. it renders as a comparison card, not a flag-only row."""
    db = _make_db(tmp_path)
    with connect(db) as conn:
        sid = _insert_submission(
            conn,
            beverage_type="WINE",
            source_of_product="IMPORTED",
            country_of_origin="Spain",
            class_type_designation="Dessert Wine",
        )
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "LA RUBIA\nDessert Wine\nProduct of Spain\n750 mL")
        s = repo.get_submission(conn, sid)
        assert s is not None
        rc.run_checks(conn, s)
        comp = conn.execute(
            "SELECT 1 FROM field_comparisons "
            "WHERE submission_id = ? AND field_key = 'country_of_origin'",
            (sid,),
        ).fetchone()
        item = conn.execute(
            "SELECT check_type, field_comparison_id FROM checklist_items "
            "WHERE submission_id = ? AND check_key = 'country_of_origin'",
            (sid,),
        ).fetchone()
    assert comp is not None  # a comparison row exists → a card
    assert item["check_type"] == "FIELD_MATCH"
    assert item["field_comparison_id"] is not None
