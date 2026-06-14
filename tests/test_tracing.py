"""Local-only toggleable tracing tests (Story 5.1, all ACs).

**Offline by construction.** No test configures a LangSmith/cloud endpoint or makes
a real provider call: tracing is local-only, and when disabled it imports nothing.
These tests pin the master off-switch (`LANGCHAIN_TRACING_ENABLED`), the captured
telemetry (identity + timing + tokens, never prompt/secret), the "behaves
identically when off" guarantee, and the firewall invariant (no off-host origin,
no cloud-trace env) — mirroring the egress rigor of ``test_llm_adapters.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.benchmark import tracing
from app.config import Settings
from app.contracts import LlmResult

# A canned successful model result — the telemetry the tracer reads (it never sees
# the prompt/image; only the produced LlmResult's identity/timing/tokens).
_RESULT = LlmResult(
    model_name="Claude Opus 4.8",
    model_id="claude-opus-4-8",
    model_full_id="claude-opus-4-8[1m]",
    provider="anthropic",
    task="extract_fields",
    result_text='{"brand_name": "Stone\'s Throw"}',
    prompt_tokens=10,
    completion_tokens=20,
    latency_ms=42,
    requested_at="2026-06-14T00:00:00+00:00",
    responded_at="2026-06-14T00:00:00.042000+00:00",
    status="OK",
)


def _enabled() -> Settings:
    return Settings(langchain_tracing_enabled=True)


def _disabled() -> Settings:
    return Settings(langchain_tracing_enabled=False)


# ── AC3: master off-switch — disabled is the default and the safe state ───────


def test_tracing_disabled_by_default() -> None:
    # A clean Settings (and a garbage env) leaves tracing OFF — the safe default.
    assert tracing.tracing_enabled(_disabled()) is False
    assert tracing.tracing_enabled(Settings()) is False


def test_tracing_enabled_only_when_flag_true() -> None:
    assert tracing.tracing_enabled(_enabled()) is True


def test_local_tracer_returns_none_when_disabled() -> None:
    # Disabled ⇒ construct NOTHING (no handler), so callers can early-return.
    assert tracing.local_tracer(_disabled()) is None


def test_trace_llm_call_is_a_noop_when_disabled() -> None:
    # Disabled ⇒ no tracing code path: returns None and captures nothing.
    assert tracing.trace_llm_call(_RESULT, settings=_disabled()) is None


def test_disabled_path_never_imports_langchain(monkeypatch) -> None:
    """AC3: when disabled, the LangChain tracing symbol is never touched — the
    model-call path behaves byte-for-byte identically to the no-tracing baseline."""

    def _boom(*_a, **_k):  # pragma: no cover - must never be called
        raise AssertionError("LangChain tracer constructed on the DISABLED path")

    monkeypatch.setattr(tracing, "_build_handler", _boom)
    assert tracing.local_tracer(_disabled()) is None
    assert tracing.trace_llm_call(_RESULT, settings=_disabled()) is None


# ── AC1/AC2: enabled ⇒ identity + timing + tokens captured locally ────────────


def test_local_tracer_returns_handler_when_enabled() -> None:
    handler = tracing.local_tracer(_enabled())
    assert handler is not None


def test_trace_captures_identity_timing_tokens_only() -> None:
    """AC2: the captured telemetry equals the LlmResult's identity/timing/tokens,
    incl. the derived total_tokens — and carries NO prompt/result_text/secret."""
    record = tracing.trace_llm_call(_RESULT, settings=_enabled())
    assert record is not None
    assert record["model_name"] == "Claude Opus 4.8"
    assert record["model_id"] == "claude-opus-4-8"
    assert record["model_full_id"] == "claude-opus-4-8[1m]"
    assert record["provider"] == "anthropic"
    assert record["requested_at"] == "2026-06-14T00:00:00+00:00"
    assert record["responded_at"] == "2026-06-14T00:00:00.042000+00:00"
    assert record["latency_ms"] == 42
    assert record["prompt_tokens"] == 10
    assert record["completion_tokens"] == 20
    assert record["total_tokens"] == 30  # derived (prompt + completion)
    # task + status are forwarded too (the benchmark needs the call's task + outcome).
    assert record["task"] == "extract_fields"
    assert record["status"] == "OK"
    # Never the model input/output or any secret.
    assert "result_text" not in record
    assert "prompt" not in record
    assert "Stone" not in str(record.values())


def test_trace_record_total_tokens_none_when_a_part_is_missing() -> None:
    partial = LlmResult(model_name="m", prompt_tokens=None, completion_tokens=5)
    record = tracing.trace_llm_call(partial, settings=_enabled())
    assert record is not None
    assert record["total_tokens"] is None


def test_trace_of_an_error_result_is_recorded_honestly() -> None:
    """An ERROR LlmResult (raising/unreachable adapter — llm.py degrade path) is traced
    too: the stage traces BEFORE branching on status, so the degraded benchmark signal
    must capture cleanly with None identity/tokens and status=ERROR, never raising."""
    error_result = LlmResult(
        model_name=None,
        model_id=None,
        provider=None,
        task="extract_fields",
        result_text="RuntimeError: provider unreachable",
        prompt_tokens=None,
        completion_tokens=None,
        status="ERROR",
    )
    record = tracing.trace_llm_call(error_result, settings=_enabled())
    assert record is not None
    assert record["status"] == "ERROR"
    assert record["model_id"] is None
    assert record["total_tokens"] is None
    # Even the degraded row carries no model output/secret.
    assert "result_text" not in record
    assert "unreachable" not in str(record.values())


def test_build_handler_degrades_to_local_sink_when_langchain_unavailable(monkeypatch) -> None:
    """AC1/degrade-never-crash: if the LangChain callback base is absent OR the subclass
    construction fails, _build_handler falls back to the local logging sink — never
    raises — and the fallback still records telemetry locally (no egress)."""
    import builtins

    real_import = builtins.__import__

    def _no_langchain(name, *args, **kwargs):
        if name.startswith("langchain"):
            raise ImportError(f"simulated: {name} unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_langchain)
    handler = tracing._build_handler()
    assert isinstance(handler, tracing._LoggingTraceHandler)
    # The fallback sink still records locally (additive instrumentation, zero egress).
    handler.record({"model_id": "x", "status": "OK"})
    assert handler.records == [{"model_id": "x", "status": "OK"}]


def test_trace_llm_call_records_into_a_passed_handler() -> None:
    """The handler= seam: trace_llm_call records the telemetry into a caller-supplied
    local sink (the records list is the local trace capture, zero egress)."""
    handler = tracing._LoggingTraceHandler()
    record = tracing.trace_llm_call(_RESULT, settings=_enabled(), handler=handler)
    assert record is not None
    assert handler.records == [record]
    assert handler.records[0]["model_id"] == "claude-opus-4-8"


# ── AC4: the firewall invariant — local-only, no cloud trace endpoint ─────────

# Cloud/telemetry trace env this module must NEVER set (LangSmith/LangChain v2).
_CLOUD_TRACE_ENV = re.compile(
    r"LANGCHAIN_ENDPOINT|LANGCHAIN_API_KEY|LANGCHAIN_TRACING_V2|"
    r"LANGSMITH_ENDPOINT|LANGSMITH_API_KEY|LANGSMITH_TRACING"
)


def test_tracing_module_sets_no_cloud_trace_endpoint() -> None:
    """AC4: benchmark/tracing.py configures NO LangSmith/cloud trace endpoint —
    local-only, zero telemetry egress. (The off-host-client guard in
    test_llm_adapters already scans this module for client construction.)"""
    src = (Path(__file__).resolve().parents[1] / "app" / "benchmark" / "tracing.py").read_text(
        encoding="utf-8"
    )
    # The module must not WRITE any cloud-trace env var (os.environ[...] = / setdefault / putenv).
    for m in re.finditer(_CLOUD_TRACE_ENV, src):
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.start())
        line = src[line_start : line_end if line_end != -1 else len(src)]
        assert "=" not in line.split("#")[0].split(m.group(0))[0][-3:], (
            f"tracing.py appears to set a cloud-trace env var: {line.strip()}"
        )


def test_enabled_tracer_opens_no_socket(monkeypatch) -> None:
    """AC4: even enabled, constructing the local tracer and tracing a call performs
    no network I/O — guard the stdlib socket so any connect attempt fails loudly."""
    import socket as _socket

    real_socket = _socket.socket

    class _NoNet(real_socket):  # type: ignore[misc, valid-type]
        def connect(self, *_a, **_k):  # pragma: no cover - must never run
            raise AssertionError("tracing opened a network socket")

        def connect_ex(self, *_a, **_k):  # pragma: no cover
            raise AssertionError("tracing opened a network socket")

    monkeypatch.setattr(_socket, "socket", _NoNet)
    handler = tracing.local_tracer(_enabled())
    assert handler is not None
    assert tracing.trace_llm_call(_RESULT, settings=_enabled()) is not None


# ── env-driven resolution (default off) ───────────────────────────────────────


def test_tracing_enabled_reads_settings_from_env_when_none_passed(monkeypatch) -> None:
    monkeypatch.delenv("LANGCHAIN_TRACING_ENABLED", raising=False)
    assert tracing.tracing_enabled() is False
    monkeypatch.setenv("LANGCHAIN_TRACING_ENABLED", "true")
    assert tracing.tracing_enabled() is True
    monkeypatch.setenv("LANGCHAIN_TRACING_ENABLED", "ture")  # garbage ⇒ off
    assert tracing.tracing_enabled() is False
