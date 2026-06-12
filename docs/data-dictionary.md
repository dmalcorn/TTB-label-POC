# Data Dictionary — TTB COLA Label Specialist POC

*Human-readable field dictionary for the mock COLA database and processing
pipeline. This document defines **what each field means**; the table/DDL
definitions (primary keys, foreign keys, indexes, constraints) live in the
companion [`database-schema.md`](./database-schema.md).*

**Author:** Diane · **Last updated:** 2026-06-11

> **Naming authority / crosswalk:** [`database-schema.md`](./database-schema.md) is the
> **authoritative source for exact column names** (DDL). A few Common-Name-driven labels
> in this dictionary differ from the schema's column names; they refer to the same fields:
>
> | This dictionary | `database-schema.md` column |
> |---|---|
> | `product_class_type` (designation) | `class_type_designation` |
> | `name_and_address` | `applicant_name_address` |
> | `formula` | `formula_id` |
> | `phone_number` / `email_address` | `phone` / `email` |
>
> (Not an exhaustive rename — just the key alignments so the two docs reconcile. Where a
> name is unlisted, the two docs already agree.)

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
3. [OCR-extracted fields](#3-ocr-extracted-fields) — per OCR engine.
4. [LLM / benchmark stat fields](#4-llm--benchmark-stat-fields) — per model run.
5. [Engine / disposition fields](#5-engine--disposition-fields) — verdict & decision.

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
| `rep_id_no` | Rep. ID No. (Box 1) | String, optional, nullable. | Third-party representative ID number, present only if the application is submitted by a representative (Item 1). |
| `plant_registry_no` | Plant Registry / Basic Permit / Brewer's No. (Box 2) | String, required. Format varies by commodity (BW-/TPWBH-/DSP- prefixes etc.). | The applicant's TTB-issued registry, basic permit, or brewer's notice number (Item 2). |
| `source_of_product` | Source of Product (Box 3) | Enum: `Domestic` \| `Imported`. Required. | Whether the product is domestically produced or imported (Item 3). Drives the country-of-origin check. |
| `product_class_type` | Type of Product / Class-Type Designation (Box 5 + designation) | Enum (beverage type): `WINE` \| `DISTILLED_SPIRITS` \| `MALT_BEVERAGE`. Plus a free-text class/type designation string (e.g. "Kentucky Straight Bourbon Whiskey"). Required. | Box 5 selects the beverage type (Sake → "wine"); the **Product Class/Type code** is the maker-entered class/type designation (typed or via lookup — see `../ref-docs/Definition of Terms.txt`, "Product Class/Type"). *Matchable* application ↔ OCR like brand name. Determines which rule set applies ([`ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf); [`Research-Findings.md`](../ref-docs/Research-Findings.md) §1). |
| `brand_name` | Brand Name (Box 6) | String, required. | The name under which the product is sold; if not sold under a brand, the name of the bottler/packer/importer (Item 6). *Matchable* against the label's brand label. |
| `fanciful_name` | Fanciful Name (Box 7) | String, optional, nullable. | A name that further identifies the product; required for some specialty products, optional otherwise (Item 7). *Matchable.* |
| `name_and_address` | Name and Address of Applicant (Box 8) | Text block, required. Includes approved DBA / trade name if used on the label. | The applicant's company name and address as shown on plant registry / basic permit / brewer's notice (Item 8). *Matchable* against the label's name/address statement (must follow "Bottled By", "Imported By", etc. — [`ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf), 27 CFR 5.66). |
| `mailing_address` | Mailing Address, if different (Box 8a) | Text block, optional, nullable. | Alternate mailing address if different from Box 8 (Item 8a). Not a label-matched field. |
| `formula` | Formula (Box 9) | String, optional, nullable. TTB Formula ID / Formula lab number. | The system-generated TTB Formula ID for products requiring pre-COLA formula approval (Item 9). |
| `grape_varietal` | Grape Varietal(s) — Wine only (Box 10) | String / list of strings, optional (wine only), nullable. | Each grape varietal appearing on a wine label (Item 10). *Matchable* (wine). Triggers appellation requirement; varietal claim requires ≥75% ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §1). |
| `wine_appellation` | Wine Appellation — if on label (Box 11) | String, optional (wine only), nullable. | The appellation of origin stated on a wine label (Item 11). *Matchable* (wine). |
| `wine_vintage` | Wine Vintage | Integer year (e.g. `2021`), optional (wine only), nullable. **Not a numbered box on the printed form** — appears in the e-filed view. | The vintage year for wine, captured in the COLAs Online record ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §5). *Matchable* (wine). |
| `alcohol_content` | Alcohol Content | Decimal percent ABV (e.g. `45.0`), with display format `Alc __ % by volume`. **E-filed field** (not a numbered box). Required per beverage rules (always for spirits). | Alcohol by volume. On distilled spirits the label statement format is "Alcohol __ % by volume"; abbreviations "Alc.", "Alc", "Vol.", "Vol", "%" are acceptable; proof is an optional addition in the same field of vision ([`ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf), 27 CFR 5.65). *Matchable.* See note below on per-type ABV rules. |
| `net_contents` | Net Contents | String with metric volume + unit (e.g. `750 mL`, `1.5 L`). **E-filed field**; for spirits/wine must meet an approved **metric standard of fill** (e.g. 750 mL — 27 CFR 5.203 / 4.72). Required. | The volume of beverage in the container. On the form, Box 15 captures it only if blown/branded/embossed and not on an affixed label. *Matchable.* ([`ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf), 27 CFR 5.70). |
| `phone_number` | Phone Number (Box 12) | String, optional, nullable. | Phone number of the person responsible for the application (Item 12). |
| `email_address` | Email Address (Box 13) | String (email), optional, nullable. | Email for TTB's response to the application (Item 13). |
| `application_type` | Type of Application (Box 14) | Enum / flag set: `a` Certificate of Label Approval \| `b` Certificate of Exemption ("For sale in __ only") \| `c` Distinctive Liquor Bottle Approval \| `d` Resubmission After Rejection. One or more. Required. | The kind of certificate requested (Item 14). `d` carries the prior `ttb_id`. |
| `resubmission_ttb_id` | Resubmission TTB ID (Box 14d) | String, 14 digits, optional, nullable. | The prior TTB ID a rejected application is being resubmitted against (Item 14d). |
| `blown_branded_text` | Blown/Branded/Embossed Info (Box 15) | Text, optional, nullable. | Info blown, branded, or embossed on the container (e.g. net contents) shown only if it does not appear on affixed labels; also foreign-language translations (Item 15). |
| `application_date` | Date of Application (Box 16) | Date (ISO `YYYY-MM-DD`). Required. | The date the application was prepared/submitted (Item 16). Captured as the submission "clock start" ([`discussion-points.md`](../ref-docs/discussion-points.md) §4). |
| `applicant_signature` | Signature of Applicant/Agent (Box 17) | String / signature flag, required. | The perjury-clause electronic verification signature (Part II, Item 17). |
| `applicant_print_name` | Print Name of Applicant/Agent (Box 18) | String, required. | Printed name of the signer (Item 18). |
| `submitted_at` | Submitted Timestamp | Timestamp (ISO 8601, UTC). Required. | When the record entered the review queue. Powers time-to-decision / throughput metrics ([`discussion-points.md`](../ref-docs/discussion-points.md) §5). |
| `decided_at` | Decision / Approval Date | Timestamp (ISO 8601, UTC), nullable until decided. | When the Label Specialist's disposition was recorded (Form Part III "Date Issued" on approval). See [§5](#5-engine--disposition-fields). |

> **Per-type ABV rule note (do not hard-code "ABV always required"):** the ABV
> requirement differs by beverage type — **spirits: always required**; **wine:
> required only if >14% ABV (or not labeled "table"/"light")**; **beer: usually
> optional**. A naive "ABV must be present" check produces false rejections on
> beer and table wine ([`Research-Findings.md`](../ref-docs/Research-Findings.md)
> §1). The matching logic must branch on `product_class_type`.

---

## 2. Label image fields

A submission carries **1–10 label images** (front/brand, back, neck, and any
additional applied labels), each tagged by label type. Baseline accepted formats
and limits come from the live COLAs Online upload screens
([`Research-Findings.md`](../ref-docs/Research-Findings.md) §6;
[`discussion-points.md`](../ref-docs/discussion-points.md) §10).

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `image_id` | Image ID | Integer / UUID, surrogate key. Not null. | Unique identifier for a single label image row. |
| `ttb_id` | TTB ID (FK) | String, 14 digits. FK → application. Not null. | Links the image to its parent submission. |
| `image_filename` | Image Filename | String (filename incl. extension). Required. | Stored filename of the label image. A submission has **1–10** such files ([`discussion-points.md`](../ref-docs/discussion-points.md) §4). |
| `image_sequence` | Image # | Integer 1–10. Required. | Ordinal position of this image within the submission's image set (1–10). |
| `image_type` | Label Type / Tag | Enum: `brand` \| `neck` \| `back` \| `front` \| `strip` \| `other`. Required. | The label-position tag applied at upload (TTB tags each image brand/neck/back/etc.). Used because mandatory elements may be distributed across labels and checked across the *union* of images ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §4, §6). |
| `image_format` | File Format | Enum: `JPG` \| `JPEG` \| `JPE` \| `TIFF` \| `TIF`. **POC may also accept `PNG`** (TODO confirm). RGB color mode (not CMYK). | The image file format. COLAs Online accepts JPG/JPEG/JPE and TIFF/TIF only ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §6). |
| `file_size_bytes` | File Size | Integer bytes. Constraint: ≤ **768,000** (750 KB) per the TTB baseline. | Size of the image file. COLAs Online caps each file at ≤750 KB ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §6). |
| `width_px` | Width (pixels) | Integer, nullable. | Pixel width, from image metadata. |
| `height_px` | Height (pixels) | Integer, nullable. | Pixel height, from image metadata. |
| `label_width_in` | Label Width (inches) | Decimal inches, nullable. | Physical label width as collected at upload; usable as a pixels→mm scale reference for (conditional) type-size checks ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §3). TODO: confirm captured in STORRd. |
| `label_height_in` | Label Height (inches) | Decimal inches, nullable. | Physical label height (scale reference companion to `label_width_in`). TODO. |
| `preprocessed` | Preprocessed Flag | Boolean, default `false`. | Whether OpenCV preprocessing (deskew / perspective / glare correction) has been applied ([`discussion-points.md`](../ref-docs/discussion-points.md) §10). |
| `uploaded_at` | Uploaded Timestamp | Timestamp (ISO 8601, UTC). | When the image was attached to the submission. |

---

## 3. OCR-extracted fields

The pipeline runs **two OCR engines (Tesseract and PaddleOCR)**, each in its own
background job with timing stats; the engine is identified per row so results can
be compared ([`discussion-points.md`](../ref-docs/discussion-points.md) §6). These
fields **mirror the matchable application fields** in
[§1](#1-application-fields) but hold the value *read off the label image*, for
side-by-side (vertical-stacked) discrepancy display.

| Field Name | Common Name | Specification | Definition |
|---|---|---|---|
| `ocr_result_id` | OCR Result ID | Integer / UUID, surrogate key. Not null. | Unique identifier for one OCR extraction run over one submission's images. |
| `ttb_id` | TTB ID (FK) | String, 14 digits. FK → application. Not null. | Submission the OCR result belongs to. |
| `ocr_engine` | OCR Engine | Enum: `tesseract` \| `paddleocr`. (Extensible — easy to add engines.) Not null. | Which OCR product produced this extraction; enables per-engine accuracy/speed comparison ([`discussion-points.md`](../ref-docs/discussion-points.md) §6). |
| `ocr_engine_version` | OCR Engine Version | String, nullable. | Version string of the OCR engine (reproducibility). |
| `ocr_brand_name` | OCR Brand Name | String, nullable. | Brand name text read from the label image (mirror of `brand_name`). |
| `ocr_fanciful_name` | OCR Fanciful Name | String, nullable. | Fanciful name read from the label (mirror of `fanciful_name`). |
| `ocr_name_and_address` | OCR Name & Address | Text, nullable. | Name/address statement read from the label (mirror of `name_and_address`). |
| `ocr_class_type` | OCR Class/Type Designation | String, nullable. | Class/type designation read from the label (mirror of `product_class_type` designation). |
| `ocr_alcohol_content` | OCR Alcohol Content | String + parsed decimal, nullable. Expected display "Alc __ % by volume". | Alcohol statement read from the label (mirror of `alcohol_content`). |
| `ocr_net_contents` | OCR Net Contents | String, nullable (e.g. "750 mL"). | Net contents read from the label (mirror of `net_contents`). |
| `ocr_grape_varietal` | OCR Grape Varietal | String, nullable (wine). | Grape varietal read from a wine label (mirror of `grape_varietal`). |
| `ocr_wine_appellation` | OCR Wine Appellation | String, nullable (wine). | Appellation read from a wine label (mirror of `wine_appellation`). |
| `ocr_wine_vintage` | OCR Wine Vintage | Integer year, nullable (wine). | Vintage read from a wine label (mirror of `wine_vintage`). |
| `ocr_gov_warning_text` | OCR Government Warning | Text, nullable. | The Health/Government Warning statement text read from the label, for deterministic exact/normalized matching of the mandated wording and the all-caps/bold "GOVERNMENT WARNING:" token ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §2; [`ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf), 27 CFR Part 16). |
| `ocr_raw_text` | OCR Raw Text | Text (full dump), nullable. | The full unstructured text the engine read, before field parsing — fallback and audit trail. |
| `ocr_confidence` | OCR Confidence | Decimal 0–1 (or 0–100), nullable. | Engine-reported confidence score for the extraction (overall or per-field). |
| `ocr_processing_ms` | OCR Time (ms) | Integer milliseconds. | Wall-clock time the OCR job took, for the speed benchmark ([`discussion-points.md`](../ref-docs/discussion-points.md) §6). |
| `ocr_extracted_at` | OCR Run Timestamp | Timestamp (ISO 8601, UTC). | When this OCR extraction ran. |

> **Note:** field-level discrepancy flags (application value vs. OCR value) are a
> derived comparison, not stored input fields. They are **persisted** — written by the
> analysis job to the `field_comparisons` table (one row per app-field vs. extracted
> value, with `match_status` / similarity), not recomputed at display time. See
> [`database-schema.md`](./database-schema.md) §1.5 / §5.

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
| `llm_run_id` | LLM Run ID | Integer / UUID, surrogate key. Not null. | Unique identifier for one LLM extraction/judgment run. |
| `ttb_id` | TTB ID (FK) | String, 14 digits. FK → application. Not null. | Submission the LLM run belongs to. |
| `model_name` | Model Name | String (e.g. "Claude Opus 4.8", "GPT", "Gemini"). Not null. | Human-friendly name of the model used ([`discussion-points.md`](../ref-docs/discussion-points.md) §4). |
| `model_id` | Model ID | String (short id, e.g. `opus-4-8`). Not null. | The short/family model identifier. |
| `full_model_id` | Full Model ID | String (fully-qualified id, e.g. `claude-opus-4-8`). Not null. | The exact, fully-qualified model identifier used for the call — the reproducible "what ran" ([`discussion-points.md`](../ref-docs/discussion-points.md) §4). |
| `provider` | Provider | Enum: `anthropic` \| `openai` \| `google` \| `local`, nullable. | The model vendor — the locked LLM roster (Anthropic Claude / OpenAI GPT / Google Gemini) plus an optional local VLM (architecture.md D6). |
| `prompt_tokens` | Prompt Tokens | Integer, nullable. | Input token count for the call (cost analysis input). |
| `completion_tokens` | Completion Tokens | Integer, nullable. | Output token count for the call. |
| `total_tokens` | Total Tokens | Integer, nullable. | Sum of prompt + completion tokens; feeds LLM-cost-per-1,000-verifications analysis ([`discussion-points.md`](../ref-docs/discussion-points.md) §6). |
| `latency_ms` | Latency (ms) | Integer milliseconds, nullable. | End-to-end response time captured (via LangChain tracing) for the speed benchmark. |
| `cost_usd` | Estimated Cost (USD) | Decimal, nullable. | Estimated dollar cost of the call (tokens × price), for the cost analysis. TODO: confirm pricing source per model. |
| `llm_output` | LLM Output | Text / JSON, nullable. | The structured extraction or judgment the model returned (mirror of matchable fields, or a match verdict). |
| `langchain_trace_id` | Trace ID | String, nullable. | LangChain trace identifier when tracing is enabled; null when disabled. |
| `llm_started_at` | Started Timestamp | Timestamp (ISO 8601, UTC). | When the LLM call started ([`discussion-points.md`](../ref-docs/discussion-points.md) §4). |
| `llm_completed_at` | Completed Timestamp | Timestamp (ISO 8601, UTC), nullable. | When the LLM call returned. |

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
| `engine_verdict_reasons` | Verdict Reasons | Text / JSON list, nullable. | Human-readable list of which checks passed/failed (e.g. missing Government Warning, ABV mismatch) backing the verdict; drives the UI checklist and discrepancy highlights. |
| `status` | Lifecycle Status | Enum (lifecycle): `RECEIVED` \| `PROCESSING` \| `READY_FOR_REVIEW` \| `IN_REVIEW` \| `DECIDED`. Default `RECEIVED`. | The submission's **lifecycle** state through the POC pre-compute and review pipeline (NOT a TTB disposition). Authoritative DDL: [`database-schema.md`](./database-schema.md) §3.1. |
| `disposition` | Disposition | Enum (disposition): `APPROVED` (Approved) \| `NEEDS_CORRECTION` (Needs Correction) \| `REJECTED` (Rejected). Nullable; set only when `status = DECIDED`. | The **Label Specialist's final decision**, the three real TTB dispositions. Mirrors TTB's real terms, not invented "Pass/Fail" ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §7; [`discussion-points.md`](../ref-docs/discussion-points.md) §8; [`database-schema.md`](./database-schema.md) §3.1). |
| `specialist_id` | Label Specialist | String / FK, nullable. | Identifier of the reviewing Label Specialist who decided the submission. The POC has no user accounts/roles — access is a single shared token gate (`ACCESS_TOKEN`), so this is a demo/token identity ([`discussion-points.md`](../ref-docs/discussion-points.md) §3; architecture.md Auth). |
| `decision_notes` | Decision Notes | Text, nullable. | Free-text rationale the Label Specialist records, especially the specified issues for a `NEEDS_CORRECTION` return. |
| `correction_due_at` | Correction Deadline | Timestamp (ISO 8601, UTC), nullable. | The 30-day deadline when status is `NEEDS_CORRECTION`; auto-rejected if not corrected ([`Research-Findings.md`](../ref-docs/Research-Findings.md) §7). |
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
4. `provider` enum **resolved** (`anthropic` \| `openai` \| `google` \| `local`); per-model `cost_usd` **pricing source still open** for the benchmarked LLMs ([§4](#4-llm--benchmark-stat-fields)).
5. **Resolved:** single shared token gate (`ACCESS_TOKEN`), no user accounts — `specialist_id` is a demo/token identity ([§5](#5-engine--disposition-fields)).
