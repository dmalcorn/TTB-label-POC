"""Seed + fixture-corpus tests (Story 1.3, AC-1..AC-5)."""

from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

import pytest

from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.db.seed import FIXTURES_DIR, _insert_label_images, _parse_image_manifest, seed

GROUND_TRUTH_CSV = FIXTURES_DIR / "ground_truth.csv"
DATA_DICTIONARY = Path(__file__).resolve().parents[1] / "docs" / "data-dictionary.md"

SUBMISSION_APPLICATION_FIELDS = [
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


def _seeded_db(tmp_path):
    db_path = tmp_path / "seed.db"
    init_db(db_path)
    count = seed(db_path)
    return db_path, count


def _csv_rows() -> list[dict]:
    with GROUND_TRUTH_CSV.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ── AC-1: corpus loaded across all three types ───────────────────────────────


def test_seed_loads_curated_corpus(tmp_path):
    _db, count = _seeded_db(tmp_path)
    # A small, curated real-COLA corpus (3 per beverage type); kept a flexible band so the
    # set can grow without churning this bound.
    assert 6 <= count <= 60


def test_all_three_beverage_types_present(tmp_path):
    db_path, _ = _seeded_db(tmp_path)
    with connect(db_path) as conn:
        types = {
            r["beverage_type"]
            for r in conn.execute("SELECT DISTINCT beverage_type FROM submissions")
        }
    assert types == {"DISTILLED_SPIRITS", "WINE", "MALT_BEVERAGE"}


def test_every_submission_has_seeded_event_and_images(tmp_path):
    db_path, count = _seeded_db(tmp_path)
    with connect(db_path) as conn:
        seeded = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type='SEEDED'"
        ).fetchone()[0]
        without_images = conn.execute(
            "SELECT COUNT(*) FROM submissions s "
            "WHERE NOT EXISTS (SELECT 1 FROM label_images li WHERE li.submission_id = s.id)"
        ).fetchone()[0]
    assert seeded == count
    assert without_images == 0


# ── AC-4: multi-image round-trip + 11th rejected ─────────────────────────────


def test_largest_submission_round_trips(tmp_path):
    db_path, _ = _seeded_db(tmp_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT submission_id, COUNT(*) AS n FROM label_images "
            "GROUP BY submission_id ORDER BY n DESC LIMIT 1"
        ).fetchone()
        assert row is not None and row["n"] >= 2, "expected a multi-image submission"
        images = repo.list_label_images(conn, row["submission_id"])
    # positions round-trip contiguously 1..N (front, back, …)
    assert [i.position for i in images] == list(range(1, len(images) + 1))


def test_eleventh_image_rejected_by_seed_validation(tmp_path):
    db_path, _ = _seeded_db(tmp_path)
    eleven = [{"filename": f"x{i}.jpg", "position": i, "role": "OTHER"} for i in range(1, 12)]
    with connect(db_path) as conn:
        sub_id = conn.execute("SELECT id FROM submissions LIMIT 1").fetchone()["id"]
        with pytest.raises(ValueError, match="maximum is 10"):
            _insert_label_images(conn, sub_id, eleven)


def test_eleventh_position_rejected_by_db_check(tmp_path):
    db_path, _ = _seeded_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = conn.execute("SELECT id FROM submissions LIMIT 1").fetchone()["id"]
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO label_images (submission_id, position, filename) VALUES (?, 11, ?)",
                (sub_id, "eleventh.jpg"),
            )


# ── AC-2: corpus spread — all three types, with an outcome mix ────────────────


def test_corpus_has_type_and_outcome_spread():
    rows = _csv_rows()
    types = {r["beverage_type"] for r in rows}
    assert types == {"DISTILLED_SPIRITS", "WINE", "MALT_BEVERAGE"}
    verdicts = {r["expected_verdict"] for r in rows}
    # the curated corpus carries at least one engineered FAIL alongside the REVIEW default
    assert "FAIL" in verdicts
    assert "REVIEW" in verdicts


# ── AC-3: Ground Truth diverges from APPLICATION on the engineered violation ──


def test_violations_have_divergent_ground_truth():
    rows = _csv_rows()
    # the engineered ABV failure files a value off from the on-label truth
    abv = next(r for r in rows if r["violation_kind"] == "abv_mismatch")
    assert abv["gt_alcohol_content"] != abv["alcohol_content"]


def test_authored_matches_have_aligned_ground_truth():
    """Real rows authored to MATCH their label carry gt_alcohol_content == the filed
    value (the answer key mirrors the application value, except the engineered mismatch)."""
    rows = _csv_rows()
    matched = [r for r in rows if r["violation_kind"] != "abv_mismatch" and r["alcohol_content"]]
    assert matched, "expected at least one authored-match row with an ABV"
    for r in matched:
        assert r["gt_alcohol_content"] == r["alcohol_content"]


# ── AC-5: idempotency, synthetic-only, data-dictionary coverage ──────────────


def test_seed_is_idempotent(tmp_path):
    db_path = tmp_path / "seed.db"
    init_db(db_path)
    first = seed(db_path)
    second = seed(db_path)
    assert first == second
    with connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        distinct_ttb = conn.execute("SELECT COUNT(DISTINCT ttb_id) FROM submissions").fetchone()[0]
    assert total == second
    assert distinct_ttb == second  # ttb_id stayed unique, no duplicates


def test_all_images_are_synthetic_jpegs():
    rows = _csv_rows()
    import json

    for r in rows:
        for img in json.loads(r["images"]):
            assert img["mime_type"] == "image/jpeg"
            assert (FIXTURES_DIR / "images" / img["filename"]).exists()


def test_every_seeded_field_is_documented():
    if not DATA_DICTIONARY.exists():
        pytest.skip("data-dictionary.md not present (docs not shipped in the runtime image)")
    text = DATA_DICTIONARY.read_text(encoding="utf-8")
    documented = set(re.findall(r"`([a-z_]+)`", text))
    missing = [c for c in SUBMISSION_APPLICATION_FIELDS if c not in documented]
    assert not missing, f"undocumented seeded fields: {missing}"


# ── Ingestion hardening: opaque errors carry the row's ttb_id (review P3) ─────


def test_parse_image_manifest_rejects_malformed_json():
    with pytest.raises(ValueError, match="26150000000099"):
        _parse_image_manifest("{not valid json", "26150000000099")


def test_parse_image_manifest_rejects_non_list():
    with pytest.raises(ValueError, match="must be an array"):
        _parse_image_manifest('{"position": 1}', "26150000000099")


def test_parse_image_manifest_empty_or_absent_yields_empty_list():
    assert _parse_image_manifest(None, "x") == []
    assert _parse_image_manifest("", "x") == []
    assert _parse_image_manifest("[]", "x") == []


def test_insert_label_images_rejects_entry_without_filename(tmp_path):
    # The guard fires before any DB write, so no real submission row is needed.
    db_path = tmp_path / "t.db"
    init_db(db_path)
    with connect(db_path) as conn:
        with pytest.raises(ValueError, match="filename"):
            _insert_label_images(conn, 1, [{"role": "BRAND", "position": 1}])
