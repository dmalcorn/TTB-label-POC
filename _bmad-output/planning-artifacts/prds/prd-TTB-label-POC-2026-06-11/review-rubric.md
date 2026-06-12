# PRD Quality Review — TTB COLA Label Specialist Workspace (POC)

## Overall verdict

This is a strong PRD: it has a real thesis ("speed is the trust mechanism" / "already done thinking," §1), decisions stated as decisions with the rejected alternatives preserved in the addendum, and FR consequences that are unusually testable for a POC document. What's at risk is small but sits on the headline claims: the 5-second figure is written as "≤ ~5 s" with no aggregation rule, and "verification" — the unit of the cost-per-1,000 procurement figure — is never defined. Both are one-line fixes; neither blocks downstream UX/architecture/epics work.

## Decision-readiness — strong

The PRD states decisions as decisions and shows its discards. §5 Non-Goals are emphatic and reasoned ("No font-size or dimension checking. Cannot be measured reliably from a photo… COLAs Online itself disclaims testing dimensions"). Addendum §A3 names six rejected/deferred alternatives with the reason each lost (horizontal comparison "rejected — horizontal layouts force the eyes too far apart"; batch upload "rejected as a v1 feature and reframed"). The single `[NOTE FOR PM]` (§6.2, two-bucket triage queue) sits at a genuine tension — "emotionally load-bearing for the junior/senior staffing story — revisit if timeline permits" — not at a safe checkpoint. §8 Open Questions are actually open: Q1/Q2 are data pulls with owners, Q3/Q4 are flagged with where the answer lands. The firewall reversal (addendum §A2: "Revised by Diane during PRD") is documented as a decision with consequences rather than smoothed over. No findings.

### Findings

- **low** Provider-unreachable behavior only half-specified (§8 Q3, §4.2 FR-12) — FR-12's consequence covers the *toggled-off* case ("With LLMs toggled off, the pipeline still completes"), and Q3 defers endpoint config to architecture. But graceful behavior when a provider errors *mid-run during evaluation* is a product-level demo risk, not purely an architecture call. *Fix:* add one FR-12 consequence: a failed LLM call degrades that Check to its rules-only/REVIEW path (per FR-16's pattern) without blocking Submission readiness.

## Substance over theater — strong

Nothing here is furniture. The personas earn their keep: Dave is not a persona card but a design gate that recurs as a requirement ("the Dave gate," NFR-4; "obvious enough that a 73-year-old uses it without hunting for a button," §4.1) and drives concrete choices (no login ceremony, vertical stacking, the 5-second wall). The Vision (§1) could not swap into another PRD — it is built from this product's specific history ("The last automation attempt took 30–40 seconds per label; specialists could check five by eye in that time, so they quietly abandoned it"). NFRs carry product-specific bounds, not boilerplate: NFR-2 enumerates an outbound-call inventory with a three-value classification; NFR-1 names the architectural mechanism, not just the number. The differentiation claim ("No tool for the federal reviewer's side of COLA publicly exists," §1) is backed by the landscape survey in addendum §A6 rather than asserted. No findings.

## Strategic coherence — strong

The thesis — speed as the trust mechanism, delivered by pre-computation rather than faster inference — organizes the whole document: the Pre-compute Pipeline (§4.2) is explicitly "the architectural answer to the 5-second wall," NFR-1 forbids buying the number "by faster request-time inference," and SM-C1 closes the loophole ("the 5-second figure counts only fully processed Submissions"). The dual identity (review workspace + procurement study, §1) could have been incoherence; instead it's load-bearing — the benchmark is the pipeline's "exhaust" (§4.5), and the deferred triage queue is justified *by* the benchmark ("requires confidence calibration that the benchmark data will itself provide," §6.2). Success Metrics validate the thesis rather than activity, counter-metrics exist and are substantive (SM-C2 names false rejects as "the costliest real-world error"), and §7's closing note honestly fences field-success signals out of the committed criteria. MVP scope is a coherent problem-solving + evidence-producing slice. No findings.

## Done-ness clarity — strong

This is where the PRD is most disciplined. Every FR carries explicit "Consequences (testable)" with concrete cases — FR-13 gives the exact PASS/FAIL boundary ("Title-case 'Government Warning'… → FAIL"; "incidental whitespace differences → PASS. No LLM participates in this Check."), FR-15 encodes the cross-commodity ABV trap as a test, FR-14 fixes three-band behavior while honestly deferring numeric thresholds via tagged assumption. The few soft phrases that remain are mostly concretized by their consequences (FR-8's "clear, easy-to-find help" is cashed out as "reachable… in one click and explains the PASS / REVIEW / FAIL vocabulary"). Remaining gaps are at the edges, not the core.

### Findings

- **medium** Headline 5-second bound is fuzzy where it can least afford to be (§7 SM-1, §10 NFR-1, FR-1) — "≤ ~5 s… measured across the seeded corpus" leaves both the number ("~") and the aggregation (every Submission? median? p95?) undefined. This is the product's identity metric and the prior pilot's exact failure mode; an evaluator timing 5.8 s on one Submission can't be told whether that's a pass. *Fix:* drop the tilde and state the protocol in SM-1, e.g. "p95 ≤ 5.0 s across all ready Submissions in the seeded corpus, measured on the deployed demo."
- **low** FR-5's "step N of M" is undefined — no consequence says what a step *is* (Checklist items? phases of review?), so the status bar's done-state can't be tested as written. *Fix:* one sentence binding steps to Checklist items or naming the step list as a UX-workflow decision.
- **low** FR-10's bar admits zero improvement — "OCR accuracy on the preprocessed image is measurably ≥ accuracy on the original" is satisfied by preprocessing that does nothing. *Fix:* require strict improvement on the degraded-fixture subset (the population FR-10 exists for), tolerance to be set with the corpus.

## Scope honesty — strong

Omissions are explicit and argued, not inferred. §5 does real work (eight non-goals, each with a reason; the batch-upload entry even pre-writes the stakeholder-management answer). §6.2 separates deferred from rejected, and the addendum (§A3) preserves *why* for each. Twelve `[ASSUMPTION]` tags are indexed in §9; the open-items density (4 Open Questions, all marked blocking/non-blocking) is right for a POC PRD that has already absorbed its research phase. De-scoping is done in the open — the help knowledge base (FR-8), allowable revisions (§6.2), and the Section 508 audit (NFR-4) are all explicitly shrunk rather than silently dropped. One roundtrip gap, noted under Mechanical notes. No dimension-level findings.

## Downstream usability — strong

The Glossary (§3) is genuinely load-bearing — Engine Verdict vs. Disposition vocabulary separation is declared ("Distinct vocabulary from Engine Verdict") and held throughout; "Submission," "Check," "Ruleset," "Checklist" are used verbatim across FRs, UJs, and SMs. IDs are contiguous and unique (FR-1–26, UJ-1–3, SM-1–4 + SM-C1/C2, NFR-1–6), every FR→UJ "Realizes" link and SM→FR "Validates" link resolves, and sections extract cleanly (each feature group restates its purpose rather than pointing "see above"). This PRD will source-extract well into the UX/architecture/epics chain it names in §0.

### Findings

- **medium** "Verification" — the unit of the headline procurement figure — is not in the Glossary (§1, FR-22, SM-3, addendum §A7) — "cost per 1,000 verifications" is the number evaluators walk away with (UJ-3), but nothing says whether a verification is one Submission, one Check execution, or one field comparison; the figure can vary by an order of magnitude depending on the answer. *Fix:* add **Verification** to §3 (most natural: one Submission fully processed by one engine/model configuration) and use it verbatim in FR-22/SM-3.

## Shape fit — strong

The shape matches the product: a capability spec organized by feature groups, with exactly three UJs — each with a named protagonist and each earning its place by driving decisions (UJ-1 → normalization tolerance and the no-ceremony entry; UJ-2 → preprocessing comparison display and exact-wording FAIL; UJ-3 → next-by-type and the Benchmark Report as first-class features). For a single-operator internal tool this could have been over-formalized; it isn't — there are no floating UJs, no persona inflation, and the evaluator is correctly modeled as a second real user rather than bolted on. The chain-top posture (§0 names the downstream BMad consumers) is matched by the traceability discipline noted above, and the addendum is the right pressure valve — technology direction, regulatory depth, and fixture detail are kept out of the PRD body but preserved. No findings.

## Mechanical notes

- **Assumptions Index roundtrip gap:** NFR-4's inline `[ASSUMPTION: full Section 508 audit out of POC scope; USWDS adherence is the v1 accessibility mechanism]` (§10) is missing from the §9 index. All twelve indexed entries do appear inline; this is the only inline tag not indexed.
- **Bare `[ASSUMPTION]` tags:** FR-1 (queue order) and FR-15 (unevaluable conditionals) carry contentless `[ASSUMPTION]` markers whose substance lives only in §9. They resolve, but a section extracted alone loses the content — inline the one-line substance.
- **Unnumbered feature-specific NFRs:** §4.1's "Feature-specific NFRs" (24-inch monitor, the Dave usability bar) sit outside the NFR-n ID scheme and partially duplicate NFR-4. Downstream extraction will pick up NFR-4; the §4.1 block risks being missed or double-counted. Fold into NFR-4 or give them IDs.
- **Working title unresolved:** "*Working title — confirm.*" still sits under the H1 — a stray open item outside §8.
- No glossary drift found; "specialist" appears as shorthand for "Label Specialist" but never as a competing synonym (agent/examiner/adjudicator are explicitly banned and absent).
