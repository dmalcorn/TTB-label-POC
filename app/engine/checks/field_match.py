"""The ``field_match`` check evaluator — three-band tolerance comparison (Story 3.3).

Plugs into the Story-3.2 dispatch seam (``{strategy: evaluator}`` registry in
``app/engine/checks/__init__.py``) under the ``field_match`` strategy, with NO
executor change. It compares the four matchable spirits fields — **brand name**,
**alcohol content**, **net contents**, **name/address** — pairing each APPLICATION
value (from ``submissions``) against the OCR/LLM-EXTRACTED value, writing one
``field_comparisons`` row, and returning a per-check :class:`CheckResult`.

**Why tolerance exists (the spine).** False rejects are the costliest error
(needless correction cycles). All comparisons route through the centralized
``app/normalize.py`` (contract #2) — that collapses incidental case/punctuation so
``"STONE'S THROW" == "Stone's Throw"`` ⇒ **PASS**. A genuine-but-soft difference
goes to **REVIEW** (defer to human); only a substantive mismatch **FAIL**s. When
unsure, the engine says REVIEW, never FAIL.

**Two outputs, distinctly.** ``field_comparisons.match_status``
(``MATCH/MISMATCH/MISSING/UNVERIFIABLE``) is the comparison OUTCOME the UI renders;
the returned ``CheckResult.verdict`` (``PASS/REVIEW/FAIL``) is the advisory engine
BAND. They are related but separate — never collapsed into one.

**Extracted-value source (provenance).** Preferred: a structured VLM extraction
(Story 2.5) — read from ``ctx.scratch["llm_extraction"]`` or the persisted ``OK``
``llm_results`` row, parsed per ``field_key``; the row's id is the
``source_llm_result_id``. Fallback (OCR-only): fuzzy-locate the value in the
submission's OCR text and record the contributing OCR row as ``source_ocr_result_id``.
Per-field extraction from a raw OCR blob is inherently heuristic — when a value
cannot be isolated, emit ``MISSING``/REVIEW (honest) rather than a fabricated match.

**VLM-only purity.** This evaluator never feeds OCR text into a model — the LLM
extraction it consumes was produced by the model reading the IMAGE (Story 2.5). OCR
text is used ONLY by this deterministic comparator.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from app import normalize, verdict
from app.db import repositories as repo
from app.engine.checks import CheckContext, CheckResult, CheckVerdict

if TYPE_CHECKING:
    from app.engine.rulesets import Check

logger = logging.getLogger(__name__)

# ── named, tunable thresholds (POC defaults — not regulation; flag for tuning) ──

# ABV tolerance: ±0.3 percentage-point. Research-Findings §1, cited in
# docs/regulatory-rules-distilled-spirits.md §3 ("±0.3-pt tolerance"). Decimal, not
# float (parse_numeric returns Decimal) — never float math on a regulated quantity.
ABV_TOLERANCE = Decimal("0.3")

# net_contents: standards of fill are DISCRETE (27 CFR 5.203) — exact-after-normalize
# (tolerance 0) so "750 mL" vs "750 ml" PASS but "750" vs "700" FAIL.
NET_CONTENTS_TOLERANCE = Decimal("0")

# Text near-miss floor: a normalized-but-not-equal similarity AT OR ABOVE this is a
# near-miss ⇒ REVIEW (the false-reject safety valve); below ⇒ substantive ⇒ FAIL.
REVIEW_FLOOR = 0.85

# Fields read from a label's free-form fine print where an OCR mismatch is inherently
# untrustworthy (the bottler name/address is abbreviated, reflowed, multi-line, and rarely
# OCRs to the filed string). A mismatch here NEVER advises FAIL — it defers to the human
# (REVIEW), never a false reject. The reviewer can still mark it failed on the card.
_REVIEW_ONLY_FIELDS = frozenset({"applicant_name_address"})

# OCR-confidence floor: an apparent match read from an OCR row below this confidence
# is forced to REVIEW — the extraction cannot be trusted (the cross-type-trap valve).
# Does NOT apply to LLM-sourced values.
OCR_CONFIDENCE_FLOOR = 0.50

# Per-tolerance lookup by field_key (numeric fields only). Keyed by the application
# field_key the matchable Check carries.
_NUMERIC_TOLERANCE: dict[str, Decimal] = {
    "alcohol_content": ABV_TOLERANCE,
    "net_contents": NET_CONTENTS_TOLERANCE,
}

# match_status / verdict are derived together but kept distinct (data vs advisory).
_MATCH = "MATCH"
_MISMATCH = "MISMATCH"
_MISSING = "MISSING"
_UNVERIFIABLE = "UNVERIFIABLE"


def field_match(check: Check, ctx: CheckContext) -> CheckResult:
    """Evaluate one matchable field: compare APPLICATION vs EXTRACTED, three-band.

    Resolves the application value (``getattr(ctx.submission, check.field_key)``) and
    the extracted value (LLM extraction preferred, OCR text fallback), normalizes
    BOTH via ``app/normalize.py`` (never inline), computes the band, writes one
    ``field_comparisons`` row, and returns the verdict + that row's id.
    """
    field_key = check.field_key
    if not field_key:
        # A field_match Check with no field_key cannot compare anything — honest REVIEW.
        return CheckResult(verdict=verdict.REVIEW, detail="field_match check has no field_key")

    submission_id = ctx.submission.id
    application_value = getattr(ctx.submission, field_key, None)

    # Resolve the extracted value + its provenance (LLM extraction first, OCR fallback).
    extracted_value, source_ocr_id, source_llm_id, ocr_confidence = _resolve_extracted(
        ctx, field_key
    )

    match_status, similarity, vdict, detail = _compare(
        field_key=field_key,
        application_value=application_value,
        extracted_value=extracted_value,
        ocr_confidence=ocr_confidence,
        is_llm_sourced=source_llm_id is not None,
    )

    # Name/address never hard-FAILs on an OCR mismatch — its fine print can't be matched
    # reliably, so defer to the human (REVIEW) instead of a false reject.
    if field_key in _REVIEW_ONLY_FIELDS and vdict == verdict.FAIL:
        vdict = verdict.REVIEW
        detail = f"{detail} — name/address OCR is unreliable; deferring to human review"

    comparison_id = repo.insert_field_comparison(
        ctx.conn,
        submission_id,
        field_key=field_key,
        application_value=application_value,
        extracted_value=extracted_value,
        match_status=match_status,
        similarity=similarity,
        source_ocr_result_id=source_ocr_id,
        source_llm_result_id=source_llm_id,
    )
    return CheckResult(verdict=vdict, detail=detail, field_comparison_id=comparison_id)


# ── extracted-value resolution (LLM extraction first, OCR text fallback) ──────


def _resolve_extracted(
    ctx: CheckContext, field_key: str
) -> tuple[str | None, int | None, int | None, float | None]:
    """Resolve ``(extracted_value, source_ocr_id, source_llm_id, ocr_confidence)``.

    Preference order (Task 2): a structured LLM extraction (scratch or the persisted
    ``OK`` ``llm_results`` row) parsed per ``field_key`` — provenance is the LLM row;
    else the OCR text fuzzy-locate — provenance is the most-confident OCR row. At most
    one source FK is ever set.
    """
    llm = _extracted_from_llm(ctx, field_key)
    if llm is not None:
        value, llm_id = llm
        return (value, None, llm_id, None)

    # OCR-only fallback. The contributing row's id + confidence travel with the value.
    source_ocr_id = repo.get_best_ocr_result_id(ctx.conn, ctx.submission.id)
    ocr_confidence = repo.get_best_ocr_confidence(ctx.conn, ctx.submission.id)
    extracted_value = _extracted_from_ocr_text(ctx.ocr_text, field_key)
    if extracted_value is None:
        # Could not isolate a value in the OCR text — honest MISSING, no fabricated FK.
        return (None, None, None, ocr_confidence)
    return (extracted_value, source_ocr_id, None, ocr_confidence)


def _extracted_from_llm(ctx: CheckContext, field_key: str) -> tuple[str, int] | None:
    """The LLM-extracted value for ``field_key`` + the source ``llm_results`` id.

    The extraction TEXT may come from the pipeline forward-seam
    (``ctx.scratch["llm_extraction"]``) or the persisted ``OK`` row; either way the
    persisted row supplies the provenance FK. ``None`` when there is no LLM extraction,
    it is not valid JSON, or it has no value for this field.
    """
    persisted = repo.get_latest_llm_extraction(ctx.conn, ctx.submission.id)
    raw_text = ctx.scratch.get("llm_extraction") if isinstance(ctx.scratch, dict) else None
    if raw_text is None and persisted is not None:
        raw_text = persisted[1]
    if raw_text is None or persisted is None:
        # No usable extraction OR no persisted row to attribute provenance to.
        return None

    value = _field_from_extraction_json(raw_text, field_key)
    if value is None:
        return None
    return (value, persisted[0])


def _field_from_extraction_json(raw_text: str, field_key: str) -> str | None:
    """Parse the VLM extraction JSON and pull ``field_key``'s value as a string.

    Tolerant: a non-JSON blob or a non-object payload yields ``None`` (degrade to the
    OCR fallback); a present-but-empty value yields ``None``; and a non-scalar value
    (list/dict/bool) yields ``None`` rather than a misleading stringified blob.
    """
    try:
        data = json.loads(raw_text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get(field_key)
    # Accept only a SCALAR field value. A model that emits a list/dict (or bool) for a
    # field is not a usable single value: stringifying it (e.g. ``['a', 'b']`` →
    # ``"['a', 'b']"``) would either substring-MATCH the application value by accident
    # (a misleading PASS) or compare against a Python-repr blob — both dishonest. We
    # degrade to the OCR fallback instead. ``bool`` is excluded explicitly (it is an
    # ``int`` subclass in Python); a numeric value is rendered without exponent noise so
    # a bare ABV ``45`` is not lost (the unit, if any, comes from the application side).
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    if isinstance(value, float):
        text = format(Decimal(str(value)).normalize(), "f").strip()
    else:
        text = str(value).strip()
    return text or None


def _extracted_from_ocr_text(ocr_text: str, field_key: str) -> str | None:
    """Heuristically isolate ``field_key``'s value from the joined OCR text.

    For NUMERIC fields, locate the first ``<number><unit>`` token (``parse_numeric``
    via the centralized normalizer) and return its surrounding raw line. For TEXT
    fields, there is no single value to extract without the application value to anchor
    on — the comparison side resolves it, so we return the whole OCR text as the
    candidate and let :func:`_compare` locate the application value within it. Returns
    ``None`` only when the OCR text is empty (⇒ MISSING)."""
    if not (ocr_text or "").strip():
        return None
    return ocr_text


# ── the three-band comparison ────────────────────────────────────────────────


def _compare(
    *,
    field_key: str,
    application_value: str | None,
    extracted_value: str | None,
    ocr_confidence: float | None,
    is_llm_sourced: bool,
) -> tuple[str, float | None, CheckVerdict, str]:
    """Compare one field and return ``(match_status, similarity, verdict, detail)``.

    Routes numeric fields to :func:`_compare_numeric` and text fields to
    :func:`_compare_text`; first guards the two "nothing to compare" cases (a missing
    application or extracted value ⇒ REVIEW, never FAIL on absence). Applies the
    low-OCR-confidence safety valve LAST (an apparent match from an untrustworthy OCR
    row is downgraded to REVIEW)."""
    if not _has_value(application_value) or application_value is None:
        # Nothing on the application side to compare — defer to the human.
        return (_UNVERIFIABLE, None, verdict.REVIEW, "application value missing")
    if not _has_value(extracted_value) or extracted_value is None:
        # Could not find the value on the label — MISSING, never a false-FAIL.
        return (_MISSING, None, verdict.REVIEW, "extracted value not found on label")

    if field_key in normalize.NUMERIC_FIELD_KEYS:
        match_status, similarity, vdict, detail = _compare_numeric(
            field_key, application_value, extracted_value
        )
    else:
        match_status, similarity, vdict, detail = _compare_text(
            field_key, application_value, extracted_value
        )

    # Low-confidence OCR safety valve: a below-floor OCR read is untrustworthy in BOTH
    # directions — an apparent PASS may be a mis-read coincidence, and an apparent FAIL
    # may be an OCR artifact rather than a real discrepancy. Either way we cannot trust
    # the extraction enough to advise PASS or FAIL, so we downgrade to REVIEW (the engine
    # spine: "when unsure, REVIEW, never FAIL" — softening a FAIL here also avoids a false
    # reject, the costliest error). REVIEW already defers, so it is left unchanged. Only
    # applies to OCR-sourced values (not LLM extraction, which read the image directly).
    if (
        not is_llm_sourced
        and vdict != verdict.REVIEW
        and ocr_confidence is not None
        and ocr_confidence < OCR_CONFIDENCE_FLOOR
    ):
        return (
            match_status,
            similarity,
            verdict.REVIEW,
            f"{detail} | low OCR confidence {ocr_confidence:.2f} < {OCR_CONFIDENCE_FLOOR}",
        )
    return (match_status, similarity, vdict, detail)


def _compare_text(
    field_key: str, application_value: str, extracted_value: str
) -> tuple[str, float | None, CheckVerdict, str]:
    """Three-band TEXT comparison via the centralized normalizer + difflib similarity.

    Normalized equality ⇒ MATCH/PASS (the "STONE'S THROW" case). Else, since the OCR
    candidate may be the whole label text, treat a normalized-substring hit as a
    located MATCH; otherwise score similarity against the most-similar window and band
    it: ``>= REVIEW_FLOOR`` ⇒ REVIEW (near-miss), below ⇒ FAIL (substantive)."""
    app_norm = normalize.normalize(application_value, field_key)
    ext_norm = normalize.normalize(extracted_value, field_key)

    if app_norm and app_norm == ext_norm:
        return (_MATCH, 1.0, verdict.PASS, f"normalized match: {app_norm!r}")

    # The OCR fallback hands us the whole label text; a clean substring hit means the
    # application value was found verbatim on the label ⇒ MATCH.
    if app_norm and app_norm in ext_norm:
        return (_MATCH, 1.0, verdict.PASS, f"located on label: {app_norm!r}")

    similarity = _best_similarity(app_norm, ext_norm)
    if similarity >= REVIEW_FLOOR:
        return (
            _MISMATCH,
            similarity,
            verdict.REVIEW,
            f"near-miss similarity {similarity:.3f} >= {REVIEW_FLOOR} — review",
        )
    return (
        _MISMATCH,
        similarity,
        verdict.FAIL,
        f"substantive mismatch: similarity {similarity:.3f} < {REVIEW_FLOOR}",
    )


def _best_similarity(app_norm: str, ext_norm: str) -> float:
    """The best normalized similarity of ``app_norm`` against ``ext_norm``.

    Compares against the full extracted string AND, when the extracted side is a
    multi-token blob (the OCR-text fallback), against a sliding word-window of the
    application value's length — so a brand name buried in a label blob still scores on
    its closest window, not diluted by the whole blob. (No per-line scan: the centralized
    ``normalize`` already collapsed every newline to a single space, so the extracted
    side is one line by the time it reaches here — the word-window is the live path.)"""
    if not app_norm or not ext_norm:
        return 0.0
    best = SequenceMatcher(None, app_norm, ext_norm).ratio()

    app_word_count = len(app_norm.split())
    candidates: list[str] = []
    words = ext_norm.split()
    if app_word_count and len(words) > app_word_count:
        candidates += [
            " ".join(words[i : i + app_word_count])
            for i in range(0, len(words) - app_word_count + 1)
        ]
    for cand in candidates:
        best = max(best, SequenceMatcher(None, app_norm, cand).ratio())
    return best


def _compare_numeric(
    field_key: str, application_value: str, extracted_value: str
) -> tuple[str, float | None, CheckVerdict, str]:
    """Numeric comparison: parse BOTH sides to ``(Decimal, unit)`` and apply tolerance.

    Same unit AND ``abs(app - ext) <= tolerance`` ⇒ MATCH/PASS; an unparseable
    extracted side ⇒ UNVERIFIABLE/REVIEW; otherwise (different unit or out-of-band) ⇒
    MISMATCH/FAIL (the "45% vs 40%" case). Uses ``Decimal`` throughout (no float drift).

    The extracted side may be a whole OCR blob carrying several ``<number><unit>``
    tokens (e.g. an ABV and a net-contents line). We anchor on the APPLICATION unit and
    pick the extracted token whose unit MATCHES it — so the net-contents check reads the
    ``750 ml`` token, not a stray ``45 %`` elsewhere. This mirrors the normalizer's
    "number and unit are one adjacent token" discipline (no cross-quantity pairing)."""
    app_num, app_unit = normalize.parse_numeric(application_value, field_key)
    tolerance = _NUMERIC_TOLERANCE.get(field_key, Decimal("0"))

    if app_num is None:
        # Application side unparseable — defer (we cannot anchor the comparison).
        return (_UNVERIFIABLE, None, verdict.REVIEW, f"application value unparseable: {field_key}")

    ext_nums = _extracted_numbers_for_unit(extracted_value, field_key, app_unit)
    if not ext_nums:
        # No SAME-UNIT number+unit token on the label. Either the label has no number
        # at all, or it carries only an unrelated quantity in a different unit (a stray
        # ``45 %`` while we sought ``ml``). We cannot honestly compare ⇒ UNVERIFIABLE/
        # REVIEW. We deliberately do NOT pair the application value with a wrong-unit
        # stray and FAIL it — that would be a false reject (the costliest error), and
        # the engine's spine is "when unsure, REVIEW, never FAIL".
        return (
            _UNVERIFIABLE,
            None,
            verdict.REVIEW,
            "no matching-unit number found on label",
        )

    # A label routinely OCRs several same-unit numbers — the stated value PLUS noise (a
    # stray ``0%`` from a smudge, a number echoed across stacked panels). The stated value
    # is CONFIRMED if it appears ANYWHERE, so pick the token CLOSEST to the application
    # value: if that closest token is within tolerance ⇒ MATCH (don't false-FAIL on a
    # spurious neighbour); else the closest IS the real discrepancy to report.
    closest = min(ext_nums, key=lambda n: abs(app_num - n))
    if abs(app_num - closest) <= tolerance:
        return (
            _MATCH,
            1.0,
            verdict.PASS,
            f"{app_num}{app_unit} ≈ {closest}{app_unit} (±{tolerance})",
        )
    # No same-unit token within tolerance — a SUBSTANTIVE numeric mismatch (the engineered
    # "6.7% vs 6.1%" case); report the closest as the deviation.
    return (
        _MISMATCH,
        0.0,
        verdict.FAIL,
        f"numeric mismatch: {app_num}{app_unit} vs {closest}{app_unit} (tol ±{tolerance})",
    )


def _extracted_numbers_for_unit(
    extracted_value: str, field_key: str, app_unit: str | None
) -> list[Decimal]:
    """ALL extracted numbers whose unit MATCHES ``app_unit`` (document order).

    Scans the extracted candidate via the centralized ``parse_all_numeric`` — EVERY
    ``<number><unit>`` token, not just the first, so a label that prints net contents and
    ABV on one line (``"750ML | 12.5% ALC./VOL."``) yields the ``%`` token even though the
    ``ml`` token comes first, AND a value echoed across stacked panels / shadowed by an OCR
    smudge (a stray ``0%``) is all surfaced for the caller to choose among. A token in a
    DIFFERENT unit is never returned: a stray cross-quantity number (e.g. a ``45 %`` ABV
    while we are matching ``net_contents`` in ``ml``) must NOT be paired with the
    application value and forced to a FAIL — that is a false reject. Empty list when no
    same-unit token is present, which the caller maps to UNVERIFIABLE/REVIEW."""
    out: list[Decimal] = []
    for line in extracted_value.splitlines() or [extracted_value]:
        for num, unit in normalize.parse_all_numeric(line, field_key):
            if unit == app_unit:
                out.append(num)
    return out


def _has_value(value: str | None) -> bool:
    """A value is present iff it is a non-empty, non-whitespace string."""
    return value is not None and bool(value.strip())
