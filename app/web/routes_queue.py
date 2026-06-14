"""Queue screen & Next Submission routes (Story 4.1).

``GET /queue``  → the single-action queue screen (State 1 waiting / State 2 empty).
``POST /next``  → serves the OLDEST ``READY_FOR_REVIEW`` submission and redirects to
                  its review screen (`/review/{id}`, built in Story 4.3); on an empty
                  queue it re-renders the calm State-2 screen — never an error.

Both honor the 5-second read contract (AR-5): the render paths do pre-computed DB
reads ONLY — no OCR, image processing, inference, or model-layer call at request
time. ``POST /next`` performs the ONE permitted cheap bookkeeping write on the
explicit POST action — the ``READY_FOR_REVIEW → IN_REVIEW`` lifecycle transition
plus an ``OPENED`` audit row (project-context Addendum A) — via
``app.pipeline.status.advance``; it never re-implements the transition or runs heavy
work. These routes carry no exemption, so the ``app/main.py`` token-gate middleware
protects them like every other screen (Story 1.5).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db import repositories as repo
from app.db.connection import connect
from app.pipeline import status

router = APIRouter()

# No per-user identity in the POC; the human actor on the audit timeline is the
# shared specialist role (architecture.md §264 — `actor` = `Label Specialist`).
SPECIALIST_ACTOR = "Label Specialist"


def _render_queue(request: Request, *, waiting: int, status_code: int = 200) -> HTMLResponse:
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request, "queue.html", {"waiting": waiting}, status_code=status_code
    )


@router.get("/queue", response_class=HTMLResponse)
def queue(request: Request) -> Response:
    """Render the queue screen with the live "N waiting" count (read-only)."""
    settings = request.app.state.settings
    with connect(settings.database_path) as conn:
        waiting = repo.count_ready_for_review(conn)
    return _render_queue(request, waiting=waiting)


@router.post("/next")
def next_submission(request: Request) -> Response:
    """Serve the oldest ready submission, or re-render the empty queue calmly.

    Deterministic oldest-first; unready submissions are skipped silently. On a hit
    we record the permitted ``READY_FOR_REVIEW → IN_REVIEW`` transition + ``OPENED``
    audit row, then redirect to the review screen. On an empty queue we re-render
    State 2 (200, not a redirect, not an error).

    The select-then-advance is a check-then-act, so a second specialist clicking
    Next at the same instant could read the same oldest id before either advances
    it. ``status.advance`` is the claim: it rejects the now non-forward
    ``IN_REVIEW → IN_REVIEW`` transition (the row the loser read was already taken)
    with a ``ValueError``. We treat that as "someone else took it" and calmly try
    the NEXT oldest ready row instead of surfacing a 500 — the queue keeps moving.
    """
    settings = request.app.state.settings
    with connect(settings.database_path) as conn:
        while True:
            sid = repo.get_oldest_ready_submission_id(conn)
            if sid is None:
                return _render_queue(request, waiting=0)
            try:
                status.advance(
                    conn,
                    sid,
                    to_status="IN_REVIEW",
                    event_type="OPENED",
                    actor=SPECIALIST_ACTOR,
                )
            except ValueError:
                # Lost the race for `sid` (already advanced past READY_FOR_REVIEW,
                # or removed) — re-select and serve the next ready item.
                continue
            break
    return RedirectResponse(f"/review/{sid}", status_code=303)
