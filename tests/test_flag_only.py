"""Flag-only checks surface as REVIEW (Story 3.7, AC1–AC4).

The same-field-of-vision (``positional``) flag-REVIEW check:
  - **AC1** always REVIEW — never PASS (co-location unconfirmable), never FAIL
    (an element's absence is another check's concern).
  - **AC2** a deterministic per-element presence report for the trio (brand /
    class-type / alcohol content), NO LLM (import-AST + token guards).
  - **AC3** a multi-image submission whose co-location is undeterminable → REVIEW
    citing 27 CFR 5.63, reporting each element's individual presence.
  - **AC4** toggle-independent (no adapter seam) + an unknown flag-only key → REVIEW.

Offline, fast, deterministic — NO real or fake model call anywhere (flag-only is
deterministic by contract: it must never touch an LLM).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.engine import checks
from app.engine.checks import flag_only as fo
from app.engine.rulesets import Check
from app.engine.rulesets import flag_only as fo_data

# ── shared fixtures (mirror tests/test_format_checks.py) ──────────────────────


def _make_db(tmp_path) -> Path:
    db_path = tmp_path / "flag_only.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26001000000077",
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


def _insert_label_image(conn: sqlite3.Connection, submission_id: int, *, position: int = 1) -> int:
    cur = conn.execute(
        "INSERT INTO label_images (submission_id, filename, position) VALUES (?, ?, ?)",
        (submission_id, f"label_{position}.png", position),
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


def _check(check_key: str = "same_field_of_vision", cfr_citation: str = "27 CFR 5.63") -> Check:
    return Check(
        check_key=check_key,
        label=check_key.replace("_", " ").title(),
        check_type="MANUAL",
        cfr_citation=cfr_citation,
        source_date="2022-01-08",
        strategy="positional",
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


def _evaluate(tmp_path, *, ocr_text: str | None, check_key: str = "same_field_of_vision", **subm):
    """Run one flag-only check against a submission with the given seeded OCR text."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, **subm)
        img = _insert_label_image(conn, sid)
        if ocr_text is not None:
            _insert_ocr(conn, sid, img, ocr_text)
        result = fo.flag_only(_check(check_key), _ctx(conn, sid))
    return result


def _detail(result) -> dict:
    assert result.detail is not None
    return json.loads(result.detail)


# ── registration / wiring ─────────────────────────────────────────────────────


def test_flag_only_is_registered_under_positional_strategy():
    """The evaluator plugs into the 3.2 dispatch seam under ``positional``."""
    assert checks.get_evaluator("positional") is fo.flag_only


# ── AC1: always REVIEW, never PASS / never FAIL ────────────────────────────────


def test_all_three_elements_present_is_still_review_not_pass(tmp_path):
    """Even with all three trio elements present, co-location is unconfirmable ⇒ REVIEW."""
    ocr = "Stone's Throw\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol.\n750 mL"
    result = _evaluate(tmp_path, ocr_text=ocr)
    assert result.verdict == "REVIEW"
    assert result.detail  # non-empty explanatory note


def test_missing_element_is_still_review_not_fail(tmp_path):
    """An element absent from the label is reported, but flag-only never FAILs."""
    ocr = "Stone's Throw\n750 mL"  # no class/type, no ABV
    result = _evaluate(tmp_path, ocr_text=ocr)
    assert result.verdict == "REVIEW"


def test_empty_ocr_is_still_review(tmp_path):
    """No readable text at all ⇒ still REVIEW (defer), never FAIL."""
    result = _evaluate(tmp_path, ocr_text=None)
    assert result.verdict == "REVIEW"


# ── AC2: per-element presence report, deterministic ───────────────────────────


def test_presence_report_all_present(tmp_path):
    ocr = "Stone's Throw\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol.\n750 mL"
    result = _evaluate(tmp_path, ocr_text=ocr)
    elements = _detail(result)["elements"]
    assert elements["brand_name"] is True
    assert elements["class_type_designation"] is True
    assert elements["alcohol_content"] is True


def test_presence_report_marks_absent_element_false(tmp_path):
    """A trio field whose value is absent from the OCR text is reported present=false."""
    ocr = "Stone's Throw\n750 mL"  # brand only
    result = _evaluate(tmp_path, ocr_text=ocr)
    elements = _detail(result)["elements"]
    assert elements["brand_name"] is True
    assert elements["class_type_designation"] is False
    assert elements["alcohol_content"] is False


def test_presence_report_normalizes_casing(tmp_path):
    """Presence uses the centralized normalize ⇒ 'STONE'S THROW' ≡ 'Stone's Throw'."""
    ocr = "STONE'S THROW\nKENTUCKY STRAIGHT BOURBON WHISKEY\n45% ALC./VOL."
    result = _evaluate(tmp_path, ocr_text=ocr)
    elements = _detail(result)["elements"]
    assert elements["brand_name"] is True
    assert elements["class_type_designation"] is True


def test_alcohol_content_present_via_abv_token_when_app_value_absent(tmp_path):
    """ABV presence may be confirmed by a %-token even when the application value is absent."""
    ocr = "Stone's Throw\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol."
    result = _evaluate(tmp_path, ocr_text=ocr, alcohol_content=None)
    elements = _detail(result)["elements"]
    assert elements["alcohol_content"] is True


def test_alcohol_content_present_when_net_contents_precedes_abv(tmp_path):
    """ABV statement on the label is present even when a net-contents size is read first.

    Regression: the numeric branch of ``normalize`` collapses the whole OCR blob to the
    FIRST ``<number><unit>`` token, so a substring test on ``normalize(blob,
    'alcohol_content')`` would see only ``'750 ml'`` and miss a verbatim ABV. The
    cue-aware ABV probe must still confirm presence regardless of token order.
    """
    ocr = "Stone's Throw\nKentucky Straight Bourbon Whiskey\n750 mL\n45% Alc./Vol."
    result = _evaluate(tmp_path, ocr_text=ocr, alcohol_content="45% Alc./Vol.")
    assert _detail(result)["elements"]["alcohol_content"] is True


def test_alcohol_content_present_when_app_abv_differs_from_label_abv(tmp_path):
    """Presence (not value-match) — an ABV statement on the label counts even if it
    differs from the application's ABV (value-match is Story 3.3's separate concern).
    """
    ocr = "Stone's Throw\nKentucky Straight Bourbon Whiskey\n40% Alc./Vol."
    result = _evaluate(tmp_path, ocr_text=ocr, alcohol_content="45% Alc./Vol.")
    assert _detail(result)["elements"]["alcohol_content"] is True


def test_marketing_percentage_alongside_no_abv_is_not_alcohol_content(tmp_path):
    """A stray promotional ``%`` ('30% off') that competes with another non-ABV ``%``
    must NOT read as the ABV statement — flag-only reuses ``format_checks._find_abv_pct``'s
    cue-word guard, so when no ``%`` is cued by an alcohol word and several ``%`` tokens
    exist, none is taken as ABV. (A lone uncued ``%`` remains the documented ABV fallback
    of the sibling check — flag-only inherits that behavior verbatim by reusing it.)
    """
    ocr = "Stone's Throw\nKentucky Straight Bourbon Whiskey\n30% OFF\n100% Natural\n750 mL"
    result = _evaluate(tmp_path, ocr_text=ocr, alcohol_content=None)
    assert _detail(result)["elements"]["alcohol_content"] is False
    assert result.verdict == "REVIEW"  # still defers — never a fabricated verdict


def test_detail_carries_reason_and_citation(tmp_path):
    ocr = "Stone's Throw\nKentucky Straight Bourbon Whiskey\n45% Alc./Vol."
    payload = _detail(_evaluate(tmp_path, ocr_text=ocr))
    assert payload["cfr_citation"] == "27 CFR 5.63"
    assert payload["reason"]  # non-empty co-location-deferred explanation
    assert payload["outcome"] == "co_location_deferred"


# ── AC3: multi-image submission → REVIEW citing §5.63 + presence report ────────


def test_multi_image_colocation_deferred_review(tmp_path):
    """Trio split across two faces ⇒ co-location unrecoverable from the flattened join ⇒ REVIEW."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        front = _insert_label_image(conn, sid, position=1)
        back = _insert_label_image(conn, sid, position=2)
        _insert_ocr(conn, sid, front, "Stone's Throw\nKentucky Straight Bourbon Whiskey")
        _insert_ocr(conn, sid, back, "45% Alc./Vol.\n750 mL")
        result = fo.flag_only(_check(), _ctx(conn, sid))
    assert result.verdict == "REVIEW"
    payload = _detail(result)
    assert payload["cfr_citation"] == "27 CFR 5.63"
    elements = payload["elements"]
    assert elements["brand_name"] is True
    assert elements["class_type_designation"] is True
    assert elements["alcohol_content"] is True


# ── AC4: toggle-independent + unknown-key default ─────────────────────────────


def test_unknown_flag_only_key_degrades_to_review(tmp_path):
    """An unhandled flag-only check_key ⇒ honest REVIEW, never a raise / fabricated verdict."""
    result = _evaluate(tmp_path, ocr_text="anything", check_key="not_a_real_flag_only")
    assert result.verdict == "REVIEW"
    assert result.detail


# ── AC2/AC4: NO-LLM guard (mirrors test_format_checks.py) ──────────────────────


def test_check_never_imports_a_model_adapter():
    """AC2: the flag-only check must NEVER import/construct a model adapter."""
    import ast

    source = Path("app/engine/checks/flag_only.py").read_text(encoding="utf-8")
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
    """AC2/AC4: belt-and-braces — no model adapter is constructed/called by the check."""
    logic = Path("app/engine/checks/flag_only.py").read_text(encoding="utf-8")
    for token in ("get_llm_adapter(", "build_extractor(", "llm_results", "get_latest_llm"):
        assert token not in logic, f"check logic references a model code path: {token!r}"


# ── CFR-as-data guard (mirrors test_format_checks.py / class_type) ─────────────


def test_cfr_citation_not_inlined_in_check_logic():
    """AC2: the §5.63 citation comes off the Check row / DATA module — never inlined."""
    logic = Path("app/engine/checks/flag_only.py").read_text(encoding="utf-8")
    assert "27 CFR" not in logic, "CFR citation literal must not be inlined in check logic"


def test_ruleset_data_carries_citation_and_trio():
    assert fo_data.CFR_CITATION == "27 CFR 5.63"
    assert fo_data.SAME_FIELD_OF_VISION_FIELDS == (
        "brand_name",
        "class_type_designation",
        "alcohol_content",
    )
    assert fo_data.SAME_FIELD_OF_VISION_REASON  # non-empty


# ── no field_comparisons row + run_checks integration ─────────────────────────


def test_flag_only_writes_no_field_comparison_row(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "Stone's Throw\nKentucky Straight Bourbon Whiskey\n45% Alc.")
        fo.flag_only(_check(), _ctx(conn, sid))
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM field_comparisons WHERE submission_id = ?", (sid,)
        ).fetchone()["n"]
    assert count == 0


def test_positional_seam_generic_fallback_is_review(tmp_path):
    """The ``positional`` evaluator has no ruleset user now (country_of_origin became a
    FIELD_MATCH card), but the seam is retained: an unhandled flag-only check_key still
    degrades to an honest REVIEW rather than raising (finalize-don't-abort, FR-9)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "Stone's Throw\n45% Alc./Vol.")
        result = fo.flag_only(_check(check_key="some_future_flag_only_check"), _ctx(conn, sid))
    assert result.verdict == "REVIEW"
    assert "deferred to specialist" in result.detail
