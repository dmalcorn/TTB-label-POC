"""Typed application settings sourced from the environment.

Every field carries a safe default so an empty environment never raises and
`GET /healthz` succeeds with nothing configured (AR-9). Absent LLM keys mean the
model layer is simply off — the OCR-only path stays fully functional.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:  # type-only — never imports a provider adapter/SDK at runtime
    from app.adapters.llm.base import ModelAdapter


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


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Parse a comma-separated env var into a lower-cased tuple (order preserved); fall
    back to ``default`` when absent/empty so a blank value never disables everything."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    items = tuple(part.strip().lower() for part in raw.split(",") if part.strip())
    return items or default


class Settings(BaseModel):
    """Environment-driven configuration.

    Secrets are read here but never logged. Absent keys leave features off
    rather than raising — the zero-egress OCR-only path must stay bootable.
    """

    access_token: str | None = None
    llm_enabled: bool = False
    llm_provider: str | None = None
    llm_base_url: str | None = None
    # Per-provider API keys (Story 2.5). Absent ⇒ that provider's model layer is
    # simply off (the factory returns None) — never an exception (AR-9). Read here
    # but NEVER logged. `local` needs no key (it is a zero-egress localhost server).
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    # Active model id (Story 2.5). Absent ⇒ a per-provider default is used; the demo
    # / benchmark sets this explicitly. Production swaps model + endpoint by config.
    llm_model_id: str | None = None
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
    # OCR feature toggle. When false, the OCR stage is skipped entirely (no engines run)
    # and the review cards show only the AI reading (provided LLM_ENABLED). OCR defaults
    # ON — it is the zero-egress baseline. Pairs with LLM_ENABLED: with BOTH on, each
    # comparison card shows an OCR row AND an AI row (the head-to-head display).
    ocr_enabled: bool = True
    # OCR pass selection (perf toggle). The pipeline OCRs each image with every engine in
    # ``ocr_engines``, on the ORIGINAL and — when ``ocr_preprocess_variants`` is true — that
    # engine's preprocessed variant. Fewer engines / no variants ⇒ fewer (slow) OCR passes.
    # Defaults run the full matrix (both engines + variants) so tests + the benchmark
    # bake-off are unchanged; deployments dial it down via OCR_ENGINES / OCR_PREPROCESS_VARIANTS.
    ocr_engines: tuple[str, ...] = ("tesseract", "paddleocr")
    ocr_preprocess_variants: bool = True

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            access_token=os.getenv("ACCESS_TOKEN"),
            llm_enabled=_env_bool("LLM_ENABLED", default=False),
            llm_provider=os.getenv("LLM_PROVIDER"),
            llm_base_url=os.getenv("LLM_BASE_URL"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            llm_model_id=os.getenv("LLM_MODEL_ID"),
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
            ocr_enabled=_env_bool("OCR_ENABLED", default=True),
            ocr_engines=_env_csv("OCR_ENGINES", default=("tesseract", "paddleocr")),
            ocr_preprocess_variants=_env_bool("OCR_PREPROCESS_VARIANTS", default=True),
        )


def get_settings() -> Settings:
    """Resolve settings from the current environment."""
    return Settings.from_env()


# ── LLM provider gating + factory (Story 2.5, AC2) ───────────────────────────
# The single decision point for "is the model layer on, and which provider?". It
# returns an adapter ONLY when LLM_ENABLED=true, a supported provider is set, and
# (for the cloud providers) the provider's key is present — otherwise None, meaning
# "model layer off; run OCR-only" (AR-9). Crucially, NO adapter is imported or
# constructed on the None paths, so `--network none` + LLM_ENABLED=false never even
# touches a provider SDK (the egress proof depends on this — outbound-calls §4).

# Supported provider keys (the LLM_PROVIDER vocabulary). `local` is the zero-egress
# localhost branch and needs no API key.
_SUPPORTED_PROVIDERS: frozenset[str] = frozenset({"openai", "anthropic", "google", "local"})

# Per-provider default model id when LLM_MODEL_ID is unset. Config-swappable — the
# benchmark/demo sets LLM_MODEL_ID explicitly; these are only sensible fallbacks.
_DEFAULT_MODEL_ID: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-opus-4-8",
    "google": "gemini-2.0-flash",
    "local": "local-vlm",
}


def _provider_api_key(settings: Settings, provider: str) -> str | None:
    """The configured API key for a cloud provider (``None`` if absent)."""
    return {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "google": settings.google_api_key,
    }.get(provider)


def _construct_adapter(provider: str, settings: Settings) -> ModelAdapter:
    """Build the concrete adapter for ``provider``. The adapter class is imported
    **lazily here** so the None paths of :func:`get_llm_adapter` never import a
    provider module, and constructing the adapter never imports its SDK or opens a
    socket (the SDK import + client are lazy inside the adapter)."""
    model_id = settings.llm_model_id or _DEFAULT_MODEL_ID[provider]
    base_url = settings.llm_base_url
    if provider == "openai":
        from app.adapters.llm.openai import OpenAiAdapter

        return OpenAiAdapter(model_id=model_id, api_key=settings.openai_api_key, base_url=base_url)
    if provider == "anthropic":
        from app.adapters.llm.anthropic import AnthropicAdapter

        return AnthropicAdapter(
            model_id=model_id, api_key=settings.anthropic_api_key, base_url=base_url
        )
    if provider == "google":
        from app.adapters.llm.google import GoogleAdapter

        return GoogleAdapter(model_id=model_id, api_key=settings.google_api_key, base_url=base_url)
    # provider == "local"
    from app.adapters.llm.local_vlm import LocalVlmAdapter

    return LocalVlmAdapter(model_id=model_id, base_url=base_url)


def get_llm_adapter(settings: Settings) -> ModelAdapter | None:
    """Resolve the active model adapter, or ``None`` when the model layer is off.

    Returns ``None`` — and constructs nothing — when ``LLM_ENABLED`` is false, no
    (or an unsupported) provider is set, or a cloud provider's key is absent. The
    pipeline treats ``None`` as "model layer off" and completes OCR-only (AC2). The
    ``local`` provider needs no key (zero-egress localhost).
    """
    if not settings.llm_enabled:
        return None
    provider = (settings.llm_provider or "").strip().lower()
    if provider not in _SUPPORTED_PROVIDERS:
        return None
    if provider != "local" and not _provider_api_key(settings, provider):
        return None
    return _construct_adapter(provider, settings)
