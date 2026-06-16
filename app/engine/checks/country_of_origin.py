"""The ``country_of_origin`` evaluator — the "Country of origin" comparison card.

Country of origin is a CONDITIONAL element: required for IMPORTED products (the label
must state it), not required for DOMESTIC ones. We **trust the application's
``source_of_product`` flag** to decide which branch applies — never re-deriving it from
the value (so there is no list-of-50-states logic here):

  - **DOMESTIC** → no country-of-origin statement is required. The card shows the filed
    origin (e.g. "Massachusetts") on the application side and **"Not imported"** on the
    label side, and **auto-PASSES** — we do NOT hunt for the state on the label.
  - **IMPORTED** → field-match the filed country (e.g. "Scotland") against the label OCR
    (reusing the Story-3.3 comparison): located → PASS; missing/garbled → REVIEW (defer to
    the human, never a false reject — OCR on imported artwork is unreliable).

Either branch writes ONE ``field_comparisons`` row, so it renders as a normal comparison
card (with the Pass/Fail control) exactly like brand / ABV. Deterministic; no LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app import verdict
from app.db import repositories as repo
from app.engine.checks import CheckContext, CheckResult
from app.engine.checks.field_match import _compare, _resolve_extracted

if TYPE_CHECKING:
    from app.engine.rulesets import Check

_DOMESTIC_ONLABEL = "Not imported"


def country_of_origin(check: Check, ctx: CheckContext) -> CheckResult:
    field_key = check.field_key or "country_of_origin"
    application_value = getattr(ctx.submission, field_key, None)
    source = (ctx.submission.source_of_product or "").upper()

    if source == "DOMESTIC":
        # No country-of-origin statement required — auto-PASS; the label side reads
        # "Not imported" (we never look for the state word on the artwork).
        comparison_id = repo.insert_field_comparison(
            ctx.conn,
            ctx.submission.id,
            field_key=field_key,
            application_value=application_value,
            extracted_value=_DOMESTIC_ONLABEL,
            match_status="MATCH",
            similarity=1.0,
        )
        return CheckResult(
            verdict=verdict.PASS,
            detail="domestic product — no country-of-origin statement required (auto-pass)",
            field_comparison_id=comparison_id,
        )

    # IMPORTED (or an unknown/blank source): field-match the country against the label.
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
    # OCR on imported labels is unreliable; a missing/garbled country statement defers to
    # the human (REVIEW) rather than a false reject (mirrors the name/address policy).
    if vdict == verdict.FAIL:
        vdict = verdict.REVIEW
        detail = f"{detail} — country-of-origin OCR is unreliable; deferring to human review"

    comparison_id = repo.insert_field_comparison(
        ctx.conn,
        ctx.submission.id,
        field_key=field_key,
        application_value=application_value,
        extracted_value=extracted_value,
        match_status=match_status,
        similarity=similarity,
        source_ocr_result_id=source_ocr_id,
        source_llm_result_id=source_llm_id,
    )
    return CheckResult(verdict=vdict, detail=detail, field_comparison_id=comparison_id)
