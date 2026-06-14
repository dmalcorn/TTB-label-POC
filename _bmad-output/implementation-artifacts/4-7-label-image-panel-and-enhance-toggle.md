---
baseline_commit: 79001b79ec3c5fd4794d08e5957abb8093eeb5e0
---
# Story 4.7: Label Image Panel & Enhance Toggle

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **TTB label specialist (Jenny/Dave persona)**,
I want **the label image(s) shown in a left-column panel beside the field comparisons, with a paging control across the submission's faces and an "Enhance" toggle that shows the local-OpenCV preprocessed image alongside the original**,
so that **I can read the actual label with my own eyes to confirm a low-confidence OCR read (e.g. glare/angle on the Brand Name), with the preprocessed variant offered as a reading aid that never replaces the original.**

## Acceptance Criteria

1. **AC1 — Two-column workspace with a left image panel.** `GET /review/{id}` renders the Review Workspace as the mockup's two-column layout: a sticky **left column** carrying the label-image panel, and the **right column** carrying the existing field cards + Government Warning card + smart checklist (4.4–4.6, unchanged in content/order). The panel shows the submission's images in `position` order; the panel header names the current image's **role** ("Brand (front)", "Back", "Neck", "Strip", "Other") as a WORD (never role-by-color alone) plus an "image N of M" counter.

2. **AC2 — Images are served same-origin, token-gated, AR-5-pure.** A new route `GET /review/{submission_id}/image/{image_id}` streams the requested image file from disk with the correct `Content-Type`, resolving the on-disk path **from the `label_images` row** (never from a client-supplied path — no path traversal). A `variant` query param (`original` default, `enhanced`, `binarized`) selects which stored path to serve. The route is a **pure single-row DB read + file stream** (no OCR/LLM/engine/pipeline import — AR-5) and carries no token-gate exemption (the `app/main.py` middleware protects it like every screen). A missing submission/image, an image not belonging to that submission, or a missing/NULL variant path ⇒ calm **404** (never a 500, never a directory listing).

3. **AC3 — Paging across faces (works without JS).** When a submission has more than one image, the panel renders previous/next controls as real same-origin links (`?image=<position>` query on the review URL) so paging works with JavaScript disabled; the server renders whichever image `?image=` selects (defaulting to the first by `position`). A single-image submission renders no pager (or an inert, clearly-disabled one) and never errors.

4. **AC4 — Enhance toggle: preprocessed ALONGSIDE original (omitted-not-inert).** When the current image HAS a preprocessed variant (`enhanced_path` non-NULL), the panel offers an **Enhance** toggle. Enabling it shows the preprocessed image **side-by-side with** the original (neither replaces the other), with an honest caption stating the preprocessing applied (e.g. "deskew · glare · contrast") drawn from the stored `preprocess_log`, and the plain-language note that the preprocessed view is a reading aid. When the image is **clean** (`enhanced_path` is NULL — no preprocessing was needed), the Enhance toggle is **omitted entirely** (not shown disabled) per the UX-DR-13 "omitted, not inert" contract — its absence honestly signals "this image needed no enhancement."

5. **AC5 — Calm empty state, never a 500.** A submission with **no `label_images` rows** renders a calm, honest empty state in the left column ("No label image was provided for this submission.") and the right column renders unchanged. The route never 500s on a missing image, a missing variant file on disk, or an empty image set.

6. **AC6 — Spine fidelity (UI-fidelity standard / UX-DR purity).** The panel reproduces the mockup's structure and labels but resolves all tokens to `static/css/brand.css` spine variables (`--brand-*`, `--brand-radius-*`), **never** the mockup's inline hex. Mockup-only scaffolding (device frame, browser chrome, the fabricated `SUB-2026-04871` / "Ready in 4.6s" demo data, the hand-drawn CSS gin label) is excluded — real `<img>` elements pointing at the new image route are used instead. Reused page state (focus jump targets) keeps working: the left-column panel section carries an `id`/`tabindex="-1"` consistent with the existing focus-jump contract so the Brand/Identity chevron + checklist jumps still land.

## Tasks / Subtasks

- [x] **Task 1 — Image-serving route (AC2)** `app/web/routes_review.py`
  - [x]Add `GET /review/{submission_id}/image/{image_id}` with an optional `variant: str = "original"` query param.
  - [x]Read the `label_images` row by `image_id` (add a `get_label_image(conn, image_id)` repo helper if one does not exist; reuse `list_label_images` otherwise). Verify the row's `submission_id` matches the path `submission_id` — mismatch ⇒ 404 (prevents cross-submission enumeration).
  - [x]Resolve the on-disk path by variant: `original` ⇒ `fixtures/images/<filename>` (the read-only seeded source root, mirror `app/pipeline/preprocess.py:SOURCE_IMAGES_DIR`); `enhanced` ⇒ `Path(settings.generated_images_dir) / enhanced_path`; `binarized` ⇒ `Path(settings.generated_images_dir) / binarized_path`. A NULL variant path or a non-existent file ⇒ 404 (calm).
  - [x]Stream the file via `fastapi.responses.FileResponse` with the row's `mime_type` (fall back to a sniffed/`image/jpeg` default). **Never** join a client-supplied string into the path — the only client input is the integer `image_id` and the constrained `variant` literal.
  - [x]Keep the route AR-5-pure: no `run_checks` / `adapters.ocr` / `adapters.llm` / `pipeline.run` / `pytesseract` imports (the existing `test_review_route_imports_no_heavy_work` guard must still pass).

- [x] **Task 2 — Image-panel presenter (AC1/AC3/AC4)** `app/web/review_view.py`
  - [x]Add a pure `image_panel(images, *, submission_id, current_position=None)` builder returning a view-model: the current image (role word, position, "N of M" counter, original `src` URL, optional `enhanced` block), the pager (prev/next positions + their review-URL hrefs, or `None` when ≤1 image), and an `is_empty` flag.
  - [x]Map `image_role` → display WORD via a small `IMAGE_ROLE_WORD` dict (`BRAND`→"Brand (front)", `BACK`→"Back", `NECK`→"Neck", `STRIP`→"Strip", `OTHER`→"Other"; NULL ⇒ "Label image"). Word always rendered; never role-by-color.
  - [x]Build the `enhanced` sub-model ONLY when `enhanced_path` is non-NULL (clean image ⇒ no Enhance block — AC4 omitted-not-inert). Derive the honest "deskew · glare · contrast" caption by reading which corrective steps were `applied` in the stored `preprocess_log` (JSON), degrading to a generic "preprocessed" caption if the log is absent/garbled (never raise).
  - [x]Build `src` URLs pointing at the new route: `/review/{submission_id}/image/{image_id}` and `…?variant=enhanced`.
  - [x]Keep it AR-5-pure (no OCR/LLM/engine imports), snake_case, CFR-as-data N/A here.

- [x] **Task 3 — Wire the presenter into the route (AC1/AC3/AC5)** `app/web/routes_review.py`
  - [x]In `GET /review/{id}`, read `images = repo.list_label_images(conn, submission_id)` and accept an optional `image: int | None = None` query param (the selected `position`).
  - [x]Pass `review_view.image_panel(images, submission_id=submission_id, current_position=image)` into the template context as `image_panel`.

- [x] **Task 4 — Template: two-column layout + panel (AC1/AC3/AC4/AC5/AC6)** `templates/review.html` (+ new `templates/_image_panel.html` partial)
  - [x]Wrap the existing right-column sections (field cards, gov-warning, checklist, decide placeholder) in a `<div class="work">` with `<div class="review-col-left">` (panel) and `<div class="review-col-right">` (existing content, unchanged order/content).
  - [x]Render the panel from the `image_panel` view-model in a `_image_panel.html` partial: header (role word + "image N of M"), pager links (only when present), Enhance toggle + side-by-side original/preprocessed (only when `enhanced` present), real `<img alt="…">` elements with descriptive alt text, and the calm empty state when `is_empty`.
  - [x]Give the left-column panel section an `id` + `tabindex="-1"` so the existing focus-jump contract still resolves; keep the existing `group-identity`/`group-gov-warning`/`group-decide` anchors intact in the right column.

- [x] **Task 5 — Spine CSS (AC6)** `static/css/brand.css`
  - [x]Append a "Label image panel + Enhance toggle (Story 4.7)" block: `.work` (two-column flex), `.review-col-left` (sticky), `.review-col-right`, `.image-panel`, `.image-panel__header`, `.image-panel__role`, `.image-panel__pager`, `.image-panel__enhance` (segmented toggle), `.image-panel__pane`, `.image-panel__img`, `.image-panel__empty`. All colors/radii via `--brand-*` / `--brand-radius-*` tokens — NO mockup inline hex.

- [x] **Task 6 — Tests (all ACs)** `tests/test_review.py`
  - [x]Add an `_insert_image(conn, submission_id, **overrides)` helper.
  - [x]AC1: two-column markup present (`class="work"`, `review-col-left`); panel shows role word + "image 1 of N"; right-column field cards still render.
  - [x]AC2: `GET /review/{sid}/image/{img_id}` returns 200 + an `image/*` content-type for original; `?variant=enhanced` serves the enhanced file; a cross-submission `image_id` ⇒ 404; a NULL/absent variant ⇒ 404; the route stays token-gated (303 → `/access`).
  - [x]AC3: multi-image submission renders prev/next links (`?image=`); single-image renders no pager.
  - [x]AC4: an image WITH `enhanced_path` renders the Enhance toggle + the side-by-side caption; a CLEAN image (NULL `enhanced_path`) renders NO Enhance toggle (omitted-not-inert).
  - [x]AC5: a submission with no images renders the calm empty state (200, never 500); a missing variant file ⇒ 404.
  - [x]AC6: the image route src appears in the page; `test_review_route_imports_no_heavy_work` still passes; no mockup inline hex leaks into the new brand.css block (assert the `.image-panel` block uses `var(--brand-` tokens).
  - [x]Reuse fixtures on disk under `fixtures/images/` for the original-serve test (e.g. seed an image row whose `filename` is a real fixture file), and write a tiny temp PNG into `settings.generated_images_dir` for the enhanced-serve test.

## Dev Notes

### What this story changes (and what it must NOT break)

The current `templates/review.html` renders the field cards / gov-warning / checklist in a **single column** (there is no `.work`/`.col-left` yet — the mockup's two-column body was deferred to THIS story). Task 4 introduces the two-column wrapper. **Preserve verbatim** every existing right-column section, its order (field cards → gov-warning → checklist → decide placeholder), and every existing `id`/`tabindex`/anchor — the 4.4/4.5/4.6 regression tests assert on them (e.g. `group-identity`, `group-gov-warning`, `group-decide` carry `tabindex="-1"`; `field-card--*`, `cli--*`, the `data-done-count`/`data-total-count` spans). Wrapping content in new divs must not change the existing substrings those tests match.

### Centralized contracts (project-context.md — import, never re-implement)

- This story touches none of the four centralized engine contracts (verdict rollup, char-diff, CFR-as-data, normalization) directly. It is a **read/presentation** story. Keep the route AR-5-pure: a single-row DB read + a file stream, NO engine/OCR/LLM/pipeline import. The existing `test_review_route_imports_no_heavy_work` guard (`tests/test_review.py:682`) enforces this — do not regress it.
- **Verdict vs disposition (contract #3):** the image panel emits NO disposition and no verdict; it is pure label imagery. Nothing here pre-selects a decision.

### Firewall / offline boundary (NFR-2 / UX-DR-6)

- Images are served **same-origin** from the new `/review/{id}/image/{id}` route — no CDN, no external origin. The `<img src>` is a relative same-origin path. Do not introduce any cross-origin reference. (The existing `test_review_js_posts_to_progress_endpoint_no_egress` pattern is the precedent for the no-egress assertion style.)

### Image storage model (the data you render) — `app/db/schema.sql:80-110`, `app/db/repositories.py:80-191`

- `label_images`: `id, submission_id, image_role (BRAND/BACK/NECK/STRIP/OTHER|NULL), position (1-10), filename (bare basename of the seeded original), mime_type, width_px, height_px, enhanced_path, binarized_path, preprocess_log (JSON), preprocess_ms, preprocessed_at, …`. `UNIQUE(submission_id, position)`.
- **Path resolution (critical):**
  - **Original** lives under the read-only seeded source root — mirror `app/pipeline/preprocess.py:SOURCE_IMAGES_DIR` = `<repo>/fixtures/images/`; the on-disk file is `SOURCE_IMAGES_DIR / filename`.
  - **enhanced_path / binarized_path** are **relative** paths stored against `settings.generated_images_dir` (default `data/generated`). Resolve as `Path(settings.generated_images_dir) / enhanced_path`.
  - **NULL `enhanced_path`/`binarized_path` ⇒ the image was clean (no preprocessing).** This is the omitted-not-inert signal for AC4 — render NO Enhance toggle, not a disabled one.
- `repo.list_label_images(conn, submission_id) -> list[LabelImage]` already returns rows in `position` order (`app/db/repositories.py:185`). Add a `get_label_image(conn, image_id) -> LabelImage | None` helper for the serve route (a single-row `SELECT … WHERE id = ?`), OR fetch via `list_label_images` + filter — prefer the explicit single-row helper for clarity and to avoid loading siblings.

### Serving — use `FileResponse`, resolve from the DB row only

- Use `from fastapi.responses import FileResponse`. Pass the resolved absolute `Path` + `media_type=row.mime_type or "image/jpeg"`. `FileResponse` sets `Content-Type`/`Content-Length` and streams without loading the whole file into memory.
- **Security:** the ONLY client inputs are the integer `image_id` (path) and the constrained `variant` (validate against `{"original","enhanced","binarized"}`; anything else ⇒ 404). The filesystem path is derived **entirely from the DB row**, so there is no path-traversal surface. Still, guard the resolved file with an existence check before responding (missing variant file on disk ⇒ 404, not a 500).
- Verify `row.submission_id == submission_id` so an attacker can't enumerate other submissions' images through a valid-but-foreign `image_id`.

### UX-DR-13 (binding for this story) — "omitted, not inert"

From epics Requirements Inventory: a control that does not apply is **omitted**, never shown disabled/greyed. For a CLEAN image the Enhance toggle is absent entirely; its absence is the honest signal that no enhancement was needed. Do NOT render a greyed-out "Enhance (n/a)" affordance. (Same principle the smart checklist uses for the Conditional chevron step.)

### Honest preprocessing caption (AC4)

- `preprocess_log` is a JSON array of `{step, applied, ms, **params}` entries (see `app/pipeline/preprocess.py`). Read it to build an honest caption naming only the corrective steps that were actually `applied` (e.g. `deskew`, `normalize_illumination_glare`→"glare", `clahe_contrast`→"contrast", `denoise`→"denoise", `perspective_correct`→"perspective"). If the log is NULL or unparseable, degrade to a plain "preprocessed" caption — never raise. Keep the parse in the presenter, defensively wrapped (`try/except (json.JSONDecodeError, TypeError, KeyError)`).

### Project Structure Notes

- **Route + serve:** `app/web/routes_review.py` (extend; the GET render + the new image route live together).
- **Presenter:** `app/web/review_view.py` (add `image_panel` + `IMAGE_ROLE_WORD` + the caption helper). Pure, AR-5-safe, snake_case.
- **Template:** `templates/review.html` (two-column wrapper) + new `templates/_image_panel.html` partial (mirrors the `_field_card.html` / `_checklist.html` partial pattern).
- **CSS:** append to `static/css/brand.css` (spine tokens only; mockup hex excluded).
- **Repo helper:** `app/db/repositories.py` — add `get_label_image` if absent.
- **Tests:** extend `tests/test_review.py` (same `_client` / `connect` harness, `monkeypatch DATABASE_PATH` + `SCHEDULER_ENABLED=false`).
- Naming: snake_case everywhere; CSS classes follow the existing BEM-ish `image-panel__*` convention used by `field-cards__*` / `checklist__*`.

### Testing standards summary

- `pytest` + `fastapi.testclient.TestClient`, the existing `_client(monkeypatch, tmp_path, token=…)` + `connect(_db_path(tmp_path))` helpers in `tests/test_review.py`. Insert rows directly via SQL helpers (see `_insert_submission`, `_insert_check`). Add `_insert_image`.
- For the original-serve test, seed a `label_images.filename` that is a **real file** under `fixtures/images/` (e.g. an existing fixture basename) so `FileResponse` finds it. For the enhanced-serve test, write a tiny valid PNG into `Path(settings.generated_images_dir)` (the monkeypatched temp dir) and set `enhanced_path` to its basename.
- Test-first: write the red test for each AC, then implement to green. Run only `tests/test_review.py` while iterating; run the full `bash scripts/ci.sh` ONCE at the end.
- mypy is part of CI — annotate the new presenter/route signatures (`list[LabelImage]`, `dict[str, object]`, `Path`, `FileResponse`).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.7] — ACs + UX-DR-13 binding.
- [Source: _bmad-output/planning-artifacts/ux-designs/.../mockups/review-workspace.html lines 150-436] — two-column `.work`/`.col-left`/`.panel`/`.enhance`/`.imgwrap` structure; "preprocessed ALONGSIDE original, neither replaces the other" copy.
- [Source: app/db/schema.sql:80-110] — `label_images` columns + variant paths.
- [Source: app/db/repositories.py:80-191] — `LabelImage` model + `list_label_images`.
- [Source: app/pipeline/preprocess.py] — `SOURCE_IMAGES_DIR`, variant production, `preprocess_log` shape, clean-image (NULL paths) decision gate.
- [Source: app/config.py:85] — `generated_images_dir` setting.
- [Source: app/web/routes_review.py] — existing GET render + AR-5 purity contract; where the new route + `image` param land.
- [Source: app/web/review_view.py] — presenter conventions (`banner`/`chevron` patterns); where `image_panel` lands.
- [Source: templates/review.html] — current single-column body to wrap; preserved anchors/ids.
- [Source: static/css/brand.css:50-86] — spine tokens (`--brand-*`, `--brand-radius-*`, `--verdict-*`).
- [Source: tests/test_review.py] — test harness + the AR-5 import guard to keep green.
- [Source: _bmad-output/project-context.md] — four centralized contracts, AR-5 read-path purity, firewall/offline boundary, VLM-only purity (OCR text never feeds the model — N/A here but the no-egress posture applies), snake_case, CFR-as-data.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (Amelia, DEV agent)

### Debug Log References

- Red phase: `pytest tests/test_review.py -k "image_route or two_column or pager or enhance or empty_state or panel_uses or image_panel or brand_css"` → 9 failed / 7 passed (the 7 are 404/token-gate cases that already 404 by default) — confirmed tests fail for the right reasons before implementing.
- Green phase: same selection → 18 passed; full `tests/test_review.py` → 57 passed (no 4.4–4.6 regression).
- Final gate: `bash scripts/ci.sh` → format ✓, lint ✓, mypy ✓ (no issues in 85 source files), pytest 598 passed / 1 skipped.

### Completion Notes List

- Ultimate context engine analysis completed — comprehensive developer guide created.
- **AC1** — `templates/review.html` now wraps the existing 4.4–4.6 sections in a `.work` two-column grid (`.review-col-left` sticky panel + `.review-col-right`); every existing right-column `id`/`tabindex`/anchor preserved verbatim (4.4–4.6 regressions all green). The panel header names the role as a WORD ("Brand (front)") + "image N of M".
- **AC2** — New `GET /review/{submission_id}/image/{image_id}` route streams via `FileResponse`, resolving the on-disk path **entirely from the `label_images` row** (no path-traversal surface). `variant` is validated against `{original,enhanced,binarized}`; a foreign `image_id`, NULL variant path, missing file, or unknown variant ⇒ calm 404. Route stays AR-5-pure (single-row DB read + file stream); `test_review_route_imports_no_heavy_work` still passes. Token-gate inherited from the global middleware (verified 303 → /access).
- **AC3** — Pager is real same-origin `?image=<position>` links rendered only when >1 image; single image ⇒ no pager. Server renders whichever `?image=` selects (defaults to first by `position`). Works with JS disabled.
- **AC4** — Enhance toggle is a JS-free `<details>` shown **only** when `enhanced_path` is non-NULL; it reveals the preprocessed image side-by-side with the original (neither replaces the other) with an honest caption naming only the `applied` corrective steps from `preprocess_log` (degrades to "preprocessed" on NULL/garbled log, never raises). A clean image (NULL `enhanced_path`) **omits** the toggle entirely (UX-DR-13 omitted-not-inert).
- **AC5** — No `label_images` rows ⇒ calm empty state in the left column; right column unchanged. Route never 500s on missing image/variant/empty set.
- **AC6** — Panel resolves all tokens to `static/css/brand.css` spine vars (`--brand-*`, `--brand-radius-*`); no mockup inline hex. Real `<img>` elements point at the same-origin image route. Left-column panel section carries `id="group-image"`/`tabindex="-1"` consistent with the focus-jump contract.

### File List

- `app/db/repositories.py` — added `get_label_image(conn, image_id) -> LabelImage | None` single-row helper.
- `app/web/review_view.py` — added `IMAGE_ROLE_WORD`, `_PREPROCESS_CAPTION`, `_enhance_caption`, `_image_src`, and the pure `image_panel(...)` presenter; imported `LabelImage`.
- `app/web/routes_review.py` — added `_SOURCE_IMAGES_DIR`/`_VARIANT_ATTR` constants, the `image: int | None` GET query param + `image_panel` context wiring, and the new `review_image` `FileResponse` route; imported `Path`/`FileResponse`.
- `templates/review.html` — wrapped the right-column 4.4–4.6 sections in the `.work` / `.review-col-left` / `.review-col-right` two-column layout with the `group-image` panel section.
- `templates/_image_panel.html` — NEW partial rendering the `image_panel` view-model (header, pager, Enhance `<details>`, calm empty state).
- `static/css/brand.css` — appended the "Label image panel + Enhance toggle (Story 4.7)" spine-token block.
- `tests/test_review.py` — added `_insert_image` helper + 14 tests covering AC1–AC6; code review added +5 regression tests (pager NULL-position ordinal fallback, caption non-list shapes, unknown-variant 404, binarized content-type, traversal containment).

### Change Log

- 2026-06-14 — Story 4.7 implemented test-first (red → green → refactor): two-column review workspace with a same-origin, AR-5-pure label-image route, JS-free pager, omitted-not-inert Enhance toggle, calm empty state, and spine-token CSS. Full CI green (598 passed / 1 skipped). Status → review.
- 2026-06-14 — Adversarial code review (Blind Hunter / Edge Case Hunter / Acceptance Auditor). All 6 ACs SATISFIED; 4 findings PATCHED (no deferrals):
  - **H1 (pager dead-link on NULL `position`)** — `label_images.position` is CHECK 1–10-or-NULL and SQLite permits multiple NULLs under `UNIQUE(submission_id, position)`. The pager keyed prev/next strictly on `position`, so a NULL-position neighbour emitted a non-resolvable `?image=None` link (and `current_position` matching could pick the wrong face). Fixed in `app/web/review_view.py`: added `_pager_selector` (uses `position` when non-NULL, else the 1-based ordinal) and refactored the selection loop to try a `position` match first, then fall back to the 1-based ordinal — so paging always resolves to a real face.
  - **M3 (`_enhance_caption` crash on non-list log shape)** — a `preprocess_log` that parses to a non-list JSON value (object/string/number) would raise on iteration. Split the `try/except` to catch only `json.JSONDecodeError` around `json.loads`, then added an explicit `isinstance(entries, list)` guard — degrades to "preprocessed", never raises.
  - **M4 (path-traversal defence made real, not assumed)** — the route resolved variant paths from DB columns the pipeline writes as basenames today, but AC2 promises a *no-traversal* security property. `app/web/routes_review.py:review_image` now `resolve()`s the candidate path and requires it to stay under its root (`fixtures/images` for original, `generated_images_dir` for derived); a stored `..`/absolute path or out-of-root symlink ⇒ calm 404 (project-context.md: prefer the more restrictive option around the firewall boundary).
  - **L1 (mime fallback served PNG variants as `image/jpeg`)** — added `_media_type_for(row, variant)`: `original` keeps the row's `mime_type`; the OpenCV-PNG `enhanced`/`binarized` variants sniff their type from the stored path suffix (a JPEG original no longer streams its PNG enhanced variant as `image/jpeg`).
  - +5 regression tests in `tests/test_review.py` (NULL-position pager ordinal fallback, non-list caption shapes, unknown-variant 404, binarized `image/png` content-type, traversal containment 404). Final gate `bash scripts/ci.sh` → format ✓ lint ✓ mypy ✓ (85 files), pytest 603 passed / 1 skipped. Status → done.
