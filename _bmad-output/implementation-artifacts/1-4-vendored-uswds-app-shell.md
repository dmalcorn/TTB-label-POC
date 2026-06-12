---
baseline_commit: dc0de45
---

# Story 1.4: Vendored USWDS app shell & Treasury brand layer

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Label Specialist and an evaluator,
I want the application chrome rendered in self-hosted USWDS with the Treasury brand layer,
so that every screen inherits the federal design system and firewall-safe assets.

## Acceptance Criteria

**AC-1 — USWDS 3.x vendored, self-hosted; every asset request same-origin**
**Given** USWDS 3.x compiled assets vendored into `static/uswds/` (CSS, JS, fonts, icon sprite) with **Public Sans** and **Roboto Mono** self-hosted (they ship inside the USWDS font set)
**When** any page renders from `templates/base.html`
**Then** every CSS / JS / font / icon request is **same-origin** (served from `/static/...`) — **no CDN, no Google Fonts, no build step, no runtime download**
**And** the served HTML contains zero references to `cdn.`, `fonts.googleapis.com`, `fonts.gstatic.com`, `unpkg`, `jsdelivr`, or any absolute `http(s)://` asset URL.

**AC-2 — Treasury brand-layer tokens applied, replacing USWDS default blue**
**Given** the Treasury brand-layer tokens from `DESIGN.md`
**When** the shell renders
**Then** a same-origin brand stylesheet (loaded **after** the USWDS stylesheet) applies primary navy `#112E51`, civic green `#2E5B46`, base canvas `#F0F0F0`, ink `#1B1B1B`, and the squared-corner radii (sm 2 / md 4 / lg 8, pill `999px` reserved for status chips), **replacing the USWDS default blue** on chrome (header, primary register)
**And** the brand tokens are defined **once** as CSS custom properties (single source) — no per-screen hard-coded hexes
**And** body type resolves to Public Sans at the ≥16px floor (`DESIGN.md` Typography).

**AC-3 — Utility header matches the across-mockups composition**
**Given** the header composition shown across `mockups/queue.html` and `mockups/review-workspace.html`
**When** `templates/base.html` renders
**Then** the utility header is a full-width navy bar containing, in order: the round **seal** (`U.S. TREAS`, `aria-hidden`), the **"TTB Label Review"** title, a flex spacer, and the **`[?]` Help control** (`aria-label="Help"`, a `<button>`)
**And** **mockup-only placeholder data is excluded** — the `J. Park` agent name is illustrative scaffolding and is **not** reproduced (no fabricated specialist identity in the shell)
**And** the header is provided by `base.html` so every later screen inherits it from one place (the Help control's slide-over behavior is Story 4.4 — here it is a present, focusable control, not yet wired).

**AC-4 — Shell renders fully styled with zero egress under `--network none`**
**Given** the firewall posture (NFR-2, AR-8)
**When** the shell renders under `docker run --network none`
**Then** the page is **fully styled** and both fonts load with **no missing-asset request** and no outbound call
**And** the egress proof is the existing `--network none` boot plus a fetch of the shell page returning 200 with the USWDS + brand stylesheets and fonts served locally. *(UX-DR-6, NFR-2, NFR-4)*

**AC-5 — One concrete page demonstrates the shell, on the 5s read-path contract**
**Given** the shell must be demonstrable end-to-end
**When** a minimal route renders a page extending `base.html`
**Then** `GET /` returns 200 HTML with the header and a `{% block content %}` body region (placeholder content that Stories 1.5 / 4.x replace), wired via Jinja2 templates and a FastAPI `StaticFiles` mount
**And** the render is a **pure template render** — no DB read beyond what already exists, no OCR, no inference, no model import, no network (AR-5 holds; this is chrome, not a data screen).

*(Source: epics.md Story 1.4; FR (chrome foundation for FR-1..FR-8); UX-DR-6 (USWDS foundation, self-hosted), UX-DR-15 (accessibility floor); DESIGN.md Colors/Typography/Shapes/Components; AR-8/AR-11; NFR-2/NFR-4.)*

> **Scope note (binding).** This story ships the **chrome only**: vendored USWDS assets, `templates/base.html` (header + brand-layer CSS + asset links + content block), the static mount + Jinja2 wiring in `app/main.py`, and **one** minimal page (`GET /`) to demonstrate it. It does **NOT** ship the token-gate screen (Story 1.5), the Queue screen (Story 4.1), the Help slide-over panel (Story 4.4), or any data-bearing view. Do **not** add routers/screens beyond the single demonstrator. The `[?]` control is present and focusable but inert (no panel) until Story 4.4.

## Tasks / Subtasks

- [x] **Task 1 — Vendor USWDS 3.x compiled assets into `static/uswds/` (AC: 1)**
  - [x] Fetched the **USWDS 3.13.0 compiled `dist`** via `npm pack @uswds/uswds@3.13.0` (one-time dev-time; no Node/build step in app or Docker). Vendored the runtime subset: `css/uswds.min.css(.map)`, `js/uswds.min.js` + `uswds-init.min.js` (+maps), `fonts/`, `img/` (incl. `sprite.svg`).
  - [x] **Public Sans** and **Roboto Mono** present under `static/uswds/fonts/`. Pruned `.ttf`/`.woff` (the compiled CSS references **only** `.woff2` — 18 refs), keeping all `.woff2` (incl. Public Sans for the brand `@font-face`). Tree trimmed 12M → 7.5M.
  - [x] Committed (not gitignored). Provenance + regen recorded in `static/uswds/VERSION` (`3.13.0`) and `static/uswds/README.md`.
- [x] **Task 2 — Brand-layer stylesheet `static/css/brand.css` (AC: 2)**
  - [x] `DESIGN.md` tokens declared **once** as `:root` custom properties (navy/dark/light, civic green, base/surface/ink/ink-muted/border; radii 2/4/8/pill; verdict + beverage tokens declared for later stories, **unused on chrome**).
  - [x] Treasury navy overrides USWDS default blue on the primary register (`.usa-button`, links) + header — brand-layer delta only, USWDS components otherwise as-is.
  - [x] Header styled (`.app-header`/`__seal`/`__title`/`__spacer`/`__help`) transcribed from `mockups/queue.html`; **spine deltas applied** — `[?]` bumped 40px→**48px** (DESIGN.md ≥48px floor). `brand.css` loaded **after** `uswds.min.css`. **Finding:** the default compiled USWDS theme renders *Source Sans Pro Web*, not Public Sans — so Public Sans is self-hosted via `@font-face` (vendored woff2) and preferred for body, with Source Sans Pro Web as the still-same-origin fallback.
- [x] **Task 3 — `templates/base.html` shell (AC: 1, 2, 3, 5)**
  - [x] `base.html`: DOCTYPE, `lang="en"`, viewport; `uswds-init` in `<head>`; `<link>` `uswds.min.css` then `brand.css`; `uswds.min.js` before `</body>` (all same-origin); utility header partial; `{% block content %}` + `{% block title %}`.
  - [x] Semantic `<header>` + `<button aria-label="Help">`; seal `aria-hidden`; **no `J. Park`/placeholder**; body ≥16px via tokens; `[?]` ≥48px target; `<main id="main-content">`.
  - [x] Icon sprite available same-origin at `/static/uswds/img/sprite.svg` (served 200; used by later `usa-icon` markup).
- [x] **Task 4 — Wire Jinja2 + StaticFiles + demonstrator route in `app/main.py` (AC: 5)**
  - [x] Mounted `StaticFiles` at `/static` and configured `Jinja2Templates`, both resolved from `BASE_DIR` (cwd-independent). Startup stays network-free (local file I/O only — AR-5/AR-8 intact).
  - [x] Added `GET /` → `TemplateResponse(request, "index.html")` (extends `base.html`, minimal placeholder content 1.5/4.x replace). `/healthz` untouched.
  - [x] Dockerfile already `COPY templates ./templates` + `COPY static ./static` (`Dockerfile:31-32`) — vendored tree bakes in; no Dockerfile change needed.
- [x] **Task 5 — Tests `tests/test_shell.py` (AC: 1, 2, 3, 5)**
  - [x] `GET /` → 200 `text/html`; header title + `[?]` `aria-label="Help"` present.
  - [x] **Same-origin assertion:** HTML-parses every `href`/`src`, rejects `http(s)://`/`cdn`/`googleapis`/`gstatic`/`unpkg`/`jsdelivr`, asserts all start `/static/`, and `uswds.min.css` before `brand.css`.
  - [x] **No placeholder leakage:** asserts `J. Park` absent.
  - [x] **Vendored presence + serve:** 7 assets (USWDS CSS/JS/init, brand CSS, Public Sans + Roboto Mono woff2, sprite) exist on disk and `TestClient`-serve 200; plus a brand-CSS `@font-face`/Public-Sans assertion. 8 tests, all green; `/healthz` regression test included.
- [x] **Task 6 — Firewall verification (AC: 4)**
  - [x] Built `ttb-label-poc:1.4`; ran `docker run --network none` (inspect confirms `none` network, no IP/gateway). In-container probe: `GET /` 200 + shell markup, no `J. Park`, and all six assets (CSS/JS/Public Sans + Roboto Mono fonts/sprite) serve 200 → fully styled, **zero egress**.

## Dev Notes

### Scope guardrails (read first)
- **Chrome only.** `base.html` + vendored USWDS + brand CSS + static/Jinja2 wiring + **one** demonstrator page (`GET /`). No token gate (1.5), no Queue (4.1), no Help panel (4.4), no data view. The `[?]` is a present, focusable, **inert** control here.
- **No build step, ever.** USWDS is vendored as **compiled `dist`** and committed; the app and Docker image carry the files as-is. Do not add Node, `npm`, `gulp`, or `uswds-compile` to the runtime/image. The only "build" is the dev-time one-time fetch of the dist, done on the host.
- **5s read-path / zero-egress invariants hold (AR-5/AR-8):** rendering the shell is a pure local template render — no DB beyond existing `init_db`, no OCR/model import, no network. The `--network none` shell fetch (AC-4) is the proof, exactly like 1.1's `/healthz` boot.

### USWDS vendoring — how to self-host without a build (the load-bearing detail)
- USWDS 3.x ships a **packaged compiled output** (`@uswds/uswds` `dist/`): `dist/css/uswds.min.css`, `dist/js/uswds.min.js` + `dist/js/uswds-init.min.js`, `dist/fonts/` (includes **Public Sans** and **Roboto Mono** — that's why no Google Fonts call is needed), `dist/img/` (includes `sprite.svg`). Copy that `dist` tree into `static/uswds/`. This is the firewall-safe path: the compiled CSS already references fonts/img by **relative** path, so once the tree is under `/static/uswds/` every request is same-origin.
- If the dist is fetched via npm on the host, that is a **dev-time** action — the resulting files are committed and shipped; `node_modules`/tooling must **not** enter `requirements.txt` or the image. (Same posture as 1.3's OpenCV generator: dev-only tool, committed output ships.)
- Pin and **record the exact USWDS 3.x version** vendored (`static/uswds/VERSION`). Per project-context tech stack: "USWDS 3.x compiled assets, vendored/self-hosted in `static/uswds/` (no CDN, no Node build)."

### Header composition — transcribe from the mockups (don't invent)
- Source CSS + markup: `mockups/queue.html` `.app-header` block (lines ~94–128) and its header markup (lines ~279–285); identical header appears in `mockups/review-workspace.html`. Structure: navy (`--primary`) bar, `gap:16px`, `padding:14px 24px`; round **seal** 40px (white bg, navy text, `U.S.<br>TREAS`, `aria-hidden`); `.app-header__title` 19px/700 "TTB Label Review"; `.app-header__spacer{flex:1}`; the `[?]` button 40px, 2px white outline, transparent bg, `radius-md`, `aria-label="Help"`.
- **Excluded scaffolding (UI fidelity standard):** the `J. Park` agent name (`.app-header__agent`) is placeholder data — **omit it**. The token-gate mockup's **browser device frame** (`.device*`) and **state-label** chrome are illustrative and never reproduced. (`mockups/token-gate.html` has **no** app-header — it's the pre-auth screen; the header is a post-auth chrome element, correctly introduced here.)
- **Spine wins on conflict:** where a mockup's inline CSS diverges from `DESIGN.md`, use `DESIGN.md` values. For the shell the relevant tokens (navy `#112E51`, base `#F0F0F0`, ink `#1B1B1B`, radii 2/4/8) agree between mockup and spine; keep them sourced from `brand.css` custom properties, not duplicated literals.

### Brand-layer tokens (from DESIGN.md front-matter — single source)
- Colors: primary `#112E51` · primary-dark `#0B1D35` · primary-light `#205493` · secondary `#2E5B46` · base `#F0F0F0` · surface `#FFFFFF` · ink `#1B1B1B` · ink-muted `#5C5C5C` · border `#DCDEE0`.
- Radii: sm `2px` (inputs/tags) · md `4px` (cards/buttons) · lg `8px` (modals/image panel) · **pill `999px` only on status chips** (not used by the shell).
- Type: Public Sans body, **16px floor**, line-height 1.5; Roboto Mono reserved for OCR raw (not used by the shell but the font must be present/self-hosted). Display 22px/700 for titles.
- **Verdict palette and beverage accents are NOT used on chrome** — declaring them as tokens is fine (forward use), but the header/shell carry **navy/civic-green only** (DESIGN.md "verdict palette … not reused for chrome, buttons, or links").

### Architecture compliance (must-follow)
- **Self-hosted, same-origin, no CDN/build** (UX-DR-6, NFR-2): every CSS/JS/font/icon under `/static`. This is the AC-1 + AC-4 core and the project's firewall spine.
- **USWDS used as-is, brand layer is a thin delta** (DESIGN.md Do/Don't): do not reimplement or restyle USWDS components beyond the navy/civic-green brand override and the domain tokens.
- **`app/web/` is the web layer** per the architecture tree — if you factor the route out of `main.py`, it belongs under `app/web/`. For a single demonstrator route, keeping it in `main.py` alongside `/healthz` is acceptable and minimal; do not front-load a router framework the later screens will define.
- **Accessibility floor (UX-DR-15, NFR-4):** body ≥16px, visible focus (USWDS default kept), tab order = reading order, `[?]` target ≥48px (mockup draws 40px — bump to the 48px DESIGN.md floor; spine wins), `lang="en"`, semantic landmarks (`<header>`, `<main>`).
- **5s read-path (AR-5):** the shell render touches no heavy work and no network.

### Project Structure Notes
- New: `static/uswds/**` (vendored dist), `static/css/brand.css`, `templates/base.html`, `templates/index.html` (or inline minimal page), `tests/test_shell.py`. UPDATE: `app/main.py` (StaticFiles mount + Jinja2 + `GET /`).
- `templates/` and `static/{uswds,js}/` currently hold only `.gitkeep` (Story 1.1) — add real content alongside/replacing the keeps. `static/css/` is new.
- Dockerfile already `COPY templates ./templates` and `COPY static ./static` (`Dockerfile:31-32`) — the vendored tree bakes into the image automatically; verify after adding files. No `.dockerignore` rule should exclude `static/uswds/`.

### Previous story intelligence (1.1 / 1.2 / 1.3)
- App factory: `app/main.py` `create_app()` with a `lifespan` that calls `init_db(settings.database_path)`; `GET /healthz` returns `{"status":"ok"}`. Add the static mount + Jinja2 templates inside `create_app()` (after settings), and the `GET /` route beside `healthz`. Keep `/healthz` import-light and network-free.
- Run tests via `.venv/Scripts/python.exe -m pytest -q`; lint `.venv/Scripts/ruff.exe check . --exclude .venv` + `ruff format --check`. Story 1.3 left the host suite green (51 passed). Keep it green; `jinja2~=3.1` is already a pinned dependency (1.1 `requirements.txt`).
- `TestClient(create_app())` is the established test harness (`tests/test_healthz.py`). Reuse it for the shell tests. Keep tests from writing into the repo; the shell route does no DB writes.
- Offline-proof pattern (1.1/1.3): `docker run --network none …` then exercise the route in-container — replicate for the shell fetch (AC-4).
- **Forward note from 1.1 review (deferred item):** a future global auth gate (Story 1.5) must **exempt `/healthz`** (and static) so the Docker HEALTHCHECK and asset serving don't 401. Not this story's job, but keep `GET /` and `/static` simple so 1.5 can wrap them cleanly.

### Testing
- Highest-value test here is the **same-origin / no-egress assertion** (AC-1): scan the rendered `GET /` HTML and reject any `cdn`/`googleapis`/`gstatic`/`unpkg`/`jsdelivr`/absolute-URL asset reference; assert load order (`uswds.min.css` before `brand.css`). This is the unit-level guardian of the firewall posture that the `--network none` run proves end-to-end.
- Assert the header contract (title text + `[?]` `aria-label`) and the **absence** of `J. Park` (fidelity/scaffolding exclusion).
- Assert vendored files exist on disk and each serves 200 via `TestClient` (USWDS CSS/JS, brand CSS, a Public Sans + a Roboto Mono font).

### Definition of Done — UI fidelity (binding)
- Per the **UI fidelity standard** (epics.md Overview), this UI story's DoD includes a **documented side-by-side comparison** of the running shell's **utility header** against the header as composed in `mockups/queue.html` / `mockups/review-workspace.html` — structure, USWDS composition, and copy ("TTB Label Review", `[?]`) — with the noted spine-over-mockup deltas applied (48px `[?]` target; `J. Park` excluded; device-frame/state-label scaffolding excluded). Record the comparison in the Dev Agent Record.

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.4: Vendored USWDS app shell & Treasury brand layer]
- [Source: _bmad-output/planning-artifacts/epics.md#UX-DR-6 — USWDS foundation, self-hosted] / [#UX-DR-15 — Accessibility floor]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/DESIGN.md#Colors] / [#Typography] / [#Shapes] / [#Components] / [#Do's and Don'ts]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/queue.html] (utility header CSS + markup; `J. Park` is excluded scaffolding)
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/token-gate.html] (pre-auth screen — no app-header; device frame is excluded scaffolding)
- [Source: _bmad-output/project-context.md#Technology Stack & Versions] (USWDS 3.x vendored, no CDN/Node build; Public Sans + Roboto Mono self-hosted) / [#UI Fidelity & USWDS Discipline] / [#Firewall & Offline Posture]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries] (templates/static/web layout)
- AR-8 (offline/pinned), AR-11 (tooling/structure), NFR-2 (firewall), NFR-4 (accessibility) [Source: epics.md]

## Dev Agent Record

### Agent Model Used

Amelia (BMad dev-story) — claude-opus-4-8[1m]

### Debug Log References

- Vendoring: `npm view @uswds/uswds version` → **3.13.0** (latest 3.x). `npm pack @uswds/uswds@3.13.0` → extracted `package/dist`. Confirmed the default compiled `uswds.min.css` `@font-face`-references **only `.woff2`** and uses *Source Sans Pro Web* as the sans family (Public Sans shipped but not the default theme face). Vendored `css`/`js`/`fonts`/`img`; pruned `.ttf`/`.woff` → `static/uswds` 12M → **7.5M**.
- RED: `pytest tests/test_shell.py` → 5 failed (missing `/` route + `/static` mount), 3 passed (disk presence, `/healthz`, brand `@font-face`). GREEN after wiring `StaticFiles` + `Jinja2Templates` + `GET /` → **8 passed**.
- Full suite: **69 passed**, `ruff check` clean, `ruff format --check` clean (26 files).
- AC-4 offline proof: `docker build -t ttb-label-poc:1.4 .` → ok. `docker run -d --network none …`; `docker inspect` → network `none` (no IP/gateway). In-container `urllib` probe: `GET /` 200 with shell markup + `aria-label="Help"`, no `J. Park`; `/static/uswds/css/uswds.min.css`, `/static/css/brand.css`, `/static/uswds/js/uswds.min.js`, Public Sans woff2, Roboto Mono woff2, and `img/sprite.svg` each 200 → **fully styled, zero egress**.
- Known non-blocking warning: pre-existing Starlette `httpx`/TestClient deprecation (carried from 1.1); current pins work.

### Completion Notes List

- **AC-1** — USWDS 3.13.0 vendored, self-hosted under `/static/uswds`; brand layer at `/static/css/brand.css`. Same-origin enforced by the HTML-parsing test (no CDN/Google Fonts/absolute URLs) and proven end-to-end under `--network none`. The compiled CSS's internal `url(../fonts|../img …)` references resolve same-origin by construction.
- **AC-2** — Treasury tokens single-sourced in `brand.css` `:root`; navy replaces USWDS blue on chrome/primary; squared radii applied; **Public Sans self-hosted** via `@font-face` (woff2) and preferred for body at the 16px floor. `uswds.min.css` loads before `brand.css` (asserted).
- **AC-3** — Utility header in `base.html` (navy bar · seal · "TTB Label Review" · spacer · `[?]`), inherited by every screen. `J. Park` placeholder excluded; `[?]` is present/focusable but inert until Story 4.4.
- **AC-4** — `--network none` container renders the fully-styled shell with all assets served locally; zero outbound calls.
- **AC-5** — `GET /` renders `index.html` (extends `base.html`) as a pure template read — no DB/OCR/model/network (AR-5 intact). `/healthz` unchanged.

**UI fidelity — documented side-by-side (DoD).** Running shell header vs `mockups/queue.html` / `review-workspace.html` `.app-header`:

| Element | Mockup | Shell (running) | Verdict |
|---|---|---|---|
| Bar | navy `#112E51`, flex, gap 16, padding 14×24 | identical (token `--brand-primary`) | match |
| Seal | 40px round, white-on-navy, `U.S.`/`TREAS`, `aria-hidden` | identical | match |
| Title | "TTB Label Review", 19px/700 | identical | match |
| Spacer | `flex:1` | identical | match |
| Agent name | `J. Park` (placeholder) | **excluded** | spine delta (scaffolding) |
| `[?]` Help | 40px outline button | **48px** outline button, `aria-label="Help"` | spine delta (≥48px floor) |
| Device frame / state labels | present | **excluded** | spine delta (scaffolding) |

Deltas are the mandated spine-over-mockup adjustments (48px target; placeholder/scaffolding excluded). Structure, USWDS composition, and copy otherwise match.

### File List

- `app/main.py` (modified — `StaticFiles` mount, `Jinja2Templates`, `GET /` shell route; `BASE_DIR`/`STATIC_DIR`/`TEMPLATES_DIR`)
- `templates/base.html` (new — shell: header + asset links + content block)
- `templates/index.html` (new — minimal shell demonstrator)
- `static/css/brand.css` (new — Treasury brand layer + Public Sans `@font-face`)
- `static/uswds/css/uswds.min.css` (+`.map`) (new — vendored USWDS 3.13.0)
- `static/uswds/js/uswds.min.js`, `uswds-init.min.js` (+`.map`) (new — vendored)
- `static/uswds/fonts/{public-sans,roboto-mono,source-sans-pro,merriweather}/*.woff2` (new — vendored, woff2 only)
- `static/uswds/img/**` (new — vendored sprite + usa-icons + component images)
- `static/uswds/VERSION` (new — `3.13.0`), `static/uswds/README.md` (new — provenance/regen)
- `static/uswds/.gitkeep` (deleted — replaced by real content)
- `tests/test_shell.py` (new — 8 tests: render, same-origin, load order, no-placeholder, presence+serve, regression)
- `_bmad-output/implementation-artifacts/1-4-vendored-uswds-app-shell.md` (story tracking)

## Change Log

| Date | Change |
|------|--------|
| 2026-06-12 | Story 1.4 drafted — vendored USWDS app shell & Treasury brand layer. Status → ready-for-dev. |
| 2026-06-12 | Story 1.4 implemented — vendored USWDS 3.13.0 (self-hosted, woff2-only, 7.5M), Treasury brand layer + self-hosted Public Sans, `base.html` shell + utility header (J. Park excluded, `[?]` 48px), `StaticFiles`/Jinja2 + `GET /`. 8 shell tests + 69 total green; ruff clean; `--network none` fully-styled zero-egress proof. Status → review. |
