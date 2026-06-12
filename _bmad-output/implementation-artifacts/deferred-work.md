# Deferred Work

## Deferred from: code review of 1-1-containerized-fastapi-skeleton (2026-06-12)

- **LLM fail-fast validation** — `LLM_ENABLED=true` with absent `LLM_PROVIDER`/`LLM_BASE_URL` yields an inconsistent Settings with no fail-fast. Add a validator in the Epic-2 story that wires the LLM. [app/config.py]
- **`access_token` empty-vs-absent** — `ACCESS_TOKEN=` (empty string) is not distinguished from absent (`None`). Decide semantics in the Story 1.5 auth gate. [app/config.py:41]
- **Import-time settings crash tripwire** — module-level `app = create_app()` runs at import; once any Settings field gains a real validator, `uvicorn app.main:app` boot will crash at import. Factory-path tests import `create_app`, not `app`, so they won't catch it. [app/main.py:38]
- **Settings caching** — `get_settings()` re-parses the environment on every call. Consider `functools.lru_cache` when settings become hot. [app/config.py:50]
- **Unpinned apt packages** — `tesseract-ocr`, `libgl1`, `libglib2.0-0` are unpinned in the Dockerfile, weakening the offline-pinned/reproducible claim. Build-time only, no runtime egress impact. [Dockerfile:16-19]
- **`/healthz` vs future auth gate** — a global auth gate (Story 1.5) added without exempting `/healthz` would 401 the Docker HEALTHCHECK. [Dockerfile:39 / app/main.py]
- **`tests/` in production image** — Dockerfile COPYs `tests/` into the runtime image (bloat/attack surface). Intentional now (in-container `pytest` verifies AC-2), revisit for prod hardening. [Dockerfile:33]

## Deferred from: code review of stories 1.1+1.2+1.3 (2026-06-12)

- **`updated_at` trigger recursion default** — `trg_submissions_set_updated_at` relies on the default `recursive_triggers = OFF`, never asserted in `connection.py`. Add a `WHEN OLD.updated_at = NEW.updated_at` guard or set the PRAGMA explicitly. Documented reliance on a stable SQLite default. [app/db/schema.sql / app/db/connection.py]
- **Concurrent seed/reset vs startup init** — no busy/lock handling for a `seed()`/`POST /reset` racing the startup `init_db` on one file. Use `BEGIN IMMEDIATE` or an app-level lock. Belongs to the Epic-6 reset story. [app/db/seed.py]
- **`audit_events` commit boundary** — table was committed under the Story 1.2 commit (`a92d674`) though it is 1.3's need. Cosmetic commit-boundary smell; no code action. [app/db/schema.sql]
- **Seed lower image-bound** — `_insert_label_images` enforces only `>10`; a 0-image submission would seed silently though AC-4 says 1–10. Add a lower-bound guard when `POST /reset` accepts external CSVs. [app/db/seed.py:74-79]
- **Government Warning canonical text** — `GOV_WARNING`/`GOV_WARNING_REWORDED` are literal constants in the dev-only `fixtures/generate.py` (legitimate as fixture image content). Epic-3's §16.21 wording check MUST read the canonical text from a Ruleset row, never duplicate this constant. [fixtures/generate.py]
- **Four root contract placeholder modules** — `app/contracts.py`/`normalize.py`/`verdict.py`/`disposition.py` named in Story 1.1's architecture tree were never created (only package dirs exist). Create stubs or leave deferred to Epics 2/3. [app/]

## Deferred from: code review of stories 1.4+1.5 (2026-06-12)

- **`Secure` cookie flag behind Railway's proxy (Story 1.6)** — the access cookie sets `secure=request.url.scheme=="https"`, which is `http` behind Railway's TLS-terminating edge unless uvicorn runs with `--proxy-headers`/`--forwarded-allow-ips` (or `ProxyHeadersMiddleware` is added). Without it the shared-token cookie is set **without `Secure` in production**. Fix in Story 1.6 deploy config; the route code is correct once forwarded-proto is trusted. [app/web/routes_access.py:55]
- **303 gate redirect coerces non-GET → GET** — every non-exempt request (any method) is `RedirectResponse("/access", 303)`, turning a future unauthenticated `POST` into a silent GET of the gate instead of a 401. Latent; only `GET /` exists today. Revisit when a protected non-GET route lands. [app/main.py]
- **Stale cookie not cleared on denial** — `POST /access` denial returns 401 without `delete_cookie(ACCESS_COOKIE)`; a rotated/old cookie lingers (correct outcome, untidy). [app/web/routes_access.py:46]
- **Un-normalized exemption-prefix matching** — `is_exempt` does case-sensitive `startswith("/static/")`; case-variants, `//static`, and `/static/..` aren't normalized. Benign today (case-sensitive routes; `StaticFiles` rejects traversal) but fragile behind a path-rewriting proxy. [app/web/deps.py:44-48]
- **Unbounded form body on `POST /access`** — the one unauthenticated body-accepting endpoint has no token length / body-size cap (minor DoS surface). [app/web/routes_access.py:41]
- **No `?next=` deep-link preservation** — unauthenticated deep-link → redirected to `/access` → lands on `/` after entry, losing the intended destination. Latent until a third gated route exists. [app/main.py]
- **Forced-colors error icon** — State-2 denial icon is a USWDS sprite `background-image` that can drop in forced-colors mode; the word "Access token required." still carries the meaning (a11y floor met). Low-risk hardening only. [templates/access.html]
