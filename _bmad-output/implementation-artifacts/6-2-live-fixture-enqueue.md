---
baseline_commit: 789f441
context:
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/project-context.md
  - docs/database-schema.md
  - _bmad-output/implementation-artifacts/6-1-demo-data-reset.md
---

# Story 6.2: Live fixture enqueue

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an evaluator,
I want to trigger a fresh fixture Submission and watch it process,
so that I can see the Pre-compute Pipeline work end to end — `submitted → processing → ready`,
then serve it via Next Submission with full Engine Verdicts.

## Acceptance Criteria

**AC-1 — `POST /enqueue` inserts ONE fresh fixture as a `RECEIVED` row only**
**Given** the operator route `POST /enqueue`
**When** it runs
**Then** it inserts exactly ONE new `submissions` row at `status='RECEIVED'` (plus that
row's `label_images` from a fixture image manifest and one `SEEDED` `audit_events` row),
in a single `BEGIN…COMMIT` transaction — and writes NOTHING else (it does NOT wipe or
re-seed the existing corpus; the prior submissions are untouched and the row count grows
by exactly one)
**And** the inserted row carries a **freshly-minted unique `ttb_id`** (and `serial_number`)
so it never collides with an already-seeded fixture under the `ttb_id NOT NULL UNIQUE`
constraint — repeated `POST /enqueue` calls each add a distinct new pending submission
**And** the row's `label_images` reference real baked-in fixture image files (under the
read-only `fixtures/images/` tree) so the background pipeline can OCR them and produce full
Engine Verdicts
**And** the web layer **never runs the pipeline synchronously** — it inserts the `RECEIVED`
row only; the existing APScheduler sweep (Story 2.2) is the sole writer that carries it
forward (AR-5 / pipeline-is-the-only-writer). *(FR-28, AR-12)*

**AC-2 — The enqueued Submission transitions through the canonical lifecycle**
**Given** the freshly-enqueued `RECEIVED` row
**When** the background sweep picks it up
**Then** it is observable transitioning through the lifecycle the UI narrates as
*submitted → processing → ready* — whose **canonical stored enum values are the
architecture's** `RECEIVED → PROCESSING → READY_FOR_REVIEW` (AR-10); the lowercase words
are user-facing copy, NOT the persisted values
**And** the enqueued row is the precondition the sweep consumes (`list_received_ids`
includes it) — this story asserts the `RECEIVED` precondition + the post-sweep
`READY_FOR_REVIEW` outcome; it does NOT re-implement or synchronously invoke the sweep.

**AC-3 — Once ready, servable via Next Submission with full Engine Verdicts**
**Given** the enqueued Submission carried forward to `READY_FOR_REVIEW` by the sweep
**When** the evaluator clicks Next Submission
**Then** it is servable through the existing queue/next path with full Engine Verdicts —
it joins the pending queue exactly like a seeded fixture (no special-casing in the read
path; the enqueued row is an ordinary `READY_FOR_REVIEW` submission). *(FR-28)*

**AC-4 — Honest redirect + token gate + no leakage**
**Given** an evaluator triggering `POST /enqueue`
**When** it completes
**Then** the route redirects back to the Queue (`303 → /queue`) — consistent with the
existing POST-action redirect pattern (`POST /next`, `POST /reset`, the disposition POST) —
so the evaluator lands on the queue and watches the new item appear
**And** the route is an operator route behind the Story 1.5 token gate (no exemption in
`main.py`): an unauthenticated `POST /enqueue` is bounced to `/access` and inserts nothing
**And** no submission rows, image bytes, or benchmark figures leak in the response (a bare
`303 → /queue`, empty body).

*(Source: epics.md Story 6.2; FR-28; AR-12; AR-10 (status lifecycle); architecture.md §Demo
Operations; project-context.md §Architectural Invariants (Pipeline-is-the-only-writer; status
lifecycle; route table `POST /enqueue`), §Firewall; docs/database-schema.md (submissions
`ttb_id` UNIQUE, status CHECK; label_images; audit_events SEEDED).)*

> **Dependency note (read first — reuse the seed insert path, do NOT rebuild it).**
> - `app/db/seed.py` already holds the single-row insert primitives this story reuses:
>   `_SUBMISSION_COLUMNS`, `_insert_submission(conn, row)` (inserts APPLICATION columns at
>   `status='RECEIVED'`, returns the new id), `_insert_label_images(conn, sid, images)`, and
>   `_parse_image_manifest(raw, ttb_id)`. The `ground_truth.csv` reader pattern is there too.
>   Promote a small **public** `enqueue_fixture(db_path) -> int` (or read a template row +
>   reuse the private helpers from `app/web/ops.py`) — do NOT duplicate the INSERT SQL.
> - `app/db/connection.py` → `get_connection` sets `PRAGMA foreign_keys = ON`; open the
>   enqueue transaction through it (same as `seed()`), one `BEGIN…COMMIT`, rollback on error.
> - `app/config.py` → `Settings.database_path` is the only path the route needs.
> - `app/web/routes_ops.py` already hosts `POST /reset`; add `POST /enqueue` beside it.
> - `app/main.py` already `include_router(ops_router)` (Story 6.1) — NO new wiring needed;
>   the token gate already protects every ops route (verify, do not re-add).
> - `app/pipeline/scheduler.py` `sweep()` + `repositories.list_received_ids` already carry
>   `RECEIVED` rows forward — the enqueued row rides the existing sweep with zero new code.

> **Scope note (binding).** This story adds the `POST /enqueue` operator endpoint + the
> single-fixture enqueue helper **only**. It does NOT add docs (Story 6.3), does NOT alter
> the schema, the seed corpus CSV, the scheduler, or any read screen, and does NOT add a
> confirmation UI (the route is the deliverable; a future story may add a button). It does
> NOT synchronously invoke the pipeline (AR-5 / pipeline-is-the-only-writer hold) — it inserts
> a `RECEIVED` row and the existing sweep does the rest.

## Tasks / Subtasks

- [x] **Task 1 — Single-fixture enqueue helper (AC: 1)**
  - [x] Add `enqueue_fixture(db_path, fixtures_dir=FIXTURES_DIR) -> int` to `app/db/seed.py`
        (the home of the corpus insert primitives). It reads the `ground_truth.csv`, takes
        ONE template fixture row (the first row — deterministic), and in a single
        `BEGIN…COMMIT` transaction inserts: one `submissions` row at `RECEIVED` with a
        **freshly-minted unique `ttb_id`** + `serial_number`, that row's `label_images` (from
        the template's image manifest, so real baked-in files back it), and one `SEEDED`
        `audit_events` row. Returns the new submission id.
  - [x] Mint the fresh `ttb_id` so it cannot collide with a seeded row under the UNIQUE
        constraint even after repeated calls: derive from the template ttb_id + a uniqueness
        suffix that is re-tried/guaranteed-unique against the live table (e.g. a count- or
        time-based suffix checked against `get_submission_by_ttb_id`/an existence query inside
        the same transaction). Same for `serial_number`.
  - [x] Reuse `_insert_submission` / `_insert_label_images` / `_parse_image_manifest` — do
        NOT re-write the INSERT SQL. Open the connection via `get_connection` (FK cascade on),
        `BEGIN`, rollback on any error (atomic — a failed enqueue leaves the corpus intact).
- [x] **Task 2 — `POST /enqueue` route in `app/web/routes_ops.py` (AC: 1, 4)**
  - [x] `@router.post("/enqueue")` → calls `enqueue_fixture(request.app.state.settings.database_path)`,
        then `RedirectResponse("/queue", status_code=303)`.
  - [x] No request body / query params consumed; response carries only the redirect (no
        submission / image / benchmark data — no leakage, AC-4). Lowercase route, no trailing
        slash, matches the project-context route table (`POST /enqueue`).
- [x] **Task 3 — Verify ops-router wiring + token gate (AC: 1, 4)**
  - [x] Confirm `app/main.py` already `include_router(ops_router)` (Story 6.1) so `POST
        /enqueue` is reachable and behind the gate with NO new wiring. Do not re-add.
- [x] **Task 4 — Tests `tests/test_routes_enqueue.py` (AC: 1, 2, 3, 4)**
  - [x] AC-1: seed → `POST /enqueue` → row count grows by exactly one; the new row is
        `RECEIVED` with decision columns NULL; it has ≥1 `label_images` row + exactly one
        `SEEDED` audit row; the prior corpus is untouched (existing rows unchanged). Two
        consecutive `POST /enqueue` calls add two DISTINCT rows with distinct `ttb_id`s (no
        UNIQUE-constraint failure).
  - [x] AC-2: the enqueued id appears in `list_received_ids` (the sweep's claim set). Drive
        the row through the real `process_submission` (or assert the `RECEIVED` precondition +
        a `READY_FOR_REVIEW` post-state) to show the canonical `RECEIVED → … → READY_FOR_REVIEW`
        transition — the stored enums, not the lowercase UI copy.
  - [x] AC-3: after the sweep readies it, the enqueued submission is servable via the existing
        next/queue path (appears among `READY_FOR_REVIEW` rows the queue serves).
  - [x] AC-4: `POST /enqueue` → `303 → /queue`; empty/no-leak body (no ttb_id, "submission",
        or "benchmark" in the payload); with `ACCESS_TOKEN` set, an unauthenticated
        `POST /enqueue` → `303 → /access` and inserts nothing (row count unchanged).
  - [x] Unit-test `enqueue_fixture` directly (single-row insert + uniqueness on repeat),
        independent of the HTTP layer.

### Project Structure Notes

- **New:** `enqueue_fixture()` in `app/db/seed.py` (beside the corpus insert primitives it
  reuses), the `POST /enqueue` route in `app/web/routes_ops.py`, `tests/test_routes_enqueue.py`.
- **Update:** none required in `app/main.py` — the ops router is already wired (Story 6.1).
- **Reuse, do not recreate:** `app/db/seed.py` `_insert_submission` / `_insert_label_images`
  / `_parse_image_manifest` / `_SUBMISSION_COLUMNS`, `app/db/connection.py` `get_connection`,
  `app/config.py` `Settings.database_path`, the existing `scheduler.sweep` + `list_received_ids`.

## Dev Notes

### The insert IS a single-fixture seed (do not re-implement the INSERT SQL)
- `seed.py` already inserts APPLICATION columns at `RECEIVED` (`_insert_submission`), the
  `label_images` rows (`_insert_label_images`), and parses the image manifest
  (`_parse_image_manifest`). `enqueue_fixture` is "`seed()` for one row, with a fresh id" — it
  reuses those primitives in one transaction. Call them; never duplicate the column lists/SQL.
- `ttb_id` is `NOT NULL UNIQUE` (schema §submissions). A naive reuse of a fixture's ttb_id
  would `UNIQUE`-fail against the already-seeded copy. Mint a fresh id (template ttb_id + a
  uniqueness suffix verified unique inside the transaction) so the insert is collision-free and
  repeatable. The label_images filenames REUSE the template's (real baked-in files) so the
  pipeline has images to OCR — only the parent identity is fresh.

### Status lifecycle & the sweep (AR-5 / pipeline-is-the-only-writer)
- Enqueue inserts at `RECEIVED`. The **existing** APScheduler sweep (Story 2.2) picks up
  `RECEIVED` rows and runs them `RECEIVED → PROCESSING → READY_FOR_REVIEW` — this story does
  NOT run the pipeline synchronously and writes NO pipeline-owned column
  (`ocr_results`/`llm_results`/`field_comparisons`/`checklist_items`/`engine_verdict`). The
  web layer only inserts the APPLICATION row + SEEDED audit row (the seed's sanctioned write
  surface) — a cheap, explicit POST action; the 5-second read contract is untouched (no
  OCR/inference on any request path).
- AC-2/AC-3 are realized cooperatively: enqueue produces a `RECEIVED` row; the sweep produces
  `READY_FOR_REVIEW`; the existing queue/next path serves it. The "full Engine Verdicts" come
  from the pipeline+engine the sweep runs — not from this story's code.

### Firewall / offline posture (NFR-2)
- Enqueue is 100% local: one DB transaction reading the baked-in `ground_truth.csv` + writing
  the local SQLite file. Zero egress — `docker run --network none` serves `POST /enqueue` and
  the insert completes with no network. No assets, no model layer, no OCR touched by the route.

### Security / no-leakage (AC-4)
- The enqueue response is a bare `303 → /queue`: no submission rows, image bytes, or benchmark
  numbers in the payload. Operator route behind the token gate (no exemption in `main.py`) — an
  unauthenticated `POST /enqueue` is bounced to `/access` like every other gated route and
  inserts nothing (verify the row count is unchanged on the gated path).

### Architecture compliance
- **snake_case** everywhere; type hints required; ruff line length 100.
- **Route conventions:** lowercase, no trailing slash, `POST /enqueue` exactly (project-context
  route table).
- **Verdict-vs-disposition separation** untouched (enqueue writes neither — it inserts an
  APPLICATION row at `RECEIVED`, decision columns NULL by the cross-column CHECK).
- **Pipeline-is-the-only-writer** untouched: enqueue writes only the seed's sanctioned surface
  (APPLICATION columns + a SEEDED audit row); it never writes a pipeline-owned column.

### Previous story intelligence (Story 6.1)
- Run targeted tests: `.venv/Scripts/python.exe -m pytest tests/test_routes_enqueue.py -q`.
  Full gate once at the end: `bash scripts/ci.sh`.
- `app/main.py` is an app factory (`create_app()`); `app.state.settings` holds the resolved
  `Settings`; the ops router is already wired (6.1). The token gate is app-wide middleware —
  no exemption for ops routes, so `/enqueue` is gated like `/reset`.
- Existing POST-action routes redirect with `303` (`POST /next`, `POST /reset` → `/queue`).
  Match that idiom: `POST /enqueue` → `303 → /queue`.
- Test fixtures: set `SCHEDULER_ENABLED=false` + isolated `DATABASE_PATH` under `tmp_path` so
  the test owns the row states (mirror `tests/test_routes_ops.py` `_client`).

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.2: Live fixture enqueue] (FR-28,
  AR-12; insert a fresh fixture as RECEIVED only, scheduler picks it up, observable
  RECEIVED→PROCESSING→READY_FOR_REVIEW, servable via Next Submission with full Engine Verdicts)
- [Source: _bmad-output/planning-artifacts/architecture.md#Demo Operations] (AR-12 enqueue =
  insert a RECEIVED row; the scheduler picks it up)
- [Source: _bmad-output/project-context.md] (route table `POST /enqueue`; status lifecycle
  AR-10; pipeline-is-the-only-writer; firewall)
- [Source: docs/database-schema.md] (submissions `ttb_id NOT NULL UNIQUE`, status CHECK,
  cross-column decision CHECK; label_images; audit_events SEEDED)
- [Source: app/db/seed.py] (`_insert_submission` / `_insert_label_images` /
  `_parse_image_manifest` / `_SUBMISSION_COLUMNS` — the reused insert primitives)
- [Source: app/web/routes_ops.py] (the existing `POST /reset` — `POST /enqueue` sits beside it)
- [Source: app/pipeline/scheduler.py + app/db/repositories.py:581] (`sweep` + `list_received_ids`
  carry the enqueued RECEIVED row forward — reused, not rebuilt)
- FR-28 / AR-12 / AR-10 [Source: epics.md]

### Review Findings

_Code review 2026-06-14 (CR) — three-layer adversarial review (Blind Hunter diff-only ·
Edge Case Hunter · Acceptance Auditor). 1 patch applied, 2 deferred, 6 dismissed. All four
ACs satisfied; no project invariant regressed. Post-review host CI green._

- [x] [Review][Patch] AC-2 lifecycle test was tautological (wrote `READY_FOR_REVIEW`, then
      asserted the value it just wrote) — strengthened to prove the *transition relationship*
      via the REAL repo functions: enqueued row is in `list_received_ids` and NOT servable
      while `RECEIVED`; after the canonical `RECEIVED → PROCESSING → READY_FOR_REVIEW` forward
      walk it LEAVES the claim set and becomes servable (`get_oldest_ready_submission_id`).
      Each forward UPDATE must satisfy the status CHECK (non-canonical enum would raise).
      [tests/test_routes_enqueue.py:178 test_enqueued_row_reaches_ready_for_review_canonical_enum]
- [x] [Review][Defer] Enqueued row inherits the corpus's coarse `submitted_at`, so it sorts
      into the OLDEST queue bucket — NOT surfaced as the "next" served item. AC-3 binds enqueue
      to "servable like a seeded fixture, no special-casing" (satisfied); whether to stamp a
      fresh `submitted_at` so the new item surfaces first is a demo-UX/product call for Diane.
      [app/db/seed.py:enqueue_fixture / app/db/repositories.py:list_received_ids] — deferred
- [x] [Review][Defer] `audit_events.actor='system:enqueue'` is a new value outside the
      schema-doc's documented actor vocabulary (constraint-legal: actor is free-text TEXT, no
      CHECK; SEEDED event_type IS in the fixed vocabulary). Same class as the deferred
      pipeline `actor="pipeline"` nit; align when the audit-actor vocabulary is formalized.
      [app/db/seed.py:enqueue_fixture] — deferred, provenance-consistency nit

_Dismissed (6): (1) Blind Hunter HIGH "`serial_number` un-probed UNIQUE collision" — FALSE
POSITIVE: `serial_number TEXT` has NO UNIQUE constraint (schema.sql:17); only `ttb_id` is
`NOT NULL UNIQUE` (:16), so the `ENQ-{n}` serial cannot collide. (2) Non-`ttb_id` template
columns copied verbatim — BY DESIGN per spec ("only the parent identity is fresh"); no UNIQUE
column besides `ttb_id`. (3) `POST /enqueue` lacks try/except → 500 — INTENTIONAL: enqueue is
an atomic DB transaction whose failure SHOULD surface (corpus intact); a swallow would be a
silent no-op, worse for a demo (unlike `/reset`'s best-effort FS purge). (4) `ENQ<n>` vs
`ENQ-<n>` format mismatch — cosmetic, two unrelated columns, no cross-ref requirement.
(5) `fixtures_dir` param unused at the call site — intentional testability seam (unit tests
inject a temp dir). (6) `json` possibly-unused import — false positive; `_parse_image_manifest`
uses `json.loads` (seed.py:107); ruff/CI would catch a truly dead import._

## Dev Agent Record

### Agent Model Used

Amelia (BMad dev-story) — claude-opus-4-8

### Debug Log References

- Targeted: `.venv/Scripts/python.exe -m pytest tests/test_routes_enqueue.py -q` → 11 passed.
- Full gate: `bash scripts/ci.sh --fix` → format + lint + mypy (no issues, 100 files) + pytest
  785 passed / 1 skipped.

### Completion Notes List

- **Test-first (red → green).** Wrote `tests/test_routes_enqueue.py` (11 tests) first;
  confirmed red (`ImportError: enqueue_fixture`), then implemented to green.
- **`enqueue_fixture(db_path, fixtures_dir=FIXTURES_DIR) -> int`** added to `app/db/seed.py`
  beside the corpus-insert primitives it reuses (`_insert_submission` /
  `_insert_label_images` / `_parse_image_manifest` / `_SUBMISSION_COLUMNS`) — NO INSERT SQL
  duplicated. Takes the first `ground_truth.csv` row as the deterministic template, mints a
  fresh unique `ttb_id`/`serial_number` via `_mint_fresh_ttb_id` (probes `submissions` for an
  absent `…-ENQ<n>` candidate inside the open transaction), inserts one `RECEIVED` row + its
  `label_images` (template image manifest → real baked-in files) + one `SEEDED` audit row in a
  single `BEGIN…COMMIT` (rollback on error → corpus intact). Reuses `get_connection` (FK-on).
- **`ttb_id NOT NULL UNIQUE` was the load-bearing constraint** (schema §submissions): a naive
  reuse of the template id would UNIQUE-fail against the already-seeded copy. The mint loop
  makes repeated enqueues collision-free (verified: 3 consecutive enqueues → 3 distinct ids).
- **`POST /enqueue`** added to `app/web/routes_ops.py` beside `POST /reset`: calls
  `enqueue_fixture(request.app.state.settings.database_path)` then `303 → /queue`. No body /
  query params; bare empty-body redirect (no leakage, AC-4).
- **No `main.py` change needed** — the ops router was already wired by Story 6.1
  (`include_router(ops_router)`, line 146); the app-wide token gate already protects every ops
  route. Verified the gated path inserts nothing (`test_post_enqueue_is_token_gated`).
- **Pipeline not driven in tests by design:** `process_submission`'s OCR/preprocess stages need
  native deps absent on the host venv, so AC-2/AC-3 assert the `RECEIVED` precondition
  (`list_received_ids` includes the enqueued id) + simulate the sweep's `READY_FOR_REVIEW`
  outcome, then prove servability via the real `count_ready_for_review` /
  `get_oldest_ready_submission_id`. The sweep itself is Story 2.2's test (unchanged).
- **Invariants held:** AR-5 (no OCR/inference on the request path — the route does one bulk
  INSERT via the sanctioned seed surface), pipeline-is-the-only-writer (no pipeline-owned
  column written — only APPLICATION columns + a `SEEDED` audit row), verdict-vs-disposition
  separation (decision columns NULL at `RECEIVED` by the cross-column CHECK), NFR-2 (100%
  local: read baked-in CSV + write local SQLite; zero egress).
- ruff reformatted `app/db/seed.py` + `tests/test_routes_enqueue.py` (line-wrapping only,
  behavior unchanged). Full CI gate green.

### File List

- `app/db/seed.py` (`enqueue_fixture` + `_mint_fresh_ttb_id` helper — reuses the corpus-insert
  primitives; no INSERT SQL duplicated)
- `app/web/routes_ops.py` (`POST /enqueue` operator route beside `POST /reset`; module docstring
  updated)
- `tests/test_routes_enqueue.py` (AC-1..AC-4 + `enqueue_fixture` unit tests)

## Change Log

| Date | Change |
|------|--------|
| 2026-06-14 | Story 6.2 spec created (CS) — `POST /enqueue` operator route: insert ONE fresh fixture (fresh unique ttb_id) as a RECEIVED row + label_images + SEEDED audit row via a reused single-fixture seed helper, `303 → /queue`, behind the token gate; the existing sweep carries it forward. |
| 2026-06-14 | Story 6.2 implemented (DS), test-first. Added `enqueue_fixture` + `_mint_fresh_ttb_id` to `app/db/seed.py` (reuses corpus-insert primitives; fresh unique `ttb_id` defeats the UNIQUE constraint on repeats), `POST /enqueue` in `routes_ops.py` (`303 → /queue`, token-gated, no-leak). Ops router already wired (6.1) — no `main.py` change. `tests/test_routes_enqueue.py` 11 passed; full CI gate green (785 passed / 1 skip). Story → review. |
