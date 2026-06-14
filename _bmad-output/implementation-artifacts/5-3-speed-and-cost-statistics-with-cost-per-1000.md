---
baseline_commit: c360659e212998685413f614dcef15783c482b45
---

# Story 5.3: Speed & cost statistics with cost-per-1,000

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a procurement evaluator,
I want latency and cost captured per engine/model,
so that I get a defensible cost-per-1,000-Verifications figure.

## Acceptance Criteria

1. **AC1 — `benchmark/cost.py` computes per-engine/per-model latency statistics from the captured rows.**
   **Given** `app/benchmark/cost.py` and the seeded corpus's captured `ocr_results.latency_ms` (per `(engine_name, image_variant)`) and `llm_results.latency_ms` (per `model_id`)
   **When** the harness computes speed statistics
   **Then** it reports per-engine (broken out by `image_variant`) and per-model **latency** as mean / median / p95 over the captured `latency_ms` values (the deployed app's ~5s claim depends on the tail, not the mean — benchmarking-plan §6 "Latency distributions"), with NULL `latency_ms` rows excluded from the statistic and the sample count reported alongside. The keys mirror the accuracy scorer's: OCR keyed `(engine_name, image_variant)`, LLM keyed `model_id`, so speed and accuracy line up row-for-row in the Story 5.4 report. *(FR-22, NFR-1; benchmarking-plan §3 OCR/LLM latency, §6)*

2. **AC2 — A cost-per-1,000-Verifications figure is produced for every configuration, with the pricing basis stated explicitly.**
   **Given** per-call token inputs (`llm_results.prompt_tokens` / `completion_tokens`) and a per-model published price (input/output `$/1k` tokens) supplied as a labeled pricing table
   **When** cost is computed
   **Then** one **verification** = extracting the matchable fields for **one submission**, and for every configuration it yields `cost_per_1000 = ((mean_prompt_tokens/1000 × input_price) + (mean_completion_tokens/1000 × output_price)) × 1000` (benchmarking-plan §7.2), including the **local-only configuration** whose marginal **API** cost is **$0** (local OCR engines and `provider == local` models — benchmarking-plan §7.1). The pricing basis is **stated explicitly and labeled**: published API prices proxy the cost of an internally-hosted model, and each `cost_usd` carries the pricing-source label + as-of date (a `PricingBasis`/`ModelPrice` carrying `source` + `as_of`), so the report can show the caveat (NFR-5; benchmarking-plan §7.3, data-dictionary §4 "pricing source still open"). `cost_usd` is **computed at analysis time, never persisted** (no schema change — data-dictionary §4, benchmarking-plan §3). Money is **`Decimal`/string, never float** (project-context: `cost_usd` as decimal/string — never float math on currency). A model with **no supplied price** yields `cost_usd = None` (honest "not priced"), never a fabricated zero. *(FR-22, NFR-5; benchmarking-plan §7)*

3. **AC3 — CPU-only-mode figures are captured.**
   **Given** `ocr_results.ran_on_cpu` (govt infra has no guaranteed GPU — the CPU numbers are the load-bearing ones)
   **When** speed statistics are computed
   **Then** each OCR engine row carries a **CPU-only flag** derived from its captured `ran_on_cpu` (the per-engine×variant `ran_on_cpu`, surfaced so Story 5.4 renders the icon+word+color CPU-only flag), so an evaluator reads the latency figure against whether it was a CPU-only run. *(FR-22, NFR-1; benchmarking-plan §2.1, §3 "CPU/GPU mode", §6)*

4. **AC4 — The figures are reproducible across the seeded corpus.**
   **Given** the same seeded corpus and the same `ocr_results` / `llm_results` rows
   **When** the harness is re-run
   **Then** it produces **identical** figures — deterministic: no wall-clock, no RNG, no dict/set-ordering dependence (sorted/stable iteration; pure functions over the rows; percentiles by a fixed, documented method; `Decimal` money rounded by a fixed quantize). A test computes the corpus stats twice and asserts byte-equal (`asdict`) output. *(FR-22 implied "defensible/reproducible"; mirrors Story 5.2 AC4)*

5. **AC5 — Pure local analysis, zero egress, read-only over the DB.**
   **Given** cost/speed statistics are a local analysis step
   **When** it runs
   **Then** it performs **DB reads only** (SELECT-only repository helpers over `ocr_results` / `llm_results` / `submissions`) — it opens **no** off-host connection (the only off-host call sites remain `app/adapters/llm/{openai,google,anthropic}.py`), constructs no provider client, makes no model call (VLM-only purity untouched — it reads captured outputs, never feeds a model), writes nothing, and is **not** on any request/render path (5s contract — AR-5; cost is a benchmark/report concern, consumed by Story 5.4, never by `GET /review/{id}`). *(NFR-2, AR-5, AR-8; project-context firewall posture)*

## Tasks / Subtasks

- [x] **Task 1 — Per-engine / per-model stat read helpers (`app/db/repositories.py`) (AC1, AC2, AC3)**
  - [x]Add SELECT-only readers (raw SQL stays in `app/db/`): `list_ocr_latency_for_cost(conn) -> list[OcrCostRow]` returning `(engine_name, image_variant, latency_ms, ran_on_cpu)` for `status = 'OK'` rows across the corpus, sorted by `(engine_name, image_variant, id)`; `list_llm_cost_rows(conn) -> list[LlmCostRow]` returning `(model_id, model_name, provider, latency_ms, prompt_tokens, completion_tokens)` for `status = 'OK' AND task = 'extract_fields'` rows, sorted by `(model_id, id)`. These surface the per-engine/per-model raw timing+token columns the cost/speed roll-up needs (AR-4 — storage is already separate). Read-only: no writes. [Source: app/db/repositories.py §"benchmark scoring read helpers"; database-schema.md §1.3 `ocr_results`, §1.4 `llm_results`]
  - [x]Define `OcrCostRow` / `LlmCostRow` as Pydantic `BaseModel`s alongside `OcrScoringRow` / `LlmScoringRow` (mirror that section's style; `ran_on_cpu` is a `bool | None`, tokens/latency `int | None`). [Source: app/db/repositories.py `OcrScoringRow`/`LlmScoringRow`]

- [x] **Task 2 — Latency statistics (`app/benchmark/cost.py`) (AC1, AC4)**
  - [x]`latency_stats(values: Sequence[int | None]) -> LatencyStats` — drop `None`s, then compute `count`, `mean`, `median`, `p95` over the kept ms values. Use a **fixed, documented percentile method** (e.g. `statistics.quantiles`/a nearest-rank index that is deterministic) so re-runs are byte-identical (AC4). Empty sample ⇒ all stats `None`, `count = 0` (honest, not zero). `mean`/`median`/`p95` as plain floats (ms; not currency). [Source: benchmarking-plan §6 "Latency distributions … the tail, not the mean"]
  - [x]Frozen `LatencyStats` dataclass (`count`, `mean_ms`, `median_ms`, `p95_ms`). [Source: Story 5.2 frozen-dataclass result pattern]

- [x] **Task 3 — Pricing basis + cost rule (`app/benchmark/cost.py`) (AC2)**
  - [x]`ModelPrice` (frozen): `input_price_per_1k: Decimal`, `output_price_per_1k: Decimal`, `source: str`, `as_of: str` (the labeled pricing basis — NFR-5). A `PricingTable = dict[str, ModelPrice]` keyed by `model_id`; local engines/`provider == local` are **$0 API** by definition (no entry needed ⇒ treated as the $0 floor, labeled "local — $0 marginal API cost"). The default pricing table is **TODO-priced** (empty / placeholder) — real per-model prices + as-of dates drop in later (benchmarking-plan §7.3 "numbers PENDING real runs"); the code path and labeling must be correct now. [Source: benchmarking-plan §7.2, §7.3; data-dictionary §4 pricing-source TODO]
  - [x]`cost_per_verification(mean_prompt_tokens, mean_completion_tokens, price) -> Decimal | None` and `cost_per_1000(...) -> Decimal | None` — **`Decimal` arithmetic only** (never float on currency), quantized to a fixed precision (e.g. `Decimal("0.000001")`) so it is reproducible. `price is None` ⇒ `None` (honest "not priced", never a fabricated 0). The **local** path is an explicit `Decimal("0")` API cost labeled local. [Source: project-context "cost_usd as decimal/string — never float math on currency"; benchmarking-plan §7.1, §7.2]

- [x] **Task 4 — Corpus roll-up (`app/benchmark/cost.py`) (AC1–AC5)**
  - [x]`cost_corpus(conn, *, pricing=None) -> CostReport` — read the OCR cost rows and LLM cost rows ONCE (the new readers), group OCR by `(engine_name, image_variant)` and LLM by `model_id` in **sorted, stable order**, and for each: `latency_stats` over its latency samples; for OCR also the **CPU-only flag** (AC3 — e.g. `ran_on_cpu` is True for all kept rows / the captured value); for LLM also `mean_prompt_tokens` / `mean_completion_tokens` and the **cost-per-1,000** via the pricing table (local ⇒ $0, unpriced ⇒ None). Return frozen `EngineCost` (keyed `(engine_name, image_variant)`: latency + cpu_only) and `ModelCost` (keyed `model_id`: latency + mean tokens + `cost_per_1000` + `cost_basis`), plus a `verification_count` (distinct submissions scored). Pure functions, no wall-clock/RNG, `Decimal` money (AC4). [Source: benchmarking-plan §6 per-engine/per-model tables, §7; Story 5.2 `score_corpus` shape]
  - [x]Keep the module **read-only** — it computes and returns a typed object Story 5.4 renders; it writes **no** `cost_usd` column / any DB row (AR-13; cost is derived/not-persisted — data-dictionary §4). [Source: AR-13; data-dictionary §4; benchmarking-plan §3]

- [x] **Task 5 — Tests (`tests/test_cost.py`) (all ACs)**
  - [x]**Offline by construction** — a temp SQLite seeded with a tiny corpus + hand-written `ocr_results` / `llm_results` rows (latency, tokens, `ran_on_cpu`); no provider call, no network. Mirror `tests/test_scoring.py`'s fixtures/helpers.
  - [x]AC1: `latency_stats` over a known sample returns the expected mean/median/p95 and count; NULL latency rows excluded; OCR variants keyed `(engine, variant)` produce separate stats.
  - [x]AC2: cost-per-1,000 from known mean tokens × a known `ModelPrice` equals the hand-computed `Decimal`; a **local** model ⇒ `Decimal("0")` labeled local; an **unpriced** model ⇒ `cost_per_1000 is None` (not 0); money is `Decimal`, never float; the `cost_basis` carries the `source` + `as_of` label.
  - [x]AC3: an OCR engine row with `ran_on_cpu = True` surfaces `cpu_only = True`; a GPU (`ran_on_cpu = False`) row surfaces `cpu_only = False`.
  - [x]AC4 (reproducible): `cost_corpus` run twice over the same DB yields byte-identical `asdict` output (incl. `Decimal` money).
  - [x]AC5 (egress/read-only guard): reuse the `_OFF_HOST_CLIENT` regex + the no-write-SQL scan from `tests/test_scoring.py` against `app/benchmark/cost.py` (no off-host client constructed; only SELECTs in the module source).

- [x] **Task 6 — Finalize (AC1, AC5)**
  - [x]`ruff check` + `ruff format` (line length 100); type hints throughout; full `pytest` green (no regressions). Update File List + Change Log + Completion Notes; set Status → review and sprint-status story `5-3` → `review`.
  - [x]Do NOT touch the report screen (Story 5.4 `GET /benchmark`) — cost only produces the speed/cost object it consumes; do NOT re-touch the accuracy scorer (Story 5.2). [Source: epics.md Stories 5.2, 5.4]

## Dev Notes

### Scope boundary (what 5.3 IS and is NOT)
- **IS:** `app/benchmark/cost.py` — the pure, reproducible, read-only **speed + cost** harness: per-engine (×image variant) and per-model **latency** mean/median/p95, the **CPU-only flag** per OCR engine, and the **cost-per-1,000-Verifications** figure for every configuration (local = $0 API floor; provider models via a labeled pricing table; unpriced ⇒ None), with the pricing basis stated explicitly. Plus the two SELECT-only stat readers.
- **IS NOT:** accuracy scoring (Story 5.2 `benchmark/scoring.py` — already done), the Benchmark Report screen + `GET /benchmark` (Story 5.4), any new schema column / persisted `cost_usd`, the LLM-as-fallback recovery study (benchmarking-plan §8 — out of POC scope), or any change to the deterministic compliance engine. 5.3 **measures speed+cost**; 5.4 **renders**. [Source: epics.md Stories 5.2–5.4; benchmarking-plan §8 "OCR+LLM fallback out of POC scope"]

### Cost is DERIVED, never stored (no schema change)
`cost_usd` is **computed at analysis time, not a stored column** (data-dictionary §4: "`cost_usd` (tokens × price) is **computed at analysis time**, not a stored column"; benchmarking-plan §3 row "Estimated cost"). So `cost.py` computes and returns it — it does **not** ALTER `llm_results` or write any row. No schema work in this story. [Source: docs/data-dictionary.md §4; docs/ocr-llm-benchmarking-plan.md §3, §7]

### Money is Decimal/string — never float (project-context invariant)
project-context: "`cost_usd` as decimal/string — never float math on currency." All cost arithmetic uses `decimal.Decimal` with a fixed quantize, so the figures are exact and reproducible. Token counts and latency are integers; latency stats (mean/median/p95) are plain floats in **ms** (not currency, so float is fine there). [Source: _bmad-output/project-context.md Naming/Format; database-schema.md §1.4]

### The pricing basis must be LABELED (NFR-5 honesty)
benchmarking-plan §7.3 + §0: published provider API prices **proxy** the cost of an internally-hosted (`models-internal-endpoint`) model — they are a stand-in, not the actual internal cost, and **prices change**. So every priced figure must carry its **pricing source + as-of date** (`ModelPrice.source` / `.as_of`), and the local path is labeled "$0 marginal API cost." This is the NFR-5 "claim only what is demonstrated; limitations beside capabilities" rule applied to the cost table. The default table is intentionally **TODO-priced** (real numbers drop in after real runs — benchmarking-plan §7.3 "numbers PENDING"); the *mechanism* and the *labels* are what this story lands. [Source: docs/ocr-llm-benchmarking-plan.md §0 firewall note, §7.3; NFR-5; data-dictionary §4 TODO "pricing source still open"]

### One verification = one submission's matchable-field extraction
benchmarking-plan §7: "One **verification** = extracting the matchable fields for **one submission** (its full label-image set)." So per-call mean tokens roll up to a per-submission verification cost, ×1000 for the per-1,000 figure. The `verification_count` is the count of distinct submissions in the corpus the stats were computed over. [Source: docs/ocr-llm-benchmarking-plan.md §7]

### CPU numbers are the load-bearing ones (AC3)
benchmarking-plan §2.1/§3: government infra has **no guaranteed GPU**, so `ran_on_cpu` is captured and the CPU-only latency is the number that matters. Surface the per-OCR-engine CPU-only flag so Story 5.4 renders it as icon+word+color (UX-DR-5 / the benchmark mockup's "CPU-only flag"). [Source: docs/ocr-llm-benchmarking-plan.md §2.1, §3, §6; UX-DR-5]

### Latency: report the tail, not just the mean (AC1)
benchmarking-plan §6 "Latency distributions: percentiles (p50/p95/p99) per engine/model, since the deployed app's ~5s interaction-latency claim depends on the *tail*, not the mean." This story reports **mean / median (p50) / p95** as the procurement-relevant trio (p99 needs a larger sample than the seeded corpus carries — mean/median/p95 is the defensible set for ~30–50 fixtures). Pick a single, documented percentile method and keep it fixed for reproducibility (AC4). [Source: docs/ocr-llm-benchmarking-plan.md §6; NFR-1 ~5s tail]

### VLM-only purity is unaffected (cost reads outputs, never feeds a model)
Cost/speed is a pure read/compute step over already-captured `ocr_results` / `llm_results` rows — it makes **no** model call, so the "OCR text never feeds a model" invariant and the honest OCR-vs-model head-to-head are untouched. [Source: _bmad-output/project-context.md VLM-only]

### Firewall / read-only / 5s-contract posture (AC5)
Cost opens **no** socket and constructs **no** provider client — the only off-host call sites in the app remain `app/adapters/llm/{openai,google,anthropic}.py`. It is DB-read-only (SELECTs over `ocr_results` / `llm_results` / `submissions`), writes nothing, and is **never** invoked on a request/render path (AR-5; it is consumed by the Story-5.4 report, computed ahead of render or as a benchmark step). Mirror the egress-origin + no-write-SQL guards from `tests/test_scoring.py` / `tests/test_llm_adapters.py`. [Source: NFR-2, AR-5, AR-8; tests/test_scoring.py AC6 guard]

### Source tree components to touch
- `app/benchmark/cost.py` (NEW — `LatencyStats`, `latency_stats`, `ModelPrice`, `PricingTable`, `cost_per_verification`, `cost_per_1000`, `EngineCost`, `ModelCost`, `CostReport`, `cost_corpus`; `Decimal` money; read-only).
- `app/db/repositories.py` (UPDATE — add `OcrCostRow` / `LlmCostRow` models + `list_ocr_latency_for_cost` / `list_llm_cost_rows` SELECT-only readers; raw SQL stays in `app/db/`).
- `tests/test_cost.py` (NEW — all-AC coverage incl. reproducibility, CPU flag, Decimal money, and the egress/read-only guard).

### Previous story intelligence
- **5.1** created `app/benchmark/` (`tracing.py`) — the local-only, zero-egress, lazy-import benchmark conventions + the egress-origin guard. [Source: app/benchmark/tracing.py; 5-1 story]
- **5.2** (`scoring.py`, **done**) is the sibling template: SELECT-only `list_*_for_scoring` readers, frozen result dataclasses keyed `(engine_name, image_variant)` (OCR) and `model_id` (LLM), stable sorted iteration for reproducibility (AC4), the `_OFF_HOST_CLIENT` + no-write-SQL structural guards. **Reuse this exact shape** so speed/cost and accuracy line up row-for-row for Story 5.4. [Source: app/benchmark/scoring.py; tests/test_scoring.py; 5-2 story]
- **2.5** persists the `llm_results` timing/token columns (`prompt_tokens`/`completion_tokens`/`latency_ms`/`requested_at`/`responded_at`); **2.4** persists `ocr_results.latency_ms` + `ran_on_cpu` + `image_variant`. These are exactly the columns the cost/speed roll-up reads. [Source: database-schema.md §1.3/§1.4; 2-4 / 2-5 stories]

### Testing standards
- Suite stays **offline by construction** — temp/in-memory SQLite, hand-seeded rows, no provider/network (`docker run --network none` safe). Highest-value tests: the **cost-per-1,000 Decimal** computation (priced / local-$0 / unpriced-None), the **latency mean/median/p95** sample, the **CPU-only flag**, **reproducibility** (twice ⇒ identical), and the **egress/read-only guard**. Mirror `tests/test_scoring.py` rigor. [Source: project-context.md Testing; benchmarking-plan §7]

### Project Structure Notes
- Realized path nests under `app/` (`app/benchmark/cost.py`) per the architecture tree, alongside `tracing.py` + `scoring.py`. The story's bare `benchmark/cost.py` resolves there. [Source: architecture.md Project Structure; 5-2 Project Structure Notes]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.3] — story statement + ACs (latency + cost per engine/model; cost-per-1,000 for every configuration incl. local-$0; pricing basis stated explicitly; CPU-only figures).
- [Source: docs/ocr-llm-benchmarking-plan.md §7 Cost analysis framework] — the authoritative method: §7.1 local OCR ≈ $0 API floor, §7.2 provider-model `cost_per_verification`/`cost_per_1000` formula, §7.3 computation template + pricing-source TODO + "numbers PENDING real runs."
- [Source: docs/ocr-llm-benchmarking-plan.md §3, §6] — the metric→column map (latency, tokens, CPU/GPU mode, estimated cost), latency distributions (tail), per-engine/per-model report tables.
- [Source: docs/database-schema.md §1.3 `ocr_results`] — `latency_ms`, `ran_on_cpu`, `image_variant`, `status`.
- [Source: docs/database-schema.md §1.4 `llm_results`] — `latency_ms`, `prompt_tokens`, `completion_tokens`, `total_tokens` (generated), `model_id`, `provider`, `task`, `status`.
- [Source: docs/data-dictionary.md §4] — `cost_usd` computed at analysis time, **not stored**; pricing source still open.
- [Source: app/benchmark/scoring.py + tests/test_scoring.py] — the sibling 5.2 shape this story mirrors (readers, frozen dataclasses, reproducibility, egress/read-only guard).
- [Source: app/db/repositories.py §benchmark scoring read helpers] — the SELECT-only reader pattern (raw SQL stays in `app/db/`).
- [Source: _bmad-output/project-context.md] — `cost_usd` as decimal/string (never float on currency), AR-4 (per-engine/model storage), AR-5 (5s read path), AR-13 (pipeline owns writes), firewall posture, VLM-only purity, NFR-5 honesty.

## Dev Agent Record

### Agent Model Used

Amelia (dev-story workflow) · claude-opus-4-8

### Debug Log References

- `_probe.py` (root, removed): verified the nearest-rank percentile `ceil` matches `math.ceil` across sample sizes n=1..59 and percentiles {0.0, 0.5, 0.95, 0.99, 1.0}; then simplified `_nearest_rank` to plain `math.ceil`.
- Targeted runs: `pytest tests/test_cost.py -q` (red → 14 passed green); `pytest tests/test_cost.py tests/test_scoring.py -q` (33 passed — no regression in shared `repositories.py`).

### Completion Notes List

- **All 5 ACs satisfied, test-first (red → green → refactor).** `app/benchmark/cost.py` is the pure, reproducible, read-only speed+cost harness; `tests/test_cost.py` covers every AC (14 tests).
- **AC1 (latency):** `latency_stats` → mean / median (p50) / p95 over non-NULL `latency_ms`, with NULLs and the sample count handled honestly (empty ⇒ all-None, count 0). `cost_corpus` keys OCR by `(engine_name, image_variant)` and LLM by `model_id` — the SAME keys as the 5.2 accuracy scorer, so 5.4 lines them up row-for-row. p95 by a fixed **nearest-rank** method (documented; reproducible).
- **AC2 (cost-per-1,000):** `cost_per_verification` / `cost_per_1000` in **`Decimal`** only (never float on currency), quantized to `0.000001`. Local OCR engines + `provider == local` models ⇒ `Decimal("0")` labeled "local — $0 marginal API cost" (§7.1 floor). Provider models via a labeled `ModelPrice` (`source` + `as_of`, NFR-5). **Unpriced provider model ⇒ `cost_per_1000 = None`** (honest "not priced", never a fabricated 0). `cost_usd` is **computed, never persisted** — no schema change. Default pricing table is intentionally TODO-priced/empty (real numbers drop in after real runs — benchmarking-plan §7.3); the mechanism + labels are what landed.
- **AC3 (CPU-only):** `EngineCost.cpu_only` derived from captured `ran_on_cpu` (True iff all flagged rows ran on CPU; False if any GPU; None if unflagged) — surfaced for 5.4's CPU-only flag.
- **AC4 (reproducible):** stable sorted iteration (readers `ORDER BY`; `sorted()` group keys), pure functions, fixed percentile method, `Decimal` money quantize — test asserts `asdict` byte-equal across two runs.
- **AC5 (firewall/read-only):** two new SELECT-only readers (`list_ocr_latency_for_cost`, `list_llm_cost_rows`) with raw SQL confined to `app/db/`; module opens no off-host client, writes nothing, off no render path. Reused the `_OFF_HOST_CLIENT` regex + no-write-SQL scan from `tests/test_scoring.py` as structural guards.
- **Invariants honored:** money is Decimal/string (never float on currency); per-engine/model storage already separate (AR-4) — readers only expose it; AR-13 (writes nothing); AR-5 (not on the 5s read path); NFR-2 (zero egress, no provider client); VLM-only purity (reads captured outputs, never feeds a model). No `auto-run/` edits.
- Validated on the host venv (Python 3.14) per CLAUDE.md; ruff + mypy clean on changed source.

### File List

- `app/benchmark/cost.py` (NEW) — `LatencyStats` + `latency_stats`/`_nearest_rank`; `ModelPrice` + `PricingTable`/`DEFAULT_PRICING`; `cost_per_verification`/`cost_per_1000` (Decimal); `EngineCost`/`ModelCost`/`CostReport` + `cost_corpus`. Read-only, zero-egress.
- `app/db/repositories.py` (UPDATE) — added `OcrCostRow`/`LlmCostRow` models + `list_ocr_latency_for_cost`/`list_llm_cost_rows` SELECT-only readers (Story 5.3 section).
- `tests/test_cost.py` (NEW) — all-AC coverage incl. Decimal cost (priced / local-$0 / unpriced-None), latency mean/median/p95, CPU-only flag, reproducibility, and the egress/read-only guard. 14 tests at dev; **+3 from code review** (`test_cpu_only_flag_none_when_unflagged`, `test_local_ocr_engine_carries_zero_api_cost_floor`, `test_mixed_provider_model_not_fabricated_zero`) ⇒ 17 tests. CR also realigned `_OFF_HOST_CLIENT` to the `tests/test_scoring.py` sibling verbatim.

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-14 | Story 5.3 drafted — speed & cost statistics (`app/benchmark/cost.py`): per-engine (×variant) and per-model latency mean/median/p95, CPU-only flag, cost-per-1,000-Verifications for every configuration (local-$0 floor, provider via a labeled `ModelPrice` table, unpriced ⇒ None), Decimal money, pricing basis labeled (NFR-5), reproducible, read-only, zero-egress. Status → ready-for-dev. |
| 2026-06-14 | Story 5.3 implemented (test-first, all 5 ACs). New `app/benchmark/cost.py` + two SELECT-only readers in `repositories.py` + `tests/test_cost.py` (14 tests). Decimal money, fixed nearest-rank p95, reproducible, zero-egress/read-only. Host validation: cost+scoring 33 passed; ruff + mypy clean. Status → review. |
| 2026-06-14 | Code review (3-layer adversarial: Blind Hunter diff-only + Edge Case Hunter + Acceptance Auditor) — 2 patches + 2 test-coverage patches applied, 2 deferrals, 5 dismissed. **F1 [HIGH — AC2/NFR-5 fabricated-zero]:** `_model_cost` used `is_local = any(provider=='local')`; since LLM rows group by `model_id` only, a single mislabeled `local` row mixed with paid-provider rows would stamp the whole paid model `Decimal("0")` — the exact fabricated zero AC2/NFR-5 forbid. Fixed to `all(provider=='local')` (honest: a disagreeing group falls through to the pricing table ⇒ unpriced None, never a fabricated $0); pinned by `test_mixed_provider_model_not_fabricated_zero`. **F2 [AC5 guard weakened]:** `test_cost.py`'s `_OFF_HOST_CLIENT` regex had diverged from the `tests/test_scoring.py` sibling the story mandated reusing (dropped `ClientSession(`, `urlopen(`, bare `socket(`); only caught literal `urllib.request`/`socket.socket(`); realigned verbatim. **F3/F4 [coverage]:** added `test_cpu_only_flag_none_when_unflagged` (AC3 honest-unknown branch) and `test_local_ocr_engine_carries_zero_api_cost_floor` (AC2 OCR-side $0 floor) — both previously untested. Dismissed/confirmed-safe: `model_id or ""` null-collapse (shared verbatim with 5.2, each model has an id, no regression); `dict(row)` (connection.py:96 sets `row_factory = sqlite3.Row`); double-quantize / median int-vs-float / empty `DEFAULT_PRICING` (intentional + spec-mandated TODO-pricing, tests pass). Deferred to deferred-work.md (metric/scope decisions for Diane): `verification_count` counts whole corpus vs covered set (presentational only — not a cost denominator today); `list_llm_cost_rows` omits the `is_benchmark_only` filter its displayed-reader siblings apply. No invariant regressed (Decimal-only money; AR-13 writes nothing [no-write-SQL guard]; AR-5 not on render path; NFR-2 no off-host client [realigned egress guard]; VLM-only purity — reads outputs, never feeds a model; no schema/`cost_usd` persistence; 5.4/5.2 untouched). Post-CR full host CI: ruff + mypy (94 files) clean, **745 passed, 1 skipped** (+3 new CR tests). Status → done. |
