# Fixture corpus

Synthetic, dummy COLA submissions for the demo and the benchmark. **No
COLA-registry artwork** — every image is generated.

## Contents

- `ground_truth.csv` — one row per submission: the APPLICATION fields (1:1 with
  the `submissions` table), design tags (`scenario`, `expected_verdict`,
  `violation_kind`), the on-label **Ground Truth** (`gt_*`) values, and an
  `images` JSON manifest. The `gt_*` columns are what is physically on the label
  (what OCR should read); for clean rows they match the APPLICATION values, for
  violation rows they deliberately diverge.
- `images/*.jpg` — synthetic label images, RGB JPEG, named
  `<ttb_id>_<NN>_<ROLE>.jpg`.

The corpus is **36 submissions** (12 per beverage type), composed so each type
has ≥1 each of PASS / REVIEW / FAIL once the Epic-3 engine runs (clean →PASS,
deliberate CFR violations →FAIL, degraded imagery →REVIEW). One submission
carries the full 10-image set.

## Regenerating

`generate.py` is a **dev tool** — it uses OpenCV, which is **not** a runtime
dependency. The committed CSV + images are what ship (baked into the Docker
image); the runtime `app/db/seed.py` is stdlib-only and just reads them.

```bash
# in the dev virtualenv (one-time): pip install opencv-python-headless~=4.13 numpy
python fixtures/generate.py
```

Generation is deterministic (fixed RNG seed), so re-running does not churn the
committed files.

## Seeding

```bash
python -m app.db.seed        # init the configured DATABASE_PATH, then load the corpus
```

`seed()` is transactional and idempotent (re-run = clear + reload, no
duplicates) — the basis Epic 6's `POST /reset` reuses.
