"""Review Workspace shell route (Story 4.3).

``GET /review/{id}`` → the Review Workspace **shell**: the beverage-type banner, the
progress chevron, and the suggested-verdict alert, rendered from pre-computed data.

This is a **pure pre-computed DB read** (AR-5, the 5-second read contract): it reads
the already-computed ``submissions`` row + its ``checklist_items`` and renders. It
performs NO OCR, inference, model import, check-engine run, or pipeline-execution call,
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

    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "submission": submission,
            "banner": review_view.banner(submission.beverage_type),
            "chevron": review_view.chevron(items),
            "alert": review_view.suggested_verdict(items),
        },
    )
