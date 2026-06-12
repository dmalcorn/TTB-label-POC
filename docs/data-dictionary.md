# Data Dictionary — TTB COLA Label Specialist POC

*Human-readable field dictionary for the mock COLA database and processing
pipeline. This document defines **what each field means**; the table/DDL
definitions (primary keys, foreign keys, indexes, constraints) live in the
companion [`database-schema.md`](./database-schema.md).*

**Author:** Diane · **Last updated:** 2026-06-12

> **This document is the authoritative per-field reference for the data model.** The architecture
> ([`../_bmad-output/planning-artifacts/architecture.md`](../_bmad-output/planning-artifacts/architecture.md),
> *Data Architecture*) references it rather than copying it. Every `field_key`/`check_key` used in the
> code and rulesets must resolve to an entry here; table/DDL definitions live in the companion
> [`database-schema.md`](database-schema.md).

> **Naming authority:** [`database-schema.md`](./database-schema.md) is the **authoritative
> source for exact column names** (DDL). As of the 2026-06-12 reconciliation, the **Field Name**
> column in this dictionary holds the **exact schema column name** for every field that is a
> real column, so the two docs reconcile 1:1 — no crosswalk needed. The **Common Name** column
> carries the friendly / Form 5100.31 label.
>
> Two things to watch:
> - Form 5100.31 boxes that the POC does **not** persist (Rep ID, signature, etc.) are listed
>   for form fidelity and marked **“Not a POC column.”** They have no schema counterpart.
> - A field's storage table is named in its Definition where it isn't obvious (e.g. per-field
>   OCR values live in `field_comparisons`, not `ocr_results`).

---

## How to read this document

Each field is described with four columns, per the request in
[`../ref-docs/discussion-points.md`](../ref-docs/discussion-points.md) §4
("a separate **data dictionary** — field name, 'common name,' specification,
definition"):

| Column | Meaning |
|---|---|
| **Field Name** | The technical / database column name (snake_case). |
| **Common Name** | The plain label a Label Specialist or applicant would recognize (often the Form 5100.31 box name). |
| **Specification** | Data type, format, length, units, and allowed values. |
| **Definition** | Plain-English meaning of the field and where it comes from. |

**Field categories** (mirroring the three storage buckets named in
[`discussion-points.md`](../ref-docs/discussion-points.md) §4 — application
fields, OCR-extracted fields, fields-to-be-defined — expanded for the POC):

1. [Application fields](#1-application-fields) — from Form 5100.31 / STORRd.
2. [Label image fields](#2-label-image-fields) — 1–10 images per submission.
3. [OCR-extracted fields](#3-ocr-extracted-fields) — per OCR engine per image.
4. [LLM / benchmark stat fields](#4-llm--benchmark-stat-fields) — per model run.
5. [Engine / disposition fields](#5-engine--disposition-fields) — verdict & decision.
6. [Comparison, checklist & audit tables](#6-comparison-checklist--audit-tables) — `field_comparisons`, `checklist_items`, `audit_events`, `submission_extra_fields`, `review_progress`.

**Primary sources** (relative-path links):
- [`../ref-docs/f510031.pdf`](../ref-docs/f510031.pdf) — TTB Form 5100.31 (04/2023), OMB 1513-0020 — application field names & box numbers.
- [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) — §5 (matchable form fields), §6 (image mechanics), §7 (dispositions).
- [`../ref-docs/ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf) — distilled-spirits mandatory-label elements & approved formats.
- [`../ref-docs/discussion-points.md`](../ref-docs/discussion-points.md) — §4 (data model), §6 (LLM stats), §10 (image types).

---

## 1. Application fields

Sourced from **TTB Form 5100.31** (the COLA application) and its e-filed
(COLAs Online / STORRd) representation. Box numbers in the **Common Name**
column refer to the printed form
([`../ref-docs/f510031.pdf`](../ref-docs/f510031.pdf)). The fields flagged
*matchable* are the ones a Label Specialist compares against the label artwork
([`Research-Findings.md`](../ref-docs/Research-Findings.md) §5).

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `ttb_id` | TTB ID | String, 14 digits, format `YYjjjnnnnnnnnn` (year + Julian filing date + sequence); system-assigned. Unique, not null. | The unique identifier TTB assigns to an application (the "eApplication") on submission. The primary external key for a submission ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §5). |
| `serial_number` | Serial Number (Box 4) | String, ≤6 chars, format `YY-nnn` (last two digits of year + applicant sequence, e.g. `26-001`). Required. | Applicant-assigned sequential serial number, beginning with the last two digits of the current calendar year (Form 5100.31 Item 4). Distinct from the TTB ID. |
| `rep_id_no` | Rep. ID No. (Box 1) | **Not a POC column.** String, optional. | Third-party representative ID number, present only if the application is submitted by a representative (Item 1). Documented for form fidelity; not persisted in the POC schema. |
| `plant_registry_no` | Plant Registry / Basic Permit / Brewer's No. (Box 2) | String, required. Format varies by commodity (BW-/TPWBH-/DSP- prefixes etc.). | The applicant's TTB-issued registry, basic permit, or brewer's notice number (Item 2). |
| `source_of_product` | Source of Product (Box 3) | Enum: `DOMESTIC` \| `IMPORTED` (TEXT + CHECK). Nullable. | Whether the product is domestically produced or imported (Item 3). Drives the country-of-origin check. |
| `beverage_type` | Type of Product (Box 5) | Enum: `WINE` \| `DISTILLED_SPIRITS` \| `MALT_BEVERAGE` (TEXT + CHECK). Not null. | Box 5 beverage type (Sake → "wine"). Determines which rule set applies ([`ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf); [`Research-Findings.md`](../ref-docs/Research-Findings.md) §1). The matching logic branches on this field. |
| `class_type_designation` | Class/Type Designation | String, nullable. Free-text (e.g. "Kentucky Straight Bourbon Whiskey"). | The maker-entered **Product Class/Type code** (typed or via lookup — see `../ref-docs/Definition of Terms.txt`, "Product Class/Type"). *Matchable* application ↔ OCR (`ocr_class_type`) like brand name. |
| `brand_name` | Brand Name (Box 6) | String, required. | The name under which the product is sold; if not sold under a brand, the name of the bottler/packer/importer (Item 6). *Matchable* against the label's brand label. |
| `fanciful_name` | Fanciful Name (Box 7) | String, optional, nullable. | A name that further identifies the product; required for some specialty products, optional otherwise (Item 7). *Matchable.* |
| `applicant_name_address` | Name and Address of Applicant (Box 8) | Text block, nullable. Includes approved DBA / trade name if used on the label. | The applicant's company name and address as shown on plant registry / basic permit / brewer's notice (Item 8). *Matchable* against the label's name/address statement (must follow "Bottled By", "Imported By", etc. — [`ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf), 27 CFR 5.66). |
| `mailing_address` | Mailing Address, if different (Box 8a) | Text block, optional, nullable. | Alternate mailing address if different from Box 8 (Item 8a). Not a label-matched field. |
| `formula_id` | Formula (Box 9) | String, optional, nullable. TTB Formula ID / Formula lab number. | The system-generated TTB Formula ID for products requiring pre-COLA formula approval (Item 9). |
| `grape_varietal` | Grape Varietal(s) — Wine only (Box 10) | String / list of strings, optional (wine only), nullable. | Each grape varietal appearing on a wine label (Item 10). *Matchable* (wine). Triggers appellation requirement; varietal claim requires ≥75% ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §1). |
| `wine_appellation` | Wine Appellation — if on label (Box 11) | String, optional (wine only), nullable. | The appellation of origin stated on a wine label (Item 11). *Matchable* (wine). |
| `wine_vintage` | Wine Vintage | **TEXT, as filed** (e.g. `"2021"`), optional (wine only), nullable. **Not a numbered box on the printed form** — appears in the e-filed view. | The vintage year for wine, captured in the COLAs Online record ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §5). *Matchable* (wine). Stored as text (as-filed) to mirror the label string; parse to a year only when needed. |
| `alcohol_content` | Alcohol Content | **TEXT, as filed** (e.g. `"45% Alc./Vol."`), nullable. **E-filed field** (not a numbered box). Required per beverage rules (always for spirits). | Alcohol by volume, stored as the as-filed string (not a parsed decimal). On distilled spirits the label statement format is "Alcohol __ % by volume"; abbreviations "Alc.", "Alc", "Vol.", "Vol", "%" are acceptable; proof is an optional addition in the same field of vision ([`ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf), 27 CFR 5.65). *Matchable.* See note below on per-type ABV rules. |
| `net_contents` | Net Contents | String with metric volume + unit (e.g. `750 mL`, `1.5 L`). **E-filed field**; for spirits/wine must meet an approved **metric standard of fill** (e.g. 750 mL — 27 CFR 5.203 / 4.72). Required. | The volume of beverage in the container. On the form, Box 15 captures it only if blown/branded/embossed and not on an affixed label. *Matchable.* ([`ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf), 27 CFR 5.70). |
| `phone` | Phone Number (Box 12) | String, optional, nullable. | Phone number of the person responsible for the application (Item 12). |
| `email` | Email Address (Box 13) | String (email), optional, nullable. | Email for TTB's response to the application (Item 13). |
| `application_type` | Type of Application (Box 14) | Enum: `LABEL_APPROVAL` \| `EXEMPTION` \| `DISTINCTIVE_BOTTLE` \| `RESUBMISSION` (TEXT + CHECK, **single value**). Nullable. | The kind of certificate requested (Item 14) — Box 14's `a/b/c/d` map to these four values respectively. `RESUBMISSION` corresponds to a prior application (the Box 14d TTB ID is **not** persisted in the POC). |
| `resubmission_ttb_id` | Resubmission TTB ID (Box 14d) | **Not a POC column.** String, 14 digits, optional. | The prior TTB ID a rejected application is being resubmitted against (Item 14d). Documented for form fidelity; not persisted in the POC schema. |
| `blown_branded_text` | Blown/Branded/Embossed Info (Box 15) | **Not a POC column.** Text, optional. | Info blown, branded, or embossed on the container (e.g. net contents) shown only if it does not appear on affixed labels; also foreign-language translations (Item 15). Documented for form fidelity; not persisted in the POC schema. |
| `application_date` | Date of Application (Box 16) | Date (ISO `YYYY-MM-DD`). Required. | The date the application was prepared/submitted (Item 16). Captured as the submission "clock start" ([`discussion-points.md`](../ref-docs/discussion-points.md) §4). |
| `applicant_signature` | Signature of Applicant/Agent (Box 17) | **Not a POC column.** String / signature flag. | The perjury-clause electronic verification signature (Part II, Item 17). Documented for form fidelity; not persisted in the POC schema. |
| `applicant_print_name` | Print Name of Applicant/Agent (Box 18) | **Not a POC column.** String. | Printed name of the signer (Item 18). Documented for form fidelity; not persisted in the POC schema. |
| `submitted_at` | Submitted Timestamp | Timestamp (ISO 8601, UTC). Required. | When the record entered the review queue. Powers time-to-decision / throughput metrics ([`discussion-points.md`](../ref-docs/discussion-points.md) §5). |
| `decided_at` | Decision / Approval Date | Timestamp (ISO 8601, UTC), nullable until decided. | When the Label Specialist's disposition was recorded (Form Part III "Date Issued" on approval). See [§5](#5-engine--disposition-fields). |

> **Per-type ABV rule note (do not hard-code "ABV always required"):** the ABV
> requirement differs by beverage type — **spirits: always required**; **wine:
> required only if >14% ABV (or not labeled "table"/"light")**; **beer: usually
> optional**. A naive "ABV must be present" check produces false rejections on
> beer and table wine ([`Research-Findings.md`](../ref-docs/Research-Findings.md)
> §1). The matching logic must branch on `beverage_type`.

---

## 2. Label image fields

A submission carries **1–10 label images** (front/brand, back, neck, and any
additional applied labels), each tagged by label type. Baseline accepted formats
and limits come from the live COLAs Online upload screens
([`Research-Findings.md`](../ref-docs/Research-Findings.md) §6;
[`discussion-points.md`](../ref-docs/discussion-points.md) §10).

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `id` | Image ID | `INTEGER PRIMARY KEY` (SQLite rowid). Not null. | Surrogate key for one label image row. |
| `submission_id` | Submission (FK) | `INTEGER`, FK → `submissions.id`, `ON DELETE CASCADE`. Not null. | Owning submission. The schema FKs on the integer `submission_id`, **not** `ttb_id`. |
| `filename` | Image Filename | String, not null. | Stored filename of the label image. A submission has **1–10** such files ([`discussion-points.md`](../ref-docs/discussion-points.md) §4). |
| `position` | Image # | Integer 1–10 (CHECK), nullable. `UNIQUE(submission_id, position)`. | Display/order index of this image within the submission's image set. |
| `image_role` | Label Type / Tag | Enum: `BRAND` \| `BACK` \| `NECK` \| `STRIP` \| `OTHER` (TEXT + CHECK), nullable. | The label-position tag (TTB tags each image). Mandatory elements may be distributed across labels and checked across the *union* of images ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §4, §6). **No `FRONT` value** — front/brand artwork is `BRAND`. |
| `mime_type` | File Format (MIME) | String, nullable. `image/jpeg` or `image/tiff` (COLAs Online accepts JPG/JPEG/TIFF; PNG a modern addition — TODO confirm). | MIME type of the image file. Stored as a MIME string, not a `JPG`/`TIFF` token ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §6). |
| `file_size_bytes` | File Size | Integer bytes, nullable. ≤750 KB is the TTB baseline (a note, **not** a CHECK in the POC schema). | Size of the image file. COLAs Online caps each file at ≤750 KB ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §6). |
| `width_px` | Width (pixels) | Integer, nullable. | Pixel width, from image metadata. |
| `height_px` | Height (pixels) | Integer, nullable. | Pixel height, from image metadata. |
| `label_width_in` | Label Width (inches) | `REAL` inches, nullable. | Physical label width; usable as a pixels→mm scale reference for (conditional) type-size checks ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §3). TODO: confirm captured in STORRd. |
| `label_height_in` | Label Height (inches) | `REAL` inches, nullable. | Physical label height (scale reference companion to `label_width_in`). TODO. |
| `created_at` | Created Timestamp | Timestamp, not null, default `CURRENT_TIMESTAMP`. | When the image row was inserted. (Images are fixtures in v1 — there is no separate upload time.) |

> **Not stored in the POC schema:** an OpenCV `preprocessed` flag (deskew / perspective / glare).
> Preprocessing is part of the pipeline ([`discussion-points.md`](../ref-docs/discussion-points.md)
> §10) but its state is not persisted on `label_images` in v1; add a column if it becomes
> load-bearing.

---

## 3. OCR-extracted fields

The pipeline runs **two OCR engines (Tesseract and PaddleOCR, optionally PP-OCRv5)**, each in its
own background job with timing stats. The schema models this as **one `ocr_results` row per engine
per image** — holding the engine's **full raw text + per-run metadata**, *not* a column per
matchable field. The parsed per-field values (brand, ABV, net contents, …) are persisted
**separately** in `field_comparisons.extracted_value`, keyed by `field_key`, where each is paired
with its application value and a `match_status` (see the relocated-fields note below).

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `id` | OCR Result ID | `INTEGER PRIMARY KEY` (SQLite rowid). Not null. | Surrogate key for one OCR run on one image. |
| `label_image_id` | Image (FK) | `INTEGER`, FK → `label_images.id`, `ON DELETE CASCADE`. Not null. | The specific image that was OCR'd. (Grain is **per image**, not per submission.) |
| `submission_id` | Submission (FK) | `INTEGER`, FK → `submissions.id`, `ON DELETE CASCADE`. Not null. | Owning submission (denormalized for roll-up; indexed). |
| `engine_name` | OCR Engine | String, not null (e.g. `tesseract`, `paddleocr`, `ppocrv5`). No CHECK — extensible. | Which OCR product produced this extraction; enables per-engine accuracy/speed comparison ([`discussion-points.md`](../ref-docs/discussion-points.md) §6). |
| `engine_version` | OCR Engine Version | String, nullable. | Version string of the OCR engine (reproducibility / procurement traceability). |
| `extracted_text` | OCR Raw Text | Text (full dump), nullable. | The full unstructured text the engine read, before field parsing — fallback and audit trail. |
| `confidence` | OCR Confidence | `REAL`, nullable. **CHECK 0–1** (not 0–100). | Engine-reported mean confidence for the extraction, where available. |
| `word_boxes` | Word Boxes (JSON) | TEXT holding JSON (Postgres: JSONB), nullable. | Per-word text + bounding boxes; supports future spatial / field-of-vision logic. |
| `latency_ms` | OCR Time (ms) | Integer milliseconds, nullable. **CHECK ≥ 0**. | Wall-clock time the engine took on this image, for the speed benchmark ([`discussion-points.md`](../ref-docs/discussion-points.md) §6). |
| `ran_on_cpu` | Ran on CPU | Boolean, default `1` (true). | Whether the run was CPU-only (govt infra has no guaranteed GPU). |
| `status` | OCR Status | Enum: `OK` \| `ERROR` (TEXT + CHECK), default `OK`. | Outcome of the OCR run. |
| `error_text` | Error Text | Text, nullable. | Populated when `status = ERROR`. |
| `created_at` | OCR Run Timestamp | Timestamp, not null, default `CURRENT_TIMESTAMP`. | When the OCR job wrote this row. |

> **Relocated — per-field OCR values are NOT columns on `ocr_results`.** The values read off the
> label for each matchable field (`brand_name`, `fanciful_name`, `applicant_name_address`,
> `class_type_designation`, `alcohol_content`, `net_contents`, `grape_varietal`,
> `wine_appellation`, `wine_vintage`, and the Government Warning) are **persisted** by the analysis
> job into `field_comparisons` — one row per application-field vs. extracted-value, with
> `extracted_value`, `match_status`, `similarity`, and a `source_ocr_result_id` / `source_llm_result_id`
> pointing back to the originating run (see [§6](#6-comparison-checklist--audit-tables) and
> [`database-schema.md`](./database-schema.md) §1.5). The Government Warning wording check is
> additionally evaluated as a `checklist_items` row ([`Research-Findings.md`](../ref-docs/Research-Findings.md)
> §2; 27 CFR Part 16). The provenance label (`ocr:tesseract`, `llm:<model_id>`) is the derived
> `extracted_source` column on the `v_field_comparisons` view, not a stored string.

---

## 4. LLM / benchmark stat fields

The LLM is **optional** (POC demonstration + fallback when OCR matching is weak),
and the pipeline is designed to **benchmark multiple LLMs** on the same extraction
task. LangChain is used **only to gather timing statistics** and is easy to
disable to honor the no-outbound-calls constraint
([`discussion-points.md`](../ref-docs/discussion-points.md) §6). The model
identity fields below are required by §4 of
[`discussion-points.md`](../ref-docs/discussion-points.md) ("capture **model name,
model ID, full model ID, and timestamps**").

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `id` | LLM Run ID | `INTEGER PRIMARY KEY` (SQLite rowid). Not null. | Surrogate key for one LLM extraction/judgment run. |
| `submission_id` | Submission (FK) | `INTEGER`, FK → `submissions.id`, `ON DELETE CASCADE`. Not null. | Submission the LLM run belongs to (FKs on `submission_id`, not `ttb_id`). |
| `label_image_id` | Image (FK) | `INTEGER`, FK → `label_images.id`, `ON DELETE SET NULL`, nullable. | The image, if the call was image-scoped (e.g. a VLM extraction); null otherwise. |
| `task` | Task | String, nullable (e.g. `extract_fields`, `ocr_fallback`, `classify`). | What the call did. |
| `model_name` | Model Name | String, nullable (e.g. "Claude Opus 4.8", "GPT", "Gemini"). | Human-friendly name of the model used ([`discussion-points.md`](../ref-docs/discussion-points.md) §4). |
| `model_id` | Model ID | String, nullable (short id, e.g. `claude-opus-4-8`). | The short/family model identifier. |
| `model_full_id` | Full Model ID | String, nullable (version-pinned id, e.g. `claude-opus-4-8[1m]`). | The exact, fully-qualified model identifier used for the call — the reproducible "what ran" ([`discussion-points.md`](../ref-docs/discussion-points.md) §4). **Schema column is `model_full_id`** (not `full_model_id`). |
| `provider` | Provider | String, nullable (`anthropic` \| `openai` \| `google` \| `local`). | The model vendor — the locked LLM roster (Anthropic Claude / OpenAI GPT / Google Gemini) plus an optional local VLM (architecture.md D6). |
| `is_benchmark_only` | Benchmark-only | Boolean, default `0` (false). | TRUE = a comparison-only model run captured purely to populate the benchmark table, distinct from the run that fed the displayed extraction/verdict. |
| `prompt_tokens` | Prompt Tokens | Integer, nullable. **CHECK ≥ 0**. | Input token count for the call (cost analysis input). |
| `completion_tokens` | Completion Tokens | Integer, nullable. **CHECK ≥ 0**. | Output token count for the call. |
| `total_tokens` | Total Tokens | Integer, nullable, **stored generated column** (`prompt_tokens + completion_tokens`) — never written directly. | Sum of prompt + completion tokens; feeds LLM-cost-per-1,000-verifications analysis ([`discussion-points.md`](../ref-docs/discussion-points.md) §6). |
| `latency_ms` | Latency (ms) | Integer milliseconds, nullable. **CHECK ≥ 0**. | End-to-end response time captured (via LangChain tracing) for the speed benchmark. |
| `result_text` | LLM Output | Text / JSON, nullable. | The structured extraction or judgment the model returned (mirror of matchable fields, or a match verdict). |
| `status` | LLM Status | Enum: `OK` \| `ERROR` (TEXT + CHECK), default `OK`. | Outcome of the LLM call. |
| `requested_at` | Started Timestamp | Timestamp, nullable. | When the LLM call started ([`discussion-points.md`](../ref-docs/discussion-points.md) §4). |
| `responded_at` | Completed Timestamp | Timestamp, nullable. | When the LLM call returned. |
| `created_at` | Created Timestamp | Timestamp, not null, default `CURRENT_TIMESTAMP`. | Row write time. |

> **Derived / not stored on `llm_results`:**
> - **`cost_usd`** (tokens × price) is **computed at analysis time**, not a stored column — see the
>   benchmarking plan ([`ocr-llm-benchmarking-plan.md`](./ocr-llm-benchmarking-plan.md)). TODO: pricing
>   source per model.
> - **`langchain_trace_id`** is **not a POC column** — LangChain tracing is local-only and
>   disable-able; add a column only if traces need to be persisted and joined.

---

## 5. Engine / disposition fields

Two distinct concepts, kept separate per
[`Research-Findings.md`](../ref-docs/Research-Findings.md) §7 and
[`discussion-points.md`](../ref-docs/discussion-points.md) §8:

- **Engine verdict** = the *software's advisory recommendation* (`PASS` /
  `REVIEW` / `FAIL`). "Review" is informal, not a TTB disposition.
- **Lifecycle `status`** = where the submission sits in the POC pipeline
  (`RECEIVED` → `PROCESSING` → `READY_FOR_REVIEW` → `IN_REVIEW` → `DECIDED`).
- **`disposition`** = the *Label Specialist's decision*, mirroring TTB's real
  states (`Approved` / `Needs Correction` / `Rejected`), set only once `status =
  DECIDED`. The software recommends; the human decides
  ([`discussion-points.md`](../ref-docs/discussion-points.md) §1). These two fields
  follow the authoritative split in [`database-schema.md`](./database-schema.md) §3.1.

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `engine_verdict` | Engine Verdict | Enum: `PASS` \| `REVIEW` \| `FAIL`. Not null once computed. | The automated pre-screen recommendation produced by the compliance engine — advisory only, never the final decision ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §7). |
| *(reasons)* | Verdict Reasons | **Not a single column** — normalized into the `checklist_items` table (one row per check). | Which checks passed/failed (e.g. missing Government Warning, ABV mismatch) backing the verdict; drives the UI checklist and discrepancy highlights. See [§6](#6-comparison-checklist--audit-tables). |
| `status` | Lifecycle Status | Enum (lifecycle): `RECEIVED` \| `PROCESSING` \| `READY_FOR_REVIEW` \| `IN_REVIEW` \| `DECIDED`. Default `RECEIVED`. | The submission's **lifecycle** state through the POC pre-compute and review pipeline (NOT a TTB disposition). Authoritative DDL: [`database-schema.md`](./database-schema.md) §3.1. |
| `disposition` | Disposition | Enum (disposition): `APPROVED` (Approved) \| `NEEDS_CORRECTION` (Needs Correction) \| `REJECTED` (Rejected). Nullable; set only when `status = DECIDED`. | The **Label Specialist's final decision**, the three real TTB dispositions. Mirrors TTB's real terms, not invented "Pass/Fail" ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §7; [`discussion-points.md`](../ref-docs/discussion-points.md) §8; [`database-schema.md`](./database-schema.md) §3.1). |
| `specialist_id` | Label Specialist | `TEXT` on `submissions`, nullable. | Identifier of the reviewing Label Specialist who decided the submission. The POC has no user accounts/roles — access is a single shared token gate (`ACCESS_TOKEN`), so this is a demo/token identity ([`discussion-points.md`](../ref-docs/discussion-points.md) §3; architecture.md Auth). |
| `decision_notes` | Decision Notes | `TEXT` on `submissions`, nullable. | Free-text rationale the Label Specialist records, especially the specified issues for a `NEEDS_CORRECTION` return. |
| `correction_due_at` | Correction Deadline | `TIMESTAMP` on `submissions`, nullable. **CHECK: non-null only when `disposition = NEEDS_CORRECTION`.** | The 30-day deadline when the disposition is `NEEDS_CORRECTION`; auto-rejected if not corrected ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §7). |
| `processing_ms` | Engine Processing Time (ms) | Integer milliseconds, nullable. | Total pre-compute pipeline time (OCR + analysis) for this submission, supporting the "displays instantly / ~5s" claim ([`discussion-points.md`](../ref-docs/discussion-points.md) §5). |
| `decided_at` | Decided Timestamp | Timestamp (ISO 8601, UTC), nullable. | When the Label Specialist recorded the disposition. Paired with `submitted_at` ([§1](#1-application-fields)) for time-to-decision metrics. |

> **`status` + `disposition` vs. TTB's combined "COLA Status":** the POC splits TTB's
> single user-facing **COLA Status** into a lifecycle `status` and a separate
> `disposition`. TTB's real combined COLA Status vocabulary is *Received / Needs
> Correction / Rejected / Approved / Withdrawn / Surrendered / Revoked*
> ([`Definition of Terms.txt`](../ref-docs/Definition%20of%20Terms.txt), "COLA Status").
> Roughly: `status=RECEIVED`→Received; the `disposition` values map to Needs
> Correction / Rejected / Approved; *Withdrawn / Surrendered / Revoked* are real TTB
> states but **out of scope** for this read-only POC. `engine_verdict`
> (PASS/REVIEW/FAIL) is a **separate** advisory machine signal — not a COLA Status.

---

## 6. Comparison, checklist & audit tables

These four tables were previously documented only in
[`database-schema.md`](./database-schema.md); their fields are listed here so the dictionary is
complete. They are **computed by background jobs** (except `submission_extra_fields`, which is
seeded/optional), not seeded as application data.

### 6.1 `field_comparisons` — application value vs. extracted value

One row per matchable field per submission; backs the UI's vertical-stacked comparison.

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `id` | Comparison ID | `INTEGER PRIMARY KEY`. Not null. | Surrogate key. |
| `submission_id` | Submission (FK) | `INTEGER`, FK → `submissions.id`, `ON DELETE CASCADE`. Not null. | Owning submission. |
| `field_key` | Field Key | String, not null (e.g. `brand_name`, `alcohol_content`). | Stable field identifier; resolves to a field defined in this dictionary. |
| `application_value` | Application Value | Text, nullable. | The APPLICATION-category value (from `submissions`). |
| `extracted_value` | Extracted Value | Text, nullable. | The OCR/LLM value read off the label. |
| `source_ocr_result_id` | OCR Source (FK) | `INTEGER`, FK → `ocr_results.id`, `ON DELETE SET NULL`, nullable. | Originating OCR run, if OCR-sourced. **At most one** of the two source FKs is set (CHECK). |
| `source_llm_result_id` | LLM Source (FK) | `INTEGER`, FK → `llm_results.id`, `ON DELETE SET NULL`, nullable. | Originating LLM run, if LLM-sourced. Neither set ⇒ `MISSING`/`UNVERIFIABLE`. |
| `match_status` | Match Status | Enum: `MATCH` \| `MISMATCH` \| `MISSING` \| `UNVERIFIABLE` (TEXT + CHECK), nullable. | The field-match outcome. |
| `similarity` | Similarity | `REAL`, nullable. **CHECK 0–1**. | Normalized similarity; the tolerance band guards the "STONE'S THROW" false-mismatch. |
| `created_at` | Created Timestamp | Timestamp, not null, default `CURRENT_TIMESTAMP`. | Job write time. |
| *(derived)* `extracted_source` | Extraction Provenance | **View-only** — on `v_field_comparisons`, not a stored column. | `ocr:<engine_name>` / `llm:<model_id>`, reconstructed from the source FK so identity has one source of truth. |

### 6.2 `checklist_items` — one required check per submission

The digital desk checklist; the submission's rolled-up `engine_verdict` is the aggregate of these.

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `id` | Checklist Item ID | `INTEGER PRIMARY KEY`. Not null. | Surrogate key. |
| `submission_id` | Submission (FK) | `INTEGER`, FK → `submissions.id`, `ON DELETE CASCADE`. Not null. | Owning submission. |
| `check_key` | Check Key | String, not null (e.g. `government_warning`, `abv_present`). | Stable check identifier. |
| `label` | Check Label | String, nullable. | Human-readable check name for the UI. |
| `cfr_citation` | CFR Citation | String, nullable (e.g. `27 CFR 16.21`). | Citation stored **as data** so the 2022 Part 5 renumbering needs no code change. |
| `check_type` | Check Type | Enum: `DETERMINISTIC` \| `FIELD_MATCH` \| `HYBRID` \| `MANUAL` (TEXT + CHECK), nullable. | How the check is evaluated. |
| `verdict` | Check Verdict | Enum: `PASS` \| `REVIEW` \| `FAIL` \| `NA` (TEXT + CHECK), nullable. | Per-check engine verdict. |
| `detail` | Detail | Text, nullable. | Advisory note / why it flagged (e.g. "warning reworded"). |
| `field_comparison_id` | Field Comparison (FK) | `INTEGER`, FK → `field_comparisons.id`, `ON DELETE SET NULL`, nullable. | Links a field-match check to its comparison row. |
| `created_at` | Created Timestamp | Timestamp, not null, default `CURRENT_TIMESTAMP`. | Job write time. |

### 6.3 `audit_events` — append-only lifecycle/processing timeline

The lightweight metrics substrate for time-to-decision, throughput, and the ~5s claim.

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `id` | Event ID | `INTEGER PRIMARY KEY`. Not null. | Surrogate key. |
| `submission_id` | Submission (FK) | `INTEGER`, FK → `submissions.id`, `ON DELETE CASCADE`. Not null. | Owning submission. |
| `event_type` | Event Type | Enum: `SEEDED` \| `OCR_STARTED` \| `OCR_COMPLETED` \| `ANALYSIS_COMPLETED` \| `READY` \| `OPENED` \| `DECIDED` \| `UNDONE` (TEXT + CHECK), not null. | The lifecycle/processing event. `UNDONE` = a just-recorded disposition reversed via the in-session "Recorded — Undo" (§6.5). |
| `actor` | Actor | String, nullable (e.g. `system:ocr_job`, `Label Specialist`). | Who/what produced the event (the POC has no real auth — a label only). |
| `from_status` | From Status | String, nullable. | Status transition source, if any. |
| `to_status` | To Status | String, nullable. | Status transition target, if any. |
| `note` | Note | Text, nullable. | Free-text detail. |
| `occurred_at` | Occurred Timestamp | Timestamp, not null, default `CURRENT_TIMESTAMP`. | Event time — the timeline axis. |

### 6.4 `submission_extra_fields` — category (c) future fields (EAV)

Thin extension table representing "fields to be defined later" without ALTERing the schema.

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `id` | Extra Field ID | `INTEGER PRIMARY KEY`. Not null. | Surrogate key. |
| `submission_id` | Submission (FK) | `INTEGER`, FK → `submissions.id`, `ON DELETE CASCADE`. Not null. | Owning submission. `UNIQUE(submission_id, field_key)`. |
| `field_key` | Field Key | String, not null. | Future field identifier; must be registered in this dictionary. |
| `category` | Category | Enum: `APPLICATION` \| `OCR_EXTRACTED` \| `FUTURE` (TEXT + CHECK), nullable. | Keeps the three field categories explicit. |
| `value_text` | Value | Text, nullable. | Value (typed loosely for the POC). |
| `created_at` | Created Timestamp | Timestamp, not null, default `CURRENT_TIMESTAMP`. | Insert time. |

### 6.5 `review_progress` — in-progress review scratch (one row per submission)

The specialist's *in-progress* manual checklist ticks and *draft* Notes, persisted server-side so a
navigate-away or full browser reload resumes exactly. Written only by the web layer — deliberately
separate from the engine-owned `checklist_items` (architecture **Addendum A**).

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `submission_id` | Submission (PK/FK) | `INTEGER PRIMARY KEY`, FK → `submissions.id`, `ON DELETE CASCADE`. Not null. | Owning submission; one progress row each (the PK enforces uniqueness, enabling upsert). |
| `ticked_check_keys` | Ticked Checks | TEXT, not null, default `'[]'`. JSON array of `check_key` strings. | The checks the specialist has **manually** ticked, distinct from the engine's auto-PASS pre-ticks; drives the "N of M done" counter. |
| `draft_notes` | Draft Notes | Text, nullable. | In-progress Notes typed before a disposition; promoted to `submissions.decision_notes` on disposition. |
| `updated_at` | Updated Timestamp | Timestamp, not null, default `CURRENT_TIMESTAMP`. | Last write (UTC ISO-8601). |

*Lifecycle:* upserted by `POST /review/{id}/progress`; retained through a disposition so
`POST /review/{id}/undo` restores the work; purged by `POST /reset`.

---

## Cross-references & open items

- **Table/DDL definitions** (keys, indexes, constraints, relationships) →
  [`database-schema.md`](./database-schema.md). This dictionary intentionally
  describes fields, not table structure.
- **Regulatory rule citations** behind the matchable fields →
  [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §1–2 and
  [`../ref-docs/ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf).

**Open TODOs gathered above:**
1. Confirm whether `PNG` is accepted in addition to JPG/TIFF for the POC ([§2](#2-label-image-fields)).
2. Confirm `label_width_in` / `label_height_in` are actually captured in STORRd (scale reference for type-size checks) ([§2](#2-label-image-fields)).
3. **Resolved:** field-level discrepancy flags are **persisted** in the `field_comparisons` table by the analysis job ([§3](#3-ocr-extracted-fields)).
4. `provider` **resolved** (`anthropic` \| `openai` \| `google` \| `local`); `cost_usd` is **computed at analysis time, not stored**; per-model **pricing source still open** ([§4](#4-llm--benchmark-stat-fields)).
5. **Resolved:** single shared token gate (`ACCESS_TOKEN`), no user accounts — `specialist_id` is a demo/token identity ([§5](#5-engine--disposition-fields)).
6. **Reconciled 2026-06-12:** Field Names now equal schema columns 1:1; `specialist_id` / `decision_notes` / `correction_due_at` were **added to `submissions`** in [`database-schema.md`](./database-schema.md); per-field OCR values are documented as living in `field_comparisons`, not `ocr_results`.
7. Form 5100.31 boxes marked **"Not a POC column"** (`rep_id_no`, `resubmission_ttb_id`, `blown_branded_text`, `applicant_signature`, `applicant_print_name`) are out of scope — promote to columns only if a use case needs them.
