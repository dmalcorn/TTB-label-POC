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

from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import cast

from app import verdict
from app.db.repositories import ChecklistItem, FieldComparison

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


def field_cards(
    items: Iterable[ChecklistItem], comparisons: Iterable[FieldComparison]
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

    cards: list[dict[str, object]] = []
    for item in items:
        if item.field_comparison_id is None:
            continue
        comparison = by_id.get(item.field_comparison_id)
        if comparison is None:
            continue

        vdt = item.verdict or verdict.REVIEW
        state = _derive_state(item, comparison)

        note: str | None = None
        diff_application: list[dict[str, str]] | None = None
        diff_extracted: list[dict[str, str]] | None = None
        diff_text_equivalent: str | None = None
        # A char-diff is drawn for the three "differs" states; its color follows the
        # VERDICT (FAIL ⇒ red del/ins; REVIEW ⇒ amber soft) so a REVIEW never paints
        # red. Whenever a diff is drawn we ALSO emit a screen-reader text equivalent
        # naming the difference (A11Y hard requirement — the diff is never a colored
        # span alone; this string survives forced-colors mode).
        if state in ("soft", "near_miss", "mismatch"):
            note = {"soft": _SOFT_NOTE, "near_miss": _NEAR_MISS_NOTE}.get(state)
            diff_application, diff_extracted = _char_diff(
                comparison.application_value or "",
                comparison.extracted_value or "",
                soft=(vdt != verdict.FAIL),
            )
            diff_text_equivalent = _diff_text_equivalent(
                comparison.application_value, comparison.extracted_value
            )
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
                "extracted_value": comparison.extracted_value,
                "extracted_source": comparison.extracted_source,
                "detail": item.detail,
                "diff_application": diff_application,
                "diff_extracted": diff_extracted,
                "diff_text_equivalent": diff_text_equivalent,
                "note": note,
                "is_problem": vdt != verdict.PASS,
                "sort_rank": _SORT_RANK.get(vdt, 1),
            }
        )

    cards.sort(key=lambda c: cast(int, c["sort_rank"]))  # stable: ties keep id (ruleset) order
    return cards
