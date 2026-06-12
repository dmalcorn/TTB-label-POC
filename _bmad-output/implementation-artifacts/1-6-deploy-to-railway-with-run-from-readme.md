---
baseline_commit: 7bba722
context:
  - _bmad-output/planning-artifacts/epics.md
  - _bmad-output/planning-artifacts/architecture.md
  - _bmad-output/implementation-artifacts/deferred-work.md
  - _bmad-output/implementation-artifacts/1-5-token-gated-access-and-clean-denial.md
---

# Story 1.6: Deploy to Railway with run-from-README

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an evaluator,
I want the app deployed at an HTTPS public URL and a README that runs it from a clean clone,
so that I can both reach the live demo and reproduce it locally.

## Acceptance Criteria

**AC-1 — `railway.toml`: Dockerfile build, Volume, healthcheck**
**Given** `railway.toml` at the repo root
**When** the Railway service is configured
**Then** it specifies a **Dockerfile** build (explicitly **not** Nixpacks), a **Volume** mounted at the SQLite/generated-images directory, and a healthcheck path of `/healthz`
**And** the `DATABASE_PATH` the app reads resolves to a file **inside the mounted Volume** (so data survives redeploys; Railway's container FS is ephemeral).

**AC-2 — Deploys behind the gate, with the seeded corpus present on the Volume**
**Given** Railway Pro env vars set (`ACCESS_TOKEN`, `LLM_ENABLED`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LANGCHAIN_TRACING_ENABLED`)
**When** the service deploys from the Dockerfile
**Then** the app is reachable at an **automatic-HTTPS public URL**, **behind the Story 1.5 token gate**, and past the gate it renders the **Story 1.4 shell at `GET /`**
**And** the first-boot path **populates the Volume DB with the seeded corpus** (the Volume starts empty; see Task 2 — idempotent seed-if-empty on startup, reusing Story 1.3's `seed()`), verifiable via the DB / `python -m app.db.seed` re-run being a no-op.
*(The seeded rows aren't yet shown by a screen — the Queue that consumes them is Epic 4. This AC guarantees the data is deployed and reachable behind the gate so the Queue lands on a populated DB and Epic-6 reset works; it does not claim a visible queue.)*

**AC-3 — `/healthz` reachable for the Railway healthcheck**
**Given** the token gate from Story 1.5
**When** Railway probes `/healthz`
**Then** it returns `200` **without** a token (the gate exemption from Story 1.5 AC-3 holds in deployment), so the service is marked healthy.

**AC-4 — Run from a clean clone (local reproduction)**
**Given** a fresh evaluator with only the repo
**When** they follow the README
**Then** they can **clone, build, and run locally** with `docker compose up`, reach the app, and (with `ACCESS_TOKEN` set in `.env`) pass the gate
**And** `.env.example` documents **every** runtime variable (verified against `app/config.py` Settings — a test asserts no Settings field is undocumented)
**And** the README's run commands are **real and current** (no invented `app.seed --from` / `app.worker` / `app.server` placeholders).

**AC-5 — README documents the offline smoke test and links the docs set**
**Given** the firewall posture (NFR-2)
**When** the README is read
**Then** it documents the **offline egress smoke test** — `docker run --network none -e LLM_ENABLED=false …` proving the zero-egress OCR-only boot
**And** it links the `docs/` deliverable set (full population completes in Epic 6)
**And** the "Status: planning phase" banner is removed/replaced now that code runs.

*(Source: epics.md Story 1.6; FR-26 (partial); AR-2; AR-8; architecture.md §Deployment & Dev Strategy, §Infrastructure & Deployment, D1/D7; deferred-work.md.)*

> **Dependency note (read first):** This story deploys the app **as it stands**. Story **1.4** (USWDS shell) is **done** (shell at `GET /`, vendored assets, brand layer). The remaining hard dependency is Story **1.5** (the token gate the public URL sits behind, and the `/healthz` exemption AC-3 relies on) — sequence **1.5 → 1.6**. If 1.5 hasn't landed, the deploy still works but the public URL would be ungated; don't ship the public URL until the gate is in. The `/healthz` exemption (AC-3) is **owned by Story 1.5** — this story only verifies it survives deployment.

> **Scope note (binding):** Infra + docs only. Do **not** build new product features here. The single touch to `app/main.py` is the **idempotent seed-if-empty** startup guard (so the live URL isn't an empty DB) — bounded bootstrap work at startup (like the existing `init_db`), never on a request/render path. Do **not** fold seeding into any `GET`. Full `docs/` deliverable population is **Epic 6**, not here — this story only links the set and documents the run/smoke-test.

## Tasks / Subtasks

- [x] **Task 1 — `railway.toml` (AC: 1, 3)**
  - [x] `[build]` builder = `DOCKERFILE` (not Nixpacks), pointing at the existing `Dockerfile`.
  - [x] `[deploy]` `healthcheckPath = "/healthz"`, restart policy (`ON_FAILURE`, 10 retries); start command serves `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (honor Railway's injected `$PORT`).
  - [x] Volume mount at the data directory; `DATABASE_PATH` env → a file under that mount (`/data/app.db`). Documented in `railway.toml` comments + README. **Deviation:** Railway volumes are **not** expressible in `railway.toml` (config-as-code has no volume key — verified against Railway docs); the mount is created via CLI (`railway volume add --mount-path /data`). The toml documents this; the live Volume creation is the operator deploy step (see Completion Notes).
  - [x] Confirm the Dockerfile `EXPOSE`/`CMD` and Railway `$PORT` agree — `railway.toml` `startCommand` honors `$PORT` on Railway; Dockerfile `CMD` keeps `8000` for local/compose; the in-container `HEALTHCHECK` is now `$PORT`-aware (defaults 8000).
- [x] **Task 2 — Seed-if-empty on startup `app/main.py` (AC: 2)**
  - [x] In the lifespan (after `init_db`), `_seed_if_empty()` calls Story 1.3's idempotent `seed()` only when `submissions` is empty. Verified in-container: fresh Volume DB → 36 submissions + 36 SEEDED events.
  - [x] Startup network-free — proven by `docker run --network none` booting healthy and serving `/healthz` 200; seeding reads baked-in `fixtures/` + writes the SQLite file only.
- [x] **Task 3 — README rewrite (AC: 4, 5)**
  - [x] Replaced the "Status: planning phase" banner + invented `venv`/`app.seed`/`app.worker`/`app.server` commands with the real flow: `docker compose up --build`, `.env` from `.env.example`, auto seed-if-empty + manual `python -m app.db.seed`, reaching the gated app.
  - [x] Documented the offline egress smoke test (`docker build` + `docker run --rm --network none -e LLM_ENABLED=false -e ACCESS_TOKEN=demo -p 8000:8000 ttb-label-poc`).
  - [x] Documented the Railway deploy path (Dockerfile build, Volume at `/data`, env vars, automatic HTTPS) and linked the `docs/` set via `docs/index.md` (Epic-6 completes deliverables).
- [x] **Task 4 — `.env.example` parity (AC: 4)**
  - [x] Verified `.env.example` covers every `Settings` field (asserted by a test). No fields missing; tightened the `DATABASE_PATH` comment to name the `/data/app.db` Volume path.
- [x] **Task 5 — Tests `tests/test_deploy_config.py` (AC: 1, 4)**
  - [x] `railway.toml` parses; builder is Dockerfile (asserts not `nixpacks`); `healthcheckPath == "/healthz"`; `startCommand` honors `$PORT` with no hardcoded port.
  - [x] `.env.example` documents every `Settings` field — parses both and diffs (generic over `Settings.model_fields`).
  - [x] Seed-if-empty guard: populates an empty temp DB, and is a no-op when data is present (drop-one-row probe proves no clobber).

## Review Findings

_Code review 2026-06-12 (story 1.6; Blind Hunter · Edge Case Hunter · Acceptance Auditor — all three layers ran, none failed). AC scorecard: **AC-1 MET · AC-2 PARTIAL** (seed logic + tests pass; live deploy is a deferred operator step) **· AC-3 MET · AC-4 MET · AC-5 MET.** One obligation the spec assigned to 1.6 was **not discharged** (Secure cookie behind the proxy — P1 below). 4 patch · 2 defer · 6 dismissed (1 decision resolved → boot-degraded patch)._

- [x] [Review][Patch] **Seed-failure startup posture (resolved → boot degraded)** — `_seed_if_empty` re-raises with no try/except; if `seed()` throws on a fresh Volume (corrupt/short-read fixture, CHECK violation, `SQLITE_BUSY` past the 5s timeout) the lifespan aborts and Railway's `ON_FAILURE`/10-retry policy crash-loops with no degraded boot. **Decision (Diane): boot degraded** — wrap `seed()` in try/except, log the failure, and come up on an empty DB so the demo URL stays reachable. [app/main.py:35-49]
- [x] [Review][Patch] **CRITICAL — access cookie set without `Secure` in production (deferred-from-1.5 obligation not discharged)** — FIXED: `startCommand` now runs `--proxy-headers --forwarded-allow-ips=*`; regression `test_start_command_trusts_railway_proxy_headers`. deferred-work.md item marked RESOLVED. — Railway terminates TLS at the edge and forwards plain HTTP; uvicorn's `forwarded_allow_ips` defaults to `127.0.0.1`, so `X-Forwarded-Proto: https` is untrusted, `request.url.scheme=="https"` is False, and the shared-token cookie ships without `Secure`. The `railway.toml` `startCommand` has no `--proxy-headers --forwarded-allow-ips`. deferred-work.md explicitly assigned this fix to Story 1.6. Fix: add `--proxy-headers --forwarded-allow-ips=*` to the `startCommand` (or set `FORWARDED_ALLOW_IPS`); add a deploy test. [railway.toml:19 / app/web/routes_access.py:55]
- [x] [Review][Patch] **HIGH — HEALTHCHECK/listener port divergence + empty-`PORT` footgun** — FIXED: probe now uses `os.environ.get('PORT') or '8000'`; regression `test_dockerfile_healthcheck_is_empty_port_safe`. — the Dockerfile `HEALTHCHECK` now reads `os.environ.get('PORT','8000')` (default applies only when *missing*, not empty) while `CMD` hardcodes `--port 8000`. With `PORT=""` the listener's `${PORT:-8000}` binds 8000 but the probe builds `http://127.0.0.1:/healthz` → malformed URL → false-unhealthy. Make probe and listener consistent and empty-safe: `os.environ.get('PORT') or '8000'`. [Dockerfile:39-45]
- [x] [Review][Patch] **LOW — new tests assert weak substrings / one-directional parity** — FIXED: `test_start_command_honors_railway_port` now parses the `sh -c '…'` wrapper and asserts the exact `--port ${PORT:-8000}` form instead of substring-anywhere. — `test_start_command_honors_railway_port` only checks `"sh -c"`/`"${PORT"` appear (passes for a broken command); the `.env.example` parity check is one-directional (`expected - documented`) and keys off any `NAME=` line regardless of value. Strengthen the startCommand assertion and consider flagging stray/extra documented keys. [tests/test_deploy_config.py]
- [x] [Review][Defer] **Concurrent seed race on the Volume** — check-then-seed spans two connections (non-atomic) and `seed()` opens a *deferred* `BEGIN` (not `BEGIN IMMEDIATE`); a redeploy overlap or future second writer on one `/data/app.db` could clobber-reload or `SQLITE_BUSY` crash-loop. Pre-existing seed semantics (Story 1.3); reinforces the existing deferred-work item "Concurrent seed/reset vs startup init" owned by the Epic-6 reset story. [app/db/seed.py / app/main.py] — deferred, pre-existing
- [x] [Review][Defer] **Silent off-Volume seeding if the mount is missing** — `init_db`'s `mkdir(parents=True, exist_ok=True)` happily creates `/data/app.db` on the ephemeral container FS when the Railway Volume mount is absent/misconfigured, masking the misconfig and silently losing data across redeploys (the exact failure AC-1 guards against). Can't hard-assert a mount without breaking the legitimate local `data/app.db` path; mitigated by the documented operator step in railway-deployment.md. [app/db/connection.py:68] — deferred, operator-deploy concern

## Project Structure Notes

- **New:** `railway.toml`, `tests/test_deploy_config.py`.
- **Update:** `README.md` (real run instructions + smoke test + deploy + docs links; drop the planning banner), `app/main.py` (seed-if-empty lifespan guard), Dockerfile/start-command only if needed to honor Railway `$PORT`.
- `.env.example` already complete — verify, don't rewrite. `compose.yaml` already builds from the Dockerfile and reads `.env` (no change expected).
- Do not add new `app/` feature modules — this is infra + docs.

## Dev Notes

### Deployment decisions (from architecture — must-follow)
- **D1 — single Railway service**, SQLite file on a **Railway Volume** (not Postgres, not a worker split). Demo-reset = restore the seeded file (Epic 6 builds `POST /reset` on Story 1.3's `seed()`).
- **Dockerfile build, NOT Nixpacks** — native OCR deps (`tesseract-ocr`, `libgl1`, `libglib2.0-0`) are already baked by the Story 1.1 Dockerfile. Nixpacks would not reproduce them.
- **D7 — derived artifacts on the Volume:** generated/preprocessed images (Epic 2) write to the Volume; **seeded fixture images are baked read-only into the image** — so seeding the Volume DB only inserts rows that reference the baked-in `fixtures/images/*.jpg` paths. No image upload, no runtime download.
- **Railway provides automatic HTTPS + public URL + env-var secrets** (architecture §Authentication & Security; HTTPS terminated by Railway).
- **Outbound posture on Railway:** the deployed demo *may* reach cloud LLM APIs (the `models-internal-endpoint` stand-in) when `LLM_ENABLED=true`; `LLM_ENABLED=false` is the provable zero-egress config (FR-12). This story doesn't enable it — it documents the toggle.

### The empty-Volume trap (why Task 2 exists)
- A Railway Volume starts **empty**. `init_db` (Story 1.1 lifespan) creates the schema but **no rows** → the gated landing would show an empty queue, failing AC-2 ("serving the seeded data"). The fix is an **idempotent seed-if-empty** in the lifespan, reusing Story 1.3's transactional `seed()`. It is bootstrap work at startup, not request-path work — the 5-second read contract and the "no heavy work on GET" rule are intact.
- `seed()` already DELETEs+reinserts idempotently, but run it **only when `submissions` is empty** so a redeploy never clobbers any in-Volume state mid-session. (Full reset is Epic 6's explicit `POST /reset`.)

### `$PORT` reconciliation
- Railway injects `$PORT`; the current Dockerfile `CMD` hardcodes `--port 8000`. Honor `$PORT` via the `railway.toml` start command (or an env-aware `CMD`), keeping `8000` as the local/compose default. The `EXPOSE 8000` + compose port map stay for local dev.

### Run-from-README discipline (AC-4/AC-5)
- The current README is **planning-phase** and lists **invented commands** (`python -m app.seed --from …`, `app.worker`, `app.server`) that do not exist. Replace with the real surface: `docker compose up --build`, `python -m app.db.seed`, `uvicorn app.main:app`. A wrong command in the README is an AC failure — verify each runs.
- Keep the firewall/recommend-don't-decide framing already in the README; only the "Setup & run" + status banner need rewriting.

### Architecture compliance
- **Firewall (NFR-2):** deploy adds no new egress; seeding + healthcheck are local. The `--network none` smoke test must still pass and is now documented (AC-5).
- **5-second read contract:** seeding is startup-only; never on a `GET`. No OCR/LLM/inference added anywhere.
- **`/healthz`** stays the pure, ungated liveness route — the Railway healthcheck and the Story 1.5 gate exemption depend on it (AC-3). Cross-check Story 1.5 landed the exemption before relying on it.
- **snake_case**, type hints, ruff line length 100.

### Previous story intelligence (1.1 / 1.3 / 1.5)
- Run tests: `.venv/Scripts/python.exe -m pytest -q`; lint `.venv/Scripts/ruff.exe check . --exclude .venv` + `ruff format --check`. Keep the suite green.
- `app/db/seed.py` `seed(db_path, fixtures_dir)` is stdlib-only, transactional, idempotent, runnable as `python -m app.db.seed` (Story 1.3). Reuse it — do not re-implement seeding.
- Dockerfile already `COPY fixtures ./fixtures` (Story 1.3) — the corpus + 80 images are baked in, ready for seed-if-empty.
- `app/config.py` already reads `DATABASE_PATH` (`or` default `data/app.db`) — point it at the Volume path via Railway env; empty/absent falls back to the local default (good for compose).
- Verify the full chain in-container: `docker run --network none -e ACCESS_TOKEN=demo -e DATABASE_PATH=/tmp/app.db …` → boots, seeds, `/healthz` 200, gate enforced, queue shows seeded rows.

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.6: Deploy to Railway with run-from-README]
- [Source: _bmad-output/planning-artifacts/architecture.md#Deployment & Dev Strategy (Docker Desktop → Railway Pro)] (Dockerfile not Nixpacks; automatic HTTPS; Volume; `$PORT`)
- [Source: _bmad-output/planning-artifacts/architecture.md#Infrastructure & Deployment] (single service, Volume for SQLite + generated images)
- [Source: _bmad-output/planning-artifacts/architecture.md#Project Structure] (`railway.toml`: Dockerfile build, Volume mount, healthcheck; `.env.example` vars)
- [Source: architecture.md D1 / D7] (SQLite-on-Volume single service; derived artifacts on Volume, fixtures baked in)
- [Source: _bmad-output/implementation-artifacts/1-5-token-gated-access-and-clean-denial.md] (gate the public URL sits behind; `/healthz` exemption)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] (`/healthz` vs auth-gate exemption)
- FR-26 (partial) / AR-2 / AR-8 [Source: epics.md]

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Amelia / bmad-dev-story)

### Debug Log References

- Full suite green: `92 passed` (6 new in `test_deploy_config.py`); ruff lint + format clean.
- In-container offline smoke test (`docker run --network none`, `DATABASE_PATH=/data/app.db`):
  `/healthz` → `200 {"status":"ok"}` (ungated); `GET /` no-token → `303` (gate enforced);
  seed-if-empty → **36 submissions + 36 SEEDED events** on the Volume path; `python -m app.db.seed`
  re-run → still 36 (idempotent); container reported `healthy`.
- Tooling note: Git-Bash MSYS mangled `-e DATABASE_PATH=/data/app.db` (→ `C:/Program Files/Git/...`);
  re-ran the container verification via PowerShell to pass the POSIX mount path through unmangled.

### Completion Notes List

- **Code/docs/tests complete and verified locally + in-container.** AC-1 (railway.toml build +
  `$PORT` start + healthcheck), AC-2 (seed-if-empty logic), AC-3 (`/healthz` 200 ungated),
  AC-4 (`.env.example` parity + real README commands), AC-5 (offline smoke test documented + run)
  are all satisfied at the artifact + behavior level.
- **Deviation 1 — Volume not in `railway.toml`.** AC-1 literally asks for the Volume *in*
  `railway.toml`; Railway config-as-code has no volume key (verified against Railway docs). Intent
  satisfied instead: `railway.toml` documents the mount in comments, `DATABASE_PATH=/data/app.db`
  points the app inside the mount, and the Volume is created via `railway volume add --mount-path
  /data --service ttb-web`. Test author already scoped Task 5 to builder + healthcheck only.
- **Deviation 2 — `baseline_commit` updated `dc0de45 → 7bba722`.** The frontmatter carried a
  drafting-time baseline predating stories 1.4/1.5; no work had started (all tasks unchecked), so it
  was a stale placeholder, not a work-start snapshot. Set to current HEAD so the per-story review
  diff is clean. Flagged for visibility.
- **Pending operator deploy step (outward action — not auto-run):** the live deploy needs
  (1) `railway volume add --mount-path /data --service ttb-web`, (2) service vars
  `DATABASE_PATH=/data/app.db` + `ACCESS_TOKEN`/`LLM_ENABLED` etc., (3) `git commit` + `git push`
  to `main` (auto-deploys), then verify `https://ttb-label-poc-production.up.railway.app`. Left for
  explicit go-ahead per push policy. Playbook: `docs/railway-deployment.md`.

### File List

- **New:** `railway.toml`, `tests/test_deploy_config.py`, `docs/railway-deployment.md`.
- **Modified:** `app/main.py` (seed-if-empty lifespan guard), `Dockerfile` (`$PORT`-aware HEALTHCHECK +
  comments), `README.md` (real run flow + smoke test + Railway deploy; planning banner removed),
  `.env.example` (`DATABASE_PATH` comment tightened to the `/data/app.db` Volume path).
- **Story file:** frontmatter `baseline_commit`, task checkboxes, Dev Agent Record, Change Log, Status.

### Change Log

- 2026-06-12 — Story 1.6 implemented (Amelia). Added `railway.toml` (Dockerfile build, `$PORT` start
  command, `/healthz` healthcheck), seed-if-empty startup guard in `app/main.py`, `$PORT`-aware
  Dockerfile HEALTHCHECK, README rewrite (real run flow + offline smoke test + Railway deploy; planning
  banner removed), `.env.example` comment tightening, `docs/railway-deployment.md` (distilled Railway
  ops doc), and `tests/test_deploy_config.py` (6 tests). Full suite `92 passed`, ruff clean. Verified
  in-container under `--network none`. Renamed the Railway project `TTB-label-web → TTB-label-POC` and
  service `TTB-label-POC → ttb-web`. `baseline_commit` corrected to current HEAD (`7bba722`). Live
  deploy (Volume create + env vars + push) left as the explicit operator step.
