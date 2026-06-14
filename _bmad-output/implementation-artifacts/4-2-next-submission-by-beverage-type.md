---
baseline_commit: 3a4cb893c9b5e16a4b89d930b5b21a9256df3c30
---

# Story 4.2: Next Submission by beverage type

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an evaluator,
I want to pull the next Submission of a specific beverage type,
so that I can demonstrate the engine knows its domain (e.g. wine rules differ).

## Acceptance Criteria

1. **(Given** the beverage-type segmented filter (Any · Wine · Spirits · Beer) from
   `queue.html`, **When** a type is selected and I click **Next Submission, Then)**
   the **oldest ready** Submission **of that type** is served — the same
   deterministic oldest-first (`submitted_at`, then `id`) selection as 4.1, now
   restricted to the chosen `beverage_type`; unready statuses
   (`RECEIVED`/`PROCESSING`/`IN_REVIEW`/`DECIDED`) are still skipped silently, and the
   response 303-redirects to `/review/{id}`. With **Any** selected (the default) the
   serve is type-agnostic exactly as in 4.1. *(FR-2, AR-5, SM-1)*
2. **(And)** when **that type's** queue is empty, the screen says so **plainly** —
   the empty-type copy `"The wine queue is empty. Try Any, or check back later."`
   (the type word lower-cased into the sentence) — with the **filter staying set**
   (the selected segment keeps `aria-pressed="true"`), the **count reflecting the
   selected type** (`N waiting` of that type), rendered at **200**, **NOT** an error
   and **NOT** a redirect. The all-types empty state (Any selected, nothing ready)
   keeps the 4.1 calm State-2 copy unchanged. *(FR-2, UX-DR-2)*
3. **(And)** the filter control and the empty-type copy **match `mockups/queue.html`**
   — the segmented control (`role="group"`, Any/Wine/Spirits/Beer, exactly one
   `aria-pressed="true"` reflecting the active selection), the `.empty-note` copy
   styled per the mockup's self-hosted brand layer (added to `static/css/brand.css`,
   never inline `<style>`), and the active type carried through `GET /queue` and
   `POST /next` so the selection is sticky across the round-trip. The UI labels map
   to the stored enums (`Wine→WINE`, `Spirits→DISTILLED_SPIRITS`, `Beer→MALT_BEVERAGE`,
   `Any→` no filter); an unrecognized `type` value degrades to **Any** (no filter,
   never a 4xx/5xx). *(FR-2, UX-DR-2, UI-fidelity standard)*
4. **(And)** the by-type serve preserves every 4.1 invariant: the routes stay
   token-gated (no exemption added), `GET /queue` is a pure pre-computed DB read
   (AR-5 — no OCR/inference/model-layer call at request time), and `POST /next`
   performs only the one permitted cheap bookkeeping write
   (`READY_FOR_REVIEW → IN_REVIEW` + an `OPENED` `audit_events` row via
   `app.pipeline.status.advance`, never re-implemented, never folded into a GET),
   including the bounded lost-race re-select loop — which now re-selects within the
   **same type filter**. *(AR-5 Addendum, FR-25)*

## Tasks / Subtasks

- [x] **Task 1 — UI-label ↔ enum mapping helper (test-first, AC1, AC3).** In
  `app/web/routes_queue.py`, add a small pure module-level mapping from the mockup's
  filter **labels** to the stored `beverage_type` enums and a resolver:
  - `FILTER_LABEL_TO_TYPE: dict[str, str] = {"wine": "WINE", "spirits":
    "DISTILLED_SPIRITS", "beer": "MALT_BEVERAGE"}` (the four-label control; **Any** is
    the absence of a key).
  - `resolve_beverage_type(raw: str | None) -> str | None` — lower-case/trim `raw`,
    return the mapped enum, or `None` for `"any"`/`""`/`None`/**any unrecognized
    value** (AC3 graceful degrade — never raise, never 4xx). Keep it a pure function
    (unit-testable without a request).
  - `TYPE_TO_FILTER_LABEL: dict[str, str]` (the inverse, enum → display label
    `"Wine"/"Spirits"/"Beer"`) for re-rendering the sticky `aria-pressed` state and
    the empty-type word. Drive the template from a single resolved value so the round
    trip is lossless.
  Unit-test the resolver directly in `tests/test_queue.py`: every label (any case)
  maps to its enum, `Any`/blank/`None`/garbage → `None`. No DB, no client.

- [x] **Task 2 — `GET /queue` honors `?type=` (test-first, AC2, AC3, AC4).** Extend
  the `GET /queue` handler to read an optional `type` query param
  (`type: str | None = None` via FastAPI), resolve it with `resolve_beverage_type`,
  compute `waiting = count_ready_for_review(conn, beverage_type=resolved)`, and pass
  to the template both the live (type-scoped) `waiting` count AND the **active filter
  identity** (the resolved enum or `None`, plus the display label) so the segmented
  control renders exactly one `aria-pressed="true"` and the empty-type copy can name
  the type. Still a pure DB read (AR-5) — no new heavy-work import. Tests: `GET
  /queue?type=wine` with mixed-type ready rows shows the wine count and `Wine`
  pressed; `?type=any` and `?type=garbage` behave as Any.

- [x] **Task 3 — `POST /next` honors the selected type (test-first, AC1, AC4).**
  Extend `POST /next` to accept the selected `type` (form field `type` AND/OR query
  param — accept a `type: str | None` so the segmented submit and a `?type=` both
  work), resolve it once with `resolve_beverage_type`, and thread the resolved enum
  through the existing select-advance loop:
  `repo.get_oldest_ready_submission_id(conn, beverage_type=resolved)` inside the
  bounded re-select loop (the lost-race `continue` re-selects within the **same**
  type). On a hit: `status.advance(... "IN_REVIEW" / "OPENED" ...)` then
  `RedirectResponse(f"/review/{sid}", 303)` — **unchanged** bookkeeping write. On an
  empty (type-scoped) queue: re-render the queue at **200** with the filter still set
  and the empty-type copy — NOT a redirect, NOT an error. Tests: `POST /next?type=wine`
  serves the oldest WINE ready (a spirits row with an earlier `submitted_at` is NOT
  chosen); empty wine queue renders the empty-type State-2 (200) with `Wine` still
  pressed; the lost-race loop still re-selects within the type.

- [x] **Task 4 — `queue.html`: wire the filter + empty-type copy (test-first
  fidelity, AC2, AC3).** Edit `templates/queue.html` so the inert 4.1 placeholders
  become live, WITHOUT JavaScript:
  - The segmented filter buttons become **`type="submit"` buttons inside the Next
    Submission `<form method="post" action="/next">`**, each carrying
    `name="type" value="wine|spirits|beer"` (and an `Any` submit with `value="any"`).
    Clicking a type submits `/next` with that type — one obvious action, no JS, Enter
    still fires the primary button. Reflect the **active** selection with
    `aria-pressed="{{ 'true' if active_label == 'Wine' else 'false' }}"` (etc.),
    exactly one pressed; **Any** pressed when `active_type is None`.
  - The selection is **sticky** across the GET render too: the active label comes from
    the template context (Task 2). Because the filter buttons live in the POST form,
    re-pulling Next after a redirect-less empty render keeps the type.
  - **Empty-type copy:** when `active_type is not None` and `waiting == 0`, render the
    `.empty-note` paragraph `"The {{ active_label|lower }} queue is empty. Try Any, or
    check back later."` (e.g. *"The wine queue is empty…"*) in place of / alongside the
    generic State-2 helper. When `active_type is None` (Any) keep the unchanged 4.1
    State-2 copy. Drive the stats strip off the (type-scoped) `waiting`.
  - Keep the disabled empty-state primary button (`disabled` + `aria-disabled="true"`)
    and the deferred Phase-2 placeholder exactly as 4.1. Do NOT reintroduce the
    excluded scaffolding (`device__chrome`, `state-label`, fabricated stats).

- [x] **Task 5 — Brand CSS for `.empty-note` (AC2, AC3).** Add the `.empty-note`
  rule to `static/css/brand.css` (mirroring the mockup's `.empty-note`:
  `margin:14px auto 0; max-width:560px; font-size:15px; color:var(--brand-ink-muted);
  font-style:italic;`). The segmented-control styles already exist from 4.1 — reuse
  them; do not duplicate. No inline `<style>`, no CDN (same-origin invariant).

- [x] **Task 6 — Tests (test-first, all ACs).** Extend `tests/test_queue.py`
  (mirroring its `_client` / `connect` / `_ready` seeding pattern; seed rows of
  differing `beverage_type` + `submitted_at`). Cover:
  - **AC1 by-type serve:** seed an older `DISTILLED_SPIRITS` ready and a newer `WINE`
    ready; `POST /next?type=wine` (follow_redirects=False) → 303 `Location ==
    /review/{wine_id}` (the older spirits row is NOT chosen); `type=spirits` serves
    the spirits row; `type=any` serves the global oldest (unchanged 4.1 behavior).
  - **AC1/AC4 transition under filter:** after `POST /next?type=wine` the served WINE
    row is `IN_REVIEW` with an `OPENED` audit row; other-type rows untouched.
  - **AC2 empty-type State-2:** with ready rows of OTHER types only, `POST /next?type=wine`
    → **200** (not redirect, not error), body contains `"The wine queue is empty. Try
    Any, or check back later."` and the disabled button; `Wine` stays
    `aria-pressed="true"`.
  - **AC2 Any-empty unchanged:** zero ready rows, `POST /next` (no type) → 200 with the
    4.1 `"No submissions waiting right now."` copy and NO empty-type note.
  - **AC3 sticky GET + count:** `GET /queue?type=wine` with 2 wine + 1 spirits ready →
    `2 waiting`, `Wine` pressed, `Any` not pressed; `?type=garbage` and `?type=any` →
    `Any` pressed, global count.
  - **AC3 resolver units:** `resolve_beverage_type` table test (labels any-case →
    enum; Any/blank/None/garbage → None).
  - **AC3 fidelity:** the filter buttons are submit buttons carrying `name="type"`;
    exactly one `aria-pressed="true"` per render; `.empty-note` present only in the
    empty-type case; brand.css linked, no inline `<style>`.
  - **AC4 lost-race within type:** pre-flip the oldest WINE ready to `IN_REVIEW` (as a
    concurrent claim), seed a second WINE ready; `POST /next?type=wine` serves the
    SECOND wine row (303), never a 500; if all wine rows raced away → empty-type
    State-2 (200), `Wine` still pressed.
  - **AC4 gating preserved:** `GET /queue?type=wine` and `POST /next` with type still
    303 → `/access` without the cookie (reuse the 4.1 gate assertions).
  - **AR-5 read-path purity** (unchanged 4.1 guard still passes — no new heavy import).

- [x] **Task 7 — Validate.** Run the targeted file green first
  (`.venv/Scripts/python.exe -m pytest tests/test_queue.py -q`), then `bash
  scripts/ci.sh` ONCE at the very end (format → lint → typecheck → tests). Update
  `_bmad-output/implementation-artifacts/sprint-status.yaml`:
  `4-2-next-submission-by-beverage-type: review`.

## Dev Notes

### Scope boundary — what 4.2 adds on top of 4.1 (read carefully)

4.1 shipped the queue screen with an **inert** segmented filter (rendered for
fidelity, no working `?type=` serve, no empty-type copy) and **repository helpers
already parameterized on `beverage_type`** (called with the default `None`). 4.2 is
the small, surgical follow-up that makes the filter live:

- **No new SQL.** `get_oldest_ready_submission_id` and `count_ready_for_review`
  already take `beverage_type=...` (Story 4.1, `app/db/repositories.py:356` /
  `:379`). 4.2 only passes the resolved enum through the route — do **NOT** add new
  repo SQL or columns.
- **No JS.** The whole app is server-rendered, no build step (project-context Tech
  Stack: "NO SPA, NO build step"). Make the filter work by turning each segment into
  a `type="submit"` button inside the existing `/next` POST form carrying
  `name="type" value=...`. Clicking a type submits Next with that type. The primary
  Next Submission button submits with the currently-selected type (or `any`). This is
  the U1 "one deliberate click" interaction — auto-focus never auto-acts.
- **The review screen is STILL Story 4.3.** As in 4.1 the redirect target
  `/review/{id}` 404s until 4.3 lands; assert the 303 `Location`, never a 200 at
  target.

### The label↔enum boundary (the one real trap)

The UI control shows **Any · Wine · Spirits · Beer** (EXPERIENCE.md / mockup), but
the DB stores `beverage_type ∈ {WINE, DISTILLED_SPIRITS, MALT_BEVERAGE}`
(`app/db/repositories.py:32`, the `BeverageType` Literal; the schema CHECK is the
write-time source of truth). **"Beer" → `MALT_BEVERAGE`** and **"Spirits" →
`DISTILLED_SPIRITS`** are the non-obvious mappings — get them right. The mapping is a
small dict in the route layer (the presentation boundary); do NOT leak UI labels into
the repo/SQL (which speak enums) and do NOT hard-code the enum literals into the
template. `Any` = absence of a filter (pass `beverage_type=None`). An unrecognized
`type` degrades to `Any` (AC3) — never a 4xx; the POC is calm by contract.

### Empty-type copy is dynamic, per-type

The empty-type sentence is the **type word lower-cased into a fixed template**:
`"The {word} queue is empty. Try Any, or check back later."` (EXPERIENCE.md State
Patterns line 99; mockup `.empty-note` line 352 shows the *wine* instance). Derive
`{word}` from the active display label (`Wine`/`Spirits`/`Beer`) lower-cased — do NOT
write three literal sentences, and do NOT show it for `Any`. The all-types empty
state keeps the 4.1 `"No submissions waiting right now."` copy unchanged (do not
regress it). **Both** empty states are calm 200 renders — never an error, never a
redirect (the negative examples in EXPERIENCE.md line 71: NOT "0 results for
type=WINE").

### The 5-second read contract & the permitted POST write (AR-5) — unchanged

- `GET /queue?type=...` stays a **DB-read-only** render (the type-scoped count is one
  `SELECT COUNT(*)`); never OCR/inference/model at request time.
- `POST /next` keeps the ONE cheap bookkeeping write — the `READY_FOR_REVIEW →
  IN_REVIEW` transition + `OPENED` audit row via the existing
  `app.pipeline.status.advance(conn, sid, to_status="IN_REVIEW",
  event_type="OPENED", actor=SPECIALIST_ACTOR)` (`app/web/routes_queue.py:73`). Do
  NOT re-implement it or add a second write. The bounded lost-race re-select loop
  (4.1 code-review HIGH fix, `routes_queue.py:68`) is preserved — it now re-selects
  **within the same type filter** so a raced-away wine row yields the next wine row,
  draining to the empty-type State-2 if all wine rows are gone (never a 500).

### Reuse — do not re-implement

- **Repo helpers:** `app/db/repositories.py:356` `get_oldest_ready_submission_id` /
  `:379` `count_ready_for_review` — both already `beverage_type`-parameterized
  (parameterized SQL, never string-interpolated). Just call with the resolved enum.
- **Status / audit:** `app/pipeline/status.advance` (`OPENED` in the locked
  `AUDIT_EVENT_TYPES`); never hand-roll the transition.
- **Token gate:** the `app/main.py` `access_gate` middleware already protects
  `/queue` + `/next` (they are not in the exempt list). Adding `?type=` changes
  nothing about gating — do NOT touch the exempt list.
- **Router/template/CSS pattern:** mirror the existing `routes_queue.py` /
  `queue.html` / `brand.css` 4.1 structures; the segmented-control CSS already
  exists (`static/css/brand.css:340`). Only `.empty-note` is new CSS.
- **Test pattern:** `tests/test_queue.py` `_client(monkeypatch, tmp_path, token=...)`
  + `connect(_db_path(tmp_path))` + `_ready(...)` seeding; FastAPI `TestClient`. A
  `DECIDED` seed row needs `disposition` + `decided_at` (schema cross-column CHECK).

### UI fidelity (hard requirement)

- The filter control + empty-type copy must reproduce `mockups/queue.html`
  (segmented `role="group"`, exactly one `aria-pressed="true"`, the `.empty-note`
  italic line). Spine wins on token conflict (DESIGN.md navy `#112E51`); CSS lives in
  the self-hosted `static/css/brand.css`, linked via `base.html` — **no inline
  `<style>`**, no CDN. Exclude the mockup scaffolding (device frame, `state-label`,
  fabricated "12 reviewed"/"4.6s"/literal "38 waiting") — 4.1 already excludes them;
  do not regress.
- Accessibility floor (carried from 4.1): segment targets ≥48px (already in CSS), body
  ≥16px, visible focus ring, color never the sole signal (the segment **word** is
  always present; `aria-pressed` carries the state to AT). The empty-type note is text,
  not color. Auto-focus the primary button; it never auto-acts.
- A documented side-by-side comparison against `mockups/queue.html` (the filter control
  + the empty-type variant) is in this story's Definition of Done.

### Naming & conventions

- snake_case everywhere (Python, DB, JSON); routes lowercase, no trailing slash. The
  `type` request param is the URL-facing name the architecture's route list uses
  (`POST /next?type=`, architecture.md §317); map it internally to the snake_case
  `beverage_type` repo arg. No camelCase. No new DB columns/tables.

### Files

- EDIT `app/web/routes_queue.py` — add `FILTER_LABEL_TO_TYPE` /
  `TYPE_TO_FILTER_LABEL` / `resolve_beverage_type`; thread `type` through
  `GET /queue` + `POST /next` (count + select scoped by the resolved enum; sticky
  active label in the template context).
- EDIT `templates/queue.html` — segmented buttons become `name="type"` submits inside
  the `/next` form; sticky `aria-pressed`; dynamic per-type `.empty-note`; Any keeps
  the 4.1 State-2 copy.
- EDIT `static/css/brand.css` — add the `.empty-note` rule (mockup-styled; tokens per
  DESIGN.md).
- EDIT `tests/test_queue.py` — by-type serve / empty-type State-2 / sticky GET +
  count / resolver units / lost-race-within-type / gating preserved / fidelity.
- EDIT `_bmad-output/implementation-artifacts/sprint-status.yaml` —
  `4-2-next-submission-by-beverage-type: review`.

### Out of scope

- No `GET /review/{id}` render (Story 4.3) — the 303 target still 404s; assert the
  `Location`, not a 200 at target. No new repo SQL/columns/tables (the helpers are
  already `beverage_type`-parameterized). No JavaScript (server-rendered submit
  buttons only). No keyboard-shortcut JS (`N`/type hotkeys are Story 4.10). No
  fabricated stats. Do NOT edit `auto-run/`.

### Project Structure Notes

- Aligns with architecture.md §317 (`routes_queue.py` = `GET /queue, POST /next,
  POST /next?type=`, FR-1/FR-2). No structural variance: the change is confined to the
  existing queue route module, its template, the brand stylesheet, and the queue test
  file. No new module, no schema change.

### References

- Epic / ACs: `_bmad-output/planning-artifacts/epics.md` — Story 4.2 (lines 553–565);
  FR-2 (line 52).
- UX: `mockups/queue.html` (the segmented filter lines 297–306/354–362; the
  `.empty-note` line 352 + style line 259–265); `EXPERIENCE.md` — Voice/Tone empty-type
  copy (line 71), Component Patterns "with a beverage-type filter set, serves the
  oldest ready of that type" (line 81), State Patterns "Empty type queue …filter stays
  set" (line 99); `DESIGN.md` (navy `#112E51`, ≥48px targets).
- Architecture: `architecture.md` §317 (`routes_queue.py` route list incl.
  `POST /next?type=`), §241 (route conventions), §264–269 (audit vocab, status
  transitions, the 5s contract + permitted POST write), §394 (`POST /next` → DB read →
  render).
- Reuse seam: `app/web/routes_queue.py` (4.1 router incl. the lost-race loop),
  `app/db/repositories.py:356/:379` (the `beverage_type`-parameterized helpers),
  `app/pipeline/status.py` (`advance`/`OPENED`), `templates/queue.html` + `base.html`
  (app shell), `static/css/brand.css:340` (segmented styles), `tests/test_queue.py`
  (TestClient + seeding pattern).
- Project rules: `_bmad-output/project-context.md` (snake_case everywhere, CFR-as-data
  N/A here, the read-path/permitted-write invariant, no-CDN/self-hosted, UI fidelity).

## Dev Agent Record

### Agent Model Used

claude-opus-4 (Amelia / Senior Software Engineer, BMad DEV agent)

### Debug Log References

- Probe confirmed the JS-free segmented submit is correct in a real browser: when a
  type segment is clicked the form sends BOTH the hidden sticky `type` (DOM-first)
  AND the clicked button's `name="type"` (DOM-second); `starlette` `FormData.get`
  returns the LAST duplicate value, so the clicked segment wins (`any`+`wine` →
  resolves `WINE`). The hidden field supplies the sticky type only for the PRIMARY
  Next submit (keyboard/Enter, no segment clicked).

### Completion Notes List

- Spec was already authored (`ready-for-dev`); verified complete & correct — not
  recreated. Python route (Tasks 1–3) + the full 4.2 test suite (Task 6) were
  already in place from in-flight work; the remaining red was the inert template and
  the missing `.empty-note` CSS.
- Task 4 (`templates/queue.html`): the segmented control is now four
  `type="submit" name="type"` buttons (`any`/`wine`/`spirits`/`beer`) INSIDE the
  single `/next` POST form — JS-free per the no-build-step rule. A hidden
  `type` field carries the active selection for the primary Next button so the
  filter is sticky on a keyboard/Enter submit; a clicked segment overrides it
  (last-value-wins). Exactly one `aria-pressed="true"` is driven from
  `active_type`/`active_label`. The per-type empty-note (`.empty-note`,
  `"The {label|lower} queue is empty. Try Any, or check back later."`) renders only
  when `active_type is not none and waiting == 0`; Any-empty keeps the unchanged 4.1
  `"No submissions waiting right now."` copy + `.helper`. Deferred Phase-2
  placeholder and excluded mockup scaffolding/fabricated stats unchanged.
- Task 5 (`static/css/brand.css`): added the `.empty-note` rule mirroring the mockup
  (`margin:14px auto 0; max-width:560px; font-size:15px; color:var(--brand-ink-muted);
  font-style:italic;`). Segmented-control CSS reused from 4.1 (not duplicated). No
  inline `<style>`, no CDN.
- AR-5 read-path purity preserved (the source guard still passes — no
  OCR/LLM/pipeline-run import); the one permitted bookkeeping write on `POST /next`
  (`READY_FOR_REVIEW → IN_REVIEW` + `OPENED` via `pipeline.status.advance`) and its
  bounded lost-race re-select loop are unchanged and now re-select within the type
  filter. No new repo SQL/columns; the `beverage_type`-parameterized 4.1 helpers are
  reused as-is.
- Validation: `tests/test_queue.py` 33 passed; full `bash scripts/ci.sh` green
  (format → lint → typecheck → tests).

### File List

- `templates/queue.html` (EDIT — live segmented filter + dynamic per-type empty-note)
- `static/css/brand.css` (EDIT — add `.empty-note` rule)
- `app/web/routes_queue.py` (EDIT — resolver + `type` threaded through GET/POST; from
  in-flight work)
- `tests/test_queue.py` (EDIT — Story 4.2 by-type / empty-type / sticky / resolver /
  lost-race-within-type / gating / fidelity tests; from in-flight work)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (EDIT — 4.2 → review)

### Review Findings

Code review 2026-06-14 (DEV agent / Amelia; Blind Hunter + Edge Case Hunter +
Acceptance Auditor layers). 1 patch applied, 1 deferred, 6 dismissed.

- [x] [Review][Patch] Typed-empty State-2 H1 diverged from the mockup and duplicated
  the per-type sentence [templates/queue.html:30-37] — the empty typed render set the
  `<h1>` to "The {type} queue is empty." AND repeated the same sentence in
  `.empty-note`, so the phrase appeared twice and the heading diverged from
  `mockups/queue.html` (which keeps the H1 generic and names the type ONLY in the
  note). AC3 is a hard UI-fidelity requirement. FIX: the typed-empty H1 now stays the
  generic mockup line "No submissions waiting right now." in both Any-empty and
  typed-empty cases; the type-specific sentence lives solely in `.empty-note` (the
  AC2/AC3-named artifact, unchanged). +1 regression test
  (`test_next_empty_type_heading_is_generic_note_only_says_type`) pins the generic H1
  + exactly-once phrase.
- [x] [Review][Defer] `.empty-note` font-size 15px below the ≥16px body floor
  [static/css/brand.css:417] — deferred, spec-vs-floor tension the story spec already
  adjudicated (Task 5 mandates 15px verbatim from the mockup); logged in
  deferred-work.md for Diane's call.

Dismissed (6): (1) Blind HIGH "filter chips open a review instead of filtering" —
working as designed; AC1/Task 4/Debug Log specify the segment IS a `type="submit"`
that serves `/next` of that type (the U1 one-click). (2) Blind/Edge "duplicate `type`
key drops the clicked segment" — empirically disproved with a real urlencoded body
(`type=any&type=wine` binds `wine`; Starlette last-duplicate-wins, the clicked segment
rendered after the hidden field wins); the Debug Log claim holds for real browsers (the
contradicting test-client result was an httpx list-of-tuples serialization artifact).
(3) `type_q` query alias "dead" — Task 3 explicitly requires accepting `type` from BOTH
form and query; both paths are tested. (4) Empty-string `type=""` form value — FastAPI
normalizes `Form("")`→default `None` by design ⇒ calm degrade-to-Any; resolver also
maps `""`→None. (5) aria-pressed-exactly-one / label round-trip / lost-race loop —
walked and confirmed sound. (6) Label set duplicated (Python dict + template strings) —
accepted POC simplicity; the template legitimately speaks display labels.
