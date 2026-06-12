# Reconciliation: Product Brief → PRD + Addendum

**Input:** `_bmad-output/planning-artifacts/briefs/brief-TTB-label-POC-2026-06-11/brief.md` ("Product Brief: TTB COLA Label Specialist Workspace", status: ready, 2026-06-11)
**Against:** `prd.md` + `addendum.md` (same folder as this file)
**Date:** 2026-06-11

## Coverage Assessment

**Overall: very high fidelity (~95%).** Every structural element of the brief — problem framing, 5-second identity, pre-compute architecture, recommend-don't-decide posture, all in-scope and out-of-scope items, all four success criteria, both personas, the procurement-study dual identity, Phase 2 vision, and the generalization claim — lands in the PRD with traceable placement, usually sharpened (e.g., brief's "several models" → SM-3's "≥ 3 LLMs"; brief's instant-load promise → FR-1's "readiness is not faked by progressive loading" consequence). The user journeys (UJ-1..3) preserve the brief's tone and demo narrative unusually well, including the "STONE'S THROW" beat, Dave's no-login-ceremony entry, and the evaluator's intended twin impressions. The addendum correctly quarantines technical depth without losing it.

The residue is what FR structures typically lose: motivating color, design-rationale narrative, and candor framing. All gaps below are documentation/narrative-level; **none requires a new FR or scope change.**

## Gap List

### G-1. Staffing-decline context dropped ("roughly 47 specialists, down from over 100 in the 1980s")
- **Input location:** Brief, "The Problem," ¶2.
- **What was lost:** PRD §1 keeps "about 47" but drops the decline from 100+. This is the urgency engine of the brief — fewer people, same 150K workload — and the strongest one-line justification for the tool's existence in front of a sponsor or evaluator.
- **Suggested placement:** One clause in PRD §1 Vision (first sentence), and/or the addendum A6 landscape narrative for `docs/`.

### G-2. The "every design choice answers a documented failure mode" meta-narrative is fragmented
- **Input location:** Brief, "What Makes This Different," ¶3 ("It is designed around why earlier attempts failed") — three legs: instant-load ↔ 5-second wall; recommend-don't-decide ↔ usurped authority; local-first ↔ the firewall that crippled the prior vendor's cloud features.
- **What was lost:** The PRD preserves each leg individually (NFR-1, FR-6/Non-Goals, NFR-2) but nowhere requires the *story* be told as a unit — and the third leg's historical why ("the firewall is what crippled the previous vendor's cloud features") appears nowhere in PRD or addendum, even though it still motivates the local-first + zero-egress-path design under the revised posture. This is the brief's central differentiation argument and the demo's intended through-line.
- **Suggested placement:** FR-26's `docs/approach.md` deliverable — add the failure-mode→design-choice mapping as required content; addendum A6 is the natural home for the prior-vendor firewall anecdote.

### G-3. "No moat" candor framing dropped
- **Input location:** Brief, "What Makes This Different," ¶1 ("there is no moat here — no proprietary data, no lock-in, nothing a competent team couldn't rebuild. Its edge is **fit** and a **measurable byproduct**").
- **What was lost:** NFR-5 covers honesty about *capabilities/limitations*, and A6 covers competitors, but the deliberate evaluator-facing candor about defensibility — a tone/voice choice that signals intellectual honesty to the take-home graders — is gone.
- **Suggested placement:** NFR-5 (one sentence extending honesty-of-claims to honesty-of-positioning) or the A6 landscape write-up.

### G-4. Image clean-up's workflow rationale dropped ("without a re-submit")
- **Input location:** Brief, Scope (in), local image clean-up bullet — "to handle imperfect photos **without a re-submit**."
- **What was lost:** FR-10 specifies the capability but not the benefit it buys: sparing the applicant round-trip (which in the real system carries the 30-day Needs Correction clock, per A4). Small, but it is the user-visible reason preprocessing exists.
- **Suggested placement:** One clause in FR-10's description; reinforces the A4 disposition-mechanics note.

### G-5. Secondary persona names (Sarah, Marcus) reduced to roles
- **Input location:** Brief, "Who This Serves," ¶2.
- **What was lost:** PRD §2.1 keeps both JTBDs faithfully (sponsor: adoption/throughput; IT: firewall/no-PII/browser-off-central-system), but Marcus disappears entirely and Sarah survives only as "Sarah Chen's wishlist" in addendum A3. Cosmetic — but downstream UX/story work that quotes personas will reach for the brief and find names the PRD doesn't use.
- **Suggested placement:** Parenthetical names in §2.1, or accept as deliberate compression (PRD already states personas live in the assignment interviews).

## Contradiction List

### C-1. Firewall posture — KNOWN DELIBERATE DIVERGENCE, not a gap
- Brief (Exec Summary, "What Makes This Different," Scope-out, and Success Criteria context): "runs entirely behind the firewall," "no cloud calls from the deployed app," "cloud models run only in an offline benchmark, never in the deployed app."
- PRD NFR-2 / FR-12 / addendum A2: LLM calls permitted in the live deployed path, modeling government-internal endpoints; outbound-call inventory mandatory; OCR-only path proves a zero-egress configuration exists.
- **Status:** Revised by Diane during PRD drafting (documented in A2). No action — though if the brief is ever re-baselined, its three firewall statements should be amended to match, since the brief is marked `status: ready` and currently contradicts the PRD on its face.

### C-2. None other found.
- "Instant / no wait" (brief Solution section rhetoric) vs. ≤ ~5 s (PRD SM-1/NFR-1): not a contradiction — the brief's own success criterion sets the same ~5 s bar; the PRD correctly codified the measurable form.
- All scope-out items, the batch-upload reframing, the font-size non-goal (including the COLAs Online disclaimer for the README, preserved in A4), and the no-decision posture are consistent across all three documents.

## Verdict

PRD + addendum may finalize after addressing G-1–G-4 as documentation-level edits (no FR/scope changes). G-5 is optional. C-1 needs no PRD change; consider annotating or re-baselining the brief so the artifact trail doesn't show an unexplained conflict to evaluators.
