# Reconciliation: Take-Home Assignment vs PRD + Addendum

**Input:** `ref-docs/TTB-take-home-instructions.md` (assignment / de-facto grading rubric)
**Against:** `prd.md` + `addendum.md` (2026-06-11)
**Date:** 2026-06-11

Verdict legend: ✅ covered · 🟡 covered with a caveat worth fixing · 🔴 gap / grading risk

---

## 1. Stakeholder asks — coverage map

### Sarah Chen (Deputy Director)

| # | Ask (paraphrase) | Where in PRD/Addendum | Verdict |
|---|---|---|---|
| S1 | Core matching: brand name, ABV, Government Warning present, vs application | FR-13, FR-14, FR-15; SM-2 | ✅ |
| S2 | **~5-second results or nobody uses it** (prior 30–40 s pilot failed) | NFR-1, SM-1, FR-1, FR-9 (Pre-compute Pipeline); SM-C1 counter-metric | ✅ Strong — it is the product's stated identity. Note: PRD reframes "results in 5 s" as "screen ready in ≤5 s via pre-compute." Satisfies the spirit; docs should state the reframe explicitly so an evaluator timing a *freshly inserted* Submission (which takes longer end-to-end) doesn't read it as a miss. |
| S3 | "My mother could figure it out" — low-tech-comfort users, no hunting for buttons | NFR-4 ("Dave gate"), FR-8 help, §4.1 feature NFR (24-inch layout) | ✅ |
| S4 | **Batch uploads** (200–300 applications dumped at once) | §5 Non-Goal with rationale; A3 (batching is applicant-side in COLAs Online; 300 batch-filed apps are still 300 individual reviews) — write-up commitment to address Sarah's wish by name | ✅ Explicitly addressed as Non-Goal with defensible rationale. **Execution dependency:** the rationale only protects the grade if it actually lands in the README/write-up; make it a named checklist item in FR-26's doc set. |

### Marcus Williams (IT)

| # | Ask | Where | Verdict |
|---|---|---|---|
| M1 | Standalone POC; **no COLA integration** | §5 Non-Goal; Mock COLA Database (FR-19); Phase 2 framing §1, §6.2 | ✅ |
| M2 | Prototype-appropriate security; "don't do anything crazy"; no sensitive data | NFR-3 (no PII, dummy data); FR-25 token gate; §5 Non-Goal (no auth system) | ✅ |
| M3 | **Network blocks outbound to ML endpoints** (vendor pilot half-broke on firewall) | NFR-2; A2 (revised posture: cloud LLM calls *model* government-internal endpoints); FR-12 toggle-off OCR-only path proves zero-egress config; FR-24 local-only tracing; FR-26 outbound-call inventory | 🟡 See Risk R3 below. The posture is coherent and documented, but the deployed POC *does* make live cloud LLM calls — superficially the exact thing that sank the vendor pilot. Coverage depends entirely on the framing being loud in README + Benchmark Report. The OCR-only zero-egress demonstration is the strongest defense; consider making "demo runs fully with LLMs off" an explicit demo script beat, not just a testable consequence. |

### Dave Morrison (Senior Agent)

| # | Ask | Where | Verdict |
|---|---|---|---|
| D1 | Nuance/judgment — "STONE'S THROW" vs "Stone's Throw" must not be flagged | FR-14 normalization; FR-3 consequence; SM-C2 (false-FAIL counter-metric); UJ-1 edge case | ✅ Directly modeled, with a counter-metric. Strong. |
| D2 | Don't make my life harder; human judgment stays in charge | FR-6 (engine never pre-selects Disposition), §5 Non-Goal "not a decision-maker", Engine Verdict vs Disposition vocabulary split | ✅ |

### Jenny Park (Junior Agent)

| # | Ask | Where | Verdict |
|---|---|---|---|
| J1 | Warning must be **exact, word-for-word** | FR-13 deterministic exact-wording check; UJ-2 | ✅ |
| J2 | "GOVERNMENT WARNING:" **all caps and bold** | FR-13: caps fully checked; bold only "where formatting is detectable" | 🟡 Caps ✅. Bold is hedged — defensible (OCR can't reliably detect weight) but the assignment names bold explicitly. Per NFR-5, document bold-detection as a known limitation in the same place the warning check is described, or graders may count it as a silent miss. |
| J3 | Creative evasions: smaller font, different wording, buried tiny text | Wording: FR-13. Font size: §5 Non-Goal with COLAs Online's own disclaimer + A4 type-size table preserved for the README | ✅ Wording covered; font size is an explicit, well-sourced Non-Goal. Same execution dependency as S4: the disclaimer must actually appear in docs. |
| J4 | Handle imperfect images (angles, lighting, glare) — Jenny flagged it as maybe out of scope | FR-10 preprocessing, FR-7 side-by-side original/cleaned, FR-20 degraded-image fixtures, A5 corpus intent | ✅ In scope despite being offered as optional — differentiator, supports "creative problem-solving." |

---

## 2. Technical requirements & additional context

| Item | Where | Verdict |
|---|---|---|
| Free choice of languages/frameworks; "we want to see your engineering, design, integration decisions" | A1 (Python rationale, OCR/LLM/tooling roster); FR-26 approach doc | ✅ Rationale write-up is flagged as still owed (`docs/approach.md`) — track it. |
| Label elements: brand name | FR-14 | ✅ |
| Class/type designation | FR-16 (hybrid check) | ✅ |
| Alcohol content **with exceptions for certain wine/beer** | FR-15 + A4 cross-commodity ABV matrix (spirits required / wine conditional / malt optional) | ✅ Exceptions explicitly modeled — directly answers "attention to requirements." |
| Net contents | FR-14, FR-15 (standards-of-fill lookup) | ✅ |
| Name and address of bottler/producer | FR-14, FR-15 (qualifying phrase) | ✅ |
| **Country of origin for imports** | FR-15 "…country of origin, etc." (one mention, inside a conditional-checks list) | 🟡 Present but thin. It's on the assignment's named-elements list; ensure the spirits/wine/malt Rulesets and at least one fixture exercise it, or it risks looking like list-padding. |
| Government Warning mandatory on all types | FR-13; all three Rulesets | ✅ |
| Sample label (OLD TOM DISTILLERY fields) must be handled | A5: seed fixture #1 verbatim | ✅ |
| Create/source additional test labels; AI generation suggested | FR-20 corpus (30–50, all types, violations, degraded tail); A5 sources incl. synthetic-per-assignment-suggestion | ✅ Exceeds ask. |
| Beverage-type variance (beer, wine, spirits) | Ruleset-per-Beverage-Type, FR-2, FR-4, FR-15 | ✅ |

---

## 3. Deliverables

| Deliverable | Where | Verdict |
|---|---|---|
| Source code repo, all source | Implied by FR-26/NFR-6 | ✅ |
| README with setup and run instructions | FR-26 ("fresh evaluator can clone, set up, run from README alone") | ✅ |
| Brief documentation: approach, tools, assumptions | FR-26 docs set (approach, tools, assumptions, trade-offs, pre-search) | ✅ Note the assignment says **brief**; the PRD's doc set is large. Keep the evaluator-facing layer short with links, so volume reads as rigor rather than padding. |
| **Deployed application URL, accessible and testable** | FR-25 token gate, SM-4 | 🟡 Two caveats. (a) Token delivery: a token gate is fine only if the token reaches evaluators frictionlessly (in the README/submission email) — make that an explicit FR-25/FR-26 consequence. (b) "Testable" — see Gap G1: evaluators can only consume seeded data; they cannot feed the app an input of their own. |

---

## 4. Evaluation criteria

| Criterion | Where | Verdict |
|---|---|---|
| Correctness & completeness of core requirements | SM-2; FR-13–FR-15 cover every named core check | ✅ on paper — contingent on Risk R2 (scope) not eating the core. |
| Code quality and organization | NFR-6 | ✅ |
| Appropriate technical choices for the scope | A1 + approach doc | ✅ |
| **User experience and error handling** | UX: NFR-4, FR-3/4/5/7/8. Error handling: FR-9 pipeline-failure state, FR-2 empty-type message, FR-12 LLM-off resilience | 🟡 UX is deeply specified; **user-facing** error handling is not — see Gap G2. |
| Attention to requirements | Assumptions Index §9, glossary discipline, this reconciliation | ✅ |
| Creative problem-solving | Pre-compute Pipeline, Benchmark Harness/procurement study, dual identity (§1) | ✅ Strong differentiators. |
| "Working core preferred over ambitious but incomplete; document trade-offs" | NFR-6 cites the rubric; NFR-5 honesty | 🔴 The PRD *quotes* the principle but its MVP scope doesn't *obey* it — see Risk R2. |

---

## 5. Gaps and risks to grading

### G1 — No evaluator-facing input path (testability gap) 🔴
The entire demo is seeded-corpus-only. §5 Non-Goals rule out image upload and data entry as *applicant-facing* features — correct domain reasoning — but the assignment's deliverable is a prototype evaluators "can access and **test**," and Sarah's batch-upload ask presupposes a single-submission intake exists at all. FR-9 even says Submissions can be "inserted during a demo," yet no FR provides any mechanism or actor for that insertion. An evaluator who wants to try their own AI-generated label (the assignment explicitly nudges them toward generating labels) has no way in.
**Recommendation:** add a small, clearly-framed *evaluator/demo affordance* — e.g., a "Create test Submission" admin page or documented script/API that inserts a Submission (fields + images) into the Mock COLA Database and triggers the pipeline — positioned as simulating COLA hand-off, not as an applicant feature. Alternatively, add an explicit Non-Goal line addressing evaluator-supplied inputs with rationale. Silence here is the PRD's single biggest grading exposure.

### G2 — User-facing error handling under-specified 🔴
"User experience **and error handling**" is a named criterion. Covered: pipeline failure → visible DB error state (FR-9); empty per-type queue message (FR-2); LLM-off resilience (FR-12). Not specified: what the *screen* shows for a failed Submission; behavior when the **entire** queue is empty (only the per-type case is covered); what the evaluator sees if an LLM provider is unreachable mid-demo (parked as Open Question 3 — risky to leave open, since evaluation happens live); token-gate failure UX beyond "clean denial"; image-load failure.
**Recommendation:** add one FR (or consequences under FR-1/FR-9) defining graceful user-visible states for: empty queue, failed-pipeline Submission, unreachable LLM provider, missing/broken image. Cheap to write, directly graded.

### G3 — Scope vs the rubric's own "working core" warning 🔴 (delivery risk, not a coverage hole)
§6.1 puts **all 26 FRs** in MVP: three full Rulesets, dual OCR, 3+ LLMs, preprocessing, benchmark harness with cost model, USWDS UI, token-gated deploy, full doc set. The assignment says explicitly: time-constrained, working core with clean code beats ambitious-incomplete. The PRD acknowledges the principle (NFR-6) but defines no internal priority order or cut line — if time runs short, there is no pre-agreed answer to "what drops first."
**Recommendation:** add a priority tiering inside §6.1 (e.g., Tier 1 = FR-1/3/6/9/11-partial/13/14/15-spirits/19/20-subset/25/26-README; Tier 2 = wine/malt depth, benchmark report, preprocessing comparison; Tier 3 = FR-2/5/8, third LLM, USWDS polish). This converts the rubric's warning into a plan instead of a hope.

### R4 — Live cloud LLM calls vs Marcus's firewall story 🟡
The deployed POC calls cloud LLMs — facially the same failure mode as the vendor pilot Marcus mocked. A2's "models government-internal endpoints" reframe plus the FR-12 OCR-only zero-egress path is a sound answer, but only if evaluators encounter the framing *before* they notice the API calls.
**Recommendation:** surface the framing in three graded places: README (outbound-call inventory up front), Benchmark Report header, and the demo script ("now watch it run with LLMs off — zero egress").

### R5 — Government Warning bold check hedged 🟡
FR-13 checks caps fully but bold only "where formatting is detectable." Jenny names bold explicitly. Acceptable engineering call; becomes a grading ding only if undocumented. Put the limitation note in the same doc section that advertises the warning check (NFR-5 pattern), alongside the font-size disclaimer from A4.

### R6 — Minor execution dependencies 🟡
- Batch-upload and font-size Non-Goal rationales are promised "in the write-up" — name them as required sections of FR-26's docs so they can't slip.
- Country-of-origin: ensure ≥1 import fixture exercises the check (per §2 table).
- Token delivery to evaluators: make it an explicit consequence of FR-25/FR-26.
- "Brief documentation": keep the evaluator-facing layer genuinely brief; link down to depth.
- Two-clocks note (A6): good catch — ensure it ships, since conflating queue-turnaround with the 5-second claim would undercut SM-1's credibility.

---

## 6. Bottom line

Coverage is unusually complete: every named stakeholder ask is either an FR/NFR with testable consequences or an explicit Non-Goal with domain-grounded rationale (batch upload and font size are model answers). The differentiators (pre-compute architecture, procurement benchmark, cross-commodity ABV matrix, false-FAIL counter-metric) map directly onto "creative problem-solving" and "attention to requirements."

The three things the PRD is currently *silent or soft* on, in grading order: **(1)** no way for an evaluator to feed the app an input (testability of the deployed deliverable), **(2)** user-visible error handling (a named criterion), **(3)** no priority cut line despite the rubric's explicit working-core-over-ambition warning. All three are fixable with small PRD edits before finalization.
