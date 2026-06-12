# Mandatory Label Requirements by Beverage Type — Beer / Wine / Spirits

> **Purpose.** A definitive, Label Specialist-facing reference for the *mandatory* (and
> key conditional) label elements TTB requires, across all three beverage types the
> COLA process covers: **beer / malt beverages (27 CFR Part 7)**, **wine (27 CFR
> Part 4)**, and **distilled spirits (27 CFR Part 5)**. The review UI must let the
> agent instantly see the beverage type, because the required checks differ by type
> ([discussion-points §9](../ref-docs/discussion-points.md)). This document is the
> single source the rules engine and the human Label Specialist share for "what does
> *this* type require?"
>
> **Scope decision (2026-06-11).** **All three beverage types are first-class** — each has
> its own check-by-check review ruleset:
> **[spirits](./regulatory-rules-distilled-spirits.md)** ·
> **[wine](./regulatory-rules-wine.md)** · **[beer](./regulatory-rules-beer.md)**. This
> document is the cross-type comparison; distilled spirits is the most fully worked example
> ([discussion-points §7](../ref-docs/discussion-points.md)).

**Sources (ground truth, local — no outbound calls):**
- [`ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) §1 — cross-type mandatory-elements table
- [`ref-docs/discussion-points.md`](../ref-docs/discussion-points.md) §7, §9 — scope & requirements-list request
- [`_bmad-output/.../domain-...-research-2026-06-11.md`](../_bmad-output/planning-artifacts/research/domain-ttb-cola-distilled-spirits-label-compliance-and-adjudication-research-2026-06-11.md) — Regulatory Requirements section, cross-type divergence
- [`ref-docs/ds-labeling-checklist.pdf`](../ref-docs/ds-labeling-checklist.pdf) — TTB's authoritative spirits checklist
- [`ref-docs/27 CFR Part 5.pdf`](../ref-docs/27%20CFR%20Part%205.pdf) — distilled spirits regulation

> **Citation caveat.** All Part 5 (spirits) section numbers reflect the **post-2022
> modernization renumbering** of 27 CFR Part 5. Older articles and checklists may use
> the pre-2022 numbers, which are now wrong. CFR citations should be stored as
> versioned data, not hard-coded.

---

## ⚠️ The Cross-Type ABV Trap — read this first

> **The single most important cross-type subtlety: the alcohol-content (ABV) rule is
> DIFFERENT in all three beverage types.** This is the **#1 false-reject risk** in the
> whole engine.
>
> | Type | ABV rule | Citation |
> |---|---|---|
> | **Distilled spirits** | **ALWAYS required.** ABV (% by volume) is mandatory. Proof is *optional* and, if shown, is an addition — proof alone is **not** sufficient. | § 5.65 |
> | **Beer / malt beverages** | **Usually OPTIONAL.** Mandatory *only* when the beer contains alcohol from added nonbeverage flavors other than hops extract. | § 7.65 / § 7.63(a)(3) |
> | **Wine** | **Required only if > 14% ABV.** At ≤ 14% it is optional *if* the label instead carries "table wine" / "light wine". | § 4.36 |
>
> **Why this matters:** a naive *"ABV must always be present"* check — the obvious
> first implementation — produces **false rejections on beer and on table wine**, two
> entirely compliant cases. The engine must branch on beverage type *before*
> evaluating ABV presence. When in doubt, prefer a **REVIEW** verdict over a hard
> FAIL so a human confirms. (See [Research-Findings.md §1](../ref-docs/Research-Findings.md);
> domain research, cross-type divergence.)
>
> **Tolerances also differ:** spirits ± 0.3 pts (§ 5.65); beer ± 0.3 pts (§ 7.65(c));
> wine ± 1.0 pt above 14% and ± 1.5 pts at ≤ 14% (§ 4.36).

---

## 1. Master Comparison Table — mandatory label elements

Legend: **R** = required · **O** = optional · **C** = conditional (required only when a
trigger is met). Each cell carries its CFR section citation.

| Element | Beer — Part 7 | Wine — Part 4 | Distilled Spirits — Part 5 |
|---|---|---|---|
| **Brand name** | **R** — § 7.64 | **R** — § 4.33 | **R** — § 5.64 |
| **Class / type designation** | **R** — § 7.63(a)(2), Subpart I | **R** — § 4.34 *(table/dessert wine exempt from a class designation)* | **R** — § 5.141 (also § 5.165) |
| **Alcohol content (ABV)** | **C — usually O** — § 7.65; mandatory only if added nonbeverage flavor (§ 7.63(a)(3)) | **C — R if > 14%** — § 4.36; O at ≤ 14% if "table"/"light" shown | **R — ALWAYS** — § 5.65 *(proof optional, not a substitute)* |
| **Net contents** | **R** — § 7.70 | **R** — § 4.37 | **R** — § 5.70 (standards of fill § 5.203) |
| **Name & address** | **R** — §§ 7.66–7.68 | **R** — § 4.35 | **R** — §§ 5.66–5.68 |
| **Country of origin** *(imports only)* | **C** — CBP 19 CFR 102/134 (§ 7.69) | **C** — 19 CFR 134.11 (CBP) *(CBP, not TTB, governs country of origin)* | **C** — CBP 19 CFR 102/134 (§ 5.69) |
| **Government Warning** | **R** *(≥ 0.5% ABV)* → 27 CFR Part 16 | **R** → 27 CFR Part 16 | **R** → 27 CFR Part 16 |
| **Sulfite declaration** *(≥ 10 ppm SO₂)* | **C** — § 7.63(b)(3) | **C** — § 4.32(e) | **C** — § 5.63(c)(7) |
| **FD&C Yellow No. 5** *(if used)* | **C** — § 7.63(b) | **C** — § 4.32(c)–(e) | **C** — § 5.63(c)(5) |
| **Cochineal / carmine** *(if used)* | **C** — § 7.63(b) | **C** — § 4.32(c)–(e) | **C** — § 5.63(c)(6) |
| **Coloring materials** *(if used)* | — *(no separate general coloring disclosure for malt beverages; § 7.63(b) is the exhaustive disclosure list)* | C — § 4.32(c) | **C** — § 5.63(c)(6) |
| **Aspartame disclosure** *(if used)* | **C** — § 7.63(b) *("PHENYLKETONURICS: CONTAINS PHENYLALANINE", all caps)* | (rare) | (rare) |
| **Appellation of origin** | n/a | **C** — § 4.34(b), triggered by varietal/vintage/semi-generic | n/a |
| **Commodity / neutral-spirits statement** | n/a | n/a | **C** — § 5.71 |
| **Statement of age** | n/a | n/a | **C** — § 5.74 (e.g., whisky aged < 4 yrs, not bottled-in-bond) |
| **Treatment with wood** | n/a | n/a | **C** — § 5.73 |
| **State of distillation** | n/a | n/a | **C** — § 5.66(f) (certain U.S. whiskies) |
| **Standards of fill** *(approved sizes)* | none mandatory | **R** — § 4.72 (set of authorized sizes incl. 750 mL) | **R** — § 5.203 (incl. 750 mL) |
| **Government Warning — exact text & format** | per § 16.21 (text) / § 16.22 (type size) | per § 16.21 / § 16.22 | per § 16.21 / § 16.22 |

> **Government Warning text (27 CFR § 16.21, verified):** `GOVERNMENT WARNING:` must be
> **all caps and bold**; the rest is not bold; the statement is separate and apart from
> other text. Treat as a deterministic exact/normalized match — no LLM needed. Full
> text and the volume-keyed type-size table are in
> [Research-Findings.md §2](../ref-docs/Research-Findings.md).
>
> **Part 16 note:** 27 CFR Part 16 is now in the local PDF set as
> [`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf) (the three
> other CFR parts cross-reference it). The § 16.21/§ 16.22 details above were originally
> cross-checked against the eCFR mirror (2026-06-09) and are now verified against the
> local Part 16 PDF — the offline rule set is complete.

---

## 2. Per-type subtleties

### 2a. Beer / malt beverages (Part 7)

- **ABV is usually optional** — mandatory only when the beer's alcohol comes from
  added nonbeverage flavors other than hops extract (§ 7.63(a)(3)); otherwise the
  brewer may omit it. Tolerance ± 0.3 pts (§ 7.65(c)). *(This is half of the
  cross-type ABV trap above.)*
- **Conditional ingredient disclosures** drive most beer-specific checks: FD&C
  Yellow No. 5, cochineal/carmine, sulfites ≥ 10 ppm, and aspartame
  (`PHENYLKETONURICS: CONTAINS PHENYLALANINE`, all caps) — § 7.63(b).
- **No mandatory standards of fill** for malt beverages — net-contents value is
  required but is not constrained to an approved-size table the way wine and spirits
  are.

### 2b. Wine (Part 4)

Applies to wine **7%–24% ABV** (§ 4.6).

- **ABV required if > 14%**; optional at ≤ 14% *only if* "table wine" or "light wine"
  appears on the label (§ 4.36). Tolerances: ± 1.0 pt (> 14%), ± 1.5 pts (≤ 14%).
  *(The other half of the cross-type ABV trap.)*
- **Appellation / varietal / vintage triggers.** An **appellation of origin** becomes
  *mandatory* once the label makes certain claims (§ 4.34(b)). The triggering claims
  carry their own percentage thresholds:
  - **Varietal** (grape-variety name): ≥ 75% of that grape (§ 4.23).
  - **Vintage** (year): ≥ 95% from that year for AVA appellations / ≥ 85% non-AVA (§ 4.27).
  - **AVA appellation**: ≥ 85% from the named area (§ 4.25).
- **Standards of fill:** wine must be in one of the authorized container sizes
  (§ 4.72), e.g., 750 mL.
- **Sulfite declaration** at ≥ 10 ppm (§ 4.32(e)) is the most common conditional.
- **Multi-label distribution** (§ 4.32): brand name + class/type + foreign-wine
  percentage must be on the *brand label*, but name/address, net contents, ABV,
  sulfites, etc. may sit on *any* affixed label — so the engine must check elements
  across the **union of all uploaded images**, not demand them all on one image
  ([Research-Findings.md §4](../ref-docs/Research-Findings.md)).

### 2c. Distilled spirits (Part 5) — the deep focus

- **The "same field of vision" rule (§ 5.63) is the structural keystone.** Three
  elements must appear **together in one field of vision** (a single side of the
  container, viewable without turning it — for a cylinder, ≤ ~40% of the
  circumference): **brand name + class/type designation + alcohol content (ABV)**.
  The other mandatory items (name/address, net contents) may appear on *any* label.
  This is a known hard case for the engine: OCR gives text + bounding boxes per image,
  so co-location must be inferred, not just presence.
- **ABV always required** (§ 5.65), stated as % by volume; **proof is optional** and,
  if shown, must be distinguished (e.g., parentheses) and sit in the same field of
  vision. Tolerance ± 0.3 pts. *(Anchor case of the cross-type ABV trap.)*
- **Standards of fill (§ 5.203):** net contents must meet an approved metric size
  (e.g., 750 mL). Deterministic table lookup.
- **Spirits-only conditional statements** (each mandatory only when its trigger fires):
  - **Commodity / neutral-spirits statement** — § 5.71 (blended/rectified spirits with
    neutral spirits; gin via continuous distillation).
  - **Statement of age** — § 5.74 (whisky aged < 4 yrs and not bottled-in-bond; certain
    brandy < 2 yrs; any age/distillation-date reference). Approved phrasings enumerated.
  - **State of distillation** — § 5.66(f) (certain U.S. whiskies not distilled in the
    state of the label's address). Note: "Kentucky Straight Bourbon Whiskey" — "Kentucky"
    can simultaneously satisfy this for whisky.
  - **Treatment with wood** — § 5.73 (whisky/brandy wood-treated other than by oak
    containers; brandy/oak-chip exception ≤ 2.5% vol).
  - **Coloring / FD&C Yellow #5 / cochineal-carmine** — § 5.63(c)(5)–(6).
- **Worked example — the brief's sample label** ("OLD TOM DISTILLERY" / "Kentucky
  Straight Bourbon Whiskey" / "45% Alc./Vol. (90 Proof)" / "750 mL"): it has brand,
  class/type, ABV (+ optional proof), and net contents — but is **missing the
  name-and-address statement (§ 5.66) and the Government Warning (Part 16)**, so it is
  itself a **FAIL** test fixture ([Research-Findings.md §1](../ref-docs/Research-Findings.md)).

For the full element-by-element spirits ruleset (verdict logic, deterministic-vs-LLM
classification per check, field-match strategy), see the companion
**[regulatory-rules-distilled-spirits.md](./regulatory-rules-distilled-spirits.md)**.

---

## Notes on font / type-size

Type-size minimums exist for every type (beer § 7.53, wine § 4.38, spirits § 5.53,
warning § 16.22) in **millimeters**, but **absolute mm cannot reliably be derived from a
photo** without a physical scale reference. Per project decision, **font sizes are NOT
checked** in the POC; this is documented as a known limitation
([discussion-points §7](../ref-docs/discussion-points.md);
[Research-Findings.md §3](../ref-docs/Research-Findings.md)).

---

## Open items / TODO

- **DONE:** The companion deep ruleset
  [`regulatory-rules-distilled-spirits.md`](./regulatory-rules-distilled-spirits.md)
  exists on disk (cross-linked throughout).
- **RESOLVED:** Part 7 has **no** separate general **coloring-material** disclosure for
  malt beverages — § 7.63(b) is the exhaustive ingredient-disclosure list (per
  [`regulatory-rules-beer.md`](./regulatory-rules-beer.md) §4).
- **DONE:** 27 CFR Part 16 is now local at
  [`../ref-docs/27 CFR Part 16.pdf`](../ref-docs/27%20CFR%20Part%2016.pdf); the
  Government Warning text and type-size table are verified against it.
- **TODO:** Verify whether any additional Part 4 conditional disclosures (e.g.,
  saccharin, specific health-related statements) belong in the master table for parity
  with Parts 5 and 7.
