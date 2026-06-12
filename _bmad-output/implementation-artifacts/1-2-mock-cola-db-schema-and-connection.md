---
baseline_commit: 552cb74b60624d037cc8ba54728671d6144a609e
---

# Story 1.2: Mock COLA Database schema & connection layer

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want the core Submissions and label-image tables plus a typed read layer,
so that application data can be stored and read consistently without an ORM.

## Acceptance Criteria

**AC-1 — `submissions` + `label_images` exist, WAL-initialized, with the right enums and naming**
**Given** `app/db/schema.sql` authored from `docs/database-schema.md`
**When** the app initializes the SQLite database (file path env-configurable for the Railway Volume; WAL enabled)
**Then** the `submissions` table (Form 5100.31 application fields, `ttb_id`, `beverage_type`, `status`, `disposition`, `submitted_at`, `decided_at`) and the `label_images` child table (1–10 images per submission) exist
**And** enums are stored as `TEXT + CHECK` in `UPPER_SNAKE` (`beverage_type`, `status`, `disposition`, `source_of_product`, `application_type`, `image_role`); `status` constrained to `RECEIVED, PROCESSING, READY_FOR_REVIEW, IN_REVIEW, DECIDED`
**And** column/table naming is `snake_case` plural per the architecture naming patterns; timestamps `_at` (UTC ISO-8601).

**AC-2 — Connection layer enforces the required PRAGMAs**
**Given** `app/db/connection.py`
**When** any connection is opened
**Then** `PRAGMA foreign_keys = ON` is set on every connection (so `ON DELETE CASCADE` and FK validity are enforced) and `PRAGMA journal_mode = WAL` is established on the database
**And** the connection uses a row factory that exposes columns by their `snake_case` name.

**AC-3 — Typed read layer returns Pydantic v2 models; SQL is confined to `db/`**
**Given** the typed read layer
**When** a row is read through `app/db/repositories.py`
**Then** it is validated/exposed via a Pydantic v2 model with `snake_case` fields
**And** raw SQL exists only inside `app/db/`; no other module issues SQL.

**AC-4 — Schema invariants hold under test**
**Given** the DDL constraints from `database-schema.md`
**When** rows are inserted
**Then** an out-of-vocabulary `status`/`beverage_type` is rejected by the `CHECK`; a `label_images` row with `position = 11` is rejected (`CHECK position BETWEEN 1 AND 10`); the cross-column invariant holds (a `DECIDED` row requires `disposition` + `decided_at`; a non-`DECIDED` row forbids them); and deleting a submission cascades to its `label_images`.

*(Source: epics.md Story 1.2; AR-2, AR-10, AR-13; docs/database-schema.md §1.1/§1.2/§3; docs/data-dictionary.md §1/§2/§5.)*

> **Scope note (binding):** This story creates **only** `submissions` and `label_images`. `ocr_results`, `llm_results`, `field_comparisons`, `checklist_items` are created by their owning stories in Epics 2–3; `audit_events`, `review_progress`, and `submission_extra_fields` are added by the later stories that first need them (seed/pipeline/review). Do **NOT** front-load the full schema (project-context: "create tables only in the story that needs them").

## Tasks / Subtasks

- [x] **Task 1 — `app/db/schema.sql`: `submissions` + `label_images` only (AC: 1, 4)**
  - [x] `submissions` transcribed faithfully from `database-schema.md §1.1`: all APPLICATION columns, lifecycle/result columns, every `TEXT + CHECK` enum, both cross-column CHECKs (DECIDED⇔disposition+decided_at; `correction_due_at` only when `NEEDS_CORRECTION`), `idx_submissions_queue`, `trg_submissions_set_updated_at` AFTER UPDATE trigger.
  - [x] `label_images` from `§1.2`: FK `ON DELETE CASCADE`, `image_role` CHECK (`BRAND/BACK/NECK/STRIP/OTHER`), `position` CHECK `BETWEEN 1 AND 10`, `filename` NOT NULL, metadata, `UNIQUE(submission_id, position)`, `idx_label_images_submission`.
  - [x] Used `CREATE … IF NOT EXISTS` (table/index/trigger) for idempotent re-init; preserved the `TODO(postgres)` portability comments verbatim. No deferred tables added.
- [x] **Task 2 — `app/config.py`: add `database_path` (AC: 1)**
  - [x] Added `database_path: str` to `Settings`, env `DATABASE_PATH`, default `data/app.db`; absent ⇒ default, never raises (AR-9).
- [x] **Task 3 — `app/db/connection.py`: connection + PRAGMAs + init (AC: 2, 1)**
  - [x] `get_connection(db_path)` → `sqlite3.Connection`, `row_factory = sqlite3.Row`, `PRAGMA foreign_keys = ON` on every connection.
  - [x] `init_db(db_path)` → makes parent dir, sets `PRAGMA journal_mode = WAL`, `executescript(schema.sql)`; idempotent. `schema.sql` loaded via `Path(__file__).parent`.
  - [x] Added `connect(db_path)` context manager (yields + commits + closes) for repositories/tests.
- [x] **Task 4 — `app/db/repositories.py`: Pydantic v2 read models + queries (AC: 3)**
  - [x] `Submission` and `LabelImage` Pydantic v2 models, `snake_case` fields mirroring columns (timestamps/dates as ISO `str | None`; numerics `int/float | None`; enums `str`).
  - [x] `get_submission`, `get_submission_by_ttb_id`, `list_label_images` — raw SQL confined to `db/`; rows mapped via `model_validate(dict(row))`. No seed/write helpers (Story 1.3).
- [x] **Task 5 — Wire init into app startup (AC: 1)**
  - [x] `app/main.py` initializes the DB once via a FastAPI `lifespan` calling `init_db(settings.database_path)`. `GET /healthz` stays DB-independent; the `--network none` boot still holds (DB init is local file work only).
- [x] **Task 6 — Tests `tests/test_repositories.py` (AC: 1, 2, 3, 4)**
  - [x] `tmp_path` DB; asserts tables created, deferred tables absent, `journal_mode=wal`, `foreign_keys=1`, idempotent re-init.
  - [x] Round-trip through `get_submission` / `get_submission_by_ttb_id` / `list_label_images` (ordered) returning Pydantic models with the right `snake_case` values.
  - [x] Constraint tests: invalid `status`/`beverage_type` rejected; `position=11` rejected; `DECIDED` without disposition rejected; disposition on non-`DECIDED` rejected; valid `DECIDED`+disposition allowed; cascade delete of `label_images`. (Also isolated the `/healthz` tests' startup DB to `tmp_path` so the suite writes nothing into the repo.)

## Dev Notes

### Scope guardrails (read first)
- **Two tables only: `submissions` + `label_images`.** The deferral is explicit in both the epic note and project-context. Adding `ocr_results`/`llm_results`/`field_comparisons`/`checklist_items`/`audit_events`/`review_progress`/`submission_extra_fields` here is the "front-loading the schema" anti-pattern — reject it.
- **`db/` is the single data-access layer.** Raw SQL lives ONLY in `app/db/` (`schema.sql`, `connection.py`, `repositories.py`). No other module issues SQL — this is the data boundary the whole app depends on (AR-13, architecture "Data boundary").
- **Read-only typed boundary:** repositories return Pydantic v2 models validated at the read boundary (AR-13). This story adds the read layer; the pipeline's writers and the web layer's human-writes come later.

### Authoritative data model — copy faithfully, do not paraphrase
- `docs/database-schema.md` is the **authoritative schema** (shape, keys, constraints). `docs/data-dictionary.md` is the **authoritative per-field reference**. Transcribe `submissions` (§1.1) and `label_images` (§1.2) DDL as written, including:
  - The exact `TEXT + CHECK` enum vocabularies (UPPER_SNAKE): `beverage_type IN ('WINE','DISTILLED_SPIRITS','MALT_BEVERAGE')`; `status IN ('RECEIVED','PROCESSING','READY_FOR_REVIEW','IN_REVIEW','DECIDED')`; `disposition IN ('APPROVED','NEEDS_CORRECTION','REJECTED')`; `source_of_product IN ('DOMESTIC','IMPORTED')`; `application_type IN ('LABEL_APPROVAL','EXEMPTION','DISTINCTIVE_BOTTLE','RESUBMISSION')`; `image_role IN ('BRAND','BACK','NECK','STRIP','OTHER')` (note: **no `FRONT`** — brand artwork is `BRAND`).
  - The two cross-column CHECKs on `submissions` (DECIDED ⇔ `disposition` + `decided_at` both present; `correction_due_at` non-null only when `disposition = 'NEEDS_CORRECTION'`).
  - `idx_submissions_queue (status, beverage_type, submitted_at)` and the `trg_submissions_set_updated_at` AFTER UPDATE trigger (SQLite idiom; keep the `TODO(postgres)` note).
  - `label_images`: `UNIQUE(submission_id, position)`, `position CHECK BETWEEN 1 AND 10`, FK `ON DELETE CASCADE`.
- **Do NOT add `submission_extra_fields` / the `v_field_comparisons` view** — they depend on deferred tables.

### Connection PRAGMAs (the silent-failure trap)
- `PRAGMA foreign_keys = ON` is **per-connection** and OFF by default in SQLite — set it on *every* connection in `get_connection()`, or `ON DELETE CASCADE` and FK validity become silently inert (orphans possible). The AC-4 cascade test guards this.
- `PRAGMA journal_mode = WAL` persists on the file — set once in `init_db()`. WAL is required because the Epic-2 pipeline runs concurrent writers (OCR job + analysis job); single-writer rollback journal would throw `SQLITE_BUSY`.

### Tech / patterns (from Story 1.1 — established, reuse)
- Stack pins unchanged (`approved-tech-stack.md`): **`pydantic~=2.13`**, stdlib `sqlite3` (no ORM, no migration framework — plain SQL DDL). Python **3.13**, type hints required, snake_case everywhere, ruff line length 100.
- App factory pattern already in `app/main.py` (`create_app()`); config pattern in `app/config.py` (`Settings.from_env()`, absent keys never raise). Extend both, don't rewrite.
- Pydantic v2 idioms: `class Submission(BaseModel)` with `model_validate(dict(row))`. No `orm_mode`; this is plain dict validation.
- Tests live in top-level `tests/`, files `test_*.py`, run via the project `.venv` (`.venv/Scripts/python.exe -m pytest -q`) and inside the Docker image. `test_repositories.py` is named in the architecture's test list.

### Architecture compliance (must-follow)
- **snake_case across DB ↔ Python ↔ JSON** — no camelCase boundary. Column names = Pydantic field names = future JSON keys.
- **`engine_verdict` vs `disposition` stay separate enums** — this story only *stores* both columns; never add a function mapping one to the other (contract #4 is enforced later in `verdict.py`/`disposition.py`).
- **5s read contract:** repositories do simple pre-computed row reads; no heavy work. DB init at startup is a one-time local file op (allowed; not on the `GET` render path).
- **Firewall:** all DB work is `local` — no egress. The `--network none` boot from Story 1.1 must still pass (DB init touches only the local file).

### Project Structure Notes
- New files land in `app/db/` (already scaffolded with `__init__.py` in Story 1.1): `schema.sql`, `connection.py`, `repositories.py`. `app/config.py` and `app/main.py` are UPDATE.
- Default DB path `data/app.db` — add `data/` to `.gitignore`? `.gitignore` already ignores `*.local` and `.env*` but not `data/`. Add a `data/` ignore line (the DB file is generated, must not be committed). Confirm before committing.

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.2: Mock COLA Database schema & connection layer]
- [Source: docs/database-schema.md#1.1 submissions] / [#1.2 label_images] / [#3. Enumerations] / [#Connection setup (required)]
- [Source: docs/data-dictionary.md#1. Application fields] / [#2. Label image fields] / [#5. Engine / disposition fields]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries] (db/ boundary; repositories.py role)
- [Source: _bmad-output/project-context.md#Naming, Format & Data Conventions] (snake_case, TEXT+CHECK enums, create-only-what-you-need)
- AR-2 / AR-10 / AR-13 [Source: epics.md#Additional Requirements]

### Previous story intelligence (1.1)
- `.venv` exists with the pinned deps; run tests with `.venv/Scripts/python.exe -m pytest -q`, lint with `.venv/Scripts/ruff.exe check . --exclude .venv` and `ruff format --check`.
- `create_app()` lifespan is the place to hook startup init; `/healthz` must stay DB-independent (its test + the `--network none` boot are existing regressions — keep them green).
- Docker image `ttb-label-poc:1.1` builds clean; `schema.sql` must be COPY'd into the image — verify the Dockerfile already copies `app/` (it does: `COPY app ./app`), so `app/db/schema.sql` ships automatically.

## Dev Agent Record

### Agent Model Used

Amelia (BMad dev-story) — claude-opus-4-8[1m]

### Debug Log References

- Host `.venv` TDD loop: `pytest -q` → **18 passed** (16 new repository/schema tests + 2 healthz regressions); `ruff check` clean; `ruff format` applied to `test_repositories.py`, then all 18 files formatted.
- Isolated the `/healthz` tests' lifespan DB init to `tmp_path` (env `DATABASE_PATH`) so the suite writes nothing into the repo; confirmed no `data/` dir is created by a run.
- `docker build -t ttb-label-poc:1.2 .` → exit 0 (deps layer cached). In-container `pytest -q` → 18 passed.
- Offline schema proof: `docker run --network none -e DATABASE_PATH=/tmp/t.db … init_db` → `tables=['label_images','submissions']`, `journal_mode=wal`, `foreign_keys=1`. Confirms only the two in-scope tables are created.
- Regression — `docker run --network none -e LLM_ENABLED=false …`: uvicorn startup complete (lifespan `init_db` ran), internal `127.0.0.1:8000/healthz` → 200, container `running`. The new startup DB init preserves the zero-egress boot (NFR-2/AR-8).

### Completion Notes List

- Created `app/db/schema.sql` (submissions + label_images, transcribed from `database-schema.md §1.1/§1.2` including both cross-column CHECKs, the queue index, and the `updated_at` trigger), `app/db/connection.py` (per-connection `foreign_keys=ON`, `init_db` with WAL + idempotent `executescript`, a `connect()` context manager), and `app/db/repositories.py` (Pydantic v2 `Submission`/`LabelImage` read models + three read functions; raw SQL confined to `db/`).
- `app/config.py` UPDATE: added `database_path` (env `DATABASE_PATH`, default `data/app.db`). `app/main.py` UPDATE: FastAPI `lifespan` runs `init_db` once on startup; `/healthz` stays DB-independent.
- **Scope discipline:** only `submissions` + `label_images` created; a dedicated test asserts the deferred tables (`ocr_results`/`llm_results`/`field_comparisons`/`checklist_items`) are absent. `audit_events`/`review_progress`/`submission_extra_fields` left for the stories that first need them.
- All 4 ACs verified on host and in-container, including the WAL/FK PRAGMAs, the typed-read round-trip, every constraint (enum CHECKs, `position` bound, the DECIDED⇔disposition invariant), and FK cascade.
- `.gitignore` updated to ignore the generated `data/` DB + WAL/SHM sidecar files.
- **Cross-story note:** because 1.1 and 1.2 are both uncommitted, the `app/db/*` modules 1.1 listed as "empty placeholders" are now full implementations. Recommend committing 1.1 and 1.2 as separate commits to restore a clean boundary (flagged in the concurrent 1.1 code review). `database_path`/`app/db/` correctly belong to **this** story.

### File List

- `app/db/schema.sql` (new)
- `app/db/connection.py` (new)
- `app/db/repositories.py` (new)
- `app/config.py` (modified — added `database_path`)
- `app/main.py` (modified — lifespan `init_db`)
- `tests/test_repositories.py` (new)
- `tests/test_healthz.py` (modified — isolated startup DB to `tmp_path`)
- `.gitignore` (modified — ignore generated `data/` + `*.db*`)
- `_bmad-output/implementation-artifacts/1-2-mock-cola-db-schema-and-connection.md` (story tracking)

## Change Log

| Date | Change |
|------|--------|
| 2026-06-12 | Story 1.2 implemented — `submissions` + `label_images` schema, WAL/FK connection layer, Pydantic v2 typed read layer, startup init. 18 tests pass host + in-container; constraints + cascade + offline boot verified. Status → review. |
