"""Centralized adapter contract shapes — OcrResult / LlmResult (Story 2.1, AC1).

These are pure in-memory shapes (architecture contract #1 / AR-3 #1). The tests
pin the EXACT field sets so an adapter can never silently widen the contract,
and guard the ``total_tokens`` derived-property behavior that mirrors the
``llm_results`` generated column.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.contracts import LlmResult, OcrResult

# The contract field names are fixed by project-context "Four Centralized
# Contracts". OcrResult = 8 fields; LlmResult = 13 (12 dataclass fields +
# total_tokens as a derived property).
OCR_FIELDS = {
    "engine_name",
    "engine_version",
    "text",
    "word_boxes",
    "confidence",
    "latency_ms",
    "ran_on_cpu",
    "status",
}
LLM_DATACLASS_FIELDS = {
    "model_name",
    "model_id",
    "model_full_id",
    "provider",
    "task",
    "result_text",
    "prompt_tokens",
    "completion_tokens",
    "latency_ms",
    "requested_at",
    "responded_at",
    "status",
}


def test_ocr_result_exact_field_set():
    assert {f.name for f in dataclasses.fields(OcrResult)} == OCR_FIELDS


def test_ocr_result_is_frozen():
    r = OcrResult(engine_name="tesseract")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.engine_name = "paddleocr"  # type: ignore[misc]


def test_ocr_result_defaults():
    r = OcrResult(engine_name="tesseract")
    assert r.status == "OK"
    assert r.ran_on_cpu is True
    assert r.text is None and r.word_boxes is None and r.confidence is None


def test_llm_result_exact_field_set():
    # total_tokens is a derived property, NOT a settable dataclass field.
    assert {f.name for f in dataclasses.fields(LlmResult)} == LLM_DATACLASS_FIELDS


def test_total_tokens_is_a_read_only_property():
    # accessed on the class, a property returns its descriptor object
    assert isinstance(LlmResult.total_tokens, property)
    assert "total_tokens" not in {f.name for f in dataclasses.fields(LlmResult)}


def test_total_tokens_sums_parts():
    assert LlmResult(prompt_tokens=10, completion_tokens=20).total_tokens == 30


def test_total_tokens_none_when_either_part_missing():
    assert LlmResult(prompt_tokens=None, completion_tokens=20).total_tokens is None
    assert LlmResult(prompt_tokens=10, completion_tokens=None).total_tokens is None
    assert LlmResult().total_tokens is None


def test_total_tokens_cannot_be_set():
    with pytest.raises((AttributeError, TypeError)):
        LlmResult(prompt_tokens=1, completion_tokens=2).total_tokens = 99  # type: ignore[misc]
