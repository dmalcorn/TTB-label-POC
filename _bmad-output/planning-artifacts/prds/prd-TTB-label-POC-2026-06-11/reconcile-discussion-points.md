# Reconciliation — Decision Register vs. PRD + Addendum

**Input:** `ref-docs/discussion-points.md` (decision register, organized 2026-06-11)
**Against:** `prd.md` and `addendum.md` in this folder (both 2026-06-11)
**Date:** 2026-06-11

Every **[DECISION]** and **[REQUEST]** item in the register is walked below. **[OPEN]** and **[RESOLVED]** items are included for completeness where they carry product content. Disposition codes:

| Code | Meaning |
|---|---|
| **PRD** | Captured in the PRD (section/FR cited) |
| **ADD** | Captured in the addendum (section cited) |
| **DEFER** | Explicitly deferred (Phase 2 / Out of Scope / Open Question) |
| **SUPERSEDED** | Knowingly revised — replacement cited |
| **GAP** | No disposition found — flagged in §Gaps |
| **PARTIAL** | Core captured, a named sub-deliverable is not — flagged |

> **Known deliberate change (not a gap):** the §3 firewall posture ("no cloud / external API calls in the deployed app") was revised by Diane during PRD work — LLM calls are allowed in the deployed live path, modeling government-internal endpoints. See PRD NFR-2 and Addendum A2.

---

## Item-by-item disposition

### §1 Purpose, Goals & Scope

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 1.1 | DECISION | POC = Label Specialist's side: read from DB, present user-friendly, automated assistance, capture decisions | **PRD** | §1 Vision; FR-1–FR-6; §4.4 (read-only except Disposition) |
| 1.2 | DECISION | Primary goal: complete take-home, demonstrate AI-assisted working code | **PRD** | §0; §2.1 (evaluator JTBD); SM-4; NFR-6 |
| 1.3 | DECISION | Secondary goal: procurement-informing evidence | **PRD** | §1 ("simultaneously a procurement study"); §4.5; SM-3 |
| 1.4 | DECISION | v1 excludes image upload and field data-entry (read-only POC) | **PRD** | §5 Non-Goals ("No image upload, no application data entry"); §4.4 |
| 1.5 | REQUEST | Two requirement sets — (a) mandatory take-home, (b) above-and-beyond — plus a take-home-specific requirements mapping | **GAP** | Not in PRD or addendum; not deferred anywhere. See Gaps G1 |
| 1.6 | DECISION | Recommend, don't decide — human makes the final call | **PRD** | §1; FR-6 (no pre-select); FR-16 (LLM capped at REVIEW); §5 Non-Goals |

### §2 Domain Terminology & Roles

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 2.1 | DECISION | "Applicant" definition | **PRD** | §3 Glossary |
| 2.2 | DECISION | "Label Specialist" official title, used throughout | **PRD** | §3 Glossary (synonyms explicitly banned) |
| 2.3 | DECISION | "Submissions" = queue of applications to review | **PRD** | §3 Glossary (Submission); FR-1 (pending queue) |

### §3 Operating Constraints & Environment

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 3.1 | DECISION | No cloud / external API calls in deployed app | **SUPERSEDED** (deliberate) | NFR-2; Addendum A2 — LLM calls allowed, modeling government-internal endpoints; zero-egress OCR-only path preserved (FR-12 toggle-off) |
| 3.2 | REQUEST | Outbound-call inventory deliverable | **PRD** | FR-26; NFR-2 (every entry classified local / none / models-internal-endpoint) |
| 3.3 | OPEN | CPU-only / no-local-disk workstations — acknowledge & analyze | **DEFER + ADD** | PRD Open Question 4; NFR-1 (CPU-only-mode benchmarks); Addendum A6 (landscape write-up) |
| 3.4 | DECISION | No auth feature; lightweight token gate for demo URL | **PRD** | FR-25; §2.2; §5 Non-Goals |

### §4 Data Model & Database

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 4.1 | REQUEST | Mock COLA database seeded with dummy data | **PRD** | FR-19, FR-20; §3 Glossary (Mock COLA Database) |
| 4.2 | REQUEST | Submissions schema + separate data dictionary (name, common name, spec, definition) | **PRD** | FR-19 (data dictionary is a repo deliverable, four-column form named) |
| 4.3 | DECISION | Label-image field accommodating 1–10 images | **PRD** | FR-19; §3 Glossary; FR-7 |
| 4.4 | DECISION | Three field categories (application / OCR-extracted / later) | **PRD** | FR-19 ("three field categories"; third category realized as engine/statistics fields) |
| 4.5 | DECISION | Capture application date and decision date | **PRD** | FR-19, FR-6 (`submitted_at` / `decided_at`) |
| 4.6 | DECISION | Capture LLM model name, model ID, full model ID, timestamps in DB | **PRD + ADD** | FR-12 consequences; FR-18; Addendum A1 (tracing fields) |

### §5 Processing Architecture & Pipeline

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 5.1 | DECISION/REQUEST | Pre-compute strategy — background OCR + analysis so next Submission displays instantly | **PRD** | §4.2 entire feature; FR-9; NFR-1; SM-1 |
| 5.2 | RESOLVED | Lightweight metrics yes, heavyweight state machine no | **PRD** | FR-9 (minimal status enum, `processing_ms`); §5 Non-Goals; Addendum A3 |
| 5.3 | REQUEST | OCR in a microservice; easy to swap/compare engines | **PRD + ADD** | FR-11 (uniform interface, engine-agnostic schema, third engine = no schema change); Addendum A1 ("microservice-style interface") |
| 5.4 | OPEN | Python vs. Bash recommendation + rationale | **ADD (deferred write-up)** | Addendum A1 — Python preferred, rationale write-up routed to architecture / `docs/approach.md` |
| 5.5 | DECISION | API = Phase 2 | **DEFER** | §5 Non-Goals; §6.2 Out of Scope (explicit) |

### §6 OCR, LLM & Benchmarking Strategy

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 6.1 | DECISION | Tesseract + PaddleOCR, each in own background job, with timing stats | **PRD + ADD** | FR-11; Addendum A1 |
| 6.2 | DECISION | Don't commit to one OCR — run multiples, collect stats for procurement | **PRD** | FR-11; §4.5; SM-3 |
| 6.3 | REQUEST | Multiple OCRs + multiple LLMs (Codex, OpenAI, Gemini + recommended) on same tasks; benchmark speed/accuracy | **PRD + ADD** | FR-21, FR-22; SM-3 (≥3 LLMs); Addendum A1 (roster: OpenAI GPT, Gemini, Claude; "Codex" clarified) |
| 6.4 | DECISION | LangChain tracing — stats-only, easy to turn off, never conflicts with firewall constraint | **PRD + ADD** | FR-24; Addendum A1 |
| 6.5 | DECISION | LLM optional; fallback when OCR matches poorly | **PRD** | FR-12 (optional, toggleable, fallback; OCR-only path must still work) |
| 6.6 | REQUEST | Stats/analysis: which OCR more accurate, which LLM better, best overall approach | **PRD / PARTIAL** | FR-21–FR-23 produce the comparative data; the "best overall approach" *recommendation* is not a named deliverable — see Gaps G3 |
| 6.7 | REQUEST | Cost analysis — LLM cost per ~1,000 verifications | **PRD + ADD** | FR-22; SM-3; Addendum A7 |
| 6.8 | REQUEST | Maybe a Python/LangChain program to retrieve, analyze, store benchmark results | **PRD** | Benchmark Harness (§4.5, FR-21–FR-24) is this program; Addendum A1 (Python, LangChain local tracing) |
| 6.9 | REQUEST | Recommendations based on POC results | **PARTIAL** | Same as 6.6 — data captured, recommendation deliverable unnamed. Gaps G3 |

### §7 Regulatory & Compliance Rules

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 7.1 | REQUEST | Extract rules from CFR 27 (beer, spirits, wine, Part 16) into clear documents | **PRD + ADD** | FR-26 ("per-type Ruleset documents"); §3 Ruleset (stored as data with citations); Addendum A4 (per-type rule docs already drafted under `docs/regulatory-rules-*.md`) |
| 7.2 | REQUEST | Government Warning verification write-up | **PRD** | FR-13 (deterministic exact verification, fully specified); FR-18 provenance |
| 7.3 | DECISION | Font sizes NOT checked | **PRD** | §5 Non-Goals; NFR-5 |
| 7.4 | REQUEST | Copy COLAs Online disclaimer verbiage into README-style docs | **ADD** | Addendum A4 (type-size table preserved; "the README should quote COLAs Online's own disclaimer") |
| 7.5 | REQUEST | Definitive requirements list per label type, sourced from TTB | **PRD + ADD** | Same as 7.1 — FR-26; Addendum A4 (authoritative sources named) |
| 7.6 | DECISION | All three alcohol types first-class; spirits deepest | **PRD** | §4.3 description; FR-15; FR-20; §6.1 |
| 7.7 | REQUEST | Find top-10 most common distilled-spirits errors | **DEFER** | PRD Open Question 2 (explicit, non-blocking) |

### §8 Label Specialist Workflow & Queue

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 8.1 | DECISION | Single "Next Submission" button, no list to browse | **PRD** | FR-1; §4.1 description |
| 8.2 | DECISION (consider) | Next Submission by Beverage Type | **PRD** | FR-2 (promoted to in-scope) |
| 8.3 | DECISION (consider) | Two-bucket queue (easy vs. troublesome, junior/senior) | **DEFER** | §6.2 Out of Scope — Phase 2, with rationale (needs benchmark-derived confidence calibration); Addendum A3 |
| 8.4 | OPEN | How a session starts and the first/next Submission is served | **PRD (designed)** | FR-1 (deterministic oldest-pending-first queue; skip-if-incomplete); UJ-1 (token URL, no login ceremony) |
| 8.5 | RESOLVED | Dispositions = Approved / Needs Correction / Rejected, distinct from engine PASS/REVIEW/FAIL | **PRD** | §3 Glossary (Disposition, Engine Verdict); FR-6 |
| 8.6 | RESOLVED | Post-determination outcomes (COLA issues / 30-day clock / terminal) | **ADD** | Addendum A4 (disposition mechanics for seeding realism) |

### §9 UI / UX & Design System

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 9.1 | DECISION | Reference USWDS standards (+ component repo) | **PRD** | NFR-4; §4.6 description |
| 9.2 | REQUEST | README statements on USWDS compliance | **PRD** | FR-26 ("USWDS-compliance notes … linked from the README") |
| 9.3 | DECISION | Minimum 24-inch monitor (27" / dual-24 typical) | **PRD** | §4.1 feature NFR; NFR-4 |
| 9.4 | DECISION | Intuitive UI for low-tech-comfort users | **PRD** | §4.1 ("the Dave gate"); NFR-4; UJ-1 |
| 9.5 | DECISION | Vertical stacked field comparison (not side-by-side) | **PRD + ADD** | FR-3; §4.1 description (with the eye-distance rationale); Addendum A3 (horizontal rejected) |
| 9.6 | DECISION | Beverage type instantly visible | **PRD** | §4.1 description ("the Beverage Type is instantly visible") |
| 9.7 | REQUEST | Highlight discrepancies between OCR and entered values | **PRD** | FR-3 (differing portion highlighted, not just the field) |
| 9.8 | DECISION/REQUEST | Visible checklist feature (+ design advice) | **PRD** | FR-4; §3 Glossary (Checklist as digital descendant of the paper one); design advice routed downstream to UX (PRD §0) |
| 9.9 | DECISION | Chevron-style status bar | **PRD** | FR-5 |
| 9.10 | REQUEST | Help/support in UI, searchable, knowledge base | **PRD + DEFER** | FR-8 (v1: static searchable help panel); §6.2 (knowledge-base product = Phase 2, explicit) |

### §10 Image Handling

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 10.1 | OPEN→REQUEST | Clarify/document supported image types | **ADD (partial doc routing)** | Addendum A5 (JPG/JPEG + TIFF, ≤750 KB, ≤10 files, as mock baseline). The "define it in the docs if absent" doc task is implicit, not named in FR-26 — minor, see Gaps G5 |
| 10.2 | REQUEST | Improve imperfect images locally, no LLM/cloud, no correction cycle | **PRD + ADD** | FR-10 (local, non-LLM); FR-7 (original + cleaned shown side by side); Addendum A1 (OpenCV-class toolset) |

### §11 Test Data & Label Sourcing

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 11.1 | REQUEST | Folder of sample label images + corresponding field data (ideally CSV) | **PRD (format unpinned)** | FR-20 (fixture corpus with Ground Truth values per Submission); CSV-specifically is not pinned — acceptable as an implementation detail |
| 11.2 | REQUEST | Where to find real labels online; as many as possible | **PRD + ADD** | FR-20 (sources named, trademark caveat enforced); Addendum A5 (registry, Kaggle, data.gov; degraded-tail corpus intent) |
| 11.3 | RESOLVED | Registry artwork = private fixtures only; synthetic for public | **PRD** | FR-20 consequence; NFR-3 |

### §12 Comparable Software & Pre-search

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 12.1 | REQUEST | Search and list applicant-facing pre-screen tools | **ADD** | Addendum A6 (verified roster; "LabelScreener"/"Label Score" flagged as unresolved — cite verified tools); `presearch.md` in FR-26 |
| 12.2 | DECISION | Acknowledge pre-screen tools → submission quality should improve | **ADD** | Addendum A6 ("Tailwind worth stating") |

### §13 Batch Uploads

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 13.1 | DECISION/OPEN | Batch upload is applicant-side, not a reviewer feature; address the brief's wishlist item in the write-up | **PRD + ADD** | §5 Non-Goals (with the 300-applications framing baked in); Addendum A3 (Sarah Chen wishlist framing for the write-up) |

### §14 Deliverables & Documentation

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 14.1 | RESOLVED | Deliverables = repo (code + docs) + deployed URL | **PRD** | §4.6; FR-25, FR-26; SM-4 |
| 14.2 | REQUEST | `docs/` folder: approach, tools-used, assumptions, tradeoffs-and-limitations, presearch, **batch-template.csv** | **PRD / PARTIAL** | FR-26 names the five .md docs; `batch-template.csv` is absent from FR-26 and the addendum — see Gaps G4. (Register notes the docs/ folder already exists on disk.) |
| 14.3 | REQUEST | README with setup/run instructions, referencing each doc | **PRD** | FR-26 ("a fresh evaluator can clone, set up, and run locally from the README alone") |

### §15 Narrative & Landscape Context

| # | Tag | Item | Disposition | Where |
|---|---|---|---|---|
| 15.1 | REQUEST | Document the applicant's distilled-spirits COLAs Online application workflow (for the README) | **GAP** | Not in PRD, addendum, or any deferral list. See Gaps G2 |
| 15.2 | REQUEST | Online-vs-paper filing counts (2024/2025/2026-to-date) | **DEFER** | PRD Open Question 1 (Diane to pull; non-blocking) |
| 15.3 | REQUEST | Landscape explanation write-up (applicant site, central DB, workstation reality, two-viewpoint framing) | **ADD** | Addendum A6 (full landscape-narrative brief for `docs/`) |
| 15.4 | CONTEXT | All application fields available to the specialist software | **PRD** | FR-19 (Form 5100.31-modeled application fields); §3 Glossary (Mock COLA Database) |

---

## Gaps

Ordered by significance. G1 and G2 are true gaps (no disposition anywhere); G3–G5 are partial.

- **G1 — Take-home requirements mapping missing (§1, REQUEST, item 1.5).** The register asks for two requirement sets — (a) the absolutely mandatory take-home requirements and (b) Diane's above-and-beyond additions — plus a requirements mapping specific to the take-home. Neither the PRD nor the addendum produces, references, or defers this. Since the primary goal (item 1.2) is the take-home itself, an explicit FR↔take-home-requirement traceability map is the one artifact proving the mandatory baseline is covered. **Suggested fix:** add it to FR-26's documentation deliverables (e.g., `docs/requirements-mapping.md`: mandatory vs. stretch, mapped to FRs), or log it as an Open Question.

- **G2 — Applicant COLAs Online workflow narrative missing (§15, REQUEST, item 15.1).** The register asks to document the distilled-spirits online application workflow an applicant follows (source: COLA Online user guide in `ref-docs/`) for the README. Addendum A6's landscape brief covers comparables, workstation reality, and the two-clocks framing — but not this walkthrough, and no deferral mentions it. **Suggested fix:** add one bullet to Addendum A6 (or the FR-26 docs list) routing it into the `docs/` landscape narrative.

- **G3 — "Recommendations" deliverable unnamed (§6, REQUESTs, items 6.6 / 6.9).** FR-21–FR-23 produce the comparative speed/accuracy/cost data, but the register twice asks for *recommendations* — which OCR, which LLM, best overall approach. FR-23's Benchmark Report presents engines "side by side … with the test conditions stated"; nothing commits to a conclusions/recommendations section. **Suggested fix:** one consequence line on FR-23 (report includes a findings-and-recommendations section) or a bullet in the `docs/` set.

- **G4 — `batch-template.csv` dropped from the docs list (§14, REQUEST, item 14.2).** FR-26 enumerates the docs set but omits `batch-template.csv`, and the addendum doesn't mention it. Plausibly an intentional casualty of the batch-is-applicant-side decision (§13 / Non-Goals / A3) — but no text says so. **Suggested fix:** either add it to FR-26 or add one line to Addendum A3 explicitly retiring it as superseded by the batch reframing. (Register notes the file may already exist in `docs/` on disk.)

- **G5 — Supported-image-types doc task implicit (§10, REQUEST, item 10.1).** Addendum A5 captures the JPG/TIFF/750 KB/10-file constraints as the mock's baseline, but the register's ask was also to *document* the supported types (the maker user guide doesn't state them). No FR-26 doc names this. Minor — one line in the data dictionary or assumptions doc closes it.

### Superseded (verified deliberate, not gaps)

- **§3 firewall posture (item 3.1):** "no cloud / external API calls" → revised 2026-06-11 by Diane: deployed-path LLM calls allowed, modeling government-internal endpoints. Fully documented in PRD NFR-2 and Addendum A2, with the zero-egress OCR-only configuration preserved as proof (FR-12 toggle-off, FR-24, FR-26 inventory). Consistent and intentional.

### Coverage summary

| Disposition | Count |
|---|---|
| Captured (PRD and/or Addendum) | 38 |
| Explicitly deferred (Phase 2 / Out of Scope / Open Question) | 5 |
| Knowingly superseded | 1 |
| Partial (sub-deliverable unpinned) | 4 (G3 ×2 merged, G4, G5, 11.1-minor) |
| True gaps | 2 (G1, G2) |
