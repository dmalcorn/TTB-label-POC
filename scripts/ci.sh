#!/usr/bin/env bash
# Local CI for the TTB label POC — the fast checks before trusting the code.
#
#   bash scripts/ci.sh          # check only: format, lint, typecheck, tests
#   bash scripts/ci.sh --fix    # auto-fix formatting + lint first, then check
#
# Per _bmad-output/planning-artifacts/architecture.md, this is a CONTAINERIZED
# FastAPI monolith: native OCR deps (Tesseract, OpenCV, PaddleOCR) and pinned
# model weights live inside the Docker image, not on the host. The checks here
# import the project, so they must run where those deps exist — i.e. inside the
# dev container (Docker Desktop, compose.yaml). When the container isn't
# available the run degrades to host-side with a loud warning (results may
# differ because host deps are missing), and every phase skips cleanly when a
# tool isn't installed or there's nothing yet to check. So this runs green today
# and gets useful as the Dockerfile/compose.yaml and code land.
#
# Not included (these belong to the heavyweight factory variant in
# targetsetup/ci-script-specification.md, not a single-service SQLite POC):
# --story flags, a migration gate (no migrations — plain SQL DDL + seed),
# multi-stack phases.

# pipefail: a failure in a `cmd | tee log` pipe is not masked by tee exiting 0.
set -euo pipefail

FIX=false
case "${1:-}" in
  --fix) FIX=true ;;
  "")    ;;
  *)     echo "Unknown flag: '$1' (use --fix or no args)" >&2; exit 2 ;;
esac

# Dev container coordination (architecture.md — Docker Desktop dev stack).
# Service name must match compose.yaml; override via env if it differs.
COMPOSE_FILE="${CI_COMPOSE_FILE:-compose.yaml}"
APP_SERVICE="${CI_APP_SERVICE:-app}"

# Can we dispatch into a running dev container?
container_ready() {
  [ -f "$COMPOSE_FILE" ] || return 1
  command -v docker >/dev/null 2>&1 || return 1
  docker info >/dev/null 2>&1 || return 1
  docker compose -f "$COMPOSE_FILE" ps "$APP_SERVICE" --format json 2>/dev/null \
    | grep -q '"State":"running"' || return 1
  return 0
}

USE_CONTAINER=false
if container_ready; then
  USE_CONTAINER=true
  echo "Dev container '$APP_SERVICE' is up — dispatching checks into it (dep parity)."
else
  echo "WARNING: dev container not available — running host-side (degraded)."
  echo "         Native OCR deps may be missing; start it with:"
  echo "           docker compose up -d $APP_SERVICE"
fi
echo ""

# Run a Python module check in the container when available, else on the host.
pyrun() { # pyrun <module> [args...]
  if $USE_CONTAINER; then
    docker compose -f "$COMPOSE_FILE" exec -T "$APP_SERVICE" python -m "$@"
  else
    python -m "$@"
  fi
}
# Is a tool importable wherever we're running checks?
have() { pyrun "$1" --version >/dev/null 2>&1; }

# Phase 0 — nothing to check yet? Exit clean rather than erroring on an empty tree.
if [ -z "$(git ls-files '*.py')" ]; then
  echo "=== No application code yet (no tracked .py files) — nothing to check ==="
  exit 0
fi

# Phase 1 — Format. Auto-write first when --fix (so trivial whitespace never
# fails a check), then always verify formatting is clean.
echo "=== Phase 1: Format (ruff) ==="
if have ruff; then
  if $FIX; then pyrun ruff format .; pyrun ruff check --fix .; fi
  pyrun ruff format --check .
else
  echo "  ruff not available — skipping"
fi

# Phase 2 — Lint.
echo "=== Phase 2: Lint (ruff) ==="
if have ruff; then
  pyrun ruff check .
else
  echo "  ruff not available — skipping"
fi

# Phase 3 — Type check.
echo "=== Phase 3: Type check (mypy) ==="
if have mypy; then
  pyrun mypy . --ignore-missing-imports
else
  echo "  mypy not available — skipping"
fi

# Phase 4 — Tests. Skip cleanly if pytest is absent or there are no tests yet
# (pytest exits 5 on "no tests collected", which would otherwise fail the run).
echo "=== Phase 4: Tests (pytest) ==="
TESTS="$(git ls-files 'test_*.py' '*_test.py' 'tests/*.py' 'tests/**/*.py')"
if ! have pytest; then
  echo "  pytest not available — skipping"
elif [ -z "$TESTS" ]; then
  echo "  no tests yet — skipping"
else
  pyrun pytest -q
fi

echo ""
echo "=== CI passed ==="
