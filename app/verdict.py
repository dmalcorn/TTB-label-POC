"""Centralized verdict roll-up — ``rollup(verdicts)``.

Placeholder: authored in Story 3.1. Severity precedence (any FAIL ⇒ FAIL; else
any REVIEW/can't-verify ⇒ REVIEW; else PASS), used by BOTH the engine and the
UI so they can never disagree. Advisory ``engine_verdict`` only — it has NO
dependency on ``disposition`` and never maps to one. See
``_bmad-output/project-context.md`` → contract #3.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

# The submission-level engine_verdict output domain (no NA). Matches the
# submissions.engine_verdict CHECK enum exactly so the rolled-up value is
# always a legal column value.
Verdict = Literal["PASS", "REVIEW", "FAIL"]

# Greppable UPPER_SNAKE constants, identical to the DB CHECK enums. PASS/REVIEW/
# FAIL are the output domain; NA is provided for callers building the per-check
# checklist_items.verdict input (which is filtered out before the roll-up).
PASS: Verdict = "PASS"
REVIEW: Verdict = "REVIEW"
FAIL: Verdict = "FAIL"
NA = "NA"


def rollup(verdicts: Iterable[str]) -> Verdict:
    """Roll a set of per-check verdicts up to one submission verdict (contract #3).

    Severity precedence — the most-severe verdict wins:

    - any ``FAIL`` ⇒ ``FAIL``;
    - else any ``REVIEW`` (the caller's representation of "can't-verify") ⇒ ``REVIEW``;
    - else ``PASS``.

    ``NA`` (not-applicable) per-check verdicts are excluded before scanning — the
    input domain is the ``checklist_items.verdict`` enum ``{PASS, REVIEW, FAIL,
    NA}``; the output domain is the ``submissions.engine_verdict`` enum ``{PASS,
    REVIEW, FAIL}`` (``NA`` never propagates).

    An empty input or an all-``NA`` input ⇒ ``REVIEW``: a submission with nothing
    actually verified defers to the human, never silently auto-``PASS`` (the
    determinism-taxonomy rule "ambiguity goes to REVIEW, never a silent
    auto-decision").

    Any token OUTSIDE the legal input enum (a typo, a wrong-case ``"fail"``, an
    empty string, a future/unknown value) is treated as can't-verify and folds to
    ``REVIEW`` — the same fail-safe rule. An unrecognized verdict must never
    silently downgrade severity to ``PASS``.

    This is the SINGLE roll-up used by BOTH the engine (submission
    ``engine_verdict``) and the UI (Suggested Alert) so they can never disagree.
    It is advisory only — it has NO dependency on ``disposition`` and emits no
    ``verdict → disposition`` mapping ("Recommend, don't decide").
    """
    scored = [v for v in verdicts if v != NA]
    if not scored:
        return REVIEW
    if FAIL in scored:
        return FAIL
    # Any REVIEW, OR any token outside the legal {PASS, FAIL} remainder, defers to
    # REVIEW (fail-safe): an unknown/malformed verdict never auto-PASSes.
    if any(v != PASS for v in scored):
        return REVIEW
    return PASS
