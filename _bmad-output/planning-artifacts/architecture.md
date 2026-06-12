---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-06-12'
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/prd.md
  - _bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/addendum.md
  - _bmad-output/planning-artifacts/briefs/brief-TTB-label-POC-2026-06-11/brief.md
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/EXPERIENCE.md
  - _bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md
  - docs/approach.md
  - docs/database-schema.md
  - docs/data-dictionary.md
  - docs/tools-used.md
  - docs/outbound-calls-inventory.md
  - docs/image-handling.md
  - docs/ocr-llm-benchmarking-plan.md
  - docs/requirements-mapping.md
  - docs/assumptions.md
  - docs/tradeoffs-and-limitations.md
  - docs/regulatory-rules-distilled-spirits.md
  - docs/regulatory-rules-wine.md
  - docs/regulatory-rules-beer.md
  - docs/label-requirements-by-type.md
workflowType: 'architecture'
project_name: 'TTB-label-POC'
user_name: 'Diane'
date: '2026-06-12'
---

# Architecture Decision Document — TTB COLA Label Specialist Workspace (POC)

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (28 FRs across 6 features):**

- **Review Workspace (FR-1–8):** Next-Submission queue (no browsing), stacked field comparison with discrepancy highlighting, per-type Checklist, chevron progress bar, Disposition capture, original-vs-preprocessed image view, in-UI help. *Architecturally: a thin read-path over pre-computed rows; zero heavy compute at request time.*
- **Pre-compute Pipeline (FR-9–12):** background processing at Submission arrival with a minimal status enum + failure state; local OpenCV preprocessing; multi-engine OCR (≥2, engine-agnostic schema); LLM extraction/fallback, toggleable, degrading to OCR-only. *The architectural centerpiece and the 5-second mechanism.*
- **Compliance Engine (FR-13–18):** deterministic Government Warning verification, field-match with tolerance bands, per-type deterministic format checks, hybrid class/type (LLM capped at REVIEW), flag-only checks, verdict provenance. *Determinism taxonomy + Rulesets-as-data with CFR citations.*
- **Mock COLA Database & Corpus (FR-19–20):** Form 5100.31-modeled schema, 1–10 images as a child table, 30–50 seeded fixtures with Ground Truth.
- **Benchmark Harness (FR-21–24):** accuracy scoring vs Ground Truth, speed/cost statistics, in-app Benchmark Report, local-only toggleable tracing.
- **Demo Access & Deliverables (FR-25–28):** token gate, documentation deliverables, demo reset, live fixture enqueue.

**Non-Functional Requirements (6):**

- **NFR-1 — Performance:** ~5s p95 review-screen readiness, achieved *architecturally* via the Pre-compute Pipeline, not by fast request-time inference.
- **NFR-2 — Firewall posture:** local-first core; LLM layer classified `models-internal-endpoint` (cloud-API stand-in for in-firewall endpoints), toggleable to a provable zero-egress OCR-only path (FR-12); outbound-call inventory with 3-way classification (`none`/`local`/`models-internal-endpoint`).
- **NFR-3 — Privacy:** no PII; dummy data only; read-only except Disposition capture and pipeline writes; registry artwork private-fixtures-only.
- **NFR-4 — Usability/accessibility:** USWDS, Section-508-conscious defaults, minimum 24" monitor layout, designed for the lowest-tech-comfort user.
- **NFR-5 — Honesty of claims:** the demo/report/docs claim only what is demonstrated; limitations documented beside capabilities.
- **NFR-6 — Code quality:** organized, evaluator-readable; working core preferred over ambitious-incomplete features.

### Scale & Complexity

- **Primary domain:** Python full-stack monolith (web app + background workers + local SQL), server-rendered USWDS UI; single-user POC.
- **Complexity level:** Medium overall, with localized **High** risk in (a) the background pipeline plus the 5-second guarantee and its failure/degradation states, and (b) the pluggable multi-engine OCR/LLM extraction + benchmark layer.
- **Estimated architectural components:** ~7 — web/read API; background job runner; OCR adapter layer (pluggable engines, uniform interface); LLM/extraction layer; compliance/rules engine (Rulesets-as-data); mock DB + seed/reset; benchmark/reporting + local tracing.

### Technical Constraints & Dependencies

- **Firewall:** local-first core; LLM layer = `models-internal-endpoint`, toggleable off to a zero-egress OCR-only configuration (FR-12). All static assets self-hosted (no CDN). Tracing local-only, no telemetry egress.
- **CPU-only deployment reality:** no guaranteed GPU; CPU figures are the procurement-relevant ones; the Benchmark Harness records CPU-mode performance.
- **Offline weights:** all model weights pinned and shipped offline (no first-run downloads at runtime).
- **Open implementation picks (architect to lock):** FastAPI vs Flask; SQLite vs PostgreSQL; in-process OCR adapters vs localhost microservice; background scheduler (APScheduler vs RQ); local-VLM fallback model + license.

### Cross-Cutting Concerns Identified

- The ~5-second readiness budget (spans pipeline, DB, read path, and UI render).
- Engine Verdict vs. Disposition separation (schema + UI + API must never blur the two vocabularies).
- Firewall classification of every component + the outbound-call inventory deliverable.
- CFR citations stored as data with source dates (the 2022 Part 5 renumbering as cautionary tale).
- Engine-agnostic result storage — adding an engine/model requires no schema change (a procurement requirement).
- Demo reproducibility: deterministic queue order (oldest-first), demo reset, and live fixture enqueue.

## Starter Template Evaluation

### Primary Technology Domain

Python full-stack **monolith**, **containerized** — FastAPI app server, server-rendered Jinja2 + vendored USWDS UI, local SQLite, in-process background-worker pre-compute pipeline. Server-rendered (not SPA) is forced by the self-hosted-assets constraint (NFR-2), the lowest-tech-comfort single-user audience (NFR-4), and evaluator-readability (NFR-6). **Dev environment: Docker Desktop. Deploy target: Railway (Pro plan), building from a Dockerfile.**

### Starter Options Considered

- **`full-stack-fastapi-template` (official, fastapi/):** React + TS + Vite + Chakra UI + SQLModel + **PostgreSQL** + Docker + **JWT auth** + Traefik. **Rejected** — its SPA frontend, built-in auth system, and weight contradict server-rendered USWDS and "token-gate-only, no auth system." (Its Docker/Compose pattern is the only part worth borrowing.)
- **Django / cookiecutter-django:** **Rejected** — Django over the already-chosen FastAPI; heavier than a read-mostly POC needs.
- **USWDS compiled-assets distribution:** **Adopted in part** — vendor USWDS 3.x compiled CSS/JS/fonts/icon-sprite; skip the Node/Jekyll build.
- **No project-generator (hand-rolled minimal FastAPI in a custom Dockerfile):** **Selected.**

### Selected Starter: None (hand-rolled minimal FastAPI) + custom Dockerfile + vendored USWDS 3.x assets

**Rationale for Selection:**

- **Minimal firewall surface + evaluator-readable** — no SPA build chain, no generated client; every dependency deliberate and inventoried (FR-26, NFR-6).
- **The Dockerfile is the "pinned, offline" artifact** — bakes native deps (`tesseract-ocr`, OpenCV/Paddle libs), pinned model weights (resolves outbound-inventory TODO-2), vendored USWDS assets, and seeded fixture images into one reproducible image that runs identically on Docker Desktop and Railway.
- **Matches the decided stack** — FastAPI + Jinja2 + SQLite + APScheduler.

**Initialization (first implementation story):**

```dockerfile
# Dockerfile (sketch) — verified current as of June 2026; exact pins at dependency-pinning step (TODO-LIC)
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # fastapi==0.136.*, uvicorn[standard], jinja2,
                                                     # apscheduler, pytesseract, paddleocr,
                                                     # opencv-python-headless, langchain
# Build-time, baked-in (no runtime egress): pinned OCR/VLM weights, USWDS 3.x assets, seeded fixtures
COPY static/uswds/ static/uswds/        # vendored USWDS compiled bundle
COPY models/ models/                    # pinned PaddleOCR / local-VLM weights (TODO-2 resolved)
COPY fixtures/ fixtures/                # seeded label images + Ground Truth CSV
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Deployment & Dev Strategy (Docker Desktop → Railway Pro)

- **Dev:** Docker Desktop — `docker build` + `docker run` (or a small `compose.yaml`) so local dev mirrors prod exactly. The firewall **offline smoke test** (outbound-inventory TODO-4) runs as `docker run --network none` with `LLM_ENABLED=false`.
- **Deploy:** Railway (Pro), building from the Dockerfile (**not** Nixpacks — native OCR deps). Railway provides automatic HTTPS + public URL (FR-25 / D4) and env-var secrets (access token, `LLM_ENABLED`, `LLM_PROVIDER` / `LLM_BASE_URL` for the config-driven endpoint swap, TODO-7).
- **Outbound posture on Railway:** the deployed demo *does* reach cloud LLM APIs — this is the `models-internal-endpoint` stand-in literally executing; `LLM_ENABLED=false` demonstrates the zero-egress OCR-only configuration (FR-12).
- **Railway Pro headroom:** up to 32 vCPU / 32 GB per service makes a **locally-hosted small VLM deployable CPU-only in the live environment** — a deployed benchmark entry *and* the zero-egress model option (upgrades addendum A1's "stretch" local VLM to deployable). Pro also makes a second (worker) service affordable.
- **Background jobs:** in-process **APScheduler** in a single service (RQ/Redis would force a second service). A dedicated worker service is an option Pro makes affordable — but see the persistence fork: **a Railway Volume binds to one service, so splitting web/worker requires Postgres** (a shared SQLite volume across services is not possible).
- **Persistence (the pivotal fork — Step-4 Decision #1):** Railway's container FS is ephemeral.
  - **Option A — SQLite on a Railway Volume, single service:** simplest; demo-reset = restore the seeded DB file; docs are SQLite-first; pre-compute shares CPU with the web path (bounded concurrency). *Recommended for a single-user demo (pre-compute is bursty, the read path is just a DB read).*
  - **Option B — Railway managed Postgres + web/worker split:** hard-isolates pre-compute from the 5s read path (structural SM-1 guarantee); no ephemeral-FS issue; schema already portable; costs a second service (painless on Pro).
- Runtime-written **preprocessed images** persist to the Volume (Option A) or as DB blobs / object storage (Option B) — sub-decision carried with the fork.

**Decisions deferred to Step 4:** **SQLite-on-Volume + single service vs Postgres + web/worker split (Decision #1)**; Flask-vs-FastAPI (lean FastAPI); APScheduler-vs-RQ (lean APScheduler); preprocessed-image persistence; pytest + ruff test/lint setup; project structure.

**Note:** Dockerfile + project init should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (block implementation):**

- **D1 — Database & topology:** SQLite (file on a Railway Volume) in a **single Railway service** (web + in-process worker). *Chosen by Diane over Postgres/split — simplest, keeps local clone-and-run trivial (FR-26), demo-reset = restore seeded file; bursty single-user pre-compute makes CPU contention a non-issue.*
- **D2 — Web framework:** FastAPI 0.136.x (async background-job friendliness; Pydantic v2 validation bundled).
- **D3 — Background pipeline runtime:** in-process **APScheduler 3.11.x** sweeping `RECEIVED` submissions; OCR/LLM/analysis run as bounded-concurrency jobs so they never starve the read path.
- **D4 — Compliance engine:** Rulesets-as-data (per-Beverage-Type) executed by the determinism taxonomy (deterministic / field-match / hybrid / flag-only); CFR citations stored as data.

**Important Decisions (shape architecture):**

- **D5 — OCR extraction layer:** pluggable engines behind one **in-process uniform adapter interface** (`extract(image) -> {text, word_boxes, confidence, latency_ms, engine, version, ran_on_cpu}`); Tesseract + PaddleOCR ship, PP-OCRv5 optional. Extract to a localhost service only if justified later (matches `approach.md` §6).
- **D6 — LLM/extraction layer:** the *same* adapter pattern for models; provider SDKs (OpenAI/Gemini/Anthropic) + optional local VLM behind one interface; `models-internal-endpoint` classification; `LLM_ENABLED`/`LLM_BASE_URL` config-driven; LangChain for local-only tracing.
- **D7 — Persistence of derived artifacts:** preprocessed (OpenCV-enhanced) images written to the **Volume** as files, referenced by path in `label_images`; seeded fixture images baked into the Docker image (read-only, no upload).
- **D8 — Frontend:** server-rendered Jinja2 + USWDS components; **progressive-enhancement vanilla JS** only (image zoom/paging, Enhance toggle, checklist→card scroll, keyboard shortcuts) — no SPA, no build step, all assets vendored.

**Deferred Decisions (post-MVP / Phase 2):**

- Postgres migration + web/worker split (the SM-1 structural guarantee) — schema kept portable so it's a low-friction flip.
- Two-bucket triage queue (needs benchmark-calibration data).
- COLA API + integration; `llm_models` normalization; Alembic migrations.

### Data Architecture

- **Engine:** SQLite (Python stdlib `sqlite3`), file on a Railway Volume; schema per `docs/database-schema.md` (TEXT + CHECK enums, kept Postgres-portable).
- **Schema/seed:** plain SQL DDL + a Python seed script loading the fixture corpus + Ground Truth CSV (no ORM/migration framework for the POC; Alembic noted as scale path). 30–50 seeded Submissions; `label_images` child table (1–10).
- **Validation:** Pydantic v2 models at the API/read boundary; `field_comparisons`/`checklist_items` written by the analysis job.
- **Demo reset (FR-27):** transactional re-seed — restore seeded rows, clear `disposition`/`decided_at`, reset `status`, purge generated preprocessed images. Reachable without redeploy.
- **Concurrency note:** single-writer SQLite is fine for a single-user demo + one background worker; WAL mode enabled for read-during-write safety.

### Authentication & Security

- **Access:** single shared **token gate** (env `ACCESS_TOKEN`), checked in FastAPI middleware/dependency; clean denial with no data leakage (FR-25). No user accounts, roles, or IdP — explicitly out of scope.
- **Secrets:** Railway env vars (`ACCESS_TOKEN`, provider keys, `LLM_*`, `LANGCHAIN_*`); absent keys ⇒ model layer simply off (still functional, OCR-only).
- **Data:** no PII; dummy data only; read-only except Disposition capture + pipeline writes (NFR-3). Registry artwork private-fixtures-only.
- **HTTPS:** terminated by Railway automatically.

### API & Communication Patterns

- **Style:** primarily **server-rendered HTML routes** (`GET /queue`, `POST /next`, `GET /review/{id}`, `POST /review/{id}/disposition`, `GET /benchmark`, operator `POST /reset`, `POST /enqueue`). A few small read-only JSON endpoints only where progressive-enhancement JS needs them (e.g. live `N of M` checklist state).
- **Error handling:** honest per-component states surfaced in the UI (pipeline failure, LLM-unavailable degrade-to-OCR, save-failure-retains-work) per EXPERIENCE.md State Patterns — never a silent stall.
- **The 5s contract:** read routes do **only** a DB read of pre-computed rows; no inference, no OCR, no blocking on the model layer at request time.

### Frontend Architecture

- **Rendering:** Jinja2 templates + vendored USWDS 3.x (Header, Step Indicator, Alert, Tag, Accordion, Modal, Table, Form controls) with the Treasury brand layer + verdict/beverage domain tokens from DESIGN.md.
- **Interactivity:** vanilla JS, progressive enhancement — mouse path always sufficient (Dave gate), additive keyboard power path (Jenny); single-letter shortcuts inert in text inputs/modals (the load-bearing safety rule).
- **No build step:** assets served same-origin from `/static` (firewall + simplicity). Accessibility = USWDS AA baseline + the DESIGN.md domain-contrast table.

### Infrastructure & Deployment

- **Container:** single Dockerfile (native OCR deps + pinned weights + vendored USWDS + seeded fixtures baked in) — the offline-pinned artifact (resolves outbound-inventory TODO-2).
- **Dev:** Docker Desktop; offline smoke test = `docker run --network none` + `LLM_ENABLED=false` (zero-egress proof, FR-12 / TODO-4).
- **Deploy:** Railway Pro, single service, Dockerfile build (not Nixpacks); Volume for the SQLite file + generated images; automatic HTTPS + public URL.
- **Process model:** Uvicorn web + in-process APScheduler in one process/container; bounded job concurrency protects the read path. Local VLM (if enabled) runs CPU-only within Pro's vCPU/RAM headroom.
- **Logging/metrics:** `audit_events` timeline + `processing_ms`/latency columns are the lightweight metrics substrate; LangChain local-only tracing (toggleable, no egress).

### Decision Impact Analysis

**Implementation sequence:**

1. Dockerfile + project skeleton + SQLite schema/DDL + seed script (the "init" story).
2. Pre-compute pipeline: APScheduler sweep → OpenCV → OCR adapters → analysis/verdict roll-up → `READY_FOR_REVIEW`.
3. Compliance engine (deterministic Government Warning + field-match + format checks; spirits Ruleset first).
4. Read-path workspace UI (Next Submission, stacked comparison, checklist, disposition).
5. Model layer (LLM extraction/fallback, `models-internal-endpoint`, toggleable) + LangChain tracing.
6. Benchmark capture + Benchmark Report; demo reset + live enqueue.

**Cross-component dependencies:**

- D1 (SQLite/single-service) ⇒ in-process APScheduler (D3) and file-on-Volume image persistence (D7); rules out a worker split without a Postgres flip.
- D5/D6 uniform-adapter pattern ⇒ engine-agnostic `ocr_results`/`llm_results` schema (FR-11) and the swap-without-schema-change procurement requirement.
- The 5s contract constrains the API layer (D2) to pre-computed reads only — the pipeline (D3) owns all heavy work.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**~9 conflict points** where agents could diverge — most resolved by inheriting the existing schema; four are project-specific contracts that MUST be centralized in one module each.

### Naming Patterns

**Database (inherit `database-schema.md` exactly):**

- Tables: `snake_case`, **plural** (`submissions`, `label_images`, `ocr_results`, `field_comparisons`, `checklist_items`, `llm_results`, `audit_events`).
- Columns: `snake_case`; PK `id`; FK `<entity>_id`; timing columns suffixed `_ms` (INTEGER); timestamps `_at` (UTC ISO-8601).
- Enums: `UPPER_SNAKE` stored as `TEXT + CHECK` (no native enum) — values fixed and greppable.
- Indexes: `idx_<table>_<cols>`.
- **Stable identifiers:** `check_key` / `field_key` are `snake_case` and MUST resolve to an entry in `data-dictionary.md` (e.g. `government_warning`, `brand_name`, `net_contents_format`).
- **Provenance string:** `extracted_source` is exactly `ocr:<engine_name>` or `llm:<model_id>` (e.g. `ocr:paddleocr`, `llm:claude-opus-4-8`).
- **CFR citation:** `"27 CFR <part>.<section>"` (e.g. `27 CFR 16.21`).

**API routes:** lowercase, no trailing slash, `{id}` path params, HTTP verb carries the action (`GET /queue`, `POST /next`, `GET /review/{id}`, `POST /review/{id}/disposition`, `GET /benchmark`, `POST /reset`, `POST /enqueue`).

**Python code:** modules/functions/vars `snake_case`; classes `PascalCase`; constants `UPPER_SNAKE`; type hints required; formatted by **ruff** (lint + format), line length 100.

**Env/config:** `UPPER_SNAKE` (`ACCESS_TOKEN`, `LLM_ENABLED`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LANGCHAIN_TRACING_ENABLED`).

### Structure Patterns

- Tests in a top-level `tests/`, files `test_*.py` (pytest), mirroring the package layout.
- Source under one app package (`app/`) split by concern (web / pipeline / engine / adapters / db / benchmark) — full tree defined in Step 6.
- Static assets under `static/` (vendored USWDS in `static/uswds/`); templates under `templates/`.
- One module owns each centralized contract (below) — agents import it, never re-implement it.

### Format Patterns

- **JSON field naming: `snake_case`** everywhere (matches DB + Python — no camelCase boundary to translate).
- **Timestamps:** ISO-8601 UTC strings in JSON; stored as TIMESTAMP. Durations are integer milliseconds (`*_ms`).
- **Booleans:** real `true/false` in JSON (SQLite stores 0/1; the data layer converts).
- **Money:** `cost_usd` as a decimal/string (never float math on currency); token counts are integers.
- **Error responses (the few JSON endpoints):** `{ "error": { "code": "<snake_case>", "message": "<plain language>" } }`; user-facing copy follows EXPERIENCE.md voice.

### Communication Patterns

- **Lifecycle events:** `audit_events.event_type` is a fixed vocabulary (`SEEDED`/`OCR_STARTED`/`OCR_COMPLETED`/`ANALYSIS_COMPLETED`/`READY`/`OPENED`/`DECIDED`); `actor` is `system:<job>` or `Label Specialist`. The append-only `audit_events` timeline is the domain event log — **distinct from** application logging.
- **Status transitions:** only the pipeline jobs and the read path write `status`, in the fixed order `RECEIVED → PROCESSING → READY_FOR_REVIEW → IN_REVIEW → DECIDED`.

### Process Patterns

- **The 5s contract (inviolable):** read/render paths do a DB read only — never OCR, inference, or a model-layer call at request time. All heavy work is pre-computed by the pipeline.
- **Degrade, never block:** if the model layer is unreachable/off, affected checks fall back to OCR-only with a visible notice; the screen never blocks on an LLM call (FR-12).
- **Honest states, never silent:** pipeline failures land in a visible per-check error state; a save failure retains Notes + tick-state and stays on the page (EXPERIENCE.md State Patterns).
- **Logging:** structured (`logging`), levels used normally; secrets/keys never logged; tracing is LangChain local-only and toggleable (no egress).

### Centralized Contracts (the four that prevent real divergence)

These MUST each live in exactly one module and be imported everywhere:

1. **`OcrResult` / `LlmResult` adapter shape** — every OCR engine returns the identical structure `{engine_name, engine_version, text, word_boxes, confidence, latency_ms, ran_on_cpu, status}`; every model adapter returns `{model_name, model_id, model_full_id, provider, task, result_text, prompt_tokens, completion_tokens, total_tokens, latency_ms, requested_at, responded_at, status}`. Adding an engine/model = a new adapter, **no schema change** (FR-11).
2. **Field-match normalization** — one `normalize(value, field_key)` function fixes the order: trim → collapse internal whitespace → Unicode NFKC → casefold → curly→straight quotes → strip trailing punctuation; numeric fields (`alcohol_content`, `net_contents`) additionally parse to number+unit. All `field_comparisons` use it — this is what makes "STONE'S THROW" == "Stone's Throw" (SM-C2).
3. **Verdict roll-up (severity precedence)** — one `rollup(verdicts)` function: any `FAIL` ⇒ `FAIL`; else any `REVIEW`/can't-verify ⇒ `REVIEW`; else `PASS`. Used by both the engine (submission `engine_verdict`) and the UI (Suggested Alert) so they can never disagree.
4. **Verdict-vs-Disposition separation** — `engine_verdict ∈ {PASS, REVIEW, FAIL}` (advisory) and `disposition ∈ {APPROVED, NEEDS_CORRECTION, REJECTED}` (human) are different enums in different modules; **no function maps one to the other**, no verdict pre-selects a disposition. (The structural form of "recommend, don't decide.")

### Enforcement Guidelines

**All agents MUST:**

- Import the four centralized contracts above — never re-implement normalization, roll-up, or the adapter shapes inline.
- Never call OCR / a model / inference from a request-render path (the 5s contract).
- Never write code that derives, defaults, or colors a `disposition` from an `engine_verdict`.
- Keep CFR citations and check definitions as **data** (Ruleset rows), never hard-coded in check logic.
- Keep all assets same-origin/self-hosted; no CDN, no outbound call outside the configured model endpoint.

**Anti-patterns to reject in review:** camelCase JSON; a `verdict→disposition` mapping; per-engine bespoke result dicts; inline normalization; OCR/LLM on the read path; verdict colors on buttons or a pre-selected disposition; CFR text hard-coded in Python.

## Project Structure & Boundaries

### Complete Project Directory Structure

```
ttb-label-poc/
├── README.md                       # setup + run (D2 deliverable); links every docs/*.md
├── Dockerfile                      # the offline-pinned artifact (native deps + weights + assets + fixtures)
├── compose.yaml                    # local dev (single service; --network none for the egress smoke test)
├── requirements.txt                # pinned deps (TODO-LIC)
├── pyproject.toml                  # ruff + pytest config
├── .env.example                    # ACCESS_TOKEN, LLM_ENABLED, LLM_PROVIDER, LLM_BASE_URL, LANGCHAIN_*
├── railway.toml                    # Railway: Dockerfile build, Volume mount, healthcheck
├── docs/                           # existing planning + deliverable docs (unchanged)
├── app/
│   ├── main.py                     # FastAPI app factory; mounts routers, static, APScheduler startup
│   ├── config.py                   # env → typed Settings (Pydantic); LLM_ENABLED gate lives here
│   ├── contracts.py                # ★ OcrResult / LlmResult shapes (Step-5 contract #1)
│   ├── normalize.py                # ★ normalize(value, field_key) (Step-5 contract #2)
│   ├── verdict.py                  # ★ rollup(verdicts) severity precedence (Step-5 contract #3)
│   ├── web/                        # ── Feature 4.1 Review Workspace + 4.6 Demo Access (read path only)
│   │   ├── deps.py                 # token-gate dependency (FR-25); DB session
│   │   ├── routes_queue.py         # GET /queue, POST /next, POST /next?type= (FR-1, FR-2)
│   │   ├── routes_review.py        # GET /review/{id}, POST /review/{id}/disposition (FR-3–7, FR-6)
│   │   ├── routes_benchmark.py     # GET /benchmark (FR-23)
│   │   ├── routes_ops.py           # POST /reset, POST /enqueue (FR-27, FR-28)
│   │   └── routes_help.py          # GET /help (FR-8)
│   ├── db/                         # ── Feature 4.4 Mock COLA Database
│   │   ├── schema.sql              # DDL (database-schema.md); WAL pragma
│   │   ├── connection.py           # sqlite3 connection + row factory (snake_case)
│   │   ├── repositories.py         # read queries (next-submission, review bundle, benchmark rollups)
│   │   └── seed.py                 # seed + reset (FR-20, FR-27) from fixtures/ + Ground Truth CSV
│   ├── pipeline/                   # ── Feature 4.2 Pre-compute Pipeline (the 5s mechanism)
│   │   ├── scheduler.py            # APScheduler sweep of RECEIVED rows; bounded concurrency
│   │   ├── preprocess.py           # OpenCV deskew/perspective/glare/contrast (FR-10)
│   │   ├── run.py                  # orchestrates: preprocess → OCR → LLM → engine → rollup → READY
│   │   └── status.py               # status transitions + audit_events writes
│   ├── adapters/                   # ── pluggable extraction (Step-5 contract #1; FR-11, FR-12)
│   │   ├── ocr/
│   │   │   ├── base.py             # OcrEngine protocol → OcrResult
│   │   │   ├── tesseract.py
│   │   │   ├── paddleocr.py
│   │   │   └── ppocrv5.py          # optional
│   │   └── llm/
│   │       ├── base.py             # ModelAdapter protocol → LlmResult
│   │       ├── openai.py · google.py · anthropic.py   # models-internal-endpoint
│   │       └── local_vlm.py        # localhost; the zero-egress model option
│   ├── engine/                     # ── Feature 4.3 Compliance Engine (determinism taxonomy)
│   │   ├── rulesets/               # Rulesets-as-DATA (per Beverage Type; CFR citations as data)
│   │   │   ├── distilled_spirits.py · wine.py · malt_beverage.py
│   │   ├── checks/                 # check implementations by strategy
│   │   │   ├── government_warning.py   # deterministic, no LLM (FR-13)
│   │   │   ├── field_match.py          # uses normalize.py (FR-14)
│   │   │   ├── format_checks.py        # ABV/net-contents/standards-of-fill (FR-15)
│   │   │   ├── class_type.py           # hybrid, LLM capped at REVIEW (FR-16)
│   │   │   └── flag_only.py            # field-of-vision/font-size → REVIEW (FR-17)
│   │   └── run_checks.py           # executes ruleset → checklist_items + provenance (FR-18)
│   ├── benchmark/                  # ── Feature 4.5 Benchmark Harness (live-pipeline byproduct)
│   │   ├── scoring.py              # vs Ground Truth; CER + field-match (FR-21)
│   │   ├── cost.py                 # $/1,000 verifications (FR-22)
│   │   ├── report.py               # rollups for GET /benchmark (FR-23)
│   │   └── tracing.py              # LangChain local-only, toggleable (FR-24)
│   └── disposition.py              # disposition enum ONLY — no verdict mapping (Step-5 contract #4)
├── templates/                      # Jinja2 + USWDS markup (server-rendered)
│   ├── base.html · queue.html · review.html · benchmark.html · help.html · _field_card.html · _checklist.html
├── static/
│   ├── uswds/                      # vendored USWDS 3.x (css/js/fonts/img) — no CDN
│   └── js/ (app.js)                # progressive-enhancement vanilla JS (zoom, enhance toggle, shortcuts)
├── fixtures/                       # seeded label images + seed-template.csv (Ground Truth); baked into image
├── models/                         # pinned OCR/VLM weights (baked at build; no runtime download)
└── tests/
    ├── test_normalize.py · test_verdict.py            # the contracts
    ├── test_government_warning.py · test_field_match.py · test_format_checks.py
    ├── test_pipeline.py · test_repositories.py · test_token_gate.py
    └── fixtures/                                       # tiny test corpus + expected verdicts
```

### Architectural Boundaries

- **API boundary:** all routes behind the token-gate dependency (`web/deps.py`); read routes touch only `db/repositories.py` (the 5s contract — no pipeline/adapter imports on the request path).
- **Pipeline boundary:** `pipeline/` is the *only* writer of `ocr_results`, `llm_results`, `field_comparisons`, `checklist_items`, and `status`/`engine_verdict`. The web layer never invokes the pipeline synchronously (except `POST /enqueue`, which only *inserts a RECEIVED row*; the scheduler picks it up).
- **Adapter boundary:** `engine/` and `pipeline/` depend on the adapter *protocols* (`adapters/*/base.py`), never on a concrete engine/provider — swap = new file, no schema/caller change (FR-11).
- **Contract boundary:** `contracts.py` / `normalize.py` / `verdict.py` / `disposition.py` are imported, never duplicated. `disposition.py` has no dependency on `verdict.py` (structural verdict-vs-disposition separation).
- **Data boundary:** `db/` is the single data-access layer; no raw SQL outside it; SQLite file + generated images live on the Railway Volume.
- **External boundary:** the *only* off-host calls originate in `adapters/llm/{openai,google,anthropic}.py` (classified `models-internal-endpoint`); everything else is `none`/`local`. `LLM_ENABLED=false` disables that boundary entirely (zero-egress, FR-12).

### Requirements → Structure Mapping

| PRD Feature | Lives in |
|---|---|
| 4.1 Review Workspace (FR-1–8) | `app/web/` + `templates/` + `static/` |
| 4.2 Pre-compute Pipeline (FR-9–12) | `app/pipeline/` + `app/adapters/` |
| 4.3 Compliance Engine (FR-13–18) | `app/engine/` (+ `normalize.py`, `verdict.py`) |
| 4.4 Mock COLA DB & Corpus (FR-19–20) | `app/db/` + `fixtures/` |
| 4.5 Benchmark Harness (FR-21–24) | `app/benchmark/` |
| 4.6 Demo Access & Deliverables (FR-25–28) | `app/web/{deps,routes_ops,routes_help}.py` + `README.md` + `docs/` |

### Data Flow

`seed.py` inserts `RECEIVED` → APScheduler sweep (`scheduler.py`) → `preprocess.py` → OCR adapters → LLM adapters (if enabled) → `engine/run_checks.py` writes `field_comparisons` + `checklist_items` → `verdict.rollup` sets `engine_verdict` → `status = READY_FOR_REVIEW` + `audit_events`. Specialist `POST /next` → `repositories.py` DB read (<5s) → render → `POST /disposition` writes `disposition`/`decided_at`.

### Development Workflow

- **Dev:** `docker compose up` (single service, Volume-backed SQLite); egress smoke test `docker run --network none -e LLM_ENABLED=false`.
- **Build:** Dockerfile bakes weights + USWDS + fixtures (offline-pinned).
- **Deploy:** Railway Pro, Dockerfile build, Volume mounted, `.env` → Railway variables.

## Architecture Validation Results

### Coherence Validation ✅

- **Decision compatibility:** FastAPI 0.136.x + Pydantic v2 + APScheduler 3.11.x + SQLite (stdlib) + Jinja2 + USWDS 3.x are mutually compatible on Python 3.11; all verified current (June 2026). No contradictory decisions.
- **Pattern consistency:** snake_case spans DB ↔ Python ↔ JSON (no translation boundary); the four centralized contracts have single-owner modules; verdict-vs-disposition separation is enforced structurally (`disposition.py` independent of `verdict.py`).
- **Structure alignment:** the tree realizes every decision — read-path/pipeline/adapter/contract boundaries each have a physical location; the 5s contract is enforced by `web/` importing only `db/repositories.py`.

### Requirements Coverage Validation ✅

- **Functional (28/28):** every FR maps to a module (see Requirements→Structure table). Spot-checks: FR-1/9 → `pipeline` + `repositories`; FR-13 → `engine/checks/government_warning.py` (deterministic, no LLM); FR-11/12 → adapter protocols; FR-21–24 → `benchmark/`; FR-25/27/28 → `web/{deps,routes_ops}`.
- **Non-functional (6/6):** NFR-1 → pre-compute + read-only path; NFR-2 → `none`/`local`/`models-internal-endpoint` boundary + `LLM_ENABLED=false` zero-egress; NFR-3 → no PII, read-only except disposition/pipeline; NFR-4 → USWDS + DESIGN.md contrast table; NFR-5 → limitations documented beside capabilities; NFR-6 → structure + patterns + ruff/pytest.

### Implementation Readiness Validation ✅

- **Decisions:** critical decisions D1–D4 documented with pinned versions; topology fork resolved.
- **Structure:** complete tree, specific files, explicit boundaries.
- **Patterns:** naming/format/process patterns + four enforced contracts + an anti-pattern reject-list.

### Gap Analysis Results

**Critical gaps:** none.

**Important (address in the pipeline story, not blocking):**

- **FR-10 proof requires OCR on *both* image variants.** To show "preprocessed accuracy > original" in the benchmark, `pipeline/run.py` must run OCR on **both** the original and the OpenCV-enhanced image for the degraded-fixture subset (store both `ocr_results` rows). The current data flow OCRs the enhanced image only — added as an explicit pipeline requirement.

**Watch-items (handled by design; state plainly per NFR-5):**

- **5s budget under a pre-compute burst on a single service (D1).** Accepted trade-off: read path is a pure DB read; mitigation = bounded job concurrency + WAL. Escape hatch = the documented Postgres + worker-split flip. Validate with SM-1 measurement on Railway.
- **Bold/caps detection on the Government Warning header (FR-13).** Best-effort from images; reported as "not-verified," never a silent PASS — a documented limitation, not a defect.

**Nice-to-have (Phase 2):** two-bucket triage queue; `llm_models` normalization; Alembic migrations.

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed (the 5s contract + watch-item)

**Implementation Patterns**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION *(all 16 items confirmed; no critical gaps; the one important gap is folded into the pipeline story below)*

**Confidence Level:** High — most decisions were pre-grounded in a mature `docs/` set; this workflow locked the open forks (firewall posture, DB/topology, the four contracts) and reconciled the contradictions.

**Key strengths:** the 5s mechanism is structural, not hopeful; verdict-vs-disposition is enforced in code shape; engine-agnostic adapters deliver the procurement swap-without-schema-change; the Dockerfile *is* the offline-pinned compliance artifact.

**Areas for future enhancement:** Postgres + worker split (SM-1 hard guarantee); triage queue; broader fixture corpus; CER persistence.

### Implementation Handoff

**AI Agent Guidelines:** follow the decisions and the four centralized contracts exactly; never put OCR/inference on a read path; never map a verdict to a disposition; keep CFR rules as data; keep assets self-hosted.

**First Implementation Priority:** the "init" story — Dockerfile + project skeleton + `db/schema.sql` + `db/seed.py`, then the pre-compute pipeline (with the FR-10 both-variants OCR requirement baked in).
