# Cover Note — Take-Home Submission

*The submission summary for this take-home — the text used in the submission form's
summary field. A one-page orientation to the deliverable and how it meets the brief.*

---

**TTB COLA Label Verification — Take-Home Submission**

- **Repository:** https://github.com/dmalcorn/TTB-label-POC
- **Live app:** https://ttb-label-poc-production.up.railway.app (opens straight to the review queue — no login)

A **federal reviewer's workspace** for COLA label review. It pulls a mock application + its label image, runs automated checks in the background, and presents advisory findings so a Label Specialist can review and decide faster. Guiding principle: **recommend, don't decide** — the engine flags `PASS`/`REVIEW`/`FAIL` per element; the human records the official disposition.

**How it meets the brief's core:**

- **Two readings of every element — OCR and AI, side by side.** Each label is read independently by the OCR engines (Tesseract + PaddleOCR) **and** an AI vision model (`gpt-4o-mini`); each card shows an *On label (OCR)* row and an *On label (AI)* row, with an **agreement-based** verdict (agree ⇒ PASS, conflict ⇒ REVIEW, both wrong ⇒ FAIL). The AI reads the image only — never OCR text — so the two genuinely cross-check, and either can be toggled off.
- **Label↔application matching** — the seven required elements (brand, class/type, ABV, net contents, name/address, country of origin, **Government Warning**). The warning match is **deterministic and exact** (enforces the all-caps "GOVERNMENT WARNING:" wording — catches the title-case/reworded cases Jenny described); brand matching is normalization-based, so "STONE'S THROW" = "Stone's Throw" (Dave's nuance).
- **~5-second response** — OCR + AI + compliance run in **background jobs at submission time**, so the review screen is a pre-computed read that renders instantly (**~0.15 s measured** on the deployed demo — directly answering the abandoned 30–40s pilot).
- **Dead-simple UX** — USWDS, single "Next Submission" action, stacked comparison, visible checklist.
- **Firewall-safe** — the OCR + rules path is **provably zero-egress** (`LLM_ENABLED=false`, verified with `docker run --network none`); the AI reading is an optional enhancement that in production points at an **in-firewall** model endpoint via `LLM_BASE_URL`. The live demo runs **AI ON** (cloud `gpt-4o-mini` standing in) so the feature is visible.
- **Batch** — reframed as applicant-side (300 apps → 300 queued items), with a live enqueue op.

**Beyond the brief (procurement angle):** the OCR-vs-AI head-to-head doubles as a **procurement bake-off** — a `/benchmark` report scores each engine, with **measured cost ≈ $0.01 per label** (`gpt-4o-mini`; ~$0.15 for the 15-record corpus). OpenCV image enhancement for imperfect photos; all three beverage types (spirits/wine/beer) with CFR-sourced rulesets; a 15-record corpus harvested from the **real public COLA registry**, including one engineered ABV mismatch to demonstrate a `FAIL`.

**Setup, approach, tools, assumptions, and trade-offs** are in the README + `docs/`. `docs/requirements-mapping.md` traces every requirement to the proving code + tests. Full suite green (836 tests); no PII (synthetic/seeded data only).
