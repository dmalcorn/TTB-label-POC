"""OCR engine adapter protocol → :class:`~app.contracts.OcrResult`.

``engine/`` and ``pipeline/`` depend on this protocol, never on a concrete
engine (architecture Adapter boundary, D5). Adding an engine = a new module
implementing :class:`OcrEngine` — no schema or caller change (FR-11, AR-4).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.contracts import OcrResult


@runtime_checkable
class OcrEngine(Protocol):
    """Uniform interface every OCR engine implements.

    ``name`` / ``version`` populate ``OcrResult.engine_name`` /
    ``engine_version``. ``extract`` runs the engine on one image and returns the
    centralized :class:`OcrResult` shape.
    """

    name: str
    version: str

    def extract(self, image_path: str | Path, *, ran_on_cpu: bool = True) -> OcrResult: ...
