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


# ── AR-5: read-path purity ───────────────────────────────────────────────────


def test_review_route_imports_no_heavy_work() -> None:
    """The review route is a pre-computed DB read — no OCR/LLM/pipeline-run import."""
    src = (REPO_ROOT / "app/web/routes_review.py").read_text(encoding="utf-8")
    for forbidden in ("run_checks", "adapters.ocr", "adapters.llm", "pipeline.run", "pytesseract"):
        assert forbidden not in src, f"review route must not import {forbidden!r} (AR-5)"
