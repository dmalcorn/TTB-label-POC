# Adversarial Review (Cynical Review) — PRD: TTB COLA Label Specialist Workspace (POC)

**Targets:** `prd.md` + `addendum.md` (2026-06-11)
**Reviewer stance:** Assume problems exist. They did not disappoint.
**Verdict:** A polished, vocabulary-disciplined PRD whose two headline claims — the 5-second promise and the procurement cost figure — are each constructed so they cannot fail, which is the same thing as not being claims. The demo as specified is single-use. Fix the critical and high findings before this goes near an evaluator who reads carefully.

Findings: **2 critical, 6 high, 8 medium, 6 low** (22 total).

---

## CRITICAL

### C-1. The 5-second claim is structurally unfalsifiable as written
*(SM-1, SM-C1, FR-1 assumption, NFR-1 — measurement honesty)*

Three clauses combine into a tautology:

1. FR-1's `[ASSUMPTION]`: a Submission whose pipeline run is incomplete is **skipped in queue order**. So Next Submission only ever serves fully pre-computed work.
2. SM-C1, the counter-metric that supposedly guards against this, requires "pre-compute coverage of the queue must stay at 100% **of ready-marked items**." Ready-marked items are *by definition* fully processed. This sentence verifies that processed things are processed. It guards nothing.
3. No NFR anywhere bounds **pipeline time-to-ready**. §4.2 explicitly invites Submissions "inserted during a demo" — that Submission could take ten minutes (or never) to become ready, and SM-1, SM-C1, and NFR-1 all still pass with flying colors.

The product's stated identity ("Speed is the trust mechanism," "the prior pilot's exact failure") rests on a metric that the system cannot fail no matter how slow the actual computation is. The old pilot's 30–40 seconds hasn't been beaten; it's been moved somewhere the stopwatch isn't pointed, and the PRD's own counter-metric is written so nobody can point it there. An evaluator who notices this — and a take-home evaluator is *paid* to notice this — will conclude the measurement was designed to flatter. The honest fix is cheap: add a pipeline-latency metric (e.g., p95 submitted→ready ≤ N minutes on the demo host) and rewrite SM-C1 to measure **queue readiness fraction at request time** ("when a specialist clicks Next, ≥X% of pending Submissions are ready"), not readiness of the ready.

### C-2. The demo is single-use and the PRD never notices
*(FR-1, FR-6, FR-25, SM-4 — scope the POC cannot realistically demo)*

FR-6: a Disposition removes the Submission from the pending queue, permanently — "exactly one Disposition," no undo, no reset. FR-20: the corpus is 30–50 Submissions, fixed. FR-25: one shared token, multiple evaluators. Walk the actual evaluation week:

- Evaluator #1 enjoys UJ-3, clicks Next Submission "repeatedly, timing readiness," dispositions a couple dozen. Evaluator #2 logs in Tuesday to a half-empty queue; evaluator #3 gets FR-2's "no pending Submissions" message as their first product experience. The PRD's own showcase journey **consumes the product**.
- Two evaluators with the same token, one global deterministic queue (FR-1: "oldest pending first"): both click Next, both get the same Submission, both record Dispositions. FR-6 says "exactly one." Which one wins? Nothing in the PRD says. Concurrency on the only write path is simply unaddressed.
- No queue-reset, replenish, demo-mode, or re-seed requirement exists anywhere in FR-1–FR-26.

A reproducible demo (FR-1's stated rationale for deterministic ordering!) that destroys its own reproducibility on first use is a contradiction in one feature. This needs a requirement: per-session queues, a reset endpoint, or Dispositions that don't dequeue in demo mode.

---

## HIGH

### H-1. "≤ ~5 s" is not a testable threshold and the measurement protocol does not exist
*(SM-1, FR-1, NFR-1 — untestable as written)*

"≤ ~5 s" — a tilde inside an inequality. Is 5.8 s a pass? Whoever wants it to be will say yes. And "measured across the seeded corpus" specifies neither the statistic (mean? p95? worst case?) nor the measurement point (server response? browser fully interactive — by what definition, TTI? LCP?) nor the conditions (evaluator on hotel Wi-Fi vs. localhost; the demo is a **deployed** URL, so network latency is inside the number for the only people who matter). "Fully interactive" is asserted in FR-1 but never operationalized. The product's single most important number has no measurement spec. Fix: "p95 ≤ 5.0 s from click to all verdicts rendered and controls enabled, measured client-side in the deployed environment, across all ready Submissions in the seeded corpus, method documented in the Benchmark Report."

### H-2. "Verification" — the unit of the headline cost metric — is never defined
*(FR-22, SM-3, §1, A7 — Glossary discipline failure at the worst possible spot)*

The Glossary defines Submission, Check, and Field Match with care, then the marquee procurement number is "cost per 1,000 **verifications**" — a term appearing nowhere in §3. Is a verification one Check? One Field Match? One Submission? One OCR pass over one image? The answers differ by two orders of magnitude in the resulting dollar figure. A procurement-study deliverable whose denominator is undefined is not a procurement study; it's a number-shaped object. This is the exact class of error the PRD's own "no synonyms, Glossary-anchored" rule exists to prevent, committed in the headline metric.

### H-3. The cost figure prices a topology the PRD says won't exist
*(FR-22, NFR-2, A2, A7, §2.1 — assumption disguised as fact; NFR-5 violation)*

NFR-2/A2 declare the deployed POC's cloud LLM calls "a *model* of internal services" — in a TTB deployment, calls terminate inside the firewall. Fine. But FR-22 computes cost from "tokens, unit prices" — i.e., **commercial public-API pricing** — and §2.1 promises evaluators "procurement-grade comparison data"; UJ-3 calls it "buying data." Government-internal model hosting has a completely different cost structure (FedRAMP-authorized capacity, provisioned throughput, infrastructure amortization — not per-token retail rates). So the headline dollar figure quantifies precisely the deployment configuration the firewall posture rules out. The equivalence "cloud call ≈ internal endpoint" is an architectural modeling assumption (legitimate) silently extended into a *pricing* assumption (unsupported, untagged — no `[ASSUMPTION]` marker, §9 silent). Calling the output "procurement-grade" collides head-on with NFR-5 ("the demo, report, and docs claim only what the POC demonstrates"). Downgrade the language or caveat the pricing model explicitly.

### H-4. SM-C2 commits the exact vocabulary violation the Glossary forbids
*(SM-C2, §3 — Engine Verdict vs. Disposition conflation)*

The Glossary's whole point: Engine Verdict (PASS/REVIEW/FAIL, "Never a decision") is "Distinct vocabulary from" Disposition (Approved/Needs Correction/**Rejected**). Then SM-C2: "False **rejects** are the costliest real-world error; false **approves** are structurally mitigated because the engine never decides." Reject and approve are Disposition verbs applied to engine behavior — the conflation the document built a glossary to prevent, inside a Success Metric, which §3 explicitly binds ("FRs, UJs, and SMs use these terms verbatim"). Separately, "False-FAIL **rate**" names a rate with no target, no denominator, and no measurement source — as a counter-metric it cannot trip. Rewrite in verdict vocabulary with a number: "false-FAIL rate on Ground-Truth-matching fields ≤ X% across the corpus; normalized-match class must be 0."

### H-5. The MVP scope and the cited rubric are at war
*(§6.1, NFR-6, SM-3, FR-20, FR-26 — scope the POC cannot realistically deliver)*

NFR-6 quotes the assignment's own rubric: "working core preferred over ambitious-incomplete features." §6.1 then puts in scope: a full review workspace (8 FRs), a background job pipeline, image preprocessing, **two** OCR engines, **three** LLM providers, **three** per-commodity Rulesets spanning Parts 4/5/7/16 (sulfites, standards-of-fill, age statements, country of origin…), a 30–50-label Ground-Truthed fixture corpus, a benchmark harness with accuracy/latency/cost scoring, an in-app report, USWDS compliance, token-gated deployment, and a seven-artifact documentation set. Nothing is staged, nothing is marked droppable; "Out of Scope" contains only Phase-2 items nobody would have built anyway. For a take-home POC this is not an MVP scope, it is a product roadmap wearing an MVP's badge — and the document *knows* the rubric punishes exactly this. Where is the cut line? Which FRs survive if the timeline halves? A PRD that cites "working core preferred" and then declares 26 FRs all in scope has answered its own question and ignored the answer.

### H-6. Pipeline completion time is unbounded — the 30–40 s failure isn't fixed, it's unobserved
*(FR-9, NFR-1, §4.2 — companion to C-1, distinct fix)*

Beyond the metric circularity (C-1): no FR or NFR places *any* requirement on how long the Pre-compute Pipeline may take per Submission, even though it now runs 2 OCR engines × up to 10 images, plus preprocessing, plus optional LLM extraction across three providers. That stack could plausibly take *longer* than the failed pilot's 30–40 s per label — the PRD has no opinion. At demo scale (50 labels, pre-seeded overnight) nobody notices. The moment anyone extrapolates to 150,000/year — which the Vision invites — pipeline throughput is the real number, and the PRD never asked for it. At minimum, require per-stage `processing_ms` (already in FR-9) to be **reported** in the Benchmark Report with a stated demo-host budget.

---

## MEDIUM

### M-1. FR-10's consequence is incoherent and bets a requirement on an empirical outcome
"OCR accuracy on the preprocessed image is **measurably ≥** accuracy on the original." "Measurably greater-than-or-equal" is self-contradicting — equality is not measurable improvement; pick one. Worse: whether preprocessing helps is an *experimental result* (it routinely hurts on some image/engine pairs — over-sharpened clean scans, CLAHE halos), yet it's written as a testable requirement. If one fixture regresses, FR-10 is "failed" even though the pipeline behaved correctly. Require it in aggregate over the degraded-image class, or require only that both images are stored and benchmarked (which FR-7/FR-21 already give you).

### M-2. FR-20's prose promises what its own consequence quietly retracts
Description: corpus includes "**every-Check-violation** examples." Testable consequence: "at least one seeded Submission per Engine Verdict outcome per Beverage Type" — nine cells. FR-15 alone enumerates ABV format, net contents/standards-of-fill, name-and-address, sulfites, coloring, age statements, country of origin "etc." across three commodities; every-Check coverage is plausibly 60+ violation fixtures, against a stated corpus of 30–50 *total* including clean labels and the degraded tail. The description writes a check the consequence (and the arithmetic) declines to cash. Say which Checks get violation fixtures, or delete "every."

### M-3. FR-5's status bar has no mechanism in the model
"Status reflects Checklist completion state and updates as the specialist works" — but every Checklist item arrives pre-computed (the whole pitch: "already done thinking"), and no FR makes the Checklist interactive or records per-item specialist acknowledgment. What, concretely, changes "as the specialist works" in a screen where all work preceded the specialist? Either FR-4 needs an item-acknowledgment interaction (new write path — note NFR-3's "read-only except Disposition capture" would then be wrong too), or FR-5's consequence is decorative fiction. Currently it is a requirement describing a UI for a workflow that doesn't exist.

### M-4. SM-2's "real labels" cannot be demonstrated on the demo evaluators actually see
SM-2: matching works "on real and synthetic labels." FR-20/NFR-3: real (registry-sourced) labels are **private fixtures only**, never in public demo flows. So the "real" half of a primary success metric is unverifiable through the deployed URL — evaluators must take the repo's word, or the private fixtures leak into evaluator-visible surfaces (Benchmark Report aggregates count?). State explicitly that real-label evidence appears only as aggregate accuracy statistics, and that the demo UI is synthetic-only.

### M-5. The layout NFR targets hardware the product's only actual users won't have
§4.1 NFR: minimum 24-inch monitor, justified by TTB workstations. But §2.2 establishes the only v1 humans are token-holding evaluators — who will open this on laptops. A demo optimized for a 24-inch floor risks degrading on the 14-inch screens where it will be judged. The persona-correct constraint and the demo-survival constraint point opposite directions and the PRD picked the persona without acknowledging the trade.

### M-6. FR-13's bold clause is a weasel
"'GOVERNMENT WARNING:' header in capitals (**bold where formatting is detectable**)." Detectable by what? Neither Tesseract nor PaddleOCR (the only named engines, A1) reliably reports font weight. As written the bold requirement evaporates exactly when convenient and no test can fail it. Either specify the detection mechanism or move bold to the documented-limitations list next to font size (Non-Goals already host its sibling).

### M-7. FR-16's "REVIEW severity" presumes an ordering the Glossary never defines
"Caps LLM-assisted results at REVIEW **severity**" treats PASS/REVIEW/FAIL as an ordered severity scale; §3 defines them as advisory verdict values, full stop. The cap's semantics also have a hole: if deterministic rules say FAIL and the escalated LLM says compliant, what's emitted? "Cap" implies the LLM could *lower* a verdict, which contradicts "an LLM opinion alone never produces FAIL"'s spirit in the other direction. Define: LLM participation can only ever yield REVIEW; deterministic FAILs are never softened by an LLM.

### M-8. The Vision pays the Glossary rule lip service
§3: "no synonyms **elsewhere in this PRD**" — that binds §1. §1 says "advisory findings" (Engine Verdicts?), "compliance checks" (Checks?); UJ-1 says lowercase "field-match" and "the Checklist… shows green down the line" — green is a color semantic for PASS introduced nowhere. Each is small; collectively the document that announces vocabulary discipline as a feature demonstrates it for exactly the sections after the announcement.

---

## LOW

### L-1. "Her queue" (UJ-2) vs. the single global queue
UJ-2: "the Submission leaves **her** queue." FR-1/FR-6 model one global pending queue, no per-specialist assignment. Trivial wording — except per-specialist queues are also the only sane answer to C-2's concurrency problem, so the slip is pointing at a real design decision nobody made.

### L-2. Dispositions are irreversible and that's load-bearing
FR-6 permits "exactly one Disposition," no correction path. A real specialist who mis-clicks Rejected has no recourse; a demo evaluator who mis-clicks permanently burns one of 30–50 fixtures (compounding C-2). Even TTB's real flow (A4) has richer state. One sentence — "a Disposition may be amended until X" or an explicit non-goal — would do.

### L-3. FR-25's consequence is proving a negative
"Without the token, **no** application data or functionality is reachable" — an absolute negative is not a testable consequence; you can test enumerated routes, not "no." Also: a token in a URL is logged by browsers, proxies, and referrer headers; fine for a POC, but the consequence should be written as an enumerable test ("all routes return 401/redirect without token") and the token's known weaknesses belong in the trade-offs doc per NFR-5.

### L-4. The Vision's arithmetic is never reconciled with itself
150,000 ÷ 47 specialists ≈ 13–14 Submissions per specialist per workday — interview figures repeated as fact (untagged; §9 silent) with no sanity note. And "specialists could check five by eye" in 30–40 s puts manual eyeballing at 6–8 s/label, meaning the 5-second tool beats the human eye by ~2 seconds. The actual value proposition (consistency, exact-wording verification, audit trail) is real but the PRD hangs identity on raw speed without ever running its own numbers. An evaluator with a calculator finds this in five minutes.

### L-5. FR-19's 11-image rejection test has no actor
"An 11th [image] is rejected by validation" — by Non-Goals, no upload or data-entry path exists; only the seed process can attempt an 11-image Submission. Validation of an input surface that doesn't exist is testing theater. Scope it honestly: "seed-time validation enforces the 10-image cap."

### L-6. Open Question 3 sits unmitigated under SM-3 with zero slack
SM-3 demands "≥ 3 LLMs"; A1's roster is exactly three families. One provider outage, quota cliff, or key problem during evaluation week and a primary success metric fails — a risk the PRD itself flags (Q3: "graceful behavior if a provider is unreachable") and then leaves with no owner, no fallback model, no cached-results contingency. "Non-blocking" for the PRD; very much blocking for demo day.

---

## What's genuinely good (credit where due, briefly)

Glossary-anchored vocabulary as an explicit rule; testable-consequence format under each FR; counter-metrics existing at all; the assumption index; the addendum's two-clocks warning (A6) — which, ironically, shows the authors *know* how to keep measurement honest, making C-1 less forgivable, not more.

## Priority order for fixes

1. C-1 + H-1 + H-6 — make the 5-second claim falsifiable: hard threshold, percentile, measurement point, pipeline-latency budget, non-circular counter-metric.
2. C-2 — demo reset/replenish + concurrency story, or the evaluation eats itself.
3. H-2 + H-3 — define "verification"; caveat or rename the cost figure before NFR-5 is violated by your own headline.
4. H-4, H-5 — fix the SM-C2 vocabulary/targets; draw a real cut line in §6.
5. Mediums in implementation order; Lows as edits.
