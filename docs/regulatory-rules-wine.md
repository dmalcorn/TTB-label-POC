# Regulatory Rules — Wine Label Review

*An easy-to-read review ruleset for wine labels, derived from TTB's own
mandatory-label checklist and the underlying CFR. This is the authoritative rule
reference for the POC's advisory compliance engine, wine track.*

**Scope:** Wine only — **27 CFR Part 4** (which applies to wine of **7%–24% ABV**,
§4.6) plus the **27 CFR Part 16** health warning. For the parallel spirits and
beer rulesets, and the cross-type comparison, see
[`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md),
[`regulatory-rules-beer.md`](./regulatory-rules-beer.md), and
[`label-requirements-by-type.md`](./label-requirements-by-type.md). See
[`approach.md`](./approach.md) for how these rules are operationalized in the
engine.

> **ABV-range scope note.** Part 4 governs wine **7%–24% ABV** (§4.6). Wine
> **below 7% ABV** is regulated as a **food** under FDA/FALCPA rules, not Part 4,
> and falls **outside** this ruleset. The engine should treat a sub-7% wine as a
> `flag-REVIEW` (out-of-Part-4 scope) rather than apply Part 4 checks to it.

---

## 1. Source authority

These rules are taken from TTB's own published guidance as the **primary** source,
with the CFR cited for each element.

| Source | Role | File / citation |
|---|---|---|
| TTB *Checklist of Mandatory Label Information — Wine* (TTB G 2019-12) | **Primary** authoritative "what TTB reviews" source | [`../ref-docs/wine-labeling-checklist.pdf`](../ref-docs/wine-labeling-checklist.pdf) — local copy of TTB G 2019-12, *"Checklist of Mandatory Label Information \| Wine."* This is the most review-authoritative source: it enumerates exactly the items and per-item checklist questions TTB reviews on every wine label/COLA. Cross-checked against this document line-by-line (2026-06-11). |
| 27 CFR Part 4 | Wine labeling regulation | [`../ref-docs/27 CFR Part 4.pdf`](../ref-docs/27%20CFR%20Part%204.pdf) — **local eCFR copy, current to 6/09/2026**. Every Part 4 section number and rule claim in this document was verified line-by-line against this PDF (2026-06-11). |
| 27 CFR Part 16 | Health (Government) Warning — exact text + type-size table | [`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf) — **local eCFR copy, current to 6/09/2026**. Cross-referenced by Part 4 (§4.7, §4.39(h)); Part 16 applies to all "alcoholic beverages" ≥0.5% ABV, which includes wine (§16.30 names parts 4/5/7). Warning text §16.21; type-size §16.22. Verified 2026-06-11. |
| Domain research report | Regulatory-requirements synthesis (cross-type divergence) | [`../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md`](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md) |

> **Verification note.** Each Part 4 section number and rule claim in this document
> was verified line-by-line against the **local** authoritative PDF
> [`../ref-docs/27 CFR Part 4.pdf`](../ref-docs/27%20CFR%20Part%204.pdf) (eCFR text,
> current to **6/09/2026**) on **2026-06-11**, and the Government Warning
> cross-reference against [`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf).
> The element list and per-item checks were additionally cross-checked against TTB's
> own [`../ref-docs/wine-labeling-checklist.pdf`](../ref-docs/wine-labeling-checklist.pdf)
> (TTB G 2019-12) on **2026-06-11**; every mandatory/conditional item the checklist
> enumerates is represented below.
> Unlike Part 5 (spirits), Part 4 (wine) was **not** subject to the 2022
> modernization renumbering (T.D. TTB-176 deferred the Part 4 rewrite), so the
> historical §4.xx citations remain current — confirmed against the local PDF's
> table of contents and section bodies.

### Core POC principle — "recommend, don't decide"

The engine emits an **advisory verdict** for each label — **PASS / REVIEW / FAIL**.
It never issues a disposition. The human **Label Specialist** reviews the findings and
issues the official TTB **disposition** — **Approved / Needs Correction /
Rejected**. "REVIEW" is an engine signal (a check the software cannot confirm
deterministically), not a disposition. See
[`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §7 and
[`approach.md`](./approach.md).

---

## 2. The "brand label" and multiple-labels rule (§4.32 / §4.10)

Wine has **no "same field of vision" rule** — that constraint is specific to
distilled spirits (§5.63, see
[`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md)
§2). Wine's structural keystone is instead the **brand-label / multi-label
distribution rule**, which the verifier must honor when checking elements across a
multi-image submission.

> *Certain items must appear on the **brand label**; the remaining mandatory items
> may appear on **any label** affixed to the container.* — **27 CFR 4.32**

**What "brand label" means (§4.10):** the label *"carrying, in the usual
distinctive design, the brand name of the wine."* **Any** affixed label can serve
as the brand label if it carries the brand name in that distinctive design — it is
not necessarily the front label.

**Items that must be on the *brand label* (§4.32(a)):**

1. Brand name (§4.33)
2. Class, type, or other designation (§4.34)
3. Percentage of foreign wine, for a blend of American and foreign wines (when foreign wine is referenced) — **§4.32(a)(4)** (note: §4.32(a)(3) is *[Reserved]*)

**Items that may be on *any* affixed label (§4.32(b)):**

- Name & address (§4.35)
- Net contents (§4.37) — *but* a non-standard fill must be on a front label
- Alcohol content (§4.36)
- Sulfite, FD&C Yellow No. 5, cochineal/carmine declarations — front, back, strip, or neck label (§4.32(c)–(e))

**POC implication — check across the UNION of label images.** A European wine can
keep its origin-country front label and add a U.S. "compliance" back/strip label
carrying the warning, sulfites, importer name/address, and net contents. The
verifier must accept a **set of images per application** and confirm each mandatory
element is present **somewhere in the union** of the uploaded labels — it must
**not** demand every element on a single image. (COLAs Online supports up to 10
tagged images per application — see
[`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §4, §6.)

**POC check type — `hybrid`.** Presence across the union is deterministic
(detect each element in the merged OCR text). The *brand-label-specific*
constraint (brand + class/type must sit on the **same** label that carries the
distinctive brand design) is a positional/per-image judgment OCR bounding boxes
alone cannot guarantee from photos — that sub-check is **`flag-REVIEW`**
(positional), mirroring the spirits field-of-vision handling. See "positional
checks" in [`approach.md`](./approach.md).

---

## 3. Always-mandatory elements

These must appear on **every** wine label (within the union of affixed labels per
§2). The "POC check type" column maps each to how the engine evaluates it:

- **deterministic** — pure rule/regex match against label text (no application
  field needed).
- **field-match (app ↔ OCR)** — compare the application-entered value against the
  OCR-extracted label text; mismatch ⇒ flag.
- **hybrid** — presence/format is deterministic, but a content judgment (validity,
  consistency) is advisory.
- **flag-REVIEW** — the engine cannot confirm reliably; surface to the Label Specialist.

| Element | What the Label Specialist checks | Citation | POC check type |
|---|---|---|---|
| **Brand name** | Present on the brand label; **matches the "Brand Name" application field** | **§4.33** | **field-match (app ↔ OCR)** + brand-label co-location `flag-REVIEW` |
| **Class / type designation** | Present on the brand label; **separate & apart** from other info; **spelled correctly**; consistent with a class/type defined in the regs (**§4.21**) — *or*, where the class is not defined in §4.21, a truthful & adequate **statement of composition** in lieu of a class designation (§4.34); a still wine may use a varietal, type-of-varietal-significance, or geographic designation in place of the class (§4.34(a)); a **grape varietal** on the brand label *is* the class/type designation (match the "Grape Varietal(s)" application field; for domestic wine each varietal must be approved for domestic use — **§4.91**); if the wine **requires a formula**, the statement of composition must match (or be more specific than) the approved-formula statement and the formula number must be selected on the application; this and other labels must be **free of conflicting/inconsistent designations** (e.g. "red wine with natural flavors" vs. "red wine"); special-sweetness label required if total solids > 17 g/100 cc; **table/dessert** classes need not be stated; appellation may be triggered (see §4 below) | **§4.21**, **§4.34** (statement of composition); **§4.91** (domestic grape varietals) | **hybrid** (presence/field-match/spelling deterministic; designation *validity*, statement-of-composition adequacy, formula, and conflicting-designation judgments `flag-REVIEW`) |
| **Alcohol content (ABV)** | **Required only if > 14% ABV** (or if the label omits a "table wine"/"light wine" designation); acceptable format/abbreviations (`Alcohol __ % by volume`, `Alc.`, `Vol.`); range statements permitted within the allowed spread | **§4.36** | **hybrid** (the *conditional trigger* + value-vs-application `field-match` with tolerances; see ABV-trap §6) |
| **Net contents** | Present on the label **or blown into / marked on the container**; acceptable format/abbreviation (e.g. `750 mL`, `1 L`); meets an authorized **standard of fill** (§4.72) — exceptions per **§4.70(b)**; non-standard fill must be on a front label | **§4.37** (standards of fill **§4.72**; exceptions **§4.70(b)**) | **hybrid** (presence + format deterministic; standard-of-fill value `field-match`/`flag-REVIEW`) |
| **Name & address** | Name (or trade name) + address (**city and State**, as listed on the permit) present; name on the label matches the permit on the application (if a DBA/trade name, it must appear on **both** application and permit); address matches the application; **immediately follows** a permitted responsibility phrase (e.g. `Bottled By`, `Imported By`, `Produced and Bottled By`) **with no intervening text** | **§4.35** | **hybrid** (presence + responsibility-phrase regex deterministic; name/address-vs-permit validity `flag-REVIEW`) |
| **Country of origin** | Imported wine only; country-of-origin statement complying with **CBP** rules (questions on the appropriate country go to CBP, not TTB) | **19 CFR 134.11** (CBP) | **flag-REVIEW** (CBP-governed; presence check if import indicated) |
| **Health (Government) Warning** | Present; **exact** wording & punctuation; `GOVERNMENT WARNING` in caps + bold; `S` in Surgeon and `G` in General capitalized; one statement; separate & apart | **27 CFR Part 16** (§16.21 text, §16.22 type-size) | **deterministic** — see §5 below |

> **ABV is NOT always required for wine.** Unlike spirits (always required, §5.65),
> wine requires an ABV statement only when **> 14% ABV**, or when the label does
> **not** carry a "table wine"/"light wine" designation (§4.36). A naive "ABV must
> always be present" check produces **false rejections on table wine**. See the
> ABV-trap callout in §6 and
> [`label-requirements-by-type.md`](./label-requirements-by-type.md).

---

## 4. Conditional elements (triggered)

These are mandatory **only when their trigger condition is met**. Wine's signature
conditional is the **appellation of origin**, which becomes mandatory once the
label makes a varietal, vintage, or semi-generic claim (§4.34(b)). Because the POC
generally cannot independently know the underlying fact (e.g. actual sulfite
content, or whether 75% of the grapes are the named variety), most conditional
checks are **`flag-REVIEW`**: the engine surfaces the trigger question and, where
the label text itself is the evidence, checks for the presence/format of the
required statement.

| Element | Trigger condition | Required statement / threshold | Citation | POC check type |
|---|---|---|---|---|
| **Appellation of origin** | A **varietal**, type-of-varietal-significance, **semi-generic** class, "Brand"-qualified name, or **vintage** appears on the label, **or the product is labeled "estate bottled" (§4.26)** | An appellation (country, State, county, AVA, or other) shown on the **brand label together with the designation**, **in direct conjunction with, and substantially as conspicuous as**, the class/type designation; must match the "Appellation" application field | **§4.25**, **§4.34(b)**, **§4.26** (estate bottled) | **hybrid** (trigger detectable from label text deterministically; appellation *presence/conspicuousness* + app-field match `flag-REVIEW`) |
| → **Varietal designation** | Label names a grape variety (e.g. `Cabernet Sauvignon`) | **≥ 75%** of the wine derived from that grape (and the named appellation); for **domestic** wine the variety must be **approved for domestic use** (§4.91) | **§4.23**; **§4.91** (domestic-approved varietals) | **flag-REVIEW** (percentage not knowable from label; triggers appellation requirement) |
| → **Vintage date** | Label shows a vintage year | **≥ 95%** from that year for **AVA** appellations / **≥ 85%** for non-AVA appellations | **§4.27** | **flag-REVIEW** (percentage not knowable from label; triggers appellation requirement) |
| → **AVA appellation** | An AVA (viticultural area) is used as the appellation | **≥ 85%** of the wine from the named area | **§4.25** | **flag-REVIEW** (percentage not knowable from label) |
| **Sulfite declaration** | Wine contains **≥ 10 ppm** total sulfur dioxide | `Contains Sulfites` (or `Contains (a) sulfiting agent(s)`); may be on front, back, strip, or neck label. `No sulfites added` is permitted **only** together with `contains naturally occurring sulfites` / `may contain naturally occurring sulfites`. If no sulfite declaration appears, the application may need a TTB-laboratory sulfite analysis showing < 10 ppm | **§4.32(e)** | **flag-REVIEW** (presence detectable; actual SO₂ content / lab-analysis requirement not knowable from label) |
| **FD&C Yellow No. 5** | FD&C Yellow No. 5 used | `Contains FD&C Yellow No. 5`; brand or back label | **§4.32(c)** | **flag-REVIEW** (presence detectable deterministically) |
| **Cochineal extract / carmine** | Cochineal extract or carmine used | `Contains Cochineal Extract` / `Contains Carmine`; front, back, strip, or neck label | **§4.32(d)** | **flag-REVIEW** (presence detectable deterministically) |
| **Percentage of foreign wine** | Blend of American and foreign wines, where foreign wine is referenced | Percentage of foreign wine, on the **brand label** | **§4.32(a)(4)** | **flag-REVIEW** (presence detectable; blend fact not knowable from label) |
| **Standards of fill** | Always (net contents must meet an authorized size) | One of the **25 authorized metric sizes** (50 mL – 3 L, plus even-liter ≥ 4 L), incl. **750 mL** | **§4.72** | **hybrid** (value `field-match` against the standards-of-fill table; non-listed size `flag-REVIEW`) |

> **Standards of fill — deterministic table lookup.** §4.72 enumerates **25**
> authorized sizes from **50 mL to 3 L**, plus 4 L and larger in even-liter
> increments (§4.72(b)). `750 mL` is authorized (§4.72(a)(6)). The engine matches the
> OCR'd net-contents value against this table; a value off-table is a `flag-REVIEW`
> (the Label Specialist confirms whether an exemption applies). *(Verified against the
> local [`../ref-docs/27 CFR Part 4.pdf`](../ref-docs/27%20CFR%20Part%204.pdf),
> §4.72(a)(1)–(25) + (b), 2026-06-11.)*

---

## 5. Government Warning verification approach

*(Identical in substance across all three beverage types. The full, deterministic
write-up — exact §16.21 text, §16.22 type-size table, and the regex pipeline —
lives in
[`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md)
§5. It is **not duplicated** here; this section summarizes and links.)*

The warning is the single most rule-bound check in the POC and is **fully
deterministic** — no LLM needed. The statement must appear **exactly** as
prescribed by **27 CFR §16.21**:

> **GOVERNMENT WARNING:** (1) According to the Surgeon General, women should not
> drink alcoholic beverages during pregnancy because of the risk of birth defects.
> (2) Consumption of alcoholic beverages impairs your ability to drive a car or
> operate machinery, and may cause health problems.

**Formatting rules (§16.21):** `GOVERNMENT WARNING` in **caps + bold** (remainder
not bold); the `S` in *Surgeon* and `G` in *General* capitalized; **one
statement**; **separate and apart** from all other label information. The §16.22
type-size table (1 / 2 / 3 mm keyed to container volume) is a **dimensional**
requirement and is **not machine-verified** by the POC (see §6).

**How the POC verifies it (deterministic):** anchor on the `GOVERNMENT WARNING:`
all-caps token; normalize whitespace/case for the body; require an **exact wording
+ punctuation match** (including the `(1)`/`(2)` markers and `Surgeon General`
capitalization). Exact match ⇒ **PASS**; absent ⇒ **FAIL**; reworded / mis-cased /
mis-punctuated ⇒ **FAIL** with the specific deviation reported. Bold is a styling
attribute OCR cannot reliably recover, so the bold requirement is `flag-REVIEW` on
visual styling only.

*(Wording verified against the local
[`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf) §16.21
(text) and §16.22 (formatting/type-size), 2026-06-11 — and see
[`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §2. Full
deterministic pipeline:
[`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md)
§5.)*

---

## 6. ⚠️ The cross-type ABV trap (wine half)

> **The single most important cross-type subtlety: the ABV rule is DIFFERENT in
> all three beverage types — and wine's is the trickiest.** This is the **#1
> false-reject risk** in the engine.

For **wine (§4.36):**

- ABV is **required only when the wine is > 14% ABV.**
- At **≤ 14% ABV**, the ABV statement is **optional** — *provided* the label
  instead carries a **"table wine"** or **"light wine"** designation (§4.32(a)(2)).
- **Tolerances differ by band:** **±1.0 percentage point** for wines **> 14%**;
  **±1.5 percentage points** for wines **≤ 14%** (§4.36). Range statements are
  also allowed: a 2% spread max (> 14%) / 3% spread max (≤ 14%).

**Why this is a trap.** A naive *"ABV must always be present"* check — the obvious
first implementation, and correct for spirits — produces **false rejections on
table wine**, an entirely compliant case. The engine must:

1. Branch on **beverage type = wine** *before* evaluating ABV presence.
2. If ABV is absent, check for a **"table wine"/"light wine"** designation; if
   present, the omission is compliant (and the wine is implicitly ≤ 14%).
3. When matching an ABV value against the application field, apply the
   **band-dependent tolerance** (±1.0 / ±1.5), not the spirits ±0.3.
4. When in doubt, prefer a **REVIEW** verdict over a hard FAIL.

Compare: **spirits — ABV always required**, tolerance ±0.3 (§5.65); **beer —
usually optional**, tolerance ±0.3 (§7.65). See the consolidated trap table in
[`label-requirements-by-type.md`](./label-requirements-by-type.md) and
[`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md).
_Source: [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §1.
Confidence: HIGH._

---

## 7. Out of scope: font / dimension size

**The POC does not verify type size or physical dimensions of any wine label
element** (including the §4.38 minimum type sizes — ≥ 2 mm for containers > 187 mL,
≥ 1 mm for ≤ 187 mL, ABV statement 1–3 mm — and the §16.22 warning type sizes).

**Rationale:**

- Type-size compliance is specified in **millimeters**, but absolute mm cannot be
  reliably recovered from a photograph without a known physical scale reference
  (pixels → mm). See
  [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §3.
- This mirrors **TTB's own COLA Online disclaimer**: label approval does **not**
  test dimensions or font size — the applicant certifies (under perjury signature
  on Form 5100.31) that the label complies. The POC adopts the same posture.
- Attempting it would produce unreliable verdicts and false rejections, which
  contradicts the "recommend, don't decide" principle.

Where a size requirement is regulatorily relevant (e.g. §4.38, the §16.22 table),
it is **documented for reference** but **not machine-verified**. This limitation is
restated in [`approach.md`](./approach.md) and the tradeoffs/limitations doc.

---

## Related documents

- [`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md)
  — companion spirits ruleset (Part 5); home of the full Government Warning
  deterministic pipeline (§5).
- [`regulatory-rules-beer.md`](./regulatory-rules-beer.md) — companion beer / malt
  beverage ruleset (Part 7).
- [`label-requirements-by-type.md`](./label-requirements-by-type.md) — cross-type
  (beer / wine / spirits) requirements comparison and the consolidated ABV-trap
  table.
- [`approach.md`](./approach.md) — how these rules drive the advisory engine
  (verdicts, check types, positional checks, OCR/LLM strategy).
- [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) — verified
  findings (§1 CFR rules, §2 warning, §3 font, §4 multi-label).

> **Note on `chapter4.pdf`.** The repo file
> [`../ref-docs/chapter4.pdf`](../ref-docs/chapter4.pdf) is **not** a wine /
> 27 CFR Part 4 reference. It is *"Chapter 4 — Class and Type Designation"* from
> TTB's **Beverage Alcohol Manual (BAM), Vol. 2, 04/2007 — distilled spirits**: a
> chart of spirits classes and types (Neutral Spirits, Whisky, Bourbon, Straight
> Rye, etc.). It is therefore relevant to
> [`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md),
> **not** to this wine document, and was not used as a source here.
