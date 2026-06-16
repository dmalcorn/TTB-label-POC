"""OpenAI model adapter → :class:`~app.contracts.LlmResult` (Story 2.5, AC1/AC4).

A concrete :class:`~app.adapters.llm.base.ModelAdapter`. One of the **only**
modules in the app permitted to open an off-host connection (classified
``models-internal-endpoint``); the pipeline depends on the protocol, never on this
class (AR-4) — adding a provider is a new adapter file, no stage/schema change.

**VLM-only extraction.** ``run`` sends the label IMAGE (as a base64 data URI on the
Chat Completions vision input) plus an instruction prompt — it is **never** handed
OCR text. The model produces its own independent reading of the label, which is what
makes the OCR-vs-model benchmark a true head-to-head (FR-12, FR-21/FR-22).

``openai`` is imported **lazily inside** :meth:`_client_lazy`, never at module load,
and the SDK client is constructed **only on the first real call**. So importing this
module — or having the factory hold the adapter — never imports the SDK and never
opens a socket; the egress proof (``--network none`` + ``LLM_ENABLED=false``)
depends on the factory simply not constructing this adapter at all (AC2).

``LLM_BASE_URL`` is passed straight to the client: production points it at an
in-firewall endpoint, the POC at ``api.openai.com`` — a config swap, no code change.
"""

from __future__ import annotations

from typing import Any

from app.adapters.llm._common import ImageArg, load_images_b64, run_extraction
from app.contracts import LlmResult

DEFAULT_TASK = "extract_fields"
_MAX_TOKENS = 1024


class OpenAiAdapter:
    """OpenAI Chat Completions (vision) via the ``openai`` SDK — a concrete
    ``ModelAdapter``.

    Construction is socket-free (the SDK is imported and the client built lazily on
    first :meth:`run`), so the adapter is safe to hold without any network. The
    Chat Completions endpoint is used because it honors ``base_url`` for the
    internal-endpoint swap, accepts image input, and returns per-call token usage
    (AC4).
    """

    provider: str = "openai"

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
        """Build (once) and return the SDK client. The lazy import keeps the module
        import path SDK-free; the client is only ever constructed when a call runs."""
        if self._client is None:
            import openai  # lazy — the only place the off-host client is created

            self._client = openai.OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def _call(
        self, prompt: str, image_path: ImageArg | None
    ) -> tuple[str | None, int | None, int | None]:
        images = load_images_b64(image_path)  # raises (→ ERROR row) if none supplied
        client = self._client_lazy()
        # One user turn: the instruction, then EVERY label image (front, back, neck, strip)
        # so the model reads the whole product in a single call.
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content += [
            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}}
            for b64, media_type in images
        ]
        response = client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": content}],
            max_tokens=_MAX_TOKENS,
            # JSON mode: the model must return a syntactically valid JSON object, so the
            # per-field extraction parses deterministically (the prompt names the exact keys).
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content if response.choices else None
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        return text, prompt_tokens, completion_tokens

    def run(self, task: str, prompt: str, *, image_path: ImageArg | None = None) -> LlmResult:
        """Run one VLM extraction over the label image(s) → :class:`LlmResult`. Never
        raises (AC3): timing and error capture live in :func:`run_extraction`. A
        missing/absent ``image_path`` degrades to an ``ERROR`` row, not an abort."""
        return run_extraction(
            provider=self.provider,
            model_name=self.model_name,
            model_id=self.model_id,
            model_full_id=self.model_full_id,
            task=task or DEFAULT_TASK,
            call=lambda: self._call(prompt, image_path),
        )
