---
baseline_commit: ec71fa057eb6efc54258e78a7cafa40cb67db6b4
---

# Story 2.5: Toggleable LLM extraction & OCR-only fallback

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an IT stakeholder enforcing the firewall,
I want LLM extraction to be optional and the pipeline to degrade cleanly to OCR-only,
so that a provable zero-egress configuration exists and the demo never blocks on a model call.

## Acceptance Criteria

1. **AC1 — Model adapters implement the `ModelAdapter` protocol → `LlmResult`; the only off-host calls.**
   **Given** `app/adapters/llm/{openai,google,anthropic}.py` (and optional `local_vlm.py`) each implementing the `ModelAdapter` protocol (`app/adapters/llm/base.py`) and returning the centralized `LlmResult` shape from `app/contracts.py`
   **When** a model runs an extraction **Then** it returns `model_name, model_id, model_full_id, provider, task, result_text, prompt_tokens, completion_tokens, total_tokens (derived), latency_ms, requested_at, responded_at, status` — and **these adapter files are the ONLY place in the codebase that opens an off-host connection** (classified `models-internal-endpoint`). *(FR-12, AR-3 #1, architecture.md External boundary)*

2. **AC2 — `LLM_ENABLED=false` ⇒ pipeline completes OCR-only, fully functional, zero-egress.**
   **Given** `LLM_ENABLED=false` (or absent provider keys)
   **When** the pipeline runs **Then** the LLM stage is **disabled entirely** — no adapter is constructed, no socket opened — and the submission still reaches `READY_FOR_REVIEW` on OCR-only results. Absent keys ⇒ model layer simply off, still functional. *(FR-12, AR-9, NFR-2)*

3. **AC3 — LLM-unreachable degrades to OCR-only and records the condition for the review notice.**
   **Given** `LLM_ENABLED=true` but a provider is unreachable/errors at processing time
   **When** the LLM stage runs **Then** affected extractions **fall back to OCR-only**, the pipeline still finalizes, and the degraded condition is **persisted** (an `ERROR`-status `llm_results` row + a clear marker) so Epic 4's review screen can surface its visible "LLM unavailable — showing OCR-only" notice. The read screen **never blocks** on a model call. *(FR-12, UX-DR-17, architecture.md API error handling)*

4. **AC4 — Per-call model identity, timing, and tokens persisted.**
   **Given** a successful LLM call
   **When** it completes **Then** an `llm_results` row records `model_name`/`model_id`/`model_full_id`, `provider`, `task`, `requested_at`/`responded_at`, `latency_ms`, `prompt_tokens`/`completion_tokens` (and the **generated** `total_tokens` — never written), and `result_text` — the procurement/cost basis for Epic 5's `$/1,000 verifications`. *(FR-12, database-schema.md §1.4)*

5. **AC5 — The zero-egress smoke test passes end-to-end.**
   **Given** `docker run --network none -e LLM_ENABLED=false`
   **When** the full pipeline sweeps the seeded corpus **Then** it completes end-to-end with **zero outbound connection attempts** and every submission reaches `READY_FOR_REVIEW` — the provable zero-egress OCR-only configuration. *(FR-12, AR-8, NFR-2, outbound-calls-inventory.md §4 smoke test)*

## Tasks / Subtasks

- [x] **Task 1 — `app/adapters/llm/` provider adapters (AC1, AC4)**
  - [x] Implement `OpenAiAdapter`, `GoogleAdapter`, `AnthropicAdapter` satisfying `ModelAdapter` (`base.py` from 2.1: model-identity attrs + `run(task, prompt, *, image_path=None) -> LlmResult`). Use the pinned provider SDKs (`openai ~=2.41`, `anthropic ~=0.79`, `google-genai ~=2.8`) **imported lazily inside the adapter** (never at module top of anything on the import path of the web app — so `--network none` + `LLM_ENABLED=false` never even imports a provider SDK if you prefer; at minimum, never *construct a client* unless enabled).
  - [x] Each adapter reads `LLM_BASE_URL` from config and passes it to the client (production points it at an **internal endpoint**; the POC at the cloud API — a config swap, no code change). Stamp `requested_at` before the call and `responded_at` after (UTC ISO-8601), compute `latency_ms`, read token counts from the provider response into `prompt_tokens`/`completion_tokens`. **Never set `total_tokens`** (derived property / generated column).
  - [x] Populate `model_name`/`model_id`/`model_full_id`/`provider` from config + the response; default task `extract_fields`. On any exception/timeout return `LlmResult(status='ERROR', provider=..., ...)` — never raise into the stage.
  - [x] **Secrets never logged.** Read API keys from env via `config.py`; do not log keys or full prompts containing them. [Source: project-context.md "Secrets/keys never logged"]

- [x] **Task 2 — Provider selection + gating in `app/config.py` (AC2)**
  - [x] Resolve the active adapter from `LLM_ENABLED` + `LLM_PROVIDER` (`openai`/`google`/`anthropic`/`local`). A `get_llm_adapter(settings) -> ModelAdapter | None` factory returns **`None`** when `LLM_ENABLED=false`, when no provider is set, or when the provider's key is absent — and the pipeline treats `None` as "model layer off." No exception on missing config (absent keys ⇒ off, still functional). [Source: AR-9; config.py existing `llm_enabled`/`llm_provider`/`llm_base_url`]
  - [x] Add any missing per-provider key settings (e.g. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`) + model-id settings to `Settings`/`.env.example`. Keep the `local`/`local_vlm` path (localhost, zero-egress) as an optional branch.

- [x] **Task 3 — LLM stage in the pipeline (AC2, AC3, AC4)**
  - [x] Add the LLM stage (e.g. `app/pipeline/llm.py` or a fn in `run.py`) registered into `run.STAGES` **after** the OCR stage (2.4) and **before** the (Epic 3) analysis/rollup. The stage: if `get_llm_adapter` is `None` → **skip entirely** (no construction, no socket); else run `extract_fields` (feeding the OCR text/image as the task input), persist the `llm_results` row via `insert_llm_result` (from 2.1), and stash the structured `result_text` for the analysis job.
  - [x] **Degrade path (AC3):** wrap the adapter call in `try/except`; on error/`status='ERROR'`, write the `ERROR` `llm_results` row (capturing `provider`, `latency_ms`, `requested_at`/`responded_at`, and the error in `result_text`/a note), then continue OCR-only. Persist a clear "LLM degraded" marker the review screen can read (the `ERROR` row is the signal; optionally an `audit_events` note). The submission still finalizes to `READY_FOR_REVIEW`.
  - [x] **Never block the read path:** all of this is background pre-compute; the `GET /review/{id}` route never calls the model layer (5s contract). [Source: architecture.md Process Patterns; FR-12]

- [x] **Task 4 — `is_benchmark_only` + multi-model capture hook (AC4, forward-compat)**
  - [x] Support writing **extra** `llm_results` rows flagged `is_benchmark_only=1` for comparison-only models (the row that feeds the displayed extraction is `is_benchmark_only=0`). 2.5 wires the single active-provider extraction; leave a clean seam for Epic 5 to run additional models for the benchmark matrix without schema change. Do not over-build the multi-model loop here. [Source: database-schema.md §1.4 `is_benchmark_only`; epics Epic 5]

- [x] **Task 5 — Dependencies + offline/egress posture (AC1, AC5)**
  - [x] Add `openai ~=2.41`, `anthropic ~=0.79`, `google-genai ~=2.8`, and `langchain ~=1.3` (local tracing only) to `requirements.txt` (pin to `approved-tech-stack.md`). Importing an SDK is fine; **opening a connection** must happen only inside an enabled adapter.
  - [x] LangChain tracing stays **local-only + toggleable** (`LANGCHAIN_TRACING_ENABLED`, default off; no LangSmith/cloud endpoint configured) — no telemetry egress. Full tracing implementation is Epic 5 (`benchmark/tracing.py`); 2.5 must not introduce any tracing egress. [Source: outbound-calls-inventory.md TODO-3; architecture.md D6]
  - [x] Verify the **only** off-host calls in the whole app originate in `app/adapters/llm/{openai,google,anthropic}.py` (grep for client construction / `httpx`/`requests`/SDK clients elsewhere = a finding).

- [x] **Task 6 — Tests (`tests/test_llm_adapters.py`, `tests/test_token_gate.py`-style egress guard) (all ACs)**
  - [x] **Offline by construction:** all tests use a **fake `ModelAdapter`** (returns a canned `LlmResult`) or a fake that raises — **no real provider call** ever in the suite. Assert `isinstance(fake, ModelAdapter)`.
  - [x] AC2: with `LLM_ENABLED=false`, `get_llm_adapter` returns `None`; the LLM stage is skipped; the submission still reaches `READY_FOR_REVIEW` with no `llm_results` row and **no client constructed** (assert via a spy/monkeypatch that the SDK client class is never instantiated).
  - [x] AC3: with an adapter that raises, the stage writes an `ERROR` `llm_results` row, sets the degraded marker, and the submission still finalizes — the review-notice signal is queryable.
  - [x] AC4: a successful fake adapter → `llm_results` row with model identity, `requested_at`/`responded_at`, `latency_ms`, tokens, and **`total_tokens` computed by the DB** (insert prompt=10/completion=20 → stored 30; never insert `total_tokens`). [Source: 2-1 story total_tokens trap]
  - [x] AC1/egress guard: a structural test asserting no off-host client is constructed when disabled, and (doc/grep-style) that LLM clients live only under `app/adapters/llm/`.
  - [x] AC5: document the `docker run --network none -e LLM_ENABLED=false` smoke test in the README run section and (if a CI hook exists) wire it; at minimum assert the OCR-only path reaches `READY_FOR_REVIEW` with the adapter factory returning `None`.

- [x] **Task 7 — Validate + finalize**
  - [x] `ruff check` + `ruff format` (line length 100); full `pytest` green (no regressions). Run the egress smoke test locally and record the result in Completion Notes.
  - [x] Update `.env.example`, the outbound-calls-inventory TODO statuses if appropriate, File List + Change Log + Completion Notes.

### Review Findings

_Code review 2026-06-13 (Amelia, 3-layer adversarial: Blind Hunter · Edge Case Hunter · Acceptance Auditor). All 5 ACs verified satisfied. The review surfaced a **spec deviation in the core behavior** (the model was fed OCR text instead of reading the label image), which was **reworked** the same day to pure VLM-only image extraction — see the 2026-06-13 rework Completion Note + Change Log. Status of each finding below._

- [x] [Review][Decision→RESOLVED] **Model was fed OCR text, not the label image** — verified against PRD FR-12 / FR-21-22, the domain-research VLM thesis, the benchmarking plan's `VLM-only` config, and the `image_path`/`llm_results.label_image_id` seams: the spec calls for the model to read the **image** independently (Diane confirmed: keep it pure, no OCR-assist anywhere in the POC). **Reworked:** adapters now send the label image (OpenAI/Anthropic base64 + Google `Part.from_bytes`), `llm_stage` reads the primary image and an OCR-free prompt, `get_submission_ocr_text` is now the Epic-3 deterministic engine's input only. The OCR+LLM hybrid is documented as a future consideration ([docs/tradeoffs-and-limitations.md](../../docs/tradeoffs-and-limitations.md) B10). [app/pipeline/llm.py, app/adapters/llm/*]
- [x] [Review][Patch→DONE] Sanitize SDK-exception text on the degrade path — `run_extraction` now truncates the captured message (`_MAX_ERROR_TEXT=500`) and logs the exception **type only** (no message/traceback body), so a prompt/key echoed in an SDK exception never reaches the log. [app/adapters/llm/_common.py] — test `test_run_extraction_truncates_an_overlong_error_message`
- [x] [Review][Patch→DONE] Egress-guard regex widened — now catches bare-import (`OpenAI(`), `Async*` clients, and `aiohttp`/`urllib`/`socket` in addition to the dotted SDK/`httpx`/`requests` forms, via a shared `_OFF_HOST_CLIENT` pattern; `*Adapter` wrappers correctly excluded. [tests/test_llm_adapters.py] — test `test_egress_guard_catches_bare_and_async_constructions`
- [x] [Review][Patch→DONE] Stage-level degrade row now stamps timing — `_run_adapter`'s fallback sets `requested_at`/`responded_at` so even a raising adapter yields an honest, timed ERROR row. [app/pipeline/llm.py] — asserted in `test_llm_stage_degrades_to_error_row_when_adapter_raises`
- [x] [Review][Patch→OBSOLETE] Empty-OCR-text paid call — moot after the rework (the stage no longer reads OCR text). Replaced by a **skip-when-no-image** guard so VLM-only never calls a provider without something to read. [app/pipeline/llm.py] — test `test_llm_stage_skips_when_no_label_image`
- [x] [Review][Defer→RESOLVED] Google `http_options` passed as a plain dict — fixed during the rework: now `types.HttpOptions(base_url=...)`. (Still build-host-verify against pinned `google-genai~=2.8`, since the SDK is absent in the offline venv.) [app/adapters/llm/google.py]
- [x] [Review][Defer] AC5 Docker `--network none` seeded-corpus sweep not literally executed — offline suite + egress guard proxy it; full container run carried forward to the build host (same discipline as 2.4). — deferred, build-host verification
- [x] [Review][Defer] Truncated response (`max_tokens=1024`) stored as `status="OK"` — no `finish_reason`/`stop_reason` check; partial JSON recorded as a clean extraction. Parsing/validation is Epic 3 scope; revisit there (raise the cap or mark truncation). [app/adapters/llm/openai.py] — deferred, Epic 3 scope

#### Re-review 2026-06-13 (post-rework, 3-layer)

_Verdict: VLM-only purity HELD on every path; all 5 ACs satisfied; all prior findings confirmed resolved. Two small new patches + one build-host defer._

- [x] [Review][Patch→DONE] Egress guard widened to bare-import stdlib offenders — `_OFF_HOST_CLIENT` now matches `ClientSession(` / `urlopen(` / `socket(` in both dotted and bare-import form; meta-test extended with the bare cases. [tests/test_llm_adapters.py]
- [x] [Review][Patch→DONE] Blank-filename skip — `llm_stage` now skips when the primary `filename` is empty/whitespace (not just when there are no images), so a blank path never triggers a doomed client construction. [app/pipeline/llm.py] — test `test_llm_stage_skips_when_primary_filename_is_blank`
- [x] [Review][Defer] Build-host SDK/model verification (offline venv can't import the provider SDKs) — confirm against the pinned SDKs: OpenAI `max_tokens` vs `max_completion_tokens` for newer/reasoning models (default `gpt-4o-mini` accepts `max_tokens`); default model ids resolve (`gpt-4o-mini` / `claude-opus-4-8` / `gemini-2.0-flash`); Google `types.HttpOptions(base_url=)` + `types.Part.from_bytes(data=, mime_type=)` keyword names on `google-genai~=2.8`. All degrade cleanly to ERROR rows if wrong and are config-swappable via `LLM_MODEL_ID`/`LLM_BASE_URL`. — deferred, build-host verification
- [x] [Review][Dismiss] `_run_adapter` fallback `LlmResult(None…)` cannot raise — every `LlmResult` field defaults to `None` (contracts.py); confirmed not a crash. Path-traversal `../` filename is pre-existing (same pattern in `preprocess.py`, already deferred under the 2.3 path-robustness item).

## Dev Notes

### Scope boundary (what 2.5 is and is NOT)
- **IS:** the provider model adapters on the `ModelAdapter` protocol, the config-gated LLM pipeline stage, the OCR-only fallback + degraded-condition persistence, per-call stats capture, and the zero-egress proof.
- **IS NOT:** the compliance engine's *use* of extracted fields (Epic 3 `field_comparisons`/`checklist_items`), the review-screen *rendering* of the "LLM unavailable" notice (Epic 4 surfaces the signal 2.5 persists), and the full benchmark/tracing harness (Epic 5 `benchmark/`). 2.5 produces and stores; downstream consumes. [Source: epics.md Epics 3–5]

### The firewall posture (read this — it's the spine of the story)
The **revised, canonical** posture (Diane, PRD 2026-06-11): the government hosts LLMs **inside** the firewall, so deployed LLM calls are acceptable — classified **`models-internal-endpoint`**, modeled in the POC by cloud-provider APIs, **swappable to internal endpoints by config (`LLM_BASE_URL`) with no code change**. The control that matters: **the local-first core (OCR/rules/DB/tracing) is fully sufficient alone**, the model layer is **additive and config-gated, never a hard dependency**, and `LLM_ENABLED=false` yields a **provable zero-egress** run (FR-12). The demo includes at least one LLM-off run. [Source: docs/outbound-calls-inventory.md §1–4; architecture.md D6/External boundary; PRD NFR-2 / addendum A2]

### Determinism cap (do not let the LLM over-reach)
This story does **extraction** (read fields off the label), not verdicts. Project-context determinism taxonomy: **an LLM opinion alone never yields FAIL** (capped at REVIEW), the **Government Warning check never calls an LLM**, and **no `verdict → disposition` mapping** exists. 2.5 must not write `engine_verdict` or any check verdict — it only writes `llm_results`. The hybrid class/type check that *uses* an LLM (capped at REVIEW) is **Epic 3 Story 3.6**, not here. [Source: project-context.md Determinism taxonomy; epics.md Story 3.6]

### `total_tokens` trap (inherited from 2.1)
`llm_results.total_tokens` is `GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED` — inserting it raises. `LlmResult.total_tokens` is a **read-only derived property**. Insert only `prompt_tokens`/`completion_tokens`; let the DB compute the sum. [Source: 2-1 story "total_tokens trap"; database-schema.md §1.4; app/contracts.py]

### Degraded-condition persistence (how Epic 4 gets its notice)
AC3's "recorded for the review screen's visible notice" = a **queryable signal**, not UI. Use the `ERROR`-status `llm_results` row (provider + latency + error in `result_text`) as the primary signal; optionally an `audit_events` note. Epic 4's `GET /review/{id}` reads "LLM was expected but every `llm_results` row for this submission is `ERROR` (or absent while `LLM_ENABLED=true`)" → render the "showing OCR-only" notice. Keep the signal honest and unambiguous. [Source: UX-DR-17 LLM-unavailable degrade; EXPERIENCE.md State Patterns; architecture.md error handling]

### Gating must prevent the socket, not just the result (AC2 subtlety)
`LLM_ENABLED=false` must mean **no client is ever constructed** — not "construct then discard." The egress proof depends on it: under `--network none`, constructing a provider client that eagerly connects would fail the smoke test. The factory returns `None` and the stage early-returns **before** any adapter import/instantiation. Test this with a spy that fails if the SDK client class is touched. [Source: outbound-calls-inventory.md §4 smoke test; AR-9]

### Architecture / boundary rules this story must honor
- **External boundary:** the **only** off-host calls originate in `adapters/llm/{openai,google,anthropic}.py`; everything else `none`/`local`. `LLM_ENABLED=false` disables the boundary entirely. [Source: architecture.md External boundary]
- **Pipeline-only writer** of `llm_results`; **data boundary** (SQL in `app/db/`, via `insert_llm_result` from 2.1); **5s contract** (model layer never on a request path). [Source: architecture.md boundaries, Process Patterns]
- **Adapter boundary:** the stage depends on the `ModelAdapter` protocol; adding a provider = a new adapter file, no stage/schema change. [Source: architecture.md D6/Adapter boundary]

### Source tree components to touch
- `app/adapters/llm/openai.py`, `app/adapters/llm/google.py`, `app/adapters/llm/anthropic.py` (NEW); optional `app/adapters/llm/local_vlm.py`. `base.py` protocol from 2.1.
- `app/pipeline/llm.py` (NEW) or LLM stage fn in `app/pipeline/run.py` (UPDATE — register after OCR).
- `app/config.py` (UPDATE — provider keys/model ids + `get_llm_adapter` factory).
- `requirements.txt` (UPDATE — openai/anthropic/google-genai/langchain, pinned).
- `.env.example` (UPDATE — provider keys, model ids).
- `docs/outbound-calls-inventory.md` (UPDATE — flip relevant TODO statuses once verified).
- `tests/test_llm_adapters.py` (NEW); `tests/test_pipeline.py` (UPDATE).

### Previous story intelligence
- **2.1** built `LlmResult`, the `ModelAdapter` protocol, `llm_results`, and `insert_llm_result` (never inserts `total_tokens`). Reuse; do not re-create the shape or write path. [Source: 2-1 story Tasks 1,3,4]
- **2.2** owns the stage seam + failure contract (the degrade path mirrors it); **2.4** produced the OCR text the LLM extraction consumes. Register the LLM stage after OCR. [Source: 2-2, 2-4 stories]
- `config.py` already reads `llm_enabled`/`llm_provider`/`llm_base_url`/`langchain_tracing_enabled` (Story 1.1/1.6) — extend, don't duplicate. [Source: app/config.py]

### Testing standards
- Suite stays **offline by construction** — fake `ModelAdapter`s only, never a real provider call; assert no client constructed when disabled. Highest-value: **`LLM_ENABLED=false` ⇒ no socket + OCR-only READY**, **unreachable ⇒ ERROR row + degraded marker + still finalizes**, **success ⇒ stats persisted with DB-computed `total_tokens`**, and the **egress-origin guard** (clients only under `adapters/llm/`). This mirrors `tests/test_token_gate.py`'s "no data leakage" rigor for the egress boundary. [Source: project-context.md Testing; outbound-calls-inventory.md §4]

### Project Structure Notes
- Realized paths nest under `app/` (`app/adapters/llm/…`, `app/pipeline/…`). [Source: 2-1/2-2 Project Structure Notes; architecture.md tree]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.5] — story statement + ACs (toggleable, degrade, stats, egress smoke test).
- [Source: docs/outbound-calls-inventory.md] the two-layer posture, the `models-internal-endpoint` classification, the `LLM_ENABLED=false` zero-egress smoke test (§4), TODO-3/TODO-7.
- [Source: _bmad-output/planning-artifacts/architecture.md D6] same adapter pattern for models, `models-internal-endpoint`, `LLM_ENABLED`/`LLM_BASE_URL` config-driven, LangChain local-only; [External/Adapter/Pipeline boundaries]; [Process Patterns] 5s contract.
- [Source: docs/database-schema.md §1.4] `llm_results` columns incl. generated `total_tokens` + `is_benchmark_only`; [§5] LLM rows job-written, may be absent.
- [Source: _bmad-output/project-context.md] firewall/offline posture; determinism taxonomy (LLM capped at REVIEW; Gov Warning never LLM); secrets never logged; anti-patterns (a CDN/outbound asset reference; OCR/LLM/inference on a read path).
- [Source: app/contracts.py, app/adapters/llm/base.py, app/db/repositories.py (2.1), app/config.py, app/pipeline/run.py (2.2/2.4)] foundations to build on.

## Dev Agent Record

### Agent Model Used

Amelia (dev-story workflow) · claude-opus-4-8[1m]

### Debug Log References

- `py -m ruff check app tests` → All checks passed (after 2 autofixes: UP017 `datetime.UTC`, I001 import sort).
- `py -m pytest -q` → **174 passed, 1 skipped** in ~7.5s (the 1 skip is the native-Tesseract smoke test; up from the 156-test 2.4 baseline — +18 new tests, zero regressions).
- Import smoke: `import app.main; import app.pipeline.run` → provider SDKs imported on web path: **NONE** (egress boundary holds at the import path).

### Completion Notes List

- **AC1 — adapters are the only off-host call site.** `OpenAiAdapter`/`AnthropicAdapter`/`GoogleAdapter` (+ optional `LocalVlmAdapter`) implement `ModelAdapter` and return the centralized `LlmResult`. Each provider SDK is imported **lazily inside `_client_lazy`** and the client is built only on the first real call. Shared timing/identity/error-wrapping lives in `app/adapters/llm/_common.py::run_extraction` so every `run()` is thin and **never raises** (degrades to an `ERROR` `LlmResult`). A structural test (`test_off_host_clients_live_only_under_adapters_llm`) enforces that no SDK/`httpx`/`requests` client is constructed anywhere outside `app/adapters/llm/`.
- **AC2 — `LLM_ENABLED=false` ⇒ OCR-only, nothing constructed.** `config.get_llm_adapter(settings)` returns `None` (and reaches `_construct_adapter` for **nothing**) when disabled, when no/unsupported provider, or when a cloud provider's key is absent. The `llm_stage` early-returns on `None` — no adapter, no client, no socket. Proven offline: the provider SDKs are **not even installed** in the host venv yet the whole suite passes; a spy asserts `_construct_adapter` is never called on the off paths.
- **AC3 — degrade to OCR-only + persisted signal.** The stage guards the adapter call; on raise **or** `status='ERROR'` it writes an `ERROR` `llm_results` row carrying `provider` + timing + the error in `result_text` — the queryable signal Epic 4's review screen reads for its "LLM unavailable — showing OCR-only" notice. The submission still finalizes to `READY_FOR_REVIEW`; the read path never calls the model layer.
- **AC4 — per-call stats.** Successful row records model identity (`model_name`/`model_id`/`model_full_id`), `provider`, `task=extract_fields`, `requested_at`/`responded_at`, `latency_ms`, `prompt_tokens`/`completion_tokens`, and `result_text`. `total_tokens` is **DB-generated** (insert 10/20 → stored 30; never inserted) — the 2.1 trap respected via `insert_llm_result`. Active extraction is `is_benchmark_only=0`; the write path already supports `=1` extra rows, the clean seam for Epic 5's benchmark matrix (Task 4 — not over-built).
- **AC5 — zero-egress proof.** README "Offline egress smoke test" documents `docker run --network none -e LLM_ENABLED=false` and now states the seeded corpus reaches `READY_FOR_REVIEW` on OCR-only with zero outbound attempts. Enforced locally by: the disabled-factory-constructs-nothing test, the egress-origin guard, and the import smoke (no provider SDK on the web path). **Carried forward (same discipline as 2.4):** a full Docker `--network none` corpus sweep with real Tesseract/Paddle should be run on the build host to validate end-to-end under genuine network isolation — the offline suite proves the gating + boundary; the container run proves the runtime.
- **Determinism cap honored:** 2.5 writes only `llm_results` — no `engine_verdict`, no verdict→disposition mapping, Government Warning never touches an LLM. The hybrid class/type check is Epic 3 Story 3.6.
- **`local` branch:** `LocalVlmAdapter` subclasses `OpenAiAdapter` against a localhost OpenAI-compatible server (classified `local`/zero-egress); the factory builds it without an API key.

- **REWORK 2026-06-13 — VLM-only image extraction (code-review spec-deviation fix).** The original implementation fed the **OCR text** to the model as the prompt; review against PRD FR-12/FR-21-22, the domain-research VLM thesis, and the benchmarking plan's `VLM-only` configuration established that the model must read the **label image** independently (no OCR help), and Diane confirmed the POC keeps this **pure** — OCR never feeds the model anywhere. Changes: (1) `_common.py` adds `load_image`/`load_image_b64`/`media_type_for` and bounds the degrade-path error text; (2) `OpenAiAdapter`/`AnthropicAdapter` send the image as base64 (Chat Completions vision / Messages image block), `GoogleAdapter` via `types.Part.from_bytes` and now `types.HttpOptions(base_url=...)`, `LocalVlmAdapter` inherits the OpenAI vision path (zero-egress VLM); (3) `llm_stage` reads the **primary label image** (`SOURCE_IMAGES_DIR / filename`) with an OCR-free instruction prompt, skips cleanly when there is no image, and stamps timing on the stage-level degrade row; (4) `get_submission_ocr_text` stays (now the **Epic-3 deterministic engine's** input — Field Match / Government Warning — never the model's). The OCR+LLM hybrid is recorded as a future consideration (tradeoffs B10; benchmarking-plan scope note). Three review patches (error-text truncation, widened egress guard, degrade-row timing) folded in; the empty-OCR-text patch is obsoleted by the skip-when-no-image guard. **174→ no LLM regressions; full suite 182 passed / 1 skipped; ruff clean.**

### File List

**New**
- `app/adapters/llm/_common.py` — shared timing/identity/error-wrapping (`run_extraction`, `utc_now_iso`); never imports a provider SDK.
- `app/adapters/llm/openai.py` — `OpenAiAdapter` (Chat Completions; lazy `openai`).
- `app/adapters/llm/anthropic.py` — `AnthropicAdapter` (Messages; lazy `anthropic`).
- `app/adapters/llm/google.py` — `GoogleAdapter` (Gemini; lazy `google.genai`).
- `app/adapters/llm/local_vlm.py` — `LocalVlmAdapter` (localhost OpenAI-compatible; zero-egress branch).
- `app/pipeline/llm.py` — config-gated `llm_stage` (skip / extract / degrade), registered last in `run.STAGES`.
- `tests/test_llm_adapters.py` — adapter protocol, `run_extraction` timing/never-raise, factory gating (egress proof), egress-origin guard.

**Modified**
- `app/config.py` — per-provider key + `llm_model_id` settings; `get_llm_adapter` factory + `_construct_adapter`/`_provider_api_key`/`_SUPPORTED_PROVIDERS`/`_DEFAULT_MODEL_ID`.
- `app/pipeline/run.py` — import + register `llm_stage` into `STAGES` (after `ocr_stage`).
- `app/db/repositories.py` — `get_submission_ocr_text` read helper (after the rework: the **Epic-3 deterministic engine's** OCR input — Field Match / Government Warning — NOT the model's; SQL stays in the data boundary).
- `tests/test_pipeline.py` — LLM stage tests: skip (AC2), degrade ERROR row (AC3), stats + DB total_tokens (AC4), full-pipeline OCR-only-reaches-READY + constructs-nothing (AC2/AC5), enabled-persists-and-finalizes (AC3/AC4).
- `requirements.txt` — `openai ~=2.41`, `anthropic ~=0.79`, `google-genai ~=2.8`, `langchain ~=1.3` (local tracing only).
- `.env.example` — `LLM_MODEL_ID`, `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/`GOOGLE_API_KEY`; expanded LLM/tracing notes.
- `README.md` — egress smoke test now covers the OCR-only corpus sweep; env-var list updated.
- `docs/outbound-calls-inventory.md` — TODO-3 (partial), TODO-4 (resolved), TODO-7 (partial: default cloud domains recorded); status/date.

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-12 | Story 2.5 drafted — toggleable LLM extraction (openai/google/anthropic ModelAdapters), config-gated LLM pipeline stage, OCR-only fallback + degraded-condition persistence for Epic 4's notice, per-call stats capture, and the provable zero-egress (`--network none` + `LLM_ENABLED=false`) configuration. Status → ready-for-dev. |
| 2026-06-13 | Story 2.5 implemented — provider ModelAdapters (lazy-SDK, never-raise via `_common.run_extraction`) + optional `local_vlm`; `get_llm_adapter` gating factory (constructs nothing when off); config-gated `llm_stage` (skip / extract / degrade-to-ERROR-row); per-call stats with DB-generated `total_tokens`; `is_benchmark_only=0` active row with a clean Epic-5 seam; deps + `.env.example` + README egress smoke test + outbound-calls TODO flips; egress-origin structural guard. ruff clean; 174 passed / 1 skipped; web import path SDK-free. Status → review. |
| 2026-06-13 | Story 2.5 **reworked** after code review — switched the model path to **pure VLM-only image extraction** (the model reads the label image, never OCR text; OCR is the Epic-3 deterministic engine's input only). Adapters send the image (OpenAI/Anthropic base64, Google `Part.from_bytes` + `HttpOptions`); `llm_stage` reads the primary image with an OCR-free prompt + skip-when-no-image guard. Folded in 3 review patches (bounded error text, widened egress guard, degrade-row timing); documented the OCR+LLM hybrid as a future consideration (tradeoffs B10 + benchmarking-plan scope note). ruff clean; **182 passed / 1 skipped**. Status → review (re-review). |
| 2026-06-13 | Story 2.5 **re-reviewed** (3-layer) post-rework — VLM-only purity HELD on every path, all 5 ACs satisfied, all prior findings confirmed resolved. Applied 2 small patches: egress guard widened to bare-import stdlib offenders (`ClientSession`/`urlopen`/`socket`), and a blank-filename skip in `llm_stage`. One build-host SDK/model-id verification deferred. ruff clean; **183 passed / 1 skipped**. Status → done. |
