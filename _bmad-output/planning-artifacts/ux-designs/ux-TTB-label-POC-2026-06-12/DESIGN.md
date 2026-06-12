---
name: TTB Label Review
description: Speed-first review workspace for TTB Label Specialists adjudicating alcohol-label (COLA) applications. Built on USWDS, fully self-hosted; this DESIGN.md specifies the Treasury-toned brand-layer delta plus the domain tokens (verdict states, beverage accents) on top of USWDS defaults.
status: final
created: 2026-06-12
updated: 2026-06-12
colors:
  # Treasury/TTB brand-layer overrides on top of USWDS theme tokens. All
  # unlisted roles (base, ink, gray ramp, disabled, link) inherit USWDS defaults.
  primary: '#112E51'            # Treasury navy — primary actions, header, active nav
  primary-dark: '#0B1D35'       # hover/pressed on primary
  primary-light: '#205493'      # USWDS-aligned mid blue — links, focus accents
  primary-foreground: '#FFFFFF'
  secondary: '#2E5B46'          # civic green — secondary accent, "ready"/throughput cues
  secondary-foreground: '#FFFFFF'
  base: '#F0F0F0'               # USWDS base-lightest — app canvas
  surface: '#FFFFFF'            # cards, panels
  ink: '#1B1B1B'                # USWDS ink — body text
  ink-muted: '#5C5C5C'          # secondary text, muted (pre-checked) checklist items
  border: '#DCDEE0'             # USWDS gray-cool-10 — quiet card borders
  # --- Verdict palette (engine advice). ALWAYS paired with icon + word. ---
  # Foregrounds darkened from the USWDS state hues to clear WCAG AA (4.5:1) on
  # their own light tints — these are small UI text, and downstream code mirrors
  # these values. Contrast table in the Colors section.
  pass: '#216E29'               # dark green — PASS text/icon/bar (AA on pass-bg)
  pass-bg: '#ECF3EC'            # success-lighter tint
  review: '#7A5900'             # dark amber/gold — REVIEW (soft/normalized + flag-only)
  review-bg: '#FAF3D1'          # warning-lighter tint
  fail: '#B50909'               # red — FAIL (AA on fail-bg)
  fail-bg: '#F4E3DB'            # error-lighter tint
  # --- Beverage-type accents (banner identity). Word always present; color reinforces. ---
  spirits: '#7A4D00'            # amber/brown — DISTILLED SPIRITS
  wine: '#6B1F3A'               # burgundy — WINE
  beer: '#B8860B'               # gold — BEER
typography:
  # USWDS default type system (Public Sans / source-sans). Sizes tuned UP for an
  # older, varied-vision userbase on large monitors. Mono used for OCR raw text
  # so character-level diffs align column-for-column.
  font-sans: 'Public Sans'      # USWDS default; self-hosted (no Google Fonts call)
  font-mono: 'Roboto Mono'      # USWDS mono token — OCR raw values, diff spans
  body:
    fontFamily: 'Public Sans'
    fontSize: 16px              # floor; never the smallest USWDS step for primary content
    lineHeight: '1.5'
  comparison-value:
    fontFamily: 'Public Sans'
    fontSize: 19px             # application/OCR values — the thing the eye reads most
    fontWeight: '400'
    lineHeight: '1.4'
  ocr-raw:
    fontFamily: 'Roboto Mono'
    fontSize: 17px
    lineHeight: '1.45'
  banner:
    fontFamily: 'Public Sans'
    fontSize: 28px             # beverage-type word
    fontWeight: '700'
    letterSpacing: 0.02em
  display:
    fontFamily: 'Public Sans'
    fontSize: 22px             # screen titles, empty-state headlines
    fontWeight: '700'
rounded:
  # USWDS-restrained. Federal tools read squared, not consumer-soft.
  sm: 2px                       # inputs, tags
  md: 4px                       # cards, buttons (USWDS default radius-md)
  lg: 8px                       # modals, image panel
  pill: 999px                   # status chips only
spacing:
  # USWDS 8px-based units inherited as-is (units-1=8 … units-2=16, units-3=24,
  # units-4=32, units-5=40, units-6=48). No overrides; layout uses the USWDS grid.
  unit: 8px
components:
  button-primary:               # Next Submission, Approve
    background: '{colors.primary}'
    foreground: '{colors.primary-foreground}'
    radius: '{rounded.md}'
    minHeight: 48px
  button-disposition-correction: # Needs Correction (USWDS outline/secondary)
    background: '{colors.surface}'
    foreground: '{colors.primary}'
    border: '2px solid {colors.primary}'
    radius: '{rounded.md}'
    minHeight: 48px
  button-disposition-reject:    # Reject (USWDS secondary/destructive register)
    background: '{colors.surface}'
    foreground: '{colors.fail}'
    border: '2px solid {colors.fail}'
    radius: '{rounded.md}'
    minHeight: 48px
  verdict-tag-pass:
    background: '{colors.pass-bg}'
    foreground: '{colors.pass}'
    radius: '{rounded.pill}'
  verdict-tag-review:
    background: '{colors.review-bg}'
    foreground: '{colors.review}'
    radius: '{rounded.pill}'
  verdict-tag-fail:
    background: '{colors.fail-bg}'
    foreground: '{colors.fail}'
    radius: '{rounded.pill}'
  field-card-match:             # quiet: thin neutral border, no fill
    background: '{colors.surface}'
    border: '1px solid {colors.border}'
    radius: '{rounded.md}'
  field-card-mismatch:          # loud: thick left bar + error tint
    background: '{colors.fail-bg}'
    borderLeft: '6px solid {colors.fail}'
    radius: '{rounded.md}'
  field-card-soft:              # normalized/case-only diff: amber, not red
    background: '{colors.review-bg}'
    borderLeft: '6px solid {colors.review}'
    radius: '{rounded.md}'
  beverage-banner-spirits:
    background: '{colors.spirits}'
    foreground: '#FFFFFF'
  beverage-banner-wine:
    background: '{colors.wine}'
    foreground: '#FFFFFF'
  beverage-banner-beer:
    background: '{colors.beer}'
    foreground: '#1B1B1B'
---

# DESIGN.md — TTB Label Review

> Visual identity spine. Built on **USWDS** (U.S. Web Design System), fully self-hosted. This file specifies only the **Treasury-toned brand-layer delta** plus the **domain tokens** (verdict states, beverage accents, comparison cards) that USWDS doesn't ship. Everything not listed inherits USWDS defaults. Spine wins on conflict with any mock or import.

## Brand & Style

TTB Label Review is the daily workspace of a federal Label Specialist adjudicating alcohol-label applications. The brand premise is a single sentence: **the screen has already done its thinking by the time the specialist sits down.** Speed is the trust mechanism (a prior automation attempt died because it took 30–40 seconds; the bar here is ~5). So the visual language is **calm, authoritative, and quiet by default** — clean matches recede, only problems draw the eye. This is the opposite of a dashboard that shouts; it is a desk that is already tidy.

The identity inherits **USWDS** wholesale — the federal design system, with its Section 508 / WCAG AA baseline — and shifts only the brand layer into a **Treasury/TTB register**: a deep Treasury navy primary and a civic green secondary, replacing USWDS's default blue. On top of USWDS we add two domain vocabularies the system doesn't ship: a **three-state verdict palette** (PASS / REVIEW / FAIL) and **beverage-type accents** (spirits / wine / beer). USWDS components — Header, Button, Alert, Tag, Step Indicator, Accordion, Modal, Table, Form controls — are used per documented markup, not reimplemented; customizing them beyond this brand layer is against the discipline.

All assets (CSS, JS, fonts, icon sprites) are **vendored and served from the app** — no CDN, no outbound request — to satisfy the firewall constraint.

## Colors

The palette is **USWDS defaults + a Treasury brand layer + two domain vocabularies.**

- **Treasury Navy (`#112E51`, dark `#0B1D35`)** — the primary. Header bar, primary buttons (Next Submission, Approve), active nav, focus on key actions. Replaces USWDS default `primary`.
- **Civic Green (`#2E5B46`)** — the secondary. "Ready" / throughput cues, the stats strip, the secondary-positive register. Used sparingly; never competes with the verdict greens.
- **Verdict palette — advisory, never decorative.** `pass #216E29` ✓ · `review #7A5900` ⚠ · `fail #B50909` ✕, each over its lighter tint. This palette appears **only** on engine verdicts (Tags, the summary Alert, field-card states). It is *not* reused for chrome, buttons, or links. Every use is paired with an icon **and** a word — color never carries meaning alone. Foregrounds are the darkened (AA-clearing) hues; the same value serves the 6px field-card left bar (a graphic, only needs 3:1).
- **Beverage accents — identity, not status.** `spirits #7A4D00` (amber/brown) · `wine #6B1F3A` (burgundy) · `beer #B8860B` (gold). Used **only** on the full-width beverage-type banner. The type *word* ("DISTILLED SPIRITS") is always present; the color reinforces it for fast recognition, never replaces it.
- **Everything else** (base canvas, ink, gray ramp, link, disabled, input) inherits USWDS defaults.

Note: `beer` gold (`#B8860B`) and `review` amber (`#7A5900`) are deliberately related hues but never co-occur in the same region (one is a top banner, the other is inline verdict chips), so they don't collide. Avoid: gradients, chromatic flourishes, a fourth brand color, using verdict colors for anything advisory-adjacent.

**Contrast (WCAG 2.x AA) — load-bearing combinations.** USWDS warrants its own defaults; these are the domain combos this spine introduces, verified explicitly. Downstream must hold these ratios.

| Combination | Use | Ratio | Target | Status |
|---|---|---|---|---|
| `pass #216E29` on `pass-bg #ECF3EC` | PASS text/chip | ~5.0:1 | 4.5:1 | ✅ |
| `review #7A5900` on `review-bg #FAF3D1` | REVIEW text/chip | ~5.6:1 | 4.5:1 | ✅ |
| `fail #B50909` on `fail-bg #F4E3DB` | FAIL text/chip | ~5.6:1 | 4.5:1 | ✅ |
| `primary-foreground #FFF` on `primary #112E51` | primary button | ~13.7:1 | 4.5:1 | ✅ |
| `#FFF` on `spirits #7A4D00` | spirits banner (28px/700) | ~7.3:1 | 3:1 | ✅ |
| `#FFF` on `wine #6B1F3A` | wine banner (28px/700) | ~11.2:1 | 3:1 | ✅ |
| `ink #1B1B1B` on `beer #B8860B` | beer banner (28px/700, dark ink) | ~5.3:1 | 3:1 | ✅ |
| verdict fg as 6px left bar on its tint | field-card bar (graphic) | ≥3:1 | 3:1 | ✅ |

Rule of thumb for any new combination: verdict/status **text** must clear 4.5:1; a status used only as a bar/icon/banner-on-large-text must clear 3:1. The beer banner uses **dark ink** (~5.3:1); white on beer gold would fail at 3.25:1, so it must stay dark ink. Never set verdict foregrounds on pure white — use the tints.

## Typography

USWDS type system (**Public Sans** body, **Roboto Mono** for raw OCR), self-hosted — **sizes tuned up** because half the userbase is 50+ on large monitors and the cost of a misread comparison value is a needless correction cycle.

- **Body ≥ 16px** — never the smallest USWDS step for primary content.
- **Comparison values 19px** — the application value and the OCR value the specialist reads most; bumped above body so the eye lands cleanly.
- **OCR raw text in Roboto Mono (17px)** — monospace so character-level diff spans line up column-for-column between the "required/application" and "on-label" strings (critical for the Government Warning exact-wording check).
- **Beverage banner word 28px/700** — first thing the eye hits on load.
- **Display 22px/700** — screen titles and empty-state headlines.

The serif/display flourish has no place here; this is a tool, and plain federal sans is the entire voice.

## Layout & Spacing

USWDS 8px grid inherited as-is (8 / 16 / 24 / 32 / 40 / 48). **Designed for large monitors** — min 24", typical 27" or dual-24 — so width is used, not crammed. The Review Workspace is a deliberate **two-column** layout: left = evidence (label image + enhance controls), right = comparison + checklist, so "what's claimed" and "what's printed" are on screen simultaneously and the specialist never toggles between them. The Queue screen is the inverse — generous whitespace around a single large button, because its job is *one obvious action.* This is not a responsive/mobile product; the desktop workstation is the only surface (see EXPERIENCE.md Foundation).

## Elevation & Depth

Inherited from USWDS — minimal. Shadow is not a hierarchy device. Hierarchy is carried by **the verdict palette and the mismatch left-bar**, not by elevation. The one intentional depth cue: the bottom **Disposition action bar** sits on a subtle top-shadow so it reads as a persistent, separate "this is where you commit the decision" zone, distinct from the advisory content above it (reinforcing the P4 verdict-vs-disposition separation).

## Shapes

USWDS-restrained corners: `2px` inputs/tags, `4px` cards and buttons, `8px` modals and the image panel. **Pill (`999px`) only on status chips** (the PASS/REVIEW/FAIL Tags). Squared corners read "federal tool," not "consumer app." The thick **6px left border** on a mismatch field card is the single loudest shape in the system — reserved for genuine FAIL/mismatch; soft/normalized diffs use the same bar in amber.

## Components

Visual reference (these tokens applied): [mockups/review-workspace.html](mockups/review-workspace.html) (verdict palette, field-card states, banner, action bar), [mockups/queue.html](mockups/queue.html), [mockups/benchmark-report.html](mockups/benchmark-report.html). **Spine wins on conflict.**

Used **as-is from USWDS** (don't customize beyond the brand layer): Header, Side Navigation, Tag, Alert, Step Indicator (the chevron), Accordion (the "Why?" expanders), Modal, Table, Text Input, Radio/Button-group, Search.

Brand-layer / domain components defined here:

- **Button — primary** (`Next Submission`, `Approve`): `{colors.primary}` fill, white text, `{rounded.md}`, **≥48px** tall (big target for low-tech-comfort, mouse-only users).
- **Disposition buttons** (`Needs Correction`, `Reject`): outline register on `{colors.surface}` — Correction outlined in navy, Reject outlined in `{colors.fail}`. Outline (not filled) so they don't compete with the single filled primary; full saturation reserved for Approve as the affirmative default path.
- **Verdict Tag** (pass / review / fail): pill chip, tinted bg + saturated fg + icon + word. The atomic unit of "engine advice."
- **Field comparison card** — three states: **match** (quiet: 1px border, no fill, green ✓ chip), **mismatch** (6px `{colors.fail}` left bar + `{colors.fail-bg}` tint, character diff on the differing span), **soft** (6px `{colors.review}` left bar + `{colors.review-bg}` tint, plain-language "capitalization differs; text matches" note). Behavioral spec in EXPERIENCE.md.
- **Beverage-type banner** — full-width, accent fill per type, large word + icon. Spirits/wine on dark fill with white text; beer gold on dark ink text (contrast).
- **Suggested-verdict Alert** — USWDS Alert in the matching verdict tint at top of Review, labeled "Suggested:" — the advisory roll-up, visually in the muted Alert register, never in the saturated Button register. The Alert always carries the verdict **icon + word**, not tint alone.
- **Government Warning card** — visually a specialization of the field-comparison card: uses `field-card-mismatch` / `field-card-soft` tokens in a "regulation-vs-label" layout, with the on-label/required strings in `ocr-raw` mono for character-aligned diffing. No separate token set.
- **Benchmark comparison table** — USWDS Table as-is; verdict palette is kept **off** this surface (chrome = navy/civic-green only), figures in `ocr-raw` mono for column alignment.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Inherit USWDS defaults for everything outside the brand + domain layers | Reimplement or restyle USWDS components beyond these tokens |
| Use the verdict palette **only** for engine advice, always with icon + word | Use verdict colors for chrome, buttons, or links — or color alone |
| Reserve beverage accents for the type banner; keep the *word* present | Color-code beverage type without the word (fails colorblind + Dave) |
| Keep matches quiet; spend visual weight on mismatches only | Highlight everything — a screen that shouts hides the real problem |
| Size comparison values up (19px) and OCR raw in mono | Use the smallest USWDS type step for the values specialists read |
| Treasury navy primary, civic green secondary, squared corners | Add a fourth brand color, gradients, or consumer-soft rounding |
| Full-saturation fill on Approve only; outline the other dispositions | Pre-select or full-fill all three dispositions (breaks recommend-don't-decide) |
