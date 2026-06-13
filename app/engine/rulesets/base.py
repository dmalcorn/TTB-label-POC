"""Ruleset-as-DATA primitives — the frozen ``Check`` row (Story 3.2, AC1/AC4).

A beverage type's compliance Checks are authored as **data** (a tuple of
:class:`Check` rows) in the sibling modules (``distilled_spirits.py``; wine/malt
are Story 3.8). Each row carries its determinism class and its **CFR citation as
data** — never hard-coded in evaluator/executor logic ("CFR rules live as data",
project-context; AC4). The executor (``app/engine/run_checks.py``) reads the
citation/type off the row when it writes each ``checklist_items`` row, so a Part
renumbering needs no code change.

This module is **pure data + types only** — it imports nothing from the engine
executor or evaluators, so it can never be the place a citation string leaks into
logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# The determinism class carried on each Check. Mirrors the
# ``checklist_items.check_type`` CHECK enum EXACTLY (TEXT + CHECK, UPPER_SNAKE) so
# the value written to the column is always legal:
#   - DETERMINISTIC — pure rule/regex match (e.g. the Government Warning; no LLM).
#   - FIELD_MATCH   — application value vs. extracted (OCR) value comparison.
#   - HYBRID        — presence/format deterministic + a content judgment (may use
#                     a VLM, capped at REVIEW — never an LLM-alone FAIL).
#   - MANUAL        — the engine cannot confirm; flag-REVIEW for the specialist
#                     (e.g. the positional same-field-of-vision check).
CheckType = Literal["DETERMINISTIC", "FIELD_MATCH", "HYBRID", "MANUAL"]


@dataclass(frozen=True)
class Check:
    """One required compliance check, expressed as immutable DATA.

    Pure data — NO logic. The executor dispatches on :attr:`strategy` to the
    matching evaluator (the ``{strategy: evaluator}`` registry in
    ``run_checks.py``), then writes the result as a ``checklist_items`` row
    carrying this row's :attr:`check_key`, :attr:`label`, :attr:`cfr_citation`,
    and :attr:`check_type` verbatim (provenance — AC3/AC4).
    """

    check_key: str
    """Stable snake_case identifier; resolves to an entry in
    ``docs/data-dictionary.md`` §6.2 (project-context "Stable identifiers")."""

    label: str
    """Human-readable check name for the UI checklist."""

    check_type: CheckType
    """The determinism class — written to ``checklist_items.check_type`` as data."""

    cfr_citation: str
    """The CFR citation as DATA: ``"27 CFR <part>.<section>"`` (AC4). The ONLY
    place this string lives — never hard-coded in evaluator/executor logic."""

    source_date: str
    """UTC ISO date the citation was current (the post-2022 Part 5 reorg)."""

    strategy: str
    """Which evaluator handles this Check (the registry key in ``run_checks.py``).
    Stories 3.3–3.7 each register one evaluator under their strategy key."""

    field_key: str | None = None
    """For field-match checks: the application/extracted field compared (resolves
    to a ``field_comparisons.field_key`` / data-dictionary field). ``None`` for
    checks that compare no single application field."""
