---
baseline_commit: c00d92dea980abab228640ea2c38af8897881a8e
---

# Story 3.1: Normalization & verdict roll-up contracts

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want the field-match normalization and verdict roll-up as two centralized, tested functions,
so that "STONE'S THROW" == "Stone's Throw" everywhere and the most-severe verdict always wins, with no divergent re-implementations.

## Acceptance Criteria

1. **AC1 — `normalize(value, field_key)` applies the fixed order and collapses incidental differences.**
   **Given** `app/normalize.py` owning `normalize(value, field_key)`
   **When** it runs
   **Then** it applies the fixed order — trim → collapse internal whitespace → Unicode NFKC → casefold → curly→straight quotes → strip trailing punctuation
   **And** numeric fields (`alcohol_content`, `net_contents`) additionally parse to number+unit
   **And** "STONE'S THROW" and "Stone's Throw" normalize equal (a unit test asserts **zero false-FAIL** on this class, **SM-C2**). *(AR-3 #2; architecture.md contract #2; project-context contract #2)*

2. **AC2 — `rollup(verdicts)` enforces severity precedence (most-severe wins).**
   **Given** `app/verdict.py` owning `rollup(verdicts)`
   **When** a set of check verdicts is rolled up
   **Then** any `FAIL` ⇒ `FAIL`; else any `REVIEW`/can't-verify ⇒ `REVIEW`; else `PASS`
   **And** the function is the single roll-up used by **both** the engine (submission `engine_verdict`) and the UI (Suggested Alert) so they can never disagree. *(AR-3 #3; architecture.md contract #3; project-context contract #3)*

3. **AC3 — The `field_comparisons` and `checklist_items` tables exist for the analysis job to write.**
   **Given** the schema this story extends
   **When** `init_db` runs on a fresh DB
   **Then** `field_comparisons` and `checklist_items` are created exactly per `docs/database-schema.md` §1.5/§1.6 (columns, CHECK enums, FKs, indexes, and the `v_field_comparisons` view) — created here, written by Stories 3.2/3.3. *(AR-3 #2, AR-3 #3; database-schema.md §1.5/§1.6)*

4. **AC4 — Both contracts are pure, dependency-clean, and tested.**
   **Given** `normalize.py` and `verdict.py`
   **When** the suite runs
   **Then** `tests/test_normalize.py` (the SM-C2 class + every pipeline step + numeric parse) and `tests/test_verdict.py` (severity precedence + `NA`/empty edge) pass; both modules are pure in-memory (zero I/O, zero DB, zero adapter imports), and `verdict.py` has **no dependency on `disposition.py`** and emits **no `verdict → disposition` mapping**. *(project-context Testing & "Recommend, don't decide"; architecture Contract boundary)*

## Tasks / Subtasks

- [ ] **Task 1 — Implement `app/normalize.py` (AC1)**
  - [ ] Replace the placeholder body (keep/extend the docstring). Implement `normalize(value: str | None, field_key: str) -> str` applying the **exact fixed order**: (1) `None`/empty → return `""` early; (2) trim (`.strip()`); (3) collapse internal whitespace (`re.sub(r"\s+", " ", s)`); (4) Unicode NFKC (`unicodedata.normalize("NFKC", s)`); (5) casefold (`.casefold()`); (6) curly→straight quotes (map `'` `'` → `'` and `"` `"` → `"`, incl. U+2018/2019/201C/201D and prime U+2032/2033 if you choose); (7) strip trailing punctuation (`.rstrip(...)` of `.,;:!?…` and stray quote/space).
  - [ ] **Order is the contract — do not reorder.** NFKC does NOT fold curly quotes to straight, so the explicit quote step is required and must run *after* casefold (casefold never touches quotes; this keeps the order stable and greppable against the documented spec).
  - [ ] Define `NUMERIC_FIELD_KEYS = frozenset({"alcohol_content", "net_contents"})`. For these, after the text pipeline, **additionally parse to number+unit** and return a canonical `"<number> <unit>"` string (e.g. `"45% Alc./Vol."` → `"45 %"`, `"750 mL"` → `"750 ml"`) so format/case/abbrev variants collapse to one comparable form.
  - [ ] Expose a companion `parse_numeric(value: str | None, field_key: str) -> tuple[Decimal | None, str | None]` returning `(number, unit)` for numeric field_keys (`(None, None)` when unparseable). Story 3.3's tolerance bands consume this. **Use `decimal.Decimal`, never `float`** — avoids comparison drift (mirrors the project's "never float math on currency" discipline). Match the unit token case-insensitively and emit a canonical lowercase unit (`%`, `ml`, `l`, `proof`).
  - [ ] Type hints required; `from __future__ import annotations` already present.

- [ ] **Task 2 — Implement `app/verdict.py` (AC2)**
  - [ ] Replace the placeholder body. Implement `rollup(verdicts: Iterable[str]) -> str`: scan once — if any `FAIL` → `"FAIL"`; elif any `REVIEW` → `"REVIEW"`; else `"PASS"`.
  - [ ] Exclude `NA` (not-applicable) check verdicts from the roll-up (filter before scanning). The roll-up **input domain** is the per-check `checklist_items.verdict` enum `{PASS, REVIEW, FAIL, NA}`; the **output domain** is the submission `engine_verdict` enum `{PASS, REVIEW, FAIL}` (no `NA`). "can't-verify" is represented by the caller as `REVIEW` — no separate token.
  - [ ] **Empty / all-`NA` ⇒ `REVIEW`** (defer to human; never silently auto-`PASS` a submission with nothing actually verified — consistent with the determinism taxonomy "ambiguity goes to REVIEW, never silent auto-decision"). Add a test pinning this; if Diane prefers `PASS`-on-empty, it's a one-line change — flag in Completion Notes.
  - [ ] Provide greppable verdict constants + a `Literal` type alias matching `contracts.py` style: `Verdict = Literal["PASS", "REVIEW", "FAIL"]` and module constants `PASS = "PASS"`, `REVIEW = "REVIEW"`, `FAIL = "FAIL"` (and `NA = "NA"` for callers). Strings stay `UPPER_SNAKE` to match the DB `CHECK` enums exactly.
  - [ ] **No import of `disposition.py`, no `verdict → disposition` mapping** anywhere. `engine_verdict` is advisory only.

- [ ] **Task 3 — Create `field_comparisons` + `checklist_items` in `app/db/schema.sql` (AC3)**
  - [ ] Append both `CREATE TABLE IF NOT EXISTS` blocks **verbatim** from `docs/database-schema.md` §1.5 and §1.6, including: the `match_status` CHECK (`MATCH/MISMATCH/MISSING/UNVERIFIABLE`), `similarity` CHECK (0–1), the at-most-one-source CHECK on `field_comparisons`; and the `check_type` CHECK (`DETERMINISTIC/FIELD_MATCH/HYBRID/MANUAL`) and `verdict` CHECK (`PASS/REVIEW/FAIL/NA`) on `checklist_items`.
  - [ ] Add the indexes (`idx_field_comparisons_submission`, `idx_checklist_items_submission`) and the **`v_field_comparisons` view** (derives `extracted_source` by joining `ocr_results`/`llm_results` — both already exist from Story 2.1).
  - [ ] **No `_ADDED_COLUMNS` ledger entry needed** — these are NEW tables; `CREATE TABLE IF NOT EXISTS` makes them with all columns. The ledger in `app/db/connection.py` is only for columns added to *pre-existing* tables. (Read the ledger's header comment before touching it.)
  - [ ] Verify `init_db` still runs idempotently (re-run safe) on both a fresh DB and a re-init.

- [ ] **Task 4 — Tests (AC1, AC2, AC4)**
  - [ ] `tests/test_normalize.py`: **SM-C2 zero-false-FAIL class** — assert `normalize("STONE'S THROW", "brand_name") == normalize("Stone's Throw", "brand_name")` for **both** straight (`'`) and curly (`'`) apostrophe variants. One test per pipeline step (whitespace collapse, NFKC e.g. fullwidth/ligature/accents, casefold, curly→straight `'`/`"`, trailing-punctuation strip), `None`/`""` → `""`, and numeric: `"45% Alc./Vol."` vs `"45 % alc/vol"` equal; `"750 mL"` vs `"750 ml"` equal; `parse_numeric("45% Alc./Vol.", "alcohol_content") == (Decimal("45"), "%")`, unparseable → `(None, None)`.
  - [ ] `tests/test_verdict.py`: any `FAIL` ⇒ `FAIL` (mixed with PASS/REVIEW/NA); no FAIL + any `REVIEW` ⇒ `REVIEW`; all `PASS` ⇒ `PASS`; `NA` excluded; empty + all-`NA` ⇒ `REVIEW`; idempotent/order-independent.
  - [ ] Pure unit tests — no DB, no fixtures, no I/O. (An `init_db`-creates-the-tables assertion may live in `tests/test_repositories.py` or a small schema test; keep `test_normalize.py`/`test_verdict.py` pure.)

- [ ] **Task 5 — Validate + finalize**
  - [ ] `ruff check` + `ruff format` (line length 100); full `pytest` green (no regressions on the existing suite). Update File List + Change Log + Completion Notes.

## Dev Notes

### Scope boundary (what 3.1 IS and is NOT)
- **IS:** two pure centralized contracts — `normalize(value, field_key)` (+ `parse_numeric`) and `rollup(verdicts)` — plus the **creation** of the `field_comparisons` and `checklist_items` tables (+ view + indexes), and their unit tests. These are the foundations the rest of Epic 3 imports.
- **IS NOT:** the **Field Match check** that *uses* `normalize` with tolerance bands (Story **3.3**, `engine/checks/field_match.py`); the **rulesets-as-data executor** that *writes* `checklist_items`/`field_comparisons` and calls `rollup` to set `engine_verdict` (Story **3.2**, `engine/run_checks.py`); the **Government Warning** check (Story 3.4); and **`app/disposition.py`** (its consumer is Epic 4's review workspace — Story 4.8 disposition bar; do **not** author it here). 3.1 defines the contracts and the empty tables; downstream stories write rows. [Source: epics.md Stories 3.2–3.4, 4.8]

### The two contracts are CENTRALIZED — single owner, imported everywhere (anti-pattern: inline re-implementation)
These are 2 of the 4 centralized contracts (`contracts.py` #1 done in 2.1; `disposition.py` #4 later). The whole point is **one implementation each** so nothing diverges. Reject any future inline normalization or ad-hoc verdict math in review. `normalize` is what makes `"STONE'S THROW" == "Stone's Throw"`; `rollup` is used by **both** the engine and the UI so the submission verdict and the Suggested Alert can never disagree. [Source: architecture.md "four centralized contracts"; project-context "import, never re-implement"]

### The normalize order is a frozen contract — implement it EXACTLY
`trim → collapse internal whitespace → Unicode NFKC → casefold → curly→straight quotes → strip trailing punctuation`. Documented identically in project-context contract #2 **and** architecture.md §"Field-match normalization". Numeric fields (`alcohol_content`, `net_contents`) get the extra number+unit parse on top. A reviewer will grep your code against this exact sequence — keep the steps in order and labeled. [Source: project-context contract #2; architecture.md line ~279]

### Numeric return-shape decision (be deliberate)
`normalize` returns a **canonical `str`** for *all* fields (this is what the AC's equality test compares). For numeric fields the canonical string is the *parsed* `"<number> <unit>"` (lowercase unit) so `"45% Alc./Vol."`, `"45 % alc/vol"`, `"45%"` collapse equal. The separate `parse_numeric → (Decimal, unit)` exists because Story 3.3 needs the **numeric value** for tolerance bands (ABV 45 vs 40 → FAIL; small rounding → REVIEW). Keep the parse here (3.1 owns "parse to number+unit"); keep the *tolerance comparison* in 3.3. Use `Decimal`, not `float`. [Source: AC1; epics.md Story 3.3; data-dictionary §`alcohol_content`/`net_contents`]

### Verdict enum + the engine-vs-human firewall
- Per-check verdict (`checklist_items.verdict`) is `PASS/REVIEW/FAIL/NA`; rolled-up `engine_verdict` (on `submissions`) is `PASS/REVIEW/FAIL`. `NA` never propagates. [Source: database-schema.md §1.6, §3.2]
- **"REVIEW" is not a disposition.** `engine_verdict` (advisory machine) and `disposition` (`APPROVED/NEEDS_CORRECTION/REJECTED`, human) are different enums in different modules; **no function maps one to the other**. `verdict.py` must not import `disposition` and must contain no mapping. This is enforced *structurally* in review. [Source: project-context "Recommend, don't decide"; architecture Contract boundary; database-schema §3.2 callout]
- Determinism taxonomy reminder: rule-bound checks are deterministic; ambiguity ⇒ REVIEW (never silent auto-decision); an LLM opinion alone never yields FAIL (capped at REVIEW). 3.1 only provides the *roll-up*; the per-check verdicts come from 3.2–3.7. [Source: project-context "Determinism taxonomy"]

### Table creation pattern (read before touching the DB)
- Schema lives in `app/db/schema.sql`; `app/db/connection.py:init_db` runs `_apply_added_columns` (the no-migration-framework column ledger) **then** `executescript(schema.sql)` with `CREATE … IF NOT EXISTS`. The project rule: **create tables only in the story that needs them** — 3.1 is that story for these two. [Source: app/db/schema.sql header; app/db/connection.py; project-context "Create tables only in the story that needs them"]
- **NEW tables need NO `_ADDED_COLUMNS` entry** (that ledger is exclusively for columns added to a table an *earlier* story already created — see the constant's header comment in `connection.py:34-43`). Copy §1.5/§1.6 DDL faithfully; the `v_field_comparisons` view's `ocr_results`/`llm_results` joins are valid because those tables exist from Story 2.1.
- Raw SQL stays confined to `app/db/` (Data boundary). Do **not** add `field_comparisons`/`checklist_items` insert helpers to `repositories.py` yet — their writers (3.2/3.3) own them (avoid building unused write paths). [Source: architecture Data boundary; app/db/connection.py docstring]

### Previous story intelligence (most-recent done work: 2.1–2.4; 2.5 drafted)
- **`app/contracts.py` (2.1)** sets the house style for these centralized shapes: pure in-memory, `from __future__ import annotations`, `Literal` type aliases for enums, frozen `@dataclass(slots=True)` where a record is needed, derived values as `@property` (the `total_tokens` trap). Mirror it — `normalize`/`verdict` are functions, but use the same `Literal`-alias-for-enum convention. [Source: app/contracts.py]
- **schema.sql grows per story** (2.1 added `ocr_results`/`llm_results`; 2.3/2.4 added columns via the ledger). Follow the established block style + `TODO(postgres)` markers where the §1.5/§1.6 source has them. [Source: app/db/schema.sql; commits 2d9133c, 1c59e2c]
- **Tests mirror `app/`**, `test_*.py`, offline by construction, ruff line 100, type hints. `test_contracts.py` is the closest stylistic precedent for pure-shape tests. [Source: tests/; project-context Testing]
- The placeholder files (`normalize.py`, `verdict.py`) already carry the right docstring + `from __future__ import annotations` — replace the body, keep/extend the docstring. Do not delete `disposition.py`'s placeholder (out of scope, leave as-is).

### Project Structure Notes
- Realized paths nest under `app/` and match the architecture tree exactly: `app/normalize.py`, `app/verdict.py`, `app/db/schema.sql`, `tests/test_normalize.py`, `tests/test_verdict.py`. No conflicts/variances. [Source: architecture.md Project Structure; existing tree]

### Testing standards
- `pytest` in top-level `tests/`, files `test_*.py` mirroring `app/`; ruff (line length 100); type hints required. Highest-value here: `test_normalize.py` (the "STONE'S THROW" class — **zero false-FAIL**, SM-C2) and `test_verdict.py` (severity precedence) — both named in project-context as the project's highest-value tests. Keep them pure (no DB/I/O). [Source: project-context Testing & Tooling]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.1] — story statement + ACs (normalize fixed order + SM-C2; rollup severity precedence; create `field_comparisons`/`checklist_items`).
- [Source: _bmad-output/project-context.md] — contracts #2 (`normalize`) and #3 (`rollup`); "Recommend, don't decide"; determinism taxonomy; "create tables only in the story that needs them"; Testing highest-value tests; anti-patterns (inline normalization, `verdict → disposition` mapping).
- [Source: _bmad-output/planning-artifacts/architecture.md] — the four centralized contracts (lines ~279–280), Contract boundary (`disposition.py` independent of `verdict.py`), Data boundary, Project Structure tree.
- [Source: docs/database-schema.md §1.5 `field_comparisons`, §1.6 `checklist_items`, §3.2 engine-verdict enum] — exact DDL, CHECK enums, the `v_field_comparisons` view, and the `PASS/REVIEW/FAIL` vs per-check `…/NA` distinction.
- [Source: docs/data-dictionary.md §`alcohol_content` (line 89), §`net_contents` (line 90)] — as-filed numeric field formats the parser must canonicalize.
- [Source: app/contracts.py, app/db/schema.sql, app/db/connection.py] — house style for centralized shapes, the schema-growth pattern, and the `_ADDED_COLUMNS` ledger rule (new tables = no entry).

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed - comprehensive developer guide created.

### File List

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-13 | Story 3.1 drafted — centralized `normalize(value, field_key)` (+ `parse_numeric`) and `rollup(verdicts)` contracts, creation of `field_comparisons`/`checklist_items` tables (+ `v_field_comparisons` view), and the SM-C2 / severity-precedence unit tests. Status → ready-for-dev. |
