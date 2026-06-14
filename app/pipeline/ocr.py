"""The OCR pipeline stage — runs every configured engine over every image variant
and persists one independent ``ocr_results`` row per (engine, image, variant)
(Story 2.4, AC2/AC3/AC5).

Registered into ``run.STAGES`` **after** the Story 2.3 preprocess stage, behind the
Story 2.2 seam — no scheduler/status change. It emits the ``OCR_STARTED`` /
``OCR_COMPLETED`` timeline markers (taking over from 2.2's ``passthrough_stage``)
and writes only ``ocr_results`` rows in between; the verdict roll-up stays Epic 3's.

**Engine-aware variant routing (AR-7 / image-handling.md §3).** Each image is always
OCR'd on the ORIGINAL; additionally, each engine OCRs its **preferred** Story-2.3
variant when one exists — Tesseract↔BINARIZED, PaddleOCR↔ENHANCED — so a degraded
image yields both an original and a preprocessed row per engine and Epic 5 can score
the preprocessing benefit. A clean image (no variant) is OCR'd on the original only.
The routing is **data-driven here in the stage** (a small preference map), never
inside the adapters — adapters are variant-agnostic and OCR whatever path they are
handed (AR-4): adding PP-OCRv5 is a new adapter + one registry line, no stage change.

**Raw text only (AC2).** Each row stores the engine's full ``extracted_text`` +
per-run metadata; per-field parsing (brand/ABV/…) into ``field_comparisons`` is the
Epic 3 analysis job, not this stage.

**Failure posture (AC5, inherits 2.2).** A per-engine/per-image failure → an
``ERROR``-status row with ``error_text``; siblings still run and the submission still
finalizes. Adapters self-guard (they return ``ERROR`` rather than raise); the stage
also guards each call so even a raising engine cannot abort the submission.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from app.adapters.ocr.base import OcrEngine
from app.adapters.ocr.paddleocr import PaddleOcrEngine
from app.adapters.ocr.tesseract import TesseractEngine
from app.config import get_settings
from app.contracts import OcrResult
from app.db import repositories as repo
from app.pipeline import status
from app.pipeline.preprocess import SOURCE_IMAGES_DIR

if TYPE_CHECKING:  # avoid a run.py ↔ ocr.py import cycle (run imports this stage)
    from app.pipeline.run import StageContext

logger = logging.getLogger(__name__)


def build_engines() -> list[OcrEngine]:
    """The configured OCR engines, in order (AR-4 registry). Constructing these does
    NOT import the native libs (the adapters import lazily), so this is safe to call
    even where Tesseract/Paddle are absent. Adding PP-OCRv5 is one more line here."""
    return [TesseractEngine(), PaddleOcrEngine()]


# Engine-aware preference: which Story-2.3 variant each engine OCRs IN ADDITION to the
# original (image-handling.md §3). Keyed by engine name so it stays data-driven and the
# stage never branches on a concrete engine type. An engine absent from the map (a
# future engine) simply runs on the original only until a preference is declared.
ENGINE_PREFERRED_VARIANT: dict[str, str] = {
    "tesseract": "BINARIZED",
    "paddleocr": "ENHANCED",
}

# image_variant enum → the key the preprocess stage stashes in ctx.scratch['variants'].
_VARIANT_SCRATCH_KEY: dict[str, str] = {
    "ENHANCED": "enhanced",
    "BINARIZED": "binarized",
}


def _variant_info(
    ctx: StageContext, image_id: int, original_filename: str
) -> dict[str, str | None]:
    """The per-image variant paths from the 2.3 preprocess scratch, with a safe
    fallback (original only) when preprocess did not run or recorded nothing."""
    variants = ctx.scratch.get("variants", {})
    info = variants.get(image_id)
    if info is None:
        return {"original": original_filename, "enhanced": None, "binarized": None}
    return info


def _tasks_for_engine(engine: OcrEngine, info: dict[str, str | None]) -> list[tuple[str, str]]:
    """The ``(image_variant, relative_path)`` list one engine OCRs for one image:
    always ORIGINAL, plus the engine's preferred variant when 2.3 produced it (AC3)."""
    tasks: list[tuple[str, str]] = []
    original = info["original"]
    if original:  # skip rather than OCR an empty path (which resolves to a directory)
        tasks.append(("ORIGINAL", original))
    preferred = ENGINE_PREFERRED_VARIANT.get(engine.name)
    if preferred is not None:
        rel = info.get(_VARIANT_SCRATCH_KEY[preferred])
        if rel:  # only when the variant file actually exists (clean image ⇒ skip)
            tasks.append((preferred, rel))
    return tasks


def _resolve_path(image_variant: str, relative: str, generated_root: Path) -> Path:
    """ORIGINAL lives under the read-only seeded fixtures root; ENHANCED/BINARIZED
    variants live under the generated-images root (paths stored RELATIVE to it)."""
    if image_variant == "ORIGINAL":
        return SOURCE_IMAGES_DIR / relative
    return generated_root / relative


def _run_and_persist(
    ctx: StageContext,
    *,
    engine: OcrEngine,
    label_image_id: int,
    image_variant: str,
    full_path: Path,
) -> None:
    """Run one engine on one image variant and write its ``ocr_results`` row.

    Guards the engine call so a raising engine (defensive — adapters self-guard) still
    yields an honest ``ERROR`` row with ``error_text`` and never aborts siblings (AC5).
    """
    error_text: str | None = None
    try:
        result = engine.extract(full_path)
    except Exception as exc:  # noqa: BLE001 — one engine must not abort the submission
        logger.exception(
            "OCR engine %s raised on %s variant of label_image %s",
            engine.name,
            image_variant,
            label_image_id,
        )
        result = OcrResult(engine_name=engine.name, status="ERROR")
        error_text = repr(exc)
    if result.status == "ERROR" and error_text is None:
        # Adapter self-caught and returned ERROR without a message — record an honest,
        # specific note so the ERROR row is never silent (AC5).
        error_text = (
            f"{engine.name} reported ERROR on the {image_variant} variant of "
            f"label_image {label_image_id} ({full_path.name})"
        )
    try:
        repo.insert_ocr_result(
            ctx.conn,
            submission_id=ctx.submission.id,
            label_image_id=label_image_id,
            result=result,
            image_variant=image_variant,
            error_text=error_text,
        )
    except sqlite3.Error as db_exc:
        # A row-level persist failure (e.g. a CHECK violation on a malformed result)
        # must NOT abort the submission or its siblings (AC5). Log it, then try once
        # more with a minimal ERROR row (no payload to violate a constraint) so the
        # failure is still recorded rather than silently lost.
        logger.exception(
            "Persisting the %s %s row for label_image %s failed; recording an ERROR row",
            engine.name,
            image_variant,
            label_image_id,
        )
        try:
            repo.insert_ocr_result(
                ctx.conn,
                submission_id=ctx.submission.id,
                label_image_id=label_image_id,
                result=OcrResult(engine_name=engine.name, status="ERROR"),
                image_variant=image_variant,
                error_text=f"persist failed: {db_exc!r}",
            )
        except sqlite3.Error:
            logger.exception(
                "Fallback ERROR-row persist also failed for label_image %s (%s, %s)",
                label_image_id,
                engine.name,
                image_variant,
            )
    # Commit THIS row before the next (engine, image, variant) extraction. The loop
    # interleaves slow engine.extract() calls with these writes; a single end-of-stage
    # commit would hold the WAL write lock across all of them, so a concurrent worker's
    # write waits past busy_timeout and fails with "database is locked". Committing per
    # row keeps the lock held only for the brief insert — concurrent workers, and this
    # submission's own next extraction, proceed unblocked.
    try:
        ctx.conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Committing the %s %s OCR row for label_image %s failed",
            engine.name,
            image_variant,
            label_image_id,
        )


def ocr_stage(ctx: StageContext) -> None:
    """Story 2.4 pipeline stage: OCR every label image with every configured engine,
    on the original and (engine-aware) its preferred preprocessed variant.

    Emits ``OCR_STARTED`` / ``OCR_COMPLETED`` around the work (preserving the 2.2
    timeline) and writes one independent ``ocr_results`` row per (engine, image, variant).
    Each row is committed as it is written (see :func:`_run_and_persist`) so the WAL
    write lock is never held across the slow per-row extraction — two pipeline workers
    OCRing at once never block each other into "database is locked". Per-engine and
    per-image isolation means no single failure aborts the submission (AC5)."""
    sid = ctx.submission.id
    status.record_event(ctx.conn, sid, event_type="OCR_STARTED")

    engines = build_engines()
    generated_root = Path(get_settings().generated_images_dir)

    for image in ctx.label_images:
        info = _variant_info(ctx, image.id, image.filename)
        for engine in engines:
            for image_variant, relative in _tasks_for_engine(engine, info):
                full_path = _resolve_path(image_variant, relative, generated_root)
                _run_and_persist(
                    ctx,
                    engine=engine,
                    label_image_id=image.id,
                    image_variant=image_variant,
                    full_path=full_path,
                )

    ctx.conn.commit()  # no-op safety — each row was already committed in _run_and_persist
    status.record_event(ctx.conn, sid, event_type="OCR_COMPLETED")
