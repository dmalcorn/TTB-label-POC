"""Settings boundary tests (AR-9 — absent/garbage env never raises, features off).

The skeleton's core invariant is that a clean OR malformed environment still
boots OCR-only with zero egress. These tests pin the env-parsing edges that the
healthz path alone does not exercise: truthy/garbage `_env_bool` values and
`Settings.from_env()` in isolation.
"""

import pytest

from app.config import Settings, _env_bool, get_settings

TRUTHY = ["1", "true", "yes", "on", "TRUE", "Yes", "  true  ", "ON"]
FALSY_OR_GARBAGE = ["0", "false", "no", "off", "", "ture", "2", "yes please", "enabled"]


@pytest.mark.parametrize("raw", TRUTHY)
def test_env_bool_truthy_values(monkeypatch, raw: str) -> None:
    monkeypatch.setenv("FLAG", raw)
    assert _env_bool("FLAG") is True


@pytest.mark.parametrize("raw", FALSY_OR_GARBAGE)
def test_env_bool_falsy_and_garbage_values_are_false(monkeypatch, raw: str) -> None:
    # Fail-safe direction: anything not explicitly truthy ⇒ False (feature off).
    monkeypatch.setenv("FLAG", raw)
    assert _env_bool("FLAG") is False


def test_env_bool_absent_returns_default(monkeypatch) -> None:
    monkeypatch.delenv("FLAG", raising=False)
    assert _env_bool("FLAG") is False
    assert _env_bool("FLAG", default=True) is True


def test_from_env_clean_environment_uses_safe_defaults(monkeypatch) -> None:
    for key in (
        "ACCESS_TOKEN",
        "LLM_ENABLED",
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LANGCHAIN_TRACING_ENABLED",
        "DATABASE_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = get_settings()
    assert settings.access_token is None
    assert settings.llm_enabled is False
    assert settings.llm_provider is None
    assert settings.llm_base_url is None
    assert settings.langchain_tracing_enabled is False
    assert settings.database_path == "data/app.db"


def test_from_env_garbage_llm_enabled_keeps_layer_off(monkeypatch) -> None:
    # A typo (`ture`) must not silently enable the LLM boundary — fail safe to off.
    monkeypatch.setenv("LLM_ENABLED", "ture")
    assert get_settings().llm_enabled is False


def test_from_env_does_not_raise_on_enabled_without_provider(monkeypatch) -> None:
    # Documents current behavior: LLM_ENABLED=true with no provider/base_url does
    # NOT raise (no fail-fast yet — deferred to the Epic-2 story that wires the
    # LLM). The skeleton must still construct Settings without error.
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    settings = Settings.from_env()
    assert settings.llm_enabled is True
    assert settings.llm_provider is None
    assert settings.llm_base_url is None


def test_database_path_empty_string_falls_back_to_default(monkeypatch) -> None:
    # A set-but-empty DATABASE_PATH="" must fall back to the default, not open a
    # throwaway temp DB via sqlite3.connect("") (code review 2026-06-12, P2).
    monkeypatch.setenv("DATABASE_PATH", "")
    assert Settings.from_env().database_path == "data/app.db"
