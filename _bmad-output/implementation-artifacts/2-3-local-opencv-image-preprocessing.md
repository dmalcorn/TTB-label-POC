---
baseline_commit: ec71fa057eb6efc54258e78a7cafa40cb67db6b4
---

# Story 2.3: Local OpenCV image preprocessing

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist reviewing imperfect photos,
I want skewed/glared/low-contrast images cleaned up locally before OCR,
so that a readable-but-imperfect photo is handled without a correction cycle back to the applicant.

## Acceptance Criteria

1. **AC1 — Local OpenCV preprocessing stage, conditional steps, fully offline.**
   **Given** `app/pipeline/preprocess.py` using local OpenCV (`opencv-python-headless`) implementing the ordered, **conditional** step chain from `docs/image-handling.md` §3 (decode/color-normalize → grayscale → denoise → glare/illumination → CLAHE contrast → deskew → perspective → binarization)
   **When** the pipeline processes a label image **Then** each step runs only when its detector says it is needed (an already-clean image is not degraded), using **no LLM and no network call** (pure `cv2`, CPU). *(FR-10, image-handling.md §3, §5)*

2. **AC2 — Enhanced + binarized variants persisted to the Volume, referenced beside the original; neither replaces it.**
   **Given** a degraded-fixture image
   **When** preprocessing runs **Then** an **enhanced** variant (grayscale/color, for PaddleOCR) and a **binarized** variant (for Tesseract) are written as files to the **Railway Volume** generated-images area, and their **paths are recorded on the `label_images` row** alongside the original `filename` — the original is untouched and remains independently viewable (the Review "Enhance" toggle shows them side by side). *(FR-10, FR-7, D7, image-handling.md §3 engine-aware note)*

3. **AC3 — Per-image preprocessing log for the benchmark + audit.**
   **Given** the benchmark needs to attribute OCR gains to enhancement
   **When** preprocessing runs **Then** the **ordered list of transforms applied**, key parameters (e.g. **detected deskew angle**, CLAHE clip limit), and **per-stage timing** are recorded per image (JSON), and the preprocessing wall-time contributes to the submission's `processing_ms`. *(image-handling.md §3 "Logging for the benchmark (required)"; FR-10)*

4. **AC4 — Enhancement helps, never harms or fabricates.**
   **Given** the non-goals in `docs/image-handling.md` §4
   **When** preprocessing runs **Then** it **never** measures font size / physical dimensions, **never** fabricates unreadable text, and **never** auto-rejects — an image that is still unreadable after enhancement is left for the engine to flag `REVIEW` downstream, not failed here. The clean-image path is a no-op-safe pass-through (no degradation). *(FR-10, image-handling.md §4)*

5. **AC5 — Registers into the 2.2 stage seam; clean images skip cleanly.**
   **Given** the orchestrator seam from Story 2.2 (`run.STAGES`)
   **When** preprocessing is registered as the first heavy stage **Then** it plugs in with **no change to `scheduler.py`/`status.py`**, runs before OCR (2.4), and a clean image with no detected defects produces **no variant files** (OCR then runs on the original only — the "omitted, not inert, when no preprocessing was applied" UI contract). *(epics.md Story 2.2 seam; UX-DR-13)*

## Tasks / Subtasks

- [x] **Task 1 — Schema: variant paths + preprocessing log on `label_images` (AC2, AC3)**
  - [x] Append nullable columns to `app/db/schema.sql` `label_images` (additive, `IF NOT EXISTS` style preserved; SQLite has no `ADD COLUMN IF NOT EXISTS`, so add them to the `CREATE TABLE` for fresh DBs — see Dev Notes "Additive schema on a no-migration project"): `enhanced_path TEXT`, `binarized_path TEXT`, `preprocess_log TEXT` (JSON), `preprocess_ms INTEGER CHECK (preprocess_ms IS NULL OR preprocess_ms >= 0)`, `preprocessed_at TIMESTAMP`.
  - [x] **Update the authoritative docs to match** (the source wins over a stale note): change `docs/database-schema.md` §1.2 and `docs/data-dictionary.md` §2 — the data-dictionary currently says a `preprocessed` flag is "**not stored** … add a column if it becomes load-bearing." It is now load-bearing (D7 + AR-7 + image-handling §3); replace that note with the real columns + rationale. [Source: docs/data-dictionary.md line ~134]
  - [x] Add `update_label_image_variants(conn, label_image_id, *, enhanced_path, binarized_path, preprocess_log, preprocess_ms, preprocessed_at)` to `app/db/repositories.py` (raw SQL stays in `app/db/`). Paths are stored **relative to the generated-images root** (portable across local/Volume), not absolute.

- [x] **Task 2 — `app/pipeline/preprocess.py`: the OpenCV chain (AC1, AC4)**
  - [x] Implement each `docs/image-handling.md` §3 step as a small pure function taking/returning a `numpy` image, each with a **detector** that decides whether to apply it (skip-when-not-needed): `decode_normalize_color`, `to_grayscale`, `denoise`, `normalize_illumination_glare`, `clahe_contrast`, `deskew` (return detected angle), `perspective_correct`, `binarize`.
  - [x] Produce **two outputs**: the **enhanced** image (through CLAHE/deskew/perspective, kept grayscale/color) and the **binarized** image (adaptive/Otsu threshold). Keep the original bytes untouched.
  - [x] `preprocess_image(src_path, out_dir) -> PreprocessResult` returns the two variant paths (or `None` each when a step was a no-op / not needed), the ordered transform log with params (incl. **deskew angle**, CLAHE clip), and per-stage ms.
  - [x] Strictly honor §4 non-goals: **no** mm/font measurement, **no** text fabrication, **no** reject decision. CPU-only; deterministic given the same input (no randomness).

- [x] **Task 3 — Variant file persistence to the Volume (AC2, D7)**
  - [x] Write variants under the generated-images root (config `GENERATED_IMAGES_DIR`, default e.g. `data/generated/` beside the SQLite file on the Volume — confirm against Story 1.6 `railway.toml` Volume mount). Naming: derive from the original, e.g. `<ttb_id>_<NN>_<ROLE>__enhanced.png` / `__binarized.png` (PNG = lossless for the OCR-input variant). **Seeded fixtures stay read-only** (baked into the image); only derived variants are written to the Volume. [Source: image-handling.md §3 resolved-note; architecture.md D7]
  - [x] Demo reset (`POST /reset`, Epic 6) must **purge** these generated files — leave a clear TODO/hook and document the generated root so AR-12/FR-27 can purge it; do not implement reset here.

- [x] **Task 4 — Register the preprocess stage into the 2.2 seam (AC5)**
  - [x] Add a `preprocess_stage(ctx)` adapting `preprocess_image` to the `Stage`/`StageContext` contract from `run.py` (Story 2.2): for each `label_image`, run preprocessing, persist variants + log via `update_label_image_variants`, accumulate `preprocess_ms`, stash variant paths in `ctx.scratch` for the OCR stage (2.4) to consume.
  - [x] Insert it at the **front** of `run.STAGES` (before OCR). Confirm `scheduler.py`/`status.py` are untouched. A clean image → no variant files, empty/short log, OCR falls back to the original.

- [x] **Task 5 — Dependencies + offline posture**
  - [x] Add `opencv-python-headless ~=4.13` and (if needed for decode) `numpy`/`pillow` to `requirements.txt` (pin to the `approved-tech-stack.md` line). Use **headless** (no GUI libs) for the slim container. Native libs (`libgl1`, `libglib2.0-0`) are already in the Dockerfile (Story 1.1) — verify; headless avoids most. [Source: project-context.md tech stack; Story 1.1 ACs]
  - [x] Confirm **zero network**: OpenCV downloads nothing at runtime. The stage must run under `docker run --network none`.

- [x] **Task 6 — Tests (`tests/test_preprocess.py`) (all ACs)**
  - [x] Generate tiny synthetic test images in-test (e.g. a skewed/low-contrast `numpy` array via `cv2`), **not** the committed fixtures, so tests are fast and self-contained.
  - [x] AC1/AC4: a **clean** synthetic image → detectors skip steps, **no variant files written**, log reflects a near-no-op; assert no exception and original untouched.
  - [x] AC1/AC3: a **deskew** case (image rotated by a known angle) → `deskew` detects ≈ that angle (within tolerance), the log records the angle + ordered transforms + per-stage ms, and an enhanced + binarized file are written.
  - [x] AC2: after the stage runs via the seam against a `tmp_path` DB, the `label_images` row has `enhanced_path`/`binarized_path`/`preprocess_log`/`preprocess_ms` populated and the original `filename` unchanged.
  - [x] AC4: assert the module exposes **no** font-size/dimension measurement and makes **no** verdict/reject call (structural — it returns images + a log only).
  - [x] AC5: assert `preprocess_stage` registers into `run.STAGES` and the lifecycle (2.2) still reaches `READY_FOR_REVIEW` with the stage present.

- [x] **Task 7 — Validate + finalize**
  - [x] `ruff check` + `ruff format` (line length 100); full `pytest` green (no Epic-1 / 2.1 / 2.2 regressions). Boots under `docker run --network none`.
  - [x] Update File List + Change Log + Completion Notes; note the `database-schema.md` / `data-dictionary.md` edits.

### Review Findings

_Code review 2026-06-13 (Blind Hunter + Edge Case Hunter + Acceptance Auditor). 3 patch, 5 defer, 5 dismissed. The Acceptance Auditor verified all five ACs + every binding boundary (zero egress, SQL-only-in-app/db, relative paths, additive schema, docs updated, reset-hook-only, read-contract, fixtures read-only, anti-patterns) are satisfied. The hunters' "High" filename-collision finding was verified DOWN to Low: the seeded fixtures are uniquely named (`<ttb_id>_<NN>_<ROLE>.jpg`), so `{stem}` variant names don't collide for the real corpus. Patches below are robustness hardening, not AC violations._

- [x] [Review][Patch] `cv2.imwrite` return value is unchecked — `preprocess_image` writes the enhanced/binarized variants (`cv2.imwrite(...)`) and discards the bool result, then persists `enhanced_path`/`binarized_path` on the row. `imwrite` returns `False` (does NOT raise) on a write failure (un-writable generated root, disk full, bad encode), so the DB ends up referencing variant files that don't exist — OCR (2.4) then reads a dangling path. Fix: check each `imwrite` return; on failure log + leave that variant path `None` (treat as no-variant) so the row never references a missing file. [app/pipeline/preprocess.py:preprocess_image] _(blind+edge, Medium)_ — FIXED: `enhanced_ok`/`binarized_ok` capture each `imwrite` result; a failed write logs a warning and drops that variant to `None`.
- [x] [Review][Patch] No per-image guard in `preprocess_stage` — the `for image in ctx.label_images` loop has no try/except, and `preprocess_image`'s "never raises" claim only covers the imread-returns-`None` path, not a `cv2.error` on a pathological input (e.g. `adaptiveThreshold` blockSize=31 / `GaussianBlur` on a sub-31px image) or a `repo.update_label_image_variants` DB error. Such a raise propagates out of the stage; 2.2's per-*stage* guard catches it and still finalizes the submission, but every image **after** the failing one is silently skipped (NULL preprocess columns, no variants) — a multi-image submission (1–10 images) is half-processed with no honest per-image record. Fix: wrap the per-image body in try/except → log an honest skip note, continue to the next image (matches AC4's "skip, don't fail the batch" posture; also contains the pathological-tiny-image `cv2.error`). [app/pipeline/preprocess.py:preprocess_stage] _(edge+blind, Medium)_ — FIXED: per-image `try/except` logs and skips the failing image (NULL variants in scratch), the rest of the submission still processes.
- [x] [Review][Patch] Dead `ctx.scratch["preprocess_ms"]` write + misleading docstring — line ~420 accumulates `preprocess_ms` into `ctx.scratch`, and the docstring says it "accumulates `preprocess_ms` into `submissions.processing_ms`", but nothing reads that scratch key; `processing_ms` is derived solely from `run.py`'s wall-clock loop timer (which already includes this stage's time, so AC3 still holds). Fix: delete the dead line (or mark it explicitly informational) and correct the docstring so a future maintainer doesn't "fix" the timer trusting a contribution path that doesn't exist. [app/pipeline/preprocess.py:preprocess_stage] _(all three, Low)_ — FIXED: removed the dead `accumulated_ms`/`ctx.scratch["preprocess_ms"]` accumulation; docstring now states processing_ms rolls up via run.py's loop timer.
- [x] [Review][Defer] Variant filename uniqueness relies on globally-unique source basenames — names are `{Path(src).stem}__enhanced.png`/`__binarized.png`. True for the seeded corpus (`<ttb_id>_<NN>_<ROLE>` stems are unique), but two `label_images` sharing a stem (a future upload, or `a.jpg`+`a.png`) would overwrite each other and both rows would point at one file. Add a `label_image.id` qualifier to the variant name if duplicate/untrusted filenames ever occur. [app/pipeline/preprocess.py:preprocess_image] — deferred, latent (not reachable with current data)
- [x] [Review][Defer] Glare/illumination detector fires only on a lighting **gradient** (background luma spread), so a flat, uniformly-blown-out glare with no gradient is a no-op — the inpaint branch is nested inside the spread gate. This is a deliberate tradeoff (Debug Log: reworked off "near-white fraction" to avoid false-firing on plain white labels). Revisit the tuning against real phone photos. [app/pipeline/preprocess.py:normalize_illumination_glare] — deferred, tuning tradeoff
- [x] [Review][Defer] Orientation not normalized — `IMREAD_COLOR` ignores EXIF orientation and `_detect_skew_angle` folds any angle into (-45, 45], so a 90°/180° EXIF-rotated photo is never straightened (the rotation is folded away); a true ~45° skew also flips correction direction at the fold boundary. Matters for real uploaded phone photos (the seeded fixtures are upright). Add EXIF-orientation handling + a >45° branch when real uploads land. [app/pipeline/preprocess.py:decode_normalize_color / _detect_skew_angle] — deferred, post-POC real-image concern
- [x] [Review][Defer] Enhanced variant is strictly grayscale, not color — AC2/§3 frame the enhanced (PaddleOCR) variant as "grayscale/color"; PaddleOCR/PP-OCRv5 often do better on color. Defensible POC choice (the chain operates on intensity), but reconsider emitting a color enhanced variant when 2.4 wires PaddleOCR. [app/pipeline/preprocess.py:preprocess_image] — deferred to Story 2.4
- [x] [Review][Defer] Path robustness for untrusted inputs — `src_path = SOURCE_IMAGES_DIR / image.filename` isn't containment-checked (a `../` or absolute `filename` would escape the read-only fixture root), and stored variant paths are basenames relative to `generated_images_dir` with no record of which root they're relative to (fragile if the config drifts between the preprocess and OCR runs). Both are safe today (trusted seeded basenames, stable config) — sanitize + pin the resolution base when real uploads land. [app/pipeline/preprocess.py:preprocess_stage] — deferred, post-POC

**Dismissed as by-design / noise (5):** per-step `ms` values in `preprocess_log` vary run-to-run (timing is inherently non-deterministic; the AC's determinism is about **image output**, which IS pixel-reproducible and tested); numpy types in the log → `json.dumps` (every logged value is explicitly `float(...)`/`round(...)`/bool-cast — confirmed safe); CLAHE firing on a pure-blank white image (a blank label isn't a real "clean text" input; the clean-text case measures std≈52, well above the 40 gate); degenerate-quad singular `getPerspectiveTransform` (perspective is heavily gated — 0.30–0.97 frame area, convex, exactly-4-point, non-axis-aligned — so degenerate quads are filtered out); `preprocess_ms=0` for a sub-millisecond run (schema `CHECK >= 0` permits it — same by-design call as 2.2).

## Dev Notes

### Scope boundary (what 2.3 is and is NOT)
- **IS:** the local OpenCV preprocessing stage, the two derived variants (enhanced + binarized), their persistence to the Volume + path/log columns on `label_images`, and registration into the 2.2 seam.
- **IS NOT:** running OCR (2.4) — this story only *produces* the variants the OCR engines will consume; the both-variants OCR + the `ocr_results` variant discriminator are **Story 2.4**. Not the LLM (2.5). Not demo-reset purge (Epic 6 — leave the hook). [Source: epics.md#Story-2.3, #Story-2.4]

### The variant-storage decision (resolves a stale-doc conflict — important)
`docs/data-dictionary.md` (older, 2026-06-11) says a `preprocessed` flag is deliberately **not** stored — "add a column if it becomes load-bearing." The **architecture (newer, 2026-06-12)** makes it load-bearing: **D7** ("preprocessed images written to the Volume as files, **referenced by path in `label_images`**"), **AR-7** (store both variants for benchmark scoring), and **image-handling.md §3** (persisted to the Volume, referenced by path; per-image transform/param/timing log required). **The source wins on conflict → store the variant paths on `label_images` and update the two docs.** [Source: architecture.md D7, AR-7; image-handling.md §3 resolved-note; project-context.md "When a rule and a source conflict, the source wins — fix this file."] Chosen shape: **columns on `label_images`** (matches D7's "by path in `label_images`") rather than a separate variant table — fewer joins, one row per logical image, and the Review "Enhance" toggle reads original + `enhanced_path` straight off the row.

### Additive schema on a no-migration project (trap)
There is **no migration framework** — `init_db` just applies `schema.sql` (idempotent `CREATE TABLE IF NOT EXISTS`). Adding columns to `label_images` only affects **freshly created** DBs; an existing dev DB won't gain them. For the POC this is fine because the canonical workflow is **re-seed from scratch** (`seed.py` `DELETE FROM submissions` + reload, and demo-reset re-seeds). Put the new columns in the `CREATE TABLE`. Document that a pre-existing local DB must be deleted/re-init'd to pick up the columns (note it in the Change Log + README dev notes if needed). Do **not** introduce Alembic — it is an explicit Phase-2 deferral. [Source: architecture.md Data Architecture "no ORM/migration framework"; app/db/seed.py transactional re-seed]

### Engine-aware variants (why two outputs)
`docs/image-handling.md` §3 engine-aware note: **Tesseract** does best on a clean **binarized** image; **PaddleOCR/PP-OCRv5** often do better on the **enhanced grayscale/color** image. Producing both lets each engine (2.4) consume its preferred input and lets the benchmark (Epic 5) compare fairly. Record which variant each `ocr_results` row consumed — that discriminator is added in **2.4**, not here. [Source: image-handling.md §3 engine-aware note + TODO "per-engine variant routing"]

### Conditional steps (don't degrade clean images)
Every step is **conditional on a detector** so an already-clean fixture isn't harmed (over-denoise/over-threshold can *lower* OCR accuracy). The clean-image path should produce **no variant files** (or variants identical to original that you choose not to persist) → the Review panel "omits, not inert, when no preprocessing was applied" (UX-DR-13). This also keeps `processing_ms` low for the clean majority. [Source: image-handling.md §3 "each is conditional"; UX-DR-13]

### Persistence + reset (D7 / AR-12)
Derived variants live on the **Volume** generated-images area, referenced by **relative** path. Seeded fixtures are **read-only** (baked into the Docker image). Demo reset (Epic 6) **purges generated preprocessed images** — this story must keep all generated output under one clearly-named, purgeable root and leave a documented hook; it does **not** implement reset. [Source: architecture.md D7, Demo reset; image-handling.md §3 resolved-note; AR-12]

### Architecture / boundary rules this story must honor
- **No egress / local-only:** OpenCV enhancement is classified **`none`** in the outbound inventory — pure local CPU, no model download, no network. Must run under `--network none`. [Source: outbound-calls-inventory.md row "OpenCV image enhancement"; image-handling.md §5]
- **Pipeline-only writer + data boundary:** variant writes go through a `repositories.py` helper; `preprocess.py` does image math, `app/db/` does SQL. [Source: architecture.md Pipeline/Data boundaries]
- **5s read contract:** preprocessing is background pre-compute only; never on a request path. The Review screen reads the pre-computed `enhanced_path` — it does not run OpenCV at request time. [Source: architecture.md Process Patterns; FR-7]

### Source tree components to touch
- `app/pipeline/preprocess.py` (NEW).
- `app/db/schema.sql` (UPDATE — additive `label_images` columns).
- `app/db/repositories.py` (UPDATE — `update_label_image_variants` write helper).
- `app/pipeline/run.py` (UPDATE — register `preprocess_stage` at the front of `STAGES`; consumes the seam from 2.2).
- `app/config.py` (UPDATE — `GENERATED_IMAGES_DIR`).
- `requirements.txt` (UPDATE — `opencv-python-headless`, numpy/pillow if needed).
- `docs/database-schema.md` §1.2 + `docs/data-dictionary.md` §2 (UPDATE — replace the "not stored" note with the real columns).
- `.env.example` (UPDATE — `GENERATED_IMAGES_DIR`).
- `tests/test_preprocess.py` (NEW).

### Previous story intelligence
- **2.2** owns `run.STAGES` / `StageContext` — this story registers a stage; it must not touch `scheduler.py`/`status.py`. Read 2.2's seam contract before wiring. [Source: 2-2 story Task 2]
- **2.1/1.2** patterns: write helpers in `repositories.py`, `connect(db_path)`, `tmp_path` test DBs via `init_db`. Reuse. [Source: 2-1 story; tests/test_repositories.py]
- `label_images` already has `filename`, `width_px`/`height_px`, `mime_type` from Story 1.2/1.3 — preprocessing may also backfill `width_px`/`height_px` if absent, but that is optional, not an AC.

### Testing standards
- pytest in `tests/`, `test_*.py`; ruff line length 100; type hints. Synthesize tiny images in-test (no heavy fixtures, no GPU). Highest-value: **deskew-angle detection**, **clean-image no-op (no files written)**, **variant paths + log persisted**, **§4 non-goals are structurally impossible** (module exposes no measure/verdict). [Source: project-context.md Testing]

### Project Structure Notes
- Realized paths nest under `app/` (`app/pipeline/preprocess.py`), per the 2.1/2.2 convention. [Source: architecture.md tree; 2-1/2-2 Project Structure Notes]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.3] — story statement + ACs.
- [Source: docs/image-handling.md §3] the ordered conditional OpenCV chain + the "produce both an enhanced and a binarized variant" engine-aware note + the required per-image log; [§4] non-goals (no font/dimension, no fabrication, no auto-reject); [§5] OpenCV-local recommendation.
- [Source: _bmad-output/planning-artifacts/architecture.md D7] derived-artifact persistence (Volume, by path in `label_images`); [AR-7] both-variants storage; [Data-Flow] preprocess is the first pipeline stage; [Pipeline/Data/External boundaries].
- [Source: docs/database-schema.md §1.2] `label_images`; [docs/data-dictionary.md §2, line ~134] the stale "not stored" note this story supersedes.
- [Source: _bmad-output/project-context.md] firewall/offline posture; 5s contract; source-wins-on-conflict rule.
- [Source: app/db/schema.sql, app/db/repositories.py, app/pipeline/run.py (2.2)] existing schema + seam to extend.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Amelia / dev-story workflow)

### Debug Log References

- Detector calibration probe (clean → all-skip / no files; 7° rotation → deskew detects ≈7°, both variants written). Tuned `_LOW_CONTRAST_STD_THRESHOLD` 50→40 for clean-image margin (a text-rich clean label measured std≈52, comfortably above 40; a genuinely faded label sits well below).
- Reworked the glare detector from a "near-white fraction" signal (which false-fired on plain white labels) to **background-unevenness** (luma spread of a heavily-smoothed background), so a uniformly-lit mostly-white page is correctly a no-op.
- Full suite: 144 passed (132 baseline + 12 new), ruff clean. No Epic-1 / 2.1 / 2.2 regressions; the new real `preprocess_stage` rides the 2.2 live-lifespan test green (handles the no-image and missing-source paths gracefully).

### Completion Notes List

- **AC1** — `app/pipeline/preprocess.py` implements the ordered, **conditional** §3 chain (decode→grayscale→denoise→illumination/glare→CLAHE→deskew→perspective→binarize) as small pure `cv2` functions, each detector-gated so a clean image is never degraded. Pure local CPU, no LLM, no network.
- **AC2** — enhanced + binarized variants are written to the generated-images root and their **relative** paths recorded on `label_images` (`enhanced_path`/`binarized_path`) via `repo.update_label_image_variants`; the original `filename` is never replaced. Engine-aware: enhanced (grayscale) for PaddleOCR, binarized for Tesseract.
- **AC3** — per-image `preprocess_log` (JSON: ordered transforms + params incl. detected **deskew angle** + CLAHE clip + per-stage ms) and `preprocess_ms` persisted; preprocess wall-time is inside `process_submission`'s timed loop, so it rolls into `submissions.processing_ms`.
- **AC4** — §4 non-goals are structural: the module exposes only image transforms + a log (no font/dimension measurement, no fabrication, no verdict/reject). An unreadable/missing source is logged and skipped, never raised — left for the engine to flag `REVIEW` downstream. Deterministic (no RNG).
- **AC5** — `preprocess_stage` registered at the **front** of `run.STAGES` (before OCR) with **zero** change to `scheduler.py`/`status.py`; a clean image produces **no** variant files (paths stay NULL, OCR uses the original — the UX-DR-13 "omitted, not inert" contract). Variant paths are stashed in `ctx.scratch['variants']` for the 2.4 OCR stage.
- **Docs updated (source-wins-on-conflict):** `docs/database-schema.md` §1.2 and `docs/data-dictionary.md` §2 — replaced the stale "preprocessing not stored" note with the five real columns + rationale (D7/AR-7/image-handling §3).
- **Deps:** added `opencv-python-headless~=4.13` + `numpy~=2.4` (requirements.txt); `GENERATED_IMAGES_DIR` config + `.env.example`. Dockerfile already bakes `libgl1`/`libglib2.0-0` (verified — headless needs no more). Zero egress: pure `cv2`, runnable under `docker run --network none`.
- **Demo-reset hook:** all derived variants live under one purgeable root (`GENERATED_IMAGES_DIR`, default gitignored `data/generated/`); a `TODO(epic-6-reset)` hook marks where `POST /reset` will purge. Reset itself is Epic 6, not implemented here.
- **Migration note:** no migration framework — the new columns are added to `CREATE TABLE`, so a **pre-existing** local dev DB must be deleted/re-init'd (re-seed from scratch) to pick them up; fresh DBs and demo-reset get them automatically.

### File List

- `app/pipeline/preprocess.py` (NEW) — the OpenCV chain, `preprocess_image`, and the `preprocess_stage` seam adapter.
- `tests/test_preprocess.py` (NEW) — 12 tests across AC1–AC5 (clean no-op, deskew detection, determinism, unreadable-skip, structural non-goals, stage persistence, scratch hand-off, registration, lifecycle).
- `app/db/schema.sql` (UPDATE) — additive `label_images` columns: `enhanced_path`, `binarized_path`, `preprocess_log`, `preprocess_ms` (CHECK ≥ 0), `preprocessed_at`.
- `app/db/repositories.py` (UPDATE) — `LabelImage` read-model fields + `update_label_image_variants` write helper.
- `app/pipeline/run.py` (UPDATE) — import + register `preprocess_stage` at the front of `STAGES`.
- `app/config.py` (UPDATE) — `generated_images_dir` setting + `GENERATED_IMAGES_DIR` env.
- `requirements.txt` (UPDATE) — `opencv-python-headless~=4.13`, `numpy~=2.4`.
- `.env.example` (UPDATE) — `GENERATED_IMAGES_DIR`.
- `docs/database-schema.md` (UPDATE) — §1.2 columns + DDL.
- `docs/data-dictionary.md` (UPDATE) — §2 columns + superseded "not stored" note.

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-12 | Story 2.3 drafted — local OpenCV preprocessing (conditional deskew/perspective/glare/CLAHE/denoise/binarize, enhanced+binarized variants persisted to the Volume + path/log columns on label_images, registered into the 2.2 seam). Resolves the stale data-dictionary "not stored" note in favor of D7/AR-7. Status → ready-for-dev. |
| 2026-06-13 | Story 2.3 implemented — `preprocess.py` conditional OpenCV chain + `preprocess_stage` at the front of `run.STAGES`; five additive `label_images` columns + `update_label_image_variants`; `GENERATED_IMAGES_DIR` config; opencv/numpy deps; `database-schema.md`/`data-dictionary.md` updated (source wins). 12 new tests, full suite 144 green, ruff clean. Status → review. |
| 2026-06-13 | Code review (3-layer adversarial). Acceptance Auditor confirmed all five ACs + every boundary satisfied; hunters' "High" filename-collision verified down to Low (seeded fixtures are uniquely named). 3 patches applied (check `cv2.imwrite` return → no dangling DB paths; per-image try/except so one bad image doesn't skip the rest; remove dead `preprocess_ms` scratch + fix docstring), 5 deferred, 5 dismissed. Full suite 144 green; ruff clean. Status → done. |
