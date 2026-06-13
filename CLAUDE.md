# CLAUDE.md — TTB-label-POC

The authoritative AI rules for this codebase live in
[`_bmad-output/project-context.md`](_bmad-output/project-context.md) — read it before
writing code and follow it exactly. This file adds operational notes that agents
working in this repo need.

## Docker Desktop IS available — use the dev container for native deps

Docker Desktop is installed and the daemon is running on this machine. The dev
container is the canonical environment for anything that needs native OCR/image
deps (Tesseract, OpenCV, PaddleOCR) or the offline-pinned runtime. **Do not report
"Docker unavailable" — bring the container up and use it.**

- The compose service is **`web`** (see [`compose.yaml`](compose.yaml)), built from
  [`Dockerfile`](Dockerfile). (Note: the service is `web`, not `app`.)
- Bring it up:  `docker compose up -d web`  (first run builds the image — slow once).
- Run commands inside it:
  - tests:  `docker compose exec -T web pytest -q`
  - the full gate:  `docker compose exec -T web bash scripts/ci.sh`
  - a shell:  `docker compose exec web bash`
- `scripts/ci.sh` auto-detects a **running** `web` container and dispatches its
  checks into it for dependency parity. If the container isn't up it degrades to
  host-side with a warning — so if you see that warning and need real deps, run
  `docker compose up -d web` first, then re-run.

### Which environment to use
- **Pure-Python stories** (e.g. Epic-3 normalization / verdict roll-up — no OCR,
  no image processing): the **host venv** (Python 3.14) is fine and faster.
- **Anything touching OCR / image / native deps, or a zero-egress / firewall
  check** (NFR-2): use the **`web` container** so deps and behavior match the
  shipped image. The egress smoke test is
  `docker run --rm --network none -e LLM_ENABLED=false ttb-label-poc`.

## CI

`bash scripts/ci.sh` runs: format → lint → typecheck (mypy) → tests. `--fix`
auto-formats and applies safe lint fixes first, then verifies. mypy is declared in
`requirements.txt` (CI Phase 3). The gate runs over the repo but **excludes
`auto-run/`** (see `[tool.ruff] extend-exclude` in `pyproject.toml`).

## Don't

- Don't edit `auto-run/` as part of story work — it is the overnight orchestrator
  harness, walled off from story commits.
