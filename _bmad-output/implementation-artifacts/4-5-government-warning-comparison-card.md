---
baseline_commit: f7ee2b9
---

# Story 4.5: Government Warning comparison card

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want the Government Warning shown as required-vs-on-label with a character-level
diff,
so that a wording deviation is unmistakable.

## Acceptance Criteria

1. **(Given** the Review Workspace served by `GET /review/{id}` (Story 4.3 shell,
   submission `IN_REVIEW`), **When** the Government Warning block renders, **Then)**
   the required §16.21 text and the on-label OCR text are **stacked** (required ABOVE
   on-label, vertical — never side-by-side) in `ocr-raw` **mono** for character-aligned
   diffing, with the differing span highlighted **plus a screen-reader text equivalent**
   (the diff is never a colored span alone — it survives forced-colors mode). Rendered
   as a pure **pre-computed DB read** (AR-5 — NO OCR / inference / model-layer call, NO
   `run_checks`, on the request path; the card reads the already-written
   `checklist_items` row whose `check_key == "government_warning"`, and parses the
   engine's stored JSON `detail` payload — it never re-runs the §16.21 comparison). The
   route stays token-gated by the existing middleware (no exemption added). *(FR-13
   surface, UX-DR-10, AR-5)*
2. **(And)** the **three outcomes render distinctly**, color always paired with icon +
   word, NEVER conflated (the engine already discriminated them via the `outcome` field
   in the JSON `detail` — the presenter dispatches on it, never re-derives):
   - **wording deviation** (`outcome == "reworded"`, verdict `FAIL`) → the required vs
     on-label stack with a **character diff** (`diff-del` / `diff-ins` / `diff-equal`
     spans built from the engine's stored `diff` opcodes) + the `✕ FAIL` chip;
   - **entirely absent** (`outcome == "absent"`, verdict `FAIL`) → `✕ FAIL` with the
     plain copy **"Required Government Warning not found on the submitted images"** and
     **NO diff against empty** (no on-label stack, no char-diff — diffing against an
     empty string would be noise);
   - **bold/caps undeterminable** (`outcome == "couldnt_verify"`, verdict `REVIEW`) →
     the **"couldn't verify"** REVIEW state with the `⚠ REVIEW` chip and a calm
     "couldn't confirm the bold/visual styling from a photo — please verify by eye"
     note, **never a silent PASS**, never red.
   The chip word/icon/class come from the engine's stored `checklist_items.verdict`
   (PASS `✓` / REVIEW `⚠` / FAIL `✕`) — never recomputed in the presenter or template.
   A **compliant** warning (`outcome == "pass"`, verdict `PASS`) renders the quiet
   `✓ PASS` state (the on-label text matched the statute — no diff). *(FR-13, UX-DR-10,
   DESIGN.md verdict palette, A11Y color-never-alone)*
3. **(And)** the card is the **Government Warning block**, NOT a stacked field
   comparison card (it has **no `field_comparisons` row** — the "required" side is the
   §16.21 statute carried in the engine's `detail` payload, not an application field).
   It fills the Story 4.3 `#group-gov-warning` placeholder section so the chevron's
   Gov. Warning step (③) anchor still resolves. When the submission has **no**
   `government_warning` checklist row at all (e.g. a not-yet-analyzed or non-applicable
   submission), the block renders a calm honest empty state ("The Government Warning
   check has not run for this submission.") — never a crash, never a fabricated PASS.
   *(UX-DR-10, EXPERIENCE.md State Patterns, honest-states)*
4. **(And)** the **required §16.21 text comes from the engine's stored `detail`
   payload** (which the Story-3.4 evaluator copied from the ruleset DATA
   `app/engine/rulesets/government_warning.py`) — the presenter and template carry **NO
   `27 CFR` literal and NO verbatim §16.21 warning string** (CFR-as-data; a grep/AST
   guard asserts no `27 CFR` literal in `review_view.py`). The CFR citation shown comes
   from `checklist_items.cfr_citation` (ruleset data) with the payload's `cfr_citation`
   as a fallback — never a Python literal. The presenter imports **nothing** from the
   OCR / LLM / engine-run layers (the Story 4.3/4.4 AR-5 source guard stays green); the
   char-diff is pure rendering of the engine's already-stored opcodes (no model, no
   `difflib` re-run needed — the diff was computed at engine time). *(FR-13, FR-18
   surface, CFR-as-data, AR-5)*
5. **(And)** the card **matches the Government Warning block in
   `mockups/review-workspace.html`** (lines 443–467 — the `Required (27 CFR §16.21)` /
   `On label (OCR)` two-row mono stack, the `✕ FAIL` chip, the `diff-del`/`diff-ins`
   spans, the plain fail note, and the "Why?" disclosure) in layout, USWDS component
   structure, all depicted states, and exact visible copy. Tokens resolve to
   `static/css/brand.css` `--verdict-*` vars (**Spine wins** over the mockup's inline
   hex — FAIL red is `#b50909`, REVIEW amber `#7a5900`), **no inline `<style>`, no
   CDN**; a documented side-by-side check against the mockup is in the DoD. The "Why?"
   `<details>`/`<summary>` (native, no JS) reveals the CFR citation + the engine
   `detail` rationale (the deviation description) + that it is a deterministic check
   (no LLM). *(FR-13, UI-fidelity standard, CFR-as-data, contract self-hosting)*

## Tasks / Subtasks

- [x] **Task 1 — Government Warning card presenter (test-first, AC1–AC5).** Extend the
  pure presenter `app/web/review_view.py` (the read-only module — keeps importing only
  `app.verdict` + the read models; NOTHING from the OCR / LLM / engine-run layers; the
  AR-5 source guard from Story 4.3/4.4 MUST stay green). Add a
  `government_warning_card(items) -> dict | None` builder, all snake_case:
  - **Locate the row.** Scan the `checklist_items` for the row with
    `check_key == "government_warning"` (a module constant `_GOV_WARNING_KEY =
    "government_warning"` — match the engine's strategy/key). Return `None` when no such
    row exists (AC3 honest empty state — the template renders the calm "check has not
    run" copy; do NOT fabricate a card).
  - **Parse the engine payload.** `checklist_items.detail` is a JSON string the
    Story-3.4 evaluator wrote: `{"outcome": "pass"|"reworded"|"absent"|
    "couldnt_verify", ...}`. Parse it defensively with `json.loads` inside a
    `try/except (json.JSONDecodeError, TypeError)` — a missing/garbled `detail` degrades
    to a `couldnt_verify`-style REVIEW card (honest, never a crash, never a silent PASS).
    Read the `outcome` discriminator; **dispatch on it, never re-derive** the §16.21
    comparison (the engine already did the work — contract: the read path re-runs no
    check).
  - **Build the view-model per outcome** (a small explicit mapping — NOT scattered
    `if`s in the template). The card dict carries:
    `{"verdict", "chip_class", "icon", "chip_word", "outcome", "cfr_citation",
    "required_text", "onlabel_text", "diff_required", "diff_onlabel",
    "diff_text_equivalent", "note", "detail"}`.
    - `outcome == "pass"` ⇒ verdict `PASS`, quiet state, the compliant on-label text
      shown (no diff), note `None`.
    - `outcome == "reworded"` ⇒ verdict `FAIL`; `required_text` = payload `expected`,
      `onlabel_text` = payload `found`; build `diff_required` / `diff_onlabel` span
      sequences (`[{"text","kind"}]`, `kind ∈ {equal, del, ins}`) from the payload's
      stored `diff` opcodes (the engine's `_char_diff` emitted `[(op, segment), …]`
      where `op ∈ {equal, delete, insert, replace}`); render `delete`→`del` on the
      required side, `insert`→`ins` on the on-label side, `equal` on both, and a
      `replace` opcode (`"<expected>→<found>"`, split on the `\u2192` arrow the engine
      embedded) as a `del` on the required side + an `ins` on the on-label side; plus a
      `diff_text_equivalent` plain string naming the deviation (A11Y). Note = the
      mockup's substantive-deviation copy.
    - `outcome == "absent"` ⇒ verdict `FAIL`; `required_text` / `onlabel_text` =
      `None`, NO diff; note = **"Required Government Warning not found on the submitted
      images"** (verbatim AC2). NO diff against empty.
    - `outcome == "couldnt_verify"` ⇒ verdict `REVIEW`; NO diff; calm "couldn't confirm
      the bold/visual styling from a photo — please verify by eye." note; never red.
  - **Chip + verdict.** Reuse the Story 4.4 `_CHIP_CLASS` / `_ALERT_ICON` maps but with
    a Government-Warning-appropriate chip WORD: PASS `PASS`, REVIEW `REVIEW`, FAIL
    `FAIL` (the field-card `_CHIP_WORD` says `match` for PASS — the Gov-Warning card is
    not a field-match, so add a small local `_GW_CHIP_WORD` map, or reuse
    `verdict`-keyed words `{PASS:"PASS", REVIEW:"REVIEW", FAIL:"FAIL"}`). The verdict is
    the engine's stored `checklist_items.verdict` — NEVER recomputed (contract #3). Pin
    the chip word/class to the verdict via the data map (icon + word ALWAYS present).
  - **CFR citation as DATA (AC4).** `cfr_citation` comes from
    `checklist_items.cfr_citation` (ruleset data), falling back to the payload's
    `cfr_citation` when the row's column is null — NEVER a `27 CFR` literal written in
    Python (a grep/AST guard asserts no `27 CFR` literal in `review_view.py`). Likewise
    the `required_text` (the §16.21 wording) comes ONLY from the parsed payload — never
    re-typed in the presenter.
  - **Diff text equivalent (A11Y).** Reuse / mirror the Story-4.4 `_diff_text_equivalent`
    idea: for a `reworded` outcome emit a plain string like
    `Required: '<expected>' — on label: '<found>'` so a screen-reader user and
    forced-colors mode still learn which side differs. (For the field cards the helper
    prefixes "Application:" — the Gov-Warning equivalent prefixes "Required:"; add a
    small `_gw_diff_text_equivalent(expected, found)` or parameterize.)
  - Tests in `tests/test_review_view.py`: a `government_warning` item with each of the
    four payloads (`pass` / `reworded` / `absent` / `couldnt_verify`) derives the right
    verdict + chip word + state; the `reworded` card carries `diff_required` /
    `diff_onlabel` span sequences built from the stored opcodes (a `del` on the required
    side + an `ins` on the on-label side, the unchanged run as `equal`) AND a
    `diff_text_equivalent`; the `absent` card draws NO diff and carries the verbatim
    "not found on the submitted images" note; the `couldnt_verify` card is REVIEW with no
    diff; a missing `government_warning` row ⇒ `government_warning_card` returns `None`;
    a malformed `detail` (non-JSON) degrades to a REVIEW card (no crash); the
    `cfr_citation` flows from the row (falling back to the payload); the AST/source
    guard still asserts `review_view` imports neither `run_checks` nor the ocr/llm
    adapters nor `pipeline.run`; the grep/AST guard asserts no `27 CFR` literal in
    `review_view.py`.

- [x] **Task 2 — wire the route read (test-first, AC1/AC3).** In
  `app/web/routes_review.py`, extend the existing `GET /review/{submission_id}` handler
  to also build the Gov-Warning card via `review_view.government_warning_card(items)`
  (reusing the `items` it ALREADY reads for the chevron + suggested-verdict + field
  cards — NO new DB query needed) and pass it to `review.html` as a `gov_warning`
  context key. The route stays a **pure read** — NO new OCR / inference / model import,
  NO `run_checks`, NO status write (the read-path source guard from Story 4.3/4.4 must
  stay green). A missing id still ⇒ calm 404.
  - Tests in `tests/test_review.py`: a seeded `IN_REVIEW` submission with a
    `government_warning` checklist row whose `detail` is the `reworded` payload renders
    200 with the `Required (27 CFR §16.21)` / `On label (OCR)` mono stack, the `FAIL`
    chip word, and `diff-del`/`diff-ins` spans; an `absent` payload renders the `FAIL`
    chip + the "not found on the submitted images" copy and NO `diff-` span; a
    `couldnt_verify` payload renders the `REVIEW` chip + the "couldn't verify" copy and
    NO red diff; a submission with NO `government_warning` row renders the calm "check
    has not run" empty state (200, never 500); the "Why?" `<details>` carries the CFR
    citation; the route remains token-gated (no-cookie ⇒ redirect to `/access`); the
    read-path source guard (no `pytesseract` / `adapters.ocr` / `adapters.llm` /
    `pipeline.run` / `run_checks` import reachable from the route) stays green.

- [x] **Task 3 — `review.html` Government Warning block (AC1–AC5).** In
  `templates/review.html`, REPLACE the inert `#group-gov-warning` placeholder section
  with the real Government Warning card (keep the placeholder sections for
  `#group-conditional` [Story 4.6] and `#group-decide` [4.8] — those stories fill
  them). No inline `<style>`, no JS; tokens via `brand.css`. Render via a new
  `templates/_gov_warning_card.html` partial (mirrors the `_field_card.html` precedent):
  - The `#group-gov-warning` section wraps the card so the chevron ③ anchor still
    resolves.
  - When `gov_warning` is falsy (no row) render the calm honest empty state copy.
  - The card header — a `Government Warning` label + the muted `cfr_citation` + the
    right-aligned `<span class="chip chip--{{ verdict|lower }}">` carrying `{{ icon }}` +
    `{{ chip_word }}` (icon + word always present), mirroring the mockup `.chead`.
  - For `reworded` (and `pass`): the **two-row mono stack** (`.gwblock`) — a
    `Required (27 CFR §16.21)`-labelled row showing `required_text` (or the diff
    segments) in `mono`, then an `On label (OCR)`-labelled row showing `onlabel_text`
    (or the `diff_onlabel` segments rendered as `diff-del`/`diff-ins`/`diff-equal`
    spans) in `mono`. When a diff is drawn, ALSO emit the visually-hidden
    `usa-sr-only` `diff_text_equivalent` (A11Y — diff never a colored span alone).
  - For `absent`: NO stack, NO diff — just the plain fail note "Required Government
    Warning not found on the submitted images" (mockup's plain-copy absent state).
  - For `couldnt_verify`: the calm REVIEW note, no diff.
  - The state note (`.field-card__note` or a gov-warning equivalent) where the state
    carries one — calm, plain language.
  - A "Why?" `<details class="…__why"><summary>Why?</summary>…</details>` revealing the
    CFR citation, the engine `detail` rationale (the deviation description), and that it
    is a deterministic check (no LLM) — native disclosure, no JS.
  - Reproduce the mockup copy/structure; Spine tokens win on color.

- [x] **Task 4 — `brand.css` Government Warning styles (AC2/AC5, no inline style).**
  Append to `static/css/brand.css` (after the field-card block) the gov-warning block
  rules — same-origin, tokens only (mirror the mockup `.gwblock`/`.gwtext`/`.lab` but
  resolve color to `--verdict-*` and the brand tokens):
  - A `.gov-warning` card surface (reuse the `.field-card` surface treatment, or a
    parallel block) with per-verdict left-bar + tint resolving to `--verdict-fail` /
    `--verdict-review` / `--verdict-pass` (the FAIL card loud, the REVIEW card amber,
    the PASS card quiet — exactly the field-card precedent at brand.css:531–545).
  - `.gov-warning__block` (the vertical required-over-onlabel stack — `flex-direction:
    column; gap`), `.gov-warning__lab` (the uppercase muted `Required` / `On label`
    label, the `Required` variant tinted), `.gov-warning__text` (the mono boxed text,
    `font-family: var(--brand-font-mono)`, ≥16px so the warning is readable — DESIGN.md
    older-eyes floor; the mockup's 14px is below the spine floor, so use ≥16px).
  - Reuse the existing `.chip` / `.chip--pass|--review|--fail` and `.diff-del` /
    `.diff-ins` / `.diff-equal` / `.diff-soft` spans (already in brand.css:646–714 — do
    NOT duplicate them; the gov-warning diff reuses the same del/ins treatment that
    survives forced-colors mode). Reuse the `.field-card__why*` disclosure styles (or a
    shared `__why` class) for the "Why?" block. Verdict color is ALWAYS paired with icon
    + word in markup; the stylesheet never carries meaning by color alone.

- [x] **Task 5 — validate (host venv).** Run the targeted suites while iterating
  (`.venv/Scripts/python.exe -m pytest tests/test_review_view.py tests/test_review.py
  -q`), then the full gate **once** at the end: `bash scripts/ci.sh` (format → lint →
  mypy → tests). The suite must be green. Update
  `_bmad-output/implementation-artifacts/sprint-status.yaml` story `4-5` → `review`.

## Dev Notes

### Scope boundary — the Government Warning block ONLY

Story 4.5 builds **only** the specialized Government Warning required-vs-on-label card,
fed by the **single** `checklist_items` row whose `check_key == "government_warning"`
(the Story-3.4 deterministic evaluator). It is NOT a stacked field comparison card —
the Government Warning has **no `field_comparisons` row** (Story 4.4 explicitly excludes
it; the "required" side is the §16.21 statute, carried in the engine's stored JSON
`detail` payload, not an application field). It fills the Story 4.3 `#group-gov-warning`
chevron placeholder.

**Out of scope (later stories):** the smart checklist (4.6 — the gov-warning item also
appears as a checklist line, that's 4.6's concern, not this card); the image panel +
Enhance (4.7); the disposition bar + Notes (4.8); the in-UI Help panel (4.9). Do NOT
add the gov-warning row to the field-cards list — `field_cards` already filters to rows
that carry a `field_comparison_id`, and the gov-warning row has none, so it is already
excluded; this story renders it as its own dedicated block.

### The engine already discriminated the three outcomes — the card RENDERS, never re-checks

Story 3.4 (`app/engine/checks/government_warning.py`) wrote the per-submission result
into the `government_warning` `checklist_items` row at pipeline time:

- `verdict` ∈ `{PASS, FAIL, REVIEW}` (FAIL for reworded/absent, REVIEW for
  couldnt_verify, PASS for compliant).
- `detail` = a JSON string with an `outcome` discriminator:
  - `{"outcome": "pass", "cfr_citation": "27 CFR 16.21"}`
  - `{"outcome": "reworded", "deviation": "...", "expected": "<§16.21 full text>",
    "found": "<on-label text>", "diff": [["equal","..."],["delete","..."],
    ["insert","..."],["replace","exp→found"], …], "cfr_citation": "27 CFR 16.21"}`
  - `{"outcome": "absent", "message": "Government Warning not found on any label",
    "cfr_citation": "27 CFR 16.21"}`
  - `{"outcome": "couldnt_verify", "message": "couldn't verify bold/visual styling from
    a photo", "cfr_citation": "27 CFR 16.21"}`

The presenter `government_warning_card` **parses `detail` and dispatches on `outcome`**.
It NEVER re-runs the §16.21 comparison, never imports the check module, never re-types
the warning text. The char-diff is rendered from the engine's stored `diff` opcodes —
pure presentation. (This is the AR-5 read contract: the read path reads pre-computed
rows only.) The `diff` opcode shape is `list[(op, segment)]` where
`op ∈ {equal, delete, insert, replace}` and a `replace` segment is `"<exp>→<found>"`
joined by `\u2192` (U+2192 RIGHTWARDS ARROW) — split on that arrow to recover the two
sides. JSON round-trips tuples as 2-element lists, so read each opcode as `op, segment =
pair[0], pair[1]`.

### AR-5 — the 5-second read contract

`GET /review/{id}` stays a **pure pre-computed DB read**: it reads the already-written
`checklist_items` rows (the same list it already reads for the chevron / suggested-
verdict / field cards — NO extra query) and renders. It performs **no** OCR, inference,
model import, `run_checks`, pipeline-run, or status write. Parsing a stored JSON string
and rendering diff opcodes is pure stdlib work over already-stored values — no model, no
network. Keep Story 4.1/4.3/4.4's read-path source guard green.

### Centralized contracts + project rules

- **Verdict vs disposition (contract #3).** The card is the engine register
  (PASS/REVIEW/FAIL) only — chip, char-diff, note. NO disposition word, NO
  `verdict → disposition` mapping anywhere in `review_view.py`. The card never
  pre-selects or colors a disposition control (that bar is Story 4.8).
- **Verdict not recomputed (contract #3).** The per-card verdict is the engine's
  already-stored `checklist_items.verdict` — never re-derived from the outcome (the
  outcome only selects the visual STATE; the verdict word/chip is the stored value).
  Do NOT call `verdict.rollup` here (this is a single check, not a roll-up).
- **CFR-as-data (AC4).** Citations come from `checklist_items.cfr_citation` (ruleset
  data) with the payload `cfr_citation` as fallback — NEVER a `27 CFR` literal in
  `review_view.py` or the template; grep-guard it. The §16.21 required text comes ONLY
  from the parsed `detail.expected` — never re-typed in Python (the warning string lives
  in `app/engine/rulesets/government_warning.py`, copied into the row at engine time).
- **Determinism honesty.** The "Why?" copy states this is a deterministic check (no
  LLM) — matching the mockup line "Deterministic check (no LLM)". The Government Warning
  check NEVER touches a model (project-context determinism taxonomy); the card reflects
  that.
- **A11Y — char-diff text equivalent (hard requirement).** The character diff is never
  conveyed by a colored span alone. The reworded card carries (a) a screen-reader text
  equivalent naming the difference ("Required: '…' — on label: '…'"), (b) a perceptible
  visual treatment (the existing `.diff-del` strike + `.diff-ins` underline + ≥3:1
  background change, not color alone), and (c) survival of forced-colors mode. The mono
  warning text is ≥16px (DESIGN.md older-eyes floor — the mockup's 14px `.gwtext` is
  below the spine floor; Spine wins).
- **Self-hosted only.** Every asset under `/static`, no CDN, no inline `<style>`. Spine
  (DESIGN.md `--verdict-*` tokens) wins over any mockup hex on conflict (FAIL red is
  `#b50909`, REVIEW amber `#7a5900` per `brand.css`).
- snake_case across DB ↔ Python ↔ JSON. Don't edit `auto-run/`. Validate on the **host
  venv**, not the Docker container.

### State-pattern copy (verbatim — match exactly)

- Absent fail note: **"Required Government Warning not found on the submitted images"**
  (AC2, verbatim).
- Couldn't-verify note: a calm REVIEW line — "Couldn't confirm the bold/visual styling
  from a photo — please verify by eye." (mirrors the EXPERIENCE.md "couldn't verify"
  voice; never a silent PASS, never red).
- Required-side label: **"Required (27 CFR §16.21)"** — but the `27 CFR §16.21` text is
  rendered from the `cfr_citation` DATA, the static word is just "Required (…)". (Render
  as `Required ({{ gov_warning.cfr_citation }})` so no CFR literal is hard-coded in the
  template either.)
- On-label-side label: **"On label (OCR)"**.
- Empty state (no row): "The Government Warning check has not run for this submission."
- "Why?" disclosure: reveals CFR citation + the engine `detail` rationale + that it is a
  deterministic check (no LLM).

### Project Structure Notes

- New: `templates/_gov_warning_card.html` (the single gov-warning card partial — mirrors
  `_field_card.html`).
- Edited: `app/web/review_view.py` (+`government_warning_card` builder + outcome dispatch
  + diff-opcode → span helper + gov diff-text-equivalent), `app/web/routes_review.py`
  (+`gov_warning` into the view-model — reuses the already-read `items`),
  `templates/review.html` (real gov-warning block replacing the `#group-gov-warning`
  placeholder), `static/css/brand.css` (+gov-warning block, reusing the existing `.chip`
  / `.diff-*` / `__why` rules), `tests/test_review_view.py`, `tests/test_review.py`
  (+gov-warning tests).
- Reuses: `app/verdict.py` (the verdict constants for chip mapping — PASS/REVIEW/FAIL),
  the `_CHIP_CLASS` / `_ALERT_ICON` maps + the `.chip` / `.diff-del` / `.diff-ins` /
  `.diff-equal` CSS (Story 4.3/4.4), the `checklist_items` rows the route ALREADY reads
  (no new repo query), the token-gate middleware, `base.html` shell, the `--verdict-*`
  brand tokens, the `_field_card.html` partial pattern.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.5]
- [Source: app/engine/checks/government_warning.py (the Story-3.4 evaluator — the
  `outcome` discriminator + the `detail` JSON payload shape: pass/reworded/absent/
  couldnt_verify; `_char_diff` opcode shape `(op, segment)`, replace = `exp→found`)]
- [Source: app/engine/rulesets/government_warning.py (the §16.21 text + CFR_CITATION as
  DATA — the presenter must NOT re-type these; they arrive via the stored `detail`)]
- [Source: app/web/review_view.py (Story 4.3/4.4 presenter — extend; the `_CHIP_CLASS`
  / `_ALERT_ICON` maps, the `_char_diff` + `_diff_text_equivalent` precedent, the AR-5
  source guard, the CFR-as-data grep guard)]
- [Source: app/web/routes_review.py (Story 4.3/4.4 pure-read route — extend; reuse the
  already-read `items`)]
- [Source: templates/review.html (Story 4.3/4.4 shell — replace the `#group-gov-warning`
  placeholder; keep `#group-conditional` / `#group-decide`)]
- [Source: templates/_field_card.html (the card-partial precedent — chip header, kv
  stack, diff spans, usa-sr-only text equivalent, native "Why?" details)]
- [Source: static/css/brand.css (--verdict-* tokens; the field-card / chip / diff-* /
  __why blocks at lines 531–745 to reuse + append after)]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/review-workspace.html
  (lines 258–266 — `.gwblock`/`.gwtext`/`.lab` styles; lines 443–467 — the Government
  Warning FAIL card markup: `.chead`, `Required (27 CFR §16.21)` / `On label (OCR)` mono
  stack, `diff-del`/`diff-ins`, fail note, "Why?")]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/DESIGN.md
  (verdict palette + tints; ocr-raw mono; the older-eyes type-size floor)]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/EXPERIENCE.md
  (Government Warning card — the three never-conflated outcomes; State Patterns;
  Accessibility Floor — char-diff text equivalent / forced-colors survival)]
- [Source: _bmad-output/project-context.md (four contracts; AR-5; verdict-vs-disposition;
  CFR-as-data; Government Warning NEVER calls an LLM; self-hosting)]

## Dev Agent Record

### Context Reference

- Story created and implemented in a single dev session (create-story + dev-story).

### Agent Model Used

- Amelia (DEV agent persona) on Claude Opus 4.

### Debug Log References

- Empty-state route assertion (`"has not run for this submission"`) initially failed
  even though the copy rendered: Jinja preserved a newline+indent that split the phrase
  across two lines. Fix: keep the empty-state `<p>` copy on a single source line in
  `templates/review.html`. (Diagnosed with a throwaway probe rendering the route HTML.)
- Route tests in `tests/test_review.py` render the real `review.html`, so Task 2 (route
  wiring) and Task 3 (template + partial) are coupled — validated together.

### Completion Notes List

- **Task 1 (presenter).** Added `government_warning_card(items) -> dict | None` to
  `app/web/review_view.py` plus helpers (`_gw_diff_text_equivalent`, `_gw_diff_spans`,
  `_gw_card`) and constants (`_GOV_WARNING_KEY`, the four `_GW_OUTCOME_*`, `_GW_CHIP_WORD`,
  the absent/couldnt-verify notes). It locates the `check_key == "government_warning"`
  row, parses the engine's JSON `detail` defensively (a missing/garbled payload degrades
  to a `couldnt_verify` REVIEW card — never a crash, never a silent PASS), and dispatches
  on the stored `outcome` (`pass`/`reworded`/`absent`/`couldnt_verify`). It NEVER re-runs
  the §16.21 comparison: the char-diff spans are built from the engine's stored opcodes
  (`replace` split on `\u2192`). Verdict/chip come from the stored
  `checklist_items.verdict` (contract #3 — never recomputed); the CFR citation flows from
  the row with the payload as fallback (CFR-as-data — no `27 CFR` literal in Python).
- **Task 2 (route).** `app/web/routes_review.py` now passes
  `gov_warning=review_view.government_warning_card(items)` into the `review.html` context,
  reusing the `items` already read (no new query). The route stays a pure read — the AR-5
  source guard stays green.
- **Task 3 (template).** New `templates/_gov_warning_card.html` partial (mirrors
  `_field_card.html`): chip header with icon + word, the two-row mono required/on-label
  stack with `diff-del`/`diff-ins`/`diff-equal` spans for `reworded`/`pass`, the plain
  fail note for `absent`, the calm REVIEW note for `couldnt_verify`, a `usa-sr-only` diff
  text equivalent, and a native `<details>` "Why?" disclosure. `review.html`'s inert
  `#group-gov-warning` placeholder is replaced with the real block + the calm honest empty
  state (`#group-conditional` / `#group-decide` placeholders kept for 4.6 / 4.8).
- **Task 4 (CSS).** Appended a gov-warning block to `static/css/brand.css` reusing the
  existing `.chip` / `.diff-*` / `.mono` rules and resolving all color to `--verdict-*` /
  `--brand-*` tokens. Mono warning text is 16px (DESIGN.md older-eyes floor — deliberately
  above the mockup's 14px; Spine wins). No inline `<style>`, no CDN.
- **Task 5 (validate).** Full host gate green: `bash scripts/ci.sh` → format clean, lint
  clean, mypy success (85 source files), **537 passed / 1 skipped**. Targeted suites
  (`tests/test_review_view.py tests/test_review.py`) → 78 passed (9 new presenter tests +
  6 new route tests).
- All ACs satisfied: AR-5 pure read (AC1), three never-conflated outcomes + quiet PASS
  (AC2), dedicated block / honest empty state (AC3), CFR-as-data + required text from the
  payload (AC4), mockup-fidelity with Spine tokens + "Why?" disclosure (AC5).

### File List

- `app/web/review_view.py` (modified — `government_warning_card` + outcome dispatch +
  diff-opcode → span helper + gov diff-text-equivalent; `import json`)
- `app/web/routes_review.py` (modified — `gov_warning` context key, reuses read `items`)
- `templates/_gov_warning_card.html` (new — the gov-warning card partial)
- `templates/review.html` (modified — real gov-warning block replacing the placeholder)
- `static/css/brand.css` (modified — gov-warning block, reusing `.chip` / `.diff-*` / `.mono`)
- `tests/test_review_view.py` (modified — 9 presenter tests + helpers; `import json`)
- `tests/test_review.py` (modified — 6 route tests + `_gov_warning_check` helper; `import json`)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — story 4-5 → review)

### Change Log

| Date       | Version | Description                                              | Author |
| ---------- | ------- | -------------------------------------------------------- | ------ |
| 2026-06-14 | 0.1     | Story 4.5 implemented (Government Warning comparison card) — presenter, route wiring, template partial, CSS; 15 tests added; CI green. Status → review. | Amelia |
