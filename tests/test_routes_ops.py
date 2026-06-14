"""Story 6.1 — Demo data reset (``POST /reset``).

Covers the four ACs of the operator reset endpoint:

- AC-1: ``POST /reset`` transactionally re-seeds the corpus via Story 1.3's
  ``seed()`` — the FK cascade clears every child table + ``review_progress`` +
  the decision columns, and restores the full pending queue at ``RECEIVED``.
- AC-2: the derived generated-images root is purged (and re-created empty); the
  read-only ``fixtures/images/`` is never touched; a missing root is a no-op.
- AC-3: after full exhaustion (every row ``DECIDED``) the reset restores the
  ``RECEIVED`` precondition the background sweep consumes — no redeploy.
- AC-4: the response is a bare ``303 → /queue`` carrying no submission / image /
  benchmark data, and the route is behind the Story 1.5 token gate.

The reset orchestrator + the purge helper are also unit-tested directly,
independent of the HTTP layer.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.connection import connect, init_db
from app.db.seed import seed
from app.main import create_app
from app.web.ops import purge_generated_images, reset

REPO_ROOT = Path(__file__).resolve().parents[1]


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path, *, token: str | None = None) -> TestClient:
    """A fresh app over an isolated temp DB + generated-images root, sweep OFF.

    ``SCHEDULER_ENABLED=false`` keeps the pipeline from advancing the seeded rows
    so the test owns the row states; ``DATABASE_PATH`` / ``GENERATED_IMAGES_DIR``
    point at throwaway paths under ``tmp_path`` so a test never touches the repo
    DB or the real ``data/generated``. The schema is created up-front so a direct
    ``connect`` can read/seed before the first request fires the lifespan.
    """
    db_path = tmp_path / "ops.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GENERATED_IMAGES_DIR", str(tmp_path / "generated"))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    if token is None:
        monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ACCESS_TOKEN", token)
    init_db(db_path)
    return TestClient(create_app())


def _decide_all(db_path) -> None:
    """Drive every submission to ``DECIDED`` and write a ``review_progress`` row.

    Simulates an exhausted demo: the cross-column CHECK requires the decision
    columns when ``status='DECIDED'``, so we set them together. We also stamp a
    ``review_progress`` scratch row per submission to prove the cascade purges it.
    """
    with connect(db_path) as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM submissions")]
        for sid in ids:
            conn.execute(
                "UPDATE submissions SET status='DECIDED', disposition='APPROVED', "
                "decided_at='2026-06-14T00:00:00Z', decision_notes='ok', "
                "engine_verdict='PASS' WHERE id=?",
                (sid,),
            )
            conn.execute(
                "INSERT INTO review_progress (submission_id, draft_notes) VALUES (?, ?)",
                (sid, "scratch"),
            )


# ── AC-2 / purge helper (unit) ───────────────────────────────────────────────


def test_purge_generated_images_empties_root_and_recreates(tmp_path):
    root = tmp_path / "generated"
    root.mkdir()
    sentinel = root / "abc__enhanced.png"
    sentinel.write_bytes(b"derived")
    nested = root / "sub"
    nested.mkdir()
    (nested / "x__binarized.png").write_bytes(b"derived")

    purge_generated_images(root)

    assert root.exists()  # re-created empty for the next sweep
    assert list(root.iterdir()) == []  # contents gone
    assert not sentinel.exists()


def test_purge_generated_images_missing_root_is_noop(tmp_path):
    root = tmp_path / "never_created"
    # Must not raise on a fresh demo that never preprocessed anything.
    purge_generated_images(root)
    # A no-op may leave the root absent OR create it empty — either is acceptable;
    # the contract is "no error" and "nothing derived remains".
    assert not root.exists() or list(root.iterdir()) == []


def test_purge_does_not_touch_fixtures_images():
    """The helper only ever references the derived root passed to it; the baked-in
    read-only fixtures are never deleted."""
    fixtures_images = REPO_ROOT / "fixtures" / "images"
    before = fixtures_images.exists()
    # Purge an unrelated derived root; fixtures must be untouched regardless.
    purge_generated_images(REPO_ROOT / "data" / "does_not_exist_xyz")
    assert fixtures_images.exists() == before


def test_purge_refuses_repo_root_and_fixtures_parents():
    """Path-safety guard: a GENERATED_IMAGES_DIR misconfig pointing AT the repo
    root, the fixtures tree, or an ancestor of fixtures must be refused — never
    rmtree'd — so AC-2 ("fixtures/images/ NEVER touched") holds even under a bad
    env. The fixtures tree is real and populated; assert it survives every probe.
    """
    fixtures_images = REPO_ROOT / "fixtures" / "images"
    assert fixtures_images.exists()  # precondition: the baked-in tree is present
    for danger in (
        REPO_ROOT,  # repo root itself
        REPO_ROOT / "fixtures",  # the fixtures tree
        REPO_ROOT / "fixtures" / "images",  # the protected leaf
    ):
        purge_generated_images(danger)  # must be a logged no-op, not destructive
        assert fixtures_images.exists()
        # The repo root / fixtures dirs are NOT emptied.
        assert any((REPO_ROOT / "fixtures").iterdir())


def test_purge_handles_non_directory_root(tmp_path):
    """A stray FILE where the derived dir was expected is removed and replaced by
    an empty dir, so the next sweep's mkdir succeeds (rather than rmtree raising
    NotADirectoryError on a file)."""
    root = tmp_path / "generated"
    root.write_bytes(b"stray-file-not-a-dir")  # misconfig: a file at the dir path
    assert root.is_file()

    purge_generated_images(root)

    assert root.is_dir()  # replaced with an empty directory
    assert list(root.iterdir()) == []


# ── Reset orchestrator (unit, no HTTP) ───────────────────────────────────────


def test_reset_reseeds_db_and_purges_generated(tmp_path, monkeypatch):
    db_path = tmp_path / "ops.db"
    gen_root = tmp_path / "generated"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GENERATED_IMAGES_DIR", str(gen_root))
    init_db(db_path)
    seed(db_path)
    _decide_all(db_path)
    gen_root.mkdir(parents=True, exist_ok=True)
    (gen_root / "stale__enhanced.png").write_bytes(b"x")

    settings = get_settings()
    reset(settings)

    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT status, disposition, decided_at, decision_notes, engine_verdict "
            "FROM submissions"
        ).fetchall()
        assert rows  # corpus restored
        assert all(r["status"] == "RECEIVED" for r in rows)
        assert all(r["disposition"] is None for r in rows)
        assert all(r["decided_at"] is None for r in rows)
        assert all(r["decision_notes"] is None for r in rows)
        assert all(r["engine_verdict"] is None for r in rows)
        assert conn.execute("SELECT COUNT(*) FROM review_progress").fetchone()[0] == 0
    assert gen_root.exists()
    assert list(gen_root.iterdir()) == []


def test_reset_swallows_fs_purge_failure_after_committed_reseed(tmp_path, monkeypatch):
    """AC-2 / Task-2 best-effort posture: the DB commit is the success boundary —
    a purge failure (ANY exception, not just OSError) is logged + swallowed so the
    committed re-seed still 'succeeds' (reset returns the count, never raises)."""
    import app.web.ops as ops

    db_path = tmp_path / "ops.db"
    gen_root = tmp_path / "generated"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GENERATED_IMAGES_DIR", str(gen_root))
    init_db(db_path)

    # Make the FS purge blow up with a NON-OSError to prove the swallow is broad
    # enough that a committed re-seed can never 500 / be reported as failed.
    def boom(_dir):
        raise RuntimeError("simulated purge failure")

    monkeypatch.setattr(ops, "purge_generated_images", boom)

    count = reset(get_settings())  # must NOT raise
    assert count > 0  # the re-seed is the authoritative, committed result
    with connect(db_path) as conn:
        rows = conn.execute("SELECT status FROM submissions").fetchall()
        assert rows and all(r["status"] == "RECEIVED" for r in rows)


def test_reset_propagates_seed_failure_leaving_prior_corpus_intact(tmp_path, monkeypatch):
    """AC-1 atomicity: if the transactional re-seed fails it rolls back (prior
    corpus intact, no partial wipe) and the failure propagates — it is NOT
    swallowed by the FS-purge guard (the purge must never even run)."""
    import app.web.ops as ops

    db_path = tmp_path / "ops.db"
    gen_root = tmp_path / "generated"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("GENERATED_IMAGES_DIR", str(gen_root))
    init_db(db_path)
    expected = seed(db_path)
    _decide_all(db_path)  # a populated, DECIDED prior corpus

    # The purge must never run if the re-seed failed; trip it if it does.
    def must_not_run(_dir):
        raise AssertionError("FS purge ran despite a failed re-seed")

    monkeypatch.setattr(ops, "purge_generated_images", must_not_run)

    def failing_seed(_db_path):
        raise sqlite3.OperationalError("simulated re-seed failure")

    monkeypatch.setattr(ops, "seed", failing_seed)

    with pytest.raises(sqlite3.OperationalError):
        reset(get_settings())

    # Prior corpus untouched: same row count, still DECIDED (no partial wipe).
    with connect(db_path) as conn:
        rows = conn.execute("SELECT status FROM submissions").fetchall()
        assert len(rows) == expected
        assert all(r["status"] == "DECIDED" for r in rows)


# ── AC-1: POST /reset transactionally re-seeds ───────────────────────────────


def test_post_reset_restores_corpus_and_clears_decisions(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "ops.db"
    expected = seed(db_path)
    _decide_all(db_path)

    resp = client.post("/reset", follow_redirects=False)
    assert resp.status_code == 303

    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, status, disposition, decided_at, decision_notes FROM submissions"
        ).fetchall()
        assert len(rows) == expected  # row-count restored
        assert all(r["status"] == "RECEIVED" for r in rows)
        assert all(r["disposition"] is None for r in rows)
        assert all(r["decided_at"] is None for r in rows)
        assert all(r["decision_notes"] is None for r in rows)
        # review_progress purged by the cascade (AR-14).
        assert conn.execute("SELECT COUNT(*) FROM review_progress").fetchone()[0] == 0
        # Children re-populated: each submission has its label_images + one SEEDED row.
        for r in rows:
            sid = r["id"]
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM label_images WHERE submission_id=?", (sid,)
                ).fetchone()[0]
                >= 1
            )
            seeded = conn.execute(
                "SELECT COUNT(*) FROM audit_events WHERE submission_id=? AND event_type='SEEDED'",
                (sid,),
            ).fetchone()[0]
            assert seeded == 1


# ── AC-2: POST /reset purges the generated-images root ───────────────────────


def test_post_reset_purges_generated_images(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "ops.db"
    seed(db_path)
    gen_root = tmp_path / "generated"
    gen_root.mkdir(parents=True, exist_ok=True)
    sentinel = gen_root / "victim__enhanced.png"
    sentinel.write_bytes(b"derived")

    resp = client.post("/reset", follow_redirects=False)
    assert resp.status_code == 303

    assert not sentinel.exists()
    assert gen_root.exists()
    assert list(gen_root.iterdir()) == []
    # Read-only baked-in fixtures untouched.
    assert (REPO_ROOT / "fixtures" / "images").exists()


def test_post_reset_with_missing_generated_root_is_clean(tmp_path, monkeypatch):
    """A fresh demo that never preprocessed (no generated root) resets without error."""
    client = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "ops.db"
    seed(db_path)
    gen_root = tmp_path / "generated"
    assert not gen_root.exists()  # never created

    resp = client.post("/reset", follow_redirects=False)
    assert resp.status_code == 303
    # No raise; root absent or empty.
    assert not gen_root.exists() or list(gen_root.iterdir()) == []


# ── AC-3: reset restores the queue after full exhaustion ─────────────────────


def test_post_reset_restores_queue_after_exhaustion(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "ops.db"
    seed(db_path)
    _decide_all(db_path)
    with connect(db_path) as conn:
        # Precondition: pending queue exhausted (no RECEIVED rows for the sweep).
        assert (
            conn.execute("SELECT COUNT(*) FROM submissions WHERE status='RECEIVED'").fetchone()[0]
            == 0
        )

    resp = client.post("/reset", follow_redirects=False)
    assert resp.status_code == 303

    with connect(db_path) as conn:
        # Every re-seeded row is RECEIVED — the precondition the sweep consumes to
        # carry rows forward to READY_FOR_REVIEW (sweep itself is Story 2.2's test).
        total = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        received = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE status='RECEIVED'"
        ).fetchone()[0]
        assert received == total
        assert received > 0


# ── AC-4: honest redirect + token gate + no leakage ──────────────────────────


def test_post_reset_redirects_to_queue_303(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    seed(tmp_path / "ops.db")
    resp = client.post("/reset", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/queue"


def test_post_reset_response_leaks_no_data(tmp_path, monkeypatch):
    client = _client(monkeypatch, tmp_path)
    db_path = tmp_path / "ops.db"
    seed(db_path)
    # Capture a known submission identifier to assert it does not appear in the body.
    with connect(db_path) as conn:
        ttb_id = conn.execute("SELECT ttb_id FROM submissions LIMIT 1").fetchone()["ttb_id"]

    resp = client.post("/reset", follow_redirects=False)
    body = resp.text
    # The bare 303 redirect carries an EMPTY body by construction — pin that so the
    # assertion can actually fail if the route ever renders a page before redirect
    # (the substring checks below are vacuous on an empty body otherwise).
    assert body == ""
    assert ttb_id not in body
    # The redirect body carries no submission/image/benchmark payload.
    assert "submission" not in body.lower()
    assert "benchmark" not in body.lower()


def test_post_reset_is_token_gated(tmp_path, monkeypatch):
    """With ACCESS_TOKEN set, an unauthenticated POST /reset is bounced to /access
    (no exemption added in main.py) — and never re-seeds."""
    client = _client(monkeypatch, tmp_path, token="s3cret")
    db_path = tmp_path / "ops.db"
    seed(db_path)
    _decide_all(db_path)

    resp = client.post("/reset", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/access"
    # The gate fired BEFORE any reset: the decided rows are untouched.
    with connect(db_path) as conn:
        decided = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE status='DECIDED'"
        ).fetchone()[0]
        assert decided > 0
