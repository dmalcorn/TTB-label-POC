# OCR & LLM Benchmarking Plan — TTB COLA Label Specialist POC

**Status:** Planning artifact (pre-implementation). Numbers marked `TODO` drop in after real benchmark runs.
**Last updated:** 2026-06-11
**Audience:** the POC engineering team; TTB reviewers assessing the procurement-informing value of the POC.

---

## 0. Why this document exists

The brief invites the POC to *"produce valuable information that could inform a future software
project (including procurement/purchase decisions)."* The single most procurement-relevant
question the POC can answer is: **which text-extraction engine should TTB buy/build on?** Rather
than pick one OCR engine or one LLM blind, the POC **runs several of each on the same extraction
tasks and collects speed + accuracy + cost statistics**, so the recommendation rests on data, not
intuition.

This plan specifies that benchmark: what is tested, how it is measured, how ground truth is
established, how the model calls relate to the **firewall posture** (PRD NFR-2 / addendum A2 —
the local-first core plus a toggleable `models-internal-endpoint` model layer), and how a
**Python + LangChain analysis program writes the results into the database** for reporting.

> **Firewall-posture note (revised 2026-06-11).** This plan originally described a cloud-LLM
> **harness "walled off" and "never deployed."** That framing is **superseded** by the PRD's
> NFR-2 revision: LLM extraction + benchmark-stat capture run **in the live pre-compute pipeline**,
> classified `models-internal-endpoint` (provider APIs in the POC, internal endpoints in
> production), and are **toggleable off** to a zero-egress OCR-only configuration (FR-12). The
> methodology below (accuracy scoring, CER, cost-per-1,000) is unchanged; only the
> deployed-vs-walled-off framing is updated. See
> [`outbound-calls-inventory.md`](./outbound-calls-inventory.md).

**Source requirements:**
[`discussion-points.md` §6 OCR, LLM & Benchmarking Strategy](../ref-docs/discussion-points.md) and
[§5 Processing Architecture](../ref-docs/discussion-points.md) (microservice; OCR in a swappable
background job). Technical grounding (engine benchmark data, the VLM landscape, the cost framing,
and the decisive **"firewall fork"**) comes from the
[domain research → Technical Trends](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md).

**Cross-references:**
- [`database-schema.md`](./database-schema.md) — the `ocr_results`, `llm_results`,
  `field_comparisons`, `checklist_items` tables that store every stat captured here.
- [`data-dictionary.md`](./data-dictionary.md) — §3 (OCR-extracted fields) and §4 (LLM / benchmark
  stat fields) define each stat column's semantics.
- [`outbound-calls-inventory.md`](./outbound-calls-inventory.md) — the firewall-compliance counterpart;
  it classifies every component `none`/`local`/`models-internal-endpoint` and defines the toggle-off
  zero-egress path. The benchmark's model calls are the `models-internal-endpoint` layer it describes.
- [`tools-used.md`](./tools-used.md) — Tesseract, PaddleOCR, OpenCV, LangChain, optional local VLM.
- [`tradeoffs-and-limitations.md`](./tradeoffs-and-limitations.md) — records the benchmark's caveats
  (CPU-vs-GPU, leaderboard volatility, small fixture set).
- [`approach.md`](./approach.md) — the pre-compute pipeline the deployed engines run in.

---

## 1. Goals

The benchmark exists to answer four questions, in order of procurement value:

1. **Which OCR engine is more accurate?** — Per-engine field-match rate and character error rate
   (CER) on the same labels, broken out by clean vs. degraded images (the glare/angle cases the
   brief calls out).
2. **Which LLM/VLM is better?** — On the *same* extraction tasks, which model extracts the
   matchable fields most accurately, how fast, and at what token cost.
3. **What is the best overall approach?** — Not just "best engine" but the best *pipeline*: local
   OCR alone, OCR + OpenCV preprocessing, OCR + LLM-fallback, or VLM-only. The hybrid
   ("classical OCR for the clean 90%, a small local VLM for the degraded tail") is the hypothesis to
   test, mirroring COLAClear's validated CV-plus-structured-LLM architecture
   ([research → Implementation considerations](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)).
4. **Procurement input.** — Produce a defensible, data-backed recommendation: which OCR engine to
   standardize on, whether an LLM layer earns its keep, and **what each path costs per ~1,000
   verifications**. Provider-model results inform a buy/build decision *and* are deployable as
   `models-internal-endpoint` (internal endpoints in production); the local OCR core remains the
   zero-egress baseline every model result is compared against.

> **Non-goal:** the benchmark does **not** pick a single winner to hard-wire into the deployed app.
> Per [`discussion-points.md` §6](../ref-docs/discussion-points.md), it deliberately *"runs multiples
> and collects stats."* The engines stay swappable behind a uniform interface (§5).

---

## 2. What is tested

### 2.1 OCR engines (deployed-path candidates — all run locally)

| Engine | Role | Notes |
|---|---|---|
| **Tesseract** | Baseline classical OCR | Light, CPU-only (~0.77 s/doc, ~10 MB), strong on clean print. The lower bound to beat. |
| **PaddleOCR** | Primary classical comparator | More accurate on curved/noisy text (~88.7% vs ~52.1% on curved; F1 0.938 vs 0.797 in one 2025 study); ships layout/table analysis; far faster *with* a GPU. |
| **PP-OCRv5** *(candidate)* | Specialized small model | ~5M-param model reported to rival billion-param VLMs on OCR while staying local-friendly. **TODO:** confirm inclusion after a first integration spike. |

Engine benchmark figures above are from
[research → Technical Trends → Emerging Technologies](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
(MEDIUM-HIGH confidence; directional, dataset-dependent — hence the local re-benchmark on TTB-like fixtures).

Each engine runs **per image** and is run in **both CPU and (where available) GPU mode** —
government infra has no guaranteed GPU, so CPU numbers are the load-bearing ones (`ocr_results.ran_on_cpu`).

### 2.2 LLMs / VLMs (live-pipeline extraction + benchmarking; `models-internal-endpoint`)

Run in the live pre-compute pipeline (§5) to extract fields and generate the comparison stats the
brief asks for. Candidate set spans the providers named in
[`discussion-points.md` §6](../ref-docs/discussion-points.md) (Codex/OpenAI, Gemini, "plus any
recommended"):

| Provider | Candidate models | `provider` value |
|---|---|---|
| Anthropic | Claude Opus-class, Claude Sonnet-class | `anthropic` |
| OpenAI | GPT-class, Codex | `openai` |
| Google | Gemini-class | `google` |
| **Local** (zero-egress model option) | small VLM — e.g. GLM-OCR (~0.9B), dots.ocr (~1.7B), Qwen3-VL | `local` |

**TODO:** pin the exact model IDs and `full_model_id` strings used in each run (these are recorded
per call — see §3). The VLM landscape is fast-moving; treat 2026 leaderboard scores as indicative
([research → Digital Transformation](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)).

> **Classification:** provider models (`anthropic`/`openai`/`google`) are `models-internal-endpoint`
> — permitted in the live path as a stand-in for in-firewall endpoints (PRD NFR-2 / addendum A2),
> toggleable off. A **locally-hosted** small VLM (`provider=local`) is the zero-egress model option.
> The whole model layer toggles off to a provable OCR-only configuration (FR-12). `is_benchmark_only`
> now distinguishes *comparison-only* runs from the run that fed the displayed extraction (§3), not
> deployed-vs-walled-off. See [`outbound-calls-inventory.md`](./outbound-calls-inventory.md).

### 2.3 The extraction tasks (what every engine/model is asked to produce)

The tasks are the **matchable label fields** — the fields a Label Specialist compares against the
artwork ([`data-dictionary.md` §1](./data-dictionary.md), flagged *Matchable*; mirrored as OCR
outputs in [`data-dictionary.md` §3](./data-dictionary.md)):

| `field_key` | What is extracted | Check type it feeds |
|---|---|---|
| `brand_name` | Brand name text | Field-match |
| `fanciful_name` | Fanciful name | Field-match |
| `class_type_designation` | Class/type designation | Hybrid (field-match + rules) |
| `alcohol_content` | ABV statement (e.g. "45% Alc./Vol.") | Field-match + format |
| `net_contents` | Net contents (e.g. "750 mL") | Field-match + standards-of-fill |
| `name_and_address` | Name/address statement | Field-match |
| `government_warning` | Full Part 16 warning text | **Deterministic** (exact/normalized) |
| `grape_varietal` / `wine_appellation` / `wine_vintage` | Wine-only fields | Field-match (wine) |

The **Government Warning** is included as an extraction task because verifying its verbatim wording
is the single most rule-bound, fully-deterministic check (27 CFR Part 16) and a prime measure of
OCR fidelity on a long, fixed string. A raw full-text dump (`ocr_raw_text`) is also captured per
engine for audit and for CER scoring (§4).

---

## 3. Metrics & how they are captured

Every metric maps to an existing column so the benchmark stores nothing the schema can't already hold.

| Metric | Definition | Where stored | How captured |
|---|---|---|---|
| **OCR latency** | Wall-clock ms for one engine on one image | `ocr_results.latency_ms` ([schema §1.3](./database-schema.md)) | Timed around the engine call in the OCR job. |
| **OCR confidence** | Engine-reported mean confidence (0–1) | `ocr_results.confidence` | Read from engine output where available. |
| **CPU/GPU mode** | Was the run CPU-only? | `ocr_results.ran_on_cpu` | Set by harness config. |
| **Engine identity** | Engine name + version | `ocr_results.engine_name`, `engine_version` | For procurement traceability. |
| **LLM latency** | End-to-end call ms | `llm_results.latency_ms` | **LangChain local tracing** (toggleable, no egress). |
| **Tokens** | Input/output/total | `llm_results.prompt_tokens`, `completion_tokens`, `total_tokens` | From the model response metadata; the cost-analysis input. |
| **Model identity** | name / short id / full pinned id / provider | `llm_results.model_name`, `model_id`, `model_full_id`, `provider` | Required by [`discussion-points.md` §4](../ref-docs/discussion-points.md) ("model name, model ID, full model ID"). |
| **Call timestamps** | Start / end | `llm_results.requested_at`, `responded_at` | Per [`discussion-points.md` §4](../ref-docs/discussion-points.md). |
| **Benchmark flag** | Comparison-only run (not the displayed extraction)? | `llm_results.is_benchmark_only` | TRUE for extra models run purely to populate the comparison table. |
| **Estimated cost** | tokens × price | `cost_usd` ([data-dictionary §4](./data-dictionary.md)) | Computed by the analysis program (§7). |
| **Field-match outcome** | MATCH / MISMATCH / MISSING / UNVERIFIABLE | `field_comparisons.match_status` | The accuracy scoring rule (§4). |
| **Field similarity** | Normalized 0–1 similarity | `field_comparisons.similarity` | Guards the "STONE'S THROW" false-mismatch (§4). |
| **Extraction provenance** | Which engine/model produced the value | `v_field_comparisons.extracted_source` (derived `ocr:tesseract` / `llm:<model_id>` from the source FK) | So per-engine accuracy can be rolled up. |
| **CER** *(derived)* | Character error rate vs. ground-truth string | Computed at analysis time (not a stored column) | See §4; reported, not persisted, unless promoted to `submission_extra_fields`. |

### LangChain — local tracing only

LangChain captures **latency/timing and model identity** for LLM calls. It runs in **local-only
mode with no telemetry egress** and is **toggleable off** so it never conflicts with the
no-outbound-calls constraint ([`discussion-points.md` §6](../ref-docs/discussion-points.md);
[`outbound-calls-inventory.md` §2 + TODO-3](./outbound-calls-inventory.md)). In the benchmark
harness LangChain may also be used to orchestrate the multi-model calls and record `langchain_trace_id`
([data-dictionary §4](./data-dictionary.md)). Master off-switch (pinned): `LANGCHAIN_TRACING_ENABLED`
— see **TODO-3** in the outbound-calls inventory.

---

## 4. Accuracy methodology

### 4.1 Ground truth — the seed CSV

The mock database is seeded from a **labels CSV** carrying the *known* field values for each label
image set ([`discussion-points.md` §11 Test Data](../ref-docs/discussion-points.md) — *"sample label
images + corresponding field data, ideally a CSV, to seed the database"*). For benchmarking, that
seed CSV is the **ground truth**: the human-verified, correct value of every matchable field per
label. Engine/model output is scored against it.

- **Seed CSV:** the ground-truth seed CSV is [`../samples/seed-template.csv`](../samples/seed-template.csv)
  and the batch template is [`batch-template.csv`](./batch-template.csv)
  ([`discussion-points.md` §14](../ref-docs/discussion-points.md)). It includes, per label set, a
  column for every `field_key` in §2.3 *and* the verbatim Government Warning text, so each extraction
  task has a gold value.
- **IP caveat:** real registry artwork is trademarked — use as **private test fixtures only**;
  use synthetic labels for anything public ([research → Data protection & privacy](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)).

### 4.2 Two accuracy measures

**(a) Field-match rate (primary, per-field).** For each `field_key`, compare the extracted value to
the ground-truth value and assign a `match_status`. This *is* the production matching logic, so the
benchmark measures exactly what the deployed app would do.

**(b) Character Error Rate (secondary, per-engine, raw-text).** CER = Levenshtein edit distance /
ground-truth length, computed over `ocr_raw_text` (and the Government Warning string) vs. the gold
text. CER is the engine-agnostic accuracy number that the OCR literature uses and that lets us
compare against the research's directional figures.

### 4.3 The field-match scoring rule (with tolerance)

The rule must **not** false-reject benign formatting differences — the **"STONE'S THROW" vs
"Stone's Throw"** case Dave raised
([research → Implementation considerations](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)).
Scoring per field:

1. **Normalize both values** (ground truth and extracted): trim, collapse internal whitespace,
   casefold (Unicode), normalize curly→straight quotes and Unicode NFKC, drop trailing punctuation.
   For `alcohol_content`/`net_contents`, additionally parse to a numeric + unit (so "45% Alc./Vol.",
   "ALC 45% BY VOLUME", and "45.0% alcohol" compare equal on the number).
2. **Compute similarity** `similarity ∈ [0,1]` (e.g. normalized Levenshtein ratio, or token-set
   ratio for multi-word fields like `name_and_address`). Store in `field_comparisons.similarity`.
3. **Assign `match_status`:**
   - `MATCH` — normalized strings equal, **or** `similarity ≥ τ_field`.
   - `MISMATCH` — both present but `similarity < τ_field`.
   - `MISSING` — ground truth present, extracted empty/null.
   - `UNVERIFIABLE` — not auto-decidable (e.g. cross-image field-of-vision) → defer to human.
4. **Per-field tolerance `τ_field`** (starting points — tune against the fixtures, **TODO**):

   | Field class | Suggested `τ` | Rationale |
   |---|---|---|
   | `government_warning` | **exact after normalization** (`τ = 1.0` on body) | Deterministic; but still **enforce** the caps "GOVERNMENT WARNING:" token separately, per Part 16. |
   | `alcohol_content`, `net_contents` | numeric exact; string `τ = 0.90` | Compare parsed number/unit; the number must match, formatting may differ. |
   | `brand_name`, `fanciful_name`, `class_type_designation` | `τ ≈ 0.90` | Absorbs case/punctuation ("STONE'S THROW"). |
   | `name_and_address` | `τ ≈ 0.85` (token-set) | Longer, more OCR noise; word-order/abbreviation tolerant. |

5. **Aggregate** to per-engine and per-model **field-match rate** = MATCH / (MATCH+MISMATCH+MISSING),
   reported overall and per `field_key`. (UNVERIFIABLE is excluded from the denominator and reported
   separately.)

> The same scoring rule runs whether the extracted value came from OCR or an LLM
> (the source FK / derived `extracted_source` records which), so OCR and LLM are scored on an identical basis — the only way
> "which is better" is a fair comparison.

---

## 5. Benchmark harness design

### 5.1 Two layers in one pipeline (local-first core + internal-endpoint model layer)

The benchmark is **not** a separate, never-deployed program — it runs as a byproduct of the live
pre-compute pipeline. The compliance boundary is **layered**, not split across two machines:

```
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │  DEPLOYED PRE-COMPUTE PIPELINE (TTB env)                                           │
  │                                                                                    │
  │  LAYER A — local-first core (classification: none / local; ALWAYS sufficient)      │
  │    • Local OCR microservice: Tesseract, PaddleOCR (, PP-OCRv5)                      │
  │    • OpenCV preprocessing   • Deterministic rules engine                           │
  │    • Optional LOCAL small-VLM (provider=local, zero-egress)                         │
  │    • LangChain tracing (local-only, no telemetry egress, toggleable)               │
  │                                                                                    │
  │  LAYER B — model layer (classification: models-internal-endpoint; TOGGLEABLE OFF)  │
  │    • Provider VLMs: Claude / GPT / Gemini — extraction + benchmark-stat capture     │
  │    • Cloud API in the POC; internal endpoint in production (PRD NFR-2 / A2)         │
  │    • Scores vs. seed-CSV ground truth; writes stats to DB                           │
  │                                                                                    │
  │  LLM_ENABLED=false  ⇒  Layer B off  ⇒  whole pipeline is zero-egress, OCR-only (FR-12)│
  └──────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Uniform engine interface (the microservice idea)

Each OCR engine sits behind a **uniform interface** — `extract(image) -> {text, word_boxes,
confidence, latency_ms}` — so engines are swap/add-able by config, not code surgery
([`discussion-points.md` §5](../ref-docs/discussion-points.md) — *"explore running OCR in a
microservice; make it easy to swap/compare OCR packages"*). The model layer (Layer B) follows the
same adapter pattern, so adding a provider model is a config/adapter change, not a redesign.

### 5.3 How the model layer stays compliant

- **Endpoint URLs are configuration** (`LLM_PROVIDER` / `LLM_BASE_URL`, TODO-7): production points
  them at **internal** model endpoints inside the firewall; the POC points them at the documented
  cloud-provider APIs that **model** those endpoints. No code change between environments.
- **The model layer toggles off** (`LLM_ENABLED=false`): with Layer B disabled, the pipeline runs
  entirely on the local-first core (Layer A) — a provable **zero-egress, OCR-only** configuration
  (FR-12). The deployed app must function on Layer A alone.
- **Tracing never egresses telemetry** (LangChain local-only; TODO-3). `is_benchmark_only = TRUE`
  marks extra models run purely for the comparison table, separate from the displayed extraction.

### 5.4 Run procedure

1. Load seed labels + ground-truth CSV (§4.1).
2. (Optional) OpenCV preprocess to also benchmark "raw vs. preprocessed" image variants.
3. For each label image: run every OCR engine (CPU and GPU mode) → write `ocr_results`.
4. For each label: run every benchmark LLM/VLM on the extraction tasks → write `llm_results`
   (model identity, tokens, latency, timestamps).
5. Score every extracted value vs. ground truth (§4) → write `field_comparisons`.
6. Run the analysis/reporting program (§6) → roll up stats, compute cost, write report tables.

---

## 6. Reporting — can we generate a report?

**Yes.** A **Python program using LangChain** retrieves the raw `ocr_results` / `llm_results` /
`field_comparisons` rows, computes the aggregate statistics, and **stores the analyzed results back
into the database** ([`discussion-points.md` §6](../ref-docs/discussion-points.md) — *"maybe a Python
program using LangChain to retrieve, analyze, and store the benchmark results in the database"*). The
report is then rendered from those stored tables.

The report includes:

- **Per-engine OCR table:** engine, version, CPU/GPU, mean/median/p95 `latency_ms`, mean confidence,
  overall field-match rate, per-field match rate, mean CER (clean vs. degraded image split).
- **Per-model LLM table:** `model_name` / `full_model_id` / provider, mean/median/p95 latency, mean
  total tokens, field-match rate, per-field match rate, and **$/label** (→ feeds §7).
- **Win-rate matrix:** for each `field_key`, which engine/model produced the highest-similarity
  correct extraction — a per-field "who wins" tally across the fixture set.
- **Latency distributions:** percentiles (p50/p95/p99) per engine/model, since the deployed app's
  ~5s interaction-latency claim depends on the *tail*, not the mean.
- **Pipeline comparison:** OCR-only vs. OCR+OpenCV vs. OCR+LLM-fallback vs. VLM-only — accuracy lift
  vs. cost/latency added (the §1 goal-3 question).
- **Cost summary:** the §7 $/1,000 table.

**TODO(report-format):** decide output format (Markdown tables committed to the repo + a generated
HTML/CSV summary). The analysis program writes the numeric results to the DB regardless of render format.

---

## 7. Cost analysis framework — $/1,000 verifications

Deliver **LLM cost per ~1,000 verifications** ([`discussion-points.md` §6](../ref-docs/discussion-points.md)).
One **verification** = extracting the matchable fields for **one submission** (its full label-image
set). Structure now; numbers drop in after real runs.

### 7.1 Local OCR path (deployed)

Marginal **API cost ≈ $0** — no token charges; cost is compute only (one-time/standing CPU, optional
GPU infra)
([research → Cost Analysis](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)).
This is itself a procurement finding: the firewall-safe local path is also the cheapest at scale.

```
cost_per_1000_local ≈ $0 (API)   +   amortized_infra_cost_per_1000   [TODO: infra model]
```

Optionally report a compute proxy:
`(mean processing_ms per submission) × 1000 × $/compute-hour` to compare CPU vs. GPU economics.

### 7.2 Provider-model cost (`models-internal-endpoint`; deployable + informs buy/build)

For each provider model:

```
cost_per_verification(model)
    = (mean_prompt_tokens   / 1000 × input_price_per_1k(model))
    + (mean_completion_tokens/ 1000 × output_price_per_1k(model))

# image inputs: include image-token cost per the provider's tokenization
cost_per_1000_verifications(model) = cost_per_verification(model) × 1000
```

`mean_prompt_tokens` / `mean_completion_tokens` come straight from the captured
`llm_results.prompt_tokens` / `completion_tokens`. The analysis program writes per-call
`cost_usd = total_tokens-derived` and aggregates the table below.

### 7.3 Computation template (numbers PENDING real runs)

| Path / model | `full_model_id` | mean prompt tok | mean compl. tok | input $/1k | output $/1k | **$/verif.** | **$/1,000 verif.** |
|---|---|---|---|---|---|---|---|
| Local OCR (Tesseract) | n/a | — | — | $0 | $0 | **≈ $0** (API) | **≈ $0** (API) |
| Local OCR (PaddleOCR) | n/a | — | — | $0 | $0 | **≈ $0** (API) | **≈ $0** (API) |
| Local small VLM | `TODO` | `TODO` | `TODO` | $0 | $0 | **≈ $0** (API) | **≈ $0** (API) |
| Cloud — Claude-class | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` |
| Cloud — GPT-class | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` |
| Cloud — Gemini-class | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` | `TODO` |

**TODO(pricing-source):** record the per-model published price (input/output $/1k tokens, plus image
pricing) and its retrieval date, since prices change — confirm `cost_usd` pricing source per model
([`data-dictionary.md` §4 open TODO 4](./data-dictionary.md)). The cost result is only as current as
that date; note it in [`tradeoffs-and-limitations.md`](./tradeoffs-and-limitations.md).

> **Procurement read:** if a provider VLM is materially more accurate but costs `$X`/1,000 while
> local OCR is "good enough" at ≈$0, the table makes the accuracy-vs-cost trade explicit. Because the
> model layer is deployable (`models-internal-endpoint`) *and* toggleable off, the provider column is
> both a **real deployment option** (at internal-endpoint cost) and **buy/build leverage** — with the
> zero-egress OCR-only path always available as the $0 floor.

---

## 8. LLM-as-fallback evaluation

The LLM is **optional**: a POC demonstrator **and** a **fallback when OCR isn't producing good
matches** ([`discussion-points.md` §6](../ref-docs/discussion-points.md)). The benchmark must measure
whether that fallback actually helps — and at what cost — so the recommendation is evidence-based.

### 8.1 When the fallback triggers

A submission/field is a fallback candidate when OCR results are poor, defined by measurable thresholds
(tuned on fixtures, **TODO**):

- `ocr_results.confidence` below a floor, **or**
- the field's `field_comparisons.match_status` is `MISMATCH`/`MISSING` across **all** OCR engines,
  **or**
- the two OCR engines **disagree** on a field value (low cross-engine `similarity`).

### 8.2 What is measured

For each triggered case, run the fallback model on the same task and record:

- **Recovery rate** — fraction of OCR-failed fields the fallback turns into a `MATCH` vs. ground truth.
- **Added latency** — fallback `latency_ms` (the tail cost; relevant to the ~5s claim if ever in the
  live path).
- **Added cost** — `total_tokens` × price (cloud) or ≈$0 (local VLM) → cost *per recovered field*.
- **Regression check** — did the fallback ever *replace a correct OCR value with a wrong one*?
  (false-recovery rate — a safety metric).

### 8.3 Two fallback variants to compare

| Variant | Classification | Purpose |
|---|---|---|
| **Local small VLM** | `local` — zero-egress | The fallback that ships with **no** endpoint dependency — measures the zero-egress recovery ceiling. |
| **Provider VLM** | `models-internal-endpoint` | Deployable as an internal endpoint (cloud-API stand-in in the POC); also the upper-bound comparator for how much recovery is on the table. |

> **Deployed-path rule:** the model layer is **toggleable off** to a zero-egress OCR-only path
> (FR-12); when enabled, its calls are `models-internal-endpoint` (internal endpoint in production,
> cloud-API stand-in in the POC) — see [`outbound-calls-inventory.md` §2–§3](./outbound-calls-inventory.md).
> Keep rule-bound checks (Government Warning, ABV format) **deterministic** regardless of any model —
> the LLM is advisory only, honoring *"recommend, don't decide"*
> ([research → Risk Mitigation](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)).

---

## 9. Open issues / TODO summary

- **Seed CSV (DONE):** the seed labels + ground-truth CSV exist — the ground-truth seed is
  [`../samples/seed-template.csv`](../samples/seed-template.csv) and the batch template is
  [`batch-template.csv`](./batch-template.csv); it is the benchmark's gold standard (§4.1).
- **TODO(τ-tuning):** tune per-field tolerance thresholds `τ_field` against the actual fixtures (§4.3).
- **TODO(model-pinning):** pin exact `model_id` / `full_model_id` for each benchmarked model (§2.2).
- **TODO(pricing-source):** record per-model token/image prices + retrieval date for the cost table (§7.3).
- **TODO(PP-OCRv5):** confirm inclusion after an integration spike (§2.1).
- **TODO(report-format):** finalize report render format; DB write is format-independent (§6).
- **TODO(fallback-thresholds):** set OCR-confidence / disagreement triggers for the fallback (§8.1).
- **LangChain-config — RESOLVED:** master off-switch is pinned (`LANGCHAIN_TRACING_ENABLED`; `false`
  for the OCR-only path); just document it
  ([`outbound-calls-inventory.md` TODO-3](./outbound-calls-inventory.md)).
- **TODO(CER-storage):** decide whether per-engine CER is persisted (e.g. via `submission_extra_fields`)
  or computed at report time only (§3).

---

## 10. Related documents

- [`database-schema.md`](./database-schema.md) — storage for every stat (`ocr_results`, `llm_results`,
  `field_comparisons`, `checklist_items`).
- [`data-dictionary.md`](./data-dictionary.md) — §3 OCR-extracted fields, §4 LLM/benchmark stat fields.
- [`outbound-calls-inventory.md`](./outbound-calls-inventory.md) — firewall compliance; the `none`/`local`/`models-internal-endpoint` classification and the toggle-off zero-egress path.
- [`tools-used.md`](./tools-used.md) — engine/library list.
- [`tradeoffs-and-limitations.md`](./tradeoffs-and-limitations.md) — benchmark caveats.
- [`approach.md`](./approach.md) — the pre-compute pipeline the deployed engines run in.
- [`discussion-points.md`](../ref-docs/discussion-points.md) — §5 (microservice), §6 (OCR/LLM/benchmark/cost), §11 (test data/CSV).
- [Domain research report](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
  — Technical Trends (engine data, VLM landscape, firewall fork) + Recommendations (Cost Analysis framing).

> Note: the sibling `docs/` files cross-linked above all exist on disk (created per
> [`discussion-points.md` §14](../ref-docs/discussion-points.md)); links resolve.
