"""Deploy-config tests (Story 1.6, AC-1 / AC-3 / AC-4).

Pins the deployment contract that can be checked WITHOUT a live Railway:
- `railway.toml` is a Dockerfile build (never Nixpacks) with the `/healthz`
  healthcheck the Story 1.5 gate exemption (AC-3) and Railway's probe rely on,
  and a start command that honors Railway's injected ``$PORT`` (AC-1).
- `.env.example` documents EVERY ``Settings`` field — a missing var is a silent
  clone-and-run footgun (AC-4).
- The seed-if-empty startup guard populates an empty Volume DB and is a no-op
  once data is present (AC-2 logic, exercised without Railway).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from app.config import Settings
from app.db.connection import connect, init_db
from app.main import _seed_if_empty

REPO_ROOT = Path(__file__).resolve().parents[1]
RAILWAY_TOML = REPO_ROOT / "railway.toml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def _railway_config() -> dict:
    with RAILWAY_TOML.open("rb") as fh:
        return tomllib.load(fh)


# ── AC-1 / AC-3: railway.toml build + deploy contract ────────────────────────


def test_railway_toml_parses() -> None:
    cfg = _railway_config()
    assert "build" in cfg
    assert "deploy" in cfg


def test_build_is_dockerfile_not_nixpacks() -> None:
    build = _railway_config()["build"]
    # The image bakes native OCR deps; Nixpacks can't reproduce them (D1).
    assert build["builder"].upper() == "DOCKERFILE"
    assert "nixpacks" not in build["builder"].lower()
    assert build["dockerfilePath"] == "Dockerfile"


def test_healthcheck_path_is_healthz() -> None:
    # Railway's probe (and the Story 1.5 gate exemption, AC-3) target /healthz.
    assert _railway_config()["deploy"]["healthcheckPath"] == "/healthz"


def test_start_command_honors_railway_port() -> None:
    # Railway runs startCommand in EXEC form (no shell), so a bare `--port $PORT`
    # reaches uvicorn literally and crashes (observed on the first 1.6 deploy). The
    # command must be shell-wrapped so $PORT expands (AC-1, $PORT reconciliation).
    start = _railway_config()["deploy"]["startCommand"]
    # Structural, not substring-anywhere: must actually be `sh -c '<uvicorn ...>'`.
    assert start.startswith("sh -c "), f"startCommand must be shell-wrapped: {start!r}"
    inner = start[len("sh -c ") :].strip().strip("'\"")
    assert inner.startswith("uvicorn app.main:app"), f"unexpected start command: {inner!r}"
    assert "--port ${PORT:-8000}" in inner  # expanded PORT ref with local fallback
    assert "--port 8000" not in inner  # no hardcoded port on the Railway path


def test_start_command_trusts_railway_proxy_headers() -> None:
    # Railway terminates TLS at its edge; without trusting forwarded headers the
    # Story 1.5 access cookie ships WITHOUT `Secure` in prod (deferred-work item
    # owned by Story 1.6). The startCommand must enable proxy-header trust.
    start = _railway_config()["deploy"]["startCommand"]
    assert "--proxy-headers" in start
    assert "--forwarded-allow-ips" in start


def test_dockerfile_healthcheck_is_empty_port_safe() -> None:
    # The probe must fall back to 8000 for BOTH an absent and an empty `PORT`.
    # `get('PORT', '8000')` only covers absent; an empty value builds a malformed
    # URL and false-fails. The fix uses `get('PORT') or '8000'`.
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "os.environ.get('PORT') or '8000'" in dockerfile
    assert "os.environ.get('PORT','8000')" not in dockerfile
    assert "os.environ.get('PORT', '8000')" not in dockerfile


# ── AC-4: .env.example documents every Settings field ────────────────────────


def _env_example_keys() -> set[str]:
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def test_env_example_documents_every_settings_field() -> None:
    documented = _env_example_keys()
    expected = {name.upper() for name in Settings.model_fields}
    missing = expected - documented
    assert not missing, f"undocumented runtime vars in .env.example: {sorted(missing)}"


# ── AC-2 logic: seed-if-empty guard (no live Railway needed) ──────────────────


def test_seed_if_empty_populates_an_empty_db(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path)
    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 0

    _seed_if_empty(db_path)

    with connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
    assert count > 0, "an empty Volume DB must be seeded on startup"


def test_seed_if_empty_boots_degraded_on_seed_failure(tmp_path, monkeypatch, caplog) -> None:
    # Boot-degraded posture (code review 2026-06-12): a seed failure must NOT
    # propagate out of startup — a reachable empty-DB demo beats a Railway
    # ON_FAILURE crash-loop. The failure is logged; the empty DB lets the next
    # clean boot retry.
    import logging

    import app.main as main

    db_path = tmp_path / "app.db"
    init_db(db_path)

    def _boom(_db_path) -> None:
        raise RuntimeError("corrupt fixture")

    monkeypatch.setattr(main, "seed", _boom)

    with caplog.at_level(logging.ERROR):
        main._seed_if_empty(db_path)  # must not raise

    with connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 0
    assert any("Seed-if-empty failed" in r.message for r in caplog.records)


def test_seed_if_empty_is_a_noop_when_data_present(tmp_path) -> None:
    db_path = tmp_path / "app.db"
    init_db(db_path)
    _seed_if_empty(db_path)
    with connect(db_path) as conn:
        seeded = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        # Drop one row so a re-seed (DELETE+reload) would be detectable.
        conn.execute("DELETE FROM submissions WHERE id = (SELECT MIN(id) FROM submissions)")

    _seed_if_empty(db_path)  # table is non-empty → must NOT reseed

    with connect(db_path) as conn:
        after = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
    assert after == seeded - 1, "seed-if-empty must not clobber an already-populated DB"
