---
baseline_commit: c00d92dea980abab228640ea2c38af8897881a8e
---

# Story 3.2: Rulesets-as-data executor with verdict provenance

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist and an evaluator,
I want each beverage type's Checks defined as data with CFR citations, executed into an explainable checklist,
so that any verdict can be traced to its rule, inputs, and citation.

## Acceptance Criteria

1. **AC1 — Per-Beverage-Type Rulesets are DATA (Check rows), starting with distilled spirits.**
   **Given** per-Beverage-Type Rulesets stored as data in `app/engine/rulesets/` — each `Check` carrying `check_key`, **determinism class** (`check_type`: `DETERMINISTIC`/`FIELD_MATCH`/`HYBRID`/`MANUAL`), `cfr_citation` string (`"27 CFR <part>.<section>"`), `source_date`, and a human `label` — authored from `docs/regulatory-rules-distilled-spirits.md`
   **When** the distilled-spirits ruleset is loaded
   **Then** it enumerates the always-mandatory spirits elements (§3), the Government Warning (Part 16), and the same-field-of-vision check (§5.63), each as a data row with its real CFR citation. *(AR-6, FR-18)*

2. **AC2 — `engine/run_checks.py` executes a submission's ruleset into a checklist + rolled-up verdict.**
   **Given** a `READY`-bound submission with OCR (and optional LLM) results
   **When** `run_checks` executes the submission's ruleset
   **Then** it writes **one `checklist_items` row per Check**, and `verdict.rollup` (Story 3.1) sets the submission's `engine_verdict`. *(AR-6, FR-18)*

3. **AC3 — Every verdict records full provenance.**
   **Given** a written `checklist_items` row
   **When** it is inspected
   **Then** it records its `check_key`, determinism class (`check_type`), `cfr_citation`, the input values compared (in `detail`), and — for LLM-assisted checks — the model identification. *(FR-18)*

4. **AC4 — CFR text/citations live ONLY as Ruleset data — never hard-coded in check logic.**
   **Given** any check evaluator
   **When** it produces a verdict
   **Then** it reads the citation from the `Check` data row; **no CFR citation string is hard-coded in evaluator/executor logic** (a grep for `27 CFR` outside ruleset data + tests is a finding). *(AR-6, project-context "CFR rules live as data")*

5. **AC5 — The engine stage is wired into the pipeline; every ready submission carries a complete, explainable checklist.**
   **Given** the Story 2.2 stage seam (`run.STAGES`)
   **When** the pipeline runs a submission end-to-end
   **Then** an `engine_stage` (registered **after** `llm_stage`) executes `run_checks`, so each submission reaching `READY_FOR_REVIEW` has a complete checklist and a non-NULL `engine_verdict` — with no scheduler/status change. *(architecture Process flow; Epic 3 standalone outcome)*

## Tasks / Subtasks

- [ ] **Task 1 — Ruleset-as-data structures in `app/engine/rulesets/` (AC1, AC4)**
  - [ ] Define a frozen `Check` dataclass (e.g. `app/engine/rulesets/base.py`): `check_key: str`, `label: str`, `check_type: CheckType` (the determinism class — `Literal["DETERMINISTIC","FIELD_MATCH","HYBRID","MANUAL"]`, matching the `checklist_items.check_type` CHECK enum exactly), `cfr_citation: str` (`"27 CFR <part>.<section>"`), `source_date: str` (UTC ISO date the citation was current), `strategy: str` (which evaluator handles it — see Task 3), and an optional `field_key: str | None` (for field-match checks). Pure data, no logic.
  - [ ] `app/engine/rulesets/distilled_spirits.py`: enumerate the spirits ruleset as a `tuple[Check, ...]` authored from `docs/regulatory-rules-distilled-spirits.md` §2/§3/§5 — the **always-mandatory** elements + Gov Warning + same-field-of-vision. Suggested rows (finalize `check_key`s against `docs/data-dictionary.md`):
    - `brand_name` — `FIELD_MATCH` — `27 CFR 5.64`
    - `class_type_designation` — `HYBRID` — `27 CFR 5.141`
    - `alcohol_content` — `HYBRID` — `27 CFR 5.65`
    - `net_contents` — `HYBRID` — `27 CFR 5.70`
    - `name_address` — `HYBRID` — `27 CFR 5.66`
    - `government_warning` — `DETERMINISTIC` — `27 CFR 16.21`
    - `same_field_of_vision` — `MANUAL` — `27 CFR 5.63`
  - [ ] `get_ruleset(beverage_type: str) -> tuple[Check, ...]` lookup. Spirits is authored at depth now; **wine/malt rulesets are Story 3.8** — return an empty/minimal ruleset for `WINE`/`MALT_BEVERAGE` here (a submission with no checks rolls up per Task 2's empty-rule policy). Do not author wine/malt at depth in 3.2.
  - [ ] **CFR citations are data here and nowhere else** (AC4). The conditional/flag-only spirits elements (§4) are **Story 3.7** — do not enumerate them now.

- [ ] **Task 2 — `app/engine/run_checks.py` executor (AC2, AC3)**
  - [ ] `run_checks(conn, submission, *, ...) -> str`: load the submission's ruleset via `get_ruleset(submission.beverage_type)`; for each `Check`, dispatch to its evaluator (Task 3), receive a `CheckResult`, and **write one `checklist_items` row** carrying `check_key`, `label`, `cfr_citation`, `check_type` (from the `Check` data — not recomputed), `verdict`, `detail` (the input values compared / why it flagged), and `field_comparison_id` when present. Then call `verdict.rollup` over the per-check verdicts and persist `engine_verdict` on the submission. Return the rolled-up verdict.
  - [ ] **Provenance in `detail`** (AC3): record the compared inputs (e.g. `app="Stone's Throw" | ocr="STONE'S THROW"`) and, for LLM-assisted checks, the model identification (`model_id`/`model_full_id`). Keep `detail` a concise advisory string. Never log secrets.
  - [ ] **Empty/all-`NA` ruleset → `engine_verdict = REVIEW`** (consistent with Story 3.1's `rollup` empty-policy and the determinism taxonomy "never silent auto-decision"). This is what a `WINE`/`MALT` submission gets until Story 3.8.
  - [ ] Idempotency: if `run_checks` may run more than once for a submission, clear prior `checklist_items` for that submission first (delete-then-insert) so re-processing does not duplicate rows. (Mirror the honest re-run posture; confirm against how `reset` / re-sweep behaves.)

- [ ] **Task 3 — Check-evaluator dispatch seam (AC2, AC4, forward-compat for 3.3–3.7)**
  - [ ] Mirror the pipeline's `STAGES` seam (Story 2.2): a registry `{strategy: evaluator}` where `evaluator(check: Check, ctx: CheckContext) -> CheckResult`. `CheckContext` bundles `conn`, `submission`, OCR text (`repo.get_submission_ocr_text`), and LLM results. `CheckResult` = `verdict` (`PASS`/`REVIEW`/`FAIL`/`NA`) + `detail` + optional `field_comparison_id` + optional model id.
  - [ ] In 3.2, register a **single honest placeholder evaluator** (default for every strategy): returns `REVIEW` with `detail="not yet evaluated by the engine"`. This yields a complete, truthful checklist now; Stories **3.3** (`field_match`), **3.4** (`government_warning`), **3.5** (`format_checks`), **3.6** (`class_type`), **3.7** (`flag_only`) each register their real evaluator under their strategy key with **no executor change** — the whole point of the seam. Do **not** implement real check logic here (that work belongs to 3.3–3.7; building it now duplicates their scope).
  - [ ] An unknown/unregistered strategy must resolve to the honest `REVIEW` default, never raise (finalize-don't-abort posture, FR-9).

- [ ] **Task 4 — Repository write helpers + engine_verdict setter (AC2, AC3)**
  - [ ] Add `insert_checklist_item(conn, submission_id, *, check_key, label, cfr_citation, check_type, verdict, detail=None, field_comparison_id=None) -> int` to `app/db/repositories.py`, mirroring the existing `insert_ocr_result`/`insert_llm_result` style (raw SQL stays in `app/db/` — the Data boundary).
  - [ ] Add `set_engine_verdict(conn, submission_id, verdict)` (or extend an existing updater). `engine_verdict` CHECK is `PASS/REVIEW/FAIL` (no `NA`) — `rollup`'s output domain already matches.
  - [ ] Add a `delete_checklist_items(conn, submission_id)` if Task 2 adopts delete-then-insert.

- [ ] **Task 5 — Wire `engine_stage` into `run.STAGES` (AC5)**
  - [ ] Add `app/engine/run_checks.py:engine_stage(ctx: StageContext) -> None` (or a thin wrapper in `app/pipeline/`) that calls `run_checks(ctx.conn, ctx.submission, ...)`. Register it **last** in `app/pipeline/run.py:STAGES` — after `preprocess_stage, ocr_stage, llm_stage`. No edit to `scheduler.py`/`status.py` (the 2.2 seam). The stage's wall-time already rolls into `processing_ms` via the timed loop; the orchestrator still emits `ANALYSIS_COMPLETED` and finalizes to `READY_FOR_REVIEW`.
  - [ ] **Watch the import cycle:** `run.py` imports the stages; have `engine_stage` live where it avoids a `run.py ↔ engine` cycle (the OCR stage uses a `TYPE_CHECKING` guard for exactly this — follow that pattern).
  - [ ] **5s contract:** all of this is background pre-compute — the engine never runs on a `GET` read path.

- [ ] **Task 6 — Register spirits `check_key`s in `docs/data-dictionary.md` (AC1, project-context invariant)**
  - [ ] project-context: every `check_key` MUST resolve to an entry in `docs/data-dictionary.md`. Add the spirits checklist `check_key` catalog (key, name, `check_type`, citation) to §6.2 (or a new "Checklist registry" subsection). CFR citations remain canonical in the ruleset data; the dictionary lists the identifiers. [Source: project-context "Stable identifiers"; data-dictionary §6.2]

- [ ] **Task 7 — Tests (`tests/test_run_checks.py`, ruleset data tests) (all ACs)**
  - [ ] `get_ruleset("DISTILLED_SPIRITS")` returns the expected Check set; each Check has a non-empty `check_key`, a valid `check_type` enum value, a `"27 CFR …"` citation, and a `source_date`. `WINE`/`MALT_BEVERAGE` → empty/minimal (3.8 sentinel).
  - [ ] Executor writes exactly one `checklist_items` row per Check with provenance (`check_key`, `check_type`, `cfr_citation`, `detail`), and `engine_verdict` equals `verdict.rollup` over the per-check verdicts. With only placeholder (`REVIEW`) evaluators, a spirits submission rolls up to `REVIEW`; an empty ruleset → `REVIEW`.
  - [ ] **AC4 guard:** a structural test asserting `27 CFR` appears only in ruleset data modules (+ tests), not in executor/evaluator logic.
  - [ ] Pipeline integration: with `engine_stage` in `STAGES`, a swept spirits submission reaches `READY_FOR_REVIEW` with a complete checklist and non-NULL `engine_verdict`. Use the existing pipeline test fixtures (`tests/test_pipeline.py` patterns); offline by construction (no real OCR/LLM — fakes/seeded text).
  - [ ] **No `verdict → disposition` mapping** anywhere; engine never imports `disposition.py`.

- [ ] **Task 8 — Validate + finalize**
  - [ ] `ruff check` + `ruff format` (line length 100); full `pytest` green (no regressions). Update File List + Change Log + Completion Notes.

## Dev Notes

### ⚠️ Depends on Story 3.1 — implement 3.1 first
3.2 imports `verdict.rollup` and writes to `checklist_items` — **both are authored by Story 3.1** (currently `ready-for-dev`, not yet done). Do not start 3.2 until 3.1's `verdict.py` and the `field_comparisons`/`checklist_items` tables exist. [Source: sprint-status; Story 3.1]

### Scope boundary (what 3.2 IS and is NOT)
- **IS:** the rulesets-as-DATA structures (`Check` + the **distilled-spirits** ruleset authored from `docs/regulatory-rules-distilled-spirits.md`), the `run_checks` executor that writes one provenance-bearing `checklist_items` row per Check and rolls up `engine_verdict`, the **check-evaluator dispatch seam** (so 3.3–3.7 plug in), the pipeline `engine_stage` wiring, and the `check_key` registry in the data dictionary.
- **IS NOT:** the **real check logic** — field match (Story **3.3**), Government Warning verification (Story **3.4**), per-type format checks (Story **3.5**), hybrid class/type with LLM (Story **3.6**), flag-only/conditional checks (Story **3.7**) — and the **wine/malt rulesets at full depth** (Story **3.8**). 3.2 ships the framework + spirits data + honest `REVIEW` placeholders; later stories fill the evaluators behind the seam. Also NOT writing `field_comparisons` (Story 3.3's `field_match` owns those). [Source: epics.md Stories 3.3–3.8]

### "Rulesets-as-data" means Python DATA modules, NOT a DB table
There is **no `rulesets` table**. The architecture tree puts rulesets in `app/engine/rulesets/{distilled_spirits,wine,malt_beverage}.py` as data; the executor writes the *results* to `checklist_items`. The data-dictionary note "Check definitions … may be seeded as a template" is optional — the canonical ruleset is the data module. Keep CFR citations there and nowhere else (AC4). [Source: architecture.md tree lines 342–351; database-schema §1.6, §5; project-context "CFR rules live as data"]

### Determinism taxonomy + the recommend-don't-decide firewall (carry as data; enforce in 3.3–3.7)
- `check_type` (the determinism class) is carried on each `Check` as data. Rule-bound checks are deterministic code; ambiguity ⇒ `REVIEW` (never silent auto-decision); an **LLM opinion alone never yields `FAIL`** (capped at `REVIEW`); the **Government Warning check never calls an LLM**. 3.2 sets up the structure; the per-strategy evaluators (3.3–3.7) enforce these. The hybrid class/type check that *uses* an LLM (capped at REVIEW) is Story 3.6. [Source: project-context Determinism taxonomy; regulatory-rules-distilled-spirits §5.4]
- `engine_verdict` is **advisory only**. `run_checks`/evaluators must not import `disposition.py` and must contain **no `verdict → disposition` mapping**. Per-check verdict domain is `PASS/REVIEW/FAIL/NA`; the rolled-up `engine_verdict` is `PASS/REVIEW/FAIL`. [Source: project-context "Recommend, don't decide"; database-schema §3.2]

### The dispatch seam mirrors the pipeline STAGES seam (the team's established pattern)
Story 2.2 built `run.STAGES` as a registration point where stages plug in with zero scheduler change; 2.3/2.4/2.5 each appended one stage. Reuse that exact mental model for checks: a `{strategy: evaluator}` registry where 3.3–3.7 each register one evaluator with no executor edit. The honest `REVIEW` default keeps the system end-to-end correct **now** (every submission gets a complete checklist) without faking results. [Source: app/pipeline/run.py STAGES seam; project-context anti-pattern "serving a partially-processed submission"]

### Pipeline wiring specifics (read `app/pipeline/run.py` before editing)
- `STAGES = [preprocess_stage, ocr_stage, llm_stage]`; append `engine_stage` last. Stages are `Callable[[StageContext], None]`; `StageContext` carries `conn`, `submission`, `label_images`, and a `scratch` dict (use it to read the LLM stage's extracted fields if needed). The orchestrator wraps each stage so a failure is recorded as an `ANALYSIS_COMPLETED` note and the submission still finalizes (FR-9) — your stage should self-guard too. `engine_verdict` is set by your stage via `ctx.conn`; the orchestrator no longer leaves it NULL (2.2's interim state ends here). [Source: app/pipeline/run.py:46-75, 104-132]
- Avoid a `run.py ↔ engine` import cycle (the OCR stage uses `if TYPE_CHECKING:` for the `StageContext` type — follow it). [Source: app/pipeline/ocr.py:45]

### Repository / Data boundary (follow the 2.1 write-helper style)
`repositories.py` already has `insert_ocr_result`/`insert_llm_result` (raw SQL, parameterized, returns new id) and updaters (`update_status`, `update_processing_ms`). Add `insert_checklist_item` + `set_engine_verdict` in the same style. Raw SQL stays inside `app/db/` only. `get_submission_ocr_text(conn, submission_id)` already concatenates a submission's OCR text — the evaluators' input. [Source: app/db/repositories.py:131,160,203,283,318]

### The spirits ruleset content (authoritative source)
`docs/regulatory-rules-distilled-spirits.md`: §3 always-mandatory (brand name §5.64; class/type §5.141/§5.165; ABV §5.65; net contents §5.70/§5.203; name & address §5.66–5.68; Gov Warning Part 16); §2 same-field-of-vision (§5.63, a `flag-REVIEW`/`MANUAL` positional check); §5 the deterministic Gov Warning approach; §4 conditional/flag-only elements (**defer to 3.7**). **Post-2022 renumbering** — use the citations as printed there (class/type is §5.141, not the old §5.35). `source_date` reflects the post-2022 reorg. [Source: docs/regulatory-rules-distilled-spirits.md §2–§5 + renumbering note]

### Previous story intelligence (3.1 + done 2.x)
- **3.1** owns `verdict.rollup` (severity precedence, `NA`-exclusion, empty⇒`REVIEW`) and the `checklist_items`/`field_comparisons` tables — import/consume, never re-create. [Source: Story 3.1]
- **2.2/2.4/2.5** established the stage seam, the finalize-don't-abort failure posture, and the `TYPE_CHECKING` cycle guard — match them. [Source: app/pipeline/run.py, ocr.py, llm.py]
- House style: `from __future__ import annotations`, `Literal` aliases for enums (mirror `repositories.py`/`contracts.py`), frozen dataclasses for pure data, type hints required, tests mirror `app/` and are offline by construction. [Source: app/contracts.py, app/db/repositories.py]

### Project Structure Notes
- New/edited: `app/engine/rulesets/base.py`, `app/engine/rulesets/distilled_spirits.py` (NEW), `app/engine/run_checks.py` (NEW), `app/db/repositories.py` (UPDATE — checklist writers), `app/pipeline/run.py` (UPDATE — register `engine_stage`), `docs/data-dictionary.md` (UPDATE — check_key registry), `tests/test_run_checks.py` (NEW), `tests/test_pipeline.py` (UPDATE). Paths match the architecture tree exactly. [Source: architecture.md lines 342–351]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.2] — story statement + ACs (rulesets-as-data with CFR citations; executor → checklist_items; rollup → engine_verdict; full provenance; citations-as-data).
- [Source: docs/regulatory-rules-distilled-spirits.md §2–§5] — the authoritative spirits ruleset: elements, citations (post-2022), determinism classes, Gov Warning approach.
- [Source: docs/database-schema.md §1.6 `checklist_items` (check_key/label/cfr_citation/check_type/verdict/detail), §3.2 engine-verdict enum, §5 seeded-vs-computed] — the write target + enums.
- [Source: docs/data-dictionary.md §6.2] — `check_key`/`check_type` definitions; the registry this story extends.
- [Source: _bmad-output/planning-artifacts/architecture.md tree (342–351), Process flow (394), AR-6/FR-18] — engine module layout, rulesets-as-data, the pre-compute flow `run_checks → checklist_items → rollup → engine_verdict`.
- [Source: _bmad-output/project-context.md] — "CFR rules live as data"; determinism taxonomy; "Recommend, don't decide"; pipeline-is-the-only-writer of `checklist_items`/`engine_verdict`; `check_key` must resolve to data-dictionary; 5s contract; anti-patterns.
- [Source: app/pipeline/run.py, app/pipeline/ocr.py, app/db/repositories.py, app/verdict.py (3.1)] — the stage seam, cycle guard, write-helper style, and the rollup contract to build on.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-13 | Story 3.2 drafted — rulesets-as-data (`Check` + distilled-spirits ruleset), `run_checks` executor writing one provenance-bearing `checklist_items` row per Check + `verdict.rollup` → `engine_verdict`, the check-evaluator dispatch seam (3.3–3.7 plug in), `engine_stage` pipeline wiring, and the `check_key` registry in the data dictionary. Status → ready-for-dev. |
