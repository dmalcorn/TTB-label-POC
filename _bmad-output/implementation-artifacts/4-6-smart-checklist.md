---
baseline_commit: cb6c33ff526628c84e6105509db0052f778c9597
---

# Story 4.6: Smart checklist

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want a per-type checklist that pre-ticks what the engine auto-verified and highlights what needs my eyes,
so that it works as my table of contents through the review.

## Acceptance Criteria

*(Verbatim from epics.md Story 4.6 — FR-4, UX-DR-12, AR-14.)*

**Given** the checklist generated from the beverage-type ruleset
**When** the review screen renders
**Then** auto-verified PASS items are pre-ticked and muted (the engine's `checklist_items` verdicts); REVIEW/FAIL items are unticked and highlighted; an "N of M done" counter shows progress
**And** clicking a checklist item moves focus + scrolls to its field card
**And** a **manual** tick is persisted server-side via `POST /review/{id}/progress` into the `review_progress.ticked_check_keys` row (the human-tick layer, kept separate from the pipeline-owned `checklist_items`); `GET /review/{id}` rehydrates the merged tick-state, so it persists per Submission across navigate-away **and full browser reload**, clearing only on a recorded disposition
**And** the checklist matches `mockups/review-workspace.html`, side-by-side check in the DoD.

### Acceptance criteria, decomposed (testable)

- **AC1 — Checklist generated from the engine's checklist_items.** The smart checklist
  renders one row per `checklist_items` row for the submission (FR-4: per-type, since the
  ruleset that produced the rows is the beverage-type ruleset), in ruleset (`id`) order,
  each row carrying its label and its engine verdict chip (icon + word, never tint alone)
  + a "auto" machine-tag for engine verdicts. The header reads `Smart checklist — <Type
  Word>` and an "N of M done" counter.
- **AC2 — Pre-tick auto-PASS, muted; highlight REVIEW/FAIL.** A row whose engine verdict is
  `PASS` is pre-ticked and rendered in the muted `done` state. A `REVIEW` row renders the
  `open` (amber) highlighted state; a `FAIL` row renders the `openfail` (red) highlighted
  state — both unticked. `NA` rows are treated as done/muted (not actionable, not a problem).
- **AC3 — "N of M done" counter.** `done = auto-PASS items (+ NA) + manually-ticked items`;
  `M = total checklist rows`. The counter text is `N of M done`, in an `aria-live="polite"`
  region so a manual tick announces the new count (UX-DR-15).
- **AC4 — Click an item scrolls/focuses its field card.** Each row links to its field group
  via a same-page anchor (the chevron's `group-*` anchors / the field-card `#field-<key>`
  ids) so a mouse click moves focus + scrolls there. The mouse path works WITHOUT JS (it is
  an `<a href="#…">`); JS adds smooth-scroll + focus polish (UX-DR-16 two-track).
- **AC5 — Manual tick persisted via `POST /review/{id}/progress`.** Posting a check_key
  upserts the submission's single `review_progress` row, adding the key to
  `ticked_check_keys` (a JSON array). The endpoint is idempotent (re-posting a ticked key is
  a no-op; an untick removes it). It is the ONE permitted cheap web-layer write — never a
  pipeline/engine run (AR-5). Token-gated like every screen. A missing submission ⇒ calm 404.
- **AC6 — `GET /review/{id}` rehydrates merged tick-state.** On render, the checklist's
  ticked set = `{auto-PASS/NA check_keys}  ∪  {review_progress.ticked_check_keys}`. A
  manually-ticked REVIEW/FAIL row therefore renders in the `usercheck` ("you confirmed")
  state after a full browser reload / navigate-away-and-back, and the counter reflects it.
- **AC7 — Separation from pipeline state (AR-14).** Manual ticks live ONLY in the
  web-layer-written `review_progress` table — NEVER in the pipeline-owned `checklist_items`.
  The `GET` render stays a pure pre-computed read (AR-5): it reads `review_progress` (a cheap
  single-row read) and never re-runs the engine.
- **AC8 — Empty checklist is calm.** A submission with no `checklist_items` rows renders an
  honest empty checklist state (no rows, "0 of 0 done"), never a 500.
- **AC9 — Mockup fidelity.** Header `Smart checklist — <Type>`, the `N of M done` counter,
  and the five row states (`done`, `usercheck`, `open`, `openfail`, plus an untouched
  default) match `mockups/review-workspace.html` (spine tokens win on conflict; the verdict
  palette resolves to `brand.css` `--verdict-*`, not the mockup's inline hex).

## Tasks / Subtasks

- [x] **Task 1 — `review_progress` table (schema + connection ledger) (AC: 5, 6, 7)**
  - [x] Add the `review_progress` table to `app/db/schema.sql` (the table-creating story, per
    project-context "create tables only in the story that needs them"). One row per
    submission: `submission_id INTEGER PRIMARY KEY REFERENCES submissions(id) ON DELETE
    CASCADE`, `ticked_check_keys TEXT NOT NULL DEFAULT '[]'` (JSON array of check_key strings),
    `draft_notes TEXT` (declared now for AR-14/Story 4.8 but NOT written by this story),
    `updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP`. Add the `idx`/comment block in
    the same house style as the other tables. New table ⇒ nothing to add to `_ADDED_COLUMNS`
    (that ledger is only for columns added to a pre-existing table).
  - [x] Document the table inline: web-layer-written, separate from `checklist_items`,
    retained through a disposition (Undo can restore), purged by `POST /reset` (Epic 6).
- [x] **Task 2 — repo read + upsert helpers (AC: 5, 6, 7)**
  - [x] `get_review_progress(conn, submission_id) -> ReviewProgress | None` — read the row,
    validate via a new Pydantic `ReviewProgress` model (`ticked_check_keys: list[str]` parsed
    from the JSON column at the read boundary, AR-13; `draft_notes`, `updated_at`). `None`
    when no row yet.
  - [x] `get_ticked_check_keys(conn, submission_id) -> set[str]` — convenience that returns the
    parsed ticked set (`set()` when no row). Used by the GET render path.
  - [x] `set_check_tick(conn, submission_id, *, check_key, ticked) -> None` — upsert: ensure the
    row exists (INSERT … ON CONFLICT(submission_id) DO …), then add/remove `check_key` from the
    JSON array and bump `updated_at`. Idempotent. Raw SQL stays in `repositories.py` (data
    boundary). DOES the write but the caller owns the commit (use `connect(...)` which commits
    on clean exit) — matching the 2.1 convention. Parameterize `submission_id`/`check_key`
    (never string-interpolate). Keep the JSON array sorted+de-duplicated for a stable render.
- [x] **Task 3 — checklist presenter `app/web/review_view.py:smart_checklist(...)` (AC: 1, 2, 3, 6, 8)**
  - [x] Add `smart_checklist(items, *, beverage_type, ticked_keys)` returning the view-model:
    `{"type_word", "rows": [...], "done_count", "total"}`. Each row:
    `{"check_key", "label", "verdict", "chip_class", "icon", "chip_word", "is_problem",
    "state", "ticked", "anchor", "machine_tag"}`.
  - [x] State derivation (pure, data-driven — no template `if` soup):
    - auto-ticked (PASS or NA) → `state="done"`, `ticked=True`, muted;
    - REVIEW row: `ticked` (in `ticked_keys`) → `"usercheck"`; else `"open"`;
    - FAIL row: `ticked` → `"usercheck"`; else `"openfail"`.
  - [x] `ticked` set passed in = the MANUAL set; the auto-tick set is unioned in the presenter
    (`verdict in (PASS, NA)`) so done-count = `len(auto ∪ manual)`.
  - [x] Reuse the existing `_CHIP_CLASS` / `_ALERT_ICON` maps; chip word = verdict word
    (`PASS`/`REVIEW`/`FAIL`) — gov-warning style, not the field-card "match". Machine-tag
    `"auto"` for auto-verified rows; `"you confirmed"` copy for `usercheck` lives in the
    template (mockup verbatim). `type_word` title-cased for the header ("Distilled Spirits").
  - [x] Anchor: map each row to its field group anchor. Reuse `CHECK_KEY_STEP` → `STEP_ANCHOR`
    for mapped keys; `government_warning` → `group-gov-warning`; otherwise `group-conditional`
    (the same buckets the chevron uses). Field-card `id="field-<field_key>"` added to
    `_field_card.html` in Task 4 (the section anchors already resolve).
  - [x] Empty: zero items ⇒ `rows=[]`, `done_count=0`, `total=0` (AC8). Pure, AR-5-safe (no
    OCR/LLM/engine import).
- [x] **Task 4 — `_checklist.html` partial + wire into `review.html` (AC: 1, 2, 3, 4, 9)**
  - [x] New `templates/_checklist.html` reproducing the mockup `.checklist` block: the
    `clhead` (title `Smart checklist — {{ checklist.type_word }}` + right-aligned
    `{{ checklist.done_count }} of {{ checklist.total }} done` counter in
    `aria-live="polite"`), then one `.cli`/`.cli--<state>` row per `checklist.rows`. Each row
    is an `<a class="cli__link" href="#{{ row.anchor }}">` carrying the box glyph
    (✓ for done/usercheck, ✕ for openfail, empty for open), the label, and the right-side
    verdict chip (icon + word + machine/confirmation tag). Use the brand-prefixed BEM classes
    (`cli`, `cli__box`, `cli__label`, `cli__right`, `cli__machine`) — NOT the mockup's bare
    `cli`/`box` — consistent with the field-card/gov-warning partials.
  - [x] Add a hidden form per actionable (REVIEW/FAIL) row OR a `data-check-key` +
    `data-ticked` attribute on the row so `review.js` can POST the tick. Provide a `<noscript>`
    / non-JS fallback note is unnecessary (persistence is a power feature; the render is
    correct without JS) — but the anchor MUST work without JS (it's a real `href`).
  - [x] Insert the checklist `<section id="group-checklist" …>` into `review.html` AFTER the
    gov-warning group (the right-column ordering of the mockup: field cards → checklist).
    Update the placeholder comment in `review.html` that currently says "smart checklist (4.6)
    … LATER" / "Conditional … arrive in Story 4.6" to reflect that 4.6 has landed.
- [x] **Task 5 — `POST /review/{id}/progress` route + GET rehydration (AC: 4, 5, 6, 7, 8)**
  - [x] Add `POST /review/{submission_id}/progress` to `app/web/routes_review.py`: accepts
    form fields `check_key: str` and `ticked: bool` (the tick/untick). 404 on a missing
    submission. Calls `repo.set_check_tick(...)` inside `connect(...)`. Returns `204 No
    Content` (the client updates the UI optimistically) — or a tiny JSON `{ticked, done_count,
    total}` so the counter can update; pick 204 + let JS recompute, keeping the endpoint
    minimal. Token-gated by the existing middleware (no exemption). NO engine/OCR import.
  - [x] Extend the `GET /review/{submission_id}` handler: read
    `repo.get_ticked_check_keys(conn, submission_id)`, build the merged ticked set
    (`manual ∪ auto`) — actually pass the MANUAL set to `smart_checklist`, which unions in the
    auto set itself — and add `"checklist": review_view.smart_checklist(items,
    beverage_type=submission.beverage_type, ticked_keys=manual_keys)` to the template context.
  - [x] Keep the GET a pure pre-computed read: the only added query is the single-row
    `review_progress` read. No write on GET.
- [x] **Task 6 — `static/js/review.js` progressive enhancement (AC: 3, 4, 5)**
  - [x] New same-origin `static/js/review.js` (no CDN/build — NFR-2/UX-DR-6), loaded from
    `review.html` via a `{% block %}`-appended `<script src="/static/js/review.js">`.
  - [x] On a checklist row click: smooth-scroll + move focus to the target field group
    (`scrollIntoView` + `el.focus()` with a tabindex fallback). For an actionable row, toggle
    its tick: optimistic class swap (`open`/`openfail` ↔ `usercheck`), `fetch('POST
    /review/{id}/progress', {check_key, ticked})` (same-origin, no egress), and recompute the
    "N of M done" counter into the `aria-live` region. On a failed fetch, revert the optimistic
    state (honest — never show a tick that didn't persist).
  - [x] Guard: the script must be inert/no-throw when the checklist is absent.
- [x] **Task 7 — CSS for the checklist states in `static/css/brand.css` (AC: 2, 9)**
  - [x] Append a `/* ── Smart checklist (Story 4.6) ── */` block: `.checklist`, `.checklist__head`,
    `.checklist__title`, `.checklist__count`, `.cli`, `.cli__box`, `.cli__label`, `.cli__right`,
    `.cli__machine`, and the state modifiers `.cli--done`, `.cli--usercheck`, `.cli--open`,
    `.cli--openfail`. Resolve all verdict colors to the existing `--verdict-*` /
    `--brand-*` tokens (spine wins — NOT the mockup's `#2E8540`/inline hex). Rows ≥16px
    (older-eyes floor), the `aria-live` counter visible. Reuse `.chip`/`.chip--*` for the
    right-side verdict chip (do not duplicate).
- [x] **Task 8 — tests (test-first; AC: all)**
  - [x] `tests/test_review_view.py`: pure presenter tests for `smart_checklist` — auto-PASS →
    `done`+ticked; REVIEW unticked → `open`; FAIL unticked → `openfail`; REVIEW/FAIL in
    `ticked_keys` → `usercheck`; NA → `done`; done-count math (auto ∪ manual); empty ⇒ 0 of 0;
    type-word header; anchor mapping; AR-5 source guard already covers the module.
  - [x] `tests/test_repositories.py` (or the review repo test file): `set_check_tick` upsert
    creates the row, adds/removes/dedups keys, bumps `updated_at`; `get_ticked_check_keys`
    returns the parsed set / empty; round-trips JSON.
  - [x] `tests/test_review.py`: route tests — GET renders the checklist header + counter + the
    four states; a manual `POST /review/{id}/progress` then a fresh GET shows `usercheck` +
    the incremented counter (rehydration across "reload"); POST is idempotent; POST 404 on a
    missing id; POST is token-gated; the empty-checklist calm state; an AR-5 guard that the
    POST route imports no engine/OCR symbol.

## Dev Notes

### What this story adds, precisely

This is the **human-tick layer** over the engine's read-only checklist. The engine already
wrote one `checklist_items` row per Check (Stories 3.2–3.8) with a per-check `verdict` +
`cfr_citation` (FR-4/FR-18). Story 4.3 reads those rows for the chevron + suggested alert; 4.4
turns the field-match subset into cards; 4.5 turns the gov-warning row into a card. **4.6 turns
the SAME `checklist_items` rows into the smart checklist** and adds the only *mutable* review
state in Epic 4 so far: the specialist's manual ticks, persisted in a NEW
web-layer-owned `review_progress` table (AR-14), upserted by `POST /review/{id}/progress` and
rehydrated by `GET /review/{id}`.

### The four centralized contracts / hard rules (project-context.md)

- **Verdict vs disposition (contract #4 / AR-3 #4).** The checklist is the engine register only
  (PASS/REVIEW/FAIL chips). It emits NO disposition word and never maps a verdict to a
  disposition. A manual *tick* is a "I looked at this" acknowledgement — it is NOT a
  disposition and does NOT change the engine verdict.
- **AR-5 (5-second read contract, inviolable).** `GET /review/{id}` stays a pure pre-computed
  read. The added work is exactly one cheap single-row `review_progress` read. The `POST
  /review/{id}/progress` is the explicit, permitted cheap bookkeeping write (one upsert) on a
  POST action — NEVER an OCR/inference/engine-run. The route must import no `run_checks`,
  `adapters.ocr`, `adapters.llm`, `pipeline.run`, or `pytesseract` symbol (mirrors the existing
  `test_review_route_imports_no_heavy_work` guard — extend it / add a sibling for the POST).
- **CFR-as-data.** Citations shown in the checklist (if any) come from the `checklist_items`
  row, never hard-coded.
- **snake_case everywhere** (DB ↔ Python ↔ JSON). New column/field names: `ticked_check_keys`,
  `draft_notes`, `check_key`, `submission_id`.
- **Pydantic v2 at the read boundary (AR-13).** New `ReviewProgress` model validates the
  `review_progress` row; the JSON `ticked_check_keys` column is parsed to `list[str]` there
  (mirrors how `word_boxes`/`preprocess_log` are JSON in their columns).

### review_progress table (AR-14 / architecture Addendum A)

> *"the specialist's manual checklist ticks + draft Notes persist server-side in a dedicated
> `review_progress` table (one row per submission, web-layer-written — never in the
> pipeline-owned `checklist_items`), upserted via `POST /review/{id}/progress` and rehydrated by
> `GET /review/{id}` so a navigate-away or full browser reload resumes. … `review_progress` is
> retained through a disposition (so Undo can restore the work) and purged by `POST /reset`.
> These are cheap single-row writes on explicit POST actions — the `GET` render stays a pure
> pre-computed read (AR-5 intact)."*

This story creates the table and writes ONLY `ticked_check_keys`. `draft_notes` is declared in
the schema now (so 4.8 needs no migration) but is NOT read/written here. The
"clear-on-disposition" + Undo-restore behavior is **Story 4.8's** `POST /review/{id}/disposition`
/ `POST /review/{id}/undo` — out of scope here; do NOT add those routes. Do NOT touch
`audit_events` (no new event type for a tick).

### Source-tree components to touch

- `app/db/schema.sql` — add `review_progress` table (NEW table; AC5/6/7).
- `app/db/repositories.py` — add `ReviewProgress` model + `get_review_progress`,
  `get_ticked_check_keys`, `set_check_tick`. Raw SQL stays here (data boundary).
- `app/web/review_view.py` — add `smart_checklist(...)` (pure presenter). Reuse `_CHIP_CLASS`,
  `_ALERT_ICON`, `BEVERAGE_WORD`, `CHECK_KEY_STEP`, `STEP_ANCHOR`.
- `app/web/routes_review.py` — extend `GET` context with `checklist`; add `POST
  /review/{id}/progress`.
- `templates/_checklist.html` — NEW partial (mockup `.checklist` block).
- `templates/review.html` — include `_checklist.html` in a new `#group-checklist` section after
  the gov-warning group; refresh the deferral comments.
- `templates/_field_card.html` — add `id="field-<field_key>"` to each card so a checklist row
  can anchor to its card (small, additive).
- `static/css/brand.css` — append the `.checklist`/`.cli--*` state block (spine tokens).
- `static/js/review.js` — NEW progressive-enhancement script (scroll/focus + tick fetch +
  live counter). Loaded from `review.html`.
- `tests/test_review_view.py`, `tests/test_review.py`, `tests/test_repositories.py` (or the
  review repo test) — see Task 8.

### Existing patterns to FOLLOW (read before writing)

- **Presenter shape & reuse**: `app/web/review_view.py` — `government_warning_card` and
  `field_cards` show the chip/icon/verdict-word maps and the "pure read-model, AR-5-safe"
  discipline. `smart_checklist` mirrors that style. The chevron's `CHECK_KEY_STEP` /
  `STEP_ANCHOR` already map a check_key → its field group anchor — reuse them for the row
  anchor (do NOT invent a second mapping).
- **Repo write convention (2.1/2.2/3.2)**: write helpers issue SQL but DO NOT commit; the
  caller owns the unit of work. Here `connect(...)` commits on clean exit, so the route uses
  `with connect(...) as conn: repo.set_check_tick(...)`. Parameterize everything; the
  `# noqa: S608` pattern in the tests is only for test-side dynamic column lists, not prod code.
- **Route patterns**: `app/web/routes_queue.py` shows `Form(...)` parsing + the
  `with connect(settings.database_path) as conn:` block + a calm re-render/redirect. The
  existing `GET /review/{id}` in `routes_review.py` shows the 404-on-missing + TemplateResponse
  shape. Reuse `SPECIALIST_ACTOR` only if you write an audit row — you do NOT here.
- **Template partials**: `templates/_field_card.html` and `templates/_gov_warning_card.html`
  show the brand-prefixed BEM + `.chip`/`.diff-*` reuse + `usa-sr-only` A11Y text-equivalents.
  Match that house style (NOT the mockup's bare class names).
- **CSS**: `static/css/brand.css` from ~line 640 (`.chip`, `.field-card__*`, the Story-4.5
  `.gov-warning-*` block) is the precedent for "spine tokens win; reuse `.chip`/`.diff-*`;
  ≥16px older-eyes floor; comment block per story". Append a parallel `Story 4.6` block.
- **Tests**: `tests/test_review.py` has `_client` (env + `init_db` + `TestClient`),
  `_insert_submission`, `_insert_check`, `_field` helpers, the token-gate test shape, and the
  AR-5 `test_review_route_imports_no_heavy_work` guard. `tests/test_review_view.py` has the
  pure `_item`/`_cmp` builders. Extend BOTH; do not re-scaffold.

### Mockup fidelity (UX-DR-12, binding)

`mockups/review-workspace.html` lines 539–551 (the `.checklist` block) is the reference:
- Header: `Smart checklist — Distilled Spirits` + `5 of 6 done`.
- `cli done` (muted, grey ✓ box) for auto-PASS, right chip `✓ PASS  auto`.
- `cli usercheck` (navy-filled ✓ box) for a human-confirmed item, right `⚠ you confirmed`.
- `cli openfail` (red ✕ box, highlighted) for FAIL, right `✕ FAIL — needs your call`.
- (`cli open` — the REVIEW-unticked amber state — is in the mockup CSS at line 289; render it
  for REVIEW rows: ✓-outline box, right `⚠ REVIEW — needs your eyes`.)
Spine wins on conflict: PASS green is `--verdict-pass` (#216E29), not the mockup's `#2E8540`;
font sizes ≥16px (mockup uses 15px). Mockup-only scaffolding (device frame, the fabricated `5 of
6`, J. Park) is illustrative — the real counter is computed. The DoD includes a documented
side-by-side of the running checklist vs the mockup, state for state.

### A11Y (UX-DR-15)

- The "N of M done" counter sits in an `aria-live="polite"` region so a manual tick announces
  the new count.
- Every state carries icon + WORD (never tint alone): the box glyph + the right-side chip word
  + the machine/confirmation tag. A `usercheck` row says "you confirmed"; an `openfail` says
  "FAIL — needs your call".
- The row is a real focusable `<a>`; tab order = reading order (the checklist sits in the right
  column after the field cards).

### Previous-story intelligence (4.3 → 4.5)

- 4.5 (just committed) added `government_warning_card` + `_gov_warning_card.html` and the
  `.gov-warning-*` CSS block; it parses the engine's JSON `detail` payload defensively and folds
  any ambiguity to REVIEW (never a silent PASS). Carry that fail-safe instinct: an unmapped
  verdict on a checklist row should render as a problem (REVIEW-ish), never silently muted.
- 4.4 established the problems-first stable sort and the `chip`/`diff` reuse; the checklist does
  NOT re-sort (it follows ruleset `id` order — the mockup shows ruleset order, problems mixed in
  place), so render `items` in the order the repo returns them.
- The chevron (`#group-checklist` is a NEW anchor) — add a `Checklist`-less note: the chevron
  steps are unchanged by this story; the checklist's per-row anchors target the EXISTING
  `group-*` anchors + the new field-card ids. Do not add a chevron step.

### Project Structure Notes

- New table created in `schema.sql` (not front-loaded) — matches project-context "create tables
  only in the story that needs them". No `_ADDED_COLUMNS` entry (new table, not an added column).
- New `static/js/review.js` is the first app JS file; same-origin, no build step, no CDN
  (UX-DR-6 / NFR-2). Loaded via a script tag appended in `review.html` (base.html already loads
  USWDS JS; add the app script after content).
- Tests mirror `app/` under top-level `tests/` (AR-11); extend the existing review test files.
- CI: validate on the HOST venv — `bash scripts/ci.sh` (format → lint → mypy → pytest), once at
  the end. Do NOT run CI in the Docker container (it bakes a stale source copy — see CLAUDE.md).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.6: Smart checklist] — the AC.
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR-12] — smart checklist behavior
  (pre-tick auto-PASS, highlight REVIEW/FAIL, "N of M done", persists across reload, clears on
  disposition).
- [Source: _bmad-output/planning-artifacts/epics.md#FR-4] — per-type checklist with verdicts +
  citations.
- [Source: _bmad-output/planning-artifacts/epics.md#AR-14] — `review_progress` table, web-layer
  ticks, `POST /review/{id}/progress`, GET rehydration, retained-through-disposition, purged by
  reset.
- [Source: _bmad-output/planning-artifacts/epics.md#AR-5] — the 5-second read contract.
- [Source: _bmad-output/project-context.md] — the four centralized contracts, the
  verdict-vs-disposition separation, snake_case, CFR-as-data, AR-13.
- [Source: mockups/review-workspace.html lines 268–295, 539–551] — the `.checklist` block +
  state CSS (the fidelity reference).
- [Source: app/web/review_view.py] — presenter patterns to reuse (`_CHIP_CLASS`, `_ALERT_ICON`,
  `BEVERAGE_WORD`, `CHECK_KEY_STEP`, `STEP_ANCHOR`).
- [Source: app/db/repositories.py] — read/write helper conventions, JSON-column handling.
- [Source: app/web/routes_review.py / routes_queue.py] — route + `connect(...)` + Form patterns.

## Dev Agent Record

### Agent Model Used

Claude Opus 4 (claude-opus-4) — Amelia (DEV agent).

### Debug Log References

- Final CI gate (`bash scripts/ci.sh`, host venv): format → lint → mypy → pytest all
  green — **580 passed, 1 skipped**. Two test files needed a `ruff format` pass first
  (`tests/test_review.py`, `tests/test_review_view.py`); applied, no logic change.

### Completion Notes List

- **Test-first, all 8 tasks green.** Built the human-tick layer over the engine's
  read-only `checklist_items` with a NEW web-layer-owned `review_progress` table (AR-14),
  upserted by `POST /review/{id}/progress` and rehydrated by `GET /review/{id}`.
- **Schema (Task 1):** `review_progress` — one row per submission, `ticked_check_keys`
  JSON, `draft_notes` declared now (so Story 4.8 needs no migration) but NOT read/written
  here. New table created in the story that needs it (no front-loading).
- **Repo (Task 2):** `ReviewProgress` Pydantic-v2 model validates the row at the read
  boundary (AR-13); the JSON `ticked_check_keys` column is parsed to `list[str]` there.
  `get_review_progress` / `get_ticked_check_keys` (read) + `set_check_tick` (upsert; issues
  SQL, does NOT commit — caller's `connect()` owns the unit of work). Idempotent: re-tick is
  a no-op, untick removes.
- **Presenter (Task 3):** `smart_checklist(...)` is a pure read-model — reuses
  `_CHIP_CLASS`, `_ALERT_ICON`, `BEVERAGE_WORD`, `CHECK_KEY_STEP`, `STEP_ANCHOR` (no second
  mapping invented). Auto-tick set = PASS/NA unioned with the manual set; done-count =
  len(auto ∪ manual). Five row states: `done`, `usercheck`, `open`, `openfail`. An unmapped
  verdict folds to a problem (REVIEW-ish), never silently muted (4.5 fail-safe instinct).
  Rows follow repo/ruleset order — no re-sort.
- **Route (Task 5):** `GET` gains one cheap single-row `review_progress` read (AR-5 intact).
  `POST /review/{id}/progress` is the explicit permitted cheap bookkeeping write (one
  upsert) → `204 No Content`; the client recomputes the counter. No OCR/inference/engine
  import — the AR-5 guard test (`test_review_route_imports_no_heavy_work`) was extended to
  cover BOTH GET and POST.
- **Contract #4 (verdict vs disposition):** the checklist shows the engine register only
  (PASS/REVIEW/FAIL chip = icon + WORD, never tint alone). A manual tick is an "I looked at
  this" acknowledgement — NOT a disposition and never a change to the engine verdict.
- **JS (Task 6):** `static/js/review.js` — first app JS file; same-origin, no build, no CDN
  (NFR-2 / UX-DR-6). Two-track (UX-DR-16): server render is already correct/usable with JS
  off (each row is a real `<a href="#group-…">`); the script ADDS smooth-scroll/focus +
  optimistic tick POST with honest revert on failed fetch + the `aria-live` "N of M done"
  recount.
- **CSS (Task 7):** appended the `Story 4.6` block to `brand.css` — spine tokens win
  (`--verdict-pass` #216E29, NOT the mockup's #2E8540), ≥16px older-eyes floor, reuses the
  `.chip` precedent. State modifiers `.cli--done/usercheck/open/openfail`.
- **A11Y (UX-DR-15):** counter in `aria-live="polite"`; every state carries box glyph +
  right-side WORD + machine/confirmation tag (state never by color alone).
- **Out of scope, honored:** `draft_notes` declared-not-used (4.8); no
  disposition/undo/reset routes added; `audit_events` untouched (a tick is not an audit
  event).

### File List

**New**

- `templates/_checklist.html` — smart-checklist partial (mockup `.checklist` block).
- `static/js/review.js` — progressive-enhancement script (scroll/focus + tick fetch +
  live counter).

**Modified**

- `app/db/schema.sql` — added the `review_progress` table.
- `app/db/repositories.py` — `ReviewProgress` model + `get_review_progress`,
  `get_ticked_check_keys`, `set_check_tick`.
- `app/web/review_view.py` — added `smart_checklist(...)` presenter.
- `app/web/routes_review.py` — `GET` context gains `checklist`; new
  `POST /review/{id}/progress`.
- `templates/review.html` — include `_checklist.html` in a `#group-checklist` section;
  load `static/js/review.js`.
- `templates/_field_card.html` — `id="field-<field_key>"` anchor per card.
- `templates/base.html` — app-script load hook (after USWDS JS).
- `static/css/brand.css` — appended the Story 4.6 `.checklist`/`.cli--*` block.
- `tests/test_review_view.py` — `smart_checklist` presenter tests.
- `tests/test_review.py` — GET render + POST `/progress` + JS-serving + CSS tests;
  extended the AR-5 import guard.
- `tests/test_repositories.py` — `review_progress` read/write/idempotency tests.

## Change Log

| Date       | Version | Description                                                          | Author |
| ---------- | ------- | -------------------------------------------------------------------- | ------ |
| 2026-06-14 | 1.0     | Story 4.6 implemented test-first; all 8 tasks green; CI gate passed. | Amelia |
| 2026-06-14 | 1.1     | Code review: 3 patches applied (NA chip-word, AC4 focus, usercheck box color); 4 deferrals logged; CI green (584 passed). Status → done. | Amelia |

## Senior Developer Review (AI)

**Reviewer:** Amelia (DEV agent, Claude Opus 4) — adversarial three-layer review
(Blind Hunter / Edge-Case Hunter / Acceptance Auditor).
**Date:** 2026-06-14
**Outcome:** Approved with patches applied. CI gate green (`bash scripts/ci.sh`,
host venv): format → lint → mypy → **584 passed, 1 skipped**.

### Patches applied (3)

1. **NA row mislabeled as "! REVIEW auto" (AC2 violation) — FIXED.** An `NA`
   checklist row is an auto-tick (`state="done"`), so the template renders
   `icon  chip_word  machine_tag`. `_CHECKLIST_CHIP_WORD` / `_ALERT_ICON` had no
   NA entry, so the row fell to the `"REVIEW"` / `"!"` fail-safe and read
   "! REVIEW auto" — wrongly flagging a not-applicable check as a problem. Added a
   dedicated `_CHECKLIST_ICON` map (NA → ✓) and an NA → "N/A" chip word. NA now
   reads "✓ N/A auto". `[app/web/review_view.py]`
2. **AC4 focus jump was a silent no-op — FIXED.** Checklist rows jump to their
   field group and `review.js` moves focus there, but the target `<section>`s were
   not programmatically focusable, so `target.focus()` did nothing for keyboard
   users. Added `tabindex="-1"` to `group-identity` / `group-gov-warning` /
   `group-decide`, and hardened `review.js:focusTarget` to walk up to the nearest
   focusable, non-`aria-hidden` ancestor (covers the `group-mandatory-text`
   in-section span; the standalone `group-conditional` marker degrades WCAG-safely
   — see deferred-work). `[templates/review.html, static/js/review.js]`
3. **`usercheck` box used the green PASS tint instead of the mockup navy accent
   (AC9 fidelity) — FIXED.** A human-confirmed tick is an acknowledgement, not the
   engine's PASS; the box used `var(--verdict-pass)` (even its own comment said
   "navy-filled"). Changed to `var(--brand-secondary)` per
   `mockups/review-workspace.html`, keeping "I looked" visually distinct from "the
   engine passed it" (contract #3/#4). `[static/css/brand.css]`

### Regression tests added

- `test_smart_checklist_na_renders_own_word_and_check_icon_not_review_failsafe`
- `test_review_get_na_row_reads_not_applicable_not_review`
- `test_review_get_group_anchors_are_focusable_for_checklist_jump`
- `test_brand_css_usercheck_box_is_secondary_accent_not_verdict_pass`

### Dismissed (false positives, empirically verified)

- *`dict(row)` would crash* — `app/db/connection.py` sets `conn.row_factory =
  sqlite3.Row` globally; rows index by name.
- *`verdict|lower` crashes on a `None` verdict* — Jinja renders `None|lower` as
  `"none"` (harmless `data-verdict="none"`); verified by probe.
- *`ticked: bool = Form(...)` mis-coerces "false"* — the passing
  `test_review_post_progress_untick_removes_key` proves the untick round-trips.

### Deferred (logged in `deferred-work.md`)

- `usercheck` row elides the verdict word ("you confirmed" only) — mockup-faithful;
  SR-pass enhancement.
- Optimistic-tick UI transient desync under concurrency — self-heals on GET (AR-14).
- No CSRF token on the tick POST — app-wide auth-model decision, low blast radius.
- `group-conditional` standalone anchor not focusable — gains a section in 4.7/4.8.
