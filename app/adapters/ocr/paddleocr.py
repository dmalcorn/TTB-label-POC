"""PaddleOCR adapter → :class:`~app.contracts.OcrResult` (Story 2.4, AC1/AC4/AC5).

The second concrete :class:`~app.adapters.ocr.base.OcrEngine`. Like the Tesseract
adapter, ``paddleocr`` is imported **lazily inside** the engine, never at module
load, so importing/registering this engine needs zero native deps (the default
suite stays offline + fast; the app boots under ``--network none`` before any OCR
runs).

**Offline weights (AC4, the firewall proof).** PaddleOCR downloads model weights on
first use by default — **forbidden at runtime** (the OCR job is classified ``none``
in the outbound-calls inventory). The Dockerfile bakes the pinned PP-OCRv5 weights
into the image at *build* time (a build-time warmup populates the PaddleX cache dir
``PADDLE_PDX_CACHE_HOME``); with the weights already on disk PaddleOCR loads them
locally and makes no network call. An optional ``PADDLEOCR_MODEL_DIR`` env lets a
deployment point detection/recognition at an explicit baked weights dir instead. The
model is CPU-only (``device='cpu'``) — govt infra has no guaranteed GPU — so
``ran_on_cpu`` is ``True``.

The expensive ``PaddleOCR(...)`` construction is done **once** (a module-level
singleton) and reused across images; init must not hit the network.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from app.contracts import OcrResult

logger = logging.getLogger(__name__)

_ENGINE_NAME = "paddleocr"

# Module-level singleton — PaddleOCR init is heavy (loads det/rec models); never
# re-init per image (AC3 routing can call extract many times per submission). The
# lock makes the check-then-build safe if the sweep ever processes submissions
# concurrently — without it two threads could both run the expensive init.
_model: Any | None = None
_model_init_failed = False
_model_lock = threading.Lock()

# PaddleOCR/PaddleX is NOT thread-safe: its pipeline carries per-call batch state across
# the shared det/rec/orientation sub-models, so two pipeline worker threads calling
# predict() on the one singleton at once corrupt that state — surfacing as an internal
# "N != 1 for key class_ids!" assertion (and, worse, possible silent cross-contamination
# of results between images). Serialize ALL inference through this lock so only one
# predict()/ocr() runs at a time. Tesseract is unaffected (it shells out to a per-call
# subprocess, so it stays parallel), and this lock is independent of the DB write lock —
# a thread doing inference here never blocks another thread's DB writes.
_inference_lock = threading.Lock()


def _resolve_version() -> str | None:
    try:
        from importlib.metadata import version

        return version("paddleocr")
    except Exception:  # noqa: BLE001 — version is best-effort metadata
        return None


def _build_model() -> Any:
    """Construct the PaddleOCR model from the **baked-in offline weights** (AC4).

    Reads the local weights dir from ``PADDLEOCR_MODEL_DIR`` (the Dockerfile bakes
    the pinned weights there at build time). Initialization is CPU-only and must not
    download — with the weights already present, PaddleOCR loads from disk. Imported
    lazily so this module stays import-safe without the native dep.
    """
    from paddleocr import PaddleOCR

    model_dir = os.getenv("PADDLEOCR_MODEL_DIR") or None
    # Minimal, conventional kwargs: English, CPU, no extra textline-orientation pass.
    # When a baked weights dir is configured AND the det/rec layout is actually present,
    # point detection + recognition at it so nothing is fetched at runtime. If the layout
    # is absent (not yet baked on this build host), fall back to the warmed PaddleX cache
    # (`PADDLE_PDX_CACHE_HOME`) — also fully offline — rather than passing a non-existent
    # dir, which could otherwise make PaddleOCR re-attempt a download (firewall regression).
    # enable_mkldnn=False: the oneDNN backend crashes PP-OCRv5 inference on this CPU
    # build of paddlepaddle 3.x ("ConvertPirAttribute2RuntimeAttribute not support
    # [pir::ArrayAttribute<pir::DoubleAttribute>]" in onednn_instruction.cc). Global
    # FLAGS_use_mkldnn is ignored — PaddleX sets its own pp_option — so it must be
    # disabled through the PaddleOCR API. Native CPU kernels read the synthetic label
    # correctly (verified under --network none). [Story 2.4 build validation, 2026-06-13]
    kwargs: dict[str, Any] = {"lang": "en", "device": "cpu", "enable_mkldnn": False}
    if model_dir:
        base = Path(model_dir)
        det_dir, rec_dir = base / "det", base / "rec"
        if det_dir.is_dir() and rec_dir.is_dir():
            kwargs["det_model_dir"] = str(det_dir)
            kwargs["rec_model_dir"] = str(rec_dir)
    return PaddleOCR(**kwargs)


def _get_model() -> Any | None:
    """Lazily build and cache the singleton; ``None`` if construction failed once
    (so a broken/missing install degrades to honest ``ERROR`` rows, not repeated
    expensive retries that each crash)."""
    global _model, _model_init_failed
    if _model is not None:
        return _model
    if _model_init_failed:
        return None
    with _model_lock:
        # Re-check inside the lock — another thread may have built (or failed) it
        # while we waited.
        if _model is not None:
            return _model
        if _model_init_failed:
            return None
        try:
            _model = _build_model()
        except Exception:  # noqa: BLE001 — never raise into the stage (AC5)
            logger.exception("PaddleOCR initialization failed")
            _model_init_failed = True
            return None
        return _model


def _iter_lines(raw: Any) -> list[tuple[str, float, Any]]:
    """Flatten PaddleOCR output into ``(text, score, box)`` triples, defensively.

    PaddleOCR's return shape has shifted across versions: the classic ``.ocr()`` form
    is ``[[[box, (text, score)], ...]]``; the 3.x ``.predict()`` form is a list of
    result objects exposing ``rec_texts`` / ``rec_scores`` / ``rec_polys``. Handle
    both rather than pinning one fragile path — unknown shapes yield no lines.
    """
    lines: list[tuple[str, float, Any]] = []
    if raw is None:
        return lines

    # 3.x predict(): list of dict-like results with parallel rec_* arrays.
    for result in raw if isinstance(raw, (list, tuple)) else [raw]:
        as_dict = result if isinstance(result, dict) else getattr(result, "__dict__", None)
        if isinstance(as_dict, dict) and "rec_texts" in as_dict:
            texts = as_dict.get("rec_texts") or []
            scores = as_dict.get("rec_scores") or []
            polys = as_dict.get("rec_polys") or as_dict.get("rec_boxes") or []
            for i, text in enumerate(texts):
                score = float(scores[i]) if i < len(scores) else 0.0
                box = polys[i] if i < len(polys) else None
                lines.append((str(text), score, box))
            continue
        # classic .ocr(): result is a list of [box, (text, score)] entries.
        if isinstance(result, (list, tuple)):
            for entry in result:
                try:
                    box, (text, score) = entry
                except (ValueError, TypeError):
                    continue
                lines.append((str(text), float(score), box))
    return lines


def _to_box(box: Any) -> Any:
    """Normalize a polygon/box to a JSON-serializable nested list (or ``None``)."""
    if box is None:
        return None
    try:
        return [[float(x) for x in pt] for pt in box]
    except (TypeError, ValueError):
        try:
            return [float(v) for v in box]
        except (TypeError, ValueError):
            return None


class PaddleOcrEngine:
    """PaddleOCR (PP-OCRv5) via ``paddleocr`` — a concrete :class:`OcrEngine` (AC1).

    Variant-agnostic (the engine-aware preference — PaddleOCR favors the enhanced
    grayscale variant — lives in the stage, AR-4). ``ran_on_cpu`` is always ``True``
    (CPU-only init). ``version`` is the installed ``paddleocr`` package version.
    """

    name: str = _ENGINE_NAME

    def __init__(self) -> None:
        # Plain attribute so ``isinstance(self, OcrEngine)`` holds without importing
        # paddleocr; resolved from package metadata if present, else stays empty.
        self.version: str = _resolve_version() or ""

    def extract(self, image_path: str | Path, *, ran_on_cpu: bool = True) -> OcrResult:
        """OCR one image → an :class:`OcrResult`. Never raises into the stage (AC5):
        a missing/failed install or any engine error returns an ``ERROR`` result."""
        start = time.monotonic()
        try:
            model = _get_model()
            if model is None:
                raise RuntimeError("PaddleOCR model unavailable (init failed or not installed)")

            raw = self._run_model(model, str(image_path))
            lines = _iter_lines(raw)
            text = "\n".join(t for t, _, _ in lines)
            word_boxes = [{"text": t, "box": _to_box(b), "conf": round(s, 4)} for t, s, b in lines]
            scores = [s for _, s, _ in lines]
            # Clamp to the contract's 0–1 invariant: scores are already ~0–1, but a
            # stray out-of-range score would otherwise hit the ocr_results.confidence
            # CHECK (BETWEEN 0 AND 1) and fail the insert (paired with the stage's
            # persist guard, AC5/AC1).
            confidence = min(1.0, max(0.0, sum(scores) / len(scores))) if scores else None
            return OcrResult(
                engine_name=_ENGINE_NAME,
                engine_version=self.version or _resolve_version(),
                text=text,
                word_boxes=word_boxes,
                confidence=confidence,
                latency_ms=int((time.monotonic() - start) * 1000),
                ran_on_cpu=ran_on_cpu,
                status="OK",
            )
        except Exception:  # noqa: BLE001 — honest ERROR row, never abort the stage (AC5)
            logger.exception("PaddleOCR failed on %s", image_path)
            return OcrResult(
                engine_name=_ENGINE_NAME,
                engine_version=self.version or None,
                latency_ms=int((time.monotonic() - start) * 1000),
                ran_on_cpu=ran_on_cpu,
                status="ERROR",
            )

    @staticmethod
    def _run_model(model: Any, path: str) -> Any:
        """Invoke whichever inference method this PaddleOCR build exposes. 3.x prefers
        ``predict``; older builds use ``ocr``. Try the modern one first.

        Serialized under :data:`_inference_lock`: PaddleOCR is not thread-safe, and the
        pipeline shares one model singleton across worker threads — concurrent calls
        otherwise race its internal batch state (see the lock's note)."""
        with _inference_lock:
            if hasattr(model, "predict"):
                return model.predict(path)
            return model.ocr(path)
