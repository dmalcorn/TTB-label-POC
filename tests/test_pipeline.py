"""Background sweep & submission lifecycle tests (Story 2.2, AC1–AC5).

Offline, fast, deterministic — NO real Tesseract/Paddle/provider and NO live
scheduler. The pipeline's middle stages are swapped for in-test stubs via the
``run.STAGES`` seam, so the whole suite runs under ``docker run --network none``
with zero native deps (the same instinct as 2.1's in-test stub adapters).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.contracts import OcrResult
from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.pipeline import run, status


def _make_db(tmp_path):
    db_path = tmp_path / "pipeline.db"
    init_db(db_path)
    return db_path


def _insert_received(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26001000000001",
        "beverage_type": "WINE",
        "brand_name": "Stone's Throw",
        "status": "RECEIVED",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    return int(cur.lastrowid)


def _insert_image(conn: sqlite3.Connection, submission_id: int, **overrides) -> int:
    cols = {
        "submission_id": submission_id,
        "image_role": "BRAND",
        "position": 1,
        "filename": "front.jpg",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO label_images ({', '.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    return int(cur.lastrowid)


def _events(conn: sqlite3.Connection, submission_id: int) -> list[sqlite3.Row]:
    # Order by (occurred_at, id): CURRENT_TIMESTAMP has 1s resolution, so the
    # monotonic id breaks ties and preserves causal/insertion order.
    return conn.execute(
        "SELECT * FROM audit_events WHERE submission_id = ? ORDER BY occurred_at, id",
        (submission_id,),
    ).fetchall()


# ── Task 1: status.py — claim, forward transitions, audit, timing ────────────


def test_claim_for_processing_flips_received_to_processing(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)
        assert status.claim_for_processing(conn, sid) is True
        assert repo.get_status(conn, sid) == "PROCESSING"


def test_claim_is_atomic_only_one_winner(tmp_path):
    """AC1: two concurrent claims on the same row → exactly one True (no double
    processing). Separate connections model two sweep workers."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)

    conn_a = repo_conn(db_path)
    conn_b = repo_conn(db_path)
    try:
        results = [
            status.claim_for_processing(conn_a, sid),
            status.claim_for_processing(conn_b, sid),
        ]
    finally:
        conn_a.close()
        conn_b.close()
    assert results.count(True) == 1
    assert results.count(False) == 1


def repo_conn(db_path) -> sqlite3.Connection:
    from app.db.connection import get_connection

    return get_connection(db_path)


def test_advance_forward_writes_status_and_audit(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)
        status.claim_for_processing(conn, sid)
        status.advance(conn, sid, to_status="READY_FOR_REVIEW", event_type="READY")
        assert repo.get_status(conn, sid) == "READY_FOR_REVIEW"
        evt = _events(conn, sid)[-1]
    assert evt["event_type"] == "READY"
    assert evt["from_status"] == "PROCESSING"
    assert evt["to_status"] == "READY_FOR_REVIEW"
    assert evt["actor"] == "pipeline"


def test_advance_rejects_non_forward_transition(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)
        status.claim_for_processing(conn, sid)
        status.advance(conn, sid, to_status="READY_FOR_REVIEW", event_type="READY")
        with pytest.raises(ValueError, match="non-forward"):
            status.advance(conn, sid, to_status="PROCESSING", event_type="OCR_STARTED")


def test_advance_rejects_out_of_vocab_event(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)
        status.claim_for_processing(conn, sid)
        with pytest.raises(ValueError, match="event_type"):
            status.advance(conn, sid, to_status="READY_FOR_REVIEW", event_type="FAILED")


def test_record_event_rejects_out_of_vocab(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)
        with pytest.raises(ValueError, match="event_type"):
            status.record_event(conn, sid, event_type="BOGUS")


def test_set_processing_ms_rejects_negative(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)
        with pytest.raises(ValueError, match=">= 0"):
            status.set_processing_ms(conn, sid, -1)


# ── Task 2 / AC2 / AC3: orchestrator, stage seam, timeline ───────────────────


def test_process_submission_finalizes_with_ordered_timeline(tmp_path):
    """AC2: after processing, status is READY_FOR_REVIEW, processing_ms is set
    (>= 0), and the audit timeline is OCR_STARTED → OCR_COMPLETED →
    ANALYSIS_COMPLETED → READY with correct from/to on the READY transition."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)
        _insert_image(conn, sid)

    run.process_submission(str(db_path), sid)

    with connect(db_path) as conn:
        sub = repo.get_submission(conn, sid)
        events = _events(conn, sid)
    assert sub is not None
    assert sub.status == "READY_FOR_REVIEW"
    assert sub.processing_ms is not None and sub.processing_ms >= 0
    assert sub.engine_verdict is None  # verdict roll-up is Epic 3, not 2.2
    assert [e["event_type"] for e in events] == [
        "OCR_STARTED",
        "OCR_COMPLETED",
        "ANALYSIS_COMPLETED",
        "READY",
    ]
    ready = events[-1]
    assert ready["from_status"] == "PROCESSING"
    assert ready["to_status"] == "READY_FOR_REVIEW"


def test_process_submission_noops_when_already_claimed(tmp_path):
    """An id that is no longer RECEIVED (claimed/processed) is a clean no-op —
    the losing worker writes nothing."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)
    run.process_submission(str(db_path), sid)  # first run finalizes it
    with connect(db_path) as conn:
        before = len(_events(conn, sid))
    run.process_submission(str(db_path), sid)  # second run must no-op
    with connect(db_path) as conn:
        after = len(_events(conn, sid))
        assert repo.get_status(conn, sid) == "READY_FOR_REVIEW"
    assert after == before


def test_stage_seam_is_the_single_registration_point(tmp_path, monkeypatch):
    """AC3/seam: swapping run.STAGES changes pipeline behavior with NO edit to
    scheduler.py/status.py. A custom stage's marker appears; the default
    OCR_STARTED/OCR_COMPLETED markers do not."""

    def custom_stage(ctx: run.StageContext) -> None:
        status.record_event(ctx.conn, ctx.submission.id, event_type="OCR_STARTED", note="custom")

    custom_stage.__name__ = "custom_stage"
    monkeypatch.setattr(run, "STAGES", [custom_stage])

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)
    run.process_submission(str(db_path), sid)

    with connect(db_path) as conn:
        events = _events(conn, sid)
        types = [e["event_type"] for e in events]
        notes = [e["note"] for e in events]
    assert "custom" in notes  # the swapped stage ran
    assert types.count("OCR_COMPLETED") == 0  # default passthrough did NOT run
    assert types[-1] == "READY"  # lifecycle spine unchanged


# ── Task 4 / AC4: finalize-on-failure, sibling unaffected ────────────────────


def test_stage_failure_finalizes_and_records_note_sibling_unaffected(tmp_path, monkeypatch):
    """AC4: a stage that raises → the submission is finalized (READY_FOR_REVIEW,
    NOT stuck PROCESSING) with an honest failure note; a sibling RECEIVED row is
    processed normally and unaffected."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        failing = _insert_received(conn, ttb_id="26001000000010")
        sibling = _insert_received(conn, ttb_id="26001000000011")

    def selective_stage(ctx: run.StageContext) -> None:
        if ctx.submission.id == failing:
            raise RuntimeError("simulated engine crash")
        status.record_event(ctx.conn, ctx.submission.id, event_type="OCR_COMPLETED")

    selective_stage.__name__ = "selective_stage"
    monkeypatch.setattr(run, "STAGES", [selective_stage])

    from app.pipeline.scheduler import sweep

    sweep(str(db_path), batch_size=10, max_workers=2)

    with connect(db_path) as conn:
        fail_sub = repo.get_submission(conn, failing)
        sib_sub = repo.get_submission(conn, sibling)
        fail_events = _events(conn, failing)
        sib_events = _events(conn, sibling)

    # Failed submission: finalized, not stuck; failure note present; no fake verdict.
    assert fail_sub is not None and fail_sub.status == "READY_FOR_REVIEW"
    assert fail_sub.engine_verdict is None
    assert any(e["note"] and "failed" in e["note"] for e in fail_events)
    # Sibling: processed normally, no failure note.
    assert sib_sub is not None and sib_sub.status == "READY_FOR_REVIEW"
    assert not any(e["note"] and "failed" in e["note"] for e in sib_events)


def test_post_claim_failure_is_rescued_not_left_stuck(tmp_path, monkeypatch):
    """[Review][Patch] An exception in the finalize steps AFTER the atomic claim
    (simulated here as a failing set_processing_ms) must NOT leave the row stuck in
    PROCESSING — the worker best-effort finalizes it to READY_FOR_REVIEW on a fresh
    connection. AC4's finalize-don't-stall posture, extended to the infra-failure
    path (claim commits PROCESSING immediately; nothing else ever re-claims it)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, ttb_id="26001000000020")

    def boom(*args, **kwargs):
        raise RuntimeError("simulated DB failure mid-finalize")

    # Fails after the claim is committed and after ANALYSIS_COMPLETED is recorded;
    # the rescue path uses status.advance (not patched), so it still finalizes.
    monkeypatch.setattr(status, "set_processing_ms", boom)

    run.process_submission(str(db_path), sid)

    with connect(db_path) as conn:
        sub = repo.get_submission(conn, sid)
        events = _events(conn, sid)

    assert sub is not None and sub.status == "READY_FOR_REVIEW"  # rescued, not stuck
    assert any(e["note"] and "after worker failure" in e["note"] for e in events)


# ── Task 3 / AC1 / AC5: bounded sweep + scheduler wiring ─────────────────────


def test_sweep_processes_whole_bounded_batch(tmp_path):
    """AC1/AC5 (light): a sweep claims and finalizes the bounded batch; structure
    and finalization are asserted, not a wall-clock SLA."""
    from app.pipeline.scheduler import sweep

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        ids = [_insert_received(conn, ttb_id=f"260010000000{i:02d}") for i in range(5)]

    sweep(str(db_path), batch_size=10, max_workers=2)

    with connect(db_path) as conn:
        statuses = {repo.get_status(conn, i) for i in ids}
    assert statuses == {"READY_FOR_REVIEW"}


def test_sweep_respects_batch_size(tmp_path):
    """AC1: only the bounded batch is claimed per tick (no unbounded fan-out)."""
    from app.pipeline.scheduler import sweep

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        ids = [_insert_received(conn, ttb_id=f"260010000001{i:02d}") for i in range(5)]

    sweep(str(db_path), batch_size=2, max_workers=2)

    with connect(db_path) as conn:
        ready = [i for i in ids if repo.get_status(conn, i) == "READY_FOR_REVIEW"]
        received = [i for i in ids if repo.get_status(conn, i) == "RECEIVED"]
    assert len(ready) == 2
    assert len(received) == 3


def test_start_scheduler_disabled_returns_none(tmp_path):
    """Guard: scheduler_enabled=false starts nothing (TestClient-friendly)."""
    from fastapi import FastAPI

    from app.config import Settings
    from app.pipeline.scheduler import start_scheduler

    app = FastAPI()
    app.state.settings = Settings(scheduler_enabled=False, database_path=str(tmp_path / "a.db"))
    assert start_scheduler(app) is None
    assert app.state.scheduler is None


def test_start_and_shutdown_scheduler_lifecycle(tmp_path):
    """Enabled path: start_scheduler builds a running scheduler; shutdown stops it.
    A long interval avoids any sweep firing during the test."""
    from fastapi import FastAPI

    from app.config import Settings
    from app.pipeline.scheduler import shutdown_scheduler, start_scheduler

    db_path = _make_db(tmp_path)
    app = FastAPI()
    app.state.settings = Settings(
        scheduler_enabled=True,
        sweep_interval_seconds=3600,
        database_path=str(db_path),
    )
    scheduler = start_scheduler(app)
    try:
        assert scheduler is not None and scheduler.running
        assert app.state.scheduler is scheduler
    finally:
        shutdown_scheduler(app)
    assert not scheduler.running


# ── Task 6: settings defaults / env parsing ──────────────────────────────────


def test_pipeline_settings_defaults(monkeypatch):
    from app.config import Settings

    for key in (
        "SCHEDULER_ENABLED",
        "SWEEP_INTERVAL_SECONDS",
        "PIPELINE_MAX_WORKERS",
        "PIPELINE_BATCH_SIZE",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = Settings.from_env()
    assert settings.scheduler_enabled is True
    assert settings.sweep_interval_seconds == 5
    assert settings.pipeline_max_workers == 2
    assert settings.pipeline_batch_size == 10


def test_pipeline_int_env_garbage_falls_back_to_default(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("PIPELINE_BATCH_SIZE", "not-a-number")
    monkeypatch.setenv("SWEEP_INTERVAL_SECONDS", "")
    settings = Settings.from_env()
    assert settings.pipeline_batch_size == 10
    assert settings.sweep_interval_seconds == 5


def test_pipeline_int_env_out_of_range_falls_back_to_default(monkeypatch):
    """[Review][Patch] Non-positive pipeline ints are degenerate config: a
    zero/negative SWEEP_INTERVAL_SECONDS crashes APScheduler at boot, and a
    zero/negative PIPELINE_BATCH_SIZE makes the LIMIT inert (0) or unbounded
    (negative ⇒ no limit in SQLite). They must floor to the safe default."""
    from app.config import Settings

    monkeypatch.setenv("SWEEP_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("PIPELINE_BATCH_SIZE", "-5")
    monkeypatch.setenv("PIPELINE_MAX_WORKERS", "0")
    settings = Settings.from_env()
    assert settings.sweep_interval_seconds == 5
    assert settings.pipeline_batch_size == 10
    assert settings.pipeline_max_workers == 2


def test_scheduler_disabled_env_is_respected(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    assert Settings.from_env().scheduler_enabled is False


# ── Live wiring: the scheduler actually FIRES through the lifespan ────────────


def test_live_scheduler_fires_and_finalizes_via_lifespan(tmp_path, monkeypatch):
    """Regression guard: the unit tests call sweep() directly, so a job that is
    registered but never fires (e.g. an accidental APScheduler `next_run_time=None`
    pause) would pass them all yet ship a dead sweep. This drives the REAL
    scheduler through the FastAPI lifespan and asserts a RECEIVED row reaches
    READY_FOR_REVIEW on its own. Bounded poll — no fixed sleep, no SLA assertion."""
    import time

    from fastapi.testclient import TestClient

    from app.main import create_app

    db_path = tmp_path / "live.db"
    init_db(db_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)  # non-empty DB ⇒ seed-if-empty no-ops

    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SWEEP_INTERVAL_SECONDS", "1")
    monkeypatch.delenv("ACCESS_TOKEN", raising=False)

    with TestClient(create_app()):
        deadline = time.monotonic() + 15.0
        final = None
        while time.monotonic() < deadline:
            with connect(db_path) as conn:
                final = repo.get_status(conn, sid)
            if final == "READY_FOR_REVIEW":
                break
            time.sleep(0.2)
    assert final == "READY_FOR_REVIEW", f"live sweep never finalized the row (stuck at {final})"


# ── Story 2.4: OCR stage — engine-aware variant routing + honest failures ─────
# Offline + native-dep-free: stub OcrEngines are injected via the ocr.build_engines
# registry seam, so no real Tesseract/Paddle is needed (same instinct as the 2.1/2.2
# stub adapters). The stubs are named "tesseract"/"paddleocr" so the engine-aware
# preference map (tesseract↔BINARIZED, paddleocr↔ENHANCED) applies unchanged.


class _StubOcr:
    """A stub OcrEngine for stage tests: returns an OK result keyed to the path it
    was handed, or raises to exercise the per-engine failure path (AC5)."""

    def __init__(self, name: str, *, raises: bool = False, version: str = "9.9-stub") -> None:
        self.name = name
        self.version = version
        self._raises = raises

    def extract(self, image_path, *, ran_on_cpu: bool = True) -> OcrResult:
        if self._raises:
            raise RuntimeError(f"{self.name} simulated crash")
        return OcrResult(
            engine_name=self.name,
            engine_version=self.version,
            text=f"text::{Path(image_path).name}",
            confidence=0.9,
            latency_ms=1,
            ran_on_cpu=ran_on_cpu,
            status="OK",
        )


def _stage_ctx(conn, sid, scratch):
    from app.pipeline.run import StageContext

    return StageContext(
        conn=conn,
        submission=repo.get_submission(conn, sid),
        label_images=repo.list_label_images(conn, sid),
        scratch=scratch,
    )


def test_ocr_stage_routes_original_plus_preferred_variant_per_engine(tmp_path, monkeypatch):
    """AC2/AC3: a degraded image (both 2.3 variants present) yields FOUR independent
    rows — each engine OCRs the ORIGINAL and its preferred variant (Tesseract↔
    BINARIZED, PaddleOCR↔ENHANCED), each row tagged with the variant it consumed."""
    from app.pipeline import ocr as ocrmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")
        img_id = _insert_image(conn, sid, filename="front.jpg")

    monkeypatch.setattr(
        ocrmod, "build_engines", lambda: [_StubOcr("tesseract"), _StubOcr("paddleocr")]
    )
    scratch = {
        "variants": {
            img_id: {
                "original": "front.jpg",
                "enhanced": "front__enhanced.png",
                "binarized": "front__binarized.png",
            }
        }
    }
    with connect(db_path) as conn:
        ocrmod.ocr_stage(_stage_ctx(conn, sid, scratch))

    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT engine_name, image_variant FROM ocr_results WHERE submission_id = ? "
            "ORDER BY engine_name, image_variant",
            (sid,),
        ).fetchall()
    assert [(r["engine_name"], r["image_variant"]) for r in rows] == [
        ("paddleocr", "ENHANCED"),
        ("paddleocr", "ORIGINAL"),
        ("tesseract", "BINARIZED"),
        ("tesseract", "ORIGINAL"),
    ]


def test_ocr_stage_clean_image_runs_original_only(tmp_path, monkeypatch):
    """AC3: a clean image (no 2.3 variants) is OCR'd on the ORIGINAL only — one row
    per engine, all ORIGINAL."""
    from app.pipeline import ocr as ocrmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")
        img_id = _insert_image(conn, sid, filename="clean.jpg")

    monkeypatch.setattr(
        ocrmod, "build_engines", lambda: [_StubOcr("tesseract"), _StubOcr("paddleocr")]
    )
    scratch = {"variants": {img_id: {"original": "clean.jpg", "enhanced": None, "binarized": None}}}
    with connect(db_path) as conn:
        ocrmod.ocr_stage(_stage_ctx(conn, sid, scratch))

    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT engine_name, image_variant FROM ocr_results WHERE submission_id = ? "
            "ORDER BY engine_name",
            (sid,),
        ).fetchall()
    assert [(r["engine_name"], r["image_variant"]) for r in rows] == [
        ("paddleocr", "ORIGINAL"),
        ("tesseract", "ORIGINAL"),
    ]


def test_ocr_stage_engine_failure_writes_error_row_sibling_survives(tmp_path, monkeypatch):
    """AC5: a raising engine → an ERROR ocr_results row WITH error_text; the sibling
    engine's row is still written and the submission still finalizes (not stuck)."""
    from app.pipeline import ocr as ocrmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, ttb_id="26001000000400")
        _insert_image(conn, sid, filename="missing.jpg")  # no file ⇒ original-only routing

    monkeypatch.setattr(
        ocrmod,
        "build_engines",
        lambda: [_StubOcr("tesseract", raises=True), _StubOcr("paddleocr")],
    )

    run.process_submission(str(db_path), sid)

    with connect(db_path) as conn:
        sub = repo.get_submission(conn, sid)
        rows = conn.execute(
            "SELECT engine_name, status, error_text FROM ocr_results WHERE submission_id = ?",
            (sid,),
        ).fetchall()
    assert sub is not None and sub.status == "READY_FOR_REVIEW"  # finalized, not stuck
    by_engine = {r["engine_name"]: r for r in rows}
    assert by_engine["tesseract"]["status"] == "ERROR"
    assert by_engine["tesseract"]["error_text"]  # honest, non-empty note
    assert by_engine["paddleocr"]["status"] == "OK"  # sibling unaffected


def test_ocr_results_stores_raw_text_only_no_per_field_columns(tmp_path):
    """AC2 structural guard: ocr_results holds raw text + metadata, NOT a column per
    matchable field — per-field parsing into field_comparisons is Epic 3, not 2.4."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(ocr_results)").fetchall()}
    assert {"extracted_text", "image_variant"} <= cols
    forbidden = {
        "brand_name",
        "fanciful_name",
        "abv",
        "alcohol_content",
        "net_contents",
        "class_type_designation",
        "grape_varietal",
        "wine_appellation",
    }
    assert cols.isdisjoint(forbidden)
