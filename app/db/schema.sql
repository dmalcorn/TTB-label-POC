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
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (submission_id, position)
);
CREATE INDEX IF NOT EXISTS idx_label_images_submission ON label_images (submission_id);
