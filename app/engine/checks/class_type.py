"""The ``class_type`` check evaluator — HYBRID: rules first, VLM capped at REVIEW (Story 3.6).

Plugs into the Story-3.2 dispatch seam (``{strategy: evaluator}`` registry in
``app/engine/checks/__init__.py``) under the ``class_type`` strategy, with NO
executor change. The existing ``class_type_designation`` Check row in
``rulesets/distilled_spirits.py`` (``check_type="HYBRID"``, §5.141) already routes
here; this module makes that row real.

**The hybrid contract — deterministic FIRST, the model LAST and capped.** This is the
ONE place in the whole POC where an LLM touches a verdict, so the guardrails are
strict (project-context "Determinism taxonomy"):

  1. **Conflict (AC3) — deterministic FAIL.** Two DIFFERENT recognized base
     class/type designations across a submission's labels (e.g. bourbon vs vodka) is
     an objective rule violation → **FAIL**, both values cited. No model.
  2. **Recognized (AC1) — deterministic PASS.** A designation matching the BAM-Ch.4
     "allowed designations" catalog (carried as DATA in
     ``rulesets/class_type.py``) → **PASS**, with **no model constructed or called**.
  3. **Ambiguous (AC2/AC4) — escalate or defer.** Neither a conflict nor recognized:
     if the model layer is ON (``get_llm_adapter`` resolves an adapter) escalate to a
     **VLM** handed the label **IMAGE** (VLM-only — never the OCR text) and **cap the
     result at REVIEW** (an LLM opinion alone never yields FAIL); if the model layer is
     OFF, degrade to rules-only **REVIEW** (defer to the human).

**VLM-only — image in, never OCR text (hard rule).** When the model is called its
ONLY input is the primary label image + a fixed, OCR-free instruction. ``ctx.ocr_text``
is NEVER passed to the model — OCR text feeds ONLY the deterministic conflict/
recognition logic here. (project-context: "any code that passes OCR output into a model
call is a finding".)

**Capped at REVIEW.** Only the DETERMINISTIC paths emit PASS (recognized) or FAIL
(conflict). The model path emits at most REVIEW — never PASS, never FAIL.

**No ``field_comparisons`` row** (like the Gov Warning + format checks): this is a
validity/conflict judgment against the catalog + a cross-label rule, not an app↔OCR
field-value comparison. Provenance travels in ``CheckResult.detail`` (+ ``model_id`` on
the escalated path, which the executor folds into the detail); ``run_checks`` writes the
single ``checklist_items`` row.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app import normalize, verdict
from app.config import get_llm_adapter, get_settings
from app.db import repositories as repo
from app.engine.checks import CheckContext, CheckResult
from app.engine.checks.field_match import _extracted_from_llm
from app.engine.rulesets import class_type as data

if TYPE_CHECKING:
    from pathlib import Path

    from app.engine.rulesets import Check

logger = logging.getLogger(__name__)

# Card display only: map the HYBRID verdict to a field_comparisons match_status so the
# class/type card reads like the other comparison cards (PASS→MATCH, FAIL→MISMATCH, else
# UNVERIFIABLE). Typed dict[str, str] so the full verdict domain (incl. NA) is a valid key.
_CARD_STATUS_FOR_VERDICT: dict[str, str] = {verdict.PASS: "MATCH", verdict.FAIL: "MISMATCH"}

# The VLM escalation instruction. The model reads the IMAGE and returns its own
# reading — there is NO OCR text in this prompt (VLM-only). The check never promotes
# the model's opinion above REVIEW, so the prompt only needs an honest assessment.
_PROMPT = (
    "You are reviewing a US TTB distilled-spirits label. Look at the attached label "
    "image and assess whether the class/type designation shown is a valid, recognized "
    "class/type (e.g. a whisky/bourbon/rye, gin, brandy, rum, tequila, vodka, or "
    "liqueur designation, or a valid statement of composition). Describe what you see; "
    "use only what the image shows."
)


def class_type(check: Check, ctx: CheckContext) -> CheckResult:
    """Evaluate the class/type designation (HYBRID) AND write a comparison row so it renders
    as a card like the other fields.

    The validity JUDGMENT is unchanged (:func:`_judge` — conflict→FAIL, recognized→PASS,
    else VLM-escalate capped at REVIEW; OCR feeds the deterministic logic only, never a
    model). On top of that we persist one ``field_comparisons`` row — declared designation
    vs the label OCR — so the Story-4.4 card renders (``field_cards`` keys on
    ``field_comparison_id``, NOT on check_type), giving spirits a class/type card while
    keeping the HYBRID/VLM path intact. The card's ``match_status`` mirrors the verdict.
    """
    ocr_text = ctx.ocr_text or ""
    designation = ctx.submission.class_type_designation or ""
    result = _judge(ctx, designation, ocr_text)
    field_key = check.field_key or "class_type_designation"
    # The HYBRID verdict is holistic (catalog recognition + cross-label conflict), so the
    # card's match_status mirrors it for every source row. We write one row per source so
    # the card shows what OCR read AND what the AI read for the class/type (the AI row was
    # missing before). The OCR row carries the whole label blob (the card isolates the
    # snippet); the AI row carries the model's structured class/type reading.
    status = _CARD_STATUS_FOR_VERDICT.get(result.verdict, "UNVERIFIABLE")
    ocr_comparison_id = repo.insert_field_comparison(
        ctx.conn,
        ctx.submission.id,
        field_key=field_key,
        application_value=designation or None,
        extracted_value=ocr_text or None,
        match_status=status,
        source_ocr_result_id=repo.get_best_ocr_result_id(ctx.conn, ctx.submission.id),
    )
    primary_id = ocr_comparison_id
    ai = _extracted_from_llm(ctx, field_key)
    if ai is not None:
        ai_value, llm_id = ai
        primary_id = repo.insert_field_comparison(
            ctx.conn,
            ctx.submission.id,
            field_key=field_key,
            application_value=designation or None,
            extracted_value=ai_value,
            match_status=status,
            source_llm_result_id=llm_id,
        )  # AI-preferred for the checklist FK; the card gathers both rows by field_key
    return CheckResult(
        verdict=result.verdict,
        detail=result.detail,
        field_comparison_id=primary_id,
        model_id=getattr(result, "model_id", None),
    )


def _judge(ctx: CheckContext, designation: str, ocr_text: str) -> CheckResult:
    """The class/type validity verdict (no persistence): conflict→FAIL, recognized→PASS,
    else VLM-escalate/REVIEW. Deterministic FIRST (AC1/AC3); the VLM LAST + capped at REVIEW
    (AC2/AC4). Reads ``ctx.ocr_text`` for the deterministic logic ONLY — never to a model."""

    # (1) Cross-label conflict (AC3) — deterministic FAIL FIRST. The label OCR carries a
    # mutually-exclusive base class (e.g. vodka) that contradicts the DECLARED
    # designation's base class (e.g. bourbon). Checked before the PASS path so a label
    # declaring a valid bourbon whose other side names a conflicting vodka cannot slip to
    # PASS. Anchored to the declared designation (not any two stray OCR words) so an
    # incidental back-label mention — a cocktail recipe, a pairing note — degrades to the
    # ambiguous/REVIEW path rather than a confident wrong FAIL ("recommend, don't
    # decide"). The liqueur/cordial group is excluded (a statement of composition that
    # names its base spirit is valid, not a conflict — see rulesets CONFLICT_GROUPS).
    conflict = _detect_conflict(designation, ocr_text)
    if conflict is not None:
        groups, values = conflict
        return CheckResult(
            verdict=verdict.FAIL,
            detail=(
                f"conflicting class/type designations across labels: {', '.join(sorted(values))} "
                f"(groups: {', '.join(sorted(groups))}) | {data.CFR_CITATION}"
            ),
        )

    # (2) Recognized designation (AC1) — deterministic PASS, NO model. Prefer the
    # application value; fall back to a recognized designation located in the OCR text.
    matched = _recognized_keyword(designation) or _recognized_keyword(ocr_text)
    if matched is not None:
        return CheckResult(
            verdict=verdict.PASS,
            detail=f"recognized class/type: {matched!r} | {data.CFR_CITATION}",
        )

    # (3) Ambiguous (AC2/AC4) — neither a conflict nor recognized. Escalate to a VLM if
    # the model layer is on (capped at REVIEW); otherwise rules-only REVIEW.
    return _escalate_or_review(ctx, designation)


# ── deterministic recognition + conflict (OCR text feeds ONLY this) ──────────


def _recognized_keyword(text: str) -> str | None:
    """The first catalog base-class keyword the normalized ``text`` CONTAINS, else None.

    Normalizes via the centralized ``app/normalize.py`` (case/punctuation collapse) so
    "BOURBON" == "bourbon". Membership is substring (a designation "contains" a base
    class). Returns the matched keyword (for the PASS detail)."""
    norm = normalize.normalize(text, "class_type_designation")
    if not norm:
        return None
    for keyword in data.KEYWORD_GROUPS:
        if _contains_phrase(norm, keyword):
            return keyword
    return None


def _detect_conflict(designation: str, ocr_text: str) -> tuple[set[str], set[str]] | None:
    """Detect a declared base class contradicted by a DIFFERENT base class in the labels.

    Returns ``(groups, matched_keywords)`` when the application's declared
    ``designation`` resolves to a mutually-exclusive base-class group AND the joined OCR
    text carries a DIFFERENT mutually-exclusive group (an AC3 violation), else ``None``.
    Deterministic — no model.

    Two refinements keep this from emitting a confident *wrong* FAIL:

    - Only :data:`~app.engine.rulesets.class_type.CONFLICT_GROUPS` (the mutually-
      exclusive spirit base classes) count. The ``liqueur``/``cordial`` group is
      excluded — a liqueur naming its base spirit ("Coffee Liqueur with Rum", "Sloe Gin
      Liqueur") is a valid statement of composition, not a conflict.
    - The conflict is **anchored to the declared designation**: at least one side must be
      the product's own declared base class. An undeclared incidental mention on a back
      label (a cocktail recipe, a pairing note) therefore degrades to the ambiguous/
      REVIEW path, never a deterministic FAIL. Same-group variants ("straight bourbon" +
      "bourbon whiskey") collapse to one group and are NOT a conflict.
    """
    declared_groups = _conflict_groups_in(designation)
    if not declared_groups:
        # No declared base class to anchor a contradiction against → not a deterministic
        # conflict (an OCR-only multi-spirit blob is genuine ambiguity → REVIEW path).
        return None

    ocr_groups = _conflict_groups_in(ocr_text)
    all_groups = declared_groups | ocr_groups
    if len(all_groups) < 2:
        return None

    # Re-collect the matched keywords (for the cited detail) across both inputs, limited
    # to the conflicting groups.
    matched: set[str] = set()
    combined = f"{designation}\n{ocr_text}"
    norm = normalize.normalize(combined, "class_type_designation")
    for keyword, group in data.KEYWORD_GROUPS.items():
        if group in all_groups and _contains_phrase(norm, keyword):
            matched.add(keyword)
    return (all_groups, matched)


def _conflict_groups_in(text: str) -> set[str]:
    """The set of mutually-exclusive base-class groups present in ``text``.

    Only :data:`~app.engine.rulesets.class_type.CONFLICT_GROUPS` members are returned —
    the ``liqueur`` group never participates in conflict detection (see that DATA
    member's rationale). Normalizes via the centralized ``app/normalize.py``."""
    norm = normalize.normalize(text, "class_type_designation")
    if not norm:
        return set()
    groups: set[str] = set()
    for keyword, group in data.KEYWORD_GROUPS.items():
        if group in data.CONFLICT_GROUPS and _contains_phrase(norm, keyword):
            groups.add(group)
    return groups


def _contains_phrase(normalized_text: str, keyword: str) -> bool:
    """Whether ``keyword`` appears in ``normalized_text`` on word boundaries.

    Word-boundary match (not a raw substring) so "gin" does not fire inside "virgin"
    and "rum" does not fire inside "drum". A multi-word ``keyword`` ("single malt")
    matches whether the label spaces or HYPHENATES it ("Single-Malt"): the internal
    space is matched as a space-or-hyphen run, since ``normalize`` collapses whitespace
    but preserves an internal hyphen. The boundary anchors the whole phrase."""
    # Each internal space in the keyword becomes a [\s-]+ run so "single malt" also
    # matches "single-malt"; \b anchors both ends against the surrounding text.
    inner = re.escape(keyword).replace(r"\ ", r"[\s-]+")
    pattern = r"\b" + inner + r"\b"
    return re.search(pattern, normalized_text) is not None


# ── the VLM escalation (image-only, capped at REVIEW) ────────────────────────


def _escalate_or_review(ctx: CheckContext, designation: str) -> CheckResult:
    """Ambiguous designation: VLM escalation when the model is on, else rules-only REVIEW.

    The model is handed the label IMAGE + an OCR-free prompt (VLM-only). Whatever it
    returns, the verdict is CAPPED at REVIEW (never PASS, never FAIL). When the model
    layer is off (``get_llm_adapter`` → None) or there is no readable image, degrade to a
    rules-only REVIEW. A raising/erroring adapter also degrades to REVIEW."""
    adapter = get_llm_adapter(get_settings())
    base_detail = (
        f"ambiguous class/type designation {designation!r}: not in the recognized "
        f"catalog | {data.CFR_CITATION}"
    )

    if adapter is None:
        # AC4 — model layer off: rules-only, defer to the specialist.
        return CheckResult(
            verdict=verdict.REVIEW,
            detail=f"{base_detail} — model layer off; defer to specialist",
        )

    image_path = _primary_image_path(ctx)
    if image_path is None:
        # No image to read — the VLM has nothing to assess; defer (still REVIEW).
        return CheckResult(
            verdict=verdict.REVIEW,
            detail=f"{base_detail} — no readable label image; defer to specialist",
        )

    # AC2 — escalate. The ONLY input is the image + the fixed OCR-free prompt. The
    # result is capped at REVIEW regardless of what the model says.
    try:
        result = adapter.run("classify_class_type", _PROMPT, image_path=str(image_path))
    except Exception as exc:  # noqa: BLE001 — degrade to REVIEW, never crash the check
        logger.warning(
            "class_type VLM escalation raised; deferring to REVIEW: %s", type(exc).__name__
        )
        return CheckResult(verdict=verdict.REVIEW, detail=f"{base_detail} — model unavailable")

    model_id = getattr(result, "model_id", None)
    return CheckResult(
        verdict=verdict.REVIEW,  # capped — an LLM opinion alone never yields PASS/FAIL
        detail=f"{base_detail} — model-assisted review (capped at REVIEW)",
        model_id=model_id,
    )


def _primary_image_path(ctx: CheckContext) -> Path | None:
    """The on-disk path of the submission's primary (display-order first) label image.

    Reuses Story 2.5's primary-image resolution (``SOURCE_IMAGES_DIR / filename``); the
    VLM reads the ORIGINAL image. ``None`` when there is no readable image."""
    from app.pipeline.preprocess import SOURCE_IMAGES_DIR

    images = repo.list_label_images(ctx.conn, ctx.submission.id)
    if not images:
        return None
    primary = images[0]
    if not (primary.filename or "").strip():
        return None
    return SOURCE_IMAGES_DIR / primary.filename
