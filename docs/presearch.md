# Pre-Search & Landscape — TTB COLA Label Specialist POC

*A pre-search/landscape document for the AI-assisted TTB Certificate of Label
Approval (COLA) **Label Specialist** proof-of-concept. It catalogs the reference
materials, surveys comparable software (and the gap the POC fills), inventories
test-data sources, summarizes the most common distilled-spirits label errors, and
documents the online-vs-paper application split.*

**Beverage focus:** distilled spirits (27 CFR Part 5 + the Part 16 health warning),
with notes where beer (Part 7) and wine (Part 4) diverge.
**Author:** Diane · **Date:** 2026-06-11

**Sourcing convention:** every external claim is a markdown link to its source URL;
local files are linked by relative path. Where a claim is **extrapolated** (reasoned
from a related but not spirits-specific source) it is labeled as such.

**Related docs:** [tools-used.md](tools-used.md) *(inventory of tools, OCR
engines, and the verified-vs-unverified search trail behind this document)* ·
[assumptions.md](assumptions.md) *(records the IP/test-fixture caveat, the
online-vs-paper "~90%" assumption, and the reviewer-side design gap)*. Both are the
companion deliverables this document cross-links.

---

## 1. Reference Documents

The catalog below is the ground-truth material this POC is built on. Files live in
[`ref-docs/`](../ref-docs/) unless noted; research outputs live under
[`_bmad-output/`](../_bmad-output/) and [`docs/`](.).

### Regulatory primary sources (the review ruleset)

The offline regulatory rule set is now **complete** — all four CFR parts and all three TTB
labeling checklists are in `ref-docs/`.

**CFR text (the underlying regulations):**

| Document | What it is | Used for |
|---|---|---|
| [`ref-docs/27 CFR Part 5.pdf`](../ref-docs/27%20CFR%20Part%205.pdf) | 27 CFR **Part 5** — distilled-spirits labeling (post-2022 renumbering) | Spirits ruleset: brand §5.64, class/type §5.141/§5.165, ABV §5.65, net contents §5.70/§5.203, name & address §§5.66–5.68, same-field-of-vision §5.63, conditional disclosures §§5.71–5.74. |
| [`ref-docs/27 CFR Part 4.pdf`](../ref-docs/27%20CFR%20Part%204.pdf) | 27 CFR **Part 4** — wine labeling (not renumbered; 2022 rewrite deferred) | Wine ruleset: brand §4.33, class/type §4.34, ABV §4.36 (>14% rule), net contents §4.37, name & address §4.35, appellation §4.34(b)/§4.25–4.27, standards of fill §4.72, sulfites §4.32(e). |
| [`ref-docs/27 CFR Part 7.pdf`](../ref-docs/27%20CFR%20Part%207.pdf) | 27 CFR **Part 7** — malt-beverage/beer labeling (post-2022 renumbering) | Beer ruleset: brand §7.64, class/type §7.63(a)(2) + Subpart I (§§7.141–7.147), ABV §7.65 (usually optional), net contents §7.70, name & address §§7.66–7.68, disclosures §7.63(b). |
| [`ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf) | 27 CFR **Part 16** — the health warning | The Government Warning's exact wording (§16.21) and type-size table (§16.22) — the single fully-deterministic check; applies to all beverages ≥0.5% ABV (§16.10). *(Now local — verified line-by-line against this PDF.)* |
| [`ref-docs/chapter4.pdf`](../ref-docs/chapter4.pdf) | TTB **Beverage Alcohol Manual (BAM), Chapter 4 — Class & Type Designation** (04/2007), distilled spirits | The **enumerated catalog of every spirits class and type** (whisky/bourbon/rye, gin, brandy, rum, tequila, the full liqueur list, recognized cocktails, specialties) with the "sufficient as a class and type designation" flags. The lookup source for the **class/type-validity check** — an "allowed designations" table can be seeded from it. *(Despite the name, this is a **spirits** reference, not wine. **2007 vintage** — predates the 2022 Part 5 modernization and newer standards such as American Single Malt Whisky; cross-check against current Part 5 Subpart I.)* |

**TTB labeling checklists (the "what TTB reviews" authority — most review-relevant):**

| Document | What it is | Used for |
|---|---|---|
| [`ref-docs/ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf) | TTB **"Checklist of Mandatory Label Information — Distilled Spirits"** | The primary spirits review authority — "the mandatory information TTB reviews on every distilled spirits label and COLA application." Drives the rules engine and on-screen checklist. |
| [`ref-docs/wine-labeling-checklist.pdf`](../ref-docs/wine-labeling-checklist.pdf) | TTB **"Checklist of Mandatory Label Information — Wine"** (TTB G 2019-12) | The primary **wine** review authority; cross-checked against [`regulatory-rules-wine.md`](regulatory-rules-wine.md) (added §4.21 standards of identity, estate-bottled §4.26, formula, sulfite phrasing). |
| [`ref-docs/malt-beverage-labeling-checklist.pdf`](../ref-docs/malt-beverage-labeling-checklist.pdf) | TTB **"Checklist of Mandatory Label Information — Malt Beverages"** | The primary **beer** review authority; cross-checked against [`regulatory-rules-beer.md`](regulatory-rules-beer.md) (added ABW handling, state-law ABV trigger, formula, U.S.-customary net contents). |

> All three beverage types now have their own check-by-check review ruleset (the
> `regulatory-rules-*` docs), each grounded in **both** its TTB checklist **and** the
> verified CFR text above; distilled spirits is the most fully worked example. The
> cross-type summary lives in
> [`docs/label-requirements-by-type.md`](label-requirements-by-type.md).

### Application & system documents (the data model and applicant workflow)

| Document | What it is | Used for |
|---|---|---|
| [`ref-docs/f510031.pdf`](../ref-docs/f510031.pdf) | **TTB Form 5100.31** — "Application for and Certification/Exemption of Label/Bottle Approval" (OMB 1513-0020) | Defines the application fields the Label Specialist matches against the label (Brand Name, Fanciful Name, Name/Address, Class/Type, Net Contents, Alcohol Content). The mock COLA DB schema mirrors these. |
| [`ref-docs/colas_ol_oim_um.pdf`](../ref-docs/colas_ol_oim_um.pdf) | **COLAs Online Industry-Member User Manual** (v3.11.3) | The applicant-side filing workflow, image-upload mechanics (JPG/TIFF, ≤750 KB, ≤10 images), and the dispositions (Approved / Needs Correction / Rejected). Documents the submitter view; the reviewer view is **not** published anywhere. |
| [`ref-docs/Definition of Terms.txt`](../ref-docs/Definition%20of%20Terms.txt) | Extracted glossary / manual text | Domain glossary support (COLA, TTB ID, class/type/fanciful name, etc.). |
| [`ref-docs/reference-urls.txt`](../ref-docs/reference-urls.txt) | List of authoritative TTB source URLs | Provenance trail for the regulatory extraction. |

### Brief & research outputs (intent and verified findings)

| Document | What it is | Used for |
|---|---|---|
| [`ref-docs/TTB-take-home-instructions.md`](../ref-docs/TTB-take-home-instructions.md) | The take-home **brief** + stakeholder interviews (Sarah Chen, Marcus Williams, Dave Morrison) | The premises: ~150k apps/yr, ~47 examiners, the 5-second requirement, the no-outbound-calls firewall constraint, the "STONE'S THROW" tolerance case, the older/varied tech-comfort user base. |
| [`ref-docs/discussion-points.md`](../ref-docs/discussion-points.md) | Polished decision register (by Mary, BA) | The working set of [DECISION]/[REQUEST]/[OPEN] items; §§7, 11, 12, 15 directly feed this document. |
| [`ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) | First-pass verified research (CFR rules, dispositions, image mechanics, comparable software) | §8 (test-data sources) and §9 (comparable software) are the verified foundation this document builds on. |
| [`_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md`](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md) | The **domain research report** (scale, solution landscape, ruleset, OCR/LLM tech) | The ~90%-online figure, the solution-landscape quadrant model, the deterministic-vs-LLM check taxonomy, and the OCR engine benchmarks. |
| [`docs/regulatory-rules-distilled-spirits.md`](regulatory-rules-distilled-spirits.md) · [`docs/label-requirements-by-type.md`](label-requirements-by-type.md) | Derived, easy-to-read rule write-ups | The human-readable rule list the Label Specialist UI surfaces. |

---

## 2. Comparable Software

The market has tooling on the **maker's** side and the **public/registry** side, plus
TTB's own applicant-facing job aids. **None of it serves the federal Label Specialist.**
That empty quadrant is precisely the niche this POC targets. The map below is the
regulatory-domain analog of a competitive landscape (there is no market-share contest —
the POC is a non-commercial federal tool).

| Camp | Who it serves | Examples | What it does |
|---|---|---|---|
| **Maker-side pre-screen** | Applicants, *before* submitting | COLAClear, GetGen AI, Phantom Ales COLA Pre-Check | Reads label artwork, checks against 27 CFR, returns pass/review/fix with citations |
| **Registry search / data** | Public, researchers | COLA Cloud, Sovos ShipCompliant LabelVision | Search already-approved COLAs; bulk datasets |
| **Official TTB job aids** | Applicants (TTB-published) | Anatomy of a Distilled Spirits Label tool; Allowable Changes Sample Label Generator | Educational/reference; authoritative TTB framing of label elements & allowable revisions |
| **Federal reviewer review workspace** | **Label Specialists** | **— none publicly exists —** | *The gap this POC fills* |

### Maker-side pre-screen tools (closest analogs to the POC's verification logic)

These check a label *before* it goes to TTB, so makers catch their own errors first.

- **COLAClear** ([colaclear.com](https://colaclear.com)) — **the closest analog to the
  POC's rules engine.** Automated TTB pre-screen for wine & spirits; reads front/back
  artwork, cross-references the full text of **27 CFR Parts 4, 5, and 16**, and returns a
  structured **pass / review / fail** report "in seconds" with a regulation citation
  behind every flag. Its May 2026 public beta runs **34 checks** — class/type, alcohol
  content, standards of fill, the verbatim Government Warning, sulfites, grape variety,
  multi-varietal percentages, plus CA/OR/VA state rules. Architecturally it is explicitly
  *not* generic AI: **computer vision for text extraction + structured-LLM reasoning for
  ambiguous fields + a hand-coded rules engine grounded in live CFR text** — and it
  disclaims legal advice / approval guarantees. This validates the POC's hybrid approach
  (deterministic where possible, LLM only for ambiguity) and its "recommend, don't decide"
  posture.
  *Source:* [Wine Industry Advisor — COLAClear Public Beta](https://wineindustryadvisor.com/2026/05/04/colaclear-launches-public-beta-automated-ttb-label-pre-screen/),
  [colaclear.com](https://colaclear.com).
- **GetGen AI** ([getgen.ai/solutions/ttb-regulations-software](https://getgen.ai/solutions/ttb-regulations-software))
  — AI-powered TTB compliance across beer/wine/spirits/specialty for marketing, packaging,
  and labels; auto-updates from TTB guidance and COLA requirements.
  *Source:* [Research-Findings.md](../ref-docs/Research-Findings.md) §9.
- **Phantom Ales — TTB Label Compliance Checker / COLA Pre-Check**
  ([phantomales.com/cola](https://phantomales.com/cola/)) — a brewery-run AI label
  compliance checker for wine, beer & spirits that "catches TTB issues before submission."
  Smaller/independent; confirms even individual producers are building pre-screen tooling.
  *Source:* [phantomales.com/cola](https://phantomales.com/cola/).

### Registry / search tools (search *already-approved* COLAs)

- **COLA Cloud** ([colacloud.us](https://colacloud.us/)) — a friendlier front-end over
  TTB's Public COLA Registry search; also publishes a Kaggle COLA dataset. Search/lookup,
  **not** compliance checking.
- **Sovos ShipCompliant — LabelVision**
  ([sovos.com/shipcompliant/products/labelvision](https://sovos.com/shipcompliant/products/labelvision))
  — a commercial COLA label search / beverage-alcohol compliance platform.
  *Source:* [Research-Findings.md](../ref-docs/Research-Findings.md) §9.

### Official TTB job aids (directly reusable references for the POC)

- **Anatomy of a Distilled Spirits Label** tool — TTB's own authoritative breakdown of
  where each mandatory element sits on a spirits label. Excellent grounding for the POC's
  checklist UI and field map.
  *Source:* [TTB Distilled Spirits Labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/labeling).
- **Allowable Changes Sample Label Generator** — TTB's official tool for which label
  changes *don't* require a new COLA; maps directly to the "allowable revisions" concept
  the Label Specialist must know.
  *Source:* [TTB Labeling Resources](https://www.ttb.gov/regulated-commodities/labeling/labeling-resources).

### A note on the brain-dump names ("LabelScreener" / "Label Score")

The names **"LabelScreener"** and **"Label Score"** appear in the original brain-dump
([discussion-points.md](../ref-docs/discussion-points.md) §12) as candidate maker-side
pre-screen tools. **In two research passes neither resolved to a distinct, currently-live
product.** They are most likely half-remembered references. To keep this document honest,
the live maker-side pre-screen field is represented by the **verified** tools above —
**COLAClear, GetGen AI, and Phantom Ales** — which should be cited in their place.
*(Absence of search hits is not proof of non-existence; flagged for Diane to confirm if she
has a source.)*

### The differentiation story

The market has solved **maker-side pre-screening** (COLAClear, GetGen, Phantom Ales) and
**registry search** (COLA Cloud, LabelVision), and TTB itself publishes **applicant job
aids**. **No one builds the federal reviewer's review workspace.** The reviewer side
is, in fact, undocumented in public — confirmed in
[Research-Findings.md](../ref-docs/Research-Findings.md) §5 (every local manual and screen
is the submitter side). Two strategic implications:

1. **Clean differentiation.** The POC occupies an unserved quadrant — the Label Specialist's
   side — so it isn't reinventing existing software. It uses the well-documented
   applicant-side data model (Form 5100.31 fields) as its input and designs the reviewer
   experience that does not publicly exist.
2. **Rising submission quality (a tailwind worth acknowledging).** As maker-side
   pre-screen tools proliferate, the *quality of incoming submissions should improve over
   time* — industry is "picking up the ball" on the pre-screening the government's own
   abandoned pilot tried and dropped. Cleaner, pre-validated inputs make a reviewer-assist
   *more* reliable, not less. This is a reasoned inference (not a measured trend), but it
   is a genuine reason to expect the Label Specialist's routine-matching workload — "half the day
   is essentially data-entry verification" per the Sarah Chen interview — to keep shrinking
   on the input side even as the POC accelerates it on the review side.

---

## 3. Test Data Sources

A strong benchmark and a credible demo both need **many** labels — not a handful. The good
news: TTB exposes real approved labels publicly. The catch is IP, not access.

### Primary source — the public COLA Registry (no login)

- **Public COLA Registry**, searchable at
  [publicSearchColasBasic.do](https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do)
  with **no registration or password**. It returns **label images** for electronically- and
  paper-approved COLAs from **1999 to present** (generally available ~48 hours after
  approval). Searchable by beverage type, brand, class/type, origin, and date — so you can
  pull a realistic, **mixed** set of beer/wine/spirits labels.
  *Source:* [TTB COLA Public Registry](https://www.ttb.gov/regulated-commodities/labeling/cola-public-registry),
  [Research-Findings.md](../ref-docs/Research-Findings.md) §8.

### Bulk sources (avoid one-at-a-time scraping)

- **data.gov — "TTB Public COLA Registry Search and Download"** — an official extract of
  COLA records meeting specified search criteria; the structured-field companion to the
  image registry.
  *Source:* [data.gov TTB COLA Registry Search and Download](https://catalog.data.gov/dataset/ttb-public-cola-registry-search-and-download-extract-data-about-colas-that-meet-specified--cafd3/resource/f7727647-e553-403e-9d5f-907255ea9e05).
- **Kaggle — "ttb-colas-demo"** (published by COLA Cloud) — a ready-made batch of COLA
  records, handy for seeding the mock DB without scraping.
  *Source:* [Research-Findings.md](../ref-docs/Research-Findings.md) §8.

### The IP caveat — private fixtures only; synthetic for anything public

The *records* are public government data, but the **label artwork itself is the brand
owner's trademark / trade dress.** This is an **IP** consideration, not a privacy one (the
POC stores no PII — per the Marcus Williams interview). Therefore:

- Use registry images as **internal/private test fixtures only** — do **not** redistribute
  brand artwork in the public repo or the deployed demo.
- For anything shown **publicly** (the live demo, screenshots, the repo), use **synthetic /
  AI-generated labels**, which the brief explicitly encourages. The provided sample label
  ("OLD TOM DISTILLERY" / "Kentucky Straight Bourbon Whiskey") is itself a useful synthetic
  fixture — and a deliberate **fail** case, since it is missing the name-and-address
  statement (§5.66) and the Government Warning (Part 16), per
  [Research-Findings.md](../ref-docs/Research-Findings.md) §1.
- Record this in [assumptions.md](assumptions.md).

### Concrete advice for building a strong data foundation

To get *many* labels — the explicit ask in
[discussion-points.md](../ref-docs/discussion-points.md) §11 — and a defensible benchmark:

1. **Start from the bulk data.gov / Kaggle extracts** for breadth, then pull matching images
   from the Registry for the subset you need rendered.
2. **Stratify the private fixture set** so the benchmark is representative, not lucky:
   - by **beverage type** (spirits primary; a few wine/beer to exercise the cross-type ABV
     logic — the ABV rule differs in all three);
   - by **class/type** (whiskey, vodka, gin, liqueur, distilled-spirits specialty/RTD —
     liqueurs and specialties are error-prone, see §4);
   - by **outcome** (deliberately include known-noncompliant labels, including the synthetic
     fail case, so the engine is tested on FAILs, not just PASSes);
   - by **image quality** (clean scans plus a glare/skew/off-angle subset to exercise the
     OpenCV preprocessing and the multi-OCR comparison).
3. **Pair every image with structured field data** in a CSV (Form 5100.31 fields → expected
   OCR values) so each fixture doubles as a labeled benchmark row — this is what makes the
   "which OCR / which LLM is more accurate" stats meaningful.
4. **Include multi-image submissions** (front + back + neck/strip) so the verifier is tested
   on checking mandatory elements across the *union* of labels, not just one image
   ([Research-Findings.md](../ref-docs/Research-Findings.md) §4).
5. **Aim for volume with intent:** dozens-to-hundreds of fixtures beats a handful; the
   procurement-grade recommendations the brief wants depend on a sample large enough to
   distinguish engines. Keep the private fixture set out of version control (or in a clearly
   non-redistributed location) per the IP caveat.

---

## 4. Top-10 Most Common Label Errors (Distilled Spirits)

**Sourcing caveat (read first):** the well-known, widely-circulated "top-10 most common
label error" lists are **wine-focused** (appellations, vintage, varietal percentages).
That is explicitly noted in [discussion-points.md](../ref-docs/discussion-points.md) §7. The
list below is assembled from **spirits-oriented and general-TTB** sources where available,
and where a point originates in a wine-centric or general list it is marked **[extrapolated
to spirits]** with the reasoning. Items grounded in spirits-specific sources are marked
**[spirits-sourced]**.

| # | Error | Basis | Source |
|---|---|---|---|
| 1 | **Missing / incorrect mandatory information** — any of brand name, class/type, alcohol content, net contents, name & address, or the Government Warning is absent or wrong. Missing any required item is a near-automatic rejection. | [spirits-sourced] (general-TTB, applies directly to spirits' §5 mandatory set) | [Zahn Law — Top Things People Get Wrong](https://www.zahnlawpc.com/top-things-people-get-wrong-on-their-ttb-labels/), [TTB DS Checklist](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-checklist) |
| 2 | **Class/type misclassification** — labeling a product with a class/type its liquid doesn't qualify for; specialty spirits, RTDs, and novel infusions are the worst offenders because TTB definitions lag innovation. Example: a "red-colored gin" is a *Distilled Spirits Specialty*, not "Gin." | [spirits-sourced] | [FX5 — Avoiding Common COLA Pitfalls (US Distillers)](https://fx5.com/avoiding-common-cola-submission-pitfalls-a-guide-for-us-distillers/), [Park Street — Common COLA Mistakes](https://www.parkstreet.com/the-most-common-cola-mistakes-to-avoid/) |
| 3 | **Government Warning errors** — missing, reworded, wrong punctuation, not "separate and apart," or "GOVERNMENT WARNING:" not in caps/bold. The most rule-bound check; "people get creative" (Jenny Park). | [spirits-sourced] (mandatory on all spirits via Part 16) | [Zahn Law](https://www.zahnlawpc.com/top-things-people-get-wrong-on-their-ttb-labels/); wording per [27 CFR §16.21](https://www.law.cornell.edu/cfr/text/27/16.21) |
| 4 | **Alcohol content (ABV) format / value errors** — improper format (e.g., must read like "ALC 45% BY VOL"), improper rounding, proof not properly distinguished, or a value that mismatches the application/formula. | [spirits-sourced] (ABV **always required** on spirits, §5.65) | [FX5](https://fx5.com/avoiding-common-cola-submission-pitfalls-a-guide-for-us-distillers/), [Zahn Law](https://www.zahnlawpc.com/top-things-people-get-wrong-on-their-ttb-labels/) |
| 5 | **Mismatched legal classification / prohibited brand-name use** — using a class/type term (e.g., "whiskey," "bourbon") in the brand or designation when the product doesn't meet that standard of identity. | [spirits-sourced] | [Zahn Law](https://www.zahnlawpc.com/top-things-people-get-wrong-on-their-ttb-labels/), [Park Street](https://www.parkstreet.com/the-most-common-cola-mistakes-to-avoid/) |
| 6 | **Formatting / "separate and apart" violations** — age statements not in the required "Aged ___ Years" form; for liqueurs, "Liqueur" must be on its own line; mandatory info buried in promotional copy. | [spirits-sourced] | [Park Street](https://www.parkstreet.com/the-most-common-cola-mistakes-to-avoid/), [FX5](https://fx5.com/avoiding-common-cola-submission-pitfalls-a-guide-for-us-distillers/) |
| 7 | **Prohibited or misleading claims** — "healthy," "hangover-free," unsubstantiated "gluten-free," or the prohibited word "pure"; misleading or indecent imagery; government seals/flags implying endorsement. | [spirits-sourced] | [Zahn Law](https://www.zahnlawpc.com/top-things-people-get-wrong-on-their-ttb-labels/), [FX5](https://fx5.com/avoiding-common-cola-submission-pitfalls-a-guide-for-us-distillers/) |
| 8 | **Net contents / standards-of-fill errors** — net contents missing, wrong format, or a fill volume not on TTB's approved metric standards-of-fill list (§5.203). | [extrapolated to spirits] — prominent on wine/general lists; spirits net-contents and standards of fill are mandatory (§5.70, §5.203), so the same error class applies | [TTB DS Checklist](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-checklist); cross-type basis [Research-Findings.md](../ref-docs/Research-Findings.md) §1 |
| 9 | **Name & address phrasing errors** — the bottler/importer name-and-address statement missing, not immediately preceded by a qualifying phrase ("Bottled By," "Imported By," "Distilled By"), or with intervening text. | [extrapolated to spirits] — spirits require it under §§5.66–5.68; the "qualifying phrase, no intervening text" rule is spirits-specific | [Research-Findings.md](../ref-docs/Research-Findings.md) §1; [TTB DS Checklist](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-checklist) |
| 10 | **Missing formula approval / formula-label inconsistency** — submitting a label before the required formula approval (flavored/specialty products), or a mismatch between the approved formula and what the label states (e.g., formula says "lavender flowers," label says "botanical extracts"). | [spirits-sourced] | [FX5](https://fx5.com/avoiding-common-cola-submission-pitfalls-a-guide-for-us-distillers/), [Zahn Law](https://www.zahnlawpc.com/top-things-people-get-wrong-on-their-ttb-labels/) |

**Honorable mentions / wine-specific (noted but *not* extrapolated to spirits):**
unauthorized **geographic / appellation** references (e.g., "Napa" without the grape-source
threshold), **vintage** and **varietal-percentage** errors. These are genuinely
wine-centric — the spirits analog is the **state-of-distillation** requirement for certain
U.S. whiskies (§5.66(f)) and **age statements** (§5.74), which are folded into items 5–6
above.

**How this maps to the POC's checks:** items 1, 3, 4, and 8 are largely **deterministic**
(presence, exact/regex match, format, lookup tables); items 2, 5, 6, 7, and 10 are
**hybrid** (rules first, LLM only for ambiguous designations / statements of composition);
item 9 is **rules + field-match** to the permit. This taxonomy mirrors the
deterministic-vs-LLM table in the
[domain research report](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
and COLAClear's validated architecture (see §2).

---

## 5. Online vs. Paper Application Volume

### What's confirmed

- **~90% of COLA applications are filed and processed electronically** through COLAs
  Online; the remainder are paper Form 5100.31 submissions. This corroborates the thesis
  that online has overtaken paper. *Confidence: MEDIUM — "~90%" recurs across secondary
  sources but is not yet pinned to an official annual figure.*
  *Source:* [TTB COLAs and Formulas Online FAQs](https://www.ttb.gov/faqs/colas-and-formulas-online-faqs),
  [TTB COLAs Online Customer Page](https://www.ttb.gov/regulated-commodities/labeling/colas),
  [domain research report — Domain Scale & Structure](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md).
- For scale context: **~150,000 label applications/year**, reviewed by **~47 examiners**
  (per the Sarah Chen interview in
  [TTB-take-home-instructions.md](../ref-docs/TTB-take-home-instructions.md)); the COLA
  online system has run since **2003**.

### Why online dominates (and why it matters to the POC)

COLAs Online enforces business rules at submission — rejecting incomplete/invalid data up
front and issuing an immediate TTB ID — so online submissions arrive cleaner and
structured. That structured-field input is exactly what the Label Specialist POC assumes it can
pull from the COLA database.
*Source:* [TTB COLAs and Formulas Online FAQs](https://www.ttb.gov/faqs/colas-and-formulas-online-faqs).

### Exact 2024 / 2025 / 2026 paper-vs-online counts — `[TODO]` (automated access blocked)

**Attempted and documented as infeasible programmatically.** The exact yearly counts are
obtainable from TTB's Public COLA Registry search, which lets you filter results and returns
exact match counts. In this session the live form-driven search
([publicSearchColasBasic.do](https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do))
could **not** be queried automatically:

- A direct fetch failed with a **TLS certificate error** ("unable to verify the first
  certificate") on `ttbonline.gov`.
- TTB.gov supporting pages (the FAQ, the registry-search how-to article, and the Public COLA
  Registry user manual) **repeatedly timed out** on automated fetch in this session — the
  same behavior the [domain research report](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
  noted ("the live search is form-driven and resisted automated fetch").

The data **exists and is publicly queryable** — only the *automation* failed. Confidence is
HIGH that a human can pull these numbers in a browser.

**`[TODO — Diane to pull the exact counts manually]`.** Suggested procedure:

1. Open the Public COLA Registry advanced search:
   [https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do](https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do)
   (click through to **Advanced Search**). No login required.
2. Set a **date range** (the search supports "Date Completed" / date-range filtering) for the
   period — e.g. **2024-01-01 to 2024-12-31**, then 2025, then 2026-01-01 to today.
   *(Optionally narrow to **Class/Type = distilled spirits** to get the spirits-only split,
   matching the POC's focus.)*
3. Use the **filing-method / application-type** filter to separate **e-filed (electronic)**
   from **paper** submissions. *(Note: the exact label of this control could not be confirmed
   from the user manual in this session — it timed out — so confirm the field name on the
   live Advanced Search page. The registry distinguishes "electronically approved" vs "paper"
   images, so the distinction is queryable.)*
4. Read the **total result count** shown for each (year × method) query and record it in the
   table below.
5. If the in-browser search is unwieldy, the **[data.gov "TTB Public COLA Registry Search and
   Download"](https://catalog.data.gov/dataset/ttb-public-cola-registry-search-and-download-extract-data-about-colas-that-meet-specified--cafd3/resource/f7727647-e553-403e-9d5f-907255ea9e05)**
   extract is the bulk alternative — pull the same date ranges and group by filing method
   offline.

| Year | Online (e-filed) | Paper | Total | % Online |
|---|---|---|---|---|
| 2024 | `[TODO]` | `[TODO]` | `[TODO]` | `[TODO]` |
| 2025 | `[TODO]` | `[TODO]` | `[TODO]` | `[TODO]` |
| 2026 (to date) | `[TODO]` | `[TODO]` | `[TODO]` | `[TODO]` |

> **Note on two distinct clocks (so the POC's perf claim isn't confused):** the multi-day
> figures TTB publishes (spirits ~2–6 days; wine cut to ~3 days in 2026) are *end-to-end
> queue latency*. The brief's **5-second requirement is per-label interaction latency** — how
> fast the screen loads once an agent opens a submission. The POC's background pre-compute
> strategy targets the second clock only.
> *Source:* [TTB Processing Times](https://www.ttb.gov/regulated-commodities/labeling/processing-times).

---

## Sources

External:
- [Wine Industry Advisor — COLAClear Public Beta](https://wineindustryadvisor.com/2026/05/04/colaclear-launches-public-beta-automated-ttb-label-pre-screen/)
- [colaclear.com](https://colaclear.com) · [getgen.ai TTB software](https://getgen.ai/solutions/ttb-regulations-software) · [phantomales.com/cola](https://phantomales.com/cola/)
- [colacloud.us](https://colacloud.us/) · [Sovos ShipCompliant LabelVision](https://sovos.com/shipcompliant/products/labelvision)
- [TTB Distilled Spirits Labeling](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/labeling) · [TTB Labeling Resources](https://www.ttb.gov/regulated-commodities/labeling/labeling-resources) · [TTB DS Checklist](https://www.ttb.gov/regulated-commodities/beverage-alcohol/distilled-spirits/ds-labeling-home/ds-checklist)
- [Zahn Law — Top Things People Get Wrong on TTB Labels](https://www.zahnlawpc.com/top-things-people-get-wrong-on-their-ttb-labels/) · [FX5 — Avoiding Common COLA Pitfalls (US Distillers)](https://fx5.com/avoiding-common-cola-submission-pitfalls-a-guide-for-us-distillers/) · [Park Street — Common COLA Mistakes](https://www.parkstreet.com/the-most-common-cola-mistakes-to-avoid/)
- [27 CFR §16.21 (Cornell LII)](https://www.law.cornell.edu/cfr/text/27/16.21) · [§16.22](https://www.law.cornell.edu/cfr/text/27/16.22)
- [TTB COLAs and Formulas Online FAQs](https://www.ttb.gov/faqs/colas-and-formulas-online-faqs) · [TTB COLAs Online Customer Page](https://www.ttb.gov/regulated-commodities/labeling/colas) · [TTB Processing Times](https://www.ttb.gov/regulated-commodities/labeling/processing-times)
- [Public COLA Registry search](https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do) · [TTB COLA Public Registry](https://www.ttb.gov/regulated-commodities/labeling/cola-public-registry) · [data.gov TTB COLA Registry Search & Download](https://catalog.data.gov/dataset/ttb-public-cola-registry-search-and-download-extract-data-about-colas-that-meet-specified--cafd3/resource/f7727647-e553-403e-9d5f-907255ea9e05)

Local:
- [ref-docs/](../ref-docs/) catalog (see §1) · [Research-Findings.md](../ref-docs/Research-Findings.md) · [discussion-points.md](../ref-docs/discussion-points.md) · [TTB-take-home-instructions.md](../ref-docs/TTB-take-home-instructions.md) · [domain research report](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md)
- Cross-links: [tools-used.md](tools-used.md) · [assumptions.md](assumptions.md)
