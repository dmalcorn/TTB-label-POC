# Requirements Mapping — TTB COLA Label Review POC

*Traceability document for the take-home project. Maps every mandatory requirement in
the brief to how this proof-of-concept (POC) satisfies it — **with the code and tests
that prove each one** — separates Diane's above-and-beyond additions from the brief's
minimum, and confirms the core "recommend, don't decide" alignment.*

**Author:** Diane · **Drafted:** 2026-06-11 · **Updated:** 2026-06-15

> **Delivery status (2026-06-15).** The POC is **built and deployed**. Every core
> requirement below is **Implemented** with code + tests on disk; the full suite is green
> (**800 tests** — host-side 799 + the OCR-native test that runs only in the container),
> and the app is live (a public, gate-open Railway URL). The Status column reflects that
> shipped reality; the "Evidence" notes point at the proving code/tests so an evaluator can
> verify each claim directly.

**Ground-truth sources:**
- The brief — [`ref-docs/TTB-take-home-instructions.md`](../ref-docs/TTB-take-home-instructions.md)
- Decision register — [`ref-docs/discussion-points.md`](../ref-docs/discussion-points.md)

**Related planning docs:**
- [`docs/approach.md`](approach.md) — overall approach
- [`docs/presearch.md`](presearch.md) — comparable-software landscape
- [`docs/tools-used.md`](tools-used.md), [`docs/assumptions.md`](assumptions.md), [`docs/tradeoffs-and-limitations.md`](tradeoffs-and-limitations.md)
- Existing research: [`ref-docs/Research-Findings.md`](../ref-docs/Research-Findings.md)

---

## 1. Project Goals

The brief is a job-application take-home (see [`ref-docs/TTB-take-home-instructions.md` L1](../ref-docs/TTB-take-home-instructions.md)).
Two goals are explicit in the decision register ([discussion-points §1, L42–46](../ref-docs/discussion-points.md)):

- **Primary goal — complete the take-home and demonstrate the ability to write working
  code using AI.** The success condition that matters: a working, deployed core application
  with clean code. The brief itself states *"A working core application with clean code is
  preferred over ambitious but incomplete features"*
  ([brief L113](../ref-docs/TTB-take-home-instructions.md)).

- **Secondary goal — produce information that could inform a future software project,
  including procurement/purchase decisions.** The brief explicitly invites this framing:
  *"Think of this as a standalone proof-of-concept that could potentially inform future
  procurement decisions"* ([brief L35](../ref-docs/TTB-take-home-instructions.md)). This goal
  justifies the benchmarking/cost-analysis work in §3 — delivered as the `/benchmark` report.

The above-and-beyond work (multi-OCR/multi-LLM benchmarking, cost analysis, tracing) is the
*mechanism* by which the secondary goal is met, and it *demonstrates* the primary goal. The
**Label Specialist-side** (federal-reviewer) framing is the POC's scope thesis, not a third goal.
**Conclusion: two goals, with benchmarking/landscape work serving the secondary goal.**

---

## 2. Mandatory Requirements (from the brief)

The brief grants free choice of stack ([L63](../ref-docs/TTB-take-home-instructions.md)) and
prizes a clean working core over scope ([L113](../ref-docs/TTB-take-home-instructions.md)), so
"mandatory" here means *core functional checks the stakeholders named*, plus the two formal
deliverables and the evaluation criteria. **Status legend:** ✅ Implemented = built, with code +
tests on disk.

### 2A. Core functional requirements

| # | Requirement | Source (brief) | How the POC satisfies it — **Evidence (code · tests)** | Status |
|---|---|---|---|---|
| 1 | **Match label artwork against the application** (the core review action) | Sarah Chen, [L15–17](../ref-docs/TTB-take-home-instructions.md) | OCR/LLM extracts label fields; the review screen stacks each application field with the extracted value beneath it, discrepancies flagged. **Code:** `app/web/review_view.py`, `app/web/routes_review.py`, `templates/review.html`. **Tests:** `tests/test_review_view.py`, `tests/test_review.py`. | ✅ Implemented |
| 2 | **Brand-name match** (the "STONE'S THROW" vs "Stone's Throw" nuance) | [L15](../ref-docs/TTB-take-home-instructions.md), Dave Morrison [L47](../ref-docs/TTB-take-home-instructions.md) | Centralized normalization (case/whitespace/punctuation-insensitive) so the two forms match, surfaced for human confirmation. **Code:** `app/normalize.py`, `app/engine/checks/field_match.py`. **Tests:** `tests/test_normalize.py`, `tests/test_field_match.py`. | ✅ Implemented |
| 3 | **ABV / alcohol-content match** | [L15](../ref-docs/TTB-take-home-instructions.md) | ABV extracted and compared to the application value; format validated. **Code:** `app/engine/checks/field_match.py`, `app/engine/checks/format_checks.py`. **Tests:** `tests/test_field_match.py`, `tests/test_format_checks.py`. | ✅ Implemented |
| 4 | **Government Health Warning — present and exact** (word-for-word; "GOVERNMENT WARNING:" all-caps + bold) | [L15, L57, L77](../ref-docs/TTB-take-home-instructions.md) | Deterministic (no-LLM) exact/normalized check enforcing the all-caps "GOVERNMENT WARNING:" token; catches title-case and reworded warnings (Jenny Park's cases). **Code:** `app/engine/checks/government_warning.py`, `app/engine/rulesets/government_warning.py`. **Tests:** `tests/test_government_warning.py`. | ✅ Implemented |
| 5 | **~5-second performance** ("results back in about 5s or nobody's going to use it") | Sarah Chen, [L19](../ref-docs/TTB-take-home-instructions.md) | **Pre-compute pipeline:** OCR + advisory compliance run in background jobs at submission time, so the review screen is a pure pre-computed DB read and renders instantly. **Code:** `app/pipeline/{run,scheduler,ocr,preprocess}.py`, `processing_ms` metric. **Tests:** `tests/test_pipeline.py`. | ✅ Implemented |
| 6 | **Ease of use for older / mixed tech-comfort users** ("clean, obvious, no hunting for buttons") | Sarah Chen, [L21](../ref-docs/TTB-take-home-instructions.md) | USWDS UI; single "Next Submission" action; vertical stacked comparison; visible checklist; chevron status bar; in-UI help. **Code:** `templates/*.html`, `static/css/brand.css`, `app/web/review_view.py`. **Tests:** `tests/test_shell.py`, `test_queue.py`, `test_review.py`, `test_help_panel.py`, `test_shortcuts.py`. | ✅ Implemented |
| 7 | **Government Warning is the highest-value, trickiest check** | Jenny Park, [L57](../ref-docs/TTB-take-home-instructions.md) | Covered by #4; called out separately because the brief stresses its difficulty. | ✅ Implemented |
| 8 | **Handle the sample distilled-spirits fields** (Brand, Class/Type, ABV, Net Contents, Government Warning) | [L85–91](../ref-docs/TTB-take-home-instructions.md) | Data model + extraction cover these fields; authored spirits ruleset. **Code:** `app/contracts.py`, `app/engine/rulesets/distilled_spirits.py`, `app/db/seed.py` + `fixtures/`. **Tests:** `tests/test_run_checks.py`, `test_seed.py`. | ✅ Implemented |
| 9 | **Operate under federal constraints** (no blocked outbound cloud APIs; no sensitive data stored) | Marcus Williams, [L37, L39](../ref-docs/TTB-take-home-instructions.md) | Provable zero-egress path: local OCR (Tesseract/PaddleOCR) + OpenCV; the LLM layer is config-gated and never constructed when `LLM_ENABLED=false`; documented outbound-call inventory; proven by a `docker run --network none` boot. **Code:** `app/config.py` (`get_llm_adapter`), `docs/outbound-calls-inventory.md`. **Tests:** `tests/test_llm_adapters.py`, `test_config.py`. | ✅ Implemented |

**Wishlist (brief-requested, flagged "would be huge" / "maybe out of scope for a prototype"):**

| # | Requirement | Source (brief) | How the POC addresses it — **Evidence** | Status |
|---|---|---|---|---|
| 10 | **Batch uploads** (importers dump 200–300 at once) | Sarah Chen, [L23](../ref-docs/TTB-take-home-instructions.md) | Reframed as *applicant-side*: 300 apps remain 300 individual submissions the queue feeds one at a time (no Label Specialist-side batch screen). Delivered as a documented `batch-template.csv` **plus a working live-enqueue operation** for demo seeding. **Code:** `app/web/routes_ops.py`, `app/web/ops.py`, `docs/batch-template.csv`. **Tests:** `tests/test_routes_enqueue.py`, `test_routes_ops.py`. | ✅ Implemented |
| 11 | **Imperfect-image handling** (glare, bad angle, poor lighting) | Jenny Park, [L59](../ref-docs/TTB-take-home-instructions.md) ("maybe out of scope") | Local OpenCV pre-processing (denoise, glare/illumination, CLAHE contrast, deskew, perspective) — no LLM/cloud call. **Code:** `app/pipeline/preprocess.py`. **Tests:** `tests/test_preprocess.py`. | ✅ Implemented |

### 2B. Deliverables (formal)

| # | Deliverable | Source (brief) | How the POC satisfies it — **Evidence** | Status |
|---|---|---|---|---|
| D1 | **Source code repository** | [L97–98](../ref-docs/TTB-take-home-instructions.md) | Public Git repo with full source + history. | ✅ Delivered |
| D2 | **README with setup and run instructions** | [L99](../ref-docs/TTB-take-home-instructions.md) | `README.md` — Docker setup/run, offline smoke test, deploy notes, docs index. **Tests:** `tests/test_docs_deliverables.py` enforces setup/run presence + link resolution. | ✅ Delivered |
| D3 | **Brief documentation of approach, tools, assumptions** | [L100](../ref-docs/TTB-take-home-instructions.md) | `docs/approach.md`, `docs/tools-used.md`, `docs/assumptions.md` (+ `tradeoffs-and-limitations.md`, `presearch.md`). | ✅ Delivered |
| D4 | **Deployed application URL** (working prototype reviewers can access and test) | [L101–102](../ref-docs/TTB-take-home-instructions.md) | Public Railway URL, gate **open** for evaluation; live queue → review → disposition path verified. See [`docs/railway-deployment.md`](railway-deployment.md). | ✅ Delivered |
| D5 | **Document trade-offs / limitations** | [L113](../ref-docs/TTB-take-home-instructions.md) | `docs/tradeoffs-and-limitations.md`. **Tests:** `tests/test_docs_deliverables.py`. | ✅ Delivered |

### 2C. Evaluation criteria (how the brief grades the work)

| # | Criterion | Source | How the POC targets it — **Evidence** | Status |
|---|---|---|---|---|
| E1 | Correctness & completeness of core requirements | [L106](../ref-docs/TTB-take-home-instructions.md) | All four core checks (#1–4) implemented, demonstrable, and tested (the green suite). | ✅ |
| E2 | Code quality & organization | [L107](../ref-docs/TTB-take-home-instructions.md) | Modular layout: engine-agnostic OCR/LLM adapters behind one interface (`app/adapters/`), four centralized contracts (`app/contracts.py`, `normalize.py`, `verdict.py`, `disposition.py`), pipeline behind a stage seam. Format → lint (ruff) → mypy → 800 tests all green. | ✅ |
| E3 | Appropriate technical choices for the scope | [L108](../ref-docs/TTB-take-home-instructions.md) | Local-first stack honoring the firewall constraint; LLM optional/toggleable; Python end-to-end (FastAPI + Jinja2 + SQLite + APScheduler); single Docker image local + deployed. | ✅ |
| E4 | User experience & error handling | [L109](../ref-docs/TTB-take-home-instructions.md) | USWDS UI, in-UI help, discrepancy highlighting, honest-state patterns (visible error cards, "LLM unavailable — showing OCR result", calm 409s, accessibility floor). **Code:** `app/web/review_view.py`, `templates/`. **Tests:** `test_review.py`, `test_help_panel.py`. | ✅ |
| E5 | Attention to requirements | [L110](../ref-docs/TTB-take-home-instructions.md) | **This traceability doc**, kept honest with code/test pointers. | ✅ |
| E6 | Creative problem-solving | [L111](../ref-docs/TTB-take-home-instructions.md) | Pre-compute strategy beating the abandoned vendor pilot; checklist reframing of Jenny's printed sheet; queue buckets by beverage type; multi-engine procurement benchmark. | ✅ |

---

## 3. Above-and-Beyond (Diane's additions)

**Everything here is beyond the brief's minimum** — included to serve the *secondary goal*
(inform future procurement) and demonstrate engineering depth. All are **built**.

| # | Above-and-beyond item | Why beyond the brief | Evidence (code · tests) | Status |
|---|---|---|---|---|
| A1 | **Multi-OCR** (Tesseract + PaddleOCR, per-engine jobs + timing) | Brief asks only to match fields. | `app/adapters/ocr/{tesseract,paddleocr}.py`, `app/pipeline/ocr.py` · `test_ocr_adapters.py` | ✅ |
| A2 | **Multi-LLM + cost analysis** (cost per ~1,000 verifications) | Brief doesn't require an LLM, let alone costing one. | `app/adapters/llm/*`, `app/benchmark/cost.py` · `test_cost.py`, `test_llm_adapters.py` | ✅ |
| A3 | **Tracing** (latency/timing, optional, disablable) | Pure instrumentation for the procurement story. | `app/benchmark/tracing.py` · `test_tracing.py` | ✅ |
| A4 | **Pre-compute pipeline** (background OCR + compliance) | Architecture choice to beat 5s dramatically (also satisfies #5). | `app/pipeline/*` · `test_pipeline.py` | ✅ |
| A5 | **Visible smart checklist** (reframes Jenny's printed sheet) | Context in the brief, not a requested feature. | `app/web/review_view.py` · `test_review_view.py` | ✅ |
| A6 | **Chevron status bar** (verdict roll-up + progress) | UX polish beyond "clean and obvious." | `app/web/review_view.py`, `app/verdict.py` · `test_verdict.py` | ✅ |
| A7 | **Queue by beverage type** (next wine/spirits/beer) | Brief asks for batch, not a routing queue. | `app/web/routes_queue.py` · `test_queue.py` | ✅ |
| A8 | **Image enhancement** (OpenCV deskew/perspective/glare/contrast) | Jenny flagged "maybe out of scope" (also #11). | `app/pipeline/preprocess.py` · `test_preprocess.py` | ✅ |
| A9 | **USWDS compliance** (design-system conformance, self-hosted) | Brief asks ease-of-use, not design-system conformance. | `templates/`, `static/` · `test_shell.py` | ✅ |
| A10 | **Token authentication** on the demo URL | Brief says auth is *not* a POC feature; added to protect the public demo (opened for evaluation). | `app/web/routes_access.py`, `app/web/deps.py` · `test_token_gate.py` | ✅ |
| A11 | **Mock COLA DB + data dictionary + schema** | Brief says *not* to integrate with COLA; a modeled mock is added rigor. | `app/db/*`, `docs/data-dictionary.md` · `test_schema_epic3.py`, `test_repositories.py`, `test_seed.py` | ✅ |
| A12 | **CFR-sourced rule write-ups** (3 per-type rulesets) | Documents the regulatory basis. | `docs/regulatory-rules-{distilled-spirits,wine,beer}.md`, `app/engine/rulesets/*` · `test_wine_malt_rulesets.py`, `test_class_type.py` | ✅ |
| A13 | **Comparable-software pre-search** | Landscape for the procurement story. | `docs/presearch.md` | ✅ |
| A14 | **Benchmark report screen + speed/cost stats** | Measurement surface beyond the functional ask; serves the procurement goal. | `app/benchmark/{scoring,cost}.py`, `app/web/routes_benchmark.py` · `test_scoring.py`, `test_benchmark.py` | ✅ |

---

## 4. Confirmation of Alignment — "Recommend, Don't Decide"

The POC provides **recommendations**; the **human Label Specialist** makes the final decision.
The software's job is to make review faster and easier, **never to make the decision itself**
([discussion-points §1 L54–57](../ref-docs/discussion-points.md)).

This aligns with the brief's framing of the tool as an *assistant to* — not a replacement for —
the agent's judgment:

- *"a lot of what we do is just… matching… drowning in routine stuff."* — Sarah Chen,
  [brief L17](../ref-docs/TTB-take-home-instructions.md). The tool clears routine matching; the
  human keeps the analysis.
- *"You can't just pattern match everything… You need judgment."* — Dave Morrison,
  [brief L47](../ref-docs/TTB-take-home-instructions.md). The "STONE'S THROW" case is exactly why
  the engine *flags and recommends* rather than auto-deciding.

Accordingly the POC separates the **engine verdict** (PASS / REVIEW / FAIL — advisory) from the
**Label Specialist disposition** (Approved / Needs Correction / Rejected — the human's decision),
mirroring TTB's real states. That separation is enforced in code (`app/verdict.py` vs
`app/disposition.py`; the engine never writes a disposition) and is the concrete implementation
of "recommend, don't decide." **Alignment confirmed.**

---

## 5. Status — Complete

All items in §2–§3 are **implemented, tested, and deployed** as of 2026-06-15:

- **Both formal deliverables shipped** — public repo + a live, gate-open deployed URL (D1–D5).
- **All four core checks** (brand, ABV, government warning, label↔application match) built and
  tested; the government-warning exactness check is deterministic (no LLM).
- **All three beverage types** (distilled spirits, wine, malt/beer) are first-class, each with its
  own CFR-sourced ruleset — no spirits-only under-coverage against criterion E1.
- **Batch** is delivered as the deliberate applicant-side reframing + a working live-enqueue op.
- **Full gate green** (format → lint → mypy → 800 tests) on both the host venv and inside the
  dev container; the zero-egress `--network none` boot proves the firewall-safe core.
