"""The VLM extraction pipeline stage — config-gated, OCR-only fallback (Story 2.5).

Registered into ``run.STAGES`` **after** the Story-2.4 ``ocr_stage`` and before the
Epic-3 analysis/rollup, behind the Story-2.2 seam — no scheduler/status change.

**VLM-only — the model reads the label IMAGE, never OCR text.** The model is handed
the primary label image plus an instruction and produces its **own** independent
extraction. It is deliberately given **no** help from the OCR engines — that keeps
the OCR-vs-model benchmark a true head-to-head (FR-12, FR-21/FR-22) and makes the
model a genuine fallback when OCR confidence is poor. The OCR text is the
deterministic compliance engine's input (Epic 3), and never feeds this stage.

The stage:

- resolves the active adapter via :func:`app.config.get_llm_adapter`. When it is
  ``None`` (``LLM_ENABLED=false``, no provider, or an absent key) the stage
  **skips entirely** — no adapter imported, no client constructed, no socket opened
  — and the submission still finalizes OCR-only (AC2, the zero-egress path);
- otherwise sends the primary label image to ``extract_fields`` and persists one
  ``llm_results`` row (``is_benchmark_only=0`` — the displayed extraction), bound to
  that image. Running additional models over every image for the benchmark matrix
  (``is_benchmark_only=1``) is Epic 5's; the write path already supports it, so that
  is a clean seam, not built here (AC4 / Task 4).

**Degrade path (AC3).** Adapters self-guard (they return an ``ERROR`` ``LlmResult``
rather than raise); the stage *also* guards the call, so even a raising adapter
yields an honest ``ERROR`` row — provider + timing + the error in ``result_text`` —
which is the **queryable signal** Epic 4's review screen reads to show its visible
"LLM unavailable — showing OCR-only" notice. The submission still reaches
``READY_FOR_REVIEW``; the read path never calls the model layer (the 5s contract).

This stage does **extraction only** — it never writes ``engine_verdict`` or any
check verdict (the determinism cap; the hybrid class/type check is Epic 3 Story 3.6).
"""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

from app.config import get_llm_adapter, get_settings
from app.contracts import LlmResult
from app.db import repositories as repo
from app.pipeline.preprocess import SOURCE_IMAGES_DIR

if TYPE_CHECKING:  # avoid a run.py ↔ llm.py import cycle (run imports this stage)
    from pathlib import Path

    from app.adapters.llm.base import ModelAdapter
    from app.db.repositories import LabelImage
    from app.pipeline.run import StageContext

logger = logging.getLogger(__name__)

EXTRACT_FIELDS_TASK = "extract_fields"

# The extraction instruction. The model reads the IMAGE and returns fields — there is
# no OCR text in this prompt (VLM-only). Per-field parsing/use of the result is Epic 3;
# 2.5 only produces and stores the raw extraction.
_PROMPT = (
    "You are extracting label fields from a US TTB alcohol-beverage label. "
    "Read the attached label image and return the fields you can see "
    "(brand name, fanciful name, class/type, alcohol content, net contents, "
    "name/address, appellation, varietal, vintage where present) as JSON. "
    "Use only what the image shows; do not invent values."
)


def _primary_image_path(image: LabelImage) -> Path:
    """The on-disk path of a label image's ORIGINAL file (the seeded fixtures root).

    The VLM reads the original image — no OCR text and no OpenCV-preprocessed variant
    (those are separate benchmark configurations); this is the pure VLM-only input."""
    return SOURCE_IMAGES_DIR / image.filename


def _run_adapter(adapter: ModelAdapter, image_path: Path) -> LlmResult:
    """Run the adapter over the label image, downgrading any escaping exception to an
    ``ERROR`` result.

    Adapters already self-guard, so this is defensive depth: it guarantees the stage
    has an honest ``LlmResult`` (with provider identity + timing) to persist as the
    degraded signal even if an adapter ever raised (AC3)."""
    from app.adapters.llm._common import utc_now_iso

    requested_at = utc_now_iso()
    try:
        return adapter.run(EXTRACT_FIELDS_TASK, _PROMPT, image_path=str(image_path))
    except Exception as exc:  # noqa: BLE001 — degrade to an ERROR row, never abort
        logger.error("LLM adapter raised in stage; degrading to OCR-only: %s", type(exc).__name__)
        return LlmResult(
            model_name=getattr(adapter, "model_name", None),
            model_id=getattr(adapter, "model_id", None),
            model_full_id=getattr(adapter, "model_full_id", None),
            provider=getattr(adapter, "provider", None),
            task=EXTRACT_FIELDS_TASK,
            result_text=f"{type(exc).__name__}: {exc}",
            requested_at=requested_at,
            responded_at=utc_now_iso(),
            status="ERROR",
        )


def llm_stage(ctx: StageContext) -> None:
    """Story 2.5 pipeline stage: config-gated VLM extraction with OCR-only fallback.

    Skips entirely (no construction, no socket) when the model layer is off or there
    is no image to read; else sends the primary label image to the model and persists
    one ``llm_results`` row — ``OK`` with stats, or ``ERROR`` as the degraded-condition
    signal. Commits once at the end (commit-per-stage)."""
    adapter = get_llm_adapter(get_settings())
    if adapter is None:
        # Model layer off — OCR-only path. No adapter, no client, no egress (AC2).
        return

    sid = ctx.submission.id
    # The displayed extraction reads the primary (display-order first) image, and the
    # row is bound to it. The Epic-5 benchmark runs every model over every image.
    primary = ctx.label_images[0] if ctx.label_images else None
    if primary is None or not (primary.filename or "").strip():
        # VLM-only extraction has nothing to read without a real image path — skip
        # cleanly (the submission still finalizes OCR-only) rather than constructing a
        # client and calling the provider with a doomed (directory/blank) path.
        logger.warning("Submission %s has no readable label image; skipping VLM extraction", sid)
        return

    result = _run_adapter(adapter, _primary_image_path(primary))

    try:
        repo.insert_llm_result(
            ctx.conn,
            submission_id=sid,
            result=result,
            label_image_id=primary.id,
            is_benchmark_only=False,  # the displayed extraction (Task 4 seam for Epic 5)
        )
        ctx.conn.commit()
    except sqlite3.Error:
        # A row-level persist failure must not abort the submission (it still
        # finalizes via run.py). Record honestly in the log; the row is lost, not
        # the run.
        logger.exception("Persisting the llm_results row for submission %s failed", sid)
        return

    if result.status == "OK":
        # Stash the structured extraction for the Epic-3 analysis job (forward seam).
        ctx.scratch["llm_extraction"] = result.result_text
    else:
        logger.warning("Submission %s VLM extraction degraded to OCR-only (ERROR row)", sid)
