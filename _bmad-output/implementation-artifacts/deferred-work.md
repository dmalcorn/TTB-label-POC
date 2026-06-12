# Deferred Work

## Deferred from: code review of 1-1-containerized-fastapi-skeleton (2026-06-12)

- **LLM fail-fast validation** — `LLM_ENABLED=true` with absent `LLM_PROVIDER`/`LLM_BASE_URL` yields an inconsistent Settings with no fail-fast. Add a validator in the Epic-2 story that wires the LLM. [app/config.py]
- **`access_token` empty-vs-absent** — `ACCESS_TOKEN=` (empty string) is not distinguished from absent (`None`). Decide semantics in the Story 1.5 auth gate. [app/config.py:41]
- **Import-time settings crash tripwire** — module-level `app = create_app()` runs at import; once any Settings field gains a real validator, `uvicorn app.main:app` boot will crash at import. Factory-path tests import `create_app`, not `app`, so they won't catch it. [app/main.py:38]
- **Settings caching** — `get_settings()` re-parses the environment on every call. Consider `functools.lru_cache` when settings become hot. [app/config.py:50]
- **Unpinned apt packages** — `tesseract-ocr`, `libgl1`, `libglib2.0-0` are unpinned in the Dockerfile, weakening the offline-pinned/reproducible claim. Build-time only, no runtime egress impact. [Dockerfile:16-19]
- **`/healthz` vs future auth gate** — a global auth gate (Story 1.5) added without exempting `/healthz` would 401 the Docker HEALTHCHECK. [Dockerfile:39 / app/main.py]
- **`tests/` in production image** — Dockerfile COPYs `tests/` into the runtime image (bloat/attack surface). Intentional now (in-container `pytest` verifies AC-2), revisit for prod hardening. [Dockerfile:33]
