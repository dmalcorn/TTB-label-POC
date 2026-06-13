"""Shared image-loading + timing / error-wrapping for the model adapters (Story 2.5).

**VLM-only extraction.** The model reads the label IMAGE directly and produces its
own extraction — it is **never** handed OCR text or any other engine's output. This
keeps the OCR-vs-model benchmark a true head-to-head (FR-12, FR-21/FR-22) and makes
the model a genuine fallback when OCR confidence is poor. The OCR text is the
deterministic compliance engine's input (Epic 3), never the model's.

Every concrete provider adapter (``openai`` / ``google`` / ``anthropic`` /
``local_vlm``) delegates to :func:`run_extraction`, which owns the parts that must
be identical across providers and that AC1/AC3/AC4 pin:

- stamps ``requested_at`` **before** and ``responded_at`` **after** the call
  (UTC ISO-8601) and derives ``latency_ms`` — the procurement/cost basis (AC4);
- on **any** exception/timeout returns an ``ERROR``-status :class:`LlmResult`
  carrying the model identity + ``provider`` + a bounded error string in
  ``result_text`` — it **never raises into the pipeline stage** (AC3, mirrors the
  OCR self-guard);
- never sets ``total_tokens`` — that is the DB-generated / derived-property sum.

The provider-specific SDK call is the only thing each adapter supplies (the
``call`` thunk); :func:`load_image` gives every adapter one way to read the image
bytes + media type. This module imports **no** provider SDK — keeping the import
path of the web app free of any networked client (the egress boundary, AC1).

Secrets posture: only the exception's type + a **truncated** message is recorded;
the prompt and image bytes are never logged. [project-context: secrets never logged]
"""

from __future__ import annotations

import base64
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app.contracts import LlmResult

logger = logging.getLogger(__name__)

# What a provider adapter's SDK call returns: (result_text, prompt_tokens, completion_tokens).
ProviderCall = Callable[[], "tuple[str | None, int | None, int | None]"]

# Cap on the error text we persist/return on the degrade path — keep the row honest
# and queryable without letting an arbitrarily long SDK exception (which can echo
# request context) bloat the column or the log. [project-context: secrets never logged]
_MAX_ERROR_TEXT = 500

# Image extension → media type for the data the VLM reads. Defaults to JPEG for an
# unknown suffix (the seeded fixtures are JP/PNG); add entries as fixture types grow.
_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def utc_now_iso() -> str:
    """Current instant as a UTC ISO-8601 string (the ``_at`` column format)."""
    return datetime.now(UTC).isoformat()


def media_type_for(image_path: str | Path) -> str:
    """The image media type for ``image_path`` from its extension (JPEG fallback)."""
    return _MEDIA_TYPES.get(Path(image_path).suffix.lower(), "image/jpeg")


def load_image(image_path: str | Path | None) -> tuple[bytes, str]:
    """Read the label image as ``(raw_bytes, media_type)`` for the VLM call.

    Raises ``ValueError`` when no image is supplied (VLM-only extraction has nothing
    to read) and lets a missing/unreadable file raise ``OSError`` — both are caught
    by :func:`run_extraction` and become an honest ``ERROR`` row, never an abort.
    """
    if image_path is None:
        raise ValueError("VLM extraction requires a label image; none was provided")
    path = Path(image_path)
    return path.read_bytes(), media_type_for(path)


def load_image_b64(image_path: str | Path | None) -> tuple[str, str]:
    """Read the label image as ``(base64_text, media_type)`` (the OpenAI/Anthropic
    wire form). Same error posture as :func:`load_image`."""
    data, media_type = load_image(image_path)
    return base64.standard_b64encode(data).decode("ascii"), media_type


def _truncate(text: str) -> str:
    """Bound a captured error string (keep the row/log honest, not unbounded)."""
    return text if len(text) <= _MAX_ERROR_TEXT else text[:_MAX_ERROR_TEXT] + "…[truncated]"


def run_extraction(
    *,
    provider: str,
    model_name: str,
    model_id: str,
    model_full_id: str,
    task: str,
    call: ProviderCall,
) -> LlmResult:
    """Run one provider ``call`` with uniform timing, identity, and error capture.

    Returns an ``OK`` :class:`LlmResult` on success or an ``ERROR`` one on any
    failure — never raises. Both carry the full model identity and timing so even a
    degraded call is an honest, queryable row (AC3/AC4).
    """
    requested_at = utc_now_iso()
    start = time.monotonic()
    try:
        result_text, prompt_tokens, completion_tokens = call()
        latency_ms = int((time.monotonic() - start) * 1000)
        return LlmResult(
            model_name=model_name,
            model_id=model_id,
            model_full_id=model_full_id,
            provider=provider,
            task=task,
            result_text=result_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,  # total_tokens is derived — never set
            latency_ms=latency_ms,
            requested_at=requested_at,
            responded_at=utc_now_iso(),
            status="OK",
        )
    except Exception as exc:  # noqa: BLE001 — degrade to ERROR, never raise into the stage
        latency_ms = int((time.monotonic() - start) * 1000)
        # Log the type only (no message/traceback body) so a prompt/key echoed in an
        # SDK exception never reaches the logs; the bounded message is captured below.
        logger.error("LLM provider %s call failed: %s", provider, type(exc).__name__)
        return LlmResult(
            model_name=model_name,
            model_id=model_id,
            model_full_id=model_full_id,
            provider=provider,
            task=task,
            result_text=_truncate(f"{type(exc).__name__}: {exc}"),  # bounded; key never echoed
            latency_ms=latency_ms,
            requested_at=requested_at,
            responded_at=utc_now_iso(),
            status="ERROR",
        )
