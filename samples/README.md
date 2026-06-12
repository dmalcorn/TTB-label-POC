# Sample Labels & Seed Data

This folder holds the **label images** and the **ground-truth field data** used to seed the
mock COLA database and to score the OCR/LLM benchmark. It directly serves the
discussion-points request (§11) for a folder of sample labels plus a CSV of the
corresponding field information.

## Folder layout

```
samples/
├── README.md            ← this file (sourcing guide + conventions)
├── seed-template.csv    ← ground-truth field data, one row per submission
└── images/              ← label image files referenced by the CSV (create as needed)
```

## `seed-template.csv` — the ground truth

Each row is one submission, with the *correct* values for every label element plus the
**expected engine verdict** (`PASS` / `REVIEW` / `FAIL`) and expected failure reasons.
This file is dual-purpose:

1. **Seeding** — populates the mock COLA DB with dummy applications (see
   [`../docs/database-schema.md`](../docs/database-schema.md)).
2. **Benchmark ground truth** — the gold standard the OCR/LLM accuracy scoring compares
   extracted text against (see
   [`../docs/ocr-llm-benchmarking-plan.md`](../docs/ocr-llm-benchmarking-plan.md)).

The four seed rows shipped here are deliberately varied: the brief's own sample label as a
known **FAIL**, a compliant import (**PASS**), a same-field-of-vision **REVIEW** case, and
a "creative warning" format **FAIL** — enough to exercise every verdict path.

> **Note on `class_type_designation`:** class/type **is** a maker-entered application field
> (the COLAs Online "Product Class/Type" code — see `../ref-docs/Definition of Terms.txt`),
> so it diffs application ↔ OCR like brand name. The one element with no maker-entered value
> is the **Government Warning**, which is verified from OCR against the fixed 27 CFR §16.21
> text (deterministic; see [`../docs/assumptions.md`](../docs/assumptions.md) A17).

## Where to source real labels

| Source | What it offers | Access |
|---|---|---|
| **TTB Public COLA Registry** | Approved label images, 1999–present; searchable by beverage type, brand, class/type, origin, date | Public, **no login** — [search page](https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do) |
| **data.gov — TTB Public COLA Registry Search & Download** | Bulk COLA records dataset | Public download |
| **Kaggle — "ttb-colas-demo"** (published by COLA Cloud) | A ready-made batch of COLA records/images | Kaggle account |

See [`../docs/presearch.md`](../docs/presearch.md) for the full landscape and citations.

## How to collect *many* labels (not just a handful)

- Search the **Public COLA Registry** filtered to **distilled spirits** over a date range,
  and page through results — each approved COLA exposes its label image(s).
- Prefer the **data.gov / Kaggle bulk sets** to grab hundreds of records at once rather than
  scraping one at a time.
- Aim for **diversity over volume-for-its-own-sake**: include whiskies (age statements),
  vodkas/gins (commodity statements), imports (country of origin), and deliberately
  non-compliant labels so the benchmark has FAIL/REVIEW cases, not just PASS.

## ⚠️ Intellectual-property caveat (important)

COLA **records** are public government data, but the **label artwork is the brand owner's
trademark / trade dress.** Therefore:

- Use registry images as **private, local test fixtures only** — do **not** commit brand
  artwork to the public repo or the deployed demo.
- For anything shown **publicly**, use **synthetic / AI-generated labels** (the brief
  explicitly encourages synthetic labels).
- Keep `samples/images/` out of public distribution if it contains real artwork (add to
  `.gitignore` as appropriate).

See [`../docs/assumptions.md`](../docs/assumptions.md) (A15) and
[`../docs/tradeoffs-and-limitations.md`](../docs/tradeoffs-and-limitations.md).
