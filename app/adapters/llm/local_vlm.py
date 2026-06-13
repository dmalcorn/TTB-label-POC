"""Local VLM adapter → :class:`~app.contracts.LlmResult` (Story 2.5, optional branch).

The **zero-egress** model option: a locally-hosted, OpenAI-compatible inference
server (Ollama / vLLM / LM Studio on ``localhost``). Classified ``local`` in the
outbound-calls inventory — it never leaves the host — so the factory builds it even
without an API key (a localhost server needs none).

Implementation reuses :class:`~app.adapters.llm.openai.OpenAiAdapter` (the same
Chat Completions **vision** wire format — the local server reads the label image
exactly as the cloud path does) with the ``base_url`` pinned to a localhost endpoint
and a placeholder key; only ``provider`` differs, so a ``local`` row is honestly
labelled ``provider='local'`` for the benchmark. This is the zero-egress VLM-only
extraction. Weights are pinned/shipped offline like the OCR engines — no runtime
download.
"""

from __future__ import annotations

from app.adapters.llm.openai import OpenAiAdapter

# A local OpenAI-compatible server's default endpoint; overridable via LLM_BASE_URL.
DEFAULT_LOCAL_BASE_URL = "http://localhost:11434/v1"


class LocalVlmAdapter(OpenAiAdapter):
    """A localhost OpenAI-compatible model — the zero-egress provider branch."""

    provider: str = "local"

    def __init__(
        self,
        *,
        model_id: str,
        base_url: str | None = None,
        model_name: str | None = None,
        model_full_id: str | None = None,
    ) -> None:
        super().__init__(
            model_id=model_id,
            # localhost servers ignore the key, but the SDK requires a non-empty one.
            api_key="local",
            base_url=base_url or DEFAULT_LOCAL_BASE_URL,
            model_name=model_name,
            model_full_id=model_full_id,
        )
