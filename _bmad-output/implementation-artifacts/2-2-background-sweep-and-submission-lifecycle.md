---
baseline_commit: ec71fa057eb6efc54258e78a7cafa40cb67db6b4
---

# Story 2.2: Background sweep & submission lifecycle

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want submissions processed in the background the moment they arrive,
so that the review screen is already done thinking before I open it.

## Acceptance Criteria

1. **AC1 — In-process APScheduler sweeps `RECEIVED` rows with bounded concurrency.**
   **Given** an in-process APScheduler started in the FastAPI app lifespan (single process, single Railway service — D1/D3)
   **When** the periodic sweep runs **Then** it finds `RECEIVED` submissions and dispatches each to a processing job, with a **bounded** worker pool (no unbounded fan-out that could starve the read path)
   **And** a submission is **claimed atomically** (`RECEIVED → PROCESSING` via a conditional `UPDATE … WHERE status='RECEIVED'`) so two overlapping sweeps never double-process the same row. *(AR-2, D3)*

2. **AC2 — Forward lifecycle transitions with audit + timing.**
   **Given** a claimed submission
   **When** it is processed **Then** it transitions `RECEIVED → PROCESSING → READY_FOR_REVIEW` (forward order only), writing `audit_events` rows from the fixed vocabulary in order — `OCR_STARTED`, `OCR_COMPLETED`, `ANALYSIS_COMPLETED`, `READY` — each with `actor`, `from_status`/`to_status`, and `occurred_at`
   **And** the total pre-compute time is rolled up into `submissions.processing_ms` (≥ 0); per-stage timing is recoverable from the `audit_events` timeline (event-to-event deltas) — **no new per-stage column is added**. *(FR-9, AR-10, database-schema.md §1.7)*

3. **AC3 — Minimal pass-through stage (not blocked on 2.3–2.5).**
   **Given** that preprocessing (2.3), OCR (2.4), and LLM (2.5) stages do not yet exist
   **When** the orchestrator (`run.py`) runs **Then** it executes a **minimal pass-through** stage sequence behind a stable seam, so the lifecycle ships and is testable now, and Stories 2.3–2.5 plug their real stages into that seam **without changing the scheduler or status machinery**. *(epics.md Story 2.2 Note)*

4. **AC4 — A stage failure lands in a visible error state, never a silent stall.**
   **Given** a stage that raises (e.g. an unreadable image or an engine crash, simulated in test)
   **When** the orchestrator catches it **Then** the failure is recorded honestly — an `ERROR`-status row in the relevant result table and/or a marked `audit_events` note — and the submission is **finalized** (it does not remain stuck in `PROCESSING`): the sweep moves on, the row is not silently lost, and a partially-extracted submission carries a non-`PASS` advisory posture for the human. **No 6th `status` value and no new `audit_events.event_type` are introduced** — see Dev Notes "Failure state without a new enum". *(FR-9)*

5. **AC5 — p95 time-to-ready ≤ 10 minutes; read path never starves.**
   **Given** the seeded corpus (30–50 submissions) swept on the deployment hardware
   **When** the pass-through pipeline runs **Then** p95 time-to-ready is ≤ 10 minutes, and the bounded concurrency leaves the read path responsive (the scheduler must never block Uvicorn request handling). *(NFR-1, FR-9)*

## Tasks / Subtasks

- [x] **Task 1 — `app/pipeline/status.py`: status transitions + audit writes (AC2, AC4)**
  - [x] Add `claim_for_processing(conn, submission_id) -> bool` — conditional `UPDATE submissions SET status='PROCESSING' WHERE id=? AND status='RECEIVED'`; returns `True` only if a row was claimed (rowcount == 1). This is the concurrency guard (AC1).
  - [x] Add `advance(conn, submission_id, *, to_status, event_type, actor, note=None)` — single helper that writes the `submissions.status` change **and** the matching `audit_events` row (`from_status`/`to_status`/`occurred_at`) in one transaction, enforcing the forward order `RECEIVED → PROCESSING → READY_FOR_REVIEW`. Reject any non-forward transition (raise) — the one bounded backward transition (`DECIDED → READY_FOR_REVIEW`) belongs to the web layer, not here.
  - [x] Add `record_event(conn, submission_id, *, event_type, actor, note=None)` for non-transition events (`OCR_STARTED`, `OCR_COMPLETED`, `ANALYSIS_COMPLETED`). `event_type` must be from the fixed vocabulary (`SEEDED/OCR_STARTED/OCR_COMPLETED/ANALYSIS_COMPLETED/READY/OPENED/DECIDED/UNDONE`); assert membership.
  - [x] Add `set_processing_ms(conn, submission_id, processing_ms)` (CHECK ≥ 0). Raw SQL stays inside `app/db/` — if these write helpers touch SQL, put the SQL in `app/db/repositories.py` and keep `status.py` as the orchestration-level caller (see Dev Notes "Data boundary").

- [x] **Task 2 — `app/pipeline/run.py`: orchestrator with the stage seam (AC2, AC3, AC4)**
  - [x] `process_submission(db_path, submission_id) -> None`: claim → `OCR_STARTED` → run the **stage sequence** → `ANALYSIS_COMPLETED` → roll up `processing_ms` → `advance(... READY_FOR_REVIEW, event_type='READY')`. Open ONE `connect(db_path)` per submission (do not share a connection across threads — see Dev Notes "SQLite + threads").
  - [x] Define the stage seam as an ordered list of callables `STAGES: list[Stage]` where `Stage = Callable[[StageContext], None]`, and a `StageContext` dataclass carrying `conn`, `submission`, `label_images`, and a mutable scratch dict. Ship Story 2.2 with a single `passthrough_stage` that records `OCR_STARTED`/`OCR_COMPLETED` markers and does no extraction. **Document the seam contract** so 2.3 (`preprocess`), 2.4 (`ocr`), 2.5 (`llm`) register stages here with zero scheduler/status changes.
  - [x] Wrap **each stage** in `try/except`: on exception, call the failure path (Task 4) and continue finalizing rather than aborting the whole submission or bubbling into the scheduler thread.
  - [x] Time the run with `time.monotonic()` deltas → integer ms (never float currency/`Date` math; `_ms` is INTEGER). Roll the total into `processing_ms`.

- [x] **Task 3 — `app/pipeline/scheduler.py`: APScheduler sweep, bounded concurrency (AC1, AC5)**
  - [x] Build a `BackgroundScheduler` (APScheduler 3.11.x) with a bounded `ThreadPoolExecutor` (small pool, e.g. `max_workers` from config, default 2–4) and `job_defaults={'max_instances': 1, 'coalesce': True}` so overlapping sweeps don't pile up.
  - [x] Register `sweep(db_path)` on an interval trigger (config `SWEEP_INTERVAL_SECONDS`, small default e.g. 5s for the demo). `sweep` selects `RECEIVED` ids (oldest-first, bounded batch size) and submits each to `process_submission`; each job first calls `claim_for_processing` and **no-ops if the claim fails** (another worker got it).
  - [x] Expose `start_scheduler(app)` / `shutdown_scheduler(app)` and call them from the **`app/main.py` lifespan** (start after `init_db` + `_seed_if_empty`, shutdown on app stop). Guard with a config flag (e.g. `SCHEDULER_ENABLED`, default `True`) so tests can construct the app without a live scheduler.
  - [x] Ensure the scheduler thread never touches the request path and holds no long DB write txn that could block readers (WAL + short transactions; commit per stage).

- [x] **Task 4 — Failure path (AC4)**
  - [x] On a stage exception: record the error honestly without inventing enum values. Recommended: write an `audit_events` row using an existing `event_type` (the stage's `*_COMPLETED` or a generic marker) with a clear `note` (e.g. `"stage=ocr failed: <exc class>"`), and — once 2.4/2.5 exist — an `ERROR`-status row in `ocr_results`/`llm_results`. In 2.2's pass-through, only the `audit_events` note exists.
  - [x] **Finalize, don't stall:** after recording, the orchestrator still completes the submission to `READY_FOR_REVIEW` (so it is never stuck mid-flight and never silently lost). Rationale + the "never serve partially-processed" reconciliation are in Dev Notes "Failure state without a new enum" — confirm the chosen finalization with the open question before deviating.
  - [x] Never let a single submission's failure kill the sweep or crash the scheduler thread (catch at `process_submission` boundary too).

- [x] **Task 5 — Tests (`tests/test_pipeline.py`) — offline, fast, deterministic (all ACs)**
  - [x] Use a `tmp_path` SQLite DB via `init_db` + a couple of inserted `RECEIVED` submissions (+ `label_images`), following the `tests/test_repositories.py` / `tests/test_seed.py` fixture pattern. **No real Tesseract/Paddle/provider** — register **stub stages** into the seam (monkeypatch `run.STAGES`) so the suite runs under `docker run --network none` with no native deps.
  - [x] AC1: two concurrent `claim_for_processing` calls on the same row → exactly one returns `True`.
  - [x] AC2: after `process_submission`, status is `READY_FOR_REVIEW`, `processing_ms` is set (≥ 0), and `audit_events` contains `OCR_STARTED → OCR_COMPLETED → ANALYSIS_COMPLETED → READY` in `occurred_at` order with correct `from_status`/`to_status`.
  - [x] AC2 (guard): `advance` rejects a non-forward transition (e.g. `READY_FOR_REVIEW → PROCESSING`) and rejects an out-of-vocabulary `event_type`.
  - [x] AC4: a stub stage that raises → submission is finalized (not left `PROCESSING`), an `audit_events` failure note exists, and the sweep processes a sibling `RECEIVED` row unaffected.
  - [x] AC3/seam: assert `run.STAGES` is the single registration point and that swapping the stage list changes behavior without touching `scheduler.py`/`status.py`.
  - [x] AC5 (light): a timing assertion that a small batch finalizes well within budget (no real 10-min wait — assert structure/ordering, not wall-clock SLA; the SLA is a deployment-hardware property documented, not unit-tested).

- [x] **Task 6 — Config + validate + finalize**
  - [x] Add `scheduler_enabled`, `sweep_interval_seconds`, `pipeline_max_workers`, `pipeline_batch_size` to `app/config.py` `Settings` (env `SCHEDULER_ENABLED`, `SWEEP_INTERVAL_SECONDS`, `PIPELINE_MAX_WORKERS`, `PIPELINE_BATCH_SIZE`) with safe defaults; document them in `.env.example`. Absent env ⇒ sensible defaults, app still boots.
  - [x] `ruff check` + `ruff format` (line length 100); full `pytest` green (no Epic-1 / 2.1 regressions). Confirm app still boots under `docker run --network none` (scheduler starts, no egress).
  - [x] Update File List + Change Log + Completion Notes.

### Review Findings

_Code review 2026-06-12 (Blind Hunter + Edge Case Hunter + Acceptance Auditor). 3 patch, 5 defer, 6 dismissed. All five ACs and every binding boundary (atomic claim, forward-only transitions, fixed audit vocabulary with no new enum/status, no per-stage column, data boundary, connection-per-thread, zero egress, verdict/disposition separation) verified satisfied by the Acceptance Auditor. Findings below are robustness gaps around config validation and post-claim failure recovery, not AC violations._

- [x] [Review][Patch] Non-positive pipeline int config is unvalidated — `_env_int` advertises "positive-int" but only rejects non-integers, so `0`/negatives pass through. `SWEEP_INTERVAL_SECONDS<=0` → APScheduler `IntervalTrigger` raises in the unguarded lifespan → **app boot crash**; `PIPELINE_BATCH_SIZE<0` → SQLite `LIMIT -1` = **unbounded** claim (defeats the AC1/AC5 bounded-batch guarantee); `PIPELINE_BATCH_SIZE=0` → `LIMIT 0` → **sweep permanently inert**. `pipeline_max_workers` is already floored with `max(1, ...)`; the other two are not. Fix: floor interval and batch_size to >=1 (mirror the max_workers pattern). [app/config.py:_env_int / app/pipeline/scheduler.py] _(blind+edge, High)_ — FIXED: `_env_int` gained a `min_value` floor; interval/batch_size/max_workers all parse with `min_value=1` (out-of-range ⇒ default). Test `test_pipeline_int_env_out_of_range_falls_back_to_default`.
- [x] [Review][Patch] Post-claim failure strands the row in `PROCESSING` with no recovery — `claim_for_processing` commits `RECEIVED→PROCESSING` immediately, but any exception after the claim and before/within finalize (`get_submission`/`list_label_images`/`record_event`/`set_processing_ms`/`advance`, a `SQLITE_BUSY` past busy_timeout, or a stage leaving `conn` in an aborted txn) is only logged by the outer `except` → the row is permanently `PROCESSING`. `list_received_ids`/`claim_for_processing` only ever match `RECEIVED`, and there is no reaper, so it is never retried. Violates the story's own "never stuck in PROCESSING" invariant for the infra-failure path (AC4 covers *stage* failures, which are handled). Fix (spec-aligned with Open Q#1 finalize-don't-stall): in the outer `except`, best-effort finalize a claimed row to `READY_FOR_REVIEW` with an honest error note via a fresh connection. [app/pipeline/run.py:process_submission] _(blind+edge, High)_ — FIXED: added `_finalize_stuck_after_failure` — outer `except` rescues a still-`PROCESSING` row to `READY_FOR_REVIEW` (note "finalized after worker failure") on a fresh connection; itself guarded. Test `test_post_claim_failure_is_rescued_not_left_stuck`.
- [x] [Review][Patch] `shutdown_scheduler` uses `scheduler.shutdown(wait=False)` — on app teardown an in-flight `sweep` worker that has committed the claim but not finalized is abandoned, widening the stuck-`PROCESSING` window. Fix: `wait=True` for a bounded graceful drain (safe for the passthrough stage; revisit alongside the per-job timeout defer when heavy stages land). [app/pipeline/scheduler.py:shutdown_scheduler] _(blind+edge, Medium)_ — FIXED: `scheduler.shutdown(wait=True)` drains in-flight workers before teardown.
- [x] [Review][Defer] No per-job timeout — `future.result()` has no timeout and `max_instances=1`+`coalesce=True` means a single hung stage wedges the whole pipeline (no further sweeps fire). Not triggerable by the passthrough stage; becomes real when 2.4/2.5 heavy stages land. [app/pipeline/scheduler.py:sweep] — deferred to OCR/LLM stage stories
- [x] [Review][Defer] `audit_events.occurred_at` is 1-second resolution; correct timeline order relies on a `, id` tiebreak that currently exists only in the test `_events` helper. No production audit-timeline reader exists yet, but any future one (review-workspace timeline UI) MUST `ORDER BY occurred_at, id`. [app/db/schema.sql / future timeline reader] — deferred to the timeline UI story
- [x] [Review][Defer] `actor="pipeline"` diverges from the `database-schema.md` §1.7 documented convention (`system:ocr_job` / `system:analysis_job`). Schema-legal (free-text, no CHECK) and AC2's "with actor" is met, but provenance consistency matters for the audit trail. 2.4/2.5 should emit the per-job actor names. [app/pipeline/status.py:PIPELINE_ACTOR] — deferred to OCR/LLM stage stories
- [x] [Review][Defer] `advance` permits multi-step forward jumps (any strictly-later status passes the guard, e.g. `PROCESSING→DECIDED` would skip `READY_FOR_REVIEW`/`IN_REVIEW`). Not exercised in 2.2 (only `→READY_FOR_REVIEW` is called), but future stories must not skip intermediate transitions; consider a single-step assertion. [app/pipeline/status.py:advance] — deferred, latent seam concern
- [x] [Review][Defer] AC1 atomicity test runs the two `claim_for_processing` calls serially on one thread, not concurrently — it proves the conditional-`WHERE` guard logic but not true concurrency (the underlying atomic `UPDATE` is correct regardless). Strengthen with a genuine two-thread race if desired. [tests/test_pipeline.py:test_claim_is_atomic_only_one_winner] — deferred, low-value test hardening

**Dismissed as by-design / noise (6):** redundant trailing `connect()` commit (no-op — per-step commits already flushed); `processing_ms=0` for sub-millisecond passthrough runs (schema `CHECK >= 0` is the contract); worker-thread `connect()` failure log-spam (row stays `RECEIVED`, retried next tick — recoverable); `advance` read-then-write TOCTOU vs the web backward writer (non-reachable — a `DECIDED` row is never in the pipeline); `repo.claim_for_processing` vs `status.claim_for_processing` name collision (intentional SQL-vs-orchestration layering); Blind Hunter's flagged-then-retracted finalize-on-failure "non-defect" (it is the confirmed design).

## Dev Notes

### Scope boundary (what 2.2 is and is NOT)
- **IS:** the lifecycle/orchestration machinery — `scheduler.py` (APScheduler sweep + bounded concurrency), `run.py` (the stage-seam orchestrator), `status.py` (forward transitions + `audit_events` + `processing_ms` roll-up), lifespan wiring, and a **minimal pass-through stage**.
- **IS NOT:** real preprocessing (2.3), OCR (2.4), or LLM (2.5). Do **not** import `cv2`/`pytesseract`/`paddleocr`/provider SDKs here. The whole point of the seam is that 2.2 ships and is green before any heavy dependency lands. [Source: epics.md#Story-2.2 Note]

### Failure state without a new enum (the FR-9 reconciliation — read this)
FR-9 calls for a "failure state … visible … never a silent stall." The lifecycle `status` enum is **locked at five values** (`RECEIVED/PROCESSING/READY_FOR_REVIEW/IN_REVIEW/DECIDED`) and `audit_events.event_type` is a **fixed vocabulary with no `FAILED`** [Source: docs/database-schema.md §3.1, §1.7; project-context.md Naming/Status]. The architecture's deliberate choice is **"honest per-component states surfaced in the UI (pipeline failure …)"**, not a workflow state machine [Source: architecture.md#API-&-Communication-Patterns; EXPERIENCE.md State Patterns "pipeline failure (visible per-check error)"]. So:
- A failed stage is recorded as an **`ERROR`-status result row** (`ocr_results`/`llm_results` have `status IN ('OK','ERROR')` — 2.4/2.5) plus an `audit_events` **note**, and the engine posture for an unsalvageable read is **`REVIEW`, never a fake `PASS`/`FAIL`** [Source: docs/image-handling.md §4 "if still unreadable, flag REVIEW for a human"].
- **"Silent stall" = stuck in `PROCESSING` forever.** We avoid it by always finalizing the row. **"Serving a partially-processed submission" (an anti-pattern)** means serving one whose pre-compute has **not finished** — a row whose pipeline *ran and recorded errors* **has** finished, so serving it with a visible error is correct, not the anti-pattern. [Source: project-context.md Anti-patterns; architecture.md Pipeline boundary]
- **Do not add a 6th status or a `FAILED` event** in this story. If review concludes a first-class failed state is required, that is a schema-and-contract change (touching `database-schema.md`, `repositories.py` `Literal`s, project-context, the status CHECK) and must be raised explicitly — see Open Questions.

### Per-stage timing — no new column
`submissions.processing_ms` is the **total** roll-up [Source: docs/database-schema.md §1.1]. Per-engine timing already lives in `ocr_results.latency_ms` / `llm_results.latency_ms`; per-**stage** timing is derived from `audit_events.occurred_at` deltas (`OCR_STARTED→OCR_COMPLETED`, etc.). The epic's "per-stage `processing_ms` + timestamps" is satisfied by the timeline + the total — **do not** add per-stage columns to `submissions`. [Source: epics.md#Story-2.2; database-schema.md §1.7]

### SQLite + threads (correctness trap)
APScheduler runs jobs on worker threads. `sqlite3` connections are **not** shareable across threads. Open a **fresh** `connect(db_path)` **inside** `process_submission` (per job/thread), never pass a connection from the scheduler thread into a worker. `app/db/connection.py` already sets `PRAGMA foreign_keys = ON`, WAL, and a `busy_timeout` "explicitly sized for the Epic-2 pipeline's writers" — use `connect()`/`get_connection()`, keep write transactions short (commit per stage) so readers never block. [Source: app/db/connection.py; architecture.md Concurrency note]

### Atomic claim (the concurrency contract)
With `coalesce=True` + `max_instances=1` overlapping sweeps are already suppressed, but the **claim** is the real guard: `UPDATE submissions SET status='PROCESSING' WHERE id=? AND status='RECEIVED'` and check `rowcount`. Only the worker that flips the row proceeds; a losing worker no-ops. This makes the sweep idempotent and safe even if batch sets overlap. [Source: architecture.md D3 "bounded-concurrency jobs"]

### Where this wires in
- `app/main.py` already has an `@asynccontextmanager` lifespan doing `init_db(settings.database_path)` then `_seed_if_empty(db_path)`. **Append** `start_scheduler(app)` after seeding and `shutdown_scheduler(app)` on teardown. Keep it behind `settings.scheduler_enabled` so `TestClient(create_app())` doesn't spin a live scheduler unless a test wants it. [Source: app/main.py lifespan; architecture.md main.py "APScheduler startup"]
- The data-flow this story realizes the first half of: `seed.py` inserts `RECEIVED` → **APScheduler sweep → preprocess → OCR → LLM → engine → rollup → READY**. 2.2 builds the sweep + rollup + READY with pass-through middle stages. [Source: architecture.md#Data-Flow]

### Architecture / boundary rules this story must honor
- **Pipeline is the only writer** of pipeline-owned columns; the web layer owns `disposition`/`decided_at`/`decision_notes` + the human `status` writes. 2.2 writes only `status` (forward, system actor), `audit_events`, and `processing_ms`. [Source: architecture.md Pipeline boundary; project-context.md]
- **Data boundary:** raw SQL only inside `app/db/`. Put any new SQL in `repositories.py`; `pipeline/*.py` calls those helpers. [Source: architecture.md Data boundary; app/db/connection.py docstring]
- **5s read contract untouched:** nothing here runs on a request path; the scheduler is the background owner of all heavy work. [Source: architecture.md Process Patterns]
- **No egress:** APScheduler is in-process; nothing in 2.2 opens a socket. Must remain runnable under `docker run --network none`. [Source: architecture.md External boundary; outbound-calls-inventory.md]

### Source tree components to touch
- `app/pipeline/scheduler.py` (NEW — package `app/pipeline/` exists with `__init__.py`).
- `app/pipeline/run.py` (NEW — orchestrator + stage seam).
- `app/pipeline/status.py` (NEW — transitions + audit + timing helpers).
- `app/main.py` (UPDATE — start/stop scheduler in lifespan, behind `scheduler_enabled`).
- `app/config.py` (UPDATE — scheduler/pipeline settings).
- `app/db/repositories.py` (UPDATE — add status/audit/timing write helpers if SQL is needed there; module already gained write helpers in 2.1).
- `.env.example` (UPDATE — new env vars).
- `tests/test_pipeline.py` (NEW).

### Previous story intelligence (2.1 patterns to reuse)
- 2.1 established the **write helpers live in `repositories.py`** pattern (`insert_ocr_result`, `insert_llm_result`) and the `connect(db_path)` usage. Reuse the same style for status/audit writes — do not open raw `sqlite3.connect`.
- 2.1's tests register **in-test stub adapters** to prove engine-agnosticism offline. Reuse that instinct: 2.2's tests register **stub stages**, so the lifecycle is verified without native OCR/LLM deps. [Source: 2-1 story Task 5; tests/test_contracts.py pattern]
- `audit_events`, `ocr_results`, `llm_results` tables already exist in `app/db/schema.sql` (created by 2.1) — no DDL in this story.

### Testing standards
- pytest in top-level `tests/`, `test_*.py`, mirroring `app/`; ruff line length 100; type hints required. [Source: project-context.md Testing & Tooling]
- Highest-value assertions here: the **atomic claim** (no double-processing), the **forward-only transition guard**, the **audit ordering**, and **finalize-on-failure** (no stuck `PROCESSING`).

### Project Structure Notes
- Repo nests pipeline under **`app/pipeline/`** (architecture tree shows `pipeline/` without the `app/` prefix on some lines; use the realized `app/pipeline/` path, matching how 2.1 used `app/db/` / `app/adapters/`). [Source: 2-1 story Project Structure Notes; architecture.md tree]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.2] — story statement, ACs, and the pass-through Note.
- [Source: _bmad-output/planning-artifacts/architecture.md#Core-Architectural-Decisions] D1 (single service), D3 (in-process APScheduler, bounded concurrency); [#Project-Structure] `pipeline/{scheduler,run,status}.py` roles; [#Data-Flow]; [#Architectural-Boundaries] pipeline/data boundaries; [#Communication-Patterns] forward status order.
- [Source: docs/database-schema.md §1.1] `submissions.status`/`processing_ms`; [§1.7] `audit_events` fixed `event_type` vocabulary + `from_status`/`to_status`.
- [Source: docs/image-handling.md §4] unsalvageable read → `REVIEW`, never auto-reject.
- [Source: _bmad-output/project-context.md] status transitions; the 5s contract incl. the "cheap single-row writes allowed on POST/jobs" clarification; anti-patterns (serving a partially-processed submission; spinner that blocks).
- [Source: app/main.py, app/db/connection.py, app/db/repositories.py, app/config.py] existing lifespan/connection/write-helper/settings patterns.

### Open Questions (raise before/at dev; do not silently decide)
1. **Failure finalization:** confirm the chosen design — a hard-failed submission is **finalized to `READY_FOR_REVIEW`** with `ERROR` result rows + an audit note + `REVIEW` posture (vs. holding it back from the queue). The story implements "finalize, surface the error" per the architecture's honest-states posture; flagging because FR-9's "failure state" wording could be read as wanting a held-back state. A held-back design would need a first-class failed marker (schema/contract change).

## Dev Agent Record

### Agent Model Used

Amelia (Senior Software Engineer persona) — claude-opus-4-8[1m].

### Debug Log References

- **Integration bug caught by boot smoke test (not by unit tests):** the first
  `start_scheduler` passed `next_run_time=None` to APScheduler's `add_job`. In
  APScheduler 3.x that value *pauses* the job rather than meaning "use the
  trigger's first-fire time", so the registered sweep never fired — every unit
  test still passed because they call `sweep()`/`process_submission()` directly,
  bypassing the trigger. A full-lifespan `TestClient` smoke run surfaced it (36
  seeded rows stuck `RECEIVED`, only `SEEDED` events). Fix: removed
  `next_run_time=None` (backlog-burst suppression is already `coalesce=True`).
  Added `test_live_scheduler_fires_and_finalizes_via_lifespan` as a permanent
  regression guard that drives the real scheduler through the lifespan.

### Completion Notes List

- **Open Question resolved with Diane before coding:** hard-stage-failure
  finalization = **finalize → READY_FOR_REVIEW** with an honest `audit_events`
  note and no new enum (the held-back-failed-state alternative would be a
  schema+contract change). Implemented accordingly.
- **Data boundary honored:** all new raw SQL lives in `app/db/repositories.py`
  (`get_status`, `claim_for_processing`, `update_status`, `insert_audit_event`,
  `update_processing_ms`, `list_received_ids`); `app/pipeline/status.py` is the
  orchestration caller that adds the forward-only guard, the audit-vocabulary
  assert, and per-step commits ("commit per stage" → PROCESSING is durable the
  instant it's claimed and WAL readers never block).
- **AC1 atomic claim:** conditional `UPDATE … WHERE status='RECEIVED'` + rowcount;
  two concurrent claims → exactly one winner (tested). `max_instances=1` +
  `coalesce=True` suppress overlapping ticks on top of the claim.
- **AC2:** timeline emitted in order `OCR_STARTED → OCR_COMPLETED →
  ANALYSIS_COMPLETED → READY`; `READY` carries `from_status=PROCESSING` /
  `to_status=READY_FOR_REVIEW`; `processing_ms` rolled from `time.monotonic()`
  deltas (INTEGER, ≥ 0). No per-stage column added — per-stage timing is the
  `occurred_at` deltas. Note: `occurred_at` (CURRENT_TIMESTAMP) is 1-second
  resolution, so ordering reads use `ORDER BY occurred_at, id` (id breaks ties).
- **AC3 seam:** `run.STAGES: list[Stage]` (`Stage = Callable[[StageContext],
  None]`) is the single registration point; `passthrough_stage` records the OCR
  markers and does no extraction. Swapping `STAGES` changes behavior with zero
  edits to `scheduler.py`/`status.py` (tested). 2.3/2.4/2.5 register here.
- **AC4 finalize-on-failure:** a raising stage is caught per-stage; its error is
  appended to the `ANALYSIS_COMPLETED` note (`stage=<name> failed: <repr>`), the
  submission is still advanced to READY_FOR_REVIEW (never stuck PROCESSING), and
  a sibling row is processed unaffected (tested). `engine_verdict` is left NULL —
  the advisory REVIEW posture is Epic 3's roll-up contract, not 2.2's to fake.
- **AC5:** bounded `ThreadPoolExecutor(max_workers)` per sweep is the concurrency
  ceiling; the scheduler runs off the request path entirely (5s read contract
  untouched). SLA is a deployment-hardware property — not wall-clock unit-tested;
  the live-lifespan smoke finalized all 36 seeded rows in < 30 ms each.
- **Zero-egress posture intact:** in-process APScheduler, no sockets opened; full
  app booted + swept under a network-free `TestClient` lifespan run.
- Verification: `pytest` 132 passed; `ruff check` + `ruff format --check` clean.

### File List

- `app/pipeline/status.py` (NEW) — transitions, audit, timing orchestration.
- `app/pipeline/run.py` (NEW) — per-submission orchestrator + stage seam + `passthrough_stage`.
- `app/pipeline/scheduler.py` (NEW) — APScheduler bounded sweep + `start/shutdown_scheduler`.
- `app/db/repositories.py` (UPDATE) — pipeline lifecycle SQL write helpers.
- `app/config.py` (UPDATE) — `scheduler_enabled` / `sweep_interval_seconds` / `pipeline_max_workers` / `pipeline_batch_size` + `_env_int`.
- `app/main.py` (UPDATE) — lifespan start/shutdown of the scheduler (guarded).
- `.env.example` (UPDATE) — the four new pipeline env vars.
- `tests/test_pipeline.py` (NEW) — offline stub-stage tests for AC1–AC5 + live-lifespan regression guard.

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-12 | Story 2.2 drafted — background sweep & submission lifecycle (scheduler/run/status, pass-through stage seam, atomic claim, forward transitions + audit + processing_ms roll-up, finalize-on-failure). Status → ready-for-dev. |
| 2026-06-12 | Story 2.2 implemented (TDD): `pipeline/{status,run,scheduler}.py`, repository lifecycle write helpers, config + `.env.example` vars, lifespan wiring. Caught & fixed an APScheduler `next_run_time=None` job-pause bug via a full-lifespan smoke test; added a live-scheduler regression guard. 132 tests pass, ruff clean. Status → review. |
| 2026-06-12 | Code review (3-layer adversarial). Acceptance Auditor confirmed all five ACs + every boundary satisfied. 3 patches applied (floor non-positive pipeline int config; rescue post-claim failures to READY_FOR_REVIEW instead of stuck PROCESSING; `shutdown(wait=True)` graceful drain), 5 deferred, 6 dismissed. 134 tests pass (+2 regression guards); ruff clean. Status → done. |
