"""Lifecycle transitions, audit timeline, and timing roll-up for the background
pipeline (Story 2.2).

This is the orchestration layer over the raw-SQL primitives in
``app/db/repositories.py`` (the data boundary keeps SQL out of ``app/pipeline/``).
It owns three guarantees the pipeline depends on:

- **Atomic claim** — :func:`claim_for_processing` flips exactly one ``RECEIVED``
  row to ``PROCESSING`` so two overlapping sweeps never double-process (AR-2).
- **Forward-only transitions** — :func:`advance` rejects any non-forward status
  change. The one bounded backward step (``DECIDED → READY_FOR_REVIEW``) belongs
  to the web layer (Addendum A), never here.
- **Fixed audit vocabulary** — every ``audit_events.event_type`` written here is
  asserted against the locked vocabulary; no ``FAILED`` value is ever invented
  (failures are surfaced as honest notes — see ``app/pipeline/run.py``).

Each helper commits its own short transaction ("commit per stage") so PROCESSING
is durable and visible the instant it is claimed, and WAL readers never block on
a long write. The web read path runs none of this — it reads pre-computed rows.
"""

from __future__ import annotations

import sqlite3

from app.db import repositories as repo

# The pipeline writes lifecycle events as a system actor; human events (OPENED /
# DECIDED / UNDONE) are written by the web layer under the specialist's identity.
PIPELINE_ACTOR = "pipeline"

# Forward lifecycle order (database-schema.md §1.1 / project-context Status). A
# transition is "forward" iff the target sits strictly later in this tuple. The
# lone backward transition (DECIDED → READY_FOR_REVIEW via POST /review/{id}/undo)
# is the web layer's, not the pipeline's — so it is intentionally not modeled here.
FORWARD_STATUSES: tuple[str, ...] = (
    "RECEIVED",
    "PROCESSING",
    "READY_FOR_REVIEW",
    "IN_REVIEW",
    "DECIDED",
)

# The locked audit vocabulary (database-schema.md §1.7). Mirrors the DB CHECK;
# kept here so a bad event_type fails fast in Python with a clear message instead
# of surfacing as an opaque IntegrityError. Keep in lockstep with schema.sql.
AUDIT_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "SEEDED",
        "OCR_STARTED",
        "OCR_COMPLETED",
        "ANALYSIS_COMPLETED",
        "READY",
        "OPENED",
        "DECIDED",
        "UNDONE",
    }
)


def _assert_event_type(event_type: str) -> None:
    if event_type not in AUDIT_EVENT_TYPES:
        raise ValueError(
            f"unknown audit event_type {event_type!r}; must be one of {sorted(AUDIT_EVENT_TYPES)}"
        )


def claim_for_processing(conn: sqlite3.Connection, submission_id: int) -> bool:
    """Atomically claim a ``RECEIVED`` submission, flipping it to ``PROCESSING``.

    Returns ``True`` only for the worker that actually claimed the row; a losing
    worker gets ``False`` and must no-op. Commits immediately so the claim is
    durable and visible to other sweeps (the real concurrency guard, AR-2/D3).
    """
    claimed = repo.claim_for_processing(conn, submission_id)
    conn.commit()
    return claimed


def advance(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    to_status: str,
    event_type: str,
    actor: str = PIPELINE_ACTOR,
    note: str | None = None,
) -> None:
    """Move a submission forward one (or more) lifecycle steps AND record the
    matching ``audit_events`` row, in one committed transaction.

    Enforces forward-only order: ``to_status`` must sit strictly later than the
    current status. Rejects a non-forward transition, an unknown status, an
    out-of-vocabulary ``event_type``, or a missing submission — raising
    ``ValueError`` rather than writing a bad row.
    """
    _assert_event_type(event_type)
    if to_status not in FORWARD_STATUSES:
        raise ValueError(f"unknown status {to_status!r}")

    from_status = repo.get_status(conn, submission_id)
    if from_status is None:
        raise ValueError(f"submission {submission_id} not found")
    if FORWARD_STATUSES.index(to_status) <= FORWARD_STATUSES.index(from_status):
        raise ValueError(
            f"non-forward transition {from_status!r} → {to_status!r} rejected; "
            "the pipeline only advances forward"
        )

    repo.update_status(conn, submission_id, to_status)
    repo.insert_audit_event(
        conn,
        submission_id=submission_id,
        event_type=event_type,
        actor=actor,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )
    conn.commit()


def record_event(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    event_type: str,
    actor: str = PIPELINE_ACTOR,
    note: str | None = None,
) -> None:
    """Append a non-transition processing event to the timeline (``OCR_STARTED``,
    ``OCR_COMPLETED``, ``ANALYSIS_COMPLETED``).

    No ``status`` change — ``from_status``/``to_status`` stay ``NULL`` because the
    event marks a processing milestone, not a lifecycle move. ``event_type`` is
    vocabulary-checked. Commits its own short transaction.
    """
    _assert_event_type(event_type)
    repo.insert_audit_event(
        conn,
        submission_id=submission_id,
        event_type=event_type,
        actor=actor,
        note=note,
    )
    conn.commit()


def set_processing_ms(conn: sqlite3.Connection, submission_id: int, processing_ms: int) -> None:
    """Roll the total pre-compute time into ``submissions.processing_ms`` (ms,
    INTEGER, ``>= 0``). Raises ``ValueError`` on a negative value before the DB
    ``CHECK`` would, for a clearer failure. Commits its own short transaction.
    """
    if processing_ms < 0:
        raise ValueError(f"processing_ms must be >= 0, got {processing_ms}")
    repo.update_processing_ms(conn, submission_id, processing_ms)
    conn.commit()
