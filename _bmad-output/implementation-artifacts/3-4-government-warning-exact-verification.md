---
baseline_commit: c00d92dea980abab228640ea2c38af8897881a8e
---

# Story 3.4: Government Warning exact verification

Status: ready-for-dev

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

- [ ] **Task 1 — Canonical §16.21 text + formatting rules as ruleset DATA (AC4)**
  - [ ] Store the exact §16.21 statement and its formatting rules in the ruleset **data** layer (e.g. `app/engine/rulesets/government_warning.py` as DATA — distinct from the `checks/government_warning.py` logic — or as `params`/`expected` on the `government_warning` `Check` row). The Government Warning (27 CFR Part 16) applies to **all** beverage types, so this is shared data, not spirits-specific.
  - [ ] Canonical text (verbatim from `docs/regulatory-rules-distilled-spirits.md` §5.1, verified against `ref-docs/27 CFR Part 16.pdf` §16.21):
    > **GOVERNMENT WARNING:** (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
  - [ ] Carry the formatting rules as data too (from §5.2): header `GOVERNMENT WARNING:` in all-caps; capital `S` in *Surgeon*, capital `G` in *General*; one contiguous statement; the `(1)`/`(2)` segment markers. `cfr_citation = "27 CFR 16.21"`, `source_date` per Part 16.
  - [ ] The check **imports** this data; it must not inline the warning string in its comparison logic (AC4).

- [ ] **Task 2 — `app/engine/checks/government_warning.py` deterministic verifier (AC1, AC2, AC3)**
  - [ ] Register an evaluator on Story 3.2's dispatch seam under the `government_warning` strategy so the ruleset's `government_warning` Check (`check_type=DETERMINISTIC`, `27 CFR 16.21`) routes here. **No executor edit.** **Never import or construct an LLM adapter** — this check is deterministic by contract (AC1).
  - [ ] Pipeline (from `docs/regulatory-rules-distilled-spirits.md` §5.4):
    1. **Locate** the warning by anchoring on the `GOVERNMENT WARNING:` token in the submission's OCR text (`repo.get_submission_ocr_text`). Not found anywhere ⇒ **AC3(b)**: FAIL, `detail` = plain "Government Warning not found on any label" — **no char-diff**.
    2. **Header caps check** — require the literal `GOVERNMENT WARNING:` token in **all-caps**. A title-case/`Government Warning:` header ⇒ FAIL (deviation: header casing).
    3. **Body wording check** — collapse whitespace (runs of spaces/line breaks → single space) and compare the body **case-insensitively** against the §16.21 expected body, requiring **exact wording + punctuation** including the `(1)`/`(2)` markers. Reworded / mis-punctuated ⇒ **AC3(a)**: FAIL with a **char-diff** (expected vs found) in `detail`.
    4. **Surgeon General casing** — require capital `S`/`G` **unless** the body is all-caps (all-caps is compliant per AC1). Lowercase `s`/`g` in an otherwise mixed-case body ⇒ FAIL (casing deviation).
    5. **One statement / separate & apart** — body is a single contiguous block (no foreign text interleaved between the `(1)` and `(2)` clauses).
    6. **Bold/visual styling undeterminable** ⇒ **AC3(c)**: REVIEW ("couldn't verify bold/visual styling from a photo"), never a silent PASS. (Bold is a styling attribute OCR cannot recover — flag for human, do not pass-or-fail on it.)
    7. **Verdict:** exact wording + correct header caps + casing ⇒ **PASS**.
  - [ ] **⚠️ Do NOT route the warning body through `app/normalize.py`.** `normalize()` casefolds and strips trailing punctuation — which would destroy the exact-punctuation and casing checks this story depends on. Use a **local whitespace-collapse helper** here (whitespace only; preserve punctuation + case for the targeted assertions). This is the deliberate exception to "always use normalize()": that contract is for field-match *equality*; the Gov Warning needs punctuation- and case-sensitive comparison.

- [ ] **Task 3 — Deviation/char-diff payload + provenance (AC3, FR-13)**
  - [ ] On a wording-deviation FAIL, compute a char-level diff (stdlib `difflib` — no new dependency) of expected-vs-found body and store it in `checklist_items.detail` as the deviation data Epic 4's Government Warning comparison card (Story **4.5**) renders. 3.4 produces the **data**; 4.5 renders the visual char-diff + its text equivalent. Keep the three outcomes structurally distinguishable in `detail` (reworded-with-diff vs absent-plain vs couldn't-verify) so 4.5 never shows a diff-against-empty.
  - [ ] **No `field_comparisons` row** — the Government Warning's "expected" side is the *regulation*, not a `submissions` field, so it is not an app↔OCR field-match. Record provenance via the returned `CheckResult` and `source_ocr_result_id` where the matched text came from; `run_checks` (3.2) writes the single `checklist_items` row. [Source: approach.md §4 "Government Warning … compares against the statute rather than a maker field"]

- [ ] **Task 4 — Tests (`tests/test_government_warning.py`) — THE three outcomes (all ACs)**
  - [ ] **PASS:** exact §16.21 text with all-caps header; correct text with **incidental whitespace** (extra spaces/line breaks); **all-caps body** ⇒ PASS.
  - [ ] **FAIL — wording deviation:** reworded/paraphrased, omitted clause, mis-punctuation, missing `(1)`/`(2)` marker ⇒ FAIL with a char-diff in `detail`.
  - [ ] **FAIL — absent:** warning not present in any image's OCR text ⇒ FAIL with plain copy, **no diff** (assert no diff payload).
  - [ ] **FAIL — header casing:** `Government Warning:` (title case) ⇒ FAIL; lowercase `s`/`g` in a mixed-case "surgeon general" body ⇒ FAIL.
  - [ ] **REVIEW — undeterminable:** the bold/visual-styling case ⇒ REVIEW "couldn't verify", **never** a silent PASS.
  - [ ] **No-LLM guard (AC1):** a structural test asserting the check never imports/constructs a model adapter (mirrors the egress rigor of `test_token_gate.py`). This is the named highest-value test `test_government_warning.py` (the three outcomes) in project-context.
  - [ ] **AC4 guard:** the warning text appears only in the ruleset data module (+ tests), not in `checks/government_warning.py` logic.

- [ ] **Task 5 — Validate + finalize**
  - [ ] `ruff check` + `ruff format` (line length 100); full `pytest` green (no regressions). Update File List + Change Log + Completion Notes.

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

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-13 | Story 3.4 drafted — deterministic (no-LLM) Government Warning verifier on the 3.2 seam: §16.21 expected text + casing rules as ruleset DATA, whitespace-normalized case-insensitive body match with enforced header/Surgeon-General casing, and the three non-conflated outcomes (reworded→char-diff FAIL, absent→plain FAIL, bold/caps undeterminable→REVIEW). Status → ready-for-dev. |
