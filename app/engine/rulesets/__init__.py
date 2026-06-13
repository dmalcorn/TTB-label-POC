"""Rulesets-as-DATA — per-beverage-type compliance Checks (Story 3.2).

The canonical ruleset for each beverage type is a Python DATA module (a tuple of
:class:`~app.engine.rulesets.base.Check` rows), NOT a DB table. Distilled spirits
is authored at depth now; WINE / MALT_BEVERAGE are the Story 3.8 sentinel — an
empty ruleset (a submission with no checks rolls up to REVIEW per
``app/verdict.py``'s empty policy).

Import :func:`get_ruleset` (the lookup) and :class:`Check` (the data shape) from
here; CFR citations live ONLY in the data modules (AC4).
"""

from __future__ import annotations

from app.engine.rulesets.base import Check, CheckType
from app.engine.rulesets.distilled_spirits import DISTILLED_SPIRITS_RULESET

__all__ = ["Check", "CheckType", "get_ruleset"]

# beverage_type → its ruleset. Spirits is authored at depth (Story 3.2); wine and
# malt are intentionally empty until Story 3.8. The map is keyed by the
# ``submissions.beverage_type`` enum value (UPPER_SNAKE).
_RULESETS: dict[str, tuple[Check, ...]] = {
    "DISTILLED_SPIRITS": DISTILLED_SPIRITS_RULESET,
    "WINE": (),
    "MALT_BEVERAGE": (),
}


def get_ruleset(beverage_type: str) -> tuple[Check, ...]:
    """The ruleset (tuple of :class:`Check` rows) for a beverage type.

    Spirits returns the authored ruleset; ``WINE`` / ``MALT_BEVERAGE`` return an
    empty tuple (the Story 3.8 sentinel). An unknown/unmapped type also returns
    ``()`` — finalize-don't-abort (FR-9): the executor rolls an empty ruleset up to
    REVIEW rather than raising.
    """
    return _RULESETS.get(beverage_type, ())
