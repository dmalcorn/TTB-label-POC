"""Story 4.3 — Review Workspace shell route (``GET /review/{id}``).

Covers the shell ACs:

- AC1: ``GET /review/{id}`` is a pure pre-computed DB read (AR-5) returning 200 with
  the three shell elements (banner, chevron, suggested-verdict alert); token-gated.
- AC2: the beverage banner shows the type word + the per-type accent class.
- AC3: the chevron shows the Conditional step ④ ONLY when a conditional/flag-only
  check is present (⑤-step), otherwise the ④-step renumbered map.
- AC4: the suggested-verdict alert rolls up via the centralized ``verdict.rollup``.
- AC5: a missing id ⇒ calm 404 (not a 500).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from app import verdict
from app.db.connection import connect, init_db
from app.db.repositories import LabelImage
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path, *, token: str | None = None) -> TestClient:
    db_path = tmp_path / "review.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    if token is None:
        monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ACCESS_TOKEN", token)
    init_db(db_path)
    return TestClient(create_app())


def _db_path(tmp_path) -> str:
    return str(tmp_path / "review.db")


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26009000000000",
        "beverage_type": "DISTILLED_SPIRITS",
        "brand_name": "Stone's Throw",
        "status": "IN_REVIEW",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_check(conn: sqlite3.Connection, submission_id: int, **overrides) -> int:
    cols = {
        "submission_id": submission_id,
        "check_key": "brand_name",
        "label": "Brand name",
        "cfr_citation": "27 CFR 5.64",
        "check_type": "FIELD_MATCH",
        "verdict": "PASS",
        "detail": None,
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO checklist_items ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_comparison(conn: sqlite3.Connection, submission_id: int, **overrides) -> int:
    cols = {
        "submission_id": submission_id,
        "field_key": "brand_name",
        "application_value": "Stone's Throw",
        "extracted_value": "Stone's Throw",
        "match_status": "MATCH",
        "similarity": 1.0,
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO field_comparisons ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _field(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    check_overrides: dict | None = None,
    cmp_overrides: dict | None = None,
) -> tuple[int, int]:
    """Seed a linked checklist_item ↔ field_comparison pair; return their ids."""
    cmp_id = _insert_comparison(conn, submission_id, **(cmp_overrides or {}))
    check = {"field_comparison_id": cmp_id}
    check.update(check_overrides or {})
    check_id = _insert_check(conn, submission_id, **check)
    return check_id, cmp_id


# ── AC1 / AC2 / AC4: 200, banner, chevron, alert ─────────────────────────────


def test_review_renders_shell_for_spirits(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn, beverage_type="DISTILLED_SPIRITS")
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
        _insert_check(
            conn, sid, check_key="government_warning", check_type="DETERMINISTIC", verdict="PASS"
        )
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    body = resp.text
    # banner word + accent class
    assert "DISTILLED SPIRITS" in body
    assert "beverage-banner--spirits" in body
    # chevron present
    assert "Identity" in body
    assert "Gov. Warning" in body
    assert "Decide" in body
    # suggested-verdict alert (advisory register, "Suggested:" label)
    assert "Suggested:" in body
    assert "PASS" in body


def test_review_banner_wine(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn, beverage_type="WINE", ttb_id="26009000000001")
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    assert "WINE" in resp.text
    assert "beverage-banner--wine" in resp.text


def test_review_banner_beer_dark_ink_class(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn, beverage_type="MALT_BEVERAGE", ttb_id="26009000000002")
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    assert "BEER" in resp.text
    assert "beverage-banner--beer" in resp.text


# ── AC4: roll-up matches the centralized verdict.rollup ──────────────────────


def test_review_alert_verdict_matches_rollup_fail(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
        _insert_check(
            conn, sid, check_key="government_warning", check_type="DETERMINISTIC", verdict="FAIL"
        )
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    rolled = verdict.rollup(["PASS", "FAIL"])
    assert rolled == "FAIL"
    assert "FAIL" in resp.text
    # advisory roll-up copy returns authority to the human
    assert "You decide" in resp.text


def test_review_alert_empty_checklist_is_review(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    # empty ⇒ REVIEW per rollup empty-policy, never a silent PASS
    assert "REVIEW" in resp.text


# ── AC3: conditional step appears only when triggered ────────────────────────


def test_review_chevron_four_steps_without_conditional(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
        _insert_check(
            conn, sid, check_key="government_warning", check_type="DETERMINISTIC", verdict="PASS"
        )
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    assert "Conditional" not in resp.text


def test_review_chevron_includes_conditional_when_present(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
        _insert_check(
            conn, sid, check_key="same_field_of_vision", check_type="MANUAL", verdict="REVIEW"
        )
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    assert "Conditional" in resp.text


# ── AC5: calm 404 for a missing id ───────────────────────────────────────────


def test_review_missing_id_is_404(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    resp = client.get("/review/999999")
    assert resp.status_code == 404


# ── AC1: token gate covers the route ─────────────────────────────────────────


def test_review_is_token_gated(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path, token="s3cret")
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    # No access cookie ⇒ redirected to /access (gate), not served.
    resp = client.get(f"/review/{sid}", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/access"


# ── Story 4.4: stacked field comparison cards ────────────────────────────────


def test_review_renders_match_card_stacked(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(
            conn,
            sid,
            check_overrides={"check_key": "brand_name", "label": "Brand Name", "verdict": "PASS"},
            cmp_overrides={
                "field_key": "brand_name",
                "application_value": "Stonebridge Cellars",
                "extracted_value": "Stonebridge Cellars",
            },
        )
    body = client.get(f"/review/{sid}").text
    assert "Brand Name" in body
    assert body.count("Stonebridge Cellars") >= 2  # both raw values render (stacked)
    assert "field-card--match" in body


def test_review_renders_mismatch_card_with_red_diff(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(
            conn,
            sid,
            check_overrides={
                "check_key": "alcohol_content",
                "label": "Alcohol Content",
                "verdict": "FAIL",
                "detail": "Values differ",
            },
            cmp_overrides={
                "field_key": "alcohol_content",
                "application_value": "45% Alc./Vol.",
                "extracted_value": "40% Alc./Vol.",
                "match_status": "MISMATCH",
                "similarity": 0.8,
            },
        )
    body = client.get(f"/review/{sid}").text
    assert "field-card--mismatch" in body
    assert "FAIL" in body
    assert "diff-del" in body
    assert "diff-ins" in body


def test_review_renders_soft_card_amber_no_red(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(
            conn,
            sid,
            check_overrides={"check_key": "brand_name", "label": "Brand Name", "verdict": "REVIEW"},
            cmp_overrides={
                "field_key": "brand_name",
                "application_value": "Stone's Throw",
                "extracted_value": "STONE'S THROW",
                "match_status": "MATCH",
                "similarity": 0.95,
            },
        )
    body = client.get(f"/review/{sid}").text
    assert "field-card--soft" in body
    assert "Capitalization differs; the text otherwise matches." in body
    assert "diff-soft" in body


def test_review_renders_not_found_card(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(
            conn,
            sid,
            check_overrides={
                "check_key": "wine_appellation",
                "label": "Appellation",
                "verdict": "REVIEW",
            },
            cmp_overrides={
                "field_key": "wine_appellation",
                "application_value": "Napa Valley",
                "extracted_value": None,
                "match_status": "MISSING",
                "similarity": None,
            },
        )
    body = client.get(f"/review/{sid}").text
    assert "Not found on label" in body


def test_review_renders_unreadable_card(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(
            conn,
            sid,
            check_overrides={
                "check_key": "net_contents",
                "label": "Net Contents",
                "verdict": "REVIEW",
            },
            cmp_overrides={
                "field_key": "net_contents",
                "application_value": "750 mL",
                "extracted_value": "7!iO m|_",
                "match_status": "UNVERIFIABLE",
                "similarity": None,
            },
        )
    body = client.get(f"/review/{sid}").text
    # apostrophe is HTML-escaped in the rendered page (correct, safe output)
    assert "read this field reliably from the photo — please verify by eye." in body
    # garbage is NOT rendered as a diff
    assert "diff-del" not in body


def test_review_renders_blank_application_card(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(
            conn,
            sid,
            check_overrides={
                "check_key": "fanciful_name",
                "label": "Fanciful Name",
                "verdict": "REVIEW",
            },
            cmp_overrides={
                "field_key": "fanciful_name",
                "application_value": "",
                "extracted_value": "Old Reserve",
                "match_status": "MISMATCH",
                "similarity": None,
            },
        )
    body = client.get(f"/review/{sid}").text
    assert "No value submitted in the application for this field." in body


def test_review_sorts_problems_before_clean(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        # a clean match seeded FIRST, a FAIL mismatch seeded SECOND — the FAIL must
        # still render before the PASS (problems-first sort, not insertion order)
        _field(
            conn,
            sid,
            check_overrides={"check_key": "brand_name", "label": "Brand Name", "verdict": "PASS"},
            cmp_overrides={"field_key": "brand_name"},
        )
        _field(
            conn,
            sid,
            check_overrides={
                "check_key": "alcohol_content",
                "label": "Alcohol Content",
                "verdict": "FAIL",
            },
            cmp_overrides={
                "field_key": "alcohol_content",
                "application_value": "45",
                "extracted_value": "40",
                "match_status": "MISMATCH",
            },
        )
    body = client.get(f"/review/{sid}").text
    assert body.index("Alcohol Content") < body.index("Brand Name")
    # the two mockup section headers are present
    assert "problems first" in body.lower()
    assert "Verified automatically" in body


def test_review_why_accordion_carries_citation_source_detail(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        # an OCR-sourced row so the view derives `ocr:tesseract`
        img = conn.execute(
            "INSERT INTO label_images (submission_id, filename) VALUES (?, 'front.jpg')", (sid,)
        ).lastrowid
        ocr_id = conn.execute(
            "INSERT INTO ocr_results (label_image_id, submission_id, engine_name, status) "
            "VALUES (?, ?, 'tesseract', 'OK')",
            (img, sid),
        ).lastrowid
        conn.commit()
        _field(
            conn,
            sid,
            check_overrides={
                "check_key": "brand_name",
                "label": "Brand Name",
                "verdict": "PASS",
                "cfr_citation": "27 CFR 5.63",
                "detail": "Application matches label.",
            },
            cmp_overrides={"field_key": "brand_name", "source_ocr_result_id": ocr_id},
        )
    body = client.get(f"/review/{sid}").text
    assert "<details" in body
    assert "Why?" in body
    assert "27 CFR 5.63" in body
    assert "ocr:tesseract" in body
    assert "Application matches label." in body


def test_review_why_accordion_carries_raw_extracted_value(monkeypatch, tmp_path) -> None:
    """AC5: the Why? accordion surfaces the raw OCR/LLM value verbatim (one of its four
    items). For a diff card the kv slot shows the segmented diff, so the clean raw value
    must still appear in the Why? body. Regression for F4 (raw value omitted)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(
            conn,
            sid,
            check_overrides={
                "check_key": "alcohol_content",
                "label": "Alcohol Content",
                "verdict": "FAIL",
            },
            cmp_overrides={
                "field_key": "alcohol_content",
                "application_value": "45% Alc./Vol.",
                "extracted_value": "40percentABV",
                "match_status": "MISMATCH",
                "similarity": 0.6,
            },
        )
    body = client.get(f"/review/{sid}").text
    # the raw read value appears (the Why? "Raw value read:" line), distinct from the
    # diffed kv slot which segments the string into spans
    assert "Raw value read:" in body
    assert "40percentABV" in body


def test_review_diff_card_emits_screen_reader_text_equivalent(monkeypatch, tmp_path) -> None:
    """A11Y hard requirement: a char-diff card carries a visually-hidden text
    equivalent (USWDS ``usa-sr-only``) naming WHICH value differs, so the diff is
    never conveyed by a colored span alone (survives forced-colors / screen readers).
    Regression for F2."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(
            conn,
            sid,
            check_overrides={
                "check_key": "brand_name",
                "label": "Brand Name",
                "verdict": "FAIL",
            },
            cmp_overrides={
                "field_key": "brand_name",
                "application_value": "Stone's Throw",
                "extracted_value": "Stoned Throw",
                "match_status": "MISMATCH",
                "similarity": 0.7,
            },
        )
    body = client.get(f"/review/{sid}").text
    assert "usa-sr-only" in body


def test_review_field_comparison_section_header_is_verbatim(monkeypatch, tmp_path) -> None:
    """AC4 / mockup: the problems section header reads verbatim "Field comparison —
    problems first" (not the placeholder "Needs a look"). Regression for F3."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(
            conn,
            sid,
            check_overrides={
                "check_key": "alcohol_content",
                "label": "Alcohol Content",
                "verdict": "FAIL",
            },
            cmp_overrides={
                "field_key": "alcohol_content",
                "application_value": "45",
                "extracted_value": "40",
                "match_status": "MISMATCH",
            },
        )
    body = client.get(f"/review/{sid}").text
    assert "Field comparison" in body
    assert "problems first" in body
    assert "Needs a look" not in body


def test_review_excludes_gov_warning_from_field_cards(monkeypatch, tmp_path) -> None:
    """A checklist row WITHOUT a field_comparison_id (Gov Warning) is not a field card."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(
            conn,
            sid,
            check_key="government_warning",
            label="Government Warning",
            check_type="DETERMINISTIC",
            verdict="PASS",
        )
    body = client.get(f"/review/{sid}").text
    # the gov-warning row exists but produces no field-card div
    assert "field-card--" not in body


# ── Government Warning comparison card (Story 4.5) ───────────────────────────


def _gov_warning_check(conn: sqlite3.Connection, submission_id: int, *, verdict_: str, detail: str):
    """Seed the single ``government_warning`` checklist row (no field_comparison_id)."""
    return _insert_check(
        conn,
        submission_id,
        check_key="government_warning",
        label="Government Warning",
        cfr_citation="27 CFR 16.21",
        check_type="MANUAL",
        verdict=verdict_,
        detail=detail,
    )


def test_review_gov_warning_reworded_renders_mono_stack_and_diff(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    detail = json.dumps(
        {
            "outcome": "reworded",
            "deviation": "header casing",
            "expected": "GOVERNMENT WARNING: text",
            "found": "Government Warning: text",
            "diff": [
                ["replace", "GOVERNMENT WARNING\u2192Government Warning"],
                ["equal", ": text"],
            ],
            "cfr_citation": "27 CFR 16.21",
        }
    )
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _gov_warning_check(conn, sid, verdict_="FAIL", detail=detail)
    body = client.get(f"/review/{sid}").text
    # the two-row mono stack labels
    assert "On label (OCR)" in body
    assert "Required (27 CFR" in body
    # the FAIL chip word + the red diff spans
    assert "FAIL" in body
    assert "diff-del" in body
    assert "diff-ins" in body


def test_review_gov_warning_absent_plain_no_diff(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    detail = json.dumps(
        {
            "outcome": "absent",
            "message": "Government Warning not found on any label",
            "cfr_citation": "27 CFR 16.21",
        }
    )
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _gov_warning_check(conn, sid, verdict_="FAIL", detail=detail)
    body = client.get(f"/review/{sid}").text
    assert "Required Government Warning not found on the submitted images" in body
    # absent ⇒ NO char-diff (diffing against empty would be noise)
    assert "diff-del" not in body
    assert "diff-ins" not in body


def test_review_gov_warning_couldnt_verify_review_no_red(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    detail = json.dumps(
        {
            "outcome": "couldnt_verify",
            "message": "couldn't verify bold/visual styling from a photo",
            "cfr_citation": "27 CFR 16.21",
        }
    )
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _gov_warning_check(conn, sid, verdict_="REVIEW", detail=detail)
    body = client.get(f"/review/{sid}").text
    assert "REVIEW" in body
    assert "verify by eye" in body.lower()
    assert "diff-del" not in body


def test_review_gov_warning_empty_state_when_no_row(monkeypatch, tmp_path) -> None:
    """A submission with NO government_warning row renders the calm honest empty state."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200  # never a 500
    assert "has not run for this submission" in resp.text


def test_review_gov_warning_why_carries_cfr_citation(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    detail = json.dumps({"outcome": "pass", "cfr_citation": "27 CFR 16.21"})
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _gov_warning_check(conn, sid, verdict_="PASS", detail=detail)
    body = client.get(f"/review/{sid}").text
    assert "Why?" in body
    assert "27 CFR 16.21" in body


def test_review_gov_warning_token_gated(monkeypatch, tmp_path) -> None:
    """The route stays token-gated — a no-cookie request redirects to /access."""
    client = _client(monkeypatch, tmp_path, token="s3cret")
    detail = json.dumps({"outcome": "pass", "cfr_citation": "27 CFR 16.21"})
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _gov_warning_check(conn, sid, verdict_="PASS", detail=detail)
    resp = client.get(f"/review/{sid}", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/access" in resp.headers["location"]


# ── AR-5: read-path purity ───────────────────────────────────────────────────


def test_review_route_imports_no_heavy_work() -> None:
    """The review route is a pre-computed DB read — no OCR/LLM/pipeline-run import.

    Covers BOTH the GET render and the POST /progress write (Story 4.6 AC7): the tick
    upsert is the ONE permitted cheap web-layer write, never an engine/OCR run.
    """
    src = (REPO_ROOT / "app/web/routes_review.py").read_text(encoding="utf-8")
    for forbidden in ("run_checks", "adapters.ocr", "adapters.llm", "pipeline.run", "pytesseract"):
        assert forbidden not in src, f"review route must not import {forbidden!r} (AR-5)"


# ── Story 4.6: smart checklist GET render + POST /progress persistence ────────


def test_review_get_renders_checklist_header_and_counter(monkeypatch, tmp_path) -> None:
    """AC1/AC3: GET renders the `Smart checklist — <Type>` header + the `N of M done`
    counter (an aria-live region) over the engine's checklist_items."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn, beverage_type="DISTILLED_SPIRITS")
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
        _insert_check(conn, sid, check_key="alcohol_content", verdict="REVIEW")
    body = client.get(f"/review/{sid}").text
    assert "Smart checklist" in body
    assert "Distilled Spirits" in body
    # one auto-PASS done out of two rows — counter is split across the
    # data-done-count / data-total-count spans (live region), so assert structurally
    assert "<span data-done-count>1</span>" in body
    assert "<span data-total-count>2</span>" in body
    assert 'aria-live="polite"' in body


def test_review_get_checklist_states_render(monkeypatch, tmp_path) -> None:
    """AC2: auto-PASS → done (muted); REVIEW → open (amber); FAIL → openfail (red)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
        _insert_check(conn, sid, check_key="alcohol_content", verdict="REVIEW")
        _insert_check(
            conn, sid, check_key="government_warning", check_type="DETERMINISTIC", verdict="FAIL"
        )
    body = client.get(f"/review/{sid}").text
    assert "cli--done" in body
    assert "cli--open" in body
    assert "cli--openfail" in body


def test_review_get_checklist_empty_state_is_calm(monkeypatch, tmp_path) -> None:
    """AC8: a submission with no checklist_items renders the calm empty state (never 500)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    body = resp.text
    assert "<span data-done-count>0</span>" in body
    assert "<span data-total-count>0</span>" in body
    assert "No checks ran for this submission." in body


def test_review_post_progress_persists_and_rehydrates(monkeypatch, tmp_path) -> None:
    """AC5/AC6: POST a manual tick on a REVIEW row, then a FRESH GET ("reload") shows
    the row in the `usercheck` state + the incremented counter (server-side rehydration)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
        _insert_check(conn, sid, check_key="alcohol_content", verdict="REVIEW")
    # before: 1 of 2 done, the REVIEW row is `open`
    before = client.get(f"/review/{sid}").text
    assert "<span data-done-count>1</span>" in before
    assert "cli--open" in before
    # POST the manual tick
    resp = client.post(
        f"/review/{sid}/progress", data={"check_key": "alcohol_content", "ticked": "true"}
    )
    assert resp.status_code == 204
    # after a fresh GET: the REVIEW row is now `usercheck`, counter is 2 of 2
    after = client.get(f"/review/{sid}").text
    assert "cli--usercheck" in after
    assert "<span data-done-count>2</span>" in after
    assert "<span data-total-count>2</span>" in after


def test_review_post_progress_untick_removes_key(monkeypatch, tmp_path) -> None:
    """AC5: an untick (ticked=false) removes the key — the counter drops back."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
        _insert_check(conn, sid, check_key="alcohol_content", verdict="REVIEW")
    client.post(f"/review/{sid}/progress", data={"check_key": "alcohol_content", "ticked": "true"})
    assert "<span data-done-count>2</span>" in client.get(f"/review/{sid}").text
    # untick
    resp = client.post(
        f"/review/{sid}/progress", data={"check_key": "alcohol_content", "ticked": "false"}
    )
    assert resp.status_code == 204
    assert "<span data-done-count>1</span>" in client.get(f"/review/{sid}").text


def test_review_post_progress_is_idempotent(monkeypatch, tmp_path) -> None:
    """AC5: re-posting an already-ticked key is a no-op (the set is de-duplicated)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
        _insert_check(conn, sid, check_key="alcohol_content", verdict="REVIEW")
    for _ in range(3):
        resp = client.post(
            f"/review/{sid}/progress", data={"check_key": "alcohol_content", "ticked": "true"}
        )
        assert resp.status_code == 204
    # still exactly 2 of 2 — never double-counted
    assert "<span data-done-count>2</span>" in client.get(f"/review/{sid}").text


def test_review_post_progress_missing_id_is_404(monkeypatch, tmp_path) -> None:
    """AC5: posting to a missing submission ⇒ calm 404 (not a 500)."""
    client = _client(monkeypatch, tmp_path)
    resp = client.post(
        "/review/999999/progress", data={"check_key": "brand_name", "ticked": "true"}
    )
    assert resp.status_code == 404


def test_review_post_progress_is_token_gated(monkeypatch, tmp_path) -> None:
    """AC5: the POST stays token-gated — a no-cookie request redirects to /access."""
    client = _client(monkeypatch, tmp_path, token="s3cret")
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
    resp = client.post(
        f"/review/{sid}/progress",
        data={"check_key": "brand_name", "ticked": "true"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/access"


# ── Story 4.6: review.js progressive enhancement (same-origin, no build) ──────


def test_review_html_loads_review_js_same_origin(monkeypatch, tmp_path) -> None:
    """AC4: the review screen references review.js via a same-origin /static path
    (no CDN/build — NFR-2/UX-DR-6); the render is correct without it."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
    body = client.get(f"/review/{sid}").text
    assert "/static/js/review.js" in body


def test_review_js_is_served_static(monkeypatch, tmp_path) -> None:
    """AC4/AC5: review.js is served same-origin from the static mount (no egress)."""
    client = _client(monkeypatch, tmp_path)
    resp = client.get("/static/js/review.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"].lower()


def test_review_js_posts_to_progress_endpoint_no_egress() -> None:
    """AC5: review.js POSTs the tick to the same-origin /progress endpoint and makes no
    cross-origin/CDN request (firewall/offline boundary, NFR-2)."""
    src = (REPO_ROOT / "static/js/review.js").read_text(encoding="utf-8")
    # the persisted-tick POST targets the same-origin progress endpoint
    assert "/progress" in src
    # progressive enhancement must reference the live-counter / tick data hooks
    assert "data-check-key" in src
    assert "data-checklist-count" in src or "data-done-count" in src
    # no external origin / CDN fetch (same-origin only)
    for forbidden in ("http://", "https://", "//cdn", "unpkg", "jsdelivr"):
        assert forbidden not in src, f"review.js must not reference {forbidden!r} (NFR-2 no egress)"


def test_brand_css_has_checklist_states_on_spine_tokens() -> None:
    """AC2/AC9: the checklist state classes exist and resolve to the spine --verdict-*
    tokens — NOT the mockup's inline hex (#2E8540). Reuses the shared palette."""
    css = (REPO_ROOT / "static/css/brand.css").read_text(encoding="utf-8")
    for cls in (".cli--done", ".cli--usercheck", ".cli--open", ".cli--openfail"):
        assert cls in css, f"brand.css missing checklist state {cls}"
    assert "Smart checklist (Story 4.6)" in css
    # the verdict colors resolve to the spine tokens, never the mockup's raw hex
    assert "--verdict-pass" in css
    assert "--verdict-review" in css
    assert "--verdict-fail" in css
    # the mockup's PASS-green hex must not leak into the spine (check both cases)
    assert "#2e8540" not in css.lower()


def test_brand_css_usercheck_box_is_secondary_accent_not_verdict_pass() -> None:
    """AC9 fidelity: a human-confirmed (usercheck) tick is an acknowledgement, NOT
    the engine's PASS — so its box uses the secondary/civic accent (mockup
    var(--secondary)), never the green --verdict-pass tint. This keeps "I looked"
    visually distinct from "the engine passed it" (contract #3/#4)."""
    css = (REPO_ROOT / "static/css/brand.css").read_text(encoding="utf-8")
    block = css.split(".cli--usercheck .cli__box", 1)[1].split("}", 1)[0]
    assert "--brand-secondary" in block
    assert "--verdict-pass" not in block


def test_review_get_group_anchors_are_focusable_for_checklist_jump(monkeypatch, tmp_path) -> None:
    """AC4: the smart-checklist rows jump to their field group. The JS moves focus
    to the target group so keyboard users land there — which only works if the
    target <section>s are programmatically focusable (tabindex=-1). Without it the
    focus call was a silent no-op."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
    body = client.get(f"/review/{sid}").text
    for anchor in ("group-identity", "group-gov-warning", "group-decide"):
        # the group <section> carries id + tabindex="-1" (focusable, not in tab order)
        assert f'id="{anchor}"' in body
        section = body.split(f'id="{anchor}"', 1)[1].split(">", 1)[0]
        assert 'tabindex="-1"' in section, f"{anchor} must be focusable (AC4 focus jump)"


def test_review_get_na_row_reads_not_applicable_not_review(monkeypatch, tmp_path) -> None:
    """AC2 regression: an NA check is a muted auto-tick — it must render its own
    'N/A' word, never the REVIEW fail-safe ('! REVIEW') that would mislabel a
    not-applicable check as a problem needing eyes."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn, beverage_type="WINE")
        _insert_check(conn, sid, check_key="standards_of_fill", check_type="MANUAL", verdict="NA")
    body = client.get(f"/review/{sid}").text
    # the NA row is its own muted done row carrying the N/A word
    assert "N/A" in body
    # it must NOT show the REVIEW "needs your eyes" copy for a not-applicable check
    na_row = body.split('data-check-key="standards_of_fill"', 1)[1].split("</a>", 1)[0]
    assert "needs your eyes" not in na_row
    assert "REVIEW" not in na_row


# ── Story 4.7: label-image panel + Enhance toggle ────────────────────────────
#
# A real fixture file under fixtures/images/ — the original-serve test seeds a row
# whose ``filename`` is this basename so FileResponse finds it on disk.
_FIXTURE_IMAGE = "26150000000001_01_BRAND.jpg"

# A 1x1 PNG (the smallest valid PNG) — written into settings.generated_images_dir
# for the enhanced-variant serve test.
_TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def _insert_image(conn: sqlite3.Connection, submission_id: int, **overrides) -> int:
    """Seed one ``label_images`` row; return its id."""
    cols: dict[str, object] = {
        "submission_id": submission_id,
        "image_role": "BRAND",
        "position": 1,
        "filename": _FIXTURE_IMAGE,
        "mime_type": "image/jpeg",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO label_images ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


# ── AC1: two-column workspace + left image panel ─────────────────────────────


def test_review_renders_two_column_with_image_panel(monkeypatch, tmp_path) -> None:
    """AC1: the workspace is the mockup's two-column layout — a left-column image
    panel + the unchanged right-column field cards/gov-warning/checklist. The panel
    header names the current image's role WORD + an "image N of M" counter."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_image(conn, sid, image_role="BRAND", position=1)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
    body = client.get(f"/review/{sid}").text
    # two-column scaffold
    assert 'class="work"' in body
    assert "review-col-left" in body
    assert "review-col-right" in body
    # the role WORD is rendered (never role-by-color alone) + the N-of-M counter
    assert "Brand (front)" in body
    assert "image 1 of 1" in body
    # the right column still carries the existing 4.4-4.6 region anchors
    assert 'id="group-identity"' in body
    assert 'id="group-checklist"' in body


# ── AC2: same-origin, token-gated, AR-5-pure image route ─────────────────────


def test_image_route_serves_original(monkeypatch, tmp_path) -> None:
    """AC2: GET /review/{sid}/image/{img} streams the original file from disk with an
    image/* content-type, resolving the path from the DB row (fixtures/images)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        img = _insert_image(conn, sid)
    resp = client.get(f"/review/{sid}/image/{img}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")
    assert len(resp.content) > 0


def test_image_route_serves_enhanced_variant(monkeypatch, tmp_path) -> None:
    """AC2: ?variant=enhanced serves the enhanced file resolved against
    settings.generated_images_dir."""
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GENERATED_IMAGES_DIR", str(gen_dir))
    client = _client(monkeypatch, tmp_path)
    (gen_dir / "front_enhanced.png").write_bytes(_TINY_PNG)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        img = _insert_image(conn, sid, enhanced_path="front_enhanced.png")
    resp = client.get(f"/review/{sid}/image/{img}?variant=enhanced")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")


def test_image_route_cross_submission_is_404(monkeypatch, tmp_path) -> None:
    """AC2: an image_id that does not belong to the path submission_id ⇒ calm 404
    (no cross-submission enumeration)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid_a = _insert_submission(conn, ttb_id="26009000000001")
        sid_b = _insert_submission(conn, ttb_id="26009000000002")
        img_b = _insert_image(conn, sid_b)
    resp = client.get(f"/review/{sid_a}/image/{img_b}")
    assert resp.status_code == 404


def test_image_route_null_variant_is_404(monkeypatch, tmp_path) -> None:
    """AC2/AC5: a NULL variant path (clean image, no enhanced) ⇒ calm 404, never 500."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        img = _insert_image(conn, sid, enhanced_path=None)
    resp = client.get(f"/review/{sid}/image/{img}?variant=enhanced")
    assert resp.status_code == 404


def test_image_route_missing_file_is_404(monkeypatch, tmp_path) -> None:
    """AC5: a row whose original file is absent on disk ⇒ calm 404, never a 500."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        img = _insert_image(conn, sid, filename="does_not_exist_on_disk.jpg")
    resp = client.get(f"/review/{sid}/image/{img}")
    assert resp.status_code == 404


def test_image_route_is_token_gated(monkeypatch, tmp_path) -> None:
    """AC2: the image route carries no token-gate exemption — when gated it redirects
    to /access like every other screen (Story 1.5)."""
    client = _client(monkeypatch, tmp_path, token="s3cret")
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        img = _insert_image(conn, sid)
    resp = client.get(f"/review/{sid}/image/{img}", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/access")


# ── AC3: paging across faces (works without JS) ──────────────────────────────


def test_review_multi_image_renders_pager(monkeypatch, tmp_path) -> None:
    """AC3: a multi-image submission renders prev/next as real ?image= links so paging
    works without JS; the server renders whichever ?image= selects."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_image(conn, sid, image_role="BRAND", position=1)
        _insert_image(conn, sid, image_role="BACK", position=2, filename="back.jpg")
    body = client.get(f"/review/{sid}").text
    # default selects position 1; a next link to position 2 is a real same-origin link
    assert "image 1 of 2" in body
    assert "?image=2" in body
    # selecting ?image=2 renders the Back face
    body2 = client.get(f"/review/{sid}?image=2").text
    assert "image 2 of 2" in body2
    assert "Back" in body2
    assert "?image=1" in body2


def test_review_single_image_renders_no_pager(monkeypatch, tmp_path) -> None:
    """AC3: a single-image submission renders no active pager link and never errors."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_image(conn, sid, position=1)
    body = client.get(f"/review/{sid}").text
    assert "image 1 of 1" in body
    # no second-position paging link
    assert "?image=2" not in body


# ── AC4: Enhance toggle — preprocessed ALONGSIDE original (omitted-not-inert) ──


def test_review_enhance_toggle_present_when_preprocessed(monkeypatch, tmp_path) -> None:
    """AC4: an image WITH enhanced_path offers the Enhance toggle + the honest
    side-by-side caption naming the applied steps from preprocess_log."""
    client = _client(monkeypatch, tmp_path)
    log = json.dumps(
        [
            {"step": "deskew", "applied": True, "ms": 3},
            {"step": "normalize_illumination_glare", "applied": True, "ms": 2},
            {"step": "clahe_contrast", "applied": True, "ms": 1},
            {"step": "denoise", "applied": False, "ms": 0},
        ]
    )
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_image(conn, sid, enhanced_path="front_enhanced.png", preprocess_log=log)
    body = client.get(f"/review/{sid}").text
    assert "Enhance" in body
    assert "?variant=enhanced" in body
    # the honest caption names ONLY applied corrective steps
    assert "deskew" in body
    assert "glare" in body
    assert "contrast" in body
    assert "denoise" not in body.split("Enhance", 1)[1].split("</", 1)[0]


def test_review_clean_image_omits_enhance_toggle(monkeypatch, tmp_path) -> None:
    """AC4: a CLEAN image (NULL enhanced_path) renders NO Enhance toggle — omitted,
    not shown disabled (UX-DR-13)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_image(conn, sid, enhanced_path=None)
    body = client.get(f"/review/{sid}").text
    assert "?variant=enhanced" not in body
    # no disabled/greyed enhance affordance either
    assert "image-panel__enhance" not in body


# ── AC5: calm empty state, never a 500 ───────────────────────────────────────


def test_review_no_images_renders_calm_empty_state(monkeypatch, tmp_path) -> None:
    """AC5: a submission with no label_images renders the calm left-column empty
    state (200, never 500) and the right column renders unchanged."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    assert "No label image was provided" in resp.text
    # right column still renders
    assert 'id="group-checklist"' in resp.text


# ── AC6: spine fidelity ──────────────────────────────────────────────────────


def test_review_image_panel_uses_route_src(monkeypatch, tmp_path) -> None:
    """AC6: the panel uses real <img> elements pointing at the new same-origin image
    route (never the mockup's hand-drawn CSS label / external origin)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        img = _insert_image(conn, sid)
    body = client.get(f"/review/{sid}").text
    assert f"/review/{sid}/image/{img}" in body
    # same-origin only — no external origin in the panel src
    for forbidden in ("http://", "https://", "//cdn"):
        assert forbidden not in body.split("review-col-left", 1)[1].split("review-col-right", 1)[0]


def test_brand_css_has_image_panel_on_spine_tokens() -> None:
    """AC6: the image-panel CSS block exists and resolves to spine --brand-* tokens,
    never the mockup's inline hex."""
    css = (REPO_ROOT / "static/css/brand.css").read_text(encoding="utf-8")
    assert "Label image panel" in css
    for cls in (".work", ".review-col-left", ".image-panel"):
        assert cls in css, f"brand.css missing image-panel class {cls}"
    # the panel block resolves to the spine tokens
    block = css.split("Label image panel", 1)[1]
    assert "var(--brand-" in block


# ── Story 4.7 code-review regression patches ─────────────────────────────────


def test_image_panel_pager_keeps_working_link_when_neighbor_position_is_null() -> None:
    """CR-H1: ``position`` is nullable/sparse in the schema; a neighbor whose ``position``
    is NULL is still a real face. The pager must emit a WORKING link for it — the 1-based
    ordinal fallback — never a dead ``?image=None`` and never a silently-dropped control.
    The selection loop resolves both the position and the ordinal selector forms."""
    from app.web.review_view import image_panel

    images = [
        LabelImage(id=10, submission_id=1, position=None, filename="a.jpg", created_at="t"),
        LabelImage(id=11, submission_id=1, position=2, filename="b.jpg", created_at="t"),
    ]
    # Standing on the second image, the previous neighbor has a NULL position → it must
    # link via its ordinal (?image=1), a working anchor, not a dropped/dead control.
    panel = image_panel(images, submission_id=1, current_position=2)
    pager = cast("dict[str, object]", panel["pager"])
    assert pager is not None
    assert pager["prev_href"] == "/review/1?image=1"
    # ?image=1 resolves back to that first (NULL-position) face via the ordinal fallback.
    back = image_panel(images, submission_id=1, current_position=1)
    assert back["counter"] == "image 1 of 2"
    # Standing on the first (NULL-position) image, the next neighbor (position 2) links.
    panel_first = image_panel(images, submission_id=1, current_position=None)
    pager_first = cast("dict[str, object]", panel_first["pager"])
    assert pager_first["next_href"] == "/review/1?image=2"


def test_enhance_caption_degrades_on_non_list_log_shape() -> None:
    """CR-M3: a top-level JSON object/string/number (not the pipeline's array) is an
    unexpected shape — degrade to the plain caption, never iterate keys/chars and
    silently drop steps, never raise."""
    from app.web.review_view import _enhance_caption

    # a one-entry log mistakenly stored as an OBJECT, not a one-element array
    assert _enhance_caption('{"step": "deskew", "applied": true}') == "preprocessed"
    assert _enhance_caption('"deskew"') == "preprocessed"
    assert _enhance_caption("42") == "preprocessed"
    assert _enhance_caption("not json at all") == "preprocessed"
    # the well-formed array still names ONLY applied corrective steps
    good = json.dumps([{"step": "deskew", "applied": True}, {"step": "denoise", "applied": False}])
    assert _enhance_caption(good) == "deskew"


def test_image_route_unknown_variant_is_404(monkeypatch, tmp_path) -> None:
    """AC2 (coverage): an unrecognized ``variant`` ⇒ calm 404 (never a 500/guess)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        img = _insert_image(conn, sid)
    resp = client.get(f"/review/{sid}/image/{img}?variant=bogus")
    assert resp.status_code == 404


def test_image_route_serves_binarized_variant(monkeypatch, tmp_path) -> None:
    """AC2 (coverage): ?variant=binarized serves the binarized file resolved against
    settings.generated_images_dir, mirroring the enhanced path."""
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GENERATED_IMAGES_DIR", str(gen_dir))
    client = _client(monkeypatch, tmp_path)
    (gen_dir / "front_binarized.png").write_bytes(_TINY_PNG)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        img = _insert_image(conn, sid, binarized_path="front_binarized.png")
    resp = client.get(f"/review/{sid}/image/{img}?variant=binarized")
    assert resp.status_code == 200
    # a PNG variant must NOT be mislabeled image/jpeg (CR-L1 mime sniff)
    assert resp.headers["content-type"] == "image/png"


def test_image_route_traversal_path_is_contained(monkeypatch, tmp_path) -> None:
    """CR-M4: a stored variant path that escapes its root (``..`` traversal) ⇒ calm 404,
    never an arbitrary-file read. The route ENFORCES the advertised no-traversal
    guarantee rather than trusting the DB column."""
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GENERATED_IMAGES_DIR", str(gen_dir))
    # plant a real file OUTSIDE the generated-images root that a traversal would reach
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        img = _insert_image(conn, sid, enhanced_path="../secret.txt")
    resp = client.get(f"/review/{sid}/image/{img}?variant=enhanced")
    assert resp.status_code == 404


# ── Story 4.11 AC3: LLM-unavailable degrade notice ───────────────────────────


def _insert_llm_result(conn: sqlite3.Connection, submission_id: int, **overrides) -> int:
    cols = {
        "submission_id": submission_id,
        "task": "extract_fields",
        "model_id": "test-model",
        "provider": "local",
        "is_benchmark_only": 0,
        "result_text": "ConnectError: unreachable",
        "status": "ERROR",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO llm_results ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


_LLM_NOTICE_COPY = "LLM check unavailable — showing OCR result"


def test_review_shows_llm_unavailable_notice_in_aria_live_region(monkeypatch, tmp_path) -> None:
    """An ERROR displayed-extraction llm_results row ⇒ the visible degrade notice in
    an aria-live region (Story 4.11 AC3). The field cards still render (OCR fallback)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(conn, sid, cmp_overrides={"extracted_value": "Stone's Throw"})
        _insert_llm_result(conn, sid, status="ERROR")
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    body = resp.text
    assert _LLM_NOTICE_COPY in body
    # the notice lives in an aria-live region so a screen reader announces it
    assert 'aria-live="polite"' in body
    assert "llm-notice" in body


def test_review_no_notice_when_extraction_ok(monkeypatch, tmp_path) -> None:
    """An OK extraction ⇒ NO degrade notice (the model worked)."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(conn, sid)
        _insert_llm_result(conn, sid, status="OK", result_text='{"brand_name": "Stone\'s Throw"}')
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    assert _LLM_NOTICE_COPY not in resp.text


def test_review_no_notice_when_llm_config_off(monkeypatch, tmp_path) -> None:
    """Config-off (no llm_results row at all) ⇒ NO notice — clean OCR-only operation
    is not a degrade and must not read as a warning."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(conn, sid)
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    assert _LLM_NOTICE_COPY not in resp.text


def test_review_no_notice_for_benchmark_only_error(monkeypatch, tmp_path) -> None:
    """An ERROR row that is benchmark-only (is_benchmark_only=1) is NOT the displayed
    extraction — it must not trigger the user-facing degrade notice."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _field(conn, sid)
        _insert_llm_result(conn, sid, status="ERROR", is_benchmark_only=1)
    resp = client.get(f"/review/{sid}")
    assert resp.status_code == 200
    assert _LLM_NOTICE_COPY not in resp.text


# ── Story 4.11 Task 5: verification tests pinning already-built behaviors ────────
# These do not change behavior — they pin the load-bearing AC1/AC5/AC6 invariants so a
# future change cannot silently regress the cold-load first paint, the mid-review
# refresh resume, the color-never-alone floor, the aria-live regions, or the type-size
# floor. (Read-purity, the sr-only diff equivalent, and the progress rehydrate already
# have dedicated tests above — these fill the remaining gaps.)


def test_review_first_paint_carries_verdict_word_without_js(monkeypatch, tmp_path) -> None:
    """AC1 (cold load): the suggested verdict WORD is present in the INITIAL server HTML
    — the specialist sees the roll-up on first paint, no JS required. The only scripts
    are deferred (end-of-body, `defer`), so nothing blocks the first render."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="FAIL")
    body = client.get(f"/review/{sid}").text
    # The roll-up word is in the document the server returned (not injected by JS).
    assert "Suggested:" in body
    assert "FAIL" in body
    # The per-page enhancement scripts (review.js / disposition.js) are deferred — they
    # layer polish on top, never gate the first paint. (The vendored USWDS init shim is
    # framework-owned and intentionally not deferred; it is not an app render dependency.)
    for src in ("/static/js/review.js", "/static/js/disposition.js"):
        idx = body.find(src)
        assert idx != -1, f"expected {src} to be referenced"
        tag_open = body.rfind("<script", 0, idx)
        head = body[tag_open : body.index(">", idx)]
        assert "defer" in head, f"{src} must be deferred (got: {head!r})"


def test_review_color_never_alone_verdict_words_present(monkeypatch, tmp_path) -> None:
    """AC6 (color never alone): each verdict chip carries a WORD next to its icon — the
    state is never conveyed by tint alone. A page mixing PASS/REVIEW/FAIL shows all three
    words in the rendered HTML (the chip__word spans), not just chip color classes."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        # One of each engine register across the field cards + checklist.
        _field(conn, sid, check_overrides={"verdict": "PASS"})
        _field(
            conn,
            sid,
            check_overrides={
                "check_key": "net_contents",
                "label": "Net contents",
                "verdict": "REVIEW",
            },
            cmp_overrides={
                "field_key": "net_contents",
                "application_value": "750 mL",
                "extracted_value": "75O mL",
                "match_status": "MISMATCH",
                "similarity": 0.6,
            },
        )
        _field(
            conn,
            sid,
            check_overrides={"check_key": "abv", "label": "Alcohol content", "verdict": "FAIL"},
            cmp_overrides={
                "field_key": "abv",
                "application_value": "40% ABV",
                "extracted_value": None,
                "match_status": "MISSING",
                "similarity": None,
            },
        )
    body = client.get(f"/review/{sid}").text
    # The verdict WORDS appear as text (chip__word), never tint alone.
    assert "chip__word" in body
    for word in ("PASS", "REVIEW", "FAIL"):
        assert word in body, f"verdict word {word!r} must be rendered (color never alone, AC6)"


def test_review_aria_live_regions_present(monkeypatch, tmp_path) -> None:
    """AC6 (announced state): the suggested-verdict alert is a `role="status"` region
    (announced on load) and the checklist "N of M done" counter is `aria-live="polite"`
    (announces a manual tick). Pin both — they are the screen's announce surfaces."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="REVIEW")
    body = client.get(f"/review/{sid}").text
    assert 'role="status"' in body  # suggested-verdict alert
    assert 'aria-live="polite"' in body  # checklist count (and the llm-notice when present)


def test_brand_css_meets_type_and_target_size_floor() -> None:
    """AC6 (sizing floor): brand.css declares the body at the 16px floor, the comparison
    values larger (19px) for older eyes, and the primary touch targets at the ≥48px
    floor. A CSS-content guard so a future edit can't drop below the accessibility floor."""
    css = (REPO_ROOT / "static/css/brand.css").read_text(encoding="utf-8")
    # Body floor: html/body declares 16px.
    assert "font-size: 16px;" in css, "body must hold the 16px type floor"
    # Comparison values are bumped above the body floor.
    assert ".field-card__kv-val {" in css and "font-size: 19px;" in css, (
        "the comparison values must be sized up (19px) above the 16px body floor"
    )
    # Touch targets meet the ≥48px floor (used on the primary action / segments / [?]).
    assert "min-height: 48px;" in css, "interactive targets must meet the ≥48px floor"
