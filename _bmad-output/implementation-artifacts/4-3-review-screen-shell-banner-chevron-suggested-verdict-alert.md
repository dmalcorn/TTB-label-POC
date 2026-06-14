---
baseline_commit: 0ffb4cbe267e7228707a5117dce51eb6acd302ad
---

# Story 4.3: Review screen shell — banner, chevron, suggested-verdict alert

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want the Review Workspace to open instantly with the beverage banner, a progress
chevron, and the suggested-verdict alert,
so that the moment a Submission loads I am oriented — what kind of product this is,
how the page is organized, and the engine's advisory roll-up — before I look at any
single field.

## Acceptance Criteria

1. **(Given** a Submission served by `POST /next` (Story 4.1/4.2, now `IN_REVIEW`),
   **When** I open **`GET /review/{id}`, Then)** the Review Workspace **shell**
   renders at **200** as a pure **pre-computed DB read** (AR-5 — no OCR / inference /
   model-layer call, no `run_checks`, on the request path), carrying the three shell
   elements: the **beverage-type banner**, the **chevron / step indicator**, and the
   **suggested-verdict alert**. The route is **token-gated** by the existing
   middleware (no exemption added), exactly like `/queue`. *(FR-3, AR-5, NFR-1)*
2. **(And)** the **beverage-type banner** renders the type **word + accent** the
   instant the screen loads — `DISTILLED SPIRITS` on `{colors.spirits}` (amber/brown,
   white text), `WINE` on `{colors.wine}` (burgundy, white text), or `BEER` on
   `{colors.beer}` (gold, **dark ink** text — white fails AA on gold). The type
   **word is always present** (color reinforces identity, never replaces it); the
   accent resolves through the linked self-hosted `brand.css` (`--bev-*` tokens,
   `beverage-banner-*` component), **never** inline `<style>`. The stored enum maps
   to the displayed word (`DISTILLED_SPIRITS→"DISTILLED SPIRITS"`, `WINE→"WINE"`,
   `MALT_BEVERAGE→"BEER"`). *(FR-3, DESIGN.md beverage accents, UX-A11Y colorblind)*
3. **(And)** the **chevron / step indicator** is a progress **map**, not a wizard
   (U4): the ordered steps **① Identity → ② Mandatory text → ③ Gov. Warning →
   ④ Conditional → ⑤ Decide**. The **Conditional step ④ appears ONLY when the
   submission's checklist actually contains a conditional/flag-only check**; when it
   is absent the remaining steps **renumber cleanly** (Decide becomes ④) so the
   numbering is never off-by-one. The current/active marker is conveyed as **text**
   (a literal "step 1 of N" / `aria-current`), **not by color/contrast alone**. The
   step→field-group mapping is carried as **DATA** (a `check_key → step` map), not
   hard-coded rule logic scattered in Python. Clicking a step is a **same-page
   anchor** to that field group's id (the field cards themselves arrive in Stories
   4.4–4.6; for the shell the anchors target stable placeholder section ids that
   later stories populate). *(FR-3, EXPERIENCE.md chevron, UX-DR-4)*
4. **(And)** the **suggested-verdict alert** is a USWDS Alert in the matching verdict
   **tint**, labeled **"Suggested:"**, carrying the verdict **icon + word** (never
   tint alone): it is the advisory roll-up over the submission's checks
   (`"4 of 6 passed automatically; 2 need your review"` style copy) computed via the
   **centralized `app/verdict.py:rollup`** over the submission's `checklist_items`
   verdicts — the **same** roll-up the engine used, so engine and UI can never
   disagree. The alert is **advisory register only** — never a button, never
   pre-selects a disposition, never inherits a disposition's wording. The copy
   **returns authority to the human** ("You decide."). When the submission has **no**
   checklist rows (an empty/unmapped ruleset), the alert falls back to **REVIEW** per
   `rollup`'s empty-policy with honest copy ("nothing was auto-verified — your call"),
   never a silent PASS. *(FR-3, contract #3 verdict-vs-disposition, EXPERIENCE.md
   suggested-verdict alert)*
5. **(And)** an **unknown / not-`IN_REVIEW`-yet** submission id is handled **calmly,
   not with a stack trace**: a `GET /review/{id}` for a **missing** id returns **404**
   (FastAPI `HTTPException`, not a 500); a `GET /review/{id}` for an id that exists is
   served (the screen does not gate on lifecycle status in this shell story — a
   specialist who navigates back to an already-opened `IN_REVIEW` item still sees it).
   The screen reproduces `mockups/review-workspace.html` for the three shell elements
   only; mockup scaffolding (device frame, the J. Park placeholder agent name,
   fabricated demo data) and the **later-story regions** (field cards 4.4–4.6, image
   panel 4.7, disposition bar 4.8) are **out of scope** and represented by inert,
   clearly-labelled placeholder sections that the chevron anchors can target.
   *(UI-fidelity standard, FR-3 scope boundary)*

## Tasks / Subtasks

- [x] **Task 1 — checklist read helper (test-first, AC4).** In
  `app/db/repositories.py`, add a typed read over `checklist_items` (raw SQL stays in
  the data boundary):
  - A Pydantic `ChecklistItem(BaseModel)` mirroring the columns the shell needs:
    `id: int`, `submission_id: int`, `check_key: str`, `label: str | None`,
    `cfr_citation: str | None`, `check_type: str | None`, `verdict: str | None`,
    `detail: str | None` (field names 1:1 with the schema columns, snake_case).
  - `list_checklist_items(conn, submission_id) -> list[ChecklistItem]` —
    `SELECT * FROM checklist_items WHERE submission_id = ? ORDER BY id` (stable
    insertion order = ruleset order). Returns `[]` when the submission has no rows.
  - Tests in `tests/test_repositories.py`: rows returned in id order; empty list for a
    submission with no checklist; the `verdict`/`check_type` values round-trip as the
    stored UPPER_SNAKE strings.

- [x] **Task 2 — review presenter module (test-first, AC2/AC3/AC4).** Add a NEW pure
  module `app/web/review_view.py` — the read-only **presenter** that turns a
  `Submission` + its `list[ChecklistItem]` into the shell view-model. It imports
  `app.verdict` (the centralized roll-up) and **nothing** from the OCR/LLM/engine-run
  layers (AR-5 purity — assert via a source guard). Contents, all snake_case:
  - **Banner.** `BEVERAGE_WORD: dict[str, str] = {"DISTILLED_SPIRITS": "DISTILLED
    SPIRITS", "WINE": "WINE", "MALT_BEVERAGE": "BEER"}` and
    `BEVERAGE_ACCENT_CLASS: dict[str, str] = {"DISTILLED_SPIRITS":
    "beverage-banner--spirits", "WINE": "beverage-banner--wine", "MALT_BEVERAGE":
    "beverage-banner--beer"}`. A `banner(beverage_type) -> dict` returning
    `{"word", "accent_class"}`; an unmapped/unknown enum degrades to the word
    title-cased and the neutral (no-accent) class — never raises.
  - **Chevron steps as DATA.** `STEP_LABELS` — the ordered tuple
    `("Identity", "Mandatory text", "Gov. Warning", "Conditional", "Decide")` — and
    `CHECK_KEY_STEP: dict[str, str]` mapping each known `check_key` to its step label
    (Identity: `brand_name`, `class_type_designation`, `name_address`; Mandatory text:
    `alcohol_content`, `net_contents`, `abv_format`, `standards_of_fill`,
    `proof_abv_consistency`; Gov. Warning: `government_warning`). The **Conditional**
    step is the bucket for any `check_key` NOT in `CHECK_KEY_STEP` whose
    `check_type == "MANUAL"` OR check_key indicating a §4/§7 conditional disclosure
    (the flag-only/positional checks — `same_field_of_vision` and the wine/malt
    conditional disclosures from Story 3.7/3.8). **Decide** is always last and carries
    no checks. Keep this mapping as DATA so a ruleset change is a data edit, not logic.
  - `chevron(items) -> list[dict]` — builds the visible step list: always include
    Identity, Mandatory text, Gov. Warning, Decide; include **Conditional** ONLY when
    at least one item maps to it. Each step dict carries `{"label", "number",
    "anchor", "present"}` where `number` is the 1-based position **after** the
    Conditional step is included/excluded (so Decide is ⑤ with Conditional, ④
    without), `anchor` is the stable section id (e.g. `"group-identity"`,
    `"group-mandatory-text"`, `"group-gov-warning"`, `"group-conditional"`,
    `"group-decide"`). No "current step" is computed server-side for the shell beyond
    marking Decide as the terminal step; mark the FIRST step `is_current=True` so the
    `aria-current`/"step 1 of N" text has a deterministic anchor (a real cursor is a
    later interaction story).
  - **Suggested-verdict alert.** `suggested_verdict(items) -> dict` returning
    `{"verdict", "alert_class", "icon", "passed", "total", "needs_review",
    "summary"}`: `verdict = app.verdict.rollup(i.verdict for i in items)` (the
    centralized roll-up — do NOT re-implement severity precedence here); `total` =
    count of non-`NA` items; `passed` = count of `PASS`; `needs_review` =
    `total - passed`; `alert_class`/`icon` selected from the verdict
    (`PASS→usa-alert--success "✓"`, `REVIEW→usa-alert--warning "!"`,
    `FAIL→usa-alert--error "✕"`); `summary` is the plain-language roll-up sentence that
    **returns authority to the human** ("… You decide."). Empty `items` ⇒ verdict
    `REVIEW`, `total == 0`, honest "nothing was auto-verified" summary. NEVER emit a
    disposition word here (contract #3).
  - Tests in a NEW `tests/test_review_view.py`: banner word/accent per type +
    unknown-type degrade; chevron includes Conditional ONLY when a conditional item is
    present and renumbers Decide (⑤ vs ④) accordingly; chevron anchors are the stable
    section ids; `suggested_verdict` rolls up via `verdict.rollup` (any FAIL⇒FAIL; any
    REVIEW⇒REVIEW; all-PASS⇒PASS; empty⇒REVIEW) with correct passed/total/needs_review
    counts; the alert carries icon+word and never a disposition string; an AST/source
    guard asserts `review_view` imports neither `run_checks` nor the ocr/llm adapters
    nor `pipeline.run`.

- [x] **Task 3 — `GET /review/{id}` route (test-first, AC1/AC5).** Add a NEW router
  module `app/web/routes_review.py` exposing `router = APIRouter()` with a single
  `GET /review/{submission_id}` handler, and `include_router` it in
  `app/main.py:create_app` (after the queue router; **no** exemption added so the
  token gate covers it). The handler:
  - opens a short read connection (`app.db.connection.connect` / `get_connection`),
    `repo.get_submission(conn, submission_id)`; if `None` ⇒
    `raise HTTPException(status_code=404, detail="Submission not found")` (calm 404,
    never a 500).
  - reads `repo.list_checklist_items(conn, submission_id)`, builds the view-model via
    `review_view.banner / chevron / suggested_verdict`, and returns
    `templates.TemplateResponse(request, "review.html", {...})`.
  - is a **pure read** — NO OCR/inference/model import, NO `run_checks`, NO status
    write (opening the item already happened in `POST /next`; the shell GET must be
    idempotent and side-effect-free per AR-5). Assert read-path purity with the same
    source-guard style as `test_queue.py` (no `pytesseract` / `adapters.ocr` /
    `adapters.llm` / `pipeline.run` / `run_checks` import reachable from the route).
  - Tests in a NEW `tests/test_review.py`: 200 + the banner word, the chevron, and the
    `Suggested:` alert text present for a seeded `IN_REVIEW` spirits submission with a
    checklist; a wine submission shows `WINE` + burgundy accent class; a beer
    submission shows `BEER` + the dark-ink accent class; a missing id ⇒ 404; the route
    is token-gated (a request without the cookie when `ACCESS_TOKEN` is set ⇒ redirect
    to `/access`); the rolled-up verdict word matches `verdict.rollup` over the seeded
    checklist; a submission with a conditional/flag-only checklist row shows the ⑤-step
    chevron, one without shows the ④-step chevron.

- [x] **Task 4 — `review.html` template (AC2/AC3/AC4/AC5).** Add
  `templates/review.html` extending `base.html`, reproducing the three shell elements
  from `mockups/review-workspace.html` and **only** those (later regions are inert
  placeholders). No inline `<style>`, no JS — tokens resolve through `brand.css`:
  - The **beverage banner** — a full-width `<div class="beverage-banner {{
    banner.accent_class }}">` with the `{{ banner.word }}` in 28px/700 (the type word
    always rendered as text).
  - The **chevron** — an ordered list/nav of `{{ chevron }}` steps, each an
    `<a href="#{{ step.anchor }}">` carrying the step `number` glyph + label;
    `aria-current="step"` + a visually-rendered "step 1 of N" text on the current
    step (text, not color alone). `role="navigation"` / `aria-label="Review progress"`.
  - The **suggested-verdict alert** — a USWDS `<section class="usa-alert {{
    alert.alert_class }}">` with `Suggested:` label + `{{ alert.icon }}` + `{{
    alert.verdict }}` word + `{{ alert.summary }}` roll-up sentence, in a polite
    `role="status"` region so a screen reader announces it on load (EXPERIENCE.md
    "announce on load"). Advisory register only — NOT a `<button>`.
  - Stable placeholder sections `<section id="group-identity"> … #group-mandatory-text
    … #group-gov-warning … #group-conditional … #group-decide` so the chevron anchors
    resolve now and Stories 4.4–4.8 fill them. Each is clearly an inert "arrives in a
    later story" placeholder (not a fake live control).

- [x] **Task 5 — brand.css shell styles (AC2/AC3, no inline style).** Append to
  `static/css/brand.css` (after the Queue block) the Review-shell rules — same-origin,
  tokens only:
  - `.beverage-banner` (full-width, 28px/700 word, padding, radius) +
    `.beverage-banner--spirits { background: var(--bev-spirits); color: #fff; }`,
    `--wine { background: var(--bev-wine); color: #fff; }`,
    `--beer { background: var(--bev-beer); color: var(--brand-ink); }` (dark ink — AA),
    and a neutral default for the unknown-type degrade.
  - `.chevron` / `.chevron__step` / `.chevron__step[aria-current="step"]` — the
    step-map row with ✓/number glyphs, a **non-color** current marker (the "step N of
    M" text + a border/weight change, not contrast alone), ≥48px targets, visible
    `:focus-visible` ring (`--brand-primary-light`).
  - `.suggested-alert` shell tweaks layered on the USWDS Alert (the `Suggested:`
    label weight); the **verdict tints/foregrounds come from the `--verdict-*`
    tokens** already declared — paired with icon + word, never tint alone, never on
    chrome.
  - `.review-placeholder` for the inert later-story sections (dashed, muted — visibly
    deferred, like the Queue `.deferred` Phase-2 box).

- [x] **Task 6 — validate (host venv).** Run the targeted suites while iterating
  (`test_repositories.py`, `test_review_view.py`, `test_review.py`), then the full
  gate **once** at the end: `bash scripts/ci.sh` (format → lint → mypy → tests). The
  suite must be green. Update
  `_bmad-output/implementation-artifacts/sprint-status.yaml` story `4-3` → `review`.

## Dev Notes

### Scope boundary — this is the SHELL only

Story 4.3 builds **only** the three orienting shell elements (banner, chevron,
suggested-verdict alert) on the two-column Review page. The field comparison cards
(4.4), Government Warning card (4.5), smart checklist (4.6), label-image panel +
Enhance (4.7), and the disposition action bar + Notes (4.8) are **later stories**.
This story therefore renders stable, clearly-inert placeholder sections (the chevron
anchor targets) that those stories fill in — never fake live controls. The
`GET /review/{id}` route is the one `POST /next` already redirects to (Story 4.1
asserted only its `Location` header); this story makes the target a real 200.

### Centralized contracts — import, never re-implement

- **Roll-up (contract #3).** The suggested-verdict alert MUST roll up via
  `app/verdict.py:rollup` — the SAME function the engine used to set
  `submissions.engine_verdict` (Story 3.1/3.2). Do not re-derive severity precedence
  in the presenter. This is what guarantees engine and UI can never disagree.
- **Verdict vs disposition (contract #3).** The alert is advisory — engine register
  (PASS/REVIEW/FAIL), muted Alert, "Suggested:" label, icon + word, authority handed
  back to the human. It NEVER emits or pre-selects a disposition (Approved / Needs
  Correction / Rejected) and never inherits a disposition's color/wording. No
  `verdict → disposition` mapping anywhere in `review_view.py`.
- **Read boundary (AR-13).** The new `ChecklistItem` read model validates at the read
  boundary like the existing `Submission` / `LabelImage` models; raw SQL stays in
  `app/db/repositories.py`.

### AR-5 — the 5-second read contract

`GET /review/{id}` is a **pure pre-computed DB read**: it reads the already-computed
`submissions` row + `checklist_items` rows and renders. It performs **no** OCR,
inference, model import, `run_checks`, or pipeline-run call, and **no** status write
(the `READY_FOR_REVIEW → IN_REVIEW` + `OPENED` audit write already happened in
`POST /next`, Story 4.1 — the GET must be idempotent and side-effect-free). Mirror
Story 4.1's read-path source guard so a regression that imports a heavy module into
the review path fails a test.

### Banner / chevron / alert specifics (from DESIGN.md + EXPERIENCE.md)

- **Banner accents (DESIGN.md).** `spirits #7A4D00` white text (~7.3:1), `wine
  #6B1F3A` white text (~11.2:1), `beer #B8860B` **dark ink** `#1B1B1B` (~5.3:1; white
  on gold FAILS at 3.25:1 — beer MUST stay dark ink). The `--bev-*` tokens already
  exist in `brand.css`. The type **word is always present**; the color reinforces, it
  never substitutes (colorblind + the Dave persona).
- **Chevron (EXPERIENCE.md).** Progress **map**, not a wizard (U4); single page;
  clicking a step **scrolls** (same-page anchor) to that field group. The Conditional
  step ④ appears only when conditional checks are present; when absent the steps
  **renumber cleanly** so anchors never go off-by-one. The current marker is a literal
  "step N of M" / `aria-current` — **text, not contrast alone**.
- **Suggested-verdict alert (EXPERIENCE.md).** USWDS Alert in the verdict tint,
  "Suggested:" label, roll-up copy ("4 of 6 passed automatically; 2 need your
  review"), severity precedence via `rollup` (any FAIL⇒FAIL; else any REVIEW⇒REVIEW;
  else PASS; empty⇒REVIEW). Advisory register only; announced on load via
  `role="status"`.

### Project rules

- snake_case across DB ↔ Python ↔ JSON; UI labels map to enums in the presenter, never
  by mutating stored values.
- Self-hosted only — every asset under `/static`, no CDN, no inline `<style>`. Spine
  (DESIGN.md tokens) wins over any mockup hex on conflict.
- Don't edit `auto-run/`. Validate on the **host venv**, not the Docker container.

### Project Structure Notes

- New: `app/web/review_view.py` (presenter), `app/web/routes_review.py` (route),
  `templates/review.html`, `tests/test_review_view.py`, `tests/test_review.py`.
- Edited: `app/db/repositories.py` (+`ChecklistItem` + `list_checklist_items`),
  `app/main.py` (+`include_router(review_router)`), `static/css/brand.css`
  (+Review-shell block), `tests/test_repositories.py` (+checklist read tests).
- Reuses: `app/verdict.py:rollup` (the roll-up), the token-gate middleware, the
  `Jinja2Templates` env on `app.state.templates`, `base.html` shell + header.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.3]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/EXPERIENCE.md
  (Chevron / Step Indicator; Beverage-type banner; Suggested-verdict Alert; announce-on-load)]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/DESIGN.md
  (beverage accents; verdict palette; contrast table; beer dark-ink rule)]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/review-workspace.html]
- [Source: app/verdict.py (centralized rollup — contract #3)]
- [Source: app/db/repositories.py (read models + queue read helpers)]
- [Source: app/web/routes_queue.py (token-gated read route pattern, AR-5 guard)]
- [Source: _bmad-output/project-context.md (four contracts; AR-5; verdict-vs-disposition; rules-as-data)]

## Dev Agent Record

### Context Reference

- Story created and implemented in a single dev session (create-story + dev-story).

### Agent Model Used

- Amelia (DEV agent persona) on Claude Opus 4.

### Debug Log References

- Targeted suites: `test_repositories.py`, `test_review_view.py`, `test_review.py`;
  full gate `bash scripts/ci.sh` once at the end.

### Completion Notes List

- Dev-story shipped the shell test-first (banner / chevron / suggested-verdict alert);
  full gate green at 477 passed / 1 skip.
- Code review (2026-06-14) found ONE material defect and applied a single patch:
  `review_view._is_conditional` had been simplified to a pure
  `check_key not in CHECK_KEY_STEP` membership test, dropping the spec-mandated
  `check_type == "MANUAL"` discriminator (Task 2). Against the SHIPPED wine/malt
  rulesets that made the Conditional step ④ appear UNCONDITIONALLY for those
  beverage types — their always-present FIELD_MATCH identity rows (`grape_varietal`,
  `fanciful_name`) are not in `CHECK_KEY_STEP` — violating AC3's "appears ONLY when
  triggered" and mis-anchoring identity fields under `group-conditional` for later
  Stories 4.4–4.6. The spirits-only test fixtures masked it.
- Fix: completed `CHECK_KEY_STEP` with the two Identity-class FIELD_MATCH keys
  (rules-as-data) AND restored the `MANUAL` gate in `_is_conditional`
  (`not in CHECK_KEY_STEP and check_type == "MANUAL"`) as a drift guard, so a future
  unmapped non-MANUAL key can never silently inflate Conditional. Added 4 regression
  tests (wine-identity / malt-fanciful_name no-trigger; genuine MANUAL §4 disclosure
  triggers; unmapped non-MANUAL no-trigger).
- 8 Blind-Hunter findings dismissed, each disproven against the real source by the
  Edge Case Hunter (KeyError unreachable — `verdict.rollup` is total over
  `{PASS,REVIEW,FAIL}`; all 5 chevron anchor targets render symmetrically; all-NA
  summary/verdict consistent; `is_current` step-1 pin spec-authorized; pydantic
  `extra=ignore` + NOT-NULL columns make `SELECT *` safe; the `pyproject.toml` mypy
  `exclude=^auto-run/` is justified CI-hygiene per CLAUDE.md).
- Post-patch full gate green: format → lint → mypy (85 source files) → **481 passed /
  1 skip**.

### File List

- New: `app/web/review_view.py`, `app/web/routes_review.py`, `templates/review.html`,
  `tests/test_review_view.py`, `tests/test_review.py`.
- Edited: `app/db/repositories.py` (+`ChecklistItem` + `list_checklist_items`),
  `app/main.py` (+`include_router(review_router)`), `static/css/brand.css`
  (+Review-shell block), `tests/test_repositories.py` (+checklist read tests),
  `pyproject.toml` (+mypy `exclude=^auto-run/`, CI-hygiene).
- Code-review patch: `app/web/review_view.py` (`CHECK_KEY_STEP` + `_is_conditional`),
  `tests/test_review_view.py` (+4 regression tests).
