---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - ref-docs/TTB-take-home-instructions.md
  - ref-docs/points-of-discussion.txt
  - ref-docs/Research-Findings.md
  - ref-docs/27 CFR Part 5.pdf
  - ref-docs/chapter4.pdf
  - ref-docs/colas_ol_oim_um.pdf
  - ref-docs/f510031.pdf
  - ref-docs/ds-labeling-checklist.pdf
workflowType: 'research'
lastStep: 5
research_type: 'domain'
research_topic: 'TTB COLA distilled spirits label compliance and review'
research_goals: 'Establish the authoritative regulatory, workflow, terminology, and quantitative domain foundation for an AI-assisted COLA Label Specialist proof-of-concept — distilled spirits primary (27 CFR Part 5 + Part 16 warning), noting where beer/wine differ.'
user_name: 'Diane'
date: '2026-06-11'
web_research_enabled: true
source_verification: true
---

# Research Report: domain

**Date:** 2026-06-11
**Author:** Diane
**Research Type:** domain

---

## Research Overview

This domain research establishes the authoritative regulatory, workflow, terminology, and
quantitative foundation for an AI-assisted TTB **Certificate of Label Approval (COLA)**
Label Specialist proof-of-concept. The primary beverage focus is **distilled spirits** (27 CFR
Part 5) plus the federal health warning (27 CFR Part 16), with notes on where malt beverage
(Part 7) and wine (Part 4) requirements diverge.

**Methodology:** Every load-bearing claim is verified against primary sources — the
eCFR, TTB.gov, and the applicant/CFR PDFs in `ref-docs/` — rather than model memory.
Critical facts (warning wording, COLA volumes, review dispositions) are
multi-source validated, and confidence levels are flagged where TTB practice is
ambiguous or unpublished.

---

## Domain Research Scope Confirmation

**Research Topic:** TTB COLA distilled spirits label compliance and review
**Research Goals:** Establish the authoritative regulatory, workflow, terminology, and
quantitative domain foundation for an AI-assisted COLA Label Specialist proof-of-concept.

**Domain Research Scope (tailored to a federal regulatory domain):**

- **Regulatory rules** — 27 CFR Part 5 mandatory distilled-spirits label info + 27 CFR
  Part 16 health warning; divergences for Part 7 (malt) and Part 4 (wine).
- **Label Specialist workflow & states** — queue/serve-next, dispositions (Approved / Needs
  Correction / Rejected), 30-day correction clock, allowable revisions.
- **Terminology & domain glossary** — COLA, TTB ID, applicant vs. Label Specialist,
  submission, class/type/fanciful name, Form 5100.31, the font-size disclaimer.
- **Volume & process facts** — ~150k applications/year, online vs. paper COLA counts
  (2024 / 2025 / 2026-to-date), review-time benchmarks for the 5-second argument.

**Research Methodology:**

- All claims verified against current primary public sources (eCFR, TTB.gov, `ref-docs/`).
- Multi-source validation for critical domain claims.
- Confidence-level framework for uncertain or unpublished information.
- Comprehensive domain coverage with regulatory-specific insights.

**Scope Confirmed:** 2026-06-11

---

<!-- Content will be appended sequentially through research workflow steps -->

## Domain Scale & Structure

*(This is the regulatory-domain analog of the template's "Industry Analysis." For a
federal process there is no market valuation or competitive rivalry — the meaningful
dimensions are workload scale, filing channels, the institutional players, and the
process throughput that frames the POC's performance argument.)*

### Workload Scale — how many labels, and who reviews them

- **~150,000 label applications/year**, reviewed by **~47 examiners** (down from 100+ in
  the 1980s). The COLA system has operated in essentially its current form since the
  online system launched in **2003**. _Source: stakeholder discovery (brief — Sarah Chen
  interview), [TTB-take-home-instructions.md](ref-docs/TTB-take-home-instructions.md).
  Confidence: HIGH for the POC's purposes; the 150k/47 figures are the brief's premises._
- Simple applications take **~5–10 minutes** of agent time; "half the day is essentially
  data-entry verification" (number-on-form vs. number-on-label matching) — the exact
  routine-matching workload an AI assist targets. _Source: brief (Sarah Chen, Jenny Park)._

### Filing Channels — online vs. paper (the volume question)

- **~90% of COLA applications are filed and processed electronically** through **COLAs
  Online**; the remainder are paper **Form 5100.31** submissions. This corroborates your
  thesis that online has overtaken paper. _Source:
  [TTB COLAs and Formulas Online FAQs](https://www.ttb.gov/faqs/colas-and-formulas-online-faqs),
  [COLAs Online Customer Page](https://www.ttb.gov/regulated-commodities/labeling/colas).
  Confidence: MEDIUM — "~90%" recurs across secondary sources; not yet pinned to an
  official annual figure._
- **Exact online-vs-paper counts for 2024 / 2025 / 2026-to-date are obtainable from TTB's
  Public COLA Registry search**, which lets you filter by filing method and year and
  returns exact result counts. The live search
  ([publicSearchColasBasic.do](https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do))
  is form-driven and resisted automated fetch in this session. **`[TODO — pull exact
  counts]`** — Diane offered to run these queries directly; recommend capturing the three
  years as a small table here. _Confidence: HIGH that the data exists and is publicly
  queryable; counts themselves pending._
- **Why online dominates / why it matters for the POC:** COLAs Online enforces business
  rules at submission (rejecting incomplete/invalid data up front) and issues an immediate
  **TTB ID** and receipt — so online submissions arrive cleaner and structured, which is
  exactly the structured-field input our Label Specialist POC assumes it can pull from the COLA
  database. _Source:
  [TTB COLAs and Formulas Online FAQs](https://www.ttb.gov/faqs/colas-and-formulas-online-faqs)._

### Process Throughput — the "5-second" performance frame

- **Current median label-processing times (2026):** distilled spirits **~2–6 days**
  (≈2 days reported March 2026, ≈6 days May 2026 — it fluctuates with submission volume);
  TTB **cut wine label approval to ~3 days** (reported May 2026). _Source:
  [TTB Processing Times for Label Applications](https://www.ttb.gov/regulated-commodities/labeling/processing-times),
  [Vinetur — TTB Cuts Wine Label Approval Time to 3 Days](https://www.vinetur.com/en/20260518100817/ttb-cuts-wine-label-approval-time-to-3-days.html)._
- **Customer-service goal: review 85% of label applications within 15 days.** _Source:
  [TTB Processing Times](https://www.ttb.gov/regulated-commodities/labeling/processing-times)._
- **Note the two distinct clocks:** the *end-to-end queue latency* (days, above) is the
  agency-wide backlog metric; the brief's **"5-second" requirement is per-label interaction
  latency** — how fast the screen loads and the assist appears once an agent opens a
  submission. Your pre-compute-OCR-in-the-background strategy targets the second clock and
  is unrelated to the multi-day queue figure. Worth stating explicitly so the POC's perf
  claim isn't confused with TTB's published turnaround. _Confidence: HIGH (definitional)._

### Institutional Players — the ecosystem map

| Actor | Role in the domain |
|---|---|
| **TTB — Alcohol Labeling & Formulation Division (ALFD)** | Owns the COLA review process; the ~47 examiners ("specialists") sit here. The POC builds *their* unbuilt reviewer workspace. |
| **Industry member / applicant** | Brewery, winery, distillery or importer who submits the COLA via COLAs Online (or paper). Signs the perjury certification. |
| **Label Specialist / specialist** | The federal examiner who reviews a submission and dispositions it (Approved / Needs Correction / Rejected). The POC's user. |
| **COLAs Online** | The applicant-facing electronic filing system (since 2003); captures images, signature, and structured fields into the COLA database. |
| **Public COLA Registry** | Free, no-login search of approved/expired/surrendered/revoked COLAs (1999–present), images visible ~48h post-approval — a real source of test fixtures. |
| **Third-party tools** | *Maker-side pre-screen:* COLA Clear, GetGen AI. *Registry search/data:* COLA Cloud, Sovos LabelVision. **None is a federal-reviewer review tool** — that gap is the POC's differentiator. _Source: [Research-Findings.md](ref-docs/Research-Findings.md) §9._ |

**Key structural insight:** the entire public-facing ecosystem (filing systems, pre-screen
SaaS, registry search) serves the *applicant* and the *public*. The **reviewer side is
undocumented and unbuilt in public** — confirmed in [Research-Findings.md](ref-docs/Research-Findings.md)
§5. The POC therefore isn't competing with existing software; it's designing the federal
Label Specialist's workspace that does not publicly exist, using the well-documented
applicant-side data model (Form 5100.31 fields) as its input. _Confidence: HIGH._

---

## Solution Landscape (Comparable Tools)

*(The regulatory-domain analog of the template's "Competitive Landscape." There is no
market-share contest — the POC is a non-commercial federal tool. The useful analysis is:
what label-compliance software already exists, who it serves, and where the gap is. This
section feeds `docs/presearch.md`.)*

### The three existing camps — and the empty fourth

| Camp | Who it serves | Examples | What it does |
|---|---|---|---|
| **Maker-side pre-screen** | Applicants, *before* submitting | **COLAClear**, **GetGen AI**, **Phantom Ales COLA Pre-Check** | Reads label artwork, checks against 27 CFR, returns pass/review/fix with citations |
| **Registry search / data** | Public, researchers | **COLA Cloud**, **Sovos ShipCompliant LabelVision** | Search already-approved COLAs; bulk datasets |
| **Official TTB job aids** | Applicants (TTB-published) | **Anatomy of a Distilled Spirits Label** tool, **Allowable Changes Sample Label Generator** | Educational/reference; authoritative TTB framing of label elements & allowable revisions |
| **Federal reviewer review workspace** | **Label Specialists** | **— none publicly exists —** | *The gap this POC fills* |

### Maker-side pre-screen tools (closest analogs to the POC's verification logic)

- **COLAClear** (`colaclear.com`) — *the closest analog to our rules engine.* Automated TTB
  pre-screen for wine & spirits; reads front/back artwork, cross-references the full text
  of **27 CFR Parts 4, 5, and 16**, and returns a structured **pass / review / fail** report
  "in seconds" with a regulation citation behind every flag. Public beta (May 2026) runs
  **34 checks** — class/type, alcohol content, standards of fill, the verbatim Government
  Warning, sulfites, grape variety, multi-varietal percentages, plus CA/OR/VA state rules.
  **Architecture worth noting:** explicitly *not* generic AI — **computer vision for text
  extraction + structured-LLM reasoning for ambiguous fields + a hand-coded rules engine
  grounded in live CFR text.** This validates the POC's hybrid approach (deterministic
  rules where possible, LLM only for ambiguity). Disclaims legal advice / approval
  guarantee — the same "recommend, don't decide" posture the POC adopts. _Source:
  [Wine Industry Advisor — COLAClear Public Beta](https://wineindustryadvisor.com/2026/05/04/colaclear-launches-public-beta-automated-ttb-label-pre-screen/),
  [colaclear.com](https://colaclear.com). Confidence: HIGH._
- **GetGen AI** (`getgen.ai/solutions/ttb-regulations-software`) — AI TTB compliance across
  beer/wine/spirits/specialty for marketing, packaging, and labels; auto-updates from TTB
  guidance. _Source: [Research-Findings.md](ref-docs/Research-Findings.md) §9._
- **Phantom Ales — TTB Label Compliance Checker / COLA Pre-Check** (`phantomales.com/cola/`)
  — a brewery-run AI label compliance checker for wine, beer & spirits that "catches TTB
  issues before submission." Smaller/independent; confirms even individual producers are
  building pre-screen tooling. _Source:
  [phantomales.com/cola](https://phantomales.com/cola/). Confidence: MEDIUM (vendor self-description)._

### Registry / search tools

- **COLA Cloud** (`colacloud.us`) — friendlier front-end over the Public COLA Registry;
  also publishes a Kaggle COLA dataset. Search/lookup, **not** compliance checking.
- **Sovos ShipCompliant — LabelVision** (`sovos.com/shipcompliant/products/labelvision`) —
  commercial COLA label search / beverage-alcohol compliance platform. _Source:
  [Research-Findings.md](ref-docs/Research-Findings.md) §9._

### Official TTB job aids (directly reusable references for the POC)

- **Anatomy of a Distilled Spirits Label** tool
  (`ttb.gov/.../distilled-spirits/ds-labeling-home/anatomy-of-a-distilled-spirits-label-tool`)
  — TTB's own authoritative breakdown of where each mandatory element sits on a spirits
  label. Excellent grounding for the POC's checklist UI and field map.
- **Allowable Changes Sample Label Generator**
  (`ttb.gov/regulated-commodities/labeling/allowable-revisions/...`) — TTB's official tool
  for which label changes *don't* require a new COLA. Maps directly to the "allowable
  revisions" domain concept the Label Specialist must know. _Source:
  [TTB Labeling Resources](https://www.ttb.gov/regulated-commodities/labeling/labeling-resources)._

### Note on names from the brief

The names **"LabelScreener"** and **"Label Score"** from `points-of-discussion.txt` did
**not** resolve to distinct, currently-live products in this search pass. The live
maker-side pre-screen field is best represented by **COLAClear, GetGen AI, and Phantom
Ales**. Recommend citing those (verifiable) rather than the half-remembered names.
_Confidence: MEDIUM — absence of search hits is not proof of non-existence; flag for Diane
to confirm if she has a source._

### The differentiation story (for presearch.md)

The market has solved **maker-side pre-screening** (COLAClear, GetGen, Phantom Ales) and
**registry search** (COLA Cloud, LabelVision), and TTB itself publishes **applicant job
aids**. **No one builds the federal reviewer's review workspace.** Two strategic
implications worth stating:

1. **Clean differentiation:** the POC occupies an unserved quadrant — the Label Specialist's
   side — so it isn't reinventing existing software.
2. **Rising submission quality (a tailwind to acknowledge):** as maker-side pre-screen
   tools proliferate, the *quality of incoming submissions should improve over time* —
   industry is "picking up the ball" on the pre-screening the government abandoned. The POC
   can lean on this: cleaner inputs make the reviewer-assist more reliable. _Confidence:
   MEDIUM (reasoned inference, not measured)._

---

## Regulatory Requirements — The Review Ruleset (Distilled Spirits)

**Primary source authority:** This section is grounded in TTB's *own* official
**"Checklist of Mandatory Label Information | Distilled Spirits"**
([ds-labeling-checklist.pdf](ref-docs/ds-labeling-checklist.pdf)) — the most
review-authoritative source available, because it is literally *"the mandatory
information that TTB reviews on every distilled spirits label and COLA application."*
Section numbers below reflect the **post-2022 modernization renumbering of 27 CFR Part 5**
and are confirmed against that checklist. The Government Warning text is from 27 CFR Part 16
(verified against the Cornell LII eCFR mirror, [Research-Findings.md](ref-docs/Research-Findings.md)
§2; the live eCFR at ecfr.gov bot-blocks automated fetch, so Cornell LII / the TTB checklist
are the working primary sources). _Confidence: HIGH._

### The "Same Field of Vision" rule (§ 5.63) — the structural keystone

Three elements **must appear together in the same field of vision**: **brand name +
alcohol content + class/type designation.** "Same field of vision" = a single side of the
container viewable without turning it; **for a cylindrical container, a side = 40% of the
circumference** (§ 5.63). The other mandatory items may appear on *any* label.

> **POC implication:** the verifier must reason about *spatial co-location*, not just
> presence. A label could contain all three elements but on different faces and still fail
> § 5.63. For the POC this is a known hard case — OCR gives text + bounding boxes per image,
> but "same side" inference across a multi-image submission is non-trivial. Recommend
> flagging field-of-vision as **checkable-where-determinable, else REVIEW** (a deterministic
> presence check plus an advisory note), rather than asserting a confident pass/fail.

### Always-mandatory elements (every distilled spirits label)

| Element | Citation | What the Label Specialist checks | POC check type |
|---|---|---|---|
| **Brand Name** | § 5.64 | Present; in same field of vision w/ ABV + class/type; **matches the "Brand Name" field on the application** | Field-match (app ↔ OCR) + presence |
| **Class/Type Designation** | § 5.141, § 5.165 | Present & in field of vision; consistent with a class/type in the regs (or trade/consumer designation, or fanciful name + statement of composition); separate & apart; spelled correctly; no conflicting designations across labels | Hybrid (rules + LLM for designation validity) |
| **Alcohol Content** | § 5.65 | Stated as % by volume in same field of vision; accepted formats "Alc.", "Alc", "Vol.", "Vol", "%"; **proof optional** but must be distinguished (e.g., parentheses/brackets) and in the same field of vision | Deterministic (format) + field-match |
| **Net Contents** | § 5.70, § 5.203 | Present on label or blown into container; accepted formats (e.g., 500 mL, 1.5 L); meets an **approved metric standard of fill** | Deterministic (standards-of-fill table) |
| **Name & Address** | § 5.66, § 5.67, § 5.68 | Present; immediately follows a qualifying phrase ("Bottled By", "Imported By", etc.) with no intervening text | Rules + field-match to permit |
| **Health Warning** | 27 CFR Part 16 | Exact wording & punctuation; "GOVERNMENT WARNING" caps + bold; "S" in Surgeon / "G" in General capitalized; one statement; separate & apart | **Deterministic (exact/regex)** |

### Conditional elements (mandatory only when triggered)

| Element | Citation | Trigger |
|---|---|---|
| **Country of Origin** | 19 CFR 134.11, § 5.69 | Imported spirits only (CBP-governed) |
| **Sulfite Declaration** | § 5.63(c)(7) | ≥ 10 ppm total SO₂ → "Contains Sulfites" |
| **Coloring Materials** | § 5.63(c)(6) | Certain colorings used → "Colored With…" / "Artificially Colored" |
| **FD&C Yellow #5** | § 5.63(c)(5) | If used → specific disclosure |
| **Cochineal / Carmine** | § 5.63(c)(6) | If used → specific disclosure |
| **Treatment with Wood** | § 5.73 | Whisky/brandy wood-treated other than via oak containers (with a brandy/oak-chip exception ≤2.5% vol) |
| **Commodity / Neutral Spirits Statement** | § 5.71 | Blended/rectified spirits w/ neutral spirits; gin/neutral spirits by continuous distillation |
| **State of Distillation** | § 5.66(f) | Certain U.S. whiskies not distilled in the state of the label's address |
| **Statement of Age** | § 5.74 | Whisky aged < 4 yrs; certain brandy aged < 2 yrs; any age reference / distillation date. Approved formats enumerated (e.g., "Aged not less than ___ years") |

### The Government Warning (27 CFR Part 16) — the one fully-deterministic check

**Exact mandated text (§ 16.21):**
> **GOVERNMENT WARNING:** (1) According to the Surgeon General, women should not drink
> alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption
> of alcoholic beverages impairs your ability to drive a car or operate machinery, and may
> cause health problems.

**Formatting rules:** "GOVERNMENT WARNING:" in **caps + bold** (the rest not bold); the "S"
in Surgeon and "G" in General capitalized; appears as **one statement, separate and apart**
from other text. **Type-size table (§ 16.22)** keyed to container volume: ≤237 mL → min 1 mm
(max 40 char/in); >237 mL–3 L → min 2 mm (max 25 char/in); >3 L → min 3 mm (max 12 char/in).

> **POC implication:** this is the single most rule-bound element and is **deterministic — no
> LLM needed.** Normalize whitespace/case for the body, but **enforce the caps+bold
> "GOVERNMENT WARNING:" token** and exact wording. This directly catches the "people get
> creative — smaller font, title case, reworded" abuse Jenny Park described. _Confidence: HIGH._

### Type-size / font compliance — the explicit non-goal

The regs give concrete **millimeter** minimums (spirits mandatory info ≥2 mm >200 mL / ≥1 mm
≤200 mL, § 5.53; warning 1/2/3 mm, § 16.22). **But absolute mm cannot be derived from a photo
without a physical scale reference** — and COLAs Online itself disclaims testing dimensions/
font size, placing that burden on the applicant's sworn certification. **Decision (matches
the brief and TTB's own posture): the POC does NOT verify font size.** Document it as a
deliberate, regulation-aligned limitation, optionally quoting TTB's own disclaimer verbatim.
_Source: [Research-Findings.md](ref-docs/Research-Findings.md) §3; brief decision. Confidence: HIGH._

### Cross-type divergence (beer / wine), for completeness

The single most important multi-type subtlety: **the ABV rule differs in all three.**
**Spirits — ABV always required** (§ 5.65). **Beer — usually optional** (§ 7.65, mandatory
only w/ added nonbeverage-flavor alcohol). **Wine — required only >14%** (or if not labeled
"table"/"light", § 4.36). A naive "ABV must always be present" rule would false-reject beer
and table wine. Net contents, name/address, and the Part 16 warning are common to all three;
class/type, standards of fill, and conditional disclosures diverge by part.
_Source: [Research-Findings.md](ref-docs/Research-Findings.md) §1. Confidence: HIGH._

### Data protection & privacy — applicability note

The template's GDPR/CCPA branch is **largely N/A by design.** COLA records are *public*
government data (the Public Registry exposes them), and the POC stores **no PII and no
sensitive data** (per Marcus Williams' guidance in the brief). The only real data-handling
consideration is **IP, not privacy**: label *artwork* is the brand owner's trademark/trade
dress — use registry images as **private test fixtures only**, synthetic labels for anything
public. _Source: brief (Marcus Williams); [Research-Findings.md](ref-docs/Research-Findings.md)
§8. Confidence: HIGH._

### Implementation considerations — deterministic vs. LLM

| Check class | Approach | Examples |
|---|---|---|
| **Fully deterministic** | String/regex + lookup tables; no LLM | Government Warning, ABV format, standards of fill, net-contents format |
| **Field-match (app ↔ OCR)** | Normalized string comparison w/ tolerance (cf. Dave's "STONE'S THROW" vs "Stone's Throw") | Brand name, ABV value, name/address |
| **Hybrid (rules + LLM-on-ambiguity)** | Rules first; LLM only for ambiguous designations / statements of composition | Class/type validity, conflicting designations |
| **Flag-as-REVIEW (not auto-decidable)** | Advisory note, defer to human | Same-field-of-vision spatial inference, font size, image-quality cases |

This mirrors COLAClear's validated architecture (CV + structured-LLM-for-ambiguity +
hand-coded CFR rules engine) and honors the brief's **"recommend, don't decide"** mandate:
the engine produces an advisory **PASS / REVIEW / FAIL** verdict per element; the human
Label Specialist still issues the disposition. _Confidence: HIGH._

### Risk assessment (regulatory)

- **False rejects** (engine says FAIL on a compliant label) are the costliest error — they
  create needless correction cycles. The cross-type ABV trap and over-strict field-matching
  (the "STONE'S THROW" case) are the main culprits → mitigate with tolerance + REVIEW band.
- **False approves** (engine says PASS on a non-compliant label) are mitigated by the
  human-in-the-loop: the engine never auto-approves; it advises.
- **Regulatory drift:** CFR text changes (e.g., the 2022 Part 5 rewrite). Mitigate by
  treating the rules engine's CFR citations as data, not hard-code, and noting the eCFR/TTB
  source dates. **The 2022 renumbering is already a live example** — any rule set citing the
  old Part 5 numbers would now be wrong.
- **Scope honesty:** font/dimension compliance is explicitly out of scope; documenting this
  (as TTB itself does) prevents over-claiming. _Confidence: HIGH._

---

## Technical Trends and Innovation (OCR / Vision-LLM / Image Stack)

*Scope note: the relevant "technology trends" for this domain are the text-extraction and
image-cleanup technologies the POC will benchmark — not general industry digital
transformation. All findings below are filtered through the brief's hard constraint:
**no outbound cloud API calls** (the TTB firewall blocks them), so the deployed POC must run
on **local, self-hosted** engines, with cloud models used only as toggleable benchmark
comparators.*

### Emerging Technologies — the OCR engine landscape

**PaddleOCR vs. Tesseract (your two chosen engines) — the data validates running both:**

- **Accuracy:** On clean printed labels both are strong (Tesseract ~95–99% on high-quality
  scans). The gap opens on *degraded* images — exactly the glare/angle cases Jenny Park
  described: PaddleOCR ~88.7% vs Tesseract ~52.1% on curved text; ~91.5% vs ~84.3% on noisy
  scans. One 2025 study reported F1 0.938 (PaddleOCR) vs 0.797 (Tesseract).
- **Speed/footprint:** Tesseract wins CPU-only (≈0.77 s/doc, ~10 MB binary, runs on a Pi);
  PaddleOCR is far faster *with a GPU* (~120 pages/min on an RTX 3090) and uniquely ships
  built-in layout/table analysis.
- **Takeaway:** these two engines have **complementary strengths** (Tesseract = light/clean,
  PaddleOCR = accurate/complex) — which is precisely why a multi-OCR benchmark is the right
  call rather than picking one blind. **PP-OCRv5** (a 5M-param specialized model) reportedly
  rivals billion-param VLMs on OCR while staying local-friendly — a strong candidate to add.
  _Source: [CodeSOTA — PaddleOCR vs Tesseract vs EasyOCR](https://www.codesota.com/ocr/paddleocr-vs-tesseract),
  [IJRPR comparative study (PDF)](https://ijrpr.com/uploads/V6ISSUE10/IJRPR53627.pdf),
  [arXiv PP-OCRv5](https://arxiv.org/pdf/2603.24373). Confidence: MEDIUM-HIGH (multiple
  secondary benchmarks agree on the directional finding; absolute numbers vary by dataset)._

### Digital Transformation — the rise of Vision-Language Models (VLMs)

The biggest 2026 shift in document AI: **VLMs now lead text extraction on hard documents**,
with reported **3–4× lower character error rate** than classical engines on noisy/distorted
inputs — while classical OCR stays **fastest and cheapest on clean print**. "Nothing wins on
every scenario" is the consensus. Early-2026 OCR leaderboards cite frontier models
(Gemini-class, Claude Opus-class, GPT-class) and a notably efficient open model, **GLM-OCR
(~0.9B params)**, scoring ~94.6 on OmniDocBench V1.5 — beating much larger models. Capable
**open-source** options (dots.ocr ~1.7B, Qwen3-VL 2B–235B) run locally at near-zero inference
cost. _Source:
[The Definitive Guide to OCR in 2026 (VLMs)](https://slavadubrov.github.io/blog/2026/03/04/the-definitive-guide-to-ocr-in-2026-from-pipelines-to-vlms/),
[ofox.ai — Best LLM for OCR 2026](https://ofox.ai/blog/best-ai-model-for-ocr-2026/),
[OmniAI — Benchmarking open-source OCR](https://getomni.ai/blog/benchmarking-open-source-models-for-ocr).
Confidence: MEDIUM — fast-moving leaderboards, vendor-adjacent sources; treat specific scores
as indicative, not authoritative._

> **The firewall fork (decisive for the POC):** frontier VLMs are **cloud-hosted → blocked by
> the TTB firewall**. So the architecture splits cleanly: **(a) deployed path** = local OCR
> (Tesseract + PaddleOCR/PP-OCRv5) and, optionally, a **locally-hosted** small VLM as the
> LLM-fallback; **(b) benchmark path** = cloud VLMs (Gemini/Claude/GPT) run *only* in an
> offline evaluation harness to generate the comparison stats the brief wants — never in the
> live request path. This is exactly why Diane's "LLM optional + easy to turn off" and
> "LangChain only for stats, then disable" design is correct, and it must be stated explicitly
> in the docs. _Confidence: HIGH (follows directly from the brief's constraint)._

### Innovation Patterns — image enhancement without a re-submit

Jenny Park's wish ("fix glare/angle without bouncing it back to the submitter") is solvable
with **open-source, local, non-LLM** preprocessing — no cloud call required:

- **OpenCV (cv2):** grayscale, adaptive thresholding/binarization, denoising, contrast
  (CLAHE), **deskew** (detect skew angle → rotate), perspective correction for off-angle
  shots, and glare/uneven-lighting mitigation. **unpaper** complements it for scanned sheets.
- These run as a cheap preprocessing stage *before* OCR and measurably lift accuracy on the
  exact "imperfect image" cases the brief calls out — and they keep everything **on-prem**.
  _Source:
  [NextGenInvent — 7 steps of image pre-processing for OCR](https://nextgeninvent.com/blogs/7-steps-of-image-pre-processing-to-improve-ocr-using-python-2/),
  [Technovators — Survey on image preprocessing for OCR](https://medium.com/technovators/survey-on-image-preprocessing-techniques-to-improve-ocr-accuracy-616ddb931b76).
  Confidence: HIGH (well-established techniques)._

### Future Outlook

- **Convergence on hybrid pipelines:** classical OCR for the cheap/clean 90%, a small local
  VLM fallback for the degraded long tail — the industry's emerging default, and a natural
  fit for the POC's "LLM-as-fallback when OCR confidence is low" design.
- **Shrinking local models:** sub-1B OCR models matching frontier accuracy mean the
  "local-only, firewall-safe" path keeps getting *more* capable over the POC's lifetime — a
  good forward-looking note for the procurement-informing goal.
- **Benchmarking is now table stakes:** OmniDocBench-style leaderboards normalize exactly the
  "collect speed + accuracy stats across engines/models" approach the POC institutionalizes.
  _Confidence: MEDIUM (directional projection)._

### Implementation Opportunities (for the POC)

- **Multi-OCR microservice** (Diane's idea): wrap each engine behind a uniform interface,
  run Tesseract + PaddleOCR (+ PP-OCRv5) per image in parallel background jobs, capture
  **per-engine latency + extracted text + confidence** → the procurement-grade comparison.
- **Pre-compute pipeline:** OCR + analysis run on submission (background), so "Next
  Submission" loads instantly — targeting the per-label *interaction* latency, the right
  clock (see Domain Scale & Structure). This is the structural answer to the abandoned
  5-minute pilot.
- **LangChain for tracing only:** capture model name/ID, full model ID, timestamps,
  latencies into the DB; **local/offline tracing, no telemetry egress**, toggleable off so it
  never touches the firewall. _Confidence: HIGH._

### Challenges and Risks (technical)

- **Pixel→mm scale** unknown without a reference ⇒ font-size checks stay out of scope (see
  Regulatory §). **GPU availability** on government infra is uncertain ⇒ don't assume
  PaddleOCR's GPU throughput; benchmark CPU-mode too. **VLM nondeterminism** ⇒ keep the
  Government Warning and other rule-bound checks deterministic; use the LLM only as advisory
  fallback. **Leaderboard volatility / vendor-adjacent sources** ⇒ treat 2026 model scores as
  indicative. _Confidence: HIGH._

---

## Recommendations

### Technology Adoption Strategy

1. **Deployed runtime = 100% local.** Tesseract + PaddleOCR (consider PP-OCRv5) for OCR; if
   an LLM fallback is enabled in the live path, it must be a **locally-hosted** small VLM.
   **No cloud calls in the request path** — document the full outbound-call inventory to prove
   it (Diane's "list all outbound calls" ask).
2. **Cloud VLMs = benchmark harness only.** Run Gemini/Claude/GPT-class models in an offline
   evaluation to produce the accuracy/speed/cost comparison the brief wants — clearly walled
   off from the deployed app and toggleable.
3. **Keep rule-bound checks deterministic** (Government Warning, ABV format, standards of
   fill); reserve LLM/VLM for ambiguity and image-degradation fallback.

### Innovation Roadmap

- **Phase 1 (POC):** local multi-OCR + OpenCV preprocessing + deterministic rules engine +
  optional local LLM fallback; background pre-compute; LangChain local tracing; benchmark
  harness for cloud-VLM comparison stats.
- **Phase 2:** API definition + integration hooks toward COLA; expand benchmark coverage;
  promote the best-performing local model based on collected stats.

### Cost Analysis (framing for the brief's "per 1,000 verifications")

- **Local OCR path:** marginal cost ≈ **compute only** (effectively ~$0 per verification at
  the API level — no token charges); the real cost is one-time/standing infra (CPU/optional
  GPU). This is itself a strong procurement finding: the firewall-safe local path is also the
  cheapest at scale.
- **Cloud-VLM comparator:** cost scales with image token count per label × model price; the
  benchmark harness should record tokens + price-per-model so a true **$/1,000 verifications**
  figure falls out of the data. Capture model name, full model ID, tokens, and latency per
  call to make this computable. _Confidence: HIGH on the structure; actual numbers pending the
  benchmark run._

### Risk Mitigation

- Tolerance bands + a REVIEW verdict to curb false rejects (cross-type ABV, "STONE'S THROW").
- Human-in-the-loop never auto-approves — engine advises, Label Specialist decides.
- CFR citations stored as data (the 2022 Part 5 renumbering shows why); source dates recorded.
- Benchmark in CPU mode too, in case government infra lacks a GPU.
