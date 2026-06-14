"""Background sweep & submission lifecycle tests (Story 2.2, AC1–AC5).

Offline, fast, deterministic — NO real Tesseract/Paddle/provider and NO live
scheduler. The pipeline's middle stages are swapped for in-test stubs via the
``run.STAGES`` seam, so the whole suite runs under ``docker run --network none``
with zero native deps (the same instinct as 2.1's in-test stub adapters).
"""

from __future__ import annotations

import sqlite3
import threading
import time
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
    assert cur.lastrowid is not None  # guaranteed by a successful INSERT
    return cur.lastrowid


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
    assert cur.lastrowid is not None  # guaranteed by a successful INSERT
    return cur.lastrowid


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
    # Story 3.2 wires engine_stage in LAST, so a finalized submission carries a
    # non-NULL advisory roll-up. The WINE ruleset is now AUTHORED (Story 3.8), so
    # real checks run and the concrete verdict depends on what OCR recovers (here,
    # with no native OCR deps, the engine still finalizes honestly) — this test's
    # subject is the lifecycle timeline + status, so assert the verdict is a legal
    # rolled-up value, not a brittle literal.
    assert sub.engine_verdict in {"PASS", "REVIEW", "FAIL"}
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
    # (STAGES is monkeypatched to [selective_stage], so engine_stage never runs here —
    # engine_verdict stays NULL, proving a crashing pipeline invents no advisory verdict.)
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


# ── Story 2.5: VLM stage — config-gated, image-based, OCR-only fallback ───────
# Offline by construction: a fake ModelAdapter (canned or raising) is injected via
# the llm.get_llm_adapter seam; OCR engines are stubbed as above. No real provider.
# VLM-only: the stage hands the model the label IMAGE, never OCR text.


class _FakeModel:
    """Canned ModelAdapter; ``raises=True`` simulates an unreachable provider.

    Records every ``run`` call so a test can assert the stage handed the model an
    image (VLM-only) and an OCR-free prompt."""

    model_name = "Fake Model"
    model_id = "fake-1"
    model_full_id = "fake-1[test]"
    provider = "local"

    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises
        self.calls: list[dict] = []

    def run(self, task, prompt, *, image_path=None):
        from app.contracts import LlmResult

        self.calls.append({"task": task, "prompt": prompt, "image_path": image_path})
        if self._raises:
            raise RuntimeError("provider unreachable")
        return LlmResult(
            model_name=self.model_name,
            model_id=self.model_id,
            model_full_id=self.model_full_id,
            provider=self.provider,
            task=task,
            result_text='{"brand_name": "Stone\'s Throw"}',
            prompt_tokens=10,
            completion_tokens=20,
            latency_ms=5,
            requested_at="2026-06-13T00:00:00+00:00",
            responded_at="2026-06-13T00:00:01+00:00",
            status="OK",
        )


def test_llm_stage_persists_stats_with_db_computed_total_tokens(tmp_path, monkeypatch):
    """AC4: a successful adapter → one llm_results row with model identity, provider,
    timing, tokens, and a DB-COMPUTED total_tokens (10+20=30, never inserted)."""
    from app.pipeline import llm as llmmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")
        img_id = _insert_image(conn, sid)

    monkeypatch.setattr(llmmod, "get_llm_adapter", lambda settings: _FakeModel())
    with connect(db_path) as conn:
        llmmod.llm_stage(_stage_ctx(conn, sid, {}))

    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM llm_results WHERE submission_id = ?", (sid,)).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "OK"
    assert row["provider"] == "local"
    assert (row["model_name"], row["model_id"], row["model_full_id"]) == (
        "Fake Model",
        "fake-1",
        "fake-1[test]",
    )
    assert row["task"] == "extract_fields"
    assert row["prompt_tokens"] == 10 and row["completion_tokens"] == 20
    assert row["total_tokens"] == 30  # DB GENERATED column — never inserted
    assert row["requested_at"] and row["responded_at"] and row["latency_ms"] == 5
    assert row["label_image_id"] == img_id
    assert row["is_benchmark_only"] == 0  # the displayed extraction (not benchmark-only)


def test_llm_stage_sends_the_image_not_ocr_text(tmp_path, monkeypatch):
    """VLM-only (the spine of the rework): the stage hands the model the primary label
    IMAGE and an OCR-free instruction prompt — it never reads or forwards OCR text."""
    from app.pipeline import llm as llmmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")
        _insert_image(conn, sid, filename="front.jpg")
        # Seed OCR rows that MUST NOT leak into the model prompt.
        repo.insert_ocr_result(
            conn,
            submission_id=sid,
            label_image_id=repo.list_label_images(conn, sid)[0].id,
            result=OcrResult(engine_name="tesseract", text="SECRET-OCR-LEAK-TOKEN", status="OK"),
        )
        conn.commit()

    fake = _FakeModel()
    monkeypatch.setattr(llmmod, "get_llm_adapter", lambda settings: fake)
    with connect(db_path) as conn:
        llmmod.llm_stage(_stage_ctx(conn, sid, {}))

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["image_path"] is not None and call["image_path"].endswith("front.jpg")
    assert "SECRET-OCR-LEAK-TOKEN" not in call["prompt"]  # OCR text never reaches the model
    assert "OCR" not in call["prompt"]  # the prompt instructs reading the image, not OCR text


def test_llm_stage_skips_when_no_label_image(tmp_path, monkeypatch):
    """VLM-only has nothing to read without an image: an enabled adapter + a submission
    with NO label image ⇒ the stage skips, no model call, no llm_results row."""
    from app.pipeline import llm as llmmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")  # no _insert_image

    fake = _FakeModel()
    monkeypatch.setattr(llmmod, "get_llm_adapter", lambda settings: fake)
    with connect(db_path) as conn:
        llmmod.llm_stage(_stage_ctx(conn, sid, {}))

    assert fake.calls == []  # the model was never called
    with connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM llm_results WHERE submission_id = ?", (sid,)
        ).fetchone()["n"]
    assert count == 0


def test_llm_stage_skips_when_primary_filename_is_blank(tmp_path, monkeypatch):
    """A label image with a blank filename has no readable path (it would resolve to
    the fixtures directory) — the stage skips rather than calling a doomed provider."""
    from app.pipeline import llm as llmmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")
        _insert_image(conn, sid, filename="   ")  # whitespace-only

    fake = _FakeModel()
    monkeypatch.setattr(llmmod, "get_llm_adapter", lambda settings: fake)
    with connect(db_path) as conn:
        llmmod.llm_stage(_stage_ctx(conn, sid, {}))

    assert fake.calls == []  # the model was never called
    with connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM llm_results WHERE submission_id = ?", (sid,)
        ).fetchone()["n"]
    assert count == 0


def test_llm_stage_skips_entirely_when_adapter_is_none(tmp_path, monkeypatch):
    """AC2: factory None ⇒ the stage writes NO llm_results row and constructs nothing."""
    from app.pipeline import llm as llmmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")
        _insert_image(conn, sid)

    monkeypatch.setattr(llmmod, "get_llm_adapter", lambda settings: None)
    with connect(db_path) as conn:
        llmmod.llm_stage(_stage_ctx(conn, sid, {}))

    with connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM llm_results WHERE submission_id = ?", (sid,)
        ).fetchone()["n"]
    assert count == 0


def test_llm_stage_degrades_to_error_row_when_adapter_raises(tmp_path, monkeypatch):
    """AC3: an unreachable provider (adapter raises) → an ERROR llm_results row that
    captures provider + the error in result_text (the queryable degraded signal)."""
    from app.pipeline import llm as llmmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")
        _insert_image(conn, sid)

    monkeypatch.setattr(llmmod, "get_llm_adapter", lambda settings: _FakeModel(raises=True))
    with connect(db_path) as conn:
        llmmod.llm_stage(_stage_ctx(conn, sid, {}))

    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, provider, result_text, requested_at, responded_at "
            "FROM llm_results WHERE submission_id = ?",
            (sid,),
        ).fetchone()
    assert row is not None
    assert row["status"] == "ERROR"
    assert row["provider"] == "local"  # identity preserved on the degraded row
    assert "unreachable" in (row["result_text"] or "")
    # The stage-level fallback stamps timing too, so even a raising adapter is honest.
    assert row["requested_at"] and row["responded_at"]


def test_pipeline_llm_disabled_reaches_ready_ocr_only_constructs_nothing(tmp_path, monkeypatch):
    """AC2/AC5: with LLM_ENABLED unset (default off) the full pipeline finalizes
    OCR-only — submission reaches READY_FOR_REVIEW, NO llm_results row exists, and the
    adapter factory constructs NOTHING (no provider SDK, no client, no socket)."""
    import app.config as cfg
    from app.pipeline import ocr as ocrmod

    for key in ("LLM_ENABLED", "LLM_PROVIDER", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    constructed: list = []
    monkeypatch.setattr(cfg, "_construct_adapter", lambda *a, **k: constructed.append(1))
    monkeypatch.setattr(
        ocrmod, "build_engines", lambda: [_StubOcr("tesseract"), _StubOcr("paddleocr")]
    )

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, ttb_id="26001000000600")
        _insert_image(conn, sid, filename="missing.jpg")

    run.process_submission(str(db_path), sid)

    with connect(db_path) as conn:
        sub = repo.get_submission(conn, sid)
        llm_count = conn.execute(
            "SELECT COUNT(*) AS n FROM llm_results WHERE submission_id = ?", (sid,)
        ).fetchone()["n"]
    assert sub is not None and sub.status == "READY_FOR_REVIEW"
    assert llm_count == 0
    assert constructed == []  # zero-egress: the model layer was never constructed


def test_pipeline_llm_enabled_persists_row_and_still_finalizes(tmp_path, monkeypatch):
    """AC3/AC4 end-to-end: with a fake adapter wired, the full pipeline writes the
    llm_results row AND the submission still reaches READY_FOR_REVIEW (the model layer
    is additive, never a hard dependency; the read path never blocks)."""
    from app.pipeline import llm as llmmod
    from app.pipeline import ocr as ocrmod

    monkeypatch.setattr(
        ocrmod, "build_engines", lambda: [_StubOcr("tesseract"), _StubOcr("paddleocr")]
    )
    monkeypatch.setattr(llmmod, "get_llm_adapter", lambda settings: _FakeModel())

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, ttb_id="26001000000601")
        _insert_image(conn, sid, filename="missing.jpg")

    run.process_submission(str(db_path), sid)

    with connect(db_path) as conn:
        sub = repo.get_submission(conn, sid)
        row = conn.execute(
            "SELECT status, total_tokens FROM llm_results WHERE submission_id = ?", (sid,)
        ).fetchone()
    assert sub is not None and sub.status == "READY_FOR_REVIEW"
    assert row is not None and row["status"] == "OK" and row["total_tokens"] == 30


# ── Story 5.1: local-only toggleable tracing wired into the LLM stage ─────────


def test_llm_stage_traces_the_call_when_tracing_enabled(tmp_path, monkeypatch):
    """5.1 AC2: with LANGCHAIN_TRACING_ENABLED=true, the stage records the call's
    telemetry locally (trace_llm_call invoked once with the produced LlmResult)."""
    from app.benchmark import tracing as trc
    from app.pipeline import llm as llmmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")
        _insert_image(conn, sid)

    monkeypatch.setenv("LANGCHAIN_TRACING_ENABLED", "true")
    monkeypatch.setattr(llmmod, "get_llm_adapter", lambda settings: _FakeModel())
    traced: list = []
    monkeypatch.setattr(trc, "trace_llm_call", lambda result, **k: traced.append(result))
    with connect(db_path) as conn:
        llmmod.llm_stage(_stage_ctx(conn, sid, {}))

    assert len(traced) == 1
    assert traced[0].model_id == "fake-1" and traced[0].status == "OK"


def test_llm_stage_does_not_trace_when_tracing_disabled(tmp_path, monkeypatch):
    """5.1 AC3: with tracing OFF (default), the stage takes the no-tracing path —
    trace_llm_call is never invoked — and the persisted llm_results row is unchanged."""
    from app.benchmark import tracing as trc
    from app.pipeline import llm as llmmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")
        _insert_image(conn, sid)

    monkeypatch.delenv("LANGCHAIN_TRACING_ENABLED", raising=False)
    monkeypatch.setattr(llmmod, "get_llm_adapter", lambda settings: _FakeModel())

    def _boom(*_a, **_k):  # pragma: no cover - must never run when disabled
        raise AssertionError("trace_llm_call invoked while tracing disabled")

    monkeypatch.setattr(trc, "trace_llm_call", _boom)
    with connect(db_path) as conn:
        llmmod.llm_stage(_stage_ctx(conn, sid, {}))

    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, model_id, total_tokens FROM llm_results WHERE submission_id = ?",
            (sid,),
        ).fetchone()
    # The displayed extraction row is identical whether tracing is on or off.
    assert row is not None
    assert row["status"] == "OK" and row["model_id"] == "fake-1" and row["total_tokens"] == 30


def test_llm_stage_persists_the_row_even_if_tracing_raises(tmp_path, monkeypatch):
    """5.1 AC3 (additive instrumentation): a tracer fault on the ENABLED path must NEVER
    abort the stage or drop the durable llm_results write. With tracing on but
    trace_llm_call raising, the stage swallows it and still persists the identical row a
    tracing-off run would have written."""
    from app.benchmark import tracing as trc
    from app.pipeline import llm as llmmod

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, status="PROCESSING")
        _insert_image(conn, sid)

    monkeypatch.setenv("LANGCHAIN_TRACING_ENABLED", "true")
    monkeypatch.setattr(llmmod, "get_llm_adapter", lambda settings: _FakeModel())

    def _raise(*_a, **_k):
        raise RuntimeError("simulated tracer failure")

    monkeypatch.setattr(trc, "trace_llm_call", _raise)
    with connect(db_path) as conn:
        # Must not raise — the tracer fault is contained in the stage.
        llmmod.llm_stage(_stage_ctx(conn, sid, {}))

    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT status, model_id, total_tokens FROM llm_results WHERE submission_id = ?",
            (sid,),
        ).fetchone()
    # The durable extraction row survives the tracer fault — byte-identical to off.
    assert row is not None
    assert row["status"] == "OK" and row["model_id"] == "fake-1" and row["total_tokens"] == 30


# ── Story 3.2: engine_stage wired LAST — checklist + advisory verdict pre-computed ──


def test_pipeline_spirits_reaches_ready_with_checklist_and_engine_verdict(tmp_path, monkeypatch):
    """Story 3.2 AC5 end-to-end: a swept DISTILLED_SPIRITS submission runs the real
    STAGES (engine_stage LAST) and reaches READY_FOR_REVIEW carrying a COMPLETE
    checklist (one row per spirits Check, each with its provenance) AND a non-NULL
    advisory engine_verdict equal to verdict.rollup over the per-check verdicts. The
    engine is background pre-compute — by the time the row is READY the verdict is
    already persisted (the 5s read path never runs the engine)."""
    from app import verdict
    from app.engine.rulesets import get_ruleset
    from app.pipeline import ocr as ocrmod

    monkeypatch.setattr(
        ocrmod, "build_engines", lambda: [_StubOcr("tesseract"), _StubOcr("paddleocr")]
    )

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, ttb_id="26001000000700", beverage_type="DISTILLED_SPIRITS")
        _insert_image(conn, sid, filename="missing.jpg")

    run.process_submission(str(db_path), sid)

    with connect(db_path) as conn:
        sub = repo.get_submission(conn, sid)
        rows = conn.execute(
            "SELECT check_key, verdict FROM checklist_items WHERE submission_id = ?",
            (sid,),
        ).fetchall()

    assert sub is not None and sub.status == "READY_FOR_REVIEW"
    # One checklist row per spirits Check — the whole ruleset was executed.
    assert len(rows) == len(get_ruleset("DISTILLED_SPIRITS"))
    # The persisted advisory verdict equals the centralized roll-up (engine & UI can
    # never disagree) and is non-NULL. Since Story 3.3 the field_match checks produce
    # REAL verdicts: the stub OCR text ("text::missing.jpg") does not match this
    # submission's application fields, so the matchable checks FAIL and the run rolls
    # up to FAIL (any FAIL ⇒ FAIL) — the still-placeholder checks (gov warning,
    # class/type, sfov) REVIEW. The invariant under test is engine==rollup, not a
    # fixed value.
    assert sub.engine_verdict == verdict.rollup([r["verdict"] for r in rows])
    assert sub.engine_verdict in {"PASS", "REVIEW", "FAIL"}


# ── Concurrency: two workers must not deadlock the SQLite write lock ──────────


class _SlowEngine:
    """A fake OCR engine whose ``extract`` is slow but does no I/O — it stands in for
    real OCR so the concurrency contention is exercised with zero native deps."""

    def __init__(self, name: str) -> None:
        self.name = name

    def extract(self, _path: Path) -> OcrResult:
        time.sleep(0.4)  # simulate slow OCR — longer than the shrunk busy_timeout below
        return OcrResult(engine_name=self.name, status="OK", text="ok")


def test_concurrent_workers_do_not_lock_the_db(tmp_path, monkeypatch):
    """Regression (2-worker DB-lock bug): two workers OCRing different submissions at
    once must not hit ``database is locked``. The OCR stage commits each row, so the
    WAL write lock is never held across the slow per-row extraction; a single
    end-of-stage commit held it for the whole loop and a second worker's write failed
    past ``busy_timeout``.
    """
    from app.pipeline import ocr as ocr_mod

    # Shrink busy_timeout so a lock held across the (simulated) slow extract fails fast
    # and deterministically rather than after the full 5s — the held window is 0.4s.
    monkeypatch.setattr("app.db.connection._BUSY_TIMEOUT_MS", 100)
    # Two engines × the ORIGINAL image ⇒ two writes per submission, with a slow extract
    # between them — exactly the interleave that used to hold the lock.
    monkeypatch.setattr(
        ocr_mod, "build_engines", lambda: [_SlowEngine("tesseract"), _SlowEngine("paddleocr")]
    )
    monkeypatch.setattr(run, "STAGES", [ocr_mod.ocr_stage])

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        s1 = _insert_received(conn, ttb_id="26001000000001")
        _insert_image(conn, s1)
        s2 = _insert_received(conn, ttb_id="26001000000002")
        _insert_image(conn, s2)

    threads = [
        threading.Thread(target=run.process_submission, args=(str(db_path), sid))
        for sid in (s1, s2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with connect(db_path) as conn:
        s1_status = repo.get_status(conn, s1)
        s2_status = repo.get_status(conn, s2)
        locked = conn.execute(
            "SELECT COUNT(*) FROM ocr_results WHERE error_text LIKE '%locked%'"
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM ocr_results").fetchone()[0]
        ok = conn.execute("SELECT COUNT(*) FROM ocr_results WHERE status = 'OK'").fetchone()[0]

    assert s1_status == "READY_FOR_REVIEW"
    assert s2_status == "READY_FOR_REVIEW"
    # No write hit the lock, and every (engine × ORIGINAL × submission) row persisted —
    # none lost to contention, none degraded to an ERROR row by "database is locked".
    assert locked == 0, "OCR persist hit 'database is locked' under concurrency"
    assert total == 4, f"expected 4 OCR rows (2 engines × 2 submissions), got {total}"
    assert ok == 4
