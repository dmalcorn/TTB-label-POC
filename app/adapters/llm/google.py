"""Google Gemini model adapter → :class:`~app.contracts.LlmResult` (Story 2.5, AC1/AC4).

A concrete :class:`~app.adapters.llm.base.ModelAdapter` and one of the only off-host
call sites (``models-internal-endpoint``). ``google.genai`` is imported **lazily
inside** :meth:`_client_lazy`; the client is built only on the first real call, so
construction is socket-free (the egress proof, AC2). ``LLM_BASE_URL`` is passed via
``HttpOptions(base_url=...)`` so the POC's ``generativelanguage.googleapis.com`` swaps
for an internal endpoint with no code change.

**VLM-only extraction.** ``run`` sends the label IMAGE (a ``types.Part.from_bytes``
inline part) plus an instruction prompt — never OCR text — so the model's reading is
its own (FR-12, FR-21/FR-22).
"""

from __future__ import annotations

from typing import Any

from app.adapters.llm._common import ImageArg, as_image_list, load_image, run_extraction
from app.contracts import LlmResult

DEFAULT_TASK = "extract_fields"


class GoogleAdapter:
    """Gemini via the ``google-genai`` SDK — a concrete ``ModelAdapter``.

    Token usage is read from ``response.usage_metadata`` (``prompt_token_count`` /
    ``candidates_token_count``) into ``prompt_tokens`` / ``completion_tokens`` (AC4).
    """

    provider: str = "google"

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
            from google import genai  # lazy — the only place the off-host client is created
            from google.genai import types

            http_options = types.HttpOptions(base_url=self._base_url) if self._base_url else None
            self._client = genai.Client(api_key=self._api_key, http_options=http_options)
        return self._client

    def _call(
        self, prompt: str, image_path: ImageArg | None
    ) -> tuple[str | None, int | None, int | None]:
        from google.genai import types

        paths = as_image_list(image_path)
        data, media_type = load_image(paths[0] if paths else None)  # first image; raises if none
        client = self._client_lazy()
        image_part = types.Part.from_bytes(data=data, mime_type=media_type)
        response = client.models.generate_content(
            model=self.model_id, contents=[prompt, image_part]
        )
        text = getattr(response, "text", None)
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
        completion_tokens = getattr(usage, "candidates_token_count", None) if usage else None
        return text, prompt_tokens, completion_tokens

    def run(self, task: str, prompt: str, *, image_path: ImageArg | None = None) -> LlmResult:
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
