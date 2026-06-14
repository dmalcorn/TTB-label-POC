"""Local-only, toggleable LangChain tracing for the model layer (Story 5.1, FR-24).

The benchmark harness wants per-call **model identity + timing + tokens** captured
for procurement comparison. Story 2.5 already persists that telemetry durably in the
``llm_results`` columns (``model_name`` / ``model_id`` / ``model_full_id`` /
``provider`` / ``requested_at`` / ``responded_at`` / ``latency_ms`` /
``prompt_tokens`` / ``completion_tokens`` + the DB-derived ``total_tokens``). This
module is the **toggleable LangChain local-only tracing envelope** on top of that
write — the thing the benchmarking plan calls for and the outbound-calls inventory
classifies ``local`` (TODO-3).

**The firewall invariant (the spine of this story).** Tracing **never egresses
telemetry**:

- it runs in **local-only mode** — this module configures **no** LangSmith / cloud
  trace endpoint (no ``LANGCHAIN_ENDPOINT`` / ``LANGSMITH_API_KEY`` is ever set here)
  and opens **no** off-host connection; the only off-host call sites in the app stay
  ``app/adapters/llm/{openai,google,anthropic}.py``;
- it is **toggleable** via the master off-switch ``LANGCHAIN_TRACING_ENABLED``
  (``Settings.langchain_tracing_enabled``, default off). When disabled, **no tracing
  code path executes** — nothing is imported, constructed, or invoked — so the
  model-call path and the review workspace behave byte-for-byte identically to the
  no-tracing baseline (AC3).

**What is captured.** Only the produced :class:`~app.contracts.LlmResult`'s identity,
timing, and token counts — **never** the prompt text, the label-image bytes, the OCR
text, or any secret/key (project-context: secrets never logged; VLM-only purity is
untouched — the tracer reads the *result*, not the model input). Per data-dictionary
§4, ``langchain_trace_id`` is **not a POC column**, so tracing adds **no** schema: the
durable record is the ``llm_results`` row; this module's value is the local-only,
toggleable instrumentation around the call.

LangChain is imported **lazily inside** :func:`_build_handler` — never at module load
and never on the web import path — exactly as the provider SDKs are lazy inside the
adapters. So a disabled run never imports LangChain, and ``import app.main`` /
``import app.pipeline.run`` stay free of the tracing client.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.config import get_settings

if TYPE_CHECKING:
    from app.config import Settings
    from app.contracts import LlmResult

logger = logging.getLogger(__name__)


def tracing_enabled(settings: Settings | None = None) -> bool:
    """The master off-switch: ``True`` only when ``LANGCHAIN_TRACING_ENABLED`` is set.

    The single decision point. Resolves from the passed ``settings`` or, when
    ``None``, from the current environment. Default off (AR-9 fail-safe) — a garbage
    env value (e.g. ``ture``) parses to ``False`` via ``config._env_bool``.
    """
    resolved = settings if settings is not None else get_settings()
    return resolved.langchain_tracing_enabled


def _build_handler() -> Any:
    """Construct the local-only LangChain callback handler (lazy LangChain import).

    Called **only** on the enabled path. Returns a :class:`LocalTraceHandler`, a
    ``BaseCallbackHandler`` subclass that records LLM-call telemetry to a **local
    sink only** — it configures no cloud endpoint and opens no socket. The import is
    here (not at module top) so a disabled run never imports LangChain and the web
    import path stays tracing-client-free.
    """
    # The whole LangChain-dependent construction — import, subclass definition, AND
    # instantiation — is inside one guard so that "LangChain absent OR incompatible"
    # all degrade to the local logging sink rather than crashing the pipeline. A
    # bare `except ImportError` would only cover a missing package; subclassing a
    # changed/abstract BaseCallbackHandler (metaclass/abstract-method enforcement) or
    # an __init__ incompatibility raises a non-ImportError that must ALSO degrade
    # (tracing is additive instrumentation — story Dev Notes "degrade, never crash").
    # No egress on either branch.
    try:
        from langchain_core.callbacks import BaseCallbackHandler

        class LocalTraceHandler(BaseCallbackHandler):  # type: ignore[misc, valid-type]
            """A LangChain callback that records identity/timing/tokens locally only.

            Records into the in-handler ``records`` list and the local structured log
            — a local sink with **zero** telemetry egress (no LangSmith/cloud endpoint).
            """

            def __init__(self) -> None:
                self.records: list[dict[str, Any]] = []

            def record(self, telemetry: dict[str, Any]) -> None:
                self.records.append(telemetry)
                _log_trace(telemetry)

        return LocalTraceHandler()
    except Exception:  # noqa: BLE001 — LangChain absent/incompatible ⇒ degrade, never crash
        logger.debug("LangChain callback base unavailable; using the local logging trace sink")
        return _LoggingTraceHandler()


class _LoggingTraceHandler:
    """Local logging-only trace sink (the fallback when the LangChain base is absent).

    Same surface as ``LocalTraceHandler.record`` — records to a local list + the
    local log; no network, no cloud endpoint.
    """

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, telemetry: dict[str, Any]) -> None:
        self.records.append(telemetry)
        _log_trace(telemetry)


def local_tracer(settings: Settings | None = None) -> Any | None:
    """The local-only trace handler, or ``None`` when tracing is disabled.

    Disabled ⇒ returns ``None`` and **constructs nothing** (no LangChain import), so
    callers early-return on the no-tracing path (AC3). Enabled ⇒ a local handler that
    records telemetry to a local sink with zero egress (AC1).
    """
    if not tracing_enabled(settings):
        return None
    return _build_handler()


def _telemetry(result: LlmResult) -> dict[str, Any]:
    """The captured trace fields for one model call — **identity + timing + tokens
    only**. Never the prompt, image bytes, ``result_text``, OCR text, or any secret.
    ``total_tokens`` is the derived sum (``None`` if a part is missing)."""
    return {
        "model_name": result.model_name,
        "model_id": result.model_id,
        "model_full_id": result.model_full_id,
        "provider": result.provider,
        "task": result.task,
        "status": result.status,
        "requested_at": result.requested_at,
        "responded_at": result.responded_at,
        "latency_ms": result.latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,  # derived property — never recomputed here
    }


def _log_trace(telemetry: dict[str, Any]) -> None:
    """Emit the trace to the local structured log (a local-only sink, no egress)."""
    logger.info(
        "llm_trace provider=%s model_id=%s latency_ms=%s total_tokens=%s status=%s",
        telemetry.get("provider"),
        telemetry.get("model_id"),
        telemetry.get("latency_ms"),
        telemetry.get("total_tokens"),
        telemetry.get("status"),
    )


def trace_llm_call(
    result: LlmResult,
    *,
    settings: Settings | None = None,
    handler: Any | None = None,
) -> dict[str, Any] | None:
    """Trace one completed model call locally — or do nothing when tracing is off.

    Disabled (the default) ⇒ a **no-op** that imports nothing and returns ``None``
    (AC3). Enabled ⇒ extracts the call's identity/timing/tokens from ``result``,
    records them to the local sink (the passed ``handler``, or a freshly built local
    one), and returns the captured telemetry dict — the local-only capture (AC2). The
    durable, queryable record remains the ``llm_results`` row the pipeline already
    wrote; this is the toggleable trace envelope, never an off-host call.
    """
    if not tracing_enabled(settings):
        return None
    telemetry = _telemetry(result)
    sink = handler if handler is not None else _build_handler()
    if sink is not None and hasattr(sink, "record"):
        sink.record(telemetry)
    else:  # pragma: no cover - defensive; _build_handler always returns a recorder
        _log_trace(telemetry)
    return telemetry
