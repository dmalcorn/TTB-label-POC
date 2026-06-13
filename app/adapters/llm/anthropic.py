"""Anthropic model adapter → :class:`~app.contracts.LlmResult` (Story 2.5, AC1/AC4).

A concrete :class:`~app.adapters.llm.base.ModelAdapter` and one of the only
off-host call sites (``models-internal-endpoint``). ``anthropic`` is imported
**lazily inside** :meth:`_client_lazy` and the client is built only on the first
real call — construction is socket-free, so the factory can hold the adapter with
zero network (the egress proof, AC2). ``LLM_BASE_URL`` swaps the POC's
``api.anthropic.com`` for an internal endpoint with no code change.

**VLM-only extraction.** ``run`` sends the label IMAGE (a base64 image content
block) plus an instruction prompt — never OCR text — so the model's reading is its
own (FR-12, FR-21/FR-22).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.adapters.llm._common import load_image_b64, run_extraction
from app.contracts import LlmResult

DEFAULT_TASK = "extract_fields"
_MAX_TOKENS = 1024


class AnthropicAdapter:
    """Anthropic Messages via the ``anthropic`` SDK — a concrete ``ModelAdapter``.

    Token usage is read from ``response.usage`` (``input_tokens`` / ``output_tokens``)
    into the contract's ``prompt_tokens`` / ``completion_tokens`` (AC4).
    """

    provider: str = "anthropic"

    def __init__(
        self,
        *,
        model_id: str,
        api_key: str | None,
        base_url: str | None = None,
        model_name: str | None = None,
        model_full_id: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.model_name = model_name or model_id
        self.model_full_id = model_full_id or model_id
        self._api_key = api_key
        self._base_url = base_url
        self._client: Any = None

    def _client_lazy(self) -> Any:
        if self._client is None:
            import anthropic  # lazy — the only place the off-host client is created

            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def _call(
        self, prompt: str, image_path: str | Path | None
    ) -> tuple[str | None, int | None, int | None]:
        b64, media_type = load_image_b64(image_path)  # raises (→ ERROR row) if absent
        client = self._client_lazy()
        response = client.messages.create(
            model=self.model_id,
            max_tokens=_MAX_TOKENS,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        # Messages return a list of content blocks; concatenate the text blocks.
        text = (
            "".join(
                getattr(block, "text", "")
                for block in getattr(response, "content", [])
                if getattr(block, "type", None) == "text"
            )
            or None
        )
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "input_tokens", None) if usage else None
        completion_tokens = getattr(usage, "output_tokens", None) if usage else None
        return text, prompt_tokens, completion_tokens

    def run(self, task: str, prompt: str, *, image_path: str | Path | None = None) -> LlmResult:
        """Run one VLM extraction over the label image → :class:`LlmResult`. Never
        raises (AC3); a missing/absent ``image_path`` degrades to an ``ERROR`` row."""
        return run_extraction(
            provider=self.provider,
            model_name=self.model_name,
            model_id=self.model_id,
            model_full_id=self.model_full_id,
            task=task or DEFAULT_TASK,
            call=lambda: self._call(prompt, image_path),
        )
