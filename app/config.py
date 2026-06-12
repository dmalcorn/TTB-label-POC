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

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            access_token=os.getenv("ACCESS_TOKEN"),
            llm_enabled=_env_bool("LLM_ENABLED", default=False),
            llm_provider=os.getenv("LLM_PROVIDER"),
            llm_base_url=os.getenv("LLM_BASE_URL"),
            langchain_tracing_enabled=_env_bool("LANGCHAIN_TRACING_ENABLED", default=False),
        )


def get_settings() -> Settings:
    """Resolve settings from the current environment."""
    return Settings.from_env()
