"""Story 6.2 — Live fixture enqueue (``POST /enqueue``).

Covers the four ACs of the operator enqueue endpoint:

- AC-1: ``POST /enqueue`` inserts exactly ONE fresh fixture as a ``RECEIVED`` row
  (+ its ``label_images`` + one ``SEEDED`` audit row) in a single transaction —
  never re-seeding/wiping the corpus; each call mints a distinct unique ``ttb_id``
  so repeats never trip the ``ttb_id NOT NULL UNIQUE`` constraint.
- AC-2: the enqueued row is the ``RECEIVED`` precondition the sweep consumes
  (``list_received_ids`` includes it); once readied it is ``READY_FOR_REVIEW``
  (the canonical stored enums for the UI's submitted→processing→ready copy).
- AC-3: a readied enqueued submission is servable via the existing next/queue path.
- AC-4: the response is a bare ``303 → /queue`` carrying no submission / image /
  benchmark data, and the route is behind the Story 1.5 token gate (inserts
  nothing when gated).

``enqueue_fixture`` is also unit-tested directly, independent of the HTTP layer.

The pipeline is NOT driven here (its OCR/preprocess stages need native deps absent
on the host venv); AC-2/AC-3 assert the ``RECEIVED`` precondition + simulate the
sweep's ``READY_FOR_REVIEW`` outcome — the sweep itself is Story 2.2's test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.db.seed import enqueue_fixture, seed
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path, *, token: str | None = None) -> TestClient:
    """A fresh app over an isolated temp DB, sweep OFF, so the test owns row states."""
    db_path = tmp_path / "enqueue.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GENERATED_IMAGES_DIR", str(tmp_path / "generated"))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    if token is None:
        monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ACCESS_TOKEN", token)
    init_db(db_path)
    return TestClient(create_app())


def _count_submissions(db_path) -> int:
    with connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0])


# ── enqueue_fixture (unit, no HTTP) ──────────────────────────────────────────


def test_enqueue_fixture_inserts_one_received_row(tmp_path):
    db_path = tmp_path / "enqueue.db"
    init_db(db_path)
    before = seed(db_path)  # full corpus

    new_id = enqueue_fixture(db_path)

    assert isinstance(new_id, int)
    assert _count_submissions(db_path) == before + 1  # exactly one more
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, disposition, decided_at, decision_notes, engine_verdict, ttb_id "
            "FROM submissions WHERE id = ?",
            (new_id,),
        ).fetchone()
        assert row["status"] == "RECEIVED"
        assert row["disposition"] is None
        assert row["decided_at"] is None
        assert row["decision_notes"] is None
        assert row["engine_verdict"] is None
        # child rows present: ≥1 label_image + exactly one SEEDED audit row
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM label_images WHERE submission_id = ?", (new_id,)
            ).fetchone()[0]
            >= 1
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM audit_events "
                "WHERE submission_id = ? AND event_type = 'SEEDED'",
                (new_id,),
            ).fetchone()[0]
            == 1
        )


def test_enqueue_fixture_repeats_mint_distinct_ttb_ids(tmp_path):
    """Repeated enqueue never trips ``ttb_id NOT NULL UNIQUE`` — each call mints a
    fresh distinct id (collision-free even against the seeded copy)."""
    db_path = tmp_path / "enqueue.db"
    init_db(db_path)
    seed(db_path)

    id1 = enqueue_fixture(db_path)
    id2 = enqueue_fixture(db_path)
    id3 = enqueue_fixture(db_path)

    assert len({id1, id2, id3}) == 3
    with connect(db_path) as conn:
        ttb_ids = [
            r["ttb_id"]
            for r in conn.execute(
                "SELECT ttb_id FROM submissions WHERE id IN (?, ?, ?)", (id1, id2, id3)
            )
        ]
    assert len(set(ttb_ids)) == 3  # all distinct
    # And none collide with a pre-existing seeded ttb_id (UNIQUE held — no raise above).


def test_enqueue_fixture_leaves_prior_corpus_intact(tmp_path):
    """Enqueue must NOT wipe/re-seed: a prior submission's row is byte-for-byte
    unchanged after an enqueue (it is an INSERT, not a re-seed)."""
    db_path = tmp_path / "enqueue.db"
    init_db(db_path)
    seed(db_path)
    with connect(db_path) as conn:
        before = conn.execute(
            "SELECT id, ttb_id, status FROM submissions ORDER BY id LIMIT 1"
        ).fetchone()
        before_dict = dict(before)

    enqueue_fixture(db_path)

    with connect(db_path) as conn:
        after = conn.execute(
            "SELECT id, ttb_id, status FROM submissions WHERE id = ?", (before_dict["id"],)
        ).fetchone()
        assert dict(after) == before_dict  # untouched


def test_enqueue_fixture_on_empty_db_inserts_cleanly(tmp_path):
    """Enqueue does not require a pre-seeded corpus — a fresh empty DB still gets one row."""
    db_path = tmp_path / "enqueue.db"
    init_db(db_path)
    assert _count_submissions(db_path) == 0

    new_id = enqueue_fixture(db_path)

    assert _count_submissions(db_path) == 1
    with connect(db_path) as conn:
        status = conn.execute("SELECT status FROM submissions WHERE id = ?", (new_id,)).fetchone()[
            "status"
        ]
    assert status == "RECEIVED"


# ── AC-2: lifecycle precondition + readied outcome ───────────────────────────


def test_enqueued_row_is_in_the_sweep_claim_set(tmp_path):
    """The enqueued RECEIVED row is exactly what ``list_received_ids`` (the sweep's
    claim set) returns — the precondition that carries it forward to READY_FOR_REVIEW."""
    db_path = tmp_path / "enqueue.db"
    init_db(db_path)
    seed(db_path)
    # Drive the seeded corpus out of RECEIVED so only the enqueued row remains claimable.
    with connect(db_path) as conn:
        conn.execute("UPDATE submissions SET status = 'READY_FOR_REVIEW'")

    new_id = enqueue_fixture(db_path)

    with connect(db_path) as conn:
        received = repo.list_received_ids(conn, 100)
    assert new_id in received


def test_enqueued_row_reaches_ready_for_review_canonical_enum(tmp_path):
    """The UI narrates submitted→processing→ready; the CANONICAL stored enums are
    RECEIVED→PROCESSING→READY_FOR_REVIEW (AR-10). Enqueue lands RECEIVED (and is in the
    sweep's claim set, NOT yet servable); the sweep (simulated here) carries it through
    the canonical forward states to READY_FOR_REVIEW — at which point it leaves the claim
    set and becomes servable. Asserted via the REAL repo claim/serve functions so the
    relationship — not a bare self-read of a value the test just wrote — is what proves
    the transition. The stored enum values, not the lowercase UI copy."""
    db_path = tmp_path / "enqueue.db"
    init_db(db_path)
    new_id = enqueue_fixture(db_path)

    # Lands at the canonical RECEIVED enum: in the sweep's claim set, not yet servable.
    with connect(db_path) as conn:
        assert (
            conn.execute("SELECT status FROM submissions WHERE id = ?", (new_id,)).fetchone()[
                "status"
            ]
            == "RECEIVED"
        )
        assert new_id in repo.list_received_ids(conn, 100)
        assert repo.get_oldest_ready_submission_id(conn) is None  # not servable while RECEIVED

    # Drive the canonical forward path the sweep walks: RECEIVED → PROCESSING →
    # READY_FOR_REVIEW. Each UPDATE must satisfy the status CHECK (only canonical enums
    # are accepted) — a non-canonical value here would raise IntegrityError.
    for state in ("PROCESSING", "READY_FOR_REVIEW"):
        with connect(db_path) as conn:
            conn.execute("UPDATE submissions SET status = ? WHERE id = ?", (state, new_id))

    # Post-sweep: left the claim set (no longer RECEIVED) and is now servable.
    with connect(db_path) as conn:
        assert (
            conn.execute("SELECT status FROM submissions WHERE id = ?", (new_id,)).fetchone()[
                "status"
            ]
            == "READY_FOR_REVIEW"
        )
        assert new_id not in repo.list_received_ids(conn, 100)
        assert repo.get_oldest_ready_submission_id(conn) == new_id


# ── AC-3: servable via the existing next/queue path once ready ───────────────


def test_readied_enqueued_submission_is_servable(tmp_path):
    """Once readied, the enqueued submission is an ordinary READY_FOR_REVIEW row the
    existing queue/next path serves (no special-casing in the read path)."""
    db_path = tmp_path / "enqueue.db"
    init_db(db_path)
    # No seed: only the enqueued row exists so it is unambiguously the served one.
    new_id = enqueue_fixture(db_path)
    with connect(db_path) as conn:
        conn.execute("UPDATE submissions SET status = 'READY_FOR_REVIEW' WHERE id = ?", (new_id,))

    with connect(db_path) as conn:
        assert repo.count_ready_for_review(conn) == 1
        assert repo.get_oldest_ready_submission_id(conn) == new_id


# ── AC-1 (HTTP): POST /enqueue inserts one fresh fixture ─────────────────────


def test_post_enqueue_inserts_one_and_redirects(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "enqueue.db"
    before = seed(db_path)

    resp = client.post("/enqueue", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/queue"
    assert _count_submissions(db_path) == before + 1


def test_post_enqueue_twice_adds_two_distinct(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "enqueue.db"
    before = seed(db_path)

    assert client.post("/enqueue", follow_redirects=False).status_code == 303
    assert client.post("/enqueue", follow_redirects=False).status_code == 303

    assert _count_submissions(db_path) == before + 2
    with connect(db_path) as conn:
        # The two newest rows carry distinct ttb_ids (no UNIQUE failure).
        ttb_ids = [
            r["ttb_id"]
            for r in conn.execute("SELECT ttb_id FROM submissions ORDER BY id DESC LIMIT 2")
        ]
    assert len(set(ttb_ids)) == 2


# ── AC-4: honest redirect + token gate + no leakage ──────────────────────────


def test_post_enqueue_response_leaks_no_data(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "enqueue.db"
    seed(db_path)
    with connect(db_path) as conn:
        ttb_id = conn.execute("SELECT ttb_id FROM submissions LIMIT 1").fetchone()["ttb_id"]

    resp = client.post("/enqueue", follow_redirects=False)
    body = resp.text
    assert body == ""  # bare 303 redirect, empty body
    assert ttb_id not in body
    assert "submission" not in body.lower()
    assert "benchmark" not in body.lower()


def test_post_enqueue_is_token_gated(tmp_path, monkeypatch):
    """With ACCESS_TOKEN set, an unauthenticated POST /enqueue is bounced to /access
    (no exemption in main.py) — and inserts nothing."""
    client = _client(monkeypatch, tmp_path, token="s3cret")
    db_path = tmp_path / "enqueue.db"
    before = seed(db_path)

    resp = client.post("/enqueue", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/access"
    # The gate fired BEFORE any insert: row count unchanged.
    assert _count_submissions(db_path) == before
