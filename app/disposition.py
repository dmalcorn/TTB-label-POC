"""Centralized human-disposition enum — ``APPROVED`` / ``NEEDS_CORRECTION`` / ``REJECTED``.

Holds the disposition enum ONLY and has NO dependency on ``verdict.py`` — the
engine's advisory verdict and the human's disposition are different enums in
different modules, and **no function maps one to the other**. See
``_bmad-output/project-context.md`` → contract #4 and "Recommend, don't decide".

This is the ONE home for the disposition values (Story 4.8): the action-bar
presenter, the ``POST /review/{id}/disposition`` route, and the
``submissions.disposition`` CHECK all speak the SAME three values from here — never
a second hard-coded literal set. ``NEEDS_NOTES`` names the subset whose POST is
soft-gated on a non-blank reason (the server boundary, never trust the client).
"""

from __future__ import annotations

from typing import Final

# The three human dispositions, mirroring the ``submissions.disposition`` CHECK
# (schema.sql). UPPER_SNAKE, snake_case-consistent with every other enum.
APPROVED: Final = "APPROVED"
NEEDS_CORRECTION: Final = "NEEDS_CORRECTION"
REJECTED: Final = "REJECTED"

# The full disposition vocabulary, in display order (Approve · Needs Correction ·
# Reject) — the action bar renders them in this order, none pre-selected.
DISPOSITIONS: Final[tuple[str, ...]] = (APPROVED, NEEDS_CORRECTION, REJECTED)

# The subset that REQUIRES a plain-language reason for the maker. Approve is
# optional; a correction or rejection needs an actionable note (AC2). This is the
# server-side soft-gate boundary as well as the JS hint.
NEEDS_NOTES: Final[frozenset[str]] = frozenset({NEEDS_CORRECTION, REJECTED})


def is_valid(value: str | None) -> bool:
    """Whether ``value`` is one of the three known dispositions (the route guard)."""
    return value in DISPOSITIONS


def requires_notes(value: str) -> bool:
    """Whether recording ``value`` requires a non-blank reason (Needs Correction / Reject)."""
    return value in NEEDS_NOTES
