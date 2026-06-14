"""The wine ruleset, authored as DATA (Story 3.8, AC1/AC2/AC3).

Authored from ``docs/regulatory-rules-wine.md`` (27 CFR **Part 4** + Part 16) —
the always-mandatory wine elements (§3), the §4 CONDITIONAL flag-only elements
(appellation / sulfites / FD&C Yellow No. 5 / cochineal-carmine / country of
origin), and the Government Warning (Part 16). Like the spirits ruleset this is
canonical DATA — there is **no** ``rulesets`` DB table; the data module IS the
ruleset (architecture tree; database-schema §1.6/§5). The executor writes the
*results* to ``checklist_items``.

**Reuse, not re-code (AC3).** Every Check below points its ``strategy`` at an
ALREADY-registered evaluator from Stories 3.3–3.7 (the ``run_checks`` dispatch
seam) — no new evaluator module is introduced for wine. The per-type behaviour
that DOES differ is encoded as DATA the shared evaluators already read:

  - **ABV trap (§4.36).** ``alcohol_content`` field-match + the ``abv_format``
    DETERMINISTIC check route to the SAME ``format_checks`` evaluator the spirits
    ruleset uses; that evaluator already branches on ``beverage_type`` via
    ``ABV_POLICY`` (wine = required-only-above-14% with the band-dependent
    tolerance), so a ≤14% table wine with no ABV is NOT failed — no code here.

  - **Two deliberate divergences from the spirits rows** (faithful to "reuse,
    don't re-code"):
      1. **class/type → ``field_match`` (NOT ``class_type``/HYBRID).** The Story
         3.6 ``class_type`` evaluator's keyword groups + VLM prompt are
         spirits-specific ("US TTB distilled-spirits label"); routing wine
         through it would mis-prompt, and authoring a wine catalog would be
         re-coding. Wine's class/type is matched as a field (§4.21/§4.34); the
         designation-*validity* judgment is the specialist's (the doc marks it
         hybrid/flag-REVIEW).
      2. **standards-of-fill → ``positional`` (NOT ``format_checks``).** The
         spirits ``_standards_of_fill`` hard-uses the §5.203 table; wine's §4.72
         table is a DIFFERENT set, and the doc treats an off-table size as a
         flag-REVIEW. Until a wine §4.72 table is added as DATA, the size check
         is surfaced as a flag-only REVIEW rather than mis-applying the spirits
         table.

**No spirits-only rows.** Wine carries NO ``same_field_of_vision`` (§5.63 is
spirits-only — wine has no field-of-vision rule, doc §2) and NO
``proof_abv_consistency`` (proof is a spirits concept).

**Part numbering.** Part 4 was **not** caught by the 2022 modernization
renumbering (T.D. TTB-176 deferred the Part 4 rewrite), so the historical §4.xx
citations remain current (doc §1 verification note). The country-of-origin
statement is CBP-governed (**19 CFR 134.11**, doc §3) — its citation is recorded
truthfully as a 19 CFR reference, not forced into 27 CFR.
"""

from __future__ import annotations

from app.engine.rulesets.base import Check

# The date every citation below was verified current against the local
# authoritative PDFs (eCFR text, current to 6/09/2026) — see the line-by-line
# verification note in docs/regulatory-rules-wine.md §1.
_SOURCE_DATE = "2026-06-11"

WINE_RULESET: tuple[Check, ...] = (
    # ── always-mandatory elements (doc §3) ───────────────────────────────────
    Check(
        check_key="brand_name",
        label="Brand name",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 4.33",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="brand_name",
    ),
    Check(
        # Divergence (1): wine class/type is a FIELD match (§4.21/§4.34), NOT the
        # spirits HYBRID ``class_type`` evaluator (whose prompt/catalog are
        # spirits-specific). The designation-validity judgment is the specialist's.
        check_key="class_type_designation",
        label="Class/type designation",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 4.21",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="class_type_designation",
    ),
    Check(
        # A grape varietal on the brand label IS the class/type designation
        # (doc §3, §4.23); matched against the application's "Grape Varietal" field.
        check_key="grape_varietal",
        label="Grape varietal designation",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 4.23",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="grape_varietal",
    ),
    Check(
        # Value match against the application field; the per-type ABV POLICY
        # (required-only-above-14%) lives in the ``abv_format`` DETERMINISTIC row.
        check_key="alcohol_content",
        label="Alcohol content",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 4.36",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="alcohol_content",
    ),
    Check(
        check_key="net_contents",
        label="Net contents",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 4.37",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="net_contents",
    ),
    Check(
        # NOTE: check_key ("name_address") vs field_key ("applicant_name_address")
        # are different namespaces ON PURPOSE (see the spirits ruleset note) —
        # field_match joins on field_key, so do NOT harmonize them.
        check_key="name_address",
        label="Name and address",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 4.35",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="applicant_name_address",
    ),
    # ── per-type DETERMINISTIC format check: the ABV trap (doc §6, §4.36) ─────
    # Routes to the SAME ``format_checks`` evaluator as spirits; that evaluator
    # reads ABV_POLICY[beverage_type] — wine = required-only-above-14% with the
    # band-dependent (±1.0 / ±1.5) tolerance — so a ≤14% table wine without ABV
    # is NOT failed. No per-type code here; the policy is DATA the evaluator owns.
    Check(
        check_key="abv_format",
        label="Alcohol content statement format",
        check_type="DETERMINISTIC",
        cfr_citation="27 CFR 4.36",
        source_date=_SOURCE_DATE,
        strategy="format_checks",
    ),
    # ── standards of fill (doc §4, §4.72) ────────────────────────────────────
    # Divergence (2): wine's §4.72 table differs from the spirits §5.203 table,
    # and an off-table size is a flag-REVIEW; surfaced via ``positional`` (an
    # unknown flag-only key → honest REVIEW) rather than mis-applying §5.203.
    Check(
        check_key="standards_of_fill",
        label="Net contents standard of fill",
        check_type="MANUAL",
        cfr_citation="27 CFR 4.72",
        source_date=_SOURCE_DATE,
        strategy="positional",
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
    # ── §4 CONDITIONAL flag-only elements (doc §4) ───────────────────────────
    # Each reuses the Story-3.7 ``positional`` strategy: an unhandled flag-only
    # check_key degrades to an honest REVIEW (finalize-don't-abort), deferring the
    # trigger/judgment to the specialist. Citations travel as DATA.
    Check(
        check_key="appellation_of_origin",
        label="Appellation of origin",
        check_type="MANUAL",
        cfr_citation="27 CFR 4.25",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
    Check(
        check_key="sulfite_declaration",
        label="Sulfite declaration",
        check_type="MANUAL",
        cfr_citation="27 CFR 4.32(e)",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
    Check(
        check_key="fdc_yellow_5",
        label="FD&C Yellow No. 5 declaration",
        check_type="MANUAL",
        cfr_citation="27 CFR 4.32(c)",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
    Check(
        check_key="cochineal_carmine",
        label="Cochineal extract / carmine declaration",
        check_type="MANUAL",
        cfr_citation="27 CFR 4.32(d)",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
    Check(
        # CBP-governed (doc §3); its citation is recorded truthfully as 19 CFR,
        # not forced into 27 CFR.
        check_key="country_of_origin",
        label="Country of origin",
        check_type="MANUAL",
        cfr_citation="19 CFR 134.11",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
)
