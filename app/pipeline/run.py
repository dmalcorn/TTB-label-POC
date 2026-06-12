"""The per-submission pipeline orchestrator and its stage seam (Story 2.2).

:func:`process_submission` is the single background unit of work: it atomically
claims a ``RECEIVED`` row, runs an ordered list of **stages** behind a stable
seam, rolls the elapsed time into ``processing_ms``, and advances the row to
``READY_FOR_REVIEW``. Story 2.2 ships ONE :func:`passthrough_stage` that records
the ``OCR_STARTED``/``OCR_COMPLETED`` timeline markers and performs no
extraction; Stories 2.3 (preprocess), 2.4 (OCR), 2.5 (LLM) register their real
stages into :data:`STAGES` with **zero** changes to the scheduler or the status
machinery — that is the whole point of the seam.

Failure posture (FR-9, confirmed design): a stage that raises does NOT abort the
submission and never bubbles into the scheduler thread. The error is recorded
honestly as an ``audit_events`` note (no ``FAILED`` enum is invented — the
vocabulary is locked) and the submission is still **finalized** to
``READY_FOR_REVIEW`` so it is neither stuck in ``PROCESSING`` nor silently lost.
A row whose pipeline *ran and recorded errors* HAS finished pre-compute, so
serving it with the error surfaced is correct — not the "serve a partially-
processed submission" anti-pattern. The advisory verdict roll-up (REVIEW, never
a fake PASS/FAIL) is Epic 3's; 2.2 leaves ``engine_verdict`` NULL.

SQLite + threads: APScheduler runs jobs on worker threads and ``sqlite3``
connections are not shareable across threads, so a FRESH ``connect(db_path)`` is
opened INSIDE this function (per job/thread) — never passed in from the sweep.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.db import repositories as repo
from app.db.connection import connect
from app.pipeline import status
from app.pipeline.preprocess import preprocess_stage

logger = logging.getLogger(__name__)


@dataclass
class StageContext:
    """Everything a pipeline stage needs, and a scratch dict to pass artifacts
    forward (e.g. preprocessed images 2.3 → OCR text 2.4 → LLM 2.5) without
    widening this signature as stages are added."""

    conn: Any  # sqlite3.Connection (opened per submission/thread)
    submission: repo.Submission
    label_images: list[repo.LabelImage]
    scratch: dict[str, Any] = field(default_factory=dict)


# A stage is a plain callable over the shared context (Story 2.2 seam contract).
# Real stages persist their own result rows (ocr_results/llm_results) and emit
# their own timeline markers; they must be resilient and side-effect via `conn`.
Stage = Callable[[StageContext], None]


def passthrough_stage(ctx: StageContext) -> None:
    """Story 2.2 placeholder for the OCR phase: records the ``OCR_STARTED`` and
    ``OCR_COMPLETED`` timeline markers and performs NO extraction.

    Stories 2.3–2.5 replace/extend this in :data:`STAGES`. It exists so the
    lifecycle (claim → markers → READY) ships green and is testable before any
    heavy native dependency (cv2/pytesseract/paddleocr/provider SDK) lands.
    """
    sid = ctx.submission.id
    status.record_event(ctx.conn, sid, event_type="OCR_STARTED")
    # No extraction in 2.2 — the seam is being proven, not the engines.
    status.record_event(ctx.conn, sid, event_type="OCR_COMPLETED")


# The single registration point for the ordered stage sequence (AC3). Swapping
# this list changes pipeline behavior with no edit to scheduler.py/status.py —
# the seam asserted by the tests. 2.3/2.4/2.5 append their stages here.
# Story 2.3 registers `preprocess_stage` at the FRONT (it runs before OCR and
# produces the enhanced/binarized variants the OCR stage will consume). Its wall-
# time is inside `process_submission`'s timed loop, so it already rolls into
# `processing_ms` (AC3) without any scheduler/status change (AC5).
STAGES: list[Stage] = [preprocess_stage, passthrough_stage]


def process_submission(db_path: str, submission_id: int) -> None:
    """Process one submission end-to-end on a background worker thread.

    Atomically claims the row, runs every stage in :data:`STAGES` (each wrapped
    so one stage's failure neither aborts the submission nor escapes the thread),
    records ``ANALYSIS_COMPLETED`` (annotated with any stage errors), rolls the
    elapsed time into ``processing_ms``, and advances to ``READY_FOR_REVIEW``.

    No-ops if another worker already claimed the row, or the row vanished. The
    whole body is also guarded so a catastrophic failure logs rather than killing
    the sweep thread.
    """
    try:
        with connect(db_path) as conn:
            if not status.claim_for_processing(conn, submission_id):
                # Another worker won the claim (or the row is no longer RECEIVED).
                return
            submission = repo.get_submission(conn, submission_id)
            if submission is None:
                return
            ctx = StageContext(
                conn=conn,
                submission=submission,
                label_images=repo.list_label_images(conn, submission_id),
            )

            errors: list[str] = []
            started = time.monotonic()
            for stage in STAGES:
                name = getattr(stage, "__name__", repr(stage))
                try:
                    stage(ctx)
                except Exception as exc:  # noqa: BLE001 — finalize, never abort (FR-9)
                    logger.exception(
                        "Pipeline stage %s failed for submission %s", name, submission_id
                    )
                    errors.append(f"stage={name} failed: {exc!r}")
            elapsed_ms = int((time.monotonic() - started) * 1000)

            # Honest failure surfacing: stage errors ride on the ANALYSIS_COMPLETED
            # note (no FAILED enum invented). None when the run was clean.
            status.record_event(
                conn,
                submission_id,
                event_type="ANALYSIS_COMPLETED",
                note="; ".join(errors) or None,
            )
            status.set_processing_ms(conn, submission_id, elapsed_ms)
            # Finalize: always reach READY_FOR_REVIEW — never stuck in PROCESSING.
            status.advance(
                conn,
                submission_id,
                to_status="READY_FOR_REVIEW",
                event_type="READY",
            )
    except Exception:  # noqa: BLE001 — a single submission must never kill the sweep
        logger.exception("process_submission failed unexpectedly for submission %s", submission_id)
        # The claim commits RECEIVED→PROCESSING immediately, but an exception in
        # the finalize steps (DB busy past busy_timeout, a stage corrupting the
        # txn, a connect/commit error) would otherwise leave the row stuck in
        # PROCESSING forever — list_received_ids/claim only ever match RECEIVED,
        # and there is no reaper. Extend the finalize-don't-stall posture to the
        # infra-failure path: best-effort finalize on a FRESH connection.
        _finalize_stuck_after_failure(db_path, submission_id)


def _finalize_stuck_after_failure(db_path: str, submission_id: int) -> None:
    """Best-effort rescue of a submission left mid-flight by a worker failure.

    Opens a FRESH connection (the failed one may be unusable) and, only if the row
    is still ``PROCESSING`` (i.e. it was claimed but never finalized), advances it
    to ``READY_FOR_REVIEW`` with an honest error note — so it is never stuck. A row
    still ``RECEIVED`` (claim never landed) is left for the next sweep; one already
    finalized needs nothing. Itself fully guarded: if the rescue also fails, it
    only logs (the row stays ``PROCESSING``) and never raises into the sweep thread.
    """
    try:
        with connect(db_path) as conn:
            if repo.get_status(conn, submission_id) != "PROCESSING":
                return  # never claimed, or already finalized — nothing to rescue
            status.advance(
                conn,
                submission_id,
                to_status="READY_FOR_REVIEW",
                event_type="READY",
                note="finalized after worker failure",
            )
            logger.warning(
                "Rescued submission %s stuck in PROCESSING; finalized to READY_FOR_REVIEW",
                submission_id,
            )
    except Exception:  # noqa: BLE001 — rescue is best-effort; never escalate
        logger.exception("Failed to rescue submission %s; left in PROCESSING", submission_id)
