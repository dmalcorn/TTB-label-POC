"""The malt-beverage (beer) ruleset, authored as DATA (Story 3.8, AC1/AC2/AC3).

Authored from ``docs/regulatory-rules-beer.md`` (27 CFR **Part 7**, post-2022
renumbering + Part 16) — the always-mandatory malt-beverage elements (§3), the
§7.63(b) CONDITIONAL flag-only ingredient disclosures (FD&C Yellow No. 5 /
cochineal-carmine / sulfites / aspartame / country of origin), and the
Government Warning (Part 16). Like the spirits ruleset this is canonical DATA —
there is **no** ``rulesets`` DB table; the data module IS the ruleset. The
executor writes the *results* to ``checklist_items``.

**Reuse, not re-code (AC3).** Every Check points its ``strategy`` at an
ALREADY-registered evaluator (the 3.3–3.7 dispatch seam) — no new evaluator is
introduced for malt. Per-type behaviour that differs is encoded as DATA the
shared evaluators already read:

  - **ABV trap (§7.65 / §7.63(a)(3)).** ``alcohol_content`` field-match + the
    ``abv_format`` DETERMINISTIC check route to the SAME ``format_checks``
    evaluator; that evaluator branches on ``beverage_type`` via ``ABV_POLICY``
    (malt = optional-unless-trigger), so a malt label without ABV is surfaced as
    REVIEW, never FAIL — no code here.

  - **class/type → ``field_match`` (NOT the spirits HYBRID ``class_type``).** The
    Story 3.6 evaluator's catalog/prompt are spirits-specific; malt's class/type
    (or fanciful name + statement of composition) is matched as a field
    (§7.141 / Subpart I); the validity judgment is the specialist's.

  - **fanciful_name field check (§7.63).** When a fanciful name is used it must
    match the application "Fanciful Name" field — a plain ``field_match`` row
    (wine has no equivalent mandatory fanciful-name element).

**No spirits/wine-only rows.** Malt carries NO ``standards_of_fill`` (Part 7 has
**no** standards of fill for malt beverages, doc §3), NO ``proof_abv_consistency``
(proof is spirits-only), and NO ``same_field_of_vision`` (§5.63 is spirits-only;
Part 7 has no across-element co-location rule, doc §2).

**Part numbering.** Section numbers are the **post-2022** Part 7 renumbering
(T.D. TTB-176): mandatory-info master §7.63; brand §7.64; ABV §7.65; name/address
§§7.66–7.68; country of origin §7.69; net contents §7.70; class/type Subpart I
(§§7.141–7.147). The conditional disclosures are §7.63(b)(1)–(4).
"""

from __future__ import annotations

from app.engine.rulesets.base import Check

# The date every citation below was verified current against the local Part 7 /
# Part 16 PDFs (eCFR text, current to 6/09/2026) — see the section-by-section
# verification note in docs/regulatory-rules-beer.md §1.
_SOURCE_DATE = "2026-06-11"

MALT_BEVERAGE_RULESET: tuple[Check, ...] = (
    # ── always-mandatory elements (doc §3) ───────────────────────────────────
    Check(
        check_key="brand_name",
        label="Brand name",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 7.64",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="brand_name",
    ),
    Check(
        # Class/type as a FIELD match (Subpart I, §7.141), NOT the spirits HYBRID.
        check_key="class_type_designation",
        label="Class/type designation",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 7.141",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="class_type_designation",
    ),
    Check(
        # A fanciful name, when used, must match the application "Fanciful Name"
        # field (doc §3, §7.63). Wine has no equivalent mandatory element.
        check_key="fanciful_name",
        label="Fanciful name",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 7.63",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="fanciful_name",
    ),
    Check(
        # Value match; the per-type ABV POLICY (optional-unless-trigger) lives in
        # the ``abv_format`` DETERMINISTIC row that routes to ``format_checks``.
        check_key="alcohol_content",
        label="Alcohol content",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 7.65",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="alcohol_content",
    ),
    Check(
        check_key="net_contents",
        label="Net contents",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 7.70",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="net_contents",
    ),
    Check(
        # check_key vs field_key are different namespaces ON PURPOSE (see spirits).
        check_key="name_address",
        label="Name and address",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 7.66",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="applicant_name_address",
    ),
    # ── per-type DETERMINISTIC format check: the ABV trap (doc §5, §7.65) ─────
    # Same ``format_checks`` evaluator as spirits/wine; ABV_POLICY[MALT_BEVERAGE]
    # = optional-unless-trigger, so absence ⇒ REVIEW (not FAIL). Policy is DATA.
    Check(
        check_key="abv_format",
        label="Alcohol content statement format",
        check_type="DETERMINISTIC",
        cfr_citation="27 CFR 7.65",
        source_date=_SOURCE_DATE,
        strategy="format_checks",
    ),
    # ── Government Warning (Part 16; applies to all types ≥0.5% ABV) ──────────
    Check(
        check_key="government_warning",
        label="Government Warning",
        check_type="DETERMINISTIC",
        cfr_citation="27 CFR 16.21",
        source_date=_SOURCE_DATE,
        strategy="government_warning",
    ),
    # ── §7.63(b) CONDITIONAL flag-only ingredient disclosures (doc §4) ────────
    # Each reuses the Story-3.7 ``positional`` strategy: an unhandled flag-only
    # check_key degrades to an honest REVIEW, deferring the trigger to the
    # specialist. Citations travel as DATA. Note: Part 7 has NO general
    # coloring-material/caramel disclosure (doc §4) — only the four items below.
    Check(
        check_key="fdc_yellow_5",
        label="FD&C Yellow No. 5 declaration",
        check_type="MANUAL",
        cfr_citation="27 CFR 7.63(b)(1)",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
    Check(
        check_key="cochineal_carmine",
        label="Cochineal extract / carmine declaration",
        check_type="MANUAL",
        cfr_citation="27 CFR 7.63(b)(2)",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
    Check(
        check_key="sulfite_declaration",
        label="Sulfite declaration",
        check_type="MANUAL",
        cfr_citation="27 CFR 7.63(b)(3)",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
    Check(
        check_key="aspartame_disclosure",
        label="Aspartame disclosure",
        check_type="MANUAL",
        cfr_citation="27 CFR 7.63(b)(4)",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
    Check(
        # CBP-governed (§7.69 + 19 CFR 102/134); the Part 7 anchor §7.69 is the
        # truthful 27 CFR citation for malt's country-of-origin element.
        check_key="country_of_origin",
        label="Country of origin",
        check_type="MANUAL",
        cfr_citation="27 CFR 7.69",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
)
