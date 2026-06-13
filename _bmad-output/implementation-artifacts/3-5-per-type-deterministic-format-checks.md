---
baseline_commit: c00d92dea980abab228640ea2c38af8897881a8e
---

# Story 3.5: Per-type deterministic format checks

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want rule-bound formats validated per beverage type,
so that ABV / net-contents / standards-of-fill and conditional requirements are checked correctly **without false rejects** (the cross-type ABV trap respected).

## Acceptance Criteria

1. **AC1 — `engine/checks/format_checks.py` validates deterministically, NO LLM.**
   **Given** `app/engine/checks/format_checks.py` (deterministic; **no model involved**) reading the cross-commodity matrix carried as ruleset **data** (`docs/label-requirements-by-type.md`)
   **When** it validates a submission
   **Then** the **alcohol-content statement format** (acceptable `Alc.`/`Vol.`/`%` abbreviations + ABV-presence policy), the **net-contents format + standards-of-fill lookup**, and the **name/address qualifying (responsibility) phrase** are checked deterministically against the submission's OCR text — **no LLM call anywhere** (an AST import-scan + source-token guard asserts it, mirroring `test_government_warning.py`'s no-LLM guards). *(FR-15; project-context determinism taxonomy)*

2. **AC2 — The ABV false-reject trap is respected per beverage type.**
   **Given** the per-type ABV-presence policy (spirits = ALWAYS required §5.65; table wine ≤14% = optional if "table/light" §4.36; malt-beverage = optional unless an added-flavor trigger fires §7.65)
   **When** the ABV-format check runs
   **Then** a **spirits** submission **missing an ABV statement → FAIL** (with citation), while a **≤14% table-wine** submission without ABV is **NOT failed** and a **malt-beverage** without ABV is **NOT failed** unless its trigger applies — a naïve "ABV must always be present" must NOT false-reject beer or table wine. *(FR-15; label-requirements-by-type.md "Cross-Type ABV Trap")*

3. **AC3 — Standards-of-fill lookup + proof↔ABV consistency.**
   **Given** the net-contents value
   **When** the standards-of-fill check runs
   **Then** **"750 mL" passes** standards of fill (27 CFR 5.203 approved-size table, as data); an **off-standard size FAILs with citation**; and when **proof is present** it must equal **2 × ABV** (within tolerance) or → **FAIL** (the proof↔ABV consistency rule). *(FR-15; regulatory-rules-distilled-spirits.md §3, label-requirements-by-type.md §2c)*

4. **AC4 — An unevaluable conditional Check → REVIEW with explanation, never a guess.**
   **Given** a conditional/format Check that cannot be evaluated from the available data (e.g. proof shown but ABV unreadable; net-contents unit not isolable from the OCR text; a beverage type whose policy is unknowable from the label)
   **When** the check runs
   **Then** it emits **REVIEW with an explanatory detail**, never a fabricated PASS or FAIL — "when unsure, REVIEW, never FAIL" (the costliest error is a false reject). *(FR-15; approach.md §4 verdict model; project-context "recommend, don't decide")*

## Tasks / Subtasks

- [x] **Task 1 — Per-type format rules as ruleset DATA (AC1, AC2, AC3)**
  - [x] Create `app/engine/rulesets/format_checks.py` (DATA — distinct from the `checks/` logic), pure data + types only (imports nothing from the executor/evaluators, mirroring `rulesets/government_warning.py`). Carry, with `cfr_citation` + `source_date` per item:
    - **ABV-presence policy per beverage type** — a mapping `BeverageType → AbvPolicy` (`ALWAYS_REQUIRED` for `DISTILLED_SPIRITS` §5.65; `OPTIONAL_UNLESS_TRIGGER` for `MALT_BEVERAGE` §7.65; `REQUIRED_ABOVE_14_PCT` for `WINE` §4.36). This is the data form of the cross-type ABV trap — the check branches on it, never hard-codes the policy.
    - **Acceptable ABV abbreviation tokens** — `("alc", "vol", "%")` and the `alc./vol.`/`% alc/vol`/`% by volume` accepted forms (so the format regex is data-driven, greppable).
    - **Standards of fill** — the 27 CFR 5.203 approved metric sizes as a frozenset of canonical `(Decimal, "ml")` values (include `750 ml`, `1.75 l`→`1750 ml`, `1 l`, `500 ml`, `375 ml`, `200 ml`, `100 ml`, `50 ml`, etc. per §5.203; canonicalize to `ml`). `STANDARDS_OF_FILL_CITATION = "27 CFR 5.203"`.
    - **Proof↔ABV ratio** = `Decimal("2")` with the §5.65 tolerance (reuse `ABV_TOLERANCE` semantics; proof tolerance = `2 × ABV_TOLERANCE` so a ±0.3-pt ABV maps to ±0.6-pt proof). `PROOF_CITATION = "27 CFR 5.65"`.
    - **Name/address responsibility phrases** — the §5.66/§5.67/§5.68 permitted qualifying phrases (`bottled by`, `distilled by`, `produced by`, `imported by`, `blended by`, `manufactured by`, …) as a tuple, lowercased for case-insensitive matching. `NAME_ADDRESS_CITATION = "27 CFR 5.66"`.
  - [x] Beverage-type values MUST match `repo.BeverageType` exactly (`DISTILLED_SPIRITS`/`WINE`/`MALT_BEVERAGE`). No CFR citation literal lives in `checks/format_checks.py` — every citation written travels off the Check row or this data module (AC1/AC4 guard).

- [x] **Task 2 — `app/engine/checks/format_checks.py` deterministic evaluator (AC1, AC2, AC3, AC4)**
  - [x] Register the evaluator on Story 3.2's dispatch seam under the `format_checks` strategy (one line in `app/engine/checks/__init__.py`, bottom-of-module, mirroring `field_match`/`government_warning`). **No executor edit.** No model import/construction (AC1 AST + source guards).
  - [x] Dispatch by `check.check_key` (one evaluator, several format checks share the `format_checks` strategy — keyed sub-logic, like a small registry inside the module):
    - `abv_format` (§5.65): resolve the per-type ABV policy from the DATA map keyed on `ctx.submission.beverage_type`. If ABV is **required** for that type and **no acceptable ABV token** is found in the OCR text → **FAIL** (citation from the Check). If present, verify the **format** (a `<number>%` with at least one accepted `alc`/`vol`/`%` token nearby) → PASS; malformed-but-present → FAIL with the deviation; **not required for this type and absent** → **PASS/NA** (NOT a FAIL — the trap). A trigger that cannot be evaluated (malt-beverage added-flavor unknowable) → **REVIEW**.
    - `standards_of_fill` (§5.203): `normalize.parse_numeric(net_contents_from_ocr, "net_contents")` → `(Decimal, unit)`; canonicalize to `ml`; membership-test against the approved-sizes frozenset → **PASS**; a parseable off-standard size → **FAIL** with citation; **unparseable / no same-unit token** → **REVIEW** (AC4, never a guessed FAIL).
    - `proof_abv_consistency` (§5.65): only when BOTH an ABV and a `proof` token are present in the OCR text → require `abs(proof − 2 × abv) <= proof_tolerance` → PASS else FAIL. ABV present but proof absent → **NA/PASS** (proof is optional — never FAIL on its absence). Proof present but ABV unreadable → **REVIEW** (AC4).
    - `name_address_format` (§5.66): scan the OCR text for any DATA responsibility phrase immediately preceding address-like text → **PASS**; none found → **REVIEW** (a missing responsibility phrase is a soft signal the human confirms — addresses vary; NOT an auto-FAIL — false-reject guard). *(Keep this REVIEW, per the regulatory doc's "address validity flag-REVIEW".)*
  - [x] The check reads ONLY `ctx.ocr_text` (the deterministic engine's input) + `ctx.submission` application fields — **never** a model, never the LLM extraction. (OCR-only — VLM purity is moot here because no model is touched, but explicitly do not read `ctx.scratch["llm_extraction"]`/`llm_results`.)
  - [x] Use the centralized `normalize`/`parse_numeric` for all value comparisons (never inline). `Decimal` for proof/ABV/size math (never float).
  - [x] Writes **NO `field_comparisons` row** (these are format/policy checks against the statute + label text, not an app-vs-OCR field comparison — that is Story 3.3's `field_match`). Provenance travels in the returned `CheckResult.detail`; `run_checks` writes the single `checklist_items` row.

- [x] **Task 3 — Add the format Checks to the spirits ruleset as DATA (AC1, AC2, AC3)**
  - [x] Append three Check rows to `DISTILLED_SPIRITS_RULESET` in `app/engine/rulesets/distilled_spirits.py`, each `check_type="DETERMINISTIC"`, `strategy="format_checks"`, with their real citations: `abv_format` (§5.65), `standards_of_fill` (§5.203), `proof_abv_consistency` (§5.65). (Optionally `name_address_format` (§5.66) — but note it returns REVIEW; include it only if it adds value beyond the existing `name_address` field_match. Decide during dev; if included it is DETERMINISTIC/format.) These **augment** the existing `field_match` checks (which compare VALUES) — the comment already left in the ruleset ("Story 3.5's per-type FORMAT checks … augment, not replace") is now realized.
  - [x] Register each new `check_key` in `docs/data-dictionary.md` §6.2.1 (the registry table) so every `check_key` written to `checklist_items` resolves to an entry (project-context "stable identifiers" rule).

- [x] **Task 4 — Tests (`tests/test_format_checks.py`) (all ACs)**
  - [x] **Registration:** `get_evaluator("format_checks")` is the new evaluator.
  - [x] **AC2 — the ABV trap (the headline tests):** spirits missing ABV → FAIL; spirits with `"45% Alc./Vol."` → PASS; **≤14% table wine** (`beverage_type=WINE`, `alcohol_content` absent, label carries "table wine") without ABV → **NOT FAIL** (PASS/NA); **malt beverage** without ABV → **NOT FAIL** (PASS/NA); malt beverage with the added-flavor trigger unknowable → REVIEW.
  - [x] **AC3 — standards of fill:** `"750 mL"` → PASS; `"680 mL"` (off-standard — note `700 mL` IS an approved §5.203 size, corrected during dev) → FAIL with `5.203` citation surfaced; `"1.75 L"` → PASS (canonicalized); a net-contents OCR with no isolable same-unit token → REVIEW.
  - [x] **AC3 — proof↔ABV:** `45% Alc./Vol. (90 Proof)` → PASS (90 = 2×45); `45% (80 Proof)` → FAIL; ABV present, no proof → PASS/NA (proof optional); proof present, ABV unreadable → REVIEW.
  - [x] **AC1 — no-LLM guards:** AST import-scan (no `adapters.llm`/`openai`/`anthropic`/`google.genai`/`langchain`) + a source-token scan (`get_llm_adapter(`, `llm_results`, `get_latest_llm`), mirroring `test_government_warning.py`. **CFR-as-data guard:** `27 CFR` does not appear inlined in `checks/format_checks.py` (it lives on the Check rows + the data module).
  - [x] **AC4 — REVIEW not guess:** every unevaluable path returns REVIEW with a non-empty explanatory `detail`; assert NO format check ever FAILs purely on absence of an optional element.
  - [x] **No `field_comparisons` row** written by this evaluator (assert count 0). **Integration through `run_checks`:** a spirits submission now carries the three new `DETERMINISTIC` format rows + their verdicts, `engine_verdict` rolls up via `verdict.rollup`; the brief's sample-label FAIL fixture (missing name/address + Gov Warning) still rolls up FAIL.
  - [x] Offline by construction (seeded OCR text only; no real/fake OCR or LLM call).

- [x] **Task 5 — Validate + finalize**
  - [x] `bash scripts/ci.sh` (HOST venv per CLAUDE.md): format → lint → mypy (story scope) → pytest, all green (no regressions — re-point any stale 3.2-era all-placeholder roll-up assertions that now see a real `format_checks` verdict, preserving their intent, as Stories 3.3/3.4 did). Update File List + Change Log + Completion Notes (record the chosen approved-size set + proof/ABV tolerance defaults so Diane can tune). Set Status → review and `sprint-status.yaml` `3-5-…: review`.

## Dev Notes

### ⚠️ Depends on Stories 3.1, 3.2 (+ 3.3/3.4 patterns) — implement on the existing seam
3.5 registers a `format_checks` evaluator behind Story **3.2**'s dispatch seam (`run_checks` + `Check.strategy="format_checks"` + `insert_checklist_item`) and uses Story **3.1**'s `normalize`/`parse_numeric`. It reuses the **3.4 pattern** (deterministic, no-LLM, CFR-as-data ruleset module + AC1/AC4 guards) and the **3.3 pattern** (numeric tolerance via `parse_numeric`, `Decimal` math). Do not start until 3.1–3.2 are done (they are). [Source: Stories 3.1–3.4; sprint-status]

### Scope boundary (what 3.5 IS and is NOT)
- **IS:** the deterministic per-type FORMAT checks — ABV-statement format + the per-type ABV-presence policy (the cross-type trap), net-contents format + standards-of-fill lookup, proof↔ABV (2×) consistency, and the name/address responsibility-phrase presence; the format rules as ruleset DATA; and the new spirits Check rows under `format_checks`.
- **IS NOT:** the **value** comparison of those fields (app↔OCR, Story **3.3** `field_match` — 3.5 augments, does not replace it); the **hybrid class/type validity** check + any LLM (Story **3.6**); the flag-only positional / same-field-of-vision check (Story **3.7**); the **wine & malt rulesets at full depth** (Story **3.8** — 3.5 builds the per-type ABV-policy DATA + evaluator so 3.8 can wire wine/malt Checks to the same `format_checks` strategy with no new logic); and **font / type-size** verification (explicitly out of scope per regulatory-rules-distilled-spirits.md §6 — mm cannot be recovered from a photo). [Source: epics.md Stories 3.3–3.8; regulatory-rules-distilled-spirits.md §6]

### The cross-type ABV trap is the heart of this story (AC2)
`label-requirements-by-type.md` calls the ABV rule "the **#1 false-reject risk** in the whole engine": a naïve "ABV must always be present" check **false-rejects beer and ≤14% table wine**, two compliant cases. The engine MUST branch on `beverage_type` BEFORE evaluating ABV presence — and that branch is carried as **DATA** (the `BeverageType → AbvPolicy` map), never hard-coded `if beverage_type == …` chains in the check. When the trigger is genuinely unknowable (malt-beverage added-flavor), prefer **REVIEW** over a FAIL. The spirits ALWAYS-required case is the only hard-FAIL-on-absence path. [Source: label-requirements-by-type.md "Cross-Type ABV Trap" + §2; regulatory-rules-distilled-spirits.md §3]

### Standards of fill — a deterministic table lookup (AC3)
27 CFR 5.203 enumerates approved metric container sizes (750 mL, 1.75 L, 1 L, 500 mL, 375 mL, 200 mL, 100 mL, 50 mL, …). The check `parse_numeric`s the net-contents value, canonicalizes the unit to `ml` (1.75 L → 1750 ml), and membership-tests the approved set → PASS; a parseable off-standard size → FAIL with the §5.203 citation; an unparseable / missing-unit value → REVIEW (AC4 — never guess). Carry the approved set as DATA so a §5.203 amendment is a one-line edit. Net contents are DISCRETE — exact-after-canonicalize, no tolerance band. [Source: regulatory-rules-distilled-spirits.md §3; label-requirements-by-type.md §2c; data-dictionary §net_contents]

### Proof ↔ ABV consistency (AC3) — only when BOTH are present
Proof is **optional** for spirits and, when shown, must equal **2 × ABV** (90 proof ↔ 45% ABV). Check this ONLY when both an ABV and a `proof` token are in the OCR text: `abs(proof − 2×abv) <= proof_tolerance` → PASS else FAIL. Proof absent → never FAIL (it is optional); proof present but ABV unreadable → REVIEW. Use `Decimal` (parse_numeric returns Decimal; `proof` is a known unit in `normalize._UNIT_PATTERNS`) — never float. Proof tolerance = `2 × ABV_TOLERANCE` (the ±0.3-pt ABV maps to ±0.6-pt proof). [Source: regulatory-rules-distilled-spirits.md §3 ("proof is optional … must be distinguished"); label-requirements-by-type.md §2c; normalize.py _UNIT_PATTERNS includes "proof"]

### Format vs value — two distinct checks on the same field (do not conflate)
The `alcohol_content`/`net_contents` Checks already route to Story 3.3's `field_match` (does the LABEL value MATCH the APPLICATION value, ±tolerance). Story 3.5 adds a SEPARATE concern: is the label statement's FORMAT/POLICY correct regardless of the application value (is ABV present at all for this type; is the size an approved standard; is proof internally consistent). Both are mandatory; they answer different questions and write different checklist rows. The new Check rows are NEW `check_key`s (`abv_format`/`standards_of_fill`/`proof_abv_consistency`), distinct from the existing `alcohol_content`/`net_contents` FIELD_MATCH keys. [Source: regulatory-rules-distilled-spirits.md §3 POC-check-type column ("presence + format deterministic; value field-match"); distilled_spirits.py existing comment]

### No `field_comparisons` row (like the Gov Warning)
These format checks compare the label against the STATUTE / a policy table, not an application field, so they write NO `field_comparisons` row — exactly like Story 3.4's Government Warning. Provenance lives in `CheckResult.detail`; `run_checks` writes the single `checklist_items` row. (Story 3.3's `field_match` owns `field_comparisons`.) [Source: Story 3.4 Task 3; approach.md §4]

### CFR-as-data + no-LLM (AC1/AC4) — the same guards as 3.4
project-context anti-patterns: "CFR text hard-coded in Python" and a deterministic check touching an LLM. The format rules + citations live in `rulesets/format_checks.py` DATA (and on the Check rows); the check logic imports them. Tests assert (a) no model import/construction (AST + token scan) and (b) `27 CFR` is not inlined in `checks/format_checks.py`. Mirror `test_government_warning.py`'s guard tests exactly. [Source: project-context "CFR rules live as data" + anti-patterns + determinism taxonomy; Story 3.4 Task 4]

### Previous story intelligence (3.1–3.4 + done 2.x)
- **3.1**: `normalize(value, field_key)` + `parse_numeric(value, field_key) -> (Decimal, unit)` — `net_contents`/`alcohol_content` are the NUMERIC_FIELD_KEYS; `proof` is a recognized unit. Import; never re-implement. [Source: app/normalize.py]
- **3.2**: the `{strategy: evaluator}` seam, `CheckContext` (`ocr_text` via `repo.get_submission_ocr_text`; `submission`), `CheckResult`, and `run_checks` (writes the `checklist_items` row, rolls up via `verdict.rollup`). Register `format_checks`; no executor change. [Source: Story 3.2; app/engine/run_checks.py, app/engine/checks/__init__.py]
- **3.3**: the numeric `parse_numeric` + `Decimal`-tolerance pattern; the named-tunable-constant discipline (flag defaults for Diane). [Source: Story 3.3; app/engine/checks/field_match.py]
- **3.4**: the deterministic-no-LLM + CFR-as-data ruleset-module pattern, the AC1/AC4 guard tests, and the "REVIEW when undeterminable, never a silent PASS/FAIL" posture. [Source: Story 3.4; app/engine/checks/government_warning.py, app/engine/rulesets/government_warning.py]
- House style: `from __future__ import annotations`, type hints, `Literal` aliases, raw SQL only in `app/db/`, tests mirror `app/`, offline by construction, ruff line 100. [Source: app/engine/*, app/db/repositories.py]

### Project Structure Notes
- New/edited: `app/engine/rulesets/format_checks.py` (NEW — per-type format rules as DATA), `app/engine/checks/format_checks.py` (NEW — deterministic evaluator), `app/engine/checks/__init__.py` (UPDATE — register `format_checks`), `app/engine/rulesets/distilled_spirits.py` (UPDATE — add the format Check rows), `docs/data-dictionary.md` §6.2.1 (UPDATE — register the new `check_key`s), `tests/test_format_checks.py` (NEW). Matches the architecture tree (`engine/checks/format_checks.py # per-type deterministic format checks (FR-15)`). [Source: architecture.md engine tree]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.5] — story statement + ACs (per-type format checks; the ABV false-reject trap; standards-of-fill + proof↔ABV; unevaluable conditional → REVIEW).
- [Source: docs/label-requirements-by-type.md] — the cross-commodity matrix (§1 master table), the **Cross-Type ABV Trap** (the #1 false-reject risk; per-type ABV rule + tolerances), §2c spirits subtleties (standards of fill, proof optional/2×, conditional statements).
- [Source: docs/regulatory-rules-distilled-spirits.md §3] — always-mandatory elements with POC-check-type column (ABV format/abbreviations, net-contents format + standards of fill, name/address responsibility phrase); §6 font/dimension OUT of scope.
- [Source: docs/database-schema.md §1.6 `checklist_items` (check_key/cfr_citation/check_type=DETERMINISTIC/verdict/detail)] — the write target (no field_comparisons row).
- [Source: docs/data-dictionary.md §6.2.1 check_key registry, §net_contents/§alcohol_content] — register the new check_keys; field formats.
- [Source: app/normalize.py (parse_numeric + units incl. "proof"), app/verdict.py (PASS/REVIEW/FAIL/rollup), app/engine/run_checks.py + dispatch seam (3.2), app/engine/checks/government_warning.py + rulesets/government_warning.py (3.4 pattern)] — the contracts/seams to build on.
- [Source: _bmad-output/project-context.md] — "CFR rules live as data" + anti-pattern "CFR text hard-coded in Python"; determinism taxonomy (no LLM here); "recommend, don't decide" / REVIEW-when-unsure; `normalize` is the only normalizer; pipeline-is-the-only-writer of `checklist_items`; snake_case everywhere.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Amelia — Senior Software Engineer, bmad-agent-dev)

### Debug Log References

- `_TOKEN_RE` originally ended in `\b`, which fails to match `45%` (a `%` is a non-word char, so the `%`→`\b` boundary before a space does not fire). Replaced the trailing `\b` with a `(?![a-z])` negative-lookahead so unit tokens like `%`/`ml`/`proof` match without requiring a word boundary. Verified with a throwaway `c:\tmp\dbg.py` (`_TOKEN_RE.finditer` / `_find_numeric_for_unit` / `_find_net_contents_ml`).
- `parse_numeric` returns only the FIRST numeric token of a string; ABV/proof co-occur in one OCR blob (`"45% Alc./Vol. (90 Proof)"`). Added `_find_numeric_for_unit` (a `finditer` over `_TOKEN_RE` that re-parses each candidate through `normalize.parse_numeric` and returns the first whose canonical unit matches), so the proof and the ABV are isolated from the same text without a second normalizer.
- Test data collisions: a shared `tmp_path` db filename + a fixed `ttb_id` tripped the `submissions.ttb_id` UNIQUE constraint across calls in one test. Added module counters `_DB_SEQ` (unique db file per `_make_db`) and `_TTB_SEQ` (unique `ttb_id` per `_insert_submission`).
- Standards-of-fill premise fix: `700 mL` IS an approved §5.203 size (post-2020 amendment) — the off-standard test was changed to `680 mL`; `700`/`1800` were retained/added in `STANDARDS_OF_FILL`.
- AC1 CFR-as-data guard caught three `27 CFR` literals leaking into `checks/format_checks.py` (two docstring mentions + one section-divider comment); all reworded to `§…` / "the CFR-citation literal" so the citation lives only on the Check rows + the data module.

### Completion Notes List

- **Seam-only, no executor edit.** Registered `format_checks` on Story 3.2's `{strategy: evaluator}` dispatch seam (one line at the bottom of `app/engine/checks/__init__.py`). The evaluator dispatches by `check.check_key` to a small in-module `_HANDLERS` registry (`abv_format`/`standards_of_fill`/`proof_abv_consistency`/`name_address_format`); an unknown key → REVIEW (never a guess).
- **Cross-type ABV trap as DATA (AC2).** The per-type ABV-presence policy is a `dict[str, AbvPolicy]` keyed EXACTLY on `repo.BeverageType` (`DISTILLED_SPIRITS`→ALWAYS, `MALT_BEVERAGE`→OPTIONAL_UNLESS_TRIGGER, `WINE`→REQUIRED_ABOVE_14_PCT). The check branches on the looked-up policy — no `if beverage_type == …` chain. Spirits-absent → FAIL is the ONLY hard-FAIL-on-absence path; table wine ≤14% absent → PASS; malt absent → PASS; an unknown/un-keyed type → REVIEW.
- **Tunable defaults Diane can change in ONE place** (all in `app/engine/rulesets/format_checks.py`, the DATA module):
  - `STANDARDS_OF_FILL` (canonical mL): **1800, 1750, 1000, 900, 750, 720, 700, 500, 375, 355, 200, 100, 50** — the post-2020 §5.203 metric set. Net contents are DISCRETE — exact-after-canonicalize, no tolerance band.
  - `WINE_ABV_REQUIRED_THRESHOLD = 14` (§4.36 — ABV required only ABOVE 14%).
  - `ABV_TOLERANCE = 0.3` pt; `PROOF_PER_ABV = 2`; ⇒ `PROOF_TOLERANCE = 0.6` pt (proof scales the ABV tolerance by 2×).
  - `ABV_ABBREVIATION_TOKENS = ("alc", "vol", "by volume", "abv")` (CR-F1: `%` removed — it is the value marker, not an abbreviation); `RESPONSIBILITY_PHRASES` (bottled/distilled/produced/imported/… by).
- **`name_address_format` handler exists but is NOT wired to a spirits Check row** (the "decide during dev" option). The existing `name_address` `field_match` row already covers name/address; the format handler is kept for Story 3.8 to reuse on wine/malt with no new logic, and would emit REVIEW (soft signal) if wired.
- **No `field_comparisons` row** — these are statute/policy checks (like the Gov Warning), not app-vs-OCR field comparisons. Provenance is in `CheckResult.detail`; `run_checks` writes the single `checklist_items` row. Test asserts a `field_comparisons` count of 0.
- **AC1/AC4 guards** mirror `test_government_warning.py`: an AST import-scan (no model adapter/LLM lib import) + a source-token scan + a `27 CFR`-not-inlined assertion on `checks/format_checks.py`.
- **Validation (HOST venv, per CLAUDE.md):** ruff format + lint clean; mypy clean on all 4 story-scope files (`Success: no issues found in 4 source files`); `pytest -q` → **344 passed, 1 skipped** (28 tests in `test_format_checks.py` after the +6 code-review regression tests; no regressions). The pre-existing `auto-run/orchestrate.py:562` mypy finding is OUTSIDE story scope (the orchestrator harness is walled off per CLAUDE.md and was not touched).

### File List

- `app/engine/rulesets/format_checks.py` (NEW) — per-type format rules as pure DATA (ABV policy map, ABV abbreviation tokens, §5.203 standards-of-fill set, proof↔ABV ratio + tolerances, responsibility phrases; citations + `SOURCE_DATE`).
- `app/engine/checks/format_checks.py` (NEW) — deterministic no-LLM evaluator; `_HANDLERS` registry dispatched by `check_key`; `_TOKEN_RE` + `_scan_unit_tokens` + cue-aware `_find_abv_pct` / `_find_net_contents_ml` + `_find_numeric_for_unit` (proof) + word-boundary `_has_abv_abbreviation` helpers (CR-F2/F3).
- `tests/test_format_checks.py` (NEW) — 28 tests across AC1–AC4 + registration + run_checks integration + no-`field_comparisons` + no-LLM/CFR-as-data guards (22 from dev + 6 code-review regressions: bare-`%` FAIL, abbreviation-not-inside-unrelated-word, promo-`%`-not-read-as-ABV, wine-unreadable-app-ABV→REVIEW, serving-size-not-grabbed, negative-size→REVIEW).
- `app/engine/checks/__init__.py` (UPDATE) — register `EVALUATORS["format_checks"]`.
- `app/engine/rulesets/distilled_spirits.py` (UPDATE) — three new DETERMINISTIC Check rows (`abv_format` §5.65, `standards_of_fill` §5.203, `proof_abv_consistency` §5.65) under `strategy="format_checks"`.
- `docs/data-dictionary.md` §6.2.1 (UPDATE) — register the three new `check_key`s; CR-F5 corrected the `alcohol_content`/`net_contents`/`name_address` rows `HYBRID`→`FIELD_MATCH` to match the `distilled_spirits.py` ruleset DATA.

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-13 | Story 3.5 drafted — deterministic per-type format checks on the 3.2 seam: per-type ABV-presence policy as DATA (the cross-type false-reject trap), net-contents format + 27 CFR 5.203 standards-of-fill lookup, proof↔ABV (2×) consistency, name/address responsibility-phrase presence; the §5.65/§5.203/§5.66 rules as ruleset DATA; new spirits Check rows under `format_checks`; AC1 no-LLM + AC4 CFR-as-data guards; unevaluable conditional → REVIEW. Status → ready-for-dev. |
| 2026-06-13 | Story 3.5 implemented (test-first) — `format_checks` DATA module + deterministic evaluator registered on the 3.2 seam (no executor edit); three spirits Check rows; data-dictionary §6.2.1 updated. ABV trap branches on a DATA policy map; `STANDARDS_OF_FILL` post-2020 §5.203 set; `PROOF_TOLERANCE=0.6`. `name_address_format` handler present but unwired (3.8 reuse). 22 new tests; 338 passed / 1 skipped; ruff + story-scope mypy clean. Status → review. |
| 2026-06-13 | Code review (Amelia, bmad-code-review; Blind Hunter + Edge Case Hunter + Acceptance Auditor) — 6 findings patched, all probe-confirmed before patching: **F1** `%` removed from `ABV_ABBREVIATION_TOKENS` (it is the value marker, not an abbreviation; the dead bare-`45%`→FAIL branch is now reachable). **F2** `_has_abv_abbreviation` switched to word-boundary matching (no more `REVOLVER`/`CALCIUM` substring false-positives). **F3** cue-aware extraction: `_find_abv_pct` prefers a `%` near an alcohol cue (`alc`/`vol`/`abv`/`alcohol`) so a promo `30% OFF` is no longer scavenged as ABV; `_find_net_contents_ml` prefers a `net`-cued size, drops `ml<=0`, falls back to the LAST size token (no first-token serving-size grab). **F4** malt-beverage ABV-absent → REVIEW (was PASS; the §7.65 added-flavor trigger is not determinable from the label). **F6** wine with unreadable application ABV + no label ABV → REVIEW (was a silent PASS). **F5** data-dictionary §6.2.1 corrected `alcohol_content`/`net_contents`/`name_address` rows `HYBRID`→`FIELD_MATCH` to match the ruleset DATA. +6 regression tests (28 in file; 344 passed / 1 skipped total). F7 (OCR-noise hardening) + F9 (`STANDARDS_OF_FILL` extra-sizes citation) deferred to `deferred-work.md`. Status → done. |
