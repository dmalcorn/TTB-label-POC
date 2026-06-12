---
stepsCompleted: [1, 2, 3, 4]
status: 'complete'
completedAt: '2026-06-12'
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/prd.md
  - _bmad-output/planning-artifacts/prds/prd-TTB-label-POC-2026-06-11/addendum.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/approved-tech-stack.md
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/EXPERIENCE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/token-gate.html
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/queue.html
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/review-workspace.html
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/help-panel.html
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/benchmark-report.html
  - docs/database-schema.md
  - docs/data-dictionary.md
  - docs/regulatory-rules-distilled-spirits.md
  - docs/regulatory-rules-wine.md
  - docs/regulatory-rules-beer.md
  - docs/label-requirements-by-type.md
  - docs/image-handling.md
  - docs/ocr-llm-benchmarking-plan.md
  - docs/outbound-calls-inventory.md
  - docs/tools-used.md
  - docs/assumptions.md
  - docs/tradeoffs-and-limitations.md
  - docs/applicant-workflow-distilled-spirits.md
project_name: 'TTB-label-POC'
user_name: 'Diane'
date: '2026-06-12'
---

# TTB-label-POC - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the TTB COLA Label Specialist Workspace (POC), decomposing the requirements from the PRD, the UX Design package (DESIGN.md, EXPERIENCE.md, and the five HTML mockups), and the Architecture decision record into implementable stories.

> **Scope decision (set with Diane, 2026-06-12).** The **entire "Full" tier is in scope** — nothing is deferred to a cut line. Epics are organized **by value area so each "Full"-tier feature is implemented alongside its related "Core" code** (e.g. next-by-type + status bar + help with the Review Workspace; local preprocessing + LLM fallback with the Pre-compute Pipeline; hybrid/flag-only checks + wine/malt-beverage rulesets with the Compliance Engine), matching the architecture's package boundaries — not split into a separate above-and-beyond epic.

> **UI fidelity standard (binding on every UI story — set with Diane, 2026-06-12).**
> Each screen must reproduce its named mockup's **layout, composition, USWDS component structure, all depicted states, and exact visible copy**, rebuilt on real vendored USWDS components with real data. **Design tokens resolve to `DESIGN.md` values; where a mockup's inline CSS conflicts with `DESIGN.md`/`EXPERIENCE.md`, the spine wins** (every mockup header states "spine wins on conflict" — e.g. PASS green is `#216E29` per DESIGN.md, not the mockups' `#2E8540`). **Mockup-only scaffolding is illustrative and must NOT be reproduced**: the browser device frame, the CSS-drawn label artwork (real label images replace it), and placeholder data (`J. Park`, `38 waiting`, `SUB-2026-04871`, etc.). **Every UI story's Definition of Done includes a documented side-by-side comparison of the running screen against its referenced mockup file**, state for state.

## Requirements Inventory

### Functional Requirements

**Feature 4.1 — Review Workspace**
- **FR-1:** Serve the next pending Submission via **Next Submission** with the review screen fully loaded (label images, application fields, OCR values, Engine Verdicts, Checklist); ≤5s interactive; deterministic oldest-first order; unready Submissions skipped, never served partially.
- **FR-2:** Serve next Submission **by Beverage Type** (next spirits / wine / malt beverage); plain "none pending" message when that type's queue is empty.
- **FR-3:** **Stacked field comparison** — each application field with its OCR-extracted value directly beneath it, Field Match Engine Verdict per pair, discrepancy visually highlighted (differing span, not whole field); normalized match shows PASS with both raw values visible.
- **FR-4:** **Per-type Checklist** of Ruleset Checks for the Submission's Beverage Type, each item carrying its Engine Verdict and CFR citation; contents differ correctly by type.
- **FR-5:** **Review progress status bar** (chevron) showing steps of the current review and overall progress (step N of M), reflecting Checklist completion.
- **FR-6:** **Record Disposition** — exactly one of Approved / Needs Correction / Rejected; Submission then leaves the pending queue; Disposition + `decided_at` persisted; Engine Verdicts never pre-select or default the control.
- **FR-7:** **Label image display with preprocessing comparison** — view all 1–10 images; where a cleaned image exists, view it beside the original; neither silently replaces the other.
- **FR-8:** **In-UI help** — clear, one-click, searchable static help panel explaining the screen, the PASS/REVIEW/FAIL vocabulary, and each Check.

**Feature 4.2 — Pre-compute Pipeline**
- **FR-9:** **Background processing at Submission arrival** — image preprocessing, OCR per engine, Check execution, with no specialist action; status enum `submitted → processing → ready` + failure state; per-stage timestamps and `processing_ms` persisted; p95 time-to-ready ≤10 min; failures land in a visible error state.
- **FR-10:** **Local image preprocessing** (deskew, perspective, glare, contrast) via local non-LLM tooling; cleaned image stored alongside original; OCR accuracy on preprocessed strictly exceeds originals across the degraded subset.
- **FR-11:** **Multi-engine OCR** (≥2: Tesseract + PaddleOCR) in independent background jobs behind a uniform interface; per-engine text/values/confidence/latency stored separately; adding a third engine requires no schema change.
- **FR-12:** **LLM extraction and fallback** — optional/toggleable; pipeline completes OCR-only when off; LLM-unreachable degrades affected Checks to OCR-only with a visible notice; per-call model name/ID/version/timestamps/latency/tokens persisted; read screen never blocks on an LLM call.

**Feature 4.3 — Compliance Engine**
- **FR-13:** **Government Warning exact verification** (deterministic, no LLM) per 27 CFR 16.21 — exact wording, caps "GOVERNMENT WARNING:" header, whitespace normalized, body case-insensitive, required casing enforced; deviations → FAIL with the deviation identified; bold undeterminable → not-verified, never silent PASS.
- **FR-14:** **Field Match with normalization tolerance** — PASS on normalized match, REVIEW on near-miss/low confidence, FAIL on substantive mismatch ("STONE'S THROW" vs "Stone's Throw" → PASS; ABV 45% vs 40% → FAIL).
- **FR-15:** **Per-type deterministic format Checks** — alcohol-content statement format, net-contents + standards-of-fill lookup, name/address qualifying phrase, conditional Checks (sulfites, coloring, age, country of origin); cross-commodity ABV rules respected; proof ↔ ABV consistency; unevaluable conditional → REVIEW.
- **FR-16:** **Hybrid class/type designation Check** — rules first, escalate only genuine ambiguity to LLM, LLM-assisted capped at REVIEW (never FAIL); cross-image designation conflicts detected deterministically → FAIL; degrades to rules-only when LLM off.
- **FR-17:** **Flag-only Checks → REVIEW** — Same Field of Vision spatial inference, "separate and apart" placement, severely degraded text → REVIEW with explanatory note, never PASS/FAIL.
- **FR-18:** **Verdict provenance** — every Engine Verdict records its Check, determinism class, CFR citation, compared input values, and (LLM-assisted) model identification; review screen can explain any verdict.

**Feature 4.4 — Mock COLA Database & Test Corpus**
- **FR-19:** **Submissions schema and data dictionary** — application fields (Form 5100.31-modeled), OCR/LLM-extracted fields, engine/statistics fields; TTB ID, Beverage Type, 1–10 label images (11th rejected), `submitted_at`/`decided_at`, Disposition, model-identification fields; data dictionary covers every field.
- **FR-20:** **Seeded fixture corpus with Ground Truth** — 30–50 dummy Submissions across all three Beverage Types (clean, every-Check-violation, degraded-image tail), each with Ground Truth; ≥1 Submission per Engine Verdict outcome per type; no registry artwork in public flows.

**Feature 4.5 — Benchmark Harness & Procurement Study**
- **FR-21:** **Accuracy scoring against Ground Truth** — per-field and aggregate match rates per OCR engine and LLM; reproducible across the seeded corpus.
- **FR-22:** **Speed and cost statistics** — per-engine/per-model latency and per-call cost inputs; cost per 1,000 Verifications per configuration ($0-marginal for local); pricing basis stated explicitly.
- **FR-23:** **Benchmark Report** — engines and models side by side (speed, accuracy, cost) with test conditions stated; reachable from the deployed demo; reflects actual runs; closes with grounded recommendations.
- **FR-24:** **Local-only tracing, toggleable** — runs locally, writes local DB only, disable-able by config with no effect on review functionality; no telemetry leaves the host.

**Feature 4.6 — Demo Access & Evaluator Deliverables**
- **FR-25:** **Token-gated access** — full demo with the token at a public URL; without it, a clean denial and no data/image/report leakage.
- **FR-26:** **Documentation deliverables** — README (setup/run), `docs/` set (approach, tools, assumptions, trade-offs, pre-search), data dictionary incl. image types, per-type Ruleset docs, landscape narrative incl. Applicant COLAs Online workflow, outbound-call inventory, USWDS-compliance notes — each linked from README; clone-and-run from README alone.
- **FR-27:** **Demo data reset** — restore full seeded queue and clear recorded Dispositions without redeployment.
- **FR-28:** **Enqueue a fixture Submission live** — trigger insertion of a fresh fixture and observe `submitted → processing → ready`, then servable via Next Submission with full Engine Verdicts.

### NonFunctional Requirements

- **NFR-1 — Performance:** review-screen readiness ≤~5s p95 from Next Submission click, achieved architecturally via the Pre-compute Pipeline (not faster request-time inference). CPU-only-mode performance recorded by the Benchmark Harness.
- **NFR-2 — Firewall posture / outbound calls:** local-first; OCR/preprocessing/rules/tracing fully local; LLM calls classified `models-internal-endpoint` and toggleable to a provable zero-egress OCR-only path; complete outbound-call inventory deliverable with 3-way classification (`none`/`local`/`models-internal-endpoint`); tracing never off-host.
- **NFR-3 — Privacy and data:** no PII; dummy data only; registry artwork private-fixtures-only; read-only posture except Disposition capture and pipeline writes.
- **NFR-4 — Usability and accessibility:** USWDS-based UI; designed for the lowest-tech-comfort user (the "Dave gate"); minimum 24-inch-monitor layout; Section-508-conscious USWDS defaults (full 508 audit out of scope).
- **NFR-5 — Honesty of claims:** demo/report/docs claim only what is demonstrated; limitations documented beside capabilities.
- **NFR-6 — Code quality:** organized, evaluator-readable codebase; documented assumptions and trade-offs; working core preferred over ambitious-incomplete features.

### Additional Requirements

*(From the Architecture decision record and approved tech stack — technical requirements that shape stories.)*

- **AR-1 — Init story (FIRST, blocks all):** hand-rolled minimal **FastAPI** app + custom **Dockerfile** baking native deps (`tesseract-ocr`, OpenCV/Paddle libs), **pinned offline model weights** (no runtime download), vendored **USWDS 3.x** assets, and seeded fixture images; plus `db/schema.sql` (WAL) + `db/seed.py`. No project generator. Python **3.13-slim** base.
- **AR-2 — Topology (D1/D3):** single **Railway** service; **SQLite** file on a Railway Volume; in-process **APScheduler 3.11.x** sweep of `RECEIVED` rows with bounded job concurrency; preprocessed images persisted to the Volume by path.
- **AR-3 — Four centralized contracts (each in exactly one module, imported everywhere):** (1) `OcrResult`/`LlmResult` adapter shapes; (2) `normalize(value, field_key)` field-match normalization; (3) `rollup(verdicts)` severity precedence; (4) verdict-vs-disposition separation (`engine_verdict` and `disposition` are different enums in different modules, with no function mapping one to the other).
- **AR-4 — Engine-agnostic schema:** adding an OCR engine or LLM = a new adapter file, no schema/caller change; per-engine/per-model results independently queryable (no merged-only storage).
- **AR-5 — The 5s contract (inviolable):** read/render routes perform a **DB read of pre-computed rows only** — never OCR, inference, or a model-layer call at request time.
- **AR-6 — Rulesets-as-data:** per-Beverage-Type Rulesets executed by the determinism taxonomy (deterministic / field-match / hybrid / flag-only); **CFR citations stored as data with source dates**; content authored in `docs/regulatory-rules-*.md` + `docs/label-requirements-by-type.md` (cross-type ABV matrix).
- **AR-7 — FR-10 both-variants OCR (gap closed in pipeline):** for the degraded-fixture subset, run OCR on **both** the original and the OpenCV-enhanced image (store both `ocr_results` rows) so the benchmark can show preprocessed accuracy > original.
- **AR-8 — Offline/pinned posture:** all weights + assets baked into the Docker image; egress smoke test = `docker run --network none -e LLM_ENABLED=false` proves the zero-egress OCR-only configuration.
- **AR-9 — Access + config:** token-gate FastAPI dependency (`ACCESS_TOKEN`); env-driven config (`LLM_ENABLED`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LANGCHAIN_*`); absent keys ⇒ model layer simply off (still functional, OCR-only).
- **AR-10 — Naming/format/process patterns:** `snake_case` across DB ↔ Python ↔ JSON; enums `UPPER_SNAKE` as `TEXT + CHECK`; status transitions `RECEIVED → PROCESSING → READY_FOR_REVIEW → IN_REVIEW → DECIDED`; fixed `audit_events.event_type` vocabulary; timing columns `_ms`, timestamps `_at` (UTC ISO-8601); `cost_usd` as decimal/string.
- **AR-11 — Tooling/structure:** `ruff` (lint+format, line length 100) + `pytest`; tests in top-level `tests/` mirroring the `app/` package; project tree per the architecture's Project Structure section.
- **AR-12 — Demo reset / enqueue mechanics:** reset = transactional re-seed (restore rows, clear `disposition`/`decided_at`, reset `status`, purge generated preprocessed images); `POST /enqueue` only inserts a `RECEIVED` row (the scheduler picks it up).
- **AR-13 — Data model authority:** canonical schema in `docs/database-schema.md`; per-field reference in `docs/data-dictionary.md`; Pydantic v2 validation at the API/read boundary; `field_comparisons`/`checklist_items` written by the analysis job only.
- **AR-14 — In-progress review state & Undo (architecture Addendum A / Decision #8):** the specialist's *manual* checklist ticks + *draft* Notes persist server-side in a dedicated **`review_progress`** table (one row per submission, web-layer-written — **never** in the pipeline-owned `checklist_items`), upserted via `POST /review/{id}/progress` and rehydrated by `GET /review/{id}` so a navigate-away or full browser reload resumes. A brief in-session **"Recorded — Undo"** (`POST /review/{id}/undo`) voids the just-recorded disposition via the **single bounded backward transition** `DECIDED → READY_FOR_REVIEW`, writing an `UNDONE` audit event. `review_progress` is retained through a disposition (so Undo can restore the work) and purged by `POST /reset`. These are cheap single-row writes on explicit POST actions — the `GET` render stays a pure pre-computed read (AR-5 intact).

### UX Design Requirements

*Each UX-DR below is governed by the **UI fidelity standard** in the Overview (structural + visual fidelity; spine wins on conflict; mockup-only scaffolding excluded; side-by-side mockup check in each story's DoD).*

**Per-screen requirements (each bound to one mockup file):**

- **UX-DR-1 — Token-gate screen** → [`mockups/token-gate.html`](ux-designs/ux-TTB-label-POC-2026-06-12/mockups/token-gate.html). Centered access card (Treasury seal, title, "Enter your access token to begin", single token text input, ≥48px navy **Enter** button, helper copy). Reproduce **both depicted states**: (1) token entry (input autofocused); (2) **clean denial** (`role="status"` alert "Access token required.", `is-error`/`aria-invalid` input, no data leakage). Realizes FR-25.
- **UX-DR-2 — Queue screen** → [`mockups/queue.html`](ux-designs/ux-TTB-label-POC-2026-06-12/mockups/queue.html). One huge auto-focused **Next Submission** button (Enter fires, never auto-opens), optional beverage-type **segmented filter** (Any · Wine · Spirits · Beer), the **Phase-2 two-bucket triage placeholder** (dashed, `aria-hidden`, clearly not a live control), and the civic-green read-only **stats strip**. Reproduce **both states**: (1) submissions waiting; (2) **empty queue** (Next Submission disabled + calm helper copy) including the **empty-type** variant copy. Realizes FR-1, FR-2; status-bar/checklist live on Review. Voice: "No submissions waiting right now.", "The wine queue is empty. Try Any, or check back later."
- **UX-DR-3 — Review Workspace (the hero)** → [`mockups/review-workspace.html`](ux-designs/ux-TTB-label-POC-2026-06-12/mockups/review-workspace.html). Full composition: utility header w/ Help; **beverage-type banner** (accent + glyph + word + submission meta); **chevron Step Indicator** (① Identity → ② Mandatory text → ③ Gov. Warning → ④ Conditional → ⑤ Decide, current step navy w/ non-color marker, done steps ✓); **Suggested-verdict Alert** (verdict tint, "Suggested:", returns authority to human); **two-column layout** (left = sticky image panel + Enhance toggle; right = field comparison cards + smart checklist); **bottom Notes + Disposition action bar** on a top-shadow. Reproduce the depicted REVIEW state (Gov Warning FAIL with char-diff, Brand REVIEW, four auto-PASS matches, "5 of 6 done"). Realizes FR-1, FR-3, FR-4, FR-5, FR-6, FR-7.
- **UX-DR-4 — Help panel** → [`mockups/help-panel.html`](ux-designs/ux-TTB-label-POC-2026-06-12/mockups/help-panel.html). Right-anchored slide-over `role="dialog"` over a scrimmed backdrop: prominent **search** ("Ask a question…" + on-server note), **browsable KB list** (so low-search-comfort users scan, not type), the **PASS/REVIEW/FAIL verdict explainer** (icon+word+color, with the verdict-vs-disposition reminder), **keyboard-shortcuts** list, and the **no-results calm state**. One-click `[?]` from every screen; `Esc` closes. Realizes FR-8.
- **UX-DR-5 — Benchmark Report** → [`mockups/benchmark-report.html`](ux-designs/ux-TTB-label-POC-2026-06-12/mockups/benchmark-report.html). Evaluator header (nav + **"Evaluator build"** badge), title/intro, civic-green **Recommendations callout**, the **side-by-side comparison table** (grouped OCR engines / Language models; columns: field accuracy, latency ms/item, cost/1,000 USD, CPU-only flag; best-in-group row highlighted; figures in mono; verdict palette kept OFF this surface), **CPU-only flag** as icon+word+color, the **honesty note** ("indicative, not audited" caveats), and footer meta. Also reproduce the EXPERIENCE.md **"no benchmark runs yet"** empty state. Read-only. Realizes FR-23 (surfaces FR-21, FR-22).

**Cross-cutting design-system requirements (apply across all screens above):**

- **UX-DR-6 — USWDS foundation, self-hosted:** vendored USWDS 3.x (Header, Step Indicator, Alert, Tag, Accordion, Modal, Table, Form controls, Search) used per documented markup, not reimplemented; Treasury brand layer (navy `#112E51` primary, civic green `#2E5B46` secondary) replacing USWDS default blue; **Public Sans** + **Roboto Mono** self-hosted (no Google Fonts call); all CSS/JS/fonts/icons same-origin (no CDN, no build step). Supports NFR-2, NFR-4.
- **UX-DR-7 — Verdict palette (advisory only):** PASS `#216E29` ✓ / REVIEW `#7A5900` ⚠ / FAIL `#B50909` ✕ each over its tint, **always paired with icon + word**, used **only** on engine verdicts (Tags, Suggested Alert, field-card states) — never on chrome/buttons/links; the DESIGN.md AA contrast ratios are held. (Spine values win over the mockups' `#2E8540`/`#B8860B`.)
- **UX-DR-8 — Beverage-type accents:** spirits `#7A4D00` / wine `#6B1F3A` / beer `#B8860B`, used **only** on the full-width banner; the type **word** is always present (beer banner keeps dark ink for contrast).
- **UX-DR-9 — Field comparison card states:** application value stacked **above** OCR value (vertical, never side-by-side); status chip right-aligned; **match** (quiet, 1px border, green ✓), **mismatch** (6px fail bar + tint + character diff on the differing span only), **soft/normalized** (amber bar + plain "capitalization differs; text matches" note, never red); plus distinct **not-found**, **OCR-unreadable**, and **blank-application** states (per EXPERIENCE.md State Patterns); mismatches/not-founds sort to top; "Why?" Accordion reveals CFR citation + raw OCR + rationale. Realizes FR-3, FR-18; supports SM-C2.
- **UX-DR-10 — Government Warning card:** "Required (27 CFR §16.21) vs On-label" layout in `ocr-raw` mono for character-aligned diffing; three never-conflated outcomes (wording deviation → char-diff FAIL; entirely absent → FAIL with plain copy, no diff-against-empty; bold/caps undeterminable → "couldn't verify" REVIEW). Realizes FR-13.
- **UX-DR-11 — Chevron Step Indicator behavior:** progress map (not a wizard); clicking a step **moves focus + scrolls** to that field group; conditional step ④ appears only when triggered and remaining steps **renumber cleanly**; current step carries a non-color marker. Realizes FR-5.
- **UX-DR-12 — Smart checklist behavior:** generated from the beverage-type ruleset; engine **pre-ticks** auto-PASS items (muted); REVIEW/FAIL items unticked + highlighted; clicking an item moves focus + scrolls to its card; "N of M done" counter; tick-state persists per submission across navigate-away **and full browser reload**, clears on disposition. Realizes FR-4.
- **UX-DR-13 — Image panel behavior:** 1–10 images paged with role labels (Brand/Back/Neck/Strip/Other), paging hidden for a single image; zoom; **Enhance toggle** shows the preprocessed image **alongside** the original (omitted, not inert, when no preprocessing was applied); per-image decode-failure placeholder; "no usable images" honest state. Realizes FR-7.
- **UX-DR-14 — Verdict-vs-Disposition separation in the UI:** advisory verdicts live in the muted Tag/Alert register labeled "Suggested:"; the three Dispositions live as full-register Buttons in the bottom action bar (Approve filled navy, Needs Correction outline navy, Reject outline red); **none pre-selected**; the bar disables on submit to prevent double-submit; on success returns to Queue with a brief **"Recorded — Undo"**; on save failure stays put and **retains Notes + tick-state**. **Notes required** for Needs Correction / Reject (soft-gate). Open-REVIEW-at-Approve → calm confirm modal. Realizes FR-6; enforces architecture contract #4.
- **UX-DR-15 — Accessibility floor (behavioral):** Section 508 / WCAG 2.x AA via USWDS; **color never alone** (icon+word everywhere); sized for older eyes (body ≥16px, comparison values 19px, targets ≥48px); keyboard-complete with tab order = reading order (left panel → right column → action bar); `aria-live` regions for "N of M done", suggested-verdict roll-up, Enhance toggle, and LLM-unavailable notice; on-load focus to the role=status summary; **char-diff text equivalent** + forced-colors survival; focus trap + return-focus for modal/Help; accessible Notes validation. Realizes NFR-4.
- **UX-DR-16 — Two-track interaction + shortcut safety:** mouse path always sufficient (one big obvious action per screen, click-to-scroll, click-to-expand); additive keyboard power path (`N`; `A`/`C`/`R` each routed through its confirm/Notes gate; `←`/`→` image faces; `?` Help; `Esc` close); **all single-letter shortcuts inert in any text input/textarea/contenteditable and while a modal owns focus**; auto-focus never auto-acts. Documented in Help.
- **UX-DR-17 — State patterns / honest states:** implement the full EXPERIENCE.md State Patterns table — cold load (no spinner dance), empty queue / empty type, item-not-ready (skipped), pipeline failure (visible per-check error), LLM-unavailable degrade-to-OCR notice, soft/normalized vs mismatch, can't-verify, OCR-unreadable, blank-application, all-REVIEW roll-up, zero-usable-images, disposition recorded/undo, save-fails-retains-work, refresh mid-review, cold demo start, demo-reset-while-open, benchmark-no-data, help-no-results. Realizes NFR-5; supports FR-9, FR-12.
- **UX-DR-18 — Voice and tone (microcopy):** plain, federal, calm (Plain Writing Act); advisory copy always returns authority to the human ("You decide", "needs your eyes"); limitations stated plainly in the same voice as capabilities (font-size, spatial co-location, OCR uncertainty); the EXPERIENCE.md Do/Don't copy table is the canonical microcopy source. Realizes NFR-5.

### FR Coverage Map

- **FR-1:** Epic 4 — Next Submission serves the next ready submission ≤5s.
- **FR-2:** Epic 4 — Next Submission by Beverage Type.
- **FR-3:** Epic 4 — Stacked field comparison with discrepancy highlighting.
- **FR-4:** Epic 4 — Per-type Checklist with verdicts + citations.
- **FR-5:** Epic 4 — Chevron review-progress status bar.
- **FR-6:** Epic 4 — Record Disposition (Approved / Needs Correction / Rejected).
- **FR-7:** Epic 4 — Label image display with preprocessing comparison.
- **FR-8:** Epic 4 — In-UI searchable help panel.
- **FR-9:** Epic 2 — Background processing at submission arrival (status enum + failure).
- **FR-10:** Epic 2 — Local OpenCV image preprocessing.
- **FR-11:** Epic 2 — Multi-engine OCR behind a uniform adapter.
- **FR-12:** Epic 2 — LLM extraction and fallback, toggleable.
- **FR-13:** Epic 3 — Government Warning exact verification (deterministic).
- **FR-14:** Epic 3 — Field Match with normalization tolerance.
- **FR-15:** Epic 3 — Per-type deterministic format Checks.
- **FR-16:** Epic 3 — Hybrid class/type Check (LLM capped at REVIEW).
- **FR-17:** Epic 3 — Flag-only Checks surface as REVIEW.
- **FR-18:** Epic 3 — Verdict provenance.
- **FR-19:** Epic 1 — Submissions schema and data dictionary.
- **FR-20:** Epic 1 — Seeded fixture corpus with Ground Truth.
- **FR-21:** Epic 5 — Accuracy scoring against Ground Truth.
- **FR-22:** Epic 5 — Speed and cost statistics (cost-per-1,000).
- **FR-23:** Epic 5 — Benchmark Report.
- **FR-24:** Epic 5 — Local-only tracing, toggleable.
- **FR-25:** Epic 1 — Token-gated access.
- **FR-26:** Epic 6 — Documentation deliverables.
- **FR-27:** Epic 6 — Demo data reset.
- **FR-28:** Epic 6 — Enqueue a fixture Submission live.

*NFR-1…NFR-6 are cross-cutting and addressed within the epics they touch: NFR-1 (Epics 2, 4), NFR-2 (Epics 1, 2, 6), NFR-3 (Epics 1, 4), NFR-4 (Epic 4 throughout; UX-DR-6/7/8/15), NFR-5 (Epics 5, 6; UX-DR-17/18), NFR-6 (all epics; AR-11).*

## Epic List

### Epic 1: Foundation, Data & Access
A deployed, token-gated app at a public URL with the seeded Mock COLA Database (30–50 fixtures + Ground Truth) and the vendored-USWDS shell in place — the data foundation and access boundary everything else reads.
**FRs covered:** FR-19, FR-20, FR-25
**Also:** AR-1 (init / Dockerfile / schema / seed), AR-2, AR-9, AR-10, AR-11, AR-13; UX-DR-1 (token-gate screen), UX-DR-6 (USWDS foundation); README scaffold (FR-26 partial).

### Epic 2: Pre-compute Pipeline & Multi-Engine Extraction
The 5-second mechanism: background jobs take each submission `received → processing → ready` via OpenCV preprocessing, dual-OCR behind a uniform adapter, and toggleable LLM extraction/fallback, with timing and provenance captured.
**FRs covered:** FR-9, FR-10, FR-11, FR-12
**Also:** AR-3 #1 (OCR/LLM adapter contract), AR-4 (engine-agnostic schema), AR-7 (both-variants OCR), AR-8 (offline / zero-egress proof).

### Epic 3: Compliance Engine & Rulesets
Given extracted data, the engine emits advisory PASS/REVIEW/FAIL per Check with provenance — deterministic Government Warning, field-match with tolerance, per-type format checks, hybrid class/type (LLM capped at REVIEW), and flag-only checks — across all three rulesets (spirits deepest, wine, malt beverage).
**FRs covered:** FR-13, FR-14, FR-15, FR-16, FR-17, FR-18
**Also:** AR-3 #2 (`normalize`), AR-3 #3 (`rollup`), AR-6 (rulesets-as-data with CFR citations).

### Epic 4: Review Workspace
The heart, where the specialist's value lands: Next Submission + next-by-type, stacked field comparison, smart checklist, chevron status bar, image panel + Enhance, Disposition capture, and in-UI Help — all rendered to the mockups under the UI fidelity standard.
**FRs covered:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8
**Also:** AR-3 #4 (verdict-vs-disposition separation), AR-5 (5s read-path contract), AR-14 (in-progress `review_progress` state + Undo); UX-DR-2/3/4 (Queue, Review, Help screens) and UX-DR-9 through UX-DR-18 (field cards, Gov Warning card, chevron, checklist, image panel, disposition bar, accessibility, interaction, state patterns, voice).

### Epic 5: Benchmark Harness & Procurement Study
Turns the pipeline's multi-engine/model exhaust into procurement evidence: accuracy vs Ground Truth, speed, cost-per-1,000 Verifications, local-only toggleable tracing, and the evaluator-facing Benchmark Report with grounded recommendations.
**FRs covered:** FR-21, FR-22, FR-23, FR-24
**Also:** UX-DR-5 (Benchmark Report screen).

### Epic 6: Evaluator Deliverables & Demo Operations
Makes the demo repeatable and the deliverable set complete: demo reset, live fixture enqueue, and the full `docs/` deliverable set + outbound-call inventory + USWDS-compliance notes linked from the README. Lands last because it documents and operates everything prior epics built.
**FRs covered:** FR-26, FR-27, FR-28

---

## Epic 1: Foundation, Data & Access

A deployed, token-gated app at a public URL with the seeded Mock COLA Database and the vendored-USWDS shell in place — the data foundation and access boundary everything else reads. Standalone outcome: an evaluator reaches the URL, is cleanly gated, and the seeded data is live behind it.

### Story 1.1: Containerized FastAPI project skeleton

As a developer building and deploying the POC,
I want a reproducible, offline-pinned FastAPI skeleton in a single Dockerfile,
So that every later story builds on one deterministic foundation that runs identically locally and on Railway.

**Acceptance Criteria:**

**Given** a clean checkout
**When** `docker build` runs against the Dockerfile
**Then** the image builds on `python:3.13-slim` with native deps (`tesseract-ocr`, `libgl1`, `libglib2.0-0`) and the pinned `requirements.txt` from `approved-tech-stack.md` (fastapi~=0.136, uvicorn, pydantic~=2.13, jinja2, apscheduler~=3.11, ruff, pytest)
**And** `docker run` serves a `GET /healthz` route returning 200
**And** the project tree matches the architecture's Project Structure (`app/` split by concern, `templates/`, `static/`, `tests/`, `fixtures/`, `models/`)
**And** `ruff` (line length 100) and `pytest` are configured in `pyproject.toml` and a placeholder test passes.

**Given** the firewall posture
**When** the container is started with `docker run --network none`
**Then** the app still boots and serves `/healthz` (no outbound call at startup).

### Story 1.2: Mock COLA Database schema & connection layer

As a developer,
I want the core Submissions and label-image tables plus a typed read layer,
So that application data can be stored and read consistently without an ORM.

**Acceptance Criteria:**

**Given** `db/schema.sql` authored from `docs/database-schema.md`
**When** the app initializes the SQLite database (file on the Railway Volume, WAL enabled)
**Then** the `submissions` table (Form 5100.31 application fields, `ttb_id`, `beverage_type`, `status`, `disposition`, `submitted_at`, `decided_at`) and the `label_images` child table (1–10 per submission) exist
**And** enums are stored as `TEXT + CHECK` in `UPPER_SNAKE` (`beverage_type`, `status`, `disposition`); `status` constrained to `RECEIVED, PROCESSING, READY_FOR_REVIEW, IN_REVIEW, DECIDED`
**And** column/table naming is `snake_case` plural per the architecture naming patterns; timestamps `_at` (UTC ISO-8601).

**Given** the typed read layer
**When** a row is read through `db/repositories.py`
**Then** it is validated/exposed via a Pydantic v2 model with `snake_case` fields
**And** raw SQL exists only inside `db/`; no other module issues SQL.

*Note: OCR/LLM/field-comparison/checklist tables are created in Epics 2 and 3 by the stories that need them — not front-loaded here.*

### Story 1.3: Seed the fixture corpus with Ground Truth

As an evaluator,
I want the database seeded with a realistic fixture corpus carrying Ground Truth,
So that the demo and the benchmark have reproducible data spanning all beverage types and verdict outcomes.

**Acceptance Criteria:**

**Given** `fixtures/` (synthetic label images + a Ground Truth CSV) and `db/seed.py`
**When** the seed script runs
**Then** 30–50 Submissions are loaded spanning distilled spirits, wine, and malt beverage, including clean labels, every-Check-violation examples, and a degraded-image tail (glare, angle, curvature)
**And** the corpus is composed so that — once the engine runs in Epic 3 — at least one Submission per Engine Verdict outcome (PASS / REVIEW / FAIL) exists per beverage type
**And** each Submission carries Ground Truth field values for accuracy scoring.

**Given** image constraints from `docs/image-handling.md`
**When** a Submission with 10 images is seeded
**Then** it round-trips correctly, and an attempt to attach an 11th image is rejected by validation
**And** no COLA-registry-sourced artwork appears in any public/demo flow (synthetic only)
**And** `docs/data-dictionary.md` covers every seeded field.

### Story 1.4: Vendored USWDS app shell & Treasury brand layer

As a Label Specialist and an evaluator,
I want the application chrome rendered in self-hosted USWDS with the Treasury brand layer,
So that every screen inherits the federal design system and firewall-safe assets.

**Acceptance Criteria:**

**Given** USWDS 3.x compiled assets vendored into `static/uswds/` (CSS/JS/fonts/icon-sprite) with Public Sans and Roboto Mono self-hosted
**When** any page renders from `templates/base.html`
**Then** all CSS/JS/font/icon requests are same-origin (no CDN, no Google Fonts, no build step)
**And** the Treasury brand-layer tokens from `DESIGN.md` are applied (primary navy `#112E51`, civic green `#2E5B46`, base `#F0F0F0`, ink `#1B1B1B`, squared corners 2/4/8, pill on chips only), replacing the USWDS default blue
**And** the utility header matches the header composition shown across the mockups (seal, "TTB Label Review" title, `[?]` Help control).

**Given** the firewall posture
**When** the shell renders under `docker run --network none`
**Then** the page is fully styled and fonts load (no missing-asset request). *(UX-DR-6, NFR-2, NFR-4)*

### Story 1.5: Token-gated access and clean denial

As an evaluator,
I want a lightweight token gate with no login ceremony,
So that I can reach the full demo while the public and bots cannot, and a bad token leaks nothing.

**Acceptance Criteria:**

**Given** a FastAPI token-gate dependency reading `ACCESS_TOKEN` from env
**When** a request arrives with the valid token
**Then** the app is reachable; **when** the token is absent or invalid, the response is a clean denial with no Submission data, images, or Benchmark figures in the payload.

**Given** the token-gate screen
**When** State 1 (token entry) and State 2 (clean denial) render
**Then** each **matches [`mockups/token-gate.html`](ux-designs/ux-TTB-label-POC-2026-06-12/mockups/token-gate.html) exactly** in layout, USWDS component structure, all depicted states, and visible copy — centered access card, seal, "Enter your access token to begin", single token input (autofocused), ≥48px navy **Enter** button, helper copy; denial state shows the `role="status"` "Access token required." alert and the `aria-invalid` input
**And** all design tokens resolve to `DESIGN.md` values (spine wins over any mockup CSS conflict)
**And** mockup-only scaffolding (browser device frame, placeholder URL) is excluded
**And** the story's Definition of Done includes a documented side-by-side comparison of both running states against the mockup file. *(FR-25, UX-DR-1, AR-9)*

### Story 1.6: Deploy to Railway with run-from-README

As an evaluator,
I want the app deployed at an HTTPS public URL and a README that runs it from a clean clone,
So that I can both reach the live demo and reproduce it locally.

**Acceptance Criteria:**

**Given** `railway.toml` (Dockerfile build, Volume mount for the SQLite file + generated images, healthcheck) and Railway Pro env vars (`ACCESS_TOKEN`, `LLM_ENABLED`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LANGCHAIN_*`)
**When** the service deploys from the Dockerfile (not Nixpacks)
**Then** the app is reachable at an automatic-HTTPS public URL behind the token gate, serving the seeded data.

**Given** a fresh evaluator with only the repo
**When** they follow the README
**Then** they can clone, build, and run locally (`docker compose up`), and `.env.example` documents every variable
**And** the README documents the offline egress smoke test (`docker run --network none -e LLM_ENABLED=false`)
**And** the README links the `docs/` set (full deliverable population completes in Epic 6). *(FR-26 partial, AR-2, AR-8)*

---

## Epic 2: Pre-compute Pipeline & Multi-Engine Extraction

The 5-second mechanism. Background jobs take each Submission `RECEIVED → PROCESSING → READY_FOR_REVIEW`: OpenCV preprocessing, dual-OCR behind a uniform adapter, and toggleable LLM extraction/fallback, with timing and provenance captured. Standalone outcome: submissions self-process and land ready with per-engine results stored, observable in the database.

### Story 2.1: Engine-agnostic OCR/LLM adapter contracts

As a developer and a procurement evaluator,
I want one centralized adapter shape for every OCR engine and every model, with engine-agnostic result storage,
So that adding an engine or model is a new adapter file with no schema change (the swap-and-compare procurement requirement).

**Acceptance Criteria:**

**Given** `app/contracts.py` as the single owner of the adapter shapes
**When** any OCR engine runs
**Then** it returns the identical `OcrResult` structure (`engine_name, engine_version, text, word_boxes, confidence, latency_ms, ran_on_cpu, status`); and every model adapter returns the identical `LlmResult` structure (`model_name, model_id, model_full_id, provider, task, result_text, prompt_tokens, completion_tokens, total_tokens, latency_ms, requested_at, responded_at, status`)
**And** the `ocr_results` and `llm_results` tables store per-engine/per-model rows independently (no merged-only storage), keyed by submission/image
**And** adding a hypothetical third engine requires only a new adapter file — no DDL change (demonstrated by a stub adapter test). *(AR-3 #1, AR-4, FR-11/FR-12 schema basis)*

### Story 2.2: Background sweep & submission lifecycle

As a Label Specialist,
I want submissions processed in the background the moment they arrive,
So that the review screen is already done thinking before I open it.

**Acceptance Criteria:**

**Given** in-process APScheduler sweeping `RECEIVED` rows with bounded job concurrency
**When** a seeded or enqueued Submission is picked up
**Then** it transitions `RECEIVED → PROCESSING → READY_FOR_REVIEW`, writing `audit_events` (`SEEDED/OCR_STARTED/OCR_COMPLETED/ANALYSIS_COMPLETED/READY`) and per-stage `processing_ms` + timestamps
**And** a stage failure (unreadable image, engine crash) lands the Submission in a visible error state, never a silent stall
**And** p95 time-to-ready ≤ 10 minutes on the deployment hardware.

*Note: this story establishes the lifecycle/orchestration machinery (`scheduler.py`, `run.py`, `status.py`); the real preprocessing/OCR/LLM stages are plugged in by Stories 2.3–2.5, so it ships with a minimal pass-through stage and is not blocked on them.* *(FR-9, AR-10)*

### Story 2.3: Local OpenCV image preprocessing

As a Label Specialist reviewing imperfect photos,
I want skewed/glared/low-contrast images cleaned up locally before OCR,
So that a readable-but-imperfect photo is handled without a correction cycle back to the applicant.

**Acceptance Criteria:**

**Given** `pipeline/preprocess.py` using local OpenCV tooling (deskew, perspective, glare/CLAHE contrast, denoise) per `docs/image-handling.md`
**When** the pipeline processes a degraded-fixture image
**Then** the cleaned image is written to the Volume and referenced alongside the original in `label_images` (neither replaces the other)
**And** no LLM or cloud call participates in preprocessing (fully local). *(FR-10)*

### Story 2.4: Tesseract + PaddleOCR extraction (both image variants)

As a procurement evaluator,
I want at least two OCR engines run independently over each submission's images, on both the original and preprocessed variants,
So that per-engine accuracy is comparable and the preprocessing benefit is measurable.

**Acceptance Criteria:**

**Given** Tesseract and PaddleOCR adapters implementing the `OcrResult` contract
**When** the pipeline OCRs a Submission
**Then** each engine's text, per-field values, confidence, and latency are stored separately
**And** for the degraded-fixture subset, OCR runs on **both** the original and the OpenCV-enhanced image (both `ocr_results` rows stored) so preprocessed-vs-original accuracy can be scored in Epic 5
**And** PaddleOCR weights load from the baked-in offline `models/` (no runtime download). *(FR-11, AR-7, AR-8)*

### Story 2.5: Toggleable LLM extraction & OCR-only fallback

As an IT stakeholder enforcing the firewall,
I want LLM extraction to be optional and the pipeline to degrade cleanly to OCR-only,
So that a provable zero-egress configuration exists and the demo never blocks on a model call.

**Acceptance Criteria:**

**Given** model adapters (OpenAI / Gemini / Anthropic + optional local VLM) implementing the `LlmResult` contract, gated by `LLM_ENABLED` / `LLM_PROVIDER` / `LLM_BASE_URL`
**When** `LLM_ENABLED=false`
**Then** the pipeline completes on OCR-only results and the run is fully functional
**And** when an LLM provider is unreachable at processing time, affected extractions fall back to OCR-only and the condition is recorded for the review screen's visible notice (Epic 4)
**And** each LLM call's model name/ID/full version, timestamps, latency, and token counts are persisted.

**Given** the egress smoke test
**When** the pipeline runs under `docker run --network none -e LLM_ENABLED=false`
**Then** it completes end-to-end with zero outbound calls. *(FR-12, AR-8, NFR-2)*

---

## Epic 3: Compliance Engine & Rulesets

Given extracted data, the engine emits an advisory PASS/REVIEW/FAIL per Check with full provenance — across all three rulesets (spirits deepest, wine, malt beverage) — using the determinism taxonomy: rule-bound Checks are deterministic code; ambiguity goes to REVIEW, never silent auto-decision. Standalone outcome: every ready Submission carries a complete, explainable set of Engine Verdicts.

### Story 3.1: Normalization & verdict roll-up contracts

As a developer,
I want the field-match normalization and verdict roll-up as two centralized, tested functions,
So that "STONE'S THROW" == "Stone's Throw" everywhere and the most-severe verdict always wins, with no divergent re-implementations.

**Acceptance Criteria:**

**Given** `app/normalize.py` owning `normalize(value, field_key)`
**When** it runs
**Then** it applies the fixed order (trim → collapse internal whitespace → Unicode NFKC → casefold → curly→straight quotes → strip trailing punctuation; numeric fields additionally parse to number+unit)
**And** "STONE'S THROW" and "Stone's Throw" normalize equal (a unit test asserts zero false-FAIL on this class, SM-C2).

**Given** `app/verdict.py` owning `rollup(verdicts)`
**When** a set of check verdicts is rolled up
**Then** any `FAIL` ⇒ `FAIL`; else any `REVIEW`/can't-verify ⇒ `REVIEW`; else `PASS`
**And** the `field_comparisons` and `checklist_items` tables are created here for the analysis job to write. *(AR-3 #2, AR-3 #3)*

### Story 3.2: Rulesets-as-data executor with verdict provenance

As a Label Specialist and an evaluator,
I want each beverage type's Checks defined as data with CFR citations, executed into an explainable checklist,
So that any verdict can be traced to its rule, inputs, and citation.

**Acceptance Criteria:**

**Given** per-Beverage-Type Rulesets stored as data (Check rows with `check_key`, determinism class, CFR citation string `"27 CFR <part>.<section>"`, source date) authored from `docs/regulatory-rules-*.md`, starting with the distilled-spirits ruleset
**When** `engine/run_checks.py` executes a Submission's ruleset
**Then** it writes one `checklist_items` row per Check, and `verdict.rollup` sets the submission's `engine_verdict`
**And** every verdict records its `check_key`, determinism class, CFR citation, the input values compared, and (for LLM-assisted checks) the model identification
**And** CFR text/citations live only as Ruleset data — never hard-coded in check logic. *(AR-6, FR-18)*

### Story 3.3: Field Match check with tolerance bands

As a Label Specialist,
I want application fields compared to OCR values with normalization tolerance,
So that real mismatches FAIL, soft differences go to REVIEW, and incidental case/punctuation differences PASS.

**Acceptance Criteria:**

**Given** `engine/checks/field_match.py` using `normalize()`
**When** it compares brand name, alcohol content, net contents, and name/address
**Then** a normalized match → PASS (both raw values retained), a near-miss / OCR-confidence-below-threshold → REVIEW, a substantive mismatch → FAIL
**And** "STONE'S THROW" vs "Stone's Throw" → PASS; application ABV 45% vs label 40% → FAIL. *(FR-14)*

### Story 3.4: Government Warning exact verification

As a Label Specialist,
I want the Government Warning verified deterministically against 27 CFR 16.21,
So that wording deviations are caught exactly the same way every time, with no model involved.

**Acceptance Criteria:**

**Given** `engine/checks/government_warning.py` (deterministic, no LLM)
**When** it verifies the warning
**Then** whitespace is normalized, body compared case-insensitively (all-caps body compliant), and required casing enforced (all-caps "GOVERNMENT WARNING:" header; capital S/G in "Surgeon General")
**And** title-case header, reworded text, or a missing statement → FAIL with the deviation identified; correct wording with incidental whitespace or an all-caps body → PASS
**And** the three outcomes are never conflated: wording deviation → char-diff FAIL; entirely absent from all images → FAIL with plain copy (no diff against empty); bold/caps undeterminable → "couldn't verify" REVIEW, never a silent PASS. *(FR-13)*

### Story 3.5: Per-type deterministic format checks

As a Label Specialist,
I want rule-bound formats validated per beverage type,
So that ABV/net-contents/standards-of-fill and conditional requirements are checked correctly without false rejects.

**Acceptance Criteria:**

**Given** `engine/checks/format_checks.py` and the cross-commodity matrix in `docs/label-requirements-by-type.md`
**When** it validates a Submission
**Then** alcohol-content statement format, net-contents format + standards-of-fill lookup, and name/address qualifying phrase are checked deterministically
**And** a spirits Submission missing an ABV statement → FAIL, while a ≤14% table-wine Submission without ABV is **not** failed and malt-beverage ABV is optional unless its trigger applies (the ABV false-reject trap respected)
**And** "750 mL" passes standards-of-fill; an off-standard size FAILs with citation; proof, when present, must equal 2 × ABV or → FAIL
**And** a conditional Check unevaluable from available data → REVIEW with explanation, never a guess. *(FR-15)*

### Story 3.6: Hybrid class/type designation check

As a Label Specialist,
I want the class/type designation validated by rules first and escalated to a model only when genuinely ambiguous,
So that an LLM opinion can advise but never produce a FAIL on its own.

**Acceptance Criteria:**

**Given** `engine/checks/class_type.py`
**When** it validates the designation
**Then** valid designations (e.g. "Kentucky Straight Bourbon Whiskey") validate deterministically with no LLM call
**And** genuinely ambiguous cases escalate to LLM assessment capped at REVIEW severity (never FAIL)
**And** conflicting designations across a Submission's multiple labels are detected deterministically → FAIL with both values cited
**And** with `LLM_ENABLED=false`, the check degrades to rules-only plus REVIEW for unresolved cases. *(FR-16)*

### Story 3.7: Flag-only checks surface as REVIEW

As a Label Specialist,
I want checks that can't be reliably auto-decided from a photo surfaced as REVIEW with an explanation,
So that the tool never guesses a PASS or FAIL it can't justify.

**Acceptance Criteria:**

**Given** `engine/checks/flag_only.py`
**When** it evaluates Same Field of Vision spatial inference, "separate and apart" placement, or severely degraded text
**Then** it emits REVIEW with an explanatory note, never PASS or FAIL
**And** a multi-image Submission whose trio co-location is undeterminable → REVIEW citing 27 CFR 5.63, reporting each element's individual presence. *(FR-17)*

### Story 3.8: Wine & malt-beverage rulesets at full depth

As a Label Specialist and an evaluator,
I want wine and malt-beverage rulesets as first-class as spirits,
So that the checklist correctly changes by beverage type.

**Acceptance Criteria:**

**Given** `engine/rulesets/wine.py` and `engine/rulesets/malt_beverage.py` authored from `docs/regulatory-rules-wine.md` and `docs/regulatory-rules-beer.md` with their conditional checks (sulfites, coloring, age, country of origin, etc.)
**When** a wine or malt-beverage Submission is analyzed
**Then** the Checklist contents differ correctly by type (e.g. no ABV demand on a ≤14% table wine; malt-beverage ABV conditional)
**And** the same deterministic check implementations (Stories 3.3–3.7) are reused via the ruleset data, not re-coded per type. *(FR-15, FR-16, FR-17 across types)*

---

## Epic 4: Review Workspace

The heart — where the specialist's value lands. Each UI story below is governed by the **UI fidelity standard** (Overview): the screen must reproduce its named mockup's layout, USWDS component structure, all states, and copy; tokens resolve to `DESIGN.md` (spine wins); mockup-only scaffolding excluded; and a documented side-by-side comparison against the mockup is in each story's Definition of Done. The **5s read contract** (AR-5) holds throughout: read routes do a DB read of pre-computed rows only.

### Story 4.1: Queue screen & Next Submission

As a Label Specialist,
I want one obvious **Next Submission** action that serves the next ready item instantly,
So that I start reviewing without hunting through a list.

**Acceptance Criteria:**

**Given** `GET /queue` and `POST /next` doing pre-computed DB reads only (no OCR/inference at request time)
**When** I click **Next Submission**
**Then** the oldest `READY_FOR_REVIEW` Submission is served (deterministic oldest-first), unready items skipped silently, and the review screen is fully interactive in ≤5s (SM-1)
**And** the Queue screen **matches [`mockups/queue.html`](ux-designs/ux-TTB-label-POC-2026-06-12/mockups/queue.html) exactly** in both states — State 1 (waiting: one large auto-focused Next Submission button with Enter firing and never auto-opening, the civic-green read-only stats strip, and the dashed Phase-2 triage placeholder marked not-live) and State 2 (empty: button disabled with the calm "No submissions waiting right now." copy) — layout, components, states, and copy
**And** tokens resolve to `DESIGN.md`, scaffolding excluded, side-by-side mockup check in the DoD. *(FR-1, UX-DR-2, AR-5)*

### Story 4.2: Next Submission by beverage type

As an evaluator,
I want to pull the next Submission of a specific beverage type,
So that I can demonstrate the engine knows its domain (e.g. wine rules differ).

**Acceptance Criteria:**

**Given** the beverage-type segmented filter (Any · Wine · Spirits · Beer) from `queue.html`
**When** a type is selected and I click Next Submission
**Then** the oldest ready Submission of that type is served
**And** when that type's queue is empty, the screen says so plainly ("The wine queue is empty. Try Any, or check back later.") with the filter staying set — not an error
**And** the filter control and empty-type copy match `mockups/queue.html`. *(FR-2, UX-DR-2)*

### Story 4.3: Review screen shell — banner, chevron, suggested-verdict alert

As a Label Specialist,
I want the review screen to orient me instantly with beverage type, progress, and the engine's suggestion,
So that I know what I'm looking at and where I am the moment it loads.

**Acceptance Criteria:**

**Given** `GET /review/{id}` rendering pre-computed rows
**When** the review screen loads
**Then** the **beverage-type banner** (accent + glyph + word + submission meta), the **chevron Step Indicator** (① Identity → ② Mandatory text → ③ Gov. Warning → ④ Conditional → ⑤ Decide; current step navy with a non-color marker; done steps ✓; conditional step ④ present only when triggered, remaining steps renumbering cleanly), and the **Suggested-verdict Alert** (verdict tint, "Suggested:", roll-up copy, "You decide.") all render per [`mockups/review-workspace.html`](ux-designs/ux-TTB-label-POC-2026-06-12/mockups/review-workspace.html) in the two-column layout
**And** the advisory verdict appears only in the muted Tag/Alert register — never as a button and never pre-selecting a disposition (verdict-vs-disposition separation)
**And** tokens resolve to `DESIGN.md` (spine PASS `#216E29`/REVIEW `#7A5900` win over the mockup's CSS), scaffolding excluded, side-by-side mockup check in the DoD. *(FR-5, UX-DR-3, UX-DR-11, AR-3 #4)*

### Story 4.4: Stacked field comparison cards

As a Label Specialist,
I want each application field stacked above its OCR value with the discrepancy highlighted,
So that I confirm a match in a single glance and the real problems jump out.

**Acceptance Criteria:**

**Given** the right-column field cards
**When** the comparison renders
**Then** the application value sits **above** the OCR value (vertical, never side-by-side), each card carries its right-aligned verdict chip (icon+word+color), and cards render in the three core states — **match** (quiet 1px border, green ✓), **mismatch** (6px fail bar + tint + character diff on the differing span only), **soft/normalized** (amber bar + plain "capitalization differs; text matches" note, never red)
**And** the distinct **not-found**, **OCR-unreadable**, and **blank-application** states render per the EXPERIENCE.md State Patterns; mismatches/not-founds sort to top, matches sink
**And** a "Why?" Accordion reveals CFR citation + raw OCR + verdict rationale
**And** the cards match `mockups/review-workspace.html` (layout/states/copy), tokens per `DESIGN.md`, side-by-side check in the DoD. *(FR-3, FR-18 surface, UX-DR-9)*

### Story 4.5: Government Warning comparison card

As a Label Specialist,
I want the Government Warning shown as required-vs-on-label with a character-level diff,
So that a wording deviation is unmistakable.

**Acceptance Criteria:**

**Given** the specialized Government Warning card
**When** it renders
**Then** the required §16.21 text and the on-label OCR text are stacked in `ocr-raw` mono for character-aligned diffing, with the differing span highlighted (plus a screen-reader text equivalent)
**And** the three outcomes render distinctly — wording deviation → char-diff FAIL; entirely absent → FAIL with plain "Required Government Warning not found on the submitted images" (no diff against empty); bold/caps undeterminable → "couldn't verify" REVIEW
**And** the card matches the Government Warning block in `mockups/review-workspace.html`, side-by-side check in the DoD. *(FR-13 surface, UX-DR-10)*

### Story 4.6: Smart checklist

As a Label Specialist,
I want a per-type checklist that pre-ticks what the engine auto-verified and highlights what needs my eyes,
So that it works as my table of contents through the review.

**Acceptance Criteria:**

**Given** the checklist generated from the beverage-type ruleset
**When** the review screen renders
**Then** auto-verified PASS items are pre-ticked and muted (the engine's `checklist_items` verdicts); REVIEW/FAIL items are unticked and highlighted; an "N of M done" counter shows progress
**And** clicking a checklist item moves focus + scrolls to its field card
**And** a **manual** tick is persisted server-side via `POST /review/{id}/progress` into the `review_progress.ticked_check_keys` row (the human-tick layer, kept separate from the pipeline-owned `checklist_items`); `GET /review/{id}` rehydrates the merged tick-state, so it persists per Submission across navigate-away **and full browser reload**, clearing only on a recorded disposition
**And** the checklist matches `mockups/review-workspace.html`, side-by-side check in the DoD. *(FR-4, UX-DR-12, AR-14)*

### Story 4.7: Label image panel & Enhance toggle

As a Label Specialist,
I want to page through the label images and compare the original to the preprocessed version,
So that I can read a degraded photo and confirm by eye.

**Acceptance Criteria:**

**Given** the left-column image panel
**When** a Submission with 1–10 images renders
**Then** images page with role labels (Brand/Back/Neck/Strip/Other), paging is hidden for a single image, and zoom is available
**And** the **Enhance toggle** shows the OpenCV-preprocessed image **alongside** the original (neither silently replaces the other); the toggle is **omitted** (not shown inert) when no preprocessing was applied
**And** a per-image decode failure shows an honest "couldn't load this image" placeholder while other faces still display; zero usable images shows the honest panel state
**And** the panel matches `mockups/review-workspace.html`, side-by-side check in the DoD. *(FR-7, UX-DR-13)*

### Story 4.8: Disposition action bar & Notes

As a Label Specialist,
I want to record exactly one disposition with a reason when needed,
So that I commit the official decision and the engine never makes it for me.

**Acceptance Criteria:**

**Given** the bottom Notes + Disposition action bar
**When** it renders
**Then** the three controls — Approve (filled navy), Needs Correction (outline navy), Reject (outline red) — show with **none pre-selected**, and `disposition` is a separate enum from `engine_verdict` with no function mapping one to the other (AR-3 #4)
**And** Notes are **required** for Needs Correction / Reject (soft-gate), optional for Approve; recording an Approve while REVIEW items are open prompts a calm confirm modal
**And** the in-progress Notes are persisted as `review_progress.draft_notes` via `POST /review/{id}/progress` (so they survive a mid-review reload, AR-14); `POST /review/{id}/disposition` persists the disposition + `decided_at`, promotes `draft_notes` to `submissions.decision_notes`, the bar disables on submit to prevent double-submit, and on success returns to Queue with a brief "Recorded — Undo"
**And** the **"Recorded — Undo"** affordance calls `POST /review/{id}/undo`, which clears `disposition`/`decided_at`/`decision_notes`, applies the single bounded backward transition `DECIDED → READY_FOR_REVIEW`, writes an `UNDONE` audit event, and reopens the item with the retained `review_progress` ticks + draft Notes restored; after it dismisses the disposition is final for the POC
**And** on save failure the screen stays put, re-enables the bar, shows an honest error, and **retains Notes + tick-state** (the `review_progress` row is intact)
**And** the action bar matches `mockups/review-workspace.html`, side-by-side check in the DoD. *(FR-6, UX-DR-14, AR-3 #4, AR-14)*

### Story 4.9: In-UI Help panel

As a Label Specialist,
I want a one-click searchable help panel,
So that I can understand the screen and the PASS/REVIEW/FAIL vocabulary without leaving my work.

**Acceptance Criteria:**

**Given** the `[?]` control in the header on every screen
**When** Help opens
**Then** a right-anchored slide-over (`role="dialog"`, focus-trapped, Esc closes, returns focus to `[?]`) shows the search box, the browsable KB list, the PASS/REVIEW/FAIL verdict explainer (icon+word+color with the verdict-vs-disposition reminder), the keyboard-shortcuts list, and the calm no-results state
**And** the panel **matches [`mockups/help-panel.html`](ux-designs/ux-TTB-label-POC-2026-06-12/mockups/help-panel.html)** in layout, components, states, and copy; tokens per `DESIGN.md`; side-by-side check in the DoD. *(FR-8, UX-DR-4)*

### Story 4.10: Keyboard power path & shortcut safety

As a high-volume Label Specialist,
I want keyboard shortcuts that never fire by accident,
So that I can move fast without risking an irreversible federal act.

**Acceptance Criteria:**

**Given** the documented keyboard path
**When** I use it
**Then** `N` = Next Submission; `A`/`C`/`R` = Approve/Needs Correction/Reject each routed through its confirm/Notes gate; `←`/`→` move between image faces; `?` opens Help; `Esc` closes the topmost layer
**And** all single-letter shortcuts are **inert when focus is in any text input/textarea/contenteditable and while a modal owns focus** (typing a correction reason can never fire `R`)
**And** the mouse path remains fully sufficient on its own (shortcuts are additive); auto-focus never auto-acts. *(UX-DR-16)*

### Story 4.11: Honest state patterns & accessibility verification

As the lowest-tech-comfort Label Specialist and a screen-reader user,
I want every honest state handled and the accessibility floor held across the workspace,
So that the tool is calm, never silently wrong, and usable by everyone.

**Acceptance Criteria:**

**Given** the EXPERIENCE.md State Patterns
**When** edge states occur
**Then** cold load renders the result as first paint (no spinner dance); a pipeline failure shows a visible per-check error; an LLM-unavailable check degrades to OCR-only with a visible `aria-live` notice; a demo reset while an item is open routes back to Queue gracefully; a mid-review refresh resumes from persisted Notes + tick-state (rehydrated from the `review_progress` row, AR-14)
**And** the accessibility floor holds: color never alone (icon+word everywhere), body ≥16px / comparison values 19px / targets ≥48px, tab order = reading order (left panel → right column → action bar), `aria-live` regions announce the "N of M done" counter and suggested-verdict roll-up, the char-diff carries a text equivalent surviving forced-colors mode, and Notes validation is announced (not color-only)
**And** all microcopy follows the EXPERIENCE.md voice/tone table (plain, federal, calm; authority returned to the human; limitations stated plainly). *(UX-DR-15, UX-DR-17, UX-DR-18, NFR-4, NFR-5)*

---

## Epic 5: Benchmark Harness & Procurement Study

Turns the pipeline's multi-engine/model exhaust into procurement evidence: accuracy vs Ground Truth, speed, cost-per-1,000 Verifications, and local-only tracing — culminating in the evaluator-facing Benchmark Report. Standalone outcome: an evaluator leaves with buying data, not just a demo.

### Story 5.1: Local-only toggleable tracing

As an IT stakeholder,
I want instrumentation that captures model identification and timing locally and can be switched off,
So that benchmark data is collected without any telemetry leaving the host.

**Acceptance Criteria:**

**Given** `benchmark/tracing.py` (LangChain, local mode) gated by `LANGCHAIN_TRACING_ENABLED`
**When** tracing is enabled
**Then** model name/ID/full version, timestamps, latency, and token counts are written to the local DB only (no egress)
**And** when disabled, no tracing code path executes and the review workspace behaves identically. *(FR-24, NFR-2)*

### Story 5.2: Accuracy scoring against Ground Truth

As a procurement evaluator,
I want each OCR engine and model scored per field against Ground Truth,
So that I can compare extraction accuracy on the same footing.

**Acceptance Criteria:**

**Given** `benchmark/scoring.py`
**When** the harness runs over the seeded corpus
**Then** it computes field-level match rates (and CER) per engine/model, reported per field (brand name, ABV, net contents, Government Warning presence/exactness) and in aggregate
**And** re-running the harness over the seeded corpus reproduces the figures
**And** preprocessed-vs-original OCR accuracy is comparable from the both-variants rows (Story 2.4). *(FR-21)*

### Story 5.3: Speed & cost statistics with cost-per-1,000

As a procurement evaluator,
I want latency and cost captured per engine/model,
So that I get a defensible cost-per-1,000-Verifications figure.

**Acceptance Criteria:**

**Given** `benchmark/cost.py`
**When** it computes statistics
**Then** per-engine/per-model latency and per-call cost inputs (tokens × unit price; $0 marginal for local engines) yield a cost-per-1,000-Verifications figure for every configuration, including the local-only one
**And** the pricing basis is stated explicitly: published API prices proxy internally-hosted model cost, labeled as such (NFR-5)
**And** CPU-only-mode figures are captured. *(FR-22, NFR-1)*

### Story 5.4: Benchmark Report screen

As a procurement evaluator,
I want the engines and models laid out side by side on accuracy, latency, and cost,
So that I can compare the options and see the recommendation.

**Acceptance Criteria:**

**Given** `GET /benchmark` rendering real seeded-corpus runs (not hand-entered numbers)
**When** the report loads
**Then** it **matches [`mockups/benchmark-report.html`](ux-designs/ux-TTB-label-POC-2026-06-12/mockups/benchmark-report.html) exactly** — evaluator header with "Evaluator build" badge, civic-green Recommendations callout, the grouped comparison table (OCR engines / Language models; columns: field accuracy, latency ms/item, cost/1,000 USD, CPU-only flag; best-in-group row highlighted; figures in mono; verdict palette kept off this surface), the CPU-only flag as icon+word+color, the "indicative, not audited" honesty note, and the footer meta
**And** before any run has populated figures, the honest "No benchmark runs yet" empty state shows (not zeros)
**And** the report closes with grounded recommendations (best OCR, best LLM, best overall); tokens per `DESIGN.md`; read-only; side-by-side mockup check in the DoD. *(FR-23, UX-DR-5, NFR-5)*

---

## Epic 6: Evaluator Deliverables & Demo Operations

Makes the demo repeatable and the deliverable set complete. Lands last because it operates and documents everything prior epics built. Standalone outcome: an evaluator can reset and re-run the demo indefinitely and verify every claim from the docs.

### Story 6.1: Demo data reset

As an evaluator,
I want to reset the demo to its seeded state,
So that the demo is never permanently exhausted.

**Acceptance Criteria:**

**Given** `POST /reset` (operator route)
**When** it runs
**Then** it transactionally re-seeds — restoring the full pending queue, clearing recorded `disposition`/`decided_at`/`decision_notes`, resetting `status`, purging generated preprocessed images, and purging all `review_progress` rows (AR-14)
**And** after all seeded Submissions have received Dispositions, reset restores the full pending queue
**And** reset is reachable without redeployment. *(FR-27, AR-12)*

### Story 6.2: Live fixture enqueue

As an evaluator,
I want to trigger a fresh fixture Submission and watch it process,
So that I can see the Pre-compute Pipeline work end to end.

**Acceptance Criteria:**

**Given** `POST /enqueue` (operator route)
**When** it runs
**Then** it inserts a fresh fixture as a `RECEIVED` row only (the scheduler picks it up — the web layer never runs the pipeline synchronously)
**And** the Submission is observable transitioning through the lifecycle the UI narrates as *submitted → processing → ready* — whose **canonical stored enum values are the architecture's** `RECEIVED → PROCESSING → READY_FOR_REVIEW` (AR-10); the lowercase words are user-facing copy, not the persisted values
**And** once ready it is servable via Next Submission with full Engine Verdicts. *(FR-28, AR-12)*

### Story 6.3: Documentation deliverable set & outbound-call inventory

As a take-home evaluator,
I want the complete documentation set with the firewall posture proven,
So that I can set up, run, and trust the POC from the repo alone.

**Acceptance Criteria:**

**Given** the README and `docs/` set
**When** an evaluator reads them
**Then** the README provides setup/run instructions and links every `docs/` deliverable (approach, tools used, assumptions, trade-offs/limitations, pre-search, data dictionary incl. supported image types, per-type Ruleset docs, landscape narrative incl. the Applicant's COLAs Online workflow, USWDS-compliance notes)
**And** the **outbound-call inventory** enumerates every external call the deployed app can make, each classified `none` / `local` / `models-internal-endpoint`
**And** a fresh evaluator can clone, set up, and run locally from the README alone
**And** limitations (font-size non-checking, mock data, prototype status) are documented beside the capabilities (NFR-5). *(FR-26, NFR-2, NFR-5)*
