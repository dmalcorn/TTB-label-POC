"""Queue screen & Next Submission routes (Stories 4.1 + 4.2).

``GET /queue``  → the single-action queue screen (State 1 waiting / State 2 empty).
``POST /next``  → serves the OLDEST ``READY_FOR_REVIEW`` submission and redirects to
                  its review screen (`/review/{id}`, built in Story 4.3); on an empty
                  queue it re-renders the calm State-2 screen — never an error.

Story 4.2 makes the beverage-type segmented filter (Any · Wine · Spirits · Beer)
live: an optional ``type`` request value (query or form field) scopes the count and
the serve to one ``beverage_type``. The UI **labels** map to the stored **enums**
here at the presentation boundary (``Wine→WINE``, ``Spirits→DISTILLED_SPIRITS``,
``Beer→MALT_BEVERAGE``, ``Any→`` no filter) — the repo/SQL speaks enums only. An
empty *typed* queue renders the per-type empty-note ("The wine queue is empty…") at
200 with the filter staying set; an unrecognized ``type`` degrades to Any (never a
4xx). The selection is sticky across the GET ↔ POST round-trip.

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

from fastapi import APIRouter, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db import repositories as repo
from app.db.connection import connect
from app.pipeline import status

router = APIRouter()

# No per-user identity in the POC; the human actor on the audit timeline is the
# shared specialist role (architecture.md §264 — `actor` = `Label Specialist`).
SPECIALIST_ACTOR = "Label Specialist"

# The presentation boundary between the mockup's filter LABELS and the stored
# `beverage_type` enums (the schema CHECK / `repo.BeverageType`). UI labels never
# leak into the repo/SQL (which speak enums), and the enum literals never leak into
# the template (which speaks labels). `Any` is the ABSENCE of a key (no filter).
# Note the non-obvious pairs: "Spirits" → DISTILLED_SPIRITS, "Beer" → MALT_BEVERAGE.
FILTER_LABEL_TO_TYPE: dict[str, str] = {
    "wine": "WINE",
    "spirits": "DISTILLED_SPIRITS",
    "beer": "MALT_BEVERAGE",
}
# The inverse (enum → display label) drives the sticky `aria-pressed` segment and the
# per-type empty-note word on re-render.
TYPE_TO_FILTER_LABEL: dict[str, str] = {
    enum: label.capitalize() for label, enum in FILTER_LABEL_TO_TYPE.items()
}


def resolve_beverage_type(raw: str | None) -> str | None:
    """Map a filter request value (a UI label) to a stored ``beverage_type`` enum.

    Returns the enum for ``wine``/``spirits``/``beer`` (any case, trimmed), or
    ``None`` for ``any``/blank/``None``/**any unrecognized value** — the calm
    degrade-to-Any contract (AC3): never raise, never a 4xx. Pure (no DB, no
    request) so it is unit-testable in isolation.
    """
    if raw is None:
        return None
    return FILTER_LABEL_TO_TYPE.get(raw.strip().lower())


def _render_queue(
    request: Request,
    *,
    waiting: int,
    active_type: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Render ``queue.html`` with the (type-scoped) waiting count + the active filter.

    ``active_type`` is the resolved ``beverage_type`` enum (or ``None`` for Any); we
    also pass the display label so the template can mark exactly one segment pressed
    and name the type in the per-type empty-note.
    """
    templates = request.app.state.templates
    active_label = TYPE_TO_FILTER_LABEL.get(active_type) if active_type is not None else None
    return templates.TemplateResponse(
        request,
        "queue.html",
        {"waiting": waiting, "active_type": active_type, "active_label": active_label},
        status_code=status_code,
    )


@router.get("/queue", response_class=HTMLResponse)
def queue(request: Request, type: str | None = Query(default=None)) -> Response:
    """Render the queue screen with the live "N waiting" count (read-only).

    With ``?type=`` set the count is scoped to that beverage type and the matching
    segment renders pressed (sticky). Pure DB read — AR-5.
    """
    settings = request.app.state.settings
    resolved = resolve_beverage_type(type)
    with connect(settings.database_path) as conn:
        waiting = repo.count_ready_for_review(conn, beverage_type=resolved)
    return _render_queue(request, waiting=waiting, active_type=resolved)


@router.post("/next")
def next_submission(
    request: Request,
    type: str | None = Form(default=None),
    type_q: str | None = Query(default=None, alias="type"),
) -> Response:
    """Serve the oldest ready submission of the selected type, or re-render calmly.

    The selected ``type`` arrives as a form field (the segmented submit) or a query
    param; either is accepted and resolved once to a ``beverage_type`` enum (Any /
    unrecognized ⇒ no filter). Deterministic oldest-first within the type; unready
    submissions are skipped silently. On a hit we record the permitted
    ``READY_FOR_REVIEW → IN_REVIEW`` transition + ``OPENED`` audit row, then redirect
    to the review screen. On an empty (type-scoped) queue we re-render State 2 (200,
    not a redirect, not an error) with the filter still set + the per-type note.

    The select-then-advance is a check-then-act, so a second specialist clicking
    Next at the same instant could read the same oldest id before either advances
    it. ``status.advance`` is the claim: it rejects the now non-forward
    ``IN_REVIEW → IN_REVIEW`` transition (the row the loser read was already taken)
    with a ``ValueError``. We treat that as "someone else took it" and calmly
    re-select the NEXT oldest ready row **within the same type filter** instead of
    surfacing a 500 — the queue keeps moving.
    """
    settings = request.app.state.settings
    resolved = resolve_beverage_type(type if type is not None else type_q)
    with connect(settings.database_path) as conn:
        while True:
            sid = repo.get_oldest_ready_submission_id(conn, beverage_type=resolved)
            if sid is None:
                return _render_queue(request, waiting=0, active_type=resolved)
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
                # or removed) — re-select and serve the next ready item of this type.
                continue
            break
    return RedirectResponse(f"/review/{sid}", status_code=303)
