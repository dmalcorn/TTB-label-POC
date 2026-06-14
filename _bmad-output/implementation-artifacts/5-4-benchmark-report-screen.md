---
baseline_commit: fe9c44a
---

# Story 5.4: Benchmark Report screen

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a procurement evaluator,
I want the engines and models laid out side by side on accuracy, latency, and cost,
so that I can compare the options and see the recommendation.

## Acceptance Criteria

1. **AC1 — `GET /benchmark` renders REAL seeded-corpus figures (never hand-entered numbers).**
   **Given** the seeded corpus with its captured `ocr_results` / `llm_results` rows
   **When** the report loads
   **Then** the route calls the Story 5.2 `app.benchmark.scoring.score_corpus(conn)` and the Story 5.3 `app.benchmark.cost.cost_corpus(conn)` over a **read-only** DB connection and renders the typed `CorpusScore` / `CostReport` objects they return — the table's accuracy / latency / cost figures are derived from those objects, never literals baked into the template. The route is a pure pre-computed **DB read** (AR-5): it constructs no provider client, opens no off-host socket, runs no OCR/inference at request time. *(FR-23, AR-5; epics.md Story 5.4 "rendering real seeded-corpus runs")*

2. **AC2 — The screen matches `mockups/benchmark-report.html` exactly (structural + visual fidelity; spine wins on conflict).**
   **Given** the binding UI-fidelity standard (epics.md Overview) and `mockups/benchmark-report.html`
   **When** the report renders
   **Then** it reproduces, rebuilt on the shared app shell + real data: the **evaluator header** carrying the **"Evaluator build" badge** and the nav (Queue · Benchmark Report active · Help); the page title "OCR & LLM Benchmark Report" + "Evaluator view · read-only" subtitle + intro paragraph; the **civic-green Recommendations callout** (✓ icon, the three grounded recommendation bullets); the **grouped comparison table** with the two group rows "OCR engines" / "Language models (judgment checks)", the columns **Engine / Model · Field accuracy · Latency (ms/item) · Cost / 1,000 (USD) · CPU-only**, the best-in-group row highlighted (`.best`), numeric cells in **Roboto Mono** (`td.num`); the **legend**; the **"How to read these numbers" honesty note** (amber callout, the four "indicative, not audited" bullets); and the **footer meta** line. Tokens resolve to `static/css/brand.css` / `DESIGN.md` values (e.g. civic green `#2E5B46`, PASS `#216E29`), **NOT** the mockup's inline hex. The **verdict palette is kept off this surface** (no PASS/REVIEW/FAIL chips — accuracy is a number, not a verdict). **Mockup-only scaffolding is excluded**: the `.device` browser frame, the URL bar, and the placeholder figures (96.4, 410, "240 sample labels", "seed-2026-06-12", etc.) are NOT reproduced — real computed figures and an honest computed fixture-count/date replace them. *(FR-23, UX-DR-5, NFR-5; UI-fidelity standard)*

3. **AC3 — The CPU-only flag is icon + word + color (never color alone).**
   **Given** the CPU-only column
   **When** a row renders
   **Then** OCR engines (self-hosted, CPU-only) show **✓ Yes** in the pass register and the language models show **⚠ No — API** in the review/amber register, each as **icon + word + color together** (A11Y floor — color never carries meaning alone). The flag for OCR comes from the captured `EngineCost.cpu_only` (Story 5.3 / AR-? `ran_on_cpu`); a model needing an outbound call is "No — API". *(UX-DR-5 accessibility floor; DESIGN.md "color never alone"; epics.md Story 5.4)*

4. **AC4 — Honest empty state before any run (not zeros).**
   **Given** a DB with **no** scorable benchmark rows (no seeded `ocr_results` / `llm_results`, so `CorpusScore.engines`/`models` and `CostReport` are empty)
   **When** the report loads
   **Then** it shows the honest **"No benchmark runs yet — figures appear after the harness runs"** empty state in place of the table — **never a table of zeros** that reads as real measurements. The Recommendations callout + honesty note may still frame the study, but no fabricated numeric row is shown. *(EXPERIENCE.md empty-state row "Benchmark Report — no data yet"; NFR-5 honesty; epics.md Story 5.4 "not zeros")*

5. **AC5 — Best-in-group highlight + grounded recommendations are derived, not hard-coded.**
   **Given** the computed per-engine / per-model figures
   **When** the report renders
   **Then** the **best-in-group** row highlight (`.best`) is computed — within OCR engines, the highest `field_match_rate`; within language models, the highest `field_match_rate` (ties broken stably by key) — so the highlight tracks the real data, not a literal class in the template. The closing **Recommendations** (best OCR, best LLM, the "keep deterministic checks deterministic" note) are present and consistent with the figures; the recommendation copy is the spine's grounded guidance (PaddleOCR baseline + Tesseract fallback; a language model for the judgment checks; the Government Warning stays a deterministic exact-text check off the LLM cost line). *(FR-23 "closes with grounded recommendations"; epics.md Story 5.4; benchmarking-plan §6)*

6. **AC6 — Pricing/figure honesty stated plainly (NFR-5) + read-only, token-gated, zero-egress.**
   **Given** NFR-5 (honesty of claims) and the firewall posture
   **When** the report renders
   **Then** the honesty note states plainly that the figures are **indicative from a seeded fixture set, not audited**, and that **published API prices proxy internally-hosted model cost** (the `ModelCost.cost_basis` NFR-5 label is surfaced for priced models; an **unpriced** provider model shows an honest "not priced" / "—", never a fabricated `$0.00`); local OCR shows `$0.00` with its "$0 marginal API cost" basis. The screen is **read-only** (no forms, no decision control), is protected by the app-wide token gate (carries no exemption — Story 1.5 middleware), and the route + template reference only same-origin `/static` assets (no CDN, no Google Fonts — NFR-2/AR-8). *(NFR-5, NFR-2, AR-5, AR-8, FR-25; cost.py `cost_basis` / `cost_per_1000 is None`)*

## Tasks / Subtasks

- [ ] **Task 1 — Benchmark route module (`app/web/routes_benchmark.py`) (AC1, AC4, AC5, AC6)**
  - [ ] Create `app/web/routes_benchmark.py` mirroring `routes_queue.py`'s structure: `from __future__ import annotations`, an `APIRouter()`, a module docstring stating the 5s read-only contract (AR-5), the token-gate (no exemption — Story 1.5), and zero-egress posture. [Source: app/web/routes_queue.py lines 1–36]
  - [ ] `GET /benchmark` handler `def benchmark(request: Request) -> HTMLResponse`: `settings = request.app.state.settings`; `with connect(settings.database_path) as conn:` call `scoring.score_corpus(conn)` and `cost.cost_corpus(conn)` (both READ-ONLY — they issue SELECTs only). Do NOT run any pipeline/OCR/inference. [Source: app/benchmark/scoring.py:401 `score_corpus`; app/benchmark/cost.py:229 `cost_corpus`; app/db/connection.py `connect`; the AR-5 read-path docstring in routes_queue.py]
  - [ ] Build a **presentation view-model** at the boundary (a private `_build_rows(...)`): zip the accuracy `CorpusScore` and the speed/cost `CostReport` by their **shared keys** — OCR rows keyed `(engine_name, image_variant)`, model rows keyed `model_id` (cost.py docstring: "the SAME keys the accuracy scorer uses … so speed/cost and accuracy line up row-for-row"). For each row expose: a **display name** (see Task 2 mapping), accuracy = `ExtractorScore.field_match_rate` (a fraction → render as `%`), latency = `LatencyStats.mean_ms` (the "ms / item" figure; `None` ⇒ "—"), cost-per-1,000 (`EngineCost.cost_per_1000` = `$0.00` for OCR; `ModelCost.cost_per_1000` Decimal / `None`), `cost_basis`, and the CPU-only flag (OCR ⇒ Yes from `EngineCost.cpu_only`; model ⇒ "No — API"). Iterate in **stable sorted key order** so the rows are deterministic. [Source: scoring.py ExtractorScore.field_match_rate:303; cost.py EngineCost/ModelCost:185–211, LatencyStats:61–72]
  - [ ] Compute **best-in-group** within OCR and within models = the max `field_match_rate` (ties broken by sorted key; skip rows whose rate is `None`). Mark that row's view-model `is_best = True`. [Source: AC5; mockup `.best` rows]
  - [ ] Compute the **has-data** flag for the empty state: `True` iff there is at least one OCR or model row with a verifiable figure (i.e. `CorpusScore.engines`/`models` non-empty). Pass `has_data`, the row groups, and an honest `fixture_count` (= `CorpusScore.scored_submissions`) to the template. [Source: AC4; EXPERIENCE.md empty-state; scoring.py CorpusScore.scored_submissions:339]
  - [ ] Render via `request.app.state.templates.TemplateResponse(request, "benchmark.html", {...})`. [Source: routes_queue.py `_render_queue` TemplateResponse pattern]

- [ ] **Task 2 — Display-name resolution at the presentation boundary (AC2, AC6)**
  - [ ] The keyed aggregates retain only `engine_name` / `model_id` (the `ExtractorScore` / `EngineCost` / `ModelCost` do NOT carry `model_name`/`provider`). Build a small presentation map in the route: OCR `engine_name → "PaddleOCR (PP-OCRv5)"` / `"Tesseract 5"` (+ the muted sub-line "self-hosted, vendored" / "· fallback"); models `model_id → display label + "API · price proxies internal cost"` sub-line. Where a friendly label is unknown, fall back to the raw `engine_name`/`model_id` verbatim (honest, never blank). Keep this mapping a module constant (a dict), NOT hard-coded inside the template. [Source: app/config.py `_DEFAULT_MODEL_ID`:131; app/db/repositories.py `LlmScoringRow.model_name`/`provider`:281–282; mockup model/sub-line copy lines 220–256]
  - [ ] Optionally enrich provider/model_name from the raw `LlmScoringRow`/`LlmCostRow` (they DO carry `model_name`/`provider`) if a richer label is wanted — but the figures themselves come ONLY from the typed aggregates (never recompute accuracy/cost in the route). [Source: repositories.py:281–282, 363–364]

- [ ] **Task 3 — Register the router (AC1, AC6)**
  - [ ] In `app/main.py`, `from app.web.routes_benchmark import router as benchmark_router` and `app.include_router(benchmark_router)` alongside the others, with a comment noting it carries no exemption so the token gate protects it (AR-5 pure read). [Source: app/main.py lines 129–136 router registration]

- [ ] **Task 4 — The template (`templates/benchmark.html`) (AC2, AC3, AC4, AC5, AC6)**
  - [ ] `{% extends "base.html" %}`; `{% block title %}TTB Label Review — Benchmark Report{% endblock %}`. The mockup's evaluator header has a nav + "Evaluator build" badge that the shared `base.html` header does NOT carry. Reproduce the evaluator header by **overriding `{% block header %}`** for this screen (still `{% include "_help_panel.html" %}` so Help works, since `help.js`/`shortcuts.js` load globally). Keep tokens resolving to `--brand-*` vars. [Source: templates/base.html header block lines 16–46; mockup header lines 172–180]
  - [ ] In `{% block content %}` reproduce, state-for-state: title/subtitle/intro; the **Recommendations** civic-green callout (✓ + three bullets); the **"Side-by-side comparison"** section heading + sub; then **either** the grouped table (when `has_data`) **or** the empty-state callout (AC4). [Source: mockup lines 182–283]
  - [ ] The table: `<caption>`, `<thead>` with the five columns (numeric headers right-aligned `.num`), a `<tr class="group-row">` "OCR engines" then each OCR row, a `<tr class="group-row">` "Language models (judgment checks)" then each model row. Numeric cells `td.num` (Roboto Mono via the `.num`/`.mono` rule). The best row gets `class="best"`. The recommended sub-line pill (`.pill.rec` "Recommended") goes on the best-in-group rows. Accuracy rendered as a percent to one decimal; latency as integer ms (or "—" when `None`); cost as `$X.XX` (or "—"/"not priced" when `ModelCost.cost_per_1000 is None`). [Source: mockup table lines 206–259; cost.py cost_per_1000 None semantics:210]
  - [ ] The **CPU-only flag** as icon+word+color: `<span class="flag yes"><span class="ic" aria-hidden="true">✓</span>Yes</span>` for OCR, `<span class="flag no"><span class="ic" aria-hidden="true">⚠</span>No — API</span>` for models. [Source: mockup lines 225, 241, 263–264; AC3]
  - [ ] The **legend**, the **honesty note** (amber; the four bullets incl. the API-prices-proxy + $0.00-local-only lines, surfacing `cost_basis` where priced), and the **footer meta** (honest computed `fixture_count` + "offline · no outbound calls"; do NOT fabricate "240 sample labels" / a hard-coded date). [Source: mockup lines 261–282; AC6; NFR-5]
  - [ ] All assets same-origin under `/static` (inherited from `base.html`); add any benchmark-specific CSS to `static/css/brand.css` (a new `/* Benchmark Report (Story 5.4) */` section) resolving the mockup's classes (`.reco`, `.sec-h`, `.table-wrap`, `.group-row`, `.flag.yes/.no`, `.pill.rec`, `.honesty`, `.legend`, `.footer-meta`, the evaluator-header nav/badge) to `--brand-*`/`--verdict-*` tokens — spine wins over the mockup's inline hex. Do NOT inline a `<style>` block or reference a CDN (NFR-2). [Source: static/css/brand.css existing per-screen sections; UI-fidelity "spine wins"]

- [ ] **Task 5 — Tests (`tests/test_benchmark.py`) (all ACs)**
  - [ ] Mirror `tests/test_queue.py`'s `_client(monkeypatch, tmp_path, token=...)` harness: temp DB, `SCHEDULER_ENABLED=false`, `init_db`, `TestClient(create_app())`. Seed a tiny corpus + hand-written `ocr_results`/`llm_results` rows (reuse the seeding approach from `tests/test_scoring.py` / `tests/test_cost*.py`) so the figures are REAL but offline. [Source: tests/test_queue.py:37–87; tests/test_scoring.py seeding]
  - [ ] **AC1**: `GET /benchmark` returns 200 and the body contains a computed accuracy figure from the seeded rows (assert the rendered percent matches `score_corpus` over the same DB — not a literal). Assert the route issued no network/model call (the egress-guard reasoning: it imports `scoring`/`cost`, never an adapter). [Source: AC1]
  - [ ] **AC2** (fidelity): assert the evaluator header ("Evaluator build" badge), the "OCR & LLM Benchmark Report" title, the Recommendations callout, both group rows ("OCR engines", "Language models"), the five column headers, and the honesty + footer meta are present; assert NO mockup scaffolding leaked (no `.device`, no URL bar, no placeholder "240 sample labels"/`seed-2026-06-12`). Assert verdict chip classes (`chip--pass` etc.) do NOT appear (verdict palette kept off this surface). [Source: AC2; UI-fidelity standard]
  - [ ] **AC3**: assert the OCR rows render "✓" + "Yes" and the model rows "⚠" + "No — API" (icon AND word both present). [Source: AC3]
  - [ ] **AC4** (empty state): with an empty DB (no ocr/llm rows), `GET /benchmark` returns 200 and shows "No benchmark runs yet" and renders NO numeric data row / no `$0.00` table cell. [Source: AC4]
  - [ ] **AC5**: seed two OCR engines with different accuracy; assert the higher-accuracy OCR row carries `class="best"` and the lower one does not (and likewise for models). [Source: AC5]
  - [ ] **AC6**: token gate — with `ACCESS_TOKEN` set and no cookie, `GET /benchmark` 303→`/access`; with the cookie, 200. Assert the honesty note states the "indicative … not audited" + "published API prices proxy" language, and that an **unpriced** model (`cost_per_1000 is None`) renders an honest "not priced"/"—", never `$0.00`. Assert no off-`/static` asset URL (no `http://`/`https://` external, no CDN) in the body. [Source: AC6; tests/test_queue.py gate tests:337–350]

- [ ] **Task 6 — Finalize (all ACs)**
  - [ ] `ruff check` + `ruff format` (line length 100); type hints throughout; run `tests/test_benchmark.py` green, then the full gate `bash scripts/ci.sh` ONCE (no regressions). Update File List + Change Log + Completion Notes; set Status → review and sprint-status story `5-4` → `review`.
  - [ ] Do NOT modify `app/benchmark/scoring.py` or `app/benchmark/cost.py` (Stories 5.2/5.3 — done; this story CONSUMES them, never re-scores). Do NOT touch `auto-run/`. [Source: CLAUDE.md "Don't edit auto-run/"; epics.md Stories 5.2–5.3 scope]

## Dev Notes

### Scope boundary (what 5.4 IS and is NOT)
- **IS:** the evaluator-facing **Benchmark Report screen** — a new `GET /benchmark` route (`app/web/routes_benchmark.py`) + a new `templates/benchmark.html` + the benchmark CSS section in `static/css/brand.css`, rendering the typed objects from Story 5.2 (`scoring.score_corpus`) and Story 5.3 (`cost.cost_corpus`) as the side-by-side comparison table with grounded recommendations, the honest empty state, the CPU-only icon+word+color flag, and the "indicative, not audited" honesty note — matching `mockups/benchmark-report.html` exactly (spine wins on conflict).
- **IS NOT:** any change to the accuracy scorer (5.2) or the cost/speed stats (5.3) — it CONSUMES their results, never recomputes; no new schema; no decision/disposition control (read-only); no sortable-table JavaScript is required (the mockup's "click to sort" is a sortable-LOOKING affordance — the spine note says "read-only surface; sortable-looking"). Server-rendered rows in a stable sorted order satisfy fidelity; do not add a JS sort dependency. [Source: mockup line 19 "Read-only surface — no decision controls"; line 204 "sortable-looking"]

### Consume the typed objects — never re-score in the route (the 5s/honesty spine)
`score_corpus(conn)` returns a `CorpusScore` (`.engines: dict[(engine_name, image_variant), ExtractorScore]`, `.models: dict[model_id, ExtractorScore]`, `.scored_submissions`). `cost_corpus(conn)` returns a `CostReport` (`.engines: dict[(engine_name, image_variant), EngineCost]`, `.models: dict[model_id, ModelCost]`, `.verification_count`). They use the **same keys**, so the route zips them row-for-row. The route is a thin presentation layer: read → zip → label → render. It must NOT re-implement match-banding, CER, latency, or cost math (those are the centralized 5.2/5.3 contracts). [Source: app/benchmark/scoring.py:329–339; app/benchmark/cost.py:214–226]

Key shapes to render (exact field names):
- `ExtractorScore.field_match_rate -> float | None` (a fraction in [0,1]; multiply by 100 for the % column; `None` ⇒ "—"). Also `.mean_cer`, `.gov_warning_presence_rate`, `.gov_warning_exactness_rate`, `.unverifiable_count` are available if the report wants secondary lines, but the mockup's 4 columns are accuracy/latency/cost/CPU-only — keep the primary table to those four. [Source: scoring.py:292–326]
- `EngineCost.latency: LatencyStats` (`.mean_ms`/`.median_ms`/`.p95_ms`/`.count`, all `float | None`), `.cpu_only: bool | None`, `.cost_per_1000: Decimal` (=`Decimal("0")`), `.cost_basis: str` (the "$0 marginal" label). [Source: cost.py:185–196]
- `ModelCost.latency: LatencyStats`, `.mean_prompt_tokens`/`.mean_completion_tokens: float | None`, `.cost_per_1000: Decimal | None` (None ⇒ honest "not priced", NEVER `$0.00`), `.cost_basis: str | None` (NFR-5 pricing basis). [Source: cost.py:199–211]
- The "ms / item" column = `LatencyStats.mean_ms` rounded to an integer (the mockup shows whole ms like 410, 1,240). `None`/`count == 0` ⇒ "—" (honest, not a fake 0 — mirrors LatencyStats' all-None-on-empty contract). [Source: cost.py:67]

### Display-name resolution lives in the route, not the template or the scorer
The aggregates are keyed by raw `engine_name` / `model_id` and do NOT retain `model_name`/`provider`. Map them to the mockup's friendly labels at the presentation boundary (a module-level dict in `routes_benchmark.py`): `paddleocr`/`paddle` → "PaddleOCR (PP-OCRv5)", `tesseract` → "Tesseract 5"; model ids → "Claude"/"GPT"/"Gemini" by provider family (the seeded/benchmark `model_id` will be e.g. an Anthropic/OpenAI/Google id — derive the family from the raw `LlmScoringRow.provider` if a robust mapping is needed, else fall back to the raw id). An unknown engine/model renders its raw key verbatim (honest, never blank). Do NOT bake friendly names into the SQL or the scorer (keeps 5.2/5.3 engine-agnostic — AR-4). [Source: app/config.py `_DEFAULT_MODEL_ID`:131; repositories.py LlmScoringRow.provider:282; AR-4]

### Empty state is honesty, not a styling nicety (AC4 / NFR-5)
Before the harness has populated rows, `CorpusScore.engines`/`models` are empty. The screen MUST show "No benchmark runs yet — figures appear after the harness runs" rather than a table of `0`/`$0.00` cells that read as real measurements. Gate the table on a `has_data` flag (any OCR or model row present). This is the EXPERIENCE.md empty-state contract and an NFR-5 honesty requirement, not optional polish. [Source: EXPERIENCE.md line 117; NFR-5]

### UI fidelity: spine wins, scaffolding excluded (the binding standard)
Reproduce the mockup's **layout, composition, USWDS structure, all states, exact visible copy**, but: (1) tokens resolve to `DESIGN.md`/`brand.css` (civic green `#2E5B46`, PASS `#216E29`) NOT the mockup's inline hex (the mockup uses `#2E8540` for pass — spine wins); (2) the verdict palette stays OFF this surface (accuracy is a measurement, not a PASS/REVIEW/FAIL verdict — no `chip--*`); (3) EXCLUDE the `.device` frame, the `.browser-bar` URL bar, and ALL placeholder figures (96.4 / 410 / "$3.10" / "240 sample labels" / "seed-2026-06-12" / "generated 2026-06-12"). Real computed figures + an honest computed fixture count replace them. Put the CSS in `brand.css` (same-origin), never an inline `<style>` (the mockup's inline CSS is illustrative). [Source: epics.md Overview UI-fidelity standard; mockup header comment lines 8–20]

### Evaluator header: override the base header block for this one screen
`base.html`'s `{% block header %}` renders the standard seal/title/[?] shell. The benchmark mockup's header additionally has a **nav** (Queue / Benchmark Report active / Help) and an **"Evaluator build" badge**. Override `{% block header %}` in `benchmark.html` to render the evaluator header (still including `_help_panel.html` so the global `help.js` toggle works), OR extend the shared header with the nav — prefer the override so the other screens are untouched. Keep the nav links real (`/queue`, `/benchmark`) so they navigate; "Help" opens the existing help panel. [Source: base.html:16–46; mockup:172–180]

### Firewall / read-only / 5s posture (AC1, AC6)
The route opens NO socket and constructs NO provider client — it does a pure DB read via `connect()` + the two read-only benchmark functions, then renders. It is NOT on any OCR/inference path (AR-5). It carries no route-level exemption, so the app-wide token-gate middleware in `main.py` protects it like every screen (Story 1.5). All template assets are same-origin `/static` (NFR-2/AR-8). The screen is read-only — no `<form>`, no disposition/decision control. [Source: app/main.py middleware:119–127; routes_queue.py AR-5 docstring; NFR-2]

### Previous story intelligence
- **5.1** established `app/benchmark/` + the local-only zero-egress conventions. **5.2** (`scoring.py`) and **5.3** (`cost.py`) are the two DONE producers this screen consumes — both return frozen, reproducible, read-only typed objects keyed identically. Do NOT fork or re-score; import and render. [Source: 5-2 story (done); 5-3 story (done)]
- **5.2 CR note**: three benchmark-vs-production-fidelity findings (near-miss banding, OCR-confidence floor, short-gold substring) were recorded in `deferred-work.md` as deliberate metric definitions — they are NOT this story's concern; the report renders whatever 5.2 computes. [Source: 5-2 Change Log 2026-06-14 CR]
- **Epic-4 UI stories (4.1–4.11)** established the screen conventions this story mirrors: `{% extends "base.html" %}`, `TemplateResponse(request, "name.html", ctx)`, per-screen CSS sections in `brand.css` (spine tokens, no inline `<style>`, no CDN), and the `tests/test_<screen>.py` `_client(monkeypatch, tmp_path, token=...)` harness with the gate tests. Follow them exactly. [Source: templates/queue.html; app/web/routes_queue.py; static/css/brand.css; tests/test_queue.py]

### Testing standards
- Offline by construction: temp SQLite, hand-seeded `ocr_results`/`llm_results` rows (reuse `tests/test_scoring.py`'s seeding helpers), `SCHEDULER_ENABLED=false`, no provider/network. Highest-value tests: **AC1** real-figure render (assert against `score_corpus` over the same DB), **AC4** empty state (no zeros), **AC5** best-in-group highlight, **AC3** CPU flag icon+word, **AC6** token gate + unpriced-model "not priced" + no off-`/static` asset. Mirror `tests/test_queue.py` rigor. [Source: tests/test_queue.py; tests/test_scoring.py]

### Project Structure Notes
- New files: `app/web/routes_benchmark.py`, `templates/benchmark.html`, `tests/test_benchmark.py`. Modified: `app/main.py` (register router), `static/css/brand.css` (benchmark CSS section). Paths follow the architecture's web/templates/static layout used by every Epic-4 screen. No schema change, no new dependency (stdlib + existing FastAPI/Jinja2). [Source: app/main.py:104–113; templates/; static/css/]

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.4] — story statement + ACs (matches the mockup exactly; honest empty state; grounded recommendations; tokens per DESIGN.md; read-only; side-by-side mockup check in DoD). *(FR-23, UX-DR-5, NFR-5)*
- [Source: _bmad-output/planning-artifacts/epics.md Overview] — the binding **UI-fidelity standard** (layout/composition/USWDS/states/exact copy; spine wins on conflict; mockup scaffolding excluded; side-by-side DoD).
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/benchmark-report.html] — the named mockup: evaluator header + badge, Recommendations callout, grouped comparison table (columns accuracy/latency/cost-1000/CPU-only), best-in-group highlight, legend, honesty note, footer meta.
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/DESIGN.md] — tokens: civic green `#2E5B46`, PASS `#216E29`, REVIEW `#7A5900`, FAIL `#B50909`; Public Sans body ≥16px / Roboto Mono numerics; squared corners; color never alone (icon+word+color).
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/EXPERIENCE.md] — Benchmark comparison-table component pattern (line 91); the "No benchmark runs yet" empty-state row (line 117); Voice/Tone "honesty stated plainly".
- [Source: app/benchmark/scoring.py] — `score_corpus(conn) -> CorpusScore`; `ExtractorScore.field_match_rate` etc.; keys `(engine_name, image_variant)` / `model_id`; `scored_submissions`.
- [Source: app/benchmark/cost.py] — `cost_corpus(conn) -> CostReport`; `EngineCost`/`ModelCost`/`LatencyStats`; `cost_per_1000` (`Decimal` / `None`), `cost_basis` (NFR-5 label); same keys as scoring.
- [Source: app/web/routes_queue.py] — the route module pattern: APIRouter, `connect(settings.database_path)`, `templates.TemplateResponse(request, "name.html", ctx)`, AR-5 read-only docstring.
- [Source: app/main.py] — router registration (129–136); token-gate middleware (119–127); `Jinja2Templates` + `app.state.templates` (108–113); `/static` mount (104).
- [Source: templates/base.html] — the app shell + `{% block header/content/title/scripts %}`; `_help_panel.html` include; global `help.js`/`shortcuts.js`.
- [Source: static/css/brand.css] — `:root` brand/verdict tokens; the per-screen CSS-section convention (queue/review/help) to follow for the benchmark section.
- [Source: tests/test_queue.py] — the `_client(monkeypatch, tmp_path, token=...)` TestClient harness + the token-gate tests; [Source: tests/test_scoring.py] — the offline ocr/llm-row seeding approach to reuse.
- [Source: _bmad-output/project-context.md] — AR-5 (5s read path), AR-4 (engine-agnostic), NFR-2 (zero egress / same-origin assets), NFR-5 (honesty), the four contracts, read-only posture.

## Dev Agent Record

### Agent Model Used

Amelia (dev-story workflow) · claude-opus-4-8

### Debug Log References

- `tests/test_benchmark.py` written first (red): 12 tests over AC1–AC6 returned 404 (route absent) — confirmed RED before implementation.
- One test-expectation correction post-implementation: `test_benchmark_empty_state_no_zeros` initially asserted the substring `"$0.00"` was wholly absent, but the honesty note legitimately *says* "$0.00" as explanatory copy (the spec/mockup require that line). Tightened the assertion to the table **structure** (`benchmark__table` / `num` cells absent) so it tests the real AC4 intent — no fabricated measurement row — not a copy substring. Green after.
- Full gate `bash scripts/ci.sh --fix`: ruff format reformatted the new `routes_benchmark.py` (cosmetic), lint clean, mypy clean (96 source files), pytest **757 passed, 1 skipped** — no regressions.

### Completion Notes List

- `GET /benchmark` is a thin presentation layer: it CONSUMES `scoring.score_corpus(conn)` (5.2) and `cost.cost_corpus(conn)` (5.3) over a read-only `connect()` and zips them row-for-row by their shared keys — it never re-scores/re-times/re-prices (AR-4 keeps 5.2/5.3 engine-agnostic). Pure pre-computed DB read (AR-5): no provider client, no socket, no inference at request time. (AC1)
- Display-name resolution lives at the route boundary (module dicts `_ENGINE_LABELS` / `_MODEL_LABELS`), never in the scorer's SQL or the template; unknown keys fall back to the raw `engine_name`/`model_id` verbatim (honest, never blank). (AC2)
- Best-in-group highlight + the "Recommended" pill are **derived** in `_best_key` (max `field_match_rate`, ties broken by sorted key, `None` skipped), so they track the real figures. (AC5)
- CPU-only flag is icon+word+color: OCR → ✓ Yes (`--verdict-pass`), models → ⚠ No — API (`--verdict-review`); color never carries meaning alone. (AC3)
- Honest empty state gated on `has_data`: before any run, the "No benchmark runs yet" callout shows in place of the table — no table of zeros. (AC4)
- Pricing honesty: `_fmt_cost` renders an unpriced model (`cost_per_1000 is None`) as "not priced", never a fabricated `$0.00`; local OCR genuinely carries `Decimal("0")` → `$0.00`. (Note: `cost.DEFAULT_PRICING` is intentionally empty, so every model is currently unpriced — the honesty path is the default path.) The honesty note states "indicative, not audited" + "published API prices proxy internal model cost". (AC6)
- Read-only (no form/decision control); token-gated by the app-wide middleware (carries no exemption — verified by the 303→/access test); all assets same-origin `/static` (no CDN, asserted). The evaluator header (nav + "Evaluator build" badge) overrides `{% block header %}` for this screen only, still including `_help_panel.html`. (AC2, AC6)
- Mockup-only scaffolding (`.device` frame, URL bar, placeholder figures `96.4`/`240 sample labels`/`seed-2026-06-12`) excluded; verdict chips kept off the surface; CSS in `brand.css` (spine tokens), no inline `<style>`. (AC2)

### File List

- `app/web/routes_benchmark.py` — NEW. The `GET /benchmark` route + the presentation view-model (`BenchmarkRow`, `_build_engine_rows`/`_build_model_rows`, `_best_key`, `_fmt_*`, display-name maps).
- `templates/benchmark.html` — NEW. Extends `base.html`; overrides the header block for the evaluator header; renders the Recommendations callout, the grouped comparison table OR the empty state, the legend, the honesty note, and the footer meta.
- `static/css/brand.css` — MODIFIED. Added the `/* Benchmark Report (Story 5.4) */` section (evaluator header, `.benchmark__*` table/flag/reco/honesty/empty/footer) resolving to `--brand-*`/`--verdict-*` tokens.
- `app/main.py` — MODIFIED. Imported + registered `benchmark_router` (no exemption — token-gate protected).
- `tests/test_benchmark.py` — NEW. 14 offline tests over AC1–AC6 (12 at implementation + 2 CR regression tests: CPU-GPU flag honesty, cost-only-extractor-not-dropped).

### Change Log

| Date | Description |
|------|-------------|
| 2026-06-14 | Story 5.4 drafted — Benchmark Report screen (`GET /benchmark` + `templates/benchmark.html` + brand.css section): renders the typed `CorpusScore` (5.2) and `CostReport` (5.3) as the side-by-side comparison table matching `mockups/benchmark-report.html` (spine wins), with the honest "No benchmark runs yet" empty state, CPU-only icon+word+color flag, derived best-in-group highlight, grounded recommendations, and the NFR-5 honesty note; read-only, token-gated, zero-egress. Status → ready-for-dev. |
| 2026-06-14 | Story 5.4 implemented (test-first). Added `app/web/routes_benchmark.py` (read-only `GET /benchmark` consuming 5.2/5.3), `templates/benchmark.html` (evaluator-header override + grouped table / empty state / honesty note / footer), the `brand.css` benchmark section, registered the router in `app/main.py`, and `tests/test_benchmark.py` (12 tests, AC1–AC6). Full gate green: ruff format + lint clean, mypy clean, pytest 757 passed / 1 skipped (no regressions). Status → review. |
| 2026-06-14 | **Code review (CR)** — adversarial 3-layer review (Blind / Edge-Case / Acceptance). Applied 3 honesty patches: (1) **AC3/NFR-5** — the CPU-only flag was hard-coded "✓ Yes"; now honors the captured `EngineCost.cpu_only` (True ⇒ ✓ Yes, False ⇒ ✗ No — GPU, None ⇒ ? Unknown), so the flag tells the truth about how the OCR row was actually run. (2) **AC1/honesty** — the view-model iterated only the score's keyset, silently dropping any cost-only extractor (gold-less submissions are skipped by `score_corpus`); now zips the **union** `set(score.engines)\|set(report.engines)` so every measured engine appears (accuracy "—" when un-scored). Hardened the row-key delimiter from `\|` to `\x00`. (3) **AC6** — `ModelCost.cost_basis` was computed but never surfaced; added a `cost_basis` field to `BenchmarkRow` and rendered it as the pricing-basis sub-label under the cost cell. Added 2 regression tests (CPU-GPU flag + cost-only-extractor-not-dropped) → 14 tests. CSS for `.benchmark__flag--unknown` / `.benchmark__cost-basis` (spine tokens). One AC5 copy-vs-data item (hard-coded Recommendations prose vs data-derived best-in-group) deferred to `deferred-work.md`. Producers (`scoring.py`/`cost.py`) untouched. Full gate green: ruff + mypy clean, pytest **759 passed / 1 skipped** (no regressions). Status → done. |
