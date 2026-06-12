"""Centralized verdict roll-up — ``rollup(verdicts)``.

Placeholder: authored in Story 3.1. Severity precedence (any FAIL ⇒ FAIL; else
any REVIEW/can't-verify ⇒ REVIEW; else PASS), used by BOTH the engine and the
UI so they can never disagree. Advisory ``engine_verdict`` only — it has NO
dependency on ``disposition`` and never maps to one. See
``_bmad-output/project-context.md`` → contract #3.
"""

from __future__ import annotations
