"""Story 4.1 — Queue screen & Next Submission.

Covers the four ACs of the first Epic-4 UI story:

- AC1: ``GET /queue`` / ``POST /next`` are pre-computed DB reads only; ``POST /next``
  serves the OLDEST ``READY_FOR_REVIEW`` submission (oldest-first by ``submitted_at``
  then ``id``), skips unready (``RECEIVED``/``PROCESSING``) rows silently, and
  redirects to ``/review/{id}`` — or, on an empty queue, re-renders the calm State-2
  screen (NOT an error, NOT a redirect).
- AC2: the screen reproduces ``mockups/queue.html`` in both states (auto-focused
  Next Submission button that submits a form, the segmented filter, the deferred
  Phase-2 placeholder, the disabled empty-state button + calm copy).
- AC3: tokens resolve via the linked brand stylesheet (no inline ``<style>``),
  mockup scaffolding + fabricated demo stats are excluded, and the stats strip shows
  only the honestly-computable live "N waiting" count.
- AC4: the routes are token-gated by the existing middleware (not exempt), and
  ``POST /next`` performs the permitted cheap bookkeeping write —
  ``READY_FOR_REVIEW → IN_REVIEW`` + an ``OPENED`` audit row.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.main import create_app
from app.pipeline import status

REPO_ROOT = Path(__file__).resolve().parents[1]


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path, *, token: str | None = None) -> TestClient:
    """A fresh app over an isolated temp DB with the background sweep OFF.

    ``SCHEDULER_ENABLED=false`` keeps the pipeline from mutating the rows the test
    seeds; ``DATABASE_PATH`` points at a throwaway file so tests never touch the
    repo DB. The schema is created up-front via :func:`init_db` so the helper tests
    can ``connect`` and seed rows BEFORE any request: ``TestClient(create_app())``
    used without a ``with`` block does not fire the FastAPI lifespan (and its
    startup ``init_db``) until the first request, which would otherwise leave the
    fresh temp DB table-less for those direct-``connect`` seed steps.
    """
    db_path = tmp_path / "queue.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    if token is None:
        monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ACCESS_TOKEN", token)
    init_db(db_path)
    return TestClient(create_app())


def _db_path(tmp_path) -> str:
    return str(tmp_path / "queue.db")


def _insert(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26009000000000",
        "beverage_type": "DISTILLED_SPIRITS",
        "brand_name": "Stone's Throw",
        "status": "RECEIVED",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _ready(conn: sqlite3.Connection, *, ttb: str, submitted_at: str, **overrides) -> int:
    return _insert(
        conn,
        ttb_id=ttb,
        status="READY_FOR_REVIEW",
        submitted_at=submitted_at,
        **overrides,
    )


# ── Repository helpers (Task 1) ──────────────────────────────────────────────


def test_oldest_ready_picks_oldest_submitted_then_id(monkeypatch, tmp_path) -> None:
    _client(monkeypatch, tmp_path)  # builds + init_db + seed
    with connect(_db_path(tmp_path)) as conn:
        newer = _ready(conn, ttb="26009000000002", submitted_at="2026-06-03T00:00:00Z")
        older = _ready(conn, ttb="26009000000001", submitted_at="2026-06-02T00:00:00Z")
        chosen = repo.get_oldest_ready_submission_id(conn)
    assert chosen == older
    assert chosen != newer


def test_oldest_ready_skips_unready_statuses(monkeypatch, tmp_path) -> None:
    _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        # Several non-ready rows with EARLIER timestamps must never be chosen.
        _insert(
            conn, ttb_id="26009000000010", status="RECEIVED", submitted_at="2026-05-01T00:00:00Z"
        )
        _insert(
            conn, ttb_id="26009000000011", status="PROCESSING", submitted_at="2026-05-02T00:00:00Z"
        )
        _insert(
            conn, ttb_id="26009000000012", status="IN_REVIEW", submitted_at="2026-05-03T00:00:00Z"
        )
        # DECIDED rows must carry a disposition + decided_at (schema CHECK constraint).
        _insert(
            conn,
            ttb_id="26009000000013",
            status="DECIDED",
            submitted_at="2026-05-04T00:00:00Z",
            disposition="APPROVED",
            decided_at="2026-05-05T00:00:00Z",
        )
        ready = _ready(conn, ttb="26009000000014", submitted_at="2026-06-09T00:00:00Z")
        chosen = repo.get_oldest_ready_submission_id(conn)
    assert chosen == ready


def test_oldest_ready_none_when_empty(monkeypatch, tmp_path) -> None:
    _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        # The fixture seed inserts only RECEIVED rows ⇒ no READY_FOR_REVIEW.
        assert repo.get_oldest_ready_submission_id(conn) is None


def test_count_ready_for_review(monkeypatch, tmp_path) -> None:
    _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        assert repo.count_ready_for_review(conn) == 0
        _ready(conn, ttb="26009000000020", submitted_at="2026-06-02T00:00:00Z")
        _ready(conn, ttb="26009000000021", submitted_at="2026-06-03T00:00:00Z")
        _insert(conn, ttb_id="26009000000022", status="RECEIVED")
        assert repo.count_ready_for_review(conn) == 2


def test_oldest_ready_type_filter(monkeypatch, tmp_path) -> None:
    """The beverage_type arg is wired (Story 4.2 exposes it through the route)."""
    _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        wine = _ready(
            conn, ttb="26009000000030", submitted_at="2026-06-05T00:00:00Z", beverage_type="WINE"
        )
        _ready(
            conn,
            ttb="26009000000031",
            submitted_at="2026-06-01T00:00:00Z",
            beverage_type="DISTILLED_SPIRITS",
        )
        assert repo.get_oldest_ready_submission_id(conn, beverage_type="WINE") == wine
        assert repo.count_ready_for_review(conn, beverage_type="WINE") == 1
        assert repo.get_oldest_ready_submission_id(conn, beverage_type="MALT_BEVERAGE") is None


# ── AC1: POST /next serves the oldest ready and redirects ─────────────────────


def test_next_serves_oldest_ready_and_redirects(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        _ready(conn, ttb="26009000000041", submitted_at="2026-06-03T00:00:00Z")
        oldest = _ready(conn, ttb="26009000000040", submitted_at="2026-06-02T00:00:00Z")
    resp = client.post("/next", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/review/{oldest}"


def test_next_never_serves_unready(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        # Earliest rows are unready; only this later row is servable.
        _insert(
            conn, ttb_id="26009000000050", status="PROCESSING", submitted_at="2026-05-01T00:00:00Z"
        )
        ready = _ready(conn, ttb="26009000000051", submitted_at="2026-06-08T00:00:00Z")
    resp = client.post("/next", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/review/{ready}"


# ── AC4: the permitted bookkeeping write on POST /next ────────────────────────


def test_next_transitions_to_in_review_and_audits(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _ready(conn, ttb="26009000000060", submitted_at="2026-06-02T00:00:00Z")
    client.post("/next", follow_redirects=False)
    with connect(_db_path(tmp_path)) as conn:
        assert repo.get_status(conn, sid) == "IN_REVIEW"
        row = conn.execute(
            "SELECT event_type, from_status, to_status FROM audit_events "
            "WHERE submission_id = ? AND event_type = 'OPENED'",
            (sid,),
        ).fetchone()
    assert row is not None
    assert row["from_status"] == "READY_FOR_REVIEW"
    assert row["to_status"] == "IN_REVIEW"


# ── AC1/AC4 race: the loser of a concurrent /next serves the next row, not a 500 ─


def test_next_lost_race_serves_next_not_500(monkeypatch, tmp_path) -> None:
    """Two specialists click Next at the same instant: both read the same oldest
    READY_FOR_REVIEW id; one wins the ``advance`` (→ IN_REVIEW), the other's
    ``advance`` is now a non-forward ``IN_REVIEW → IN_REVIEW`` and ``status.advance``
    raises ``ValueError``. The route must NOT 500 — it calmly re-selects and serves
    the NEXT oldest ready row. We simulate the lost race by pre-flipping the oldest
    row to IN_REVIEW (as if a concurrent request just claimed it) and asserting the
    POST serves the second-oldest instead of erroring.
    """
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        taken = _ready(conn, ttb="26009000000100", submitted_at="2026-06-01T00:00:00Z")
        nxt = _ready(conn, ttb="26009000000101", submitted_at="2026-06-02T00:00:00Z")
        # A concurrent request already advanced the oldest row out of the queue.
        status.advance(
            conn, taken, to_status="IN_REVIEW", event_type="OPENED", actor="Label Specialist"
        )
    resp = client.post("/next", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/review/{nxt}"


def test_next_all_rows_raced_away_renders_empty_state2(monkeypatch, tmp_path) -> None:
    """If every ready row is claimed out from under the request, the loop drains to
    an empty queue and re-renders the calm State-2 screen (200) — never a 500."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        only = _ready(conn, ttb="26009000000110", submitted_at="2026-06-01T00:00:00Z")
        status.advance(
            conn, only, to_status="IN_REVIEW", event_type="OPENED", actor="Label Specialist"
        )
    resp = client.post("/next", follow_redirects=False)
    assert resp.status_code == 200
    assert "No submissions waiting right now." in resp.text


# ── AC1: empty queue is a calm State-2 render, not a redirect or error ─────────


def test_next_empty_queue_renders_state2(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    # Fixture seed makes only RECEIVED rows ⇒ nothing READY_FOR_REVIEW.
    resp = client.post("/next", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.text
    assert "No submissions waiting right now." in body
    assert 'aria-disabled="true"' in body


# ── AC2: State 1 fidelity (waiting) ───────────────────────────────────────────


def test_queue_state1_fidelity(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        _ready(conn, ttb="26009000000070", submitted_at="2026-06-02T00:00:00Z")
    body = client.get("/queue").text
    # The Next Submission control is a real submitting form, auto-focused.
    assert "btn-next" in body
    assert "autofocus" in body
    assert 'action="/next"' in body
    assert 'method="post"' in body
    assert "Next Submission" in body
    assert "Pull the next label for review." in body
    # The optional beverage-type segmented filter (Any preselected).
    for label in ("Any", "Wine", "Spirits", "Beer"):
        assert f">{label}<" in body
    assert 'aria-pressed="true"' in body
    # The Phase-2 deferred placeholder — present, not a live control.
    assert "deferred" in body
    assert 'aria-hidden="true"' in body
    # The shared app shell header is inherited from base.html.
    assert 'class="app-header"' in body


# ── AC2: State 2 fidelity (empty) ─────────────────────────────────────────────


def test_queue_state2_fidelity(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    body = client.get("/queue").text  # no ready rows seeded
    assert "No submissions waiting right now." in body
    assert "btn-next" in body
    assert 'aria-disabled="true"' in body
    assert "disabled" in body
    # Calm, not an error.
    assert "error" not in body.lower() or "usa-input--error" not in body


# ── AC3: honest stats + no mockup scaffolding ─────────────────────────────────


def test_queue_shows_live_waiting_count(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        _ready(conn, ttb="26009000000080", submitted_at="2026-06-02T00:00:00Z")
        _ready(conn, ttb="26009000000081", submitted_at="2026-06-03T00:00:00Z")
        _ready(conn, ttb="26009000000082", submitted_at="2026-06-04T00:00:00Z")
    body = client.get("/queue").text
    assert "3 waiting" in body


def test_queue_excludes_scaffolding_and_fabricated_stats(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        _ready(conn, ttb="26009000000090", submitted_at="2026-06-02T00:00:00Z")
    body = client.get("/queue").text
    # Mockup-only scaffolding must not be reproduced.
    assert "device__chrome" not in body
    assert "state-label" not in body
    # Fabricated demo numbers from the mockup must not appear.
    assert "reviewed by you today" not in body
    assert "38 waiting" not in body
    assert "4.6s" not in body
    assert "avg" not in body.lower()
    # Tokens come from the linked self-hosted brand stylesheet, not inline <style>.
    assert "<style" not in body
    assert "/static/css/brand.css" in body


# ── AC4: token gating ─────────────────────────────────────────────────────────


def test_queue_and_next_are_gated(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path, token="secret")  # no cookie set
    q = client.get("/queue", follow_redirects=False)
    assert q.status_code == 303
    assert q.headers["location"] == "/access"
    n = client.post("/next", follow_redirects=False)
    assert n.status_code == 303
    assert n.headers["location"] == "/access"


def test_queue_reachable_with_valid_cookie(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path, token="secret")
    client.cookies.set("ttb_access", "secret")
    assert client.get("/queue").status_code == 200


# ── AR-5: read-path purity (no OCR/LLM/pipeline import in the queue route) ─────


def test_queue_route_imports_no_heavy_work() -> None:
    """The 5s read contract: the queue route does DB reads + the one bookkeeping
    write only — it must not import OCR / LLM / pipeline-run symbols."""
    src = (REPO_ROOT / "app/web/routes_queue.py").read_text(encoding="utf-8")
    for forbidden in ("run_checks", "adapters.ocr", "adapters.llm", "pipeline.run", "pytesseract"):
        assert forbidden not in src, f"queue route must not import {forbidden!r} (AR-5)"
