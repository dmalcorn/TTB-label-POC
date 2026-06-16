"""Per-type deterministic format checks (Story 3.5, AC1–AC4).

Deterministic, OFFLINE, no model anywhere (this check is deterministic by
contract — it must never touch an LLM). Covers:

  - **AC2** the cross-type ABV false-reject trap: spirits ALWAYS-required (absent
    → FAIL), table-wine ≤14% and malt-beverage NOT failed on absence.
  - **AC3** standards-of-fill table lookup (750 mL pass / off-standard FAIL) and
    proof↔ABV (2×) consistency.
  - **AC4** an unevaluable conditional → REVIEW with explanation, never a guess.
  - **AC1** the no-LLM + CFR-as-data guards (mirror test_government_warning.py).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.engine import checks
from app.engine import run_checks as rc
from app.engine.checks import format_checks as fc
from app.engine.rulesets import Check
from app.engine.rulesets import format_checks as fc_data

# ── shared fixtures (mirror tests/test_government_warning.py) ─────────────────


_DB_SEQ = 0
_TTB_SEQ = 0


def _make_db(tmp_path) -> Path:
    """A FRESH db file per call (unique name) so repeated calls in one test never collide."""
    global _DB_SEQ
    _DB_SEQ += 1
    db_path = tmp_path / f"format_checks_{_DB_SEQ}.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    global _TTB_SEQ
    _TTB_SEQ += 1
    cols = {
        "ttb_id": f"260010000000{_TTB_SEQ:02d}",
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


def _check(check_key: str, cfr_citation: str = "27 CFR 5.65") -> Check:
    return Check(
        check_key=check_key,
        label=check_key.replace("_", " ").title(),
        check_type="DETERMINISTIC",
        cfr_citation=cfr_citation,
        source_date="2022-01-08",
        strategy="format_checks",
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


def _evaluate(tmp_path, check_key, ocr_text, *, cfr="27 CFR 5.65", **subm):
    """Run one format check against a submission with the given seeded OCR text."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, **subm)
        img = _insert_label_image(conn, sid)
        if ocr_text is not None:
            _insert_ocr(conn, sid, img, ocr_text)
        result = fc.format_checks(_check(check_key, cfr), _ctx(conn, sid))
    return result


# ── registration / wiring ────────────────────────────────────────────────────


def test_format_checks_is_registered_under_its_strategy():
    """The evaluator plugs into the 3.2 dispatch seam under ``format_checks``."""
    assert checks.get_evaluator("format_checks") is fc.format_checks


# ── AC2: the cross-type ABV false-reject trap ────────────────────────────────


def test_abv_spirits_present_passes(tmp_path):
    result = _evaluate(tmp_path, "abv_format", "45% Alc./Vol.\n750 mL")
    assert result.verdict == "PASS"


def test_abv_spirits_absent_fails(tmp_path):
    """Spirits ABV is ALWAYS required (§5.65) — absent ⇒ FAIL with citation."""
    result = _evaluate(tmp_path, "abv_format", "STONE'S THROW BOURBON\n750 mL")
    assert result.verdict == "FAIL"


def test_abv_table_wine_under_14_absent_not_failed(tmp_path):
    """≤14% table wine without ABV is COMPLIANT — must NOT be failed (the trap)."""
    result = _evaluate(
        tmp_path,
        "abv_format",
        "SUNNY VALLEY TABLE WINE\n750 mL",
        cfr="27 CFR 4.36",
        beverage_type="WINE",
        alcohol_content=None,
    )
    assert result.verdict != "FAIL"


def test_abv_malt_beverage_absent_not_failed(tmp_path):
    """Malt beverage ABV is usually optional — absent ⇒ NOT a FAIL (the trap).

    The added-flavor (§7.65) trigger is NOT determinable from the label, so the honest
    verdict is REVIEW (AC4 "when unsure, REVIEW, never guess") — never a guessed PASS
    and never a FAIL.
    """
    result = _evaluate(
        tmp_path,
        "abv_format",
        "HOPPY LAGER\n12 FL OZ",
        cfr="27 CFR 7.65",
        beverage_type="MALT_BEVERAGE",
        alcohol_content=None,
    )
    assert result.verdict != "FAIL"
    assert result.verdict == "REVIEW"
    assert result.detail


def test_abv_bare_percent_without_abbreviation_fails(tmp_path):
    """A bare ``45%`` with NO accepted abbreviation word is malformed ⇒ FAIL.

    Regression: ``%`` is the value marker, not an abbreviation — it must not satisfy the
    §5.65 abbreviation-format requirement on its own (the malformed-but-present path).
    """
    result = _evaluate(tmp_path, "abv_format", "STONE'S THROW\n45%\n750 mL")
    assert result.verdict == "FAIL"


def test_abv_abbreviation_not_matched_inside_unrelated_word(tmp_path):
    """Regression: ``vol``/``alc`` must match as WORDS, not substrings (revolver/calcium).

    A bare ``45%`` whose only ``alc``/``vol`` substring sits inside an unrelated brand
    word must still read malformed (FAIL), not spuriously well-formed.
    """
    result = _evaluate(tmp_path, "abv_format", "REVOLVER BRAND\n45%\n750 mL")
    assert result.verdict == "FAIL"


def test_abv_spirits_promo_percent_not_read_as_abv(tmp_path):
    """Regression: a promotional ``30% OFF`` (no alcohol cue) is NOT read as the ABV.

    A distilled-spirits label carrying only a promo ``%`` and no real ABV statement must
    FAIL (ABV always required) — the stray ``%`` must not be scavenged into a PASS.
    """
    result = _evaluate(tmp_path, "abv_format", "STONE'S THROW BOURBON\nGET 30% OFF\n750 mL")
    assert result.verdict == "FAIL"


def test_abv_wine_unreadable_application_abv_reviews_not_passes(tmp_path):
    """Regression (AC4): WINE, no label ABV, UNREADABLE application ABV ⇒ REVIEW, not PASS.

    An unparseable application ABV means we cannot confirm the §4.36 ">14%" rule even
    applies — defer to the human rather than guess a "may omit" PASS.
    """
    result = _evaluate(
        tmp_path,
        "abv_format",
        "MYSTERY WINE\n750 mL",
        cfr="27 CFR 4.36",
        beverage_type="WINE",
        alcohol_content="see COLA",
    )
    assert result.verdict == "REVIEW"
    assert result.detail


# ── AC3: standards of fill (27 CFR 5.203 table lookup) ───────────────────────


def test_standards_of_fill_750ml_passes(tmp_path):
    result = _evaluate(tmp_path, "standards_of_fill", "750 mL", cfr="27 CFR 5.203")
    assert result.verdict == "PASS"


def test_standards_of_fill_ignores_leading_serving_size(tmp_path):
    """Regression: a serving/ingredient volume BEFORE the net contents must not be picked.

    ``contains 5 mL flavoring ... NET 750 mL`` must read the cued net-contents (750 mL,
    an approved size) and PASS — not the leading 5 mL serving numeral (which would FAIL).
    """
    result = _evaluate(
        tmp_path,
        "standards_of_fill",
        "contains 5 mL flavoring\nNET 750 mL",
        cfr="27 CFR 5.203",
    )
    assert result.verdict == "PASS"


def test_standards_of_fill_negative_size_reviews_not_fails(tmp_path):
    """Regression (AC4): an OCR ``-750 mL`` artifact ⇒ REVIEW, never a confident FAIL."""
    result = _evaluate(tmp_path, "standards_of_fill", "NET -750 mL", cfr="27 CFR 5.203")
    assert result.verdict == "REVIEW"


def test_standards_of_fill_1_75l_passes(tmp_path):
    """1.75 L canonicalizes to 1750 mL — an approved size."""
    result = _evaluate(tmp_path, "standards_of_fill", "1.75 L", cfr="27 CFR 5.203")
    assert result.verdict == "PASS"


def test_standards_of_fill_off_standard_fails_with_citation(tmp_path):
    """An off-standard size (680 mL is not in the §5.203 table) ⇒ FAIL with citation."""
    result = _evaluate(tmp_path, "standards_of_fill", "680 mL", cfr="27 CFR 5.203")
    assert result.verdict == "FAIL"
    assert result.detail is not None and "5.203" in result.detail


def test_standards_of_fill_unparseable_reviews(tmp_path):
    """No isolable same-unit net-contents token ⇒ REVIEW, never a guessed FAIL (AC4)."""
    result = _evaluate(tmp_path, "standards_of_fill", "STONE'S THROW BOURBON", cfr="27 CFR 5.203")
    assert result.verdict == "REVIEW"
    assert result.detail


# ── AC3: proof ↔ ABV (2×) consistency ────────────────────────────────────────


def test_proof_abv_consistent_passes(tmp_path):
    result = _evaluate(tmp_path, "proof_abv_consistency", "45% Alc./Vol. (90 Proof)")
    assert result.verdict == "PASS"


def test_proof_abv_inconsistent_fails(tmp_path):
    result = _evaluate(tmp_path, "proof_abv_consistency", "45% Alc./Vol. (80 Proof)")
    assert result.verdict == "FAIL"


def test_proof_absent_is_not_failed(tmp_path):
    """Proof is OPTIONAL — its absence is never a FAIL."""
    result = _evaluate(tmp_path, "proof_abv_consistency", "45% Alc./Vol.\n750 mL")
    assert result.verdict != "FAIL"


def test_proof_present_abv_unreadable_reviews(tmp_path):
    """Proof shown but ABV unreadable ⇒ REVIEW (cannot verify the 2× rule) (AC4)."""
    result = _evaluate(tmp_path, "proof_abv_consistency", "OLD TOM (90 Proof)\n750 mL")
    assert result.verdict == "REVIEW"
    assert result.detail


# ── AC4: name/address responsibility phrase (soft → REVIEW, never auto-FAIL) ──


def test_name_address_with_responsibility_phrase_passes(tmp_path):
    result = _evaluate(
        tmp_path,
        "name_address_format",
        "BOTTLED BY ACME DISTILLERS, LOUISVILLE, KY",
        cfr="27 CFR 5.66",
    )
    assert result.verdict == "PASS"


def test_name_address_missing_phrase_reviews_not_fails(tmp_path):
    """A missing responsibility phrase is a soft signal ⇒ REVIEW, never auto-FAIL."""
    result = _evaluate(
        tmp_path,
        "name_address_format",
        "ACME DISTILLERS LOUISVILLE KY",
        cfr="27 CFR 5.66",
    )
    assert result.verdict == "REVIEW"


# ── AC4: an unevaluable check never guesses ──────────────────────────────────


def test_review_paths_carry_an_explanation(tmp_path):
    """Every REVIEW path returns a non-empty explanatory detail (never a bare guess)."""
    for key, ocr, cfr in (
        ("standards_of_fill", "NO SIZE HERE", "27 CFR 5.203"),
        ("proof_abv_consistency", "OLD TOM (90 Proof)", "27 CFR 5.65"),
        ("name_address_format", "ACME DISTILLERS", "27 CFR 5.66"),
    ):
        result = _evaluate(tmp_path, key, ocr, cfr=cfr)
        if result.verdict == "REVIEW":
            assert result.detail


# ── provenance: no field_comparisons row (like the Gov Warning) ──────────────


def test_no_field_comparison_row_written(tmp_path):
    """Format checks compare against the STATUTE/policy, not a field ⇒ NO field_comparisons."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "45% Alc./Vol. (90 Proof)\n750 mL")
        fc.format_checks(_check("proof_abv_consistency"), _ctx(conn, sid))
        rows = conn.execute(
            "SELECT COUNT(*) AS n FROM field_comparisons WHERE submission_id = ?", (sid,)
        ).fetchone()
    assert rows["n"] == 0
    result = _evaluate(tmp_path, "abv_format", "45% Alc./Vol.")
    assert result.field_comparison_id is None


# ── integration through run_checks (3.2 seam) ────────────────────────────────


def test_format_checks_removed_from_rulesets(tmp_path):
    """Seven-only checklist (Diane's call, 2026-06-16): the DETERMINISTIC format checks were
    dropped from the rulesets, so run_checks emits NO abv_format / standards_of_fill /
    proof_abv_consistency rows. The ``format_checks`` evaluator stays registered + is
    unit-tested directly elsewhere in this file, for a future story."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "45% Alc./Vol. (90 Proof)\n750 mL\nBOTTLED BY ACME, KY")
        submission = repo.get_submission(conn, sid)
        assert submission is not None
        rc.run_checks(conn, submission)
        rows = conn.execute(
            "SELECT check_key FROM checklist_items WHERE submission_id = ? AND check_key IN "
            "('abv_format','standards_of_fill','proof_abv_consistency')",
            (sid,),
        ).fetchall()
    assert rows == []  # none of the format checks are emitted anymore
    assert checks.get_evaluator("format_checks") is not None  # evaluator still registered


# ── AC1: NO-LLM guard (mirrors test_government_warning.py) ────────────────────


def test_check_never_imports_a_model_adapter():
    """AC1: the deterministic check must NEVER import/construct a model adapter."""
    import ast

    source = Path("app/engine/checks/format_checks.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    banned = ("adapters.llm", "openai", "anthropic", "google.genai", "google_genai", "langchain")
    for mod in imported:
        low = mod.lower()
        assert not any(b in low for b in banned), f"check imports a model module: {mod!r}"


def test_check_constructs_no_model_client():
    """AC1: belt-and-braces — no model adapter is constructed/called by the check."""
    logic = Path("app/engine/checks/format_checks.py").read_text(encoding="utf-8")
    for token in ("get_llm_adapter(", "build_extractor(", "llm_results", "get_latest_llm"):
        assert token not in logic, f"check logic references a model code path: {token!r}"


def test_cfr_citation_not_hardcoded_in_check_logic():
    """AC1/AC4 guard: ``27 CFR`` must not be hard-coded in the check logic (lives as data)."""
    logic = Path("app/engine/checks/format_checks.py").read_text(encoding="utf-8")
    assert "27 CFR" not in logic


def test_data_module_carries_citations_and_policy():
    assert fc_data.STANDARDS_OF_FILL_CITATION == "27 CFR 5.203"
    assert fc_data.ABV_POLICY["DISTILLED_SPIRITS"] == fc_data.ABV_ALWAYS_REQUIRED
    assert fc_data.ABV_POLICY["MALT_BEVERAGE"] == fc_data.ABV_OPTIONAL_UNLESS_TRIGGER
    assert fc_data.ABV_POLICY["WINE"] == fc_data.ABV_REQUIRED_ABOVE_14_PCT
    # 750 mL is an approved standard of fill.
    from decimal import Decimal

    assert (Decimal("750"), "ml") in fc_data.STANDARDS_OF_FILL
