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

import mimetypes
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app import disposition as dispo
from app.db import repositories as repo
from app.db.connection import connect
from app.pipeline import status as lifecycle
from app.web import review_view

router = APIRouter()

# The disposition + undo writes are the human specialist's, recorded under the same
# actor the queue uses for OPENED (Story 4.1) — the audit timeline reads as one person.
SPECIALIST_ACTOR = "Label Specialist"

# The read-only seeded source root for ORIGINAL images. Mirrors
# ``app/pipeline/preprocess.py:SOURCE_IMAGES_DIR`` = ``<repo>/fixtures/images``;
# duplicated as a constant here (not imported) so this read route never reaches into
# the pipeline layer (AR-5 read-path purity).
_SOURCE_IMAGES_DIR: Path = Path(__file__).resolve().parents[2] / "fixtures" / "images"

# The constrained ``variant`` query values → the LabelImage attribute holding the
# stored (relative) path. ``original`` is special-cased (it lives under the seeded
# source root by ``filename``, not under the generated-images root).
_VARIANT_ATTR: dict[str, str] = {
    "enhanced": "enhanced_path",
    "binarized": "binarized_path",
}


def _media_type_for(row: repo.LabelImage, variant: str) -> str:
    """Pick the Content-Type for the streamed file.

    The ``original`` carries the row's own ``mime_type`` (the seeded source's true type).
    The derived ``enhanced`` / ``binarized`` variants are OpenCV PNG outputs and do NOT
    inherit the original's mime — so sniff their type from the variant file's suffix
    (a JPEG original must not stream its PNG enhanced variant as ``image/jpeg``). Falls
    back to ``image/jpeg`` only when nothing better is known.
    """
    if variant == "original":
        return row.mime_type or "image/jpeg"
    rel = getattr(row, _VARIANT_ATTR[variant], None)
    guessed, _ = mimetypes.guess_type(rel) if rel else (None, None)
    return guessed or "image/png"


@router.get("/review/{submission_id}", response_class=HTMLResponse)
def review(request: Request, submission_id: int, image: int | None = None) -> HTMLResponse:
    """Render the Review Workspace shell for one submission (pure read, AR-5).

    Reads the submission + its checklist + its single ``review_progress`` row, builds
    the banner / chevron / suggested-verdict / field-card / gov-warning / smart-checklist
    view-models + the label-image panel (Story 4.7), and renders ``review.html``. The
    optional ``image`` query param selects which face (by ``position``) the panel shows
    so paging works without JS (AC3). A missing id ⇒ calm 404.
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
        # The label-image set (Story 4.7), in position order; ``[]`` ⇒ calm empty state.
        images = repo.list_label_images(conn, submission_id)
        # The autosaved draft Notes (Story 4.8), rehydrated into the textarea so a
        # mid-review reload keeps the typed reason. ``None`` ⇒ empty textarea.
        draft_notes = repo.get_draft_notes(conn, submission_id)

    cards = review_view.field_cards(items, comparisons)
    # The smart checklist drives the confirm-modal copy: a still-open REVIEW/FAIL row
    # means "you're committing with items still flagged" — the action bar passes that
    # through (the engine never blocks; it just makes the choice honest).
    checklist = review_view.smart_checklist(
        items, beverage_type=submission.beverage_type, ticked_keys=ticked_keys
    )
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "submission": submission,
            "banner": review_view.banner(submission.beverage_type),
            "chevron": review_view.chevron(items),
            "alert": review_view.suggested_verdict(items),
            # The label-image panel (Story 4.7) — the left column. Pure read-model over
            # the already-read ``images``; the selected face follows ``?image=<pos>``.
            "image_panel": review_view.image_panel(
                images, submission_id=submission_id, current_position=image
            ),
            "field_cards_problems": [c for c in cards if c["is_problem"]],
            "field_cards_clean": [c for c in cards if not c["is_problem"]],
            # The Government Warning card (Story 4.5) — built from the SAME ``items``
            # already read (no new query); ``None`` when the submission has no
            # government_warning row (the template renders the honest empty state).
            "gov_warning": review_view.government_warning_card(items),
            # The smart checklist (Story 4.6) — the per-type table-of-contents over the
            # SAME ``items``. ``ticked_keys`` is the manual set; the presenter unions in
            # the auto set so done-count = len(auto ∪ manual).
            "checklist": checklist,
            # The commit action bar (Story 4.8): three disposition controls (none
            # pre-selected), the rehydrated draft Notes, and whether any checklist row
            # is still open (drives the confirm-modal copy — never blocks the commit).
            "action_bar": review_view.action_bar(
                draft_notes=draft_notes,
                has_open_review=review_view.checklist_has_open(checklist),
            ),
        },
    )


@router.post("/review/{submission_id}/progress")
def set_progress(
    request: Request,
    submission_id: int,
    check_key: str | None = Form(default=None),
    ticked: bool | None = Form(default=None),
    draft_notes: str | None = Form(default=None),
) -> Response:
    """Persist a cheap web-layer review-progress beacon (Stories 4.6 tick + 4.8 notes).

    The ONE permitted cheap web-layer write: upsert the submission's single
    ``review_progress`` row. Two independent payloads share this beacon:

    - **tick** (4.6): ``check_key`` + ``ticked`` add/remove a key from
      ``ticked_check_keys`` (idempotent; a manual acknowledgement — NEVER a disposition
      or the engine verdict, contract #4);
    - **draft_notes** (4.8): the autosaved reason text, rehydrated on the next GET.

    Both are optional so a single beacon carries either (the JS posts whichever
    changed). An empty beacon (neither field) is a calm ``204`` no-op — never a 422.
    No OCR / inference / engine run (AR-5): just single-row upserts. A missing
    submission ⇒ calm 404. Returns ``204 No Content``; the client recomputes the
    "N of M done" counter optimistically.
    """
    settings = request.app.state.settings
    with connect(settings.database_path) as conn:
        submission = repo.get_submission(conn, submission_id)
        if submission is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        if check_key is not None and ticked is not None:
            repo.set_check_tick(conn, submission_id, check_key=check_key, ticked=ticked)
        if draft_notes is not None:
            repo.set_draft_notes(conn, submission_id, draft_notes=draft_notes)
    return Response(status_code=204)


@router.post("/review/{submission_id}/disposition")
def record_disposition(
    request: Request,
    submission_id: int,
    disposition: str = Form(...),
    notes: str = Form(default=""),
) -> Response:
    """Commit the human disposition for one submission (Story 4.8, FR-6 / AC2/AC3).

    The official decision the specialist records — the engine NEVER makes it
    (contract #4 / AR-3 #4). Validates the disposition is one of the three enum
    values (else calm 400) and enforces the server-side soft-gate: NEEDS_CORRECTION /
    REJECTED require a non-blank reason (else 400 — the row stays untouched, never
    half-decided).

    Writes are ordered so the schema cross-column CHECK holds the moment status flips:
    ``repo.record_disposition`` (no commit) sets the decision columns, THEN
    ``status.advance(... DECIDED ...)`` commits the status + the ``DECIDED`` audit row.
    A second disposition (already DECIDED) ⇒ ``status.advance`` raises ValueError ⇒
    calm 409 (the first decision stands, never overwritten). A missing submission ⇒
    404. On success: ``303 → /queue?recorded={id}`` (PRG; the queue shows the
    Recorded — Undo banner).
    """
    if not dispo.is_valid(disposition):
        raise HTTPException(status_code=400, detail="Unknown disposition")
    decision_notes = notes.strip()
    if dispo.requires_notes(disposition) and not decision_notes:
        raise HTTPException(
            status_code=400,
            detail="A reason is required for Needs Correction / Reject",
        )

    settings = request.app.state.settings
    with connect(settings.database_path) as conn:
        submission = repo.get_submission(conn, submission_id)
        if submission is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        # The decision columns + the DECIDED status flip happen in ONE statement
        # (the cross-column CHECK is symmetric + per-statement) — owned by
        # status.record_decision, which guards the transition + writes the audit row.
        try:
            lifecycle.record_decision(
                conn,
                submission_id,
                disposition=disposition,
                decided_at=datetime.now(UTC).isoformat(),
                actor=SPECIALIST_ACTOR,
                note=decision_notes or None,
            )
        except ValueError as exc:
            # Already DECIDED (or any non-forward state) ⇒ calm 409. The connection
            # never committed, so the first decision stands.
            raise HTTPException(status_code=409, detail="Already decided") from exc
    return RedirectResponse(url=f"/queue?recorded={submission_id}", status_code=303)


@router.post("/review/{submission_id}/undo")
def undo_disposition(request: Request, submission_id: int) -> Response:
    """Undo a just-recorded decision (Story 4.8 AC4 — the single bounded backward step).

    The lone ``DECIDED → READY_FOR_REVIEW`` transition (Addendum A). Clears the four
    human-decision columns (no commit), THEN ``status.reopen`` flips status back +
    writes the ``UNDONE`` audit row (commits) — ordered so the cross-column CHECK
    (``status<>'DECIDED' ⇒ disposition IS NULL``) holds per-statement. The
    ``review_progress`` row (ticks + draft notes) is RETAINED so the specialist
    resumes where they were. Undo on a non-DECIDED row ⇒ calm 409; missing ⇒ 404.
    On success: ``303 → /review/{id}`` (back to the workspace).
    """
    settings = request.app.state.settings
    with connect(settings.database_path) as conn:
        submission = repo.get_submission(conn, submission_id)
        if submission is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        # status.reopen NULLs the decision columns + flips status back in ONE
        # statement (cross-column CHECK is symmetric + per-statement) and audits UNDONE.
        try:
            lifecycle.reopen(conn, submission_id, actor=SPECIALIST_ACTOR)
        except ValueError as exc:
            # Not a DECIDED row ⇒ calm 409 (the connection never committed).
            raise HTTPException(status_code=409, detail="Nothing to undo") from exc
    return RedirectResponse(url=f"/review/{submission_id}", status_code=303)


@router.get("/review/{submission_id}/image/{image_id}")
def review_image(
    request: Request, submission_id: int, image_id: int, variant: str = "original"
) -> FileResponse:
    """Stream one label image from disk (Story 4.7 AC2 — same-origin, AR-5-pure).

    A pure single-row DB read + a file stream: read the ``label_images`` row by
    ``image_id``, verify its ``submission_id`` matches the path (no cross-submission
    enumeration), resolve the on-disk path ENTIRELY from the row (never a client path —
    no traversal), and ``FileResponse`` it with the row's ``mime_type``.

    The only client inputs are the integer ``image_id`` and the constrained ``variant``
    (``original`` default / ``enhanced`` / ``binarized``; anything else ⇒ 404).
    ``original`` resolves under the read-only seeded source root by ``filename``;
    ``enhanced`` / ``binarized`` resolve under ``settings.generated_images_dir`` by the
    stored relative path. A missing row, a foreign row, a NULL variant path, or a file
    absent on disk ⇒ calm 404 (never a 500, never a directory listing). No OCR / LLM /
    engine / pipeline import (AR-5).
    """
    settings = request.app.state.settings
    with connect(settings.database_path) as conn:
        row = repo.get_label_image(conn, image_id)
    if row is None or row.submission_id != submission_id:
        raise HTTPException(status_code=404, detail="Image not found")

    if variant == "original":
        root = _SOURCE_IMAGES_DIR
        file_path = root / row.filename
    elif variant in _VARIANT_ATTR:
        rel = getattr(row, _VARIANT_ATTR[variant])
        if not rel:  # NULL variant path ⇒ clean image had no such variant (AC4/AC5)
            raise HTTPException(status_code=404, detail="Image variant not available")
        root = Path(settings.generated_images_dir)
        file_path = root / rel
    else:  # an unrecognized variant is treated as not-found (no 500, no guessing)
        raise HTTPException(status_code=404, detail="Unknown image variant")

    # ENFORCE — not merely assume — the advertised "no traversal" guarantee. The path is
    # built from DB columns the pipeline writes as basenames today, but the route promises
    # a security property, so make it real: resolve symlinks / ``..`` and require the
    # result to stay under its root. A stored ``..`` / absolute path (or an out-of-root
    # symlink) ⇒ calm 404, never an arbitrary-file read. (project-context.md: prefer the
    # more restrictive option around the firewall boundary.)
    resolved = file_path.resolve()
    root_resolved = root.resolve()
    if root_resolved != resolved and root_resolved not in resolved.parents:
        raise HTTPException(status_code=404, detail="Image not found")

    if not resolved.is_file():  # absent on disk ⇒ calm 404 (AC5)
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(resolved, media_type=_media_type_for(row, variant))
