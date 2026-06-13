---
baseline_commit: c00d92dea980abab228640ea2c38af8897881a8e
---

# Story 3.4: Government Warning exact verification

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want the Government Warning verified deterministically against 27 CFR 16.21,
so that wording deviations are caught exactly the same way every time, with no model involved.

## Acceptance Criteria

1. **AC1 — `engine/checks/government_warning.py` verifies deterministically, NO LLM.**
   **Given** `app/engine/checks/government_warning.py` (deterministic, **no model involved**)
   **When** it verifies the warning
   **Then** whitespace is normalized, the **body is compared case-insensitively** (an all-caps body is compliant), and **required casing is enforced**: all-caps `GOVERNMENT WARNING:` header, capital `S`/`G` in "Surgeon General". *(FR-13; project-context "Government Warning check NEVER calls an LLM")*

2. **AC2 — Correct wording PASSES; deviation/absence FAILS with the deviation identified.**
   **Given** the OCR text of a submission's label(s)
   **When** the check runs
   **Then** correct wording with **incidental whitespace** or an **all-caps body → PASS**; a **title-case header, reworded text, or a missing statement → FAIL** with the deviation identified. *(FR-13)*

3. **AC3 — The three outcomes are NEVER conflated.**
   **Given** the possible failure modes
   **When** a verdict is produced
   **Then**: (a) **wording deviation** (present but reworded/mis-cased/mis-punctuated) → **char-diff FAIL** (the specific deviation, diffed against the §16.21 expected text); (b) **entirely absent** from all images → **FAIL with plain copy** ("warning not found" — **no diff against empty**); (c) **bold/caps undeterminable** (a visual-styling attribute OCR cannot recover) → **"couldn't verify" REVIEW**, never a silent PASS. *(FR-13; EXPERIENCE.md honest-state patterns; project-context accessibility char-diff)*

4. **AC4 — The §16.21 expected text + formatting rules live as DATA, not hard-coded in check logic.**
   **Given** the canonical Government Warning text and its formatting rules
   **When** the check reads its "expected" side
   **Then** the §16.21 text + casing rules are stored in the ruleset **data** layer (with `cfr_citation = "27 CFR 16.21"` + `source_date`) and imported by the check — **no CFR text hard-coded inside the check logic** (a grep for the warning text inside `checks/` logic, or `27 CFR` outside data + tests, is a finding). *(AR-6, project-context "CFR rules live as data"; anti-pattern "CFR text hard-coded in Python")*

## Tasks / Subtasks

- [x] **Task 1 — Canonical §16.21 text + formatting rules as ruleset DATA (AC4)**
  - [x] Stored the exact §16.21 statement + formatting rules in `app/engine/rulesets/government_warning.py` (DATA — distinct from the `checks/` logic), shared across all beverage types. `HEADER`, `BODY`, `FULL_TEXT`, `FormattingRules`/`RULES`, `CFR_CITATION = "27 CFR 16.21"`, `SOURCE_DATE`.
  - [x] Canonical text verbatim from §5.1; formatting rules (header all-caps; capital `S`/`G`; one statement; `(1)`/`(2)` markers; bold-but-unverifiable) carried as the `FormattingRules` dataclass.
  - [x] The check **imports** `government_warning as data` and never inlines the warning string (AC4 guard test asserts the body + `27 CFR` literal do NOT appear in `checks/government_warning.py`).

- [x] **Task 2 — `app/engine/checks/government_warning.py` deterministic verifier (AC1, AC2, AC3)**
  - [x] Registered the evaluator on Story 3.2's dispatch seam under `government_warning` (one line in `app/engine/checks/__init__.py`). **No executor edit.** No model import/construction (AC1 AST + source guards).
  - [x] Pipeline implemented: (1) locate via whitespace-tolerant case-insensitive header regex → absent ⇒ plain FAIL no-diff; (2) header all-caps (whitespace-collapsed) → title-case FAIL; (3) body whitespace-collapse + case-insensitive exact-prefix match (punctuation + `(1)`/`(2)` preserved) → reworded ⇒ char-diff FAIL; (4) Surgeon/General capitals enforced only on a mixed-case body; (5) one-statement prefix-match; (6) bold-undeterminable (scratch signal) ⇒ REVIEW; (7) else PASS.
  - [x] Did NOT route the body through `app/normalize.py` — used a local whitespace-only `_collapse_ws` helper (punctuation + case preserved).

- [x] **Task 3 — Deviation/char-diff payload + provenance (AC3, FR-13)**
  - [x] On a wording-deviation FAIL, computed a stdlib `difflib` char-level diff (`_char_diff`, opcode list expected→found) stored in `checklist_items.detail` as a JSON payload with an `outcome` discriminator (`reworded` w/ `diff`+`expected`+`found` · `absent` plain no-diff · `couldnt_verify` · `pass`) so Story 4.5 never diffs against empty.
  - [x] **No `field_comparisons` row** — verified by test; provenance travels in the returned `CheckResult`, `run_checks` (3.2) writes the single `checklist_items` row.

- [x] **Task 4 — Tests (`tests/test_government_warning.py`) — THE three outcomes (all ACs)** — 24 tests: PASS (exact / incidental-whitespace / all-caps body / surrounded), FAIL-reworded (reworded/omitted-clause/missing-marker/mis-punctuation w/ char-diff), FAIL-header-casing, FAIL-Surgeon/General-casing, FAIL-absent (plain, no diff; + no-OCR), REVIEW-bold-undeterminable, no-`field_comparisons`, run_checks integration, AC4 data-only guards, AC1 no-LLM AST + source guards.

- [x] **Task 5 — Validate + finalize** — `bash scripts/ci.sh`: format ✅ · lint ✅ · mypy clean on story files (the sole mypy error is the pre-existing walled-off `auto-run/orchestrate.py:562`, untouched by this story) · **308 passed / 1 skip**. Updated three stale `test_run_checks.py` assertions whose hardcoded `== "REVIEW"` was a 3.2-era all-placeholder artifact (now real `field_match`/`government_warning` evaluators run) — re-pointed them to assert agreement with `verdict.rollup` + legality, preserving each test's intent.

## Dev Notes

### ⚠️ Depends on Story 3.2 — implement the executor/seam first
3.4 registers its evaluator behind Story **3.2**'s dispatch seam (`run_checks` + `Check.strategy="government_warning"` + `insert_checklist_item`). It does **not** need Story 3.1's `normalize()` (it deliberately uses its own whitespace-only helper — see Task 2). Do not start 3.4 until 3.2 is done. [Source: Stories 3.2; sprint-status]

### Scope boundary (what 3.4 IS and is NOT)
- **IS:** the deterministic Government Warning verifier, the canonical §16.21 text + formatting rules as ruleset data, the three-outcome verdict logic, and the char-diff deviation payload (data only).
- **IS NOT:** the §16.22 **type-size / dimensional** verification (explicitly **out of scope** — mm cannot be recovered from a photo; documented for reference only), the **rendering** of the Government Warning comparison card / char-diff (Story **4.5**), field-match checks (Story 3.3), and any LLM involvement (forbidden here). [Source: regulatory-rules-distilled-spirits.md §5.3/§6; epics.md Story 4.5]

### Why this check is the determinism poster child
The required wording is fixed by regulation, so creative deviations — smaller font, title case, paraphrase, omitted clause — are caught reliably by string/regex comparison. **An LLM's nondeterminism is a liability here**, so the check is deterministic by contract and must stay that way. This is the single most rule-bound check in the POC. [Source: regulatory-rules-distilled-spirits.md §5.4 "Why deterministic"; project-context determinism taxonomy; approach.md §4]

### The three outcomes must stay distinct (the heart of FR-13 + AC3)
This is exactly the famous failure of conflation:
- **Reworded** (present, wrong) → a char-diff *against the expected text* — the specialist sees precisely what deviates.
- **Absent** (not present at all) → plain "not found" copy. **Never diff against empty** — a char-diff of the entire warning would be noise, implying the label *tried* and failed when it simply lacks the statement.
- **Undeterminable** (bold/visual styling OCR can't recover) → **REVIEW** "couldn't verify", never a silent PASS — honest about the engine's limits. Pretending bold is fine would be a false PASS; failing it would be a false reject. REVIEW is the only honest call.
Encode the outcome discriminator in `detail` so the UI (4.5) renders the right one. [Source: epics.md Story 3.4 AC; EXPERIENCE.md honest-state patterns; project-context accessibility]

### Casing rules — the subtle part (read carefully)
- **Header**: `GOVERNMENT WARNING:` must be **all-caps** — enforced regardless of body case. `Government Warning:` ⇒ FAIL.
- **Body wording**: compared **case-insensitively** after whitespace collapse — so an **all-caps body is compliant** (PASS) and so is the normal mixed case.
- **Surgeon General**: capital `S`/`G` required — but an all-caps body trivially satisfies this. The only S/G failure is a **mixed-case** body with lowercase `s`/`g`. Implement: `if body is not all-caps: require capital S in "Surgeon" and G in "General"`.
[Source: regulatory-rules-distilled-spirits.md §5.2; epics.md Story 3.4 AC]

### CFR text as data (AC4) — the anti-pattern this guards against
project-context anti-pattern: "CFR text hard-coded in Python." The §16.21 text is rule **data** — it lives in the ruleset data layer (where rulesets-as-data already live, Story 3.2), carrying its citation + source date, and the check logic *imports* it. Storing it in the designated data module (not inline in the comparison code) is what satisfies the invariant and keeps a future §16.21 amendment a one-line data edit, no logic change. [Source: project-context "CFR rules live as data" + anti-patterns; AR-6]

### Previous story intelligence (3.2 + done 2.x)
- **3.2**: the `{strategy: evaluator}` seam, `CheckContext` (OCR text via `repo.get_submission_ocr_text`), `CheckResult`, and `run_checks` (writes the `checklist_items` row from the returned result). Register `government_warning`; no executor change. [Source: Story 3.2]
- **3.2 ruleset**: the `government_warning` Check row already exists (`DETERMINISTIC`, `27 CFR 16.21`) in the spirits ruleset; 3.4 fills its evaluator + the expected-text data. When wine/malt land (Story 3.8) they include the same check — keep the text shared. [Source: Story 3.2 Task 1]
- House style: `from __future__ import annotations`, type hints, raw SQL only in `app/db/`, tests mirror `app/`, offline by construction, ruff line 100. [Source: app/contracts.py, app/db/repositories.py]

### Project Structure Notes
- New/edited: `app/engine/checks/government_warning.py` (NEW — logic), `app/engine/rulesets/government_warning.py` (NEW — the §16.21 text + rules as data, or extend the Check params), the Story-3.2 strategy registry (UPDATE — register `government_warning`), `tests/test_government_warning.py` (NEW). Matches the architecture tree (`engine/checks/government_warning.py # deterministic, no LLM (FR-13)`). [Source: architecture.md line 346]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.4] — story statement + ACs (deterministic verification; the three outcomes never conflated).
- [Source: docs/regulatory-rules-distilled-spirits.md §5] — §5.1 exact text, §5.2 formatting/casing rules, §5.3 type-size table (out of scope), §5.4 deterministic verification approach, "Why deterministic".
- [Source: docs/database-schema.md §1.6 `checklist_items` (check_key/cfr_citation/check_type=DETERMINISTIC/verdict/detail), §3.2 engine-verdict] — the write target.
- [Source: docs/approach.md §4 "Class/type and the Government Warning — how each is verified"] — the warning compares against the statute, not a maker field (so no field_comparisons row).
- [Source: _bmad-output/project-context.md] — "Government Warning check NEVER calls an LLM"; "CFR rules live as data" + anti-pattern "CFR text hard-coded in Python"; determinism taxonomy; accessibility char-diff carries a text equivalent; highest-value test `test_government_warning.py` (the three outcomes); pipeline-is-the-only-writer of `checklist_items`.
- [Source: app/engine/run_checks.py + dispatch seam (3.2), app/db/repositories.py] — the seam + write helpers to build on.

## Dev Agent Record

### Agent Model Used

Amelia (DEV / Senior Software Engineer persona) — Claude Opus 4.

### Debug Log References

- Two red-after-green misses fixed during the green phase: (a) whitespace-tolerant header locator (the incidental-whitespace PASS case doubled spaces inside `GOVERNMENT  WARNING:`) → regex now joins header words on `\s+`; (b) AC4 guard tripped on a `27 CFR` literal in the check docstring → rephrased the prose to `§16.21` so the check module carries no CFR citation literal at all.
- No-LLM guard hardened: the initial bare-substring `"llm"` scan would false-positive on docstring prose; replaced with an AST import scan (`test_check_never_imports_a_model_adapter`) + a targeted code-path token scan (`test_check_constructs_no_model_client`).

### Completion Notes List

- Deterministic (no-LLM) Government Warning verifier implemented on the Story-3.2 dispatch seam — no executor edit. The §16.21 text + formatting rules live as ruleset DATA (`app/engine/rulesets/government_warning.py`), imported by the check; the check module contains neither the warning body nor a CFR citation literal (AC4 guards).
- The three outcomes stay structurally distinct via a JSON `outcome` discriminator in `checklist_items.detail`: `reworded` (char-diff via stdlib `difflib`, expected+found), `absent` (plain copy, NO diff against empty), `couldnt_verify` (bold/visual REVIEW), `pass`. Story 4.5 renders these; 3.4 produces the data.
- Deliberate `normalize()` exception honored: a local whitespace-only `_collapse_ws` preserves punctuation + case (normalize would casefold + strip trailing punctuation, destroying the exact-match assertions). Body compared case-insensitively (all-caps body compliant); header all-caps + Surgeon/General capitals enforced on mixed-case bodies only.
- No `field_comparisons` row (the expected side is the statute, not an application field) — verified by test; `run_checks` writes the single `checklist_items` row.
- Validation: `bash scripts/ci.sh` — ruff format + lint clean; mypy clean on story files (the only error is the pre-existing walled-off `auto-run/orchestrate.py:562`); full suite **308 passed / 1 skip**.
- Regression-touch: three `test_run_checks.py` assertions hardcoding the 3.2-era all-placeholder `"REVIEW"` roll-up were re-pointed to assert agreement with `verdict.rollup` + legality (real `field_match`/`government_warning` evaluators now run). No test weakened; intent preserved.

### Code Review (2026-06-13)

Three parallel adversarial layers (Blind Hunter diff-only, Edge Case Hunter, Acceptance Auditor). Two confirmed false-FAIL classes were empirically reproduced and patched; all four ACs verified satisfied; §16.21 BODY confirmed verbatim against §5.1.

- **Patch 1 — casing check (false-FAIL on over-/under-capitalization).** The substring-membership casing test (`if word not in matched_body`) false-FAILed two compliant shapes: an *over-capitalized* "Surgeon General" (extra capitals are compliant per §5.2 — only the S/G initials are mandated) and an all-caps body carrying one OCR-lowercased stray word. Replaced with a positional initial-letter check `_initial_is_capital(body, word)` that locates each mandated word case-insensitively and asserts only its first letter is uppercase. Anchored to docs/regulatory-rules-distilled-spirits.md §5.2 ("The S in Surgeon and the G in General are capitalized").
- **Patch 2 — multi-occurrence header locate (decoy / reworded-first false-FAIL).** The verifier evaluated only the *first* `GOVERNMENT WARNING` header match, so a decoy header before the real warning — or a reworded front label preceding a compliant back label — false-FAILed. Refactored `government_warning()` to `finditer` all header occurrences and PASS if *any* occurrence is compliant, reporting the first non-pass otherwise. Per-occurrence logic extracted into `_evaluate_occurrence(ctx, ocr_text, match)`.
- **Regression tests (+8 net):** lowercase-surgeon-only / lowercase-general-only FAIL, over-capitalized Surgeon General PASS, all-caps body with one OCR-lowercased word PASS, interleaved-foreign-text-between-clauses FAIL, decoy-header-before-correct-warning PASS, reworded-front-then-correct-back PASS, all-occurrences-deviate FAIL.
- **Deferred** (to `deferred-work.md`): three declared-but-unconsulted `FormattingRules` flags (AC4-intent gap, deferred per anti-over-engineering); whitespace-only normalization does not fold non-whitespace unicode OCR artifacts (latent, ASCII-only corpus today).
- **Dismissed as by-design:** prefix-match trailing-superset (intended), bold→REVIEW path (intended visual-undeterminable seam), casefold length-change slice (unreachable on ASCII).
- Re-validation: `bash scripts/ci.sh` — ruff format + lint clean; mypy clean on story files (only the pre-existing walled-off `auto-run/orchestrate.py:562`); full suite **316 passed / 1 skip**.

### File List

- `app/engine/rulesets/government_warning.py` — NEW (§16.21 text + formatting rules as DATA, AC4)
- `app/engine/checks/government_warning.py` — NEW (deterministic verifier; the three outcomes; char-diff; no-LLM)
- `app/engine/checks/__init__.py` — UPDATED (register the `government_warning` evaluator on the seam)
- `tests/test_government_warning.py` — NEW (32 tests; the three outcomes + AC4 data-only + AC1 no-LLM guards + 8 code-review regression tests)
- `tests/test_run_checks.py` — UPDATED (3 stale `== "REVIEW"` roll-up assertions re-pointed to `verdict.rollup` agreement)

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-13 | Story 3.4 drafted — deterministic (no-LLM) Government Warning verifier on the 3.2 seam: §16.21 expected text + casing rules as ruleset DATA, whitespace-normalized case-insensitive body match with enforced header/Surgeon-General casing, and the three non-conflated outcomes (reworded→char-diff FAIL, absent→plain FAIL, bold/caps undeterminable→REVIEW). Status → ready-for-dev. |
| 2026-06-13 | Story 3.4 implemented (test-first) — §16.21 text/rules as DATA module + deterministic verifier registered on the 3.2 seam (no executor edit), JSON `outcome` discriminator with stdlib char-diff, local whitespace-only normalization (the deliberate `normalize()` exception), AC1 no-LLM AST/source guards, AC4 data-only guards, no `field_comparisons` row. 24 new tests; 3 stale 3.2-era roll-up assertions in `test_run_checks.py` re-pointed to `verdict.rollup`. ci.sh format/lint clean, 308 passed / 1 skip. Status → review. |
| 2026-06-13 | Code review (3 parallel adversarial layers) → 2 patches applied + 8 regression tests, 2 deferrals, 4 by-design dismissals. Patch 1: casing check moved from substring-membership to positional initial-letter (`_initial_is_capital`) — fixes false-FAIL on over-capitalized Surgeon/General and all-caps body with one OCR-lowercased word (anchored to §5.2). Patch 2: header locate scans ALL `GOVERNMENT WARNING` occurrences (`finditer`), PASS if any is compliant — fixes decoy-header-first and reworded-front/correct-back false-FAILs; per-occurrence logic extracted to `_evaluate_occurrence`. ci.sh format/lint/mypy clean, 316 passed / 1 skip. Status → done. |
