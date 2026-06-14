---
baseline_commit: ec00d36f2f7b0ff6251a66e964de1fde6e5212e3
---

# Story 3.6: Hybrid class/type designation check

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want the class/type designation validated by rules first and escalated to a model only when genuinely ambiguous,
so that an LLM opinion can advise but never produce a FAIL on its own.

## Acceptance Criteria

1. **AC1 — Valid designations validate deterministically, with NO LLM call.**
   **Given** `app/engine/checks/class_type.py` registered on Story 3.2's dispatch seam under the `class_type` strategy (the existing `class_type_designation` Check row in `distilled_spirits.py` already points here — `check_type="HYBRID"`, §5.141)
   **When** it validates a designation that matches a recognized spirits class/type (e.g. "Kentucky Straight Bourbon Whiskey" — bourbon/whiskey is a catalogued class/type) carried as ruleset **DATA** (the BAM Ch.4 "allowed designations" catalog seeded into `app/engine/rulesets/class_type.py`)
   **Then** it returns **PASS** **without constructing or calling any model adapter** — the recognized-designation path is pure deterministic rule logic. *(FR-16; project-context determinism taxonomy + "VLM-only"; regulatory-rules-distilled-spirits.md §3 class/type row "presence/field-match deterministic")*

2. **AC2 — Genuinely ambiguous cases escalate to a VLM, capped at REVIEW, image-only (never OCR text).**
   **Given** a designation that is **neither** clearly recognized **nor** a detected cross-label conflict (genuinely ambiguous — e.g. an unlisted/novel designation that may be a valid trade-understanding or fanciful-name-plus-statement-of-composition)
   **When** the model layer is ON (`get_llm_adapter` resolves an adapter) the check escalates to a VLM assessment that is handed the label **IMAGE** (VLM-only — the model reads the image and produces its own reading) and is **capped at REVIEW severity (never FAIL)** — an LLM opinion alone never yields FAIL
   **And** the OCR text is **never** passed into the model call (no OCR→LLM hint, no OCR-assisted prompt) — per project-context "VLM-only" hard rule, the only model input is the image + a fixed instruction. *(FR-16; project-context "VLM-only — a model reads the IMAGE, never OCR text" + "LLM-assisted verdicts are capped at REVIEW")*

3. **AC3 — Conflicting designations across a submission's multiple labels → FAIL, deterministically, both values cited.**
   **Given** a submission whose joined OCR text (across all label images) carries **two different recognized base class/type designations that conflict** (e.g. "Bourbon Whiskey" on one label and "Vodka" on another)
   **When** the check runs
   **Then** the conflict is detected **deterministically** (no LLM) and returns **FAIL** with **both conflicting values cited** in the detail. A cross-image designation conflict is an objective rule violation, so it is a deterministic FAIL — distinct from the AC2 ambiguity path. *(FR-16; regulatory-rules-distilled-spirits.md §3 class/type row "no conflicting designations across labels")*

4. **AC4 — With `LLM_ENABLED=false`, degrade to rules-only + REVIEW for unresolved cases.**
   **Given** the model layer is OFF (`get_llm_adapter` returns `None` — `LLM_ENABLED=false`, no provider, or an absent key)
   **When** the check encounters a genuinely ambiguous designation it cannot resolve by rules
   **Then** it degrades to **rules-only** and emits **REVIEW with an explanatory detail** (defer to the human) — never a fabricated PASS/FAIL and never a guess. The deterministic PASS (AC1) and the deterministic conflict-FAIL (AC3) paths are unchanged by the toggle; only the ambiguous-escalation path differs (REVIEW instead of a VLM opinion). *(FR-16; project-context "recommend, don't decide" / REVIEW-when-unsure; firewall posture — `LLM_ENABLED=false` disables the boundary entirely)*

## Tasks / Subtasks

- [x] **Task 1 — Class/type "allowed designations" catalog as ruleset DATA (AC1, AC3)**
  - [x] Create `app/engine/rulesets/class_type.py` (DATA — distinct from the `checks/` logic), pure data + types only (imports nothing from the executor/evaluators, mirroring `rulesets/government_warning.py` + `rulesets/format_checks.py`). Carry, with `CFR_CITATION` + `SOURCE_DATE`:
    - **`RECOGNIZED_CLASS_TYPES`** — a frozenset of canonical lowercased base class/type **keywords** seeded from the BAM Ch.4 catalog (`ref-docs/chapter4.pdf`, summarized in `regulatory-rules-distilled-spirits.md` §1): the enumerated spirits classes — `whisky`/`whiskey`, `bourbon`, `rye`, `corn whisky`, `scotch`, `gin`, `brandy`, `cognac`, `rum`, `tequila`, `mezcal`, `vodka`, `liqueur`/`cordial`, `gin`, `american single malt whisky` (post-2022 §5.143). These are the recognized **base classes** — a designation is "recognized" when its normalized text CONTAINS at least one of these keywords. Carry the keyword set as DATA so a §5.141/BAM amendment is a one-line edit, never a hard-coded `if` chain.
    - **`CONFLICTING_GROUPS`** (or an equivalent representation) — the mutually-exclusive base-class groups used for AC3 conflict detection: e.g. `{whisky/bourbon/rye/scotch}`, `{vodka}`, `{gin}`, `{rum}`, `{tequila/mezcal}`, `{brandy/cognac}`, `{liqueur/cordial}`. Two recognized designations CONFLICT when they resolve to **different** groups (bourbon vs vodka conflict; "bourbon" vs "straight bourbon whiskey" do NOT — same group). Represent the grouping as DATA (a mapping keyword→group, or a tuple of frozensets) — the conflict logic reads it, never hard-codes the pairs.
    - `CFR_CITATION = "27 CFR 5.141"`; `SOURCE_DATE = "2022-01-08"` (the post-2022 Part 5 renumbering, matching the spirits ruleset).
  - [x] No CFR citation literal lives in `checks/class_type.py` — every citation travels off the Check row or this DATA module (the AC1 CFR-as-data guard, mirroring 3.4/3.5).

- [x] **Task 2 — `app/engine/checks/class_type.py` hybrid evaluator (AC1, AC2, AC3, AC4)**
  - [x] Register the evaluator on Story 3.2's dispatch seam under the `class_type` strategy (one line at the bottom of `app/engine/checks/__init__.py`, mirroring `field_match`/`government_warning`/`format_checks`). **No executor edit.**
  - [x] Resolution order (deterministic-FIRST, the hybrid contract):
    1. **Conflict detection (AC3) — deterministic FAIL FIRST.** Scan the joined OCR text (`ctx.ocr_text`) for ALL recognized base class/type designations (keyword membership from the DATA catalog), resolve each to its conflict group, and if **two or more DISTINCT groups** are present → **FAIL** citing both/all conflicting values in the detail. No LLM. (Conflict is checked before the PASS path so a label that names a valid bourbon AND a conflicting vodka cannot slip to PASS.)
    2. **Recognized → PASS (AC1) — deterministic, NO model.** Resolve the designation to compare: prefer the application `class_type_designation` (`ctx.submission.class_type_designation`); if absent, fall back to the recognized designation located in the OCR text. Normalize via `app/normalize.py` (never inline). If the normalized designation CONTAINS a recognized keyword from the DATA catalog → **PASS** with a detail naming the matched class/type. **No adapter is constructed or called on this path** (AC1 — the spy-adapter test asserts `run` was never invoked).
    3. **Ambiguous → escalate (AC2) or REVIEW (AC4).** Neither a conflict nor a recognized designation (e.g. an unlisted/novel designation). Resolve the active adapter via `app/config.get_llm_adapter(get_settings())`:
       - **adapter is not None (model layer ON):** call the VLM with the primary label **IMAGE** (`list_label_images` → `SOURCE_IMAGES_DIR / filename`, the same primary-image resolution as `pipeline/llm.py`) and a fixed class/type-assessment instruction — **never** the OCR text in the prompt. **Cap the result at REVIEW** (never FAIL): whatever the model says, the worst this check emits via the model path is REVIEW; record `model_id` on the `CheckResult` (the executor folds it into the detail provenance). On adapter error/raise → REVIEW (degrade honestly).
       - **adapter is None (model layer OFF, AC4):** **REVIEW** with an explanatory detail ("ambiguous class/type designation; model layer off — defer to specialist"). Rules-only degrade.
  - [x] **VLM-only purity (AC2, hard rule).** The model call's ONLY input is the image path + the fixed instruction. The check NEVER passes `ctx.ocr_text` (or any OCR-derived text) into the adapter. The conflict + recognition logic reads OCR text for the DETERMINISTIC engine only; it is never forwarded to a model. (Mirror `pipeline/llm.py`'s `_PROMPT` discipline — an OCR-free instruction.)
  - [x] **Capped at REVIEW.** The model path constructs its `CheckResult` with `verdict in {PASS_is_not_emitted_by_model, REVIEW}` — concretely, the model path emits **REVIEW** (an advisory escalation), never PASS and never FAIL. Only the DETERMINISTIC paths emit PASS (AC1) or FAIL (AC3). This realizes "an LLM opinion alone never yields FAIL" and "LLM-assisted capped at REVIEW".
  - [x] Writes **NO `field_comparisons` row** (this is a class/type-validity judgment against the catalog + a cross-label conflict rule, not an app↔OCR field-value comparison — that is Story 3.3's `field_match` on `brand_name` etc.; the existing `class_type_designation` field-value match is a separate concern). Provenance travels in `CheckResult.detail` (+ `model_id` for the escalated path); `run_checks` writes the single `checklist_items` row.

- [x] **Task 3 — Confirm the spirits ruleset Check row + register in the data-dictionary (AC1)**
  - [x] The `class_type_designation` Check row already exists in `DISTILLED_SPIRITS_RULESET` (`strategy="class_type"`, `check_type="HYBRID"`, `cfr_citation="27 CFR 5.141"`, `field_key="class_type_designation"`) — Story 3.6 implements its evaluator; **no ruleset edit needed** beyond confirming the row routes correctly. (Do NOT add a duplicate row.)
  - [x] Confirm `class_type_designation` is registered in `docs/data-dictionary.md` §6.2.1 (it already is — `HYBRID`, §5.141). Update the §6.2.1 note that currently says these strategies "arrive with Story 3.7/3.8" if it implies class/type is unimplemented — class/type is now realized by Story 3.6.

- [x] **Task 4 — Tests (`tests/test_class_type.py`) (all ACs)**
  - [x] **Registration:** `get_evaluator("class_type")` is the new evaluator (no longer the placeholder).
  - [x] **AC1 — recognized → PASS, NO model call (the headline):** a submission with `class_type_designation="Kentucky Straight Bourbon Whiskey"` (+ matching OCR text) → **PASS**; inject a **spy adapter** via the `get_llm_adapter` seam whose `run` raises/records if called, and assert it was **NEVER called** on the recognized path. Other recognized designations (`"London Dry Gin"`, `"Blanco Tequila"`, `"Vodka"`) → PASS.
  - [x] **AC3 — cross-label conflict → deterministic FAIL, both cited:** OCR text carrying "Bourbon Whiskey" (front) and "Vodka" (back) → **FAIL**, with BOTH "bourbon"/"vodka" surfaced in the detail; assert NO model call (spy adapter not invoked). A submission with the SAME class on two labels ("Straight Bourbon" + "Bourbon Whiskey") → **NOT** a conflict (same group).
  - [x] **AC2 — ambiguous + model ON → VLM, capped REVIEW, image-only:** an unlisted designation (e.g. `class_type_designation="Sasquatch Spirit Elixir"`, OCR text with no recognized keyword) with a **fake adapter** injected (the `_FakeModel` pattern from `test_pipeline.py` that records its `run` calls) → result is **REVIEW** (never FAIL even if the model "fails" the designation), `model_id` recorded; assert the adapter was handed an **`image_path`** and that **the OCR text does NOT appear in the prompt** (VLM-only). A model that raises → REVIEW (degrade).
  - [x] **AC4 — ambiguous + model OFF → rules-only REVIEW:** same unlisted designation with the `get_llm_adapter` seam returning `None` → **REVIEW** with a non-empty explanatory detail; assert no adapter constructed/called.
  - [x] **AC1 — no-LLM on the deterministic paths:** unlike 3.4/3.5, this module LEGITIMATELY imports the adapter seam for the escalation path, so the blanket import-AST guard does NOT apply. Instead assert behaviorally (the spy adapter) that the PASS (AC1) and conflict-FAIL (AC3) paths construct/call **no model**. Add a guard that **`ctx.ocr_text` is never forwarded into the adapter `run`** (capture the prompt + image_path in the fake and assert the OCR string is absent from the prompt) — the VLM-only invariant.
  - [x] **No `field_comparisons` row** written by this evaluator (assert count 0). **Integration through `run_checks`:** a spirits submission's `class_type_designation` Check now produces a real `class_type` verdict (PASS for a recognized bourbon), `engine_verdict` rolls up via `verdict.rollup`; no regression to the existing roll-up fixtures.
  - [x] Offline by construction (seeded OCR text + a fake/spy adapter only; **no real provider call, no network**). The image_path handed to the fake need not exist on disk (the fake never opens it).

- [x] **Task 5 — Validate + finalize**
  - [x] `bash scripts/ci.sh` (HOST venv per CLAUDE.md): format → lint → mypy (story scope) → pytest, all green (no regressions — re-point any stale roll-up assertion that previously saw the `class_type` placeholder REVIEW and now sees a real PASS, preserving its intent, as Stories 3.3/3.4/3.5 did). Update File List + Change Log + Completion Notes (record the recognized-designation keyword set + conflict groups so Diane can tune). Set Status → review and `sprint-status.yaml` `3-6-…: review`.
  - [x] **Code review (2026-06-14):** 3 patches applied (CR F1 liqueur-group excluded from `CONFLICT_GROUPS` — compound liqueur designations no longer false-FAIL; CR F2 conflict anchored to the declared designation — un-anchored OCR-soup no longer FAILs; CR F3 hyphenated multi-word keyword now matches, "Single-Malt" ≡ "single malt") + 8 net new regression tests (370 suite green / 1 skip; ruff + story-scope mypy clean). 4 findings deferred to `deferred-work.md` (F2 residual incidental-mention, F6 OCR-fallback false-PASS, F4 bare rye/corn catalog, F5 app↔label value-match by-design). Status → done.

## Dev Notes

### ⚠️ Depends on Stories 3.1, 3.2 (+ 2.5 VLM seam, 3.4/3.5 patterns) — implement on the existing seam
3.6 registers a `class_type` evaluator behind Story **3.2**'s dispatch seam (`run_checks` + the existing `class_type_designation` Check row + `insert_checklist_item`) and uses Story **3.1**'s `normalize`. It reuses the **3.4/3.5 pattern** (CFR-as-data ruleset module; "REVIEW when undeterminable, never a guess") and the **Story 2.5 VLM seam** (`config.get_llm_adapter` + the primary-image resolution `SOURCE_IMAGES_DIR / filename` + `ModelAdapter.run(task, prompt, image_path=...)` returning the `LlmResult` contract). The `class_type_designation` Check row already routes to the `class_type` strategy (currently the placeholder REVIEW); 3.6 makes it real. [Source: Stories 3.1–3.5, 2.5; app/engine/checks/__init__.py; app/engine/rulesets/distilled_spirits.py; app/pipeline/llm.py; app/config.py]

### The hybrid contract — deterministic FIRST, model LAST and capped (the spine of this story)
This is the POC's ONE place an LLM touches a verdict, so the guardrails are strict:
- **Rules decide PASS and FAIL; the model only ever advises REVIEW.** The recognized-designation PASS (AC1) and the cross-label conflict FAIL (AC3) are BOTH deterministic — no model is constructed on those paths. The model is escalated ONLY for genuine ambiguity, and its worst output is REVIEW (AC2). "LLM-assisted verdicts are capped at REVIEW — an LLM opinion alone never yields FAIL" (project-context determinism taxonomy). [Source: project-context "Determinism taxonomy"; epics.md Story 3.6 ACs]
- **VLM-only — image in, never OCR text.** When the model is called it is handed the label IMAGE (the same primary-image the 2.5 stage reads) and a fixed instruction; `ctx.ocr_text` is NEVER passed to the model. OCR text feeds ONLY the deterministic conflict/recognition logic. This is the project-context hard rule (and the §41 line: "any code that passes OCR output into a model call is a finding"). [Source: project-context "VLM-only"; app/pipeline/llm.py `_PROMPT` + `_primary_image_path`]
- **Toggle-safe (AC4).** `get_llm_adapter` returning `None` (LLM off) must leave the deterministic paths identical and turn the ambiguous-escalation into a plain REVIEW — the OCR-only path stays whole and zero-egress. [Source: project-context firewall posture; config.get_llm_adapter]

### Recognized designations as a keyword catalog (AC1) — seeded from BAM Ch.4
`regulatory-rules-distilled-spirits.md` §1 names `ref-docs/chapter4.pdf` (TTB BAM Vol. 2, Ch. 4 — Class & Type Designation) as "the enumerated catalog of valid spirits classes and types" and says the class/type check "can be seeded from this chart as an 'allowed designations' lookup". For the POC, carry a pragmatic **base-class keyword set** (whisky/bourbon/rye/scotch/corn, gin, brandy/cognac, rum, tequila/mezcal, vodka, liqueur/cordial, american single malt whisky) as DATA. A designation is "recognized" when its normalized text contains a catalog keyword — so "Kentucky Straight Bourbon Whiskey" → bourbon → recognized → PASS. An unlisted/novel designation is "ambiguous" → escalate (AC2) or REVIEW (AC4). Carry the set as DATA so a §5.141/BAM amendment is a one-line edit (never a hard-coded `if` chain — the project-context anti-pattern). [Source: regulatory-rules-distilled-spirits.md §1 + §3 class/type row; project-context "CFR rules live as data"]

### Conflict detection (AC3) — different groups = FAIL, deterministically
The §3 class/type row lists "no conflicting designations across labels" as a requirement. Two recognized designations CONFLICT when they resolve to DIFFERENT mutually-exclusive base-class groups (bourbon vs vodka). Same-group variants do NOT conflict ("Straight Bourbon Whiskey" and "Bourbon" are both the whisky group). Detect by scanning the joined OCR text (all labels concatenated by `get_submission_ocr_text`) for catalog keywords, mapping each to its group, and FAILing when ≥2 distinct groups appear — citing the conflicting values. This is an objective rule violation ⇒ a deterministic FAIL (NOT the ambiguity path; NOT an LLM call). [Source: regulatory-rules-distilled-spirits.md §3 class/type row; epics.md Story 3.6 AC "conflicting designations … detected deterministically → FAIL with both values cited"]

### No `field_comparisons` row (like the Gov Warning + format checks)
Class/type VALIDITY is a judgment against the catalog + a cross-label conflict rule, not an application-field VALUE comparison, so this evaluator writes NO `field_comparisons` row — exactly like Story 3.4 (Gov Warning) and 3.5 (format checks). (The app↔OCR value match of `class_type_designation` is a SEPARATE field-match concern; it is not what this HYBRID check answers.) Provenance lives in `CheckResult.detail` (+ `model_id` on the escalated path); `run_checks` writes the single `checklist_items` row. [Source: Story 3.4 Task 3, Story 3.5 "No field_comparisons row"; run_checks._detail_with_provenance folds model_id]

### AC1 guard — behavioral, not a blanket import-AST scan (the difference from 3.4/3.5)
Unlike the Gov Warning (3.4) and format checks (3.5) — which are deterministic-by-contract and assert NO model import at all — this module **legitimately imports the adapter seam** (`config.get_llm_adapter`) for the AC2 escalation. So the AC1 "no LLM" guarantee is asserted **behaviorally**: inject a spy adapter via the `get_llm_adapter` seam and assert its `run` is **never called** on the recognized-PASS (AC1) and conflict-FAIL (AC3) paths. Plus the VLM-only guard: capture the prompt + image_path the fake receives and assert the OCR text is absent from the prompt. (The CFR-as-data guard from 3.4/3.5 still applies — `27 CFR` is not inlined in `checks/class_type.py`.) [Source: project-context determinism taxonomy + VLM-only; test_pipeline.py `_FakeModel`]

### Previous story intelligence (3.1–3.5 + 2.5)
- **3.1**: `normalize(value, field_key)` — import; never re-implement. Class/type is a TEXT field; normalize collapses case/punctuation so "BOURBON" == "bourbon". [Source: app/normalize.py]
- **3.2**: the `{strategy: evaluator}` seam, `CheckContext` (`ocr_text`, `submission`, `conn`, `scratch`), `CheckResult` (with `model_id` for LLM-assisted provenance — already present, used here), `run_checks` (writes the `checklist_items` row, rolls up via `verdict.rollup`). Register `class_type`; no executor change. [Source: Story 3.2; app/engine/run_checks.py + checks/__init__.py]
- **2.5**: the VLM seam — `config.get_llm_adapter(get_settings())` returns a `ModelAdapter | None`; the adapter's `run(task, prompt, *, image_path=...)` returns an `LlmResult`; the primary image is `SOURCE_IMAGES_DIR / label_images[0].filename`. The prompt is OCR-free (VLM-only). Reuse this EXACTLY for the escalation. [Source: app/pipeline/llm.py; app/config.py; app/adapters/llm/base.py]
- **3.4/3.5**: deterministic-no-LLM + CFR-as-data ruleset-module pattern; "REVIEW when undeterminable, never a guess"; no `field_comparisons` row; the §6.2.1 registry discipline. [Source: app/engine/checks/government_warning.py + format_checks.py; rulesets/government_warning.py + format_checks.py]
- House style: `from __future__ import annotations`, type hints, `Literal` aliases, raw SQL only in `app/db/`, tests mirror `app/`, offline by construction, ruff line 100. [Source: app/engine/*]

### Scope boundary (what 3.6 IS and is NOT)
- **IS:** the hybrid class/type-designation VALIDITY check — deterministic recognition (catalog PASS), deterministic cross-label conflict (FAIL, both cited), and the genuinely-ambiguous escalation to a VLM (image-only, capped REVIEW) that degrades to rules-only REVIEW when the model is off; the recognized-designations + conflict-groups as ruleset DATA.
- **IS NOT:** the class/type field-VALUE match (app↔OCR — Story 3.3 `field_match`, a separate concern); the same-field-of-vision POSITIONAL co-location check (Story 3.7 `positional`/`flag_only`); the per-type FORMAT checks (Story 3.5, done); the wine & malt rulesets at full depth (Story 3.8 — wine/malt class/type catalogs reuse this `class_type` strategy with their own DATA, no new logic); and font/type-size (out of scope — not recoverable from a photo). [Source: epics.md Stories 3.3–3.8; regulatory-rules-distilled-spirits.md §6]

### Project Structure Notes
- New/edited: `app/engine/rulesets/class_type.py` (NEW — recognized-designations + conflict-groups as DATA), `app/engine/checks/class_type.py` (NEW — hybrid evaluator), `app/engine/checks/__init__.py` (UPDATE — register `class_type`), `docs/data-dictionary.md` §6.2.1 (UPDATE — confirm/annotate `class_type_designation` now implemented by 3.6), `tests/test_class_type.py` (NEW). `distilled_spirits.py` needs **no** new row (the `class_type_designation` row already routes to `class_type`). Matches the architecture tree (`engine/checks/class_type.py # hybrid class/type designation (FR-16)`). [Source: architecture.md engine tree]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.6] — story statement + ACs (rules-first; ambiguous → VLM capped REVIEW, image not OCR text; cross-label conflict → deterministic FAIL both cited; LLM-off → rules-only + REVIEW).
- [Source: docs/regulatory-rules-distilled-spirits.md §1 (BAM Ch.4 catalog), §3 class/type row (hybrid; "no conflicting designations across labels"; §5.141/§5.165)] — the regulatory basis.
- [Source: app/pipeline/llm.py + app/config.py:get_llm_adapter + app/adapters/llm/base.py] — the VLM seam to reuse (image-only, OCR-free prompt, `ModelAdapter.run`).
- [Source: app/engine/checks/__init__.py (the `class_type` strategy is reserved + the placeholder), run_checks.py (`_detail_with_provenance` folds `model_id`; `CheckResult.model_id`)] — the seam + provenance plumbing.
- [Source: app/engine/checks/government_warning.py + rulesets/government_warning.py; format_checks.py] — the CFR-as-data + no-`field_comparisons` + REVIEW-when-unsure patterns.
- [Source: docs/data-dictionary.md §6.2.1 (`class_type_designation` HYBRID §5.141)] — the registry entry (already present).
- [Source: _bmad-output/project-context.md] — "VLM-only — a model reads the IMAGE, never OCR text"; "LLM-assisted verdicts capped at REVIEW — an LLM opinion alone never yields FAIL"; "recommend, don't decide"; "CFR rules live as data"; pipeline-is-the-only-writer of `checklist_items`; snake_case everywhere.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Amelia — Senior Software Engineer, bmad-agent-dev)

### Debug Log References

None — no blocking issues. Targeted `tests/test_class_type.py` green on first full run (18 passed); full `scripts/ci.sh` gate green with no regressions to the existing roll-up/integration fixtures.

### Completion Notes List

- **Implemented the hybrid contract behind the existing seam.** `app/engine/checks/class_type.py` registers under the `class_type` strategy (one line in `checks/__init__.py`); the pre-existing `class_type_designation` Check row (`distilled_spirits.py`, `check_type="HYBRID"`, §5.141) now routes to real logic instead of the placeholder REVIEW. No executor/ruleset/schema edit.
- **Resolution order — deterministic FIRST, model LAST & capped.** (1) Cross-label conflict (≥2 distinct base-class groups in the joined OCR text) → deterministic **FAIL**, both values + groups cited; checked before PASS so a valid-bourbon-AND-conflicting-vodka label cannot slip to PASS. (2) Recognized designation (app value, else OCR text contains a catalog keyword) → deterministic **PASS**, no adapter constructed. (3) Ambiguous → escalate to an image-only VLM **capped at REVIEW** when the model is on, else rules-only **REVIEW** (AC4). A raising adapter or missing image also degrades to REVIEW.
- **VLM-only purity enforced + tested.** The escalation hands the adapter the primary label IMAGE (`SOURCE_IMAGES_DIR / label_images[0].filename`) + a fixed OCR-free `_PROMPT`; `ctx.ocr_text` is NEVER forwarded. A test captures the prompt + image_path the spy receives and asserts the OCR sentinel token ("ZZZQ…") is absent from the prompt while `front_1.png` is the image_path.
- **AC1 "no LLM" asserted behaviorally** (not the 3.4/3.5 import-AST scan, since this module legitimately imports the adapter seam): a spy adapter whose `run` records/raises is injected via the `get_llm_adapter` seam and asserted **never called** on the recognized-PASS and conflict-FAIL paths. CFR-as-data guard still applies — no `27 CFR` literal in `checks/class_type.py`.
- **Recognition catalog + conflict groups carried as DATA** in `app/engine/rulesets/class_type.py` (`KEYWORD_GROUPS` keyword→group map, `RECOGNIZED_CLASS_TYPES` frozenset, `CFR_CITATION`, `SOURCE_DATE`). Recognition is normalized word-boundary phrase membership (`_contains_phrase` uses `\b…\b` so "gin" does not fire in "virgin", "rum" not in "drum"). A §5.141/BAM amendment is a one-line edit here. **For Diane to tune:** groups are `whisky` (whisky/whiskey/bourbon/rye/scotch/corn/single malt), `gin`, `brandy` (brandy/cognac), `rum`, `agave` (tequila/mezcal), `vodka`, `liqueur` (liqueur/cordial).
- **No `field_comparisons` row** (a validity/conflict judgment, not an app↔OCR value match — like Gov Warning 3.4 & format checks 3.5); provenance in `CheckResult.detail` (+ `model_id` on the escalated path, which `run_checks._detail_with_provenance` folds in). `run_checks` writes the single `checklist_items` row.
- **Tests:** 18 in `tests/test_class_type.py` — registration; recognized→PASS (+ parametrized designations) with spy never called; cross-label conflict→FAIL both cited; same-group not a conflict; ambiguous+model-ON→capped REVIEW + `model_id`; VLM-only prompt guard; model-raises→REVIEW; ambiguous+model-OFF→REVIEW; toggle does not change deterministic verdicts; no `field_comparisons` row; `run_checks` integration PASS + roll-up; CFR-not-inlined guard; catalog keyword→group integrity. All offline (seeded OCR + spy/fake adapter; image_path need not exist).

### File List

- `app/engine/rulesets/class_type.py` — NEW (recognized-designation keyword catalog + conflict groups + `CFR_CITATION`/`SOURCE_DATE`, as DATA). **CR-updated:** added `CONFLICT_GROUPS` (the mutually-exclusive base classes; `liqueur` excluded — a statement of composition naming its base spirit is not a conflict).
- `app/engine/checks/class_type.py` — NEW (the hybrid evaluator: conflict→FAIL / recognized→PASS / ambiguous→VLM-capped-REVIEW or rules-only REVIEW; VLM-only image escalation). **CR-updated:** `_detect_conflict` now anchored to the declared designation + filtered to `CONFLICT_GROUPS` (+ `_conflict_groups_in` helper); `_contains_phrase` matches hyphenated multi-word keywords.
- `app/engine/checks/__init__.py` — UPDATED (register `class_type` on the dispatch seam; one import + one `EVALUATORS[...]` line).
- `docs/data-dictionary.md` — UPDATED (§6.2.1 note annotates the `class_type_designation` HYBRID row as realized by Story 3.6 — sole model-assisted row, capped at REVIEW).
- `tests/test_class_type.py` — NEW (AC1–AC4 + VLM-only + integration). **CR-updated:** 18 → 26 tests (+ liqueur-excluded, 4× compound-liqueur PASS, anchored-conflict, hyphenated-single-malt, conflict-FAIL-unchanged-by-toggle).
- `_bmad-output/implementation-artifacts/deferred-work.md` — UPDATED (4 CR deferrals: F2 residual incidental-mention, F6 OCR-fallback false-PASS, F4 bare rye/corn catalog, F5 app↔label value-match by-design).

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-14 | Story 3.6 drafted — hybrid class/type designation check: deterministic recognition (BAM Ch.4 catalog as DATA) → PASS with no model; deterministic cross-label conflict → FAIL both cited; genuinely-ambiguous → VLM escalation (image-only, OCR-free prompt, capped at REVIEW, never FAIL) degrading to rules-only REVIEW when LLM off. Registered on the 3.2 `class_type` seam (the existing Check row routes here); no executor/ruleset edit. AC1 asserted behaviorally (spy adapter never called on deterministic paths) + VLM-only guard (OCR text absent from prompt). Status → ready-for-dev. |
| 2026-06-14 | Story 3.6 implemented (Amelia, DEV) — DATA module + hybrid evaluator + seam registration + 18 tests, all green; full CI gate (format/lint/mypy/pytest) green, no regressions. data-dictionary §6.2.1 annotated. Status → review. |
| 2026-06-14 | Story 3.6 code review (Amelia, DEV) — 3 patches: **CR F1** the `liqueur`/`cordial` group is excluded from a new `CONFLICT_GROUPS` (DATA) so a compound statement-of-composition designation ("Coffee Liqueur with Rum", "Sloe Gin Liqueur", "Whisky Liqueur") no longer false-FAILs; **CR F2** `_detect_conflict` is now anchored to the declared `class_type_designation` (+ `_conflict_groups_in` helper) so an un-anchored OCR-only multi-spirit blob degrades to REVIEW instead of a fabricated FAIL — the AC3 bourbon/vodka cross-label conflict still FAILs; **CR F3** `_contains_phrase` matches a hyphenated multi-word keyword ("Single-Malt" ≡ "single malt"). +8 net regression tests (26 in `test_class_type.py`; 370 suite green / 1 skip; ruff + story-scope mypy clean). 4 findings deferred to `deferred-work.md` (residual incidental-mention not deterministically separable from a true conflict; OCR-fallback recognition false-PASS; bare rye/corn catalog gap → safe REVIEW; app↔label value-match is Story 3.3 scope by design). The lone CI mypy error is pre-existing in the walled-off `auto-run/orchestrate.py` (out of story scope, untouched). Status → done. |
