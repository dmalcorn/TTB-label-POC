---
baseline_commit: ec71fa057eb6efc54258e78a7cafa40cb67db6b4
---

# Story 2.4: Tesseract + PaddleOCR extraction (both image variants)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a procurement evaluator,
I want at least two OCR engines run independently over each submission's images, on both the original and preprocessed variants,
so that per-engine accuracy is comparable and the preprocessing benefit is measurable.

## Acceptance Criteria

1. **AC1 — Two real OCR adapters implementing the `OcrEngine` protocol → `OcrResult`.**
   **Given** `app/adapters/ocr/tesseract.py` and `app/adapters/ocr/paddleocr.py`, each implementing the `OcrEngine` protocol (`app/adapters/ocr/base.py`) and returning the centralized `OcrResult` shape from `app/contracts.py`
   **When** an engine runs on an image **Then** it returns `engine_name`, `engine_version`, `text`, `word_boxes`, `confidence` (0–1), `latency_ms`, `ran_on_cpu`, `status` — **no per-engine bespoke dict**, no re-implemented shape. *(FR-11, AR-3 #1, AR-4)*

2. **AC2 — Independent per-engine rows; raw text only (not per-field parsing).**
   **Given** the `ocr_results` table (created by 2.1)
   **When** both engines OCR an image **Then** each engine writes its **own** `ocr_results` row (independently queryable by `engine_name`), storing the engine's **full raw `extracted_text` + per-run metadata** — **not** a column per matchable field. Per-field parsing (brand/ABV/…) into `field_comparisons` is the **Epic 3 analysis job**, not this story. *(FR-11, AR-4, data-dictionary.md §3, database-schema.md §1.3)*

3. **AC3 — Both image variants OCR'd for the degraded subset; the row records which variant it consumed.**
   **Given** the enhanced/binarized variants produced by Story 2.3 (`label_images.enhanced_path`/`binarized_path`)
   **When** the OCR stage runs on a degraded-fixture image **Then** OCR runs on **both** the original and the OpenCV-preprocessed variant, storing **both** `ocr_results` rows, and each row records **which variant it consumed** via a new `image_variant` discriminator (`ORIGINAL` / `ENHANCED` / `BINARIZED`) — so Epic 5 can score preprocessed-vs-original accuracy. A clean image with no variants runs on the **original only**. *(FR-11, AR-7, image-handling.md §3)*

4. **AC4 — PaddleOCR loads baked-in offline weights; zero runtime download; CPU-only.**
   **Given** PaddleOCR model weights baked into `models/` at build time (Dockerfile)
   **When** PaddleOCR initializes **Then** it loads weights from the local `models/` path with **no runtime network download**, and `ran_on_cpu` reflects CPU-only execution. The whole OCR stage runs under `docker run --network none`. *(FR-11, AR-8, outbound-calls-inventory.md TODO-2)*

5. **AC5 — Engine-aware variant routing; failures are honest, never fatal.**
   **Given** the engine-aware note (Tesseract↔binarized, PaddleOCR↔enhanced) and the 2.2 failure contract
   **When** an engine fails on an image (crash/unreadable) **Then** an `ERROR`-status `ocr_results` row is written with `error_text`, the other engine/image still runs, and the submission still finalizes (no stuck `PROCESSING`); the OCR stage registers into the 2.2 seam with **no scheduler/status change**. *(FR-11, image-handling.md §3 engine-aware note; 2.2 failure path)*

## Tasks / Subtasks

- [x] **Task 1 — Schema: `image_variant` discriminator on `ocr_results` (AC3)**
  - [x] Add `image_variant TEXT NOT NULL DEFAULT 'ORIGINAL' CHECK (image_variant IN ('ORIGINAL','ENHANCED','BINARIZED'))` to `app/db/schema.sql` `ocr_results`. Add an index `idx_ocr_results_variant` (or extend an existing index) if helpful for the benchmark roll-up.
  - [x] **Update the authoritative docs:** add the `image_variant` column to `docs/database-schema.md` §1.3 and `docs/data-dictionary.md` §3 with rationale (AR-7 both-variants comparison) — this column did not exist in the original schema because both-variant OCR was an architecture-era addition (D7/AR-7). [Source: database-schema.md §1.3; AR-7]
  - [x] Update `insert_ocr_result(...)` in `app/db/repositories.py` (added by 2.1) to accept and persist `image_variant` (default `'ORIGINAL'`). Keep the contract→column mapping from 2.1 (`OcrResult.text → extracted_text`; `word_boxes` list → `json.dumps`).

- [x] **Task 2 — `app/adapters/ocr/tesseract.py` (AC1, AC5)**
  - [x] Implement `TesseractEngine` satisfying `OcrEngine` (`name`, `version`, `extract(image_path, *, ran_on_cpu=True) -> OcrResult`) via `pytesseract`. Capture `text` (full), `word_boxes` from `image_to_data` (list of `{text, box, conf}`), a mean `confidence` normalized to **0–1** (pytesseract reports 0–100 → divide by 100; drop `-1` sentinels), `latency_ms` via `time.monotonic`, `engine_version` from `pytesseract.get_tesseract_version()`.
  - [x] On exception return `OcrResult(engine_name='tesseract', status='ERROR', ...)` (the writer adds `error_text`); never raise into the stage.

- [x] **Task 3 — `app/adapters/ocr/paddleocr.py` (AC1, AC4, AC5)**
  - [x] Implement `PaddleOcrEngine` satisfying `OcrEngine` via `paddleocr`. Point it at the **baked-in offline weights** in `models/` (constructor args / env for model dir; disable any auto-download). Map PaddleOCR output to `OcrResult`: concatenate line texts → `text`; per-line boxes+scores → `word_boxes`; mean line score → `confidence` (already ~0–1); `latency_ms`; `engine_version` from the paddleocr package version; `ran_on_cpu=True`.
  - [x] Lazy-init the model once (module-level/singleton) — PaddleOCR init is expensive; do not re-init per image. Initialization must not hit the network.
  - [x] On exception → `OcrResult(engine_name='paddleocr', status='ERROR', ...)`; never raise into the stage.

- [x] **Task 4 — `app/pipeline/` OCR stage + variant routing (AC2, AC3, AC5)**
  - [x] Add the OCR stage (e.g. `app/pipeline/ocr.py` or a function in `run.py`) registered into `run.STAGES` **after** `preprocess_stage` (2.3). For each `label_image`: build the list of `(variant, path)` to OCR — always `('ORIGINAL', filename)`; plus `('BINARIZED', binarized_path)` and/or `('ENHANCED', enhanced_path)` when 2.3 produced them.
  - [x] **Engine-aware routing:** run **Tesseract on the binarized variant** (fallback original) and **PaddleOCR on the enhanced variant** (fallback original); for the degraded subset this yields the original **and** preprocessed rows per engine (AR-7). Persist each via `insert_ocr_result(..., image_variant=...)`.
  - [x] Use the engine **protocols**, never concrete imports in the stage beyond construction — iterate a list of configured `OcrEngine`s so adding PP-OCRv5 later is a new adapter + one registry line, no stage change (AR-4). Record `OCR_STARTED`/`OCR_COMPLETED` audit markers (or rely on 2.2's stage markers) and accumulate latency into `processing_ms`.
  - [x] Honor the 2.2 failure contract: an engine `ERROR` row does not abort the submission; siblings continue; the row still finalizes.

- [x] **Task 5 — Dependencies + offline weights (AC4)**
  - [x] Add `pytesseract` and `paddleocr ~=3.4` to `requirements.txt` (pin to `approved-tech-stack.md`). `tesseract-ocr` system binary is already installed in the Dockerfile (Story 1.1 AC); verify the language data is present.
  - [x] Dockerfile: bake PaddleOCR weights into `models/` at **build** time (`COPY models/ models/` / a pinned fetch at build), so runtime never downloads. Document the pinned weight versions. Verify the egress smoke test (`docker run --network none`) still completes the OCR stage. [Source: architecture.md D7/Infrastructure; outbound-calls-inventory.md TODO-2]

- [x] **Task 6 — Tests (`tests/test_ocr_adapters.py`, extend `tests/test_pipeline.py`) (all ACs)**
  - [x] **Unit (offline, no native engines):** assert both adapter classes satisfy `isinstance(x, OcrEngine)` (runtime-checkable protocol) and that a **stubbed** `extract` returns a valid `OcrResult` with `confidence` in 0–1 and `status` in `{OK,ERROR}`. Do **not** require real Tesseract/Paddle in the default suite (keep CI offline + fast) — gate any real-engine test behind a marker/skip-if-unavailable.
  - [x] AC2/AC3 (stage, stubbed engines): register two stub engines into the OCR stage against a `tmp_path` DB with a `label_image` that has `binarized_path`/`enhanced_path` set (from a faked 2.3 run) → assert **multiple `ocr_results` rows**, independently queryable by `engine_name`, with the correct `image_variant` per row (ORIGINAL + ENHANCED/BINARIZED). A `label_image` with no variants → original-only rows.
  - [x] AC1: confidence normalization (a Tesseract-style 0–100 input maps to 0–1) — unit test the mapping helper.
  - [x] AC5: a stub engine that raises → an `ERROR` `ocr_results` row with `error_text`, sibling engine row still written, submission still reaches `READY_FOR_REVIEW`.
  - [x] Confirm **no per-field columns** were added to `ocr_results` (structural guard: the table stores raw text only; field parsing is Epic 3).

- [x] **Task 7 — Validate + finalize**
  - [x] `ruff check` + `ruff format` (line length 100); full `pytest` green (no regressions). OCR stage runs under `docker run --network none` with baked weights. *(ruff clean; 156 passed, 1 skipped. The `--network none` smoke test is a Docker-build/CI gate — see Completion Notes.)*
  - [x] Update File List + Change Log + Completion Notes; note the `image_variant` schema + doc edits.

### Review Findings

_Code review 2026-06-13 (Blind Hunter · Edge Case Hunter · Acceptance Auditor). ACs 1, 2, 3, 5 verified satisfied; AC4 flagged below._

- [x] [Review][Patch] PaddleOCR offline-weights wiring — env-var mismatch (AC4 / firewall NFR-2) [app/adapters/ocr/paddleocr.py:62-71; Dockerfile:15,40-41; requirements.txt:27] — The adapter keys its explicit weights-dir pinning off `PADDLEOCR_MODEL_DIR`, but the Dockerfile only sets `PADDLE_PDX_CACHE_HOME` and never `PADDLEOCR_MODEL_DIR`. So the `det_model_dir`/`rec_model_dir` branch is dead in the shipped image; offline loading rests entirely on the build-time cache warmup populating the default cache home — there is no explicit auto-download-disable, contrary to AC4 Dev Notes ("point PaddleOCR at the baked dir with auto-download disabled"). `requirements.txt:27` ("loaded from `PADDLEOCR_MODEL_DIR`") is factually wrong. **Resolution (review decision, option 1): activate the explicit branch** — set `PADDLEOCR_MODEL_DIR` in the Dockerfile to the baked dir + verify the `det/`/`rec/` layout on a build host, and fix the requirements.txt comment. ⚠️ Build-host verification of the directory layout and the `det_model_dir`/`rec_model_dir` kwargs validity for `paddleocr ~=3.4` is required (cannot be confirmed in this dev environment). [blind+auditor]
- [x] [Review][Patch] DB insert sits outside the failure-isolation guard — a row-level CHECK/Integrity error aborts the whole submission (AC5) [app/pipeline/ocr.py:137-144] — `repo.insert_ocr_result(...)` is outside the `try/except` that wraps `engine.extract`. A concrete trigger: PaddleOCR `confidence` is unclamped (`app/adapters/ocr/paddleocr.py:169`); a build returning a line score > 1.0 yields `confidence > 1`, hits `ocr_results.confidence CHECK BETWEEN 0 AND 1`, raises `IntegrityError`, and aborts the submission (stuck `PROCESSING`) — defeating the AC5 "siblings survive / submission finalizes" guarantee. Fix: wrap the persist per (engine,image,variant) so a DB error degrades to a logged skip/ERROR; clamp confidence to ≤1. [edge]
- [x] [Review][Patch] PaddleOCR module singleton is not thread-safe [app/adapters/ocr/paddleocr.py:78-89] — `_get_model()` does check-then-build on the `_model`/`_model_init_failed` module globals with no lock. Under concurrent submission processing two callers can double-run the heavy init or race on `_model`. Fix: guard with a module-level `threading.Lock`. (Latent if the sweep is strictly single-threaded; new code regardless.) [blind+edge]
- [x] [Review][Patch] ORIGINAL task queued with an empty path when `info["original"]` is falsy [app/pipeline/ocr.py:88] — `("ORIGINAL", info["original"] or "")` resolves an empty basename to the images **directory**, manufacturing a guaranteed ERROR row instead of skipping. Near-unreachable (preprocess always stashes a filename) but a one-line defensive guard. Fix: skip the ORIGINAL task when the basename is falsy. [blind+edge]

_Dismissed as noise (6): PaddleOCR `ran_on_cpu` param decoupled from hard-coded `device='cpu'` (latent, stage never passes False); redundant `_resolve_version()` per-image on the Paddle OK path (best-effort metadata); `_iter_lines` silently dropping unknown shapes (defensive by design, no clear correct alternative); `error_text = repr(exc)` embedding a filesystem path (not a secret); Tesseract `_text_from_data`/`_word_boxes_from_data` parallel-array index access (DICT output arrays are equal-length by Tesseract's contract — unreachable)._

**Resolution (2026-06-13):** all 4 patches applied; ruff clean; 156 passed, 1 skipped (unchanged). Changes:
- **AC4 wiring** — Dockerfile now sets `PADDLEOCR_MODEL_DIR=/app/models/paddlex`; the adapter pins det/rec explicitly **only when that baked layout exists on disk**, else falls back to the warmed `PADDLE_PDX_CACHE_HOME` (both offline) so a layout mismatch can never re-enable a download; `requirements.txt` comment corrected.
- **AC5 persist guard** — `_run_and_persist` wraps the insert; a row-level `sqlite3.Error` logs + writes a minimal ERROR row instead of aborting the submission. PaddleOCR row-level confidence clamped to 0–1.
- **Thread-safety** — `_get_model()` now uses double-checked locking (`_model_lock`).
- **Empty-path guard** — `_tasks_for_engine` skips the ORIGINAL task when the basename is falsy.

> ⚠️ **Carried to build host (firewall gate, was already deferred at delivery):** verify the `det/`/`rec/` bake layout under `PADDLEOCR_MODEL_DIR` and the `det_model_dir`/`rec_model_dir` kwarg validity for `paddleocr ~=3.4`, and run the `docker run --network none` OCR smoke test. The runtime path is offline-correct via the cache fallback regardless; full explicit pinning activates once the layout is baked.

### Build Blocker → RESOLVED (found & fixed 2026-06-13 by actually building + running the image in Docker)

Three real defects surfaced that the offline host suite structurally could not catch (the Epic-2 image had never been built — only `ttb-label-poc:1.1–1.6` existed). All fixed and validated end-to-end under `docker run --network none`:

- [x] [Build][Blocker] **`docker build` failed at the PaddleOCR weight-bake (AC4)** — `ModuleNotFoundError: No module named 'paddle'`. `paddleocr` does not depend on the `paddlepaddle` inference framework; it was listed in **neither** `requirements.txt` **nor** `approved-tech-stack.md`. **Fix:** added `paddlepaddle~=3.0` (CPU) to `requirements.txt` + recorded in `approved-tech-stack.md §9`.
- [x] [Build][Hardening] **Suppressed the PaddleOCR model-source connectivity probe** — set `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` in the Dockerfile ENV so neither build nor the cached-weights runtime makes the "checking the model hosters" outbound call (clean `--network none`).
- [x] [Build][Blocker] **Real PaddleOCR inference crashed at runtime** — `NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]` in `onednn_instruction.cc`: the oneDNN backend in paddlepaddle 3.x can't run PP-OCRv5 on this CPU. Global `FLAGS_use_mkldnn`/`FLAGS_enable_pir_api` are ignored (PaddleX sets its own pp_option). **Fix:** `_build_model` now passes `enable_mkldnn=False` (native CPU kernels). Verified: the adapter OCRs a synthetic label `status=OK text='STONES THROW' conf=0.996` offline.
- Confirmed: the warmup bakes weights under `$PADDLE_PDX_CACHE_HOME/official_models/<MODEL_NAME>` — there is **no `det/`/`rec/` layout**, validating the P1 disk-gated fallback (it correctly declines to mis-pin).

**End-to-end Docker validation (all under `--network none`, Python 3.13):**
- ✅ Image builds; the `assert weights baked` gate passes (AC4 build-time).
- ✅ Real **Tesseract** smoke OCRs synthetic text (`test_tesseract_reads_synthetic_text` — skipped on host, passes in-container).
- ✅ Real **PaddleOCR** loads baked weights + OCRs offline via the adapter (`status=OK`, conf 0.996).
- ✅ OCR/pipeline suite: 34 passed. App boots and serves `/healthz` with zero network.
- ⚠️ **Follow-up (non-blocking):** image is now **~2.82 GB** (paddlepaddle + PP-OCRv5 `server` det weights) vs 734 MB at 1.6. Worth revisiting `mobile` model variants / slimming before the slim-container goal hardens. The 7 `test_deploy_config.py` failures seen in-container are host-context tests (repo-root files not shipped in the image) — they pass on the host; **not regressions**.

## Dev Notes

### Scope boundary (what 2.4 is and is NOT)
- **IS:** the two real OCR adapters, the `image_variant` discriminator on `ocr_results`, the both-variants OCR stage with engine-aware routing, and offline PaddleOCR weights.
- **IS NOT:** per-field extraction/parsing (brand/ABV → `field_comparisons`) — that is the **Epic 3 analysis job** [Source: data-dictionary.md §3 "not a column per matchable field … persisted separately in field_comparisons"]. Not the LLM (2.5). Not preprocessing itself (2.3 produces the variants; 2.4 consumes them).

### "Per-field values" is a red herring here — store RAW text only (critical)
The epic AC says "each engine's text, **per-field values**, confidence, and latency are stored separately." The authoritative data model is explicit that `ocr_results` holds the engine's **full raw text + metadata, NOT a column per matchable field**; the **parsed per-field values land in `field_comparisons.extracted_value` keyed by `field_key`** — written by the **analysis job (Epic 3)**, not the OCR job. So in 2.4: **do not** add `brand_name`/`abv`/… columns to `ocr_results` and **do not** parse fields. Persist `extracted_text` + `word_boxes` + `confidence` + `latency_ms`. [Source: docs/data-dictionary.md §3 intro; docs/database-schema.md §1.3, §5 "OCR job: one row per engine per image"]

### The `image_variant` discriminator (the schema gap this story closes)
`ocr_results` (from 2.1, copied verbatim from the doc) has **no way to tell** a row OCR'd on the original from one OCR'd on the enhanced variant — both share `engine_name` + `label_image_id`. AR-7 requires **both** rows for the degraded subset so Epic 5 can score "preprocessed > original." This story adds `image_variant ∈ {ORIGINAL, ENHANCED, BINARIZED}` (default `ORIGINAL`) — the minimal, greppable `TEXT + CHECK` discriminator consistent with the naming conventions. This pairs with the `enhanced_path`/`binarized_path` columns 2.3 added to `label_images`. [Source: AR-7; architecture.md D7; image-handling.md §3 TODO "per-engine variant routing … record it per ocr_results row"]

### Engine-aware routing (image-handling §3)
Tesseract → **binarized** input; PaddleOCR/PP-OCRv5 → **enhanced grayscale/color** input. Always also OCR the **original** so original-vs-preprocessed is comparable. When 2.3 produced no variant (clean image), fall back to the original for that engine. Keep the routing in the stage (data-driven from a small config map), not hard-coded inside the adapters — adapters are variant-agnostic; they OCR whatever path they're handed. [Source: image-handling.md §3 engine-aware note]

### Confidence normalization (0–1 invariant)
`OcrResult.confidence` and the `ocr_results.confidence` CHECK are **0–1**. pytesseract's `image_to_data` reports **0–100** (with `-1` for non-text) → divide by 100, drop `-1`s, mean over valid words. PaddleOCR line scores are already ~0–1. Get this wrong and the CHECK constraint rejects the insert. [Source: database-schema.md §1.3 `confidence CHECK BETWEEN 0 AND 1`; data-dictionary.md §3]

### Offline weights (firewall proof)
PaddleOCR downloads weights on first run by default — **forbidden** at runtime. Bake pinned weights into `models/` at build and point PaddleOCR at that dir with auto-download disabled. Tesseract is a system binary + language data, both installed in the image (Story 1.1). The OCR background job is classified **`none`** in the outbound inventory — it must make zero network calls. [Source: outbound-calls-inventory.md rows "Tesseract"/"PaddleOCR" + TODO-2; architecture.md D7]

### Adapter boundary (AR-4 — swap = new file)
The stage iterates a registry of `OcrEngine` protocol instances; adding PP-OCRv5 = a new `app/adapters/ocr/ppocrv5.py` + one registry entry, **no schema/stage/caller change**. This is the procurement "swap-and-compare" guarantee 2.1's stub-engine test already proves; 2.4 must not regress it (no concrete-engine branching inside the stage logic). [Source: architecture.md Adapter boundary, D5; 2-1 story AC3]

### Failure handling (inherit 2.2)
Reuse Story 2.2's failure contract: a per-engine/per-image failure → an `ERROR` `ocr_results` row (`status='ERROR'`, `error_text` set) + the submission still finalizes; never let one engine crash abort the submission or the sweep. An image unreadable by **all** engines after enhancement → leave it for the engine layer (Epic 3) to flag `REVIEW`; 2.4 does not decide verdicts. [Source: 2-2 story Task 4; image-handling.md §4]

### Architecture / boundary rules this story must honor
- **Pipeline-only writer** of `ocr_results`; **data boundary** (SQL in `app/db/`); **5s contract** (OCR is background only, never request-time). [Source: architecture.md boundaries, Process Patterns]
- **No egress** — `--network none` must pass with baked weights. [Source: architecture.md External boundary]

### Source tree components to touch
- `app/adapters/ocr/tesseract.py`, `app/adapters/ocr/paddleocr.py` (NEW — `base.py` protocol from 2.1).
- `app/pipeline/ocr.py` (NEW) or OCR stage fn in `app/pipeline/run.py` (UPDATE — register after preprocess).
- `app/db/schema.sql` (UPDATE — `image_variant` column + index).
- `app/db/repositories.py` (UPDATE — `insert_ocr_result` gains `image_variant`).
- `requirements.txt` (UPDATE — `pytesseract`, `paddleocr`).
- `Dockerfile` (UPDATE — bake PaddleOCR weights into `models/`).
- `docs/database-schema.md` §1.3 + `docs/data-dictionary.md` §3 (UPDATE — document `image_variant`).
- `tests/test_ocr_adapters.py` (NEW); `tests/test_pipeline.py` (UPDATE).

### Previous story intelligence
- **2.1** built `OcrResult`, the `OcrEngine` protocol, `ocr_results`, and `insert_ocr_result` with the `text→extracted_text` + `word_boxes→json.dumps` mapping and the stub-engine proof. Reuse all of it; extend `insert_ocr_result` for `image_variant` rather than writing a new path. [Source: 2-1 story Tasks 1,3,4,5]
- **2.2** owns the stage seam + failure contract; **2.3** produces `enhanced_path`/`binarized_path` on `label_images` and stashes them in `ctx.scratch`. Consume both. [Source: 2-2, 2-3 stories]

### Testing standards
- Keep the default suite **offline and native-dep-free**: use **stub `OcrEngine`s** for stage/persistence tests; gate real-Tesseract/real-Paddle tests behind availability skips. Highest-value: **independent per-engine rows**, **correct `image_variant` per row**, **confidence 0–1 normalization**, **ERROR-row on failure with siblings surviving**, and the **no-per-field-columns** structural guard. [Source: project-context.md Testing; 2-1 test pattern]

### Project Structure Notes
- Realized paths nest under `app/` (`app/adapters/ocr/…`, `app/pipeline/…`). [Source: 2-1/2-2 Project Structure Notes; architecture.md tree]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.4] — story statement + ACs (incl. AR-7 both-variants, AR-8 offline weights).
- [Source: docs/database-schema.md §1.3] `ocr_results` columns + `confidence` 0–1 CHECK + per-engine independence; [§5] OCR-job-written; [data-dictionary.md §3] raw-text-not-per-field + `field_comparisons` relocation.
- [Source: docs/image-handling.md §3] engine-aware variant routing + "record per ocr_results row" TODO; [§4] unreadable → REVIEW downstream.
- [Source: _bmad-output/planning-artifacts/architecture.md D5] uniform OCR adapter interface; [AR-4/Adapter boundary] swap = new file; [AR-7] both-variants; [AR-8/D7] baked offline weights.
- [Source: docs/outbound-calls-inventory.md] Tesseract/PaddleOCR classified `none`; TODO-2 pin weights offline.
- [Source: _bmad-output/project-context.md] contract #1; anti-patterns (per-engine bespoke result dicts; merged-only storage; OCR on a read path).
- [Source: app/contracts.py, app/adapters/ocr/base.py, app/db/repositories.py (2.1), app/pipeline/run.py (2.2), app/pipeline/preprocess.py (2.3)] foundations to build on.

## Dev Agent Record

### Agent Model Used

Amelia (bmad-dev-story) · claude-opus-4-8[1m]

### Debug Log References

- Resolver script (`resolve_customization.py`) could not run — no Python on the Bash PATH; workflow + agent blocks resolved manually from `customize.toml` (no team/user overrides present). Tests run via the project `.venv` (Python 3.14, pytest 9.0.3) through PowerShell.

### Completion Notes List

- **Test-first, all ACs green:** baseline was 144 passing; final suite **156 passed, 1 skipped** (the skip is the gated real-Tesseract smoke test — `pytesseract`/Pillow are absent locally), ruff check + format clean (line length 100).
- **AC1 — two real adapters on the protocol:** `app/adapters/ocr/tesseract.py` (`TesseractEngine`) and `app/adapters/ocr/paddleocr.py` (`PaddleOcrEngine`), both returning the centralized `OcrResult` (no per-engine dict). `pytesseract`/`paddleocr` are imported **lazily inside `extract`** so importing/registering the engines — and booting the app under `--network none` — needs zero native deps; that's what keeps the default suite offline. Confidence is normalized to 0–1 (`normalize_confidence` unit-tested: 0–100 → 0–1, `-1`/None dropped, empty → `None`).
- **AC2 — independent per-engine rows, raw text only:** the stage writes one `ocr_results` row per (engine, image, variant), independently queryable by `engine_name`; no per-field columns were added (structural guard test). Per-field parsing stays Epic 3.
- **AC3 — both variants + discriminator:** new `ocr_results.image_variant` (`ORIGINAL`/`ENHANCED`/`BINARIZED`, default `ORIGINAL`, `TEXT + CHECK`) + index `idx_ocr_results_variant (engine_name, image_variant)`; documented in `database-schema.md` §1.3 and `data-dictionary.md` §3. A degraded image yields original + preferred-variant rows per engine; a clean image is original-only.
- **AC4 — offline PaddleOCR weights:** Dockerfile bakes the pinned PP-OCRv5 weights at **build** time via a warmup into `PADDLE_PDX_CACHE_HOME` (build fails loudly if weights aren't baked); runtime loads from disk, zero egress. `ran_on_cpu=True` (CPU-only). **The `docker run --network none` smoke test is a Docker-build/CI gate, not runnable in this dev environment** (no Docker here) — the code path is import-safe and egress-free by construction; flagged for the reviewer to confirm on a build host.
- **AC5 — honest, non-fatal failures:** adapters self-guard (return `ERROR`, never raise); the stage *also* guards each call and writes an `ERROR` row with `error_text` (real exception repr when an engine raises; a specific note when an adapter self-caught). Siblings still run; the submission still finalizes to `READY_FOR_REVIEW` (inherits the 2.2 contract).
- **Seam:** `passthrough_stage` (2.2 placeholder) was removed; `ocr_stage` replaces it in `run.STAGES = [preprocess_stage, ocr_stage]` and now owns the `OCR_STARTED`/`OCR_COMPLETED` markers, so the existing 2.2 timeline test is unchanged. Engine-aware routing is data-driven in the stage (`ENGINE_PREFERRED_VARIANT`), never branching on a concrete engine type (AR-4) — adding PP-OCRv5 is a new adapter file + one line in `build_engines`.

### File List

- `app/adapters/ocr/tesseract.py` (NEW) — `TesseractEngine` + `normalize_confidence` helper.
- `app/adapters/ocr/paddleocr.py` (NEW) — `PaddleOcrEngine` with module-level singleton + offline-weights init.
- `app/pipeline/ocr.py` (NEW) — `ocr_stage` + engine-aware variant routing (`build_engines`, `ENGINE_PREFERRED_VARIANT`).
- `app/pipeline/run.py` (MOD) — removed `passthrough_stage`; `STAGES = [preprocess_stage, ocr_stage]`; docstring update.
- `app/db/schema.sql` (MOD) — `ocr_results.image_variant` column + `idx_ocr_results_variant`.
- `app/db/repositories.py` (MOD) — `insert_ocr_result(..., image_variant='ORIGINAL')`.
- `requirements.txt` (MOD) — `pytesseract~=0.3`, `paddleocr~=3.4`.
- `Dockerfile` (MOD) — `PADDLE_PDX_CACHE_HOME` env + build-time PaddleOCR weight bake/warmup; `eng` language-data note.
- `docs/database-schema.md` (MOD) — §1.3 `image_variant` column + DDL + index.
- `docs/data-dictionary.md` (MOD) — §3 `image_variant` field row.
- `tests/test_ocr_adapters.py` (NEW) — protocol conformance (offline), confidence-mapping units, adapter ERROR self-guard, skip-gated real-engine smoke test.
- `tests/test_pipeline.py` (MOD) — OCR-stage routing (both-variants + clean-image), engine-failure/sibling-survives, no-per-field-columns guard.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (MOD) — 2.4 → in-progress → review.

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-12 | Story 2.4 drafted — Tesseract + PaddleOCR adapters on the OcrEngine protocol, both-image-variants OCR with a new `ocr_results.image_variant` discriminator, engine-aware routing, offline baked PaddleOCR weights, raw-text-only persistence (per-field parsing deferred to Epic 3). Status → ready-for-dev. |
| 2026-06-13 | Story 2.4 implemented (test-first). New OCR adapters (`tesseract.py`, `paddleocr.py`) on the `OcrEngine` protocol with lazy native imports; new `ocr_stage` with engine-aware variant routing replacing 2.2's `passthrough_stage`; `ocr_results.image_variant` discriminator + index + doc edits; offline PaddleOCR weight bake in the Dockerfile; `pytesseract`/`paddleocr` pinned. Tests: `test_ocr_adapters.py` (new) + `test_pipeline.py` (stage routing/failure/structural guard). 156 passed, 1 skipped; ruff clean. Status → review. |
| 2026-06-13 | Code review (Blind Hunter · Edge Case Hunter · Acceptance Auditor): ACs 1/2/3/5 verified; 4 patches applied — AC4 `PADDLEOCR_MODEL_DIR` wiring + disk-gated det/rec pinning (Dockerfile, `paddleocr.py`, `requirements.txt`); AC5 stage persist guard + ERROR-row fallback; PaddleOCR confidence clamp; thread-safe model singleton (`_model_lock`); empty-path ORIGINAL guard (`ocr.py`). ruff clean; 156 passed, 1 skipped. Build-host firewall verification carried forward. Status → done. |
| 2026-06-13 | Docker build validation (Docker Desktop available locally) reverted done → in-progress: the Epic-2 image had never built. Fixed 3 build/runtime defects — missing `paddlepaddle~=3.0` dep (AC4 weight-bake `ModuleNotFoundError: paddle`); `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` for clean `--network none`; `enable_mkldnn=False` (oneDNN inference crash on CPU). Validated end-to-end under `--network none`: image builds, real Tesseract + real PaddleOCR OCR offline (Paddle `status=OK`, conf 0.996), 34 OCR/pipeline tests pass, `/healthz` boots zero-network. Host: 156 passed, 1 skipped, ruff clean. Image 2.82 GB (size follow-up noted). Status → done. |
