# Story 3.8: Wine & malt-beverage rulesets at full depth

Status: done

## Story

As a Label Specialist and an evaluator,
I want wine and malt-beverage rulesets as first-class as spirits,
So that the checklist correctly changes by beverage type.

## Acceptance Criteria

1. **(Given)** `engine/rulesets/wine.py` and `engine/rulesets/malt_beverage.py`
   authored from `docs/regulatory-rules-wine.md` and `docs/regulatory-rules-beer.md`
   with their conditional checks (sulfites, coloring, age, country of origin, etc.).
2. **(When a wine or malt-beverage Submission is analyzed, Then)** the Checklist
   contents differ correctly by type (e.g. no ABV demand on a ≤14% table wine;
   malt-beverage ABV conditional).
3. **(And)** the same deterministic check implementations (Stories 3.3–3.7) are
   reused via the ruleset data, **not re-coded per type**. *(FR-15, FR-16, FR-17
   across types)*

## Tasks / Subtasks

- [ ] **Task 1 — Author the WINE ruleset as DATA (AC1, AC2).**
  Create `app/engine/rulesets/wine.py` — a `WINE_RULESET: tuple[Check, ...]`
  authored line-by-line from `docs/regulatory-rules-wine.md` §3 (always-mandatory)
  and §4 (conditional). Every CFR citation is **27 CFR Part 4** (NOT renumbered —
  the wine doc §1 verification note: Part 4 was *not* subject to the 2022 Part 5
  renumbering, so the historical §4.xx citations remain current) + Part 16. Source
  date reflects the wine doc's verification (`2026-06-11`). Map each element to an
  EXISTING strategy (the 3.3–3.7 seam — reuse, not re-code; AC3):
  - `brand_name` → `field_match`, field_key `brand_name` — §4.33.
  - `class_type_designation` → `field_match`, field_key `class_type_designation`
    — §4.21/§4.34. **(NOT `class_type`/HYBRID:** the 3.6 evaluator's keyword
    catalog **and** its VLM prompt are spirits-specific — `_PROMPT` literally says
    "US TTB distilled-spirits label". Routing wine through it would mis-prompt a
    wine label as spirits. The wine doc maps class/type to "field-match + validity
    flag-REVIEW"; the deterministic value match is the reusable part, so wine's
    designation is a `field_match` row. The *validity* judgment is out of scope —
    no wine class catalog exists, and inventing one is "re-coding per type", which
    AC3 forbids.)
  - `grape_varietal` → `field_match`, field_key `grape_varietal` — §4.23/§4.91 (a
    varietal on the brand label IS the class/type designation; matches the
    application "Grape Varietal" field).
  - `alcohol_content` → **TWO** rows (mirroring spirits' value-vs-format split):
    `alcohol_content` (`field_match`, field_key `alcohol_content`, §4.36) for the
    value comparison, AND `abv_format` (`format_checks`, §4.36) for the per-type
    ABV-presence policy — the `ABV_POLICY["WINE"]` branch (`ABV_REQUIRED_ABOVE_14_PCT`)
    is ALREADY authored in `rulesets/format_checks.py` and handled by the
    `_abv_format` evaluator; wine reuses it verbatim (AC2: no ABV demand on a ≤14%
    table wine).
  - `net_contents` → `field_match`, field_key `net_contents` — §4.37.
  - `standards_of_fill` → **`positional`** (flag_only), §4.72. **(NOT
    `format_checks`/`standards_of_fill`:** that handler hard-uses the spirits
    §5.203 table `data.STANDARDS_OF_FILL`. Wine's §4.72 enumerates a DIFFERENT set
    of 25 sizes; reusing the spirits table would be regulatorily wrong. The wine
    doc maps off-table sizes to **flag-REVIEW**. Routing wine standards-of-fill
    through the `positional` strategy yields the honest deferred-REVIEW with the
    §4.72 citation written to the checklist row by the executor — reuse, not
    re-code.)
  - `name_address` → `field_match`, field_key `applicant_name_address` — §4.35.
  - `government_warning` → `government_warning` (DETERMINISTIC), §16.21 — the
    type-agnostic Part 16 evaluator (3.4) is reused verbatim.
  - Conditional §4 flag-only rows (all `positional`, REVIEW-with-citation via the
    flag_only unknown-key path): `appellation_of_origin` (§4.25/§4.34(b)),
    `sulfite_declaration` (§4.32(e)), `fdc_yellow_5` (§4.32(c)),
    `cochineal_carmine` (§4.32(d)), `country_of_origin` (19 CFR 134.11).
  - **NO** `same_field_of_vision` row (wine has no §5.63 co-location rule — wine
    doc §2: "Wine has no 'same field of vision' rule").
  - **NO** `proof_abv_consistency` row (proof is a distilled-spirits concept).

- [ ] **Task 2 — Author the MALT_BEVERAGE ruleset as DATA (AC1, AC2).**
  Create `app/engine/rulesets/malt_beverage.py` — a
  `MALT_BEVERAGE_RULESET: tuple[Check, ...]` authored from
  `docs/regulatory-rules-beer.md` §3 (always-mandatory) and §4 (conditional).
  Citations are **27 CFR Part 7** (post-2022 renumbering — beer doc §1: §7.63
  master, §7.64 brand, §7.65 ABV, §7.66 name/address, §7.70 net contents, Subpart
  I §7.141 class/type) + Part 16. Map to EXISTING strategies (AC3):
  - `brand_name` → `field_match`, field_key `brand_name` — §7.64.
  - `class_type_designation` → `field_match`, field_key `class_type_designation`
    — §7.141 (same reasoning as wine: no malt class catalog; field-match is the
    reusable part).
  - `fanciful_name` → `field_match`, field_key `fanciful_name` — §7.63 (a fanciful
    name, when used, matches the application "Fanciful Name" field).
  - `alcohol_content` → `field_match`, field_key `alcohol_content`, §7.65, AND
    `abv_format` (`format_checks`, §7.65) — the `ABV_POLICY["MALT_BEVERAGE"]`
    branch (`ABV_OPTIONAL_UNLESS_TRIGGER`) is ALREADY authored + handled; malt
    reuses it verbatim (AC2: malt-beverage ABV conditional — absent ⇒ never FAIL,
    REVIEW when the §7.63(a)(3) added-flavor trigger is undeterminable).
  - `net_contents` → `field_match`, field_key `net_contents` — §7.70. **NO**
    `standards_of_fill` row (beer doc §3: "No mandatory standards of fill for malt
    beverages").
  - `name_address` → `field_match`, field_key `applicant_name_address` — §7.66.
  - `government_warning` → `government_warning` (DETERMINISTIC), §16.21 — reused.
  - Conditional §4 flag-only rows (`positional`, REVIEW-with-citation):
    `fdc_yellow_5` (§7.63(b)(1)), `cochineal_carmine` (§7.63(b)(2)),
    `sulfite_declaration` (§7.63(b)(3)), `aspartame_disclosure` (§7.63(b)(4)),
    `country_of_origin` (§7.69 / 19 CFR).
  - **NO** `same_field_of_vision` row (beer doc §2: "No 'same field of vision'
    rule for beer"). **NO** `proof_abv_consistency`. **NO** `standards_of_fill`.

- [ ] **Task 3 — Wire the two rulesets into the lookup (AC2).**
  In `app/engine/rulesets/__init__.py`, replace the empty `()` sentinels:
  `"WINE": WINE_RULESET`, `"MALT_BEVERAGE": MALT_BEVERAGE_RULESET`. Import both at
  the top alongside `DISTILLED_SPIRITS_RULESET`. No change to `get_ruleset`'s
  signature or behavior — `run_checks` already dispatches on `beverage_type`.
  Update the module docstring (drop the "intentionally empty until Story 3.8"
  note).

- [ ] **Task 4 — Register the §4/§7 conditional check_keys in the data-dictionary.**
  Add the new wine + malt `check_key`s to `docs/data-dictionary.md` §6.2.1 (the
  registry is the single index of every `check_key` — project-context "stable
  identifiers"). Add a short note that wine uses Part 4 (un-renumbered) and malt
  uses Part 7 (post-2022), and that conditional rows reuse the `positional`
  strategy. No new table — citations remain canonical in the data modules.

- [ ] **Task 5 — Tests (test-first, AC1–AC3).** `tests/test_wine_malt_rulesets.py`,
  mirroring `tests/test_format_checks.py` seeding helpers:
  - **Wiring:** `get_ruleset("WINE")` and `get_ruleset("MALT_BEVERAGE")` are
    non-empty; every Check's `strategy` resolves via `get_evaluator` to a REAL
    (non-placeholder) evaluator (reuse proof, AC3); every `check_key` is unique
    within its ruleset.
  - **AC2 the checklist differs by type (end-to-end via `run_checks`):**
    - A ≤14% table wine with NO ABV on the label and app ABV ≤14% ⇒ the
      `abv_format` checklist row is **not FAIL** (the trap).
    - A malt beverage with NO ABV ⇒ `abv_format` row is **not FAIL** (REVIEW).
    - A spirits submission's checklist contains `same_field_of_vision` +
      `proof_abv_consistency` + `standards_of_fill`; the wine + malt checklists do
      **not** (the per-type difference is observable in `checklist_items`).
    - The wine checklist contains `grape_varietal`; malt contains `fanciful_name`;
      spirits contains neither.
  - **AC1 the conditional checks are present as DATA:** the wine ruleset carries
    `sulfite_declaration` / `fdc_yellow_5` / `cochineal_carmine` /
    `country_of_origin` / `appellation_of_origin`; malt carries
    `fdc_yellow_5` / `cochineal_carmine` / `sulfite_declaration` /
    `aspartame_disclosure` / `country_of_origin`. Each carries its real Part 4 /
    Part 7 citation (assert the citation string off the Check row).
  - **AC3 reuse, not re-code:** assert no NEW evaluator module is required — i.e.
    every wine/malt `strategy` is one of the already-registered keys
    (`field_match`, `format_checks`, `government_warning`, `positional`); a guard
    test asserts `{c.strategy for c in WINE_RULESET} <= set(EVALUATORS)` (and same
    for malt). A conditional flag-only row routed through `flag_only` returns
    REVIEW with its citation surfaced (the unknown-key deferred path).
  - **Citations-as-data:** assert each ruleset module has NO logic (pure data) and
    the citations live on the Check rows (a structural mirror of the spirits
    ruleset; no `27 CFR` literal needs to appear in any *evaluator* — none is
    edited).
  - **Regression:** the full spirits suite stays green (no spirits behavior change);
    `get_ruleset("UNKNOWN")` still returns `()` (finalize-don't-abort).

- [ ] **Task 6 — Validate.** Run the targeted test file green, then `bash
  scripts/ci.sh` ONCE at the end (format → lint → typecheck → tests).

## Dev Notes

### The shape of this story: DATA authoring, zero new evaluator code

This story is **almost entirely ruleset DATA** — its whole point (AC3) is that the
3.3–3.7 evaluators already do the work and just need per-type Check rows pointed at
them. The dispatch architecture makes this clean:

- `run_checks(conn, submission)` calls `get_ruleset(submission.beverage_type)` and
  dispatches each Check to `get_evaluator(check.strategy)`
  (`app/engine/run_checks.py:98`, `:118`). WINE/MALT are currently `()` sentinels
  in `app/engine/rulesets/__init__.py:23-27`.
- The evaluators are **already per-type aware where it matters**:
  - `_abv_format` branches on `data.ABV_POLICY[beverage_type]`, which already has
    `WINE` (`ABV_REQUIRED_ABOVE_14_PCT`) and `MALT_BEVERAGE`
    (`ABV_OPTIONAL_UNLESS_TRIGGER`) entries
    (`app/engine/rulesets/format_checks.py`). The cross-type ABV trap (AC2) is
    handled the moment a wine/malt `abv_format` Check row exists.
  - `government_warning`, `field_match`, and `flag_only` are type-agnostic.
- The flag_only evaluator's UNKNOWN-check_key path returns a truthful REVIEW
  ("deferred to specialist") — so a conditional flag-only Check (sulfites, etc.)
  authored purely as a DATA row routes through `positional` and produces a
  REVIEW with its CFR citation written to the checklist row by the executor. **No
  new handler code is required** for the conditional checks; they are DATA.

### Why class/type and standards-of-fill are NOT routed to their spirits evaluators

Two deliberate divergences (both faithful to AC3 "reuse, not re-code"):

1. **Class/type → `field_match`, not `class_type` (HYBRID).** The 3.6 `class_type`
   evaluator's catalog (`KEYWORD_GROUPS`: bourbon/gin/rum/…) and its VLM `_PROMPT`
   ("US TTB **distilled-spirits** label") are spirits-specific. Feeding a wine
   label through it would mis-prompt the VLM and never recognize a wine
   designation. The reusable part is the deterministic value comparison
   (app `class_type_designation` ↔ OCR) — i.e. `field_match`. Building a wine/malt
   class catalog would be "re-coding per type", which AC3 forbids, and is out of
   scope (the validity judgment is a flag-REVIEW in both docs).

2. **Wine standards-of-fill → `positional`, not `format_checks`.** The
   `_standards_of_fill` handler hard-uses the spirits §5.203 table; wine's §4.72 is
   a DIFFERENT set of 25 sizes, and malt has **no** standards of fill at all. Wine
   off-table sizes are flag-REVIEW per the doc — so `positional` (deferred REVIEW
   with the §4.72 citation) is both correct and reuse-faithful.

### Regulatory invariants (per-type divergences to encode)

| Concern | Spirits (Part 5) | Wine (Part 4, un-renumbered) | Malt (Part 7, post-2022) |
|---|---|---|---|
| ABV presence | ALWAYS req §5.65 | req only >14% §4.36 | optional unless trigger §7.65 |
| Standards of fill | §5.203 table | §4.72 table → flag-REVIEW | NONE |
| Proof | §5.65 (2×) | n/a | n/a |
| Same field of vision | §5.63 (positional) | NONE (§2) | NONE (§2) |
| Class/type | HYBRID §5.141 | field-match §4.21/4.34 | field-match §7.141 |
| Conditional (flag-only) | §4 (Story 3.7+) | sulfites/FD&C-Y5/cochineal/appellation/country | FD&C-Y5/cochineal/sulfites/aspartame/country |

### Application fields available for field_match (confirmed in `repositories.py`)

`brand_name`, `class_type_designation`, `fanciful_name`, `grape_varietal`,
`wine_appellation`, `alcohol_content`, `net_contents`, `applicant_name_address`.
(field_key for name/address is `applicant_name_address`, mirroring spirits.)

### Hard rules (project-context — do not violate)

- **CFR rules as DATA, never in logic.** Citations live ONLY on the Check rows in
  the two new data modules (mirrors `distilled_spirits.py`). No evaluator is
  edited, so no `27 CFR` literal can leak into logic.
- **Reuse the four centralized contracts.** No new normalize/verdict/rollup paths.
- **VLM-only / no-LLM purity is preserved** because no model-assisted evaluator is
  added or edited (class/type for wine/malt is deterministic `field_match`).
- **snake_case everywhere**; check_keys are stable snake_case identifiers
  registered in the data-dictionary.
- **Do NOT edit `auto-run/`.**

### Files

- CREATE `app/engine/rulesets/wine.py`
- CREATE `app/engine/rulesets/malt_beverage.py`
- EDIT `app/engine/rulesets/__init__.py` (wire the two rulesets into `_RULESETS`)
- EDIT `docs/data-dictionary.md` (§6.2.1 — register the new check_keys)
- CREATE `tests/test_wine_malt_rulesets.py`

### Out of scope

- No UI (Epic 4). No new evaluator modules. No wine/malt class-type catalog or VLM
  prompt. No standards-of-fill table for wine (§4.72 is flag-REVIEW). No changes to
  the spirits ruleset or any 3.3–3.7 evaluator.

## Dev Agent Record

### Context Reference

- Epic: `_bmad-output/planning-artifacts/epics.md` — Story 3.8.
- Regulatory sources: `docs/regulatory-rules-wine.md`, `docs/regulatory-rules-beer.md`,
  `docs/label-requirements-by-type.md` (cross-type ABV trap).
- Reuse seam: `app/engine/checks/__init__.py` (EVALUATORS registry),
  `app/engine/run_checks.py` (dispatch on beverage_type),
  `app/engine/rulesets/distilled_spirits.py` (the authored-ruleset template),
  `app/engine/rulesets/format_checks.py` (ABV_POLICY already per-type).

### Completion Notes

- **dev-story:** wine + malt rulesets authored as pure DATA reusing the 3.3–3.7
  evaluators (no new evaluator strategy, AC3); ABV trap handled by the shared
  `format_checks` evaluator reading `ABV_POLICY`; conditional §4/§7.63(b) flag-only
  rows reuse the `positional` unknown-key⇒honest-REVIEW path; citations Part 4
  (wine, un-renumbered) / Part 7 (malt, post-2022) / Part 16 + 19 CFR 134.11.
- **code-review (this pass):** 1 HIGH patch applied + 2 regression tests.
  - **CR-F1 (HIGH, AC2 trap half-open):** the cross-type ABV trap was defeated by an
    incidental marketing/nutrition `%` on a label that compliantly omits its ABV
    (e.g. a ≤14% table wine printing "100% Estate Grown", or a malt "100% Natural").
    `format_checks._find_abv_pct`'s lone-`%` fallback read that stray token as "ABV
    present", bypassing the per-type absent-policy, then the missing-abbreviation gate
    FAILed it — exactly the false reject AC2 exists to prevent (confirmed via probe:
    wine⇒FAIL, malt⇒FAIL). **FIX:** the lone-uncued-`%` fallback now fires ONLY when
    an accepted ABV abbreviation word (alc/vol/by volume/abv) appears somewhere on the
    label (the legitimate bare `45%` … `Alc./Vol.` case is preserved); with no
    abbreviation word the lone `%` is treated as absent so the per-type policy decides
    (spirits⇒FAIL-on-absence — verdict unchanged; ≤14% wine⇒PASS; malt⇒REVIEW). Patch
    is in the Story-3.5 `format_checks` evaluator (not the new DATA modules) but is the
    activation of the wine/malt `abv_format` paths this story introduces. Spirits
    regression guards (`test_abv_bare_percent_without_abbreviation_fails`,
    `test_abv_abbreviation_not_matched_inside_unrelated_word`) stay green.
  - Triaged non-fixes: wine `appellation_of_origin` is intentionally a flag-only
    `positional` MANUAL row per Task 1 (doc maps appellation to flag-REVIEW; the
    `wine_appellation` field is deferred to the specialist, not silently dropped) — by
    design; "age" conditional is spirits-only (§5.74), correctly absent from Part 4 /
    Part 7 — out of scope; `checklist_items` has no UNIQUE(submission_id, check_key)
    backstop but per-ruleset key uniqueness is test-guarded — pre-existing schema, out
    of scope. All citations verified against the source docs with zero drift.

### File List

- CREATE `app/engine/rulesets/wine.py`
- CREATE `app/engine/rulesets/malt_beverage.py`
- EDIT `app/engine/rulesets/__init__.py`
- EDIT `docs/data-dictionary.md` (§6.2.1.1 wine, §6.2.1.2 malt)
- CREATE `tests/test_wine_malt_rulesets.py`
- EDIT `tests/test_run_checks.py`, `tests/test_pipeline.py` (re-point pre-3.8
  empty-sentinel assertions)
- EDIT `app/engine/checks/format_checks.py` (CR-F1: abbreviation-guard the lone-`%`
  ABV fallback — close the AC2 incidental-`%` false-FAIL)
