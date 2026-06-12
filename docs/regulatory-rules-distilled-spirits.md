# Regulatory Rules — Distilled Spirits Label Review

*An easy-to-read review ruleset for distilled spirits (DS) labels, derived
from TTB's own mandatory-label checklist and the underlying CFR. This is the
authoritative rule reference for the POC's advisory compliance engine.*

**Scope:** This document covers **distilled spirits** (27 CFR Part 5 + the Part 16 health
warning). Wine and beer are first-class too, each with its own ruleset
([wine](./regulatory-rules-wine.md) · [beer](./regulatory-rules-beer.md)); see
[`label-requirements-by-type.md`](./label-requirements-by-type.md) for the cross-type
comparison and [`approach.md`](./approach.md) for how these rules are operationalized.
The class/type chart in [`ref-docs/chapter4.pdf`](../ref-docs/chapter4.pdf) (TTB BAM Vol. 2,
Ch. 4 — Class & Type Designation, 04/2007) is the **enumerated catalog of valid spirits
classes and types** (whisky/bourbon/rye, gin, brandy, rum, tequila, the liqueur list,
recognized cocktails, specialties), with the "sufficient as a class and type designation"
flags. **The class/type-validity check** (the *hybrid* rules+LLM check in the mandatory-elements
table below) can be **seeded from this chart as an "allowed designations" lookup**, making the
check more deterministic and reducing LLM reliance. *(2007 vintage — cross-check against current
27 CFR Part 5 Subpart I for post-2022 additions such as American Single Malt Whisky.)*

---

## 1. Source authority

These rules are taken from TTB's own published guidance as the **primary** source,
with the CFR cited for each element.

| Source | Role | File / citation |
|---|---|---|
| TTB *Checklist of Mandatory Label Information — Distilled Spirits* | **Primary** authoritative ruleset (post-2022 renumbering) | [`../ref-docs/ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf) |
| 27 CFR Part 5 | Distilled spirits labeling regulation | [`../ref-docs/27 CFR Part 5.pdf`](../ref-docs/27%20CFR%20Part%205.pdf) |
| 27 CFR Part 16 | Health (Government) Warning — exact text + type-size table | Cross-referenced by Part 5; verified against the local PDF [`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf) (originally cross-checked against the eCFR mirror, see [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §2) |
| Domain research report | Regulatory-requirements synthesis | [`../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md`](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md) |

> **Renumbering note.** Section numbers reflect the **post-2022** reorganization of
> 27 CFR Part 5, exactly as printed on the TTB checklist PDF. The class/type
> designation now lives at **§5.141** (with the designation rules at **§5.165**),
> not the older §5.35. Use the citations in this document, not pre-2022 ones.

### Core POC principle — "recommend, don't decide"

The engine emits an **advisory verdict** for each label — **PASS / REVIEW / FAIL**.
It never issues a disposition. The human **Label Specialist** reviews the findings and
issues the official TTB **disposition** — **Approved / Needs Correction /
Rejected**. "REVIEW" is an engine signal (a check the software cannot confirm
deterministically), not a disposition. See
[`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §7 and
[`approach.md`](./approach.md).

---

## 2. The "same field of vision" rule (§5.63)

> *A label or labels bearing the **brand name**, **alcohol content**, and
> **class/type designation** must appear in the **same field of vision**.*
> — TTB DS checklist, citing **27 CFR 5.63**

**What "same field of vision" means** (per the checklist): a **single side of the
container** where all of these pieces of information can be viewed
**simultaneously without turning the container**. For a cylindrical container, a
"side" is **40 percent of the circumference**.

**The three elements that must co-locate:**

1. Brand name (§5.64)
2. Class/type designation (§5.141 / §5.165)
3. Alcohol content (§5.65)

**What the Label Specialist checks:** that all three appear together on one viewable
face — typically the brand/front label. Net contents, name & address, and the
health warning may appear on *any* affixed label (§5.63(b)) and are **not**
constrained to the same field of vision.

**POC check type — `flag-REVIEW` (positional).** Determining whether three OCR
text regions fall within one 40%-of-circumference face requires reliable spatial /
per-image grouping that OCR bounding boxes alone cannot guarantee from photos. The
engine confirms the three elements are **present** (deterministically / via field
match) and flags the *co-location* requirement for the Label Specialist to eyeball on
the rendered label. See "positional checks" in [`approach.md`](./approach.md).

---

## 3. Always-mandatory elements

These must appear on **every** distilled spirits label. The "POC check type"
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
| **Brand name** | Present; appears in same field of vision with alcohol content + class/type; **matches the "Brand Name" application field** | **§5.64** | **field-match (app ↔ OCR)** + co-location `flag-REVIEW` |
| **Class/type designation** | Present; in same field of vision; consistent with a class/type listed in the regs (or a valid trade-understanding / fanciful-name-plus-statement-of-composition designation); separate & apart; spelled correctly; no conflicting designations across labels; formula selected if required | **§5.141** (designation must appear) / **§5.165** (how it's designated) | **hybrid** (presence/field-match deterministic; class/type *validity* + formula judgment `flag-REVIEW`) |
| **Alcohol content** | Stated in same field of vision; acceptable format/abbreviations (`Alc.`, `Alc`, `Vol.`, `Vol`, `%`); if proof is also shown it is distinguished (parens/brackets) from the mandatory % ABV and in the same field of vision | **§5.65** | **hybrid** (presence + ABV-format regex deterministic; value vs. application field `field-match`; ±0.3-pt tolerance per Research-Findings §1) |
| **Net contents** | Present on the label (or blown/marked into the container); acceptable format/abbreviation (e.g. `500 mL`, `1.5 L`); meets an approved (metric) standard of fill | **§5.70 / §5.203** | **hybrid** (presence + format deterministic; standard-of-fill value `field-match`/`flag-REVIEW`) |
| **Name & address** | Name (or trade name) + address (city, state) present; immediately follows a permitted responsibility phrase (e.g. `Bottled By`, `Imported By`) with no intervening text | **§5.66 / §5.67 / §5.68** | **hybrid** (presence + responsibility-phrase regex deterministic; address validity `flag-REVIEW`) |
| **Health (Government) Warning** | Present; **exact** wording & punctuation; `GOVERNMENT WARNING` in caps + bold; `S` in Surgeon and `G` in General capitalized; one statement; separate & apart | **27 CFR Part 16** (§16.21 text, §16.22 type-size) | **deterministic** — see §5 below |

> **ABV is always required for spirits.** Unlike beer (usually optional) and table
> wine (only required above 14%), §5.65 requires an ABV statement on **every**
> distilled spirits label. Proof is an *optional addition*, never a substitute.
> See [`label-requirements-by-type.md`](./label-requirements-by-type.md).

---

## 4. Conditional elements (triggered)

These are mandatory **only when their trigger condition is met**. Because the POC
generally cannot independently know the underlying fact (e.g. whether sulfites are
actually present, or the spirit was wood-treated), most conditional checks are
**`flag-REVIEW`**: the engine surfaces the trigger question and, where the label
text itself is the evidence (e.g. an import implying country-of-origin), checks for
the presence/format of the required statement.

| Element | Trigger condition | Required statement (example) | Citation | POC check type |
|---|---|---|---|---|
| **Country of origin** | Imported distilled spirits only | Country-of-origin statement complying with CBP rules | **§5.69** + **19 CFR 134.11** | **flag-REVIEW** (CBP-governed; presence check if import indicated) |
| **Sulfite declaration** | Product contains ≥ 10 ppm total sulfur dioxide | `Contains Sulfites` | **§5.63(c)(7)** | **flag-REVIEW** (presence detectable; trigger not knowable from label) |
| **Presence of coloring materials** | Certain coloring materials used | `Colored With Caramel`, `Artificially Colored`, or `certified color added` (in statement of composition or separate disclosure) | **§5.63(c)(6)** | **flag-REVIEW** |
| **FD&C Yellow #5** | FD&C Yellow #5 used | `Contains FD&C Yellow #5` (specific disclosure) | **§5.63(c)(5)** | **flag-REVIEW** (presence detectable deterministically) |
| **Cochineal extract / carmine** | Cochineal extract or carmine used | `Contains Cochineal Extract` / `Contains Carmine` (specific disclosure) | **§5.63(c)(6)** | **flag-REVIEW** (presence detectable deterministically) |
| **Treatment with wood** | Whisky/brandy treated with wood other than via oak-container contact (narrow oak-chip brandy exception ≤ 2.5% by vol.) | `Colored and flavored with wood ____` (chips, slabs, extracts) | **§5.73** | **flag-REVIEW** |
| **Commodity statement (neutral spirits present)** | Spirits (other than cordials/liqueurs/specialties) made by blending or rectification using neutral spirits | `50% Neutral Spirits Distilled From Corn` (% + commodity) | **§5.71** | **flag-REVIEW** |
| **Commodity statement (neutral spirits or gin)** | Neutral spirits / gin made by continuous distillation | `Distilled from Potato` (commodity) | **§5.71** | **flag-REVIEW** |
| **State of distillation** | Certain U.S. whiskies, where whisky is **not** distilled in the state given in the label address | `Distilled in Idaho` / `Idaho Corn Whisky` | **§5.66(f)** | **flag-REVIEW** |
| **Statement of age** | Whisky aged < 4 yrs; grape lees/pomace/marc brandy aged < 2 yrs; certain misc. age references; or a distillation date is shown | `3 Years Old`; `Aged not less than 6 months` | **§5.74** (see FAQ S11) | **hybrid** (approved-format regex deterministic; trigger `flag-REVIEW`) |

**Approved age-statement formats** (§5.74) the engine recognizes as valid:

- `____ years old`
- `____ months old`
- `Aged ____ years`
- `Aged at least ____ years`
- `Aged a minimum of ____ months`
- `Over ____ years old`
- `Aged not less than ____ years`
- `___% whisky aged __ years; __% whisky aged ___ years`

---

## 5. Government Warning verification approach

*(This section satisfies the discussion-points §7 request for a "Government Warning
check write-up." It is the single most rule-bound check in the POC — and it is
**fully deterministic**, requiring no LLM.)*

### 5.1 Exact mandated text (§16.21)

The statement must appear **exactly** as prescribed:

> **GOVERNMENT WARNING:** (1) According to the Surgeon General, women should not
> drink alcoholic beverages during pregnancy because of the risk of birth defects.
> (2) Consumption of alcoholic beverages impairs your ability to drive a car or
> operate machinery, and may cause health problems.

*(Verified against the local [`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf)
§16.21; originally cross-checked against the eCFR mirror, 2026-06-09 — see
[`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §2.)*

### 5.2 Formatting rules

From the TTB DS checklist (Health Warning row) and §16.21:

- The words **`GOVERNMENT WARNING`** must be in **capital letters and bold type**;
  the remainder of the statement is **not** bold.
- The **`S`** in *Surgeon* and the **`G`** in *General* are **capitalized**.
- It must appear as **one statement**.
- It must be **separate and apart** from all other label information.

### 5.3 Type-size table (§16.22)

Keyed to container volume (verified against the local Part 16 PDF):

| Container volume | Min. type size | Max. characters per inch |
|---|---|---|
| ≤ 237 mL (8 fl oz) | **1 mm** | 40 |
| > 237 mL to 3 L | **2 mm** | 25 |
| > 3 L | **3 mm** | 12 |

> The **minimum type size** and characters-per-inch are dimensional requirements.
> Consistent with the font/dimension out-of-scope decision (§6), the POC does
> **not** verify the §16.22 measurements; the table is documented here for
> completeness and for the Label Specialist's reference.

### 5.4 How the POC verifies the warning (deterministic)

The engine treats the warning as an **exact / normalized string match**, run as a
deterministic regex pipeline against the OCR-extracted label text:

1. **Locate** the warning block by anchoring on the `GOVERNMENT WARNING:` token.
2. **Caps + bold token check.** Require the literal `GOVERNMENT WARNING:` token in
   all-caps. (Bold is a styling attribute OCR cannot reliably recover from a photo;
   the caps form is enforced deterministically, and the bold requirement is noted
   for Label Specialist confirmation — `flag-REVIEW` on the visual styling only.)
3. **Body wording check.** Normalize **whitespace** (collapse runs of spaces /
   line breaks) and **case** for the *body* of the statement, then require an
   **exact wording + punctuation match** against the §16.21 text — including the
   `(1)` and `(2)` segment markers and the `Surgeon General` capitalization.
4. **One statement / separate & apart.** Confirm the body is a single contiguous
   block (no foreign text interleaved between the two numbered clauses).
5. **Verdict.** Exact match ⇒ **PASS**; absent ⇒ **FAIL**; present but reworded /
   mis-cased / mis-punctuated ⇒ **FAIL** (with the specific deviation reported).

**Why deterministic.** The required wording is fixed by regulation, so creative
deviations — smaller font, title case, paraphrase, omitted clause — are caught
reliably by a string/regex comparison. No LLM is involved or needed for this
check.

---

## 6. Out of scope: font / dimension size

**The POC does not verify type size or physical dimensions of any label element**
(including the §5.53 minimum type sizes and the §16.22 warning type sizes).

**Rationale:**

- Type-size compliance is specified in **millimeters**, but absolute mm cannot be
  reliably recovered from a photograph without a known physical scale reference
  (pixels → mm). See [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §3.
- This mirrors **TTB's own COLA Online disclaimer**: label approval does **not**
  test dimensions or font size — the applicant certifies (under perjury signature
  on Form 5100.31) that the label complies. The POC adopts the same posture.
- Attempting it would produce unreliable verdicts and false rejections, which
  contradicts the "recommend, don't decide" principle.

Where a size requirement is regulatorily relevant (e.g. the §16.22 table above),
it is **documented for reference** but **not machine-verified**. This limitation is
restated in [`approach.md`](./approach.md) and the tradeoffs/limitations doc.

---

## Related documents

- [`label-requirements-by-type.md`](./label-requirements-by-type.md) — cross-type
  (beer / wine / spirits) requirements comparison.
- [`approach.md`](./approach.md) — how these rules drive the advisory engine
  (verdicts, check types, positional checks, OCR/LLM strategy).
- [`../ref-docs/ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf)
  — TTB primary source.
- [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) — verified
  findings (§1 CFR rules, §2 warning, §3 font, §4 multi-label).
