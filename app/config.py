"""Typed application settings sourced from the environment.

Every field carries a safe default so an empty environment never raises and
`GET /healthz` succeeds with nothing configured (AR-9). Absent LLM keys mean the
model layer is simply off — the OCR-only path stays fully functional.
"""

from __future__ import annotations

import os

from pydantic import BaseModel


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, min_value: int | None = None) -> int:
    """Parse an int env var; fall back to ``default`` on absent/garbage so a
    malformed value never stops the app booting (AR-9, fail-safe to default).

    When ``min_value`` is given, an in-range integer is required: a parsed value
    below it (e.g. ``0`` or a negative for a worker/batch/interval count) also
    falls back to ``default`` rather than producing a degenerate config — a
    non-positive scheduler interval crashes APScheduler at boot, and a ``LIMIT``
    of ``0``/negative makes the sweep silently inert (``LIMIT 0``) or unbounded
    (SQLite reads a negative ``LIMIT`` as no limit), defeating the bounded-batch
    read-path guarantee. The floor closes both."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    if min_value is not None and value < min_value:
        return default
    return value


class Settings(BaseModel):
    """Environment-driven configuration.

    Secrets are read here but never logged. Absent keys leave features off
    rather than raising — the zero-egress OCR-only path must stay bootable.
    """

    access_token: str | None = None
    llm_enabled: bool = False
    llm_provider: str | None = None
    llm_base_url: str | None = None
    langchain_tracing_enabled: bool = False
    # SQLite database file. Local default for dev; the Railway Volume mount path in
    # deployment (Story 1.6 wires the mount). Absent ⇒ default, never raises.
    database_path: str = "data/app.db"
    # Background sweep / pipeline (Story 2.2). Safe defaults so an empty env boots:
    # the sweep runs in-process with bounded concurrency. `scheduler_enabled=false`
    # disables the live sweep entirely (tests construct the app without one).
    scheduler_enabled: bool = True
    sweep_interval_seconds: int = 5
    pipeline_max_workers: int = 2
    pipeline_batch_size: int = 10
    # Root for DERIVED generated images — the OpenCV enhanced/binarized variants
    # (Story 2.3). A purgeable directory on the Railway Volume (default beside the
    # SQLite file under `data/`, which is gitignored). Seeded fixtures stay read-only
    # and baked into the image; ONLY derived variants are written here. Demo reset
    # (Epic 6, POST /reset) purges this root — see the TODO hook in pipeline/preprocess.
    generated_images_dir: str = "data/generated"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            access_token=os.getenv("ACCESS_TOKEN"),
            llm_enabled=_env_bool("LLM_ENABLED", default=False),
            llm_provider=os.getenv("LLM_PROVIDER"),
            llm_base_url=os.getenv("LLM_BASE_URL"),
            langchain_tracing_enabled=_env_bool("LANGCHAIN_TRACING_ENABLED", default=False),
            # `or` (not getenv's default arg) so a set-but-empty DATABASE_PATH=""
            # falls back to the default instead of opening a throwaway temp DB.
            database_path=os.getenv("DATABASE_PATH") or "data/app.db",
            scheduler_enabled=_env_bool("SCHEDULER_ENABLED", default=True),
            sweep_interval_seconds=_env_int("SWEEP_INTERVAL_SECONDS", default=5, min_value=1),
            pipeline_max_workers=_env_int("PIPELINE_MAX_WORKERS", default=2, min_value=1),
            pipeline_batch_size=_env_int("PIPELINE_BATCH_SIZE", default=10, min_value=1),
            # `or` so a set-but-empty GENERATED_IMAGES_DIR="" falls back to the default
            # rather than writing variants into the process CWD.
            generated_images_dir=os.getenv("GENERATED_IMAGES_DIR") or "data/generated",
        )


def get_settings() -> Settings:
    """Resolve settings from the current environment."""
    return Settings.from_env()
