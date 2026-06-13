# CLAUDE.md — TTB-label-POC

The authoritative AI rules for this codebase live in
[`_bmad-output/project-context.md`](_bmad-output/project-context.md) — read it before
writing code and follow it exactly. This file adds operational notes that agents
working in this repo need.

## Validate on the HOST venv — do NOT run CI inside the container (for now)

Validate your work with the **host venv** (Python 3.14): `bash scripts/ci.sh` or
`.venv/Scripts/python.exe -m pytest -q`. It has every pure-Python dep and is fast.

**Do NOT try to run the test/CI suite inside the `web` Docker container.** The
container COPYs the source at build time (no bind-mount in `compose.yaml`), so it
holds a **frozen, stale** snapshot — `docker compose exec web …` would test old code,
not your edits. Don't `docker compose up -d` to "get dep parity for CI"; it won't
reflect your changes and just wastes time. (Live bind-mounted container CI is a
planned future enhancement; until then, host validation is canonical.)

mypy note: the host has no `cv2`/OCR natives, so `mypy --ignore-missing-imports`
treats those as `Any` — type errors in code that imports them won't surface
host-side. That's expected; don't chase it.

The container/image is for **building the production artifact and the zero-egress
smoke test** (NFR-2): `docker run --rm --network none -e LLM_ENABLED=false ttb-label-poc`
— not for live development CI.

## CI

`bash scripts/ci.sh` runs: format → lint → typecheck (mypy) → tests. `--fix`
auto-formats and applies safe lint fixes first, then verifies. mypy is declared in
`requirements.txt` (CI Phase 3). The gate runs over the repo but **excludes
`auto-run/`** (see `[tool.ruff] extend-exclude` in `pyproject.toml`).

## Don't

- Don't edit `auto-run/` as part of story work — it is the overnight orchestrator
  harness, walled off from story commits.
