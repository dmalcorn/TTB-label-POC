# Regulatory Rules — Beer / Malt Beverage Label Review

*An easy-to-read review ruleset for beer / malt-beverage (MB) labels, derived
from 27 CFR Part 7 and TTB's malt-beverage labeling guidance. This is the
authoritative rule reference for the POC's advisory compliance engine, for the
**beer** beverage type.*

**Scope:** Beer / malt beverages only (27 CFR Part 7 + the Part 16 health
warning). For the sibling deep rulesets see
[`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md)
and [`regulatory-rules-wine.md`](./regulatory-rules-wine.md). For the cross-type
comparison see [`label-requirements-by-type.md`](./label-requirements-by-type.md),
and [`approach.md`](./approach.md) for how these rules are operationalized in the
engine.

---

## 1. Source authority

The **primary "what TTB reviews" source** is TTB's own *Checklist of Mandatory Label
Information — Malt Beverage* (the authoritative list of what a TTB Label Specialist
checks on every malt-beverage COLA), grounded element-by-element in **27 CFR Part 7**
as the underlying regulation, with TTB's published malt-beverage labeling guidance and
the cross-type research synthesis as supporting sources. Each element cites its CFR
section. *(This mirrors how
[`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md) §1
treats the spirits checklist as its most review-authoritative source.)*

| Source | Role | File / citation |
|---|---|---|
| TTB *Checklist of Mandatory Label Information — Malt Beverage* | **Primary "what TTB reviews" source** — the authoritative checklist of items TTB reviews on every malt-beverage COLA (post-2022 renumbering, citing 27 CFR parts 7, 16, 25; subpart E) | [`../ref-docs/malt-beverage-labeling-checklist.pdf`](../ref-docs/malt-beverage-labeling-checklist.pdf) |
| 27 CFR Part 7 (Labeling and Advertising of Malt Beverages) | Underlying authoritative regulation cited by the checklist (post-2022 modernization renumbering, T.D. TTB-176, 87 FR 7605, Feb. 9, 2022) | **Verified against the local PDF** [`../ref-docs/27 CFR Part 7.pdf`](../ref-docs/27%20CFR%20Part%207.pdf) (eCFR, current as of 2026-06-09) |
| 27 CFR Part 16 | Health (Government) Warning — exact text + type-size table | Cross-referenced by Part 7 (**§7.7(a)**); **verified against the local PDF** [`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf) (§16.21 text, §16.22 type-size) |
| 27 CFR Part 25 | Beer (brewery) regs cross-referenced by the checklist — bottling-location coding (§§25.141–25.142) and the brewer's notice that the name/address must match | Cited by the checklist; cross-referenced at §7.66(e) |
| Cross-type research synthesis | Per-type mandatory/conditional element table | [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §1 |
| Domain research report | Regulatory-requirements synthesis & cross-type divergence | [`../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md`](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md) |

> **Grounded in the TTB checklist + verified against the local Part 7 PDF.** Every
> mandatory/conditional item below is cross-checked against TTB's official
> [`../ref-docs/malt-beverage-labeling-checklist.pdf`](../ref-docs/malt-beverage-labeling-checklist.pdf)
> (the "what TTB reviews" list, subpart E), and each CFR citation is independently
> verified.
>
> **Verified against the local Part 7 PDF.** 27 CFR Part 7 is now in the downloaded
> `ref-docs/` set as [`../ref-docs/27 CFR Part 7.pdf`](../ref-docs/27%20CFR%20Part%207.pdf)
> (the full eCFR text, current as of 2026-06-09). Every section citation and rule
> claim in this document was checked **section-by-section against that PDF** on
> 2026-06-11 (§§7.5, 7.7, 7.52–7.56, 7.61–7.70, 7.141–7.147 read directly).
> Confidence on the
> mandatory/conditional §7.63–7.70 citations: **high** (read directly from the
> authoritative PDF). The companion Government-Warning regulation is likewise
> grounded in [`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf).

> **Renumbering note.** Section numbers reflect the **post-2022** modernization of
> 27 CFR Part 7 (T.D. TTB-176, parallel to the Part 5 renumbering). The
> mandatory-information master section is now **§7.63** ("Mandatory label
> information"), with per-element sections at **§7.64** (brand name), **§7.65**
> (alcohol content), **§§7.66–7.68** (name & address), **§7.69** (country of
> origin), **§7.70** (net contents), and the class/type designation rules in
> **Subpart I** (**§§7.141–7.147**). Pre-2022 mandatory-info citations (the old
> §7.22 et seq.) are now wrong — use the citations in this document. (Note: the
> numbers §7.22 and §7.24 still exist post-2022 but now address **COLA rules**, not
> mandatory label content.)

### Core POC principle — "recommend, don't decide"

The engine emits an **advisory verdict** for each label — **PASS / REVIEW / FAIL**.
It never issues a disposition. The human **Label Specialist** reviews the findings and
issues the official TTB **disposition** — **Approved / Needs Correction /
Rejected**. "REVIEW" is an engine signal (a check the software cannot confirm
deterministically), not a disposition. See
[`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §7 and
[`approach.md`](./approach.md).

---

## 2. No "same field of vision" rule for beer

> **Beer has no §5.63-style "same field of vision" co-location requirement.** This
> is a notable structural difference from distilled spirits.

For **distilled spirits**, 27 CFR **§5.63** requires the brand name, alcohol
content, and class/type designation to appear together in one field of vision (a
single viewable face of the container) — a positional check that the spirits engine
must flag for the Label Specialist to eyeball. **Part 7 imposes no such across-element
constraint on malt beverages.** Per **§7.61(a)** and **§7.63(a)**, the mandatory
elements may appear on any label affixed to the container, distributed across
front/back/neck labels as the brewer chooses.

> **Two narrow Part 7 exceptions (intra-element only).** Part 7 has no
> *across-element* co-location rule, but two *within-element* positional rules do
> exist and are confirmed in the PDF: (a) **§7.70(c)** — when an optional **metric**
> net-contents measure is shown, it must appear **in the same field of vision** as
> the U.S.-customary net-contents statement; and (b) **§7.141(a)** — *all parts of
> a single class/type designation* must **appear together**. Neither requires the
> brand / ABV / class-type elements to share a field of vision, so the spirits-style
> co-location `flag-REVIEW` still does not apply to beer.

**Implication for the POC:** the beer engine checks the mandatory elements across
the **union of all uploaded label images** (presence + field match), and does
**not** run the spirits "co-location `flag-REVIEW`" positional check. This removes
the single hardest positional check from the beer path. See the spirits doc §2 for
the contrasting rule and [`approach.md`](./approach.md) for positional checks.

---

## 3. Always-mandatory elements

These must appear on **every** malt-beverage label (per §7.63(a)), with the one
big exception of alcohol content (see §5 — the ABV trap). The "POC check type"
column maps each to how the engine evaluates it:

- **deterministic** — pure rule/regex match against label text (no application
  field needed).
- **field-match (app ↔ OCR)** — compare the application-entered value against the
  OCR-extracted label text; mismatch ⇒ flag.
- **hybrid** — presence/format is deterministic, but a content judgment (validity,
  consistency) is advisory.
- **flag-REVIEW** — the engine cannot confirm reliably; surface to the Label Specialist.

| Element | What the Label Specialist checks | Citation | POC check type |
|---|---|---|---|
| **Brand name** | Present; **matches the "Brand Name" application field**; not misleading as to age/origin/identity (if no brand name, the bottler/importer name in the name-&-address statement is treated as the brand name) | **§7.64** (mandated by §7.63(a)(1)) | **field-match (app ↔ OCR)** (misleading-name judgment `flag-REVIEW`) |
| **Class/type designation** | Present; consistent with a class/type listed in the regs or TTB guidance under **Subpart I** (e.g. `Malt Beverage`, `Stout`, `Ale`, `India Pale Ale`) **OR** a distinctive/fanciful name plus an adequate & truthful **statement of composition** (e.g. `Spicy Nut Ale` + `Ale with walnuts and other natural flavors`); **separate and apart** from all other info (**§7.52(b)**); spelled correctly; no conflicting designations across labels. **Formula:** if the beverage requires an approved formula, has one been approved, the statement of composition matched to it, and the **formula number selected on the COLA application**? If a fanciful name is used, does it **match the "Fanciful Name" application field**? | **§7.63** + **Subpart I** (separate-and-apart: **§7.52(b)**) | **hybrid** (presence/field-match deterministic — incl. fanciful-name field match; class/type *validity*, formula approval/selection `flag-REVIEW`) |
| **Alcohol content (ABV)** | **Usually OPTIONAL** — see §5 (also mandatory if **required by one or more States**). When present (or when mandatory under §7.63(a)(3)): acceptable format/abbreviations (`Alc.`, `Alc`, `%`, `Vol`, `Vol.`; e.g. `Alcohol 4.2% by volume`, `Alc. 4.0% Vol.`); expressed to nearest 0.1 point; ±0.3-pt tolerance. **Alcohol by weight (ABW), if shown,** must appear **together with and as part of** a percentage-by-volume statement, with the ABW **accurately converted** to its ABV equivalent (ABW abbreviations: `Alc.`, `Alc`, `%`, `Wt`, `Wt.`) | **§7.65** (trigger at **§7.63(a)(3)**) | **hybrid** (presence is *conditional* — branch on type first; ABV/ABW-format regex deterministic; value vs. application field `field-match` with ±0.3-pt tolerance; ABW→ABV conversion accuracy `flag-REVIEW`) |
| **Net contents** | Present on a label (or blown/embossed/molded into the container); stated in **U.S. customary units** (fluid ounces, pints, quarts, gallons — the mandatory measure); acceptable format/abbreviation (e.g. `12 FL OZ`, `fl. oz.`) using the correct unit for the volume; an optional metric measure may be added (see §2, §7.70(c)). **No mandatory standards of fill for malt beverages** | **§7.70** (mandated by §7.63(a)(5)) | **hybrid** (presence + U.S.-customary format deterministic; no standard-of-fill table lookup) |
| **Name & address** | Bottler's/importer's name (or DBA/trade name) + address (city, state) present (or blown/embossed/molded into the container); matches the brewer's notice / importer's permit and the COLA application; immediately follows a permitted responsibility phrase (e.g. `Bottled By`, `Canned By`, `Brewed and Bottled By`, `Imported By`; `Bottled for`/`Distributed by` when bottled for another) with **no intervening text**. *Conditional sub-checks (all `flag-REVIEW`):* principal place of business shown in lieu of bottling location (**§7.66(e)**, with actual-place coding per **§§25.141–25.142**); multiple breweries under common ownership (**§7.66(f)**); same brand bottled by two-plus breweries not commonly owned (**§7.66(g)**); imported product subject to post-import blending/production (**§7.67**) | **§7.66** (domestic) / **§7.67–§7.68** (imported / not wholly fermented in U.S.) | **hybrid** (presence + responsibility-phrase regex + app/permit field-match deterministic; address validity & §7.66(e)–(g)/§7.67 sub-cases `flag-REVIEW`) |
| **Health (Government) Warning** | Present; **exact** wording & punctuation; `GOVERNMENT WARNING` in caps + bold; `S` in Surgeon and `G` in General capitalized; one statement; separate & apart. Applies to **all beverages ≥ 0.5% ABV** | **27 CFR Part 16** (§16.21 text, §16.22 type-size) | **deterministic** — see §6 below |

> **Country of origin (imports).** For imported malt beverages, a country-of-origin
> statement is governed by CBP rules (**19 CFR 102/134**, cross-referenced at
> **§7.69**), not by TTB type-size rules. POC check type: **flag-REVIEW** (CBP-
> governed; presence check if an import is indicated on the label or application).

---

## 4. Conditional / ingredient-disclosure elements (triggered)

These are mandatory **only when their trigger condition is met** (§7.63(b)). Because
the POC generally cannot independently know the underlying fact (e.g. whether
aspartame or sulfites are actually present), most conditional checks are
**`flag-REVIEW`**: the engine surfaces the trigger question and, where the label
text itself is the evidence, checks for the **presence/format** of the required
statement deterministically.

| Element | Trigger condition | Required statement | Citation | POC check type |
|---|---|---|---|---|
| **FD&C Yellow No. 5** | FD&C Yellow No. 5 used | `FD&C Yellow No. 5` or `Contains FD&C Yellow No. 5` | **§7.63(b)(1)** | **flag-REVIEW** (presence detectable deterministically; trigger not knowable from label) |
| **Cochineal extract / carmine** | Cochineal extract or carmine used | `Contains Cochineal Extract` / `Contains Carmine` | **§7.63(b)(2)** | **flag-REVIEW** (presence detectable deterministically) |
| **Sulfite declaration** | Product contains ≥ 10 ppm total sulfur dioxide | `Contains Sulfites` (or equivalent) | **§7.63(b)(3)** | **flag-REVIEW** (presence detectable; trigger not knowable from label) |
| **Aspartame disclosure** | Aspartame used | `PHENYLKETONURICS: CONTAINS PHENYLALANINE` (**all capital letters**, **separate and apart** from all other info) | **§7.63(b)(4)** | **hybrid** (exact all-caps phrase is a deterministic regex match; trigger `flag-REVIEW`) |
| **Country of origin** | Imported malt beverage | Country-of-origin statement complying with CBP rules | **§7.69** + **19 CFR 102/134** | **flag-REVIEW** (CBP-governed; presence check if import indicated) |

> **No general "coloring materials" / caramel disclosure for beer.** Unlike
> distilled spirits (which require a `Colored With Caramel` / `Artificially Colored`
> disclosure under §5.63(c)(6)), 27 CFR Part 7's ingredient disclosures are limited
> to the specific items above (FD&C Yellow No. 5, cochineal/carmine, sulfites,
> aspartame). This resolves the open "confirm Part 7 coloring cite" TODO in
> [`label-requirements-by-type.md`](./label-requirements-by-type.md): there is **no**
> separate general coloring-material disclosure mandated for malt beverages.
> Confidence: **high** (read directly from §7.63(b) in the local
> [`../ref-docs/27 CFR Part 7.pdf`](../ref-docs/27%20CFR%20Part%207.pdf), 2026-06-11).
> Note: §7.82 also provides for **voluntary** major-food-allergen disclosure
> ("Contains: …"), which is optional and outside the mandatory ruleset here.

---

## 5. ⚠️ The ABV trap — beer's key subtlety (read this)

> **For beer, the alcohol-content statement is USUALLY OPTIONAL.** This is half of
> the cross-type ABV trap and the **#1 false-reject risk** on the beer path.

Per **§7.65(a)**, an alcohol-content statement *may* be stated on any malt-beverage
label but is not generally required. Per the TTB checklist, it becomes **mandatory
only when** the beer's alcohol comes from **added nonbeverage flavors or other added
nonbeverage ingredients containing alcohol (other than hop extract)** — **§7.63(a)(3)**
— **OR** when **required by one or more States**.

- **Format (when present):** expressed as a percentage of alcohol by volume, to the
  nearest 0.1 point; per the TTB checklist the permitted abbreviations are `Alc.`,
  `Alc`, `%`, `Vol`, `Vol.` (e.g. `Alcohol 4.2% by volume`, `Alc. 4.0% Vol.`) —
  **§7.65(b)**.
- **Alcohol by weight (ABW):** a malt-beverage label may also state ABW, but per the
  checklist it must appear **together with and as part of** a statement of alcohol
  content **as a percentage of alcohol by volume**, and the ABW must be **accurately
  converted** to its ABV equivalent. ABW abbreviations: `Alc.`, `Alc`, `%`, `Wt`,
  `Wt.` ABW alone (without the accompanying ABV) is not acceptable.
- **State-law trigger:** an ABV statement is also mandatory when **required by one or
  more States** — a fact the engine cannot know from the label, so prefer **REVIEW**
  over FAIL on absence.
- **Tolerance:** **±0.3 percentage points** above or below the stated value for
  beverages ≥ 0.5% ABV — **§7.65(c)**. The same tolerance as spirits (§5.65),
  unlike wine (±1.0 / ±1.5).

**Why this matters — cross-type contrast:**

| Type | ABV rule | Citation |
|---|---|---|
| **Distilled spirits** | **ALWAYS required** (proof optional, not a substitute) | §5.65 |
| **Beer / malt beverages** | **Usually OPTIONAL** — mandatory only if added nonbeverage-flavor alcohol (other than hops extract) | §7.65 / §7.63(a)(3) |
| **Wine** | **Required only if > 14% ABV** (optional ≤ 14% if "table"/"light" shown) | §4.36 |

> A naive *"ABV must always be present"* check — the obvious first implementation —
> produces **false rejections on compliant beer** (and on table wine). **The engine
> must branch on beverage type before evaluating ABV presence.** For beer, absence
> of an ABV statement is **PASS** (not FAIL) unless the §7.63(a)(3) trigger is known
> to apply; when the trigger is uncertain, prefer **REVIEW** over a hard FAIL.
> See [`label-requirements-by-type.md`](./label-requirements-by-type.md) (Cross-Type
> ABV Trap) and [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §1.

---

## 6. Government Warning verification approach

The Government (health) Warning under **27 CFR Part 16** applies to **all alcoholic
beverages ≥ 0.5% ABV** — including malt beverages — and is **the single most
rule-bound check in the POC**. It is **fully deterministic** (no LLM), and the
verification approach is **identical across all three beverage types**.

Rather than duplicate it here, see the full deterministic write-up in
**[`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md)
§5** (exact §16.21 text, §16.22 type-size table, and the regex pipeline). Summary
for beer:

- **Exact §16.21 text** (verified against the local
  [`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf), §16.21;
  Part 16 applies to "alcoholic beverage[s]" = liquids **≥ 0.5% ABV** per §16.10,
  and §7.7(a) of Part 7 cross-references it for malt beverages):
  > **GOVERNMENT WARNING:** (1) According to the Surgeon General, women should not
  > drink alcoholic beverages during pregnancy because of the risk of birth defects.
  > (2) Consumption of alcoholic beverages impairs your ability to drive a car or
  > operate machinery, and may cause health problems.
- **Formatting:** `GOVERNMENT WARNING` in **caps + bold**; remainder not bold;
  `S` in Surgeon and `G` in General capitalized; one statement; separate and apart.
- **§16.22 type-size table** is keyed to container volume (1 / 2 / 3 mm by size).
  Like all dimensional rules, **the POC does not measure it** (see §7) — documented
  for reference only.
- **How the POC verifies it (deterministic):** anchor on the `GOVERNMENT WARNING:`
  caps token, normalize whitespace/case for the body, then require an exact
  wording + punctuation match against §16.21 (including the `(1)`/`(2)` markers).
  Exact match ⇒ **PASS**; absent ⇒ **FAIL**; present but reworded / mis-cased /
  mis-punctuated ⇒ **FAIL** (with the specific deviation reported). The bold
  styling is `flag-REVIEW` only (OCR cannot reliably recover bold from a photo).

---

## 7. Out of scope: font / dimension size

**The POC does not verify type size or physical dimensions of any label element**
(including the §7.53 minimum type sizes for malt-beverage mandatory information and
the §16.22 warning type sizes).

**Rationale:**

- Type-size compliance is specified in **millimeters** (beer: §7.53 — generally
  ≥ 2 mm for containers > ½ pint, ≥ 1 mm for ≤ ½ pint), but absolute mm cannot be
  reliably recovered from a photograph without a known physical scale reference
  (pixels → mm). See
  [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §3.
- This mirrors **TTB's own COLA Online disclaimer**: label approval does **not**
  test dimensions or font size — the applicant certifies (under perjury signature
  on Form 5100.31) that the label complies. The POC adopts the same posture.
- Attempting it would produce unreliable verdicts and false rejections, which
  contradicts the "recommend, don't decide" principle.

Where a size requirement is regulatorily relevant (e.g. the §7.53 minimums or the
§16.22 warning table), it is **documented for reference** but **not machine-
verified**. This limitation is restated in [`approach.md`](./approach.md) and the
tradeoffs/limitations doc.

---

## Related documents

- [`label-requirements-by-type.md`](./label-requirements-by-type.md) — cross-type
  (beer / wine / spirits) requirements comparison and the full ABV-trap table.
- [`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md)
  — sibling deep ruleset for distilled spirits (incl. the full Government Warning
  verification write-up in its §5).
- [`regulatory-rules-wine.md`](./regulatory-rules-wine.md) — sibling deep ruleset
  for wine.
- [`approach.md`](./approach.md) — how these rules drive the advisory engine
  (verdicts, check types, OCR/LLM strategy).
- [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) — verified
  findings (§1 cross-type CFR rules, §2 warning, §3 font, §4 multi-label).
- [`../ref-docs/malt-beverage-labeling-checklist.pdf`](../ref-docs/malt-beverage-labeling-checklist.pdf)
  — TTB *Checklist of Mandatory Label Information — Malt Beverage*, the **primary
  "what TTB reviews" source** for this ruleset.
- [`../ref-docs/27 CFR Part 7.pdf`](../ref-docs/27%20CFR%20Part%207.pdf) — the local
  authoritative 27 CFR Part 7 PDF (eCFR text), the **underlying regulation** for the
  CFR citations in this ruleset.
- [`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf) — the local
  27 CFR Part 16 PDF (Government Warning: §16.21 text, §16.22 type-size).
