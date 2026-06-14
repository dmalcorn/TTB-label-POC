"""Story 4.8 — Disposition action bar & Notes (routes + write path).

Covers the commit-zone ACs end-to-end over the FastAPI app:

- AC1: the action bar renders three controls (Approve / Needs Correction / Reject)
  with NONE pre-selected, and no verdict CSS class leaks onto a disposition control.
- AC2: the server soft-gate — Needs Correction / Reject with blank notes ⇒ 400.
- AC3: ``POST /review/{id}/disposition`` writes disposition + decided_at +
  decision_notes, flips status to DECIDED, and redirects to ``/queue?recorded={id}``;
  ``POST /review/{id}/progress`` persists ``draft_notes`` (204) which rehydrate on GET.
- AC4: ``POST /review/{id}/undo`` clears the three columns, applies the lone bounded
  backward transition DECIDED → READY_FOR_REVIEW, writes an UNDONE audit row, and
  RETAINS the review_progress row (ticks + draft notes).
- AC5: a double-disposition ⇒ calm 409 (never 500); the row stays put.

Reuses the token-gate-off / tmp-DB ``_client`` idiom from ``test_review.py``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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


def _row(tmp_path, submission_id: int) -> sqlite3.Row:
    with connect(_db_path(tmp_path)) as conn:
        return conn.execute("SELECT * FROM submissions WHERE id = ?", (submission_id,)).fetchone()


def _audit_types(tmp_path, submission_id: int) -> list[str]:
    with connect(_db_path(tmp_path)) as conn:
        rows = conn.execute(
            "SELECT event_type FROM audit_events WHERE submission_id = ? ORDER BY id",
            (submission_id,),
        ).fetchall()
    return [r["event_type"] for r in rows]


# ── AC3: disposition happy paths ─────────────────────────────────────────────


@pytest.mark.parametrize("disposition", ["APPROVED", "NEEDS_CORRECTION", "REJECTED"])
def test_disposition_records_decision_and_redirects(monkeypatch, tmp_path, disposition) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="brand_name", verdict="PASS")
    resp = client.post(
        f"/review/{sid}/disposition",
        data={"disposition": disposition, "notes": "a clear reason for the maker"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/queue?recorded={sid}"

    row = _row(tmp_path, sid)
    assert row["status"] == "DECIDED"
    assert row["disposition"] == disposition
    assert row["decided_at"] is not None
    assert row["decision_notes"] == "a clear reason for the maker"
    assert "DECIDED" in _audit_types(tmp_path, sid)


def test_disposition_approve_allows_blank_notes(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    resp = client.post(
        f"/review/{sid}/disposition",
        data={"disposition": "APPROVED", "notes": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    row = _row(tmp_path, sid)
    assert row["status"] == "DECIDED"
    assert row["disposition"] == "APPROVED"


# ── AC2: server-side soft-gate ───────────────────────────────────────────────


@pytest.mark.parametrize("disposition", ["NEEDS_CORRECTION", "REJECTED"])
def test_disposition_blank_notes_rejected(monkeypatch, tmp_path, disposition) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    resp = client.post(
        f"/review/{sid}/disposition",
        data={"disposition": disposition, "notes": "   "},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    # The row is untouched — never half-decided.
    row = _row(tmp_path, sid)
    assert row["status"] == "IN_REVIEW"
    assert row["disposition"] is None


def test_disposition_unknown_value_is_400(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    resp = client.post(
        f"/review/{sid}/disposition",
        data={"disposition": "MAYBE", "notes": "x"},
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert _row(tmp_path, sid)["status"] == "IN_REVIEW"


def test_disposition_missing_submission_is_404(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    resp = client.post(
        "/review/9999/disposition",
        data={"disposition": "APPROVED", "notes": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 404


# ── AC5: double-disposition is a calm 409, not a 500 ─────────────────────────


def test_double_disposition_is_409(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    first = client.post(
        f"/review/{sid}/disposition",
        data={"disposition": "APPROVED", "notes": ""},
        follow_redirects=False,
    )
    assert first.status_code == 303
    second = client.post(
        f"/review/{sid}/disposition",
        data={"disposition": "REJECTED", "notes": "changed my mind"},
        follow_redirects=False,
    )
    assert second.status_code == 409
    # The first decision stands — the second never overwrote it.
    row = _row(tmp_path, sid)
    assert row["disposition"] == "APPROVED"


# ── AC4: undo ────────────────────────────────────────────────────────────────


def test_undo_clears_decision_and_reopens(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    client.post(
        f"/review/{sid}/disposition",
        data={"disposition": "NEEDS_CORRECTION", "notes": "fix the warning"},
        follow_redirects=False,
    )
    assert _row(tmp_path, sid)["status"] == "DECIDED"

    resp = client.post(f"/review/{sid}/undo", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/review/{sid}"

    row = _row(tmp_path, sid)
    assert row["status"] == "READY_FOR_REVIEW"
    assert row["disposition"] is None
    assert row["decided_at"] is None
    assert row["decision_notes"] is None
    assert row["correction_due_at"] is None
    assert "UNDONE" in _audit_types(tmp_path, sid)


def test_undo_retains_review_progress(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="net_contents", verdict="REVIEW")
    # A manual tick + a draft note land in review_progress.
    client.post(f"/review/{sid}/progress", data={"check_key": "net_contents", "ticked": "true"})
    client.post(f"/review/{sid}/progress", data={"draft_notes": "looked closely at the ABV"})
    client.post(
        f"/review/{sid}/disposition",
        data={"disposition": "APPROVED", "notes": ""},
        follow_redirects=False,
    )
    client.post(f"/review/{sid}/undo", follow_redirects=False)

    with connect(_db_path(tmp_path)) as conn:
        progress = conn.execute(
            "SELECT * FROM review_progress WHERE submission_id = ?", (sid,)
        ).fetchone()
    assert progress is not None
    assert "net_contents" in progress["ticked_check_keys"]
    assert progress["draft_notes"] == "looked closely at the ABV"


def test_undo_on_non_decided_is_409(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn, status="IN_REVIEW")
    resp = client.post(f"/review/{sid}/undo", follow_redirects=False)
    assert resp.status_code == 409
    assert _row(tmp_path, sid)["status"] == "IN_REVIEW"


def test_undo_missing_submission_is_404(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    resp = client.post("/review/9999/undo", follow_redirects=False)
    assert resp.status_code == 404


# ── CR Patch 1: the disposition write is an atomic compare-and-swap ───────────
# The decide UPDATE fires only WHERE status='IN_REVIEW', so the open state IS the
# claim. A row that was never opened (still READY_FOR_REVIEW / PROCESSING) cannot be
# decided — and two concurrent decisions can no longer both win (the loser's CAS
# matches zero rows). These guard the TOCTOU the read-then-check had: two POSTs both
# reading IN_REVIEW before either wrote, the loser overwriting the winner.


@pytest.mark.parametrize("status", ["READY_FOR_REVIEW", "PROCESSING", "RECEIVED"])
def test_disposition_on_unopened_row_is_409(monkeypatch, tmp_path, status) -> None:
    # Deciding a submission that was never opened for review (not IN_REVIEW) is a calm
    # 409, never a 500 — and the row is left exactly as it was (never half-decided).
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn, status=status)
    resp = client.post(
        f"/review/{sid}/disposition",
        data={"disposition": "APPROVED", "notes": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 409
    row = _row(tmp_path, sid)
    assert row["status"] == status
    assert row["disposition"] is None
    assert row["decided_at"] is None
    # The rejected claim wrote no DECIDED audit row.
    assert "DECIDED" not in _audit_types(tmp_path, sid)


# ── CR Patch 2: the queue "Recorded — Undo" banner is gated on a real DECIDED row ─
# `?recorded=` is an unauthenticated client-supplied id; the banner must render ONLY
# when it names a submission that is actually DECIDED right now (else it is a false
# Undo affordance whose POST would just 409).


def test_queue_recorded_banner_shows_for_decided_row(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    client.post(
        f"/review/{sid}/disposition",
        data={"disposition": "APPROVED", "notes": ""},
        follow_redirects=False,
    )
    body = client.get(f"/queue?recorded={sid}").text
    assert "Decision recorded." in body
    assert f"/review/{sid}/undo" in body


def test_queue_recorded_banner_suppressed_for_bogus_id(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    body = client.get("/queue?recorded=9999").text
    assert "Decision recorded." not in body


def test_queue_recorded_banner_suppressed_for_non_decided_row(monkeypatch, tmp_path) -> None:
    # A still-IN_REVIEW row id (e.g. a stale `recorded` after an Undo) drops the banner.
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn, status="IN_REVIEW")
    body = client.get(f"/queue?recorded={sid}").text
    assert "Decision recorded." not in body


def test_queue_recorded_banner_suppressed_after_undo(monkeypatch, tmp_path) -> None:
    # Decide → Undo leaves the row READY_FOR_REVIEW; the leftover `?recorded=` id no
    # longer offers a false Undo (the decision was already reversed).
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    client.post(
        f"/review/{sid}/disposition",
        data={"disposition": "APPROVED", "notes": ""},
        follow_redirects=False,
    )
    client.post(f"/review/{sid}/undo", follow_redirects=False)
    body = client.get(f"/queue?recorded={sid}").text
    assert "Decision recorded." not in body


# ── AC3: draft-notes autosave on POST /progress ──────────────────────────────


def test_progress_draft_notes_only_is_204_and_rehydrates(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="net_contents", verdict="REVIEW")
    resp = client.post(f"/review/{sid}/progress", data={"draft_notes": "draft reason text"})
    assert resp.status_code == 204
    with connect(_db_path(tmp_path)) as conn:
        progress = conn.execute(
            "SELECT draft_notes FROM review_progress WHERE submission_id = ?", (sid,)
        ).fetchone()
    assert progress["draft_notes"] == "draft reason text"
    # The draft rehydrates into the textarea on the next GET.
    body = client.get(f"/review/{sid}").text
    assert "draft reason text" in body


def test_progress_empty_beacon_is_noop_204(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    # Neither a tick nor draft_notes ⇒ a calm 204 no-op (never a 422).
    resp = client.post(f"/review/{sid}/progress", data={})
    assert resp.status_code == 204


def test_progress_tick_path_still_works(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="net_contents", verdict="REVIEW")
    resp = client.post(
        f"/review/{sid}/progress", data={"check_key": "net_contents", "ticked": "true"}
    )
    assert resp.status_code == 204
    with connect(_db_path(tmp_path)) as conn:
        progress = conn.execute(
            "SELECT ticked_check_keys FROM review_progress WHERE submission_id = ?", (sid,)
        ).fetchone()
    assert "net_contents" in progress["ticked_check_keys"]


# ── AC1 / AC6: the bar renders, none pre-selected, no verdict class on a button ─


def test_review_renders_action_bar_none_preselected(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="net_contents", verdict="FAIL")
    body = client.get(f"/review/{sid}").text
    # Three disposition controls present, carrying the disposition enum values.
    assert 'value="APPROVED"' in body
    assert 'value="NEEDS_CORRECTION"' in body
    assert 'value="REJECTED"' in body
    # The disposition form posts to the disposition route.
    assert f"/review/{sid}/disposition" in body
    # The required-notes marker copy + the "none pre-selected" hint.
    assert "required for Needs Correction / Reject" in body
    assert "None pre-selected" in body


def test_review_action_bar_no_verdict_class_on_button(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
        _insert_check(conn, sid, check_key="net_contents", verdict="FAIL")
    body = client.get(f"/review/{sid}").text
    # The disposition controls use dispo-- classes (verdict chip-- classes never on a button).
    assert "dispo--approve" in body
    assert "dispo--correct" in body
    assert "dispo--reject" in body
