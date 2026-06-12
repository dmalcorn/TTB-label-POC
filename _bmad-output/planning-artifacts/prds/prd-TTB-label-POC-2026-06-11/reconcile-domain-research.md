# Reconciliation: Domain Research → PRD + Addendum

**Input:** `_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md`
**Against:** `prd.md` + `addendum.md` (prd-TTB-label-POC-2026-06-11)
**Date:** 2026-06-11
**Known deliberate divergence (excluded from gap list):** firewall posture revised by Diane — LLM calls allowed in the deployed live path, modeling government-internal endpoints (research said offline-harness-only). Documented in NFR-2 and addendum A2; treated below only where a *residual* loss survives the revision.

---

## 1. Coverage Assessment

Overall: **very high fidelity.** The PRD + addendum preserve essentially all load-bearing research content, and the deliberate PRD/addendum split works — regulatory depth (A4), fixture/data depth (A5), landscape narrative (A6), and cost framing (A7) all land in the addendum with correct citations.

Confirmed covered (spot-checked, no action needed):

| Research item | Where covered |
|---|---|
| 150k apps / 47 examiners / half-day data-entry / 5-second lesson | PRD §1 Vision |
| Two clocks (queue days vs. per-interaction seconds) | Addendum A6 (explicit "never conflate") |
| Online-vs-paper exact counts TODO | PRD §8 Open Q1 (carried) |
| Same Field of Vision §5.63 (40% circumference; flag-only with per-element presence) | FR-17, Glossary, A4 |
| Government Warning exact text, header caps+bold-where-detectable, deterministic, no LLM | FR-13 |
| Type-size table §16.22 + font-size non-goal + COLAs Online disclaimer quote | PRD §5 Non-Goals, A4 |
| Cross-commodity ABV trap (spirits/wine/malt matrix) | FR-15 consequence, A4 |
| Determinism taxonomy (deterministic / field-match / hybrid / flag-only) | Glossary "Check", §4.3 |
| False-rejects-costliest + REVIEW band + human-never-auto-approves | SM-C2, §5, FR-14 |
| CFR citations as data with source dates (2022 renumbering cautionary tale) | §4.3 description, §6.2, A3 |
| Standards-of-fill lookup, name/address qualifying phrase | FR-15 |
| "STONE'S THROW" normalization tolerance | FR-3, FR-14, UJ-1 |
| Tesseract+PaddleOCR complementarity, PP-OCRv5 candidate, uniform interface | FR-11, A1 |
| OpenCV-class local preprocessing (deskew/perspective/CLAHE/glare), unpaper | FR-10, A1 |
| LangChain local-only toggleable tracing w/ model ID capture | FR-24, FR-12, A1 |
| CPU-only benchmark mode (GPU uncertainty) | NFR-1, A1 |
| Pre-compute targets the interaction clock | §4.2, NFR-1 |
| Registry images private-fixtures-only (IP not privacy), no PII | FR-20, NFR-3 |
| Registry ~48h image visibility, Kaggle/data.gov, synthetic-for-public | A5 |
| Landscape camps + empty fourth quadrant + COLAClear analog + LabelScreener/Label Score non-resolution + tailwind | A6, PRD §1 |
| Outbound-call inventory deliverable | FR-26, NFR-2 |
| $0-marginal local path as headline procurement finding | FR-22, A7 |
| Disposition vocabulary (Approved / Needs Correction / Rejected) and 30-day clock | Glossary, A4 |
| Allowable revisions — consciously out of scope | §6.2 (tagged assumption) |

Vocabulary check: clean. PRD uses Label Specialist (not agent/examiner), Disposition vs. Engine Verdict as distinct vocabularies, "malt beverage" (not "beer") per Part 7, PASS/REVIEW/FAIL exactly as the research framed them. No misuse found.

---

## 2. Gaps (silently dropped or under-specified)

### GAP-1 — Class/type "separate and apart" + "no conflicting designations across labels" checks dropped
**Input location:** Regulatory Requirements → Always-mandatory elements table, Class/Type row (§5.141, §5.165): "*separate & apart; spelled correctly; no conflicting designations across labels*."
**Status in PRD/addendum:** FR-16 covers designation validity (lists, spelling, LLM-on-ambiguity) but says nothing about (a) the separate-and-apart placement requirement or (b) cross-label designation consistency within a multi-image Submission. Neither appears in A4.
**Severity:** Medium — cross-label conflict is a real, checkable rule (string comparison across per-image OCR results, no spatial inference needed), so it does not deserve to fall into the flag-only bucket by omission.
**Suggested placement:** Add a consequence to FR-16 ("designations extracted from different label images of one Submission that conflict → FAIL/REVIEW with both values shown"); note "separate and apart" as flag-only alongside FR-17's spatial checks, or list it in A4 as Ruleset-data depth.

### GAP-2 — Proof statement rules absent despite proof appearing in seed fixture #1
**Input location:** Regulatory Requirements → Alcohol Content row (§5.65): "*proof optional but must be distinguished (e.g., parentheses/brackets) and in the same field of vision*."
**Status in PRD/addendum:** FR-15 has "alcohol-content statement format" generically; A5's seed fixture is "45% Alc./Vol. (90 Proof)" — but no Check anywhere covers proof formatting or the obvious deterministic ABV↔proof consistency check (proof = 2 × ABV), which the fixture itself invites.
**Severity:** Medium-low — likely intended to live in the Ruleset data (A4 points at `ds-labeling-checklist.pdf` and drafted `docs/regulatory-rules-*.md`), but the PRD's only fixture example contains a proof statement the FRs never mention.
**Suggested placement:** One clause in FR-15's deterministic format list ("including optional proof statement format and ABV/proof consistency where stated"), or an explicit line in A4.

### GAP-3 — Local/open-source small-VLM option lost entirely (residual beyond the firewall divergence)
**Input location:** Technical Trends → VLM section (dots.ocr ~1.7B, Qwen3-VL, GLM-OCR ~0.9B "run locally at near-zero inference cost"); Recommendations #1 ("if an LLM fallback is enabled in the live path, it must be a locally-hosted small VLM"); Future Outlook ("shrinking local models… a good forward-looking note for the procurement-informing goal"; "promote the best-performing local model" in Phase 2).
**Status in PRD/addendum:** The firewall revision (A2) legitimately removes the *mandate* for a local-only LLM path. But the research's *procurement* point survives independently: a locally-hostable small VLM as a benchmark comparator, and the "local models keep getting more capable" outlook. A1's LLM roster is cloud-only (GPT/Gemini/Claude); the local-VLM candidate and the forward-looking note appear nowhere. NFR-2's "OCR-only path proves a zero-egress configuration exists" preserves zero-egress for OCR, but the benchmark — the procurement study itself — now compares zero local LLM options, weakening the $/1,000 story the research framed (local ≈ $0 vs. cloud token cost applies to OCR only as written).
**Severity:** Medium — this is procurement-evidence scope, the POC's second identity.
**Suggested placement:** A1 LLM roster ("consider one locally-hostable small VLM, e.g. Qwen-VL-class, as a fourth benchmark candidate — CPU-mode caveats apply") and/or A7 + a `docs/` landscape note carrying the shrinking-local-models outlook. Optionally an Open Question in PRD §8.

### GAP-4 — Government Warning body-case handling is stricter than the research prescribed (false-FAIL risk)
**Input location:** Regulatory Requirements → Government Warning POC implication: "*Normalize whitespace/case for the body, but enforce the caps+bold 'GOVERNMENT WARNING:' token*" (plus required "S"/"G" capitals).
**Status in PRD/addendum:** FR-13 says "Whitespace is normalized; wording and **required casing** are not." If "required casing" is read narrowly (header + S/G) this matches the research; read broadly (full case-sensitive body match) it would FAIL a label that prints the entire warning in capitals — a common real-world rendering that is compliant — i.e., exactly the false-reject class SM-C2 guards against.
**Severity:** Low-medium — wording precision, not a missing feature; but it is the one place the PRD could be implemented contrary to the research's explicit guidance.
**Suggested placement:** Tighten FR-13: "body case is normalized; the 'GOVERNMENT WARNING:' header capitals and the capital S/G in Surgeon General are enforced." Also note: the research's "separate and apart / one statement" rule is only half-carried (FR-13 has "one statement"; *separate and apart* is spatial and belongs with FR-17's flag-only class or an FR-13 caveat).

### GAP-5 — "Online submissions arrive cleaner/structured" fixture-realism point dropped
**Input location:** Domain Scale & Structure → Filing Channels: COLAs Online "enforces business rules at submission (rejecting incomplete/invalid data up front)… so online submissions arrive cleaner and structured, which is exactly the structured-field input our POC assumes."
**Status in PRD/addendum:** The Mock COLA Database is modeled on Form 5100.31 (FR-19, A5), but the corollary for corpus design is unstated: seeded *application fields* should be structurally valid (COLAs Online would have rejected garbage), so fixture errors should live on the **labels**, not in malformed application data. A5's corpus-design note covers image degradation but not this.
**Severity:** Low — fixture-design guidance; cheap to lose, cheap to keep.
**Suggested placement:** One line in A5 corpus design intent, or an FR-20 consequence.

---

## 3. Contradictions

1. **NFR-2 / FR-12 vs. research firewall fork and Recommendation #1–2** — research mandated cloud VLMs offline-harness-only and local-only live path. **Known deliberate divergence; not a gap.** The addendum (A2) documents the revision, its rationale, and the surviving obligations (outbound-call inventory, classification, tracing off-host-free, OCR-only zero-egress proof). Handled correctly. Residual loss is GAP-3 only.
2. **FR-13 casing wording vs. research normalization guidance** — potential contradiction depending on reading; see GAP-4. No other contradictions found: dispositions, verdict vocabulary, ABV matrix, non-goals, scope boundaries, and risk posture all align with the research.

## 4. Minor notes (no action required)

- Research recommended TTB's **Anatomy of a Distilled Spirits Label** tool specifically as "grounding for the POC's checklist UI and field map." A6 keeps it only as landscape context; consider handing the UX workflow that pointer.
- Research's name/address check column says "field-match **to permit**"; the POC has no permit data — FR-14 matching against the application field is the right mock-world reduction. Fine as-is; could be a one-line limitation note in `docs/`.
- Conditional disclosures (FD&C Yellow #5, cochineal/carmine, treatment with wood §5.73, commodity/neutral spirits §5.71, state of distillation §5.66(f)) are compressed into FR-15's "etc." — acceptable because Rulesets are data and A4 anchors the authoritative checklist, but the per-type rule docs (`docs/regulatory-rules-*.md`) must enumerate them fully.
