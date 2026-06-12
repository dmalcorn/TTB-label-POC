---
name: TTB Label Review
status: final
created: 2026-06-12
updated: 2026-06-12
sources:
  - prd: ../../prds/prd-TTB-label-POC-2026-06-11/prd.md
  - addendum: ../../prds/prd-TTB-label-POC-2026-06-11/addendum.md
  - brief: ../../briefs/brief-TTB-label-POC-2026-06-11/brief.md
  - ux_notes: ../../../../docs/ux-design-notes.md
  - domain_research: ../../research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md
---

# EXPERIENCE.md — TTB Label Review

> Experience spine: information architecture, behavior, states, interactions, accessibility, journeys. Visual identity (tokens, palette, components) lives in `DESIGN.md`; this file references its tokens by `{path.to.token}` and specifies only the behavioral delta on top of USWDS. Spine wins on conflict with any mock or import.

## Foundation

**Form-factor: desktop web, large monitor only.** Browser-based app with server-side compute (CPU-only, no local disk) — matching the federal workstation reality. Tuned for **min 24", typical 27" or dual-24** displays. This is a specialist's daily desk tool, **not** a responsive or mobile experience; there is no phone/tablet layout and none is planned.

**UI system: USWDS, self-hosted.** Both spines inherit USWDS components, tokens, and its Section 508 / WCAG AA baseline. `DESIGN.md` names the Treasury-toned brand layer; this spine specifies behavior only. All assets vendored — no outbound calls (firewall).

**The load-bearing premise (governs every screen):** results are **pre-computed in the background** before the specialist opens an item. The UI's entire job is to (a) never block on that work and (b) present the already-computed result instantly (~5s readiness is the product identity, NFR-1 / SM-1). The specialist **decides**; the engine only **recommends** (P4).

**Single-user POC.** Concurrent/multi-user access and item-locking are out of scope (one evaluator per token). The UX does not design for two specialists pulling the same item; the demo-reset and fixture-enqueue surfaces are operator tools, not concurrent-use features.

**Two vocabularies that must never blur** — the spine enforces this everywhere:

| | Engine **Verdict** (advice) | Specialist **Disposition** (the decision) |
|---|---|---|
| Values | PASS · REVIEW · FAIL | Approved · Needs Correction · Rejected |
| Register | muted Tag / Alert, labeled "Suggested:" | full-register Buttons, bottom action bar |
| Authority | recommendation only | the official, recorded act |
| Never | pre-selects a disposition | inherits a verdict's color/wording |

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| **Token gate** | App URL | Lightweight access (no login ceremony). Clean denial on bad/absent token; no data leakage. |
| **Queue / "Get Next"** | After token / `g q` | One primary action: **Next Submission**. Optional beverage-type filter (Any · Wine · Spirits · Beer). Informational stats strip. **No list browsing.** |
| **Review Workspace** | Next Submission → serves next ready item | The heart. Beverage banner + chevron + label image(s) + stacked field comparison + smart checklist + suggested verdict + Notes + Disposition bar. |
| **Help panel** | `[?]` in header (every screen) | Searchable local knowledge base + inline "Why?" context. One-click, predictable spot. |
| **Benchmark Report** | Evaluator entry (header link, evaluator build) | Procurement study: OCR engines + LLM models side-by-side on speed / accuracy / cost-per-1,000. |
| **Operational** (non-specialist) | Direct routes | Demo reset (restore fixture queue, clear dispositions); fixture enqueue (observe submitted → processing → ready). |

**Deferred to Phase 2 (placeholder in IA, not designed as a live control):** the **two-bucket triage queue** ("Likely compliant" / "Needs a closer look"). It requires verdict-confidence calibration from benchmark data that doesn't exist yet. The Queue screen reserves vertical space and a comment marker for it but ships **Next Submission + beverage-type filter only.**

**Navigation model:** single forward path — Token gate → Queue → Review → (record disposition) → Queue → next. No back-stack browsing, no search-and-pick over submissions. The only "lists" in the product are *within* a submission (the checklist, the field cards) and *within* the Benchmark Report (the comparison table).

→ Composition reference (offline HTML mocks; **spine wins on conflict**):
- [mockups/token-gate.html](mockups/token-gate.html) — token entry + clean denial state
- [mockups/queue.html](mockups/queue.html) — Next Submission at rest, beverage filter, Phase-2 triage placeholder, empty-queue state
- [mockups/review-workspace.html](mockups/review-workspace.html) — the hero: DISTILLED SPIRITS / REVIEW (Gov Warning FAIL + char-diff, Brand REVIEW + Enhance, smart checklist, disposition bar)
- [mockups/help-panel.html](mockups/help-panel.html) — searchable KB + PASS/REVIEW/FAIL explainer + no-results state
- [mockups/benchmark-report.html](mockups/benchmark-report.html) — evaluator OCR + LLM comparison table

## Voice and Tone

Microcopy. Brand voice / aesthetic posture live in `DESIGN.md`. **Plain language, federal, calm** (Plain Writing Act). Never alarming; never jargon.

| Do | Don't |
|---|---|
| "Next Submission" | "Fetch next record" |
| "Suggested: REVIEW — 2 items need your eyes. You decide." | "Verdict: REVIEW (auto)" |
| "Send back for correction" | "NEEDS_CORRECTION" |
| "Capitalization differs; the text otherwise matches." | "Normalization tolerance applied (case)" |
| "No submissions waiting right now." | "Error: queue empty" |
| "We couldn't check font size — that's measured on the physical label, not the photo." | (silently omitting it) |
| "The wine queue is empty. Try Any, or check back later." | "0 results for type=WINE" |

Two tone rules specific to this product: **(1)** advisory copy always returns authority to the human ("You decide," "needs your eyes," "your call"); **(2)** limitations are stated plainly in the same voice as capabilities (font-size, spatial co-location, OCR uncertainty) — honesty is a feature, not a disclaimer to bury.

## Component Patterns

Behavioral. Visual specs live in `DESIGN.md.Components`.

| Component | Use | Behavioral rules |
|---|---|---|
| **Next Submission button** | Queue | Serves the oldest **ready** submission (deterministic, oldest-first). Skips not-yet-`ready` items silently — never serves a partial. With a beverage-type filter set, serves the oldest ready of that type. Auto-focused on Queue load (Enter fires it) but **never auto-opens** — one deliberate click (U1). |
| **Beverage-type banner** | Review (top) | Renders type **word + icon + accent** (`{colors.spirits}`, `{colors.wine}`, or `{colors.beer}`) the instant the screen loads — required checks differ by type, so this orients first. |
| **Chevron / Step Indicator** | Review (top) | Progress *map*, not a wizard (U4): ① Identity → ② Mandatory text → ③ Gov. Warning → ④ Conditional → ⑤ Decide. Single page; clicking a step **scrolls** to that field group. Done steps carry ✓; current step carries a non-color marker (a literal "step 3 of 5" / "current" label, not contrast alone). Conditional step ④ only appears when conditional checks are triggered; when absent, the remaining steps **renumber cleanly** (Decide becomes ④) so scroll/focus targets never go off-by-one. |
| **Field comparison card** | Review (right column) | Application value stacked **above** OCR value (vertical, never side-by-side). Status chip right-aligned. **Match** = quiet. **Mismatch** (values differ) = loud (left bar + tint + character diff on the differing span only). **Not found** (element genuinely absent on the label) = distinct from mismatch: card shows "Not found on label" in the OCR slot, REVIEW or FAIL per the rule for that element (a missing *mandatory* element is FAIL; a missing *conditional* is per trigger). (An element that *is* on the label but unreadable from the photo is the separate OCR-unreadable state — REVIEW, see State Patterns.) **Soft/normalized** (e.g., "STONE'S THROW" vs "Stone's Throw") = amber "check" + plain-language note, **never red** (P5). When an element appears across multiple images (brand on front + back), the card notes which image role the matched value came from. Mismatches and not-founds sort to top; matches sink. "Why?" Accordion reveals CFR citation + raw OCR + verdict rationale. |
| **Government Warning card** | Review | Special "Required (27 CFR §16.21) vs On-label" layout — compares to the *regulation*, not a maker value. Deterministic. Character-level diff in mono so wording deviations are unmistakable. Three distinct outcomes, never conflated: **wording deviation** = char-diff (FAIL); **entirely absent** from all images = FAIL with plain copy "Required Government Warning not found on the submitted images" (no diff against an empty string); **bold/caps undeterminable** from the image = "couldn't verify," REVIEW, not a silent PASS. If the warning text spans multiple images, the engine assembles across faces; if it can't, it surfaces "couldn't verify — warning spans multiple images" rather than a false FAIL. |
| **Smart checklist** | Review (right column) | Generated from the ruleset for the beverage type. Engine **pre-ticks** auto-verified PASS items (muted); REVIEW/FAIL items left unticked + highlighted for the human. Clicking an item **scrolls to its field card**. "N of M done" counter. Tick-state persists per submission across navigate-away; clears on disposition (U3). |
| **Suggested-verdict Alert** | Review (top) | USWDS Alert in verdict tint, labeled "Suggested:". Roll-up of all checks ("4 of 6 passed automatically; 2 need your review"). **Roll-up rule (severity precedence):** any check FAIL → submission **FAIL**; else any REVIEW (or any "can't-verify") → **REVIEW**; else **PASS**. The most severe state always wins — the Alert can never suggest PASS while any check is FAIL/REVIEW. Advisory register only — never a button, never pre-selects disposition. |
| **Image panel** | Review (left column) | 1–10 images, paged with role labels (Brand / Back / Neck / Strip / Other). Paging hidden for a single image; scales to the 10-image max. Zoom. **Enhance toggle** shows the local-OpenCV preprocessed image (deskew / glare / contrast) **alongside** the original — neither replaces the other silently (FR-7). When no preprocessing was applied (clean photo), the toggle is **omitted**, not shown inert. If an image fails to decode, that face shows an honest "couldn't load this image" placeholder while other faces still display. |
| **Notes field** | Review (action bar) | **Required** when disposition = Needs Correction or Reject (maker needs a reason); optional for Approve. Soft-gate validation blocks the record until filled for those two. |
| **Disposition action bar** | Review (bottom) | Three controls: Approve (filled primary), Needs Correction (outline navy), Reject (outline red). **None pre-selected** (P4). On click, the bar **disables to prevent double-submit** while the save is in flight. On success: persists disposition + timestamp, returns to Queue with a brief "Recorded — Undo" affordance (see State Patterns). On save failure: see State Patterns (stays put, retains work). |
| **Benchmark comparison table** | Benchmark Report | USWDS Table: engines/models as rows, metrics (accuracy, latency, cost/1,000, CPU-only flag) as columns. Sortable by column. Recommendations callout above. Read-only. |

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| Cold load (pre-compute done) | Review | Instant render from cached results (~5s p95 from click). No spinner-then-content dance — the result *is* the first paint. |
| Empty queue | Queue / Next Submission | Calm message: "No submissions waiting right now." Next Submission disabled with helper text. **Not** an error. |
| Empty type queue | Queue (filtered) | "The wine queue is empty. Try Any, or check back later." Filter stays set. |
| Item not yet `ready` | Queue (behind the scenes) | Skipped in queue order — never served partially. Invisible to the specialist. |
| Pipeline failure (unreadable image / engine crash) | Review | Visible honest error state on the affected check(s), not a silent stall. Other checks still shown. |
| LLM provider unreachable (FR-12) | Review | Affected checks degrade to **OCR-only** with a visible notice ("LLM check unavailable — showing OCR result"). Screen never blocks on an LLM call. With LLMs config-off, screen still fully functions on OCR-only. |
| Match (clean) | Review field card | Quiet — thin border, green ✓ "match" chip. Both raw values still visible. |
| Soft / normalized diff | Review field card | Amber "check" state + plain note. PASS-eligible but surfaced for the human's judgment (P5). Zero false FAILs on this class is a counter-metric (SM-C2). |
| Mismatch | Review field card | Loud — left bar + tint + character diff on the differing span only. Floats to top. |
| Can't verify (font size, spatial co-location) | Review checklist / card | Stated plainly: "We can't check this from a photo." REVIEW, never a guessed PASS/FAIL. |
| OCR unreadable for a human-readable field | Review field card | Distinct from mismatch: "Couldn't read this field reliably from the photo — please verify by eye." REVIEW, **not** FAIL (garbage rendered as a diff would wrongly imply the *label* is wrong). |
| Blank application value | Review field card | Application side empty but label has text: show the OCR value with "No value submitted in the application for this field." REVIEW for human judgment — no baseline to diff against. |
| All checks REVIEW (nothing quiet) | Review | Calm-by-default inverts gracefully: roll-up copy "0 of 6 passed automatically — all items need your review." Layout still legible when nothing sinks. |
| Zero usable images | Review image panel | Honest "No images available for this submission"; affected checks degrade accordingly (REVIEW), never a blank panel. |
| Open REVIEW items at Approve | Review (soft gate) | Calm USWDS Modal: "2 items weren't reviewed — approve anyway?" Confirms; doesn't hard-block (P5). Skips are deliberate, not silent. |
| Disposition recorded | Review → Queue | On success: returns to Queue; checklist tick-state for that item cleared; ready for Next Submission. Stay-in-flow. A brief **"Recorded — Undo"** affordance lets the specialist reverse a just-recorded disposition (esp. a mis-clicked Approve) within the session before moving on; Undo reopens the item and voids that disposition record. After it dismisses, a recorded disposition is final for the POC (no back-stack to re-pick). |
| Disposition save fails | Review (stays) | Save failure (DB/network) does **not** return to Queue. Stays on Review, re-enables the action bar, shows an honest error ("Couldn't record that — try again"), and **retains Notes + checklist tick-state**. Honors the no-work-loss promise; a never-recorded item is never mistaken for adjudicated. |
| Browser refresh mid-review | Review | Checklist tick-state and Notes persist per submission (server-side with the pre-computed record), so a refresh resumes where the specialist left off — not just navigate-away. Cleared only on a recorded disposition. |
| Cold demo start (nothing ready yet) | Queue | If no submissions of any type are ready (fresh deploy / post-reset, items still `processing`), Queue shows the same calm empty state with helper copy ("Submissions are still being prepared — check back in a moment"), never an error or a partial. |
| Demo reset while an item is open | Review → Queue | If an operator resets the queue while a specialist has an item open, recording a disposition fails gracefully (item no longer exists) and routes back to Queue with a plain notice; no crash, no orphaned write. |
| Benchmark Report — no data yet | Benchmark Report | Before any benchmark run has populated figures, the table shows an honest empty state ("No benchmark runs yet — figures appear after the harness runs"), not zeros that read as real measurements. |
| Help search — no results | Help panel | Calm no-results state ("No help articles matched — try a different term"), consistent with empty-queue voice. Browsable KB list still visible to scan. |

## Interaction Primitives

**Two-track by design** — a mouse-only path that is *always fully sufficient* (Dave, low-tech, the adoption gate) layered with a keyboard power path (Jenny, high-volume).

- **Mouse path (sufficient):** one big obvious button per screen; click checklist item → scroll to field; click chevron step → scroll; click "Why?" → expand. No hover-only affordances for primary actions.
- **Keyboard power path (additive, documented in Help):**
  - `N` — Next Submission
  - `A` / `C` / `R` — Approve / Needs Correction / Reject (each routes through its confirm/notes gate)
  - `←` / `→` — move between label image faces
  - `?` — open Help
  - `Esc` — close modal / Help / expander
- **Shortcut safety (load-bearing — these fire irreversible federal acts):** all single-letter shortcuts are **inert when focus is in any text input / textarea / contenteditable** (so typing a correction reason in Notes can never fire `R`) and **inert while a modal owns focus**. `A`/`C`/`R` route through their confirm/Notes gate — a real focus-trapped dialog, never an inline auto-submit. Screen-reader users (whose browse mode consumes single letters) use the on-screen buttons as the canonical path; the buttons, not the shortcuts, are the spec'd route.
- **Auto-focus, never auto-act:** Queue lands focus on Next Submission (Enter fires) but does not auto-open a submission (U1).

**Banned everywhere:** auto-selecting a disposition; color-only status; hover-only primary actions; work-losing timeouts; any spinner that blocks the pre-computed result; serving a partially-processed submission.

## Accessibility Floor

Behavioral. Visual contrast lives in `DESIGN.md` — USWDS AA baseline, plus an explicit contrast table for the domain combos this product introduces (verdict text on tints, the three beverage banners). Verdict foregrounds were darkened to clear 4.5:1; beer banner keeps dark ink (white fails). Downstream must hold those ratios.

- **Section 508 / WCAG 2.x AA** via USWDS components (keyboard nav, focus states, ARIA, contrast). Full 508 audit is out of POC scope; USWDS adherence is the v1 mechanism.
- **Color never alone** — every status carries **icon + word** (✓ match / ⚠ check / ✕ mismatch; PASS / REVIEW / FAIL). Serves colorblind users and the older userbase.
- **Sized for older eyes:** body ≥16px, comparison values 19px, click targets ≥48px (`DESIGN.md.typography`).
- **Keyboard-complete:** every action reachable by keyboard; Tab order matches reading order (left image panel → right comparison/checklist → bottom action bar); `Esc` closes the topmost layer.
- **Screen reader — on load:** Review announces beverage type + suggested verdict by moving focus to the `<h1>`/role=status summary ("Distilled Spirits, suggested verdict REVIEW, 2 of 6 checks need review"). Field cards announce status as **text** ("FAIL — mismatch"), not color.
- **Screen reader — after load (live regions):** changes that happen post-render must announce, or they're invisible. A polite `aria-live` region carries the "N of M done" counter and the suggested-verdict roll-up; the Enhance toggle ("showing enhanced image beside original") and the "LLM check unavailable — showing OCR result" notice announce when they appear.
- **Character-diff has a text equivalent:** the Government Warning / mismatch diff is never conveyed by a colored span alone. It carries (a) a screen-reader text equivalent naming the difference ("Required: 'GOVERNMENT WARNING' — on label: 'Government Warning'"), (b) a perceptible visual treatment (bold + ≥3:1 background change + marker, not a thin underline or color alone), and (c) survival of Windows High Contrast / forced-colors mode.
- **Focus management:** the soft-gate Modal and Help panel trap focus while open, move focus to the dialog heading/first control on open, and **return focus to the triggering control** on close/Esc (Approve button, or the `[?]`). Activating a checklist item or chevron step moves **focus** to the target field card, not just the scroll position — keyboard/SR users land on it, not behind it.
- **Notes validation is accessible:** the Notes textarea has an associated `<label>`; when the soft-gate blocks a Needs Correction / Reject, focus moves to the field, `aria-invalid` is set, and a plain-language error announces via a live region ("Add a short reason for the maker before sending this back.") — never signaled by a red border (color) alone.
- **No work loss:** Notes and checklist tick-state persist across navigate-away **and full browser reload**; no timeouts.
- **Calm by default** — the cognitive-accessibility move: quiet matches, only problems draw the eye, one primary action per screen (P1/P2).

## Key Flows

### Flow 1 — Dave clears a clean bourbon without breaking stride

Dave Morrison, 28 years a Label Specialist, still prints his email. He is the adoption gate: anything slow or that second-guesses him, he abandons.

1. Dave opens the workspace (token URL — no login). Focus is already on **Next Submission**.
2. He clicks it. In under five seconds the Review screen is fully there — amber **DISTILLED SPIRITS** banner, label image left, fields stacked right.
3. Out of 28 years of habit he eyeballs the label once. The screen agrees: brand name, ABV, net contents, Government Warning all show quiet green ✓ matches; the spirits checklist is pre-ticked green down the line; the suggested verdict reads "Suggested: PASS — all checks passed automatically. You decide."
4. **Climax:** there is nothing to hunt for and nothing arguing with him. The machine did the boring confirming; the judgment is still his. He clicks **Approve** — the one filled button — and the screen returns to Queue with Next Submission already focused.
5. He clicks Next Submission again. Elapsed on that label: well under a minute. He never touched the keyboard, never opened Help, never waited on a spinner.

Failure: if pre-compute had failed, the screen would show an honest per-check error — not a stall — and Dave would simply review by eye, the way he always has.

### Flow 2 — Jenny catches a creative Government Warning

Jenny Park, eight months in, fast, keyboard-fluent, used to a printed checklist taped to her desk.

1. She presses `N`. A gin label loads — **DISTILLED SPIRITS**, suggested verdict **REVIEW**.
2. Her eye goes straight to the two loud cards (everything calm has sunk below them). The **Government Warning** card is **FAIL**: the required §16.21 text and the on-label text sit stacked in mono, and the character diff lights up exactly where the label reworded "GOVERNMENT WARNING:" into title case. No ambiguity about *what's* wrong.
3. The **Brand Name** card is amber **REVIEW** — the photo was shot at an angle with glare. She clicks **Enhance**; the deskewed, glare-corrected image appears beside the original. The brand name is legible; it matches. She ticks that checklist item herself — a judgment tick, not a machine tick.
4. She works down the remaining required items using the checklist as her table of contents, clicking each to jump to its card. "5 of 6 done."
5. **Climax:** the warning is a real, substantive defect — the maker has to fix the wording. She presses `C` for **Needs Correction**. Because correction requires a reason, the Notes field is focused and required; she types one line for the maker, records it. The submission leaves the queue; Queue returns, Next Submission focused.

Failure: had the diff been only capitalization in the *body* text (an allowed incidental difference), the card would have been amber "check," not red — and Jenny would have used her judgment rather than reflexively bouncing it.

### Flow 3 — An evaluator stress-tests the procurement case

A take-home evaluator weighing whether to buy, not a specialist.

1. They open the token-gated URL and click **Next Submission** repeatedly, watching the clock — each Review screen is ready in roughly five seconds. The speed claim is self-evidently true.
2. They set the filter to **Wine** and pull one: the checklist visibly changes to wine rules (no ABV demanded on a ≤14% table wine). The system clearly knows its domain.
3. They deliberately pull a degraded-photo submission and watch the original/enhanced comparison do real work.
4. **Climax:** they open the **Benchmark Report**. Tesseract and PaddleOCR, and the GPT / Gemini / Claude models, are laid out side by side — field-level accuracy, latency, cost per 1,000 verifications, CPU-only figures flagged honestly. They leave with two impressions: *the screen had already done its thinking,* and *the team handed us buying data, not just a demo.*

## Inspiration & Anti-patterns

- **Lifted from USWDS:** the entire surface vocabulary and the federal-standard posture. The product's identity is *what we add to USWDS* (Treasury tone, verdict palette, beverage accents, the stacked comparison), not a from-scratch system. Deliberate, not a shortcut.
- **Lifted from the specialists themselves:** Jenny's paper desk checklist becomes the in-screen smart checklist; Dave's "something my mother could figure out" becomes one-primary-action-per-screen.
- **Rejected — a queue/list view to browse and pick from:** adds hunting and decisions for zero benefit. One button serves the next item. (Two-bucket triage is a *Phase-2* idea, gated on calibration data, not a v1 browse list.)
- **Rejected — side-by-side field comparison:** forces the eye too far apart on a wide monitor. Vertical stacking keeps both values in one short saccade.
- **Rejected — the engine auto-approving, auto-rejecting, or pre-selecting a disposition:** structurally forbidden. Advice and decision live in different visual registers and the human always commits the act.
- **Rejected — font-size / dimension checking:** can't be measured from a photo without a scale; the UI says so plainly rather than guessing (matches TTB's own COLAs Online disclaimer).
- **Rejected — alarming, dashboard-style density:** the screen is calm; only problems draw the eye.
