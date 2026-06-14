---
baseline_commit: fa66c9b
context:
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/project-context.md
  - docs/database-schema.md
  - _bmad-output/implementation-artifacts/deferred-work.md
---

# Story 6.1: Demo data reset

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an evaluator,
I want to reset the demo to its seeded state,
so that the demo is never permanently exhausted — I can re-run it indefinitely and verify every claim from the docs.

## Acceptance Criteria

**AC-1 — `POST /reset` transactionally re-seeds the corpus**
**Given** the operator route `POST /reset`
**When** it runs
**Then** it restores the full seeded corpus by invoking Story 1.3's transactional `seed(db_path)` — a single `BEGIN…COMMIT` that `DELETE`s all `submissions` (FK `ON DELETE CASCADE` clears `label_images`, `ocr_results`, `llm_results`, `field_comparisons`, `checklist_items`, `audit_events`, and `review_progress`) then reloads every fixture row + its `label_images` + one `SEEDED` `audit_events` row at `status='RECEIVED'`
**And** because every seeded row returns at `RECEIVED`, recorded `disposition`/`decided_at`/`decision_notes` (and `engine_verdict`, `correction_due_at`, `processing_ms`) are necessarily cleared and `status` is reset (the cross-column CHECK guarantees a non-`DECIDED` row carries NULL decision columns) — restoring the full pending queue
**And** all `review_progress` rows (the web-layer human ticks + draft Notes, AR-14) are purged by the same cascade
**And** the operation is atomic: any failure rolls back, leaving the prior corpus intact (no partial wipe).

**AC-2 — Generated/preprocessed images are purged**
**Given** the derived-images root (`settings.generated_images_dir`, default `data/generated`) holding the pipeline's OpenCV `__enhanced.png` / `__binarized.png` variants
**When** `POST /reset` runs
**Then** the generated-images root is purged of its contents (the directory itself is re-created empty, or left absent for the pipeline to re-create) — closing the `pipeline/preprocess.py` `TODO(epic-6-reset)` hook
**And** the read-only seeded fixture images under `fixtures/images/` are **never** touched (they are baked into the image; only derived variants are purgeable)
**And** a missing/empty generated-images root is a no-op, never an error (a fresh demo that has not preprocessed anything resets cleanly).

**AC-3 — Reset restores the queue after full exhaustion, without redeployment**
**Given** a demo where **all** seeded Submissions have received Dispositions (every row `DECIDED`, the pending queue empty)
**When** `POST /reset` runs and the background sweep subsequently processes the re-seeded `RECEIVED` rows
**Then** the full pending queue is restored — the same fixture corpus is servable again via Next Submission, with no redeploy and no process restart
**And** the route is reachable on the running deployment (an in-process endpoint, not a CLI/redeploy step). *(FR-27, AR-12)*

**AC-4 — Honest response + reset-while-open safety**
**Given** an evaluator (or a specialist mid-review) triggering `POST /reset`
**When** it completes
**Then** the route redirects back to the Queue (`303 → /queue`) so the evaluator lands on the restored, calm State-1/State-2 screen — consistent with the existing POST-action redirect pattern (`POST /next`, disposition)
**And** the already-shipped **demo-reset-while-open** handling (Story 4.11 AC4: `GET /review/{id}` and the disposition POST route back calmly to `/queue?gone=1` when their submission no longer exists) continues to hold — a reset fired while a review screen is open never crashes the open session
**And** no Submission rows, image bytes, or benchmark figures leak in the reset response (it carries only the redirect).

*(Source: epics.md Story 6.1; FR-27; AR-12; AR-14; architecture.md §Demo Operations / §Architectural Boundaries; project-context.md §Architectural Invariants (Pipeline-is-the-only-writer; status lifecycle), §Firewall; docs/database-schema.md (FK cascades, `review_progress` purge note); deferred-work.md.)*

> **Dependency note (read first — the seed is DONE and reset-ready).** The transactional re-seed already exists — reuse it, do not rebuild:
> - `app/db/seed.py` → **`seed(db_path) -> int`** is explicitly documented "the reset-friendly basis Epic 6's `POST /reset` calls": one `BEGIN`, `DELETE FROM submissions` (cascades to children), reload corpus, `COMMIT`, rollback-on-error. It is idempotent (covered by `tests/test_seed.py` AC-5). **Call it as-is** — do not duplicate its DELETE/reload logic in the route.
> - `app/db/connection.py` → `get_connection` sets `PRAGMA foreign_keys = ON` on every connection, so the cascade actually fires (it is OFF by default in SQLite). `seed()` opens its own connection via `get_connection`, so the cascade is guaranteed.
> - `app/config.py` → `Settings.generated_images_dir` (default `data/generated`, env `GENERATED_IMAGES_DIR`) is the single purgeable root. `app/pipeline/preprocess.py:397` carries the `TODO(epic-6-reset / AR-12 / FR-27)` hook this story closes.
> - `app/main.py` → routers are wired with `app.include_router(...)`; `app.state.settings` holds the resolved `Settings`. Add an ops router here exactly like the others; it carries **no exemption**, so the Story 1.5 token gate protects `/reset` like every screen (operator route = behind the gate).

> **Scope note (binding).** This story adds the `POST /reset` operator endpoint + the generated-images purge helper **only**. It does NOT add `POST /enqueue` (Story 6.2) or any docs (Story 6.3). It does NOT alter the schema, the seed corpus, the scheduler, or any read screen. The reset re-seeds rows to `RECEIVED`; the **existing** background sweep (Story 2.2) takes them forward to `READY_FOR_REVIEW` — this story does not re-implement or synchronously invoke the pipeline (AR-5 / pipeline-is-the-only-writer hold). No confirmation UI is in scope (the route is the deliverable; a future story may add a button).

## Tasks / Subtasks

- [x] **Task 1 — Generated-images purge helper (AC: 2)**
  - [x] Add a small, pure helper that purges the contents of `settings.generated_images_dir` (delete the directory tree, then re-create the empty root so the pipeline can write into it next sweep). Place it where the derived root is owned — `app/db/seed.py` already imports `pathlib`/`get_settings`, OR a focused `app/web/ops.py` orchestrator (prefer keeping the FS purge next to the reset orchestrator, not in `seed.py`, so `seed()` stays purely DB-scoped).
  - [x] Missing root ⇒ no-op (never raise). Only the **derived** root is touched; `fixtures/images/` is never referenced.
  - [x] Use `shutil.rmtree(..., ignore_errors=False)` guarded by an existence check, then `mkdir(parents=True, exist_ok=True)`.
- [x] **Task 2 — Reset orchestrator (AC: 1, 2)**
  - [x] A `reset(settings)` orchestrator that calls `seed(settings.database_path)` (transactional re-seed) **then** purges the generated-images root. Order: DB re-seed first (the authoritative state), then FS purge (best-effort cleanup of now-orphaned variants).
  - [x] The DB re-seed is the atomic unit (AC-1); the FS purge is a follow-on. A purge failure must not corrupt the (already-committed) re-seed — log and continue, or surface as a 500 only after the DB is consistent. (Prefer: DB commit is the success boundary; FS purge errors are swallowed+logged, matching the `_seed_if_empty` boot-degraded posture.)
- [x] **Task 3 — `POST /reset` route in `app/web/routes_ops.py` (AC: 1, 3, 4)**
  - [x] New `routes_ops.py` with `router = APIRouter()` and `@router.post("/reset")` → calls the reset orchestrator with `request.app.state.settings`, then `RedirectResponse("/queue", status_code=303)`.
  - [x] No request body, no query params consumed; response carries only the redirect (no submission/image/benchmark data — no leakage, AC-4).
  - [x] Lowercase route, no trailing slash, matches the project-context route table (`POST /reset`).
- [x] **Task 4 — Wire the ops router into `app/main.py` (AC: 3, 4)**
  - [x] `from app.web.routes_ops import router as ops_router` + `app.include_router(ops_router)`. No exemption added → the token gate protects `/reset` (operator route behind the gate). Startup stays network-free.
- [x] **Task 5 — Tests `tests/test_routes_ops.py` (AC: 1, 2, 3, 4)**
  - [x] AC-1: seed → decide some rows / mutate `review_progress` → `POST /reset` → assert corpus row-count restored, all `disposition`/`decided_at`/`decision_notes` NULL, all `status='RECEIVED'`, zero `review_progress` rows, children re-populated (label_images present, one SEEDED audit row per submission).
  - [x] AC-2: write a sentinel file into `generated_images_dir` → `POST /reset` → assert the root is emptied and the sentinel gone; `fixtures/images/` untouched. Missing-root reset is a no-op (no raise).
  - [x] AC-3: drive every row to `DECIDED` (empty pending queue) → `POST /reset` → re-seeded rows are `RECEIVED` again (queue restorable; the sweep is out of scope to run in-test — assert the `RECEIVED` precondition the sweep consumes).
  - [x] AC-4: `POST /reset` → `303 → /queue`; response body carries no submission/image/benchmark data; unit-test the purge helper directly (sentinel + missing-root + re-created-empty).
  - [x] Reset orchestrator unit test (DB re-seed + FS purge composed) independent of the HTTP layer.

### Project Structure Notes

- **New:** `app/web/routes_ops.py` (the `POST /reset` operator route), the reset orchestrator + purge helper (in `routes_ops.py` or a sibling `app/web/ops.py` — keep the FS purge OUT of `seed.py` so `seed()` stays DB-only), `tests/test_routes_ops.py`.
- **Update:** `app/main.py` (include the ops router — no exemption). Close the `TODO(epic-6-reset)` comment in `app/pipeline/preprocess.py:397` (point it at the new purge helper; optional, cosmetic).
- **Reuse, do not recreate:** `app/db/seed.py` `seed()` (the transactional re-seed), `app/db/connection.py` `get_connection`/`connect` (FK-on cascade), `app/config.py` `Settings.generated_images_dir`. The architecture maps FR-27 Demo Reset to `web/routes_ops.py` — the canonical home for this route.

## Dev Notes

### The re-seed IS the reset (do not re-implement the wipe)
- `seed()` is documented (`app/db/seed.py:9-12`) as the reset-friendly basis: one transaction, `DELETE FROM submissions` (cascades to `label_images`/`ocr_results`/`llm_results`/`field_comparisons`/`checklist_items`/`audit_events`/`review_progress`), reload, commit, rollback-on-error. Call it; never duplicate the DELETE/reload in the route.
- **FK cascade is load-bearing.** It only fires because `get_connection` sets `PRAGMA foreign_keys = ON` per connection (`app/db/connection.py:97`) — and `seed()` opens its connection through `get_connection`. Do not open a raw `sqlite3.connect` in this story.
- The cross-column CHECK on `submissions` (`status='DECIDED' ⇔ disposition/decided_at NOT NULL`) means a row re-seeded at `RECEIVED` **cannot** retain decision columns — clearing `disposition`/`decided_at`/`decision_notes` is automatic, not a separate UPDATE. AC-1 is satisfied by the wipe-and-reload, not by column surgery.

### Status lifecycle & the sweep (AR-5 / pipeline-is-the-only-writer)
- Reset re-seeds to `RECEIVED`. The **existing** APScheduler sweep (Story 2.2) picks up `RECEIVED` rows and runs them forward to `READY_FOR_REVIEW` — this story does NOT run the pipeline synchronously and does NOT write any pipeline-owned column. The web layer only triggers the DB re-seed + FS purge (cheap, explicit POST action) — the 5-second read contract is untouched (no OCR/inference on any request path; the reset POST does bulk DB writes via `seed()`, which is an explicit operator action, not a render path).
- AC-3's "restores the full pending queue" is realized cooperatively: reset produces `RECEIVED` rows; the sweep produces `READY_FOR_REVIEW`. In-test, assert the `RECEIVED` precondition (the sweep is exercised by its own Story 2.2 tests).

### Generated-images purge (AC-2)
- Purge ONLY `settings.generated_images_dir` (default `data/generated`) — the derived OpenCV variants (`*__enhanced.png` / `*__binarized.png`, `app/pipeline/preprocess.py:19-22`). `fixtures/images/` is read-only and baked into the Docker image — never delete it.
- Missing root ⇒ no-op (a fresh demo that never preprocessed). Re-create the empty root so the next sweep writes into it without a `mkdir` race. Path comes from `settings`, never from user input (no traversal surface).

### Firewall / offline posture (NFR-2)
- Reset is 100% local: a DB transaction + a local FS purge. Zero egress — `docker run --network none` must still serve `/reset` and the re-seed/purge must complete with no network. No assets, no model layer, no OCR touched.

### Security / no-leakage (AC-4)
- The reset response is a bare `303 → /queue`: no submission rows, image bytes, or benchmark numbers in the payload. It is an operator route behind the token gate (no exemption in `main.py`), so an unauthenticated `POST /reset` is bounced to `/access` like every other gated route — verify in the test (gated when `ACCESS_TOKEN` set).

### Reset-while-open is already handled (do not re-build)
- Story 4.11 AC4 already routes `GET /review/{id}` and the disposition POST calmly to `/queue?gone=1` when their submission no longer exists (`app/web/routes_review.py:231-237`). A reset firing mid-review therefore never crashes the open session. This story only adds the reset trigger; it must not regress that behavior (it won't — the cascade simply removes-then-reinserts rows, and `gone=1` keys on `get_submission(...) is None` at the moment the stale screen acts).

### Architecture compliance
- **snake_case** everywhere; type hints required; ruff line length 100.
- **Route conventions:** lowercase, no trailing slash, `POST /reset` exactly (project-context route table).
- **Verdict-vs-disposition separation** untouched (reset writes neither; it wipes-and-reloads).
- **Pipeline-is-the-only-writer** untouched: reset writes only via `seed()` (which writes APPLICATION columns + SEEDED audit rows — the seed's existing, sanctioned write surface) and purges the FS; it never writes `ocr_results`/`llm_results`/`field_comparisons`/`checklist_items`/`engine_verdict`.

### Previous story intelligence
- Run targeted tests: `.venv/Scripts/python.exe -m pytest tests/test_routes_ops.py -q`. Full gate once at the end: `bash scripts/ci.sh`.
- `app/main.py` is an app factory (`create_app()`); module-level `app = create_app()`. TestClient drives the real `app`. The lifespan starts the scheduler unless `scheduler_enabled=false` — tests that don't want a live sweep construct the app accordingly (mirror existing route tests' fixtures).
- Existing POST-action routes redirect with `303` (`POST /next` → `/review/{id}` or re-render; disposition → `/queue?recorded=…`). Match that idiom: `POST /reset` → `303 → /queue`.

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.1: Demo data reset] (FR-27, AR-12; transactional re-seed, clear disposition/decided_at/decision_notes, reset status, purge preprocessed images, purge review_progress, reachable without redeploy)
- [Source: _bmad-output/planning-artifacts/architecture.md#Demo Operations] (AR-12 reset = transactional re-seed + purge)
- [Source: _bmad-output/project-context.md] (route table `POST /reset`; status lifecycle; pipeline-is-the-only-writer; AR-14 review_progress purged by reset; firewall)
- [Source: docs/database-schema.md] (FK `ON DELETE CASCADE`; `review_progress` purged by `POST /reset`; cross-column CHECK on submissions)
- [Source: app/db/seed.py] (the reset-friendly transactional `seed()`)
- [Source: app/config.py] (`generated_images_dir`) · [Source: app/pipeline/preprocess.py:397] (the TODO hook closed here)
- [Source: app/web/routes_review.py:231-237] (demo-reset-while-open `?gone=1` — already shipped, must stay green)
- FR-27 / AR-12 / AR-14 [Source: epics.md]

## Dev Agent Record

### Agent Model Used

Amelia (BMad dev-story) — claude-opus-4-8

### Debug Log References

_(populated during implementation)_

### Completion Notes List

- Verified the prior implementation pass (`app/web/ops.py`, `app/web/routes_ops.py`,
  `tests/test_routes_ops.py`) against all four ACs and the reusable deps
  (`seed()`, `Settings.database_path`/`generated_images_dir`, `connect`/`init_db`,
  token gate) — code is faithful to the spec.
- **Defect found + fixed during verification:** Task 4 (wire the ops router into
  `app/main.py`) was marked done but the edit had not been applied — `routes_ops`
  was never imported or `include_router`'d, so `POST /reset` would 404 and every
  ops test would fail. Added `from app.web.routes_ops import router as ops_router`
  and `app.include_router(ops_router)` (no exemption → token gate protects it).
- `tests/test_routes_ops.py`: 11 passed. Re-seed reuses `seed()` (no DELETE/reload
  duplication); FS purge is best-effort + swallowed; route is a bare `303 → /queue`.
- **Code review (CR) — patches applied, all in `app/web/ops.py` + tests:**
  - *Path-safety guard (AC-2 hardening):* `purge_generated_images` now refuses any
    root that resolves to the repo root, the read-only `fixtures/` tree, or an
    ancestor of either — a `GENERATED_IMAGES_DIR` operator misconfig (e.g. `.`,
    the WORKDIR, a parent of `fixtures/`) is logged and skipped, never `rmtree`'d.
    This closes the only realistic vector that could violate AC-2's "`fixtures/images/`
    is NEVER touched".
  - *Non-directory root:* a stray FILE at the derived path is now unlinked +
    replaced with an empty dir (was: `rmtree` raised `NotADirectoryError`).
  - *Broadened best-effort swallow (Task-2 intent):* the FS-purge guard in `reset()`
    now catches `Exception` (was `OSError` only) so a committed re-seed can never be
    reported as failed / 500 by a non-`OSError` purge edge (e.g. `SQLITE_BUSY`-class
    races, `shutil` corner cases) — "the DB commit is the success boundary".
  - *Test coverage for the two AC failure paths (previously uncovered):*
    `test_reset_swallows_fs_purge_failure_after_committed_reseed` (AC-2 swallow),
    `test_reset_propagates_seed_failure_leaving_prior_corpus_intact` (AC-1 atomic
    rollback — prior corpus intact, purge never runs), `test_purge_refuses_repo_root_and_fixtures_parents`,
    `test_purge_handles_non_directory_root`; tightened the no-leak test to pin the
    empty-body bare-redirect contract (was vacuous on a 303 body).
  - `tests/test_routes_ops.py`: **15 passed**; full CI gate green.
- **Dismissed/deferred findings:** CSRF on `POST /reset` — mitigated by the existing
  `SameSite=Lax` + `HttpOnly` access cookie (`routes_access.py:49-55`); CSRF tokens
  are a cross-cutting concern absent from every POST route, out of 6.1 scope.
  Symlinked-root purge and reset-during-live-sweep (`SQLITE_BUSY`) characterization
  are deployment-specific and deferred (see `deferred-work.md`).

### File List

- `app/web/ops.py` (reset orchestrator + `purge_generated_images` helper)
- `app/web/routes_ops.py` (`POST /reset` operator route)
- `app/main.py` (wired the ops router — fix applied during verification)
- `tests/test_routes_ops.py` (AC-1..AC-4 + unit tests for the orchestrator/helper)

## Change Log

| Date | Change |
|------|--------|
| 2026-06-14 | Story 6.1 spec created (CS) — `POST /reset` operator route: transactional re-seed via `seed()` (cascade clears all children + review_progress + decision columns), generated-images purge, `303 → /queue`, behind the token gate. |
| 2026-06-14 | Story 6.1 implemented + verified (DS). Found the ops router was never wired into `app/main.py` (Task 4 mismarked); applied the import + `include_router`. `tests/test_routes_ops.py` 11 passed; full CI gate green. |
| 2026-06-14 | Story 6.1 code review (CR) — patches applied to `app/web/ops.py`: path-safety guard refusing repo-root/fixtures/ancestor purges (AC-2 hardening), non-directory-root handling, and broadened the best-effort FS-purge swallow `OSError → Exception` (Task-2 "DB commit is the success boundary"). Added 4 tests (AC-1 atomic-rollback, AC-2 swallow, path-safety, non-dir root) + tightened the no-leak assertion. `tests/test_routes_ops.py` 15 passed; full CI gate green. Symlink-root purge, reset-during-live-sweep, and CSRF deferred to `deferred-work.md`. Story → done. |
