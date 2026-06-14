"""The ``flag_only`` (positional) evaluator — flag-REVIEW checks (Story 3.7).

Plugs into the Story-3.2 dispatch seam (``{strategy: evaluator}`` registry in
``app/engine/checks/__init__.py``) under the ``positional`` strategy, with NO
executor change. It hosts checks that CANNOT be reliably auto-decided from a flat
photo — placement/co-location judgments OCR bounding boxes alone cannot guarantee —
by surfacing them as **REVIEW** with an explanatory note, never a guessed PASS/FAIL
(FR-17). Story 3.7 ships ONE handler: the same-field-of-vision spatial-inference
check (§5.63). (Other positional/flag-REVIEW checks — "separate and apart" placement,
severely degraded text — are future handlers on this same seam, not yet implemented.)

One evaluator hosts several flag-only checks, dispatched by ``check.check_key`` (the
``_HANDLERS`` registry, mirroring ``format_checks``), so the §4 CONDITIONAL flag-only
checks (sulfites, country-of-origin, coloring — Story 3.8) reuse this strategy with
their own DATA and a new handler — no executor change. Story 3.7 ships the
``same_field_of_vision`` handler.

**ALWAYS REVIEW (AC1).** The same-field-of-vision check NEVER emits PASS (it cannot
confirm co-location from a flattened OCR-text join) and NEVER emits FAIL (an element's
absence is a different check's concern — ``field_match``/``format_checks``; flag-only's
job is to defer the positional judgment, not duplicate a value FAIL). It reports each
trio element's INDIVIDUAL presence so the specialist sees what the engine COULD
confirm (presence) vs what it is deferring (co-location).

**NO LLM, by contract (AC2/AC4).** Flag-only is deterministic code (project-context
determinism taxonomy). This module never imports/constructs a model adapter and never
reads the LLM extraction — it reads ONLY ``ctx.ocr_text`` (the deterministic engine's
input) + ``ctx.submission`` application fields. That makes it toggle-independent and
keeps the OCR-only path zero-egress.

**CFR citation lives as DATA (AC2).** The §5.63 citation + the trio + the
co-location reason are imported from ``app/engine/rulesets/flag_only.py`` — never
inlined here. A grep for the CFR-citation literal inside this logic is a review
finding.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING

from app import normalize, verdict
from app.engine.checks import CheckContext, CheckResult
from app.engine.checks.format_checks import _find_abv_pct
from app.engine.rulesets import flag_only as data

if TYPE_CHECKING:
    from app.engine.rulesets import Check

# A keyed sub-evaluator: judges one flag-only Check against the submission's OCR text.
_Handler = Callable[[CheckContext, str], CheckResult]

# Outcome discriminator for the same-field-of-vision presence report (mirrors the
# Gov-Warning ``outcome`` discriminator so a UI story can render it structurally).
_OUTCOME_CO_LOCATION_DEFERRED = "co_location_deferred"


def flag_only(check: Check, ctx: CheckContext) -> CheckResult:
    """Dispatch one flag-only Check to its keyed sub-evaluator (deterministic, no LLM).

    Routes on ``check.check_key``; an unknown key degrades to an honest REVIEW
    (finalize-don't-abort, FR-9) rather than raising. Reads ONLY ``ctx.ocr_text`` +
    the submission's application fields — never a model. Writes NO ``field_comparisons``
    row (a positional/placement judgment, not an application-field VALUE comparison).
    """
    ocr_text = ctx.ocr_text or ""
    handler = _HANDLERS.get(check.check_key)
    if handler is None:
        # Unknown/unhandled flag-only check — defer to the human, never a raise.
        return CheckResult(
            verdict=verdict.REVIEW,
            detail=f"flag-only check {check.check_key!r}: deferred to specialist",
        )
    return handler(ctx, ocr_text)


# ── same_field_of_vision — §5.63 flag-REVIEW (AC1, AC2, AC3) ──────────────────


def _same_field_of_vision(ctx: CheckContext, ocr_text: str) -> CheckResult:
    """Report each trio element's individual presence; ALWAYS defer co-location (REVIEW).

    For each field_key in ``data.SAME_FIELD_OF_VISION_FIELDS``, determine individual
    presence DETERMINISTICALLY (the application value located in the OCR text via the
    centralized ``normalize``; ``alcohol_content`` also confirmable by an ABV %-token).
    The verdict is ALWAYS REVIEW — even all-three-present does not upgrade to PASS,
    because co-location across faces is unrecoverable from a flattened OCR-text join
    (AC3). The §5.63 citation + the reason travel from the DATA module.
    """
    elements = {
        field_key: _element_present(ctx, ocr_text, field_key)
        for field_key in data.SAME_FIELD_OF_VISION_FIELDS
    }
    payload = {
        "outcome": _OUTCOME_CO_LOCATION_DEFERRED,
        "elements": elements,
        "reason": data.SAME_FIELD_OF_VISION_REASON,
        "cfr_citation": data.CFR_CITATION,
    }
    return CheckResult(verdict=verdict.REVIEW, detail=json.dumps(payload))


def _element_present(ctx: CheckContext, ocr_text: str, field_key: str) -> bool:
    """Whether a trio element is individually present on the label, deterministically.

    ``alcohol_content`` (a numeric statement field) is detected by the cue-aware
    ``format_checks._find_abv_pct`` — an ABV ``%``-token sitting near an alcohol cue
    word (alc/vol/abv/alcohol), reused so flag-only and the ABV format check agree on
    what counts as an ABV statement and a stray promotional/nutrition ``%`` ("30% off",
    "100% natural") is NOT mistaken for one. The TEXT fields (brand / class-type) use
    the centralized ``normalize`` substring containment ("STONE'S THROW" ≡ "Stone's
    Throw"). This is informational only; it never changes the REVIEW verdict.
    """
    if field_key == "alcohol_content":
        # A numeric field: the whole-blob ``normalize`` collapse is a single-token
        # extractor (wrong for a substring haystack), so detect the ABV STATEMENT on
        # the label directly via the cue-aware probe — independent of the app value.
        return _find_abv_pct(ocr_text) is not None
    app_value = getattr(ctx.submission, field_key, None)
    return _value_in_ocr(app_value, ocr_text, field_key)


def _value_in_ocr(app_value: str | None, ocr_text: str, field_key: str) -> bool:
    """Whether the normalized application value appears in the normalized OCR text.

    Routes BOTH sides through the centralized ``app/normalize.py`` (never inline) and
    tests normalized-substring membership — the same presence discipline
    ``field_match._compare_text`` uses for a value buried in a label blob. Used for the
    TEXT trio fields (brand / class-type); ``alcohol_content`` uses the cue-aware ABV
    probe instead (the numeric branch of ``normalize`` collapses the blob to one token).
    """
    if app_value is None or not app_value.strip():
        return False
    app_norm = normalize.normalize(app_value, field_key)
    ocr_norm = normalize.normalize(ocr_text, field_key)
    return bool(app_norm) and app_norm in ocr_norm


# ── the keyed sub-evaluator registry (dispatched by check_key) ───────────────
# Story 3.7 ships the same-field-of-vision handler; Story 3.8 adds the §4 conditional
# flag-only handlers (sulfites/country-of-origin/coloring) here with their own DATA.

_HANDLERS: dict[str, _Handler] = {
    "same_field_of_vision": _same_field_of_vision,
}
