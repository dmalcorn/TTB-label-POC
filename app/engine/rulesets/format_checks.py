"""Per-type FORMAT rules carried as DATA (Story 3.5, AC1–AC4).

The single place the per-type ABV-presence policy (the cross-type false-reject
trap), the 27 CFR 5.203 standards-of-fill approved-size table, the proof↔ABV
ratio, and the §5.66 name/address responsibility phrases live as DATA. The
deterministic evaluator (``app/engine/checks/format_checks.py``) *imports* this
module and must never inline a CFR citation or a rule literal in its comparison
logic (a grep for ``27 CFR`` inside ``checks/format_checks.py`` is a review
finding — AC1/AC4).

This module is **pure data + types only** — it imports nothing from the engine
executor/evaluators, so a citation string can never leak into logic from here
(mirrors ``app/engine/rulesets/government_warning.py``).

Sources: ``docs/label-requirements-by-type.md`` (the cross-type ABV trap + the
master mandatory-elements matrix) and ``docs/regulatory-rules-distilled-
spirits.md`` §3 (always-mandatory elements: ABV format/abbreviations, net-
contents standards of fill, proof optional/2×, name/address responsibility
phrase). Citations use the post-2022 Part 5 renumbering.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

# The date the citations below were verified current (the post-2022 Part 5
# reorganization), matching the spirits ruleset source-date convention.
SOURCE_DATE = "2022-01-08"

# ── per-type ABV-presence policy (the cross-type ABV trap) — AC2 ──────────────
# Carried as DATA so the check BRANCHES on it rather than hard-coding an
# ``if beverage_type == …`` chain. label-requirements-by-type.md calls this the
# "#1 false-reject risk": a naïve "ABV must always be present" false-rejects beer
# and ≤14% table wine. The policy is keyed on ``repo.BeverageType`` EXACTLY.
AbvPolicy = Literal[
    "ABV_ALWAYS_REQUIRED",  # distilled spirits §5.65 — ABV mandatory on every label
    "ABV_OPTIONAL_UNLESS_TRIGGER",  # malt beverage §7.65 — optional unless added-flavor
    "ABV_REQUIRED_ABOVE_14_PCT",  # wine §4.36 — required only > 14% ABV
]

ABV_ALWAYS_REQUIRED: AbvPolicy = "ABV_ALWAYS_REQUIRED"
ABV_OPTIONAL_UNLESS_TRIGGER: AbvPolicy = "ABV_OPTIONAL_UNLESS_TRIGGER"
ABV_REQUIRED_ABOVE_14_PCT: AbvPolicy = "ABV_REQUIRED_ABOVE_14_PCT"

# Keyed on the ``submissions.beverage_type`` enum (repo.BeverageType). A type not
# present here has an UNKNOWN policy ⇒ the check defers to REVIEW (never a guess).
ABV_POLICY: dict[str, AbvPolicy] = {
    "DISTILLED_SPIRITS": ABV_ALWAYS_REQUIRED,
    "MALT_BEVERAGE": ABV_OPTIONAL_UNLESS_TRIGGER,
    "WINE": ABV_REQUIRED_ABOVE_14_PCT,
}

# The wine ABV-required threshold (§4.36): ABV is required only ABOVE this %.
WINE_ABV_REQUIRED_THRESHOLD = Decimal("14")

# ── acceptable ABV statement abbreviations (§5.65) ───────────────────────────
# The accepted abbreviation WORDS an ABV statement must carry alongside the
# percentage ("Alc.", "Vol.", "by volume", "abv"). Lowercased for case-insensitive
# matching. Data-driven so a token change is a one-line edit. NOTE: ``%`` is the
# VALUE marker, NOT an abbreviation — it is deliberately NOT in this list, so a bare
# ``45%`` with no accepted word is a malformed (FAIL) statement, and a stray promo
# ``%`` ("30% off") can never spuriously satisfy the abbreviation requirement.
ABV_ABBREVIATION_TOKENS: tuple[str, ...] = ("alc", "vol", "by volume", "abv")

# ── standards of fill (27 CFR 5.203) — AC3 ───────────────────────────────────
# The approved metric container sizes, canonicalized to ``(Decimal, "ml")`` (so a
# "1.75 L" net-contents value, parsed + canonicalized to 1750 ml, is found). Per
# 27 CFR 5.203 (post-2022). Carried as DATA so a §5.203 amendment is a one-line
# edit; net contents are DISCRETE — exact-after-canonicalize, no tolerance band.
STANDARDS_OF_FILL_CITATION = "27 CFR 5.203"

# The post-2020 §5.203 approved metric sizes for distilled spirits (the 2020
# amendment removed the closed list of 1980-era sizes and re-added these). All
# canonicalized to mL. (375 mL, not 350; 200, 100, 50 retained.) A §5.203 change
# is a one-line edit here, never in the check logic.
STANDARDS_OF_FILL: frozenset[tuple[Decimal, str]] = frozenset(
    (Decimal(ml), "ml")
    for ml in (
        "1800",  # 1.8 L
        "1750",  # 1.75 L
        "1000",  # 1 L
        "900",
        "750",
        "720",
        "700",
        "500",
        "375",
        "355",
        "200",
        "100",
        "50",
    )
)

# ── proof ↔ ABV (2×) consistency (§5.65) — AC3 ───────────────────────────────
PROOF_CITATION = "27 CFR 5.65"

# Proof is exactly twice the ABV percentage (90 proof ↔ 45% ABV).
PROOF_PER_ABV = Decimal("2")

# ABV tolerance is ±0.3 pt (§5.65; Research-Findings §1 — the same value Story 3.3
# uses). Proof is 2× ABV, so the proof tolerance scales by 2 ⇒ ±0.6 pt.
ABV_TOLERANCE = Decimal("0.3")
PROOF_TOLERANCE = PROOF_PER_ABV * ABV_TOLERANCE

# ── name/address responsibility (qualifying) phrases (§5.66/§5.67/§5.68) ──────
# The permitted phrases that must immediately precede the name/address. Lowercased
# for case-insensitive matching. A missing phrase is a SOFT signal (addresses
# vary) ⇒ the check REVIEWs, never auto-FAILs (the regulatory doc's "address
# validity flag-REVIEW").
NAME_ADDRESS_CITATION = "27 CFR 5.66"

RESPONSIBILITY_PHRASES: tuple[str, ...] = (
    "bottled by",
    "distilled by",
    "produced by",
    "produced and bottled by",
    "distilled and bottled by",
    "blended by",
    "blended and bottled by",
    "manufactured by",
    "imported by",
    "bottled for",
    "packed by",
    "prepared by",
    "made by",
)
