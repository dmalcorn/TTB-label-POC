"""Review Workspace route (Stories 4.3, 4.4).

``GET /review/{id}`` → the Review Workspace: the beverage-type banner, the progress
chevron, the suggested-verdict alert (4.3), and the stacked field comparison cards
(4.4), all rendered from pre-computed data.

This is a **pure pre-computed DB read** (AR-5, the 5-second read contract): it reads
the already-computed ``submissions`` row, its ``checklist_items`` and its
``v_field_comparisons`` rows, and renders. It performs NO OCR, inference, model
import, char-diff aside, check-engine run, or pipeline-execution call,
and NO status write — the ``READY_FOR_REVIEW → IN_REVIEW`` + ``OPENED`` audit write
already happened in ``POST /next`` (Story 4.1). The GET is idempotent + side-effect-free.

A missing id is handled calmly with a 404 (``HTTPException``), never a 500. The route
carries no exemption, so the ``app/main.py`` token-gate middleware protects it like
every other screen (Story 1.5).

The advisory roll-up is computed via the centralized ``app/verdict.py:rollup`` (through
``app.web.review_view``) — the SAME roll-up the engine used to set
``submissions.engine_verdict`` — so the Suggested alert can never disagree with the
engine (contract #3). Everything rendered here is the engine register (PASS/REVIEW/
FAIL), advisory only; this route emits no disposition.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.db import repositories as repo
from app.db.connection import connect
from app.web import review_view

router = APIRouter()


@router.get("/review/{submission_id}", response_class=HTMLResponse)
def review(request: Request, submission_id: int) -> HTMLResponse:
    """Render the Review Workspace shell for one submission (pure read, AR-5).

    Reads the submission + its checklist, builds the banner / chevron / suggested-
    verdict view-models, and renders ``review.html``. A missing id ⇒ calm 404.
    """
    settings = request.app.state.settings
    templates = request.app.state.templates
    with connect(settings.database_path) as conn:
        submission = repo.get_submission(conn, submission_id)
        if submission is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        items = repo.list_checklist_items(conn, submission_id)
        comparisons = repo.list_field_comparisons(conn, submission_id)

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
        },
    )
