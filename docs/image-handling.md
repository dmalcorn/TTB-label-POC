# Image Handling — TTB COLA Label Specialist POC

**Status:** Design document (no application code). · **Last updated:** 2026-06-11
**Audience:** implementers seeding the mock database, building the pre-OCR pipeline, and
writing the benchmark harness.

## Purpose & scope

This document gives the **definitive answer to the brief's open question** about supported
image types (`ref-docs/discussion-points.md` §10 — "not found in the alcohol-makers' user
guide; define it in the docs if absent"), and specifies how the POC **handles imperfect
images** (glare, off-angle) **without bouncing them back to the submitter** for a correction
cycle — using **local, open-source OpenCV**, not a cloud or LLM call.

Ground-truth requirements come from:

- [`ref-docs/discussion-points.md`](../ref-docs/discussion-points.md) §10 (image types +
  imperfect-image enhancement), §4 (a label = 1–10 images, tagged by type), §3 (no-cloud
  constraint), §7 (font size is NOT checked).
- [`ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §6 (the real government
  baseline: JPG/JPEG/TIFF, ≤750 KB, up to 10 files, RGB not CMYK, one label per image, tag by
  type), §3 (font/scale — no reliable pixel→mm conversion), §4 (mandatory elements spread
  across a *set* of labels).
- [`_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md`](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
  (Technical Trends — OpenCV enhancement without a re-submit; the firewall fork; local-VLM
  fallback).

**Cross-references:**

- [`approach.md`](approach.md) — overall architecture and the background **pre-compute
  pipeline** that this enhancement stage feeds.
- [`database-schema.md`](database-schema.md) — the **`label_images`** child table (1–10 images
  per submission, tagged by role) and **`ocr_results`** that consume enhanced images.
- [`tradeoffs-and-limitations.md`](tradeoffs-and-limitations.md) — font-size non-goal and the
  enhancement limits this document records.
- [`outbound-calls-inventory.md`](outbound-calls-inventory.md) — confirms the enhancement stage
  makes **no outbound calls** (it is pure local OpenCV).

---

## 1. Supported image types & constraints (the definitive answer)

The COLAs Online Industry Member user guide and screens establish the **real government
baseline** (Research-Findings §6). The brief's open question — "what image types are
supported?" — is answered by adopting that baseline and documenting it explicitly here, since
it is not stated in the makers' user guide:

| Format | Accepted? | Source / rationale | Notes |
|---|---|---|---|
| **JPG / JPEG / JPE** | **Yes** | COLAs Online accepted formats (Research-Findings §6, from the COLAs Online screens). | The common case. Stored as `mime_type = image/jpeg` in `label_images`. |
| **TIFF / TIF** | **Yes** | COLAs Online accepted formats (Research-Findings §6). | Must **not** be saved with JPG compression (per the COLAs Online guidance). `mime_type = image/tiff`. |
| **PNG** | **No (POC enhancement / `TODO`)** | PNG is **not** in the documented COLAs Online set. | **`TODO`:** treat PNG support as a deliberate POC modernization. If enabled, accept `image/png`, convert to RGB, and add it to the `mime_type` CHECK in `label_images`. Flag clearly as *beyond the documented government baseline*, not a TTB requirement. |
| **Other (GIF, BMP, WebP, HEIC, PDF, …)** | **No** | Not in the COLAs Online accepted set. | Out of scope; reject or ignore for the POC. |

**Cross-cutting constraints (all from Research-Findings §6 unless noted):**

- **Color mode: RGB, not CMYK.** Print artwork is often CMYK; the accepted upload is RGB. The
  POC assumes RGB input; a `TODO` is to convert CMYK→RGB on ingest if a fixture is CMYK.
- **File size: ≤ 750 KB per file** (the documented government cap). Recorded in
  `label_images.file_size_bytes` for the baseline note. The POC does not re-impose this on
  seeded fixtures, but documents it as the real-system constraint.
- **Count: 1–10 images per submission** (`discussion-points.md` §4). Enforced by
  `label_images.position CHECK (position BETWEEN 1 AND 10)` and `UNIQUE(submission_id,
  position)` — see [`database-schema.md` §1.2](database-schema.md).
- **One label per image** — each uploaded image shows a single label, **tagged by type**
  (brand/front, back, neck, strip, other). See §2.
- **Quality guidance (informational):** COLAs Online sets JPG compression to medium (7/10),
  crops white space / printer's-proof margins, and photographs at actual print size reduced to
  ≤ 8.5×11". The POC treats these as documentation of the input it can expect, not as checks it
  enforces.

> **Why document this at all?** The brief flags that supported types are "not found in the
> alcohol-makers' user guide." This table **is** that missing definition: the answer is
> **JPG/JPEG and TIFF (RGB, ≤750 KB, up to 10, one label each), with PNG as an explicit POC
> `TODO`.**

---

## 2. Image-set model — how 1–10 images per submission are stored & tagged

A **label is not a single image** — it is a **set of 1–10 images** (front/brand, back, neck,
strip, and any additional applied labels), each **tagged by its label role**. This matters for
review because mandatory elements may be **distributed across the set** (Research-Findings
§4: a European wine may carry the brand on the front and the Government Warning, sulfites, and
importer name/address on a back/strip label). The verifier must check the required elements
across the **union** of all images, never demand every element on one image.

This is modeled by the **`label_images`** child table in
[`database-schema.md` §1.2](database-schema.md) — **one row per image file**, not ten columns
(the rationale is documented there: a child table avoids NULL-padding, carries per-image
metadata, and hard-caps cleanly at 1–10 via a single `CHECK`).

| Concept | How it's stored | Source |
|---|---|---|
| The 1–10 images | One `label_images` row each, `position` 1–10, `UNIQUE(submission_id, position)`. | `database-schema.md` §1.2; discussion-points §4 |
| Label-role tag | `image_role` enum: **`BRAND` / `BACK` / `NECK` / `STRIP` / `OTHER`** — mirrors TTB's per-image type tagging. | Research-Findings §6 ("each upload tagged with a type") |
| Format / size | `mime_type` (`image/jpeg` \| `image/tiff` \| `TODO` `image/png`), `file_size_bytes` (≤750 KB baseline). | §1 above |
| Scale (if known) | `label_width_in` / `label_height_in` — the **only** possible pixel→mm scale reference; usually absent (see §4). | Research-Findings §3 |
| OCR linkage | Each image fans out to per-engine `ocr_results` rows (Tesseract, PaddleOCR, …). | `database-schema.md` §1.3 |

**In the POC (v1 read-only):** images are **seeded fixtures**, not uploaded — there is no
upload UI (`discussion-points.md` §1, §4; `database-schema.md` §5). The enhancement pipeline
(§3) runs against the seeded image files in the background pre-compute stage.

---

## 3. Imperfect-image enhancement pipeline (local OpenCV, pre-OCR)

**Goal (Jenny Park's wish, discussion-points §10):** fix glare/angle/skew **without sending the
application back to the submitter** for a correction cycle. The domain research (Technical
Trends — "image enhancement without a re-submit") confirms this is solvable with **open-source,
local, non-LLM** preprocessing — **no cloud call required**.

**Where it runs:** as a **pre-OCR stage** inside the background **pre-compute pipeline** (see
[`approach.md`](approach.md)). For each `label_images` row, the raw image is enhanced, then the
enhanced image is handed to each OCR engine, whose output lands in `ocr_results`
([`database-schema.md` §1.3](database-schema.md)). **Every step is logged** (which transforms
ran, parameters, detected skew angle, timing) so the **benchmark** can attribute OCR-accuracy
gains to enhancement — and so a human can audit what was changed.

**All steps are 100% local OpenCV (`cv2`)** — zero outbound calls (see
[`outbound-calls-inventory.md`](outbound-calls-inventory.md)). Steps run in this order; each is
**conditional** (skipped when its detector says it is not needed, to avoid degrading an
already-clean image):

| # | Step | OpenCV technique | Purpose |
|---|---|---|---|
| 1 | **Decode & normalize color** | `imread`, ensure RGB, convert CMYK→RGB if needed | Consistent input regardless of source; honor the RGB-not-CMYK constraint (§1). |
| 2 | **Grayscale** | `cvtColor(..., COLOR_BGR2GRAY)` | Most downstream steps (skew, threshold) operate on intensity; reduces noise from color channels. |
| 3 | **Denoise** | `fastNlMeansDenoising`, median/bilateral filter | Remove sensor/JPEG-compression noise (the ≤750 KB medium-compression inputs are lossy) before it corrupts thresholding. |
| 4 | **Illumination / glare normalization** | background estimation + division; morphological top-hat; inpaint blown-out highlights | Even out uneven lighting and **glare hotspots** — the exact "imperfect image" case the brief calls out — so text isn't lost under a bright patch. |
| 5 | **Contrast (CLAHE)** | `createCLAHE(...).apply(...)` | Contrast-Limited Adaptive Histogram Equalization lifts faint/low-contrast text locally without over-amplifying noise. |
| 6 | **Deskew** | detect skew angle (Hough lines / `minAreaRect` on text mask) → `warpAffine` rotate | Straighten tilted scans/photos so OCR line-detection works. The **detected angle is logged**. |
| 7 | **Perspective correction** | detect label quad (contour / edge detection) → `getPerspectiveTransform` + `warpPerspective` | Flatten **off-angle** ("bad angle") photos where the label is shot from a slant — rectify to a front-on view. |
| 8 | **Binarization** | adaptive threshold (`adaptiveThreshold`) / Otsu | Crisp black-text-on-white for OCR engines (esp. Tesseract). Applied as an **OCR-input variant**, keeping the enhanced grayscale around too. |

> **Engine-aware note:** Tesseract benefits most from a clean **binarized** image; PaddleOCR /
> PP-OCRv5 often do better on the **enhanced grayscale/color** image. The pipeline can produce
> **both an enhanced and a binarized variant** and let each engine consume its preferred input
> — recorded per `ocr_results` row so the benchmark compares fairly. **`TODO`:** decide whether
> to persist enhanced image artifacts or regenerate them on demand.

**Complementary tool (optional `TODO`):** `unpaper` for scanned-sheet cleanup (border removal,
de-skew of paper scans) where OpenCV alone is awkward. Still fully local.

**Logging for the benchmark (required):** for each image, record the **ordered list of
transforms applied**, key parameters (e.g. **detected deskew angle**, CLAHE clip limit), and
the **per-stage timing**, alongside the OCR result. This makes "did enhancement improve OCR
accuracy/latency?" a measurable question and supports the procurement-grade stats the brief
wants (discussion-points §6). It also rolls into the submission's `processing_ms`
([`database-schema.md` §1.1](database-schema.md)).

---

## 4. What enhancement does NOT do

The enhancement stage **improves readability; it does not invent facts, and it never
auto-rejects.** Explicit non-goals:

- **No font-size / dimension measurement.** Enhancement does **not** measure character height
  in millimeters. Absolute mm cannot be derived from a photo without a reliable physical scale
  reference, and the POC deliberately does **not** check font size — matching both the brief's
  decision and TTB's own posture (applicant swears compliance; COLAs Online disclaims testing
  dimensions/font size). The only possible scale would be the `label_width_in` /
  `label_height_in` fields **if present**; they usually are not, so type-size stays out of
  scope. _Source: discussion-points §7; Research-Findings §3._ See
  [`tradeoffs-and-limitations.md`](tradeoffs-and-limitations.md).
- **No fabrication of unreadable text.** Enhancement never "guesses" or hallucinates characters
  a human couldn't read. It only normalizes the image; the OCR engines (and optional VLM
  fallback) read what is actually there. There is no generative fill-in.
- **No auto-reject on a bad image.** If, after enhancement, text remains unreadable (severe
  glare burn-out, motion blur, missing crop), the submission is **flagged for human review** —
  the engine verdict is **`REVIEW`**, not `FAIL` — so a Label Specialist looks rather than the
  system bouncing it back. `REVIEW` is the engine's "not auto-decidable" band, distinct from the
  TTB **Needs Correction** disposition that only a human can choose. _Source:
  `database-schema.md` §3.2 (engine-verdict enum); discussion-points §1, §8 ("recommend, don't
  decide")._ The point of enhancement is to **avoid** a needless correction cycle; when the
  image truly can't be salvaged, a human decides — the system still does not auto-reject.

> **Net rule:** enhance to help OCR → if still unreadable, **flag REVIEW for a human**, never
> auto-reject and never fabricate.

---

## 5. LLM vs. open-source for enhancement — recommendation

**Recommendation: use local open-source OpenCV for image enhancement — not an LLM/cloud call.**

| Option | Verdict | Why |
|---|---|---|
| **OpenCV (local, open-source)** | **Recommended** | Deskew, perspective correction, glare/illumination normalization, CLAHE, denoise, binarization are **well-established, deterministic, fast, CPU-friendly** techniques that run **entirely on-prem** — **firewall-safe** (no outbound traffic), zero per-image API cost. Directly answers the brief's question "does it require an LLM, or can open-source do it?" → **open-source can.** _Source: domain research, Technical Trends; discussion-points §10 RESOLVED-direction._ |
| **Cloud LLM / VLM enhancement call** | **Rejected for the deployed path** | The TTB firewall blocks outbound cloud API calls (discussion-points §3). A cloud call to "clean up" an image would violate the no-outbound-calls constraint, add cost and latency, and is unnecessary — OpenCV handles the documented cases. |
| **Local VLM as a *read* (OCR) fallback** | **Optional, fallback only** | A **locally-hosted** small VLM (e.g. GLM-OCR / dots.ocr / Qwen3-VL class — domain research, "the firewall fork") may **read** a degraded image the classical OCR engines fail on. This is an **OCR fallback**, not an enhancement step, and is **local** so it stays firewall-safe. It is the brief's "LLM optional + fallback when OCR isn't producing good matches" (discussion-points §6). Kept **out of the request path by default**, toggleable. |
| **Provider VLM (read/extract + benchmark)** | **Allowed in the live pipeline — `models-internal-endpoint`** | Provider VLMs run field extraction and populate the benchmark comparison in the live pre-compute pipeline. Classified `models-internal-endpoint` (cloud API in the POC, internal endpoint in production; PRD NFR-2 / addendum A2), recorded in `llm_results`, and **toggleable off** — with the model layer off, the image path runs OCR-only and zero-egress. _Note: this is a **read/extract** step, never image **enhancement** — enhancement stays local OpenCV._ |

**Summary of the split:** **enhancement = local OpenCV (always, zero-egress);** **read = local OCR
first, optional local VLM fallback;** **provider VLM extraction + benchmarking = live pipeline,
classified `models-internal-endpoint` and toggleable off.** The enhancement path is always local;
the model layer follows the revised firewall posture — see
[`outbound-calls-inventory.md`](outbound-calls-inventory.md).

---

## 6. Open issues (TODO)

- **`TODO` (PNG):** decide whether to enable PNG as a POC modernization beyond the documented
  JPG/TIFF baseline; if so, add `image/png` to the `label_images.mime_type` set and convert to
  RGB on ingest.
- **`TODO` (CMYK):** add a CMYK→RGB conversion on ingest if any seeded fixture is CMYK (baseline
  is RGB).
- **`TODO` (artifact persistence):** persist enhanced/binarized image variants vs. regenerate on
  demand; tie to where OCR reads its input.
- **`TODO` (per-engine variant routing):** confirm which enhanced variant (binarized vs.
  grayscale/color) each OCR engine consumes, and record it per `ocr_results` row.
- **`TODO` (unpaper):** evaluate adding `unpaper` for scanned-sheet cleanup alongside OpenCV.
- **`TODO` (local VLM fallback):** select and wire a locally-hosted small VLM as the optional,
  toggleable OCR-fallback read; confirm it adds no outbound calls.
