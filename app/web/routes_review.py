"""Review Workspace route (Stories 4.3, 4.4, 4.5, 4.6).

``GET /review/{id}`` → the Review Workspace: the beverage-type banner, the progress
chevron, the suggested-verdict alert (4.3), the stacked field comparison cards (4.4),
the Government Warning card (4.5), and the smart checklist (4.6) — all rendered from
pre-computed data.

This is a **pure pre-computed DB read** (AR-5, the 5-second read contract): it reads
the already-computed ``submissions`` row, its ``checklist_items``, its
``v_field_comparisons`` rows, and the single ``review_progress`` row (the cheap
human-tick layer, Story 4.6), and renders. It performs NO OCR, inference, model
import, char-diff aside, check-engine run, or pipeline-execution call,
and NO status write — the ``READY_FOR_REVIEW → IN_REVIEW`` + ``OPENED`` audit write
already happened in ``POST /next`` (Story 4.1). The GET is idempotent + side-effect-free.

``POST /review/{id}/progress`` (Story 4.6) is the ONE permitted cheap web-layer write:
it upserts the submission's ``review_progress.ticked_check_keys`` (a manual "I looked
at this" acknowledgement — NEVER a disposition, never the engine verdict; contract #4).
It runs no OCR/inference/engine — just a single-row upsert (AR-5 intact). Returns
``204 No Content``; the client recomputes the counter optimistically.

A missing id is handled calmly with a 404 (``HTTPException``), never a 500. The routes
carry no exemption, so the ``app/main.py`` token-gate middleware protects them like
every other screen (Story 1.5).

The advisory roll-up is computed via the centralized ``app/verdict.py:rollup`` (through
``app.web.review_view``) — the SAME roll-up the engine used to set
``submissions.engine_verdict`` — so the Suggested alert can never disagree with the
engine (contract #3). Everything rendered here is the engine register (PASS/REVIEW/
FAIL), advisory only; this route emits no disposition.
"""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from app.db import repositories as repo
from app.db.connection import connect
from app.web import review_view

router = APIRouter()


@router.get("/review/{submission_id}", response_class=HTMLResponse)
def review(request: Request, submission_id: int) -> HTMLResponse:
    """Render the Review Workspace shell for one submission (pure read, AR-5).

    Reads the submission + its checklist + its single ``review_progress`` row, builds
    the banner / chevron / suggested-verdict / field-card / gov-warning / smart-checklist
    view-models, and renders ``review.html``. A missing id ⇒ calm 404.
    """
    settings = request.app.state.settings
    templates = request.app.state.templates
    with connect(settings.database_path) as conn:
        submission = repo.get_submission(conn, submission_id)
        if submission is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        items = repo.list_checklist_items(conn, submission_id)
        comparisons = repo.list_field_comparisons(conn, submission_id)
        # The human-tick layer (Story 4.6): the MANUAL ticked set. The presenter
        # unions in the auto-tick set (PASS/NA) itself, keeping the merge in one place.
        ticked_keys = repo.get_ticked_check_keys(conn, submission_id)

    cards = review_view.field_cards(items, comparisons)
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "submission": submission,
            "banner": review_view.banner(submission.beverage_type),
            "chevron": review_view.chevron(items),
            "alert": review_view.suggested_verdict(items),
            "field_cards_problems": [c for c in cards if c["is_problem"]],
            "field_cards_clean": [c for c in cards if not c["is_problem"]],
            # The Government Warning card (Story 4.5) — built from the SAME ``items``
            # already read (no new query); ``None`` when the submission has no
            # government_warning row (the template renders the honest empty state).
            "gov_warning": review_view.government_warning_card(items),
            # The smart checklist (Story 4.6) — the per-type table-of-contents over the
            # SAME ``items``. ``ticked_keys`` is the manual set; the presenter unions in
            # the auto set so done-count = len(auto ∪ manual).
            "checklist": review_view.smart_checklist(
                items, beverage_type=submission.beverage_type, ticked_keys=ticked_keys
            ),
        },
    )


@router.post("/review/{submission_id}/progress")
def set_progress(
    request: Request,
    submission_id: int,
    check_key: str = Form(...),
    ticked: bool = Form(...),
) -> Response:
    """Persist one manual checklist tick/untick (Story 4.6, AC5).

    The ONE permitted cheap web-layer write: upsert the submission's single
    ``review_progress`` row, adding/removing ``check_key`` from ``ticked_check_keys``.
    Idempotent (re-ticking is a no-op; untick removes). A manual tick is an
    acknowledgement — NEVER a disposition and never the engine verdict (contract #4).

    No OCR / inference / engine run (AR-5): just a single-row upsert. A missing
    submission ⇒ calm 404. Returns ``204 No Content`` — the client recomputes the
    "N of M done" counter optimistically.
    """
    settings = request.app.state.settings
    with connect(settings.database_path) as conn:
        submission = repo.get_submission(conn, submission_id)
        if submission is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        repo.set_check_tick(conn, submission_id, check_key=check_key, ticked=ticked)
    return Response(status_code=204)
