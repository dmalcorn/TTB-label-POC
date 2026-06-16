"""Model adapter protocol → :class:`~app.contracts.LlmResult`.

The *same* uniform-adapter pattern as OCR, applied to models (architecture
Adapter boundary, D6). ``engine/`` and ``pipeline/`` depend on this protocol,
never on a concrete provider. Adding a model = a new module implementing
:class:`ModelAdapter` — no schema or caller change (FR-12, AR-4). The only
off-host calls in the whole app originate in the concrete provider adapters
(``openai``/``google``/``anthropic``), classified ``models-internal-endpoint``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.adapters.llm._common import ImageArg
from app.contracts import LlmResult


@runtime_checkable
class ModelAdapter(Protocol):
    """Uniform interface every model adapter implements.

    The identity attributes populate ``LlmResult``'s model-identification fields.
    ``run`` performs one model call over one OR many label images (``image_path``
    accepts a single path or a sequence) and returns the centralized
    :class:`LlmResult` shape.
    """

    model_name: str
    model_id: str
    model_full_id: str
    provider: str

    def run(self, task: str, prompt: str, *, image_path: ImageArg | None = None) -> LlmResult: ...
