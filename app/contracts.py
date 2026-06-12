"""Centralized adapter contracts — ``OcrResult`` / ``LlmResult`` shapes.

The single module that owns the adapter return shapes (architecture contract #1,
AR-3 #1). Every OCR engine returns an :class:`OcrResult`; every model adapter
returns an :class:`LlmResult`. No other module re-implements these — they import
from here. Adding an engine/model is a new adapter file, no schema change (FR-11).

These are pure in-memory shapes: zero I/O, zero DB, zero adapter imports. The
mapping to the ``ocr_results`` / ``llm_results`` columns (including the one
name difference, ``text`` → ``extracted_text``) lives in
``app/db/repositories.py`` — the data boundary. project-context: "Pydantic v2
validates at the API/read boundary only", so these internal shapes are plain
frozen dataclasses rather than Pydantic models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OcrStatus = Literal["OK", "ERROR"]
LlmStatus = Literal["OK", "ERROR"]


@dataclass(frozen=True, slots=True)
class OcrResult:
    """One OCR engine's run on one image — the uniform shape every engine returns.

    Field-for-field the architecture's contract #1 (8 fields). ``text`` is stored
    in the ``ocr_results.extracted_text`` column; ``word_boxes`` (a list of
    per-word ``{text, box}`` dicts) is persisted as JSON TEXT. ``error_text`` is
    NOT part of the shape — it is a writer-supplied column.
    """

    engine_name: str
    engine_version: str | None = None
    text: str | None = None
    word_boxes: list[dict] | None = None
    confidence: float | None = None
    latency_ms: int | None = None
    ran_on_cpu: bool = True
    status: OcrStatus = "OK"


@dataclass(frozen=True, slots=True)
class LlmResult:
    """One model run — the uniform shape every model adapter returns.

    The architecture's contract #1 lists 13 fields including ``total_tokens``.
    ``total_tokens`` is a DERIVED read-only property (``prompt + completion``,
    ``None`` if either part is ``None``), never independently set — mirroring the
    ``llm_results.total_tokens`` SQLite generated column so the in-memory shape
    and the stored value can never drift. ``is_benchmark_only`` is NOT part of
    the shape — it is a writer-supplied column.
    """

    model_name: str | None = None
    model_id: str | None = None
    model_full_id: str | None = None
    provider: str | None = None
    task: str | None = None
    result_text: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int | None = None
    requested_at: str | None = None
    responded_at: str | None = None
    status: LlmStatus = "OK"

    @property
    def total_tokens(self) -> int | None:
        """``prompt_tokens + completion_tokens``; ``None`` if either is ``None``."""
        if self.prompt_tokens is None or self.completion_tokens is None:
            return None
        return self.prompt_tokens + self.completion_tokens
