"""Flag-only (positional) rules carried as DATA (Story 3.7, AC1–AC3).

The single place the same-field-of-vision trio + the co-location-deferred reason +
the §5.63 citation live as DATA. The flag-REVIEW evaluator
(``app/engine/checks/flag_only.py``) *imports* this module and must never inline a
CFR citation or a rule literal in its logic (a grep for ``27 CFR`` inside
``checks/flag_only.py`` is a review finding — AC2).

This module is **pure data + types only** — it imports nothing from the engine
executor/evaluators, so a citation string can never leak into logic from here
(mirrors ``app/engine/rulesets/government_warning.py`` + ``format_checks.py`` +
``class_type.py``).

Source: ``docs/regulatory-rules-distilled-spirits.md`` §2 — the same-field-of-vision
rule (§5.63): "a label or labels bearing the **brand name**, **alcohol content**,
and **class/type designation** must appear in the **same field of vision**." The POC
check type is **flag-REVIEW (positional)**: the engine confirms the three elements
are present and flags the *co-location* requirement for the Label Specialist, because
"OCR bounding boxes alone cannot guarantee [one viewable face] from photos."
Citations use the post-2022 Part 5 renumbering.
"""

from __future__ import annotations

# The date the citation below was verified current (the post-2022 Part 5
# reorganization), matching the spirits ruleset source-date convention.
SOURCE_DATE = "2022-01-08"

# ── same field of vision (§5.63) — AC2/AC3 ───────────────────────────────────
# The §5.63 citation as DATA — never inlined in the check logic.
CFR_CITATION = "27 CFR 5.63"

# The ordered trio of application field_keys whose INDIVIDUAL presence the
# same-field-of-vision check reports. Per §5.63: brand name, alcohol content, and
# class/type designation must appear in the same field of vision. Carried as DATA so a
# §5.63 amendment to the trio is a one-line edit, never a hard-coded list in logic.
SAME_FIELD_OF_VISION_FIELDS: tuple[str, ...] = (
    "brand_name",
    "class_type_designation",
    "alcohol_content",
)

# The fixed explanatory note describing WHY co-location is deferred to the human. A
# flat photo + a flattened OCR-text join cannot prove the trio shares one
# 40%-of-circumference viewable face, so the engine confirms presence and flags the
# co-location for the specialist to eyeball on the rendered label.
SAME_FIELD_OF_VISION_REASON = (
    "co-location on one viewable face (a single side viewable without turning the "
    "container, ~40% of the circumference) cannot be confirmed from a flat photo — "
    "the engine confirms each element's presence and flags the co-location for the "
    "specialist to eyeball on the rendered label"
)
