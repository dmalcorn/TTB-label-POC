# Research Findings — First Pass

*Answers to the **[RESEARCH]** items in `Requirements-Questions.md`. Section
numbers in parentheses (e.g., "→ §1") refer back to that document.*

**Sources used (all local — no outbound calls):**
- `27 CFR Part 4 (...).pdf` — wine
- `27 CFR Part 5 (...).pdf` — distilled spirits
- `27 CFR Part 7 (...).pdf` — malt beverages / beer
- `wine-labeling-checklist.pdf` — TTB G 2019-12 checklist
- `docs/f510031.pdf` — TTB Form 5100.31
- `colas_ol_oim_um.pdf` — COLAs Online Industry Member user manual (v3.11.3)
- `TTB current screens/` — prepare-images, upload-label-images, verify-application

**Note on Part 16:** **27 CFR Part 16** (the Government Warning's exact wording
and type-size table) is **not** in the downloaded set — the three CFR parts only
*cross-reference* it. Section 2 below was verified against the Cornell LII mirror
of the eCFR (`law.cornell.edu/cfr/text/27/16.21` and `/16.22`) on 2026-06-09.
Recommended: download Part 16 into the repo alongside Parts 4/5/7 for a complete
local rule set.

---

## 1. TTB Mandatory Label Requirements, by Beverage Type (→ §5)

The CFR organizes each beverage type the same way: a master "what must appear"
section, then per-element sections. Citations are to the relevant Part.

| Element | Beer (Part 7) | Wine (Part 4) | Spirits (Part 5) |
|---|---|---|---|
| **Brand name** | Required § 7.64 | Required § 4.33 | Required § 5.64 |
| **Class/type designation** | Required § 7.63(a)(2), Subpart I | Required § 4.34 (table/dessert exempt from designating) | Required § 5.141 |
| **Alcohol content (ABV)** | **Optional** unless nonbeverage-flavor alcohol present § 7.65 | **Required if >14%**; optional ≤14% if labeled "table"/"light" wine § 4.36 | **Always required** § 5.65 (proof optional) |
| **Net contents** | Required § 7.70 | Required § 4.37 | Required § 5.70 |
| **Name & address** | Required §§ 7.66–7.68 | Required § 4.35 | Required §§ 5.66–5.68 |
| **Country of origin (imports)** | Per CBP 19 CFR 102/134 (§ 7.69) | Per CBP 19 CFR 102/134 (§ 4.35(e)) | Per CBP 19 CFR 102/134 (§ 5.69) |
| **Government Warning** | Required (≥0.5% ABV) → 27 CFR Part 16 | Required → Part 16 | Required → Part 16 |
| **Sulfite declaration** | If ≥10 ppm § 7.63(b)(3) | If ≥10 ppm § 4.32(e) | If ≥10 ppm § 5.63(c)(7) |

**The single most important cross-type subtlety for the verifier:** the ABV rule
is **different in all three**. Beer: usually optional. Wine: required only above
14% (or if not labeled "table"/"light"). Spirits: always required, and must be
ABV (proof alone is not sufficient; proof is an optional *addition*). A naive
"ABV must always be present" check would produce false rejections on beer and
table wine.

### Per-type specifics worth modeling

**Beer / malt beverages (Part 7)**
- ABV mandatory only when alcohol comes from added nonbeverage flavors other than
  hops extract (§ 7.63(a)(3)); otherwise optional. Tolerance ±0.3 pts (§ 7.65(c)).
- Conditional ingredient disclosures: FD&C Yellow No. 5, cochineal/carmine,
  sulfites ≥10 ppm, aspartame ("PHENYLKETONURICS: CONTAINS PHENYLALANINE", all
  caps) — § 7.63(b).
- No mandatory standards of fill.

**Wine (Part 4)** — applies to wine 7%–24% ABV (§ 4.6)
- ABV required if >14%; optional ≤14% only if "table"/"light" appears (§ 4.36).
  Tolerances: ±1% (>14%), ±1.5% (≤14%).
- **Appellation of origin** becomes mandatory when triggered by a varietal,
  vintage, semi-generic type, etc. (§ 4.34(b)). Varietal ≥75% (§ 4.23); vintage
  ≥95% AVA / ≥85% non-AVA (§ 4.27); AVA appellation ≥85% (§ 4.25).
- 25 authorized standards of fill, incl. 750 mL (§ 4.72).
- Sulfite declaration at ≥10 ppm (§ 4.32(e)).

**Distilled spirits (Part 5)** — most relevant to the brief's sample label
- Three items must share **the same field of vision**: brand name, class/type,
  ABV (§ 5.63(a)). Name/address and net contents may go anywhere (§ 5.63(b)).
- ABV always required; proof optional and, if used, must be in the same field of
  vision (§ 5.65). Tolerance ±0.3 pts.
- "Kentucky Straight Bourbon Whiskey" is a valid type; "Kentucky" also satisfies
  the **state-of-distillation** requirement for whisky (§ 5.66(f)).
- 750 mL is an authorized standard of fill (§ 5.203).
- Conditional: neutral-spirits/commodity statement, coloring, wood treatment, age
  statement (mandatory if whisky aged <4 yrs and not bottled-in-bond) — §§ 5.71–5.74.

**Assessment of the brief's sample label** ("OLD TOM DISTILLERY" / "Kentucky
Straight Bourbon Whiskey" / "45% Alc./Vol. (90 Proof)" / "750 mL"): it shows
brand, class/type, ABV (+optional proof), and net contents — but is **missing
the two other mandatory elements**: the **name-and-address statement** (§ 5.66)
and the **Government Warning** (Part 16). Good news for the prototype: this means
the provided sample is itself a "fail" case, useful as a test fixture.

---

## 2. The Government Warning Statement (→ §5)

**This is the single most rule-bound check, and it's deterministic — no LLM
needed.** This directly answers your §5 question (LLM vs. script): a string/regex
comparison is the correct approach.

**Exact mandated text (27 CFR § 16.21 — VERIFIED against Cornell LII eCFR
mirror, 2026-06-09):**

> **GOVERNMENT WARNING:** (1) According to the Surgeon General, women should not
> drink alcoholic beverages during pregnancy because of the risk of birth
> defects. (2) Consumption of alcoholic beverages impairs your ability to drive a
> car or operate machinery, and may cause health problems.

Formatting rules the agents confirmed from the CFR cross-references + the wine
checklist:
- "**GOVERNMENT WARNING**" must be in **capital letters and bold**; the rest is
  not bold.
- Must appear as **one statement**, **separate and apart** from other text.
- The "S" in Surgeon and "G" in General are capitalized (per the checklist).

**Type-size table (27 CFR § 16.22 — VERIFIED):** keyed to container volume —
- ≤ 237 mL (8 fl oz): min **1 mm**, max 40 characters/inch
- > 237 mL to 3 L: min **2 mm**, max 25 characters/inch
- > 3 L: min **3 mm**, max 12 characters/inch

**Recommendation:** treat the warning as exact-match (normalize whitespace/case
for the body, but enforce the all-caps/bold "GOVERNMENT WARNING:" token). This is
exactly the kind of "people get creative — smaller font, title case, reworded"
abuse Jenny Park described, and a deterministic check catches it reliably.

---

## 3. Font / Type-Size Compliance — feasibility (→ §5 font question)

The regs give concrete **millimeter** thresholds, which makes this *measurable*
from an image **if** you know the physical scale:

- **Beer** (§ 7.53): mandatory info ≥ 2 mm ( >½ pint) or ≥ 1 mm (≤½ pint).
- **Wine** (§ 4.38): ≥ 2 mm ( >187 mL) or ≥ 1 mm (≤187 mL); ABV statement 1–3 mm.
- **Spirits** (§ 5.53): ≥ 2 mm ( >200 mL) or ≥ 1 mm (≤200 mL).
- **Warning** (§ 16.22): 1/2/3 mm by container size (above).

**The hard part is the pixels→mm conversion.** You can't get absolute mm from a
photo without a scale reference. Practical options for the prototype:
1. Use the **label dimensions** COLAs Online already collects at upload (width ×
   height in inches — see §6) as the scale reference → pixels-per-inch → mm.
2. Measure character height in pixels (OCR bounding boxes give this for free).
3. Flag as "cannot verify type size — physical dimensions unknown" when no scale
   is available, rather than guessing.

This is worth writing up as a **known limitation** in the docs: type-size
compliance is *conditionally* checkable, dependent on a reliable scale reference.

---

## 4. Multiple Labels on One Container / European Wine (→ §5 multi-label question)

**Confirmed: yes, the regulation explicitly contemplates multiple labels**, and
your European-wine intuition is essentially correct — mandatory U.S. items can be
distributed across several physical labels (front/brand, back, strip, neck).

From **wine § 4.32** (the clearest example):
- **Must be on the brand label:** brand name, class/type designation, foreign-wine
  percentage. ("Brand label" = "the label carrying, in the usual distinctive
  design, the brand name" — § 4.10. **Any** label can serve as the brand label if
  it carries these items.)
- **May be on *any* affixed label:** name/address, net contents, ABV (§ 4.32(b)).
- Sulfites, cochineal/carmine, FD&C Yellow No. 5: front, back, strip, or neck
  label (§ 4.32(c)–(e)).

So a European wine can keep its origin-country front label and add a U.S.
"compliance" back/strip label carrying the warning, sulfites, importer
name/address, and net contents. **Implication for the prototype:** the verifier
must accept a **set of images per application** and check the mandatory elements
across the *union* of all labels, not demand every element on one image. COLAs
Online already supports this: up to 10 images, each tagged brand/neck/back/etc.
(see §6).

---

## 5. The COLA System & Form 5100.31 (→ §1)

**Form 5100.31** = "Application for and Certification/Exemption of Label/Bottle
Approval" (TTB F 5100.31, OMB 1513-0020). It IS the label application. Three
parts: Part I applicant data, Part II applicant certification (perjury
signature), Part III TTB certificate (filled on issuance).

**Answer to "what is created after the session?" (→ §1):** **Both.** COLAs Online
creates a **database record** (the "eApplication", assigned a **TTB ID** on
submission) that **can be rendered/printed as a populated Form 5100.31** at any
time. They're two representations of the same submission. So it's not "form OR
database" — it's a database record with a form view.

**Answer to "what does the reviewing agent see?" (→ §1, §9):** **Unknown from
these documents — and this is an important finding.** All five local files are
the **industry-member (submitter) side**. The manual only says ALFD personnel
"process the applications electronically and provide notification of approval,
rejection, or needing correction." **The TTB-specialist/reviewer interface, the
queue, and how a reviewer pulls the "next" application are NOT documented
anywhere in the provided sources.** Your §9 question ("how does an agent get to
the first screen / how are applications queued") has no published answer here —
so for the prototype, **we get to design it**, and should say so explicitly. The
"ASSIGNED" status implies applications are assigned to specialists, but no
mechanics are given.

This actually clarifies the §2 scope question: the prototype is building the
**reviewer-side experience that doesn't publicly exist**, using the submitter-side
data model (Form 5100.31 fields) as its input.

**Fields on Form 5100.31 relevant to label matching:** Brand Name (Box 6),
Fanciful Name (7), Name/Address incl. DBA (8), Product type (5), Grape Varietal
(10), Wine Appellation (11); the e-filed view adds explicit **Net Contents**,
**Alcohol Content**, and **Wine Vintage** fields. These are exactly the fields an
agent matches against the label artwork.

---

## 6. Image Types & Upload Mechanics (→ §6 image types, upload UX)

Directly from the COLAs Online screens — this answers your "what image types?"
and "how does upload work?" questions with the **real government baseline**:

- **Accepted formats:** **JPG/JPEG/JPE and TIFF/TIF only.** (RGB color mode, not
  CMYK.)
- **File size:** each file **≤ 750 KB**; **up to 10 files** per application.
- **Quality:** compression set to medium (7/10); TIFFs not saved with JPG
  compression; white space / printer's proof cropped out.
- **Photographing:** actual print size; reduce to ≤ 8.5×11"; **one label per
  image**; each upload tagged with a type (brand, neck, back, etc.).
- **Upload UX:** **Browse + Attach** file-picker, one file at a time, then Done.
  **No drag-and-drop** in the current system. Multiple images supported (up to
  10). Post-upload, the user clicks the image to confirm it's clear/readable.

**Design note:** the current system is deliberately modest (browse-only, 750 KB
cap, JPG/TIFF). Your wishlist (drag-and-drop, multi-select, batch — §6) is a
genuine **improvement over the baseline**, which is a good story to tell. But
matching the accepted formats (JPG/TIFF, and probably PNG for modern uploads) and
the "tag each image by label type" pattern keeps us aligned with TTB conventions.

---

## 7. Review Terminology & Dispositions (→ §9 pass/fail/correction)

This answers your §9 question about the right vocabulary. **TTB's actual terms:**

| Status | Meaning | What happens next |
|---|---|---|
| **RECEIVED** | Submitted, awaiting/under review | Can be withdrawn by submitter |
| **ASSIGNED** | Assigned to a specialist | — |
| **APPROVED** | COLA issued | Printable COLA; can later be surrendered |
| **NEEDS CORRECTION** | Returned to fix specified issues | Submitter has **30 days** to correct & resend; else auto-rejected |
| **REJECTED** | Terminal denial | Submitter must file a **new** resubmission (refs prior TTB ID) |
| **WITHDRAWN** | Pulled by submitter while Received | Confirmation issued |
| **SURRENDERED** | Approved COLA voluntarily relinquished | Confirmation issued |

**So, to your specific question:** the correct term is **"Needs Correction"** (not
"Returned for Correction", which the system doesn't use literally). The key
distinction: **Needs Correction** is fixable in place (original preserved, 30-day
clock), while **Rejected** is terminal (requires a fresh application). The word
**"review"** is used informally ("under review") but is **not** a formal
disposition. For the prototype I'd recommend mirroring TTB's real states —
Approved / Needs Correction / Rejected — rather than inventing "Pass/Fail",
because it matches what agents already know.

---

## 8. Public COLA Registry as an Image Source (→ §13)

**Yes — it's a viable source of real, approved label images.** Verified
2026-06-09.

- **Public search, no login:** the Public COLA Registry is searchable at
  `https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do` with no
  registration or password (per TTB's
  `ttb.gov/regulated-commodities/labeling/cola-public-registry`).
- **It returns label images:** electronically-approved and paper label images are
  viewable/printable for COLAs from **1999 to present**, generally available ~48
  hours after approval. You can search by beverage type, brand, class/type,
  origin, date, etc. — useful for pulling a realistic mix of beer/wine/spirits.
- **Bulk option:** there's a **data.gov** "TTB Public COLA Registry Search and
  Download" dataset, and a Kaggle **"ttb-colas-demo"** dataset (published by
  COLA Cloud) — handy if we want a batch of records without scraping.

**Caveat to document (IP, not access):** the *records* are public government data,
but the **label artwork itself is the brand owner's trademark/trade dress**. For a
prototype that's fine to use a handful as **internal test fixtures**, but we
should **not redistribute** brand artwork in the public repo or deployed demo.
Safer for the public deliverable: AI-generated / synthetic labels (which the
brief explicitly encourages) for anything shown publicly, and registry images for
private local testing only. Worth a line in the Assumptions/Limitations doc.

---

## 9. Comparable Software, for `presearch.md` (→ §14)

Verified 2026-06-09. The key framing you wanted holds up: **none of these is a
federal-reviewer review tool.** They split into two camps — *maker
pre-screen* tools and *registry search/data* tools — and our prototype (the
**reviewer** side) occupies a gap none of them fill.

**Maker-facing pre-screen tools** (catch errors *before* submitting to TTB):
- **COLA Clear** — `colaclear.com`. Automated TTB label pre-screen for wine &
  spirits; reads front/back artwork, cross-references 27 CFR Parts 4/5/16, returns
  a color-coded **pass / review / fix** report with rule citations. Public beta
  (~34 checks incl. health warning, ABV format, standards of fill, sulfites,
  grape variety, plus CA/OR/VA state rules). Stack: computer vision + structured
  LLM reasoning + a hand-coded rules engine on live CFR text. *Closest analog to
  our verification logic — but aimed at producers, not agents.*
- **GetGen AI** — `getgen.ai/solutions/ttb-regulations-software`. AI-powered TTB
  compliance for marketing, packaging, and labels across beer/wine/spirits/
  specialty; auto-updates from TTB guidance and COLA requirements.

**Registry search / data tools** (search *already-approved* COLAs):
- **COLA Cloud** — `colacloud.us`. A friendlier front-end over TTB's Public COLA
  Registry search; also publishes the Kaggle COLA dataset. *Search/lookup, not
  compliance checking.*
- **Sovos ShipCompliant — LabelVision** —
  `sovos.com/shipcompliant/products/labelvision`. Commercial TTB COLA label search
  / beverage-alcohol compliance platform. (Note: a separate tool also called
  "LabelVision" is discussed at `winelawonreserve.com` — verify which is meant
  before citing.)

**The takeaway line for `presearch.md`:** the market has solved *maker-side
pre-screening* (COLA Clear, GetGen) and *registry search* (COLA Cloud,
LabelVision), but **no one is building the federal reviewer's review
workspace** — which is exactly what this prototype targets. That's a clean
differentiation story, and it shows we surveyed the landscape.

---

## Remaining (optional, low-priority)

- **(→ §2) Characterize the live public COLA site from both viewpoints** — the
  *submitter* view is well-covered by the local manual/screens (§§5–7 above); the
  *public registry* view is covered in §8. The internal *reviewer* view isn't
  publicly documented (confirmed in §5), so "both viewpoints" for `presearch.md`
  realistically means **submitter + public-registry**, with the reviewer view
  noted as a design gap we're filling.
- **Download 27 CFR Part 16 into the repo** — Section 2 is verified online; adding
  the PDF locally would complete the offline rule set (Parts 4/5/7 + 16).
