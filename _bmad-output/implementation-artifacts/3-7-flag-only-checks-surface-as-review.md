---
baseline_commit: 9dc90575f14e30f79701201a5247f2ebd1aac41b
---

# Story 3.7: Flag-only checks surface as REVIEW

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want checks that can't be reliably auto-decided from a photo surfaced as REVIEW with an explanation,
so that the tool never guesses a PASS or FAIL it can't justify.

## Acceptance Criteria

1. **AC1 — Flag-only checks always emit REVIEW with an explanatory note, never PASS or FAIL.**
   **Given** `app/engine/checks/flag_only.py` registered on Story 3.2's dispatch seam under the `positional` strategy (the existing `same_field_of_vision` Check row in `distilled_spirits.py` already points here — `check_type="MANUAL"`, §5.63)
   **When** it evaluates the Same Field of Vision spatial-inference check (brand name + alcohol content + class/type co-location), a "separate and apart" placement requirement, or severely degraded text
   **Then** it returns **REVIEW** with a non-empty explanatory `detail` — **never PASS and never FAIL** — because the requirement cannot be confirmed from a flat photo (OCR bounding boxes alone cannot guarantee one 40%-of-circumference viewable face). *(FR-17; regulatory-rules-distilled-spirits.md §2 "POC check type — flag-REVIEW (positional)"; project-context "recommend, don't decide" / REVIEW-when-unsure)*

2. **AC2 — The check reports each trio element's INDIVIDUAL presence, deterministically (no LLM).**
   **Given** the submission's joined OCR text (`ctx.ocr_text`) and the application trio fields (`brand_name`, `class_type_designation`, `alcohol_content`)
   **When** the same-field-of-vision check runs
   **Then** it determines, **deterministically (no model call)**, whether each of the three elements is individually present on the label, and folds that per-element presence report into the REVIEW `detail` so the specialist knows what the engine COULD confirm (presence) vs what it is deferring (co-location). The §5.63 citation travels off the Check row / ruleset DATA — never inlined in the check logic. *(FR-17; project-context determinism taxonomy — flag-only is deterministic code, NO LLM; regulatory-rules-distilled-spirits.md §2 "the engine confirms the three elements are present … and flags the co-location requirement")*

3. **AC3 — A multi-image submission whose trio co-location is undeterminable → REVIEW citing 27 CFR 5.63, reporting each element's individual presence.**
   **Given** a submission with **multiple** label images (the joined OCR text concatenates all of them, so which face carries which element is not recoverable from the flattened text)
   **When** the check runs
   **Then** it returns **REVIEW** with the 27 CFR 5.63 citation (carried as DATA) and a per-element presence report (each of brand / class-type / alcohol content marked present-or-not), explicitly noting that the co-location across faces cannot be auto-determined and is deferred to the specialist. The single-image case is handled identically (co-location is no more recoverable from one flattened image's OCR text than from several). *(FR-17 — the named AC: "a multi-image Submission whose trio co-location is undeterminable → REVIEW citing 27 CFR 5.63, reporting each element's individual presence")*

4. **AC4 — Flag-only is toggle-independent and never aborts the run.**
   **Given** the model layer is OFF or ON (`LLM_ENABLED` either way)
   **When** the check runs
   **Then** the verdict is unchanged (always REVIEW) — flag-only checks make **no model call** in either state, so the OCR-only path stays whole and zero-egress. An unknown/unhandled flag-only `check_key` degrades to an honest REVIEW (finalize-don't-abort, FR-9), never a raise and never a fabricated PASS/FAIL. *(FR-17; FR-9; project-context firewall posture — the OCR-only path completes end-to-end with zero egress)*

## Tasks / Subtasks

- [x]**Task 1 — Flag-only rules carried as ruleset DATA (AC1, AC2, AC3)**
  - [x]Create `app/engine/rulesets/flag_only.py` (DATA — distinct from the `checks/` logic), pure data + types only (imports nothing from the executor/evaluators, mirroring `rulesets/government_warning.py` + `rulesets/format_checks.py` + `rulesets/class_type.py`). Carry, with `CFR_CITATION` + `SOURCE_DATE`:
    - **`SAME_FIELD_OF_VISION_FIELDS`** — the ordered trio of application field_keys whose individual presence the same-field-of-vision check reports: `("brand_name", "class_type_designation", "alcohol_content")` (per §5.63 / regulatory-rules-distilled-spirits.md §2: "a label or labels bearing the **brand name**, **alcohol content**, and **class/type designation** must appear in the same field of vision"). Carry as DATA so a §5.63 amendment to the trio is a one-line edit, never a hard-coded list in logic.
    - **`SAME_FIELD_OF_VISION_REASON`** — the fixed explanatory note (DATA string) describing WHY co-location is deferred ("co-location on one 40%-of-circumference viewable face cannot be confirmed from a flat photo — flagged for the specialist to eyeball on the rendered label").
    - `CFR_CITATION = "27 CFR 5.63"`; `SOURCE_DATE = "2022-01-08"` (the post-2022 Part 5 renumbering, matching the spirits ruleset).
  - [x]No CFR citation literal lives in `checks/flag_only.py` — every citation travels off the Check row (`check.cfr_citation`) or this DATA module (the AC2 CFR-as-data guard, mirroring 3.4/3.5/3.6).

- [x]**Task 2 — `app/engine/checks/flag_only.py` flag-REVIEW evaluator (AC1, AC2, AC3, AC4)**
  - [x]Register the evaluator on Story 3.2's dispatch seam under the `positional` strategy (one line at the bottom of `app/engine/checks/__init__.py`, mirroring `field_match`/`government_warning`/`format_checks`/`class_type`). **No executor edit.**
  - [x]**Deterministic, NO LLM, by contract (like Gov Warning 3.4 & format checks 3.5).** This module never imports/constructs a model adapter and never reads the LLM extraction — it reads ONLY `ctx.ocr_text` (the deterministic engine's input) + `ctx.submission` application fields. (project-context determinism taxonomy — flag-only is deterministic code; the AC2 no-LLM guarantee is asserted by an import-AST guard, like 3.4/3.5, since this module legitimately needs NO adapter seam.)
  - [x]Dispatch on `check.check_key` to a keyed sub-evaluator (mirror `format_checks._HANDLERS`), so the single `positional` strategy can host several flag-only checks as the rulesets deepen (3.8 adds wine/malt flag-only conditional checks — sulfites, country-of-origin, coloring — that reuse this strategy with their own DATA). The Story-3.7 handler is `same_field_of_vision`:
    - **`same_field_of_vision` handler (AC2, AC3):** for each field_key in `data.SAME_FIELD_OF_VISION_FIELDS`, determine individual presence **deterministically**. Presence = the application value (when present) located in the joined OCR text via the centralized `app/normalize.py` (normalize both sides, substring/word-window match — reuse the SAME presence test the field_match text path uses so "STONE'S THROW" ≡ "Stone's Throw"; do NOT inline normalization), with a fallback to a recognized-keyword presence when the application value is absent (e.g. an ABV `%`-token for `alcohol_content`). Build a per-element presence report `{field_key: present_bool}`. Return **REVIEW** with a JSON `detail` payload carrying `{"outcome": "co_location_deferred", "elements": {<field_key>: <present>}, "reason": data.SAME_FIELD_OF_VISION_REASON, "cfr_citation": data.CFR_CITATION}` — **always REVIEW, never PASS/FAIL** (AC1). The presence report is informational only — even all-three-present does NOT upgrade to PASS (co-location is still unconfirmable).
  - [x]**Unknown key / finalize-don't-abort (AC4).** An unhandled flag-only `check_key` resolves to an honest REVIEW (`detail` = "flag-only check <key>: deferred to specialist") — never a raise, never a fabricated PASS/FAIL (mirror `format_checks`'s unknown-key REVIEW default).
  - [x]Writes **NO `field_comparisons` row** (this is a positional/placement judgment + a presence report, not an application↔OCR field-VALUE comparison — that is Story 3.3's `field_match` on `brand_name` etc.). Provenance travels in `CheckResult.detail`; `run_checks` writes the single `checklist_items` row.

- [x]**Task 3 — Confirm the spirits ruleset Check row + register in the data-dictionary (AC1)**
  - [x]The `same_field_of_vision` Check row already exists in `DISTILLED_SPIRITS_RULESET` (`strategy="positional"`, `check_type="MANUAL"`, `cfr_citation="27 CFR 5.63"`) — Story 3.7 implements its evaluator; **no ruleset edit needed** beyond confirming the row routes correctly. (Do NOT add a duplicate row.)
  - [x]Confirm `same_field_of_vision` is registered in `docs/data-dictionary.md` §6.2.1 (it already is — `MANUAL`, §5.63). Update the §6.2.1 note that currently says "§4 conditional/flag-only checks arrive with Story 3.7" so it reflects that the same-field-of-vision flag-only (`positional`) check is now realized by Story 3.7 (the §4 conditional flag-only checks — sulfites/country-of-origin/coloring — remain Story 3.8, reusing this `positional` strategy with their own DATA).

- [x]**Task 4 — Tests (`tests/test_flag_only.py`) (all ACs)**
  - [x]**Registration:** `get_evaluator("positional")` is the new evaluator (no longer the placeholder).
  - [x]**AC1 — always REVIEW, never PASS/FAIL (the headline):** a submission whose OCR text carries ALL THREE trio elements (brand + class/type + ABV) → **REVIEW** (NOT PASS — co-location still unconfirmable); a submission MISSING one or more → still **REVIEW** (NOT FAIL — absence of a single element is reported, but this check never FAILs; the field_match/format checks own the value/presence FAILs). Parametrize a few presence combinations and assert the verdict is REVIEW in every case.
  - [x]**AC2 — per-element presence report, deterministic, no LLM:** assert the REVIEW `detail` JSON carries an `elements` map with the correct present/absent boolean for each of brand_name / class_type_designation / alcohol_content given the seeded OCR text + application fields (e.g. brand "Stone's Throw" present in OCR ⇒ `true`; an application field whose value is absent from the OCR ⇒ `false`). Assert NO model is constructed/called — an **import-AST guard** that `checks/flag_only.py` imports no LLM adapter / `get_llm_adapter` (mirror the 3.4/3.5 no-LLM scan).
  - [x]**AC3 — multi-image submission → REVIEW citing §5.63 + presence report:** a submission with TWO label images, each contributing OCR text (brand+class/type on one, ABV on the other) → **REVIEW**, `detail` carries `cfr_citation == "27 CFR 5.63"` and an `elements` map marking all three present; assert the reason note explains co-location is deferred. (Single-image case asserted identically.)
  - [x]**AC4 — toggle-independent + unknown-key default:** the verdict is REVIEW regardless of `LLM_ENABLED` (no adapter seam touched — covered by the import-AST guard); an unknown flag-only `check_key` (a synthetic `Check(strategy="positional", check_key="not_a_real_flag_only")`) → honest REVIEW with a non-empty detail, never a raise.
  - [x]**CFR-as-data guard:** assert the `27 CFR` literal is NOT inlined in `checks/flag_only.py` source (mirror 3.4/3.5/3.6) — the citation comes off the Check row / the DATA module.
  - [x]**No `field_comparisons` row** written by this evaluator (assert count 0). **Integration through `run_checks`:** a spirits submission's `same_field_of_vision` Check now produces a real `positional` REVIEW verdict (no longer the placeholder REVIEW, but a structured presence report); `engine_verdict` rolls up via `verdict.rollup`; no regression to the existing roll-up fixtures (the row was already REVIEW under the placeholder, so the rolled-up verdict is unchanged — only the `detail` is now meaningful).
  - [x]Offline by construction (seeded OCR text + application fields only; **no real or fake provider call, no network**).

- [x]**Task 5 — Validate + finalize**
  - [x]`bash scripts/ci.sh` (HOST venv per CLAUDE.md): format → lint → mypy (story scope) → pytest, all green (no regressions — the `same_field_of_vision` row was already REVIEW under the 3.2 placeholder, so the integration/roll-up fixtures are unchanged; if any fixture asserts the placeholder `detail` text for this row, re-point it to the new structured `detail`, preserving intent, as Stories 3.3/3.4/3.5/3.6 did). Update File List + Change Log + Completion Notes (record the trio field set + the co-location reason so Diane can tune). Set Status → review and `sprint-status.yaml` `3-7-…: review`.
  - [x]Do NOT run the code-review skill / commit — later phases do that.

## Dev Notes

### ⚠️ Depends on Stories 3.1, 3.2 (+ 3.3/3.4/3.5/3.6 patterns) — implement on the existing seam
3.7 registers a `positional` evaluator behind Story **3.2**'s dispatch seam (`run_checks` + the existing `same_field_of_vision` Check row + `insert_checklist_item`) and uses Story **3.1**'s `normalize` for the presence test. It reuses the **3.4/3.5 deterministic-no-LLM + CFR-as-data ruleset-module pattern** and the **3.5 keyed-sub-evaluator dispatch** (`_HANDLERS` keyed on `check_key`, so one strategy hosts several flag-only checks). The `same_field_of_vision` Check row already routes to the `positional` strategy (currently the placeholder REVIEW); 3.7 makes it real (a structured presence report, still REVIEW). [Source: Stories 3.1–3.6; app/engine/checks/__init__.py; app/engine/rulesets/distilled_spirits.py; app/engine/checks/format_checks.py]

### Why flag-only is REVIEW, ALWAYS (the spine of this story)
`docs/regulatory-rules-distilled-spirits.md` §2 is explicit: determining whether three OCR text regions fall within one 40%-of-circumference viewable face "requires reliable spatial / per-image grouping that OCR bounding boxes alone cannot guarantee from photos. The engine confirms the three elements are **present** (deterministically / via field match) and flags the *co-location* requirement for the Label Specialist to eyeball on the rendered label." So this check NEVER emits PASS (it cannot confirm co-location) and NEVER emits FAIL (absence of an element is a different check's concern — field_match/format checks; flag-only's job is to defer the positional judgment, not duplicate a value FAIL). It ALWAYS emits REVIEW with a presence report + the §5.63 citation. This is the literal "Flag-only Checks → REVIEW" of FR-17. [Source: FR-17; regulatory-rules-distilled-spirits.md §2 + §3 same-field-of-vision row; epics.md Story 3.7 ACs]

### Deterministic, NO LLM (the import-AST guard, like 3.4/3.5)
Flag-only is deterministic code by the determinism taxonomy — it makes NO model call (unlike the HYBRID class/type check 3.6, which legitimately imports the adapter seam). So the AC2 "no LLM" guarantee is asserted with the SAME blanket import-AST scan 3.4/3.5 use: `checks/flag_only.py` imports no LLM adapter and no `get_llm_adapter`. This also gives AC4 for free (no seam ⇒ toggle-independent ⇒ zero egress on the OCR-only path). [Source: project-context determinism taxonomy ("rule-bound checks are deterministic code (no LLM)"); test_government_warning.py / test_format_checks.py no-LLM guards]

### Presence test — reuse normalize, don't reinvent (AC2)
Individual presence = the application value located in the joined OCR text via the centralized `app/normalize.py` (normalize both sides, then a substring / word-window match — the SAME discipline `field_match._compare_text` uses so "STONE'S THROW" ≡ "Stone's Throw" and a brand buried in a label blob still matches). For `alcohol_content` (a numeric/statement field), presence may also be confirmed by an ABV `%`-token in the OCR text when the application value is absent (a light reuse of the format-check ABV cue, NOT a value comparison). The presence report is informational — it never changes the REVIEW verdict, it just tells the specialist what the engine could confirm. Do NOT inline normalization (project-context anti-pattern). [Source: app/normalize.py; app/engine/checks/field_match.py _compare_text/_best_similarity; app/engine/checks/format_checks.py _find_abv_pct]

### Multi-image co-location is unrecoverable from flattened OCR text (AC3)
`get_submission_ocr_text` concatenates every `OK` `ocr_results` row's text in id order — so which physical face (front/back/neck) carried which element is GONE by the time the engine reads it. That is precisely why co-location is deferred: even with all three elements present in the joined text, the engine cannot assert they share one viewable face. AC3 is therefore satisfied by the SAME code path as the single-image case — the check reports each element's presence and defers the co-location, citing §5.63. The multi-image test simply seeds two `label_images` + two `ocr_results` rows to exercise the join. [Source: app/db/repositories.py:get_submission_ocr_text; regulatory-rules-distilled-spirits.md §2 "single side of the container … viewed simultaneously without turning the container"]

### No `field_comparisons` row (like the Gov Warning + format checks + class/type)
Same-field-of-vision is a positional/placement judgment + a presence report, not an application↔OCR field-VALUE comparison, so this evaluator writes NO `field_comparisons` row — exactly like Story 3.4 (Gov Warning), 3.5 (format checks), 3.6 (class/type). (The app↔OCR value match of brand/class-type/ABV is a SEPARATE field-match concern, Story 3.3.) Provenance lives in `CheckResult.detail`; `run_checks` writes the single `checklist_items` row. [Source: Story 3.4 Task 3, Story 3.5/3.6 "No field_comparisons row"]

### Keyed sub-evaluator dispatch — room for the 3.8 flag-only conditionals
Mirror `format_checks`'s `_HANDLERS` dict keyed on `check.check_key`, so the single `positional` strategy hosts the same-field-of-vision check now AND the §4 conditional flag-only checks later (Story 3.8 — sulfites §5.63(c)(7), country-of-origin §5.69, coloring §5.63(c)(6), FD&C Yellow #5, cochineal) which are all "flag-REVIEW (presence detectable; trigger not knowable from label)" per regulatory-rules-distilled-spirits.md §4. Those reuse this strategy + handler-dispatch with their own DATA — no new logic, no executor change. Story 3.7 ships only the `same_field_of_vision` handler; the dispatch shape makes 3.8 a data+handler addition. [Source: regulatory-rules-distilled-spirits.md §4 conditional/flag-REVIEW table; epics.md Story 3.8 "the same deterministic check implementations (Stories 3.3–3.7) are reused via the ruleset data, not re-coded per type"]

### Previous story intelligence (3.1–3.6)
- **3.1**: `normalize(value, field_key)` — import; never re-implement. Used for the presence test. [Source: app/normalize.py]
- **3.2**: the `{strategy: evaluator}` seam, `CheckContext` (`ocr_text`, `submission`, `conn`, `scratch`), `CheckResult` (`verdict`/`detail`), `run_checks` (writes the `checklist_items` row, rolls up via `verdict.rollup`). Register `positional`; no executor change. [Source: Story 3.2; app/engine/run_checks.py + checks/__init__.py]
- **3.4**: deterministic-no-LLM + CFR-as-data ruleset-module pattern; JSON `detail` payload with an `outcome` discriminator (reuse the shape so Story 4-x can render the presence report); whitespace-only / centralized normalization discipline; no `field_comparisons` row; the §6.2.1 registry discipline. [Source: app/engine/checks/government_warning.py + rulesets/government_warning.py]
- **3.5**: the keyed `_HANDLERS` dispatch on `check_key` + the unknown-key REVIEW default; the import-AST no-LLM guard; `_find_abv_pct` cue-aware ABV presence (reusable for the alcohol_content presence signal). [Source: app/engine/checks/format_checks.py]
- **3.6**: REVIEW-when-undeterminable / "recommend, don't decide"; the data-dictionary §6.2.1 annotation discipline. [Source: app/engine/checks/class_type.py; docs/data-dictionary.md §6.2.1]
- House style: `from __future__ import annotations`, type hints, `Literal` aliases, raw SQL only in `app/db/`, tests mirror `app/`, offline by construction, ruff line 100. [Source: app/engine/*]

### Scope boundary (what 3.7 IS and is NOT)
- **IS:** the same-field-of-vision flag-REVIEW (`positional`) check — always REVIEW, a deterministic per-element presence report for the trio (brand / class-type / alcohol content), the §5.63 citation as DATA, the co-location deferred to the specialist; multi-image handled by the same path (co-location unrecoverable from the flattened OCR join). The keyed-handler dispatch shape that 3.8 extends.
- **IS NOT:** the field-VALUE match of brand/class-type/ABV (Story 3.3 `field_match`, done — a separate concern); the §4 CONDITIONAL flag-only checks (sulfites/country-of-origin/coloring — Story 3.8, reuse this strategy with their own DATA); any spatial/bounding-box geometry inference (out of scope — the whole POINT of flag-REVIEW is that OCR boxes cannot guarantee it); font/type-size (out of scope). [Source: epics.md Stories 3.3–3.8; regulatory-rules-distilled-spirits.md §2/§4]

### Project Structure Notes
- New/edited: `app/engine/rulesets/flag_only.py` (NEW — trio field set + co-location reason + §5.63 as DATA), `app/engine/checks/flag_only.py` (NEW — flag-REVIEW evaluator, keyed-handler dispatch), `app/engine/checks/__init__.py` (UPDATE — register `positional`), `docs/data-dictionary.md` §6.2.1 (UPDATE — annotate `same_field_of_vision` now realized by 3.7), `tests/test_flag_only.py` (NEW). `distilled_spirits.py` needs **no** new row (the `same_field_of_vision` row already routes to `positional`). Matches the architecture tree (`engine/checks/flag_only.py # flag-only → REVIEW (FR-17)`). [Source: architecture.md engine tree]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.7] — story statement + ACs (flag-only → REVIEW with an explanation, never PASS/FAIL; multi-image co-location undeterminable → REVIEW citing 27 CFR 5.63, reporting each element's individual presence).
- [Source: docs/regulatory-rules-distilled-spirits.md §2 (same field of vision §5.63, "POC check type — flag-REVIEW (positional)"), §3 same-field-of-vision row] — the regulatory basis: confirm presence deterministically, flag co-location for the specialist.
- [Source: app/engine/checks/__init__.py (the `positional` strategy is reserved + the placeholder), run_checks.py] — the seam + the placeholder this story replaces.
- [Source: app/engine/checks/government_warning.py + rulesets/government_warning.py; format_checks.py + rulesets/format_checks.py] — the deterministic-no-LLM + CFR-as-data + no-`field_comparisons` + keyed-handler + REVIEW-when-unsure patterns.
- [Source: app/engine/checks/field_match.py _compare_text] — the normalize-based presence/substring test to reuse for individual presence.
- [Source: app/db/repositories.py:get_submission_ocr_text, list_label_images] — the joined OCR text (multi-image flattening) the check reads.
- [Source: docs/data-dictionary.md §6.2.1 (`same_field_of_vision` MANUAL §5.63)] — the registry entry (already present).
- [Source: _bmad-output/project-context.md] — "recommend, don't decide" / REVIEW-when-unsure; "CFR rules live as data"; determinism taxonomy (flag-only is deterministic, NO LLM); pipeline-is-the-only-writer of `checklist_items`; snake_case everywhere; firewall posture (OCR-only path zero-egress).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Amelia — Senior Software Engineer, bmad-agent-dev)

### Debug Log References

- Test-first RED confirmed: `tests/test_flag_only.py` failed with `ImportError: cannot import name 'flag_only' from 'app.engine.checks'` before the evaluator existed — the intended red state.
- GREEN: `tests/test_flag_only.py` → 17 passed; engine regression → 126 passed; full suite → 387 passed, 1 skipped.
- Full CI gate (`bash scripts/ci.sh`): format clean, lint clean, mypy reports a single pre-existing error at `auto-run/orchestrate.py:562` — out of story scope, walled off per CLAUDE.md (`git diff --stat -- auto-run/orchestrate.py` shows no change). pytest 387 passed / 1 skipped.

### Completion Notes List

- Reused the existing `same_field_of_vision` Check row in `app/engine/rulesets/distilled_spirits.py` (strategy=`positional`, check_type=`MANUAL`, cfr_citation=`27 CFR 5.63`) — **no ruleset / executor / schema edit**. The evaluator wired in behind the 3.2 `{strategy: evaluator}` seam (one-line registration: `EVALUATORS["positional"] = _flag_only`).
- **AC1** — the evaluator ALWAYS returns `REVIEW` (never PASS — co-location on one viewable face is unconfirmable from a flat photo; never FAIL — element absence is another check's concern).
- **AC2** — deterministic per-element presence report for the trio (brand_name / class_type_designation / alcohol_content) folded into the REVIEW `detail` as JSON. TEXT fields (brand / class-type) use `app.normalize.normalize(value, field_key)` substring containment; `alcohol_content` reuses `format_checks._find_abv_pct` (cue-aware ABV-statement probe, post-CR) so flag-only and the ABV format check agree on what counts as an ABV statement and a marketing `%` is not mistaken for one. NO LLM (import-AST guard test enforces it) ⇒ toggle-independent + zero-egress.
- **AC3** — multi-image co-location is unrecoverable from the flattened OCR join (`repo.get_submission_ocr_text`), so the same REVIEW path serves the multi-image case; detail carries the `27 CFR 5.63` citation + each element's individual presence.
- **AC4** — unknown `check_key` under the `positional` strategy degrades to a truthful REVIEW (`"deferred to specialist"`) — finalize-don't-abort. Behavior identical regardless of the LLM toggle.
- CFR citation + trio field set + co-location reason live as ruleset DATA in `app/engine/rulesets/flag_only.py` (no `27 CFR` literal in check logic — grep-guard test enforces it).
- Keyed `_HANDLERS` dispatch shape (mirrors `format_checks`) lets the one `positional` strategy host multiple flag-only checks; Story 3.8 extends it with the §4 conditional flag-only + wine/malt keys.
- No `field_comparisons` row is written (this is not a value-comparison check) — verified by test.

### File List

- `app/engine/rulesets/flag_only.py` — **NEW** (DATA: §5.63 citation, trio field set, co-location reason, source_date).
- `app/engine/checks/flag_only.py` — **NEW** (evaluator: `flag_only` dispatch → `_same_field_of_vision`, `_element_present`, `_value_in_ocr`; `alcohol_content` presence reuses `format_checks._find_abv_pct` post-CR).
- `app/engine/checks/__init__.py` — **UPDATED** (register `EVALUATORS["positional"] = _flag_only`).
- `docs/data-dictionary.md` — **UPDATED** (§6.2.1 note: flag-only `positional` `same_field_of_vision` now realized; §4 conditional flag-only + wine/malt keys arrive with 3.8).
- `tests/test_flag_only.py` — **NEW** (20 tests: registration, AC1–AC4, no-LLM import-AST guard, no-model-client guard, CFR-not-inlined guard, ruleset DATA, no `field_comparisons` row, run_checks integration; **CR-added**: ABV presence is token-order-independent, ABV presence is value-independent, marketing-`%` is not mistaken for ABV).

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-14 | Story 3.7 drafted — flag-only checks surface as REVIEW: the same-field-of-vision (`positional`) flag-REVIEW evaluator on the 3.2 seam (the existing `same_field_of_vision` Check row routes here). Always REVIEW (never PASS/FAIL); a deterministic per-element presence report for the trio (brand / class-type / alcohol content) folded into the REVIEW detail; §5.63 citation + trio field set + co-location reason as ruleset DATA; multi-image co-location unrecoverable from the flattened OCR join → same REVIEW path. NO LLM (import-AST guard) ⇒ toggle-independent + zero-egress. Keyed-handler dispatch shape that Story 3.8 extends with the §4 conditional flag-only checks. No executor/ruleset/schema edit; no `field_comparisons` row. Status → ready-for-dev. |
| 2026-06-14 | Story 3.7 implemented (test-first red→green) — `app/engine/rulesets/flag_only.py` (DATA) + `app/engine/checks/flag_only.py` (evaluator) + `positional` registration; 17 new tests all green; full suite 387 passed / 1 skipped; format + lint clean (mypy lone error pre-existing, walled-off `auto-run/`). All 4 ACs satisfied. Status → review. |
| 2026-06-14 | **Code review (CR) — patches applied, Status → done.** Review layers (Blind Hunter / Edge Case Hunter / Acceptance Auditor) converged on one real defect cluster in the `alcohol_content` presence probe: (1) **HIGH** — `_value_in_ocr` misused the NUMERIC branch of `normalize` as a substring haystack; `normalize(ocr_blob, "alcohol_content")` collapses the whole multi-line blob to the FIRST `<number><unit>` token, so a label whose net-contents (`750 mL`) is read before its ABV returned `alcohol_content=false` despite a verbatim `45% Alc./Vol.` on the label; (2) **MEDIUM** — the bespoke `_ABV_PCT_RE = \d[\d.,]*\s*%` fallback false-fired on promotional/nutrition `%` ("100% natural", "30% off"), regressing the cue-word discipline `format_checks._find_abv_pct` was written to enforce. **Fix:** `alcohol_content` presence now reuses `format_checks._find_abv_pct` (cue-aware ABV-statement probe) directly — the two checks now agree on what counts as an ABV statement; the broken `_value_in_ocr` numeric path + the bespoke regex are removed. Text fields (brand / class-type) keep the centralized-`normalize` substring path. Module docstring corrected (it overclaimed "separate-and-apart placement / severely-degraded-text" handling — those are future handlers, not shipped). +3 regression tests (token-order-independent ABV presence; value-independent ABV presence; competing-uncued-marketing-`%` rejected). Non-fixes (triaged, intentional): the `positional` strategy key matches the Check row (Auditor confirmed consistent); the unknown-key plain-string `detail` matches the sibling `format_checks` convention; short-brand substring presence is an accepted POC simplification (informational-only, never changes the REVIEW verdict). AC1 "always REVIEW" remains provable by inspection — every path returns `verdict.REVIEW`. Full CI green: format + lint clean, 390 passed / 1 skipped (mypy lone error pre-existing, walled-off `auto-run/orchestrate.py:562`). |
