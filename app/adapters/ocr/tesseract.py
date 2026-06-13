"""Tesseract OCR adapter → :class:`~app.contracts.OcrResult` (Story 2.4, AC1/AC5).

A concrete :class:`~app.adapters.ocr.base.OcrEngine`. The pipeline depends only on
the protocol (AR-4) — this module is one of two real engines (PaddleOCR is the
other); adding a third (PP-OCRv5) is a new adapter file + one registry line, no
schema or caller change.

``pytesseract`` (and the Pillow it pulls in) is imported **lazily inside**
:meth:`TesseractEngine.extract`, never at module load, so importing this module —
and registering the engine into the pipeline — works with **zero native deps**.
That keeps the default test suite offline and fast (it exercises stub engines and
asserts protocol-conformance), and lets the app boot under ``docker run
--network none`` even before the engines run. The real binary is a system package
baked into the image (Dockerfile, Story 1.1); a missing/failed engine is reported
as an ``ERROR`` :class:`OcrResult`, never raised into the stage (AC5).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from pathlib import Path

from app.contracts import OcrResult

logger = logging.getLogger(__name__)

_ENGINE_NAME = "tesseract"


def normalize_confidence(confidences: Sequence[float | int | str | None]) -> float | None:
    """Map pytesseract's per-word confidences (**0–100**, ``-1`` for non-text) to the
    contract's **0–1** mean (AC1; ``ocr_results.confidence CHECK BETWEEN 0 AND 1``).

    Drops the ``-1`` sentinels and any ``None``/unparseable entries, divides by 100,
    and means over the remaining valid words. Returns ``None`` when no word carried a
    valid confidence (an empty image) — distinct from ``0.0`` (read, zero-confidence).
    Get this wrong and the ``confidence`` CHECK constraint rejects the insert.
    """
    valid: list[float] = []
    for raw in confidences:
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value < 0:  # tesseract's -1 sentinel for a non-text box
            continue
        valid.append(value / 100.0)
    if not valid:
        return None
    return sum(valid) / len(valid)


def _text_from_data(data: dict) -> str:
    """Reconstruct readable text from one ``image_to_data`` dict in a SINGLE OCR pass.

    Groups words by their (block, paragraph, line) indices and joins — so we don't
    run OCR twice (``image_to_string`` + ``image_to_data``) and inflate ``latency_ms``,
    which is a benchmark stat. Blank tokens (the spacing rows tesseract emits) are
    skipped; lines are newline-joined in reading order.
    """
    words = data.get("text", [])
    blocks = data.get("block_num", [])
    pars = data.get("par_num", [])
    lines = data.get("line_num", [])
    grouped: dict[tuple[int, int, int], list[str]] = {}
    order: list[tuple[int, int, int]] = []
    for i, word in enumerate(words):
        token = (word or "").strip()
        if not token:
            continue
        key = (blocks[i], pars[i], lines[i])
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(token)
    return "\n".join(" ".join(grouped[key]) for key in order)


def _word_boxes_from_data(data: dict) -> list[dict]:
    """Per-word ``{text, box, conf}`` list (AC1). ``box`` is ``[left, top, width,
    height]`` (tesseract's native geometry); ``conf`` is normalized to 0–1 to match
    the row-level confidence. Skips blank tokens and ``-1``-confidence boxes."""
    boxes: list[dict] = []
    words = data.get("text", [])
    confs = data.get("conf", [])
    lefts, tops = data.get("left", []), data.get("top", [])
    widths, heights = data.get("width", []), data.get("height", [])
    for i, word in enumerate(words):
        token = (word or "").strip()
        if not token:
            continue
        try:
            conf = float(confs[i])
        except (TypeError, ValueError, IndexError):
            conf = -1.0
        if conf < 0:
            continue
        boxes.append(
            {
                "text": token,
                "box": [int(lefts[i]), int(tops[i]), int(widths[i]), int(heights[i])],
                "conf": round(conf / 100.0, 4),
            }
        )
    return boxes


class TesseractEngine:
    """Tesseract 5 via ``pytesseract`` — a concrete :class:`OcrEngine` (AC1).

    Variant-agnostic: it OCRs whatever image path the stage hands it (the engine-aware
    routing — Tesseract prefers the binarized variant — lives in the stage, not here,
    per AR-4). ``version`` starts empty and is filled with the live tesseract binary
    version on the first successful :meth:`extract`.
    """

    name: str = _ENGINE_NAME

    def __init__(self) -> None:
        # Plain attribute (not a property) so ``isinstance(self, OcrEngine)`` holds
        # WITHOUT importing pytesseract; the live version is resolved lazily below.
        self.version: str = ""

    def extract(self, image_path: str | Path, *, ran_on_cpu: bool = True) -> OcrResult:
        """OCR one image → an :class:`OcrResult`. Never raises into the stage (AC5):
        a missing binary, an unreadable file, or any engine error returns an
        ``ERROR``-status result (the stage adds ``error_text``)."""
        start = time.monotonic()
        try:
            import pytesseract  # lazy — keeps module import native-dep-free

            engine_version = str(pytesseract.get_tesseract_version())
            self.version = engine_version
            data = pytesseract.image_to_data(str(image_path), output_type=pytesseract.Output.DICT)
            latency_ms = int((time.monotonic() - start) * 1000)
            return OcrResult(
                engine_name=_ENGINE_NAME,
                engine_version=engine_version,
                text=_text_from_data(data),
                word_boxes=_word_boxes_from_data(data),
                confidence=normalize_confidence(data.get("conf", [])),
                latency_ms=latency_ms,
                ran_on_cpu=ran_on_cpu,
                status="OK",
            )
        except Exception:  # noqa: BLE001 — honest ERROR row, never abort the stage (AC5)
            logger.exception("Tesseract failed on %s", image_path)
            return OcrResult(
                engine_name=_ENGINE_NAME,
                engine_version=self.version or None,
                latency_ms=int((time.monotonic() - start) * 1000),
                ran_on_cpu=ran_on_cpu,
                status="ERROR",
            )
