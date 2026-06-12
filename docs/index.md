# Documentation Index

Planning and design documentation for the **TTB COLA Label Specialist proof-of-concept**.
These docs were distilled from the requirements register
([`../ref-docs/discussion-points.md`](../ref-docs/discussion-points.md)), the take-home brief,
and the domain research. Implementation-dependent choices are marked `TODO` with a
recommendation.

## Start here

- [`requirements-mapping.md`](requirements-mapping.md) — what the take-home **requires**
  (mandatory) vs. the **above-and-beyond** features added, plus the project goals.
- [`approach.md`](approach.md) — the central design: architecture, the pre-compute pipeline,
  the verification engine, processing states, Python-vs-Bash, and phasing.

## Regulatory & compliance

- [`regulatory-rules-distilled-spirits.md`](regulatory-rules-distilled-spirits.md) — the
  review ruleset for distilled spirits (27 CFR Part 5 + Part 16), including the
  **Government Warning verification approach** and the font-size out-of-scope note.
- [`regulatory-rules-wine.md`](regulatory-rules-wine.md) — the review ruleset for wine
  (27 CFR Part 4), including the >14% ABV rule and appellation/varietal/vintage triggers.
- [`regulatory-rules-beer.md`](regulatory-rules-beer.md) — the review ruleset for malt
  beverages/beer (27 CFR Part 7), including the optional-ABV rule and ingredient disclosures.
- [`label-requirements-by-type.md`](label-requirements-by-type.md) — mandatory label elements
  across beer / wine / spirits side-by-side, with the cross-type ABV trap.

## Data model

- [`database-schema.md`](database-schema.md) — the mock COLA submissions schema (design only).
- [`data-dictionary.md`](data-dictionary.md) — field name / common name / specification /
  definition for every field.

## Engine, tooling & benchmarking

- [`tools-used.md`](tools-used.md) — every tool/library, why chosen, and local-vs-cloud status.
- [`ocr-llm-benchmarking-plan.md`](ocr-llm-benchmarking-plan.md) — multi-OCR / multi-LLM
  benchmark design, accuracy methodology, and the **cost-per-1,000-verifications** framework.
- [`outbound-calls-inventory.md`](outbound-calls-inventory.md) — proof the deployed app makes
  **no firewall-relevant outbound calls**.
- [`image-handling.md`](image-handling.md) — supported image types and the local OpenCV
  enhancement pipeline for imperfect images.

## Experience & process

- [`ux-design-notes.md`](ux-design-notes.md) — the Label Specialist UI: Next-Submission queue,
  vertical stacked comparison, discrepancy highlighting, the checklist feature, the chevron
  status bar, help/KB, and **USWDS compliance statements**.
- [`applicant-workflow-distilled-spirits.md`](applicant-workflow-distilled-spirits.md) — how an
  applicant submits a distilled-spirits COLA in COLAs Online (the data source for the POC).

## Honest framing

- [`assumptions.md`](assumptions.md) — A1–A29, the assumptions the design rests on.
- [`tradeoffs-and-limitations.md`](tradeoffs-and-limitations.md) — design trade-offs and known
  limitations, framed with mitigations.
- [`presearch.md`](presearch.md) — reference materials, comparable software, test-data sources,
  top spirits label errors, and the online-vs-paper volume picture.

## Templates & samples

- [`batch-template.csv`](batch-template.csv) — applicant-side batch-upload template (≤300
  applications, one signature).
- [`../samples/`](../samples/) — sample labels + `seed-template.csv` ground truth + the
  label-sourcing guide.

## Related (outside `docs/`)

- [`../ref-docs/discussion-points.md`](../ref-docs/discussion-points.md) — the decisions/requests register.
- [`../ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md) — verified first-pass findings.
- [`../_bmad-output/planning-artifacts/research/`](../_bmad-output/planning-artifacts/research/) — the domain research report.
