# PRD Addendum — TTB COLA Label Specialist Workspace (POC)

Preserves depth that belongs downstream (architecture, solution design, UX, fixture work) or that earned preservation but not PRD placement. Companion to `prd.md` (2026-06-11).

## A1. Technology direction already decided (architecture inputs, not PRD capabilities)

- **OCR engines:** Tesseract + PaddleOCR (consider PP-OCRv5). Complementary profiles: Tesseract light/fast on clean print; PaddleOCR far stronger on curved/noisy text (research cites ~88.7% vs ~52.1% on curved text). Run each in its own background job behind a uniform microservice-style interface (FR-11's engine-agnostic schema).
- **Image preprocessing:** OpenCV-class local tooling — deskew, perspective correction, CLAHE contrast, denoise, glare mitigation; `unpaper` as a candidate. No LLM/cloud needed for FR-10.
- **LLM roster (benchmark + fallback):** OpenAI GPT (vision-capable line), Google Gemini, Anthropic Claude. "Codex" from the original notes is OpenAI's coding-focused line; vision models are the right entry for label extraction.
- **Local small-VLM stretch candidate:** Include at least one locally hosted small VLM in the benchmark if feasible — it is the only roster entry matching the zero-egress deployment topology, and "local models keep shrinking" is itself a procurement outlook worth one line in the Benchmark Report.
- **Tracing:** LangChain used for local/offline tracing only — model name/ID/full version ID, timestamps, latency, token counts → local DB. Toggleable off (FR-24); inclusion documented as easy-to-disable so it never conflicts with the firewall posture.
- **Language choice:** Python preferred over Bash for system components (ecosystem: OCR bindings, OpenCV, LangChain, web frameworks). Open register item §5 — final rationale write-up belongs in architecture/`docs/approach.md`.
- **CPU-mode benchmarking:** Record benchmark numbers in CPU-only mode as well — government GPU availability is uncertain; CPU figures are the procurement-realistic ones.

## A2. Firewall posture detail (NFR-2 background)

Original posture (brief + research): cloud models strictly offline-harness-only. **Revised by Diane during PRD (2026-06-11):** the government hosts LLMs inside its firewall, so LLM calls from the deployed POC are acceptable — in production they would be internal endpoints, not external API calls. The POC's cloud calls are therefore a *model* of internal services. Consequences: outbound-call inventory remains mandatory; every entry classified (none / local / models-internal-endpoint); tracing stays off-host-free; OCR/rules/preprocessing stay fully local so the OCR-only path proves a zero-egress configuration exists (FR-12 toggle-off).

## A3. Rejected / deferred alternatives and why

- **Two-bucket triage queue** (easy vs. troublesome, junior/senior routing): deferred to Phase 2 — requires verdict-confidence calibration that only the benchmark corpus runs can supply. Revisit once SM-3 data exists.
- **Side-by-side (horizontal) field comparison:** rejected — horizontal layouts force the eyes too far apart; vertical stacking confirmed as the comparison pattern (FR-3).
- **Heavyweight workflow state machine:** rejected — minimal status enum + timestamps capture time-to-decision and the 5-second claim without rebuilding COLA's workflow engine.
- **"Select which value to keep" feature:** removed from scope in the discussion register — it is an applicant-prescreener idea, not a reviewer-workspace function.
- **Batch upload in the reviewer tool:** rejected as a v1 feature and reframed — batching is an applicant-side COLAs Online affordance; 300 batch-filed applications remain 300 individual Submissions to the specialist. Address Sarah Chen's wishlist item in the write-up with exactly this framing. (The register's `batch-template.csv` deliverable is superseded by this decision; if produced at all, it is an illustrative applicant-side artifact in `docs/`.)
- **Live CFR retrieval:** rejected — eCFR.gov bot-blocks automated fetch; Rulesets are versioned data snapshots with source dates (working sources: TTB's own checklists in `ref-docs/`, Cornell LII mirror).

## A4. Regulatory depth held for Ruleset/fixture work

- Authoritative spirits ruleset: `ref-docs/ds-labeling-checklist.pdf` (post-2022 Part 5 numbering); wine and malt-beverage counterparts in `ref-docs/`. Per-type rule docs already drafted under `docs/regulatory-rules-*.md`.
- Government Warning type-size table (27 CFR 16.22): ≤237 mL → min 1 mm (max 40 char/in); >237 mL–3 L → 2 mm (25 char/in); >3 L → 3 mm (12 char/in). **Not checkable from images** — preserved here because the README should quote COLAs Online's own disclaimer (approval does not test dimensions/type size; the applicant's perjury certification carries the burden) when documenting the font-size non-goal.
- Same Field of Vision (27 CFR 5.63): "side" = 40% of circumference for cylindrical containers; multi-image co-location inference is why FR-17 is flag-only.
- Cross-commodity ABV matrix (the #1 false-reject trap): spirits always required (§5.65); malt beverages usually optional (§7.65 — mandatory only with added nonbeverage-flavor alcohol); wine required only >14% ABV or when not designated "table"/"light" (§4.36).
- Disposition mechanics for seeding realism: Approved → COLA issued (later surrenderable); Needs Correction → 30-day clock to fix and resend, else auto-reject; Rejected → terminal, fresh resubmission references the prior TTB ID. Deeper state detail: `ref-docs/colas_ol_oim_um.pdf`, `ref-docs/chapter4.pdf`.

## A5. Data and fixture depth

- Application-field model anchors on Form 5100.31 (`ref-docs/f510031.pdf`); COLAs Online image constraints set the baseline for the mock: JPG/JPEG and TIFF, ≤750 KB, up to 10 files per application.
- Fixture sources: Public COLA Registry (no-login, images 1999–present, visible ~48 h post-approval), COLA Cloud Kaggle dataset, data.gov sets. Label artwork is trademarked → registry images private-fixtures-only; synthetic (AI-generated, per the assignment's own suggestion) for anything public.
- Corpus design intent for FR-20: include the degraded long tail (glare, angle, curvature, noise) deliberately — it is where OCR engines diverge and where preprocessing + LLM fallback earn their place in the benchmark.
- Fixture realism: COLAs Online enforces business rules at submission, so application *fields* arrive clean — corpus error cases should live on the labels (wrong/missing/malformed label content), not in malformed application data.
- Sample label fields from the assignment (seed fixture #1): OLD TOM DISTILLERY / Kentucky Straight Bourbon Whiskey / 45% Alc./Vol. (90 Proof) / 750 mL / standard warning.

## A6. Landscape narrative for `docs/` (procurement-context framing)

- Comparable camps: maker-side pre-screen (COLAClear, GetGen AI, Phantom Ales), registry search/data (COLA Cloud, Sovos LabelVision), TTB's own job aids (Anatomy of a Distilled Spirits Label; Allowable Changes Sample Label Generator). **No federal-reviewer workspace publicly exists** — the POC's empty room.
- COLAClear is the closest architectural analog (34 checks vs Parts 4/5/16; CV extraction + structured-LLM for ambiguity + hand-coded rules; pass/review/fail with citations; disclaims legal advice) — independent validation of the hybrid approach.
- "LabelScreener" / "Label Score" from the original notes did not resolve to live products; cite the verified tools instead.
- Tailwind worth stating: maker-side pre-screen proliferation should improve submission quality over time, making reviewer-assist progressively more reliable.
- Workstation reality: specialists work browser-first against central systems (CPU-only, no local disk reported) — supports the web-app/server-side-compute architecture; include in the landscape write-up.
- Two clocks, stated plainly for evaluators: TTB's published multi-day queue turnaround (spirits median ~2–6 days; 85%-in-15-days service goal) is a different clock from the POC's 5-second per-interaction readiness claim. Never conflate them in demo or docs.
- Narrative threads from the brief to preserve in `docs/approach.md`: the "every design choice answers a documented failure mode" meta-story (instant-load ↔ 5-second wall; recommend-don't-decide ↔ specialist authority; local-first ↔ the prior vendor's firewall-blocked ML endpoints), and the no-moat candor ("nothing a competent team couldn't rebuild — the edge is fit plus the measurement byproduct").
- Demo script note: include one demonstrated LLM-toggled-off run (FR-12) in the evaluator walkthrough — it is the live proof that a zero-egress configuration exists, and it preempts the "you said firewall, but I see API calls" question.
- Applicant-workflow doc source for FR-26: `ref-docs/colas_ol_oim_um.pdf` (COLAs Online user guide) — narrate the distilled-spirits application flow the Applicant follows.

## A7. Cost-framing nuance for the Benchmark Report

Local OCR path ≈ $0 marginal per verification (compute only) — itself a procurement finding worth headlining next to per-model LLM costs. Capture tokens + unit prices per call so the $/1,000-verifications figure falls out of recorded data rather than estimation (FR-22).
