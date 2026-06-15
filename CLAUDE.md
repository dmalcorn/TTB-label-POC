# CLAUDE.md — TTB-label-POC

The authoritative AI rules for this codebase live in
[`_bmad-output/project-context.md`](_bmad-output/project-context.md) — read it before
writing code and follow it exactly. This file adds operational notes that agents
working in this repo need.

## Validating: host venv (fast) or the dev container (full dep parity)

Two equally-valid ways to validate — pick by whether you need the native OCR stack:

**Host venv** (Python 3.14) — fast, pure-Python: `bash scripts/ci.sh` or
`.venv/Scripts/python.exe -m pytest -q`. Has every pure-Python dep; the OCR-native
tests skip cleanly (Tesseract/PaddleOCR aren't installed host-side). Best for the
inner loop.

**Dev container** (`web`) — full parity with the shipped image, including native
Tesseract + PaddleOCR + OpenCV:

```
docker compose up -d        # start the web service (built image + LIVE source mounts)
bash scripts/ci.sh          # auto-detects the running service & runs the checks IN it
```

`compose.yaml` now **bind-mounts the live source** onto the image, so the container
tests *your current code* — not a build-time snapshot. Use it to run the OCR-native
tests for real and to type-check the OCR/`cv2` code paths.

mypy note: on the **host** there's no `cv2`/OCR natives, so `mypy
--ignore-missing-imports` treats those as `Any` — type errors in OCR-importing code
won't surface host-side (run mypy in the container to catch them). That's expected
for a host run; don't chase it there.

The image also serves the **production artifact + the zero-egress smoke test**
(NFR-2): `docker run --rm --network none -e LLM_ENABLED=false ttb-label-poc`.

## CI

`bash scripts/ci.sh` runs: format → lint → typecheck (mypy) → tests. `--fix`
auto-formats and applies safe lint fixes first, then verifies. mypy is declared in
`requirements.txt` (CI Phase 3). The gate runs over the repo but **excludes
`auto-run/`** (see `[tool.ruff] extend-exclude` in `pyproject.toml`).

## Don't

- Don't edit `auto-run/` as part of story work — it is the overnight orchestrator
  harness, walled off from story commits.
