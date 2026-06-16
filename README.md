# TTB COLA Label Specialist — AI-Assisted Label Verification (Proof of Concept)

A proof-of-concept **Label Specialist workspace** for the U.S. Treasury TTB Certificate of Label
Approval (COLA) process. It pulls a submitted application and its label image(s) from a mock
COLA database, runs automated checks, and presents the Label Specialist with **advisory findings**
so they can review and decide faster.

> **Guiding principle — recommend, don't decide.** The software produces advisory verdicts
> (`PASS` / `REVIEW` / `FAIL`) per label element. The **human Label Specialist** reviews the
> findings and records the official disposition (**Approved / Needs Correction / Rejected**).
> The goal is to make the job faster and easier — never to make the decision.

> **Try it live:** **<https://ttb-label-poc-production.up.railway.app>** (no login — the demo's
> token gate is open). Every review screen reads each label element **two ways — by OCR and by an
> AI vision model — side by side**, so the specialist sees exactly what each method found and where
> they agree. The review page loads in ~0.15 s (the brief's 5-second contract, with a 25× margin).

## What this is (and isn't)

- **Is:** the **federal reviewer's** side of COLA review — a workspace that doesn't publicly
  exist today. It reads from a mock COLA DB and assists the Label Specialist.
- **Isn't:** the applicant's filing system (that's **COLAs Online**, already in production —
  see [`docs/applicant-workflow-distilled-spirits.md`](docs/applicant-workflow-distilled-spirits.md)),
  and it does **not** make the approval decision itself.

**Scope:** all three beverage types are first-class — distilled spirits (27 CFR Part 5), wine
(Part 4), and malt beverages/beer (Part 7), plus the Part 16 health warning that applies to
all. Each has its own review ruleset
([spirits](docs/regulatory-rules-distilled-spirits.md) ·
[wine](docs/regulatory-rules-wine.md) · [beer](docs/regulatory-rules-beer.md)); distilled
spirits is the most fully worked example.

## Goals

1. **Primary** — complete the take-home and demonstrate writing working, AI-assisted code.
2. **Secondary** — produce information that could inform a future TTB software project,
   including procurement decisions (e.g., which OCR/LLM performs best).

See [`docs/requirements-mapping.md`](docs/requirements-mapping.md) for the full mandatory-vs-
above-and-beyond breakdown.

## Key design decisions

- **Two readings of every label — OCR and AI, side by side.** Each label image is read
  independently by the **OCR engines** (Tesseract + PaddleOCR) **and** by an **AI vision model**
  (OpenAI `gpt-4o-mini`). Every comparison card shows an *On label (OCR)* row **and** an
  *On label (AI)* row, and the per-element verdict is **agreement-based**: both sources agree with
  the application ⇒ **PASS**; they conflict (or only one is confident) ⇒ **REVIEW**; both disagree
  ⇒ **FAIL**. The AI reads the **image only** — OCR text is never fed to the model — so the two are
  a genuine cross-check, and either source can be toggled off. At ~**$0.01 per label**
  (`gpt-4o-mini`), the AI reading is essentially free at TTB's volume.
- **Firewall-safe / local-first.** OCR, image enhancement (OpenCV), the rules engine, and tracing
  run **locally, with no telemetry egress**. The AI reading is an **optional enhancement**: with
  `LLM_ENABLED=false` the model layer is never constructed — a provable **zero-egress, OCR-only**
  configuration that runs entirely behind the TTB firewall. In production `LLM_BASE_URL` points the
  model layer at an **in-firewall endpoint** (no code change); the deployed demo uses OpenAI's cloud
  as a stand-in to showcase the feature. Every call is classified
  `none` / `local` / `models-internal-endpoint` in
  [`docs/outbound-calls-inventory.md`](docs/outbound-calls-inventory.md).
- **Speed via pre-compute.** OCR and analysis run in **background jobs on submission**, so the
  review screen loads instantly (~0.15 s measured on the deployed demo) — addressing the abandoned
  5–10-minute pilot the brief describes. See [`docs/approach.md`](docs/approach.md).
- **Deterministic where the law is exact.** The Government Warning is verified by exact §16.21 text
  + formatting match — no model opinion drives that verdict. The AI's role here is only to *read*
  the warning verbatim (a clean second pair of eyes where OCR garbles small back-label print); the
  match itself stays deterministic. See
  [`docs/regulatory-rules-distilled-spirits.md`](docs/regulatory-rules-distilled-spirits.md).
- **Font/dimension size is not checked** — it can't be measured reliably from a photo, and
  this matches TTB's own COLAs Online disclaimer.
- **Accessible, federal UI.** Built to **USWDS** standards (self-hosted assets, no CDN),
  designed for a clean, "no hunting for buttons" experience on large monitors. See
  [`docs/ux-design-notes.md`](docs/ux-design-notes.md).
- **Data:** seeded dummy applications only; **no PII**; label artwork is brand IP → used as
  **private test fixtures only**.

## Documentation

Full index: **[`docs/index.md`](docs/index.md)**. The brief's required docs:

| Doc | Purpose |
|---|---|
| [`docs/approach.md`](docs/approach.md) | Architecture, pre-compute pipeline, verification engine, phasing |
| [`docs/tools-used.md`](docs/tools-used.md) | Every tool/library, rationale, local-vs-cloud status |
| [`docs/assumptions.md`](docs/assumptions.md) | A1–A29 assumptions the design rests on |
| [`docs/tradeoffs-and-limitations.md`](docs/tradeoffs-and-limitations.md) | Design trade-offs and honest limitations |
| [`docs/presearch.md`](docs/presearch.md) | Reference materials, comparable software, test data, common errors |

Plus: [regulatory rules](docs/regulatory-rules-distilled-spirits.md),
[label requirements by type](docs/label-requirements-by-type.md),
[database schema](docs/database-schema.md), [data dictionary](docs/data-dictionary.md),
[OCR/LLM benchmarking plan](docs/ocr-llm-benchmarking-plan.md),
[image handling](docs/image-handling.md), and the
[applicant workflow](docs/applicant-workflow-distilled-spirits.md).

**Architecture decision record (source of authority for stack & deployment):**
[`_bmad-output/planning-artifacts/architecture.md`](_bmad-output/planning-artifacts/architecture.md)
— the locked technical decisions (D1–D8: FastAPI + SQLite on Railway, the pre-compute pipeline,
the engine-agnostic adapters, and the four centralized contracts). The `docs/` set above remains
the authoritative source for the data model and rulesets; the architecture record references them.

## Sample data

- [`samples/`](samples/) — sample labels, `seed-template.csv` ground truth, and the
  label-sourcing guide.
- [`docs/batch-template.csv`](docs/batch-template.csv) — applicant-side batch-upload template.

## Setup & run

Everything runs in **Docker** — the same offline-pinned image locally and on Railway. You
need only **Docker Desktop** and a clone of this repo.

### Run locally (`docker compose`)

```bash
# 1. Configure the environment (every var is optional — see .env.example)
cp .env.example .env          # then set ACCESS_TOKEN to a value of your choice

# 2. Build and start the single service
docker compose up --build     # serves http://localhost:8000
```

> **Heads-up:** the *first* build takes ~10–20 minutes — it installs the native OCR stack
> (Tesseract, OpenCV) and bakes the pinned PaddleOCR weights into the image so the runtime
> never downloads them (the firewall-safe guarantee). It's a one-time cost; later starts are
> seconds. To skip the build entirely, just use the deployed URL.

Open <http://localhost:8000>. With `ACCESS_TOKEN` set you'll meet the **token gate** — enter
the same value at `/access` to reach the app. With `ACCESS_TOKEN` empty/unset the gate is
disabled (clone-and-run convenience).

**Seeding is automatic.** On startup the app creates the SQLite schema and, *only if the
database is empty*, loads the seeded mock-COLA corpus from the baked-in `fixtures/` — **15 real
records harvested from the public COLA registry** (5 each across wine, malt, and spirits) with
their real label images, including one record with an intentionally engineered ABV mismatch to
demonstrate a `FAIL`. A populated database is never re-seeded. To (re)seed manually:

```bash
docker compose run --rm web python -m app.db.seed
```

### Offline egress smoke test (NFR-2 / FR-12)

Proves the **zero-egress, OCR-only** configuration — build the image, then run it with **no
network** and confirm it boots, serves, *and* pre-computes the seeded corpus end-to-end:

```bash
docker build -t ttb-label-poc .
docker run --rm --network none -e LLM_ENABLED=false -e ACCESS_TOKEN=demo \
  -p 8000:8000 ttb-label-poc
# in another shell:  curl -fsS http://localhost:8000/healthz   ->  {"status":"ok"}
```

`--network none` strips all connectivity. With `LLM_ENABLED=false` the model layer is **never
constructed** — no provider SDK is imported and no client is built (Story 2.5) — so the
background sweep runs preprocess + Tesseract + PaddleOCR locally and every seeded submission
reaches `READY_FOR_REVIEW` on **OCR-only** results, with **zero** failed outbound connection
attempts. A clean boot, `200 /healthz`, and the whole corpus advancing to `READY_FOR_REVIEW`
together are the proof that the local-first core stands alone (the only off-host calls in the
app live in `app/adapters/llm/{openai,google,anthropic}.py`, gated entirely by `LLM_ENABLED`).

### Deploy (Railway)

The demo runs as a **single Railway service** built from this **Dockerfile** (not Nixpacks),
with **automatic HTTPS** on a public URL sitting behind the token gate. A **Railway Volume**
mounted at `/data` holds the SQLite file and generated images so data survives redeploys
(Railway's container filesystem is ephemeral); `DATABASE_PATH=/data/app.db` points the app at
it and the seed-if-empty startup fills a fresh Volume. `railway.toml` pins the build/deploy
contract; the operational playbook — service identity, env vars, Volume creation, CLI quirks —
is in **[`docs/railway-deployment.md`](docs/railway-deployment.md)**.

The live demo is at **<https://ttb-label-poc-production.up.railway.app>** and **runs with the AI
reading ON** (`LLM_ENABLED=true`, `gpt-4o-mini`) so evaluators see the OCR-vs-AI cards — the cloud
API standing in for an in-firewall endpoint.

Runtime configuration is entirely env-driven (`.env.example` documents every variable):
`ACCESS_TOKEN`, `LLM_ENABLED`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL_ID`,
`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` (only the selected provider's is
needed), `LANGCHAIN_TRACING_ENABLED`, `DATABASE_PATH`, and the read-source toggles
`OCR_ENABLED` / `OCR_ENGINES` / `OCR_PREPROCESS_VARIANTS`. Absent keys leave features off — the
OCR-only path stays fully functional, and with **both** OCR and the AI on, each card shows both
rows. `LLM_ENABLED=false` is the provable zero-egress configuration; production swaps the cloud
API for an in-firewall endpoint via `LLM_BASE_URL` with no code change.

> The full `docs/` deliverable set is delivered and indexed at
> **[`docs/index.md`](docs/index.md)** (linked under [Documentation](#documentation) above) —
> approach, tools used, assumptions, trade-offs/limitations, pre-search, the data dictionary, the
> three per-type rulesets, the landscape/COLAs-Online workflow narrative, the outbound-call
> inventory, and the USWDS-compliance notes — so an evaluator can set up, run, and trust the POC
> from this repo alone.

## USWDS compliance (summary)

This POC follows the **U.S. Web Design System**: USWDS components and design tokens (self-
hosted, no external CDN, keeping it firewall-safe), accessible color/typography for an older,
mixed-tech userbase, large-screen layouts (≥24″), and Section 508 / WCAG-aligned patterns.
Full statements in [`docs/ux-design-notes.md`](docs/ux-design-notes.md).

## License & data notice

Proof of concept for evaluation. Contains **no PII**. Any real COLA label artwork is the
property of the respective brand owners and is used only as private local test fixtures, never
redistributed; public-facing examples use synthetic labels.
