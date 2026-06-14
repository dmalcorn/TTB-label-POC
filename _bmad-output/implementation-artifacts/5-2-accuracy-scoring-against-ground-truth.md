---
baseline_commit: f80163d90c487c281bff4bf86e6e1c5d08bb93dd
---

# Story 5.2: Accuracy scoring against Ground Truth

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a procurement evaluator,
I want each OCR engine and model scored per field against Ground Truth,
so that I can compare extraction accuracy on the same footing.

## Acceptance Criteria

1. **AC1 — `benchmark/scoring.py` computes field-level match rates per engine/model against Ground Truth.**
   **Given** `app/benchmark/scoring.py` and the seeded corpus (`fixtures/ground_truth.csv` as the gold standard — its `gt_*` columns are the human-verified correct value of every matchable field, never persisted to the DB; see seed.py)
   **When** the harness scores extracted values against ground truth
   **Then** for each matchable `field_key` (**brand_name**, **alcohol_content**, **net_contents**, **applicant_name_address**, **class_type_designation**) it compares the engine/model's extracted value against the `gt_*` value, normalizing **BOTH** sides through the centralized `app/normalize.py` (contract #2 — never inline; numeric fields parse to number+unit), and assigns a `match_status` ∈ `{MATCH, MISMATCH, MISSING, UNVERIFIABLE}` with a `similarity ∈ [0,1]`, **reported per field AND in aggregate** as a field-match rate = MATCH / (MATCH+MISMATCH+MISSING) (UNVERIFIABLE excluded from the denominator and reported separately). *(FR-21; benchmarking-plan §4.2(a), §4.3, §4.4)*

2. **AC2 — Government Warning presence/exactness is scored as a field.**
   **Given** the `gt_government_warning` gold string
   **When** the Government Warning is scored
   **Then** the report carries both a **presence** measure (was a Government-Warning string extracted at all) and an **exactness** measure (normalized-equal to the gold body), distinct from the four field-match fields, so the report can show "Government Warning presence/exactness" per the AC. The deterministic engine's verdict logic is **not** re-implemented here — scoring measures extraction fidelity (does the engine/model read the warning text correctly), reusing `normalize` for the body comparison. *(FR-21; benchmarking-plan §2.3, §4.3 `government_warning` row)*

3. **AC3 — CER (character error rate) is computed per engine/model.**
   **Given** the raw extracted text (`ocr_results.extracted_text` per engine/variant; `llm_results.result_text` per model) and the gold strings
   **When** CER is computed
   **Then** `cer = levenshtein(extracted_norm, gold_norm) / len(gold_norm)` (a pure-stdlib edit-distance, **no new dependency**) is reported per engine/model — the secondary, engine-agnostic accuracy number (benchmarking-plan §4.2(b)). CER is **computed at analysis time, not persisted** (no schema change; `submission_extra_fields` promotion is out of scope). *(FR-21; benchmarking-plan §3 "CER (derived)", §4.2(b))*

4. **AC4 — The figures are reproducible across the seeded corpus.**
   **Given** the same seeded corpus and the same `ocr_results`/`llm_results` rows
   **When** the harness is re-run
   **Then** it produces **identical** figures (deterministic: no wall-clock, no RNG, no dict-ordering dependence — sorted/stable iteration; pure functions over the rows). A test scores the corpus twice and asserts byte-equal aggregate output. *(FR-21 "reproducible"; benchmarking-plan §4)*

5. **AC5 — Preprocessed-vs-original OCR accuracy is comparable from the both-variants rows.**
   **Given** the both-variants `ocr_results` rows (Story 2.4 / AR-7: `image_variant ∈ {ORIGINAL, ENHANCED, BINARIZED}` — the same engine OCR'd the original and the OpenCV-preprocessed image)
   **When** the harness scores OCR accuracy
   **Then** per-engine accuracy is **broken out by `image_variant`** so an evaluator can compare preprocessed (ENHANCED/BINARIZED) against ORIGINAL on the degraded subset — the figure that demonstrates FR-10's "preprocessed > original". The scoring keys on `(engine_name, image_variant)` so the variants are never merged. *(FR-21, AR-7; benchmarking-plan §5.4 step 2, §6 "raw vs preprocessed")*

6. **AC6 — Pure local analysis, zero egress, read-only over the DB.**
   **Given** scoring is a local analysis step
   **When** it runs
   **Then** it performs **DB reads only** (and reads the committed `fixtures/ground_truth.csv`) — it opens **no** off-host connection (the only off-host call sites remain `app/adapters/llm/{openai,google,anthropic}.py`), constructs no provider client, and is **not** on any request/render path (5s contract — AR-5; scoring is a benchmark/report concern, called by Story 5.4, never by `GET /review/{id}`). *(NFR-2, AR-5, AR-8; project-context firewall posture)*

## Tasks / Subtasks

- [ ] **Task 1 — Ground-truth loader (`app/benchmark/scoring.py`) (AC1, AC2)**
  - [ ] Add `load_ground_truth(csv_path: Path | str | None = None) -> dict[str, GroundTruth]` reading `fixtures/ground_truth.csv` (default resolved like `seed.py`'s `FIXTURES_DIR`), keyed by `ttb_id`. Map the `gt_*` columns to a frozen `GroundTruth` dataclass: `brand_name`, `class_type_designation`, `alcohol_content`, `net_contents`, `applicant_name_address`, `government_warning`. Empty cells → `None` (mirror seed.py `_nullify`). Stdlib `csv` only. [Source: app/db/seed.py FIXTURES_DIR + `_nullify`; fixtures/ground_truth.csv header `gt_*`]
  - [ ] Define the matchable `field_key`→`gt_*` mapping as a module constant (`_FIELD_TO_GT`), so the four field-match fields + class/type designation resolve to their gold column. The `field_key`s mirror the submission columns (snake_case, data-dictionary §1). [Source: docs/data-dictionary.md §1; app/db/repositories.py Submission fields]

- [ ] **Task 2 — Per-engine / per-model extracted-value readers (AC1, AC3, AC5)**
  - [ ] Add read helpers (raw SQL stays in `app/db/`, so add thin readers to `app/db/repositories.py`): `list_ocr_results_for_scoring(conn, submission_id) -> list[OcrScoringRow]` returning `(engine_name, image_variant, extracted_text, confidence)` for OK rows; `list_llm_results_for_scoring(conn, submission_id) -> list[LlmScoringRow]` returning `(model_id, model_name, provider, result_text)` for OK `extract_fields` rows. Per-engine/per-model storage is already separate (AR-4) — these surface it for scoring. [Source: app/db/repositories.py existing readers; database-schema.md §1.3/§1.4]
  - [ ] In `scoring.py`, derive per-`field_key` extracted values from the raw text the SAME way the engine does — **reuse, do not re-implement**: for OCR, the engine value is located in the raw `extracted_text` blob; for LLM, parse the `result_text` JSON per `field_key`. Import the existing helpers from `app.engine.checks.field_match` (`_field_from_extraction_json` for LLM JSON; the OCR text is the located candidate). If those private helpers are unsuitable to import, factor the minimal shared parse into a small public function rather than duplicating it — never inline a second normalization. [Source: app/engine/checks/field_match.py `_field_from_extraction_json`, `_extracted_from_ocr_text`]

- [ ] **Task 3 — The scoring rule + CER (AC1, AC2, AC3)**
  - [ ] `score_field(field_key, extracted, gold) -> FieldScore` — normalize BOTH via `normalize.normalize(_, field_key)`; assign `match_status`: normalized-equal (or numeric within the field's tolerance for `alcohol_content`/`net_contents`) ⇒ MATCH/similarity 1.0; both present but below the per-field `τ` ⇒ MISMATCH; gold present & extracted empty ⇒ MISSING; gold absent ⇒ UNVERIFIABLE. Similarity = `difflib.SequenceMatcher` ratio on the normalized strings (same library `field_match.py` uses). Reuse the per-field tolerance constants from `app.engine.checks.field_match` (`ABV_TOLERANCE`, `NET_CONTENTS_TOLERANCE`, `REVIEW_FLOOR` as the text τ) — do not invent new thresholds. [Source: benchmarking-plan §4.3; app/engine/checks/field_match.py thresholds]
  - [ ] `government_warning_score(extracted, gold) -> GovWarningScore` — `present` (extracted non-empty) + `exact` (normalized-equal to gold body). Reuse `normalize`; do NOT re-run the deterministic Gov-Warning verdict engine (this measures extraction fidelity, not compliance). [Source: AC2; benchmarking-plan §2.3, §4.3]
  - [ ] `cer(extracted: str, gold: str) -> float` — pure-stdlib Levenshtein edit distance / `len(gold_norm)`; both sides normalized first; `gold==""` ⇒ define as `0.0` if extracted also empty else `1.0` (documented edge). No new dependency. [Source: benchmarking-plan §4.2(b)]

- [ ] **Task 4 — Aggregation across the corpus (AC1, AC4, AC5)**
  - [ ] `score_corpus(conn, *, csv_path=None) -> CorpusScore` — for every seeded submission (joined to its `ttb_id`→`GroundTruth`), for every `(engine_name, image_variant)` OCR row and every `model_id` LLM row, score each matchable field + Gov Warning + CER, then roll up to **per-engine/per-variant** and **per-model** aggregates: per-`field_key` match rate, overall match rate (MATCH / (MATCH+MISMATCH+MISSING)), UNVERIFIABLE count (reported separately), mean CER, Gov-Warning presence/exactness rates. Iterate in **sorted, stable order** (sort submissions by `ttb_id`, engines/variants/models by key) so re-runs are byte-identical (AC4). Pure functions over the rows — no wall-clock, no RNG. [Source: benchmarking-plan §4.4, §6; AR-4]
  - [ ] Shape the result as frozen dataclasses (`CorpusScore`, `EngineScore` keyed `(engine_name, image_variant)`, `ModelScore` keyed `model_id`, `FieldRate`) so Story 5.4's report screen consumes a typed object. Keep the module **read-only** — it computes and returns; it does **not** write `field_comparisons` (the pipeline owns those — AR-13) or any DB row. [Source: AR-13 pipeline-owns-writes; epics.md Story 5.4 consumes this]

- [ ] **Task 5 — Tests (`tests/test_scoring.py`) (all ACs)**
  - [ ] **Offline by construction** — an in-memory / temp SQLite seeded with a tiny fixture corpus + hand-written `ocr_results`/`llm_results` rows; no provider call, no network. AC1: a brand match across normalization ("STONE'S THROW" vs gold "Stone's Throw") ⇒ MATCH; "45%" vs gold "40%" ⇒ MISMATCH/FAIL band; gold-present-extracted-empty ⇒ MISSING; gold-absent ⇒ UNVERIFIABLE (excluded from the denominator). Per-field AND aggregate rates asserted.
  - [ ] AC2: Gov-Warning presence (empty extraction ⇒ present=False) and exactness (a one-word deviation ⇒ exact=False, present=True; exact gold ⇒ both True).
  - [ ] AC3: `cer` returns 0.0 on an exact (post-normalize) match and a known fraction on a seeded 1-edit string; the empty-gold edge is asserted.
  - [ ] AC4 (reproducible): `score_corpus` run twice over the same DB yields byte-identical aggregate output (e.g. compare a stable `repr`/`asdict`).
  - [ ] AC5 (both-variants): seed ORIGINAL + ENHANCED rows for the same engine with different text; assert the two variants score **separately** (keyed on `(engine_name, image_variant)`), so preprocessed-vs-original is comparable.
  - [ ] AC6 (egress/read-only guard): a structural test asserting `app/benchmark/scoring.py` constructs no off-host client / sets no cloud-trace env (extend the `tests/test_llm_adapters.py` egress-origin reasoning — off-host clients live ONLY under `app/adapters/llm/`); and that scoring issues only SELECTs (no INSERT/UPDATE/DELETE in the module source). [Source: tests/test_llm_adapters.py egress-origin guard; tests/test_tracing.py guard pattern]

- [ ] **Task 6 — Finalize (AC1, AC6)**
  - [ ] `ruff check` + `ruff format` (line length 100); type hints throughout; full `pytest` green (no regressions). Update File List + Change Log + Completion Notes; set Status → review and sprint-status story `5-2` → `review`.
  - [ ] Do NOT touch the report screen (Story 5.4 `GET /benchmark`) or cost stats (Story 5.3 `benchmark/cost.py`) — scoring only produces the accuracy object they consume. [Source: epics.md Stories 5.3, 5.4]

## Dev Notes

### Scope boundary (what 5.2 is and is NOT)
- **IS:** `app/benchmark/scoring.py` — the pure, reproducible, read-only **accuracy scorer**: per-`field_key` and aggregate field-match rates **and** CER, **per OCR engine (broken out by image variant) and per LLM model**, scored against the `fixtures/ground_truth.csv` gold values through the centralized `normalize`; Government-Warning presence/exactness as a scored field; the both-variants (preprocessed-vs-original) breakout.
- **IS NOT:** speed/cost statistics & cost-per-1,000 (Story 5.3 `benchmark/cost.py`), the Benchmark Report screen + `GET /benchmark` (Story 5.4), any new schema column / persisted CER, any `field_comparisons` write (pipeline-owned — AR-13), or any change to the deterministic compliance engine. 5.2 **measures**; 5.4 **renders**. [Source: epics.md Stories 5.3–5.4]

### Ground truth lives in the CSV, never in the DB
`app/db/seed.py` is explicit: *"The Ground Truth (`gt_*`) columns stay in the CSV for the Epic-5 benchmark; the seed writes only APPLICATION values to `submissions`."* So scoring **reads the CSV** (keyed by `ttb_id`) for gold values and joins it to the seeded submissions — it does NOT expect a `ground_truth` table. The header columns are `gt_brand_name, gt_class_type_designation, gt_alcohol_content, gt_net_contents, gt_applicant_name_address, gt_government_warning`. [Source: app/db/seed.py lines 11–12, `FIXTURES_DIR`, `_nullify`; fixtures/ground_truth.csv header]

### Normalize is the contract — reuse it on BOTH sides (the "STONE'S THROW" spine)
The benchmark scores **exactly what the deployed matcher does**: normalize the gold AND the extracted value via `app/normalize.py` (contract #2), then band. This is what makes "STONE'S THROW" == "Stone's Throw" ⇒ MATCH and `45% Alc./Vol.` == `45%` ⇒ MATCH (numeric fields parse to number+unit). **Never inline a second normalization** — import `app.normalize`. Reuse `field_match.py`'s tolerance constants (`ABV_TOLERANCE`, `NET_CONTENTS_TOLERANCE`, `REVIEW_FLOOR`) so the benchmark and the engine agree by construction. [Source: project-context.md contract #2; app/engine/checks/field_match.py; benchmarking-plan §4.3]

### Per-engine/per-model values come from the RAW rows (AR-4), not `field_comparisons`
`field_comparisons` records only the ONE source the engine chose for the displayed extraction (a single `source_ocr_result_id` OR `source_llm_result_id`). To score **every** engine and model independently (benchmarking-plan §4.4 "the same scoring rule runs whether OCR or LLM"), read the raw `ocr_results` rows (per `engine_name` × `image_variant`) and the raw `llm_results` rows (per `model_id`) directly, and derive the per-field value from each using the same parse the engine uses (`_field_from_extraction_json` for LLM JSON; the OCR blob as the located candidate). Per-engine/per-model rows are already stored separately (AR-4), so no merge is needed. [Source: AR-4; app/db/repositories.py; app/engine/checks/field_match.py `_resolve_extracted`]

### VLM-only purity is unaffected (scoring reads outputs, never feeds a model)
Scoring is a pure read/compute step over already-captured rows — it makes **no** model call, so the "OCR text never feeds a model" invariant is untouched. The OCR-vs-model comparison stays an honest head-to-head: each extractor was produced independently (OCR from text, the VLM from the image), and scoring compares both to the same gold string on an identical basis. [Source: project-context.md VLM-only; benchmarking-plan §4.3 note]

### CER is derived, not stored (no schema change)
Per benchmarking-plan §3 ("CER (derived) … Computed at analysis time (not a stored column)") and §4.2(b), CER is `levenshtein(extracted_norm, gold_norm) / len(gold_norm)`, computed and reported, **never persisted**. Implement the edit distance in pure stdlib (a small DP) — do **not** add a dependency. The `submission_extra_fields` promotion mentioned in §3/§9 is explicitly out of scope. [Source: benchmarking-plan §3, §4.2(b), §9 TODO(CER-storage)]

### Reproducibility (AC4 — the spine of "procurement-grade")
The figures must be byte-reproducible: iterate submissions/engines/models/variants in **sorted key order**, use only pure functions over the rows (no `datetime.now()`, no RNG, no set-ordering leak into output), and return `Decimal`/rounded floats deterministically. A test scores the corpus twice and asserts equality. This is what lets an evaluator trust the numbers. [Source: FR-21 "reproducible"; benchmarking-plan §4]

### Firewall / read-only / 5s-contract posture (AC6)
Scoring opens **no** socket and constructs **no** provider client — the only off-host call sites in the app remain `app/adapters/llm/{openai,google,anthropic}.py`. It is DB-read-only (SELECTs over `ocr_results`/`llm_results`/`submissions` + the CSV), writes nothing, and is **never** invoked on a request/render path (AR-5; it is called by the Story-5.4 report, computed ahead of render or as a benchmark step). Mirror the egress-origin guard from `tests/test_llm_adapters.py` / `tests/test_tracing.py`. [Source: NFR-2, AR-5, AR-8; tests/test_llm_adapters.py guard]

### Source tree components to touch
- `app/benchmark/scoring.py` (NEW — `load_ground_truth`, `GroundTruth`, `score_field`, `government_warning_score`, `cer`, `score_corpus`, result dataclasses; reuses `app.normalize` + `field_match.py` constants/parsers; read-only).
- `app/db/repositories.py` (UPDATE — add `list_ocr_results_for_scoring` / `list_llm_results_for_scoring` read helpers; raw SQL stays in `app/db/`).
- `tests/test_scoring.py` (NEW — all-AC coverage incl. reproducibility + both-variants + egress/read-only guard).

### Previous story intelligence
- **5.1** created `app/benchmark/` (now holding `tracing.py`) and established the local-only, zero-egress, lazy-import-disciplined benchmark conventions + the egress-origin guard. 5.2 adds the accuracy scorer alongside it. Reuse the guard pattern and the `get_settings()` convention. [Source: 5-1 story; app/benchmark/tracing.py]
- **2.4 / AR-7** persists the both-variants OCR rows (`image_variant ∈ {ORIGINAL, ENHANCED, BINARIZED}`) precisely so this benchmark can show preprocessed > original — AC5 consumes them. [Source: app/db/repositories.py `insert_ocr_result` image_variant; epics.md Story 2.4]
- **3.3** (`field_match.py`) is the authoritative matcher whose normalization + tolerance this story mirrors — import its constants/parsers, do not fork them. [Source: app/engine/checks/field_match.py]

### Testing standards
- Suite stays **offline by construction** — temp/in-memory SQLite, hand-seeded rows, no provider/network. Highest-value tests: the **"STONE'S THROW" MATCH** + **"45% vs 40%" MISMATCH** scoring class, **reproducibility** (twice ⇒ identical), **both-variants separation**, **Gov-Warning presence/exactness**, and the **egress/read-only guard**. Mirrors `tests/test_normalize.py` and `tests/test_llm_adapters.py` rigor. [Source: project-context.md Testing; benchmarking-plan §4.3]

### Project Structure Notes
- Realized path nests under `app/` (`app/benchmark/scoring.py`) per the architecture tree (`app/benchmark/ … scoring.py`). The story's bare `benchmark/scoring.py` resolves there, alongside `tracing.py`. [Source: architecture.md Project Structure; 5-1 Project Structure Notes]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.2] — story statement + ACs (field-level match rates + CER per engine/model, per-field + aggregate; reproducible; preprocessed-vs-original from both-variants rows).
- [Source: docs/ocr-llm-benchmarking-plan.md §4 Accuracy methodology] — the authoritative method: §4.1 ground-truth seed CSV, §4.2 field-match rate (primary) + CER (secondary), §4.3 normalize-both-then-band scoring rule with per-field τ, §4.4 aggregate to per-engine/per-model rate.
- [Source: docs/ocr-llm-benchmarking-plan.md §2.3, §3] — the matchable extraction tasks (incl. `government_warning`), the metric→column map, CER as derived/not-persisted.
- [Source: app/db/seed.py] — `gt_*` stays in the CSV (not the DB); `FIXTURES_DIR`, `_nullify`.
- [Source: fixtures/ground_truth.csv] — the gold columns: `gt_brand_name, gt_class_type_designation, gt_alcohol_content, gt_net_contents, gt_applicant_name_address, gt_government_warning`.
- [Source: app/normalize.py] — `normalize(value, field_key)` (contract #2) + `parse_numeric`; the single normalization both sides route through.
- [Source: app/engine/checks/field_match.py] — the production matcher whose tolerance constants + per-field parsers this story reuses (no fork).
- [Source: app/db/repositories.py] — existing readers + the pattern for new SELECT-only scoring readers (raw SQL stays in `app/db/`).
- [Source: docs/database-schema.md §1.3/§1.4/§1.5] — `ocr_results` (incl. `image_variant`), `llm_results` (incl. `result_text`, `model_id`), `field_comparisons`.
- [Source: _bmad-output/project-context.md] — contract #2 (normalize), AR-4 (per-engine/model storage), AR-5 (5s read path), AR-13 (pipeline owns `field_comparisons`), firewall posture, VLM-only purity.

## Dev Agent Record

### Agent Model Used

Amelia (dev-story workflow) · claude-opus-4-8

### Debug Log References

`bash scripts/ci.sh` (host venv, Python 3.14) — format + lint + mypy (92 source files,
no issues) + pytest (726 passed, 1 skipped). `tests/test_scoring.py` — 17 passed.

Post-CR (2026-06-14): host pytest 728 passed, 1 skipped; `tests/test_scoring.py` — 19
passed; ruff + mypy clean on the changed source (`app/benchmark/scoring.py`,
`app/db/repositories.py`).

### Completion Notes List

- **AC1** — `score_corpus` reads the RAW `ocr_results` / `llm_results` rows (via the new
  SELECT-only `list_*_for_scoring` readers), not `field_comparisons` (which holds only the
  one chosen source), so every engine/model is scored independently. Both the extracted
  value and the gold are passed through the centralized `app/normalize.py` before banding —
  the benchmark uses the SAME normalizer + matcher constants as production (`field_match`),
  so it agrees with the deployed comparator by construction (no forked thresholds).
- **AC2** — Government Warning scored as presence + exactness (`government_warning_score`),
  separate from the deterministic verdict engine.
- **AC3** — CER derived from a pure-stdlib two-row Levenshtein over normalized strings
  (`_levenshtein` / `len(gold_norm)`), no new dependency, never persisted.
- **AC4** — reproducible: `score_corpus` iterates submissions and engine/model keys in a
  stable sorted order, pure functions, no wall-clock / RNG. `test_scoring_is_reproducible`
  asserts `asdict` equality across two runs.
- **AC5** — preprocessed-vs-original falls out of keying OCR scores by
  `(engine_name, image_variant)`; `test_variants_scored_separately` proves the variants
  score independently. (Fixture note: `_ocr_blob`'s producer line embeds the brand
  verbatim, so the failing-variant blob is fully wrong text — gold absent — to exercise a
  genuine MISMATCH via the whole-blob substring fallback.)
- **AC6** — scoring is read-only (SELECT only) and pure-local: `test_scoring_issues_no_write_sql`
  scans the module source for INSERT/UPDATE/DELETE, and the egress-guard test reuses the
  `_OFF_HOST_CLIENT` regex from `test_llm_adapters.py` to confirm no off-host client is
  imported. VLM-only purity preserved — scoring reads outputs and never feeds a model.

### File List

- `app/benchmark/scoring.py` (new) — ground-truth loader, per-field scoring band, Gov-Warning
  presence/exactness, CER, per-engine/per-model aggregation, `score_corpus`.
- `app/db/repositories.py` (modified) — added `OcrScoringRow`, `LlmScoringRow`,
  `ScoringSubmission` models + `list_submissions_for_scoring`,
  `list_ocr_results_for_scoring`, `list_llm_results_for_scoring` (SELECT-only readers).
- `tests/test_scoring.py` (new) — offline temp-SQLite tests covering AC1–AC6.

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-14 | Story 5.2 drafted — accuracy scoring against Ground Truth (`app/benchmark/scoring.py`): per-field + aggregate field-match rates and CER, per OCR engine (broken out by image variant) and per LLM model, scored vs `fixtures/ground_truth.csv` gold through the centralized `normalize`; Gov-Warning presence/exactness; preprocessed-vs-original from the both-variants rows; reproducible, read-only, zero-egress. Status → ready-for-dev. |
| 2026-06-14 | Story 5.2 implemented test-first (red→green→refactor). Added `app/benchmark/scoring.py` + 3 SELECT-only scoring readers in `repositories.py` + `tests/test_scoring.py` (17 tests). Full CI green (726 passed, 1 skipped; mypy + ruff clean). Status → review. |
| 2026-06-14 | Code review (CR). Patched two findings: (F4, HIGH) `_gov_warning_value` no longer falls back to the raw JSON blob when an LLM payload omits `government_warning` — a JSON object is now detected (`_is_json_object`) and its field lookup is authoritative, so an absent warning scores `present=False` and is not fed into CER (previously corrupted AC2 presence + AC3 CER for any model omitting the field). (F6, efficiency/consistency) `score_corpus` fetches the submission list ONCE and derives both the loop and `scored_submissions` from it (removed a redundant second `list_submissions_for_scoring` query). Added 2 regression tests (gov-warning JSON-without-field via `score_corpus`; the `_gov_warning_value` JSON-vs-blob discriminator). Three benchmark-vs-production-fidelity findings (near-miss-as-MATCH banding, OCR-confidence-floor omission, short-gold substring) recorded in `deferred-work.md` as deliberate, story-spec-conformant metric definitions for Diane to adjudicate. Full host CI green (728 passed, 1 skipped; mypy + ruff clean). Status → done. |
