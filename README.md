# TTB COLA Label Specialist — AI-Assisted Label Verification (Proof of Concept)

A proof-of-concept **Label Specialist workspace** for the U.S. Treasury TTB Certificate of Label
Approval (COLA) process. It pulls a submitted application and its label image(s) from a mock
COLA database, runs automated checks, and presents the Label Specialist with **advisory findings**
so they can review and decide faster.

> **Guiding principle — recommend, don't decide.** The software produces advisory verdicts
> (`PASS` / `REVIEW` / `FAIL`) per label element. The **human Label Specialist** reviews the
> findings and records the official disposition (**Approved / Needs Correction / Rejected**).
> The goal is to make the job faster and easier — never to make the decision.

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

- **Firewall-safe / local-first.** The deployed app makes **no outbound cloud API calls**
  (the TTB network blocks them). OCR runs locally (Tesseract + PaddleOCR); image enhancement
  is local (OpenCV); cloud LLMs are used **only** in a separate, offline benchmark harness.
  Proof: [`docs/outbound-calls-inventory.md`](docs/outbound-calls-inventory.md).
- **Speed via pre-compute.** OCR and analysis run in **background jobs on submission**, so the
  "Next Submission" screen loads instantly — addressing the abandoned 5–10-minute pilot the
  brief describes. See [`docs/approach.md`](docs/approach.md).
- **Deterministic where the law is exact.** The Government Warning is verified by exact text +
  formatting match (no LLM). See
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

## Sample data

- [`samples/`](samples/) — sample labels, `seed-template.csv` ground truth, and the
  label-sourcing guide.
- [`docs/batch-template.csv`](docs/batch-template.csv) — applicant-side batch-upload template.

## Setup & run

> ⚠️ **Status: planning phase.** The documentation and design are complete; application code is
> the next step. The commands below are the **intended** setup and will be finalized when the
> implementation lands (tracked as a `TODO` here and in [`docs/tools-used.md`](docs/tools-used.md)).

```bash
# (intended — pending implementation)
# 1. Create a virtual environment and install dependencies
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Initialize and seed the mock COLA database
python -m app.seed --from samples/seed-template.csv

# 3. Run the background OCR/analysis workers (pre-compute)
python -m app.worker

# 4. Start the web app
python -m app.server            # then open the printed local URL

# 5. (optional, offline) run the OCR/LLM benchmark harness
python -m benchmark.run --report
```

**Deployed demo:** the public URL will be gated by a **token** so only an evaluator — not the
public or bots — can access it (authentication is otherwise out of scope per the brief).

## USWDS compliance (summary)

This POC follows the **U.S. Web Design System**: USWDS components and design tokens (self-
hosted, no external CDN, keeping it firewall-safe), accessible color/typography for an older,
mixed-tech userbase, large-screen layouts (≥24″), and Section 508 / WCAG-aligned patterns.
Full statements in [`docs/ux-design-notes.md`](docs/ux-design-notes.md).

## License & data notice

Proof of concept for evaluation. Contains **no PII**. Any real COLA label artwork is the
property of the respective brand owners and is used only as private local test fixtures, never
redistributed; public-facing examples use synthetic labels.
