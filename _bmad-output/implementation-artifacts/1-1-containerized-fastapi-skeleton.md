---
baseline_commit: 552cb74b60624d037cc8ba54728671d6144a609e
---

# Story 1.1: Containerized FastAPI project skeleton

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer building and deploying the POC,
I want a reproducible, offline-pinned FastAPI skeleton in a single Dockerfile,
so that every later story builds on one deterministic foundation that runs identically locally and on Railway.

## Acceptance Criteria

**AC-1 — Image builds offline-pinned on `python:3.13-slim` with native deps + pinned requirements**
**Given** a clean checkout
**When** `docker build` runs against the Dockerfile
**Then** the image builds `FROM python:3.13-slim` with native deps installed via apt (`tesseract-ocr`, `libgl1`, `libglib2.0-0`) and the pinned `requirements.txt` from `approved-tech-stack.md` (`fastapi~=0.136`, `uvicorn[standard]~=0.49`, `pydantic~=2.13`, `jinja2~=3.1`, `apscheduler~=3.11`, plus dev tools `ruff~=0.15`, `pytest~=9.0`).

**AC-2 — `GET /healthz` returns 200**
**Given** the built image
**When** `docker run` starts the container and a request hits `GET /healthz`
**Then** the route returns HTTP 200.

**AC-3 — Project tree matches the architecture's Project Structure**
**Given** the architecture's "Complete Project Directory Structure"
**When** the repo is inspected
**Then** the tree exists split by concern — `app/` (with `web/`, `db/`, `pipeline/`, `adapters/ocr`, `adapters/llm`, `engine/rulesets`, `engine/checks`, `benchmark/`), `templates/`, `static/` (`uswds/`, `js/`), `tests/`, `fixtures/`, `models/` — each Python package carrying an `__init__.py`.

**AC-4 — `ruff` + `pytest` configured and a placeholder test passes**
**Given** `pyproject.toml`
**When** `ruff check .` and `pytest` run
**Then** ruff is configured with line length 100, pytest is configured to discover `tests/`, and at least one placeholder test passes green.

**AC-5 — Boots with zero egress under `--network none`**
**Given** the firewall posture (NFR-2)
**When** the container starts with `docker run --network none`
**Then** the app still boots and serves `GET /healthz` — no outbound call at startup.

*(Source: epics.md Story 1.1; AR-1, AR-8, AR-11; approved-tech-stack.md §9)*

## Tasks / Subtasks

- [x] **Task 1 — `requirements.txt` pinned to the version-of-record (AC: 1)**
  - [x] Author `requirements.txt` from `approved-tech-stack.md §9`: `fastapi~=0.136`, `uvicorn[standard]~=0.49`, `pydantic~=2.13`, `jinja2~=3.1`, `apscheduler~=3.11`, `ruff~=0.15`, `pytest~=9.0`.
  - [x] Do **not** add `openai`/`anthropic`/`google-genai`/`paddleocr`/`opencv`/`langchain` yet — those land in their owning stories (Epic 2). Keep this skeleton minimal so the build stays fast and the `--network none` boot is clean. (Added `httpx~=0.28` as the TestClient transport — test-only, flagged in a comment.)
- [x] **Task 2 — FastAPI app factory + `/healthz` (AC: 2, 5)**
  - [x] `app/main.py`: app factory `create_app()` returning a `FastAPI` instance; register `GET /healthz` returning `{"status": "ok"}` (200). No DB, no scheduler, no adapter import on this path — startup does zero network I/O (AR-5/AR-8).
  - [x] `app/config.py`: minimal Pydantic `Settings` reading env (`ACCESS_TOKEN`, `LLM_ENABLED`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LANGCHAIN_*`) with safe defaults; **absent keys do not raise** (model layer simply off — AR-9). `/healthz` does not depend on any being set.
- [x] **Task 3 — Directory skeleton per architecture (AC: 3)**
  - [x] Create the package tree exactly as the architecture's directory structure lays it out (see Dev Notes). Every Python sub-package gets an empty `__init__.py`; non-Python dirs (`templates/`, `static/uswds/`, `static/js/`, `fixtures/`, `models/`, `tests/fixtures/`) get a `.gitkeep`.
  - [x] Did **not** author module bodies that belong to later stories (`db/schema.sql`, `db/seed.py`, `contracts.py`, `normalize.py`, `verdict.py`, `disposition.py`, routes, adapters, checks) — left as empty package placeholders per project-context "create only what the story needs."
- [x] **Task 4 — `pyproject.toml`: ruff + pytest (AC: 4)**
  - [x] `[tool.ruff]` line-length 100; `[tool.pytest.ini_options]` testpaths `tests`.
  - [x] `tests/test_healthz.py`: placeholder/regression test asserting `GET /healthz` → 200 via FastAPI `TestClient`, plus an empty-environment boot test (AR-9 / AC-5).
- [x] **Task 5 — Dockerfile (AC: 1, 2, 5)**
  - [x] `FROM python:3.13-slim`; `apt-get install --no-install-recommends tesseract-ocr libgl1 libglib2.0-0` then clean apt lists; `pip install -r requirements.txt`; copy app; `CMD` runs uvicorn serving the app factory; `HEALTHCHECK` hits `/healthz`. Added `.dockerignore` to keep `.venv`/caches/artifacts out of the build context.
  - [x] Verified `docker run --network none <img>` boots and `/healthz` answers 200 (AC-5).
- [x] **Task 6 — `compose.yaml` + `.env.example` (supporting AR-2/AR-9)**
  - [x] `compose.yaml`: single service, Dockerfile build, port mapping; optional `.env` (`required: false`); egress smoke-test invocation documented in a comment.
  - [x] `.env.example`: documents every variable (`ACCESS_TOKEN`, `LLM_ENABLED`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LANGCHAIN_TRACING_ENABLED`).

*(`railway.toml` and the README run-from-clone are Story 1.6, not here.)*

### Review Findings

_Code review 2026-06-12 (Blind Hunter · Edge Case Hunter · Acceptance Auditor). All 5 ACs PASS on disk. Note: the working tree changed mid-review — Story 1.2 DB files appeared concurrently; findings below reflect live disk._

- [x] [Review][Decision] In-flight Story 1.2 DB layer is sitting in the 1.1 tree — `app/db/schema.sql`, `app/db/connection.py`, `app/db/repositories.py` are full implementations (not the "empty package placeholders" the File List and Completion Notes claim). `schema.sql:1` self-identifies as Story 1.2. **RESOLVED: out of scope for 1.1 — these are parallel Story 1.2 work and will be reviewed under story 1-2. 1.1's File List/Completion Notes reconciled below to stop claiming the `app/db/` bodies are empty.**
- [x] [Review][Decision] `database_path` config field added to the 1.1-owned `app/config.py:34-36,46` ahead of the DB story. **RESOLVED: keep — defaulted, never raises, AC-5 zero-egress boot unaffected; it's harmless forward config surface for 1.2/1.6. Completion Notes reconciled below.**
- [x] [Review][Patch] Story's core invariant ("garbage/absent env never raises, features stay off") has zero negative-path coverage — **FIXED:** added `tests/test_config.py` (21 cases: truthy/garbage `_env_bool`, isolated `from_env`, clean-env defaults, garbage `LLM_ENABLED` stays off, enabled-without-provider doesn't raise)
- [x] [Review][Patch] `test_app_boots_with_empty_environment` clears only 4 keys — **FIXED:** added `LANGCHAIN_TRACING_ENABLED` to the delenv loop (`DATABASE_PATH` already isolated to tmp_path by the 1.2 session) [tests/test_healthz.py]
- [x] [Review][Patch] HEALTHCHECK `urllib.request.urlopen(...)` has no `timeout=` — **FIXED:** added `timeout=2` so the probe self-bounds [Dockerfile:39]
- [x] [Review][Patch] `compose.yaml` `environment:` block shadows `.env` (Compose precedence: environment > env_file) — **FIXED:** removed the override; `.env` is now the single runtime source, absent-`.env` defaults handled by `app/config.py` [compose.yaml]
- [x] [Review][Defer] `LLM_ENABLED=true` with absent `LLM_PROVIDER`/`LLM_BASE_URL` produces an inconsistent Settings with no fail-fast — belongs to the Epic-2 story that wires the LLM [app/config.py] — deferred, model layer not wired in 1.1
- [x] [Review][Defer] `access_token` empty-string (`ACCESS_TOKEN=`) vs absent (`None`) not distinguished — resolve in the Story 1.5 auth gate [app/config.py:41] — deferred, auth not in 1.1
- [x] [Review][Defer] Module-level `app = create_app()` runs at import; once any field gains a real validator, `import app.main` (uvicorn boot) crashes — and factory-path tests import `create_app`, not `app`, so they'd miss it [app/main.py:38] — deferred, currently no field can raise
- [x] [Review][Defer] `get_settings()` re-parses the environment on every call (no caching) — consider `functools.lru_cache` when settings get hot [app/config.py:50] — deferred, inert for a skeleton
- [x] [Review][Defer] Dockerfile apt packages (`tesseract-ocr`, `libgl1`, `libglib2.0-0`) are unpinned — weakens the "offline-pinned/reproducible" claim (the `~=` Python pins are intentional per project policy) [Dockerfile:16-19] — deferred, build-time only, no runtime egress impact
- [x] [Review][Defer] `/healthz` would 401 if a global auth gate (Story 1.5) is added without exempting it — Docker HEALTHCHECK would start failing [Dockerfile:39 / app/main.py] — deferred, forward-looking to 1.5
- [x] [Review][Defer] `tests/` is COPY'd into the production image — bloat/attack surface; intentional now (in-container `pytest` verifies AC-2 per Dev Record), revisit for prod hardening [Dockerfile:33] — deferred, intentional for now

## Dev Notes

### Scope guardrails (read first)
- **This is the init story (AR-1) — skeleton only.** It ships: Dockerfile, app factory, `/healthz`, the directory tree, tooling config, one placeholder/regression test, `compose.yaml`, `.env.example`. It does **NOT** ship the DB schema (Story 1.2), seed corpus (1.3), USWDS shell (1.4), token gate (1.5), or Railway deploy (1.6).
- **Project-context rule, binding:** "Create tables only in the story that needs them — do NOT front-load the full schema." Same logic applies to the four contracts and routes: stub directories, not implementations.
- **5s read-path / zero-egress invariants apply from day one:** `/healthz` and app startup perform **no** network I/O, no OCR, no model import. The `--network none` boot (AC-5) is the proof.

### Tech stack (pin to the version-of-record — `approved-tech-stack.md`)
- Python **3.13.x**, Docker base `python:3.13-slim`. Type hints required.
- `fastapi~=0.136` · `uvicorn[standard]~=0.49` · `pydantic~=2.13` (**v2**) · `jinja2~=3.1` · `apscheduler~=3.11` (NOT the 4.0 pre-release).
- Dev: `ruff~=0.15` (lint + format, line length **100**) · `pytest~=9.0`.
- System (apt, in Dockerfile): `tesseract-ocr` (5.5.x), `libgl1`, `libglib2.0-0`.
- **Pin to the minor line** (`~=major.minor`) unless a patch is named. Heavy extraction deps (paddleocr, opencv, langchain, provider SDKs) are intentionally deferred to their Epic-2 stories.

### Project structure to scaffold (from architecture.md "Complete Project Directory Structure")
Root: `README.md` (1.6), `Dockerfile`, `compose.yaml`, `requirements.txt`, `pyproject.toml`, `.env.example`, `railway.toml` (1.6), `docs/` (exists).
```
app/
  main.py            # app factory + GET /healthz  ← THIS STORY
  config.py          # env → typed Settings (defaults safe; absent keys never raise)  ← THIS STORY
  contracts.py       # placeholder (filled in Story 2.1)
  normalize.py       # placeholder (Story 3.1)
  verdict.py         # placeholder (Story 3.1)
  disposition.py     # placeholder (Story 3.x)
  web/   db/   pipeline/   adapters/ocr/   adapters/llm/   engine/rulesets/   engine/checks/   benchmark/
templates/   static/uswds/   static/js/   fixtures/   models/   tests/   tests/fixtures/
```
Create the dirs + `__init__.py`/`.gitkeep`; only `main.py`, `config.py`, the Dockerfile, tooling, and the test carry real content this story.

### Architecture compliance (must-follow)
- **snake_case everywhere** — Python, future DB columns, future JSON. No camelCase.
- **Config via env, absent keys ⇒ feature off, never a crash** (AR-9). `Settings` defaults must let `/healthz` succeed with an empty environment.
- **No OCR/inference/model import on any request or startup path** (AR-5/AR-8) — the whole point of the `--network none` test.
- Tooling/structure per AR-11: tests in top-level `tests/` mirroring `app/`, files `test_*.py`.

### Testing
- `tests/test_healthz.py` — `TestClient(create_app())`, `GET /healthz` → 200. This single test satisfies both "placeholder test passes" (AC-4) and the AC-2 contract. Keep it import-light so collection doesn't pull deferred deps.
- Run `ruff check .` and `pytest` locally; both green is the bar. There is a "local CI" referenced in recent commits — keep it passing.

### Project Structure Notes
- The architecture tree is authoritative; this story realizes its *shape*, with most leaf modules as deferred placeholders. No conflicts with the epic scope — epics.md explicitly puts schema in 1.2, seed in 1.3, USWDS in 1.4.

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.1: Containerized FastAPI project skeleton]
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure & Boundaries] (directory tree, boundaries)
- [Source: _bmad-output/planning-artifacts/approved-tech-stack.md#9. Summary — full pin list] (version-of-record)
- [Source: _bmad-output/project-context.md#Technology Stack & Versions] (pinning policy, snake_case, firewall posture)
- AR-1 / AR-8 / AR-9 / AR-11 [Source: epics.md#Additional Requirements]; NFR-2 firewall [Source: epics.md#NonFunctional Requirements]

## Dev Agent Record

### Agent Model Used

Amelia (BMad dev-story) — claude-opus-4-8[1m]

### Debug Log References

- Local TDD loop run in a throwaway `.venv` (host Python 3.14; project pins 3.13 — the image is the source of truth): `pytest -q` → 2 passed; `ruff check .` → All checks passed; `ruff format --check .` → 15 files already formatted.
- `docker build -t ttb-label-poc:1.1 .` → exit 0; installed exact pins fastapi-0.136.3, uvicorn-0.49.0, pydantic-2.13.4, jinja2-3.1.6, apscheduler-3.11.2, ruff-0.15.17, pytest-9.0.3, httpx-0.28.1.
- AC-2: container run, host `GET /healthz` → 200 `{"status":"ok"}`; `docker exec … pytest -q` → 2 passed (in-container).
- AC-5: `docker run --network none -e LLM_ENABLED=false` → networks = `{none}` (no IP/gateway), uvicorn startup complete, internal `127.0.0.1:8000/healthz` → 200, container state `running`. Zero-egress boot proven.
- Known non-blocking warning: Starlette deprecation suggesting `httpx2` for `TestClient`; current `httpx~=0.28` works and is pinned. Revisit if Starlette drops `httpx` support.

### Completion Notes List

- Init/skeleton story (AR-1) complete: Dockerfile, FastAPI app factory + `/healthz`, full directory tree (packages with `__init__.py`, asset dirs with `.gitkeep`), ruff/pytest config, `compose.yaml`, `.env.example`, `.dockerignore`.
- Scope held to the epic split — no seed (1.3), USWDS shell (1.4), token gate (1.5), or Railway deploy (1.6). Deferred contract/route modules left as empty package placeholders, honoring project-context "create only what the story needs."
- **Reconciliation (code review 2026-06-12):** `app/db/` is NOT empty — `schema.sql`, `connection.py`, `repositories.py` were authored by a parallel **Story 1.2** session and live uncommitted in this tree. They are out of scope for 1.1 and reviewed under story 1-2; do not treat them as 1.1 deliverables. The `database_path` field in `app/config.py` was added here ahead of the DB story and kept (defaulted, AC-5-safe).
- All 5 ACs verified end-to-end, including the firewall-posture `--network none` boot (NFR-2 / AR-8). `.gitignore` already excludes `.venv/`, caches, and `.env`; no change needed.

### File List

- `requirements.txt` (new)
- `pyproject.toml` (new)
- `Dockerfile` (new)
- `.dockerignore` (new)
- `compose.yaml` (new)
- `.env.example` (new)
- `app/main.py` (new)
- `app/config.py` (new)
- `app/__init__.py`, `app/web/__init__.py`, `app/db/__init__.py`, `app/pipeline/__init__.py`, `app/adapters/__init__.py`, `app/adapters/ocr/__init__.py`, `app/adapters/llm/__init__.py`, `app/engine/__init__.py`, `app/engine/rulesets/__init__.py`, `app/engine/checks/__init__.py`, `app/benchmark/__init__.py`, `tests/__init__.py` (new package markers)
- _Not 1.1 deliverables — Story 1.2 work present in-tree (reviewed under story 1-2): `app/db/schema.sql`, `app/db/connection.py`, `app/db/repositories.py`._
- `tests/test_healthz.py` (new)
- `templates/.gitkeep`, `static/uswds/.gitkeep`, `static/js/.gitkeep`, `fixtures/.gitkeep`, `models/.gitkeep`, `tests/fixtures/.gitkeep` (new)
- `_bmad-output/implementation-artifacts/1-1-containerized-fastapi-skeleton.md` (story tracking)

## Change Log

| Date | Change |
|------|--------|
| 2026-06-12 | Story 1.1 implemented — containerized FastAPI skeleton; all 5 ACs verified (build, /healthz 200, tree, ruff/pytest, --network none zero-egress boot). Status → review. |
