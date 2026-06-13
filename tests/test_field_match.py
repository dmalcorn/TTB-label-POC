"""Field-match evaluator with tolerance bands (Story 3.3, AC1–AC4).

Offline, fast, deterministic — no real OCR/LLM call. The evaluator is exercised
directly against a temp DB (seeded OCR text / a fake LLM extraction JSON), and the
integration path runs through Story 3.2's ``run_checks`` so the spirits ruleset's
matchable fields now produce real verdicts + linked ``field_comparison_id``s.

Scope guard (3.3): only the ``field_match`` strategy + its three-band tolerance +
the ``field_comparisons`` writes. The Government Warning (3.4), per-type format
checks (3.5), the hybrid class/type validity judgment (3.6), and flag-only checks
(3.7) are NOT asserted here.
"""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.engine import checks
from app.engine import run_checks as rc
from app.engine.checks import field_match as fm
from app.engine.rulesets import Check, get_ruleset

# ── shared fixtures (mirror tests/test_run_checks.py helpers) ────────────────


def _make_db(tmp_path) -> Path:
    db_path = tmp_path / "field_match.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26001000000001",
        "beverage_type": "DISTILLED_SPIRITS",
        "brand_name": "Stone's Throw",
        "alcohol_content": "45% Alc./Vol.",
        "net_contents": "750 mL",
        "applicant_name_address": "Acme Distillers, Louisville, KY",
        "class_type_designation": "Kentucky Straight Bourbon Whiskey",
        "status": "PROCESSING",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_label_image(conn: sqlite3.Connection, submission_id: int) -> int:
    cur = conn.execute(
        "INSERT INTO label_images (submission_id, filename, position) VALUES (?, ?, ?)",
        (submission_id, "front.png", 1),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_ocr(
    conn: sqlite3.Connection,
    submission_id: int,
    label_image_id: int,
    text: str,
    *,
    confidence: float = 0.95,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO ocr_results
            (label_image_id, submission_id, engine_name, extracted_text,
             confidence, ran_on_cpu, image_variant, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (label_image_id, submission_id, "tesseract", text, confidence, True, "ORIGINAL", "OK"),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_llm_extraction(conn: sqlite3.Connection, submission_id: int, fields: dict) -> int:
    cur = conn.execute(
        """
        INSERT INTO llm_results
            (submission_id, task, model_name, model_id, provider, result_text, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            submission_id,
            "extract_fields",
            "gpt-x",
            "gpt-x-mini",
            "openai",
            json.dumps(fields),
            "OK",
        ),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _check(field_key: str, *, check_key: str | None = None) -> Check:
    return Check(
        check_key=check_key or field_key,
        label=field_key,
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 5.64",
        source_date="2022-01-08",
        strategy="field_match",
        field_key=field_key,
    )


def _ctx(conn, submission_id, **kw) -> checks.CheckContext:
    submission = repo.get_submission(conn, submission_id)
    assert submission is not None
    return checks.CheckContext(
        conn=conn,
        submission=submission,
        ocr_text=kw.get("ocr_text", repo.get_submission_ocr_text(conn, submission_id)),
        scratch=kw.get("scratch", {}),
    )


def _comparison(conn, submission_id) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM field_comparisons WHERE submission_id = ? ORDER BY id DESC LIMIT 1",
        (submission_id,),
    ).fetchone()


# ── registration / wiring ────────────────────────────────────────────────────


def test_field_match_is_registered_under_its_strategy():
    """Task 1: the evaluator plugs into the 3.2 dispatch seam under ``field_match``."""
    assert checks.get_evaluator("field_match") is fm.field_match


def test_spirits_matchable_fields_route_to_field_match():
    """AC1: the four matchable spirits checks dispatch to ``field_match``."""
    by_key = {c.check_key: c for c in get_ruleset("DISTILLED_SPIRITS")}
    for key in ("brand_name", "alcohol_content", "net_contents", "name_address"):
        assert by_key[key].strategy == "field_match"


# ── AC3: the two canonical cases ─────────────────────────────────────────────


def test_stones_throw_incidental_case_punctuation_passes(tmp_path):
    """AC3 / SM-C2: "STONE'S THROW" vs "Stone's Throw" ⇒ PASS / MATCH (zero false-FAIL)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "STONE'S THROW\nKentucky Bourbon")
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)

    assert result.verdict == "PASS"
    assert row["match_status"] == "MATCH"
    assert row["similarity"] == pytest.approx(1.0)


def test_curly_apostrophe_variant_also_passes(tmp_path):
    """AC3: the curly-apostrophe form of the same name also PASSes (NFKC + quote fold)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone\u2019s Throw")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "stone's throw")
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()

    assert result.verdict == "PASS"


def test_cross_type_abv_substantive_mismatch_fails(tmp_path):
    """AC3: application ABV 45% vs label 40% ⇒ FAIL (beyond ±0.3-pt tolerance)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, alcohol_content="45% Alc./Vol.")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "40% Alc./Vol.")
        result = fm.field_match(_check("alcohol_content"), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)

    assert result.verdict == "FAIL"
    assert row["match_status"] == "MISMATCH"


# ── AC2: the three bands ─────────────────────────────────────────────────────


def test_zero_false_fail_class_all_pass(tmp_path):
    """AC2: the broader incidental-difference class (case, whitespace, trailing
    punctuation, NFKC) all normalize-equal ⇒ PASS."""
    db_path = _make_db(tmp_path)
    cases = [
        ("Old Reserve", "OLD RESERVE"),
        ("Old  Reserve", "Old Reserve"),  # collapsed whitespace
        ("Old Reserve.", "Old Reserve"),  # trailing punctuation
        ("Café Noir", "Cafe\u0301 Noir"),  # NFKC normalization
    ]
    with connect(db_path) as conn:
        for i, (app_val, ocr_val) in enumerate(cases):
            sid = _insert_submission(conn, brand_name=app_val, ttb_id=f"260010000001{i:02d}")
            img = _insert_label_image(conn, sid)
            _insert_ocr(conn, sid, img, ocr_val)
            result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
            conn.commit()
            assert result.verdict == "PASS", f"{app_val!r} vs {ocr_val!r}"


def test_near_miss_text_goes_to_review(tmp_path):
    """AC2: a high-but-not-1.0 similarity text difference ⇒ REVIEW (false-reject safety
    valve), not FAIL."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "Stones Throwe")  # OCR slip, still close
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)

    assert result.verdict == "REVIEW"
    assert row["match_status"] == "MISMATCH"
    assert 0.0 < row["similarity"] < 1.0


def test_substantive_text_mismatch_fails(tmp_path):
    """AC2: a genuinely different brand name (low similarity) ⇒ FAIL."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "Mountain Peak Vodka XYZ")
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()

    assert result.verdict == "FAIL"


def test_abv_within_tolerance_passes(tmp_path):
    """AC2/AC3: app 45% vs label 45.2% (within ±0.3-pt) ⇒ PASS."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, alcohol_content="45%")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "45.2% Alc./Vol.")
        result = fm.field_match(_check("alcohol_content"), _ctx(conn, sid))
        conn.commit()

    assert result.verdict == "PASS"


def test_abv_just_outside_tolerance_fails(tmp_path):
    """AC2/AC3: app 45% vs label 45.5% (outside ±0.3-pt) ⇒ FAIL."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, alcohol_content="45%")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "45.5% Alc./Vol.")
        result = fm.field_match(_check("alcohol_content"), _ctx(conn, sid))
        conn.commit()

    assert result.verdict == "FAIL"


def test_net_contents_unit_variant_passes_but_value_change_fails(tmp_path):
    """net_contents standards of fill are discrete: 750 mL vs 750 ml ⇒ PASS,
    750 mL vs 700 mL ⇒ FAIL (exact-after-normalize, tolerance 0)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid_ok = _insert_submission(conn, net_contents="750 mL", ttb_id="26001000000201")
        img_ok = _insert_label_image(conn, sid_ok)
        _insert_ocr(conn, sid_ok, img_ok, "750 ml")
        ok = fm.field_match(_check("net_contents"), _ctx(conn, sid_ok))

        sid_bad = _insert_submission(conn, net_contents="750 mL", ttb_id="26001000000202")
        img_bad = _insert_label_image(conn, sid_bad)
        _insert_ocr(conn, sid_bad, img_bad, "700 ml")
        bad = fm.field_match(_check("net_contents"), _ctx(conn, sid_bad))
        conn.commit()

    assert ok.verdict == "PASS"
    assert bad.verdict == "FAIL"


def test_unparseable_numeric_extracted_is_unverifiable_review(tmp_path):
    """AC2: an unparseable extracted numeric side ⇒ UNVERIFIABLE / REVIEW."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, alcohol_content="45%")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "alcohol by volume not legible")
        result = fm.field_match(_check("alcohol_content"), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)

    assert result.verdict == "REVIEW"
    assert row["match_status"] in {"UNVERIFIABLE", "MISSING"}


# ── review-hardening regressions (zero-false-FAIL, SM-C2) ────────────────────


def test_numeric_wrong_unit_only_stray_is_unverifiable_not_fail(tmp_path):
    """Regression: when the label carries NO same-unit number+unit token for the
    field, a stray number in a *different* unit must NOT be coerced into a FAIL.
    The honest answer is UNVERIFIABLE / REVIEW (a wrong-unit match is unverifiable,
    not a substantive mismatch — false FAIL is the costliest error, SM-C2)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, net_contents="750 mL")
        img = _insert_label_image(conn, sid)
        # OCR has a "45% ..." number but NO "mL" net-contents token at all.
        _insert_ocr(conn, sid, img, "STONE'S THROW\n45% Alc./Vol.\nKentucky Bourbon")
        result = fm.field_match(_check("net_contents"), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)

    assert result.verdict == "REVIEW"
    assert row["match_status"] == "UNVERIFIABLE"


def test_low_ocr_confidence_softens_fail_to_review(tmp_path):
    """Regression: a substantive text MISMATCH from a LOW-confidence OCR read is
    softened FAIL→REVIEW (the low-confidence valve applies symmetrically, not only
    to PASS) — a shaky read must not drive a false reject."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "MOUNTAIN PEAK VODKA XYZ", confidence=0.10)
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()

    assert result.verdict == "REVIEW"


def test_substantive_fail_survives_when_ocr_confidence_is_high(tmp_path):
    """Guard for the valve above: the SAME substantive MISMATCH at HIGH confidence
    still FAILs — the valve keys off confidence, it does not blanket-soften FAILs."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "MOUNTAIN PEAK VODKA XYZ", confidence=0.95)
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()

    assert result.verdict == "FAIL"


def test_llm_non_scalar_value_degrades_to_ocr_fallback(tmp_path):
    """Regression: a non-scalar LLM field value (list/dict/bool) is NOT stringified
    into a bogus extracted value — it is dropped, and the evaluator falls back to the
    OCR path (which supplies the source FK and a truthful comparison)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        img = _insert_label_image(conn, sid)
        ocr_id = _insert_ocr(conn, sid, img, "Stone's Throw\nKentucky Bourbon")
        _insert_llm_extraction(conn, sid, {"brand_name": ["Stone's Throw", "Other"]})
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)

    # Non-scalar LLM value dropped → OCR fallback owns the comparison + the FK.
    assert row["source_llm_result_id"] is None
    assert row["source_ocr_result_id"] == ocr_id
    assert result.verdict == "PASS"


def test_llm_bare_numeric_abv_is_used(tmp_path):
    """Guard for the scalar filter above: a scalar LLM value (here a string ABV) is
    still used as the extracted value — only non-scalars are dropped."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, alcohol_content="45% Alc./Vol.")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "totally different ocr text")
        llm_id = _insert_llm_extraction(conn, sid, {"alcohol_content": "45% Alc./Vol."})
        result = fm.field_match(_check("alcohol_content"), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)

    assert result.verdict == "PASS"
    assert row["source_llm_result_id"] == llm_id


def test_missing_extracted_value_is_review_not_fail(tmp_path):
    """AC2: a value the engine cannot locate ⇒ MISSING / REVIEW (defer to human,
    never FAIL on absence — that would be a false reject)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "completely unrelated text about nothing")
        # No fuzzy locate possible → MISSING/REVIEW (very low similarity falls to FAIL only
        # when a candidate exists; with no candidate at all it is MISSING).
        ctx = _ctx(conn, sid, ocr_text="")  # empty OCR text ⇒ nothing to locate
        result = fm.field_match(_check("brand_name"), ctx)
        conn.commit()
        row = _comparison(conn, sid)

    assert result.verdict == "REVIEW"
    assert row["match_status"] == "MISSING"


def test_application_value_missing_is_review(tmp_path):
    """AC2: a missing APPLICATION value ⇒ UNVERIFIABLE / REVIEW (nothing to compare)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name=None)
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "Some Label Text")
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)

    assert result.verdict == "REVIEW"
    assert row["match_status"] == "UNVERIFIABLE"


def test_low_ocr_confidence_forces_review_even_on_match(tmp_path):
    """AC2: when the source OCR row's confidence is below the floor, an apparent
    match is forced to REVIEW (cannot trust the extraction — the cross-type-trap
    safety valve)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "STONE'S THROW", confidence=0.10)
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()

    assert result.verdict == "REVIEW"


# ── AC4: provenance ──────────────────────────────────────────────────────────


def test_ocr_path_sets_exactly_one_source_fk_and_raw_values(tmp_path):
    """AC4: the OCR path writes both raw values, a match_status, a similarity, and
    sets source_ocr_result_id (and NOT source_llm_result_id)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        img = _insert_label_image(conn, sid)
        ocr_id = _insert_ocr(conn, sid, img, "STONE'S THROW")
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)

    assert result.field_comparison_id == row["id"]
    assert row["application_value"] == "Stone's Throw"  # RAW, un-normalized
    assert row["extracted_value"]  # the located raw text
    assert row["source_ocr_result_id"] == ocr_id
    assert row["source_llm_result_id"] is None
    assert row["match_status"] == "MATCH"
    assert row["similarity"] is not None


def test_llm_extraction_path_sets_llm_source_fk(tmp_path):
    """AC4 / Task 2: when a structured LLM extraction exists, the evaluator parses it
    per field_key and sets source_llm_result_id (preferred over OCR)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "totally different ocr text")
        llm_id = _insert_llm_extraction(conn, sid, {"brand_name": "Stone's Throw"})
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid))
        conn.commit()
        row = _comparison(conn, sid)

    assert result.verdict == "PASS"
    assert row["source_llm_result_id"] == llm_id
    assert row["source_ocr_result_id"] is None


def test_llm_extraction_from_scratch_is_used(tmp_path):
    """Task 2: the LLM extraction may arrive via ctx.scratch["llm_extraction"] (the
    pipeline forward-seam) as well as the persisted llm_results row."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, brand_name="Stone's Throw")
        llm_id = _insert_llm_extraction(conn, sid, {"brand_name": "Stone's Throw"})
        scratch = {"llm_extraction": json.dumps({"brand_name": "Stone's Throw"})}
        result = fm.field_match(_check("brand_name"), _ctx(conn, sid, scratch=scratch))
        conn.commit()
        row = _comparison(conn, sid)

    assert result.verdict == "PASS"
    # The persisted OK row supplies the provenance FK even when scratch supplies the text.
    assert row["source_llm_result_id"] == llm_id


# ── named tunable constants ──────────────────────────────────────────────────


def test_tolerance_and_threshold_constants_are_exposed():
    """Task 1: thresholds/tolerances are named, tunable module constants."""
    assert fm.ABV_TOLERANCE == Decimal("0.3")
    assert fm.NET_CONTENTS_TOLERANCE == Decimal("0")
    assert 0.0 < fm.REVIEW_FLOOR < 1.0
    assert 0.0 < fm.OCR_CONFIDENCE_FLOOR < 1.0


# ── integration through Story 3.2's run_checks ───────────────────────────────


def test_integration_run_checks_produces_real_field_match_verdicts(tmp_path):
    """Task 4: through run_checks, a spirits submission's matchable checks now produce
    real verdicts + linked field_comparison_ids, and engine_verdict rolls up.

    A clean, matching label ⇒ the field-match checks PASS; the still-placeholder
    checks (gov warning, class/type, sfov) REVIEW, so the submission rolls up to
    REVIEW — but the matchable rows are real, not placeholders."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        img = _insert_label_image(conn, sid)
        _insert_ocr(
            conn,
            sid,
            img,
            "STONE'S THROW\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol.\n"
            "750 mL\nAcme Distillers, Louisville, KY",
        )
        submission = repo.get_submission(conn, sid)
        rolled = rc.run_checks(conn, submission)
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM checklist_items WHERE submission_id = ? ORDER BY id", (sid,)
        ).fetchall()

    by_key = {r["check_key"]: r for r in rows}
    # The field-match checks carry a real linked comparison and a non-placeholder detail.
    for key in ("brand_name", "alcohol_content", "net_contents", "name_address"):
        assert by_key[key]["verdict"] == "PASS", key
        assert by_key[key]["field_comparison_id"] is not None, key
    assert rolled in {"PASS", "REVIEW", "FAIL"}


def test_integration_substantive_mismatch_rolls_up_to_fail(tmp_path):
    """Task 4: a substantive ABV mismatch through run_checks drives engine_verdict to
    FAIL (any FAIL ⇒ FAIL precedence)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, alcohol_content="45% Alc./Vol.")
        img = _insert_label_image(conn, sid)
        _insert_ocr(
            conn,
            sid,
            img,
            "STONE'S THROW\nKentucky Straight Bourbon Whiskey\n40% Alc./Vol.\n"
            "750 mL\nAcme Distillers, Louisville, KY",
        )
        submission = repo.get_submission(conn, sid)
        rolled = rc.run_checks(conn, submission)
        conn.commit()
        stored = repo.get_submission(conn, sid).engine_verdict

    assert rolled == "FAIL"
    assert stored == "FAIL"
