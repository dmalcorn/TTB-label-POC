---
title: "TTB COLA Label Specialist Workspace (POC)"
status: final
created: 2026-06-11
updated: 2026-06-12
---

# PRD: TTB COLA Label Specialist Workspace (POC)

*Working title — confirm.*

## 0. Document Purpose

This PRD is for Diane (builder/PM), the downstream BMad workflow owners (UX, architecture, epics & stories, dev), and secondarily the take-home evaluators, for whom the planning-artifact trail is itself evidence of a disciplined AI-assisted engineering process. It builds on the product brief (`_bmad-output/planning-artifacts/briefs/brief-TTB-label-POC-2026-06-11/brief.md`), the domain research report (`_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md`), the take-home assignment (`ref-docs/TTB-take-home-instructions.md`), and Diane's decision register (`ref-docs/discussion-points.md`) — it does not duplicate them. Vocabulary is Glossary-anchored (§3); features are grouped with globally numbered FRs nested; inferences carry inline `[ASSUMPTION]` tags indexed in §9. Technical depth that belongs downstream lives in `addendum.md` beside this file.

## 1. Vision

About 47 TTB Label Specialists — down from more than 100 in the 1980s — review roughly 150,000 alcohol-label applications a year, and by their own account half of that work is data-entry verification: confirming that the brand name, alcohol content, and Government Warning on the label match the application. The last automation attempt took 30–40 seconds per label; specialists could check five by eye in that time, so they quietly abandoned it. The earned lesson — *"if we can't get results back in about 5 seconds, nobody's going to use it"* — is this product's identity. Speed is the trust mechanism.

This POC is the Label Specialist's review workspace: a tool that is **already done thinking by the time the specialist sits down**. OCR and compliance checks run as background jobs the moment a Submission arrives, so when a specialist clicks **Next Submission**, the review screen — label images, application fields, advisory findings — loads in about five seconds or less. The engine recommends (PASS / REVIEW / FAIL per Check); the human decides (Approved / Needs Correction / Rejected). It never overrides or second-guesses the specialist — keeping the human in command is what makes the speed trustworthy enough to adopt.

The POC is simultaneously a **procurement study**: every Submission is processed by two OCR engines and several LLMs in parallel, with speed, accuracy, and cost captured per engine and model, producing a cost-per-1,000-Verifications figure. If the prototype succeeds, Phase 2 integrates it with the real COLA system via an API — and the pattern generalizes to any federal review desk buried in routine document-matching. No tool for the federal reviewer's side of COLA publicly exists; the POC steps into an empty room.

## 2. Target User

### 2.1 Jobs To Be Done

- **Functional (Label Specialist):** clear the routine matching checks on a Submission in seconds instead of minutes; apply the Government Warning rule the same exact way every time; record a Disposition and move on.
- **Emotional (Label Specialist):** stop spending expert judgment on rote matching; trust that the tool will not slow me down, fight me, or make my call for me.
- **Functional (Deputy Director / sponsor):** evidence of throughput improvement potential and adoption-worthiness.
- **Functional (IT):** confirmation the tool respects the firewall boundary, stores no PII, and runs in the browser off a central system.
- **Functional (take-home evaluator):** a working, testable prototype with clean code, documented trade-offs, and procurement-grade comparison data.

### 2.2 Non-Users (v1)

- **Applicants / industry members** — this is exclusively the federal reviewer's side. No applicant-facing screens, no pre-screening service.
- **The public** — the demo URL is token-gated; only evaluators reach it.

### 2.3 Key User Journeys

*Personas are drawn from the assignment's stakeholder interviews; scenes are constructed from their own accounts.* `[ASSUMPTION: journey beats inferred from interview notes, not separately narrated by Diane]`

- **UJ-1. Dave clears a clean bourbon label without breaking stride.**
  Dave, 28-year veteran who still prints his email, has watched every modernization attempt make his job harder. He opens the workspace (token URL, no login ceremony) and clicks **Next Submission**. In under five seconds the screen is ready: label images on one side; each application field stacked vertically with the machine-read value directly beneath it, every pair already marked. Brand name, ABV, net contents, warning — all PASS; the Checklist for distilled spirits shows green down the line. He eyeballs the label once — the judgment habit of 28 years — clicks **Approved**, and clicks **Next Submission** again. Total elapsed: well under a minute. The tool never asked him to wait, hunt for a button, or argue with a machine's opinion. **Edge case:** the application says "STONE'S THROW," the label reads "Stone's Throw." The engine normalizes case and punctuation, marks the Field Match PASS with a note showing both values — it does not bother Dave with a false mismatch.

- **UJ-2. Jenny catches a creative Government Warning.**
  Jenny, 8 months in, used to work from a printed desk checklist. Her next Submission is a gin label whose warning statement reads "Government Warning" in title case, slightly reworded. The engine has already marked the Government Warning Check **FAIL** — exact-wording comparison, with the deviation highlighted character-precisely — and the brand-name Check **REVIEW**, because the label photo came in at an angle with glare (the pipeline's preprocessed image is displayed beside the original). Jenny confirms the warning violation in one glance, uses the Checklist to verify the remaining required items, records **Needs Correction**, and the Submission leaves her queue. What used to be her trickiest eyes-only check — word-for-word warning verification — is now the easiest.

- **UJ-3. An evaluator stress-tests the demo and walks away with procurement data.**
  A take-home evaluator opens the token-gated URL. They click **Next Submission** repeatedly, timing readiness; they pull a wine Submission via next-by-type and note the Checklist changes to wine rules (no ABV demand on a table wine); they deliberately review a degraded-photo Submission. Then they open the **Benchmark Report**: Tesseract vs. PaddleOCR and three LLMs side by side — per-field accuracy against Ground Truth, latency, and cost per 1,000 Verifications. They leave with both impressions the project was designed to create: *the screen was already done thinking*, and *this team handed us buying data, not just a demo.*

## 3. Glossary

*FRs, UJs, and SMs use these terms verbatim; no synonyms elsewhere in this PRD.*

- **COLA** — Certificate of Label Approval, issued by TTB when a label application is approved.
- **COLAs Online** — TTB's real applicant-facing e-filing system (since 2003). The POC does not touch it; the Mock COLA Database stands in for its data store.
- **Submission** — one label application awaiting review: application fields plus 1–10 label images. The unit of work served to a Label Specialist.
- **Label Specialist** — the federal reviewer (TTB's official title). The POC's primary user. Synonyms (agent, examiner, adjudicator) are not used.
- **Applicant** — the industry member who filed the Submission. Not a user of this product.
- **Beverage Type** — distilled spirits, wine, or malt beverage. Determines which Ruleset applies.
- **Ruleset** — the per-Beverage-Type set of Checks, derived from 27 CFR Parts 5 (spirits), 4 (wine), 7 (malt beverages), and 16 (warning), stored as data with citations and source dates.
- **Check** — one verifiable label requirement within a Ruleset (e.g., Government Warning exact wording; brand-name Field Match). Each Check has a determinism class: deterministic, field-match, hybrid, or flag-only.
- **Field Match** — comparison of an application field value against the corresponding OCR-extracted value, with normalization tolerance (case, punctuation, whitespace).
- **Engine Verdict** — the advisory result of a Check: **PASS / REVIEW / FAIL**. Never a decision.
- **Disposition** — the Label Specialist's official decision on a Submission: **Approved / Needs Correction / Rejected** (TTB's real states). Distinct vocabulary from Engine Verdict.
- **Government Warning** — the health warning statement mandated by 27 CFR Part 16, with exact required wording and a caps-and-bold "GOVERNMENT WARNING:" header.
- **Same Field of Vision** — 27 CFR 5.63 requirement that brand name, alcohol content, and class/type appear together on one viewable side.
- **Pre-compute Pipeline** — the background jobs that preprocess images, run OCR, and execute Checks at Submission arrival, so review screens load instantly.
- **Mock COLA Database** — the POC's seeded database of dummy Submissions, modeled on Form 5100.31 fields. Read-only for the review workspace except Disposition capture and engine writes.
- **Ground Truth** — the known-correct field values stored with each seeded Submission, against which OCR/LLM extraction accuracy is scored.
- **Benchmark Harness** — the instrumentation that runs multiple OCR engines and LLMs over the same Submissions and captures speed, accuracy, and cost statistics.
- **Verification** — one complete extraction-plus-Checks pass over one Submission by one engine/model configuration. The denominator of the cost-per-1,000-Verifications figure.
- **Checklist** — the in-UI, per-Beverage-Type walk of required Checks; the digital descendant of the paper checklist specialists keep at their desks.
- **TTB ID** — the identifier a Submission carries (issued at filing in the real system; seeded in the mock).

## 4. Features

### 4.1 Review Workspace

**Description:** The Label Specialist's single screen of work. One entry point — **Next Submission** — serves the next queued Submission directly; there is no list to browse. The screen shows the label images, every application field stacked vertically with its OCR-extracted value directly beneath it (vertical, not side-by-side — horizontal layouts force the eyes too far apart), each pair carrying its Engine Verdict with discrepancies highlighted. The Beverage Type is instantly visible, the Checklist walks the required Checks for that type, and a chevron-style status bar shows where the specialist is in the review. The specialist records a Disposition and the workspace serves the next Submission. Realizes UJ-1, UJ-2. Designed against the hardest adoption gate: obvious and instant enough that Dave keeps using it past day one.

**Functional Requirements:**

#### FR-1: Serve next Submission
A Label Specialist can click **Next Submission** and be served the next pending Submission with the review screen fully loaded — label images, application fields, OCR values, Engine Verdicts, Checklist. Realizes UJ-1.
**Consequences (testable):**
- Screen is fully interactive in ≤ 5 seconds from click (see NFR-1), with all pre-computed findings present — readiness is not faked by progressive loading of verdicts. `[ASSUMPTION: a Submission whose pipeline run is incomplete is skipped in queue order rather than served partially]`
- Queue order is deterministic (oldest pending first) so demos are reproducible. `[ASSUMPTION]`

#### FR-2: Serve next Submission by Beverage Type
A Label Specialist can request the next Submission of a specific Beverage Type (next spirits / next wine / next malt beverage). Realizes UJ-3.
**Consequences (testable):**
- If the selected Beverage Type has no pending Submissions, the screen says so plainly rather than erroring.

#### FR-3: Stacked field comparison with discrepancy highlighting
A Label Specialist can see each application field with the OCR-extracted value directly beneath it and the Field Match Engine Verdict per pair, with any discrepancy visually highlighted, so a match is confirmed in a single glance. Realizes UJ-1.
**Consequences (testable):**
- A normalized match ("STONE'S THROW" / "Stone's Throw") shows PASS with both raw values visible.
- A mismatch highlights the differing portion, not just the field.

#### FR-4: Per-type Checklist
A Label Specialist can walk a visible Checklist of the Ruleset Checks for the Submission's Beverage Type, each item carrying its Engine Verdict and CFR citation. Realizes UJ-2, UJ-3.
**Consequences (testable):**
- Checklist contents differ correctly by Beverage Type (e.g., ABV item required for spirits, conditional for wine and malt beverages).
- Each item links to or displays the regulation citation text stored in the Ruleset.

#### FR-5: Review progress status bar
A Label Specialist can see a chevron-style status bar showing the steps of the current review and overall progress (step N of M).
**Consequences (testable):**
- Steps correspond to the Checklist's required-Check groups for the Beverage Type; status reflects Checklist completion state and updates as the specialist works.

#### FR-6: Record Disposition
A Label Specialist can record exactly one Disposition — Approved, Needs Correction, or Rejected — on the served Submission, after which the Submission leaves the pending queue. Realizes UJ-1, UJ-2.
**Consequences (testable):**
- Disposition and `decided_at` timestamp are persisted to the Mock COLA Database.
- Engine Verdicts never pre-select or default the Disposition control; the engine recommends, the human decides.

#### FR-7: Label image display with preprocessing comparison
A Label Specialist can view all 1–10 label images of a Submission, and where the Pre-compute Pipeline produced a cleaned image (deskew, glare, contrast), view it beside the original. Realizes UJ-2.
**Consequences (testable):**
- Both original and preprocessed image are available for a degraded-image Submission; neither replaces the other silently.

#### FR-8: In-UI help
A Label Specialist can open clear, easy-to-find help describing the screen and each Check. `[ASSUMPTION: v1 help is a static, searchable help panel — not a full knowledge-base product; the register's knowledge-base ambition is Phase 2]`
**Consequences (testable):**
- Help is reachable from the review screen in one click and explains the PASS / REVIEW / FAIL vocabulary and each Checklist item.

**Feature-specific NFRs:** Layout designed for a minimum 24-inch monitor (27-inch or dual-24 typical). Usability bar: obvious enough that a 73-year-old uses it without hunting for a button.

### 4.2 Pre-compute Pipeline

**Description:** The architectural answer to the 5-second wall. When a Submission arrives in the Mock COLA Database (seeded, or inserted during a demo), background jobs — not request-time processing — preprocess its images (OpenCV-class local clean-up: deskew, perspective, glare, contrast), run each OCR engine, optionally run LLM extraction, execute the applicable Ruleset, and store extracted fields, Engine Verdicts, and timing statistics. By the time a Label Specialist pulls the Submission, everything is already done. Realizes UJ-1, UJ-2. The pipeline is also the Benchmark Harness's data producer (§4.5).

**Functional Requirements:**

#### FR-9: Background processing at Submission arrival
The system processes each newly arrived Submission in the background — image preprocessing, OCR extraction per engine, Check execution — without any Label Specialist action, and marks the Submission ready for review on completion.
**Consequences (testable):**
- A newly seeded Submission transitions through a minimal status enum (e.g., `submitted → processing → ready`) observable in the database. `[ASSUMPTION: exact enum values are an architecture decision; the PRD requires only submitted/processing/ready semantics plus failure state]`
- Time-to-ready is bounded: p95 ≤ 10 minutes from Submission arrival to `ready` on the deployment hardware. `[ASSUMPTION: generous bound — real queue latency is days; the bound exists so the 5-second readiness claim is falsifiable rather than achieved by indefinite skipping]`
- `submitted_at`, processing timestamps, and per-stage `processing_ms` are persisted.
- A pipeline failure (unreadable image, engine crash) lands the Submission in a visible error state, not a silent stall.

#### FR-10: Local image preprocessing
The system improves imperfect label images (skew, perspective, glare, low contrast) using local, non-LLM tooling before OCR — so a readable-but-imperfect photo is handled without a correction cycle back to the Applicant — storing the cleaned image alongside the original. Realizes UJ-2.
**Consequences (testable):**
- Across the degraded fixture subset in aggregate, OCR field-level accuracy on preprocessed images strictly exceeds accuracy on the originals (captured by the Benchmark Harness).

#### FR-11: Multi-engine OCR extraction
The system runs at least two OCR engines (Tesseract and PaddleOCR) over each Submission's images in independent background jobs with a uniform interface, storing each engine's extracted text, per-field values, confidence, and latency separately.
**Consequences (testable):**
- Per-engine results are independently queryable for the same Submission (no merged-only storage).
- Adding a third engine requires no schema change. `[ASSUMPTION: engine-agnostic result schema is a requirement, not an implementation detail, because swap-and-compare is a stated procurement goal]`

#### FR-12: LLM extraction and fallback
The system can run LLM-based field extraction on Submissions — both for Benchmark Harness comparison and as a fallback when OCR Field Match confidence is poor. LLM use is optional and toggleable; the deployed POC's LLM calls model government-internal endpoints (see NFR-2).
**Consequences (testable):**
- With LLMs toggled off, the pipeline still completes and the review screen functions on OCR-only results.
- If an LLM provider is unreachable at processing time, the affected Checks degrade to OCR-only results with a visible notice on the review screen; the review screen never blocks on an LLM call.
- Each LLM call's model name, model ID, full version ID, timestamps, latency, and token counts are persisted.

### 4.3 Compliance Engine

**Description:** Executes the Ruleset for the Submission's Beverage Type and emits an advisory Engine Verdict per Check. The engine's discipline is its determinism taxonomy: rule-bound Checks are deterministic code, never LLM calls; ambiguity goes to REVIEW, never to silent auto-decision. Distilled spirits is the most fully worked Ruleset; wine and malt beverages are first-class with their own Rulesets. Rulesets store CFR citations **as data with source dates** (the 2022 Part 5 renumbering is the cautionary tale). Realizes UJ-1, UJ-2.

**Functional Requirements:**

#### FR-13: Government Warning exact verification
The system verifies the Government Warning deterministically: exact required wording per 27 CFR 16.21, "GOVERNMENT WARNING:" header in capitals, one statement. Whitespace is normalized; body text is compared case-insensitively (an all-caps body is compliant); required casing — the all-caps header and the capital S and G in "Surgeon General" — is enforced exactly. Realizes UJ-2.
**Consequences (testable):**
- Title-case "Government Warning" header, reworded text, or missing statement → FAIL with the deviation identified.
- Correct wording with incidental whitespace differences, or an all-caps body, → PASS.
- Bold detection on the header is best-effort from images: where boldness cannot be determined, the Check reports it as not-verified (a stated limitation), never as a silent PASS. `[ASSUMPTION: best-effort bold detection is acceptable; documented in trade-offs]`
- No LLM participates in this Check.

#### FR-14: Field Match with normalization tolerance
The system compares application fields (brand name, alcohol content value, net contents, name/address) against OCR-extracted values using normalization (case, punctuation, whitespace) and emits PASS on normalized match, REVIEW on near-miss, FAIL on substantive mismatch. Realizes UJ-1.
**Consequences (testable):**
- "STONE'S THROW" vs "Stone's Throw" → PASS.
- Application ABV 45%, label 40% → FAIL.
- OCR confidence below threshold → REVIEW, not FAIL. `[ASSUMPTION: near-miss and confidence thresholds tuned during implementation against the fixture corpus; PRD fixes the three-band behavior, not the numeric thresholds]`

#### FR-15: Per-type deterministic format Checks
The system deterministically validates rule-bound formats per Beverage Type: alcohol-content statement format, net-contents format and standards-of-fill lookup, name-and-address qualifying phrase presence, and the conditional Checks the Ruleset defines (sulfites, coloring disclosures, age statements, country of origin, etc.).
**Consequences (testable):**
- A spirits Submission missing an ABV statement → FAIL on that Check; a table-wine Submission without ABV is **not** failed (cross-commodity ABV rules respected); malt-beverage ABV is optional unless the Ruleset's trigger applies.
- Net contents "750 mL" passes standards-of-fill lookup; an off-standard size fails with the citation.
- Proof, when present on a spirits label, must be distinguished from the ABV statement (parentheses/brackets) and numerically consistent with it (proof = 2 × ABV); inconsistency → FAIL.
- A conditional Check that cannot be evaluated from available data (e.g., sulfite ppm unknown) → REVIEW with explanation, not a guess. `[ASSUMPTION]`

#### FR-16: Hybrid class/type designation Check
The system validates the class/type designation by rules first (valid designation lists, spelling), escalating only genuinely ambiguous cases to LLM assessment — where the model reads the label **image** (VLM-only), never the OCR text — and caps LLM-assisted results at REVIEW severity — an LLM opinion alone never produces FAIL. `[ASSUMPTION: capping LLM-derived verdicts at REVIEW is the right recommend-don't-decide posture]` `[VLM-only: OCR output is never fed to a model anywhere in the POC; the OCR+LLM hybrid is a documented future consideration only — see tradeoffs-and-limitations.md B10]`
**Consequences (testable):**
- "Kentucky Straight Bourbon Whiskey" validates deterministically without an LLM call.
- Conflicting class/type designations across a Submission's multiple labels are detected deterministically (text comparison across images) → FAIL with both values cited.
- With LLMs toggled off, this Check degrades to rules-only plus REVIEW for unresolved cases.

#### FR-17: Flag-only Checks surface as REVIEW
For Checks that cannot be reliably auto-decided from images — Same Field of Vision spatial inference across multiple images, "separate and apart" placement requirements, severely degraded text — the system emits REVIEW with an explanatory note, never PASS or FAIL.
**Consequences (testable):**
- A multi-image Submission where the trio's co-location is undeterminable → REVIEW citing 27 CFR 5.63, with the presence of each element individually reported.

#### FR-18: Verdict provenance
Every Engine Verdict records which Check produced it, the determinism class, the CFR citation, the input values compared, and (for LLM-assisted Checks) the model identification — so any verdict can be explained to a specialist or an evaluator.
**Consequences (testable):**
- The review screen can show, for any Checklist item, why the verdict is what it is, including both compared values.

### 4.4 Mock COLA Database & Test Corpus

**Description:** The POC's data foundation: a seeded database standing in for the COLA system, modeled on Form 5100.31 application fields, plus the fixture corpus with Ground Truth that powers both the demo and the Benchmark Harness. The review workspace reads from it; the only writes from the UI are Dispositions; the Pre-compute Pipeline writes extraction results and statistics.

**Functional Requirements:**

#### FR-19: Submissions schema and data dictionary
The system stores Submissions with three field categories — application fields (Form 5100.31-modeled), OCR/LLM-extracted fields, and engine/statistics fields — including TTB ID, Beverage Type, 1–10 label-image references, `submitted_at`/`decided_at`, Disposition, and model-identification fields. A data dictionary (field name, common name, specification, definition) is a repo deliverable.
**Consequences (testable):**
- A Submission with 10 images round-trips correctly; an 11th is rejected by validation.
- The data dictionary covers every schema field.

#### FR-20: Seeded fixture corpus with Ground Truth
The system ships seeded with 30–50 dummy Submissions spanning all three Beverage Types, including clean labels, every-Check-violation examples, and a degraded-image tail (glare, angle, curvature), each carrying Ground Truth field values. Sources: synthetic labels for anything public-facing; COLA Registry images as private test fixtures only (label artwork is trademarked).
**Consequences (testable):**
- At least one seeded Submission exists per Engine Verdict outcome per Beverage Type (a wine PASS, a spirits Government-Warning FAIL, a malt-beverage REVIEW, etc.). `[ASSUMPTION: exact corpus composition matrix decided during fixture creation]`
- No registry-sourced label artwork appears in public demo flows or the public repo.

### 4.5 Benchmark Harness & Procurement Study

**Description:** The POC's second identity. Because every Submission already flows through multiple OCR engines and LLMs (§4.2), the harness turns that exhaust into procurement evidence: per-engine and per-model speed, accuracy against Ground Truth, and cost — culminating in a cost-per-1,000-Verifications figure. Tracing (LangChain-class, local-only, toggleable) captures model identification and timing into the database. Realizes UJ-3.

**Functional Requirements:**

#### FR-21: Accuracy scoring against Ground Truth
The system scores each OCR engine's and each LLM's extraction per field against Ground Truth and computes field-level match rates per engine/model across the corpus.
**Consequences (testable):**
- Accuracy figures are reproducible by re-running the harness over the seeded corpus.
- Scores are reported per field (brand name, ABV, net contents, Government Warning presence/exactness) and in aggregate.

#### FR-22: Speed and cost statistics
The system captures per-engine/per-model latency and per-call cost inputs (tokens, unit prices; $0-marginal for local engines) and computes cost per 1,000 Verifications per configuration.
**Consequences (testable):**
- The cost-per-1,000-Verifications figure is produced for every benchmarked engine/model, including the local-only configuration.
- The report states its pricing basis explicitly: published API prices are used as a proxy for internally hosted model cost, and are labeled as such (honesty per NFR-5).

#### FR-23: Benchmark Report
An evaluator can view a Benchmark Report presenting engines and models side by side — speed, accuracy, cost — with the test conditions stated. Realizes UJ-3. `[ASSUMPTION: report rendered as a page within the app; a generated document would also satisfy the brief]`
**Consequences (testable):**
- Report is reachable from the deployed demo and reflects the actual seeded-corpus runs, not hand-entered numbers.
- The report closes with a recommendations section — best OCR engine, best LLM, best overall approach — each grounded in the collected statistics, per the procurement-study goal.

#### FR-24: Local-only tracing, toggleable
The system's tracing/instrumentation runs locally, writes to the local database only, and can be disabled by configuration without affecting review functionality.
**Consequences (testable):**
- With tracing disabled, no tracing code paths execute and the review workspace behaves identically.
- No tracing telemetry leaves the host (covered by the outbound-call inventory, NFR-2).

### 4.6 Demo Access & Evaluator Deliverables

**Description:** How evaluators reach and trust the POC. The deployed app sits behind a lightweight token gate (no auth system is built — the token only keeps the public and bots out). The interface follows USWDS. The repo carries the documentation set the assignment requires, including the outbound-call inventory that proves the firewall posture. Realizes UJ-3.

**Functional Requirements:**

#### FR-25: Token-gated access
An evaluator with the token can use the full demo at a public URL; without the token, no application data or functionality is reachable.
**Consequences (testable):**
- Requests without the token receive a clean denial; no Submission data, images, or Benchmark Report leak.

#### FR-26: Documentation deliverables
The repo provides: README with setup and run instructions; `docs/` set (approach, tools used, assumptions, trade-offs and limitations, pre-search); the data dictionary (FR-19) including supported image types; the per-type Ruleset documents; the landscape narrative including the Applicant's COLAs Online application workflow; the outbound-call inventory; and USWDS-compliance notes — each linked from the README.
**Consequences (testable):**
- A fresh evaluator can clone, set up, and run locally from the README alone.
- The outbound-call inventory enumerates every external call the deployed app can make, each classified (none required / models-internal-endpoint).

#### FR-27: Demo data reset
An evaluator can reset the demo to its seeded state — restoring the full fixture queue and clearing recorded Dispositions — so the demo is never permanently exhausted. Realizes UJ-3. `[ASSUMPTION: one evaluator at a time per token; multi-user isolation is out of scope]`
**Consequences (testable):**
- After all seeded Submissions receive Dispositions, reset restores the full pending queue.
- Reset is reachable without redeployment.

#### FR-28: Enqueue a fixture Submission live
An evaluator can trigger insertion of a fresh fixture Submission and observe it progress `submitted → processing → ready`, demonstrating the Pre-compute Pipeline end to end. Realizes UJ-3. `[ASSUMPTION: fixture-based only — arbitrary image upload remains a Non-Goal]`
**Consequences (testable):**
- The enqueued Submission becomes servable via Next Submission once ready, with full Engine Verdicts.

## 5. Non-Goals (Explicit)

- **Not a decision-maker.** The engine never auto-approves, auto-rejects, or pre-selects a Disposition. Advisory only, structurally.
- **Not an applicant-facing product.** No image upload, no application data entry, no pre-screening service — capturing applications is the applicant system's job.
- **No font-size or dimension checking.** Cannot be measured reliably from a photo without a scale reference; COLAs Online itself disclaims testing dimensions — the POC documents the same disclaimer.
- **No integration with the real COLA system.** Standalone over the Mock COLA Database; API and integration are Phase 2.
- **No authentication system, no PII, no sensitive data.** Token gate only; dummy data only.
- **No batch-upload feature.** Batch filing is applicant-side in COLAs Online; 300 batch-filed applications are still 300 individual Submissions to the Label Specialist. The write-up addresses the stakeholder wish by explaining exactly this.
- **No heavyweight workflow state machine.** Minimal status enum and timestamps only — enough for time-to-decision and the 5-second claim, not a rebuild of COLA's workflow engine.
- **Not claiming production-readiness.** A modest, honest prototype that claims only what it demonstrates.

## 6. MVP Scope

### 6.1 In Scope

Scope is tiered to honor the assignment's own rubric — *"a working core application with clean code is preferred over ambitious but incomplete features."* If time runs short, the cut line falls between the tiers; nothing in Core is cuttable. The tiers also answer the register's request to separate the take-home-mandatory requirements from the above-and-beyond additions.

**Core (take-home-mandatory — the working core):**
- Review Workspace essentials: Next Submission (FR-1), stacked comparison (FR-3), Checklist (FR-4), Disposition capture (FR-6), image display (FR-7).
- Pre-compute Pipeline: background jobs (FR-9), dual-OCR (FR-11).
- Compliance Engine, distilled spirits Ruleset deepest: Government Warning exact (FR-13), Field Match (FR-14), deterministic format Checks (FR-15), verdict provenance (FR-18).
- Seeded Mock COLA Database with Ground Truth corpus (FR-19, FR-20).
- Token-gated deployment, USWDS UI, README + core docs (FR-25, FR-26), demo reset (FR-27).

**Full (above-and-beyond — the procurement study and polish):**
- Next-by-type (FR-2), status bar (FR-5), in-UI help (FR-8), live fixture enqueue (FR-28).
- Local image preprocessing (FR-10), LLM extraction/fallback (FR-12).
- Hybrid and flag-only Checks (FR-16, FR-17); wine and malt-beverage Rulesets at full depth.
- Benchmark Harness and Benchmark Report with cost-per-1,000-Verifications figure and recommendations (FR-21–FR-24).

### 6.2 Out of Scope for MVP

- **Two-bucket triage queue** (likely-compliant vs. troublesome) — Phase 2; requires confidence calibration that the benchmark data will itself provide. `[NOTE FOR PM: emotionally load-bearing for the junior/senior staffing story — revisit if timeline permits]`
- **COLA API definition and integration hooks** — Phase 2, explicitly.
- **Knowledge-base/help search product** — v1 ships the static help panel (FR-8).
- **Live CFR text retrieval** — Rulesets are data snapshots with source dates; no runtime regulatory fetch.
- **Allowable-revisions handling** (label changes not requiring a new COLA) — real-world concept documented in research; not modeled in v1. `[ASSUMPTION: out of scope as not demo-critical]`

## 7. Success Metrics

**Primary**

- **SM-1 — Ready in 5 seconds:** from **Next Submission** click to fully interactive review screen (label, fields, verdicts) in ≤ 5.0 s at p95, measured across serves of the full seeded corpus on the deployed demo. The product's identity and the prior pilot's exact failure. Validates FR-1, FR-9.
- **SM-2 — Core matching works end to end:** on real and synthetic labels, brand name, alcohol content, and Government Warning are checked against the application with correct PASS / REVIEW / FAIL behavior — Government Warning wording verified exactly. Validates FR-13, FR-14, FR-15.
- **SM-3 — Procurement evidence produced:** two OCR engines and ≥ 3 LLMs reported side by side on speed, accuracy, and cost, including cost per 1,000 Verifications. Validates FR-21, FR-22, FR-23.
- **SM-4 — Testable and clean:** a deployed URL evaluators can exercise; organized code; documented approach, tools, assumptions, trade-offs. Validates FR-25, FR-26.

**Counter-metrics (do not optimize)**

- **SM-C1 — Readiness must not be bought by skipping work:** at steady state, ≥ 95% of pending Submissions are `ready`; FR-1 skips of unready Submissions are logged and rare; the FR-9 time-to-ready bound (p95 ≤ 10 min) holds. The 5-second figure is meaningless if the pipeline hides work by lagging. Counterbalances SM-1.
- **SM-C2 — False-FAIL rate:** strictness must not be gamed for impressive-looking catches; the false-FAIL count on the normalized-match fixture class (the "STONE'S THROW" cases) is zero. False FAILs are the costliest real-world error — they trigger needless correction cycles; erroneous-approval risk is structurally mitigated because an Engine Verdict is never a Disposition. Counterbalances SM-2.

*Field-success signals (adoption, throughput, fewer missed errors) belong to the Vision, deliberately not to these criteria — the POC commits only to what it can demonstrate.*

## 8. Open Questions

1. **Exact online-vs-paper filing counts (2024/2025/2026-to-date)** — Diane to pull from the Public COLA Registry search; lands in `docs/` narrative, not blocking. (Carried from research TODO.)
2. **Top-10 most common distilled-spirits label errors** — would sharpen the Checklist's ordering and fixture corpus; published lists found so far are wine-only. Non-blocking.
3. **LLM endpoint configuration at deploy time** — which concrete API endpoints/keys the deployed demo uses for the three model families, and graceful behavior if a provider is unreachable during evaluation. Architecture decision; PRD requires only FR-12's toggle-off resilience.
4. **CPU-only, no-local-disk workstation reality** — acknowledged via the browser-app/server-side-compute design and a `docs/` landscape note; confirm no further product impact. `[ASSUMPTION: no v1 feature impact]`

## 9. Assumptions Index

- §2.3 — User journeys constructed from the assignment's interview notes rather than separately narrated.
- §4.1 FR-1 — Incompletely processed Submissions are skipped, not served partially; queue order oldest-first for reproducibility.
- §4.1 FR-8 — v1 help is a static searchable panel; knowledge base is Phase 2.
- §4.2 FR-9 — Status enum semantics fixed (submitted/processing/ready/failed); exact values are architecture's call. Time-to-ready bound (p95 ≤ 10 min) set generously so the readiness claim is falsifiable.
- §4.2 FR-11 — Engine-agnostic result schema is a requirement because swap-and-compare is a procurement goal.
- §4.3 FR-13 — Best-effort bold detection on the warning header is acceptable, reported as not-verified where undeterminable.
- §4.3 FR-14 — Numeric tolerance/confidence thresholds tuned during implementation; PRD fixes the three-band behavior only.
- §4.3 FR-15 — Unevaluable conditional Checks emit REVIEW with explanation.
- §4.3 FR-16 — LLM-assisted verdicts are capped at REVIEW severity.
- §4.4 FR-20 — Exact fixture-corpus composition matrix decided during fixture creation.
- §4.5 FR-23 — Benchmark Report rendered in-app (a generated document would also satisfy).
- §4.6 FR-27 — One evaluator at a time per token; multi-user isolation out of scope.
- §4.6 FR-28 — Live enqueue is fixture-based only; arbitrary upload remains a Non-Goal.
- §6.2 — Allowable-revisions handling out of v1 scope as not demo-critical.
- §8 Q4 — CPU-only workstation reality has no v1 feature impact beyond the browser-based design.
- §10 NFR-4 — Full Section 508 audit out of POC scope; USWDS adherence is the v1 accessibility mechanism.

## 10. Cross-Cutting NFRs

- **NFR-1 — Performance:** review-screen readiness ≤ ~5 s from Next Submission click (SM-1), achieved architecturally via the Pre-compute Pipeline, not by faster request-time inference. Benchmark Harness additionally records CPU-only-mode performance, since government GPU availability is uncertain.
- **NFR-2 — Firewall posture and outbound calls:** the deployed app is local-first. OCR, preprocessing, rules, and tracing are fully local. LLM API calls are permitted in the live path for extraction and benchmark-stat capture, and **model government-internal LLM endpoints** — in a TTB deployment these calls would terminate inside the firewall; the POC documents this equivalence. A complete outbound-call inventory is a deliverable (FR-26); everything in it must be classified local, none, or models-internal-endpoint. Tracing never sends telemetry off-host (FR-24).
- **NFR-3 — Privacy and data:** no PII anywhere; dummy application data only; registry-sourced label artwork confined to private fixtures (FR-20); nothing sensitive stored. Read-only posture except Disposition capture and pipeline writes.
- **NFR-4 — Usability and accessibility:** USWDS-based UI; designed for the lowest-tech-comfort user (the Dave gate); minimum 24-inch-monitor layout; Section 508-conscious component choices via USWDS defaults. `[ASSUMPTION: full Section 508 audit out of POC scope; USWDS adherence is the v1 accessibility mechanism]`
- **NFR-5 — Honesty of claims:** the demo, report, and docs claim only what the POC demonstrates; limitations (font-size non-checking, mock data, prototype status) are documented in the same place the capabilities are.
- **NFR-6 — Code quality:** organized, evaluator-readable codebase; documented assumptions and trade-offs; working core preferred over ambitious-incomplete features (the assignment's own rubric).
