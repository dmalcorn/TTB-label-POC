"""Class/type designation catalog + conflict groups, as DATA (Story 3.6, AC1/AC3).

The hybrid class/type-designation check (``app/engine/checks/class_type.py``)
*imports* this data and must never inline a catalog keyword or the CFR citation in
its logic — "CFR rules live as data; never hard-coded in check logic" (project-
context; AC1). A grep for ``27 CFR`` inside ``checks/class_type.py`` is a finding.

Pure data + types only — imports nothing from the engine executor/evaluators, so a
citation string can never leak into logic from here (mirrors
``rulesets/government_warning.py`` + ``rulesets/format_checks.py``).

**Recognition is keyword-based.** A designation is "recognized" when its normalized
text CONTAINS one of the catalog base-class keywords below. The catalog is seeded
from the TTB BAM Vol. 2, Ch. 4 (Class & Type Designation) chart — the enumerated
catalog of valid spirits classes/types (``ref-docs/chapter4.pdf``; summarized in
``docs/regulatory-rules-distilled-spirits.md`` §1) — pragmatically reduced to the
base classes for the POC. A §5.141 / BAM amendment is a one-line edit here.

**Conflict detection is group-based (AC3).** Each keyword maps to a mutually-
exclusive base-class GROUP. Two recognized designations CONFLICT when they resolve
to DIFFERENT groups (bourbon vs vodka); same-group variants ("straight bourbon" vs
"bourbon") do NOT conflict. The check reads :data:`KEYWORD_GROUPS`; it never hard-
codes the conflicting pairs.
"""

from __future__ import annotations

# The CFR citation for the class/type designation, as DATA (AC1). The ONLY place
# this literal lives alongside the spirits ruleset Check row (which carries the same
# citation as its own data). Format per project-context: ``"27 CFR <part>.<section>"``.
CFR_CITATION = "27 CFR 5.141"

# The date the citation was verified current (the post-2022 Part 5 reorganization,
# matching the spirits ruleset source-date convention). A future amendment edits here.
SOURCE_DATE = "2022-01-08"

# ── recognized base-class keyword → mutually-exclusive group (AC1, AC3) ───────
# Keys are lowercase keywords matched as substrings against the NORMALIZED
# designation text (``app/normalize.py`` collapses case/punctuation first). Values
# are the conflict group: two recognized designations in DIFFERENT groups conflict.
# Multi-word keys (e.g. "single malt") are checked as phrases. Ordering does not
# matter — recognition is membership, conflict is the set of distinct groups present.
#
# Groups (the mutually-exclusive base classes of 27 CFR Part 5 / BAM Ch.4):
#   whisky  — whisky/whiskey/bourbon/rye/scotch/corn whisky/single malt
#   gin     — gin
#   brandy  — brandy/cognac
#   rum     — rum
#   agave   — tequila/mezcal
#   vodka   — vodka
#   liqueur — liqueur/cordial
KEYWORD_GROUPS: dict[str, str] = {
    "bourbon": "whisky",
    "rye whisky": "whisky",
    "rye whiskey": "whisky",
    "corn whisky": "whisky",
    "corn whiskey": "whisky",
    "scotch": "whisky",
    "single malt": "whisky",
    "whiskey": "whisky",
    "whisky": "whisky",
    "gin": "gin",
    "cognac": "brandy",
    "brandy": "brandy",
    "rum": "rum",
    "tequila": "agave",
    "mezcal": "agave",
    "vodka": "vodka",
    "liqueur": "liqueur",
    "cordial": "liqueur",
}

# Convenience: the recognized keyword set (for "is this designation recognized?").
RECOGNIZED_CLASS_TYPES: frozenset[str] = frozenset(KEYWORD_GROUPS)

# ── conflict groups: the MUTUALLY-EXCLUSIVE base classes (AC3) ────────────────
# Only these groups participate in cross-label conflict detection. A submission
# whose labels carry two DIFFERENT groups from this set is an objective class/type
# contradiction (bourbon vs vodka). ``liqueur`` is deliberately EXCLUDED: a
# liqueur/cordial is a statement of composition that legitimately NAMES its base
# spirit ("Coffee Liqueur with Rum", "Sloe Gin Liqueur", "Whisky Liqueur") — that
# co-occurrence is valid, not a conflict, so the liqueur group never triggers a
# FAIL. (DATA, so the policy is a one-line edit — never hard-coded in check logic.)
CONFLICT_GROUPS: frozenset[str] = frozenset(KEYWORD_GROUPS.values()) - {"liqueur"}
