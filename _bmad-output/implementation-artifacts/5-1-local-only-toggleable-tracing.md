---
baseline_commit: c46b61ec54e0d37b13c761dc45f2b5cadbd7daff
---

# Story 5.1: Local-only toggleable tracing

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an IT stakeholder,
I want instrumentation that captures model identification and timing locally and can be switched off,
so that benchmark data is collected without any telemetry leaving the host.

## Acceptance Criteria

1. **AC1 — `benchmark/tracing.py` provides a LangChain local-only tracer gated by `LANGCHAIN_TRACING_ENABLED`.**
   **Given** `app/benchmark/tracing.py` exposes a tracer keyed off `Settings.langchain_tracing_enabled` (env `LANGCHAIN_TRACING_ENABLED`, default off)
   **When** tracing is **enabled**
   **Then** model calls are instrumented in **local-only mode** — a LangChain callback/handler (or equivalent local sink) captures the call's telemetry on the host and **no LangSmith/cloud tracing endpoint is ever configured** (no `LANGCHAIN_ENDPOINT`/`LANGSMITH_API_KEY` set by this code; nothing is POSTed off-host). *(FR-24, NFR-2, architecture.md D6 / §Process-Patterns; outbound-calls-inventory.md §2 row "LangChain tracing" + TODO-3)*

2. **AC2 — When enabled, model name/ID/full version, timestamps, latency, and token counts are written to the local DB only.**
   **Given** tracing is enabled and a model call completes (an `LlmResult` is produced)
   **When** the call is traced
   **Then** the captured telemetry — `model_name`, `model_id`, `model_full_id`, `provider`, `requested_at`/`responded_at`, `latency_ms`, `prompt_tokens`/`completion_tokens` (+ DB-derived `total_tokens`) — lands in the **local SQLite DB only** (the existing `llm_results` columns; per data-dictionary §4 `langchain_trace_id` is **not a POC column**, so no new schema), with **zero egress**. The capture is identity + timing + tokens — never the prompt text, image bytes, or any secret. *(FR-24, AR-3 #1, database-schema.md §1.4, data-dictionary.md §4)*

3. **AC3 — When disabled, no tracing code path executes and the review workspace behaves identically.**
   **Given** `LANGCHAIN_TRACING_ENABLED=false` (the default) or absent
   **When** the pipeline runs and a model call is made (or the model layer is off entirely)
   **Then** **no tracing handler is constructed, registered, or invoked** — the model-call path and the review workspace behave **byte-for-byte identically** to the no-tracing baseline, and the OCR-only / zero-egress path is unaffected. Disabling tracing is the master off-switch (TODO-3). *(FR-24, NFR-2, AR-9)*

4. **AC4 — Tracing never egresses telemetry, even when enabled (the firewall invariant).**
   **Given** tracing is enabled
   **When** any model call is traced
   **Then** the tracer originates **no off-host connection** — it writes to the local DB / local sink only; the only off-host call sites in the app remain `app/adapters/llm/{openai,google,anthropic}.py` (`models-internal-endpoint`). A structural/grep guard proves `benchmark/tracing.py` opens no client and configures no cloud trace endpoint. *(NFR-2, AR-8, outbound-calls-inventory.md §3–4, project-context.md firewall posture)*

## Tasks / Subtasks

- [x] **Task 1 — `app/benchmark/tracing.py`: the toggleable local-only tracer (AC1, AC3, AC4)**
  - [x] Add a `tracing_enabled(settings: Settings | None = None) -> bool` predicate reading `Settings.langchain_tracing_enabled` (env `LANGCHAIN_TRACING_ENABLED`, default off — already in `config.py`). This is the single decision point; nothing below runs when it returns `False`.
  - [x] Add a **local-only** tracer. Preferred shape: a `local_tracer(settings) -> LocalCallbackHandler | None` factory that returns `None` when disabled (so callers can early-return and **construct nothing**), and otherwise a LangChain `BaseCallbackHandler` subclass that records each LLM call's identity + timing + tokens to a **local sink only**. Import LangChain **lazily inside the factory** (never at module top of anything on the web import path), so a disabled run never imports it. The handler **must not** set `LANGCHAIN_ENDPOINT`/`LANGSMITH_*` or post anywhere off-host. [Source: docs/ocr-llm-benchmarking-plan.md §LangChain — local tracing only; architecture.md D6]
  - [x] Provide a thin `trace_llm_call(result: LlmResult, *, settings=None) -> None` (or a context manager) used by the model-call path: **when disabled it is a no-op that imports nothing**; when enabled it records the trace locally. Keep capture to **identity + timing + tokens** — never the prompt/image/secret (project-context: secrets never logged). [Source: docs/data-dictionary.md §4; project-context.md secrets never logged]
  - [x] The telemetry sink is the **local DB**: the durable record is the existing `llm_results` row (model name/ID/full version, timestamps, latency, tokens) written by the pipeline via `insert_llm_result`. Tracing **adds the LangChain local-trace capture on top** without a new schema column (`langchain_trace_id` is NOT a POC column — data-dictionary §4). If a structured local trace log is emitted, it is a local-only sink, no egress. [Source: data-dictionary.md §4 lines re `langchain_trace_id`; database-schema.md §1.4]

- [x] **Task 2 — Wire the tracer into the model-call path, gated (AC2, AC3)**
  - [x] In the LLM pipeline stage (`app/pipeline/llm.py`) consult `benchmark.tracing` **only when enabled**: when the active adapter runs, the traced telemetry (the produced `LlmResult`) is recorded via `trace_llm_call`. When `tracing_enabled()` is `False`, the stage takes the **exact same code path it does today** (no import of `benchmark.tracing`'s LangChain bits, no handler) — AC3's "behaves identically". [Source: app/pipeline/llm.py `llm_stage`]
  - [x] Do **not** alter the OCR-only / `LLM_ENABLED=false` path: with the model layer off there is no model call to trace; tracing stays inert. The zero-egress smoke test (`--network none` + `LLM_ENABLED=false`) is unaffected. [Source: Story 2.5 AC2/AC5; NFR-2]
  - [x] Keep the read path untouched — tracing is a background-pipeline concern only; `GET /review/{id}` never touches it (5s contract). [Source: architecture.md Process Patterns; AR-5]

- [x] **Task 3 — Tests (`tests/test_tracing.py`) (all ACs)**
  - [x] **Offline by construction** — no LangSmith/cloud, no real provider call. AC3: `tracing_enabled()` is `False` by default and on garbage env; `local_tracer(disabled)` returns `None`; `trace_llm_call(disabled)` imports nothing and is a no-op (assert via a spy/monkeypatch that the LangChain symbol is never touched on the disabled path).
  - [x] AC1/AC2: with `LANGCHAIN_TRACING_ENABLED=true`, `local_tracer` returns a handler and `trace_llm_call` records the call's identity + timing + tokens; assert the captured fields equal the `LlmResult`'s (`model_name`/`model_id`/`model_full_id`/`provider`/`requested_at`/`responded_at`/`latency_ms`/`prompt_tokens`/`completion_tokens`) and that the durable record is the `llm_results` row (DB-derived `total_tokens`). No prompt/image/secret captured.
  - [x] AC3 (behaves identically): the `llm_stage` over a fake adapter produces the **same** `llm_results` row whether tracing is on or off (the stored extraction is unchanged by tracing); with tracing off, `benchmark.tracing`'s LangChain path is never entered.
  - [x] AC4 (egress guard): a structural test asserting `app/benchmark/tracing.py` constructs **no** off-host client and sets **no** `LANGCHAIN_ENDPOINT`/`LANGSMITH_*`/cloud-trace env — extend the `tests/test_llm_adapters.py` egress-origin guard's allowlist reasoning (off-host clients live ONLY under `app/adapters/llm/`). [Source: tests/test_llm_adapters.py egress-origin guard]

- [x] **Task 4 — Docs + finalize (AC1, AC4)**
  - [x] Flip **TODO-3** in `docs/outbound-calls-inventory.md` to RESOLVED (the full local-only tracing-to-DB harness now lives in `app/benchmark/tracing.py`; master off-switch `LANGCHAIN_TRACING_ENABLED` wired; no LangSmith/cloud endpoint; zero egress). Document the tracer in `docs/tools-used.md` (LangChain — local tracing only) as TODO-3 directs.
  - [x] `ruff check` + `ruff format` (line length 100); full `pytest` green (no regressions). Update File List + Change Log + Completion Notes; set Status → review and sprint-status story `5-1` → `review`.

## Dev Notes

### Scope boundary (what 5.1 is and is NOT)
- **IS:** the toggleable, **local-only** LangChain tracer in `app/benchmark/tracing.py` (master off-switch `LANGCHAIN_TRACING_ENABLED`), its gated wiring into the model-call path, the guarantee that enabled-tracing writes telemetry to the **local DB only** (zero egress), and the guarantee that disabled-tracing executes **no tracing code path** (identical behavior).
- **IS NOT:** accuracy scoring (Story 5.2 `benchmark/scoring.py`), speed/cost statistics & cost-per-1,000 (Story 5.3 `benchmark/cost.py`), the Benchmark Report screen (Story 5.4 `benchmark/report.py` + `GET /benchmark`), or any new `llm_results` columns. 5.1 instruments; later stories aggregate and render. [Source: epics.md Stories 5.2–5.4]

### The telemetry already lands in the DB — tracing is the *toggleable capture layer* on top
Story 2.5 already persists per-call `model_name`/`model_id`/`model_full_id`/`provider`/`requested_at`/`responded_at`/`latency_ms`/`prompt_tokens`/`completion_tokens` (DB-derived `total_tokens`) into `llm_results` via `insert_llm_result`. **5.1 does not duplicate that write.** It adds the LangChain **local-only tracing** harness that the benchmarking plan calls for (latency/timing + model identity captured by LangChain in local-only mode), gated by `LANGCHAIN_TRACING_ENABLED`, configuring **no** LangSmith/cloud endpoint. The durable, queryable record stays the `llm_results` row; the tracer's value is the toggleable, local-only instrumentation envelope around the call. [Source: docs/ocr-llm-benchmarking-plan.md §LangChain; app/pipeline/llm.py; app/db/repositories.py `insert_llm_result`]

### `langchain_trace_id` is NOT a POC column (no schema change)
data-dictionary §4 is explicit: *"`langchain_trace_id` is **not a POC column** — LangChain tracing is local-only and disable-able; add a column only if traces need to be persisted and joined."* So 5.1 adds **no** schema column and writes the trace telemetry through the existing `llm_results` columns (and, optionally, a local-only structured trace log). Do not add a `traces` table or a `langchain_trace_id` column. [Source: docs/data-dictionary.md §4]

### The firewall invariant (the spine of this story)
Tracing **never egresses telemetry** — local-only, no LangSmith/cloud endpoint, ever (outbound-calls-inventory §2 classifies LangChain tracing **`local`**, TODO-3). The only off-host call sites in the whole app remain `app/adapters/llm/{openai,google,anthropic}.py` (`models-internal-endpoint`). `benchmark/tracing.py` must construct no HTTP/SDK client and set no cloud-trace env var. When disabled, it imports nothing and runs nothing. [Source: outbound-calls-inventory.md §2–4; architecture.md External boundary; project-context.md firewall posture; NFR-2]

### "Behaves identically when off" (AC3 subtlety)
`LANGCHAIN_TRACING_ENABLED=false` (the default) must mean the model-call path is **unchanged** — the same imports, the same `llm_results` row, no handler constructed or registered. Prove it with a spy that fails if the LangChain tracing symbol is touched on the disabled path, and by asserting the produced `llm_results` row is identical with tracing on vs off. The 5s read-contract and the OCR-only zero-egress path are untouched either way. [Source: AR-9; Story 2.5 gating-prevents-the-socket pattern]

### Lazy import discipline (mirrors the adapters)
Import `langchain`'s tracing/callback symbols **lazily inside the factory**, never at module top of `tracing.py` (and never on the web import path), exactly as the provider SDKs are imported lazily inside the adapters. This keeps `import app.main` / `import app.pipeline.run` free of LangChain's tracing client and keeps the disabled path import-free. [Source: app/adapters/llm/openai.py `_client_lazy`; Story 2.5 Completion Notes import-smoke]

### Determinism / contract rules this story must honor
- Tracing captures **identity + timing + tokens only** — never the prompt text, image bytes, OCR text, or any secret/key (project-context: secrets never logged; VLM-only purity is unaffected — tracing reads the `LlmResult`, not the model input). [Source: project-context.md secrets never logged; VLM-only]
- **Pipeline-only writer** of `llm_results`; tracing does not write verdicts or dispositions; the read path never invokes tracing (5s contract). [Source: architecture.md boundaries, Process Patterns; AR-5]
- **Adapter boundary intact:** tracing wraps the *result* of a `ModelAdapter` call; it adds no provider-specific code and no new off-host origin. [Source: architecture.md D6]

### Source tree components to touch
- `app/benchmark/tracing.py` (NEW — `tracing_enabled`, `local_tracer`, `trace_llm_call`; LangChain lazy-imported, local-only).
- `app/pipeline/llm.py` (UPDATE — gated call to `trace_llm_call` after the adapter run; no behavior change when disabled).
- `tests/test_tracing.py` (NEW — toggle gating, captured-telemetry equality, behaves-identically, egress guard).
- `docs/outbound-calls-inventory.md` (UPDATE — flip TODO-3 to RESOLVED), `docs/tools-used.md` (UPDATE — document the local-only tracer).

### Previous story intelligence
- **2.5** built the provider adapters, `get_llm_adapter` gating, the `llm_stage`, and the per-call `llm_results` write (with DB-derived `total_tokens`) — and added the `langchain ~=1.3` dependency (local tracing only) while wiring **no** tracing (TODO-3 PARTIAL). 5.1 completes TODO-3. Reuse the lazy-import + gating discipline and the egress-origin guard. [Source: 2-5 story Tasks 5–6, Completion Notes; requirements.txt `langchain~=1.3`]
- `config.py` already reads `langchain_tracing_enabled` (env `LANGCHAIN_TRACING_ENABLED`, default off) — extend, don't duplicate. [Source: app/config.py]

### Testing standards
- Suite stays **offline by construction** — no LangSmith/cloud, no real provider call, fake `ModelAdapter`s / `LlmResult`s only. Highest-value tests: **disabled ⇒ no tracing path + identical `llm_results` row**, **enabled ⇒ identity+timing+tokens captured locally**, **egress-origin guard** (no off-host client / cloud-trace env in `benchmark/tracing.py`). Mirrors `tests/test_token_gate.py` / `tests/test_llm_adapters.py` egress rigor. [Source: project-context.md Testing; outbound-calls-inventory.md §4]

### Project Structure Notes
- Realized path nests under `app/` (`app/benchmark/tracing.py`), per the architecture tree (`app/benchmark/ … tracing.py — LangChain local-only, toggleable (FR-24)`). The story's bare `benchmark/tracing.py` resolves there. [Source: architecture.md Project Structure tree line ~356]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.1] — story statement + ACs (gated by `LANGCHAIN_TRACING_ENABLED`; local DB only; off ⇒ identical behavior).
- [Source: docs/ocr-llm-benchmarking-plan.md §"LangChain — local tracing only"] — LangChain captures latency/timing + model identity in local-only mode, toggleable, no telemetry egress; master off-switch `LANGCHAIN_TRACING_ENABLED`.
- [Source: docs/outbound-calls-inventory.md §2 row "LangChain tracing" (`local`) + §3–4 + TODO-3] — the local classification, the zero-egress posture, TODO-3 to resolve here.
- [Source: docs/data-dictionary.md §4] — `langchain_trace_id` is NOT a POC column; the LLM/benchmark stat fields that already capture identity/timing/tokens.
- [Source: docs/database-schema.md §1.4] — `llm_results` columns incl. generated `total_tokens`; `latency_ms` "(LangChain-traced, local-only)".
- [Source: _bmad-output/planning-artifacts/architecture.md D6 / External boundary / Process Patterns] — LangChain local-only tracing, only off-host calls in `adapters/llm/*`, 5s read contract.
- [Source: _bmad-output/project-context.md] — firewall/offline posture (tracing never off-host); secrets never logged; anti-patterns (a CDN/outbound asset reference; inference on a read path).
- [Source: app/config.py, app/pipeline/llm.py, app/adapters/llm/_common.py, app/db/repositories.py, app/contracts.py] — foundations to build on.

## Dev Agent Record

### Agent Model Used

Amelia (dev-story workflow) · claude-opus-4-8

### Debug Log References

- `bash scripts/ci.sh` (host venv, Python 3.14): Phase 1 format ✓ (87 files), Phase 2 lint ✓ (after removing two unused test imports `os`/`pytest`), Phase 3 mypy ✓ (no issues in 90 source files), Phase 4 pytest ✓ — **703 passed, 1 skipped**.
- Red→green: `tests/test_tracing.py` first failed at collection (`ImportError: cannot import name 'tracing' from 'app.benchmark'`); green after writing `app/benchmark/tracing.py` — 11 tracing tests pass.
- Import-path probe (`_probe.py`, deleted after use): `import app.main; import app.pipeline.run; import app.benchmark.tracing` ⇒ **zero** `langchain*` modules loaded — the web import path and disabled run stay LangChain-free.

### Completion Notes List

- **AC1** — `app/benchmark/tracing.py` exposes `tracing_enabled()` (single decision point off `Settings.langchain_tracing_enabled` / env `LANGCHAIN_TRACING_ENABLED`, default off) and a local-only `local_tracer()` / `trace_llm_call()`. The LangChain `BaseCallbackHandler` is **lazily imported inside `_build_handler`** (with a local logging-sink fallback if absent); the module sets **no** `LANGCHAIN_ENDPOINT`/`LANGSMITH_*` and opens no socket. A regex guard in the tests scans the source for any cloud-trace env write and fails on one.
- **AC2** — When enabled, `_telemetry(result)` captures **identity + timing + tokens only** (`model_name`/`model_id`/`model_full_id`/`provider`/`task`/`status`/`requested_at`/`responded_at`/`latency_ms`/`prompt_tokens`/`completion_tokens` + DB-derived `total_tokens`) — never prompt text, image bytes, OCR text, or secrets. The durable record stays the existing `llm_results` row; **no schema change** (`langchain_trace_id` is not a POC column).
- **AC3** — `app/pipeline/llm.py` gates on `tracing.tracing_enabled()` **before** calling `trace_llm_call`, so the disabled (default) path constructs/imports/invokes nothing. Pipeline tests assert the produced `llm_results` row is byte-identical with tracing on vs off, and that the disabled path never enters the LangChain code (spy raises if touched).
- **AC4** — The tracer originates no off-host connection: the only off-host call sites remain `app/adapters/llm/{openai,google,anthropic}.py`. The existing egress-origin guard in `tests/test_llm_adapters.py` already rglobs all of `app/` except `adapters/llm/`, so it structurally covers `app/benchmark/tracing.py`; a socket-monkeypatch test additionally proves the enabled tracer opens no socket.
- No regressions: full host CI green (703 passed, 1 skipped). OCR-only / `LLM_ENABLED=false` zero-egress path and the 5s read contract untouched (tracing is a background-pipeline concern only).

#### Code-review patches (CR, 2026-06-14)

Adversarial review (Blind Hunter / Edge Case Hunter / Acceptance Auditor) surfaced one **Critical** AC3 violation and four lower-severity items; all applied:

- **F1 (Critical — AC3 "behaves identically") — additive tracing must never abort the stage.** A raising `trace_llm_call` propagated out of `llm_stage` and **skipped the durable `insert_llm_result` write**, so an enabled run could lose the very `llm_results` row a disabled run would have persisted — the exact opposite of "behaves identically when off". Empirically confirmed via a `_probe.py` (`llm_stage` raised; `insert_llm_result called: False`). Fix: the gated trace call in `app/pipeline/llm.py` is now wrapped in `try/except Exception` — the fault is logged via `logger.exception` and swallowed, and the stage still persists the row. New regression test `test_llm_stage_persists_the_row_even_if_tracing_raises` in `tests/test_pipeline.py` pins it.
- **F3 (correctness) — resolve `Settings` once.** `llm_stage` now resolves `trace_settings = get_settings()` a single time and threads it through both `tracing_enabled(...)` and `trace_llm_call(..., settings=...)` — one env read, no window where the toggle could flip between the gate check and the trace.
- **F2 (robustness — AC1 degrade-never-crash) — widen the LangChain guard.** `_build_handler` in `app/benchmark/tracing.py` now wraps the **entire** LangChain-dependent path (import + `BaseCallbackHandler` subclass definition + instantiation) in one `try/except Exception`, degrading to the local `_LoggingTraceHandler` sink on any failure (not just a missing import). New test `test_build_handler_degrades_to_local_sink_when_langchain_unavailable` proves the fallback still records locally.
- **F4 (docs accuracy) — "local sink", not "local DB write".** `docs/tools-used.md` and `docs/outbound-calls-inventory.md` reworded: the tracer captures to a **local-only sink** (in-process record list + local structured log); the **durable, queryable record stays the `llm_results` row** the pipeline already writes (no separate trace DB write, no new schema).
- **F5 (test coverage) — strengthen the telemetry assertions.** `tests/test_tracing.py` gained positive `task`/`status` field assertions, an ERROR-`LlmResult` honesty test (`test_trace_of_an_error_result_is_recorded_honestly`), and a `handler=`-seam test (`test_trace_llm_call_records_into_a_passed_handler`).
- **Dismissed (no change):** LangChain `BaseCallbackHandler` subclass is intentional "cosmetic" inheritance per Dev Notes (local-only, no on_llm_* hooks needed); `total_tokens` derivation is by-design; the socket-monkeypatch test is defense-in-depth atop the canonical egress-origin guard; `_log_trace` `.get()` leniency is acceptable.
- **Out-of-scope mypy noise deferred:** `bash scripts/ci.sh` halted in Phase 3 on 12 mypy errors in **untracked** `targetsetup/scripts/{cola_capture,cola_backs}.py` — files NOT in this story's change set (`git diff baseline -- targetsetup/` empty; not in `git ls-files`). The story's changed source passes mypy cleanly (`mypy app/benchmark/tracing.py app/pipeline/llm.py` ⇒ Success). Recorded in `deferred-work.md`; validated via the canonical host pytest suite (green).
- Post-CR full host pytest: **707 passed, 1 skipped** (baseline 703 + 4 new CR tests).

### File List

- `app/benchmark/tracing.py` (NEW) — local-only toggleable tracer: `tracing_enabled`, `local_tracer`, `_build_handler` (lazy LangChain + `_LoggingTraceHandler` fallback, single widened `try/except` per CR F2), `_telemetry`, `_log_trace`, `trace_llm_call`.
- `app/pipeline/llm.py` (MODIFIED) — `from app.benchmark import tracing`; settings resolved once (`trace_settings`, CR F3), gated trace call wrapped in `try/except` so a tracer fault never aborts the durable `insert_llm_result` write (CR F1), after the adapter run.
- `tests/test_tracing.py` (NEW) — 14 tests across all ACs (toggle gating, captured-telemetry equality incl. `task`/`status`, ERROR-result honesty, no-prompt/secret, LangChain-unavailable degrade, `handler=` seam, no cloud-trace env, no socket, env-driven resolution).
- `tests/test_pipeline.py` (MODIFIED) — 3 integration tests: traces once when enabled; never traces and produces an identical row when disabled; persists the row even if tracing raises (CR F1 regression).
- `docs/outbound-calls-inventory.md` (MODIFIED) — TODO-3 PARTIAL → RESOLVED; §2 "LangChain tracing" row updated to local-only RESOLVED; wording clarified to local-only sink (CR F4).
- `docs/tools-used.md` (MODIFIED) — §9.1 references `app/benchmark/tracing.py`; §12 TODO-3 → RESOLVED; wording clarified to local-only sink (CR F4).

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-14 | Story 5.1 drafted — local-only toggleable LangChain tracing (`app/benchmark/tracing.py`): master off-switch `LANGCHAIN_TRACING_ENABLED`, enabled ⇒ model identity/timing/tokens captured to the local DB only (zero egress, no LangSmith/cloud endpoint), disabled ⇒ no tracing code path + identical review-workspace behavior; completes outbound-calls TODO-3. Status → ready-for-dev. |
| 2026-06-14 | Story 5.1 implemented (TDD red→green) — `app/benchmark/tracing.py` + gated wiring in `app/pipeline/llm.py`; `tests/test_tracing.py` (11) + 2 pipeline integration tests; docs TODO-3 flipped RESOLVED. Full host CI green (703 passed, 1 skipped). Status → review. |
| 2026-06-14 | Code review (CR) — adversarial 3-layer review. Applied F1 (Critical: wrap gated trace in try/except so a tracer fault never skips the durable `insert_llm_result` write — AC3 "behaves identically"), F2 (widen `_build_handler` LangChain guard to degrade on any failure), F3 (resolve `Settings` once per stage call), F4 (docs: local-only sink wording), F5 (tests: `task`/`status` asserts, ERROR-result honesty, LangChain-degrade, `handler=` seam + F1 pipeline regression). Out-of-scope untracked `targetsetup/` mypy errors deferred to `deferred-work.md`. Post-CR host pytest 707 passed, 1 skipped. Status → done. |
