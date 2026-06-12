# Accessibility Review — TTB Label Review UX Spines

Reviewer: Accessibility auditor (Section 508 / WCAG 2.x AA)
Date: 2026-06-12
Scope: `DESIGN.md` + `EXPERIENCE.md` + `.decision-log.md` (spine pair, critique only — no edits made)
Userbase context: federal Label Specialists, ~half 50+, varied vision, mixed/low tech comfort, desktop-only.

## Overall verdict

The spine is unusually strong on accessibility intent — the color+icon+word rule, sized-up type, ≥48px targets, no-timeout/no-work-loss, calm-by-default, and the keyboard power path are real, specified commitments, and the USWDS foundation buys a genuine 508/WCAG AA baseline for inherited components. But the spines lean on "USWDS holds the ratios" as a blanket claim that is provably false for two of the domain-specific color tokens the team *added on top* of USWDS: the **REVIEW amber verdict text (#B8860B) fails AA at 2.91:1**, and the **PASS green verdict text (#2E8540) fails normal-text AA at 4.09:1** on its tint — these are load-bearing engine-advice colors, not chrome. The other systemic gaps are under-specification rather than wrong decisions: keyboard shortcut safety (A/C/R firing destructively), focus management on modals, aria-live for the dynamic comparison results, and accessible error messaging on the required Notes field are all asserted at a high level but never specified, so an implementer can satisfy the spine and still ship an inaccessible app.

## Findings grouped by severity

### Critical

**[critical] REVIEW verdict text fails AA contrast (DESIGN.md colors.review `#B8860B` on review-bg `#FAF3D1`; verdict-tag-review, field-card-soft note text, Suggested Alert)** — Computed ratio **2.91:1**, below the 4.5:1 normal-text floor and even below the 3:1 large-text/graphic floor. This is one of the three load-bearing engine-advice states, used on the soft/normalized "check" cards and the Suggested-verdict Alert — exactly the ambiguous cases where an older low-vision specialist most needs to read the plain-language note clearly. The spine's own claim "Treasury brand layer verified to hold ratios" (EXPERIENCE.md Accessibility Floor; DESIGN.md is silent on actual numbers) is contradicted here. — *Fix:* Darken the amber foreground to ~`#8A6100` or darker (USWDS `warning-darker`/`gold-warm-vivid-80` region clears 4.5:1 on this tint), OR keep `#B8860B` only as the left-bar/icon graphic and render the REVIEW word/note text in `ink #1B1B1B`. Re-verify ≥4.5:1.

**[critical] PASS verdict text fails normal-text AA on its tint (DESIGN.md colors.pass `#2E8540` on pass-bg `#ECF3EC`; verdict-tag-pass, "match" chip text)** — Computed ratio **4.09:1**, under the 4.5:1 normal-text floor. The PASS Tag/chip text ("PASS", "match") is small UI text, not large text, so 4.5:1 applies. Pervasive (every clean field card, the most-rendered state). — *Fix:* Use a darker green for text/icon (e.g. USWDS `green-cool-60` / ~`#1E6E33` or darker) to reach ≥4.5:1 on `#ECF3EC`, or darken the foreground while keeping the tint. The green-on-white form of the chip (4.62:1) passes, so the failure is specifically text-on-tint — verify whichever pairing actually ships.

### High

**[high] Blanket "USWDS holds AA" claim masks unverified custom tokens (EXPERIENCE.md Accessibility Floor; DESIGN.md Colors / frontmatter)** — The verdict palette, beverage accents, and comparison-card tints are *additions the team invented*, not USWDS tokens, so USWDS's audited ratios do not cover them. Two already fail (above). The spine asserts verification that did not happen. — *Fix:* Add an explicit contrast table to DESIGN.md with computed ratios for every custom fg/bg pairing and the target it must clear (4.5:1 text, 3:1 graphic), and make "passes its stated target" a token-acceptance gate before build.

**[high] A / C / R keyboard shortcuts can fire a disposition destructively without a focus-safe guard (EXPERIENCE.md Interaction Primitives; Component Patterns → Notes field)** — `A`/`C`/`R` map to Approve/Needs-Correction/Reject — irreversible recorded federal acts. The spine says each "routes through its confirm/notes gate," but single un-modified letter keys are dangerous: (a) they will fire while the user is typing in the **Notes** field or Help **Search** unless explicitly suppressed when focus is in a text input — a specialist typing a correction reason could trigger `R`; (b) single-letter keys collide with screen-reader pass-through/quick-nav modes (JAWS/NVET browse mode consumes single letters as element-navigation, so the SR user may be unable to invoke them *or* may invoke them unexpectedly). — *Fix:* Spec that all letter shortcuts are inert when focus is in any text input/textarea/contenteditable or when a modal owns focus; require the confirm gate to be a real focus-trapped dialog (not an inline auto-submit); document that SR users must use the on-screen buttons and ensure those buttons are the canonical path. Consider requiring a modifier or making A/C/R only *move focus to* the button rather than activating it.

**[high] aria-live announcement of dynamic comparison/verdict results is not specified (EXPERIENCE.md Accessibility Floor, Component Patterns → Field card / Checklist)** — On the ~5s instant render, the SR user gets the load announcement (good — "Distilled Spirits, suggested verdict REVIEW, 2 of 6 checks need review"), but the spine never says *how* that fires (focus move? aria-live region? page-title?), and never specifies live-region behavior for the things that change *after* load: ticking a checklist item ("5 of 6 done"), clicking Enhance (new image appears beside original), a field card sorting to top, or the LLM-degraded notice. Silent DOM changes are invisible to SR users. — *Fix:* Specify a polite `aria-live` region for the "N of M done" counter and the suggested-verdict roll-up; specify that the on-load summary is announced via a focus move to an `<h1>`/role=status or an assertive live region; specify that the Enhance toggle and the "LLM check unavailable" notice announce; ensure the mono character-diff spans have a text equivalent (see below).

**[high] Character-level diff relies on visual span styling with no specified non-visual / non-color equivalent (DESIGN.md Typography/Shapes "character diff on the differing span"; EXPERIENCE.md Gov. Warning + Field card)** — The Government Warning exact-wording check — the substantive defect in Flow 2 — is conveyed by lighting up "exactly where the label reworded" the text. If that highlight is color/background alone on a mono span, it (a) is invisible to a screen reader reading linearly (the SR user hears two strings with no indication of *which characters* differ), and (b) may not survive Windows High Contrast Mode, and (c) a thin/low-contrast highlight is hard for low-vision users. The spine warns against "thin underline alone" nowhere — it just says "diff span." — *Fix:* Pair the visual diff with a text equivalent the SR reads (e.g. an off-screen "Required text differs at: 'GOVERNMENT WARNING' vs 'Government Warning'"), use a perceptible highlight (bold + ≥3:1 background change + an icon/marker, not color alone), and verify it persists in forced-colors mode.

**[high] Notes field validation / error messaging accessibility unspecified (EXPERIENCE.md Notes field, State Patterns "soft-gate")** — Notes is *required* for Needs Correction / Reject and "soft-gate validation blocks the record until filled." Nothing specifies: programmatic label association, that the error is announced (`aria-describedby` + `role=alert`/live region, not color-only red border), that focus moves to the field on block, or that the message is plain-language per the Voice rules. A red border alone fails color-alone; a visually-only error fails SR users. — *Fix:* Spec: `<label>` associated to the textarea; on block, set `aria-invalid`, move focus to the field, and announce a plain-language error ("Add a short reason for the maker before sending this back.") via an associated live region; never signal the required/error state by color alone.

### Medium

**[medium] Beer-gold banner color-onto-white-text trap is one token away from failing (DESIGN.md beverage-banner-beer: ink `#1B1B1B` on beer `#B8860B`)** — The spec correctly uses dark ink on beer gold (5.29:1, passes) while spirits/wine use white — an intentional, correct contrast call. But the asymmetry is fragile: white on `#B8860B` is **3.25:1** (fails normal text), so any future "make banners consistent, all white text" change silently breaks AA on beer only. — *Fix:* Add an explicit DESIGN.md note that beer banner text MUST be dark ink (with the 3.25:1 white-on-gold figure recorded as the reason), so the constraint survives later edits.

**[medium] Tab order asserted but modal/Help focus management not fully specified (EXPERIENCE.md Accessibility Floor; State Patterns soft-gate Modal; IA Help panel)** — Tab order = reading order is stated, and `Esc` closes the topmost layer (good). But the spine never specifies focus *trapping* inside the soft-gate Modal and Help panel, where focus goes when they open, or where focus *returns* on close. Without a return target, a keyboard/SR user is dumped to the top of the page after closing the soft-gate, losing their place mid-disposition. — *Fix:* Spec USWDS Modal focus-trap usage explicitly; on open, move focus to the dialog (heading or first control); on close/Esc, return focus to the triggering control (the Approve button / the `[?]`).

**[medium] Suggested-verdict Alert and amber states risk color-alone in the muted register (DESIGN.md Suggested-verdict Alert "in the matching verdict tint")** — The rule "icon + word + color" is stated and mostly honored, but the Suggested Alert is described primarily by *tint*; confirm the icon and the word ("Suggested: REVIEW") are both present in the Alert itself, and that the chevron Step Indicator's "current is high-contrast; upcoming muted; done ✓" distinction does not rely on contrast/color alone for the *current vs upcoming* difference (done carries ✓, but current-vs-upcoming may be color/weight only). — *Fix:* Confirm Alert renders icon + literal word; give the chevron's current step a non-color affordance (e.g. "current"/"step 3 of 5" text or a shape marker), not just higher contrast.

**[medium] "Why?" Accordion and chevron scroll-to are click-described; verify keyboard + SR parity (EXPERIENCE.md Component Patterns)** — Clicking a checklist item or chevron step "scrolls to" its field card. Scroll-on-click must also move *focus* (or at least programmatic focus/`tabindex`) so keyboard and SR users land on the target, not just sighted mouse users — otherwise the keyboard user scrolls the viewport but their focus is left behind. — *Fix:* Spec that activating a checklist item / chevron step moves focus to the target field card (focusable container), not just visual scroll.

### Low

**[low] ink-muted on canvas for pre-checked checklist items is close to the floor (DESIGN.md ink-muted `#5C5C5C`)** — Muted pre-ticked items are `#5C5C5C`; on white that's 6.69:1 (fine), but on the `#F0F0F0` canvas it's **5.87:1** — still passing, but "muted" text for a 50+ low-vision audience is worth not pushing further. Disabled controls (empty-queue Next Submission) are exempt from contrast minimums but should still be legible. — *Fix:* Keep muted text ≥ the body floor on whatever background it actually sits on; don't let "muted" drift lighter in implementation.

**[low] Card "match" state distinguished partly by 1px border at 1.35:1 (DESIGN.md field-card-match border `#DCDEE0` on surface)** — The quiet match card's 1px neutral border is 1.35:1 vs surface — far below 3:1. This is acceptable *only because* the match state is also carried by the green ✓ "match" chip + word (the real signal), so the border is decorative, not the sole indicator. Flagged so it stays that way. — *Fix:* None required as long as the ✓ chip + "match" word remain the load-bearing indicator and the border is never the only thing distinguishing a state.

**[low] Letter-spacing on the 28px/700 banner is minor but verify with real type (DESIGN.md banner letterSpacing 0.02em)** — Cosmetic; no AA issue. Noted only because tracking on heavy weights can slightly reduce legibility for some dyslexic readers; 0.02em is mild and fine.

## Contrast table

Targets: normal text ≥ 4.5:1 · large text (≥18.66px bold or ≥24px) ≥ 3:1 · UI components/graphics ≥ 3:1.

| Combination | Tokens | Ratio | Target | Verdict |
|---|---|---|---|---|
| PASS verdict text on tint | `#2E8540` on `#ECF3EC` | **4.09:1** | 4.5 (small UI text) | **FAIL** |
| REVIEW verdict text on tint | `#B8860B` on `#FAF3D1` | **2.91:1** | 4.5 (and even <3:1) | **FAIL** |
| FAIL verdict text on tint | `#B50909` on `#F4E3DB` | 5.60:1 | 4.5 | PASS |
| Banner: white on spirits | `#FFFFFF` on `#7A4D00` | 7.27:1 | 3 (28px/700 = large) | PASS |
| Banner: white on wine | `#FFFFFF` on `#6B1F3A` | 11.16:1 | 3 | PASS |
| Banner: ink on beer gold | `#1B1B1B` on `#B8860B` | 5.29:1 | 3 | PASS |
| Banner: WHITE on beer gold *(if ever used)* | `#FFFFFF` on `#B8860B` | 3.25:1 | 4.5 (small) / 3 (large) | FAIL small / borderline-PASS large — do not use |
| Primary button: white on navy | `#FFFFFF` on `#112E51` | 13.69:1 | 4.5 | PASS |
| Outline Correction: navy text on white | `#112E51` on `#FFFFFF` | 13.69:1 | 4.5 | PASS |
| Outline Reject: fail-red text on white | `#B50909` on `#FFFFFF` | 6.98:1 | 4.5 | PASS |
| Body ink on canvas | `#1B1B1B` on `#F0F0F0` | 15.11:1 | 4.5 | PASS |
| Body ink on surface | `#1B1B1B` on `#FFFFFF` | 17.22:1 | 4.5 | PASS |
| ink-muted on surface | `#5C5C5C` on `#FFFFFF` | 6.69:1 | 4.5 | PASS |
| ink-muted on canvas | `#5C5C5C` on `#F0F0F0` | 5.87:1 | 4.5 | PASS |
| REVIEW fg on white *(if reused off-tint)* | `#B8860B` on `#FFFFFF` | 3.25:1 | 4.5 | FAIL — keep off white |
| FAIL left bar vs fail-bg (graphic) | `#B50909` on `#F4E3DB` | 5.60:1 | 3 | PASS |
| REVIEW left bar vs review-bg (graphic) | `#B8860B` on `#FAF3D1` | 2.91:1 | 3 | **FAIL** (bar not distinct enough from its own tint) |
| Match card border vs surface (graphic) | `#DCDEE0` on `#FFFFFF` | 1.35:1 | 3 | FAIL as indicator — OK only as decorative (✓ chip carries state) |
| primary-light link on white | `#205493` on `#FFFFFF` | 7.63:1 | 4.5 | PASS |
| secondary civic green on white | `#2E5B46` on `#FFFFFF` | 7.77:1 | 4.5 | PASS |

Note on the REVIEW left-bar row: at 2.91:1 the amber 6px bar barely differs from its own `#FAF3D1` tint, so the "loud vs quiet" left-bar signal is weak for the soft state — the bar is meant to be a perceivable graphic boundary and misses the 3:1 graphic floor. Darkening the amber token fixes both the text and the bar at once.

---
Report file: `c:\alcorn\Treasury\TTB-label-POC\_bmad-output\planning-artifacts\ux-designs\ux-TTB-label-POC-2026-06-12\review-accessibility.md`
