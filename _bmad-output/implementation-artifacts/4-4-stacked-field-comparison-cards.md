---
baseline_commit: 5ff3d32c653fee62c612a7ef267bdc6691897dea
---

# Story 4.4: Stacked field comparison cards

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want each application field stacked above its OCR/LLM-extracted value with the
discrepancy highlighted,
so that I confirm a match in a single glance and the real problems jump out.

## Acceptance Criteria

1. **(Given** the Review Workspace served by `GET /review/{id}` (Story 4.3 shell,
   submission `IN_REVIEW`), **When** the right-column field comparison renders, **Then)**
   each matchable field is a **card** with the **application value stacked ABOVE the
   OCR/LLM value (vertical, never side-by-side)**, each card carrying its
   **right-aligned verdict chip (icon + word + color)**, rendered as a pure
   **pre-computed DB read** (AR-5 — no OCR / inference / model-layer call, no
   `run_checks`, on the request path; the cards read the already-written
   `field_comparisons` + `checklist_items` rows). The route stays token-gated by the
   existing middleware (no exemption added). *(FR-3, AR-5)*
2. **(And)** the cards render the **three core states** exactly per
   `mockups/review-workspace.html` + EXPERIENCE.md State Patterns, color always paired
   with icon + word: **match** (quiet — 1px border, green `✓ match` chip, both raw
   values visible); **mismatch** (loud — 6px fail left-bar + fail tint + **character
   diff on the differing span only**, `✕ FAIL` chip); **soft/normalized** (amber bar +
   tint + a plain note "Capitalization differs; the text otherwise matches.", an
   amber-diff span, **never red**, `⚠ REVIEW` chip). The verdict word + chip class come
   from the per-field engine result (the `checklist_items.verdict` joined to the
   field's `field_comparisons.match_status`), never recomputed in the template.
   *(FR-3, FR-18 surface, UX-DR-9, DESIGN.md verdict palette, A11Y color-never-alone)*
3. **(And)** the **distinct non-core states** render per EXPERIENCE.md State Patterns,
   each REVIEW (never a false FAIL): **not-found** (element genuinely absent on the
   label — `match_status = MISSING`) shows "Not found on label" in the OCR slot with
   REVIEW; **OCR-unreadable** (`match_status = UNVERIFIABLE`) shows "Couldn't read this
   field reliably from the photo — please verify by eye." REVIEW (garbage rendered as a
   diff would wrongly imply the *label* is wrong — so no diff is drawn); **blank
   application** (application value empty but the label has text) shows the OCR value
   with "No value submitted in the application for this field." REVIEW. *(UX-DR-9,
   EXPERIENCE.md State Patterns)*
4. **(And)** cards **sort problems first**: mismatches and not-founds (and any
   REVIEW/FAIL) float to the top under a "Field comparison — problems first" heading;
   clean matches sink under a "Verified automatically" heading — matching the mockup's
   two-section ordering. Sort order is stable and deterministic (a fixed verdict
   severity rank, then the ruleset/`field_key` order) so the same submission always
   renders the same order. *(UX-DR-9, EXPERIENCE.md "Mismatches and not-founds sort to
   top; matches sink")*
5. **(And)** each card carries a **"Why?" accordion** (a native `<details>`/`<summary>`,
   no JS) revealing the **CFR citation** (from `checklist_items.cfr_citation`, rules as
   data — never a hard-coded literal in the template/presenter), the **raw OCR/LLM
   value**, the **extraction provenance** (`extracted_source` — `ocr:<engine>` /
   `llm:<model_id>`, read from the `v_field_comparisons` view, the DERIVED label, never
   a re-derived string), and the **verdict rationale** (`checklist_items.detail`). The
   cards reproduce `mockups/review-workspace.html` (layout / states / copy) with tokens
   resolving to `static/css/brand.css` `--verdict-*` vars (Spine wins over the mockup's
   inline hex), no inline `<style>`, no CDN; a side-by-side check against the mockup is
   in the DoD. The cards fill the Story 4.3 chevron placeholder sections
   (`#group-identity`, `#group-mandatory-text`) so the chevron anchors still resolve.
   *(FR-3, UI-fidelity standard, CFR-as-data, contract self-hosting)*

## Tasks / Subtasks

- [x] **Task 1 — field-comparison read helper (test-first, AC1/AC5).** In
  `app/db/repositories.py`, add a typed read over the **`v_field_comparisons` view**
  (the view that DERIVES `extracted_source` from the source FK — read the view, never
  re-derive the provenance string; raw SQL stays in the data boundary):
  - A Pydantic `FieldComparison(BaseModel)` mirroring the view columns the cards need:
    `id: int`, `submission_id: int`, `field_key: str`, `application_value: str | None`,
    `extracted_value: str | None`, `match_status: str | None`, `similarity: float |
    None`, `source_ocr_result_id: int | None`, `source_llm_result_id: int | None`,
    `extracted_source: str | None` (the view-derived `ocr:<engine_name>` /
    `llm:<model_id>` label), `created_at: str` (snake_case, 1:1 with the columns; enum
    columns stay plain `str`, the DB `CHECK` is the source of truth — matches the
    `ChecklistItem` precedent from Story 4.3).
  - `list_field_comparisons(conn, submission_id) -> list[FieldComparison]` —
    `SELECT * FROM v_field_comparisons WHERE submission_id = ? ORDER BY id` (stable
    insertion = ruleset order). Returns `[]` when the submission has none.
  - Tests in `tests/test_repositories.py`: rows returned in id order; empty list for a
    submission with no comparisons; `extracted_source` derives `ocr:<engine_name>` for
    an OCR-sourced row and `llm:<model_id>` for an LLM-sourced row and `None` when
    neither FK is set; `match_status` round-trips the stored UPPER_SNAKE string;
    `application_value`/`extracted_value` round-trip the RAW (un-normalized) stored text.

- [x] **Task 2 — field-card presenter (test-first, AC2/AC3/AC4/AC5).** Extend the pure
  presenter `app/web/review_view.py` (the read-only module — keeps importing only
  `app.verdict` + the read models; NOTHING from the OCR/LLM/engine-run layers; the AR-5
  source guard from Story 4.3 must stay green). Add the field-card view-model builders,
  all snake_case:
  - **Join checklist ↔ comparison.** A `field_cards(items, comparisons) -> list[dict]`
    that joins each FIELD_MATCH `checklist_items` row to its `field_comparisons` row via
    `checklist_items.field_comparison_id == field_comparisons.id` (the existing FK). Only
    rows that HAVE a `field_comparison_id` become field cards here — the Government
    Warning (4.5), the checklist (4.6) and flag-only/positional checks (no comparison
    row) are NOT field cards and are excluded. Each card dict carries:
    `{"field_key", "field_label", "cfr_citation", "verdict", "chip_class", "icon",
    "chip_word", "state", "application_value", "extracted_value", "extracted_source",
    "detail", "diff_application", "diff_extracted", "note", "sort_rank"}`.
  - **State derivation (DATA-driven, AC2/AC3).** Derive `state ∈ {match, mismatch,
    soft, not_found, unreadable, blank_application}` from the pair
    (`checklist_items.verdict`, `field_comparisons.match_status`, whether
    `application_value` is blank) using a small explicit mapping — NOT scattered
    `if`s buried in template logic:
    - `match_status == MATCH` + verdict `PASS` ⇒ `match` (quiet, green `✓ match`).
    - `match_status == MATCH`/`MISMATCH` + verdict `REVIEW` (the soft/normalized class —
      values normalize-equal but differ raw, e.g. case) ⇒ `soft` (amber, `⚠ REVIEW`,
      the "Capitalization differs; the text otherwise matches." note, amber diff).
    - `match_status == MISMATCH` + verdict `FAIL` ⇒ `mismatch` (loud, red `✕ FAIL`, red
      char-diff on the differing span only).
    - `match_status == MISSING` ⇒ `not_found` (REVIEW or FAIL per the joined
      `checklist_items.verdict` — a missing mandatory element is FAIL, a missing
      conditional is REVIEW per the engine's already-computed verdict; the OCR slot reads
      "Not found on label"; NO diff drawn).
    - `match_status == UNVERIFIABLE` ⇒ `unreadable` (REVIEW; OCR slot reads "Couldn't
      read this field reliably from the photo — please verify by eye."; NO diff — a
      garbage diff would wrongly imply the label is wrong).
    - `application_value` blank but `extracted_value` present ⇒ `blank_application`
      (REVIEW; note "No value submitted in the application for this field."; NO diff —
      no baseline to diff against).
    - The chip word/icon/class come from the **verdict** via a DATA map reusing the
      Story 4.3 `_ALERT`-style tables (PASS `✓`/`usa`-success-equivalent card class,
      REVIEW `⚠`, FAIL `✕`) and the per-state card class (`field-card--match` /
      `--mismatch` / `--soft`); never recompute severity here.
  - **Character diff (AC2).** Add a SMALL local char-diff helper that, for the
    `mismatch` and `soft` states ONLY, returns two HTML-safe span sequences (application
    side + extracted side) marking the differing span — built on the **stdlib**
    `difflib.SequenceMatcher` (no new dependency; mirrors the Story 3.4 Government
    Warning char-diff approach). Emit structured segments (`[{"text", "kind"}]` where
    `kind ∈ {equal, del, ins, soft}`) the template renders as
    `diff-del`/`diff-ins`/`diff-soft` spans — and the template ALSO renders a
    **screen-reader text equivalent** naming the difference (A11Y: the diff is never a
    colored span alone — it carries a text equivalent surviving forced-colors mode). Do
    NOT pass any OCR text into a model — this is pure deterministic string diffing on
    already-stored values (VLM-only purity is irrelevant here; no model is touched).
  - **Sort (AC4).** `sort_rank` = a fixed severity rank (`FAIL` < `REVIEW`/not-found <
    `PASS`) so a stable sort floats problems first; ties break on the original
    ruleset/`field_key` order (the list is already in id order). Expose
    `field_cards_sorted(...)` (or have `field_cards` return pre-sorted) AND a partition
    helper or flag so the template can render the two mockup sections ("problems first"
    vs "verified automatically") — a card is "problem" when its verdict is not `PASS`.
  - **Field label + citation as DATA.** The human `field_label` (e.g. "Brand Name",
    "Class / Type", "Alcohol Content", "Net Contents", "Name & Address (Bottler)") comes
    from `checklist_items.label` (already carried as ruleset data, Story 3.2) — fall back
    to a title-cased `field_key` only when null. `cfr_citation` comes straight off
    `checklist_items.cfr_citation` — NEVER a CFR literal written in Python (CFR-as-data;
    a grep-guard test asserts no `27 CFR` literal in `review_view.py`).
  - Tests in `tests/test_review_view.py`: the join pairs a checklist row to its
    comparison via `field_comparison_id`; a checklist row WITHOUT a `field_comparison_id`
    (Gov Warning / flag-only) produces NO card; each of the six states derives correctly
    from its (`verdict`, `match_status`, blank-application) inputs; the chip word/icon
    matches the verdict (icon + word always present); the char-diff marks only the
    differing span for `mismatch`/`soft` and is ABSENT for `match`/`not_found`/
    `unreadable`/`blank_application`; `extracted_source` flows through unchanged from the
    view; sort floats FAIL/REVIEW/not-found above PASS with a stable tie-break; the
    AST/source guard still asserts `review_view` imports neither `run_checks` nor the
    ocr/llm adapters nor `pipeline.run`; a grep/AST guard asserts no `27 CFR` literal in
    `review_view.py`.

- [x] **Task 3 — wire the route read (test-first, AC1).** In
  `app/web/routes_review.py`, extend the existing `GET /review/{submission_id}` handler
  to also read `repo.list_field_comparisons(conn, submission_id)` and build the
  field-card view-model via `review_view.field_cards(...)`, passing it to
  `review.html` (e.g. a `field_cards` / `field_cards_problems` + `field_cards_clean`
  context). The route stays a **pure read** — NO new OCR/inference/model import, NO
  `run_checks`, NO status write (the read-path source guard from Story 4.3 must stay
  green). A missing id still ⇒ calm 404.
  - Tests in `tests/test_review.py`: a seeded `IN_REVIEW` spirits submission with a
    full FIELD_MATCH checklist + comparisons renders 200 with each field card's label,
    application value (above), and OCR value (below); a mismatch field shows the `FAIL`
    chip word + a `diff-del`/`diff-ins` span; a soft/normalized field shows the `REVIEW`
    chip + the "Capitalization differs" note + an amber `diff-soft` span and NO red
    diff; a MISSING field shows "Not found on label" + REVIEW; an UNVERIFIABLE field
    shows the "Couldn't read this field reliably" copy + REVIEW + no diff; a
    blank-application field shows the "No value submitted in the application" copy; the
    problems-first card precedes the clean cards in the rendered HTML (sort assertion);
    the "Why?" `<details>` carries the CFR citation + `extracted_source` + detail; the
    route remains token-gated (no-cookie ⇒ redirect to `/access`); the read-path source
    guard (no `pytesseract` / `adapters.ocr` / `adapters.llm` / `pipeline.run` /
    `run_checks` import reachable from the route) stays green.

- [x] **Task 4 — `review.html` field cards (AC1–AC5).** In `templates/review.html`,
  REPLACE the inert `#group-identity` and `#group-mandatory-text` placeholder sections
  with the real field cards (keep the placeholder sections for `#group-gov-warning`
  [Story 4.5], `#group-conditional` [4.6] and `#group-decide` [4.8] — those stories fill
  them). No inline `<style>`, no JS; tokens via `brand.css`:
  - A "Field comparison — problems first" `section-h` then the problem cards, then a
    "Verified automatically" `section-h` then the clean cards (the mockup's two-section
    order). Each card is a `<div class="field-card field-card--{{ card.state }}">` with:
    - a header (`.field-card__head`) — the `field_label` (700/16px) + the muted
      `cfr_citation` + the right-aligned `<span class="chip chip--{{ verdict|lower }}">`
      carrying `{{ icon }}` + `{{ chip_word }}` (icon + word always present).
    - the vertical stacked values (`.field-card__kv`) — "APPLICATION VALUE" label above
      the `application_value` (19px), then "ON LABEL (OCR)" / source label above the
      `extracted_value` in `mono` (17px). For `mismatch`/`soft`, render the char-diff
      segments as `diff-del`/`diff-ins`/`diff-soft` spans PLUS a visually-hidden
      screen-reader text equivalent naming the difference. For `not_found` /
      `unreadable` / `blank_application`, render the state's plain note in the OCR slot
      instead of a diff.
    - the state note (`.field-card__note`) where the state carries one (soft / mismatch
      / not_found / unreadable / blank_application) — calm, plain language.
    - a "Why?" `<details class="field-card__why"><summary>Why?</summary>…</details>`
      revealing the CFR citation, the raw extracted value, `extracted_source`, and the
      `detail` rationale (native disclosure, no JS).
  - Reproduce the mockup copy/structure; Spine tokens win on color.
- [x] **Task 5 — `brand.css` field-card styles (AC2/AC3/AC5, no inline style).** Append
  to `static/css/brand.css` (after the Review-shell block) the field-card rules —
  same-origin, tokens only (mirror the mockup `.card`/`.chip`/`.kv`/`.diff-*`/`.note`/
  `.why` but resolve color to `--verdict-*`):
  - `.field-card` base (surface, radius `--md`, padding, margin) +
    `.field-card--match { border: 1px solid var(--border); }`,
    `.field-card--mismatch { background: var(--verdict-fail-bg); border-left: 6px solid
    var(--verdict-fail); }`,
    `.field-card--soft { background: var(--verdict-review-bg); border-left: 6px solid
    var(--verdict-review); }`, and a calm neutral treatment for `not_found` /
    `unreadable` / `blank_application` (REVIEW-toned but not loud-red).
  - `.chip` (pill, icon+word) + `.chip--pass`/`--review`/`--fail` from the `--verdict-*`
    tokens; `.field-card__kv` (vertical stack — the `.k` uppercase muted label, the `.v`
    19px value, `.v.mono` 17px); the char-diff spans `.diff-del` (line-through),
    `.diff-ins` (bold), `.diff-soft` (amber) with a **≥3:1 background change + a marker
    that survives forced-colors mode** (not color alone — A11Y char-diff text
    equivalent); `.field-card__note` (calm); `.field-card__why` (the dashed-top "Why?"
    disclosure). Verdict color is ALWAYS paired with icon + word in markup; the
    stylesheet never carries meaning by color alone.
- [x] **Task 6 — validate (host venv).** Run the targeted suites while iterating
  (`test_repositories.py`, `test_review_view.py`, `test_review.py`), then the full gate
  **once** at the end: `bash scripts/ci.sh` (format → lint → mypy → tests). The suite
  must be green. Update
  `_bmad-output/implementation-artifacts/sprint-status.yaml` story `4-4` → `review`.

## Dev Notes

### Scope boundary — FIELD_MATCH comparison cards ONLY

Story 4.4 builds **only** the stacked field comparison cards for the **matchable**
fields — those FIELD_MATCH `checklist_items` rows that carry a `field_comparison_id`
linking to a `field_comparisons` row (brand_name, class/type [wine/malt are FIELD_MATCH;
spirits class/type is the HYBRID `class_type_designation` which also writes a comparison
row via Story 3.6], alcohol_content, net_contents, name_address, grape_varietal,
fanciful_name, etc.). It fills the Story 4.3 chevron placeholder sections
`#group-identity` and `#group-mandatory-text`.

**Out of scope (later stories):** the **Government Warning** comparison card (Story 4.5
— a special required-vs-on-label layout, NOT a `field_comparisons` row); the **smart
checklist** (Story 4.6); the **flag-only / positional** checks (Story 3.7/3.8 — no
comparison row, REVIEW-only, surface in the checklist/conditional group, not as field
cards); the **image panel + Enhance** (4.7); the **disposition bar + Notes** (4.8). A
checklist row WITHOUT a `field_comparison_id` MUST NOT become a field card.

### AR-5 — the 5-second read contract

`GET /review/{id}` stays a **pure pre-computed DB read**: it reads the already-written
`field_comparisons` (via the `v_field_comparisons` view) + `checklist_items` rows and
renders. It performs **no** OCR, inference, model import, `run_checks`, pipeline-run, or
status write. The char-diff is pure stdlib `difflib` string work over already-stored
values — no model, no network. Keep Story 4.1/4.3's read-path source guard green.

### Centralized contracts + project rules

- **Verdict vs disposition (contract #3).** The cards are the engine register
  (PASS/REVIEW/FAIL) only — chips, char-diff, notes. NO disposition word, NO
  `verdict → disposition` mapping anywhere in `review_view.py`. The card never
  pre-selects or colors a disposition control (that bar is Story 4.8).
- **Roll-up (contract #3).** Don't re-derive verdict severity in the card presenter;
  the per-card verdict is the engine's already-stored `checklist_items.verdict`. The
  suggested-verdict alert (Story 4.3) already rolls these up via `app/verdict.py:rollup`.
- **Normalization (contract #2).** The soft/normalized state EXISTS because
  `app/normalize.py` made "STONE'S THROW" == "Stone's Throw" at engine time (Story 3.3),
  yielding a REVIEW with raw values that differ — the card SHOWS the raw values (the DB
  stores raw `application_value`/`extracted_value`) and explains the case difference. Do
  NOT re-normalize in the presenter; just render raw + the engine's verdict.
- **CFR-as-data.** Citations come from `checklist_items.cfr_citation` (ruleset data),
  NEVER a `27 CFR` literal in `review_view.py` or the template — grep-guard it.
- **Provenance one-source-of-truth.** `extracted_source` is the DERIVED
  `v_field_comparisons.extracted_source` (`ocr:<engine_name>` / `llm:<model_id>`) — read
  the view, never reconstruct the label from the FKs in Python.
- **Read boundary (AR-13).** The new `FieldComparison` read model validates at the read
  boundary like `Submission` / `LabelImage` / `ChecklistItem`; raw SQL stays in
  `app/db/repositories.py`.
- **Self-hosted only.** Every asset under `/static`, no CDN, no inline `<style>`. Spine
  (DESIGN.md `--verdict-*` tokens) wins over any mockup hex on conflict (e.g. PASS green
  is `#216E29` per `brand.css`, not the mockup's `#2E8540`).
- snake_case across DB ↔ Python ↔ JSON; UI labels map to enums/`field_key` in the
  presenter, never by mutating stored values. Don't edit `auto-run/`. Validate on the
  **host venv**, not the Docker container.

### A11Y — char-diff text equivalent (hard requirement)

The character diff is never conveyed by a colored span alone. Each diffed card carries
(a) a screen-reader text equivalent naming the difference ("Required: 'GOVERNMENT
WARNING' — on label: 'Government Warning'" style for fields: "Application: 'Stone's
Throw' — on label: 'STONE'S THROW'"), (b) a perceptible visual treatment (bold + ≥3:1
background change + marker, not a thin underline or color alone), and (c) survival of
Windows High Contrast / forced-colors mode. Body ≥16px, comparison values 19px (mono
17px) per the accessibility floor.

### State-pattern copy (verbatim from EXPERIENCE.md / mockup — match exactly)

- Soft/normalized note: **"Capitalization differs; the text otherwise matches."**
- Not-found OCR slot: **"Not found on label"** (REVIEW/FAIL per the engine verdict).
- OCR-unreadable: **"Couldn't read this field reliably from the photo — please verify by
  eye."** (REVIEW, never FAIL).
- Blank application: **"No value submitted in the application for this field."** (REVIEW).
- Section headers: **"Field comparison — problems first"** and **"Verified
  automatically"**.
- "Why?" accordion: reveals CFR citation + raw OCR/LLM value + `extracted_source` +
  verdict rationale.

### Project Structure Notes

- New: nothing net-new module-wise — extends the Story 4.3 files.
- Edited: `app/db/repositories.py` (+`FieldComparison` model + `list_field_comparisons`
  over `v_field_comparisons`), `app/web/review_view.py` (+`field_cards` join/state/diff/
  sort builders + char-diff helper), `app/web/routes_review.py` (+`list_field_comparisons`
  read into the view-model), `templates/review.html` (real cards replacing the
  `#group-identity` / `#group-mandatory-text` placeholders), `static/css/brand.css`
  (+field-card block), `tests/test_repositories.py`, `tests/test_review_view.py`,
  `tests/test_review.py` (+field-card tests).
- Reuses: `app/verdict.py` (the verdict enum/constants for chip mapping), the
  `v_field_comparisons` view (Story 3.1/3.3), the `field_comparison_id` FK on
  `checklist_items` (Story 3.2/3.3), `difflib` (stdlib, the Story 3.4 char-diff
  precedent), the token-gate middleware, `base.html` shell + header, the `--verdict-*`
  brand tokens (Story 4.3).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.4]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/EXPERIENCE.md
  (Field comparison card; State Patterns — Match/Soft-normalized/Mismatch/Not-found/
  OCR-unreadable/Blank-application; Accessibility Floor — char-diff text equivalent)]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/DESIGN.md
  (verdict palette + tints; comparison-value 19px / ocr-raw mono 17px; field-card
  match/mismatch/soft)]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/review-workspace.html
  (lines 439–537 — field cards, chip/kv/diff/note/why markup)]
- [Source: app/db/schema.sql (field_comparisons table + v_field_comparisons view; the
  checklist_items.field_comparison_id FK)]
- [Source: app/db/repositories.py (ChecklistItem precedent; insert_field_comparison
  raw-value storage; the read-boundary pattern)]
- [Source: app/web/review_view.py (Story 4.3 presenter — extend; AR-5 source-guard;
  verdict→chip mapping precedent)]
- [Source: app/web/routes_review.py (Story 4.3 pure-read route — extend)]
- [Source: templates/review.html (Story 4.3 shell — replace #group-identity /
  #group-mandatory-text placeholders)]
- [Source: static/css/brand.css (--verdict-* tokens; Review-shell block to append after)]
- [Source: docs/data-dictionary.md (field_key registry §; extracted_source view-derived)]
- [Source: _bmad-output/project-context.md (four contracts; AR-5; verdict-vs-disposition;
  CFR-as-data; normalize raw-vs-compared; self-hosting)]

## Dev Agent Record

### Context Reference

- Story created and implemented in a single dev session (create-story + dev-story).

### Agent Model Used

- Amelia (DEV agent persona) on Claude Opus 4.

### Debug Log References

- RED→GREEN per task. Task 1 RED: `AttributeError: module 'app.db.repositories' has
  no attribute 'list_field_comparisons'`. Task 2 RED: 16 presenter tests failed
  (undefined `field_cards`). Task 3 RED: 8 route tests failed (cards not rendered).
- One HTML-escaping fix in the route tests: Jinja2 autoescapes `'` → `&#39;`, so the
  match test now asserts both raw values via `body.count(value) >= 2` (apostrophe-free
  value), and the unreadable test asserts the note minus the leading "Couldn't"
  apostrophe word. Escaping is correct, safe output — the page renders the apostrophe.
- One mypy fix: `cards.sort(key=...)` over a `list[dict[str, object]]` — the key now
  uses `typing.cast(int, c["sort_rank"])`.

### Completion Notes List

- **Task 1** — `FieldComparison(BaseModel)` + `list_field_comparisons(conn, sid)` read
  the `v_field_comparisons` view (`SELECT * … ORDER BY id`); validates at the read
  boundary (AR-13). `extracted_source` is the view-DERIVED `ocr:<engine>`/`llm:<model>`
  label — never re-derived in Python.
- **Task 2** — `field_cards(items, comparisons)` joins each `checklist_items` row to its
  `field_comparisons` row via `field_comparison_id`; rows without that FK (Gov Warning /
  flag-only) produce no card. State precedence (blank_application → unreadable →
  not_found → soft → mismatch → match) is an explicit derivation, not template `if`s.
  Per-card verdict is the engine's stored `checklist_items.verdict`, never recomputed
  (contract #3). Char-diff via stdlib `difflib.SequenceMatcher` (soft = amber-only,
  mismatch = del/ins) — drawn for soft/mismatch only. Citations come from
  `cfr_citation` (CFR-as-data); a grep-guard asserts no `27 CFR` literal in the module.
- **Task 3** — `GET /review/{id}` also reads `list_field_comparisons`, builds the cards
  and partitions into `field_cards_problems` / `field_cards_clean` for the template.
  Stays a pure read (AR-5 source guard green); missing id ⇒ calm 404.
- **Task 4** — `templates/review.html` replaces the `#group-identity` /
  `#group-mandatory-text` placeholders with the field-card region (both chevron anchors
  preserved); cards render via the `templates/_field_card.html` partial — stacked
  application-over-extracted values, verdict chip (icon + word), diff spans, state note,
  and a native `<details>` "Why?" disclosure. No inline `<style>`, no JS.
- **Task 5** — `static/css/brand.css` gains the `.field-card*` / `.chip*` / `.diff-*`
  block; all color resolves to the shared `--verdict-*` tokens; diff spans pair color
  with underline/strike so meaning survives forced-colors mode.
- **Task 6** — `bash scripts/ci.sh` green: format + lint clean, mypy clean (85 files),
  **514 passed / 1 skipped**.

### File List

- `app/db/repositories.py` (M) — `FieldComparison` model + `list_field_comparisons`.
- `app/web/review_view.py` (M) — `field_cards` join/state/diff/sort builders + helpers.
- `app/web/routes_review.py` (M) — read field_comparisons, partition cards into context.
- `templates/review.html` (M) — field-card region replacing the two placeholders.
- `templates/_field_card.html` (A) — single field-card partial.
- `static/css/brand.css` (M) — field-card / chip / diff styles.
- `tests/test_repositories.py` (M) — `list_field_comparisons` tests.
- `tests/test_review_view.py` (M) — `field_cards` presenter tests.
- `tests/test_review.py` (M) — route-level field-card render tests.
