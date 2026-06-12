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
    # Railway injects $PORT (defaults to 8080); the listener must follow it so the
    # edge and the container never disagree (AC-1, the $PORT reconciliation).
    start = _railway_config()["deploy"]["startCommand"]
    assert "$PORT" in start
    assert "app.main:app" in start
    assert "--port 8000" not in start  # no hardcoded port on the Railway path


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
