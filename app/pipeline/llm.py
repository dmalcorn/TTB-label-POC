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

from app.benchmark import tracing
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

# The extraction instruction. The model reads the IMAGE(s) and returns fields — there is
# no OCR text in this prompt (VLM-only). The keys are the exact ``submissions`` field_keys
# the deterministic comparator (Story 3.3) looks up, so the JSON parses per field with no
# remapping. JSON mode (set by the adapter) guarantees a valid object; we still tell the
# model to return ONLY JSON. Transcribe verbatim; never guess — a missing field is null.
_PROMPT = (
    "You are reading a US TTB alcohol-beverage label from the attached image(s) "
    "(there may be several panels: front/brand, back, neck, strip). Transcribe ONLY what "
    "is visibly printed — never guess, infer, or complete a value. Return a single JSON "
    "object with EXACTLY these keys; the value is the text AS PRINTED, or null when the "
    "field is not visible on any image:\n"
    '  "brand_name": the primary commercial/brand name;\n'
    '  "class_type_designation": what the product is (e.g. "Kentucky Straight Bourbon '
    'Whiskey", "Cabernet Sauvignon", "India Pale Ale");\n'
    '  "alcohol_content": the alcohol statement as printed (e.g. "45% ALC/VOL", "90 PROOF");\n'
    '  "net_contents": the fill statement as printed (e.g. "750 ML", "12 FL OZ", "1 PINT");\n'
    '  "applicant_name_address": the bottler/producer/importer name with city and state;\n'
    '  "country_of_origin": an origin statement if present (e.g. "PRODUCT OF FRANCE"), '
    "else null;\n"
    '  "government_warning": the full Surgeon General GOVERNMENT WARNING statement, '
    "transcribed verbatim, else null.\n"
    "Return JSON only — no commentary, no markdown."
)


def _image_path(image: LabelImage) -> Path:
    """The on-disk path of a label image's ORIGINAL file (the seeded fixtures root).

    The VLM reads the original image — no OCR text and no OpenCV-preprocessed variant
    (those are separate benchmark configurations); this is the pure VLM-only input."""
    return SOURCE_IMAGES_DIR / image.filename


def _run_adapter(adapter: ModelAdapter, image_paths: list[Path]) -> LlmResult:
    """Run the adapter over ALL of the submission's label images in ONE call, downgrading
    any escaping exception to an ``ERROR`` result.

    Adapters already self-guard, so this is defensive depth: it guarantees the stage
    has an honest ``LlmResult`` (with provider identity + timing) to persist as the
    degraded signal even if an adapter ever raised (AC3)."""
    from app.adapters.llm._common import utc_now_iso

    requested_at = utc_now_iso()
    try:
        return adapter.run(EXTRACT_FIELDS_TASK, _PROMPT, image_path=[str(p) for p in image_paths])
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
    # Send EVERY label image (front/back/neck/strip) in one call — net contents, ABV, the
    # name/address line, and the warning often live on a different panel than the brand. The
    # llm_results row is bound to the primary (display-order first) image for provenance.
    primary = ctx.label_images[0] if ctx.label_images else None
    image_paths = [_image_path(img) for img in ctx.label_images if (img.filename or "").strip()]
    if primary is None or not image_paths:
        # VLM-only extraction has nothing to read without a real image path — skip
        # cleanly (the submission still finalizes OCR-only) rather than constructing a
        # client and calling the provider with a doomed (directory/blank) path.
        logger.warning("Submission %s has no readable label image; skipping VLM extraction", sid)
        return

    result = _run_adapter(adapter, image_paths)

    # Local-only, toggleable tracing (Story 5.1, FR-24). Gated on
    # LANGCHAIN_TRACING_ENABLED: when off (the default) this is a no-op that
    # constructs/imports nothing — the stage behaves identically to the no-tracing
    # baseline (AC3). When on, the call's identity/timing/tokens are captured to a
    # LOCAL sink only (no egress, no LangSmith/cloud endpoint — AC2/AC4). The durable
    # record stays the llm_results row written below.
    #
    # Tracing is ADDITIVE instrumentation: it must NEVER abort the stage or block the
    # durable insert_llm_result write below. A tracer fault would otherwise make the
    # enabled path lose the llm_results row a disabled run would have persisted — the
    # exact opposite of AC3's "behaves identically". So the trace call is wrapped: any
    # exception is logged and swallowed, and the stage still persists the row. Resolve
    # settings ONCE and thread it through both calls (one env read; no window where the
    # toggle could change between the gate and the trace).
    trace_settings = get_settings()
    if tracing.tracing_enabled(trace_settings):
        try:
            tracing.trace_llm_call(result, settings=trace_settings)
        except Exception:  # noqa: BLE001 — tracing is additive; never break the pipeline
            logger.exception("Local trace of the LLM call for submission %s failed", sid)

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
