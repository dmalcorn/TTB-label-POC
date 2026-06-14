# Story 4.9: In-UI Help panel

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want a one-click searchable help panel,
so that I can understand the screen and the PASS/REVIEW/FAIL vocabulary without leaving my work.

## Acceptance Criteria

(Verbatim intent from `epics.md` Story 4.9 — *(FR-8, UX-DR-4)*; the cross-cutting
accessibility/voice floors UX-DR-15/16/18 apply.)

1. **AC1 — one-click `[?]` opens a right-anchored dialog from every screen.** Given the
   `[?]` control already present in the utility header (`templates/base.html`) on every
   post-auth screen, when it is activated (mouse click — the `?` keyboard shortcut is
   Story 4.10's global concern, but the panel must not break it), then a **right-anchored
   slide-over** appears as `role="dialog"` (with an accessible name "Help") over a
   **scrimmed backdrop**, focus moves into the dialog, focus is **trapped** while it is
   open, **Esc closes** it, and closing **returns focus to the `[?]` control**.

2. **AC2 — the panel shows the five mockup regions, in order, with exact copy.** When Help
   is open, the panel body shows — matching `mockups/help-panel.html` layout, USWDS
   component structure, and **exact visible copy**:
   1. a prominent **search box** ("Ask a question…") with the **on-server note**
      ("Everything here is on this server — no internet, nothing leaves the workstation.");
   2. the **browsable KB list** (the four "Common questions" Q+A items) so a
      low-search-comfort user can scan, not type;
   3. the **PASS / REVIEW / FAIL verdict explainer** (each row **icon + word + colour**,
      verdict palette per DESIGN.md), preceded by the **verdict-vs-disposition reminder**
      ("These are the engine's **suggestions**. The disposition … is always your decision.")
      and followed by the "Color is never the whole story…" note;
   4. the **keyboard-shortcuts list** (N; A/C/R; ←/→; ? / Esc);
   5. the **calm no-results state** copy ("No matches yet for that." + try-fewer-words
      guidance + example terms), consistent with the empty-queue voice (never an error).

3. **AC3 — search filters the local KB client-side; no egress; honest no-results.** When
   the user types a query and searches, the KB list filters to matching questions/answers
   **entirely on the server's own assets** (same-origin static JS — **no network call, no
   CDN, no telemetry**; the on-server promise is literally true); a query with no match
   shows the **no-results calm state** while the browsable KB stays available to scan; an
   empty/cleared query restores the full list. The server render is correct **without**
   JavaScript (the full KB + explainer + shortcuts are all present in the HTML); JS only
   **adds** the live filter (progressive enhancement, UX-DR-16 two-track).

4. **AC4 — tokens resolve to the spine; self-hosted; colour never alone.** All colours/
   fonts/spacing resolve to `static/css/brand.css` `--brand-*` / `--verdict-*` tokens
   (DESIGN.md), **not** the mockup's inline hex (e.g. PASS green is `#216E29`, REVIEW
   `#7A5900`, FAIL `#B50909` — the spine values, not the mockup's `#2E8540`/`#B8860B`);
   every status carries **icon + word + colour** (never colour alone); body ≥16px, targets
   ≥48px; all assets same-origin (no Google Fonts, no CDN — NFR-2). Mockup-only scaffolding
   (the browser device frame, the dimmed-Review backdrop artwork, the "No-results state"
   frame-label caption) is **not** reproduced.

5. **AC5 — mockup fidelity, side-by-side check.** The panel **matches**
   `mockups/help-panel.html` in layout, USWDS component structure, all depicted states
   (open dialog + no-results), and exact copy; a documented side-by-side comparison against
   the mockup file (state for state) is in the Definition of Done.

## Tasks / Subtasks

> **Test-first throughout (red → green → refactor).** This is a **template + CSS + JS**
> story — there is **no new Python route, no DB read/write, no schema change**. The Help
> panel is **static post-auth chrome** rendered in `templates/base.html`, so it ships on
> *every* screen that extends `base.html` (queue, review) with zero per-route work. Search
> is **client-side filtering of the static KB** (`static/js/help.js`) — the honest reading
> of "everything here is on this server." Do **not** add a search endpoint or a KB table;
> that would be over-engineering and would weaken the zero-egress claim.

- [ ] **Task 1 — Help panel markup in `templates/base.html` (AC1, AC2, AC4, AC5).** (AC: 1, 2, 4, 5)
  - [ ] In `templates/base.html`, **inside the existing `{% block header %}`** (so it is
        post-auth chrome and inherits the token gate — `access.html` already empties this
        block pre-auth, keeping Help gated), wire the existing
        `<button class="app-header__help" aria-label="Help">?</button>` to the panel:
        add `aria-haspopup="dialog"`, `aria-controls="help-panel"`, `aria-expanded="false"`,
        and `data-help-open` so `help.js` can find it. Keep `type="button"` and the `?`
        glyph + `aria-label="Help"`.
  - [ ] Add the slide-over panel as a **new `templates/_help_panel.html` partial** included
        once in `base.html` (right after the header, still inside the `header` block so it
        is suppressed pre-auth). Structure (matching `mockups/help-panel.html`):
    - a **backdrop/scrim** element (`<div class="help-scrim" data-help-scrim hidden aria-hidden="true">`),
    - an `<aside id="help-panel" class="help-panel" role="dialog" aria-labelledby="help-panel-title" aria-modal="true" hidden>`
      with:
      - `.help-panel__head` → `<h2 id="help-panel-title">Help</h2>` + the sub line "Search
        the local knowledge base, or browse below." + a **close button**
        (`class="help-panel__close" aria-label="Close help" data-help-close` title `Close (Esc)`, ≥48px target),
      - `.help-panel__body` containing, **in order**, the five regions of AC2 (search,
        KB list, verdict explainer, keyboard shortcuts, no-results state).
  - [ ] **Search region**: `<label class="help-search__label" for="help-search">Ask a question</label>`,
        an `<input id="help-search" class="help-search__input" type="search" placeholder="Ask a question…" aria-label="Ask a question" autocomplete="off" data-help-search>`,
        a `Search` button (`type="button"`, decorative — filtering is live on input), and the
        on-server hint `<p class="help-search__hint">Everything here is on this server — no
        internet, nothing leaves the workstation.</p>`.
  - [ ] **KB list region**: `<section class="help-section"><h3>Common questions</h3>`, then a
        `<ul class="help-kb" data-help-kb>` of four `<li class="help-kb__item" data-help-kbitem>`,
        each `<p class="help-kb__q">…</p><p class="help-kb__a">…</p>`. Use the **exact four Q/A
        pairs** from the mockup (see References — Gov Warning wording / font size / capitalization
        difference / Needs Correction vs Rejected). The `&rsaquo;` chevron is decorative
        (`aria-hidden="true"`).
  - [ ] **Verdict explainer region**: `<section class="help-section"><h3>What PASS, REVIEW and
        FAIL mean</h3>`, the verdict-vs-disposition reminder paragraph (exact copy), then a
        `.help-verdicts` grid of three rows. Each row = a **chip** (`.help-vtag .help-vtag--pass|review|fail`)
        carrying `<span class="ic" aria-hidden="true">✓|⚠|✕</span>` + the WORD, plus the
        description text (exact copy). Close with the
        `<p class="help-note">Color is never the whole story…</p>` note.
  - [ ] **Keyboard-shortcuts region**: `<section class="help-section"><h3>Keyboard shortcuts
        (optional)</h3>` + a `<ul class="help-kbd">` of `<li>`s with `<kbd>` elements:
        `N` Next Submission; `A` `C` `R` Approve · Needs Correction · Reject; `←` `→` Move
        between label image faces; `?` Open Help · `Esc` Close this panel; then the
        "The mouse path does everything on its own…" hint.
  - [ ] **No-results region**: a `<div class="help-empty" data-help-empty hidden>` (hidden until
        a search yields zero matches) — round `?` ico (`aria-hidden`), `<h3>No matches yet for
        that.</h3>`, the guidance paragraph, and the "You could try" example list. Do **NOT**
        reproduce the mockup's "No-results state" `frame-label` caption (that is illustrative
        scaffolding — UI fidelity standard).
  - [ ] **Exclude mockup scaffolding**: no `.device`/`.browser-bar`/`.url`/`.backdrop`/
        `.bd-*`/`.scrim` artwork, no fabricated review-screen hint. The real Review screen IS
        the backdrop in the running app; the scrim is a functional dim layer only.

- [ ] **Task 2 — Help panel styles in `static/css/brand.css` (AC1, AC4, AC5).** (AC: 1, 4, 5)
  - [ ] Append a `Help panel (Story 4.9)` block. Reuse existing `--brand-*` / `--verdict-*`
        tokens and the established radius/spacing scale — **no new `:root` hex**, no inline
        `<style>`, no `@import`/CDN/font URL.
  - [ ] `.help-scrim`: fixed full-viewport dim (`background: rgba(11,29,53,.42)` expressed
        via the navy token where practical), below the panel; toggled by removing `hidden`.
  - [ ] `.help-panel`: fixed, anchored right (`top:0; right:0; bottom:0`), width ~520px
        (`max-width:100%` so it never overflows a narrow viewport), `--brand-surface`
        background, navy left border, drop shadow, `display:flex; flex-direction:column`;
        `[hidden]` fully hides it (no flex override of `hidden`).
  - [ ] `.help-panel__head` navy bar (`--brand-primary` bg, `--brand-primary-foreground`
        text), title 22px/700; `.help-panel__close` ≥48px target with a visible
        `:focus-visible` ring (`outline: 4px solid var(--brand-primary-light)` — mirror the
        existing `.app-header__help:focus-visible`).
  - [ ] `.help-panel__body` scrolls (`overflow:auto`); search input ≥48px min-height,
        font ≥16px; `.help-kb__item` left-accent border (`--brand-primary-light`); the
        `.help-vtag--pass|review|fail` chips use the matching `--verdict-*` + `--verdict-*-bg`
        token pair (pill radius, the chips are the ONE allowed pill use); `kbd` styled per the
        mockup using neutral tokens. Body text ≥16px; KB question ≥17px (older-eyes floor).
  - [ ] A `body.help-open` or panel-`[hidden]`-toggle approach is fine; keep it CSS-simple.

- [ ] **Task 3 — `static/js/help.js` progressive enhancement (AC1, AC3).** (AC: 1, 3)
  - [ ] New same-origin script (no build, no CDN), loaded from `base.html` so it is present
        on every post-auth screen. Mirror the IIFE / inert-when-absent / no-throw style of
        `static/js/review.js` and `static/js/disposition.js`. Header comment must state:
        same-origin, server render correct without it, NFR-2 zero-egress, contract: search is
        a **local DOM filter** — it makes **no network request**.
  - [ ] **Open**: clicking `[data-help-open]` removes `hidden` from the scrim + panel, sets
        the trigger's `aria-expanded="true"`, records `document.activeElement` as the return
        target, and moves focus to the panel's close button (or the dialog heading).
  - [ ] **Close** (Esc, the close button, or a click on the scrim): re-adds `hidden`, sets
        `aria-expanded="false"`, and **returns focus to the `[?]` trigger** (AC1). Esc only
        closes when the panel is open (don't swallow Esc otherwise).
  - [ ] **Focus trap**: while open, `Tab`/`Shift+Tab` cycle within the panel's focusable
        elements (mirror the `disposition.js` modal trap: compute first/last focusable, wrap).
  - [ ] **Search filter** (AC3): on `input` of `[data-help-search]`, lower-case the trimmed
        query and show/hide each `[data-help-kbitem]` by substring match against its
        question+answer text; when the query is non-empty AND **zero** items match, reveal
        `[data-help-empty]` and (optionally) hide the KB `<ul>`; an empty/cleared query
        restores all items and hides the empty state. **No `fetch`/`XMLHttpRequest`** anywhere
        in this file (the no-egress guard test asserts this).

- [ ] **Task 4 — Wire `help.js` into `base.html` (AC1, AC3).** (AC: 1, 3)
  - [ ] Add `<script src="/static/js/help.js"></script>` to `base.html`. It applies on every
        screen, so add it **after the USWDS script** in the body (NOT inside a per-page
        `{% block scripts %}`) — the panel is global chrome. Confirm `queue.html` and
        `review.html` (which both `{% extends "base.html" %}` and may define `scripts`) still
        load their own per-page scripts via `{{ super() }}`-safe blocks or by the global tag
        living outside the block. Simplest: place the global Help `<script>` in `base.html`
        outside `{% block scripts %}` so per-page blocks are untouched.

- [ ] **Task 5 — Tests (all ACs).** Write FIRST (red), then implement to green. New file
      `tests/test_help_panel.py` (render-level, via the existing TestClient pattern) +
      content guards over the JS/template. (AC: 1, 2, 3, 4, 5)
  - [ ] **Render presence (AC1/AC2)**: GET `/queue` (and `/review/{id}` for a seeded ready
        submission) returns 200 and the HTML contains: the `[?]` trigger wired with
        `aria-controls="help-panel"` + `aria-haspopup="dialog"`; `id="help-panel"` with
        `role="dialog"` + `aria-modal="true"` + an accessible name; the search input
        (`data-help-search`, placeholder "Ask a question…"); the on-server hint text; the four
        KB questions (assert each exact question string); the three verdict words PASS/REVIEW/
        FAIL each with its icon (✓/⚠/✕); the verdict-vs-disposition reminder phrase; the
        keyboard-shortcut tokens (N, A, C, R, ?, Esc); and the no-results copy "No matches yet
        for that.".
  - [ ] **Gated (AC1)**: with the token gate ENABLED and no cookie, GET `/queue` redirects to
        `/access` (the panel never leaks pre-auth); and `access.html` (the deny page) does
        **not** contain `id="help-panel"` (header block is empty pre-auth). Reuse the gate
        setup from `tests/test_token_gate.py` / `tests/test_queue.py`.
  - [ ] **Verdict palette = spine, not mockup (AC4)**: assert `static/css/brand.css` Help
        block references the `--verdict-pass/review/fail` tokens and does **not** introduce a
        new `#2e8540`/`#b8860b` literal in the Help section; assert no `@import`, no `http`/
        `https://` URL, no `cdn`/`googleapis`/`fonts.g` reference anywhere in the Help CSS
        block (NFR-2). (Read the file in the test and assert.)
  - [ ] **No-egress JS guard (AC3/NFR-2)**: read `static/js/help.js` and assert it contains
        **no** `fetch(`, `XMLHttpRequest`, `import(`, `https://`, `http://`, or `//cdn`
        substring — search is a pure local DOM filter. Also assert the file IS referenced by
        `base.html` (`/static/js/help.js`).
  - [ ] **Icon+word never colour-alone (AC4)**: assert each verdict chip in the rendered HTML
        carries both the icon char and the WORD adjacent (e.g. the rendered panel contains
        `✓` and `PASS` within the same chip element / line).
  - [ ] **No mockup scaffolding (AC5)**: assert the rendered HTML does **not** contain the
        device-frame / backdrop scaffolding class names (`browser-bar`, `bd-img`, `frame-label`).

- [ ] **Task 6 — DoD side-by-side mockup check (AC5).** In the Completion Notes, record a
      state-for-state comparison of the running panel against `mockups/help-panel.html`
      (open-dialog state + no-results state), noting every spine-token substitution and every
      excluded scaffolding element with its rationale.

## Dev Notes

### What this story is — and is NOT

- **IS**: static, server-rendered Help chrome in `base.html` (present on every post-auth
  screen) + spine-token CSS + one progressive-enhancement JS file that does **client-side**
  KB filtering and dialog focus management. Pure presentation.
- **IS NOT**: a Python route, a DB read/write, a schema change, a search index/endpoint, or
  anything touching the engine/pipeline. There is **no AR-5 read-path risk** here because no
  request handler changes — but the same discipline holds (the panel is static HTML).
- **Reuse, don't reinvent**: the `[?]` button (`templates/base.html:25`) and its
  `.app-header__help` + `:focus-visible` styles (`static/css/brand.css`) already exist — wire
  them, don't recreate. Mirror the **focus-trap + Esc + return-focus** pattern already proven
  in `static/js/disposition.js` (the confirm modal). Mirror the **IIFE / inert-when-absent /
  same-origin** shape of `review.js` + `disposition.js`.

### The honesty constraint (NFR-2 — non-negotiable)

The panel literally says *"Everything here is on this server — no internet, nothing leaves the
workstation."* That copy must be **true**: the KB is static HTML, and search is a **local DOM
filter** in `help.js` with **no `fetch`/XHR/CDN/external font**. A server search endpoint or a
remote font would make the on-screen promise a lie — reject either in review. This is the same
zero-egress posture proven by `docker run --network none` (AR-8) and the `tests/test_token_gate.py`
no-leak class.

### Accessibility floor (UX-DR-15 — applies even though this is "just help")

- `role="dialog"` + `aria-modal="true"` + `aria-labelledby` the title; `aria-haspopup="dialog"`
  + `aria-controls` + `aria-expanded` on the trigger.
- **Focus trap** while open; **Esc closes**; **focus returns to `[?]`** on close
  (EXPERIENCE.md Focus management line 147; AC1).
- **Colour never alone**: every verdict chip = icon **and** word **and** colour (UX-DR-7).
- Body ≥16px, KB question ≥17px, targets ≥48px (close button, search input). `:focus-visible`
  ring on the close button and search input.
- The `[?]` shortcut (`?`) and global `Esc` layering are **Story 4.10's** concern — do not
  implement the global single-letter shortcut handler here, but do not block it either (the
  panel's own Esc handler is scoped to "when open").

### Verdict-vs-disposition separation (contract #4 / AR-3 #4)

The verdict explainer must keep the engine register (PASS/REVIEW/FAIL = *suggestions*) and the
human register (Approve / Needs Correction / Reject = *your decision*) **distinct in copy**, with
the reminder paragraph "These are the engine's suggestions. The disposition … is always your
decision." This is copy only — no enum, no mapping, no code.

### Exact KB copy (from `mockups/help-panel.html`, reproduce verbatim)

1. **Q:** "What exactly must the Government Warning say?"
   **A:** "The full text is fixed by 27 CFR §16.21. We compare the label, word for word, to
   that regulation — not to anything the maker typed. The character diff shows exactly where
   the wording differs."
2. **Q:** "Why didn't the tool check the font size?"
   **A:** "Font size is measured on the physical label, not the photo — there's no scale in an
   image. So we say so plainly and leave it for your eyes, rather than guessing a pass or fail."
3. **Q:** "The names differ only in capitalization — is that a real mismatch?"
   **A:** "Usually not. Capitalization differs; the text otherwise matches. We mark that as an
   amber \"check,\" not a red mismatch, and leave the call to you."
4. **Q:** "What's the difference between Needs Correction and Rejected?"
   **A:** "Needs Correction sends the application back to the maker to fix and resubmit.
   Rejected closes it out. Both need a note so the maker knows the reason — you decide which fits."

**Verdict rows (exact):**
- **PASS** ✓ — "Checked automatically and matched. Nothing for you to chase — confirm if you like."
- **REVIEW** ⚠ — "Needs your eyes. Either a soft difference (like capitalization) or something a
  photo can't confirm. Your call."
- **FAIL** ✕ — "A clear mismatch against the rule or the regulation. The differing text is
  highlighted so you can see what's wrong."
- Reminder (above the rows): "These are the engine's **suggestions**. The disposition — Approve,
  Needs Correction, Reject — is always your decision."
- Note (below the rows): "Color is never the whole story — every status carries an icon and a
  word as well as a color."

**No-results state (exact):** heading "No matches yet for that."; body "Try fewer words, or
browse the common questions above. If it's about a specific check, open its "Why?" note on the
Review screen."; "You could try": "Government Warning wording", "capitalization difference",
"why a check says "couldn't verify"". (The mockup's `frame-label` "No-results state" caption is
scaffolding — exclude it.)

### Spine token substitutions (mockup hex → brand.css token)

| Mockup inline | Use instead (brand.css) | Note |
|---|---|---|
| navy `#112E51` | `var(--brand-primary)` | panel head, left border |
| `#205493` (blue) | `var(--brand-primary-light)` | KB left accent, chevrons, focus ring |
| PASS `#2E8540` / bg `#ECF3EC` | `var(--verdict-pass)` / `var(--verdict-pass-bg)` | **spine wins** |
| REVIEW `#B8860B` / bg `#FAF3D1` | `var(--verdict-review)` / `var(--verdict-review-bg)` | **spine wins** |
| FAIL `#B50909` / bg `#F4E3DB` | `var(--verdict-fail)` / `var(--verdict-fail-bg)` | matches |
| surface `#FFFFFF`, ink `#1B1B1B`, muted `#5C5C5C`, border `#DCDEE0`, base `#F0F0F0` | `--brand-surface`/`--brand-ink`/`--brand-ink-muted`/`--brand-border`/`--brand-base` | |
| fonts Public Sans / Roboto Mono | `var(--brand-font-sans)` / `var(--brand-font-mono)` | self-hosted, no Google Fonts |

### Source tree components to touch

- `templates/base.html` — **UPDATE**: wire the `[?]` button ARIA + include the new partial;
  add the global `help.js` `<script>`. (Today the header comment at lines 16–19 says the
  panel "is wired in Story 4.4" — that note was aspirational; this is the story that wires it.
  Update that comment to reference Story 4.9.)
- `templates/_help_panel.html` — **NEW**: the slide-over dialog partial (scrim + panel).
- `static/css/brand.css` — **UPDATE**: append the Help-panel block (spine tokens only).
- `static/js/help.js` — **NEW**: dialog open/close/focus-trap + client-side KB filter.
- `tests/test_help_panel.py` — **NEW**: render + gate + no-egress + fidelity guards.

### Project Structure Notes

- Templates live at repo-root `templates/` (NOT `app/templates/`); static at repo-root
  `static/` — both mounted in `app/main.py` (`TEMPLATES_DIR`, `STATIC_DIR`). Partials are
  prefixed `_` (`_field_card.html`, `_action_bar.html`, …) — follow that convention with
  `_help_panel.html`.
- No new route ⇒ `app/main.py` is unchanged; the panel rides the already-mounted templates env
  and the existing token-gate middleware (every screen extending `base.html` is already gated).
- snake_case everywhere; ruff line length 100; no inline `<style>`, no CDN, no build step.

### Testing standards summary

- pytest in top-level `tests/`, `test_*.py`. Use the existing app/TestClient fixtures (see
  `tests/test_queue.py` and `tests/test_review*.py` for the seeded-DB + gate-toggle patterns).
- Render-level assertions over the returned HTML string (the panel is in `base.html`, so any
  screen that extends it carries it — `/queue` is the cheapest probe; also assert on a seeded
  `/review/{id}`).
- File-content guards (read `brand.css` / `help.js` / `base.html`) for the **no-egress** and
  **spine-token** invariants — these are the highest-value tests for this story (they keep the
  "everything on this server" promise honest and prevent a CDN regression).
- Run only `tests/test_help_panel.py` while iterating; run the full `bash scripts/ci.sh` once
  at the end.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.9: In-UI Help panel] (lines 657–668) — AC + FR-8/UX-DR-4.
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR-4] (line 127) — right-anchored slide-over `role="dialog"`, scrim, search + on-server note, browsable KB, verdict explainer, shortcuts, no-results; one-click `[?]` every screen; Esc closes.
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR-6] (line 132) — vendored USWDS, self-hosted fonts, same-origin, no CDN/build.
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR-7] (line 133) — verdict palette icon+word+colour, spine values win (#216E29/#7A5900/#B50909).
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR-15] (line 141) — accessibility floor: colour never alone, ≥16px/≥48px, focus trap + return-focus for Help.
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR-16] (line 142) — two-track interaction; `?` Help / `Esc` close are documented in Help; single-letter shortcuts inert in inputs (4.10 owns the global handler).
- [Source: ux-designs/.../mockups/help-panel.html] — the binding mockup (layout, components, exact copy, both states); inline hex is illustrative — spine wins.
- [Source: ux-designs/.../EXPERIENCE.md#Help panel] (line 44, 56, 118, 147) — searchable local KB; help no-results calm state; focus return to `[?]`.
- [Source: ux-designs/.../EXPERIENCE.md#Voice and Tone] (lines 66, 73) — verdict-vs-disposition wording; authority returns to the human; limitations stated plainly.
- [Source: CLAUDE.md / project-context.md#Firewall & Offline Posture] — NFR-2: all assets same-origin, no CDN/Google Fonts; the only permitted egress is the LLM adapters (irrelevant here).
- [Source: project-context.md#UI Fidelity & USWDS Discipline] — every screen matches its mockup; spine wins on conflict; mockup scaffolding excluded; side-by-side check in DoD.
- [Pattern: static/js/disposition.js:113-195] — focus-trap + Esc + return-focus modal pattern to mirror.
- [Pattern: static/js/review.js:19-25] — IIFE + inert-when-absent + same-origin script shape.
- [Pattern: templates/base.html:20-27] — the existing `[?]` button + `{% block header %}` (empty pre-auth in access.html:6).

## Dev Agent Record

### Agent Model Used

claude-opus-4 (Amelia, Senior Software Engineer)

### Debug Log References

- Initial RED: `tests/test_help_panel.py` 12 failed / 3 passed (no impl). GREEN after
  Tasks 1–5: 15 passed.
- Two self-inflicted guard failures caught by the no-egress / spine-token tests and
  fixed (the tests doing their job):
  1. The Help **CSS banner comment** literally contained `no CDN` and the mockup hex
     `#2e8540`/`#b8860b` — the `test_help_css_*` guards scan the whole block including
     comments, so the comment was reworded to drop those substrings (the *rule* the
     prose described would otherwise have tripped its own guard).
  2. The Help **JS header comment** listed `XMLHttpRequest` as forbidden-API prose —
     the no-egress substring guard flagged it; reworded to avoid any
     network-request/remote-resource literal.
- Final full gate: `bash scripts/ci.sh` → format ok, lint ok, mypy ok, **650 passed,
  1 skipped**.

### Completion Notes List

- **Architecture**: zero new Python — the panel is static chrome in `templates/base.html`
  (`{% include "_help_panel.html" %}` inside `{% block header %}`), so it rides every
  screen that extends base (queue, review) and is suppressed pre-auth (access.html
  empties the header block). No route, no DB, no schema. AR-5 untouched (no handler
  changed).
- **NFR-2 honesty kept literal**: search is a client-side DOM filter in
  `static/js/help.js` — the file contains no network-request / remote-resource /
  dynamic-load reference (substring-guarded in the tests), so the on-screen promise
  "everything here is on this server" is true.
- **Progressive enhancement**: the full KB + verdict explainer + shortcuts render
  without JS; help.js only adds open/close/focus-trap + the live filter. Focus trap +
  Esc + return-focus mirror the proven `static/js/disposition.js` modal pattern.

- **DoD side-by-side vs `mockups/help-panel.html` (state for state):**
  - *Open-dialog state*: head (navy bar, `Help` title + sub + close), search +
    on-server hint, four KB items (verbatim copy), PASS/REVIEW/FAIL explainer with the
    verdict-vs-disposition reminder + "Color is never the whole story" note, keyboard
    shortcuts (N; A/C/R; ←/→; ?/Esc) — all reproduced.
  - *No-results state*: the `.help-empty` block ("No matches yet for that." + guidance +
    "You could try" examples) reproduced; revealed by the filter only on zero matches
    (calm, never an error).
  - **Spine-token substitutions applied** (mockup inline hex → brand.css token): navy
    `#112E51`→`--brand-primary`; blue `#205493`→`--brand-primary-light`; PASS
    `#2E8540`/`#ECF3EC`→`--verdict-pass`/`--verdict-pass-bg` (spine green `#216E29`
    wins); REVIEW `#B8860B`/`#FAF3D1`→`--verdict-review`/`--verdict-review-bg` (spine
    `#7A5900` wins); FAIL `#B50909`→`--verdict-fail` (matches); surface/ink/muted/border/
    base → `--brand-*`; Public Sans / Roboto Mono → `--brand-font-sans`/`--brand-font-mono`
    (self-hosted, no Google Fonts). KB answer + verdict desc + note bumped to ≥16px
    (older-eyes floor); KB question 17px.
  - **Excluded mockup scaffolding** (UI fidelity standard): the `.device` browser frame,
    the `.browser-bar`/`.url` chrome, the dimmed-Review `.backdrop`/`.bd-*` artwork, and
    the `.frame-label` "No-results state" caption. The running Review screen IS the
    backdrop; `.help-scrim` is a functional dim layer only.

### Code Review (2026-06-14) — 5 patches applied to static/js/help.js, 0 deferred

Three-layer adversarial review (Blind Hunter diff-only / Edge-Case Hunter / Acceptance
Auditor). All 5 ACs SATISFIED; copy fidelity, spine-token, NFR-2 zero-egress, and
verdict-vs-disposition invariants all preserved. Five robustness patches to the
progressive-enhancement JS (no template/CSS/route change — AR-5 untouched):

- **CR-1 (M1/L5/L6, converged 3 layers) — return-focus could silently drop to `<body>`.**
  `closePanel` restored `lastFocused` whenever it had a `.focus` method, but a detached/
  hidden node (or `document.body`) keeps that method while `.focus()` is a no-op, dropping
  the keyboard user's place instead of returning to `[?]`. Now guarded on
  `!== document.body && isConnected && offsetParent !== null`, else falls back to the
  trigger (the canonical return target, AC1).
- **CR-2 (Edge M4) — stale filter state persisted across reopen.** A no-match query left
  `.help-empty` showing and the KB list hidden; reopening Help showed "No matches yet for
  that." with the box pre-filled (looked broken, violated AC2 "full KB browsable").
  `openPanel` now clears the search box and re-runs `filterKb()` before showing.
- **CR-3 (Edge M2 / Blind L8) — filter haystack included the decorative chevron.** Matching
  on the whole `<li>` `textContent` meant a query of `›` (the `&rsaquo;` chevron,
  `aria-hidden`) matched every item. Corpus now built from `.help-kb__q` + `.help-kb__a`
  text only.
- **CR-4 (Edge M3) — curly-quote mismatch made the empty-state's own advice fail.** The KB
  copy uses typographic apostrophes (`couldn't`, `What's`); a user typing the ASCII `'`
  got zero matches — and the no-results state literally suggests the query
  `"couldn't verify"`. `filterKb` now folds curly→straight quotes on both query and
  haystack before substring match.
- **CR-5 (Edge L7) — scrim drag-release closed the panel.** A text-selection drag that
  began inside the panel and released over the scrim fired the scrim `click` and discarded
  the panel. Mirrored the `disposition.js` backdrop guard: track `mousedown` and only
  close when both `mousedown` and `click` target the scrim itself. Also hardened the Tab
  trap to re-anchor focus into the panel when `activeElement` isn't among the computed
  focusables (Blind H2 robustness).

**Dismissed (out of scope / by design):** Blind/Edge "global `?` shortcut / `?`-in-input
propagation" — explicitly Story 4.10's concern (the panel owns only its scoped Esc; the
spec forbids implementing the global single-letter handler here). Blind H3 "no-results
leaves other sections visible" — by design: AC3 scopes the filter to the KB region only.
Auditor MEDIUM `offsetParent` focus-trap "break" — empirically disproved (the always-
present close button guarantees ≥1 focusable); hardened anyway via CR-5's re-anchor guard.
Auditor LOW `.help-panel__sub` `#cdd6e0` and `.help-verdicts__reminder` 15px — faithful-to-
mockup small print (header tint / hint register), not spine-floor violations the story
called out; left as-is.

+5 regression guards in `tests/test_help_panel.py` (reset-on-open, curly-quote fold,
Q/A-scoped haystack, safe return-focus, scrim drag guard). Full host gate green:
format → lint → mypy (87 files) → **655 passed / 1 skipped**.

### File List

- `templates/base.html` — UPDATE: wired the `[?]` button (`aria-haspopup="dialog"`,
  `aria-controls`, `aria-expanded`, `data-help-open`), included `_help_panel.html` inside
  the header block, added the global `/static/js/help.js` script tag.
- `templates/_help_panel.html` — NEW: the right-anchored slide-over dialog partial
  (scrim + panel; five regions; exact copy).
- `static/css/brand.css` — UPDATE: appended the `Help panel (Story 4.9)` block
  (spine `--brand-*`/`--verdict-*` tokens only).
- `static/js/help.js` — NEW: open/close/focus-trap + return-focus + client-side KB
  filter (no network call).
- `tests/test_help_panel.py` — NEW: render presence, gating, no-egress JS guard,
  spine-token CSS guard, icon+word, no-scaffolding.
