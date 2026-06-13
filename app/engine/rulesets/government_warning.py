"""The canonical Government Warning (27 CFR 16.21) text + formatting rules, as DATA.

Story 3.4, AC4 — "CFR rules live as data; never hard-coded in check logic". This
module is the **single** place the §16.21 statement and its formatting rules live;
``app/engine/checks/government_warning.py`` *imports* this data and must never
inline the warning string in its comparison logic (a grep for the warning text, or
``27 CFR`` outside data + tests, inside ``checks/`` is a review finding).

The Government Warning (27 CFR Part 16) applies to **ALL** beverage types, so this
is shared regulation data — not spirits-specific. When the wine/malt rulesets land
(Story 3.8) they reuse this exact module; do not fork the text.

Pure data + types only — imports nothing from the engine executor/evaluators, so a
citation string can never leak into logic from here.

Source: ``docs/regulatory-rules-distilled-spirits.md`` §5.1 (exact text) + §5.2
(formatting/casing rules), verified against ``ref-docs/27 CFR Part 16.pdf`` §16.21.
"""

from __future__ import annotations

from dataclasses import dataclass

# The CFR citation for the warning, as DATA (AC4). The ONLY place this literal lives
# alongside the spirits ruleset Check row (which carries the same citation as its own
# data). Format per project-context: ``"27 CFR <part>.<section>"``.
CFR_CITATION = "27 CFR 16.21"

# The date the §16.21 text was verified current (Part 16; matches the spirits ruleset
# source-date convention). A future §16.21 amendment is a one-line edit here.
SOURCE_DATE = "2022-01-08"

# The all-caps header token that anchors the warning and is itself caps-enforced.
HEADER = "GOVERNMENT WARNING:"

# The exact §16.21 BODY (everything AFTER the header), verbatim from §5.1 — including
# the (1)/(2) segment markers and all punctuation. The check compares the located body
# against this case-INSENSITIVELY after whitespace collapse (so an all-caps body is
# compliant), but requires EXACT wording + punctuation. This string is regulation DATA,
# never re-typed inside the check logic.
BODY = (
    "(1) According to the Surgeon General, women should not drink alcoholic beverages "
    "during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

# The full canonical statement (header + body), single contiguous space-joined block —
# the "expected" side of a char-diff on a wording deviation.
FULL_TEXT = f"{HEADER} {BODY}"


@dataclass(frozen=True)
class FormattingRules:
    """The §16.21/§5.2 formatting rules carried as DATA (not logic).

    The check reads these flags to decide WHICH assertions to enforce; encoding them
    as data (rather than as ``if`` literals in the check) keeps a rule change a data
    edit. ``mixed_case_capitals`` are the letters that must be capitalized in a
    *mixed-case* body (an all-caps body trivially satisfies them).
    """

    header_all_caps: bool = True
    """``GOVERNMENT WARNING:`` must appear in all-caps (header casing enforced)."""

    one_statement: bool = True
    """The body must be one contiguous statement (no foreign text between (1)/(2))."""

    segment_markers: tuple[str, ...] = ("(1)", "(2)")
    """The required numbered segment markers, in order."""

    mixed_case_capitals: tuple[str, ...] = ("Surgeon", "General")
    """Words requiring a capital initial in a MIXED-CASE body (the ``S``/``G`` rule).
    Skipped when the body is all-caps (all-caps is compliant per AC1)."""

    bold_required_but_unverifiable: bool = True
    """``GOVERNMENT WARNING`` must be BOLD, but bold is a visual-styling attribute OCR
    cannot recover from a photo — so the check flags it for human review (AC3(c)),
    never silently PASSing or FAILing on it."""


# The single shared rules instance the check imports.
RULES = FormattingRules()
