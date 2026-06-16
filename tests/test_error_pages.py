"""Branded HTTP-error page (app/main.py ``styled_http_exception`` + templates/error.html).

A human navigating into an HTTPException must get the calm, on-brand error page — never
FastAPI's default terse JSON body (the "ugly plain page" a double-submitted disposition's
409 used to show). Fetch/XHR/image callers, which only read the status code, keep the
terse default body. These tests pin both halves: the styled HTML for an HTML-accepting
request, and the plain JSON for a non-HTML one — across a 404 and the disposition 409.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.connection import connect, init_db
from app.main import create_app

HTML = {"accept": "text/html,application/xhtml+xml"}
JSON = {"accept": "application/json"}


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    db_path = tmp_path / "errors.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    init_db(db_path)
    return TestClient(create_app())


def _insert_in_review(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO submissions (ttb_id, beverage_type, brand_name, status, submitted_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            "26009000000000",
            "DISTILLED_SPIRITS",
            "Stone's Throw",
            "IN_REVIEW",
            "2026-06-01T12:00:00Z",
        ),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


# ── 404: a human gets the styled page; a fetch gets terse JSON ────────────────


def test_missing_id_html_renders_branded_page(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    resp = client.get("/review/999999", headers=HTML)
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("text/html")
    # Apostrophe-free fragment of the headline ("We couldn't find that") so the
    # assertion isn't tripped by Jinja's &#39; auto-escaping of the apostrophe.
    assert "find that" in resp.text
    assert "Back to the queue" in resp.text  # the one obvious way forward
    assert "usa-alert--warning" in resp.text  # branded alert, not a raw string
    assert "<!DOCTYPE html>" in resp.text  # full branded shell


def test_missing_id_non_html_stays_terse_json(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    resp = client.get("/review/999999", headers=JSON)
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"detail": "Submission not found"}
    assert "We couldn't find that" not in resp.text


# ── 409: the double-submitted disposition lands on the calm "Already recorded" ─


def test_second_disposition_409_renders_branded_page(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(str(tmp_path / "errors.db")) as conn:
        sid = _insert_in_review(conn)

    first = client.post(
        f"/review/{sid}/disposition", data={"disposition": "APPROVED"}, follow_redirects=False
    )
    assert first.status_code == 303  # recorded ⇒ PRG back to the queue

    # The frantic second click (slow commit) — already DECIDED ⇒ calm 409, styled.
    second = client.post(
        f"/review/{sid}/disposition",
        data={"disposition": "APPROVED"},
        headers=HTML,
        follow_redirects=False,
    )
    assert second.status_code == 409
    assert second.headers["content-type"].startswith("text/html")
    assert "Already recorded" in second.text
    assert "your first decision stands" in second.text
