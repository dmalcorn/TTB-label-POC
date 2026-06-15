# Cover Note — Take-Home Submission

*The submission summary for this take-home — the text used in the submission form's
summary field. A one-page orientation to the deliverable and how it meets the brief.*

---

**TTB COLA Label Verification — Take-Home Submission**

- **Repository:** https://github.com/dmalcorn/TTB-label-POC
- **Live app:** https://ttb-label-poc-production.up.railway.app (opens straight to the review queue — no login)

A **federal reviewer's workspace** for COLA label review. It pulls a mock application + its label image, runs automated checks in the background, and presents advisory findings so a Label Specialist can review and decide faster. Guiding principle: **recommend, don't decide** — the engine flags `PASS`/`REVIEW`/`FAIL` per element; the human records the official disposition.

**How it meets the brief's core:**

- **Label↔application matching** — brand, ABV, and the **Government Warning** (deterministic, exact: enforces the all-caps "GOVERNMENT WARNING:" wording — catches the title-case/reworded cases Jenny described). Brand matching is normalization-based, so "STONE'S THROW" = "Stone's Throw" (Dave's nuance).
- **~5-second response** — OCR + compliance run in **background jobs at submission time**, so the review screen is a pre-computed read that renders instantly (directly answering the abandoned 30–40s pilot).
- **Dead-simple UX** — USWDS, single "Next Submission" action, stacked comparison, visible checklist.
- **Firewall-safe** — provable **zero-egress** OCR-only path (Tesseract/PaddleOCR + OpenCV local; LLM layer optional and off by default; verified with `docker run --network none`).
- **Batch** — reframed as applicant-side (300 apps → 300 queued items), with a live enqueue op.

**Beyond the brief (procurement angle):** multi-OCR + multi-LLM benchmarking with **cost-per-1,000** and a `/benchmark` report; OpenCV image enhancement for imperfect photos; all three beverage types (spirits/wine/beer) with CFR-sourced rulesets.

**Setup, approach, tools, assumptions, and trade-offs** are in the README + `docs/`. `docs/requirements-mapping.md` traces every requirement to the proving code + tests. Full suite green (800 tests); no PII (synthetic/seeded data only).
