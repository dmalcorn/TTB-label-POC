---
baseline_commit: 7138a75
context:
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/EXPERIENCE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/token-gate.html
  - _bmad-output/implementation-artifacts/deferred-work.md
---

# Story 1.5: Token-gated access and clean denial

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an evaluator,
I want a lightweight token gate with no login ceremony,
so that I can reach the full demo while the public and bots cannot, and a bad token leaks nothing.

## Acceptance Criteria

**AC-1 — Token-gate dependency enforces the access boundary**
**Given** a FastAPI token-gate dependency reading `ACCESS_TOKEN` from env (via `app/config.py` Settings)
**When** a request arrives carrying the valid token (the access cookie set after a successful entry)
**Then** the request reaches the protected route
**And when** the token is absent or invalid, the request is denied with **no Submission data, image bytes, or Benchmark figures** anywhere in the response payload — only the gate screen.
**And** token comparison is constant-time (`hmac.compare_digest`), and the token value is never logged.

**AC-2 — Gate screen matches `token-gate.html` exactly (both states)**
**Given** the token-gate screen rendered from a server template
**When** State 1 (token entry) and State 2 (clean denial) render at runtime
**Then** each **matches [`mockups/token-gate.html`](../planning-artifacts/ux-designs/ux-TTB-label-POC-2026-06-12/mockups/token-gate.html) exactly** in layout, USWDS component structure, all depicted states, and visible copy:
  - centered access card (max-width 440px), navy seal, `<h1>` "TTB Label Review", sub-copy "Enter your access token to begin."
  - a single **autofocused** Access-token text input (`autocomplete="off"`), a navy **Enter** button ≥48px tall, and the helper copy ("Your token was sent with your assignment. No username or password — just paste the token and select Enter.")
  - **State 2** additionally shows the `role="status"` alert with head "Access token required." + body "We couldn't verify that token. Check it and try again, or use the link from your assignment.", and the token input rendered with `aria-invalid="true"` and the error border.
**And** all design tokens resolve to `DESIGN.md` values — **spine wins over any mockup CSS conflict** (navy `#112E51`, fail `#B50909`, radius 2/4/8, Public Sans, focus ring `4px #205493`).
**And** mockup-only scaffolding (browser device frame `.device*`, placeholder URL, the `state-label` captions) is **excluded** from the running page.

**AC-3 — `/healthz` and the gate's own surface are exempt; assets reachable**
**Given** the gate is applied app-wide
**When** an unauthenticated request hits `GET /healthz`, the gate GET/POST routes themselves, or `GET /static/*`
**Then** each is served **without** a token (so the Docker/Railway healthcheck passes, the entry page is reachable, and the gate page renders fully styled with same-origin USWDS assets + Public Sans).
**And** no other route is reachable unauthenticated.

**AC-4 — `ACCESS_TOKEN` absent/empty semantics are explicit**
**Given** the deferred decision on empty-vs-absent `ACCESS_TOKEN` ([deferred-work.md](deferred-work.md), Story-1.1 review)
**When** `ACCESS_TOKEN` is **unset or empty string**
**Then** the gate is **not enforced** (all routes reachable) — the documented AR-9 / `.env.example` "Absent ⇒ gate not enforced yet" dev posture, so a clean clone boots usable with nothing configured
**And when** `ACCESS_TOKEN` is a non-empty value, the gate **is** enforced for every non-exempt route.
*(This is a deliberate POC choice — fail-open-when-unconfigured for local dev, fully enforced once Railway sets the secret. The dev may flip to fail-closed if Diane prefers; flag it in the PR.)*

**AC-5 — Successful entry, denial, and DoD comparison**
**Given** a running app with `ACCESS_TOKEN` set
**When** the evaluator submits the correct token on the entry form
**Then** an `HttpOnly`, `SameSite=Lax`, `Secure`-in-prod access cookie is set and the evaluator is redirected to the post-gate landing route
**And** submitting an absent/wrong token re-renders State 2 (clean denial) with HTTP `401`, leaking nothing
**And** the story's Definition of Done includes a **documented side-by-side comparison of both running states** (State 1 entry, State 2 denial) against `mockups/token-gate.html`.

*(Source: epics.md Story 1.5; FR-25; UX-DR-1; AR-9; architecture.md §Authentication & Security, §Architectural Boundaries (API boundary); DESIGN.md §Colors/Typography/Components; EXPERIENCE.md §Information Architecture (Token gate), §State Patterns; deferred-work.md.)*

> **Dependency note (read first — Story 1.4 is DONE).** The shell foundation already exists — reuse it, do not rebuild:
> - `templates/base.html` — head with same-origin `<link>`s to `/static/uswds/css/uswds.min.css` then `/static/css/brand.css`, the utility header, and `{% block content %}` / `{% block title %}`.
> - `static/css/brand.css` — the **single source** of DESIGN.md tokens as `:root` CSS custom properties (navy `--…`, fail, radii 2/4/8, etc.) + the Public Sans `@font-face`. Resolve every gate token to these vars — never copy hex from the mockup.
> - `app/main.py` already mounts `StaticFiles` at `/static` and configures `Jinja2Templates(directory=TEMPLATES_DIR)` with `BASE_DIR/STATIC_DIR/TEMPLATES_DIR` constants. **Do NOT re-mount static or re-create the templates env** — reuse them.
> - **The gate page has NO app-header** (it is pre-auth; the header is post-auth chrome — 1.4 scope note + the `token-gate.html` mockup has no header). But `base.html` hardcodes the header directly in `<body>` (not a block). So **this story must wrap that header in `{% block header %}…{% endblock %}` in `base.html`** (an additive, regression-safe edit), then `access.html` extends `base.html` and overrides `{% block header %}{% endblock %}` empty. That keeps one asset source and avoids a duplicate bare layout. (1.4's `test_shell.py` still expects the header on `GET /` — keep the default block content intact so that test stays green.)
>
> The 5-second read contract is untouched: the gate is a cheap cookie/string compare, no DB read required to deny.

> **Scope note (binding):** This story adds the access boundary + the entry/denial screen **only**. It does **not** build the Queue, Review, Benchmark, or any protected content — those land in their own epics. The gate wraps whatever routes exist today: `/healthz` + `/static` + `/access` exempt; the **Story 1.4 shell at `GET /`** becomes the protected post-gate landing. Do not introduce user accounts, roles, sessions-beyond-the-shared-token, or an IdP (explicitly out of scope per architecture).

## Tasks / Subtasks

- [x] **Task 1 — Token-gate dependency `app/web/deps.py` (AC: 1, 3, 4)**
  - [x] Pure helpers `token_matches(submitted, settings)` / `has_valid_access(request, settings)` — constant-time `hmac.compare_digest` against `Settings.access_token` (the enforcement guard lives in `main.py`, so a per-route `require_access` dependency was unnecessary — the app-wide middleware reuses these helpers).
  - [x] `gate_enabled(settings) -> bool` = `bool(settings.access_token)` (treats `""` and `None` identically — resolves the deferred empty-vs-absent note). Disabled ⇒ guard is a pass-through.
  - [x] Exemption set `EXEMPT_PATHS={"/healthz","/access"}` + `EXEMPT_PREFIXES=("/static/",)` via `is_exempt(path)`. Implemented as an app-wide HTTP middleware (chosen over a per-route dep so `/healthz` stays a pure no-DB response and every future route is covered by default).
  - [x] Token/cookie value never logged.
- [x] **Task 2 — Access router `app/web/routes_access.py` (AC: 2, 5)**
  - [x] `GET /access` → State 1 entry (autofocused input); already-valid cookie → 303 to `/`. (`GET /` stays the 1.4 shell = protected landing.)
  - [x] `POST /access` → constant-time compare; success sets `HttpOnly`/`SameSite=Lax`/`Secure`-when-`https` cookie + 303 to `/`; failure re-renders State 2 with HTTP `401`, `aria-invalid`, and the `role="status"` alert. Uses FastAPI `Form(...)` — `python-multipart~=0.0.32` added to the pinned stack (**approved by Diane**).
  - [x] Router context carries only static gate copy — no submission/image/benchmark data (no-leakage; asserted).
- [x] **Task 3 — Template `templates/access.html` extending `base.html` (header block overridden empty) (AC: 2)**
  - [x] `{% extends "base.html" %}` + `{% block header %}{% endblock %}` (no app-header pre-auth) + centered card in `{% block content %}`. (`base.html` header wrapped in `{% block header %}` — additive, 1.4's `test_shell.py` stays green.)
  - [x] Faithful to `token-gate.html`: centered card, 56px seal, title, sub, **USWDS `.usa-input`** + ≥48px navy **`.usa-button`** Enter, helper. State 2 → **USWDS error Alert** (`role="status"`) + `aria-invalid`. Single `denied` flag drives both states.
  - [x] Tokens resolve to `static/css/brand.css` `:root` vars (spine wins); denial accent → spine fail `#B50909`. Device frame / URL / state-label scaffolding excluded.
- [x] **Task 4 — Wire the gate into `app/main.py` (AC: 1, 3)**
  - [x] Reused the 1.4 `StaticFiles` mount + `Jinja2Templates` (shared via `app.state.settings`/`app.state.templates`); included `access_router`; registered the app-wide gate middleware. `/`+future screens protected; `/healthz`/`/access`/`/static/*` exempt. Startup stays network-free.
- [x] **Task 5 — Tests `tests/test_token_gate.py` (AC: 1, 2, 3, 4, 5)**
  - [x] Valid cookie → protected shell; absent/invalid → 303 to `/access`; POST wrong → `401` State 2; **no-leakage** + token-never-echoed assertions.
  - [x] `/healthz`, `/static/*`, `/access` reachable unauthenticated; protected route is not.
  - [x] empty/absent `ACCESS_TOKEN` ⇒ gate open (AC-4); set ⇒ enforced.
  - [x] constant-time `token_matches` unit test + `compare_digest` source assertion.
  - [x] State-1 copy/structure + (in cookie-flow tests) State-2 `role="status"`/`aria-invalid`. **15 tests, all green.**

### Review Findings

_Code review 2026-06-12 (stories 1.4+1.5; Blind Hunter · Edge Case Hunter · Acceptance Auditor). **All ACs PASS** — 1.4 (shell) clean; 1.5 gate enforces correctly (constant-time, no-leakage, exemptions, fail-open-when-unset all verified). Two real defects cross-validated by two layers each; the rest are low/latent. Triaged below._

- [x] [Review][Patch] Non-ASCII token crashes the auth path — `hmac.compare_digest(str, str)` raises `TypeError` when either operand has a code point >127, surfacing as an unhandled **500 on the unauthenticated `POST /access`** (and on every gated request if `ACCESS_TOKEN` itself is non-ASCII). **FIXED:** `token_matches` now compares UTF-8 bytes. Regression: `test_token_matching_tolerates_whitespace_and_non_ascii`. [app/web/deps.py:51-63]
- [x] [Review][Patch] Pasted token with surrounding whitespace/newline → silent false denial — `token_matches` compared raw values; a token copied with a trailing `\n` never matched. **FIXED:** `.strip()` both operands (covers form + cookie paths uniformly). Regression: same test as above. [app/web/deps.py:51-63]
- [x] [Review][Patch] Missing State-2 regression assertions — `test_token_gate.py` asserted `role="status"`/`aria-invalid` but not the binding denial **body copy** nor `usa-input--error`. **FIXED:** both asserted in `test_post_wrong_token_denial_401_state2`. [tests/test_token_gate.py]
- [x] [Review][Defer] `Secure` cookie flag is OFF behind Railway's TLS-terminating proxy — `secure=request.url.scheme=="https"` sees `http` unless uvicorn runs with `--proxy-headers`/`--forwarded-allow-ips` (or `ProxyHeadersMiddleware`). **Owned by Story 1.6 deploy config** — the code is correct once forwarded-proto is trusted. [app/web/routes_access.py:55] — deferred to 1.6
- [x] [Review][Defer] 303 redirect coerces any non-exempt **non-GET** request into a GET of `/access` (silently masks a future unauthenticated `POST`). Latent — only `GET /` exists today; revisit when a protected non-GET route lands. [app/main.py] — deferred, latent
- [x] [Review][Defer] Denial path does not clear a stale `ttb_access` cookie (`delete_cookie` on deny would be cleaner). Minor UX; correct outcome today. [app/web/routes_access.py:46] — deferred, cosmetic
- [x] [Review][Defer] Exemption prefix match is un-normalized (case-variant `/Static`, double-slash `//static`, `/static/..`). Benign now (routes are case-sensitive; `StaticFiles` rejects traversal), but a path-rewriting proxy could change that. [app/web/deps.py:44-48] — deferred, benign today
- [x] [Review][Defer] `POST /access` buffers an unbounded form body — no length cap on the one unauthenticated body-accepting endpoint (minor DoS surface). [app/web/routes_access.py:41] — deferred, minor
- [x] [Review][Defer] No `?next=` preservation — a deep-linked unauthenticated user lands on `/` after entry, losing the intended destination. Latent until a third gated route exists. [app/main.py] — deferred, latent UX
- [x] [Review][Defer] State-2 error icon renders via the USWDS sprite CSS `background-image`, which can drop in forced-colors mode; the word "Access token required." still carries meaning (a11y floor met), so low-risk hardening only. [templates/access.html] — deferred, a11y hardening

### Project Structure Notes

- **New:** `app/web/deps.py`, `app/web/routes_access.py`, `templates/access.html`, `tests/test_token_gate.py`.
- **Update:** `app/main.py` (include access router + register gate guard — static mount & `Jinja2Templates` already wired by 1.4); `templates/base.html` (wrap the existing header in `{% block header %}…{% endblock %}` so the gate page can suppress it — additive, keeps 1.4's `test_shell.py` green). Possibly `app/config.py` only if a `gate_enabled` convenience is added there instead of `deps.py` (prefer `deps.py`).
- `routes_access.py` is a small structural addition to the `app/web/` tree (architecture maps FR-25 Demo Access to `web/{deps,routes_ops,routes_help}.py`; the entry/denial surface is part of that feature — note the added filename in the PR).
- `app/web/__init__.py` already exists (empty). Story 1.4 shipped `templates/base.html` + `templates/index.html`, `static/css/brand.css`, and the vendored `static/uswds/**` (USWDS 3.13.0, Public Sans + Roboto Mono woff2) — all present; reuse, don't recreate.

## Dev Notes

### Security posture (must-follow)
- **No data leakage (FR-25):** the denial path returns the gate screen and nothing else — no submission rows, no image bytes, no benchmark numbers, no stack traces. Test this explicitly.
- **Constant-time compare:** `hmac.compare_digest(submitted, settings.access_token)` — never `==` (timing oracle). Never log the token or the cookie.
- **Single shared token, no accounts.** Cookie is the transport after entry; `HttpOnly` + `SameSite=Lax`, and `Secure` when served over HTTPS (Railway). Keep it minimal — "no login ceremony."
- **Prefer the more restrictive option around the boundary** — but AC-4 is the one deliberate exception (fail-open only when *unconfigured*, for clone-and-run). Once `ACCESS_TOKEN` is set, every non-exempt route is closed.

### `/healthz` exemption is load-bearing
- The Dockerfile `HEALTHCHECK` and Railway healthcheck both hit `GET /healthz`. A global gate that 401s `/healthz` would mark the container unhealthy and fail deploy (explicit forward note in [deferred-work.md](deferred-work.md)). `/healthz` MUST stay a pure, ungated, no-DB response.
- Static assets must be ungated too, or the gate page renders unstyled (and Public Sans 404s) — which also breaks the offline `--network none` styling proof from Story 1.4.

### UI fidelity (hard requirement)
- The binding standard is **exact match to `mockups/token-gate.html`** for both states (layout, USWDS structure, every state, visible copy) — a documented side-by-side comparison is in the DoD (AC-5). This is Diane's recurring fidelity bar; do not approximate copy or spacing.
- **Spine wins on conflict:** resolve every token to `DESIGN.md` / `EXPERIENCE.md`, not the mockup's literal CSS where they differ. The mockup's inline `:root` vars happen to match DESIGN.md here (navy `#112E51`, fail `#B50909`, radii 2/4/8) — use the Story 1.4 brand-layer vars as the source, not copy-pasted hex.
- Verdict palette does **not** appear on this screen (no engine advice here); `#B50909` is used as the denial/error accent, paired with the "!" icon **and** the word "Access token required." (color never alone).
- Accessibility floor: body ≥16px, input/button targets ≥48px, visible 4px focus ring, autofocus on the token input, `role="status"` announces the denial, `aria-invalid` on the errored input. Tab order = reading order.

### Config inputs (already present from Story 1.1)
- `app/config.py` `Settings.access_token: str | None` is already wired from `ACCESS_TOKEN`. This story decides its empty-vs-absent semantics (AC-4) — both `None` and `""` mean "gate disabled."
- `.env.example` already documents `ACCESS_TOKEN` ("Absent ⇒ gate not enforced yet.") — consistent with AC-4; no `.env.example` change needed unless the wording is sharpened.

### Architecture compliance
- **API boundary (architecture §Architectural Boundaries):** "all routes behind the token-gate dependency (`web/deps.py`)" — this story creates that dependency. Read routes still touch only `db/repositories.py`; the gate adds no DB read on the deny path.
- **Firewall:** the gate is 100% local (cookie + string compare); zero egress. `docker run --network none` must still boot and serve `/healthz` and the gate page.
- **5-second read contract** untouched — denial is a constant-time compare, not a DB/OCR/inference call.
- **snake_case** everywhere; type hints required; ruff line length 100.

### Previous story intelligence (1.1 / 1.2 / 1.3)
- Run tests: `.venv/Scripts/python.exe -m pytest -q`; lint `.venv/Scripts/ruff.exe check . --exclude .venv` + `ruff format --check`. ~51 tests currently green — keep them green.
- `app/main.py` is an app factory (`create_app()`) that **already** mounts `/static` and configures `Jinja2Templates` (Story 1.4) and serves `GET /` (the shell) + `/healthz`. Add only the access router + gate guard, preserving the zero-network lifespan (`init_db` only). Reuse `BASE_DIR`/`TEMPLATES_DIR`.
- `app/main.py` exposes module-level `app = create_app()`; factory-path tests import `create_app` — add a TestClient-based test that drives the real `app` through the gate.
- Verify in-container too: `docker build` then `docker run --network none -e ACCESS_TOKEN=secret …` → `/healthz` 200 (ungated), gate page styled, protected route 401 without cookie.

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.5: Token-gated access and clean denial]
- [Source: _bmad-output/planning-artifacts/architecture.md#Authentication & Security] (single shared token, env `ACCESS_TOKEN`, clean denial, no accounts/IdP)
- [Source: _bmad-output/planning-artifacts/architecture.md#Architectural Boundaries] (API boundary: all routes behind `web/deps.py`)
- [Source: ux-designs/ux-TTB-label-POC-2026-06-12/mockups/token-gate.html] (both states; the exact-match target)
- [Source: ux-designs/ux-TTB-label-POC-2026-06-12/DESIGN.md#Colors/Typography/Components] (navy `#112E51`, fail `#B50909`, radii 2/4/8, Public Sans, ≥48px button)
- [Source: ux-designs/ux-TTB-label-POC-2026-06-12/EXPERIENCE.md#Information Architecture / State Patterns] (lightweight access, clean denial, no data leakage)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] (empty-vs-absent `ACCESS_TOKEN`; `/healthz` vs auth-gate exemption)
- FR-25 / UX-DR-1 / AR-9 [Source: epics.md]

## Dev Agent Record

### Agent Model Used

Amelia (BMad dev-story) — claude-opus-4-8[1m]

### Debug Log References

- **Dependency:** Starlette 1.3.1 `request.form()`/`Form(...)` requires `python-multipart` even for urlencoded bodies (verified: `AssertionError: python-multipart must be installed`). Initially shipped a stdlib `urllib.parse` workaround to avoid an unapproved dep; **Diane then approved adding it**, so `POST /access` was refactored to idiomatic FastAPI `Form(...)` and `python-multipart~=0.0.32` pinned in `requirements.txt`. Rebuilt image carries `python-multipart 0.0.32`; offline `Form()` POST path verified (correct→303+cookie, wrong→401 State 2, zero egress).
- RED: `pytest tests/test_token_gate.py` → 8 failed (enforcement, `/access`, cookie flow, constant-time helper), 7 passed (exemption/fail-open, trivially open with no gate). GREEN after deps+router+template+wiring → 14/15, then 15/15 (fixed a template line-wrap that split "your\\n assignment" — copy now contiguous).
- Full suite **84 passed** (69 → 84), `ruff check` clean, `ruff format --check` clean (29 files). 1.4 `test_shell.py` stays green — the header `{% block header %}` default still renders on `GET /`.
- AC offline proof: `docker build -t ttb-label-poc:1.5 .`; `docker run -d --network none -e ACCESS_TOKEN=secret …` (`inspect` → network `none`). In-container `urllib`: `/healthz` 200 (ungated) · `/access` 200 State-1 + no `app-header` · `/static/css/brand.css` 200 (exempt) · `GET /` no cookie → **303 → /access** · `POST /access token=secret` → **303 → / + `ttb_access=secret; HttpOnly; Path=/; SameSite=lax`** (no `Secure` on http — correct) · `GET /` with cookie → 200 shell. **Zero egress.**

### Completion Notes List

- **AC-1** — App-wide middleware gate: valid cookie reaches `/`; absent/invalid → 303 to `/access`; constant-time `hmac.compare_digest`; token/cookie never logged. No DB read on the deny path (AR-5 intact).
- **AC-2** — `access.html` reproduces `token-gate.html` both states on real USWDS components (`.usa-input`/`.usa-button`/`.usa-alert--error`), tokens from `brand.css` `:root` (spine wins; denial accent spine fail `#B50909`); device-frame/URL/state-label scaffolding excluded; no `app-header` (pre-auth).
- **AC-3** — `/healthz`, `/access`, `/static/*` exempt; every other route gated. The `/healthz` exemption keeps the Docker/Railway healthcheck green; static exemption keeps the gate page styled + Public Sans loaded (offline proof holds).
- **AC-4** — Fail-open when `ACCESS_TOKEN` is unset **or** empty (`gate_enabled` = `bool(...)`); fully enforced once set. Both paths unit-tested. *(Deliberate POC posture — flag for Diane in the PR: flip to fail-closed if preferred.)*
- **AC-5** — Correct token → `HttpOnly`/`SameSite=Lax`/`Secure`-in-prod cookie + 303 to `/`; wrong/absent → State 2 denial at HTTP `401`, no cookie granted, nothing leaked.

**UI fidelity — documented side-by-side (DoD), running gate vs `mockups/token-gate.html`:**

| Element | Mockup | Running gate | Verdict |
|---|---|---|---|
| Layout | centered card, max-width 440px, base canvas | identical (`.gate`/`.gate-card`) | match |
| Seal | 56px navy round, `U.S./TREAS`, `aria-hidden` | identical | match |
| Title / sub (State 1) | "TTB Label Review" / "Enter your access token to begin." | identical | match |
| Input | single, autofocused, `autocomplete="off"`, ≥48px | USWDS `.usa-input`, autofocus, 48px | match |
| Enter button | navy, ≥48px, full-width | USWDS `.usa-button`, navy, 48px, full-width | match |
| Helper copy | State 1 incl. "Your token was sent…"; State 2 short form | identical (conditional) | match |
| Denial (State 2) | `role="status"` "Access token required." + body, `aria-invalid` input, error border | USWDS error Alert `role="status"` + `aria-invalid` + `usa-input--error` | match (spine `#B50909`) |
| Device frame / URL / state-label | present (scaffolding) | **excluded** | spine delta |
| App-header | absent (pre-auth) | absent (`{% block header %}` empty) | match |

### File List

- `app/web/deps.py` (new — gate helpers: `gate_enabled`, `is_exempt`, `token_matches`, `has_valid_access`, `ACCESS_COOKIE`, exemption sets)
- `app/web/routes_access.py` (new — `GET`/`POST /access`; FastAPI `Form(...)`)
- `requirements.txt` (modified — pinned `python-multipart~=0.0.32` for the gate form)
- `templates/access.html` (new — token-gate screen, both states)
- `templates/base.html` (modified — header wrapped in `{% block header %}`)
- `static/css/brand.css` (modified — token-gate screen section + error-alert spine accent)
- `app/main.py` (modified — `app.state.settings`/`templates`, access-gate middleware, include access router)
- `tests/test_token_gate.py` (new — 15 tests across AC-1..5)
- `_bmad-output/implementation-artifacts/1-5-token-gated-access-and-clean-denial.md` (story tracking)

## Change Log

| Date | Change |
|------|--------|
| 2026-06-12 | Story 1.5 implemented — token-gate access boundary (app-wide middleware, constant-time compare, fail-open-when-unconfigured), entry/denial screen matching `token-gate.html` both states on USWDS, `/healthz`+`/static`+`/access` exempt. 15 gate tests + 84 total green; ruff clean; `--network none` + `ACCESS_TOKEN` offline proof (exemptions, gating, cookie flow, zero egress). Status → review. |
| 2026-06-12 | `POST /access` refactored to FastAPI `Form(...)`; `python-multipart~=0.0.32` pinned (Diane-approved). Image rebuilt + offline form path re-verified; 84 tests still green, ruff clean. |
