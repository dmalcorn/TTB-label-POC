# Discussion Points & Decisions — TTB COLA Label Specialist POC

*Polished, grouped, and categorized from the original `points-of-discussion.txt`
brain-dump. This is the working register of decisions, requests, and open questions
for the proof-of-concept. Every point from the original notes is preserved here —
consolidated so each topic appears once with its current status.*

**Author:** Diane · **Last organized:** 2026-06-11 (by Mary, Business Analyst)

---

## Legend

| Tag | Meaning |
|---|---|
| **[DECISION]** | A design decision has been made — carry it into the PRD / architecture / specs. |
| **[REQUEST]** | A deliverable or action to produce (research, document, code, analysis). |
| **[OPEN]** | An open question still needing analysis, an answer, or a decision. |
| **[RESOLVED]** | Already answered — pointer to where the answer lives. |

**Key reference artifacts** (where answers already exist):
- `ref-docs/TTB-take-home-instructions.md` — the take-home brief & stakeholder interviews.
- `ref-docs/Research-Findings.md` — first-pass answers to many points below (CFR rules, dispositions, image mechanics, comparable software).
- `_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md` — the domain research report (scale, solution landscape, regulatory ruleset, OCR/LLM tech).
- `ref-docs/ds-labeling-checklist.pdf` — TTB's own distilled-spirits mandatory-label checklist (authoritative ruleset).

> **Reconciliation note:** The original notes' closing section marked several `docs/*.md`
> files (e.g. `presearch.md`, `approach.md`, `assumptions.md`) as "written." The `docs/`
> folder now **exists on disk** with the full doc set — those deliverables have been
> created (captured under **§14 Deliverables**). The cited `Research-Findings.md` and the
> domain research report also exist.

---

## 1. Purpose, Goals & Scope

- **[DECISION]** This project is a **proof of concept** for the **Label Specialist's**
  (federal reviewer's) side of the COLA process: pull application + label data from a
  database and present it to the Label Specialist in a user-friendly way, with as much
  automated assistance as possible, and capture their reviewed decisions.
- **[DECISION]** **Primary goal:** complete the take-home as a job application and
  demonstrate the ability to write working code using AI.
- **[DECISION]** **Secondary goal:** produce valuable information that could inform a
  future software project (including procurement/purchase decisions), as the brief invites.
  → *Confirm with analysis whether these are the two main goals or if a third exists.*
- **[DECISION]** **v1 scope excludes** image upload and field data-entry — the POC only
  *reads* from the (mock) COLA database and displays/assists. Capturing new applications
  is not the intent of the POC.
- **[REQUEST]** Review the brief and produce **two requirement sets**: (a) the absolutely
  **mandatory** take-home requirements and what must be delivered, and (b) the
  **above-and-beyond** requirements Diane is choosing to add. Then a requirements mapping
  specific to the take-home (not the full self-imposed wishlist).
- **[DECISION]** **Recommend, don't decide:** the software provides *recommendations*; the
  human Label Specialist reviews findings and makes the final decision. The goal is to make the
  job easier and faster, never to do the Label Specialist's job. → *Confirm this aligns with the
  brief's wording.* **[RESOLVED]** Aligns — see `Research-Findings.md` §7 and the brief.

## 2. Domain Terminology & Roles

- **[DECISION]** **Applicant** = the industry member who submits a COLA (Certificate of
  Label Approval) application.
- **[DECISION]** **Label Specialist** = the federal government employee who reviews the
  application and makes the decision. ("Label Specialist" is TTB's official job title for
  these COLA reviewers — used throughout in place of the generic "adjudicator.")
- **[DECISION]** **Submissions** = the queue of applications that need to be reviewed.

## 3. Operating Constraints & Environment

- **[DECISION]** **No cloud / external API calls** in the deployed app — the government
  firewall blocks outbound traffic to many domains. → **[REQUEST]** Produce a documented
  **inventory of all outbound calls** in the deliverables so reviewers can confirm none
  require firewall exceptions.
- **[OPEN]** Label Specialists reportedly work on **CPU-only workstations with no local disk**.
  Decide whether to acknowledge this, and analyze its impact. Working theory: they operate
  off a **website (URL to the main COLA system)** rather than installing anything locally,
  while persistence lives in the central COLA databases. → *Analyze & discuss for the
  landscape write-up.*
- **[DECISION]** **Authentication is explicitly not a POC feature** (per the brief). To
  protect the public demo URL, use lightweight **token authentication** so only an
  evaluator — not the public or bots — can interact with it.

## 4. Data Model & Database

- **[REQUEST]** Create a **mock COLA database** with the fields the Label Specialist needs, and
  **seed it with dummy application data**.
- **[REQUEST]** Define the **submissions schema**, plus a separate **data dictionary**
  (field name, "common name," specification, definition).
- **[DECISION]** Include a **label-image filename field** that accommodates a label made up
  of **1–10 images** (front, back, and any additional applied labels).
- **[DECISION]** The database holds three field categories: (a) **application fields** (from
  the actual application in STORRd / Form 5100.31), (b) **OCR-extracted fields**, and (c)
  **fields to be defined later**.
- **[DECISION]** Capture the **application date** and **approval/decision date**.
- **[DECISION]** For LLM stats, capture **model name, model ID, full model ID, and
  timestamps** in the database.

## 5. Processing Architecture & Pipeline

- **[DECISION / REQUEST]** **Pre-compute strategy** (the centerpiece — must beat the
  abandoned 5–10-minute pilot): (1) store baseline info on submission; (2) a batch job steps
  through newly-submitted records and triggers **background OCR**; (3) OCR extracts and
  stores what it can; (4) a background job analyzes OCR results and collects advisory
  compliance results. By the time a Label Specialist pulls the next submission, it displays
  **instantly**. → *Analyze and propose a design that is a significant improvement over prior
  attempts.*
- **[RESOLVED]** **State machine?** Lightweight metrics **in scope**; a heavyweight workflow
  state machine **out of scope**. Capture `submitted_at` / `decided_at` timestamps, a minimal
  `status` enum, and engine `processing_ms` — enough for time-to-decision, throughput, and
  the ~5s claim without rebuilding COLA's workflow engine.
- **[REQUEST]** Explore running **OCR in a microservice**; make it easy to swap/compare OCR
  packages.
- **[OPEN]** **Python vs. Bash** for system components — recommend which and explain why
  Python is preferred.
- **[DECISION]** **API = phase two.** Keep the POC minimal; phase two is an API definition
  that also supports integrating with existing systems.

## 6. OCR, LLM & Benchmarking Strategy

- **[DECISION]** Use **two OCR products: Tesseract and PaddleOCR**, each in its own
  background job, with **timing statistics**.
- **[DECISION]** Don't commit to one OCR engine now — **run multiples and collect stats** to
  inform future procurement.
- **[REQUEST]** Explore using **multiple OCRs and multiple LLMs** (Codex, OpenAI, Gemini,
  plus any recommended) performing the same extraction tasks; produce **benchmark data on
  speed and accuracy**.
- **[DECISION]** Use **LangChain to trace** latencies/timings. Document that LangChain is
  included for its benefits but is **easy to turn off**, is used **only for gathering
  statistics**, and can be disabled so it never conflicts with the no-outbound-calls /
  firewall constraint.
- **[DECISION]** Make the **LLM optional**: used for the POC, and additionally as a
  **fallback when OCR isn't producing good matches**.
- **[REQUEST]** Collect statistics/analysis on **which OCR is more accurate, which LLM is
  better, and what the best overall approach is**.
- **[REQUEST]** Produce a **cost analysis** — LLM cost per ~1,000 verifications.
- **[REQUEST]** Maybe a **Python program using LangChain** to retrieve, analyze, and store
  the benchmark results in the database.
- **[REQUEST]** Make **recommendations** based on the POC results (depends on a strong data
  foundation — see §11 label sourcing).

## 7. Regulatory & Compliance Rules

- **[REQUEST]** Extract the **distilled spirits rules** from the CFR 27 documents in
  `ref-docs/` and create a clear, easy-to-read document listing all rules used to review
  a label + application. Four sources: CFR 27 for **beer (malt beverages)**, **distilled
  spirits**, **wine**, and **Part 16 (government warning)**.
  → **[RESOLVED — foundation]** TTB's own `ds-labeling-checklist.pdf` + the domain research
  report (Regulatory section) already pin the exact post-2022 §§ for all mandatory/conditional
  spirits elements.
- **[REQUEST]** A clear write-up on the **Government Warning Statement check** — how the words
  are verified. → **[RESOLVED — approach]** Deterministic exact/normalized match; enforce the
  caps+bold "GOVERNMENT WARNING:" token; see `Research-Findings.md` §2 and the domain research.
- **[DECISION]** **Font sizes are NOT checked** — not reliably possible from a photo without a
  scale reference, and there's a rule against it. → **[REQUEST]** Copy the relevant **COLA
  Online disclaimer verbiage** (approval won't test dimensions/font size; applicant swears
  compliance) and note in the README-style docs that the POC does the same.
- **[REQUEST]** A **definitive requirements list per label type** (beer, wine, distilled
  spirits) — sourced from TTB.gov.
- **[DECISION]** **Cover all three alcohol types** — beer, wine, and distilled spirits — as
  first-class. The brief doesn't require all three, but the decision (2026-06-11) is to
  support each fully: every type has its own review ruleset doc
  ([regulatory-rules-distilled-spirits](../docs/regulatory-rules-distilled-spirits.md),
  [-wine](../docs/regulatory-rules-wine.md), [-beer](../docs/regulatory-rules-beer.md)).
  Distilled spirits remains the most fully worked example.
- **[REQUEST]** Find resources on the **top-10 most common errors for distilled spirits**
  (the articles found so far are wine-only, which is out of plan).

## 8. Label Specialist Workflow & Queue

- **[DECISION]** A single **"Next Submission"** button serves the next item directly — no
  list to choose from.
- **[DECISION — consider]** Allow selecting the next submission **by application type**
  (next wine / spirits / beer) so a Label Specialist can specialize in one type.
- **[DECISION — consider]** Optionally split the queue into **two buckets** — very-likely-
  compliant vs. troublesome — so junior staff take the easy ones and senior staff the
  complex ones. Let the agent choose what to pull next.
- **[OPEN]** Define how an agent **starts a session and reaches the first label** — how
  submissions are queued and how the system serves the next one on login ("get next item →
  load review screen"). *(Not publicly documented; the POC designs it — see
  `Research-Findings.md` §5.)*
- **[RESOLVED]** **Dispositions** mirror TTB's real states — **Approved / Needs Correction /
  Rejected** (not invented "Pass/Fail"). These are the *Label Specialist's disposition*, distinct
  from the *engine verdict* (**PASS / REVIEW / FAIL**). "Review" is informal, not a
  disposition; the TTB term is **Needs Correction** (fixable, 30-day clock) vs. **Rejected**
  (terminal). See `Research-Findings.md` §7.
- **[RESOLVED]** **What happens after each determination:** **Approved** → COLA issues (can
  later be surrendered); **Needs Correction** → returned to submitter, 30 days to fix & resend,
  else auto-rejected; **Rejected** → terminal, requires a fresh resubmission referencing the
  prior TTB ID.

## 9. UI / UX & Design System

- **[DECISION]** Reference the **USWDS (U.S. Web Design System)** standards; consider its
  **GitHub component repo** for components to copy/clone. → **[REQUEST]** A few README
  statements on how the software complies with USWDS.
- **[DECISION]** Design for a **minimum 24-inch monitor**, likely **27-inch or dual 24-inch**.
- **[DECISION]** **Intuitive, easy-to-navigate UI** is a priority — the user base skews older
  with wide-ranging tech comfort ("something my mother could figure out… clean, obvious, no
  hunting for buttons"). Want creative ideas here.
- **[DECISION]** **Vertical stacked field comparison:** show each application field with the
  OCR/LLM-retrieved text **immediately below it** (not side-by-side) — horizontal layouts
  force the eyes too far apart to compare easily.
- **[DECISION]** The review UI must let the agent **instantly see the beverage type** (beer /
  wine / spirits), since required checks differ by type.
- **[REQUEST]** Propose a way to **highlight discrepancies** when the OCR result differs from
  the maker-entered field value.
- **[DECISION / REQUEST]** Add a **visible checklist feature** (reframing Jenny Park's printed
  desk checklist) that guides the agent through required checks. Want advice on designing the
  checklist experience.
- **[DECISION]** Where it fits, show process steps in a **chevron-style status bar** (step 1
  of N + overall progress).
- **[REQUEST]** Provide clear, easy-to-find **help/support in the UI**, including a way to
  **search for help** and a **knowledge base** of answers.

## 10. Image Handling

- **[OPEN → REQUEST]** Clarify and document the **supported image types** (not found in the
  alcohol-makers' user guide; define it in the docs if absent). *(Baseline from
  `Research-Findings.md` §6: COLAs Online accepts JPG/JPEG and TIFF, ≤750 KB, up to 10 files.)*
- **[REQUEST]** Address **imperfect images** (glare, bad angle) — a way to improve them
  **without** sending back to the submitter for a correction cycle. Does it require an LLM, or
  can open-source software do it? → **[RESOLVED — direction]** Open-source, local **OpenCV**
  (deskew, perspective correction, glare/contrast) — no LLM/cloud call needed; see the domain
  research (Technical Trends).

## 11. Test Data & Label Sourcing

- **[REQUEST]** Create a **folder for sample label images** + corresponding field data
  (ideally a **CSV**) to seed the database.
- **[REQUEST]** Suggest **where to find real labels online** and how to collect them — want
  **as many as possible**, not a handful, for a strong data foundation.
- **[RESOLVED]** Source: the **public, no-login COLA Registry** (label images 1999–present)
  plus **data.gov / Kaggle** bulk sets. **Caveat:** records are public but **label artwork is
  trademarked → use as private test fixtures only**; use synthetic labels for anything public.
  See `Research-Findings.md` §8.

## 12. Comparable Software & Pre-search

- **[REQUEST]** Search for **applicant-facing pre-screen tools** (websites makers use to check
  labels/images/data before submitting) and list them — e.g. *LabelScreener, Label Score*.
- **[DECISION]** Acknowledge in the pre-search doc that these exist and support the argument
  that **submission quality should improve** now that pre-screening tools are available
  (industry "picking up the ball" after the government's abandoned pre-screen attempt).
- **[RESOLVED]** Landscape captured: maker-side pre-screen (**COLAClear, GetGen, Phantom
  Ales**) and registry search (**COLA Cloud, Sovos LabelVision**) — none is a federal-reviewer
  review tool (the POC's differentiation). See the domain research (Solution Landscape).
  → *Note: "LabelScreener"/"Label Score" did not resolve to live products in research — confirm
  source or cite the verified tools instead.*

## 13. Batch Uploads

- **[DECISION / OPEN]** Treat **batch upload as an applicant-side feature** of COLAs Online,
  **not** a Label Specialist-screen feature (the POC's focus). An industry member could upload,
  say, **300 applications with one signature**, but they remain **300 individual applications**
  with **no impact on the Label Specialist**. → *Discuss how to address the brief's batch wishlist
  item in the write-up.*

## 14. Deliverables & Documentation

- **[RESOLVED]** Confirmed deliverables: **(1)** the source repo (code + README +
  approach/tools/assumptions docs) and **(2)** a deployed application URL.
- **[REQUEST]** Create a **`docs/` folder** linked from the README, with clearly-named files:
  **`approach.md`**, **`tools-used.md`**, **`assumptions.md`**,
  **`tradeoffs-and-limitations.md`**, **`presearch.md`**, plus a **`batch-template.csv`**.
  Seed them with the actual research findings (superseding the original "To be determined"
  placeholders), leaving `TODO` markers only where implementation choices remain.
  → *Status: DONE — the `docs/` folder exists on disk with the full doc set (see Reconciliation note).*
- **[REQUEST]** The **README** must include **setup and run instructions** and reference each
  of the docs above.

## 15. Narrative & Landscape Context to Document

- **[REQUEST]** Document the **distilled-spirits online application workflow** an applicant
  follows in COLAs Online (for the README). *(Source: the COLA Online user guide in
  `ref-docs/`.)*
- **[REQUEST]** Note that TTB.gov states there are **more online than paper applications**;
  confirm exact counts via the **public COLA search** (filter paper vs. online) for **2024,
  2025, and 2026-to-date**. → *Diane can pull these if automated access fails.* **[RESOLVED —
  partial]** ~90% are filed online (domain research, Domain Scale & Structure); exact yearly
  counts still `TODO`.
- **[REQUEST]** Write up the **landscape explanation** (the existing applicant website, the
  central COLA database, the CPU-only/no-disk workstation point from §3, and the
  maker-vs-reviewer two-viewpoint framing).
- **[CONTEXT]** The existing applicant website captures **label images, the electronic
  verification signature, and field data**, storing them (with the application and Form
  5100.31) in a database; **all distinct application fields are available to the Label Specialist
  software**.

---

## Quick Index of Open Questions

These are the **[OPEN]** items still needing a decision or analysis:

1. Confirm the two project goals — or identify a third (§1).
2. Whether/how to acknowledge the CPU-only, no-disk workstation reality (§3).
3. Python vs. Bash recommendation + rationale (§5).
4. How an agent starts a session and is served the first/next submission (§8).
5. How to position the batch-upload wishlist item in the write-up (§13).

*Resolved 2026-06-11: cover all three alcohol types (§7, was #4); the "select which value to
keep" feature is **out of scope** and removed (was an applicant-prescreener idea, §9).*
