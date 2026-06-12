---
baseline_commit: ec71fa057eb6efc54258e78a7cafa40cb67db6b4
---

# Story 2.1: Engine-agnostic OCR/LLM adapter contracts

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer and a procurement evaluator,
I want one centralized adapter shape for every OCR engine and every model, with engine-agnostic result storage,
so that adding an engine or model is a new adapter file with no schema change (the swap-and-compare procurement requirement).

## Acceptance Criteria

1. **AC1 — Centralized contract shapes (`app/contracts.py` is the single owner).**
   **Given** `app/contracts.py` as the single module owning the adapter shapes
   **When** any OCR engine runs **Then** it returns the identical `OcrResult` structure with exactly these fields: `engine_name, engine_version, text, word_boxes, confidence, latency_ms, ran_on_cpu, status`
   **And** every model adapter returns the identical `LlmResult` structure with exactly these fields: `model_name, model_id, model_full_id, provider, task, result_text, prompt_tokens, completion_tokens, total_tokens, latency_ms, requested_at, responded_at, status`
   **And** no other module re-implements either shape (they import it from `app/contracts.py`). *(AR-3 #1)*

2. **AC2 — Engine-agnostic, independent per-engine/per-model storage.**
   **Given** the `ocr_results` and `llm_results` tables (created by this story from `docs/database-schema.md` §1.3/§1.4)
   **When** two different OCR engines run on the same image (and two different models on the same submission)
   **Then** each engine/model gets its **own** row keyed by `submission_id` (+ `label_image_id` for OCR), with no merged-only storage — both rows are independently queryable by `engine_name` / `model_id`. *(AR-4, FR-11/FR-12 schema basis)*

3. **AC3 — Adding an engine is a new adapter file, no DDL change.**
   **Given** the `OcrEngine` / `ModelAdapter` protocols in `app/adapters/{ocr,llm}/base.py`
   **When** a hypothetical third OCR engine is added as a new adapter implementing `OcrEngine`
   **Then** it persists through the existing write path with **zero** changes to `schema.sql` or the write function — demonstrated by a stub-adapter test that runs two distinct stub engines through the same store path and asserts two independent rows. *(AR-4)*

## Tasks / Subtasks

- [x] **Task 1 — Author the centralized contract shapes in `app/contracts.py` (AC1)**
  - [x] Define `OcrResult` with exactly the 8 fields: `engine_name: str`, `engine_version: str | None`, `text: str | None`, `word_boxes: list[dict] | None`, `confidence: float | None`, `latency_ms: int | None`, `ran_on_cpu: bool`, `status: OcrStatus` where `OcrStatus = Literal["OK", "ERROR"]`.
  - [x] Define `LlmResult` with exactly the 13 fields: `model_name`, `model_id`, `model_full_id`, `provider`, `task`, `result_text`, `prompt_tokens: int | None`, `completion_tokens: int | None`, `total_tokens`, `latency_ms: int | None`, `requested_at: str | None`, `responded_at: str | None`, `status: LlmStatus` (`Literal["OK","ERROR"]`).
  - [x] Implement `total_tokens` as a **read-only derived property** = `prompt_tokens + completion_tokens`, returning `None` if either part is `None` — it is NEVER independently set (mirrors the DB generated column; see Dev Notes "total_tokens trap").
  - [x] Use frozen `@dataclass(slots=True)` for both shapes (pure in-memory contract, not an API-boundary model — see Dev Notes "dataclass vs Pydantic"). Keep the module pure: zero I/O, zero DB, zero adapter imports.
  - [x] RED→GREEN: `tests/test_contracts.py` asserts each shape's exact field set (e.g. via `dataclasses.fields`), the `Literal` status values, and the `total_tokens` derivation incl. the `None` cases.

- [x] **Task 2 — Create `ocr_results` and `llm_results` tables (AC2)**
  - [x] Append both `CREATE TABLE … IF NOT EXISTS` blocks (+ their indexes) to `app/db/schema.sql`, copied verbatim from `docs/database-schema.md` §1.3 / §1.4, with the same `TODO(postgres)` markers. Add `IF NOT EXISTS` to each `CREATE TABLE`/`CREATE INDEX` to match the file's idempotent style (the doc DDL omits it).
  - [x] Confirm FK targets already exist in `schema.sql` (`label_images`, `submissions`) — they do (Story 1.2). `init_db` is idempotent; no migration framework.
  - [x] Keep the `llm_results.total_tokens` column exactly as `GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED` — do not write it.
  - [x] RED→GREEN: a test creates a fresh DB via `init_db` and asserts both tables + their indexes exist (`sqlite_master`), and that inserting a row WITHOUT `total_tokens` yields the computed sum.

- [x] **Task 3 — Adapter protocols `app/adapters/{ocr,llm}/base.py` (AC3)**
  - [x] `app/adapters/ocr/base.py`: `OcrEngine` `typing.Protocol` (`@runtime_checkable`) with `name: str`, `version: str`, and `extract(self, image_path: str | Path, *, ran_on_cpu: bool = True) -> OcrResult`.
  - [x] `app/adapters/llm/base.py`: `ModelAdapter` `typing.Protocol` (`@runtime_checkable`) with model identity attributes and `run(self, task: str, prompt: str, *, image_path: str | Path | None = None) -> LlmResult`.
  - [x] Protocols import `OcrResult`/`LlmResult` from `app/contracts.py` only. NO concrete engine/provider import (`engine/`/`pipeline/` depend on protocols, never concretes — architecture Adapter boundary).

- [x] **Task 4 — Persistence write path mapping contract → columns (AC2, AC3)**
  - [x] Add `insert_ocr_result(conn, *, submission_id, label_image_id, result: OcrResult, error_text: str | None = None) -> int` and `insert_llm_result(conn, *, submission_id, result: LlmResult, label_image_id: int | None = None, is_benchmark_only: bool = False) -> int` to `app/db/repositories.py` (raw SQL stays inside `app/db/`).
  - [x] Map the contract→column name differences explicitly: `OcrResult.text → extracted_text`; `word_boxes` (Python list) → `json.dumps(...)` into the TEXT column (NULL when `None`).
  - [x] **Never** insert `llm_results.total_tokens` (generated). Insert `prompt_tokens`/`completion_tokens` only.
  - [x] RED→GREEN: round-trip test — insert an `OcrResult`, read the row back, assert `extracted_text` and JSON `word_boxes` survive; insert an `LlmResult` with prompt=10/completion=20, assert stored `total_tokens == 30`.

- [x] **Task 5 — Engine-agnosticism proof test (AC3)**
  - [x] In `tests/test_contracts.py` (or `tests/test_adapters.py`), define two trivial in-test stub engines (`StubEngineA`, `StubEngineB`) each satisfying `OcrEngine` and returning distinct `OcrResult`s.
  - [x] Run both through `insert_ocr_result` against one seeded submission+image; assert two independent `ocr_results` rows exist, queryable separately by `engine_name`, with NO schema change required to add the second engine.
  - [x] Assert both stubs pass `isinstance(stub, OcrEngine)` (runtime-checkable protocol), proving the "new adapter file, no DDL/caller change" contract.

- [x] **Task 6 — Validate & finalize**
  - [x] `ruff check` + `ruff format` (line length 100); full `pytest` green (no Epic-1 regressions).
  - [x] Update File List + Change Log + Completion Notes.

### Review Findings

_Code review 2026-06-12 (Blind Hunter + Edge Case Hunter + Acceptance Auditor). 3 patch, 3 defer, 6 dismissed. DDL verified verbatim vs `docs/database-schema.md` §1.3/§1.4; all ACs substantively met._

- [x] [Review][Patch] AC2 LLM-side independent-row query is unproven — only OCR has the two-engine test; add a test inserting two distinct `LlmResult`s on one submission and querying both back by `model_id` [tests/test_adapters.py] — FIXED: `test_two_models_store_independent_rows_queryable_by_model_id`
- [x] [Review][Patch] Generated `total_tokens` NULL-case asserted only on the in-memory property, never on the DB column — add a DB assertion that prompt=10/completion=NULL stores `total_tokens IS NULL` (closes the "property mirrors generated column, can't drift" claim at the DB level) [tests/test_adapters.py] — FIXED: `test_total_tokens_generated_is_null_when_one_part_missing`
- [x] [Review][Patch] `insert_*` transaction ownership undocumented — helpers correctly delegate commit to the caller (`connect()` commits on clean exit; `get_connection()` does not), but the docstrings don't say so and the round-trip tests read back inside the same transaction, so they don't prove post-close durability. Document the caller-owns-commit contract; optionally harden one round-trip test to reopen a fresh connection before reading back [app/db/repositories.py] — FIXED: transaction-ownership note added to the write-helpers block; `test_ocr_result_round_trips_with_name_mapping` now reads back through a fresh connection
- [x] [Review][Defer] `word_boxes` `json.dumps` raises `TypeError` on non-serializable cells (e.g. numpy scalars from a real PaddleOCR engine) — the OCR adapters (Story 2.4) must emit plain JSON-able types per the contract; revisit there [app/db/repositories.py] — deferred, downstream story
- [x] [Review][Defer] `llm_results.label_image_id ON DELETE SET NULL` transition is untested (cascade-via-submission masks it) [tests/test_adapters.py] — deferred, minor coverage
- [x] [Review][Defer] Partial-batch durability — an exception mid-unit-of-work skips `connect()`'s post-yield commit and rolls back earlier inserts; transaction granularity for the multi-engine write is an Epic-2 pipeline concern [app/db/connection.py] — deferred, downstream

**Dismissed as by-design / noise (6):** no runtime range-validation on the dataclasses (DB `CHECK` is the write-time source of truth, AR-13); `status` `Literal` vs DB `CHECK` drift (same — comment-maintained lockstep is the documented design); `runtime_checkable` `isinstance` ignoring signatures (the two-engine round-trip test exercises the real `extract()` call, proving behavior beyond name-presence); `status`/`error_text` not coupled (spec doesn't require it); `lastrowid` under a hypothetical future `WITHOUT ROWID` (latent, current schema is rowid); abbreviated `TODO(normalization)` comment in `schema.sql` (comment-only — the executable DDL is verbatim, `TODO(postgres)` markers preserved).

## Dev Notes

### Scope boundary (what 2.1 is and is NOT)
- **IS:** the contract shapes, the two storage tables, the adapter **protocols**, and the contract→DB write path + the stub-engine proof.
- **IS NOT:** real Tesseract/PaddleOCR adapters (Story 2.4), the scheduler/lifecycle (Story 2.2), preprocessing (2.3), or live LLM provider adapters (2.5). Do **not** add `pytesseract`/`paddleocr`/provider SDK imports here. No new runtime dependencies — stdlib + existing pinned stack only.

### total_tokens trap (critical — do not let it drift)
`llm_results.total_tokens` is a SQLite `GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED` column [Source: docs/database-schema.md#1.4]. The DB computes it; inserting it raises. The `LlmResult.total_tokens` contract field must therefore be a **derived read-only property** (`prompt + completion`, `None` if either is `None`), never an independently-assignable field — the in-memory shape and the stored value can then never disagree. The epic lists `total_tokens` among the 13 LlmResult fields, so it must be *present on the shape* (as a property), just not *settable*.

### Contract ↔ column name mapping (the one mismatch)
The contract field is `text`; the column is `extracted_text` [Source: docs/database-schema.md#1.3]. Every other OcrResult field maps 1:1 by name. `result_text` (LlmResult) maps 1:1. `word_boxes` is a Python `list[dict]` on the shape, stored as JSON TEXT (`json.dumps`) — Postgres TODO is JSONB. `error_text` (OCR) and `is_benchmark_only` (LLM) are **columns but not contract fields** — they are writer-supplied parameters, not part of the fixed adapter shape (project-context fixes OcrResult to 8 fields / LlmResult to 13). Keep them out of `contracts.py`.

### dataclass vs Pydantic (settled — don't re-litigate)
Use frozen `@dataclass(slots=True)`. project-context: "Pydantic v2 validates at the **API/read boundary only**." These adapter shapes are internal in-memory return values produced by the pipeline, not an API/read-boundary model, so a plain dataclass keeps them dependency-light and I/O-free. The DB `CHECK`/generated columns remain the write-time source of truth; `Literal["OK","ERROR"]` documents the status domain. (`app/db/repositories.py` Pydantic models stay where they belong — the read boundary.)

### Architecture / boundary rules this story must honor
- **Adapter boundary:** `engine/` and `pipeline/` depend on `adapters/*/base.py` **protocols**, never a concrete engine/provider — swap = new file, no schema/caller change [Source: architecture.md#Architectural-Boundaries, D5/D6]. That is exactly what AC3 proves.
- **Contract boundary:** `contracts.py` is imported, never duplicated [Source: architecture.md#Architectural-Boundaries].
- **Data boundary:** raw SQL only inside `app/db/` (this story adds write helpers to `repositories.py` and DDL to `schema.sql`) [Source: app/db/connection.py docstring; architecture.md].
- **No egress:** nothing in this story makes a network call; it must remain importable/runnable under `docker run --network none`.
- **No verdict/disposition logic** touched here.

### Source tree components to touch
- `app/contracts.py` (UPDATE — currently a placeholder docstring authored for this exact story; replace the body, keep `from __future__ import annotations`).
- `app/db/schema.sql` (UPDATE — append the two tables; mirror the existing `IF NOT EXISTS` idempotent style and `TODO(postgres)` comments).
- `app/db/repositories.py` (UPDATE — add the two `insert_*` write helpers; this is the first write code in the module, whose header says "Seeding/writes are Story 1.3+; this module is read-only" — update that note).
- `app/adapters/ocr/base.py`, `app/adapters/llm/base.py` (NEW — packages `app/adapters/ocr/` and `app/adapters/llm/` already exist with `__init__.py`).
- `tests/test_contracts.py` (NEW; optionally `tests/test_adapters.py`).

### Project Structure Notes
- Repo uses **`app/db/`** (not top-level `db/`) and **`app/adapters/`** — both already scaffolded from Epic 1. Matches the architecture tree (`app/` split by concern) [Source: architecture.md Project Structure]. The architecture tree shows these paths without the `app/` prefix in some lines; the realized repo nests them under `app/`. Use the **realized** paths.
- snake_case across DB ↔ Python ↔ JSON; enums `UPPER_SNAKE` as `TEXT + CHECK`; `_ms` timing / `_at` timestamps [Source: project-context.md Naming].

### Previous story intelligence (Story 1.2 patterns to reuse, not reinvent)
- `app/db/connection.py` already provides `get_connection`/`connect`/`init_db` with `PRAGMA foreign_keys = ON`, WAL, and a `busy_timeout` explicitly sized for "the Epic-2 pipeline's writers (OCR job + analysis job)". Use `connect(db_path)` / `get_connection` — do not open raw `sqlite3.connect`.
- `repositories.py` style: module-level `Literal` aliases mirroring CHECK vocabularies; `sqlite3.Row` → `dict(row)`; functions take `conn: sqlite3.Connection` as first arg. Follow it.
- Tests use top-level `tests/`, `test_*.py`, an in-memory or tmp_path SQLite DB seeded via `init_db`. See `tests/test_repositories.py` and `tests/test_seed.py` for the fixture pattern (build a DB, insert a submission + label_image, then exercise).
- ABI note: enums stored as `TEXT + CHECK`, `BOOLEAN` stored as SQLite int (`ran_on_cpu DEFAULT 1`).

### Testing standards
- pytest in top-level `tests/`, mirroring `app/`. ruff line length 100, type hints required [Source: project-context.md Testing & Tooling].
- This story's highest-value assertions: exact field sets (guards against an adapter silently widening the contract), independent multi-engine rows (AC2/AC3), and the `total_tokens` generated-column round-trip (guards the trap above).

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.1] — story statement + ACs.
- [Source: docs/database-schema.md#1.3] `ocr_results` DDL; [#1.4] `llm_results` DDL incl. generated `total_tokens`.
- [Source: _bmad-output/planning-artifacts/architecture.md#Centralized-Contracts] contract #1 exact field lists; [#Architectural-Boundaries] adapter/contract/data boundaries; [D5/D6] uniform adapter interface.
- [Source: _bmad-output/project-context.md] Four Centralized Contracts; firewall posture; naming/format conventions; anti-patterns (per-engine bespoke result dicts; merged-only storage).
- [Source: app/db/connection.py, app/db/repositories.py, app/contracts.py] existing patterns + placeholder to replace.

## Dev Agent Record

### Agent Model Used

Amelia (BMad dev-story) — Claude Opus 4.8 (1M context), `claude-opus-4-8[1m]`.

### Debug Log References

- Host test runs use the project venv: `./.venv/Scripts/python.exe -m pytest` (Python 3.14; Docker target remains 3.13-slim). Baseline before work: 95 passed. After: 111 passed (+16).
- Baseline commit captured in frontmatter: `ec71fa057eb6efc54258e78a7cafa40cb67db6b4`.

### Completion Notes List

- **AC1** — `app/contracts.py` now owns `OcrResult` (8 fields) and `LlmResult` (12 dataclass fields + `total_tokens` derived property = 13). Frozen `@dataclass(slots=True)`; pure in-memory, no I/O. `total_tokens` is a read-only property returning `prompt+completion` (or `None`), mirroring the DB generated column so the two can never drift.
- **AC2** — `ocr_results` + `llm_results` tables created in `schema.sql` (idempotent `IF NOT EXISTS`), per the authoritative §1.3/§1.4 DDL incl. the `total_tokens GENERATED … STORED` column. Per-engine/per-model rows stored independently (verified by the two-engines test).
- **AC3** — `OcrEngine` / `ModelAdapter` runtime-checkable Protocols in `app/adapters/{ocr,llm}/base.py`; proven by a stub engine satisfying the protocol via `isinstance`, and two distinct stub engines persisting independent rows through the unchanged write path (zero DDL/caller change).
- **Write path** — `insert_ocr_result` / `insert_llm_result` added to `repositories.py` (raw SQL stays in `app/db/`). Contract→column mapping isolated here: `OcrResult.text → extracted_text`; `word_boxes → json.dumps`; `total_tokens` never inserted (DB-generated, asserted = sum).
- **Regression** — moved the `test_deferred_tables_not_created` scope guard (Story 1.2) off `ocr_results`/`llm_results` (now created here) to the still-deferred `field_comparisons`/`checklist_items`/`review_progress`.
- **Firewall** — no new deps; all modules import and tests pass with zero network (offline import smoke verified). Tesseract/Paddle/provider SDK adapters remain out of scope (Stories 2.4/2.5).
- ruff (line length 100) clean across `app/` + `tests/`; full suite 111 passed.

### File List

- `app/contracts.py` (UPDATE — authored `OcrResult` / `LlmResult` shapes)
- `app/db/schema.sql` (UPDATE — added `ocr_results` + `llm_results` tables and indexes)
- `app/db/repositories.py` (UPDATE — added `insert_ocr_result` / `insert_llm_result`; docstring)
- `app/adapters/ocr/base.py` (NEW — `OcrEngine` protocol)
- `app/adapters/llm/base.py` (NEW — `ModelAdapter` protocol)
- `tests/test_contracts.py` (NEW — contract-shape tests, AC1)
- `tests/test_adapters.py` (NEW — tables/protocols/round-trip/agnosticism, AC2/AC3)
- `tests/test_repositories.py` (UPDATE — narrowed the deferred-tables scope guard)

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-12 | Story 2.1 drafted — engine-agnostic OCR/LLM adapter contracts (contracts.py shapes, ocr_results/llm_results tables, adapter protocols, contract→DB write path + stub-engine proof). Status → ready-for-dev. |
| 2026-06-12 | Story 2.1 implemented — contracts, two tables, adapter protocols, write helpers, 16 tests (AC1–AC3). Full suite 111 passed; ruff clean. Status → review. |
| 2026-06-12 | Code review (3-layer adversarial). 3 patches applied (AC2 LLM-side independent-rows test; DB-level `total_tokens` NULL-case assertion; documented caller-owns-commit + hardened OCR round-trip to a fresh connection), 3 deferred, 6 dismissed. Full suite 113 passed; ruff clean. Status → done. |
