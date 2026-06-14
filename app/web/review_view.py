"""Review Workspace shell presenter (Story 4.3).

Pure, read-only view-model builders that turn a submission's beverage type + its
``checklist_items`` into the three orienting shell elements rendered by
``templates/review.html``:

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

from app import verdict
from app.db.repositories import ChecklistItem

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
