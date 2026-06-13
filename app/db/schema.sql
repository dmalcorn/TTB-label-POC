-- Mock COLA Submissions schema — Story 1.2 (submissions + label_images only).
-- Authoritative source: docs/database-schema.md §1.1 / §1.2.
-- Scope: the OCR/LLM/comparison/checklist/audit/review_progress/extra-field tables
-- are created by the later stories that first need them (Epics 2–3, seed/review) —
-- NOT front-loaded here (project-context: "create tables only in the story that needs them").
--
-- SQLite-friendly form; TODO(postgres) markers preserved for the Phase-2 portability flip.
-- Connection settings (PRAGMA foreign_keys = ON per connection; PRAGMA journal_mode = WAL
-- once on the file) are applied by app/db/connection.py, not here.

-- ── submissions ──────────────────────────────────────────────────────────────
-- One mock COLA application: APPLICATION-category fields (Form 5100.31), the
-- minimal lifecycle (status + timestamps), and the rolled-up advisory engine verdict.
CREATE TABLE IF NOT EXISTS submissions (
    id                      INTEGER PRIMARY KEY,          -- Postgres: BIGINT GENERATED ALWAYS AS IDENTITY
    ttb_id                  TEXT    NOT NULL UNIQUE,
    serial_number           TEXT,
    beverage_type           TEXT    NOT NULL
                              CHECK (beverage_type IN ('WINE','DISTILLED_SPIRITS','MALT_BEVERAGE')),
    source_of_product       TEXT    CHECK (source_of_product IN ('DOMESTIC','IMPORTED')),
    application_type        TEXT    CHECK (application_type IN
                              ('LABEL_APPROVAL','EXEMPTION','DISTINCTIVE_BOTTLE','RESUBMISSION')),
    -- APPLICATION-category fields (Form 5100.31 / e-filed) --
    brand_name              TEXT,
    fanciful_name           TEXT,
    class_type_designation  TEXT,
    applicant_name_address  TEXT,
    mailing_address         TEXT,
    plant_registry_no       TEXT,
    alcohol_content         TEXT,
    net_contents            TEXT,
    grape_varietal          TEXT,
    wine_appellation        TEXT,
    wine_vintage            TEXT,
    formula_id              TEXT,
    phone                   TEXT,
    email                   TEXT,
    -- lifecycle + rolled-up engine result --
    status                  TEXT    NOT NULL DEFAULT 'RECEIVED'
                              CHECK (status IN
                              ('RECEIVED','PROCESSING','READY_FOR_REVIEW','IN_REVIEW','DECIDED')),
    engine_verdict          TEXT    CHECK (engine_verdict IN ('PASS','REVIEW','FAIL')),
    disposition             TEXT    CHECK (disposition IN
                              ('APPROVED','NEEDS_CORRECTION','REJECTED')),
    application_date        DATE,
    submitted_at            TIMESTAMP,
    decided_at              TIMESTAMP,
    specialist_id           TEXT,        -- who decided; demo/token identity (no user accounts in the POC)
    decision_notes          TEXT,        -- rationale; the specified issues for a NEEDS_CORRECTION return
    correction_due_at       TIMESTAMP,   -- 30-day clock; set only when disposition = NEEDS_CORRECTION
    processing_ms           INTEGER   CHECK (processing_ms IS NULL OR processing_ms >= 0),
    created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Cross-column invariant: a disposition AND a decision time exist IFF the row is DECIDED.
    -- Blocks a DECIDED row with no disposition, and a disposition/decided_at on a non-DECIDED row.
    CHECK (
        (status =  'DECIDED' AND disposition IS NOT NULL AND decided_at IS NOT NULL) OR
        (status <> 'DECIDED' AND disposition IS NULL     AND decided_at IS NULL)
    ),
    -- A correction deadline only makes sense for a NEEDS_CORRECTION disposition.
    CHECK (correction_due_at IS NULL OR disposition = 'NEEDS_CORRECTION')
);

CREATE INDEX IF NOT EXISTS idx_submissions_queue ON submissions (status, beverage_type, submitted_at);

-- Keep updated_at honest: neither engine updates it on its own (SQLite has no ON UPDATE clause).
-- Relies on the default PRAGMA recursive_triggers = OFF so the inner UPDATE does not re-fire.
CREATE TRIGGER IF NOT EXISTS trg_submissions_set_updated_at
AFTER UPDATE ON submissions
FOR EACH ROW
BEGIN
    UPDATE submissions SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
-- TODO(postgres): replace with a BEFORE UPDATE trigger calling a set_updated_at() function
-- (NEW.updated_at := now(); RETURN NEW); the AFTER-UPDATE re-update above is a SQLite idiom.
-- TODO(postgres): replace TEXT+CHECK enums with native CREATE TYPE … AS ENUM if deploying on
-- Postgres; keep CHECK constraints on SQLite. Recommendation: keep CHECK-constrained TEXT for
-- the POC — it is portable, greppable, and trivially seedable.

-- ── label_images ─────────────────────────────────────────────────────────────
-- The 1–10 images that make up one label set (brand/front, back, neck, additional).
-- One row per image file; child of submissions.
CREATE TABLE IF NOT EXISTS label_images (
    id               INTEGER PRIMARY KEY,
    submission_id    INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    image_role       TEXT    CHECK (image_role IN ('BRAND','BACK','NECK','STRIP','OTHER')),
    position         INTEGER CHECK (position BETWEEN 1 AND 10),
    filename         TEXT    NOT NULL,
    mime_type        TEXT,
    width_px         INTEGER,
    height_px        INTEGER,
    label_width_in   REAL,
    label_height_in  REAL,
    file_size_bytes  INTEGER,
    -- Local-OpenCV preprocessing outputs (Story 2.3 / architecture D7 + AR-7). Derived
    -- enhanced/binarized variants are written as FILES to the generated-images root on the
    -- Volume and referenced here by path RELATIVE to that root (portable local↔Volume); the
    -- original `filename` is never replaced. NULL when a clean image needed no enhancement
    -- (no variant files written — the "omitted, not inert" UI contract, UX-DR-13).
    enhanced_path    TEXT,          -- grayscale/color variant (PaddleOCR input), relative path
    binarized_path   TEXT,          -- thresholded variant (Tesseract input), relative path
    preprocess_log   TEXT,          -- JSON: ordered transforms applied + params (deskew angle,
                                    -- CLAHE clip) + per-stage ms; for the Epic-5 benchmark/audit
    preprocess_ms    INTEGER CHECK (preprocess_ms IS NULL OR preprocess_ms >= 0),
    preprocessed_at  TIMESTAMP,     -- UTC ISO-8601 when preprocessing ran; NULL until it has
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (submission_id, position)
);
CREATE INDEX IF NOT EXISTS idx_label_images_submission ON label_images (submission_id);

-- ── audit_events ─────────────────────────────────────────────────────────────
-- Append-only lifecycle/processing timeline (database-schema.md §1.7). The seed
-- writes one SEEDED row per submission; the pipeline (Epic 2) and web layer write
-- the rest of the fixed event vocabulary. Added here because Story 1.3 is the
-- first to need it.
CREATE TABLE IF NOT EXISTS audit_events (
    id             INTEGER PRIMARY KEY,
    submission_id  INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    event_type     TEXT NOT NULL CHECK (event_type IN
                     ('SEEDED','OCR_STARTED','OCR_COMPLETED','ANALYSIS_COMPLETED',
                      'READY','OPENED','DECIDED','UNDONE')),
    actor          TEXT,
    from_status    TEXT,
    to_status      TEXT,
    note           TEXT,
    occurred_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_events_submission ON audit_events (submission_id, occurred_at);

-- ── ocr_results ──────────────────────────────────────────────────────────────
-- One row per OCR engine run on one image — the multi-OCR benchmark store
-- (database-schema.md §1.3). Each engine (tesseract / paddleocr / …) gets its
-- OWN row per image: per-engine results are stored independently, never merged
-- (AR-4). Created here by Story 2.1, the first to need it.
CREATE TABLE IF NOT EXISTS ocr_results (
    id               INTEGER PRIMARY KEY,
    label_image_id   INTEGER NOT NULL REFERENCES label_images(id) ON DELETE CASCADE,
    submission_id    INTEGER NOT NULL REFERENCES submissions(id)  ON DELETE CASCADE,
    engine_name      TEXT    NOT NULL,
    engine_version   TEXT,
    extracted_text   TEXT,           -- the OcrResult.text contract field
    confidence       REAL    CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    word_boxes       TEXT,           -- JSON (list of per-word {text, box}); Postgres: JSONB
    latency_ms       INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
    ran_on_cpu       BOOLEAN DEFAULT 1,
    -- Which image variant THIS row OCR'd (Story 2.4 / AR-7). A degraded image is OCR'd on
    -- both the ORIGINAL and a preprocessed variant (engine-aware: Tesseract↔BINARIZED,
    -- PaddleOCR↔ENHANCED) so Epic 5 can score preprocessed-vs-original accuracy; a clean
    -- image (no Story 2.3 variants) is OCR'd on the ORIGINAL only. Default ORIGINAL so
    -- pre-2.4 inserts and the clean-image path need no caller change.
    image_variant    TEXT    NOT NULL DEFAULT 'ORIGINAL'
                       CHECK (image_variant IN ('ORIGINAL','ENHANCED','BINARIZED')),
    status           TEXT DEFAULT 'OK' CHECK (status IN ('OK','ERROR')),
    error_text       TEXT,           -- writer-supplied; not part of the OcrResult shape
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ocr_results_image      ON ocr_results (label_image_id);
CREATE INDEX IF NOT EXISTS idx_ocr_results_engine     ON ocr_results (engine_name);
CREATE INDEX IF NOT EXISTS idx_ocr_results_submission ON ocr_results (submission_id);
-- Per-(engine, variant) roll-up for the Epic-5 preprocessed-vs-original benchmark.
CREATE INDEX IF NOT EXISTS idx_ocr_results_variant    ON ocr_results (engine_name, image_variant);
-- TODO(postgres): word_boxes -> JSONB for indexed querying. SQLite: store JSON as TEXT.

-- ── llm_results ──────────────────────────────────────────────────────────────
-- One row per LLM/VLM model run — full model identity, timing, and token counts
-- so the benchmark can compute $/1,000 verifications (database-schema.md §1.4).
-- The LLM is optional (OCR-only fallback), so rows here may be absent. Per-model
-- rows are stored independently (AR-4). Created here by Story 2.1.
CREATE TABLE IF NOT EXISTS llm_results (
    id                INTEGER PRIMARY KEY,
    submission_id     INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    label_image_id    INTEGER REFERENCES label_images(id) ON DELETE SET NULL,
    task              TEXT,
    model_name        TEXT,
    model_id          TEXT,
    model_full_id     TEXT,
    provider          TEXT,
    is_benchmark_only BOOLEAN DEFAULT 0,   -- writer-supplied; not part of the LlmResult shape
    prompt_tokens     INTEGER CHECK (prompt_tokens     IS NULL OR prompt_tokens     >= 0),
    completion_tokens INTEGER CHECK (completion_tokens IS NULL OR completion_tokens >= 0),
    -- Derived, never inserted: the sum can never drift from its parts. NULL if either part is NULL.
    -- Mirrored by the LlmResult.total_tokens read-only property in app/contracts.py.
    total_tokens      INTEGER GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED,
    latency_ms        INTEGER CHECK (latency_ms        IS NULL OR latency_ms        >= 0),
    requested_at      TIMESTAMP,
    responded_at      TIMESTAMP,
    result_text       TEXT,
    status            TEXT DEFAULT 'OK' CHECK (status IN ('OK','ERROR')),
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_llm_results_submission ON llm_results (submission_id);
CREATE INDEX IF NOT EXISTS idx_llm_results_model      ON llm_results (model_id);
-- TODO(normalization): if the model list grows, factor model_name/model_id/model_full_id/
-- provider into a `llm_models` reference table and FK to it. Keep inline for the POC.
