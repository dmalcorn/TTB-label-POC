# Outbound-Calls Inventory — TTB COLA Label Specialist POC

**Status:** Planning artifact (updated as components are built). LLM layer implemented in Story 2.5.
**Last updated:** 2026-06-13
**Audience:** TTB reviewers verifying firewall compliance; the POC engineering team.

---

## 1. Purpose

The deployed proof-of-concept models a TTB environment whose **firewall blocks outbound traffic
to *external* domains** but **hosts LLM endpoints *inside* the firewall**. This document exists so
a TTB reviewer can confirm, **at a glance**, how every component in the deployed app relates to
that boundary — and that the app needs **no firewall exceptions** beyond reaching the
(in-production, internal) model endpoints it is designed around.

This inventory is the documented "list of all outbound calls" requested in the discussion
register. See [`discussion-points.md` §3 Operating Constraints](../ref-docs/discussion-points.md)
("Produce a documented inventory of all outbound calls") and
[§6 OCR, LLM & Benchmarking Strategy](../ref-docs/discussion-points.md) (LangChain tracing is
local-only and toggleable; the LLM is optional).

**The firewall posture was revised by Diane during the PRD (2026-06-11)** — see
[PRD §10 NFR-2](../_bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/prd.md) and
[addendum A2](../_bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/addendum.md).
The original posture (brief + domain research's **"firewall fork"**) confined cloud models to an
offline, never-deployed harness. The **revised, canonical** posture is:

> The government hosts LLMs **inside** its firewall, so **LLM calls from the deployed POC are
> acceptable** — in production they would terminate at **internal endpoints**, not external APIs.
> The POC's cloud-API calls (OpenAI / Gemini / Anthropic) are therefore a **model of internal
> services**, not a firewall violation.

Every entry below is classified under the three categories NFR-2 mandates: **`none` / `local` /
`models-internal-endpoint`**.

> **One-line takeaway for a reviewer:** OCR, image preprocessing, the rules engine, the database,
> and tracing are all **local** (tracing never egresses telemetry). The **only** components that
> reach off-host are the **LLM extraction + benchmark calls**, classified
> **`models-internal-endpoint`** — in a real TTB deployment they terminate inside the firewall.
> Those LLM calls are **toggleable off**, and the resulting **OCR-only path is a fully zero-egress
> configuration** (FR-12) — the proof that the local-first core stands on its own.

---

## 2. Outbound-Call Inventory

Legend:
- **Classification** — `none` (no network at all), `local` (localhost / on-prem only), or
  `models-internal-endpoint` (reaches a model endpoint that, in production, lives inside the TTB
  firewall; the POC stands in for it with a cloud API).
- **In deployed request path?** — Does the component run as part of serving a live Label Specialist
  request (or its background pre-compute) in the deployed POC?

| Component | Classification | Destination | In deployed request path? | Notes |
|---|---|---|---|---|
| **Web UI / static assets** (HTML/CSS/JS, USWDS components, fonts, icons) | **`none`** *(self-hosted — see TODO-1)* | Served from the app server only | **Yes** | USWDS assets, fonts, and icons must be **bundled and self-hosted**, not pulled from a CDN. No third-party CDN, font host, analytics, or telemetry. See **TODO-1**. |
| **App server** (Python web service, e.g. FastAPI/Flask) | **`local`** | localhost / on-prem DB only | **Yes** | Listens for inbound requests; talks only to the local database, local OCR/processing, and the configured model endpoint(s). |
| **Tesseract OCR** (background job) | **`none`** | Local process / local model files | **Yes** | Runs fully on-prem as a local binary; language/model data files are installed locally. No network access. |
| **PaddleOCR** (background job; optional PP-OCRv5) | **`none`** | Local process / local model files | **Yes** (background pre-compute) | Model weights are **downloaded once at build/setup time, then pinned and shipped offline**. At runtime it loads local weights only. See **TODO-2**. |
| **OpenCV image enhancement** (deskew, perspective, glare/contrast) | **`none`** | Local process | **Yes** | Pure local CPU image processing (`cv2`). No model download, no network. _Source: research → Technical Trends → Image-Quality Remediation._ |
| **Database** (mock COLA DB; e.g. SQLite/PostgreSQL on-prem) | **`local`** | localhost / on-prem only | **Yes** | Stores submissions, OCR/LLM results, and timing/benchmark stats. Local connection only; no external replication or telemetry. |
| **LangChain tracing** (local, statistics only) | **`local`** *(local-only — TODO-3 RESOLVED, Story 5.1)* | Local trace sink (in-process record list + local log); durable record is the `llm_results` row | **Yes** (when enabled) | `app/benchmark/tracing.py` captures latency, model name/ID/full-ID, timestamps, and token counts to a **local-only sink** wrapped around each model call; the durable, queryable record stays the pipeline's `llm_results` row (no new schema). Runs with **local/offline tracing and no telemetry egress** — configures no LangSmith/cloud endpoint. **Toggleable off** via `LANGCHAIN_TRACING_ENABLED` (default off); disabled ⇒ no tracing code path executes. _Source: research → Technical Trends._ See **TODO-3 (RESOLVED)**. |
| **Local LLM** (optional; locally-hosted small VLM) | **`local`** | Local inference endpoint (localhost) | **Optional** | A locally-hosted model (e.g. Ollama/vLLM on localhost) — the zero-egress model option. Weights pinned/shipped offline like PaddleOCR. See **TODO-2**. |
| **LLM extraction + benchmark calls** (Gemini / OpenAI / Anthropic in the POC) | **`models-internal-endpoint`** | Provider APIs in the POC (e.g. `api.openai.com`, `generativelanguage.googleapis.com`, `api.anthropic.com`); **internal endpoints in production** | **Yes** *(toggleable off)* | The live pipeline runs LLM extraction and captures per-model benchmark stats (PRD §4.5). In a TTB deployment these resolve to **in-firewall endpoints**; the POC's cloud-API calls **model** them (PRD NFR-2 / addendum A2). **Toggle these off** and the pipeline completes on OCR-only — the zero-egress configuration (FR-12). API keys/base URLs are configuration, so production swaps cloud URLs for internal ones with no code change. See **TODO-7**. |

---

## 3. The Boundary: local-first core + internal-endpoint model layer

The compliance story is **not** "no outbound calls of any kind." It is a **two-layer** posture:

**A. Local-first core (always on, fully zero-egress):**
- Web UI + app server + local database.
- Local OCR: **Tesseract** and **PaddleOCR/PP-OCRv5**.
- Local **OpenCV** image enhancement.
- The deterministic **rules / compliance engine** (Government Warning, ABV format, standards of
  fill, etc.).
- **LangChain tracing in local-only mode** (toggleable; no telemetry egress).
- **Classification: `none` / `local`.** Nothing in this layer reaches off-host.

**B. Model layer (LLM extraction + benchmark capture — `models-internal-endpoint`):**
- Runs LLM-based field extraction and records per-model speed/accuracy/cost stats **in the live
  pre-compute pipeline** (the procurement study, PRD §4.5).
- In production these calls terminate at **internal endpoints inside the TTB firewall**; the POC
  uses cloud-provider APIs as a faithful **stand-in**, recorded as such.
- **Toggleable off by configuration.** With the model layer disabled, the app runs entirely on
  layer A — a provable **zero-egress, OCR-only** configuration (FR-12).

> **Boundary rule (the control that matters):** the **local-first core (layer A) is fully
> sufficient on its own.** The model layer is additive and configuration-gated — never a hard
> dependency. The demo includes at least one **LLM-toggled-off run** to prove the zero-egress
> configuration exists (PRD addendum A6). Endpoint URLs are configuration: production points them
> at internal services; the POC points them at cloud APIs that model those services.

---

## 4. How a Reviewer Can Verify

A reviewer (or auditor) can confirm the posture without reading the full codebase:

1. **Configuration flags (deployment ships these settings):**
   - `LLM_ENABLED` — the master switch for the model layer. With `LLM_ENABLED=false`, the app runs
     **OCR-only, zero-egress** (the provable local configuration; FR-12).
   - `LLM_PROVIDER` / `LLM_BASE_URL` — in production, point at the **internal** model endpoint; in
     the POC, the cloud-provider API that models it. Swapping environments is a config change, not
     a code change. See **TODO-7**.
   - `LANGCHAIN_TRACING_ENABLED=false` — the pinned master switch for tracing; with no LangSmith/
     cloud telemetry endpoint configured, **no trace data egresses**, ever (architecture.md
     Env/config, D6). See **TODO-3**.

2. **The zero-egress smoke test (the headline proof).** Run the deployed app with `LLM_ENABLED=false`
   and **outbound network access blocked at the host** (loopback-only). The full Label Specialist
   flow — load next submission, view OCR-extracted fields, run rule checks, record a disposition —
   must complete with **zero failed outbound connection attempts**. This proves the local-first
   core stands alone. See **TODO-4**.

3. **The internal-endpoint equivalence.** With the model layer enabled, confirm every off-host call
   targets **only** the configured model endpoint(s) — no other external domain. In production those
   endpoints are internal; in the POC they are the documented cloud-provider APIs and nothing else.

4. **Static assets are self-hosted.** Confirm the served HTML references only same-origin asset URLs
   (no `https://cdn.…`, no external font/icon hosts, no analytics scripts). See **TODO-1**.

5. **Tracing egress check:** with tracing configured per the deployed settings, capture outbound
   connections during a representative session; expect **none** to any telemetry/LangSmith domain.

---

## 5. TODO Markers (depend on final implementation)

- **TODO-1 — Self-host all USWDS / font / icon assets.** **Recommendation: do not load USWDS,
  Google Fonts, Font Awesome, or any asset from a CDN.** Bundle and self-host them with the app so
  the UI makes **zero** third-party requests. *(This is the most likely place an accidental
  outbound call would creep in — flag it during UI review.)*
- **TODO-2 — Pin and ship model weights offline (RESOLVED by the Dockerfile).** PaddleOCR (and any
  local VLM) typically download weights on first run. The Dockerfile bakes pinned OCR/VLM weights
  into the image at build time (`COPY models/ models/`), so the **runtime** never reaches the network
  for weights (architecture.md D7 / Infrastructure). Remaining: verify checksum/version pinning at the
  dependency-pinning step.
- **TODO-3 — Document the pinned LangChain local-only config (RESOLVED — Story 5.1).** The master
  off-switch `LANGCHAIN_TRACING_ENABLED` (default `false`) is wired and documented in `.env.example`
  / README; Story 2.5 added the `langchain` dependency but wired no tracing. **Story 5.1 lands the
  full local-only tracing harness in `app/benchmark/tracing.py`:** gated entirely on
  `LANGCHAIN_TRACING_ENABLED`, it captures per-call **model identity + timing + tokens** to a
  **local-only sink** (an in-process record list + the local structured log) wrapped around each
  model call; the durable, queryable record stays the `llm_results` row the pipeline writes
  (`langchain_trace_id` is not a POC column — data-dictionary §4, no new schema). It **configures no
  LangSmith/cloud trace endpoint** (no
  `LANGCHAIN_ENDPOINT`/`LANGSMITH_API_KEY` set) and opens no off-host connection — classified
  **`local`**, zero telemetry egress. When disabled, **no tracing code path executes** (LangChain is
  imported lazily inside the handler factory, never on the web import path) and the review workspace
  behaves identically. Documented in [`tools-used.md`](./tools-used.md). _(FR-24, NFR-2)_
- **TODO-4 — Add the zero-egress smoke test to the run instructions (RESOLVED — Story 2.5).** The
  README "Offline egress smoke test" section documents `docker run --network none -e
  LLM_ENABLED=false`; the model layer is never constructed under that flag (no SDK import, no
  client) and the seeded corpus reaches `READY_FOR_REVIEW` on OCR-only with zero outbound attempts.
  The offline test suite (`tests/test_llm_adapters.py`, `tests/test_pipeline.py`) enforces it: the
  factory constructs nothing when disabled, and off-host clients live only under `app/adapters/llm/`.
- **TODO-5 — Confirm DB deployment topology.** Verify the database is local/on-prem with no external
  replication, backup-to-cloud, or telemetry.
- **TODO-6 — Verify no implicit telemetry from dependencies.** Audit third-party libraries (e.g.
  update-checkers, usage analytics) for any default "phone-home" behavior and disable it.
- **TODO-7 — Record the cloud domains contacted (PARTIAL — Story 2.5).** The endpoint-swap mechanism
  is implemented: `LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_MODEL_ID` move provider config from cloud-API
  (POC) to internal endpoint (production) with no code change, and the only off-host clients in the app
  are constructed in `app/adapters/llm/{openai,google,anthropic}.py` (a structural test enforces it;
  `local_vlm.py` is the zero-egress localhost branch). Default cloud domains the POC contacts at
  runtime (when `LLM_ENABLED=true` and `LLM_BASE_URL` is unset): `api.openai.com` (openai),
  `api.anthropic.com` (anthropic), `generativelanguage.googleapis.com` (google). Remaining: capture an
  at-runtime connection log with the model layer enabled to confirm no other domain is contacted.

---

## 6. Related Documents

- [`approach.md`](./approach.md) — overall POC approach and the local-first architecture this
  inventory enforces.
- [`tools-used.md`](./tools-used.md) — the tool/library list (Tesseract, PaddleOCR, OpenCV,
  LangChain, LLMs) whose outbound behavior is itemized here.
- [`ocr-llm-benchmarking-plan.md`](./ocr-llm-benchmarking-plan.md) — the multi-OCR / multi-LLM
  benchmark that runs as a live-pipeline byproduct and produces the $/1,000-verifications figure.
- [`discussion-points.md`](../ref-docs/discussion-points.md) — §3 (firewall constraint + this
  inventory request) and §6 (LangChain local-only, optional LLM).
- [PRD §10 NFR-2](../_bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/prd.md) and
  [addendum A2](../_bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/addendum.md)
  — the **canonical, revised** firewall posture this inventory implements.
- [Domain research report](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
  — "Technical Trends" (the original firewall fork; LangChain local tracing). *Note: the research's
  "cloud = benchmark only" framing predates the NFR-2 revision; this inventory supersedes it.*
