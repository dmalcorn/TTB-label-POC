"""OCR adapter tests (Story 2.4, AC1/AC4/AC5).

Default-suite tests are **offline and native-dep-free**: they assert the two real
adapters satisfy the runtime-checkable :class:`OcrEngine` protocol (construction must
NOT import Tesseract/Paddle), unit-test the confidence-normalization mapping, and
prove the adapters' self-guard (a missing native engine → an ``ERROR`` result, never
a raise). Real-engine smoke tests are gated behind a skip so CI stays fast and
``--network none``-clean. Stage-level routing/persistence lives in ``test_pipeline.py``.
"""

from __future__ import annotations

import importlib.util

import pytest

from app.adapters.ocr.base import OcrEngine
from app.adapters.ocr.paddleocr import PaddleOcrEngine
from app.adapters.ocr.tesseract import TesseractEngine, normalize_confidence
from app.contracts import OcrResult


def _installed(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


# ── AC1: protocol conformance without native deps ────────────────────────────


def test_tesseract_engine_satisfies_protocol_offline():
    # Construction must not import pytesseract — the engine is registrable (and the
    # app bootable under --network none) even where the native engine is absent.
    assert isinstance(TesseractEngine(), OcrEngine)


def test_paddleocr_engine_satisfies_protocol_offline():
    assert isinstance(PaddleOcrEngine(), OcrEngine)


# ── AC1: confidence 0–100 → 0–1 mapping helper ───────────────────────────────


def test_normalize_confidence_maps_0_100_to_0_1():
    # Tesseract reports 0–100; the contract + DB CHECK require 0–1.
    assert normalize_confidence([100, 50, 0]) == pytest.approx(0.5)


def test_normalize_confidence_drops_minus_one_sentinels_and_none():
    # -1 marks a non-text box; None is a gap. Mean is over the valid words only.
    assert normalize_confidence([90, -1, None, 80]) == pytest.approx((0.9 + 0.8) / 2)


def test_normalize_confidence_empty_is_none_not_zero():
    # No valid word ⇒ None (unknown), distinct from 0.0 (read, zero-confidence).
    assert normalize_confidence([]) is None
    assert normalize_confidence([-1, -1]) is None


def test_normalize_confidence_result_is_in_0_1_band():
    conf = normalize_confidence([100, 95, 88, -1])
    assert conf is not None and 0.0 <= conf <= 1.0


# ── AC5: adapters self-guard — a missing native engine yields ERROR, not a raise ──


def test_tesseract_extract_returns_error_when_engine_unavailable():
    # pytesseract is absent in the default env: extract must return an ERROR
    # OcrResult (engine_name set, status ERROR), never raise into the stage.
    result = TesseractEngine().extract("does-not-exist.png")
    assert isinstance(result, OcrResult)
    assert result.engine_name == "tesseract"
    assert result.status == "ERROR"
    assert result.latency_ms is not None and result.latency_ms >= 0


def test_paddleocr_extract_returns_error_when_engine_unavailable():
    result = PaddleOcrEngine().extract("does-not-exist.png")
    assert isinstance(result, OcrResult)
    assert result.engine_name == "paddleocr"
    assert result.status == "ERROR"


# ── Real-engine smoke tests (skipped unless the native engine is installed) ───


@pytest.mark.skipif(
    not (_installed("pytesseract") and _installed("PIL")),
    reason="pytesseract/Pillow not installed — real-engine test skipped (offline CI)",
)
def test_tesseract_reads_synthetic_text(tmp_path):
    import cv2
    import numpy as np

    img = np.full((120, 480), 255, dtype=np.uint8)
    cv2.putText(img, "STONES THROW", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 0, 4)
    path = tmp_path / "label.png"
    cv2.imwrite(str(path), img)

    result = TesseractEngine().extract(path)
    assert result.status == "OK"
    assert "STONES" in (result.text or "").upper()
    assert result.confidence is None or 0.0 <= result.confidence <= 1.0
    assert result.ran_on_cpu is True
