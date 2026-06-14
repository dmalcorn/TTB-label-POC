---
baseline_commit: a026052
context:
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/project-context.md
  - README.md
  - docs/index.md
  - docs/outbound-calls-inventory.md
  - _bmad-output/implementation-artifacts/6-2-live-fixture-enqueue.md
---

# Story 6.3: Documentation deliverable set & outbound-call inventory

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a take-home evaluator,
I want the complete documentation set with the firewall posture proven,
so that I can set up, run, and trust the POC from the repo alone.

## Acceptance Criteria

**AC-1 — README provides setup/run instructions and links every required `docs/` deliverable**
**Given** the README and `docs/` set
**When** an evaluator reads the README
**Then** it provides **setup/run instructions** (clone → configure → build/run; the offline
egress smoke test) AND **links every** brief-mandated `docs/` deliverable: approach, tools
used, assumptions, trade-offs/limitations, pre-search, data dictionary (incl. supported image
types), the three per-type Ruleset docs (spirits/wine/beer), the landscape narrative incl. the
Applicant's COLAs Online workflow, and the USWDS-compliance notes
**And** every such link is a **same-repo relative path that resolves to a file that exists** (no
dangling deliverable link). *(FR-26)*

**AC-2 — The outbound-call inventory enumerates every external call, 3-way classified**
**Given** [`docs/outbound-calls-inventory.md`](../../docs/outbound-calls-inventory.md)
**When** a reviewer reads it
**Then** it enumerates every external call the deployed app can make, **each classified exactly
one of `none` / `local` / `models-internal-endpoint`** (the NFR-2 vocabulary), with the only
off-host class being `models-internal-endpoint` (the LLM layer in `app/adapters/llm/`)
**And** it is presented as a **finalized deliverable**, not a planning artifact with open
blocking TODOs — the firewall posture it documents is the one the code implements (the LLM
boundary lives only in `app/adapters/llm/{openai,google,anthropic}.py`, gated by `LLM_ENABLED`).
*(FR-26, NFR-2)*

**AC-3 — A fresh evaluator can clone, set up, and run locally from the README alone**
**Given** a fresh clone and the README only
**When** the evaluator follows it
**Then** the README's run path is self-contained: the configure step (`.env.example` → `.env`),
the build/run command(s), the open-in-browser step, and the token-gate behavior are all stated;
**no stale "completes in a later epic" disclaimer** remains telling the evaluator the deliverable
set is incomplete (Epic 6 IS that completion — the doc set is now whole). *(FR-26)*

**AC-4 — Limitations documented beside the capabilities (NFR-5)**
**Given** the documentation set
**When** an evaluator reads the README and the trade-offs/limitations doc
**Then** the headline limitations — **font/dimension size is not checked**, **mock/seeded data
only (no PII)**, and **prototype/POC status** — are documented **beside** the capabilities (in
the README's design-decisions/limitations narrative AND in
[`docs/tradeoffs-and-limitations.md`](../../docs/tradeoffs-and-limitations.md)), so the claims
the demo makes are matched by stated limits. *(FR-26, NFR-5)*

*(Source: epics.md Story 6.3; FR-26; NFR-2; NFR-5; project-context.md §Firewall & Offline
Posture (the only off-host calls originate in `adapters/llm/*`; 3-way classification),
§Anti-patterns (no CDN/outbound asset reference); architecture.md §D6/D7 (offline posture,
env/config). README.md, docs/index.md, docs/outbound-calls-inventory.md are the surfaces edited.)*

> **Dependency note (read first — this is a documentation/finalization story, not new app code).**
> - **Nearly every deliverable already exists** in `docs/` (approach, tools-used, assumptions,
>   tradeoffs-and-limitations, presearch, data-dictionary, image-handling, the three
>   regulatory-rules-*, label-requirements-by-type, applicant-workflow-distilled-spirits,
>   ux-design-notes incl. §10 USWDS Compliance Statements, outbound-calls-inventory) and most are
>   already linked from `README.md` + `docs/index.md`. This story **finalizes** that set — it does
>   NOT author the docs from scratch.
> - The **landscape narrative incl. the Applicant's COLAs Online workflow** is
>   `docs/applicant-workflow-distilled-spirits.md` (already linked from README §"What this is"
>   and the Documentation table's prose).
> - The **USWDS-compliance notes** live in `docs/ux-design-notes.md` §10 "USWDS Compliance
>   Statements (README-ready)" (README §"USWDS compliance" already links it).
> - The **outbound-call inventory** is `docs/outbound-calls-inventory.md`. It is currently
>   headed **"Status: Planning artifact"** with several open `TODO` markers — finalize the framing
>   to a delivered artifact (the implementation TODOs that are RESOLVED are noted as such; the few
>   remaining are operational/verification notes, not blocking gaps).
> - The README carries a **stale disclaimer** ("population of the remaining deliverables completes
>   in Epic 6", lines ~157-159) — Epic 6 is now landing, so that note must go (AC-3).

> **Scope note (binding).** This story edits **documentation surfaces only** — `README.md`,
> `docs/outbound-calls-inventory.md`, `docs/index.md` (and only if a required deliverable is
> genuinely unlinked, a one-line link addition). It adds ONE regression test
> (`tests/test_docs_deliverables.py`) that PINS the deliverable contract (every required doc is
> linked + resolves; the inventory's 3-way classification is present; no stale "later epic"
> disclaimer; limitations stated). It does **NOT** touch `app/`, the schema, the seed corpus, any
> route, or any planning artifact under `_bmad-output/planning-artifacts/`. It does NOT rewrite
> the substance of existing, accurate docs — only finalizes framing/links and adds the guard test.
> `auto-run/` is off-limits (CLAUDE.md).

## Tasks / Subtasks

- [x] **Task 1 — Regression test pinning the deliverable contract (AC: 1, 2, 3, 4) — RED FIRST**
  - [x] Create `tests/test_docs_deliverables.py`. Resolve `REPO_ROOT =
        Path(__file__).resolve().parents[1]` (mirror `tests/test_deploy_config.py`).
  - [x] AC-1: read `README.md`; assert it links each required deliverable by relative path AND
        that each linked path exists on disk. Required set: `docs/approach.md`,
        `docs/tools-used.md`, `docs/assumptions.md`, `docs/tradeoffs-and-limitations.md`,
        `docs/presearch.md`, `docs/data-dictionary.md`, `docs/image-handling.md`,
        `docs/regulatory-rules-distilled-spirits.md`, `docs/regulatory-rules-wine.md`,
        `docs/regulatory-rules-beer.md`, `docs/label-requirements-by-type.md`,
        `docs/applicant-workflow-distilled-spirits.md`, `docs/ux-design-notes.md`,
        `docs/outbound-calls-inventory.md`. Also assert the README contains the setup/run cues
        (`.env.example`, a `docker` build/run command, the offline `--network none` smoke test).
  - [x] AC-1 (generalized no-dangling-link): extract EVERY relative markdown link target from
        `README.md` (and `docs/index.md`) that points into the repo (skip `http(s)://`,
        anchors-only `#…`, and `mailto:`) and assert each resolves to an existing file/dir.
  - [x] AC-2: read `docs/outbound-calls-inventory.md`; assert all three classification tokens
        (`none`, `local`, `models-internal-endpoint`) appear; assert the off-host boundary names
        `app/adapters/llm` (the only off-host class); assert the doc is NOT framed as an
        incomplete planning artifact (no header literally `Status: Planning artifact`).
  - [x] AC-3: assert NO stale "completes in Epic 6" / "remaining deliverables completes" / "Epic 6
        partial" disclaimer remains in `README.md`.
  - [x] AC-4: assert the README + `docs/tradeoffs-and-limitations.md` together state the headline
        limitations — font/dimension size **not** checked, mock/seeded/no-PII data, prototype/POC
        status.
  - [x] Run it; confirm it goes RED on the currently-stale README disclaimer + the inventory's
        `Status: Planning artifact` header (and any genuinely-missing link).
- [x] **Task 2 — Finalize the README (AC: 1, 3, 4) — GREEN**
  - [x] Remove the stale blockquote disclaimer ("…population of the remaining deliverables
        completes in Epic 6"). Replace with a one-line statement that the full `docs/` set is
        delivered + indexed at `docs/index.md` (no "later epic" language).
  - [x] Verify the Documentation section links every required deliverable (add a link only if one
        is genuinely missing — most are present). Ensure the landscape narrative
        (`applicant-workflow-distilled-spirits.md`) and USWDS-compliance notes
        (`ux-design-notes.md`) are reachable as named deliverables.
  - [x] Confirm the setup/run + offline-smoke-test + token-gate + limitations narrative are intact
        and self-contained (no edits needed if already correct — verify against the test).
- [x] **Task 3 — Finalize the outbound-call inventory as a delivered artifact (AC: 2) — GREEN**
  - [x] Change the header from "Status: Planning artifact (updated as components are built)…" to a
        finalized-deliverable framing (e.g. "Status: Delivered — reflects the implemented firewall
        posture (LLM layer, Story 2.5; tracing, Story 5.1)."). Keep the 3-way classification table
        and the boundary section intact (they are accurate).
  - [x] Reconcile the open `TODO` markers: the implementation-resolved ones (TODO-1 self-hosted
        assets — done; TODO-2 weights baked; TODO-3 tracing local-only; TODO-4 smoke test; TODO-7
        endpoint swap) are marked RESOLVED with the implementing story; any genuinely-operational
        residue (TODO-5 DB topology, TODO-6 dependency phone-home audit) is reframed as a
        deployment-time verification note, NOT a blocking gap. Do NOT fabricate completion —
        state what is verified vs. what is an operational check.
- [x] **Task 4 — `docs/index.md` link integrity (AC: 1) — GREEN**
  - [x] Verify `docs/index.md` links every `docs/` deliverable and that all its relative links
        resolve (the generalized no-dangling-link assertion covers it). Add a missing link only if
        the test surfaces one.

### Review Findings (code review 2026-06-14, CR — Amelia)

_Three parallel review layers (Blind Hunter diff-only · Edge Case Hunter · Acceptance Auditor)._
_All four ACs functionally satisfied; suite green throughout (14/14 targeted, 799 passed / 1 skipped full CI)._
_Findings clustered on guard-test robustness — patched so each assertion faithfully pins its AC._

- [x] [Review][Patch] `test_outbound_inventory_has_three_way_classification` keyed on bare English substrings (`none`/`local`) — now asserts each token in its backtick-quoted classification form so the NFR-2 scheme is the genuine discriminator [tests/test_docs_deliverables.py:122]
- [x] [Review][Patch] `test_outbound_inventory_is_a_delivered_artifact` only forbade one stale phrase (no positive assertion; whitespace-fragile) — now normalizes bold/space and additionally asserts `Status: Delivered`, so a missing/`Draft` status cannot pass [tests/test_docs_deliverables.py:140]
- [x] [Review][Patch] `test_readme_documents_font_size_limitation` checked `"font"` and `"not checked"` independently (spuriously co-satisfiable) — now pins the contiguous claim `font/dimension size is not checked` (bold/space-insensitive) [tests/test_docs_deliverables.py:175]
- [x] [Review][Patch] AC-4 tradeoffs-doc guard asserted only `"font"` — broadened to also pin the no-PII/seeded-data and proof-of-concept limits in `docs/tradeoffs-and-limitations.md` (AC-4 binds all three to that doc, not only the README) [tests/test_docs_deliverables.py:195]
- [x] [Review][Defer] AC-1 "data dictionary (incl. supported image types)" — `docs/data-dictionary.md` PNG row still `TODO confirm`; authoritative answer is in `docs/image-handling.md` (both linked, AC intent met). Resolving the PNG `TODO` is a data-dictionary substance edit OUT of this docs-finalization story's scope — deferred [docs/data-dictionary.md:126,468]

_Dismissed as noise (latent-only / hypothetical / handled): `_MD_LINK` regex can't parse titled/image/angle links (no such links exist in README/index — latent future false-fail only); brittle exact-casing of `"no PII"`/`"--network none"` (content confirmed present, green); the dead `"remaining deliverables completes"` stale-marker (other markers catch the regression); residual `PARTIAL`/`Remaining:` TODO tokens in the inventory (AC-2 forbids only *blocking* TODOs — §5 preamble defensibly reframes them as operational/provenance verification notes)._

## Project Structure Notes

- **New:** `tests/test_docs_deliverables.py` (the deliverable-contract regression test).
- **Update:** `README.md` (drop stale Epic-6 disclaimer; verify deliverable links),
  `docs/outbound-calls-inventory.md` (finalize status framing + reconcile TODOs),
  `docs/index.md` (only if a link is genuinely missing).
- **Do NOT touch:** anything under `app/`, the DB schema, the seed corpus, routes, templates,
  static assets, `_bmad-output/planning-artifacts/`, or `auto-run/`.
- **Reuse the test idiom:** `REPO_ROOT = Path(__file__).resolve().parents[1]` reading repo files,
  exactly as `tests/test_deploy_config.py` does for the `.env.example`/`railway.toml` contract.

## Dev Notes

### This is a finalization + guard-test story, not a doc-authoring story
- The brief-required deliverables already exist and are mostly linked. The risk this story
  removes is **drift**: a stale "later epic" disclaimer that tells an evaluator the set is
  incomplete, an inventory still framed as a planning artifact, and the absence of a regression
  guard that would catch a future dangling deliverable link. The test is the durable contract;
  the doc edits make it green.
- Do NOT rewrite accurate prose. Minimal, surgical edits: delete the stale disclaimer, retitle the
  inventory's status line, mark resolved TODOs, and (only if needed) add a missing link.

### Firewall / outbound-call posture (NFR-2) — the inventory is the deliverable
- The canonical posture (project-context §Firewall): the ONLY permitted off-host calls originate
  in `app/adapters/llm/{openai,google,anthropic}.py` (classified `models-internal-endpoint`);
  everything else is `none`/`local`. `LLM_ENABLED=false` disables that boundary entirely → a
  provable zero-egress OCR-only path (`docker run --network none` smoke test). The inventory
  already documents exactly this — the finalization is framing, not a posture change.
- 3-way classification vocabulary is fixed: `none` / `local` / `models-internal-endpoint`. The
  test asserts all three tokens are present and that the off-host boundary names `app/adapters/llm`.

### Limitations beside capabilities (NFR-5)
- Headline limits to keep visible: font/dimension size not checkable from a photo (matches TTB's
  own COLAs Online disclaimer), seeded dummy data only / no PII / brand artwork is private
  fixtures, and prototype/POC status. The README's "Key design decisions" + "License & data
  notice" sections already carry these; `docs/tradeoffs-and-limitations.md` is the full treatment.

### Architecture compliance
- Documentation-only + one test. No `app/` code, no schema, no route, no asset. The 5-second read
  contract, verdict-vs-disposition separation, pipeline-is-the-only-writer, and VLM-only purity
  are all untouched (nothing executable changes). snake_case test names; ruff line length 100;
  type hints in the test (`from __future__ import annotations`, `-> None`).

### Testing approach (test-first)
- One new file: `tests/test_docs_deliverables.py`. It reads repo text files only — pure-Python,
  fast, host-venv-safe (no OCR natives, no DB, no network). Run targeted:
  `.venv/Scripts/python.exe -m pytest tests/test_docs_deliverables.py -q`. Full gate ONCE at the
  end: `bash scripts/ci.sh`.

### Previous story intelligence (Story 6.2)
- Story 6.2 (live fixture enqueue) is `done`; its doc footprint is none. Epic 6's first two
  stories shipped the operator routes (`/reset`, `/enqueue`); 6.3 closes the epic by finalizing
  the deliverable set + outbound-call inventory — the documentation half of Epic 6's charter.
- ruff/mypy run over the repo excluding `auto-run/`; a markdown-only change plus a typed test file
  passes cleanly. Full CI is re-run by the pipeline after this — run the gate at most once here.

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.3: Documentation deliverable set &
  outbound-call inventory] (FR-26, NFR-2, NFR-5; README links every docs/ deliverable; outbound
  inventory 3-way classified; clone-and-run from README alone; limitations beside capabilities)
- [Source: _bmad-output/planning-artifacts/epics.md#Requirements Inventory] (FR-26 deliverable
  list; NFR-2 3-way classification; NFR-5 honesty of claims)
- [Source: _bmad-output/project-context.md#Firewall & Offline Posture] (only off-host calls in
  `app/adapters/llm/*`; `none`/`local`/`models-internal-endpoint`; `LLM_ENABLED=false` zero-egress)
- [Source: _bmad-output/project-context.md#Anti-patterns] (no CDN/outbound asset reference)
- [Source: README.md] (the stale "completes in Epic 6" disclaimer to remove; the Documentation
  table + setup/run + offline smoke test + USWDS compliance + limitations sections)
- [Source: docs/outbound-calls-inventory.md] (the planning-artifact header + TODO markers to
  finalize; the 3-way classification table + boundary section to keep)
- [Source: docs/index.md] (the full deliverable index whose links must resolve)
- [Source: tests/test_deploy_config.py] (the `REPO_ROOT` repo-file-reading test idiom reused)

## Dev Agent Record

### Agent Model Used

Amelia (BMad dev-story) — claude-opus-4-8

### Debug Log References

- Targeted: `.venv/Scripts/python.exe -m pytest tests/test_docs_deliverables.py -q` →
  RED first (12 passed / 2 failed: stale README disclaimer AC-3 + inventory `Status: Planning
  artifact` AC-2), then GREEN (14 passed).
- Full gate: `bash scripts/ci.sh` → format + lint + mypy + pytest (full suite green).

### Completion Notes List

- **Test-first (red → green).** Wrote `tests/test_docs_deliverables.py` (14 tests) first;
  confirmed RED on the two stale-framing surfaces (the README "completes in Epic 6" disclaimer →
  AC-3; the inventory `Status: Planning artifact` header → AC-2), then finalized the docs to green.
- **This was a finalization + guard story, not doc authoring.** Every brief-mandated deliverable
  already existed and was already linked from `README.md` + `docs/index.md` — no link additions
  were needed (the generalized no-dangling-link assertion passed on the first run for both files).
- **AC-1 (README links every deliverable, all resolve).** Pinned the full FR-26 required set
  (approach, tools-used, assumptions, tradeoffs-and-limitations, presearch, data-dictionary,
  image-handling, the three regulatory-rules-*, label-requirements-by-type, the
  applicant-workflow landscape narrative, ux-design-notes USWDS-compliance, outbound-calls-
  inventory) + the setup/run cues (`.env.example`, `docker`, `--network none`). Generalized
  no-dangling-link check over README + docs/index.md.
- **AC-2 (outbound-call inventory finalized, 3-way classified).** Retitled the header from
  "Status: Planning artifact" to "Status: Delivered (Story 6.3)" reflecting the implemented
  posture; kept the accurate 3-way classification table + boundary section. Reconciled §5: TODO-1
  marked RESOLVED (Story 1.4 self-hosted USWDS/fonts, no CDN), TODO-5/-6 reframed as
  deployment-time verification notes with the `--network none` smoke test as backstop. Test
  asserts all three tokens (`none`/`local`/`models-internal-endpoint`) + the `app/adapters/llm`
  off-host boundary. No fabricated completion — verified-vs-operational stated honestly.
- **AC-3 (clone-and-run, no stale disclaimer).** Removed the README blockquote telling evaluators
  the deliverable set completes in a later epic; replaced with a delivered-set statement naming the
  docs. Setup/run path is self-contained (configure → build/run → open → token gate).
- **AC-4 (limitations beside capabilities, NFR-5).** Verified the README states font-size-not-
  checked + no-PII/mock-data + proof-of-concept status, and `docs/tradeoffs-and-limitations.md`
  covers the font limitation — all already present, now guarded by the test.
- **Invariants held:** documentation-only + one pure-Python test (reads repo text files; no app
  code, schema, route, asset, or planning-artifact touched). The 5-second read contract,
  verdict-vs-disposition separation, pipeline-is-the-only-writer, VLM-only purity, and the
  firewall boundary are all untouched — nothing executable changed. `auto-run/` not touched.

### File List

- `tests/test_docs_deliverables.py` (NEW — the FR-26/NFR-2/NFR-5 deliverable-contract guard)
- `README.md` (removed the stale "completes in Epic 6" disclaimer → delivered-set statement)
- `docs/outbound-calls-inventory.md` (header → "Status: Delivered (Story 6.3)"; §5 retitled +
  TODO-1 RESOLVED, TODO-5/-6 reframed as deployment-time verification notes)

## Change Log

| Date | Change |
|------|--------|
| 2026-06-14 | Story 6.3 spec created (CS) — finalize the FR-26 documentation deliverable set + the NFR-2 outbound-call inventory: README links every required `docs/` deliverable (all resolve), inventory enumerates every external call 3-way classified, stale "Epic 6 partial" disclaimer removed (clone-and-run from README alone), limitations beside capabilities (NFR-5); pinned by a new `tests/test_docs_deliverables.py` regression guard. |
| 2026-06-14 | Story 6.3 implemented (DS), test-first. New `tests/test_docs_deliverables.py` (14 tests) RED → GREEN: removed the README's stale "completes in Epic 6" disclaimer (AC-3), finalized `docs/outbound-calls-inventory.md` to a delivered artifact with the 3-way classification intact + §5 markers reconciled (AC-2), pinned every required deliverable link + resolution + setup/run cues (AC-1) and the limitations-beside-capabilities content (AC-4). Docs-only + one pure-Python guard test; no `app/`/schema/route change. Full CI gate green. Story → review. |
