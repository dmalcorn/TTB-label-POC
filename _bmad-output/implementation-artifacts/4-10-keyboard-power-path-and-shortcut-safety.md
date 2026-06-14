# Story 4.10: Keyboard power path & shortcut safety

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a high-volume Label Specialist,
I want keyboard shortcuts that never fire by accident,
so that I can move fast without risking an irreversible federal act.

## Acceptance Criteria

(Verbatim intent from `epics.md` Story 4.10 — *(UX-DR-16)*; the cross-cutting
accessibility/voice floors UX-DR-15/18 apply. The shortcut **vocabulary** is already
documented to the user in the Story 4.9 Help panel's "Keyboard shortcuts" region — this
story makes that documented path **live**, additively, without breaking the mouse path.)

1. **AC1 — the documented keyboard path works.** Given the documented keyboard path,
   when the specialist uses it, then:
   - `N` = **Next Submission** (fires the Queue's primary `/next` POST form; inert when
     there is no enabled Next button — e.g. the empty-queue State-2 disabled button);
   - `A` / `C` / `R` = **Approve / Needs Correction / Reject**, each **routed through its
     existing confirm/Notes gate** — the shortcut *activates the matching disposition
     control* (the same code path a mouse click takes), so the Notes soft-gate (Needs
     Correction / Reject) and the open-REVIEW confirm modal still apply; a shortcut
     **never** bypasses a gate or auto-submits an ungated disposition;
   - `←` / `→` = **move between label image faces** (follow the image panel's
     prev/next pager links when present; inert when there is no pager — single image or
     no images);
   - `?` = **open Help** (the Story 4.9 slide-over);
   - `Esc` = **close the topmost layer** (the disposition confirm modal first, else the
     Help panel — closing exactly one layer per press, the one that owns focus).

2. **AC2 — single-letter shortcuts are inert in text entry and while a modal owns
   focus.** All single-letter shortcuts (`N`/`A`/`C`/`R` and `?`) are **inert when focus
   is in any `<input>` / `<textarea>` / `contenteditable` element** (typing a correction
   reason into Notes can **never** fire `R`) **and inert while a modal owns focus** (the
   disposition confirm modal or the Help dialog) — so a stray letter cannot reach through
   an open dialog to commit a federal act. `Esc` is the one key that **is** honoured while
   a modal owns focus (it is the documented "close" affordance). The arrow keys `←`/`→`
   are likewise suppressed while focus is in a text field or a modal owns focus (so arrow
   navigation within Notes / a select is never hijacked).

3. **AC3 — the mouse path remains fully sufficient; auto-focus never auto-acts.**
   Shortcuts are **purely additive** progressive enhancement (UX-DR-16 two-track): every
   action remains reachable by mouse with **no** keyboard handler present (the server
   render + the existing forms/links/`disposition.js`/`help.js` already do the work). The
   keyboard handler **must not** change any server route, template structure, or the
   existing JS behaviours — it only *dispatches to* the controls already on the page. The
   Queue still **auto-focuses** the Next Submission button (Enter fires it natively) but
   **never auto-opens** a submission, and no shortcut fires on load.

## Tasks / Subtasks

> **Test-first throughout (red → green → refactor).** This is a **single new
> progressive-enhancement JS file** story — there is **no new Python route, no DB
> read/write, no schema change, and no change to the existing templates' structure or the
> other JS files' behaviour**. Mirror the IIFE / inert-when-absent / no-throw / same-origin
> shape of `static/js/help.js`, `static/js/review.js`, and `static/js/disposition.js`. The
> handler **dispatches to controls that already exist** (the `/next` form button, the
> `disposition.js`-managed `<button name="disposition">` controls, the image pager `<a>`
> links, the `[?]` Help trigger) — it never re-implements their behaviour, so the existing
> gates (Notes soft-gate, confirm modal, focus-trap) keep working unchanged. Do **NOT**
> add a server endpoint, a new control, or duplicate the disposition/help logic — that
> would be over-engineering and risk a gate-bypass (the exact danger AC2 guards against).

- [ ] **Task 1 — New global shortcut handler `static/js/shortcuts.js` (AC1, AC2, AC3).** (AC: 1, 2, 3)
  - [ ] New same-origin script (no build, no CDN). Header comment must state: same-origin /
        zero-egress (NFR-2, contains no network-request, remote-resource, or dynamic-load
        reference); the mouse path is fully sufficient WITHOUT it (UX-DR-16); it **dispatches
        to existing controls** and never re-implements a gate; single-letter shortcuts are
        **inert in text entry and while a modal owns focus** (UX-DR-16 shortcut safety) — the
        load-bearing safety invariant.
  - [ ] IIFE, `"use strict"`, inert/no-throw. A single `document.addEventListener("keydown", …)`
        in the **bubble** phase (default), so a layer that already handled the key — e.g. the
        Help panel's own scoped `Esc`/`Tab` trap, or `disposition.js`'s modal `Esc`/`Tab`
        — runs first and the global handler can detect/skip via the guards below.
  - [ ] **Modifier guard**: ignore the event when any of `event.ctrlKey` / `event.metaKey` /
        `event.altKey` is set (don't hijack browser/OS chords like ⌘R, Ctrl+A); also ignore
        `event.isComposing` / `keyCode === 229` (IME composition) and any
        `event.defaultPrevented` event (a deeper handler already consumed it).
  - [ ] **Text-entry guard** (`isTextEntry(el)`, AC2): true when the event target (or
        `document.activeElement`) is an `<input>` (any non-button type), `<textarea>`,
        `<select>`, or an element with `isContentEditable` / `contenteditable="true"`. When
        true, **all single-letter shortcuts and the arrow keys are suppressed** (return
        early) — `Esc` is NOT a single-letter shortcut here and is handled by the layer that
        owns focus, so it is unaffected.
  - [ ] **Modal-owns-focus guard** (`modalOpen()`, AC2): true when a `[data-disposition-modal]`
        is present and **not** `hidden`, OR the Help `#help-panel` is present and **not**
        `hidden`. While true, **suppress every single-letter shortcut and the arrow keys** —
        a stray `R` must never reach through an open dialog. `Esc` is allowed to pass through
        to the owning layer (do not preventDefault it here; the modal/help handler closes
        itself). Belt-and-braces only: `?` opening Help while Help is already open is a
        no-op anyway, but the guard keeps `A/C/R` from firing under the confirm modal.
  - [ ] **Key dispatch** (only reached past the guards above):
    - `event.key === "?"` → if a Help trigger `[data-help-open]` exists, `preventDefault()`
      and dispatch a `click()` to it (reuse help.js's open path; do NOT re-implement the
      dialog). Inert if absent. (`?` is typically Shift+/, so it must be checked by `key`,
      not `code`; the modifier guard above already excludes Ctrl/Meta/Alt but Shift is
      expected for `?`, so do **not** block on `shiftKey`.)
    - `event.key === "n" || "N"` → find the Queue primary Next control
      `form[action="/next"] button[type="submit"].btn-next` (the enabled one — not the
      `is-disabled`/`disabled` State-2 button). If found and not disabled, `preventDefault()`
      and `click()` it (native submit carries the sticky `type`). Inert otherwise.
    - `event.key in {a,A / c,C / r,R}` → map to the disposition KEY
      (`A→APPROVED`, `C→NEEDS_CORRECTION`, `R→REJECTED`) and find the matching
      `button[name="disposition"][value="<KEY>"]` inside `[data-disposition-form]`. If found
      and not disabled, `preventDefault()` and `click()` it — this re-enters `disposition.js`'s
      own click handler, so the Notes soft-gate + confirm modal + double-submit guard ALL
      still apply (AC1: "routed through its confirm/Notes gate"). Inert when the bar is absent
      (e.g. the Queue screen) or the button is disabled.
    - `event.key === "ArrowLeft"` → follow the image pager's `prev` link
      (`.image-panel__pager-link[rel="prev"]`); `event.key === "ArrowRight"` → the `next`
      link (`[rel="next"]`). If present, `preventDefault()` and navigate
      (`window.location.assign(href)` or `link.click()`); inert when no pager (single/zero
      images). (These are real `<a href="?image=…">` links, so following them is the same
      JS-free paging the mouse uses.)
  - [ ] **`Esc` is intentionally NOT globally handled here** beyond passing through: the Help
        panel (help.js) and the confirm modal (disposition.js) each own their scoped `Esc`
        when they hold focus, closing exactly the topmost layer (AC1's "close the topmost
        layer"). The global handler must NOT add a second `Esc` close (that would double-close
        / close the wrong layer). A short comment must record this delegation so a future
        reader doesn't "fix" it by adding an Esc branch.

- [ ] **Task 2 — Wire `shortcuts.js` into `base.html` (AC1, AC3).** (AC: 1, 3)
  - [ ] Add `<script src="/static/js/shortcuts.js"></script>` to `templates/base.html`
        **next to the global `/static/js/help.js` tag, OUTSIDE `{% block scripts %}`** (the
        shortcut path is global chrome — it must be present on Queue AND Review, both of which
        extend `base.html`). Load it AFTER `help.js` so `[data-help-open]` is already wired
        when a `?` press dispatches a click (order is not strictly required since both bind
        on their own, but keep the global scripts grouped). Per-page `{% block scripts %}`
        (review.html's `review.js` + `disposition.js`) is untouched.
  - [ ] Update the `base.html` comment that introduces the global scripts to mention the
        Story 4.10 shortcut handler alongside the Story 4.9 Help script.

- [ ] **Task 3 — `aria-keyshortcuts` discoverability hints on the live controls (AC1).** (AC: 1)
  - [ ] The Queue Next button already carries `aria-keyshortcuts="N"` (queue.html:59) —
        leave it. Add `aria-keyshortcuts` to the controls this story now drives so a screen
        reader announces the available shortcut (UX-DR-15 — the buttons are the canonical
        SR path, the hint is additive):
    - In `templates/_action_bar.html`, add `aria-keyshortcuts="{{ {'APPROVED':'A',
      'NEEDS_CORRECTION':'C','REJECTED':'R'}[control.key] }}"` to each
      `<button name="disposition">` (map by the disposition KEY — A/C/R).
    - In `templates/_image_panel.html`, add `aria-keyshortcuts="ArrowLeft"` to the `prev`
      pager link and `aria-keyshortcuts="ArrowRight"` to the `next` pager link.
  - [ ] Do **not** restyle anything or change control structure — these are ARIA-only
        attribute additions (AC3: structure unchanged). The `[?]` trigger keeps its existing
        `aria-label="Help"`; optionally add `aria-keyshortcuts="?"` (low-risk hint).

- [ ] **Task 4 — Tests (all ACs).** Write FIRST (red), then implement to green. New file
      `tests/test_shortcuts.py` — render-level assertions (the `aria-keyshortcuts` hints +
      the script wiring) plus **file-content guards over `static/js/shortcuts.js`** (the
      keyboard behaviour itself is client-side; pytest cannot execute it, so we assert the
      load-bearing safety invariants are present in the source, mirroring the
      `tests/test_help_panel.py` JS-guard pattern). (AC: 1, 2, 3)
  - [ ] **Wiring (AC1/AC3)**: `base.html` references `/static/js/shortcuts.js`; the file
        exists; it loads OUTSIDE the per-page scripts block (assert the tag is present in
        `base.html`, the global template, not only in review.html). GET `/queue` returns 200
        with the script tag in the HTML; GET `/review/{id}` (seeded ready submission) also
        returns 200 with it.
  - [ ] **No-egress JS guard (AC3/NFR-2)**: read `static/js/shortcuts.js` and assert it
        contains **no** `fetch(`, `XMLHttpRequest`, `import(`, `https://`, `http://`, or
        `//cdn` substring — the handler only dispatches DOM clicks/navigation, no network.
  - [ ] **Text-entry inert guard (AC2 — the load-bearing safety test)**: assert the source
        guards on text entry — it references `tagName`/`TEXTAREA`/`INPUT`/`SELECT` and
        `isContentEditable` (or `contenteditable`) and returns early so a single-letter
        shortcut is suppressed in a field. (Read the file and assert the substrings exist.)
  - [ ] **Modal-owns-focus inert guard (AC2)**: assert the source checks
        `data-disposition-modal` AND `help-panel` for an open (`hidden`) state before firing a
        single-letter shortcut (so `A/C/R` can't reach through an open dialog).
  - [ ] **Modifier guard (AC2)**: assert the source ignores `ctrlKey`, `metaKey`, and
        `altKey` (don't hijack ⌘R / Ctrl+A) and skips `defaultPrevented` events.
  - [ ] **Dispatch-not-reimplement (AC1/AC3)**: assert the source dispatches to existing
        controls — it references `data-disposition-form` + `name="disposition"` (A/C/R route
        through disposition.js's gate, NOT a direct form.submit of a disposition value — assert
        `form.submit(` does NOT appear for the disposition path), `data-help-open` (`?`),
        `action="/next"` / `.btn-next` (`N`), and `rel="prev"` / `rel="next"` (arrows).
        Assert it contains **no** `value="REJECTED"`-style hardcoded submit that bypasses the
        button (i.e. it must `.click()` the button, not synthesize the POST) — guard by
        asserting `XMLHttpRequest`/`fetch(` absent (already) AND that `disposition` appears
        only as an attribute selector, not as a created hidden input
        (`createElement("input")` must NOT appear in this file — that is disposition.js's job).
  - [ ] **`aria-keyshortcuts` hints (AC1)**: GET `/review/{id}` HTML carries
        `aria-keyshortcuts="A"`, `="C"`, `="R"` on the three disposition buttons (pick a
        seeded submission that renders the action bar); and the Next button on `/queue` keeps
        `aria-keyshortcuts="N"`. If the seeded submission has a multi-image pager, assert
        `aria-keyshortcuts="ArrowLeft"`/`="ArrowRight"`; otherwise assert the attribute string
        is present in the `_image_panel.html` template source (file-content guard) so the test
        does not depend on fixture image counts.
  - [ ] **Esc not double-handled (AC1)**: assert `shortcuts.js` does NOT add its own
        `Escape` close branch that calls a close/`hidden` toggle (guard: the file may mention
        `Escape` only in a comment explaining the delegation; assert there is no
        `key === "Escape"` dispatch that toggles `hidden` — keep this guard lenient: assert
        the delegation comment phrase is present, e.g. "topmost layer" / "delegat").
  - [ ] **Mouse-path-sufficiency (AC3)**: a render-level assertion that the existing controls
        still render unchanged with the script absent in spirit — i.e. GET `/queue` still has
        the real `form action="/next"` submit button and GET `/review/{id}` still has the real
        `data-disposition-form` POST form and (if applicable) pager links. (These already pass
        from 4.1/4.7/4.8; re-assert here to pin that 4.10 did not alter structure.)

- [ ] **Task 5 — DoD: documented two-track check (AC3).** In the Completion Notes, record
      that the keyboard path mirrors the Help panel's documented shortcut list (N; A/C/R;
      ←/→; ?; Esc), that each `A/C/R` was verified to route through `disposition.js`'s
      gate (by dispatching a click, not synthesizing a POST), and that with JS disabled the
      mouse path is unchanged (the script is purely additive). Note the shortcut-safety
      invariants (inert in text entry + under a modal + modifier chords ignored) explicitly.

## Dev Notes

### What this story is — and is NOT

- **IS**: one new same-origin progressive-enhancement JS file (`static/js/shortcuts.js`)
  wired globally in `base.html`, plus ARIA-only `aria-keyshortcuts` discoverability hints
  on the controls it drives. It **dispatches** keystrokes to controls that already exist
  (the `/next` form button, the disposition buttons, the image pager links, the `[?]`
  trigger). Pure client-side polish.
- **IS NOT**: a Python route, a DB read/write, a schema change, a new control, or a
  re-implementation of the disposition gate / Help dialog / image paging. There is **no
  AR-5 read-path risk** (no request handler changes) — and crucially, **no gate-bypass
  risk**, because `A/C/R` `.click()` the real disposition buttons and so re-enter
  `disposition.js`'s soft-gate + confirm-modal path rather than synthesizing a POST.
- **Reuse, don't reinvent**: the shortcut vocabulary is already DOCUMENTED in the Story 4.9
  Help panel (`templates/_help_panel.html`, "Keyboard shortcuts" region: N; A/C/R; ←/→; ?;
  Esc). This story makes that documented contract live. The dispatch targets already carry
  stable hooks: `form[action="/next"]` + `.btn-next` (queue.html), `[data-disposition-form]`
  + `button[name="disposition"][value="…"]` (`_action_bar.html`), `.image-panel__pager-link[rel]`
  (`_image_panel.html`), `[data-help-open]` (base.html). Mirror the IIFE / inert-when-absent
  / same-origin shape of `help.js` + `review.js` + `disposition.js`.

### The shortcut-safety invariant (UX-DR-16 — load-bearing, non-negotiable)

These shortcuts can fire **irreversible federal acts** (`R` = Reject). The spec is explicit:
single-letter shortcuts are **inert when focus is in any text input / textarea /
contenteditable** (so typing a correction reason in Notes can never fire `R`) **and inert
while a modal owns focus**. Implement BOTH guards as an early-return at the top of the
keydown handler, before any dispatch. `A/C/R` route through `disposition.js`'s real
gate — the handler `.click()`s the button, it never synthesizes the disposition POST. A
reviewer should reject any code path where a keystroke submits a disposition without going
through the button's click handler. (This mirrors the project-context rule: "prefer the more
restrictive option" around irreversible actions.)

### Why dispatch a click instead of submitting

`disposition.js` intercepts each disposition button's `click` to apply the Notes soft-gate,
the open-REVIEW confirm modal, and the double-submit guard. If `shortcuts.js` synthesized a
`form.submit()` with a hidden `disposition` field, it would **bypass all three gates** —
exactly the accident AC2 guards against. So `R` must `button.click()` the Reject control and
let `disposition.js` do its job. Same logic for `N` (click the native submit so the sticky
`type` rides along) and the arrows (follow the real `<a href="?image=…">` link, which is the
JS-free paging the mouse uses).

### Esc layering (AC1 — "close the topmost layer")

Do NOT add a global `Esc` handler. The two closable layers each already own their scoped
`Esc` while they hold focus: `disposition.js` (the confirm modal, disposition.js:166-171)
and `help.js` (the Help dialog, help.js:132-137). Because a modal/dialog traps focus, its
own `Esc` listener fires and closes exactly that one layer; the global handler adding a
second `Esc` branch would double-close or close the wrong layer. Record this delegation in a
comment so it is not "fixed" later.

### Accessibility floor (UX-DR-15 — applies even though this is "just shortcuts")

- `aria-keyshortcuts` on the live controls (Next already has it; add to A/C/R + the pager
  links) so a screen reader announces the available shortcut. The **buttons are the canonical
  SR path** (browse mode consumes single letters), so the shortcuts are strictly additive —
  never the only way to act.
- The handler must be inert in text entry (so SR/forms aren't hijacked) and never fire on
  load (no auto-act, U1). The mouse path is fully sufficient with the script absent (AC3).

### Source tree components to touch

- `static/js/shortcuts.js` — **NEW**: the global keydown handler (guards + dispatch).
- `templates/base.html` — **UPDATE**: add the global `<script src="/static/js/shortcuts.js">`
  next to `help.js` (outside `{% block scripts %}`); extend the global-scripts comment.
- `templates/_action_bar.html` — **UPDATE**: `aria-keyshortcuts="A|C|R"` on the three
  disposition buttons (ARIA-only; no structure/style change).
- `templates/_image_panel.html` — **UPDATE**: `aria-keyshortcuts="ArrowLeft|ArrowRight"`
  on the prev/next pager links (ARIA-only).
- `tests/test_shortcuts.py` — **NEW**: wiring + no-egress + safety-guard + dispatch +
  aria-keyshortcuts + mouse-path-sufficiency assertions.

### Project Structure Notes

- Templates at repo-root `templates/`, static at repo-root `static/` (mounted in
  `app/main.py`). No new route ⇒ `app/main.py` unchanged. snake_case everywhere; ruff line
  length 100; no inline `<style>`, no CDN, no build step.
- The script rides the already-mounted static dir and the existing token-gate middleware
  (it loads from `base.html`, suppressed pre-auth alongside the rest of the header chrome —
  but note the global `<script>` tags live in `<body>` outside the header block, like
  `help.js`; the handler is inert pre-auth anyway because none of its target controls exist
  on the access screen).

### Testing standards summary

- pytest in top-level `tests/`, `test_*.py`. Use the existing app/TestClient fixtures (see
  `tests/test_queue.py` / `tests/test_review*.py` for the seeded-DB + gate-toggle patterns,
  and `tests/test_help_panel.py` for the JS-file-content-guard pattern this story mirrors).
- The keyboard behaviour is client-side JS; pytest cannot execute it. The highest-value
  tests are therefore **file-content guards** over `static/js/shortcuts.js` asserting the
  load-bearing safety invariants (text-entry inert, modal-owns-focus inert, modifier-chord
  ignore, dispatch-not-synthesize) — these prevent a regression that would let a keystroke
  fire an ungated disposition.
- Run only `tests/test_shortcuts.py` while iterating; run the full `bash scripts/ci.sh` once
  at the end.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.10: Keyboard power path & shortcut safety] (lines 670–682) — AC + UX-DR-16; N; A/C/R routed through confirm/Notes gate; ←/→ faces; ? Help; Esc closes topmost; single-letter inert in text input/textarea/contenteditable AND while a modal owns focus; mouse path sufficient; auto-focus never auto-acts.
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR-16] (line 142) — two-track interaction + shortcut safety: mouse path always sufficient; additive keyboard power path; all single-letter shortcuts inert in text fields + while a modal owns focus; auto-focus never auto-acts; documented in Help.
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR-15] (line 141) — accessibility floor: colour never alone; keyboard-complete; aria-live; the buttons are the canonical SR path.
- [Source: ux-designs/.../EXPERIENCE.md#Interaction Primitives] (lines 120–134) — the keyboard power-path list (N; A/C/R; ←/→; ?; Esc); shortcut safety "load-bearing — these fire irreversible federal acts"; A/C/R route through their confirm/Notes gate (a real focus-trapped dialog, never an inline auto-submit); SR users use the on-screen buttons as the canonical path; auto-focus never auto-acts.
- [Source: ux-designs/.../mockups/help-panel.html] / [templates/_help_panel.html] — the documented shortcut list the user already sees (N; A/C/R; ←/→; ?/Esc).
- [Source: CLAUDE.md / project-context.md#Firewall & Offline Posture] — NFR-2: all assets same-origin, no CDN; "prefer the more restrictive option" (here: never bypass a disposition gate).
- [Source: project-context.md#Anti-patterns] — no auto-selected/auto-fired disposition; the verdict→disposition separation is untouched (a shortcut records the human decision via the human's own button).
- [Pattern: static/js/help.js:25-32, 107-110] — IIFE + inert-when-absent + the `[data-help-open]` open path to dispatch for `?`.
- [Pattern: static/js/disposition.js:166-195, 197-231] — the modal `Esc`/`Tab` trap (Esc delegation) + the disposition button click handler the `A/C/R` dispatch must re-enter (the gate).
- [Pattern: templates/queue.html:56-68] — `form[action="/next"]` + `.btn-next` (`aria-keyshortcuts="N"` already present); the disabled State-2 button to skip.
- [Pattern: templates/_action_bar.html:48-60] — `[data-disposition-form]` + `button[name="disposition"][value="APPROVED|NEEDS_CORRECTION|REJECTED"]` to add `aria-keyshortcuts` to + dispatch.
- [Pattern: templates/_image_panel.html:23-32] — `.image-panel__pager-link[rel="prev"|"next"]` to add `aria-keyshortcuts` to + follow for the arrows.
- [Pattern: templates/base.html:43-50] — where the global `help.js` `<script>` lives (outside `{% block scripts %}`); add `shortcuts.js` beside it.

## Dev Agent Record

### Agent Model Used

claude-opus-4 (Amelia, Senior Software Engineer)

### Debug Log References

- Initial RED: `tests/test_shortcuts.py` 15 failed / 2 passed (the two passing were the
  mouse-path-sufficiency render assertions — structure already correct from 4.1/4.8;
  everything touching the not-yet-created `shortcuts.js` + the `aria-keyshortcuts` hints
  failed).
- Two GREEN follow-ups after the first implementation pass:
  1. `test_shortcuts_js_dispatches_to_existing_controls` — the pager selector was built by
     string-concatenation (`'…[rel="' + rel + '"]'`), so the contiguous literal `rel="prev"`
     never appeared in the source for the guard to find. Refactored to two named constant
     selectors (`PAGER_PREV`/`PAGER_NEXT`) — clearer AND the guard passes.
  2. `test_queue_next_keeps_keyshortcut_hint` — the empty-DB queue renders the *disabled*
     State-2 Next button (no shortcut by design). Seeded a `READY_FOR_REVIEW` submission so
     the enabled Next button (which carries `aria-keyshortcuts="N"`) renders.
- Final targeted: `tests/test_shortcuts.py` → **17 passed**. Full host gate: see Completion
  Notes (format → lint → mypy → tests, all green).

### Completion Notes List

- **Architecture**: zero new Python — one new same-origin progressive-enhancement file
  `static/js/shortcuts.js`, wired globally in `templates/base.html` (outside
  `{% block scripts %}`, beside `help.js`), plus ARIA-only `aria-keyshortcuts` hints on the
  controls it drives. No route, no DB, no schema, no structural template change. AR-5
  untouched (no request handler changed).
- **Dispatch, never re-implement (no gate bypass)**: the handler `.click()`s the controls
  that already exist — `N` → the `/next` submit button; `A/C/R` → the real
  `button[name="disposition"][value="…"]` so `disposition.js`'s Notes soft-gate +
  open-REVIEW confirm modal + double-submit guard ALL still run; `←/→` → the real pager
  `<a href="?image=…">` links; `?` → the `[data-help-open]` trigger (help.js owns the
  dialog). The file creates no form fields and submits no form for the disposition path —
  guarded by `test_shortcuts_js_does_not_bypass_the_disposition_gate` (no `createElement`,
  no `.submit(`).
- **Shortcut safety (UX-DR-16, load-bearing)** — implemented as an early-return at the top
  of the single `keydown` handler, before any dispatch:
  - **inert in text entry**: `isTextEntry()` returns true for `<textarea>`/`<input>`/
    `<select>`/`contenteditable` (checked on both `event.target` and
    `document.activeElement`), so typing a correction reason in Notes can never fire `R`;
  - **inert while a modal owns focus**: `modalOpen()` true when `[data-disposition-modal]`
    or `#help-panel` is present and not `hidden` — a stray `A/C/R`/`?`/arrow can't reach
    through an open dialog;
  - **modifier chords ignored**: `ctrlKey`/`metaKey`/`altKey`, IME composition
    (`isComposing`/`keyCode 229`), and `defaultPrevented` events are skipped.
- **Esc delegation**: the handler does NOT close anything on `Esc` — it returns early so
  the layer that owns focus (help.js / disposition.js, each focus-trapped with its own
  scoped `Esc`) closes exactly the topmost layer. A header comment + a regression test
  (`test_shortcuts_js_delegates_esc_to_owning_layer`) pin this so it isn't "fixed" later.
- **NFR-2 zero egress**: the file makes no network/remote/dynamic-load reference (guarded);
  it only dispatches DOM clicks and follows same-origin links.
- **Two-track / mouse-path-sufficiency (UX-DR-16 / AC3)**: shortcuts are purely additive —
  the render is correct and fully usable with the script absent (the `/next` form, the
  disposition POST form, and the pager links are all real, re-asserted by the
  mouse-path-sufficiency tests). Nothing fires on load (Queue still auto-focuses Next but
  never auto-opens — U1).
- **DoD documented two-track check**: the live keyboard path mirrors the documented Help
  shortcut list (`templates/_help_panel.html` "Keyboard shortcuts": N; A/C/R; ←/→; ?; Esc)
  exactly. Each `A/C/R` routes through `disposition.js`'s gate (verified by dispatching a
  button click, not synthesizing a POST). Discoverability via `aria-keyshortcuts` (Next
  already had `N`; added `A/C/R` to the disposition buttons and `ArrowLeft/ArrowRight` to
  the pager links). With JS disabled the mouse path is unchanged.

### File List

- `static/js/shortcuts.js` — NEW: the global `keydown` handler — guards (modifier chords,
  text-entry inert, modal-owns-focus inert, Esc delegation) + dispatch to existing controls
  (N / A,C,R / ←,→ / ?).
- `templates/base.html` — UPDATE: added the global `/static/js/shortcuts.js` script tag
  beside `help.js` (outside `{% block scripts %}`); extended the global-scripts comment.
- `templates/_action_bar.html` — UPDATE: ARIA-only `aria-keyshortcuts="A|C|R"` on the three
  disposition buttons (mapped by disposition key; no structure/style change).
- `templates/_image_panel.html` — UPDATE: ARIA-only `aria-keyshortcuts="ArrowLeft"`/
  `"ArrowRight"` on the prev/next pager links.
- `tests/test_shortcuts.py` — NEW: wiring + no-egress + safety-guard (text-entry,
  modal-owns-focus, modifier chords) + dispatch-not-bypass + Esc-delegation + aria hints +
  mouse-path-sufficiency assertions (17 tests; +2 in code review → 19).

### Code Review (2026-06-14)

Three-layer adversarial review (Blind Hunter diff-only + Edge-Case Hunter +
Acceptance Auditor). **All 3 ACs satisfied** (Auditor: ALL MET); no project invariant
regressed. **2 patches applied + 2 regression tests; 0 deferred.**

- **PATCH-1 (`static/js/shortcuts.js`) — autorepeat guard.** Convergent root finding
  (Blind C2 + Edge F1/F4): a HELD key fires `keydown` continuously with no `event.repeat`
  guard, so a held `A/C/R` could re-click a disposition button during `disposition.js`'s
  brief native-submit re-enable window (`disposition.js:221-229` re-enables the clicked
  button so the form submit carries its value, then re-disables on a 0ms timer) —
  re-entering the click on an irreversible federal act. Added `if (event.repeat) return;`
  after the modifier/IME/`defaultPrevented` guards. One deliberate press, one dispatch;
  closes the machine-gun and the clean-path re-enable trigger with zero coupling to
  disposition.js internals.
- **PATCH-2 (`static/js/shortcuts.js`) — Shift-chord guard on the action branch.** (Blind
  H3) Gated the single-letter ACTION branch (`N` / `A,C,R`) on `!event.shiftKey`, placed
  AFTER the `?`/arrow branches so `?` (Shift+/) and the arrows are unaffected — a deliberate
  `Shift+R` (or a capital letter meant as text) can't reach the disposition dispatch. The
  matching button's own gate would still apply; the stricter option is the right default for
  an irreversible act (project-context: "prefer the more restrictive option").
- **+2 regression guards** in `tests/test_shortcuts.py`
  (`test_shortcuts_js_guards_against_key_autorepeat`, `test_shortcuts_js_action_keys_require_no_shift`).

**Dismissed (with rationale):** Blind C1 (R fires unconfirmed) — refuted by context:
`disposition.js:198-231` independently gates every disposition click; `.click()` re-enters
that handler (diff-blindness artifact). Blind H1/H2 (modal allowlist / `hidden`-only) — the
two-modal `data-disposition-modal`/`#help-panel` check IS the contract and both layers toggle
the `.hidden` property; generalizing is speculative. Edge F3 (`?` on AltGr layouts) —
US-layout deployment target, mouse `[?]` always works. Edge F7 (Esc dead-key on focus-loss) —
owning-layer concern, the Hunter explicitly says not to add an Esc branch here; out of scope,
not regressed. Edge F5 (pager skips `aria-disabled`) — latent only; the template omits
boundary links rather than disabling them.

Invariants preserved: verdict↔disposition separation, no auto-selected/auto-fired
disposition, AR-5 read purity, NFR-2 zero-egress, purely-additive two-track. Full host gate
green: format → lint → mypy 88 files → **674 passed / 1 skipped**.
