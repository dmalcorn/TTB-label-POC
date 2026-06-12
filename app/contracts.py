"""Centralized adapter contracts — ``OcrResult`` / ``LlmResult`` shapes.

Placeholder: the contract definitions are authored in Story 2.1. Every OCR
engine and every model adapter imports its shape from here (never re-implements
it), so this stays the single module that owns those types. See
``_bmad-output/project-context.md`` → "The Four Centralized Contracts".
"""

from __future__ import annotations
