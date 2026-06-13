"""The distilled-spirits ruleset, authored as DATA (Story 3.2, AC1/AC4).

Authored from ``docs/regulatory-rules-distilled-spirits.md`` §2/§3/§5 — the
**always-mandatory** spirits elements (§3), the Government Warning (Part 16), and
the same-field-of-vision positional check (§5.63). CFR citations use the
**post-2022** Part 5 renumbering exactly as printed on the TTB checklist (class/
type is §5.141, not the old §5.35).

This is the canonical spirits ruleset — there is **no** ``rulesets`` DB table; the
data module IS the ruleset (architecture tree; database-schema §1.6/§5). The
executor writes the *results* to ``checklist_items``.

**Scope (3.2):** only the always-mandatory elements + Gov Warning + same-field-of-
vision. The §4 conditional/flag-only elements (sulfites, country-of-origin, age
statements, …) are **Story 3.7** and are deliberately NOT enumerated here.

``strategy`` names the evaluator each Check dispatches to (the ``run_checks``
registry). In 3.2 every strategy resolves to the honest ``REVIEW`` placeholder;
Stories 3.3–3.7 register the real evaluator under the same key with no executor
change:
  - ``field_match``        → Story 3.3 (field match with tolerance bands)
  - ``government_warning`` → Story 3.4 (exact Gov-Warning verification)
  - ``format_checks``      → Story 3.5 (per-type deterministic format checks)
  - ``class_type``         → Story 3.6 (hybrid class/type with a VLM, capped REVIEW)
  - ``positional``         → flag-REVIEW positional check (same field of vision)
"""

from __future__ import annotations

from app.engine.rulesets.base import Check

# The date the citations below were verified current (the post-2022 Part 5
# reorganization, as printed on the TTB distilled-spirits checklist PDF).
_SOURCE_DATE = "2022-01-08"

# The always-mandatory spirits elements (§3) + the Government Warning (Part 16) +
# the same-field-of-vision positional check (§2/§5.63), each a DATA row with its
# real CFR citation. Citations are taken from
# docs/regulatory-rules-distilled-spirits.md (post-2022 renumbering).
DISTILLED_SPIRITS_RULESET: tuple[Check, ...] = (
    Check(
        check_key="brand_name",
        label="Brand name",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 5.64",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="brand_name",
    ),
    Check(
        check_key="class_type_designation",
        label="Class/type designation",
        check_type="HYBRID",
        cfr_citation="27 CFR 5.141",
        source_date=_SOURCE_DATE,
        strategy="class_type",
        field_key="class_type_designation",
    ),
    Check(
        # The matchable fields route to the Story-3.3 ``field_match`` evaluator
        # (application value vs OCR/LLM-extracted value, three-band tolerance), so
        # check_type is FIELD_MATCH: the field-match component is what the engine
        # confirms here. Story 3.5's per-type FORMAT checks (ABV format/abbreviation,
        # metric standards-of-fill) are a SEPARATE concern added under their own
        # strategy later — they augment, not replace, this comparison.
        check_key="alcohol_content",
        label="Alcohol content",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 5.65",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="alcohol_content",
    ),
    Check(
        check_key="net_contents",
        label="Net contents",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 5.70",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="net_contents",
    ),
    Check(
        # NOTE: check_key ("name_address") and field_key ("applicant_name_address")
        # are DIFFERENT namespaces ON PURPOSE — the check identifier vs. the
        # application field it compares. Both resolve in docs/data-dictionary.md
        # (check_key in §6.2.1; field_key as a matchable field). Do NOT "harmonize"
        # them: Story 3.3's field_match joins on field_key, so renaming would break
        # the comparison link.
        check_key="name_address",
        label="Name and address",
        check_type="FIELD_MATCH",
        cfr_citation="27 CFR 5.66",
        source_date=_SOURCE_DATE,
        strategy="field_match",
        field_key="applicant_name_address",
    ),
    Check(
        check_key="government_warning",
        label="Government Warning",
        check_type="DETERMINISTIC",
        cfr_citation="27 CFR 16.21",
        source_date=_SOURCE_DATE,
        strategy="government_warning",
    ),
    Check(
        check_key="same_field_of_vision",
        label="Same field of vision (brand, class/type, alcohol content)",
        check_type="MANUAL",
        cfr_citation="27 CFR 5.63",
        source_date=_SOURCE_DATE,
        strategy="positional",
    ),
)
