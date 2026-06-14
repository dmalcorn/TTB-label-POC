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

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import verdict
from app.db.connection import connect, init_db
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


# ── AR-5: read-path purity ───────────────────────────────────────────────────


def test_review_route_imports_no_heavy_work() -> None:
    """The review route is a pre-computed DB read — no OCR/LLM/pipeline-run import."""
    src = (REPO_ROOT / "app/web/routes_review.py").read_text(encoding="utf-8")
    for forbidden in ("run_checks", "adapters.ocr", "adapters.llm", "pipeline.run", "pytesseract"):
        assert forbidden not in src, f"review route must not import {forbidden!r} (AR-5)"
