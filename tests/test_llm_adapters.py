"""LLM adapter, factory-gating, and egress-boundary tests (Story 2.5, all ACs).

**Offline by construction.** No test makes a real provider call: the provider SDKs
are imported lazily inside the adapters and never reached here. Tests exercise the
shared timing/error wrapper, a fake ``ModelAdapter``, the config factory's gating
(the egress proof: nothing is constructed when the layer is off), and a structural
guard that off-host clients live ONLY under ``app/adapters/llm/``. The pipeline
stage's end-to-end behavior (skip / degrade / persist) lives in ``test_pipeline.py``.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import pytest

import app.config as cfg
from app.adapters.llm._common import load_image, load_image_b64, media_type_for, run_extraction
from app.adapters.llm.base import ModelAdapter
from app.config import Settings, get_llm_adapter
from app.contracts import LlmResult

# The off-host-client signatures the structural egress guard forbids outside
# ``app/adapters/llm/``. Widened beyond the dotted SDK forms so a BARE-import
# construction (``from openai import OpenAI; OpenAI(...)``), an async client, or a
# raw stdlib/third-party HTTP call is caught too (Story 2.5 code-review patch). The
# adapter classes (``OpenAiAdapter`` etc.) do NOT match — they end in ``Adapter``.
_OFF_HOST_CLIENT = re.compile(
    r"\b(?:Async)?OpenAI\(|"
    r"\b(?:Async)?Anthropic\(|"
    r"genai\.Client\(|"
    r"httpx\.(?:Client|AsyncClient)\(|"
    r"requests\.(?:get|post|put|delete|patch|head|request|Session)\(|"
    # The stdlib/aiohttp offenders are matched in BOTH dotted and bare-import form
    # (``from socket import socket; socket(...)``) — the names are distinctive enough
    # not to false-positive on this codebase.
    r"\bClientSession\(|"
    r"\burlopen\(|"
    r"\bsocket\("
)

# ── A fake adapter — the canned/raising stand-in every offline test uses ──────


class FakeModel:
    """A canned :class:`ModelAdapter`; ``raises=True`` simulates an unreachable
    provider whose ``run`` raises (the worst case the stage must still survive)."""

    model_name = "Fake Model"
    model_id = "fake-1"
    model_full_id = "fake-1[test]"
    provider = "local"

    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises

    def run(self, task: str, prompt: str, *, image_path=None) -> LlmResult:
        if self._raises:
            raise RuntimeError("provider unreachable")
        return LlmResult(
            model_name=self.model_name,
            model_id=self.model_id,
            model_full_id=self.model_full_id,
            provider=self.provider,
            task=task,
            result_text='{"brand_name": "Stone\'s Throw"}',
            prompt_tokens=10,
            completion_tokens=20,
            latency_ms=5,
            requested_at="2026-06-13T00:00:00+00:00",
            responded_at="2026-06-13T00:00:01+00:00",
            status="OK",
        )


def test_fake_model_satisfies_protocol():
    assert isinstance(FakeModel(), ModelAdapter)


# ── _common.run_extraction: timing, identity, and never-raise error capture ──


def test_run_extraction_wraps_success_with_timing_and_tokens():
    res = run_extraction(
        provider="openai",
        model_name="m",
        model_id="mid",
        model_full_id="mfid",
        task="extract_fields",
        call=lambda: ("text", 3, 4),
    )
    assert res.status == "OK"
    assert res.result_text == "text"
    assert (res.prompt_tokens, res.completion_tokens) == (3, 4)
    assert res.total_tokens == 7  # derived, never set directly
    assert res.requested_at and res.responded_at and res.latency_ms is not None


def test_run_extraction_downgrades_any_exception_to_error_never_raises():
    def boom():
        raise RuntimeError("unreachable")

    res = run_extraction(
        provider="anthropic",
        model_name="m",
        model_id="mid",
        model_full_id="mfid",
        task="extract_fields",
        call=boom,
    )
    assert res.status == "ERROR"
    assert res.provider == "anthropic"  # identity preserved on the degraded row (AC3)
    assert "unreachable" in (res.result_text or "")
    # Timing is captured even on failure — the benchmark row stays honest (AC4).
    assert res.requested_at and res.responded_at and res.latency_ms is not None


def test_run_extraction_truncates_an_overlong_error_message():
    """A pathological SDK exception must not bloat result_text/the log unbounded."""

    def boom():
        raise RuntimeError("x" * 5000)

    res = run_extraction(
        provider="openai",
        model_name="m",
        model_id="mid",
        model_full_id="mfid",
        task="extract_fields",
        call=boom,
    )
    assert res.status == "ERROR"
    assert len(res.result_text or "") <= 520  # bounded (+ the "…[truncated]" marker)
    assert (res.result_text or "").endswith("…[truncated]")


# ── VLM-only: image loading the adapters share (read bytes + media type) ──────


def test_load_image_returns_bytes_and_media_type(tmp_path):
    p = tmp_path / "label.png"
    p.write_bytes(b"\x89PNG\r\nfake-bytes")
    data, media_type = load_image(p)
    assert data == b"\x89PNG\r\nfake-bytes"
    assert media_type == "image/png"
    b64, media_type_b64 = load_image_b64(p)
    assert base64.standard_b64decode(b64) == data
    assert media_type_b64 == "image/png"


def test_media_type_for_maps_extensions_with_jpeg_fallback():
    assert media_type_for("front.jpg") == "image/jpeg"
    assert media_type_for("front.JPEG") == "image/jpeg"
    assert media_type_for("back.png") == "image/png"
    assert media_type_for("odd.heic") == "image/jpeg"  # unknown ⇒ JPEG fallback


def test_load_image_without_a_path_raises_value_error():
    """VLM-only extraction has nothing to read without an image."""
    with pytest.raises(ValueError, match="requires a label image"):
        load_image(None)


def test_run_extraction_degrades_when_the_image_is_missing():
    """A provider call that fails to load its image → ERROR row, never a raise (AC3)."""
    res = run_extraction(
        provider="openai",
        model_name="m",
        model_id="mid",
        model_full_id="mfid",
        task="extract_fields",
        call=lambda: (load_image(None), None, None),  # ValueError inside the call
    )
    assert res.status == "ERROR"
    assert "requires a label image" in (res.result_text or "")


# ── AC1: the real provider adapters construct offline (no SDK import, no socket) ──


def test_provider_adapters_construct_offline_and_satisfy_protocol():
    from app.adapters.llm.anthropic import AnthropicAdapter
    from app.adapters.llm.google import GoogleAdapter
    from app.adapters.llm.local_vlm import LocalVlmAdapter
    from app.adapters.llm.openai import OpenAiAdapter

    adapters = [
        OpenAiAdapter(model_id="m", api_key="k"),
        AnthropicAdapter(model_id="m", api_key="k"),
        GoogleAdapter(model_id="m", api_key="k"),
        LocalVlmAdapter(model_id="m"),
    ]
    for adapter in adapters:
        assert isinstance(adapter, ModelAdapter)
    # The local adapter is the zero-egress branch and needs no key.
    assert adapters[-1].provider == "local"


# ── AC2: factory gating — None paths construct NOTHING (the egress proof) ──────


def test_factory_returns_none_and_constructs_nothing_when_off(monkeypatch):
    """LLM_ENABLED=false / no provider / absent key ⇒ None, and ``_construct_adapter``
    is NEVER reached — so no provider module is imported and no client is built. This
    is what makes ``--network none`` + LLM_ENABLED=false a provable zero-egress run."""
    constructed: list = []
    monkeypatch.setattr(cfg, "_construct_adapter", lambda *a, **k: constructed.append(1))

    assert get_llm_adapter(Settings(llm_enabled=False)) is None
    assert get_llm_adapter(Settings(llm_enabled=True, llm_provider=None)) is None
    assert get_llm_adapter(Settings(llm_enabled=True, llm_provider="bogus")) is None
    # Enabled + supported provider but NO key ⇒ still off (absent key ⇒ layer off).
    assert get_llm_adapter(Settings(llm_enabled=True, llm_provider="openai")) is None

    assert constructed == []  # nothing was ever constructed on the off paths


def test_factory_constructs_adapter_when_enabled_and_keyed():
    adapter = get_llm_adapter(
        Settings(llm_enabled=True, llm_provider="openai", openai_api_key="sk-test")
    )
    assert adapter is not None and isinstance(adapter, ModelAdapter)
    assert adapter.provider == "openai"


def test_factory_local_provider_needs_no_key():
    adapter = get_llm_adapter(Settings(llm_enabled=True, llm_provider="local"))
    assert adapter is not None and adapter.provider == "local"


def test_factory_is_case_insensitive_and_trims_provider():
    adapter = get_llm_adapter(
        Settings(llm_enabled=True, llm_provider="  Anthropic ", anthropic_api_key="k")
    )
    assert adapter is not None and adapter.provider == "anthropic"


def test_factory_uses_configured_model_id_over_default():
    adapter = get_llm_adapter(
        Settings(
            llm_enabled=True,
            llm_provider="google",
            google_api_key="k",
            llm_model_id="gemini-custom",
        )
    )
    assert adapter is not None and adapter.model_id == "gemini-custom"


# ── AC1 egress-origin guard: off-host clients ONLY under app/adapters/llm/ ─────


def test_off_host_clients_live_only_under_adapters_llm():
    """A structural firewall guard: scan every app/ module and assert no off-host
    client is constructed outside ``app/adapters/llm/``. New code that adds an SDK
    client (or a raw httpx/requests/urllib/socket call) anywhere else is a finding
    (AC1, NFR-2)."""
    app_root = Path(__file__).resolve().parents[1] / "app"
    violations: list[str] = []
    for path in app_root.rglob("*.py"):
        rel = path.relative_to(app_root)
        if rel.parts[:2] == ("adapters", "llm"):
            continue  # the ONLY permitted home for an off-host client
        if _OFF_HOST_CLIENT.search(path.read_text(encoding="utf-8")):
            violations.append(str(rel))
    assert violations == [], f"off-host client constructed outside adapters/llm: {violations}"


def test_egress_guard_catches_bare_and_async_constructions():
    """The widened guard catches a BARE-import construction and async/other-lib
    clients — not just the dotted SDK forms — while ignoring the ``*Adapter`` wrappers."""
    for offender in (
        "OpenAI(api_key=k)",  # bare `from openai import OpenAI`
        "AsyncOpenAI()",
        "Anthropic(api_key=k)",
        "genai.Client()",
        "httpx.AsyncClient()",
        "requests.get(url)",
        "aiohttp.ClientSession()",
        "ClientSession()",  # bare `from aiohttp import ClientSession`
        "urllib.request.urlopen(url)",
        "urlopen(url)",  # bare `from urllib.request import urlopen`
        "socket.socket()",
        "s = socket()",  # bare `from socket import socket`
    ):
        assert _OFF_HOST_CLIENT.search(offender), offender
    # The factory's adapter-class constructions must NOT trip the guard.
    for safe in ("OpenAiAdapter(", "AnthropicAdapter(", "GoogleAdapter(", "LocalVlmAdapter("):
        assert not _OFF_HOST_CLIENT.search(safe), safe


def test_resolving_a_disabled_factory_imports_no_provider_sdk():
    """The web import path must stay SDK-free. Importing config + the adapter modules
    and resolving a DISABLED factory must not import any provider SDK — they are lazy
    inside ``_client_lazy``. (In the offline suite the SDKs are not even installed, so
    any eager import would also fail outright — the strongest possible egress proof.)"""
    import sys

    # Touch the adapter modules (factory would import these) — still no SDK import.
    import app.adapters.llm.anthropic  # noqa: F401
    import app.adapters.llm.google  # noqa: F401
    import app.adapters.llm.openai  # noqa: F401

    assert get_llm_adapter(Settings(llm_enabled=False)) is None
    for sdk in ("openai", "anthropic", "google.genai"):
        assert sdk not in sys.modules, f"{sdk} was imported without a real call"
