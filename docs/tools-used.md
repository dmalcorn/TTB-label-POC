# Tools Used — TTB COLA Label Specialist POC

**Status:** Planning artifact (pre-implementation). Updated as components are built.
**Last updated:** 2026-06-11
**Audience:** TTB reviewers assessing the technology stack; the POC engineering team.

---

## 1. Purpose & guiding principles

This document records **every tool, library, framework, and service** the proof-of-concept
uses (or recommends), and for each one: **what it is**, **why it was chosen**, **how it is
used here**, its **license**, and — most importantly for this project — its
**local-vs-cloud / firewall status**.

Three project constraints shape every choice below. They come from
[`discussion-points.md` §3, §5, §6, §9](../ref-docs/discussion-points.md) and the
[domain research → Technical Trends](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md):

1. **Local-first.** The deployed app's core — OCR, image preprocessing, the rules engine, the
   database, and tracing — runs **fully local** (classified `none`/`local`), and tracing never
   egresses telemetry. The per-component proof lives in
   [`outbound-calls-inventory.md`](./outbound-calls-inventory.md).
2. **Internal-endpoint model layer (revised 2026-06-11).** The government hosts LLMs **inside**
   its firewall, so **LLM calls from the deployed POC are acceptable** — in production they
   terminate at internal endpoints, and the POC's cloud-API calls (OpenAI/Gemini/Anthropic) are a
   **stand-in** for them, classified `models-internal-endpoint` (PRD §10 NFR-2 / addendum A2).
   The model layer is **toggleable off**, leaving a provable **zero-egress, OCR-only**
   configuration (FR-12). *(This supersedes the original "firewall fork / cloud = offline harness
   only" framing from the brief and domain research.)*
3. **Recommend, don't decide blind.** Where a final implementation pick is still open, this
   doc gives a **recommendation** and marks it **TODO** rather than pretending it's settled.

> **Cross-links:** [`approach.md`](./approach.md) (overall architecture this stack serves) ·
> [`outbound-calls-inventory.md`](./outbound-calls-inventory.md) (firewall proof, per
> component) · [`ocr-llm-benchmarking-plan.md`](./ocr-llm-benchmarking-plan.md) (the in-pipeline
> multi-OCR/multi-LLM comparison). *Some sibling docs are planned per
> [`discussion-points.md` §14](../ref-docs/discussion-points.md); links resolve as they land.*

---

## 2. Summary table

| Tool / Library | Purpose | Local / Cloud | License |
|---|---|---|---|
| **Python 3.11+** | Primary language/runtime for app, OCR jobs, rules engine, benchmark harness | Local | PSF (permissive) |
| **Web/UI framework** *(TODO — recommend FastAPI + server-rendered Jinja2 templates)* | Serve the Label Specialist workspace UI + read APIs | Local | BSD/MIT-class |
| **USWDS** (U.S. Web Design System) | Federal design system — components, tokens, accessibility | Local (**self-hosted assets**) | Public domain / CC0-class (US Gov) |
| **SQLite** (POC) | Mock COLA database — submissions, OCR/LLM results, timing stats | Local | Public domain |
| **PostgreSQL** *(scale path, not POC)* | Production-scale database when POC graduates | Local / on-prem | PostgreSQL License (permissive) |
| **Tesseract OCR** | Local OCR engine #1 — fast, light, clean print | Local | Apache-2.0 |
| **PaddleOCR** (+ **PP-OCRv5**) | Local OCR engine #2 — accurate on degraded/curved/noisy labels | Local (weights pinned offline) | Apache-2.0 |
| **OpenCV** (`cv2`) | Image enhancement — deskew, perspective, glare, contrast | Local | Apache-2.0 |
| **LangChain** | Local tracing of OCR/LLM latencies & model IDs (**toggleable**) | Local (no telemetry egress) | MIT |
| **Local LLM fallback** *(optional; e.g. Ollama/vLLM + small VLM)* | Advisory fallback when OCR confidence is low | Local (localhost only) | Varies by model/runtime |
| **LLM/VLM set** (OpenAI / Gemini / Claude-class) | Live-pipeline field extraction + accuracy/speed/cost benchmarking | **`models-internal-endpoint`** — cloud API in the POC, internal endpoint in production; toggleable off | Proprietary APIs |
| **Background jobs/scheduler** *(TODO — recommend APScheduler or RQ for POC)* | Pre-compute OCR + rule analysis on submission | Local | MIT / BSD-class |
| **Token auth gate** *(lightweight)* | Protect the public demo URL from public/bots | Local | (app code) |

> License notes are the upstream project's published license at time of writing; **verify the
> exact license + version** during the dependency-pinning step (TODO-LIC). Model weights carry
> **their own** licenses, distinct from the framework that loads them.

---

## 3. Language & runtime — Python

**What it is.** Python 3.11+, the general-purpose interpreted language, is the runtime for the
web service, the OCR/analysis background jobs, the rules engine, and the benchmark
harness.

**Why chosen (Python over Bash).** [`discussion-points.md` §5](../ref-docs/discussion-points.md)
explicitly asks for a Python-vs-Bash recommendation. **Python is preferred** because:

- The entire OCR/vision/LLM ecosystem the POC depends on is Python-native — `pytesseract`,
  `paddleocr`, `opencv-python` (`cv2`), and `langchain` are all Python libraries. Bash would
  only shell out to them, losing structured data handling.
- The pipeline needs **structured data** (extracted fields, confidence scores, per-engine
  timings written to the DB). Python has first-class JSON/dataclass/DB support; Bash manipulates
  text streams and is brittle for structured records.
- **Cross-platform & testable.** Python runs identically on the dev machines (Windows here) and
  a Linux deployment target; it has real unit-testing, typing, and error handling. Bash scripts
  are OS-shell-dependent and hard to test.
- **Maintainability for a federal handoff.** Python is far more readable to a future team than
  chained shell pipelines — aligning with the procurement-informing secondary goal.

Bash remains fine for **thin operational glue** (a one-line launch script, a cron entry), but
**no business logic lives in Bash.**

**Firewall status.** **Local.** The interpreter and standard library make no outbound calls;
network behavior comes only from the libraries inventoried below.

**License.** Python Software Foundation License (permissive, GPL-compatible).

---

## 4. Web / UI framework — *TODO (recommendation below)*

**Recommendation (TODO-UI-1).** Use **FastAPI** (Python) for the app server + read APIs, with
**server-rendered HTML via Jinja2 templates** styled by **USWDS**. Rationale:

- Python-native (single language across the stack — see §3), async-capable, minimal, well
  documented.
- **Server-rendered HTML keeps the firewall surface tiny** — no heavy client-side SPA pulling
  packages/CDNs at runtime. The UI ships as same-origin HTML + self-hosted CSS/JS.
- Pairs cleanly with USWDS, which is framework-agnostic markup + CSS (§5).

*Flask is an acceptable lighter alternative if async isn't needed. **The exact framework is a
recommendation, not a locked decision — mark TODO-UI-1 until confirmed in
[`approach.md`](./approach.md).***

**How it's used here.** Serves the "Next Submission" review screen, the vertical
stacked field-comparison view, the checklist, and read-only APIs over the mock DB. No
write/upload flows in v1 (POC reads from the mock COLA DB —
[`discussion-points.md` §1](../ref-docs/discussion-points.md)).

**Firewall status.** **Local.** Listens for inbound requests; talks only to the local DB and
local OCR/processing components. See the App-server row in
[`outbound-calls-inventory.md` §2](./outbound-calls-inventory.md).

**License.** FastAPI = MIT; Jinja2 = BSD; Flask (alt) = BSD. All permissive.

---

## 5. UI design system — USWDS (self-hosted)

**What it is.** The **U.S. Web Design System** — the federal government's official library of
accessible, standards-based UI components, design tokens, and guidance.

**Why chosen.** [`discussion-points.md` §9](../ref-docs/discussion-points.md) calls for
referencing USWDS and reusing its components. It gives the POC a credible federal look-and-feel,
built-in **Section 508 / accessibility** alignment, and component patterns (buttons, step
indicators/chevrons, alerts for discrepancy highlighting) that match the UX asks (clean,
obvious, large-monitor, older-user-friendly).

**How it's used here.** USWDS components/tokens drive the review workspace: chevron-style
**step indicator** for process status, **alert/tag** styling to highlight OCR-vs-application
discrepancies, and accessible form/table styling for the stacked field comparison.

**Firewall status — IMPORTANT: self-hosted, no CDN.** USWDS CSS/JS, fonts, and icons **must be
bundled and self-hosted** with the app — **never** pulled from a CDN, Google Fonts, or an
external icon host. This is the single most likely place an accidental outbound call would creep
in. Tracked as **TODO-1** in
[`outbound-calls-inventory.md` §5](./outbound-calls-inventory.md) (self-host all assets; verify
the served HTML references only same-origin URLs).

**License.** USWDS is U.S. Government work — effectively **public domain (CC0-class)** for the
design system code; bundled fonts (e.g. Public Sans, Source Sans) carry their own **OFL/open**
licenses — confirm and ship them locally.

---

## 6. Database — SQLite (POC), PostgreSQL (scale path)

**What it is.** **SQLite** is a serverless, file-based, zero-configuration SQL database.
**PostgreSQL** is a full client-server RDBMS.

**Why SQLite for the POC.** The mock COLA database is a single-node, read-mostly fixture seeded
with dummy applications. SQLite needs **no server to install or administer**, ships as a single
file (easy to seed, version, and hand off), and is more than fast enough for a POC. It backs the
schema in [`database-schema.md`](./database-schema.md) — submissions, the 1–10 image child
table, OCR/LLM-extracted fields, dispositions, and the timing/benchmark stats
([`discussion-points.md` §4, §6](../ref-docs/discussion-points.md)).

**Why Postgres is the scale path (not the POC).** At production scale (concurrent Label Specialists,
larger queues, richer indexing/analytics on benchmark stats, real auth), **PostgreSQL** is the
recommended graduation target. The schema is written to be portable so the migration is
low-friction. *Marked as the documented scale path, not a POC dependency.*

**Firewall status.** **Local.** Local file (SQLite) or on-prem server (Postgres). No external
replication, cloud backup, or telemetry — see the DB row + **TODO-5** in
[`outbound-calls-inventory.md`](./outbound-calls-inventory.md).

**License.** SQLite = **public domain**. PostgreSQL = PostgreSQL License (permissive,
BSD/MIT-style).

---

## 7. OCR engines — Tesseract + PaddleOCR (+ PP-OCRv5)

Per [`discussion-points.md` §6](../ref-docs/discussion-points.md), the POC runs **two OCR
products, each in its own background job, with timing statistics** — deliberately **not**
committing to one engine, so the collected stats can inform future procurement. The research
[Technical Trends → OCR engine landscape](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
validates running both because their strengths are **complementary**.

### 7.1 Tesseract OCR

**What it is.** A mature, widely deployed open-source OCR engine (via the `pytesseract`
wrapper).

**Why chosen.** It is the **light/clean** half of the pair: **fastest on CPU-only**
(~0.77 s/doc), a tiny footprint (~10 MB binary — "runs on a Pi"), and **~95–99% accurate on
clean, high-quality printed labels**. Government workstations may be **CPU-only**
([`discussion-points.md` §3](../ref-docs/discussion-points.md)), which makes Tesseract's
CPU efficiency a direct fit.

**Tradeoff.** Accuracy **degrades sharply on hard inputs** — the research cites ~52.1% on curved
text and lower on noisy scans. That's exactly why it's paired with PaddleOCR rather than used
alone.

**How it's used here.** One of two parallel background OCR jobs per label image; emits extracted
text + per-engine latency into the DB for the benchmark comparison.

**Firewall status.** **Local.** Local binary + locally installed language/model data; **no
network access.**

**License.** **Apache-2.0** (engine). The `pytesseract` wrapper is Apache-2.0.

### 7.2 PaddleOCR (+ PP-OCRv5)

**What it is.** A deep-learning OCR toolkit (detection + recognition + optional layout/table
analysis). **PP-OCRv5** is a newer, ~5M-param specialized model in the same family.

**Why chosen.** It is the **accurate/complex** half of the pair. On the **degraded** images
Jenny Park described (glare, bad angle, curvature), it substantially outperforms Tesseract —
research cites ~88.7% vs ~52.1% on curved text, ~91.5% vs ~84.3% on noisy scans, and one 2025
study reporting **F1 0.938 (PaddleOCR) vs 0.797 (Tesseract)**. It uniquely ships built-in
layout/table analysis. **PP-OCRv5** reportedly **rivals billion-param VLMs on OCR while staying
local-friendly** — a strong candidate to add to the benchmark (TODO-OCR-1: evaluate PP-OCRv5
alongside the default PaddleOCR models).

**Tradeoff.** Its big speed advantage is **GPU-dependent** (~120 pages/min on an RTX 3090);
**GPU availability on government infra is uncertain**, so the POC must **benchmark CPU-mode too**
and not assume GPU throughput (research, Challenges & Risks).

**How it's used here.** The second parallel background OCR job per image; same uniform interface
and stats capture as Tesseract, enabling the head-to-head procurement comparison.

**Firewall status.** **Local — with one setup caveat.** PaddleOCR typically **downloads model
weights on first run**. To stay firewall-safe, weights are **downloaded once at build/setup
time, then pinned and shipped offline**; at runtime it loads local weights only and makes **no
outbound calls**. Tracked as **TODO-2** in
[`outbound-calls-inventory.md`](./outbound-calls-inventory.md).

**License.** **Apache-2.0** (toolkit). Bundled model weights carry their own license — confirm
during pinning.

---

## 8. Image processing — OpenCV (`cv2`)

**What it is.** OpenCV is the standard open-source computer-vision library (used via
`opencv-python` / `cv2`).

**Why chosen.** It directly answers Jenny Park's wish to **fix imperfect images (glare, bad
angle) without bouncing the submission back** — and the research confirms this is achievable with
**open-source, local, non-LLM** preprocessing, **no cloud call required**
([Technical Trends → Image-Quality Remediation](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)).

**How it's used here.** A cheap preprocessing stage **before** OCR that measurably lifts accuracy
on degraded labels:

- **Deskew** (detect skew angle → rotate),
- **Perspective correction** for off-angle photos,
- **Glare / uneven-lighting mitigation**,
- **Contrast** (CLAHE), grayscale, adaptive thresholding/binarization, denoising.

(*`unpaper` may complement it for scanned sheets — optional.*)

**Firewall status.** **Local.** Pure local CPU image processing; no model download, no network.

**License.** **Apache-2.0** (OpenCV 4.5+).

---

## 9. LLM tooling

This is where the firewall posture lives. There are **three distinct things** here, and they are
deliberately kept apart. Per the revised posture (PRD §10 NFR-2 / addendum A2): tracing is
**local-only**; an optional **local** VLM is the zero-egress model option; and the **provider
LLMs** run in the live pipeline classified `models-internal-endpoint` (cloud API in the POC,
internal endpoint in production), **toggleable off** to leave a zero-egress OCR-only path.

### 9.1 LangChain — local tracing only (toggleable)

**What it is.** LangChain is a Python framework for building LLM applications; the POC uses
**only its tracing/observability** capability.

**Why chosen.** [`discussion-points.md` §6](../ref-docs/discussion-points.md) calls for using
LangChain to **trace latencies/timings**, while documenting that it is **included for its
benefits but easy to turn off** and **used only for gathering statistics**. It gives a uniform
way to capture **model name, model ID, full model ID, timestamps, and latencies** into the DB
(feeding the cost analysis and the OCR/LLM benchmark).

**How it's used here.** Implemented in **`app/benchmark/tracing.py`** (Story 5.1). It captures
per-call **model identity (name / ID / full ID), timestamps, latency, and token counts** to a
**local-only sink** — an in-process record list plus the local structured log — wrapped around each
model call. The **durable, queryable record stays the `llm_results` row** that the pipeline already
writes; the tracer is the toggleable local-only instrumentation envelope on top of it, adding **no**
schema (`langchain_trace_id` is **not** a POC column — see
[`data-dictionary.md` §4](./data-dictionary.md)). The whole module is **gated on the
master off-switch `LANGCHAIN_TRACING_ENABLED`** (default `false`): when off, no tracing code path
executes (LangChain is imported lazily inside the handler factory, never on the web import path) and
the review workspace behaves identically; when on, capture is **identity + timing + tokens only** —
never the prompt, label-image bytes, OCR text, or any secret. Run in **local/offline mode only**.

**Firewall status — local, with hard guardrails.** LangChain can phone home to **LangSmith**
cloud tracing; that is **disabled**. `app/benchmark/tracing.py` **configures no LangSmith/cloud
trace endpoint** — it never sets `LANGCHAIN_ENDPOINT` / `LANGCHAIN_TRACING_V2` / `LANGSMITH_API_KEY`
and opens no off-host connection — so tracing runs **local-only with no telemetry egress**, even
when enabled. The **master off-switch** is `LANGCHAIN_TRACING_ENABLED` (default `false`); see
**TODO-3 (RESOLVED)** in [`outbound-calls-inventory.md` §5](./outbound-calls-inventory.md).

**License.** **MIT.**

### 9.2 Optional local LLM (the zero-egress model option)

**What it is.** An optional, **locally-hosted small VLM** — served from a local inference runtime
(e.g. **Ollama** or **vLLM**) on localhost — used both as an OCR-fallback and as the model
configuration that keeps the whole app zero-egress when no internal endpoint is reachable.

**Why chosen.** [`discussion-points.md` §6](../ref-docs/discussion-points.md) makes the LLM
**optional**: used in the POC and as a **fallback when OCR isn't producing good matches**. The
research's "hybrid pipeline" outlook (classical OCR for the clean 90%, a small local VLM for the
degraded long tail) is a natural fit. Capable sub-1B/small open models (GLM-OCR ~0.9B, dots.ocr,
Qwen3-VL small) now run locally at near-zero inference cost.

**How it's used here.** **Off by default.** When enabled, it only runs on **low-confidence OCR
results**, as **advisory** input. **Rule-bound checks stay deterministic** (Government Warning,
ABV format, standards of fill) — the LLM never overrides them; it only assists ambiguous reads.

**Firewall status.** **Local — localhost only.** A locally-hosted model (localhost inference
endpoint) reaches no external domain. Weights pinned and shipped offline like PaddleOCR
(**TODO-2**). It is the model configuration that keeps the deployed app fully zero-egress;
`provider=local` is verified per [`outbound-calls-inventory.md` §4](./outbound-calls-inventory.md).

**License.** Runtime: Ollama (MIT), vLLM (Apache-2.0). **Model weights carry their own licenses**
— confirm per chosen model (TODO-LLM-1).

### 9.3 Provider LLM/VLM set — live-pipeline extraction + benchmarking (`models-internal-endpoint`)

**What it is.** A set of **frontier provider models** (OpenAI / Gemini / Claude-class, and capable
open models) that run field extraction and produce accuracy/speed/cost comparisons over the **same**
extraction tasks.

**Why chosen.** The brief and [`discussion-points.md` §6](../ref-docs/discussion-points.md) ask
for **benchmark data on multiple OCRs and multiple LLMs** plus a **cost analysis ($/1,000
verifications)** to inform future procurement. The research shows VLMs lead on hard documents
(~3–4× lower CER on noisy inputs) — so the comparison is genuinely informative.

**How it's used here.** In the **live pre-compute pipeline**: every Submission flows through the
configured models for extraction and benchmark-stat capture (PRD §4.5). It records model name,
full model ID, tokens, latency, and price so a true $/1,000 figure falls out of recorded data —
see [`ocr-llm-benchmarking-plan.md`](./ocr-llm-benchmarking-plan.md).

**Firewall status — `models-internal-endpoint`; toggleable off.** Per the revised posture (PRD §10
NFR-2 / addendum A2), these LLM calls are **permitted in the deployed path**: in production they
terminate at **internal endpoints inside the TTB firewall**, and the POC's calls to
`api.openai.com` / `generativelanguage.googleapis.com` / `api.anthropic.com` are a documented
**stand-in** for them. Endpoint URLs are configuration (TODO-7), so production swaps cloud for
internal with no code change. The whole model layer is **toggleable off** (`LLM_ENABLED=false`),
leaving the provable **zero-egress OCR-only** configuration (FR-12). See the
`models-internal-endpoint` row + the two-layer boundary in
[`outbound-calls-inventory.md` §2–§3](./outbound-calls-inventory.md).

**License.** Proprietary provider APIs (commercial terms, paid). Open comparators carry their
own licenses.

---

## 10. Background jobs / scheduler — *TODO (recommendation below)*

**What it does.** The **pre-compute strategy** is the centerpiece
([`discussion-points.md` §5](../ref-docs/discussion-points.md)): a background pipeline steps
through newly-submitted records, triggers OCR (Tesseract + PaddleOCR in parallel), stores the
results, runs the advisory rule analysis — so that when a Label Specialist clicks **"Next
Submission,"** the screen loads **instantly**.

**Recommendation (TODO-JOB-1).** For the POC, keep it **simple and local**:

- **APScheduler** (in-process scheduler) for a periodic batch sweep of new submissions — minimal,
  no extra services, ideal for a single-node POC; **or**
- **RQ (Redis Queue)** if true parallel worker processes are wanted for the per-image OCR jobs
  (adds a local Redis dependency).

**Recommendation:** start with **APScheduler** for the POC (fewest moving parts, no extra
service); note **RQ/Celery** as the scale path when concurrency grows. *Marked TODO until
confirmed in [`approach.md`](./approach.md).* Heavyweight workflow/state-machine engines are
**out of scope** (resolved in `discussion-points.md` §5 — minimal status enum + timestamps only).

**Firewall status.** **Local.** In-process (APScheduler) or local Redis (RQ) — no external
service.

**License.** APScheduler = MIT; RQ = BSD; Redis = (local) BSD/RSALv2 depending on version
(confirm if used).

---

## 11. Auth — token gate for the public demo URL

**What it is.** A lightweight **token-based gate** in front of the deployed demo URL.

**Why chosen.** [`discussion-points.md` §3](../ref-docs/discussion-points.md) states
**authentication is explicitly NOT a POC feature** (per the brief). But because the POC is
deployed at a **public URL**, a minimal token gate is needed so **only an evaluator** — not the
public or bots — can interact with it. This is purely demo-URL protection, **not** an attempt to
model real COLA authentication (which would be a phase-two concern).

**How it's used here.** A shared secret token (e.g. a query param or header / simple
bearer-style check) required to reach the app; documented for the evaluator. **No user accounts,
roles, or identity provider** — those are deliberately absent in the POC.

**Firewall status.** **Local.** Validated in-app against a configured secret; no external identity
provider, no outbound call.

**License.** Implemented in app code (no third-party auth service).

---

## 12. Open TODOs (implementation picks still to confirm)

- **TODO-UI-1** — Confirm the web/UI framework (**recommended: FastAPI + Jinja2 + USWDS**).
- **TODO-1** *(in inventory)* — **Self-host all USWDS/font/icon assets** (no CDN). Highest-risk
  accidental-outbound spot.
- **TODO-2** *(in inventory)* — **Pin & ship PaddleOCR / local-VLM weights offline** so runtime
  never reaches the network.
- **TODO-3** *(in inventory)* — **RESOLVED (Story 5.1).** LangChain local-only tracing implemented
  in `app/benchmark/tracing.py`; master off-switch `LANGCHAIN_TRACING_ENABLED` (default `false`); no
  LangSmith/cloud endpoint configured; identity + timing + tokens captured to the local DB only.
- **TODO-OCR-1** — Evaluate **PP-OCRv5** alongside default PaddleOCR models in the benchmark.
- **TODO-JOB-1** — Confirm the **scheduler** (recommended: APScheduler for POC).
- **TODO-LLM-1** — Pick the **local fallback model** + confirm its weight license.
- **TODO-LIC** — Pin dependency versions and **verify each license** at build time.

---

## 13. Related documents

- [`approach.md`](./approach.md) — overall POC approach / local-first architecture this stack
  serves. *(Planned sibling doc.)*
- [`outbound-calls-inventory.md`](./outbound-calls-inventory.md) — per-component firewall proof;
  the authoritative source for outbound-call status referenced throughout this doc.
- [`ocr-llm-benchmarking-plan.md`](./ocr-llm-benchmarking-plan.md) — the multi-OCR/multi-LLM
  benchmark (a live-pipeline byproduct) and the $/1,000-verifications cost analysis.
- [`database-schema.md`](./database-schema.md) — the mock COLA schema (submissions, OCR/LLM
  results, timing stats) this stack reads/writes.
- [`discussion-points.md`](../ref-docs/discussion-points.md) — §3 (firewall, auth), §5 (Python
  vs Bash, pre-compute), §6 (OCR/LLM/LangChain), §9 (USWDS/UI).
- [Domain research report](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
  — Technical Trends (PaddleOCR-vs-Tesseract data, VLM landscape, OpenCV, the firewall fork).
  *Its "deployed = 100% local; cloud VLMs = benchmark only" recommendation predates the NFR-2
  revision (PRD addendum A2) — the deployed path now permits LLM calls as `models-internal-endpoint`.*
