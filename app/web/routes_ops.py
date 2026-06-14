"""Demo-operations routes (Story 6.1 ``POST /reset``; Story 6.2 ``POST /enqueue``).

The operator endpoints that drive the demo:

- ``POST /reset`` re-arms the demo: it triggers the :func:`app.web.ops.reset`
  orchestrator (transactional DB re-seed + derived-images purge).
- ``POST /enqueue`` inserts ONE fresh fixture as a ``RECEIVED`` row (via
  :func:`app.db.seed.enqueue_fixture`) so the evaluator can watch the Pre-compute
  Pipeline carry it ``RECEIVED → PROCESSING → READY_FOR_REVIEW`` end to end (FR-28).

Both redirect back to the Queue so the evaluator lands on the queue — consistent
with the existing POST-action redirect pattern (``POST /next``, the disposition POST).

This is an explicit operator POST action, not a render path: the bulk DB writes
happen via the sanctioned ``seed()`` transaction, so the 5-second read contract
(AR-5) is intact (no OCR / image processing / inference / model-layer call on any
request path). The route carries **no exemption**, so the Story 1.5 token-gate
middleware in ``app/main.py`` protects ``/reset`` like every screen — an
unauthenticated ``POST /reset`` is bounced to ``/access`` and never re-seeds.

The response is a bare ``303 → /queue``: no submission rows, image bytes, or
benchmark figures leak in the payload (AC-4). The already-shipped
demo-reset-while-open handling (Story 4.11 AC4) continues to hold — a reset fired
while a review screen is open routes that stale screen calmly to ``/queue?gone=1``,
never a crash.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.db.seed import enqueue_fixture
from app.web.ops import reset

router = APIRouter()


@router.post("/reset")
def reset_demo(request: Request) -> RedirectResponse:
    """Re-seed the corpus + purge derived images, then redirect to the Queue.

    No request body or query params are consumed; the response carries only the
    redirect (no submission / image / benchmark data — no leakage, AC-4).
    """
    reset(request.app.state.settings)
    return RedirectResponse("/queue", status_code=303)


@router.post("/enqueue")
def enqueue_demo(request: Request) -> RedirectResponse:
    """Insert ONE fresh fixture as a ``RECEIVED`` row, then redirect to the Queue.

    Inserts a single new pending submission (fresh unique ``ttb_id``) via the
    sanctioned :func:`app.db.seed.enqueue_fixture` transaction; the existing
    background sweep (Story 2.2) carries it ``RECEIVED → PROCESSING →
    READY_FOR_REVIEW`` — the web layer never runs the pipeline synchronously
    (AR-5 / pipeline-is-the-only-writer). No request body or query params are
    consumed; the response carries only the redirect (no submission / image /
    benchmark data — no leakage, AC-4).
    """
    enqueue_fixture(request.app.state.settings.database_path)
    return RedirectResponse("/queue", status_code=303)
