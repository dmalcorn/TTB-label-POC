# Story 4.11: Honest state patterns and accessibility verification

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a label specialist (Dave / Jenny) using the Review Workspace,
I want every degraded / failure / interrupted state to be shown honestly (never a silent stall, blank panel, or color-only signal) and the accessibility floor to hold,
so that I always know what the system did and didn't check, and I can trust the workspace under real-world conditions (a flaky LLM provider, a crashed check, a mid-review refresh, an operator resetting the demo).

## Acceptance Criteria

This is a **verification + honest-states** story over the already-built Review Workspace (Stories 4.1–4.10). Most behaviors already exist; the ACs below pin them with tests AND close the genuine gaps (LLM-unavailable notice, per-check pipeline-failure error state, Notes `aria-invalid`, demo-reset graceful routing).

1. **Cold load renders the result as first paint** — `GET /review/{id}` is a pure DB read of pre-computed rows (AR-5); the result is the first paint, no spinner-then-content dance. The progressive-enhancement scripts are `defer`/end-of-body and additive only. *(verify-and-pin)*

2. **Pipeline failure shows a visible per-check error** — when a check could not run (unreadable image / engine crash), the affected check(s) render a visible honest error state, **not** a silent stall, and the other checks are still shown. *(implement honest error surface for failed checks)*

3. **LLM-unavailable check degrades to OCR-only with a visible `aria-live` notice** — when a field's extraction degraded to OCR because the VLM/LLM was unavailable (the comparison's `extracted_source` is `ocr:…`, no `llm:` source), the card shows the OCR result and a visible notice **"LLM check unavailable — showing OCR result"** in an `aria-live` region. The screen never blocks on an LLM call; with LLMs config-off it still fully functions on OCR-only. *(implement notice + view-model flag)*

4. **Demo reset while an item is open routes back to Queue gracefully** — if an operator resets the queue while a specialist has the item open, recording a disposition (or progress beacon) on a now-missing submission fails gracefully and routes back to Queue with a plain notice; no crash, no orphaned write. *(implement graceful redirect on disposition; the POST disposition path currently raises a raw 404)*

5. **Mid-review refresh resumes from persisted Notes + tick-state** — a full browser refresh resumes from the `review_progress` row (rehydrated `draft_notes` into the Notes textarea + `ticked_check_keys` into the checklist), AR-14. *(verify-and-pin)*

6. **Accessibility floor holds** *(verify-and-pin, with the Notes `aria-invalid` gap closed)*:
   - Color is never alone — every status carries **icon + word** (field cards, checklist rows, gov-warning, suggested-verdict roll-up).
   - Body ≥16px / comparison values 19px / click targets ≥48px (enforced in `brand.css`; pin with a token/CSS-content check).
   - Tab order = reading order (left image panel → right comparison/checklist → bottom action bar) — DOM source order matches; no positive `tabindex` reorders it.
   - `aria-live` regions announce the **"N of M done"** counter (`_checklist.html`) and the **suggested-verdict roll-up** (`review.html` `role="status"`).
   - The char-diff carries a **text equivalent** (`.usa-sr-only`) naming the difference, surviving forced-colors mode (field cards + gov-warning).
   - **Notes validation is announced, not color-only** — when the soft-gate blocks a Needs Correction / Reject, focus moves to the textarea, **`aria-invalid="true"` is set**, and a plain-language error announces via a live region: **"Add a short reason for the maker before sending this back."** The `aria-invalid` clears when the user starts typing. *(implement aria-invalid toggle + align the announced copy with EXPERIENCE.md)*

7. **All microcopy follows the EXPERIENCE.md voice/tone table** — plain, calm, second-person where it addresses the specialist; no jargon, no blame, no false precision.

*(UX-DR-15, UX-DR-17, UX-DR-18, NFR-4, NFR-5)*

## Tasks / Subtasks

- [x] **Task 1 — LLM-unavailable degrade notice (AC: #3)** — SUBMISSION-LEVEL (corrected design)
  - [x] The honest, intended signal (per `app/pipeline/llm.py:25-30`): a submission whose displayed VLM extraction degraded has an `llm_results` row with `status="ERROR"`, `task="extract_fields"`, `is_benchmark_only=0`. Config-off produces NO `llm_results` row (llm.py:113-115 returns early) ⇒ no notice. This is a SUBMISSION-level condition, not per-field (the VLM reads the primary image once for the whole submission).
  - [x] In `app/db/repositories.py`, add `llm_extraction_unavailable(conn, submission_id) -> bool`: True iff a displayed (`is_benchmark_only=0`) `extract_fields` `llm_results` row exists with `status='ERROR'` (mirror `get_latest_llm_extraction`'s SQL shape). Pure read; does not commit.
  - [x] In `app/web/review_view.py`, add `llm_notice(degraded: bool) -> dict | None`: returns `{"text": _LLM_UNAVAILABLE_NOTE}` when degraded, else `None`. Add constant `_LLM_UNAVAILABLE_NOTE = "LLM check unavailable — showing OCR result"` (verbatim, EXPERIENCE.md line 102/145). Keep `review_view.py` import-pure (no engine/OCR/LLM-run imports — the route passes the bool in).
  - [x] In `app/web/routes_review.py:review`, read the flag via `repo.llm_extraction_unavailable(...)` inside the existing `with connect(...)` block (pure DB read, AR-5) and pass `review_view.llm_notice(...)` as `llm_notice` into the template context.
  - [x] In `templates/review.html`, render the notice in an `aria-live="polite"` region (icon + word, never color alone) above the field cards ONLY when `llm_notice` is truthy. Additive — the OCR-fallback field cards still render.
  - [x] TEST FIRST (`tests/test_review_view.py`): `llm_notice(True)["text"] == "LLM check unavailable — showing OCR result"`; `llm_notice(False) is None`.
  - [x] TEST FIRST (`tests/test_review.py`): a submission with an ERROR displayed-extraction `llm_results` row renders the notice text inside an `aria-live` region; a config-off submission (no `llm_results` row) and an OK-extraction submission do NOT render the notice.

- [x] **Task 2 — Per-check pipeline-failure visible error state (AC: #2)**
  - [x] Identify how a failed check is represented in the data (a `checklist_items` row whose `verdict` is REVIEW with an `UNVERIFIABLE` comparison, OR a check_type that failed to produce a comparison). Reuse the existing `unreadable` state where it already means "couldn't read this field" — confirm `_derive_state` already returns `unreadable` for `UNVERIFIABLE` (it does, review_view.py:320-321). The genuine gap is a check that errored entirely (no comparison row) being SILENTLY omitted.
  - [x] In `app/web/review_view.py`, surface checks that the engine could not run as a visible honest error state rather than silent omission. Prefer the smallest change: if a FIELD_MATCH `checklist_items` row carries a `field_comparison_id` that does NOT resolve to a comparison (currently `continue`-skipped at review_view.py:359-360), emit a minimal error card with state `error` and the note "This check couldn't be completed — please verify by eye." instead of dropping it. Keep clean rows untouched; the other checks still render.
  - [x] In `templates/_field_card.html`, render the `error` state with an icon + word (REVIEW register — never a guessed PASS/FAIL) and the plain note.
  - [x] TEST FIRST (`tests/test_review_view.py`): a FIELD_MATCH item whose `field_comparison_id` resolves to no comparison produces a card with `state="error"` and `is_problem=True`, while sibling clean cards are unaffected.

- [x] **Task 3 — Notes `aria-invalid` + corrected announced copy (AC: #6)**
  - [x] In `templates/_action_bar.html`, the Notes textarea: confirm it has an associated `<label>` and `aria-describedby` (it does). No static `aria-invalid` (absent = valid).
  - [x] In `static/js/disposition.js`, when the soft-gate blocks (requiresNotes && notesAreBlank): set `textarea.setAttribute("aria-invalid", "true")` BEFORE/with `announce(...)`; change the announced/announcer message to the EXPERIENCE.md copy: **"Add a short reason for the maker before sending this back."** On the textarea `input` handler, clear `aria-invalid` (`textarea.removeAttribute("aria-invalid")`) so it goes valid again as the user types.
  - [x] TEST FIRST (`tests/test_disposition.py` file-content guard, matching Story 4-10 JS-test style): assert `disposition.js` sets `aria-invalid` on the textarea in the soft-gate branch, clears it on input, and contains the exact EXPERIENCE.md soft-gate string. Keep it a static source guard (no JS runtime), consistent with the existing client-side test convention.

- [x] **Task 4 — Demo-reset-while-open graceful routing (AC: #4)**
  - [x] In `app/web/routes_review.py:record_disposition`, replace the raw `HTTPException(404)` on missing submission (lines 224-225) with a graceful `303 → /queue?gone=1` redirect — the specialist lands on the Queue with a plain notice; no crash, no orphaned write (the connection never wrote anything). Keep the 409 (already-decided) and 400 (validation) paths unchanged.
  - [x] In `templates/queue.html`, render a calm `role="status"` notice when `gone` query param is truthy: "That submission is no longer available — it may have been reset. Here's the queue." (align with empty-queue voice).
  - [x] In `app/web/routes_queue.py` (the GET /queue handler), thread the `gone` query param into the template context (mirroring how `recorded` is threaded).
  - [x] Decide the progress-beacon (`POST /review/{id}/progress`) behavior: it already returns a calm 404 on missing submission and is fire-and-forget from JS (no user-visible crash) — leave it (the beacon is best-effort; the disposition is the user-facing commit). Note this rationale in Dev Notes.
  - [x] TEST FIRST (`tests/test_disposition.py`): posting a disposition for a missing submission returns 303 with `Location` containing `/queue?gone=1` (NOT 404). TEST FIRST (`tests/test_queue.py`): `GET /queue?gone=1` renders the plain notice in a `role="status"` region; `GET /queue` (no param) does not.

- [x] **Task 5 — Verification tests pinning already-built behaviors (AC: #1, #5, #6)**
  - [x] `tests/test_review.py` (or test_review_view.py as appropriate): pin AC1 — the GET review route does only DB reads (no OCR/inference import on the path); the rendered HTML's scripts are `defer`/end-of-body; the result content is present in the first response (no JS required to see the verdict). A source/render assertion is sufficient (e.g. the suggested-verdict word is in the initial HTML).
  - [x] Pin AC5 — `GET /review/{id}` after a `POST /review/{id}/progress` (tick + draft_notes) rehydrates the ticked row + the Notes textarea value (full-refresh resume). Likely already covered by test_review/test_disposition; add an explicit "mid-review refresh resumes" test if not present.
  - [x] Pin AC6 color-never-alone: every verdict chip in the rendered review page carries a WORD adjacent to its icon (assert PASS/REVIEW/FAIL words appear, not just chip classes).
  - [x] Pin AC6 aria-live: `_checklist.html` "N of M done" region has `aria-live="polite"`; `review.html` suggested-verdict has `role="status"`.
  - [x] Pin AC6 char-diff text equivalent: a mismatch card renders the `.usa-sr-only` `_diff_text_equivalent` string.
  - [x] Pin AC6 sizing floor: assert `static/css/brand.css` declares the body/comparison/target tokens at the required floor (≥16px body, 19px comparison values, ≥48px targets) — a CSS-content guard on the relevant custom properties / rules.

- [x] **Task 6 — Microcopy voice/tone pass (AC: #7)**
  - [x] Review every NEW string added in Tasks 1–4 against the EXPERIENCE.md voice/tone table (plain, calm, second-person to the specialist, no jargon/blame/false precision). The new strings are the LLM-unavailable note, the pipeline-error note, the corrected soft-gate copy, and the demo-reset notice — all sourced verbatim or styled to match EXPERIENCE.md. No throwaway copy.

- [x] **Task 7 — Full gate**
  - [x] Run `bash scripts/ci.sh` once at the very end (format → lint → typecheck → tests). All green; no skipped/weakened tests.

## Dev Notes

### What this story is

A capstone verification story for the Review Workspace. Stories 4.1–4.10 built the screen; 4.11 proves it behaves honestly under degradation/failure/interruption and that the accessibility floor holds, closing four genuine gaps. **Do not re-architect** — make the smallest honest change per gap and pin the rest with tests.

### Architecture constraints (project-context.md — binding)

- **AR-5 (5-second read contract):** `GET /review/{id}` is a pure DB read of pre-computed rows — NEVER OCR/inference/model call on the request path. The LLM-unavailable signal is read from already-stored DATA (`v_field_comparisons.extracted_source`), NOT by probing a provider at render time. Do not import OCR/LLM/engine-run modules into `review_view.py`. The only permitted web-layer write is the cheap `review_progress` upsert on explicit POST.
- **Contract #4 — verdict vs disposition separation:** the engine register is `{PASS, REVIEW, FAIL}` (advisory); disposition is `{APPROVED, NEEDS_CORRECTION, REJECTED}` (human). Honest error / LLM-unavailable / pipeline-failure states stay in the VERDICT register (REVIEW — "needs your eyes"), NEVER a guessed PASS/FAIL and NEVER a disposition. `review_view.py` emits no disposition word.
- **Contract #3 — centralized roll-up:** `suggested_verdict` rolls up via `app.verdict.rollup`; never re-implement severity precedence. Pipeline-error cards must not change the engine's stored verdict — they reflect data, they don't recompute it.
- **CFR-as-data / state copy as data:** new copy strings are module-level constants (mirroring `_SOFT_NOTE`, `_NOT_FOUND_NOTE` etc. at review_view.py:232-236), not scattered template literals.
- **snake_case everywhere; type hints required; ruff line-length 100.**

### Source tree components to touch

- `app/web/review_view.py` — add `llm_unavailable` per-card flag (Task 1), `error` state for unresolved comparisons (Task 2), the new copy constants. Pure read-model; no new imports from engine layers.
- `templates/_field_card.html` — render LLM-unavailable `aria-live` notice (Task 1) + `error` state (Task 2), both icon+word.
- `static/js/disposition.js` — `aria-invalid` toggle + corrected soft-gate copy (Task 3). Keep the IIFE / inert-when-absent / no-throw shape.
- `templates/_action_bar.html` — confirm Notes textarea label/describedby (Task 3); no static `aria-invalid`.
- `app/web/routes_review.py` — graceful 303 redirect on missing submission in `record_disposition` (Task 4).
- `app/web/routes_queue.py` — thread `gone` param into context (Task 4).
- `templates/queue.html` — render the `gone` plain notice (Task 4).

### Current state of files being modified (read before editing)

- **`routes_review.py:record_disposition` (lines 189-242):** validates disposition enum (400), soft-gates required notes (400), reads submission and raises raw `HTTPException(404)` at 224-225 when missing, then `lifecycle.record_decision` (409 on already-DECIDED), else `303 → /queue?recorded={id}`. **Change ONLY the 404 branch → 303 → /queue?gone=1.** The connection has not written when the submission is missing, so there is no orphaned write to undo. Leave validation/409/success paths intact.
- **`routes_review.py:set_progress` (lines 153-186):** already returns calm 404 on missing submission; it is a best-effort JS beacon (204 on success). LEAVE AS-IS (rationale: fire-and-forget; the disposition is the user-facing commit). Document this.
- **`review_view.py:field_cards` (lines 335-415):** joins FIELD_MATCH items to `v_field_comparisons` by FK; items with `field_comparison_id is None` are correctly skipped (not field cards). The gap is items WITH a `field_comparison_id` that does NOT resolve (`by_id.get(...) is None` → `continue` at 359-360) being silently dropped — that is the pipeline-failure-omission to surface as an `error` card. `_derive_state` already returns `unreadable` for `UNVERIFIABLE`/`MISSING` comparisons (handles the "couldn't read" class). `extracted_source` is the `ocr:`/`llm:`/None display label from the view (repositories.py:147) — the LLM-unavailable signal.
- **`disposition.js` (soft-gate branch lines 203-211):** currently `announce("A reason is required for Needs Correction or Reject.")` + `textarea.focus()`. Add `aria-invalid="true"` set here; clear on the existing `input` listener (line 66, `scheduleSave`); change the announced string to "Add a short reason for the maker before sending this back."
- **`_field_card.html` (78 lines):** char-diff `.usa-sr-only` text equivalent at 24-26; icon+word chip at 15-18. Add the two new conditional blocks keyed on `card.llm_unavailable` and `card.state == 'error'`.
- **`_checklist.html:21`:** "N of M done" already `aria-live="polite"`. **`review.html:64`:** suggested-verdict already `role="status"`. **Pin, don't change.**

### Testing standards

- pytest in top-level `tests/`. Server-rendered assertions hit the route via the test client and assert on HTML content (see existing `tests/test_review.py`, `tests/test_disposition.py`, `tests/test_queue.py`, `tests/test_review_view.py`).
- For client-side JS (`disposition.js`), follow Story 4-10's **file-content guard** convention: assert on the JS SOURCE string (the handler sets `aria-invalid`, clears on input, contains the exact copy) — no JS runtime in the test suite.
- TEST FIRST per task: write the failing test, watch it fail (red), implement, watch it pass (green), refactor. Validate on the HOST venv: `.venv/Scripts/python.exe -m pytest -q` during the loop; `bash scripts/ci.sh` once at the end. Do NOT run CI in Docker (stale snapshot — CLAUDE.md).
- Never weaken or skip a test to make the suite pass.

### Project Structure Notes

- Aligns with the established web layer: routes in `app/web/routes_*.py`, presenters in `app/web/review_view.py`, templates in `templates/`, client JS in `static/js/`. No new modules required; all changes extend existing files.
- No conflicts with the four centralized contracts — this story reads existing pre-computed data and adds presentation/UX honesty; it adds no new contract and touches no pipeline-owned table.
- The `gone` query param mirrors the existing `recorded` param flow on `/queue` (queue.html:43-50, threaded from the queue route) — same shape, calm `role="status"` banner.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.11] — ACs verbatim (lines 690-696): cold load first paint; per-check pipeline error; LLM-unavailable OCR-only + aria-live notice; demo-reset graceful routing; mid-review refresh resume (AR-14); accessibility floor; EXPERIENCE.md voice/tone. Tags UX-DR-15, UX-DR-17, UX-DR-18, NFR-4, NFR-5.
- [Source: EXPERIENCE.md#State Patterns line 101] — pipeline failure: "Visible honest error state on the affected check(s), not a silent stall. Other checks still shown."
- [Source: EXPERIENCE.md#State Patterns line 102 / line 145] — LLM unreachable: degrade to OCR-only with visible notice **"LLM check unavailable — showing OCR result"**, announced via aria-live; never blocks on an LLM call.
- [Source: EXPERIENCE.md#State Patterns line 116] — demo reset while open: "recording a disposition fails gracefully (item no longer exists) and routes back to Queue with a plain notice; no crash, no orphaned write."
- [Source: EXPERIENCE.md#State Patterns line 114] — browser refresh mid-review: tick-state + Notes persist server-side, resume on refresh.
- [Source: EXPERIENCE.md#Accessibility Floor lines 141-148] — color never alone (icon+word); body ≥16px / comparison 19px / targets ≥48px; tab order = reading order; aria-live for "N of M done" + suggested-verdict roll-up; char-diff text equivalent surviving forced-colors; Notes validation accessible: focus moves, `aria-invalid` set, live-region error **"Add a short reason for the maker before sending this back."**, never red border alone.
- [Source: _bmad-output/project-context.md] — AR-5 read-path purity; four centralized contracts; verdict vs disposition separation; snake_case; copy-as-data.
- [Source: app/web/routes_review.py:189-242] — record_disposition (the 404→303 change).
- [Source: app/web/review_view.py:335-415] — field_cards (llm_unavailable flag + error card).
- [Source: static/js/disposition.js:203-211] — soft-gate branch (aria-invalid + copy).
- [Source: app/db/repositories.py:125-148] — FieldComparison.extracted_source = ocr:/llm:/None.

## Dev Agent Record

### Agent Model Used

claude-opus-4 (Amelia — Senior Software Engineer)

### Debug Log References

### Completion Notes List

Ultimate context engine analysis completed — comprehensive developer guide created.

**Code review (2026-06-14, Amelia — DEV Agent): review -> done. 0 patches applied, 0 deferred, all findings dismissed.** Three-layer adversarial review (Blind Hunter diff-only / Edge-Case Hunter / Acceptance Auditor). Acceptance Auditor: ACCEPTANCE-COMPLETE — all 7 ACs + 7 Tasks met and pinned; AR-5 read-path purity, Contract #4 (verdict↔disposition separation), copy-as-data, and snake_case+type-hints all hold. Blind Hunter's 3 "Major" test-correctness flags (`card` undefined; cross-function `src` scope; `_error_card` bare-subscript KeyError) were ALL THREE refuted against the real files — artifacts of the summarized diff (the real tests carry `card = cards[0]` and local `src` reads; `_error_card`'s `vdt` is hardcoded `verdict.REVIEW`, present in all four lookup maps, so no KeyError). Edge Hunter found no Blocker/Major/Minor. The lone candidate patch — Auditor NIT-1 (AC2 error card pinned only at view-model level, no route-level rendered-HTML test) — was empirically dismissed via a repo-root `_probe.py`: the dangling-FK error state is UNREACHABLE through the live DB (`PRAGMA foreign_keys=ON` rejects a dangling `field_comparison_id`; `ON DELETE SET NULL` routes a deleted comparison to the `field_comparison_id IS NULL` *skip* path, not the *error* path), so the view-model unit test is the correct and only honest level — a route test would have to subvert the DB contract. Cosmetic nits (no bespoke `.field-card--error`/`.llm-notice` CSS; assertive-vs-polite announcer asymmetry) dismissed as by-design. No project invariant regressed. Full host gate green: format → lint → mypy (88 files) → 690 passed / 1 skipped.

### File List
