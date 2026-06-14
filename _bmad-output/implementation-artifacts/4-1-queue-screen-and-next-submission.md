# Story 4.1: Queue screen & Next Submission

Status: done

## Story

As a Label Specialist,
I want one obvious **Next Submission** action that serves the next ready item instantly,
So that I start reviewing without hunting through a list.

## Acceptance Criteria

1. **(Given** `GET /queue` and `POST /next` doing pre-computed DB reads only — no
   OCR / inference / model-layer call at request time. **When** I click **Next
   Submission, Then)** the oldest `READY_FOR_REVIEW` Submission is served
   (deterministic oldest-first by `submitted_at`, then `id`), unready items
   (`RECEIVED` / `PROCESSING`) skipped silently, and the response redirects to that
   submission's review screen (`/review/{id}`). *(FR-1, AR-5, SM-1)*
2. **(And)** the Queue screen **matches `mockups/queue.html`** in both states —
   **State 1 (waiting):** one large auto-focused **Next Submission** button (Enter
   fires it via native `type="submit"`, never auto-opening), the optional
   beverage-type segmented filter (Any · Wine · Spirits · Beer, **Any** preselected),
   the civic-green read-only stats strip, and the dashed Phase-2 triage placeholder
   marked not-live (`aria-hidden`); **State 2 (empty):** the **Next Submission**
   button disabled (`disabled` + `aria-disabled="true"`) with the calm "No
   submissions waiting right now." copy — layout, USWDS/brand component structure,
   states, and copy. *(UX-DR-2)*
3. **(And)** tokens resolve to `DESIGN.md` (navy `#112E51`, civic green `#2E5B46`),
   mockup-only scaffolding (browser device frame, `state-label`, fabricated demo
   numbers) is **excluded**, and the stats strip shows only **honestly-computable**
   data (the live "N waiting" count of `READY_FOR_REVIEW`); the mockup's fabricated
   "reviewed by you today" / "avg load" figures are omitted (no per-user identity;
   `processing_ms` unpopulated pre-pipeline) rather than hard-coded. A side-by-side
   mockup check is in the DoD. *(UX-DR-2, AR-5, UI-fidelity standard)*
4. **(And)** the routes are token-gated like every other protected route (the
   `app/main.py` middleware already covers any non-exempt path; `/queue` and `/next`
   are **not** added to the exempt list), and `POST /next` performs the permitted
   cheap bookkeeping write on the explicit POST action — the `READY_FOR_REVIEW →
   IN_REVIEW` lifecycle transition plus an `OPENED` `audit_events` row (never folded
   into a `GET` render). *(AR-5 Addendum, FR-25)*

## Tasks / Subtasks

- [x] **Task 1 — Repository read/count helpers (test-first, AC1, AC3).**
  In `app/db/repositories.py`, add two pure-SQL helpers mirroring the existing
  `list_received_ids` style (oldest-first `ORDER BY submitted_at, id`, uses the
  `idx_submissions_queue` index):
  - `get_oldest_ready_submission_id(conn, *, beverage_type: str | None = None) ->
    int | None` — `SELECT id FROM submissions WHERE status = 'READY_FOR_REVIEW'`
    (`AND beverage_type = ?` when `beverage_type` is given) `ORDER BY submitted_at,
    id LIMIT 1`; returns the id or `None`. (The `beverage_type` arg is wired but
    Story 4.2 owns exposing it through the route — 4.1 calls it with the default
    `None`.)
  - `count_ready_for_review(conn, *, beverage_type: str | None = None) -> int` —
    `SELECT COUNT(*) FROM submissions WHERE status = 'READY_FOR_REVIEW'`
    (`AND beverage_type = ?` when given). Returns the live waiting count for the
    stats strip.
  Both are parameterized (no string interpolation of `beverage_type`). No commit
  (reads). Tests in `tests/test_repositories.py` (or the new queue test file): seed
  rows across statuses + beverage types and assert oldest-first selection, the
  `READY_FOR_REVIEW`-only filter, the skip of `RECEIVED`/`PROCESSING`/`IN_REVIEW`/
  `DECIDED`, `None` on an empty ready set, and the count.

- [x] **Task 2 — `routes_queue.py` router: `GET /queue` + `POST /next` (test-first,
  AC1, AC4).** Create `app/web/routes_queue.py` with an `APIRouter` mirroring
  `routes_access.py` conventions (`request.app.state.templates` /
  `request.app.state.settings`, no module-level DB handle):
  - `GET /queue` → render `queue.html`. Open a `connect(settings.database_path)`
    read, compute `waiting = count_ready_for_review(conn)`, pass `waiting` to the
    template. Pure DB read — NO OCR/inference/model import (AR-5). `response_class =
    HTMLResponse`.
  - `POST /next` → open `connect(...)`, `sid = get_oldest_ready_submission_id(conn)`.
    - If `sid is None` (empty queue): re-render `queue.html` with `waiting = 0`
      (State 2 — calm, NOT an error; `status_code` stays 200). Do **not** redirect.
    - Else: perform the bookkeeping transition `status.advance(conn, sid,
      to_status="IN_REVIEW", event_type="OPENED", actor=...)` (the permitted cheap
      POST-action write; `advance` commits), then
      `RedirectResponse(f"/review/{sid}", status_code=303)`. *(The `/review/{id}`
      target is built in Story 4.3; 4.1 owns the serve + redirect contract, not the
      review render — the test asserts the redirect Location, not a 200 at the
      target.)*
  - `actor` for the `OPENED` event: a constant placeholder specialist identity
    (e.g. module-level `SPECIALIST_ACTOR = "Label Specialist"`, matching
    architecture.md §264 `actor` = `Label Specialist`) — there is no per-user
    identity in the POC.
  - Mount the router in `app/main.py` via `app.include_router(queue_router)`
    alongside `access_router`. Do NOT touch the exempt list (so `/queue` + `/next`
    are gated by default — AC4).

- [x] **Task 3 — `queue.html` template (test-first fidelity, AC2, AC3).** Create
  `templates/queue.html` extending `base.html` (inherits the app-header + USWDS/
  brand links; the `J. Park` agent name stays excluded per the 1.4 base decision).
  Reproduce the mockup's `<main class="queue">` body **minus** the device frame /
  `state-label` / fabricated numbers:
  - `queue__eyebrow` + `queue__title` (State 1: "Ready when you are." / "Pull the
    next label for review."; State 2: "All caught up." / "No submissions waiting
    right now."). Drive the two states off `waiting` (`{% if waiting > 0 %}`).
  - The **Next Submission** control is a real `<form method="post" action="/next">`
    with a `<button type="submit" class="btn-next" autofocus ...>` so Enter fires it
    natively (no JS). State 1: enabled, `autofocus`, the ▶ glyph + "Next Submission"
    + `aria-keyshortcuts="N"`. State 2: `disabled` + `aria-disabled="true"` + the
    `is-disabled` class, with the helper copy ("Nothing in the queue at the
    moment. New labels appear here as they finish processing — check back shortly.").
  - The beverage-type **segmented filter** (`role="group"`, Any/Wine/Spirits/Beer
    buttons; **Any** `aria-pressed="true"`). Rendered per mockup; the by-type serve
    is Story 4.2, so 4.1 ships the control visually (the buttons are inert
    placeholders this story — no `name`/submit wiring yet; do not fake a working
    filter).
  - The Phase-2 **deferred** dashed placeholder (`aria-hidden="true"`, the
    "Two-bucket triage — Phase 2" copy) — present, clearly not a live control.
  - The civic-green **stats strip**: render ONLY `<strong>{{ waiting }} waiting</strong>`
    (live count). OMIT the mockup's "reviewed by you today" and "avg … to load"
    (fabricated — no identity, `processing_ms` null pre-pipeline). AC3.
  - The empty-type variant copy ("The wine queue is empty…") is **Story 4.2** — do
    not render it here (4.1 has no working type filter).

- [x] **Task 4 — Brand CSS for the queue (AC2, AC3).** Add the queue component
  styles to `static/css/brand.css` (the same self-hosted brand layer the mockup's
  inline `<style>` carried): `.queue`, `.queue__eyebrow`, `.queue__title`,
  `.btn-next` (+ `:hover` / `:focus-visible` / `.is-disabled` / `:disabled`),
  `.filter` / `.filter__label`, `.segmented` / `.segmented__item`
  (`[aria-pressed="true"]`), `.deferred` (+ `__tag` / `__note`), `.stats`, `.helper`.
  Use the DESIGN.md tokens (navy `#112E51`, civic green `#2E5B46`) — NOT a CDN, NOT
  inline `<style>` (no-CDN/self-hosted invariant). Accessibility floor: button
  `min-height: 72px` (≥48px), body ≥16px, visible focus ring, color never the sole
  signal (icon + word present).

- [x] **Task 5 — Tests (test-first, all ACs).** Create `tests/test_queue.py`
  mirroring `tests/test_token_gate.py`'s `_client(monkeypatch, token)` +
  `TestClient(create_app())` pattern. Seed a DB via the same helper the repo tests
  use; flip some rows to `READY_FOR_REVIEW` (and vary `submitted_at` + beverage
  type) to exercise selection. Cover:
  - **AC1 serve:** with ≥1 ready row, `POST /next` (follow_redirects=False) returns
    303 with `Location == /review/{oldest_ready_id}`; the chosen id is the oldest
    `submitted_at` (tie-break `id`); `RECEIVED`/`PROCESSING` rows are never served.
  - **AC4 transition:** after `POST /next`, the served submission's status is
    `IN_REVIEW` and an `OPENED` `audit_events` row exists for it (read back via repo
    / SQL).
  - **AC1 empty:** with zero ready rows, `POST /next` returns **200** rendering the
    State-2 empty queue (NOT a redirect, NOT an error/4xx); body carries "No
    submissions waiting right now." and the disabled button (`aria-disabled="true"`).
  - **AC2 State 1 fidelity:** `GET /queue` with ready rows → 200, body has
    `class="btn-next"`, `autofocus`, `<form` `action="/next"` `method="post"`, the
    segmented filter (`Any`/`Wine`/`Spirits`/`Beer`, `aria-pressed="true"` on Any),
    the `deferred` placeholder with `aria-hidden`, and the app-header
    (`class="app-header"`).
  - **AC2 State 2 fidelity:** `GET /queue` with zero ready rows → the disabled
    button + calm copy; **no** redirect.
  - **AC3 honesty / no scaffolding:** the rendered queue body does NOT contain the
    mockup scaffolding (`device__chrome`, `state-label`) and does NOT contain the
    fabricated stats ("reviewed by you today", "avg", "4.6s", the literal "38
    waiting"); it DOES contain the live "<n> waiting" derived from the seeded ready
    count. Assert tokens are NOT inlined (no `<style>` block in the body; brand.css
    is linked from base).
  - **AC4 gating:** with `ACCESS_TOKEN` set and no cookie, `GET /queue` and
    `POST /next` both redirect (303) to `/access` (reuse the token-gate assertions);
    with the valid cookie they reach the route.
  - **AR-5 read-path purity:** assert (by import/AST guard or by behavior) that the
    queue route module imports no OCR/LLM/pipeline-run symbol — a structural guard
    that `GET /queue` / `POST /next` do only DB reads + the one bookkeeping write.

- [x] **Task 6 — Validate.** Run the targeted files green first
  (`.venv/Scripts/python.exe -m pytest tests/test_queue.py tests/test_repositories.py
  -q`), then `bash scripts/ci.sh` ONCE at the very end (format → lint → typecheck →
  tests). Update
  `_bmad-output/implementation-artifacts/sprint-status.yaml`:
  `4-1-queue-screen-and-next-submission: review`.

## Dev Notes

### Scope boundary with Stories 4.2 and 4.3 (read carefully)

This is the FIRST UI/route story of Epic 4. Three deliberate scope cuts keep it
honest and non-overlapping:

1. **By-type filtering is Story 4.2.** 4.1 renders the segmented filter control
   (mockup fidelity) but the buttons are **inert placeholders** — no working
   `?type=` serve, no empty-type copy ("The wine queue is empty…"). The repository
   helpers take a `beverage_type` arg (wired, defaulted `None`) so 4.2 only adds the
   route plumbing, not new SQL. Do NOT fake a working filter in 4.1.
2. **The review screen is Story 4.3.** No `GET /review/{id}` route exists yet
   (confirmed: `app/main.py` mounts only `access_router`; `app/web/` has only
   `routes_access.py`). 4.1 owns the **serve + redirect contract** — `POST /next`
   selects the oldest ready item, does the bookkeeping transition, and redirects to
   `/review/{id}`. The redirect **target** 404s until 4.3 lands; that is expected and
   correct — the test asserts the 303 `Location`, never a 200 at `/review/{id}`. Do
   NOT build the review render here.
3. **Honest stats, not the mockup's demo numbers.** The mockup's stats strip shows
   "38 waiting · 12 reviewed by you today · avg 4.6s to load". Only **N waiting**
   (`COUNT(*) WHERE status='READY_FOR_REVIEW'`) is truthfully computable today:
   there is no per-user identity (`specialist_id` is NULL on every seeded row — no
   accounts in the POC), and `processing_ms` is NULL until a submission finishes the
   pipeline. Per the UI-fidelity standard ("placeholder data is illustrative — do
   not reproduce it"), render the live count and OMIT the fabricated figures. Do NOT
   hard-code "12 reviewed" / "4.6s".

### The 5-second read contract & the permitted POST write (AR-5)

- `GET /queue` and the `/review/{id}` render path are **DB-read-only** — never OCR,
  image processing, inference, or a model-layer call at request time (project-context
  Architectural Invariants; architecture.md §269).
- `POST /next` IS allowed the one cheap bookkeeping write: the `READY_FOR_REVIEW →
  IN_REVIEW` status lifecycle transition + the `OPENED` audit row, because it is an
  **explicit POST action**, never folded into a `GET` render (project-context
  Addendum A; architecture.md §265, §269). Use the existing
  `app.pipeline.status.advance(conn, sid, to_status="IN_REVIEW",
  event_type="OPENED", actor=SPECIALIST_ACTOR)` — it enforces forward-only order,
  vocabulary-checks the event, and commits its own transaction. Do NOT re-implement
  the transition or write SQL for it.

### Reuse — do not re-implement

- **Token gate:** the `app/main.py` `access_gate` middleware already protects every
  non-exempt path. Mounting `/queue` + `/next` WITHOUT adding them to
  `EXEMPT_PATHS`/`EXEMPT_PREFIXES` (`app/web/deps.py`) gates them automatically. No
  per-route dependency needed.
- **Router pattern:** mirror `app/web/routes_access.py` — `APIRouter()`,
  `request.app.state.templates`, `request.app.state.settings`,
  `templates.TemplateResponse(request, "queue.html", {...}, status_code=...)`.
- **DB access:** `with connect(settings.database_path) as conn:` (auto-commits on
  clean exit) from `app/db/connection.py`. Read helpers live in
  `app/db/repositories.py` — add the two new ones there (the SQL boundary), call
  them from the route. The new helpers follow the `list_received_ids` template
  (oldest-first `ORDER BY submitted_at, id`, the `idx_submissions_queue` index).
- **Status / audit:** `app/pipeline/status.advance` (above). `Status` literal =
  `RECEIVED|PROCESSING|READY_FOR_REVIEW|IN_REVIEW|DECIDED`; `OPENED` is in the locked
  `AUDIT_EVENT_TYPES`.

### UI fidelity (hard requirement)

- The screen must reproduce `mockups/queue.html`'s `<main class="queue">` — layout,
  USWDS/brand structure, all states, exact copy — EXCLUDING the illustrative
  scaffolding (the `.device`/`device__chrome` browser frame, the `.state-label`
  headers, the placeholder `J. Park`, the fabricated stat numbers). Spine wins on
  token conflict (DESIGN.md). The mockup's styling is INLINE `<style>`; we move it to
  the self-hosted `static/css/brand.css` (no-CDN / same-origin invariant) and link it
  via `base.html` — no inline `<style>` block in the served page.
- Accessibility floor: Next Submission ≥48px (mockup uses 72px), body ≥16px, visible
  focus ring, color never alone (the ▶ glyph + the word "Next Submission" carry it),
  the disabled empty-state button carries `aria-disabled="true"`. Auto-focus the
  button but it **never auto-acts** (one deliberate click / Enter — U1).
- A documented side-by-side comparison against `mockups/queue.html` (both states) is
  in this story's Definition of Done.

### Naming & conventions

- snake_case everywhere (Python, DB, JSON). Routes lowercase, no trailing slash,
  `{id}` path params. New repo helpers snake_case. No camelCase.
- No new DB columns / tables (the schema already carries `submissions.status`,
  `submitted_at`, `beverage_type`, `audit_events`). Create-tables-only-when-needed
  does not apply — nothing new is needed.

### Files

- EDIT `app/db/repositories.py` — add `get_oldest_ready_submission_id` +
  `count_ready_for_review`.
- CREATE `app/web/routes_queue.py` — `GET /queue`, `POST /next`.
- EDIT `app/main.py` — `app.include_router(queue_router)`.
- CREATE `templates/queue.html` — extends `base.html`, both states.
- EDIT `static/css/brand.css` — queue component styles (tokens per DESIGN.md).
- CREATE `tests/test_queue.py` — route + fidelity + gating + read-path-purity tests.
- EDIT `tests/test_repositories.py` (or cover the new helpers in `test_queue.py`).
- EDIT `_bmad-output/implementation-artifacts/sprint-status.yaml` — 4-1 → `review`.

### Out of scope

- No `GET /review/{id}` render (Story 4.3). No working beverage-type filter / by-type
  serve / empty-type copy (Story 4.2). No keyboard shortcut JS for `N` beyond the
  native auto-focus + Enter-submits-the-form (the `N` global shortcut is Story 4.10;
  4.1 only sets `aria-keyshortcuts="N"` as the mockup does). No fabricated stats. No
  schema changes. Do NOT edit `auto-run/`.

### Review Findings

Code review 2026-06-14 (Blind Hunter + Edge Case Hunter + Acceptance Auditor). 2
patches applied, 0 deferred, 5 dismissed as by-design/false-positive.

- [x] [Review][Patch] `POST /next` concurrency TOCTOU → uncaught `ValueError` →
  HTTP 500 [app/web/routes_queue.py:50] — **HIGH** (Blind + Edge converged). The
  select-then-advance is a check-then-act with no atomic claim: two specialists
  clicking Next at the same instant both read the same oldest `READY_FOR_REVIEW`
  id; the winner advances it to `IN_REVIEW`, the loser's `status.advance` then
  rejects the non-forward `IN_REVIEW → IN_REVIEW` with `ValueError`, which escaped
  uncaught (no exception handler) → raw 500, breaking the route's calm contract.
  Confirmed empirically with a probe (`'IN_REVIEW' → 'IN_REVIEW' rejected`). FIX:
  `status.advance` IS the claim — wrapped it in a bounded re-select loop that
  catches the lost-race `ValueError` and serves the NEXT oldest ready row, draining
  to the calm State-2 empty render if all rows were raced away. Never a 500. +2
  regression tests (`test_next_lost_race_serves_next_not_500`,
  `test_next_all_rows_raced_away_renders_empty_state2`).
- [x] [Review][Patch] `is-focused` mockup-scaffolding class on the live Next
  Submission button [templates/queue.html:27, static/css/brand.css:314] — LOW
  (Acceptance Auditor). The mockup's static `is-focused` illustration class was
  carried into the live template, painting the focus ring unconditionally (even
  after focus leaves the button). The genuine `autofocus` + `:focus-visible` rule
  already satisfy the visible-focus floor. FIX: dropped `is-focused` from the
  rendered button and removed the now-orphaned `.btn-next.is-focused` selector,
  keeping `:focus-visible`. AC2 scaffolding-exclusion tightened.
- [x] [Review][Dismiss] `/review/{id}` redirect 404s / row "stranded" in IN_REVIEW
  — by-design per Dev Notes scope cut #2 (4.3 builds the review render; the 303
  Location is the asserted contract, not a 200 at target).
- [x] [Review][Dismiss] empty `POST /next` returns 200 inline instead of a 303 —
  by-design per Task 2 ("re-render `queue.html` with `waiting = 0`, `status_code`
  stays 200. Do **not** redirect").
- [x] [Review][Dismiss] hardcoded `waiting = 0` on the empty render is "stale" —
  spec-mandated literal (Task 2); cosmetic only.
- [x] [Review][Dismiss] `row["id"]`/`row["n"]` assume `sqlite3.Row` — false
  positive; `connection.get_connection` sets `conn.row_factory = sqlite3.Row`.
- [x] [Review][Dismiss] `advance` double-commits inside `connect()` — false
  positive; the context manager's second commit is a harmless no-op.

## Dev Agent Record

### Context Reference

- Epic: `_bmad-output/planning-artifacts/epics.md` — Story 4.1 (lines 539–551).
- UX: `mockups/queue.html`; `EXPERIENCE.md` (IA Queue/"Get Next", Component Patterns
  Next Submission button, State Patterns empty queue, lines 42/81/98/132);
  `DESIGN.md` (navy `#112E51`, civic green `#2E5B46`, button-primary ≥48px).
- Architecture: `architecture.md` §188/§241 (route list `GET /queue`, `POST /next`),
  §264–269 (audit vocab, status transitions, the 5s contract + permitted POST
  writes), §317 (`routes_queue.py`), §394 (`POST /next` → DB read → render).
- Reuse seam: `app/web/routes_access.py` (router pattern), `app/main.py`
  (middleware + include_router), `app/web/deps.py` (gate), `app/db/repositories.py`
  (`list_received_ids` template + add the two helpers), `app/pipeline/status.py`
  (`advance`/`OPENED`), `templates/base.html` (app shell), `tests/test_token_gate.py`
  (TestClient pattern).

### Completion Notes

- **TDD red→green.** Wrote `tests/test_queue.py` first (16 tests across the four ACs),
  then the two repo helpers, the router, the template, and the brand CSS until green.
- **AC1 (serve + oldest-first + skip-unready + empty-calm).** `get_oldest_ready_submission_id`
  / `count_ready_for_review` filter on `status='READY_FOR_REVIEW'` and order
  `submitted_at, id`; both parameterize the optional `beverage_type` (wired for 4.2,
  called with default `None` here). `POST /next` serves the oldest ready row and
  303-redirects to `/review/{id}`; on an empty ready set it re-renders State 2 at 200
  (never a redirect, never an error). Unready rows (`RECEIVED`/`PROCESSING`/`IN_REVIEW`/
  `DECIDED`) are never chosen.
- **AC4 (gating + the one permitted POST write).** The routes carry no exemption, so
  the existing `app/main.py` token-gate middleware protects `/queue` + `/next` (tested:
  303 → `/access` without the cookie, reachable with it). `POST /next` does the single
  cheap bookkeeping write via the existing `app.pipeline.status.advance` —
  `READY_FOR_REVIEW → IN_REVIEW` + an `OPENED` audit row — never re-implemented, never
  folded into a GET.
- **AC2/AC3 (fidelity + honesty).** `queue.html` extends `base.html` and reproduces
  both mockup states (auto-focused submitting Next Submission form / disabled empty-state
  button + calm copy, the inert Any/Wine/Spirits/Beer segmented filter with Any
  preselected for 4.2, the aria-hidden Phase-2 deferred placeholder). Only the live
  "N waiting" count renders; the mockup's fabricated "12 reviewed by you today" / "avg
  4.6s" / literal "38 waiting" and the `device__chrome`/`state-label` scaffolding are
  excluded. Tokens come from the linked self-hosted `static/css/brand.css` (no inline
  `<style>`).
- **AR-5 read-path purity** asserted by a source guard — `routes_queue.py` imports no
  `run_checks` / `adapters.ocr` / `adapters.llm` / `pipeline.run` / `pytesseract`.
- **Validation.** `tests/test_queue.py` green (16 passed). Full suite **430 passed /
  1 skipped**. `bash scripts/ci.sh` format + lint clean; story-scope mypy clean
  (`app/web/routes_queue.py`, `app/db/repositories.py`, `app/main.py`,
  `tests/test_queue.py`). The only gate error is the **pre-existing**
  `auto-run/orchestrate.py:562` mypy `[assignment]` — outside this story's scope, not
  in the diff, and walled off per CLAUDE.md.
- **Test-helper note.** `tests/test_queue.py::_client` calls `init_db(db_path)` before
  building the app because `TestClient(create_app())` used WITHOUT a `with` block does
  not fire the FastAPI lifespan (its startup `init_db`) until the first request — the
  helper tests `connect()` and seed rows before any request, so the schema must exist
  up-front. (A `DECIDED` seed row carries `disposition='APPROVED'` + `decided_at` to
  satisfy the schema's DECIDED cross-column CHECK.)

### File List

- CREATE `app/web/routes_queue.py` — `GET /queue`, `POST /next`.
- EDIT `app/main.py` — `app.include_router(queue_router)` (no exempt-list change).
- EDIT `app/db/repositories.py` — `get_oldest_ready_submission_id` +
  `count_ready_for_review`.
- CREATE `templates/queue.html` — extends `base.html`, both states.
- EDIT `static/css/brand.css` — queue component styles (DESIGN.md tokens).
- CREATE `tests/test_queue.py` — route + fidelity + gating + read-path-purity tests
  (16 tests, repo helpers covered here).
- EDIT `_bmad-output/implementation-artifacts/sprint-status.yaml` — epic-4 →
  in-progress, 4-1 → `review`.
