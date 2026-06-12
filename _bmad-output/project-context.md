---
project_name: 'TTB-label-POC'
user_name: 'Diane'
date: '2026-06-12'
sections_completed: ['technology_stack', 'architectural_invariants', 'centralized_contracts', 'naming_format_data', 'firewall_offline', 'ui_fidelity', 'testing_tooling', 'anti_patterns']
existing_patterns_found: 0
status: 'complete'
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

Pinned in `_bmad-output/planning-artifacts/approved-tech-stack.md` (version-of-record). Pin to the minor line (`~=major.minor`) unless a patch is named.

- **Python 3.13** (Docker base `python:3.13-slim`). Type hints required.
- **Web (server-rendered, NO SPA, NO build step):** FastAPI ~=0.136 · Uvicorn ~=0.49 · Pydantic v2 ~=2.13 · Jinja2 3.1.
- **Background jobs:** APScheduler ~=3.11 (in-process; NOT the 4.0 pre-release).
- **Data:** SQLite via stdlib `sqlite3`, WAL mode. No ORM, no migration framework — plain SQL DDL + Python seed script.
- **OCR/Image (all local):** Tesseract 5.5 (apt) + pytesseract · PaddleOCR ~=3.4 · opencv-python-headless ~=4.13.
- **LLM (toggleable, `internal-endpoint`):** openai ~=2.41 · anthropic ~=0.79 · google-genai ~=2.8. **LangChain ~=1.3 — local tracing only, no telemetry egress.**
- **UI:** USWDS 3.x compiled assets, vendored/self-hosted in `static/uswds/` (no CDN, no Node build). Fonts Public Sans + Roboto Mono, self-hosted.
- **Tooling:** ruff ~=0.15 (lint + format, line length 100) · pytest ~=9.0.
- **Deploy:** Docker (Desktop dev) → Railway Pro, single service, Dockerfile build (NOT Nixpacks), Volume for the SQLite file + generated images. Model weights baked into the image (no runtime download).

## Critical Implementation Rules

### Architectural Invariants (non-negotiable)

- **The 5-second read contract:** the `GET` render route does a DB read of pre-computed rows ONLY. NEVER run OCR, image processing, inference, or a model-layer call on a request/render path. All heavy work is done by the background pipeline. *Cheap single-row bookkeeping writes are NOT "heavy work"* and ARE allowed — but only on explicit `POST` actions, never folded into the `GET` render: the `status` lifecycle write, and the `review_progress` upsert + `undo` writes (architecture **Addendum A**). The prohibition is on heavy work, not on all writes.
- **Recommend, don't decide:** `engine_verdict ∈ {PASS, REVIEW, FAIL}` (advisory) and `disposition ∈ {APPROVED, NEEDS_CORRECTION, REJECTED}` (human) are different enums in different modules. NO function maps one to the other; no verdict pre-selects/colors/defaults a disposition control.
- **Pipeline is the only writer** of `ocr_results`, `llm_results`, `field_comparisons`, `checklist_items`, and `engine_verdict`. The web layer owns the *human* writes — `disposition`/`decided_at`/`decision_notes`, the `status` lifecycle transitions, and the `review_progress` scratch row (human checklist ticks + draft Notes; Addendum A) — which never overlap the pipeline's columns. **Human checklist tick-state lives in `review_progress`, NEVER in the pipeline-owned `checklist_items`.** The web layer never invokes the pipeline synchronously — `POST /enqueue` only inserts a `RECEIVED` row; the scheduler picks it up.
- **Adapters depend on protocols, never concretes:** `engine/` and `pipeline/` import `adapters/*/base.py`, never a specific engine/provider. Adding an engine/model = a new adapter file, NO schema or caller change.
- **CFR rules live as data** (Ruleset rows with citation + source date), NEVER hard-coded in check logic.
- **Determinism taxonomy:** rule-bound checks are deterministic code (no LLM). The Government Warning check NEVER calls an LLM. LLM-assisted verdicts are capped at REVIEW — an LLM opinion alone never yields FAIL.

### The Four Centralized Contracts (import, never re-implement)

Each lives in exactly one module; import it everywhere.

1. **`app/contracts.py`** — `OcrResult` / `LlmResult` adapter shapes. Every OCR engine returns `{engine_name, engine_version, text, word_boxes, confidence, latency_ms, ran_on_cpu, status}`; every model returns `{model_name, model_id, model_full_id, provider, task, result_text, prompt_tokens, completion_tokens, total_tokens, latency_ms, requested_at, responded_at, status}`.
2. **`app/normalize.py`** — `normalize(value, field_key)`: trim → collapse internal whitespace → Unicode NFKC → casefold → curly→straight quotes → strip trailing punctuation; numeric fields additionally parse to number+unit. ALL field comparisons use it (this is what makes "STONE'S THROW" == "Stone's Throw").
3. **`app/verdict.py`** — `rollup(verdicts)`: any FAIL ⇒ FAIL; else any REVIEW/can't-verify ⇒ REVIEW; else PASS. Used by both the engine and the UI so they can never disagree.
4. **`app/disposition.py`** — disposition enum ONLY; has NO dependency on `verdict.py`.

### Naming, Format & Data Conventions

- **snake_case everywhere** — DB columns, Python, AND JSON. No camelCase boundary to translate.
- Tables: snake_case **plural** (`submissions`, `label_images`, `ocr_results`, `field_comparisons`, `checklist_items`, `llm_results`, `audit_events`, `review_progress`). PK `id`; FK `<entity>_id`. (`review_progress` is the exception: PK is `submission_id`, one row per submission, for upsert.)
- Enums: `UPPER_SNAKE` stored as `TEXT + CHECK` (no native enums) — greppable.
- Timing columns suffixed `_ms` (INTEGER ms); timestamps `_at` (UTC ISO-8601). `cost_usd` as decimal/string — never float math on currency; token counts integers; booleans real `true/false` in JSON.
- Stable identifiers: `check_key` / `field_key` are snake_case and MUST resolve to an entry in `docs/data-dictionary.md`.
- Provenance string: `extracted_source` is exactly `ocr:<engine_name>` or `llm:<model_id>`. CFR citation format: `"27 CFR <part>.<section>"`.
- **Status transitions, forward order:** `RECEIVED → PROCESSING → READY_FOR_REVIEW → IN_REVIEW → DECIDED`, plus **exactly one bounded backward transition** `DECIDED → READY_FOR_REVIEW` reachable ONLY via `POST /review/{id}/undo` (in-session "Recorded — Undo"; Addendum A). `audit_events.event_type` is a fixed vocabulary (`SEEDED/OCR_STARTED/OCR_COMPLETED/ANALYSIS_COMPLETED/READY/OPENED/DECIDED/UNDONE`).
- API routes: lowercase, no trailing slash, `{id}` path params (`GET /queue`, `POST /next`, `GET /review/{id}`, `POST /review/{id}/progress`, `POST /review/{id}/undo`, `POST /review/{id}/disposition`, `GET /benchmark`, `POST /reset`, `POST /enqueue`).
- Create tables only in the story that needs them — do NOT front-load the full schema. Pydantic v2 validates at the API/read boundary only.
- The authoritative data model is `docs/database-schema.md` + `docs/data-dictionary.md` — read them; do not duplicate them.

### Firewall & Offline Posture (NFR-2)

- The ONLY permitted off-host calls originate in `adapters/llm/{openai,google,anthropic}.py` (classified `models-internal-endpoint`). Everything else is `none`/`local`.
- `LLM_ENABLED=false` must disable that boundary entirely — the OCR-only path must complete end-to-end with zero egress (`docker run --network none` is the smoke test).
- All assets same-origin/self-hosted — no CDN, no Google Fonts, no first-run weight downloads. Config via env: `ACCESS_TOKEN`, `LLM_ENABLED`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LANGCHAIN_*`. Absent keys ⇒ model layer simply off (still functional).
- Secrets/keys never logged. Tracing is LangChain local-only and toggleable.

### UI Fidelity & USWDS Discipline (hard requirement)

- **Every screen must match its mockup** in `_bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/` — layout, USWDS component structure, all states, and exact copy. A side-by-side comparison against the mockup is in each UI story's Definition of Done. (token-gate · queue · review-workspace · help-panel · benchmark-report.)
- **Spine wins on conflict:** design tokens resolve to `DESIGN.md`/`EXPERIENCE.md`, NOT a mockup's literal CSS where they differ (e.g. PASS green is `#216E29` per DESIGN.md, not the mockups' `#2E8540`). Mockup scaffolding (browser frame, CSS-drawn labels, placeholder data) is illustrative — do not reproduce it.
- Use USWDS components per documented markup — do NOT restyle them beyond the Treasury brand layer + domain tokens.
- **Verdict palette only on engine advice**, always paired with icon + word (color never carries meaning alone). Beverage accents only on the type banner, word always present.
- Field comparison is vertical (application value above OCR value), never side-by-side. Quiet matches, loud mismatches only.
- Accessibility floor: body ≥16px, comparison values 19px, targets ≥48px; tab order = reading order; `aria-live` for post-render changes; char-diff carries a text equivalent surviving forced-colors mode. Single-letter shortcuts are inert in text inputs and while a modal owns focus.

### Testing & Tooling

- pytest in top-level `tests/`, files `test_*.py`, mirroring the `app/` package. Format/lint with ruff (line length 100) — type hints required.
- Highest-value tests: `test_normalize.py` (the "STONE'S THROW" class — zero false-FAIL, SM-C2), `test_verdict.py` (severity precedence), `test_government_warning.py` (the three outcomes), `test_token_gate.py` (no data leakage).
- Structured logging (`logging`), normal levels; never log secrets.

### Anti-patterns to reject in review

- camelCase JSON · a `verdict → disposition` mapping · per-engine bespoke result dicts · inline normalization · OCR/LLM/inference on a read path · a verdict color on a disposition button or a pre-selected disposition · CFR text hard-coded in Python · a CDN/outbound asset reference · serving a partially-processed submission · a spinner that blocks the pre-computed result.

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code; follow every rule exactly.
- When in doubt, prefer the more restrictive option (especially around the firewall boundary and the verdict-vs-disposition separation).
- The authoritative sources behind these rules: `_bmad-output/planning-artifacts/architecture.md` (decisions D1–D8, the four contracts), `approved-tech-stack.md` (version-of-record), `docs/database-schema.md` + `docs/data-dictionary.md` (data model), and the UX package under `_bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/` (DESIGN.md, EXPERIENCE.md, mockups). When a rule and a source conflict, the source wins — fix this file.

**For Humans:**

- Keep this file lean and focused on what agents miss; update it when the tech stack or a contract changes.
- Remove rules that become obvious over time; this is a reminder sheet, not documentation.

Last Updated: 2026-06-12
