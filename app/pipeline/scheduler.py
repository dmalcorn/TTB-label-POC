"""In-process APScheduler sweep that drives the background pipeline (Story 2.2).

A single ``BackgroundScheduler`` (APScheduler 3.11.x), started in the FastAPI
lifespan, ticks :func:`sweep` on an interval. Each tick claims a **bounded
batch** of the oldest ``RECEIVED`` submissions and processes them through a
**bounded** ``ThreadPoolExecutor`` — never an unbounded fan-out that could starve
the read path (AC1/AC5). The atomic claim in :func:`status.claim_for_processing`
is the real double-process guard; ``max_instances=1`` + ``coalesce=True`` keep
overlapping ticks from piling up on top of it (D3).

Boundaries this honors: it is in-process (D1 single service, no broker, no
egress — runnable under ``docker run --network none``); it never touches the
request path (the scheduler owns all heavy work, the 5-second read contract is
untouched); and every DB write is a short WAL transaction (``status.py`` commits
per step) so readers never block. ``sqlite3`` connections are never shared across
threads — :func:`run.process_submission` opens its own per job.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.config import Settings
from app.db import repositories as repo
from app.db.connection import connect
from app.pipeline.run import process_submission

logger = logging.getLogger(__name__)

_SWEEP_JOB_ID = "pipeline_sweep"


def sweep(db_path: str, *, batch_size: int, max_workers: int) -> None:
    """Claim and process one bounded batch of ``RECEIVED`` submissions.

    Selects the oldest-first ``RECEIVED`` ids (capped at ``batch_size``) in a
    short read, then fans them out across a bounded ``ThreadPoolExecutor`` of at
    most ``max_workers`` — the concurrency ceiling that keeps the read path
    responsive. Each worker opens its own connection and re-checks the atomic
    claim, so an id that another tick already took is a cheap no-op. A single
    submission's failure can never break the batch (``process_submission`` catches
    its own exceptions; we still guard the future result defensively).
    """
    with connect(db_path) as conn:
        ids = repo.list_received_ids(conn, batch_size)
    if not ids:
        return

    logger.debug("Sweep claiming %d submission(s): %s", len(ids), ids)
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
        futures = [pool.submit(process_submission, db_path, sid) for sid in ids]
        for future in futures:
            try:
                future.result()
            except Exception:  # noqa: BLE001 — defensive; process_submission self-guards
                logger.exception("A sweep worker raised unexpectedly")


def start_scheduler(app: FastAPI) -> BackgroundScheduler | None:
    """Build, register, and start the interval sweep — or skip it cleanly.

    Returns ``None`` (and starts nothing) when ``scheduler_enabled`` is false, so
    a ``TestClient`` lifespan can construct the app without a live scheduler. On
    start, stores the scheduler on ``app.state.scheduler`` for shutdown.
    """
    settings: Settings = app.state.settings
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false); sweep not started")
        app.state.scheduler = None
        return None

    db_path = settings.database_path
    scheduler = BackgroundScheduler(
        # One sweep at a time; a slow tick coalesces instead of stacking up (D3).
        job_defaults={"max_instances": 1, "coalesce": True},
    )
    scheduler.add_job(
        sweep,
        trigger="interval",
        seconds=settings.sweep_interval_seconds,
        id=_SWEEP_JOB_ID,
        kwargs={
            "db_path": db_path,
            "batch_size": settings.pipeline_batch_size,
            "max_workers": settings.pipeline_max_workers,
        },
        # coalesce=True (job_defaults) already collapses a backlog of missed ticks
        # into a single run, so a busy host never fires a burst at the read path.
        # (Do NOT pass next_run_time=None here — that PAUSES the job in APScheduler
        # rather than using the trigger's first-fire time.)
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(
        "Background sweep started: every %ss, batch %d, max_workers %d",
        settings.sweep_interval_seconds,
        settings.pipeline_batch_size,
        settings.pipeline_max_workers,
    )
    return scheduler


def shutdown_scheduler(app: FastAPI) -> None:
    """Stop the sweep on app teardown, if one is running. Idempotent / safe when
    the scheduler was never started (disabled path)."""
    scheduler: BackgroundScheduler | None = getattr(app.state, "scheduler", None)
    if scheduler is not None and scheduler.running:
        # wait=True drains an in-flight sweep so a worker that has already claimed
        # a row (committed RECEIVED→PROCESSING) finalizes it to READY_FOR_REVIEW
        # rather than being abandoned mid-flight, leaving the row stuck PROCESSING.
        # Safe for the bounded passthrough stage; revisit alongside a per-job
        # timeout when heavy OCR/LLM stages (2.4/2.5) can hang a worker.
        scheduler.shutdown(wait=True)
        logger.info("Background sweep stopped")
