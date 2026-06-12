# Database Schema — Mock COLA Submissions (Label Specialist POC)

**Status:** Design document (no application code). · **Last updated:** 2026-06-11
**Audience:** implementers seeding the mock database and building the read-only Label Specialist POC.

## Purpose & scope

This document specifies the **mock COLA-submissions schema** that backs the TTB COLA
**Label Specialist** proof-of-concept. It is the data foundation for the reviewer-side workspace
that does not publicly exist (see [`approach.md`](approach.md) and the domain research, which
confirms the applicant side is well-documented but the reviewer side is unbuilt).

Ground-truth requirements come from `ref-docs/discussion-points.md` (§4 Data Model, §5
Processing, §6 OCR/LLM stats), `ref-docs/Research-Findings.md` (§5 Form 5100.31 fields, §6
image mechanics, §7 dispositions), and TTB Form 5100.31 (`ref-docs/f510031.pdf`).

**Honored decisions (do not relitigate here):**

- The DB holds **three field categories**: (a) **APPLICATION** fields (from the real
  application / Form 5100.31, "STORRd" / submitted), (b) **OCR-EXTRACTED** fields, (c)
  **future** fields defined later. See [§4](#4-the-three-field-categories).
- A **label = 1–10 images** (front / back / additional applied labels). Modeled as a
  **child table**, not 10 columns — see [§1](#label_images) for the rationale.
- Capture `application_date`, decision date, a **minimal `status` enum** + timestamps
  (NOT a heavyweight workflow state machine — RESOLVED in discussion-points §5/§11), engine
  `processing_ms`, and **per-OCR / per-LLM timing stats**.
- **LLM stats** capture model name, model ID, full model ID, timestamps, latency, and tokens
  (for the `$/1,000 verifications` cost analysis).
- **Dispositions** are the real TTB Label Specialist states (**Approved / Needs Correction /
  Rejected**); the **engine verdict** (**PASS / REVIEW / FAIL**) is a *separate* advisory
  signal. See [§3](#3-enumerations).
- **v1 only READS** seeded dummy data — no image upload, no data entry. Everything is either
  **seeded** or **computed by background jobs** (see [§5](#5-seeded-vs-computed)).

**Cross-references:**

- [`data-dictionary.md`](data-dictionary.md) — the per-field reference (common name,
  specification, definition, source) for every column listed here. This schema gives **shape
  and relationships**; the data dictionary gives **per-field semantics**. They are meant to be
  read together.
- [`approach.md`](approach.md) — overall architecture, the pre-compute pipeline, and the
  deterministic-vs-LLM check strategy that populate these tables.

**Portability:** DDL is written to run on **SQLite** (the locked POC engine — architecture.md D1) and
**PostgreSQL** with minimal change. Where the two diverge (enums, JSON, timestamps,
identity columns), the SQLite-friendly form is shown inline and the Postgres variant is noted
in a comment or a `TODO`.

---

## 1. Entity overview (ER description)

The schema centers on a **`submissions`** row (one mock COLA application). Everything else
hangs off it:

```
                         ┌──────────────────────────┐
                         │        submissions       │  one mock COLA application
                         │  (application fields +    │  (APPLICATION-category fields,
                         │   lifecycle + verdict)    │   status, timestamps, engine ms)
                         └────────────┬─────────────┘
                                      │ 1
          ┌───────────────┬───────────┼───────────────┬────────────────────┐
          │ N             │ N         │ N             │ N                  │ N
   ┌──────┴──────┐ ┌──────┴──────┐ ┌──┴───────────┐ ┌─┴──────────────┐ ┌──┴───────────┐
   │ label_images│ │field_       │ │checklist_    │ │ llm_results    │ │ audit_events │
   │ (1–10 per   │ │comparisons  │ │items         │ │ (per model run)│ │ (timeline)   │
   │  submission)│ │(app vs      │ │(per required │ └────────────────┘ └──────────────┘
   └──────┬──────┘ │ extracted)  │ │ check +      │
          │ 1      └─────────────┘ │ verdict)     │
          │ N                      └──────────────┘
   ┌──────┴──────┐
   │ ocr_results │  per OCR engine, per image (Tesseract, PaddleOCR, …)
   │ (per engine │
   │  per image) │
   └─────────────┘
```

| Table | Grain (one row =) | Purpose |
|---|---|---|
| **`submissions`** | one mock COLA application | The application/Form 5100.31 fields, beverage type, lifecycle (`status` + timestamps), and the rolled-up engine verdict + `processing_ms`. |
| **`label_images`** | one image file (1–10 per submission) | The 1–10 label images (brand/front, back, neck, additional), each tagged by label-role; filename + metadata. |
| **`ocr_results`** | one OCR engine run on one image | Raw + extracted text, confidence, and timing for each OCR engine on each image — the multi-OCR benchmark data. |
| **`llm_results`** | one LLM/VLM model run | Model identity, latency, token counts, and result for each LLM call — feeds the cost & accuracy benchmark. |
| **`field_comparisons`** | one application-field vs extracted-value comparison | The vertical-stacked "app value vs OCR/LLM value" rows the review UI shows, with a match outcome. |
| **`checklist_items`** | one required check for a submission | The reframed desk-checklist: each mandatory CFR check, its per-check engine verdict, and citation. |
| **`audit_events`** | one lifecycle/processing event | Append-only timeline (seeded + job-written) for time-to-decision, throughput, and the ~5s claim. |

A separate small reference table, **`ocr_engines`** / **`llm_models`** (optional), can
normalize engine/model identity; for the POC these are kept as plain columns on
`ocr_results` / `llm_results` (see the `TODO` in [§1.4](#llm_results)) to keep seeding simple.

---

### 1.1 `submissions`

One mock COLA application. Holds the **APPLICATION-category** fields (Form 5100.31), the
beverage type, the **lifecycle** (minimal `status` enum + timestamps), and the **rolled-up
engine verdict** with total `processing_ms`. This is the row the "Next Submission" button
serves.

| Column | Type | Key | Purpose |
|---|---|---|---|
| `id` | INTEGER / BIGSERIAL | PK | Surrogate key. |
| `ttb_id` | TEXT | UNIQUE | TTB ID assigned on submission (the public identifier). |
| `serial_number` | TEXT |  | Form 5100.31 Box 4 (year + sequence). APPLICATION. |
| `beverage_type` | TEXT (enum) |  | `WINE` / `DISTILLED_SPIRITS` / `MALT_BEVERAGE`. Box 5. Drives which checks apply; shown prominently in the UI. |
| `source_of_product` | TEXT (enum) |  | `DOMESTIC` / `IMPORTED`. Box 3. |
| `application_type` | TEXT (enum) |  | `LABEL_APPROVAL` / `EXEMPTION` / `DISTINCTIVE_BOTTLE` / `RESUBMISSION`. Box 14. |
| `brand_name` | TEXT |  | Box 6. APPLICATION. Matched against the label. |
| `fanciful_name` | TEXT |  | Box 7 (optional). APPLICATION. |
| `class_type_designation` | TEXT |  | Product class/type designation (e.g. "Kentucky Straight Bourbon Whiskey"). APPLICATION — **maker-entered** (the COLAs Online "Product Class/Type" code, typed or via lookup; see `../ref-docs/Definition of Terms.txt`). Matched application ↔ OCR (`ocr_class_type`) like brand name. |
| `applicant_name_address` | TEXT |  | Box 8 name + address (incl. approved DBA/tradename). APPLICATION. |
| `mailing_address` | TEXT |  | Box 8a (if different). APPLICATION. |
| `plant_registry_no` | TEXT |  | Box 2 plant registry / basic permit / brewer's no. APPLICATION. |
| `alcohol_content` | TEXT |  | ABV as filed (e.g. "45% Alc./Vol."). APPLICATION (e-filed field). |
| `net_contents` | TEXT |  | e.g. "750 mL". APPLICATION (e-filed field). |
| `grape_varietal` | TEXT |  | Box 10 (wine only). APPLICATION. |
| `wine_appellation` | TEXT |  | Box 11 (wine only). APPLICATION. |
| `wine_vintage` | TEXT |  | Vintage (wine only, e-filed). APPLICATION. |
| `formula_id` | TEXT |  | Box 9 formula / pre-import approval ref. APPLICATION. |
| `phone` | TEXT |  | Box 12. APPLICATION. |
| `email` | TEXT |  | Box 13. APPLICATION. |
| `status` | TEXT (enum) | NOT NULL | Lifecycle state — see [§3.1](#31-lifecycle-status-enum). |
| `engine_verdict` | TEXT (enum) |  | Rolled-up advisory verdict `PASS`/`REVIEW`/`FAIL` — see [§3.2](#32-engine-verdict-enum). NULL until analysis runs. |
| `disposition` | TEXT (enum) |  | The Label Specialist's final TTB disposition, set on decision — see [§3.1](#31-lifecycle-status-enum). NULL until decided. |
| `application_date` | DATE |  | Box 16 — date the applicant filed. SEEDED. |
| `submitted_at` | TIMESTAMP |  | When the record entered the mock review queue. SEEDED. |
| `decided_at` | TIMESTAMP |  | When the Label Specialist dispositioned it. NULL until decided. |
| `processing_ms` | INTEGER |  | Total engine pre-compute time (sum of OCR + analysis), for the ~5s claim. Job-written. |
| `created_at` | TIMESTAMP | NOT NULL | Row insert time. |
| `updated_at` | TIMESTAMP | NOT NULL | Last update time. |

```sql
-- SQLite-friendly; see TODO notes for Postgres variants.
CREATE TABLE submissions (
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
    processing_ms           INTEGER,
    created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_submissions_queue ON submissions (status, beverage_type, submitted_at);
-- TODO(postgres): replace TEXT+CHECK enums with native CREATE TYPE … AS ENUM if deploying on
-- Postgres; keep CHECK constraints on SQLite. Recommendation: keep CHECK-constrained TEXT for
-- the POC — it is portable, greppable, and trivially seedable.
```

> **Why these APPLICATION fields?** They are exactly the Form 5100.31 fields a Label Specialist
> matches against the artwork (Research-Findings §5): brand, fanciful, name/address,
> class/type, net contents, ABV, plus the wine-only varietal/appellation/vintage. The
> per-field common name / spec / definition lives in [`data-dictionary.md`](data-dictionary.md).

---

### 1.2 `label_images`

The **1–10 images** that make up one label set (brand/front, back, neck, and any additional
applied labels). One row per image file.

| Column | Type | Key | Purpose |
|---|---|---|---|
| `id` | INTEGER | PK | Surrogate key. |
| `submission_id` | INTEGER | FK → submissions.id | Owning submission. |
| `image_role` | TEXT (enum) |  | `BRAND` / `BACK` / `NECK` / `STRIP` / `OTHER` — the TTB image tag. |
| `position` | INTEGER |  | Display/order index 1–10 within the submission. |
| `filename` | TEXT | NOT NULL | The label-image filename (the field discussion-points §4 calls for). |
| `mime_type` | TEXT |  | `image/jpeg` or `image/tiff` (COLAs Online accepts JPG/JPEG/TIFF; PNG noted as a modern addition — Research-Findings §6). |
| `width_px` / `height_px` | INTEGER |  | Pixel dimensions (from OCR/preprocessing). |
| `label_width_in` / `label_height_in` | REAL |  | Physical label size if captured — the *only* possible scale reference; absent → font-size checks stay out of scope. |
| `file_size_bytes` | INTEGER |  | For the ≤750 KB baseline note. |
| `created_at` | TIMESTAMP | NOT NULL | Insert time. |

```sql
CREATE TABLE label_images (
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
CREATE INDEX idx_label_images_submission ON label_images (submission_id);
```

> **Child table vs. 10 columns — the rationale.** discussion-points §4 requires accommodating
> **1–10 images**. A `label_image_1 … label_image_10` set of columns is rejected because it:
> (a) wastes columns and forces NULL-padding for the common 1–2 image case; (b) makes "extract
> text from every image" a 10-way `UNION` instead of a simple join; (c) cannot carry
> per-image metadata (role, dimensions, size) without ballooning to ~60 columns; (d) hard-caps
> the design — a child table extends to 11+ by changing one `CHECK`. **Recommendation
> (adopted): a child `label_images` table**, one row per image, `UNIQUE(submission_id,
> position)` enforcing ordering, role tag mirroring TTB's per-image type tagging. This is the
> standard one-to-many normalization and it makes the per-image `ocr_results` join natural.

---

### 1.3 `ocr_results`

One row per **OCR engine** run on **one image**. This is the multi-OCR benchmark store:
Tesseract and PaddleOCR (and optionally PP-OCRv5) each get their own row with **timing
statistics** (discussion-points §6).

| Column | Type | Key | Purpose |
|---|---|---|---|
| `id` | INTEGER | PK | Surrogate key. |
| `label_image_id` | INTEGER | FK → label_images.id | The image OCR'd. |
| `submission_id` | INTEGER | FK → submissions.id | Denormalized for easy roll-up queries. |
| `engine_name` | TEXT |  | `tesseract` / `paddleocr` / `ppocrv5` …. |
| `engine_version` | TEXT |  | Engine version string (procurement traceability). |
| `extracted_text` | TEXT |  | Full text the engine returned. |
| `confidence` | REAL |  | Engine-reported mean confidence (0–1), where available. |
| `word_boxes` | TEXT (JSON) |  | Per-word text + bounding boxes (JSON); supports future spatial/field-of-vision logic. |
| `latency_ms` | INTEGER |  | Wall-clock time for this engine on this image — the timing stat. |
| `ran_on_cpu` | BOOLEAN |  | Whether run was CPU-only (govt infra has no guaranteed GPU). |
| `status` | TEXT (enum) |  | `OK` / `ERROR`. |
| `error_text` | TEXT |  | Populated on `ERROR`. |
| `created_at` | TIMESTAMP | NOT NULL | When the OCR job wrote this row. |

```sql
CREATE TABLE ocr_results (
    id               INTEGER PRIMARY KEY,
    label_image_id   INTEGER NOT NULL REFERENCES label_images(id) ON DELETE CASCADE,
    submission_id    INTEGER NOT NULL REFERENCES submissions(id)  ON DELETE CASCADE,
    engine_name      TEXT    NOT NULL,
    engine_version   TEXT,
    extracted_text   TEXT,
    confidence       REAL,
    word_boxes       TEXT,           -- JSON; Postgres: JSONB
    latency_ms       INTEGER,
    ran_on_cpu       BOOLEAN DEFAULT 1,
    status           TEXT DEFAULT 'OK' CHECK (status IN ('OK','ERROR')),
    error_text       TEXT,
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_ocr_results_image  ON ocr_results (label_image_id);
CREATE INDEX idx_ocr_results_engine ON ocr_results (engine_name);
-- TODO(postgres): word_boxes -> JSONB for indexed querying. SQLite: store JSON as TEXT.
```

---

### 1.4 `llm_results`

One row per **LLM / VLM model run**. Captures full **model identity, timing, and token
counts** so the benchmark can compute `$/1,000 verifications` (discussion-points §4, §6).
The LLM is **optional** (POC + OCR-fallback), so rows here may be absent for a submission.

| Column | Type | Key | Purpose |
|---|---|---|---|
| `id` | INTEGER | PK | Surrogate key. |
| `submission_id` | INTEGER | FK → submissions.id | Owning submission. |
| `label_image_id` | INTEGER | FK → label_images.id (nullable) | Image, if the call was image-scoped. |
| `task` | TEXT |  | What the call did (e.g. `extract_fields`, `ocr_fallback`, `classify`). |
| `model_name` | TEXT |  | Human model name (e.g. "Claude Opus 4.8"). discussion-points §4. |
| `model_id` | TEXT |  | Short model ID (e.g. `claude-opus-4-8`). |
| `model_full_id` | TEXT |  | Full/version-pinned model ID (e.g. `claude-opus-4-8[1m]`). |
| `provider` | TEXT |  | `anthropic` / `openai` / `google` / `local`. A cloud provider here is classified `models-internal-endpoint` (stand-in for an in-firewall endpoint); `local` is zero-egress. See [`outbound-calls-inventory.md`](outbound-calls-inventory.md). |
| `is_benchmark_only` | BOOLEAN |  | TRUE = a comparison-only model run (extra models run purely to populate the benchmark table), distinct from the run that fed the displayed extraction/verdict. Both run in the live pipeline; this flag separates "shown to the specialist" from "captured for procurement comparison." |
| `prompt_tokens` | INTEGER |  | Input tokens — cost analysis. |
| `completion_tokens` | INTEGER |  | Output tokens — cost analysis. |
| `total_tokens` | INTEGER |  | Convenience sum. |
| `latency_ms` | INTEGER |  | Call latency (LangChain-traced, local-only). |
| `requested_at` / `responded_at` | TIMESTAMP |  | Call start/end timestamps. discussion-points §4. |
| `result_text` | TEXT |  | Raw model output (or extracted JSON). |
| `status` | TEXT (enum) |  | `OK` / `ERROR`. |
| `created_at` | TIMESTAMP | NOT NULL | Row write time. |

```sql
CREATE TABLE llm_results (
    id                INTEGER PRIMARY KEY,
    submission_id     INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    label_image_id    INTEGER REFERENCES label_images(id) ON DELETE SET NULL,
    task              TEXT,
    model_name        TEXT,
    model_id          TEXT,
    model_full_id     TEXT,
    provider          TEXT,
    is_benchmark_only BOOLEAN DEFAULT 0,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    latency_ms        INTEGER,
    requested_at      TIMESTAMP,
    responded_at      TIMESTAMP,
    result_text       TEXT,
    status            TEXT DEFAULT 'OK' CHECK (status IN ('OK','ERROR')),
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_llm_results_submission ON llm_results (submission_id);
CREATE INDEX idx_llm_results_model      ON llm_results (model_id);
-- TODO(normalization): if the model list grows, factor model_name/model_id/model_full_id/
-- provider into a `llm_models` reference table and FK to it. Recommendation: keep them inline
-- for the POC (fewer joins, simpler seeding); normalize in phase 2 when the benchmark matrix
-- is larger.
```

---

### 1.5 `field_comparisons`

One row per **application-field vs extracted-value** comparison — the backing data for the
UI's **vertical stacked** comparison (application value on top, OCR/LLM value below) and the
**discrepancy highlighting** (discussion-points §9). This is where the three field categories
meet: an APPLICATION value is compared to an OCR/LLM-EXTRACTED value.

| Column | Type | Key | Purpose |
|---|---|---|---|
| `id` | INTEGER | PK | Surrogate key. |
| `submission_id` | INTEGER | FK → submissions.id | Owning submission. |
| `field_key` | TEXT |  | Stable field identifier (e.g. `brand_name`, `alcohol_content`) — joins to [`data-dictionary.md`](data-dictionary.md). |
| `application_value` | TEXT |  | The APPLICATION-category value (from `submissions`). |
| `extracted_value` | TEXT |  | The OCR/LLM-EXTRACTED value found on the label. |
| `extracted_source` | TEXT |  | Provenance: `ocr:tesseract`, `ocr:paddleocr`, `llm:<model_id>`. |
| `source_ocr_result_id` | INTEGER | FK → ocr_results.id (nullable) | Link to the originating OCR row. |
| `source_llm_result_id` | INTEGER | FK → llm_results.id (nullable) | Link to the originating LLM row. |
| `match_status` | TEXT (enum) |  | `MATCH` / `MISMATCH` / `MISSING` / `UNVERIFIABLE`. |
| `similarity` | REAL |  | Normalized similarity 0–1 (tolerance band guards the "STONE'S THROW" false-mismatch). |
| `created_at` | TIMESTAMP | NOT NULL | Job write time. |

```sql
CREATE TABLE field_comparisons (
    id                    INTEGER PRIMARY KEY,
    submission_id         INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    field_key             TEXT    NOT NULL,
    application_value     TEXT,
    extracted_value       TEXT,
    extracted_source      TEXT,
    source_ocr_result_id  INTEGER REFERENCES ocr_results(id) ON DELETE SET NULL,
    source_llm_result_id  INTEGER REFERENCES llm_results(id) ON DELETE SET NULL,
    match_status          TEXT CHECK (match_status IN ('MATCH','MISMATCH','MISSING','UNVERIFIABLE')),
    similarity            REAL,
    created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_field_comparisons_submission ON field_comparisons (submission_id);
```

---

### 1.6 `checklist_items`

One row per **required check** for a submission — the digital version of Jenny Park's printed
desk checklist (discussion-points §9). Each row carries a **per-check engine verdict** and the
**CFR citation as data** (so the 2022 Part 5 renumbering doesn't require code changes). The
submission's rolled-up `engine_verdict` is the aggregate of these.

| Column | Type | Key | Purpose |
|---|---|---|---|
| `id` | INTEGER | PK | Surrogate key. |
| `submission_id` | INTEGER | FK → submissions.id | Owning submission. |
| `check_key` | TEXT |  | Stable check identifier (e.g. `government_warning`, `abv_present`, `net_contents_format`). |
| `label` | TEXT |  | Human-readable check name for the UI. |
| `cfr_citation` | TEXT |  | Citation stored as data (e.g. `27 CFR 16.21`, `27 CFR 5.65`). |
| `check_type` | TEXT (enum) |  | `DETERMINISTIC` / `FIELD_MATCH` / `HYBRID` / `MANUAL` — how it's evaluated. |
| `verdict` | TEXT (enum) |  | `PASS` / `REVIEW` / `FAIL` / `NA` per check. |
| `detail` | TEXT |  | Advisory note / why it flagged (e.g. "warning reworded"). |
| `field_comparison_id` | INTEGER | FK → field_comparisons.id (nullable) | Links a field-match check to its comparison row. |
| `created_at` | TIMESTAMP | NOT NULL | Job write time. |

```sql
CREATE TABLE checklist_items (
    id                   INTEGER PRIMARY KEY,
    submission_id        INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    check_key            TEXT    NOT NULL,
    label                TEXT,
    cfr_citation         TEXT,
    check_type           TEXT CHECK (check_type IN ('DETERMINISTIC','FIELD_MATCH','HYBRID','MANUAL')),
    verdict              TEXT CHECK (verdict IN ('PASS','REVIEW','FAIL','NA')),
    detail               TEXT,
    field_comparison_id  INTEGER REFERENCES field_comparisons(id) ON DELETE SET NULL,
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_checklist_items_submission ON checklist_items (submission_id);
```

---

### 1.7 `audit_events`

Append-only **timeline** of lifecycle and processing events. This is the lightweight metrics
substrate (discussion-points §5 RESOLVED) that yields time-to-decision, throughput, and the
~5s interaction-latency claim — **without** a heavyweight workflow engine.

| Column | Type | Key | Purpose |
|---|---|---|---|
| `id` | INTEGER | PK | Surrogate key. |
| `submission_id` | INTEGER | FK → submissions.id | Owning submission. |
| `event_type` | TEXT (enum) |  | `SEEDED` / `OCR_STARTED` / `OCR_COMPLETED` / `ANALYSIS_COMPLETED` / `READY` / `OPENED` / `DECIDED`. |
| `actor` | TEXT |  | `system:ocr_job`, `system:analysis_job`, or `Label Specialist` (the POC has no real auth — a label only). |
| `from_status` / `to_status` | TEXT |  | Status transition captured (if any). |
| `note` | TEXT |  | Free-text detail. |
| `occurred_at` | TIMESTAMP | NOT NULL | Event time — the timeline axis. |

```sql
CREATE TABLE audit_events (
    id             INTEGER PRIMARY KEY,
    submission_id  INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    event_type     TEXT NOT NULL CHECK (event_type IN
                     ('SEEDED','OCR_STARTED','OCR_COMPLETED','ANALYSIS_COMPLETED',
                      'READY','OPENED','DECIDED')),
    actor          TEXT,
    from_status    TEXT,
    to_status      TEXT,
    note           TEXT,
    occurred_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_audit_events_submission ON audit_events (submission_id, occurred_at);
```

---

## 2. Future fields (category c)

To represent **"fields to be defined later"** (discussion-points §4 category c) without
ALTERing the schema every time, the POC uses a thin **EAV-style extension table** plus a
documented convention. This keeps category (c) explicit and queryable rather than smuggling it
into ad-hoc JSON.

| Column | Type | Key | Purpose |
|---|---|---|---|
| `id` | INTEGER | PK | Surrogate key. |
| `submission_id` | INTEGER | FK → submissions.id | Owning submission. |
| `field_key` | TEXT |  | Future field identifier (must be registered in [`data-dictionary.md`](data-dictionary.md)). |
| `category` | TEXT (enum) |  | `APPLICATION` / `OCR_EXTRACTED` / `FUTURE` — keeps the three categories explicit. |
| `value_text` | TEXT |  | Value (typed loosely for the POC). |
| `created_at` | TIMESTAMP | NOT NULL | Insert time. |

```sql
CREATE TABLE submission_extra_fields (
    id             INTEGER PRIMARY KEY,
    submission_id  INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    field_key      TEXT NOT NULL,
    category       TEXT CHECK (category IN ('APPLICATION','OCR_EXTRACTED','FUTURE')),
    value_text     TEXT,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (submission_id, field_key)
);
-- TODO: decide whether future fields graduate to first-class columns once stable.
-- Recommendation: prototype new fields here; promote a field to a real `submissions` column
-- once it is load-bearing and its data-dictionary entry is finalized.
```

---

## 3. Enumerations

The two enum families are **deliberately separate** and must not be conflated: `status` +
`disposition` describe **the TTB process**; `engine_verdict` describes **the machine's
advice**. The engine never sets a disposition — it only advises; the human decides
(discussion-points §1, §8 RESOLVED).

### 3.1 Lifecycle `status` enum (+ `disposition`)

**`status`** — the minimal POC lifecycle (NOT TTB's full workflow). It tracks the
pre-compute pipeline and review, with timestamps doing the heavy lifting:

| `status` | Meaning | Set by |
|---|---|---|
| `RECEIVED` | Seeded into the mock queue, not yet processed. | Seed |
| `PROCESSING` | OCR / analysis background jobs running. | OCR job |
| `READY_FOR_REVIEW` | Pre-compute done; "Next Submission" can serve it instantly. | Analysis job |
| `IN_REVIEW` | A Label Specialist has opened it. | UI (read path) |
| `DECIDED` | Label Specialist recorded a disposition. | UI |

**`disposition`** — the **real TTB Label Specialist decision** (Research-Findings §7), set only
when `status = DECIDED`:

| `disposition` | Meaning |
|---|---|
| `APPROVED` | COLA issues. |
| `NEEDS_CORRECTION` | Returned to submitter; fixable (30-day clock). |
| `REJECTED` | Terminal denial; requires fresh resubmission. |

> `RECEIVED` / `ASSIGNED` / `WITHDRAWN` / `SURRENDERED` are real TTB states but **out of scope**
> for this read-only POC. `ASSIGNED` is folded into `READY_FOR_REVIEW` / `IN_REVIEW`. Documented
> here so the mapping to TTB's full vocabulary is explicit.

### 3.2 Engine-verdict enum

**`engine_verdict`** — the **advisory** machine signal, distinct from any TTB state.
Per-check on `checklist_items`, rolled up onto `submissions`:

| `engine_verdict` | Meaning |
|---|---|
| `PASS` | All checks pass; nothing flagged. |
| `REVIEW` | Not auto-decidable (ambiguity, missing scale, spatial inference) — defer to human. |
| `FAIL` | A deterministic check failed (e.g. Government Warning reworded / missing). |

> **"REVIEW" is not a disposition.** It is an informal engine band. The TTB term for a fixable
> problem is **Needs Correction**. Keeping the two enums separate is the whole point: the engine
> can say `FAIL` while the Label Specialist still chooses `NEEDS_CORRECTION` (fixable) rather than
> `REJECTED` (terminal) — a judgment only the human makes.

---

## 4. The three field categories

discussion-points §4 mandates three categories. They are represented as follows:

| Category | What it is | Where it lives |
|---|---|---|
| **(a) APPLICATION** | Fields from the real application / Form 5100.31 ("STORRd" / as-submitted). | First-class columns on **`submissions`** (brand_name, alcohol_content, net_contents, …). Optionally extended via `submission_extra_fields` with `category='APPLICATION'`. |
| **(b) OCR-EXTRACTED** | Text/values pulled from the label artwork by OCR (or LLM fallback). | **`ocr_results`** (raw per engine/image) and **`llm_results`** (per model), distilled into the `extracted_value` column of **`field_comparisons`**. |
| **(c) FUTURE** | Fields defined later. | **`submission_extra_fields`** with `category='FUTURE'`, registered in [`data-dictionary.md`](data-dictionary.md); promoted to real columns when stable. |

The **`field_comparisons`** table is where (a) and (b) are placed side by side (logically;
**vertically** in the UI) and a `match_status` is computed. Every `field_key` in
`field_comparisons` / `submission_extra_fields` resolves to an entry in
[`data-dictionary.md`](data-dictionary.md), which is the single source of truth for each
field's common name, specification, definition, and **category**.

---

## 5. Seeded vs. computed

The POC **only reads**; nothing is entered through the UI. Each row is either **seeded**
(dummy fixture data) or **written by a background job** during the pre-compute pipeline.

| Table | Seeded (fixtures) | Computed by background jobs |
|---|---|---|
| `submissions` | All APPLICATION fields, `ttb_id`, `beverage_type`, `application_date`, `submitted_at`, `status='RECEIVED'`. | `status` transitions, `engine_verdict`, `processing_ms`. `disposition`/`decided_at` set when a Label Specialist decides in the read UI. |
| `label_images` | Filenames + role + dimensions for the 1–10 seeded images. | (none — images are fixtures, no upload in v1). |
| `ocr_results` | — | **OCR job:** one row per engine per image, with `latency_ms`, text, confidence. |
| `llm_results` | — | **Analysis job / benchmark harness:** model identity, tokens, latency. |
| `field_comparisons` | — | **Analysis job:** compares APPLICATION vs EXTRACTED → `match_status`. |
| `checklist_items` | Check definitions (`check_key`, `label`, `cfr_citation`, `check_type`) may be seeded as a template. | **Analysis job:** the per-check `verdict` + `detail`. |
| `audit_events` | A `SEEDED` event per submission. | Job-written events (`OCR_STARTED` … `DECIDED`). |
| `submission_extra_fields` | Optional seeded category-c samples. | Future-job-written as new fields appear. |

**Pre-compute flow (writes that populate the computed columns):** seed `submissions` +
`label_images` → OCR job writes `ocr_results` → analysis job writes `llm_results` (if used),
`field_comparisons`, and `checklist_items`, then rolls up `engine_verdict` + `processing_ms`
onto `submissions` and flips `status` to `READY_FOR_REVIEW`. By the time the Label Specialist hits
"Next Submission," everything is already computed — the structural answer to the abandoned
5-minute pilot. See [`approach.md`](approach.md) for the pipeline design.

---

## 6. Open choices (TODO)

- **Resolved (architecture.md D1):** `TEXT + CHECK` for the POC; native Postgres `ENUM` is the
  Phase-2 scale path — portable across SQLite/Postgres, greppable, trivially seeded.
- **TODO(model normalization):** inline model columns on `llm_results` vs. an `llm_models`
  reference table. **Recommendation:** inline for the POC; normalize in phase 2 as the
  benchmark matrix grows.
- **TODO(JSON columns):** `word_boxes` as TEXT (SQLite) vs. JSONB (Postgres). **Recommendation:**
  TEXT-JSON now; switch to JSONB only if spatial/field-of-vision queries become real.
- **TODO(future-field graduation):** when a `submission_extra_fields` field becomes
  load-bearing, promote it to a first-class `submissions` column and update
  [`data-dictionary.md`](data-dictionary.md).
- **TODO(queue buckets):** discussion-points §8 floats splitting the queue into
  "very-likely-compliant vs troublesome." If adopted, derive it from `engine_verdict` at query
  time rather than adding a column. **Recommendation:** keep it a query, not schema.
