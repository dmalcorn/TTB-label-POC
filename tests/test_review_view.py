"""Story 4.3 — Review Workspace shell presenter (``app/web/review_view.py``).

Pure view-model tests for the three shell elements:

- the beverage-type banner (word + accent class per type, unknown-type degrade);
- the chevron / step indicator (Conditional step ④ appears ONLY when a
  conditional/flag-only check is present, and the remaining steps renumber cleanly —
  Decide is ⑤ with Conditional, ④ without);
- the suggested-verdict alert (advisory roll-up via the centralized
  ``app/verdict.py:rollup``; icon + word; never a disposition).

Plus an AR-5 source guard: the presenter imports no OCR/LLM/engine-run symbol.
"""

from __future__ import annotations

from pathlib import Path

from app import verdict
from app.db.repositories import ChecklistItem
from app.web import review_view

REPO_ROOT = Path(__file__).resolve().parents[1]


def _item(
    check_key: str, vdt: str, *, check_type: str = "FIELD_MATCH", item_id: int = 1
) -> ChecklistItem:
    return ChecklistItem(
        id=item_id,
        submission_id=1,
        check_key=check_key,
        label=check_key.replace("_", " ").title(),
        cfr_citation="27 CFR 5.64",
        check_type=check_type,
        verdict=vdt,
        detail=None,
        created_at="2026-06-14T00:00:00Z",
    )


# ── Banner ───────────────────────────────────────────────────────────────────


def test_banner_spirits_word_and_accent():
    b = review_view.banner("DISTILLED_SPIRITS")
    assert b["word"] == "DISTILLED SPIRITS"
    assert b["accent_class"] == "beverage-banner--spirits"


def test_banner_wine_word_and_accent():
    b = review_view.banner("WINE")
    assert b["word"] == "WINE"
    assert b["accent_class"] == "beverage-banner--wine"


def test_banner_beer_word_and_accent():
    b = review_view.banner("MALT_BEVERAGE")
    assert b["word"] == "BEER"
    assert b["accent_class"] == "beverage-banner--beer"


def test_banner_unknown_type_degrades_without_raising():
    b = review_view.banner("CIDER")
    # word still present (never blank); no accent class applied
    assert b["word"]
    assert b["accent_class"] == ""


# ── Chevron ──────────────────────────────────────────────────────────────────


def test_chevron_without_conditional_has_four_steps_decide_is_fourth():
    items = [
        _item("brand_name", "PASS", item_id=1),
        _item("alcohol_content", "PASS", item_id=2),
        _item("government_warning", "FAIL", check_type="DETERMINISTIC", item_id=3),
    ]
    steps = review_view.chevron(items)
    labels = [s["label"] for s in steps]
    assert labels == ["Identity", "Mandatory text", "Gov. Warning", "Decide"]
    assert "Conditional" not in labels
    decide = next(s for s in steps if s["label"] == "Decide")
    assert decide["number"] == 4
    # anchors are the stable section ids the template/later stories target
    assert [s["anchor"] for s in steps] == [
        "group-identity",
        "group-mandatory-text",
        "group-gov-warning",
        "group-decide",
    ]


def test_chevron_with_conditional_renumbers_decide_to_five():
    items = [
        _item("brand_name", "PASS", item_id=1),
        _item("government_warning", "PASS", check_type="DETERMINISTIC", item_id=2),
        # a flag-only / positional conditional check (Story 3.7/3.8)
        _item("same_field_of_vision", "REVIEW", check_type="MANUAL", item_id=3),
    ]
    steps = review_view.chevron(items)
    labels = [s["label"] for s in steps]
    assert labels == ["Identity", "Mandatory text", "Gov. Warning", "Conditional", "Decide"]
    cond = next(s for s in steps if s["label"] == "Conditional")
    decide = next(s for s in steps if s["label"] == "Decide")
    assert cond["number"] == 4
    assert decide["number"] == 5


def test_chevron_wine_identity_fields_do_not_trigger_conditional():
    """A wine checklist's always-present FIELD_MATCH identity row (grape_varietal)
    must NOT surface the Conditional step on its own. Regression for the membership-
    only ``_is_conditional`` that showed Conditional unconditionally for wine/malt
    (AC3 — Conditional appears ONLY when triggered)."""
    items = [
        _item("brand_name", "PASS", item_id=1),
        _item("class_type_designation", "PASS", item_id=2),
        _item("grape_varietal", "PASS", item_id=3),  # FIELD_MATCH, not in CHECK_KEY_STEP pre-fix
        _item("alcohol_content", "PASS", item_id=4),
        _item("government_warning", "PASS", check_type="DETERMINISTIC", item_id=5),
    ]
    steps = review_view.chevron(items)
    labels = [s["label"] for s in steps]
    assert "Conditional" not in labels
    assert labels == ["Identity", "Mandatory text", "Gov. Warning", "Decide"]


def test_chevron_malt_fanciful_name_does_not_trigger_conditional():
    """A malt checklist's always-present FIELD_MATCH ``fanciful_name`` identity row
    must not, by itself, surface the Conditional step (AC3)."""
    items = [
        _item("brand_name", "PASS", item_id=1),
        _item("fanciful_name", "PASS", item_id=2),  # FIELD_MATCH, not in CHECK_KEY_STEP pre-fix
        _item("government_warning", "PASS", check_type="DETERMINISTIC", item_id=3),
    ]
    steps = review_view.chevron(items)
    assert "Conditional" not in [s["label"] for s in steps]


def test_chevron_manual_disclosure_triggers_conditional():
    """A genuine §4/§7 MANUAL flag-only disclosure (e.g. sulfite_declaration) DOES
    surface the Conditional step — the discriminator is ``check_type == "MANUAL"``,
    not bare map-absence."""
    items = [
        _item("brand_name", "PASS", item_id=1),
        _item("sulfite_declaration", "REVIEW", check_type="MANUAL", item_id=2),
    ]
    steps = review_view.chevron(items)
    assert "Conditional" in [s["label"] for s in steps]


def test_chevron_unmapped_non_manual_check_does_not_trigger_conditional():
    """An unmapped check that is NOT MANUAL (a future FIELD_MATCH/DETERMINISTIC key
    not yet added to CHECK_KEY_STEP) must NOT inflate the Conditional step — only
    MANUAL disclosures do (rules-as-data drift guard)."""
    items = [
        _item("brand_name", "PASS", item_id=1),
        _item("some_future_field", "PASS", check_type="FIELD_MATCH", item_id=2),
    ]
    steps = review_view.chevron(items)
    assert "Conditional" not in [s["label"] for s in steps]


def test_chevron_marks_a_single_current_step():
    items = [_item("brand_name", "PASS")]
    steps = review_view.chevron(items)
    current = [s for s in steps if s.get("is_current")]
    assert len(current) == 1
    assert current[0]["label"] == "Identity"


def test_chevron_empty_checklist_still_has_core_steps_no_conditional():
    steps = review_view.chevron([])
    labels = [s["label"] for s in steps]
    assert labels == ["Identity", "Mandatory text", "Gov. Warning", "Decide"]


# ── Suggested-verdict alert ──────────────────────────────────────────────────


def test_suggested_verdict_all_pass():
    items = [_item("brand_name", "PASS", item_id=1), _item("net_contents", "PASS", item_id=2)]
    a = review_view.suggested_verdict(items)
    assert a["verdict"] == verdict.PASS
    assert a["alert_class"] == "usa-alert--success"
    assert a["total"] == 2
    assert a["passed"] == 2
    assert a["needs_review"] == 0
    assert a["icon"]
    # authority returns to the human
    assert "you decide" in a["summary"].lower()


def test_suggested_verdict_any_fail_wins():
    items = [
        _item("brand_name", "PASS", item_id=1),
        _item("government_warning", "FAIL", check_type="DETERMINISTIC", item_id=2),
        _item("net_contents", "REVIEW", item_id=3),
    ]
    a = review_view.suggested_verdict(items)
    assert a["verdict"] == verdict.FAIL
    assert a["alert_class"] == "usa-alert--error"
    assert a["passed"] == 1
    assert a["needs_review"] == 2


def test_suggested_verdict_any_review_when_no_fail():
    items = [_item("brand_name", "PASS", item_id=1), _item("net_contents", "REVIEW", item_id=2)]
    a = review_view.suggested_verdict(items)
    assert a["verdict"] == verdict.REVIEW
    assert a["alert_class"] == "usa-alert--warning"
    assert a["passed"] == 1
    assert a["needs_review"] == 1


def test_suggested_verdict_empty_checklist_is_review_not_pass():
    a = review_view.suggested_verdict([])
    assert a["verdict"] == verdict.REVIEW
    assert a["total"] == 0
    assert a["passed"] == 0
    # honest copy — nothing was auto-verified, never a silent PASS
    assert "auto" in a["summary"].lower() or "verified" in a["summary"].lower()


def test_suggested_verdict_na_items_excluded_from_counts():
    items = [
        _item("brand_name", "PASS", item_id=1),
        _item("wine_appellation", "NA", check_type="MANUAL", item_id=2),
    ]
    a = review_view.suggested_verdict(items)
    # NA is not scored — total counts only scored items
    assert a["total"] == 1
    assert a["passed"] == 1
    assert a["verdict"] == verdict.PASS


def test_suggested_verdict_matches_centralized_rollup():
    items = [
        _item("brand_name", "PASS", item_id=1),
        _item("net_contents", "REVIEW", item_id=2),
        _item("government_warning", "FAIL", check_type="DETERMINISTIC", item_id=3),
    ]
    a = review_view.suggested_verdict(items)
    assert a["verdict"] == verdict.rollup(i.verdict for i in items)


def test_suggested_verdict_never_emits_a_disposition_word():
    items = [_item("brand_name", "PASS")]
    a = review_view.suggested_verdict(items)
    blob = " ".join(str(v) for v in a.values()).lower()
    for disposition in ("approved", "needs_correction", "rejected", "needs correction"):
        assert disposition not in blob


# ── AR-5 source guard ────────────────────────────────────────────────────────


def test_review_view_imports_no_heavy_work():
    """The presenter is a pure read-model — no OCR / LLM / engine-run import (AR-5)."""
    src = (REPO_ROOT / "app/web/review_view.py").read_text(encoding="utf-8")
    for forbidden in ("run_checks", "adapters.ocr", "adapters.llm", "pipeline.run", "pytesseract"):
        assert forbidden not in src, f"review_view must not import {forbidden!r} (AR-5)"
