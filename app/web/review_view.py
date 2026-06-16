"""Review Workspace presenter (Stories 4.3, 4.4).

Pure, read-only view-model builders that turn a submission's beverage type + its
``checklist_items`` (and, for 4.4, its ``v_field_comparisons`` rows) into the shell
elements and stacked field comparison cards rendered by ``templates/review.html``:

- :func:`banner` — the beverage-type banner (word + accent class);
- :func:`chevron` — the progress step-map (Identity → Mandatory text → Gov. Warning
  → Conditional → Decide), with the Conditional step appearing ONLY when a
  conditional/flag-only check is present and the remaining steps renumbering cleanly;
- :func:`suggested_verdict` — the advisory roll-up alert.

**Centralized roll-up (contract #3).** :func:`suggested_verdict` rolls the per-check
verdicts up via :func:`app.verdict.rollup` — the SAME function the engine used to set
``submissions.engine_verdict`` — so the UI's Suggested alert can never disagree with
the engine. Severity precedence is NOT re-implemented here.

**Verdict vs disposition (contract #3).** Everything here is the engine register
(``PASS``/``REVIEW``/``FAIL``) — advisory only. This module emits NO disposition word
(Approved / Needs Correction / Rejected) and no ``verdict → disposition`` mapping.

**AR-5 purity.** This module imports nothing from the OCR/LLM/engine-run layers; it is
a pure read-model used on the ``GET /review/{id}`` read path. The step→group mapping is
carried as DATA (``CHECK_KEY_STEP``) so a ruleset change is a data edit, not logic.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import cast

from app import disposition, normalize, verdict
from app.db.repositories import ChecklistItem, FieldComparison, LabelImage

# ── Beverage-type banner (DESIGN.md beverage accents) ────────────────────────
# The stored enum → displayed word. The word is ALWAYS rendered (colorblind + the
# Dave persona); the accent only reinforces it.
BEVERAGE_WORD: dict[str, str] = {
    "DISTILLED_SPIRITS": "DISTILLED SPIRITS",
    "WINE": "WINE",
    "MALT_BEVERAGE": "BEER",
}
# The brand.css accent class per type. Beer uses dark ink (white fails AA on gold) —
# the contrast rule lives in the stylesheet; the class selection lives here.
BEVERAGE_ACCENT_CLASS: dict[str, str] = {
    "DISTILLED_SPIRITS": "beverage-banner--spirits",
    "WINE": "beverage-banner--wine",
    "MALT_BEVERAGE": "beverage-banner--beer",
}


def banner(beverage_type: str | None) -> dict[str, str]:
    """The beverage banner view-model: ``{"word", "accent_class"}``.

    An unmapped / unknown enum degrades to the type title-cased with NO accent class
    (the neutral banner) — never raises, never blanks the word."""
    key = beverage_type or ""
    word = BEVERAGE_WORD.get(key)
    if word is None:
        # Unknown type: still show a word, drop the accent (neutral banner).
        return {"word": key.replace("_", " ").title() or "UNKNOWN", "accent_class": ""}
    return {"word": word, "accent_class": BEVERAGE_ACCENT_CLASS[key]}


# ── Chevron / step indicator (EXPERIENCE.md progress map, U4) ─────────────────
# The ordered step labels and the stable same-page anchor id per step. The field
# cards for each group arrive in Stories 4.4–4.8; the anchors target placeholder
# sections in the shell so they resolve now and stay stable.
_IDENTITY = "Identity"
_MANDATORY = "Mandatory text"
_GOV_WARNING = "Gov. Warning"
_CONDITIONAL = "Conditional"
_DECIDE = "Decide"

STEP_LABELS: tuple[str, ...] = (_IDENTITY, _MANDATORY, _GOV_WARNING, _CONDITIONAL, _DECIDE)

STEP_ANCHOR: dict[str, str] = {
    _IDENTITY: "group-identity",
    _MANDATORY: "group-mandatory-text",
    _GOV_WARNING: "group-gov-warning",
    _CONDITIONAL: "group-conditional",
    _DECIDE: "group-decide",
}

# check_key → step label, carried as DATA (rules-as-data). A ruleset change is a data
# edit here, never a logic change. Keys not in this map fall to the Conditional bucket
# (see :func:`_is_conditional`).
CHECK_KEY_STEP: dict[str, str] = {
    # ① Identity — who/what the product is
    "brand_name": _IDENTITY,
    "class_type_designation": _IDENTITY,
    "name_address": _IDENTITY,
    "grape_varietal": _IDENTITY,  # wine ruleset (Story 3.8), an always-present identity field
    "fanciful_name": _IDENTITY,  # malt ruleset (Story 3.8), an always-present identity field
    # ② Mandatory text — the always-required label statements
    "alcohol_content": _MANDATORY,
    "net_contents": _MANDATORY,
    "abv_format": _MANDATORY,
    "standards_of_fill": _MANDATORY,
    "proof_abv_consistency": _MANDATORY,
    # ③ Gov. Warning
    "government_warning": _GOV_WARNING,
}


def _is_conditional(item: ChecklistItem) -> bool:
    """Whether a checklist item belongs to the Conditional step ④.

    The conditional bucket is the §4/§7 conditional disclosures + the same-field-of-
    vision positional check (Story 3.7/3.8): a check NOT in the core ``CHECK_KEY_STEP``
    map **whose ``check_type`` is ``MANUAL``** (the flag-only / positional strategy
    marker). Gating on ``MANUAL`` — not bare map-absence — is what keeps an
    always-present FIELD_MATCH identity field that simply isn't yet in the map (a
    rules-as-data drift, e.g. a new beverage-type identity column) from silently
    inflating the Conditional step: only the genuinely conditional MANUAL disclosures
    trigger step ④, so it appears ONLY when actually triggered (AC3)."""
    return item.check_key not in CHECK_KEY_STEP and item.check_type == "MANUAL"


def chevron(items: Iterable[ChecklistItem]) -> list[dict[str, object]]:
    """Build the visible chevron steps for a submission's checklist.

    Identity, Mandatory text, Gov. Warning and Decide are always present; the
    **Conditional** step is included ONLY when at least one item maps to it. ``number``
    is the 1-based position AFTER Conditional is included/excluded, so Decide is ⑤ with
    Conditional and ④ without — anchors never go off-by-one. The first step is marked
    ``is_current`` so the ``aria-current`` / "step 1 of N" text has a deterministic
    anchor (a live cursor is a later interaction story)."""
    item_list = list(items)
    has_conditional = any(_is_conditional(i) for i in item_list)

    visible = [_IDENTITY, _MANDATORY, _GOV_WARNING]
    if has_conditional:
        visible.append(_CONDITIONAL)
    visible.append(_DECIDE)

    steps: list[dict[str, object]] = []
    for number, label in enumerate(visible, start=1):
        steps.append(
            {
                "label": label,
                "number": number,
                "anchor": STEP_ANCHOR[label],
                "present": True,
                "is_current": number == 1,
            }
        )
    return steps


# ── Suggested-verdict alert (EXPERIENCE.md advisory roll-up) ──────────────────
# verdict → (USWDS Alert modifier class, text-equivalent icon glyph). Paired with the
# verdict WORD in the template — never tint/color alone.
_ALERT_CLASS: dict[str, str] = {
    verdict.PASS: "usa-alert--success",
    verdict.REVIEW: "usa-alert--warning",
    verdict.FAIL: "usa-alert--error",
}
_ALERT_ICON: dict[str, str] = {
    verdict.PASS: "\u2713",  # ✓
    verdict.REVIEW: "!",
    verdict.FAIL: "\u2717",  # ✗
}


def _summary(rolled: str, *, passed: int, total: int, needs_review: int) -> str:
    """The plain-language roll-up sentence — authority always returns to the human.

    Honest empty case: nothing was auto-verified ⇒ defer to the human, never imply a
    silent PASS."""
    if total == 0:
        return "Nothing was auto-verified — your call. You decide."
    if needs_review == 0:
        return f"All {total} checks passed automatically. You decide."
    return f"{passed} of {total} passed automatically; {needs_review} need your review. You decide."


def suggested_verdict(items: Iterable[ChecklistItem]) -> dict[str, object]:
    """The suggested-verdict alert view-model (advisory roll-up).

    Rolls the per-check verdicts up via the centralized :func:`app.verdict.rollup`
    (the SAME roll-up the engine used). Counts exclude ``NA`` (the per-check
    not-applicable value — matching ``rollup``'s scoring). Returns
    ``{"verdict", "alert_class", "icon", "passed", "total", "needs_review",
    "summary"}``. Empty / all-``NA`` ⇒ ``REVIEW`` with honest copy (never a silent
    PASS). Emits NO disposition word (contract #3)."""
    item_list = list(items)
    raw = [i.verdict for i in item_list if i.verdict is not None]
    rolled = verdict.rollup(raw)

    scored = [v for v in raw if v != verdict.NA]
    total = len(scored)
    passed = sum(1 for v in scored if v == verdict.PASS)
    needs_review = total - passed

    return {
        "verdict": rolled,
        "alert_class": _ALERT_CLASS[rolled],
        "icon": _ALERT_ICON[rolled],
        "passed": passed,
        "total": total,
        "needs_review": needs_review,
        "summary": _summary(rolled, passed=passed, total=total, needs_review=needs_review),
    }


# ── Stacked field comparison cards (Story 4.4) ───────────────────────────────
# Each FIELD_MATCH checklist row that links a field_comparisons row (via the
# field_comparison_id FK) becomes one stacked card: the application value above
# the OCR/LLM value, a verdict chip, an explained discrepancy. The per-card
# verdict is the engine's already-stored checklist_items.verdict — NEVER
# recomputed here (contract #3). Citations come from the row (CFR-as-data).

# verdict → (chip CSS class, text-equivalent icon glyph, chip word). The word +
# icon are ALWAYS rendered alongside color (A11Y: never tint alone). Reuses the
# Story 4.3 _ALERT_ICON glyphs.
_CHIP_CLASS: dict[str, str] = {
    verdict.PASS: "chip--pass",
    verdict.REVIEW: "chip--review",
    verdict.FAIL: "chip--fail",
}
_CHIP_WORD: dict[str, str] = {
    verdict.PASS: "match",
    verdict.REVIEW: "REVIEW",
    verdict.FAIL: "FAIL",
}

# State-pattern copy (verbatim from EXPERIENCE.md / mockup). Carried as data so a
# wording change is a single-line edit, never scattered template logic.
_SOFT_NOTE = "Capitalization differs; the text otherwise matches."
_NEAR_MISS_NOTE = "The values are close but not identical — please verify by eye."
_NOT_FOUND_NOTE = "Not found on label"
_UNREADABLE_NOTE = "Couldn't read this field reliably from the photo — please verify by eye."
_BLANK_APPLICATION_NOTE = "No value submitted in the application for this field."
# A check the engine could not complete (its comparison row never materialized): a
# visible honest error rather than a silent drop (Story 4.11 AC2). It stays in the
# advisory REVIEW register — never a guessed PASS/FAIL — and draws no fabricated diff.
_CHECK_ERROR_NOTE = "This check couldn't be completed — please verify by eye."

# The visible degrade notice when the submission's displayed VLM extraction errored
# (an ``llm_results`` row with ``status='ERROR'``) — the model was enabled and tried
# but was unreachable, so the comparison fell back to OCR (FR-12). Verbatim from
# EXPERIENCE.md (State Patterns / Accessibility Floor). Carried as data, not a
# template literal, so a wording change is one edit.
_LLM_UNAVAILABLE_NOTE = "LLM check unavailable — showing OCR result"

# severity rank for the problems-first sort (lower floats to the top). FAIL above
# REVIEW above PASS; the list is already in id (ruleset) order so a STABLE sort
# preserves that as the tie-break.
_SORT_RANK: dict[str, int] = {verdict.FAIL: 0, verdict.REVIEW: 1, verdict.PASS: 2}


def _is_blank(value: str | None) -> bool:
    """A field value that carries no content (None or whitespace-only)."""
    return value is None or value.strip() == ""


def _char_diff(
    application: str, extracted: str, *, soft: bool
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Character-level diff of two already-stored strings (stdlib ``difflib``).

    Returns ``(application_segments, extracted_segments)`` — each a list of
    ``{"text", "kind"}`` segments the template renders as ``diff-*`` spans. A
    ``soft`` (normalized-equal) diff marks every differing span with the amber
    ``soft`` kind (never the red ``del``/``ins``); a hard mismatch marks the
    application side with ``del`` and the extracted side with ``ins``. Equal spans
    carry the ``equal`` kind. Pure deterministic string work — no model, no
    network (VLM-only purity is irrelevant; nothing here touches a model)."""
    app_segs: list[dict[str, str]] = []
    ext_segs: list[dict[str, str]] = []
    matcher = SequenceMatcher(None, application, extracted, autojunk=False)
    diff_kind = "soft" if soft else None
    for op, a1, a2, b1, b2 in matcher.get_opcodes():
        if op == "equal":
            app_segs.append({"text": application[a1:a2], "kind": "equal"})
            ext_segs.append({"text": extracted[b1:b2], "kind": "equal"})
            continue
        if application[a1:a2]:
            app_segs.append({"text": application[a1:a2], "kind": diff_kind or "del"})
        if extracted[b1:b2]:
            ext_segs.append({"text": extracted[b1:b2], "kind": diff_kind or "ins"})
    return app_segs, ext_segs


def _diff_text_equivalent(application: str | None, extracted: str | None) -> str:
    """Screen-reader text equivalent naming a diff (A11Y hard requirement).

    The character diff is never conveyed by a colored span alone. Whenever a diff is
    drawn the card carries this plain-language string (rendered visually-hidden) so a
    screen-reader user — and forced-colors mode, where the span color is stripped —
    still learns WHICH value differs from which, e.g. ``Application: 'Stone's Throw' —
    on label: 'STONE'S THROW'``. Mirrors the EXPERIENCE.md accessibility-floor copy."""
    app = application if application is not None else ""
    ext = extracted if extracted is not None else ""
    return f"Application: {app!r} — on label: {ext!r}"


def _isolate_ocr_snippet(field_key: str, application_value: str | None, blob: str) -> str | None:
    """Isolate the part of the whole-label OCR blob that corresponds to ONE field.

    The OCR-only fallback (Story 3.3) stores the entire label's OCR text as a field's
    candidate ``extracted_value`` (the comparator locates the value within it). For
    DISPLAY that would dump the whole label into every card; instead show just the
    located snippet — the matching ``<number><unit>`` line for a numeric field, or the
    best-matching word window for a text field — so the discovered side reads
    "OLD TOM DISTILLERY" / "750 mL", not the full dump. Deterministic string work over
    already-stored text (no model; VLM-only purity is untouched). With an application
    value it falls back to the blob only if isolation fails; with NO application value
    (ABV / net contents / grape varietal — fields the public registry doesn't carry) it
    returns an isolated numeric line or, for text fields, nothing — never the full dump."""
    text = (blob or "").strip()
    if not text:
        return blob
    has_app = application_value is not None and bool(application_value.strip())
    if field_key in normalize.NUMERIC_FIELD_KEYS:
        # Numeric fields isolate their own unit-bearing line; never dump the blob.
        return _isolate_numeric_line(field_key, application_value if has_app else None, text)
    if has_app and application_value is not None:
        return _isolate_text_window(field_key, application_value, text) or blob
    # No application value to anchor a text field (e.g. grape varietal — the public
    # registry doesn't carry it) — never dump the whole label; show nothing instead.
    return None


# Unit classes per numeric field, used to isolate the right line when there is no
# application value to anchor on (so net_contents won't grab a stray ABV "%").
_FIELD_NUMERIC_UNITS = {
    "alcohol_content": {"%", "proof"},
    "net_contents": {"ml", "l"},
}


def _isolate_numeric_line(field_key: str, application_value: str | None, text: str) -> str | None:
    """The blob line carrying this field's quantity, matched by UNIT so cross-field
    numbers don't bleed in (net_contents shows ``750 ml``, never a stray ``45 %`` ABV).
    Prefers the application's unit; with none, any unit valid for this field. Returns
    None when no field-appropriate quantity is on the label (the card shows blank, never
    the whole dump)."""
    app_unit = (
        normalize.parse_numeric(application_value, field_key)[1] if application_value else None
    )
    allowed = {app_unit} if app_unit else _FIELD_NUMERIC_UNITS.get(field_key, set())
    lines = text.splitlines() or [text]
    for line in lines:
        # parse_all_numeric (not parse_numeric) so a unit-bearing token is found even when
        # it is NOT first on its line — a label routinely prints several quantities on one
        # line ("750ml! / 151 Proof / Alc. 75.5% by Vol."), and the ABV card must locate
        # the "%" token rather than show "(not found)" because "750ml" came first.
        for num, unit in normalize.parse_all_numeric(line, field_key):
            if num is not None and (not allowed or unit in allowed):
                return line.strip()
    return None


def _isolate_text_window(field_key: str, application_value: str, text: str) -> str | None:
    """The original-text word window that best matches the application value (by
    normalized similarity). Returns the closest window verbatim, so the card shows what
    OCR actually read for this field — the matched form for a hit, the nearest text
    otherwise — instead of the entire label."""
    app_norm = normalize.normalize(application_value, field_key)
    words = text.split()
    if not app_norm or not words:
        return None
    n = max(1, len(app_norm.split()))
    best_score, best = -1.0, None
    for size in {min(n, len(words)), min(n + 1, len(words))}:
        for i in range(0, len(words) - size + 1):
            window = " ".join(words[i : i + size])
            score = SequenceMatcher(None, app_norm, normalize.normalize(window, field_key)).ratio()
            if score > best_score:
                best_score, best = score, window
    return best


def _displayed_extracted(comparison: FieldComparison) -> str | None:
    """The discovered value to SHOW on a card.

    LLM-sourced comparisons already carry a structured per-field value (shown as-is).
    The OCR-text fallback stores the WHOLE label blob, so isolate just this field's
    snippet (:func:`_isolate_ocr_snippet`) — otherwise every card shows the full dump."""
    ext = comparison.extracted_value
    if ext is None:
        return None
    if comparison.source_llm_result_id is None and comparison.source_ocr_result_id is not None:
        return _isolate_ocr_snippet(comparison.field_key, comparison.application_value, ext)
    return ext


def _derive_state(item: ChecklistItem, comparison: FieldComparison) -> str:
    """Derive the card state from (verdict, match_status, blank-application).

    A small explicit precedence — NOT scattered ``if``s in the template. The verdict
    REVIEW reaches the engine by *three* distinct routes, only one of which is the
    cosmetic ``soft`` case, so REVIEW is NOT a synonym for ``soft`` — the state is
    gated on ``match_status`` so the on-card note + diff never contradict the engine:

    - blank application value (with extracted text) ⇒ ``blank_application``;
    - ``UNVERIFIABLE`` ⇒ ``unreadable``;
    - ``MISSING`` ⇒ ``not_found``;
    - ``MATCH`` + verdict ``REVIEW`` (normalized-equal but raw differs — a case-only
      difference) ⇒ ``soft`` (amber, "Capitalization differs" note + amber diff). But a
      ``MATCH`` + ``REVIEW`` whose raw values are *identical* is the low-OCR-confidence
      safety valve (``field_match`` softens a clean MATCH to REVIEW without changing the
      text) — there is no character difference to show, so it degrades to ``unreadable``
      (honest "verify by eye" note, no phantom diff) rather than a false soft diff;
    - ``MISMATCH`` + verdict ``FAIL`` ⇒ ``mismatch`` (loud, red char-diff — a
      substantive discrepancy the maker must fix);
    - ``MISMATCH`` + verdict ``REVIEW`` ⇒ ``near_miss`` (a near-miss ≥ the review
      floor — a real textual difference shown as a char-diff, but amber not red, with a
      "differs — please verify" note rather than the false "Capitalization differs");
    - otherwise ⇒ ``match``.

    Verdict is the engine's already-stored value — never recomputed (contract #3).
    The card's color (red vs amber vs green) follows the VERDICT in :func:`field_cards`,
    so a REVIEW never paints red — only the deterministic FAIL mismatch does."""
    status = comparison.match_status
    if _is_blank(comparison.application_value) and not _is_blank(comparison.extracted_value):
        return "blank_application"
    if status == "UNVERIFIABLE":
        return "unreadable"
    if status == "MISSING":
        return "not_found"
    if status == "MATCH" and item.verdict == verdict.REVIEW:
        # normalized-equal but raw differs ⇒ the cosmetic soft case; identical raw
        # values ⇒ the low-OCR-confidence valve (no diff to draw) ⇒ unreadable.
        if comparison.application_value != comparison.extracted_value:
            return "soft"
        return "unreadable"
    if status == "MISMATCH":
        return "mismatch" if item.verdict == verdict.FAIL else "near_miss"
    return "match"


def llm_notice(degraded: bool) -> dict[str, str] | None:
    """The workspace-level LLM-unavailable notice view-model (Story 4.11 AC3).

    ``degraded`` is the submission's already-stored signal that its displayed VLM
    extraction errored (an ``llm_results`` row with ``status='ERROR'`` — the model
    was enabled and attempted but unreachable, so the comparison fell back to OCR,
    FR-12). Returns ``{"text": …}`` carrying the verbatim EXPERIENCE.md copy when
    degraded, else ``None`` (no notice — including the config-off OCR-only path,
    which writes no ``llm_results`` row at all). The route reads the bool from the DB
    on the AR-5-pure read path and passes it in; this presenter touches no model."""
    if not degraded:
        return None
    return {"text": _LLM_UNAVAILABLE_NOTE}


def _error_card(item: ChecklistItem) -> dict[str, object]:
    """A visible honest error card for a check the engine could not complete (AC2).

    Built when a FIELD_MATCH ``checklist_items`` row references a comparison that
    never materialized. Stays in the advisory REVIEW register (never a guessed
    PASS/FAIL, contract #4), is flagged a problem so it floats up, carries the plain
    "couldn't be completed" note, and draws NO char-diff (there is nothing to diff)."""
    vdt = verdict.REVIEW
    return {
        "field_key": item.check_key,
        "field_label": item.label or item.check_key.replace("_", " ").title(),
        "cfr_citation": item.cfr_citation,
        "verdict": vdt,
        "chip_class": _CHIP_CLASS[vdt],
        "icon": _ALERT_ICON[vdt],
        "chip_word": _CHIP_WORD[vdt],
        "state": "error",
        "application_value": None,
        "extracted_value": None,
        "extracted_source": None,
        "detail": item.detail,
        "diff_application": None,
        "diff_extracted": None,
        "diff_text_equivalent": None,
        "note": _CHECK_ERROR_NOTE,
        "is_problem": True,
        "sort_rank": _SORT_RANK[vdt],
    }


def _card_decision(vdt: str, check_key: str, decisions: dict[str, str]) -> dict[str, object]:
    """The reviewer's per-card Pass/Fail state. An explicit decision wins; otherwise a
    Match (engine PASS/NA) PRE-SELECTS Pass, while REVIEW/FAIL start with neither chosen
    (the reviewer must make the call). ``decided`` drives the checklist's done count."""
    explicit = decisions.get(check_key)
    if explicit in ("pass", "fail"):
        pass_active, fail_active = explicit == "pass", explicit == "fail"
    else:
        pass_active, fail_active = vdt in (verdict.PASS, verdict.NA), False
    return {
        "check_key": check_key,
        "decision_pass": pass_active,
        "decision_fail": fail_active,
        "decided": pass_active or fail_active,
    }


def field_cards(
    items: Iterable[ChecklistItem],
    comparisons: Iterable[FieldComparison],
    *,
    decisions: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    """Build the stacked field comparison cards, sorted problems-first (Story 4.4).

    Joins each FIELD_MATCH ``checklist_items`` row to its ``field_comparisons`` row
    via the ``field_comparison_id`` FK. ONLY rows that carry a ``field_comparison_id``
    resolving to a comparison become cards — the Government Warning (Story 4.5), the
    checklist (4.6) and flag-only / positional checks (no comparison row) are
    excluded. Each card carries its raw values, the engine verdict + chip, the
    derived state, the char-diff segments (for ``mismatch``/``soft`` only), the state
    note, and the "Why?" data (``cfr_citation`` / ``extracted_source`` / ``detail``).

    Cards sort problems-first by a fixed verdict severity rank (FAIL < REVIEW <
    PASS) with a STABLE tie-break on the original id (ruleset) order. The per-card
    verdict is the engine's already-stored ``checklist_items.verdict`` — never
    recomputed; citations come from the row (CFR-as-data). A pure read-model."""
    by_id = {c.id: c for c in comparisons}
    decisions = decisions or {}

    cards: list[dict[str, object]] = []
    for item in items:
        if item.field_comparison_id is None:
            continue
        comparison = by_id.get(item.field_comparison_id)
        if comparison is None:
            # A check that expected a comparison row but has none — the engine could
            # not complete it. Surface a visible honest error card (Story 4.11 AC2)
            # in the advisory REVIEW register rather than silently dropping it; the
            # other checks still render.
            err = _error_card(item)
            err.update(_card_decision(verdict.REVIEW, item.check_key, decisions))
            cards.append(err)
            continue

        vdt = item.verdict or verdict.REVIEW
        state = _derive_state(item, comparison)
        # The OCR-only fallback stores the whole-label blob as extracted_value; show
        # just this field's isolated snippet (the card + diff render this, not the dump).
        display_extracted = _displayed_extracted(comparison)

        note: str | None = None
        diff_application: list[dict[str, str]] | None = None
        diff_extracted: list[dict[str, str]] | None = None
        diff_text_equivalent: str | None = None
        # The two "differs" states get a short plain note; the values themselves are shown
        # verbatim (application above, OCR below) so the reviewer compares them by eye. We
        # deliberately do NOT draw a character-level redline/track-changes diff — on noisy
        # OCR text it produces a tangle of strike/underline marks that is harder to read
        # than the two raw strings.
        if state in ("soft", "near_miss", "mismatch"):
            note = {"soft": _SOFT_NOTE, "near_miss": _NEAR_MISS_NOTE}.get(state)
        elif state == "not_found":
            note = _NOT_FOUND_NOTE
        elif state == "unreadable":
            note = _UNREADABLE_NOTE
        elif state == "blank_application":
            note = _BLANK_APPLICATION_NOTE

        cards.append(
            {
                "field_key": comparison.field_key,
                "field_label": item.label or comparison.field_key.replace("_", " ").title(),
                "cfr_citation": item.cfr_citation,
                "verdict": vdt,
                "chip_class": _CHIP_CLASS.get(vdt, "chip--review"),
                "icon": _ALERT_ICON.get(vdt, "!"),
                "chip_word": _CHIP_WORD.get(vdt, "REVIEW"),
                "state": state,
                "application_value": comparison.application_value,
                "extracted_value": display_extracted,
                "extracted_source": comparison.extracted_source,
                "detail": item.detail,
                "diff_application": diff_application,
                "diff_extracted": diff_extracted,
                "diff_text_equivalent": diff_text_equivalent,
                "note": note,
                "is_problem": vdt != verdict.PASS,
                "sort_rank": _SORT_RANK.get(vdt, 1),
                **_card_decision(vdt, item.check_key, decisions),
            }
        )

    cards.sort(key=lambda c: cast(int, c["sort_rank"]))  # stable: ties keep id (ruleset) order
    return cards


# ── Government Warning comparison card (Story 4.5) ───────────────────────────
# The Government Warning is NOT a field comparison — it has no field_comparisons
# row (the "required" side is the §16.21 statute, not an application field). The
# Story-3.4 deterministic evaluator already discriminated the three outcomes and
# wrote them into the single ``government_warning`` checklist_items row as a JSON
# ``detail`` payload with an ``outcome`` discriminator. This presenter PARSES that
# payload and dispatches on the outcome — it NEVER re-runs the §16.21 comparison,
# never re-types the warning text, never imports the check module (AR-5). The
# char-diff renders the engine's already-stored opcodes (pure presentation).

# The strategy/key the Story-3.4 evaluator writes its row under.
_GOV_WARNING_KEY = "government_warning"

# Engine outcome discriminators (mirror app/engine/checks/government_warning.py).
_GW_OUTCOME_PASS = "pass"
_GW_OUTCOME_REWORDED = "reworded"
_GW_OUTCOME_ABSENT = "absent"
_GW_OUTCOME_COULDNT_VERIFY = "couldnt_verify"

# verdict → Government-Warning chip word. The field-card map says "match" for PASS;
# the gov-warning card is not a field-match, so it uses the verdict word itself.
_GW_CHIP_WORD: dict[str, str] = {
    verdict.PASS: "PASS",
    verdict.REVIEW: "REVIEW",
    verdict.FAIL: "FAIL",
}

# State-pattern copy (verbatim — EXPERIENCE.md / AC2). Carried as data so a wording
# change is a single-line edit, never scattered template logic.
_GW_ABSENT_NOTE = "Required Government Warning not found on the submitted images"
_GW_COULDNT_VERIFY_NOTE = (
    "Couldn't confirm the bold/visual styling from a photo — please verify by eye."
)
# A compliant pass has no diff to stack; a bare chip read as "empty" to reviewers, so
# confirm in plain words that the on-label warning matched the statute (citation in header).
_GW_PASS_NOTE = "On-label warning matches the required statement — exact wording and casing."


def _gw_diff_text_equivalent(expected: str, found: str) -> str:
    """Screen-reader text equivalent for the gov-warning char-diff (A11Y).

    Mirrors :func:`_diff_text_equivalent` but prefixes ``Required:`` (the §16.21
    statute side) instead of ``Application:`` — the diff is never conveyed by a
    colored span alone, and this survives forced-colors mode."""
    return f"Required: {expected!r} — on label: {found!r}"


def _gw_diff_spans(
    diff_opcodes: object,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Render the engine's stored char-diff opcodes into required/on-label spans.

    The engine's ``_char_diff`` emitted ``[(op, segment), …]`` (JSON round-trips
    each tuple as a 2-element list) where ``op ∈ {equal, delete, insert, replace}``.
    Builds two span sequences (``[{"text","kind"}]``, ``kind ∈ {equal, del, ins}``):
    ``delete`` → a ``del`` on the required side; ``insert`` → an ``ins`` on the
    on-label side; ``equal`` → both; ``replace`` (``"<exp>\u2192<found>"``) → a
    ``del`` on required + an ``ins`` on on-label (split on the U+2192 arrow the
    engine embedded). Pure render of pre-computed data — no diff re-run."""
    required: list[dict[str, str]] = []
    onlabel: list[dict[str, str]] = []
    if not isinstance(diff_opcodes, list):
        return required, onlabel
    for pair in diff_opcodes:
        # Each opcode is a 2-element [op, segment]; ignore anything malformed.
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        op, segment = pair[0], pair[1]
        if not isinstance(op, str) or not isinstance(segment, str):
            continue
        if op == "equal":
            required.append({"text": segment, "kind": "equal"})
            onlabel.append({"text": segment, "kind": "equal"})
        elif op == "delete":
            required.append({"text": segment, "kind": "del"})
        elif op == "insert":
            onlabel.append({"text": segment, "kind": "ins"})
        elif op == "replace":
            expected_part, _, found_part = segment.partition("\u2192")
            if expected_part:
                required.append({"text": expected_part, "kind": "del"})
            if found_part:
                onlabel.append({"text": found_part, "kind": "ins"})
    return required, onlabel


def _gw_card(
    item: ChecklistItem,
    *,
    outcome: str,
    vdt: str,
    cfr_citation: str | None,
    required_text: str | None = None,
    onlabel_text: str | None = None,
    diff_required: list[dict[str, str]] | None = None,
    diff_onlabel: list[dict[str, str]] | None = None,
    diff_text_equivalent: str | None = None,
    note: str | None = None,
    deviation: str | None = None,
) -> dict[str, object]:
    """Assemble the gov-warning card view-model with the chip pinned to the verdict.

    Verdict is the engine's stored value — never recomputed (contract #3); the
    outcome only selects the visual STATE. The chip word/icon/class come from the
    data maps so icon + word are ALWAYS present (A11Y: never tint alone)."""
    return {
        "verdict": vdt,
        "chip_class": _CHIP_CLASS.get(vdt, "chip--review"),
        "icon": _ALERT_ICON.get(vdt, "!"),
        "chip_word": _GW_CHIP_WORD.get(vdt, "REVIEW"),
        "outcome": outcome,
        "cfr_citation": cfr_citation,
        "required_text": required_text,
        "onlabel_text": onlabel_text,
        "diff_required": diff_required,
        "diff_onlabel": diff_onlabel,
        "diff_text_equivalent": diff_text_equivalent,
        "note": note,
        "deviation": deviation,
        "detail": item.detail,
    }


def government_warning_card(
    items: Iterable[ChecklistItem], *, decisions: dict[str, str] | None = None
) -> dict[str, object] | None:
    """The Government Warning card view-model + the reviewer's per-card Pass/Fail state."""
    card = _government_warning_card_inner(items)
    if card is not None:
        card.update(_card_decision(cast(str, card["verdict"]), _GOV_WARNING_KEY, decisions or {}))
    return card


def _government_warning_card_inner(items: Iterable[ChecklistItem]) -> dict[str, object] | None:
    """Build the Government Warning comparison card from the engine's stored row.

    Locates the single ``government_warning`` ``checklist_items`` row and parses its
    JSON ``detail`` payload (the Story-3.4 evaluator wrote it). Dispatches on the
    ``outcome`` discriminator — never re-running the §16.21 comparison (AR-5). Returns
    ``None`` when no such row exists (the template renders the honest empty state — do
    NOT fabricate a card). A missing / garbled ``detail`` degrades to a calm REVIEW
    card (honest, never a crash, never a silent PASS).

    The per-card verdict is the engine's already-stored ``checklist_items.verdict`` —
    never recomputed (contract #3); the citation comes from the row (CFR-as-data),
    falling back to the payload when the row column is null. The required §16.21 text
    comes ONLY from the parsed payload — never re-typed here."""
    row: ChecklistItem | None = next((i for i in items if i.check_key == _GOV_WARNING_KEY), None)
    if row is None:
        return None

    vdt = row.verdict or verdict.REVIEW

    # Parse the engine payload defensively — a missing/garbled detail degrades to a
    # couldn't-verify-style REVIEW (honest; never crash, never a silent PASS).
    try:
        payload = json.loads(row.detail) if row.detail else None
    except (json.JSONDecodeError, TypeError):
        payload = None
    if not isinstance(payload, dict):
        return _gw_card(
            row,
            outcome=_GW_OUTCOME_COULDNT_VERIFY,
            vdt=verdict.REVIEW,
            cfr_citation=row.cfr_citation,
            note=_GW_COULDNT_VERIFY_NOTE,
        )

    # CFR citation from the row (ruleset data), payload as fallback — never a literal.
    cfr_citation = row.cfr_citation or payload.get("cfr_citation")
    outcome = payload.get("outcome")

    if outcome == _GW_OUTCOME_REWORDED:
        # Show the required §16.21 text and the OCR'd on-label text verbatim (stacked),
        # NOT a character-level redline — on noisy OCR the diff is a tangle, not a help.
        return _gw_card(
            row,
            outcome=_GW_OUTCOME_REWORDED,
            vdt=vdt,
            cfr_citation=cfr_citation,
            required_text=payload.get("expected"),
            onlabel_text=payload.get("found"),
            deviation=payload.get("deviation"),
        )

    if outcome == _GW_OUTCOME_ABSENT:
        return _gw_card(
            row,
            outcome=_GW_OUTCOME_ABSENT,
            vdt=vdt,
            cfr_citation=cfr_citation,
            note=_GW_ABSENT_NOTE,
        )

    if outcome == _GW_OUTCOME_COULDNT_VERIFY:
        # When the warning was detected via content anchors (header too OCR-garbled to
        # locate), the payload carries the OCR'd warning region + a tailored message —
        # show the on-label text so the reviewer can confirm wording/casing. The other
        # couldn't-verify case (bold/visual styling) keeps the standard verify-by-eye note.
        onlabel_text = payload.get("found")
        note = payload.get("message") if onlabel_text else _GW_COULDNT_VERIFY_NOTE
        return _gw_card(
            row,
            outcome=_GW_OUTCOME_COULDNT_VERIFY,
            vdt=vdt,
            cfr_citation=cfr_citation,
            onlabel_text=onlabel_text or None,
            note=note or _GW_COULDNT_VERIFY_NOTE,
        )

    if outcome == _GW_OUTCOME_PASS:
        # The compliant state. The engine's ``pass`` payload carries NO on-label text
        # (only the outcome + citation) and AR-5 forbids re-reading OCR here, so there is
        # no required/on-label stack to draw — but a bare green chip read as "empty" to
        # reviewers, so add a plain confirmation note that the on-label warning matched the
        # required statement (citation is in the header). No warning text is re-typed.
        return _gw_card(
            row,
            outcome=_GW_OUTCOME_PASS,
            vdt=vdt,
            cfr_citation=cfr_citation,
            note=_GW_PASS_NOTE,
        )

    # A missing or UNKNOWN ``outcome`` on an otherwise-valid dict is ambiguous — fold it
    # to the honest couldn't-verify REVIEW (never silent-PASS a check we can't classify),
    # matching the codebase's ambiguity⇒REVIEW fail-safe (``verdict.rollup`` and the
    # malformed-payload path above both degrade to REVIEW, never the most-reassuring state).
    return _gw_card(
        row,
        outcome=_GW_OUTCOME_COULDNT_VERIFY,
        vdt=verdict.REVIEW,
        cfr_citation=cfr_citation,
        note=_GW_COULDNT_VERIFY_NOTE,
    )


# ── Smart checklist (Story 4.6) ──────────────────────────────────────────────
# The per-type table-of-contents over the SAME `checklist_items` rows. Each row
# carries the engine verdict chip + a state derived from (verdict, ticked):
#
#   - auto-ticked (verdict PASS or NA)        → `done`     (muted, pre-ticked)
#   - REVIEW, ticked by the human             → `usercheck` ("you confirmed")
#   - REVIEW, untouched                       → `open`      (amber, needs eyes)
#   - FAIL,   ticked by the human             → `usercheck`
#   - FAIL,   untouched                       → `openfail`  (red, needs your call)
#
# "N of M done" counts the MERGED ticked set (auto ∪ manual) so a manual tick on
# an already-auto-PASS row never double-counts. The verdict is the engine's
# stored value — never recomputed (contract #3); a manual TICK is an
# acknowledgement ("I looked at this"), NOT a disposition and not a verdict
# change. Anchors reuse the chevron's `CHECK_KEY_STEP` → `STEP_ANCHOR` data (no
# second mapping). Pure read-model, AR-5-safe.

# The verdicts that the engine auto-verified — pre-ticked + muted. NA is "not
# applicable" (nothing to look at), so it counts as done alongside PASS.
_AUTO_TICK_VERDICTS: frozenset[str] = frozenset({verdict.PASS, verdict.NA})

# verdict → smart-checklist chip word. Unlike the field card ("match" for PASS),
# the checklist shows the verdict word itself (mockup `✓ PASS  auto`). NA is an
# auto-tick (muted "done") row, so it carries its own honest word/icon — without
# them it would inherit the REVIEW fail-safe and read "! REVIEW auto", wrongly
# flagging a not-applicable check as a problem (AC2: NA is not a problem).
_CHECKLIST_CHIP_WORD: dict[str, str] = {
    verdict.PASS: "PASS",
    verdict.REVIEW: "REVIEW",
    verdict.FAIL: "FAIL",
    verdict.NA: "N/A",
}
# Per-row icon for the smart checklist. Reuses the Story 4.3 _ALERT_ICON glyphs
# but adds NA's ✓ (an auto-verified "done" row, same muted check as PASS) so an
# NA row reads "✓ N/A auto", not the "!" REVIEW fail-safe.
_CHECKLIST_ICON: dict[str, str] = {
    **_ALERT_ICON,
    verdict.NA: "\u2713",  # ✓
}


def _checklist_anchor(item: ChecklistItem) -> str:
    """Map a checklist row to its field-group anchor — reusing the chevron data.

    A mapped ``check_key`` targets its ``CHECK_KEY_STEP`` → ``STEP_ANCHOR`` group;
    an unmapped row falls to the Conditional bucket (``group-conditional``), the
    same bucket :func:`_is_conditional` routes the chevron's ④ step to. No second
    mapping is invented (rules-as-data)."""
    step = CHECK_KEY_STEP.get(item.check_key)
    if step is not None:
        return STEP_ANCHOR[step]
    return STEP_ANCHOR[_CONDITIONAL]


def smart_checklist(
    items: Iterable[ChecklistItem],
    *,
    beverage_type: str | None,
    decisions: dict[str, str] | None = None,
    carded: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build the smart-checklist view-model — the tally of the reviewer's per-check calls.

    One row per ``checklist_items`` row, in the order given (ruleset / ``id`` order —
    the checklist does NOT re-sort). ``decisions`` is the human Pass/Fail map
    (``review_progress.decisions``); each row's EFFECTIVE decision is the reviewer's
    explicit call if present, else a Match (engine PASS/NA) defaults to ``pass``, while
    REVIEW/FAIL default to undecided. ``done_count`` is the number of DECIDED rows.

    ``carded`` maps ``check_key → card anchor`` for checks that HAVE a card: those rows
    are read-only here (the result text + a jump to the card — the decision is made ON
    the card). Rows NOT in ``carded`` have no card, so they carry the Pass/Fail control
    in the checklist itself (the only place to decide them).

    The per-row verdict is the engine's stored value — never recomputed (contract #3)."""
    item_list = list(items)
    decisions = decisions or {}
    carded = carded or {}

    rows: list[dict[str, object]] = []
    done_count = 0
    for item in item_list:
        vdt = item.verdict
        dstate = _card_decision(vdt or "", item.check_key, decisions)
        decision = "pass" if dstate["decision_pass"] else "fail" if dstate["decision_fail"] else ""
        decided = bool(decision)
        if decided:
            done_count += 1

        rows.append(
            {
                "check_key": item.check_key,
                "label": item.label or item.check_key.replace("_", " ").title(),
                "verdict": vdt,
                "chip_class": _CHIP_CLASS.get(vdt or "", "chip--review"),
                "icon": _CHECKLIST_ICON.get(vdt or "", "!"),
                "chip_word": _CHECKLIST_CHIP_WORD.get(vdt or "", "REVIEW"),
                "decision": decision,
                "decision_pass": dstate["decision_pass"],
                "decision_fail": dstate["decision_fail"],
                "decided": decided,
                "is_problem": not decided,
                "anchor": _checklist_anchor(item),
                # Carded checks are decided ON their card; the row links there + shows the
                # read-only result. Carded-less checks carry the control in the row.
                "has_card": item.check_key in carded,
                "card_anchor": carded.get(item.check_key, _checklist_anchor(item)),
            }
        )

    return {
        "type_word": banner(beverage_type)["word"].title(),
        "rows": rows,
        "done_count": done_count,
        "total": len(item_list),
    }


# ── Label-image panel + Enhance toggle (Story 4.7) ───────────────────────────
# The stored ``image_role`` enum → the display WORD. The word is ALWAYS rendered
# (never role-by-color alone, A11Y / AC1). A NULL role degrades to "Label image".
IMAGE_ROLE_WORD: dict[str, str] = {
    "BRAND": "Brand (front)",
    "BACK": "Back",
    "NECK": "Neck",
    "STRIP": "Strip",
    "OTHER": "Other",
}

# The corrective preprocess_log step name → the honest one-word caption fragment.
# Only the CORRECTIVE steps appear (decode/grayscale/binarize are structural). The
# caption names ONLY the steps actually ``applied`` on the image (AC4 honesty).
_PREPROCESS_CAPTION: dict[str, str] = {
    "deskew": "deskew",
    "normalize_illumination_glare": "glare",
    "clahe_contrast": "contrast",
    "denoise": "denoise",
    "perspective_correct": "perspective",
}


def _enhance_caption(preprocess_log: str | None) -> str:
    """Build the honest "deskew · glare · contrast" caption from the stored log.

    Reads the JSON ``preprocess_log`` and names ONLY the corrective steps that were
    actually ``applied`` (AC4). Degrades to a plain "preprocessed" caption when the log
    is NULL / unparseable / shaped unexpectedly — never raises."""
    if not preprocess_log:
        return "preprocessed"
    try:
        entries = json.loads(preprocess_log)
    except json.JSONDecodeError:
        return "preprocessed"
    # The pipeline writes a JSON ARRAY of step entries (preprocess.py). Anything else —
    # a top-level object/string/number — is an unexpected shape: degrade honestly to a
    # plain caption rather than iterate keys/characters and silently drop real steps.
    if not isinstance(entries, list):
        return "preprocessed"
    applied = [
        _PREPROCESS_CAPTION[e["step"]]
        for e in entries
        if isinstance(e, dict) and e.get("applied") and e.get("step") in _PREPROCESS_CAPTION
    ]
    return " · ".join(applied) if applied else "preprocessed"


def _pager_selector(images: list[LabelImage], idx: int) -> int:
    """The ``?image=`` selector for the image at list index ``idx``.

    Prefer the DB ``position`` (the natural deep-link), falling back to the 1-based
    ordinal when ``position`` is NULL — so a NULL-position neighbor still gets a working
    link instead of a dead ``?image=None``. The selection loop in ``image_panel`` tries a
    position match first and the ordinal second, so both selector forms resolve."""
    pos = images[idx].position
    return pos if pos is not None else idx + 1


def _image_src(submission_id: int, image_id: int, variant: str = "original") -> str:
    """Build the same-origin URL for the image-serving route (NFR-2: relative path)."""
    base = f"/review/{submission_id}/image/{image_id}"
    return base if variant == "original" else f"{base}?variant={variant}"


def image_panel(
    images: list[LabelImage],
    *,
    submission_id: int,
) -> dict[str, object]:
    """The left-column label-image panel view-model.

    Pure, AR-5-safe. ``images`` is ``repo.list_label_images`` output (already in
    ``position`` order — front, then back, then any others). Returns
    ``{"is_empty": True}`` for a submission with no images (the calm empty state),
    else ``{"is_empty": False, "images": [...], "total": N}`` where each entry carries
    the role WORD + the same-origin original ``<img>`` src/alt.

    EVERY image is returned so the template stacks them all, always visible — no paging,
    no Enhance toggle (the reviewer must never click to see a label). The OpenCV
    preprocessed variants still exist for the OCR engines; they are simply not surfaced
    in the UI."""
    if not images:
        return {"is_empty": True}
    panel_images = []
    for img in images:
        role_word = IMAGE_ROLE_WORD.get(img.image_role or "", "Label image")
        panel_images.append(
            {
                "role_word": role_word,
                "src": _image_src(submission_id, img.id, "original"),
                "alt": f"{role_word} label image",
            }
        )
    return {"is_empty": False, "images": panel_images, "total": len(panel_images)}


# ── Disposition action bar (Story 4.8) ───────────────────────────────────────
# The human-decision register lives in ``app.disposition`` (contract #4) — the ONE
# home for the three values. This presenter renders their controls; it takes NO
# verdict / engine_verdict argument, so there is structurally NO place to map an
# engine verdict onto a disposition or to pre-select a control. The engine
# recommends (the Suggested alert / chips); the specialist records (these buttons).
DISPOSITION_LABEL: dict[str, str] = {
    disposition.APPROVED: "Approve",
    disposition.NEEDS_CORRECTION: "Needs Correction",
    disposition.REJECTED: "Reject",
}
# Disposition controls use ``dispo--*`` classes — NEVER the verdict ``chip--*``
# classes (AR-3 #4). A verdict→disposition class reuse here is a review finding.
DISPOSITION_CSS_CLASS: dict[str, str] = {
    disposition.APPROVED: "dispo--approve",
    disposition.NEEDS_CORRECTION: "dispo--correct",
    disposition.REJECTED: "dispo--reject",
}


def action_bar(*, draft_notes: str | None, has_open_review: bool) -> dict[str, object]:
    """The commit action-bar view-model (Story 4.8 AC1/AC2).

    Returns the three disposition controls in their fixed order
    (``APPROVED`` → ``NEEDS_CORRECTION`` → ``REJECTED``), with NONE pre-selected —
    the engine never makes the call (contract #4 / AR-3 #4). Each control carries its
    human WORD label and its ``dispo--*`` accent class (never a verdict ``chip--*``
    class). ``requires_notes_for`` names the two dispositions whose Notes are
    mandatory (the soft-gate is enforced server-side in the route; this just labels
    the field). ``notes_value`` rehydrates the autosaved draft (never the literal
    "None"). ``has_open_review`` is passed through for the confirm-modal copy."""
    controls = [
        {
            "key": value,
            "label": DISPOSITION_LABEL[value],
            "css_class": DISPOSITION_CSS_CLASS[value],
        }
        for value in disposition.DISPOSITIONS
    ]
    return {
        "controls": controls,
        "requires_notes_for": disposition.NEEDS_NOTES,
        "notes_value": draft_notes or "",
        "has_open_review": has_open_review,
    }


def checklist_has_open(checklist: dict[str, object]) -> bool:
    """Whether the smart-checklist (Story 4.6) still has an un-done row.

    Reuses the already-built :func:`smart_checklist` roll-up (``done_count`` < ``total``)
    so the confirm-modal copy can never disagree with the checklist counter — and we
    never re-walk the rows or re-query. Owns the ``object``→``int`` narrowing at this
    boundary so the route stays type-clean. An empty checklist (``total == 0``) reads as
    no open review. This is advisory copy only — it NEVER blocks the commit (AC2)."""
    done = cast(int, checklist["done_count"])
    total = cast(int, checklist["total"])
    return done < total
