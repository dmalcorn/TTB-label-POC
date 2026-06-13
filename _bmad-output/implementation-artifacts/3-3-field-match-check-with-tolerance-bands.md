---
baseline_commit: c00d92dea980abab228640ea2c38af8897881a8e
---

# Story 3.3: Field Match check with tolerance bands

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want application fields compared to OCR values with normalization tolerance,
so that real mismatches FAIL, soft differences go to REVIEW, and incidental case/punctuation differences PASS.

## Acceptance Criteria

1. **AC1 — `engine/checks/field_match.py` compares the matchable fields using `normalize()`.**
   **Given** `app/engine/checks/field_match.py` using `normalize()` (Story 3.1)
   **When** it compares **brand name**, **alcohol content**, **net contents**, and **name/address**
   **Then** for each it pairs the APPLICATION value (from `submissions`) against the OCR/LLM-EXTRACTED value and produces a `field_comparisons` row + a per-check verdict. *(FR-14)*

2. **AC2 — Three-band verdict via normalization + tolerance.**
   **Given** a field comparison
   **When** it is evaluated
   **Then** a **normalized match → PASS** (both raw values retained), a **near-miss / OCR-confidence-below-threshold → REVIEW**, and a **substantive mismatch → FAIL**. *(FR-14, approach.md §4 verdict model)*

3. **AC3 — The two canonical cases hold.**
   **Given** the SM-C2 + cross-type-ABV cases
   **When** field match runs
   **Then** **"STONE'S THROW" vs "Stone's Throw" → PASS** (incidental case/punctuation), and **application ABV 45% vs label 40% → FAIL** (substantive numeric mismatch beyond tolerance). *(FR-14; project-context "zero false-FAIL" SM-C2)*

4. **AC4 — `field_comparisons` rows carry both raw values, a `match_status`, a `similarity`, and normalized provenance.**
   **Given** a written `field_comparisons` row
   **When** it is inspected
   **Then** it stores the raw `application_value` and `extracted_value`, a `match_status` (`MATCH`/`MISMATCH`/`MISSING`/`UNVERIFIABLE`), a `similarity` (0–1), and **exactly one** source FK (`source_ocr_result_id` **or** `source_llm_result_id`) — the normalized provenance the review UI's `v_field_comparisons` view derives `extracted_source` from. The owning `checklist_items` row links back via `field_comparison_id`. *(database-schema §1.5; FR-14)*

## Tasks / Subtasks

- [ ] **Task 1 — `app/engine/checks/field_match.py` evaluator (AC1, AC2, AC3)**
  - [ ] Implement an evaluator on Story 3.2's dispatch seam: `field_match(check: Check, ctx: CheckContext) -> CheckResult`. Register it under the `field_match` strategy so the spirits-ruleset checks `brand_name`, `alcohol_content`, `net_contents`, `name_address` route here (their `Check.field_key` names the `submissions` column: `brand_name`, `alcohol_content`, `net_contents`, `applicant_name_address`). **No executor edit** — registration only (the seam's whole point).
  - [ ] Resolve the APPLICATION value: `getattr(ctx.submission, check.field_key)`. Resolve the EXTRACTED value (see Task 2). `normalize()` **both** with the field's `field_key` (Story 3.1) before comparing — never inline normalization.
  - [ ] **Verdict bands (AC2):**
    - **Text fields** (`brand_name`, `applicant_name_address`): normalized **equality ⇒ `MATCH`/PASS** (similarity `1.0`) — this is what makes `"STONE'S THROW" == "Stone's Throw"` PASS. Else compute `similarity` (stdlib `difflib.SequenceMatcher(None, a, b).ratio()` over the normalized strings — **no new dependency**): `similarity ≥ REVIEW_FLOOR ⇒ MISMATCH`/**REVIEW** (near-miss, the false-reject safety valve); below ⇒ `MISMATCH`/**FAIL** (substantive).
    - **Numeric fields** (`alcohol_content`, `net_contents`): `parse_numeric()` (Story 3.1) both sides → `(Decimal, unit)`. Same unit **and** `abs(app − ocr) ≤ tolerance ⇒ `MATCH`/PASS`; otherwise `MISMATCH`/**FAIL** (the `45 % vs 40 %` case). Unparseable extracted side ⇒ `UNVERIFIABLE`/**REVIEW**.
  - [ ] **Tolerance + thresholds as named, tunable constants** (with rationale comments): `ABV_TOLERANCE = Decimal("0.3")` (±0.3 percentage-point — Research-Findings §1, cited in `regulatory-rules-distilled-spirits.md` §3); a `net_contents` tolerance (recommend exact-after-normalize, i.e. `0`, since standards of fill are discrete — confirm); `REVIEW_FLOOR` similarity (recommend `0.85`); `OCR_CONFIDENCE_FLOOR` (recommend `0.50`). Flag these defaults in Completion Notes so Diane can tune.
  - [ ] **Low-confidence ⇒ REVIEW (AC2):** if the source OCR row's `confidence` is below `OCR_CONFIDENCE_FLOOR`, force the verdict to **REVIEW** (cannot trust the extraction) even on an apparent match — the cross-type-trap safety valve. (Does not apply to LLM-sourced values.)
  - [ ] **Missing extracted value ⇒ `MISSING`/REVIEW** (defer to human; never FAIL on absence — that would be a false reject). Application value missing ⇒ `UNVERIFIABLE`/REVIEW.

- [ ] **Task 2 — Extracted-value resolution (OCR-only and LLM-assisted paths) (AC1, AC4)**
  - [ ] **LLM-assisted path (preferred when present):** if a structured extraction exists (the Story 2.5 `llm_stage` stashes it at `ctx.scratch["llm_extraction"]` and persists it as the `OK` `llm_results.result_text` JSON), parse that JSON for `check.field_key` → `extracted_value`; set `source_llm_result_id` to that `llm_results` row id.
  - [ ] **OCR-only fallback:** with no LLM extraction, derive the extracted value from the submission's OCR text. Realistic POC heuristic: confirm presence/fuzzy-locate the normalized application value within the normalized OCR text (per FR-14 "compare the application value against the OCR-extracted label text"); set `source_ocr_result_id` to the contributing OCR row (recommend the highest-`confidence` `ocr_results` row for the submission). Keep this heuristic honest — when it cannot isolate a value, emit `MISSING`/REVIEW rather than guessing.
  - [ ] **At most one source FK** (the table's CHECK enforces it). Record the raw, un-normalized values in `application_value`/`extracted_value` (the UI shows raw; normalization is comparison-only).

- [ ] **Task 3 — `field_comparisons` write helper (AC4)**
  - [ ] Add `insert_field_comparison(conn, submission_id, *, field_key, application_value, extracted_value, match_status, similarity=None, source_ocr_result_id=None, source_llm_result_id=None) -> int` to `app/db/repositories.py` (raw SQL stays in `app/db/` — the Data boundary; mirror `insert_ocr_result`/`insert_checklist_item` style). The evaluator calls it and returns the new id in `CheckResult.field_comparison_id`; Story 3.2's `run_checks` writes the `checklist_items` row with that link. **field_comparisons is written here — this is the story that owns it** (3.1 created the table, 3.2 deferred the writes to here).
  - [ ] Respect the schema CHECKs: `match_status ∈ {MATCH,MISMATCH,MISSING,UNVERIFIABLE}`, `similarity` NULL or 0–1, at most one source FK.

- [ ] **Task 4 — Tests (`tests/test_field_match.py`) (all ACs)**
  - [ ] **SM-C2 (AC3):** `"STONE'S THROW"` vs `"Stone's Throw"` (straight + curly apostrophe) ⇒ PASS / `MATCH`. Add the broader zero-false-FAIL class (case, whitespace, trailing punctuation, NFKC) all PASS.
  - [ ] **Cross-type ABV trap (AC3):** app `"45% Alc./Vol."` vs label `"40% Alc./Vol."` ⇒ FAIL; app `"45%"` vs label `"45.2%"` (within ±0.3) ⇒ PASS; app `"45%"` vs `"45.5%"` (outside) ⇒ FAIL/REVIEW per band.
  - [ ] **Bands:** near-miss text (high-but-not-1.0 similarity) ⇒ REVIEW; substantive mismatch ⇒ FAIL; missing extracted ⇒ REVIEW (`MISSING`); low OCR confidence ⇒ REVIEW.
  - [ ] **Provenance (AC4):** row has both raw values, a `match_status`, a `similarity`, exactly one source FK; the LLM path sets `source_llm_result_id`, the OCR path sets `source_ocr_result_id`.
  - [ ] **Integration:** through Story 3.2's `run_checks`, a spirits submission's `brand_name`/`alcohol_content`/`net_contents`/`name_address` checks now produce real verdicts + linked `field_comparison_id`s, and `engine_verdict` rolls up accordingly. Offline by construction (seeded OCR text / fake LLM extraction — no real OCR/LLM call).

- [ ] **Task 5 — Validate + finalize**
  - [ ] `ruff check` + `ruff format` (line length 100); full `pytest` green (no regressions). Update File List + Change Log + Completion Notes (record the chosen threshold/tolerance defaults).

## Dev Notes

### ⚠️ Depends on Stories 3.1 and 3.2 — implement both first
3.3 imports `normalize()`/`parse_numeric()` (Story **3.1**), writes the `field_comparisons` table (created in **3.1**), and **registers its evaluator behind the dispatch seam built in Story 3.2** (`run_checks` + `Check.strategy="field_match"` + `insert_checklist_item`). Do not start 3.3 until 3.1 and 3.2 are done. [Source: Stories 3.1, 3.2; sprint-status]

### Scope boundary (what 3.3 IS and is NOT)
- **IS:** the `field_match` evaluator (one of the four check strategies), its three-band tolerance logic, the `field_comparisons` writes (+ the write helper), and the matchable fields **brand name, alcohol content, net contents, name/address**.
- **IS NOT:** the Government Warning check (deterministic, Story **3.4**), per-type format checks (Story **3.5**), the **hybrid class/type validity** check (Story **3.6** — note class/type's *field-match component* can reuse this evaluator, but its regulatory-validity judgment + LLM is 3.6), flag-only/positional checks (Story **3.7**), and the rulesets/executor framework (Story **3.2**, already built). [Source: epics.md Stories 3.4–3.7; approach.md §4 strategy matrix]

### The verdict model + why tolerance exists (the spine of this story)
**False rejects are the costliest error** (needless correction cycles). Tolerance + the REVIEW band exist specifically to curb them — the SM-C2 "STONE'S THROW" over-strict-match case and the cross-type ABV trap. `normalize()` is what collapses incidental case/punctuation to **PASS**; the similarity band sends genuine-but-soft differences to **REVIEW** (defer to human); only substantive mismatches **FAIL**. When unsure, the engine says REVIEW, never FAIL. [Source: approach.md §4 "PASS/REVIEW/FAIL verdict model" + "False rejects are the costliest error"; project-context determinism taxonomy]

### `match_status` (data) vs `verdict` (advisory) — both, distinctly
`field_comparisons.match_status` (`MATCH/MISMATCH/MISSING/UNVERIFIABLE`) is the *comparison outcome* the UI renders; the `checklist_items.verdict` (`PASS/REVIEW/FAIL/NA`) is the *advisory engine band*. They are related but separate columns — derive both. A `MATCH` ⇒ PASS; `MISSING`/`UNVERIFIABLE` ⇒ REVIEW; `MISMATCH` ⇒ FAIL or REVIEW by the similarity/confidence band. Do **not** collapse them into one. [Source: database-schema §1.5, §1.6, §3.2]

### Extracted-value source: LLM extraction first, OCR text fallback (be honest about the heuristic)
The extracted side has two sources, and the provenance FK records which:
- **LLM-assisted:** Story 2.5's `llm_stage` already runs `extract_fields` and stashes the structured JSON at `ctx.scratch["llm_extraction"]` (and the `OK` `llm_results.result_text`). Parse it per `field_key`; set `source_llm_result_id`.
- **OCR-only:** no LLM → fuzzy-locate the value in the submission's OCR text (`repo.get_submission_ocr_text`), set `source_ocr_result_id` to the contributing row.
Per-field extraction from a raw OCR blob is inherently heuristic — when you cannot isolate a value confidently, emit `MISSING`/REVIEW (honest) rather than a fabricated match. This is consistent with the "recommend, don't decide" posture and the anti-pattern against serving misleading results. [Source: app/pipeline/llm.py:116-120; approach.md §3 pipeline; database-schema §1.5 provenance]

### Class/type is a field-match too (forward note, do not build here)
`class_type_designation` is a maker-entered application field, so its presence/value is a normal field-match (this evaluator can serve it). Its *regulatory validity* (is "Kentucky Straight Bourbon Whiskey" a valid designation?) is the hybrid rules+LLM check capped at REVIEW — **Story 3.6**. 3.3 implements the four AC-named fields only; wiring class/type's field-match component is 3.6's call. [Source: approach.md §4 "Class/type and the Government Warning"; epics.md Story 3.6]

### Tolerance / threshold values (named constants, tunable)
- **ABV ±0.3 percentage-point** — Research-Findings §1, cited in `regulatory-rules-distilled-spirits.md` §3 ("±0.3-pt tolerance"). Use `Decimal`, not float (Story 3.1's `parse_numeric` returns `Decimal`).
- **net_contents** — standards of fill are discrete; recommend exact-after-normalize (tolerance `0`) so `750 mL` vs `750 ml` PASS but `750` vs `700` FAIL. Confirm against `docs/data-dictionary.md` §`net_contents` / §5.203 standards.
- **similarity REVIEW_FLOOR ≈ 0.85**, **OCR_CONFIDENCE_FLOOR ≈ 0.50** — starting points; expose as module constants and note them for tuning. These are POC defaults, not regulation. [Source: regulatory-rules-distilled-spirits.md §3; approach.md §4]

### Previous story intelligence (3.1, 3.2 + done 2.x)
- **3.1**: `normalize(value, field_key)` (canonical string) + `parse_numeric(value, field_key) -> (Decimal, unit)` for numeric keys; the `field_comparisons` table + `v_field_comparisons` view. Import; never re-implement normalization or re-create the table. [Source: Story 3.1]
- **3.2**: the `{strategy: evaluator}` dispatch seam, `CheckContext`/`CheckResult`, `run_checks` (writes `checklist_items` from the returned `CheckResult`, including `field_comparison_id`), and `insert_checklist_item`. 3.3 plugs in the `field_match` evaluator with no executor change. [Source: Story 3.2]
- **2.5**: `ctx.scratch["llm_extraction"]` + the `OK` `llm_results.result_text` JSON — the LLM-assisted extracted-value source; absent when the model layer is off (OCR-only path still works). [Source: app/pipeline/llm.py:116-120]
- House style: `from __future__ import annotations`, `Literal` aliases, `Decimal` for numerics, raw SQL only in `app/db/`, tests mirror `app/`, offline by construction, ruff line 100, type hints. [Source: app/db/repositories.py, app/contracts.py]

### Project Structure Notes
- New/edited: `app/engine/checks/field_match.py` (NEW), `app/db/repositories.py` (UPDATE — `insert_field_comparison`), the Story-3.2 strategy registry (UPDATE — register `field_match`), `tests/test_field_match.py` (NEW), `tests/test_run_checks.py` / `tests/test_pipeline.py` (UPDATE — integration). Paths match the architecture tree (`engine/checks/field_match.py # uses normalize.py (FR-14)`). [Source: architecture.md line 347]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.3] — story statement + ACs (field-match using normalize; three-band tolerance; the two canonical cases).
- [Source: docs/approach.md §3 (pipeline ANALYSIS/VERIFY), §4 (four strategies, PASS/REVIEW/FAIL model, false-reject rationale, class/type vs Gov Warning)] — where field-match sits and why tolerance + REVIEW exist.
- [Source: docs/database-schema.md §1.5 `field_comparisons` (columns, `match_status`/`similarity`/source-FK CHECKs, `v_field_comparisons` view), §1.6 `checklist_items` (`field_comparison_id` link), §3.2 engine-verdict] — the write target + provenance.
- [Source: docs/data-dictionary.md §`brand_name`/`alcohol_content`/`net_contents`/`applicant_name_address` (matchable fields), §6.x] — the four fields' formats/specs the comparator must honor.
- [Source: docs/regulatory-rules-distilled-spirits.md §3] — the ABV ±0.3-pt tolerance + acceptable ABV/net-contents formats.
- [Source: app/normalize.py + app/verdict.py (3.1), app/engine/run_checks.py + dispatch seam (3.2), app/pipeline/llm.py (2.5), app/db/repositories.py] — the contracts/seams to build on.
- [Source: _bmad-output/project-context.md] — `normalize` is the only normalizer (anti-pattern: inline normalization); field comparison is vertical (raw app value above raw OCR value); determinism taxonomy; pipeline-is-the-only-writer of `field_comparisons`; SM-C2 zero-false-FAIL.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-13 | Story 3.3 drafted — `engine/checks/field_match.py` evaluator on the 3.2 dispatch seam: normalize-based three-band tolerance (PASS/REVIEW/FAIL), ABV ±0.3-pt + similarity/confidence bands, `field_comparisons` writes with normalized provenance (OCR vs LLM source), and the SM-C2 + cross-type-ABV guard tests. Status → ready-for-dev. |
