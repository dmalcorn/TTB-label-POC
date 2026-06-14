# Story 4.8: Disposition action bar & Notes

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist,
I want to record exactly one disposition with a reason when needed,
so that I commit the official decision and the engine never makes it for me.

## Acceptance Criteria

(Verbatim from `epics.md` Story 4.8 — *(FR-6, UX-DR-14, AR-3 #4, AR-14)*)

1. **AC1 — bar renders, none pre-selected, separate enum.** Given the bottom Notes +
   Disposition action bar, when it renders, then the three controls — **Approve**
   (filled navy), **Needs Correction** (outline navy), **Reject** (outline red) — show
   with **none pre-selected**, and `disposition` is a separate enum from `engine_verdict`
   with **no function mapping one to the other** (AR-3 #4). No verdict colour on a
   disposition control; no verdict pre-selects/defaults a control.

2. **AC2 — Notes required-gate.** Notes are **required** for Needs Correction / Reject
   (soft-gate), **optional** for Approve; recording an **Approve while REVIEW items are
   open** prompts a **calm confirm modal**.

3. **AC3 — draft persistence + disposition write.** The in-progress Notes are persisted
   as `review_progress.draft_notes` via `POST /review/{id}/progress` (so they survive a
   mid-review reload, AR-14); `POST /review/{id}/disposition` persists the disposition +
   `decided_at`, **promotes `draft_notes` to `submissions.decision_notes`**, the bar
   **disables on submit** to prevent double-submit, and on success **returns to Queue**
   with a brief **"Recorded — Undo"**.

4. **AC4 — Undo.** The **"Recorded — Undo"** affordance calls `POST /review/{id}/undo`,
   which clears `disposition`/`decided_at`/`decision_notes`, applies the single bounded
   backward transition **`DECIDED → READY_FOR_REVIEW`**, writes an **`UNDONE`** audit
   event, and **reopens** the item with the **retained `review_progress` ticks + draft
   Notes restored**; after it dismisses the disposition is final for the POC.

5. **AC5 — save-failure honesty.** On save failure the screen **stays put**, **re-enables
   the bar**, shows an **honest error**, and **retains Notes + tick-state** (the
   `review_progress` row is intact).

6. **AC6 — mockup fidelity.** The action bar **matches `mockups/review-workspace.html`**,
   side-by-side check in the DoD.

## Tasks / Subtasks

- [ ] **Task 1 — `review_progress.draft_notes` upsert (AC3, AR-14).** (AC: 3, 5)
  - [ ] Add `repo.set_draft_notes(conn, submission_id, *, draft_notes)` in
        `app/db/repositories.py` — an upsert mirroring `set_check_tick`'s `ON CONFLICT`
        keyed on `submission_id`, writing only `draft_notes` (preserving any existing
        `ticked_check_keys`), bumping `updated_at`. Does NOT commit (the `connect()`
        context manager commits on clean exit). No new column — `draft_notes` already
        exists (schema.sql, declared by 4.6 for this story).
  - [ ] Add `repo.get_draft_notes(conn, submission_id) -> str | None` (reads via the
        existing `get_review_progress`; `None` when no row).
- [ ] **Task 2 — disposition + undo write helpers (AC3, AC4).** (AC: 3, 4)
  - [ ] Add `repo.record_disposition(conn, submission_id, *, disposition, decision_notes,
        decided_at)` — a single `UPDATE submissions SET disposition=?, decision_notes=?,
        decided_at=? WHERE id=?`. **Status is NOT written here** — the lifecycle
        transition is owned by `app/pipeline/status.advance` (see Task 3). Does NOT commit.
  - [ ] Add `repo.clear_disposition(conn, submission_id)` — `UPDATE submissions SET
        disposition=NULL, decided_at=NULL, decision_notes=NULL, correction_due_at=NULL
        WHERE id=?`. Does NOT commit. (Clears `correction_due_at` too so the schema
        cross-column CHECK stays satisfiable — it is only valid for NEEDS_CORRECTION.)
- [ ] **Task 3 — the lone bounded backward transition `DECIDED → READY_FOR_REVIEW`
      (AC4).** (AC: 4)
  - [ ] Add `status.reopen(conn, submission_id, *, actor, note=None)` in
        `app/pipeline/status.py` — the **web-layer-only** backward step. It must:
        verify `from_status == "DECIDED"` (else `ValueError`), `repo.update_status(...,
        "READY_FOR_REVIEW")`, and `repo.insert_audit_event(... event_type="UNDONE",
        from_status="DECIDED", to_status="READY_FOR_REVIEW", actor=actor, note=note)`,
        then `conn.commit()`. `UNDONE` is already in `AUDIT_EVENT_TYPES`. Do NOT touch
        `advance` (forward-only) — add a sibling function with its own guard.
  - [ ] Keep the docstring note that `advance` is forward-only and `reopen` is the single
        bounded backward transition (Addendum A).
- [ ] **Task 4 — disposition route `POST /review/{id}/disposition` (AC1, AC3, AC5).**
      (AC: 1, 3, 5)
  - [ ] In `app/web/routes_review.py`, add `POST /review/{submission_id}/disposition`
        with form fields `disposition: str = Form(...)`, `notes: str = Form("")`. Validate
        `disposition ∈ {APPROVED, NEEDS_CORRECTION, REJECTED}` (reuse a module-level
        frozenset; an unknown value ⇒ 400, never a 500, never a silent default).
  - [ ] **Server-side soft-gate (AC2 mirror):** for `NEEDS_CORRECTION`/`REJECTED`, blank
        notes ⇒ **400** with an honest message (the JS gates first, but the server is the
        real boundary — never trust the client). Approve with blank notes is allowed.
  - [ ] On valid input: read submission (missing ⇒ calm 404); compute `decided_at` =
        current UTC ISO-8601 (use the same stamping approach the codebase uses; a
        `datetime.now(UTC).isoformat()` style string is fine — keep it ISO-8601 `_at`);
        `repo.record_disposition(...)`, then `status.advance(conn, sid,
        to_status="DECIDED", event_type="DECIDED", actor=SPECIALIST_ACTOR, note=...)`.
        Order matters: write the disposition columns BEFORE `advance` flips status to
        DECIDED, because the schema cross-column CHECK requires `disposition IS NOT NULL`
        the moment `status='DECIDED'`. (`advance` commits; do the `record_disposition`
        write on the same `conn` first so they land in one connection's sequence — verify
        the CHECK is satisfied. If a single committed unit is needed, write disposition +
        status + audit in one transaction; see Dev Notes "transaction shape".)
  - [ ] Promote `draft_notes → decision_notes`: the persisted `notes` value submitted with
        the POST is authoritative (it IS the promoted draft); write it to
        `decision_notes`. (The JS keeps `draft_notes` synced via Task 6; the POST carries
        the final text so the disposition is correct even if the last autosave was in
        flight.)
  - [ ] On success **redirect 303 to `/queue?recorded={id}`** (so the Queue can show the
        "Recorded — Undo" affordance for that id). On a `ValueError` from `advance`
        (already decided / lost race) ⇒ re-render the review screen with an honest error
        (AC5) at 409, screen stays put — do NOT 500.
- [ ] **Task 5 — undo route `POST /review/{id}/undo` (AC4).** (AC: 4)
  - [ ] Add `POST /review/{submission_id}/undo`: read submission (missing ⇒ 404);
        `repo.clear_disposition(...)` then `status.reopen(conn, sid,
        actor=SPECIALIST_ACTOR)`. Order: clear the disposition columns BEFORE flipping
        status away from DECIDED so the cross-column CHECK (`status<>'DECIDED' ⇒
        disposition IS NULL`) is satisfied. **Retain the `review_progress` row** (ticks +
        draft notes) — do NOT delete it (AC4 "restored"). On success **redirect 303 to
        `/review/{id}`** (reopened). A non-DECIDED submission (`ValueError` from `reopen`)
        ⇒ calm 409 / honest message, never 500.
- [ ] **Task 6 — Notes draft autosave wired into `POST /review/{id}/progress` (AC3, AR-14).**
      (AC: 3, 5)
  - [ ] Extend the existing `POST /review/{submission_id}/progress` handler to ALSO accept
        an optional `draft_notes: str | None = Form(None)`. When `check_key`/`ticked` are
        present it ticks as today; when `draft_notes` is present it calls
        `repo.set_draft_notes(...)`. Keep returning `204`. Both may be present; a request
        with ONLY `draft_notes` is valid (the Notes autosave). Make `check_key`/`ticked`
        optional (default `None`) so a notes-only POST validates — but preserve the tick
        path exactly (when a tick is posted, behave as before). Guard: if neither a tick
        nor draft_notes is supplied ⇒ 204 no-op (never 422 on an empty beacon).
  - [ ] The render path `GET /review/{id}` rehydrates `draft_notes` into the textarea
        (read it alongside `ticked_keys` from the already-read `review_progress`; pass to
        the view-model). Pure read — AR-5 intact.
- [ ] **Task 7 — action-bar view-model in `app/web/review_view.py` (AC1, AC6).** (AC: 1, 6)
  - [ ] Add `action_bar(submission, *, draft_notes, has_open_review)` returning the
        view-model: the three control descriptors (key, label, css class, icon — **the
        css classes are `dispo--approve`/`dispo--correct`/`dispo--reject`, NOT verdict
        classes**), `notes_value` (the rehydrated draft), `requires_notes_for` set, and
        `has_open_review` (any non-auto, un-ticked REVIEW/FAIL row remains ⇒ the Approve
        confirm modal arms). Emit **NO** `verdict → disposition` mapping and no
        verdict-derived default/colour (contract #4 — a review finding otherwise).
  - [ ] `has_open_review` is computed from the SAME `smart_checklist` rows already built
        (reuse `is_problem`/`state`), so the modal arming and the checklist never disagree.
- [ ] **Task 8 — template: replace the Decide placeholder with the action bar (AC1, AC2,
      AC6).** (AC: 1, 2, 6)
  - [ ] In `templates/review.html`, replace the `#group-decide` placeholder `<section>`
        with the Notes + Disposition `<form method="post"
        action="/review/{{submission.id}}/disposition">` bar matching the mockup
        (`.commit` block, lines 556–568): the Notes label + "required for Needs
        Correction / Reject" reqd marker, the hint, the `<textarea name="notes">`
        pre-filled with the rehydrated draft, then the three `<button>`s
        (Approve filled navy / Needs Correction outline navy / Reject outline red) each
        carrying `name="disposition" value="APPROVED|NEEDS_CORRECTION|REJECTED"`, plus the
        "None pre-selected — the engine recommends, you record the decision." hint. Keep
        `id="group-decide"` + `tabindex="-1"` so the chevron ⑤ anchor + focus-jump still
        resolve. Targets ≥48px (mockup `.btn min-height:48px`); textarea ≥16px font.
  - [ ] Add an inert (JS-hydrated) confirm-modal scaffold (`role="dialog"`, hidden by
        default) for the Approve-with-open-REVIEW path (AC2). Without JS the form still
        submits and the **server** enforces the notes gate (AC5 safety net), so the modal
        is progressive enhancement.
- [ ] **Task 9 — progressive-enhancement JS for the bar (AC2, AC3, AC5).** (AC: 2, 3, 5)
  - [ ] Add `static/js/disposition.js` (same-origin, no build, NFR-2). It: (a) debounced
        autosaves the textarea to `POST /review/{id}/progress` as `draft_notes` (AR-14
        survive-reload); (b) **soft-gates** Notes for Needs Correction / Reject — block
        submit + focus the textarea + announce via `aria-live` when blank (never
        colour-only, UX-DR-15); (c) on **Approve while open REVIEW** items remain, opens
        the calm confirm modal (focus-trapped, Esc closes, returns focus); (d) **disables
        the bar on submit** (AC3 double-submit guard); (e) is inert/no-throw when the bar
        is absent. Single-letter behaviour: not in scope here (Story 4.10), but ensure the
        textarea does not trip any global shortcut — none exists yet.
  - [ ] Wire it in the `{% block scripts %}` of `review.html` alongside `review.js`.
- [ ] **Task 10 — Queue "Recorded — Undo" affordance (AC3, AC4).** (AC: 3, 4)
  - [ ] `GET /queue` already exists (`routes_queue.py`). Accept an optional
        `recorded: int | None = Query(None)`; when present, pass it to `queue.html` so a
        brief banner renders: "Recorded — Undo" where **Undo** is a `<form method="post"
        action="/review/{recorded}/undo">` submit button (works without JS). Keep the
        queue render a pure read (AR-5). The redirect from Task 4 sets `?recorded={id}`.
  - [ ] (No persistent toast store — the affordance is the post-redirect banner for that
        one id; navigating away / refreshing clears it. "after it dismisses the
        disposition is final for the POC" — AC4.)
- [ ] **Task 11 — tests (test-first, RED → GREEN).** (AC: 1–6)
  - [ ] `tests/test_review_view.py`: `action_bar` returns three controls none-selected,
        correct dispo css classes (assert NO `chip--`/verdict class leaks onto a button),
        `has_open_review` true iff an un-ticked REVIEW/FAIL remains, `notes_value`
        rehydrates the draft.
  - [ ] `tests/test_disposition.py` (NEW route test module): `POST /disposition` happy
        paths for each enum (200/303 → `/queue?recorded=`), submission becomes DECIDED with
        disposition + decided_at + decision_notes set; NEEDS_CORRECTION/REJECT with blank
        notes ⇒ 400 (server soft-gate); unknown disposition ⇒ 400; missing id ⇒ 404;
        double-disposition (already DECIDED) ⇒ 409 not 500. `POST /undo`: clears the three
        columns, status back to READY_FOR_REVIEW, an UNDONE audit row exists, the
        `review_progress` row (ticks + draft_notes) survives; undo on a non-DECIDED ⇒ 409.
        `POST /progress` with `draft_notes` only ⇒ 204 and the draft persists + rehydrates
        on the next `GET`. Render: `GET /review/{id}` shows the three buttons, the reqd
        marker, the rehydrated textarea, none pre-selected, no verdict class on a button.
  - [ ] Reuse the `_client` / `_insert_submission` helpers' style from `test_review.py`
        (token-gate off, `SCHEDULER_ENABLED=false`, tmp DB via `init_db`).

## Dev Notes

### What this story is (and the spine it must hold)

This is the **commit zone** of the Review Workspace — the human's official act. It is the
clearest place the project's central separation must be visible in code:

- **Verdict vs disposition (AR-3 #4 / project-context "Recommend, don't decide").**
  `engine_verdict ∈ {PASS, REVIEW, FAIL}` is advisory and lives in `app/verdict.py`;
  `disposition ∈ {APPROVED, NEEDS_CORRECTION, REJECTED}` is the human's and lives in
  `app/disposition.py`. **No function maps one to the other.** No verdict pre-selects,
  defaults, or colours a disposition control. The action-bar buttons use
  `dispo--approve/correct/reject` classes — NEVER `chip--pass/review/fail`. A
  `verdict→disposition` mapping or a verdict colour on a disposition button is an explicit
  **review finding** (project-context "Anti-patterns to reject in review").
  → `app/disposition.py` currently holds ONLY the enum placeholder. If the route needs the
  set of valid disposition values, define them there (it's the one home for the enum) and
  import — do NOT hard-code the literal set in the route as a second source of truth. Keep
  `app/disposition.py` free of any `verdict` import.

- **AR-5, the 5-second read contract.** `GET /review/{id}` stays a pure pre-computed read
  — it gains ONE thing: reading `draft_notes` from the already-read `review_progress` row
  (no extra query — `get_review_progress` already returns it). All WRITES happen ONLY on
  explicit POSTs: `/disposition` (status + disposition columns + audit), `/undo`
  (clear + backward status + audit), `/progress` (the draft-notes upsert). These are
  cheap single-row bookkeeping writes — explicitly permitted by Addendum A. No OCR /
  inference / model / pipeline import anywhere on these paths.

- **Pipeline is the only writer of the engine columns.** The web layer writes ONLY the
  human columns: `disposition` / `decided_at` / `decision_notes` / `correction_due_at`,
  the `status` lifecycle transitions, and `review_progress` (ticks + draft notes). These
  **never overlap** the pipeline's `checklist_items` / `engine_verdict` / comparisons.
  Do not touch `checklist_items` from this story.

### Schema is already in place — NO migration needed

`app/db/schema.sql` (read it) already declares everything:

- `submissions.disposition` (CHECK `APPROVED/NEEDS_CORRECTION/REJECTED`),
  `decided_at`, `decision_notes`, `correction_due_at`, `specialist_id`.
- **The cross-column invariant CHECK** (schema.sql lines 56–61):
  `(status='DECIDED' AND disposition IS NOT NULL AND decided_at IS NOT NULL) OR
   (status<>'DECIDED' AND disposition IS NULL AND decided_at IS NULL)`, plus
  `correction_due_at IS NULL OR disposition='NEEDS_CORRECTION'`.
  **This drives the write ORDER**: when recording, set `disposition` + `decided_at`
  BEFORE (or in the same statement-run as) flipping status to `DECIDED`; when undoing,
  NULL them BEFORE flipping status back. Otherwise SQLite raises `IntegrityError` mid-flip.
- `review_progress.draft_notes` — declared by Story 4.6 *expressly for this story*
  (schema.sql lines 272–277). No new column.
- `audit_events.event_type` already includes `DECIDED` and `UNDONE` (schema.sql line
  119–121 and `status.AUDIT_EVENT_TYPES`).
- `submissions` status CHECK already includes `DECIDED`.

### Transaction shape (important — the CHECK constraint)

`status.advance` currently does `update_status` + `insert_audit_event` + `conn.commit()`
in one transaction. The cross-column CHECK is evaluated **per-statement** in SQLite, so
the moment `UPDATE submissions SET status='DECIDED'` runs, `disposition` must ALREADY be
non-NULL on that row. Two safe options — pick the simpler that keeps `status.py` clean:

1. **Recommended:** in the disposition route, on a single `conn`: call
   `repo.record_disposition(...)` (writes disposition/decided_at/decision_notes, no
   commit), THEN `status.advance(..., to_status="DECIDED", event_type="DECIDED")` (which
   updates status, inserts the audit row, and commits). Because `record_disposition`
   already ran on the same connection, the row has a non-NULL disposition when `advance`'s
   `UPDATE status` fires → CHECK satisfied. (`connect()` wraps the block; `advance`'s
   explicit commit finalizes.)
2. If you prefer atomicity in one helper, add a dedicated `status.record_decision(...)`
   that does record_disposition + update_status + insert DECIDED audit + commit together.
   Keep `advance` untouched (forward-only, pipeline-shaped). Either is acceptable — do NOT
   weaken the CHECK or split into two commits that can leave a DECIDED row without a
   disposition.

For **undo**, symmetric: `repo.clear_disposition(...)` (NULLs the columns, no commit) →
`status.reopen(...)` (updates status to READY_FOR_REVIEW, inserts UNDONE audit, commits).
NULL columns first so the `status<>'DECIDED'` branch of the CHECK holds.

### Files to touch

- **UPDATE** `app/db/repositories.py` — add `set_draft_notes`, `get_draft_notes`,
  `record_disposition`, `clear_disposition` (raw SQL stays here, the data boundary; the
  helpers do NOT commit, matching every other write helper in this file).
- **UPDATE** `app/pipeline/status.py` — add `reopen` (the lone bounded backward
  transition; web-actor). Possibly `record_decision` per the transaction-shape note.
- **UPDATE** `app/web/routes_review.py` — add `POST /disposition`, `POST /undo`; extend
  `POST /progress` to accept `draft_notes`; pass `draft_notes` + `action_bar` to the
  render context. Reuse `SPECIALIST_ACTOR` (defined in `routes_queue.py` — import it or
  define a single shared constant; do not duplicate the string with a different value).
- **UPDATE** `app/web/review_view.py` — add `action_bar(...)`. NO verdict→disposition map.
- **UPDATE** `app/web/routes_queue.py` — `GET /queue` accepts `recorded` and passes it.
- **UPDATE** `templates/review.html` — replace the `#group-decide` placeholder with the
  action bar + confirm-modal scaffold.
- **UPDATE** `templates/queue.html` — render the "Recorded — Undo" banner when `recorded`.
- **NEW** `static/js/disposition.js` — autosave + soft-gate + confirm modal + disable-on-
  submit. Wire into `review.html` scripts block.
- **UPDATE** `app/disposition.py` — add the disposition value constants/enum if the route
  needs them (the one home; no `verdict` import).
- **NEW** `tests/test_disposition.py`; **UPDATE** `tests/test_review_view.py`,
  `tests/test_review.py` (render assertions for the bar).

### Mockup fidelity (AC6)

Mockup `_bmad-output/.../mockups/review-workspace.html` lines 296–320 (CSS) + 556–568
(markup): the `.commit` bar — top border + upward shadow (persistent commit zone); Notes
label with the red **"required for Needs Correction / Reject"** marker; the hint line; the
`<textarea>`; the `.dispo` row with three `.btn` (Approve `background:var(--primary)
color:#fff`; Needs Correction outline navy; Reject outline `var(--fail)`/red); the
right-aligned "None pre-selected — the engine recommends, you record the decision." hint.
**Spine wins:** resolve colours to `static/css/brand.css` tokens (the same `--primary` /
`--fail` the app already uses), NOT the mockup's literal hex. Exclude mockup scaffolding
(device frame, fabricated SUB-id, J. Park). Add the `.commit`/`.dispo`/`.btn` rules to
`static/css/brand.css` (where the other `review`/`work`/`cli` classes live — grep there).
Note the Reject button is the ONE place red appears on a disposition control — that's the
disposition's own semantic red (it is NOT a verdict colour; it's the destructive-action
colour, mockup `.btn.reject`), and it is paired with the ✗ icon + the word "Reject"
(never colour alone, UX-DR-15).

### Accessibility floor (UX-DR-15 / NFR-4)

- Buttons ≥48px target (mockup `.btn min-height:48px`); textarea font ≥16px.
- Notes-required failure is announced via `aria-live` (not colour-only); focus moves to
  the textarea.
- The confirm modal: `role="dialog"`, focus-trapped, Esc closes, returns focus to the
  Approve button. Tab order = reading order (left panel → right column → action bar).
- Icon + word on every control (✓ Approve / �Needs Correction / ✗ Reject) — colour never
  alone.

### Previous-story intelligence (Story 4.7 + 4.6)

- 4.6 established the **`review_progress` upsert pattern** (`set_check_tick`,
  `get_ticked_check_keys`) and the `POST /review/{id}/progress` → 204 + optimistic-revert
  JS. Mirror it for `draft_notes`: same upsert idiom (`ON CONFLICT(submission_id)`
  preserving the OTHER column), same 204, same honest-revert philosophy in JS.
- 4.6 already wired `review.js` (defer) + the `aria-live` "N of M done" region. Add
  `disposition.js` as a SECOND defer script; keep them independent (each guards its own
  root element, no shared globals).
- 4.7 added the two-column `.work` / `.review-col-left` / `.review-col-right` layout; the
  action bar lives at the bottom of the right column (or full-width below `.work` per the
  mockup `.commit` sits after `/work`). Match the mockup: `.commit` is a sibling AFTER
  `.work`, full-width. Adjust the template structure accordingly (the `#group-decide`
  anchor currently sits inside `.review-col-right`; moving the bar to a full-width
  `.commit` after `.work` is fine — keep an `id="group-decide"` element the chevron
  targets, whether on the `.commit` section or a marker).
- The codebase stamps timestamps as ISO-8601 strings (repositories.py docstring: "kept as
  ISO-8601 str"). Use a UTC ISO-8601 string for `decided_at`.

### Project Structure Notes

- snake_case everywhere (columns/Python/JSON); routes lowercase no-trailing-slash with
  `{id}` params — `POST /review/{id}/disposition`, `POST /review/{id}/undo` are already in
  the project-context canonical route list. No deviations.
- Raw SQL only in `app/db/`; orchestration (status machine) in `app/pipeline/status.py`;
  HTTP in `app/web/routes_review.py`; pure view-models in `app/web/review_view.py`. Keep
  the layering.
- `SPECIALIST_ACTOR = "Label Specialist"` is the human actor on the audit timeline
  (already defined in `routes_queue.py`). Reuse the same value for DECIDED/UNDONE.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.8] — the six ACs (verbatim).
- [Source: _bmad-output/planning-artifacts/epics.md#Requirements Inventory] — FR-6,
  UX-DR-14, AR-3 #4, AR-14, the UI-fidelity standard.
- [Source: _bmad-output/project-context.md] — Recommend-don't-decide; the 5-second read
  contract + permitted POST writes (Addendum A); pipeline-is-only-writer; the four
  contracts (#4 `app/disposition.py`); status transitions incl. the lone backward
  `DECIDED → READY_FOR_REVIEW` via `POST /review/{id}/undo`; audit vocabulary; anti-pattern
  list (verdict→disposition map / verdict colour on a disposition button).
- [Source: app/db/schema.sql#submissions] — disposition/decided_at/decision_notes/
  correction_due_at columns + the cross-column CHECK invariant (drives write order);
  [#review_progress] draft_notes; [#audit_events] DECIDED/UNDONE vocabulary.
- [Source: app/pipeline/status.py] — `advance` (forward-only), `AUDIT_EVENT_TYPES`,
  `PIPELINE_ACTOR`; the docstring already names `DECIDED → READY_FOR_REVIEW` as the web
  layer's via `POST /review/{id}/undo`.
- [Source: app/db/repositories.py] — `set_check_tick`/`get_review_progress` upsert pattern
  to mirror; `update_status`/`insert_audit_event` primitives; the no-commit convention.
- [Source: app/web/routes_review.py] — the existing `GET /review/{id}` + `POST /progress`
  to extend; AR-5 read-path purity.
- [Source: app/web/routes_queue.py] — `POST /next` + `status.advance` OPENED pattern;
  `SPECIALIST_ACTOR`; the 303-redirect idiom.
- [Source: .../mockups/review-workspace.html lines 296–320, 556–568] — the `.commit`
  Notes + Disposition action-bar layout/components/copy (AC6 fidelity target).

## Dev Agent Record

### Agent Model Used

claude-opus-4 (Amelia, DEV agent)

### Debug Log References

### Completion Notes List

### File List
