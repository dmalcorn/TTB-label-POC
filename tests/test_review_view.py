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
from app.db.repositories import ChecklistItem, FieldComparison
from app.web import review_view

REPO_ROOT = Path(__file__).resolve().parents[1]


def _item(
    check_key: str,
    vdt: str,
    *,
    check_type: str = "FIELD_MATCH",
    item_id: int = 1,
    field_comparison_id: int | None = None,
    label: str | None = None,
    cfr_citation: str | None = "27 CFR 5.64",
    detail: str | None = None,
) -> ChecklistItem:
    return ChecklistItem(
        id=item_id,
        submission_id=1,
        check_key=check_key,
        label=label if label is not None else check_key.replace("_", " ").title(),
        cfr_citation=cfr_citation,
        check_type=check_type,
        verdict=vdt,
        detail=detail,
        field_comparison_id=field_comparison_id,
        created_at="2026-06-14T00:00:00Z",
    )


def _cmp(
    field_key: str,
    *,
    cmp_id: int = 1,
    application_value: str | None = "Stone's Throw",
    extracted_value: str | None = "Stone's Throw",
    match_status: str | None = "MATCH",
    similarity: float | None = 1.0,
    extracted_source: str | None = "ocr:tesseract",
) -> FieldComparison:
    return FieldComparison(
        id=cmp_id,
        submission_id=1,
        field_key=field_key,
        application_value=application_value,
        extracted_value=extracted_value,
        match_status=match_status,
        similarity=similarity,
        source_ocr_result_id=None,
        source_llm_result_id=None,
        extracted_source=extracted_source,
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


# ── Field comparison cards (Story 4.4) ───────────────────────────────────────


def test_field_cards_join_pairs_checklist_to_comparison():
    items = [_item("brand_name", "PASS", item_id=1, field_comparison_id=10)]
    comparisons = [_cmp("brand_name", cmp_id=10)]
    cards = review_view.field_cards(items, comparisons)
    assert len(cards) == 1
    assert cards[0]["field_key"] == "brand_name"
    assert cards[0]["application_value"] == "Stone's Throw"
    assert cards[0]["extracted_value"] == "Stone's Throw"


def test_field_cards_excludes_rows_without_comparison_id():
    """Gov Warning / flag-only checks (no field_comparison_id) are NOT field cards."""
    items = [
        _item("brand_name", "PASS", item_id=1, field_comparison_id=10),
        _item("government_warning", "PASS", check_type="DETERMINISTIC", item_id=2),
        _item("same_field_of_vision", "REVIEW", check_type="MANUAL", item_id=3),
    ]
    comparisons = [_cmp("brand_name", cmp_id=10)]
    cards = review_view.field_cards(items, comparisons)
    assert [c["field_key"] for c in cards] == ["brand_name"]


def test_field_cards_excludes_row_whose_comparison_is_missing():
    """A field_comparison_id pointing at no comparison row produces no card (defensive)."""
    items = [_item("brand_name", "PASS", item_id=1, field_comparison_id=999)]
    cards = review_view.field_cards(items, [])
    assert cards == []


# ── State derivation ─────────────────────────────────────────────────────────


def test_state_match():
    items = [_item("brand_name", "PASS", field_comparison_id=10)]
    comparisons = [_cmp("brand_name", cmp_id=10, match_status="MATCH")]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["state"] == "match"
    assert card["verdict"] == verdict.PASS
    assert card["chip_word"] == "match"
    assert card["icon"]
    assert card["chip_class"] == "chip--pass"
    # quiet match draws no diff
    assert card["diff_application"] is None
    assert card["diff_extracted"] is None


def test_state_mismatch_has_red_char_diff():
    items = [_item("brand_name", "FAIL", field_comparison_id=10, detail="values differ")]
    comparisons = [
        _cmp(
            "brand_name",
            cmp_id=10,
            application_value="Stone's Throw",
            extracted_value="Stoned Throw",
            match_status="MISMATCH",
            similarity=0.7,
        )
    ]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["state"] == "mismatch"
    assert card["verdict"] == verdict.FAIL
    assert card["chip_class"] == "chip--fail"
    # char diff present on both sides, marking only the differing span
    assert card["diff_application"] is not None
    assert card["diff_extracted"] is not None
    kinds = {seg["kind"] for seg in card["diff_application"]}
    assert "equal" in kinds  # the common span is preserved
    assert any(seg["kind"] == "del" for seg in card["diff_application"])
    # no soft-kind segment in a hard mismatch
    assert all(seg["kind"] != "soft" for seg in card["diff_application"])


def test_state_soft_is_amber_never_red():
    items = [_item("brand_name", "REVIEW", field_comparison_id=10)]
    comparisons = [
        _cmp(
            "brand_name",
            cmp_id=10,
            application_value="Stone's Throw",
            extracted_value="STONE'S THROW",
            match_status="MATCH",
            similarity=0.95,
        )
    ]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["state"] == "soft"
    assert card["verdict"] == verdict.REVIEW
    assert card["chip_class"] == "chip--review"
    assert card["note"] == "Capitalization differs; the text otherwise matches."
    # soft diff uses the amber `soft` kind, never the red `del`/`ins`
    kinds = {seg["kind"] for seg in card["diff_application"]}
    assert "soft" in kinds
    assert "del" not in kinds and "ins" not in kinds


def test_state_not_found_is_review_no_diff():
    items = [_item("wine_appellation", "REVIEW", field_comparison_id=10)]
    comparisons = [
        _cmp(
            "wine_appellation",
            cmp_id=10,
            application_value="Napa Valley",
            extracted_value=None,
            match_status="MISSING",
            similarity=None,
            extracted_source=None,
        )
    ]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["state"] == "not_found"
    assert card["verdict"] == verdict.REVIEW
    assert card["note"] == "Not found on label"
    assert card["diff_application"] is None
    assert card["diff_extracted"] is None


def test_state_not_found_keeps_engine_fail_when_mandatory():
    """A MISSING mandatory element the engine ruled FAIL stays FAIL (verdict from engine)."""
    items = [_item("alcohol_content", "FAIL", field_comparison_id=10)]
    comparisons = [
        _cmp(
            "alcohol_content",
            cmp_id=10,
            application_value="45% Alc./Vol.",
            extracted_value=None,
            match_status="MISSING",
            similarity=None,
            extracted_source=None,
        )
    ]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["state"] == "not_found"
    assert card["verdict"] == verdict.FAIL  # never downgraded — engine owns the verdict


def test_state_unreadable_is_review_no_diff():
    items = [_item("net_contents", "REVIEW", field_comparison_id=10)]
    comparisons = [
        _cmp(
            "net_contents",
            cmp_id=10,
            application_value="750 mL",
            extracted_value="7!iO m|_",
            match_status="UNVERIFIABLE",
            similarity=None,
        )
    ]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["state"] == "unreadable"
    assert card["verdict"] == verdict.REVIEW
    assert card["note"] == (
        "Couldn't read this field reliably from the photo — please verify by eye."
    )
    # garbage rendered as a diff would wrongly imply the label is wrong — so no diff
    assert card["diff_application"] is None
    assert card["diff_extracted"] is None


def test_state_blank_application_is_review_no_diff():
    items = [_item("fanciful_name", "REVIEW", field_comparison_id=10)]
    comparisons = [
        _cmp(
            "fanciful_name",
            cmp_id=10,
            application_value="",
            extracted_value="Old Reserve",
            match_status="MISMATCH",
            similarity=None,
        )
    ]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["state"] == "blank_application"
    assert card["verdict"] == verdict.REVIEW
    assert card["note"] == "No value submitted in the application for this field."
    assert card["diff_application"] is None
    assert card["diff_extracted"] is None


def test_state_near_miss_is_amber_diff_not_soft_capitalization():
    """A MISMATCH the engine ruled REVIEW (a near-miss ≥ the review floor — e.g.
    ``field_match`` returns MISMATCH+REVIEW for a real-but-close textual difference)
    must render as ``near_miss``: a char-diff shown in AMBER (the soft kind, never
    red del/ins) with the honest "verify by eye" note — NOT the false
    "Capitalization differs" soft note. Regression for ``_derive_state`` treating
    verdict REVIEW as a synonym for the cosmetic soft case (F1)."""
    items = [_item("brand_name", "REVIEW", field_comparison_id=10)]
    comparisons = [
        _cmp(
            "brand_name",
            cmp_id=10,
            application_value="Stone's Throw",
            extracted_value="Stones Throw",
            match_status="MISMATCH",
            similarity=0.9,
        )
    ]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["state"] == "near_miss"
    assert card["verdict"] == verdict.REVIEW
    assert card["chip_class"] == "chip--review"
    # the note must NOT falsely claim a capitalization-only difference
    assert card["note"] != "Capitalization differs; the text otherwise matches."
    assert card["note"] == "The values are close but not identical — please verify by eye."
    # a real diff is shown, but amber (soft kind) — a REVIEW never paints red
    assert card["diff_application"] is not None
    kinds = {seg["kind"] for seg in card["diff_application"]}
    assert "soft" in kinds
    assert "del" not in kinds and "ins" not in kinds


def test_state_low_confidence_match_review_identical_raw_is_unreadable_no_phantom_diff():
    """The low-OCR-confidence safety valve: ``field_match`` softens a clean MATCH to
    REVIEW WITHOUT changing the text (identical raw values). There is no character
    difference to show, so the card must degrade to ``unreadable`` (honest "verify by
    eye", no diff) — NOT a false ``soft`` with a phantom diff that highlights nothing.
    Regression for F1 (MATCH+REVIEW assumed to always be a capitalization diff)."""
    items = [_item("net_contents", "REVIEW", field_comparison_id=10)]
    comparisons = [
        _cmp(
            "net_contents",
            cmp_id=10,
            application_value="750 mL",
            extracted_value="750 mL",  # identical raw — low-confidence downgrade
            match_status="MATCH",
            similarity=0.6,
        )
    ]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["state"] == "unreadable"
    assert card["verdict"] == verdict.REVIEW
    assert card["note"] == (
        "Couldn't read this field reliably from the photo — please verify by eye."
    )
    # no phantom diff that would highlight nothing
    assert card["diff_application"] is None
    assert card["diff_extracted"] is None


# ── A11Y: char-diff screen-reader text equivalent (F2) ───────────────────────


def test_diff_text_equivalent_present_for_each_diff_state():
    """Whenever a char-diff is drawn (soft / near_miss / mismatch), the card must
    carry a plain-language screen-reader text equivalent naming WHICH value differs —
    the diff is never conveyed by a colored span alone (A11Y hard requirement, F2).
    It names both raw strings so it also survives forced-colors mode."""
    cases = [
        # (verdict, match_status, application, extracted, expected_state)
        ("REVIEW", "MATCH", "Stone's Throw", "STONE'S THROW", "soft"),
        ("REVIEW", "MISMATCH", "Stone's Throw", "Stones Throw", "near_miss"),
        ("FAIL", "MISMATCH", "Stone's Throw", "Stoned Throw", "mismatch"),
    ]
    for vdt, status, app_val, ext_val, expected_state in cases:
        items = [_item("brand_name", vdt, field_comparison_id=10)]
        comparisons = [
            _cmp(
                "brand_name",
                cmp_id=10,
                application_value=app_val,
                extracted_value=ext_val,
                match_status=status,
                similarity=0.9,
            )
        ]
        card = review_view.field_cards(items, comparisons)[0]
        assert card["state"] == expected_state
        eq = card["diff_text_equivalent"]
        assert eq is not None, f"{expected_state} must carry a diff text equivalent"
        # names BOTH raw values so the difference is legible without color
        assert app_val in eq
        assert ext_val in eq


def test_diff_text_equivalent_absent_when_no_diff_drawn():
    """States that draw no diff (match / not_found / unreadable / blank_application)
    must NOT carry a diff text equivalent — it would be a screen-reader phantom."""
    # quiet match
    items = [_item("brand_name", "PASS", field_comparison_id=10)]
    comparisons = [_cmp("brand_name", cmp_id=10, match_status="MATCH")]
    assert review_view.field_cards(items, comparisons)[0]["diff_text_equivalent"] is None
    # not_found
    items = [_item("wine_appellation", "REVIEW", field_comparison_id=10)]
    comparisons = [
        _cmp(
            "wine_appellation",
            cmp_id=10,
            application_value="Napa Valley",
            extracted_value=None,
            match_status="MISSING",
            similarity=None,
            extracted_source=None,
        )
    ]
    assert review_view.field_cards(items, comparisons)[0]["diff_text_equivalent"] is None


# ── Label, citation, provenance flow-through ─────────────────────────────────


def test_field_label_comes_from_checklist_label():
    items = [_item("brand_name", "PASS", field_comparison_id=10, label="Brand Name")]
    comparisons = [_cmp("brand_name", cmp_id=10)]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["field_label"] == "Brand Name"


def test_field_label_falls_back_to_titleized_field_key():
    items = [_item("net_contents", "PASS", field_comparison_id=10, label=None)]
    comparisons = [_cmp("net_contents", cmp_id=10)]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["field_label"] == "Net Contents"


def test_cfr_citation_and_detail_and_source_flow_through():
    items = [
        _item(
            "brand_name",
            "PASS",
            field_comparison_id=10,
            cfr_citation="27 CFR 5.63",
            detail="Application 'Stone's Throw' matches label.",
        )
    ]
    comparisons = [_cmp("brand_name", cmp_id=10, extracted_source="llm:claude-opus-4")]
    card = review_view.field_cards(items, comparisons)[0]
    assert card["cfr_citation"] == "27 CFR 5.63"
    assert card["detail"] == "Application 'Stone's Throw' matches label."
    assert card["extracted_source"] == "llm:claude-opus-4"


# ── Sort — problems first ────────────────────────────────────────────────────


def test_field_cards_sort_floats_problems_first():
    items = [
        _item("brand_name", "PASS", item_id=1, field_comparison_id=10),
        _item("alcohol_content", "FAIL", item_id=2, field_comparison_id=20),
        _item("net_contents", "REVIEW", item_id=3, field_comparison_id=30),
        _item("class_type_designation", "PASS", item_id=4, field_comparison_id=40),
    ]
    comparisons = [
        _cmp("brand_name", cmp_id=10, match_status="MATCH"),
        _cmp(
            "alcohol_content",
            cmp_id=20,
            match_status="MISMATCH",
            application_value="45",
            extracted_value="40",
        ),
        _cmp(
            "net_contents",
            cmp_id=30,
            match_status="MATCH",
            application_value="750 mL",
            extracted_value="750 ML",
        ),
        _cmp("class_type_designation", cmp_id=40, match_status="MATCH"),
    ]
    cards = review_view.field_cards(items, comparisons)
    verdicts = [c["verdict"] for c in cards]
    # FAIL first, then REVIEW, then the two PASSes (stable tie-break = id order)
    assert verdicts == [verdict.FAIL, verdict.REVIEW, verdict.PASS, verdict.PASS]
    assert [c["field_key"] for c in cards][:2] == ["alcohol_content", "net_contents"]
    # stable tie-break: brand_name (id 10) before class_type_designation (id 40)
    assert [c["field_key"] for c in cards][2:] == ["brand_name", "class_type_designation"]


def test_field_cards_problem_flag_marks_non_pass():
    items = [
        _item("brand_name", "PASS", item_id=1, field_comparison_id=10),
        _item("alcohol_content", "FAIL", item_id=2, field_comparison_id=20),
    ]
    comparisons = [
        _cmp("brand_name", cmp_id=10),
        _cmp(
            "alcohol_content",
            cmp_id=20,
            match_status="MISMATCH",
            application_value="45",
            extracted_value="40",
        ),
    ]
    cards = review_view.field_cards(items, comparisons)
    by_key = {c["field_key"]: c for c in cards}
    assert by_key["alcohol_content"]["is_problem"] is True
    assert by_key["brand_name"]["is_problem"] is False


# ── AR-5 source guard ────────────────────────────────────────────────────────


def test_review_view_imports_no_heavy_work():
    """The presenter is a pure read-model — no OCR / LLM / engine-run import (AR-5)."""
    src = (REPO_ROOT / "app/web/review_view.py").read_text(encoding="utf-8")
    for forbidden in ("run_checks", "adapters.ocr", "adapters.llm", "pipeline.run", "pytesseract"):
        assert forbidden not in src, f"review_view must not import {forbidden!r} (AR-5)"


def test_review_view_has_no_cfr_literal():
    """CFR citations come from checklist data, never a literal in the presenter."""
    src = (REPO_ROOT / "app/web/review_view.py").read_text(encoding="utf-8")
    assert "27 CFR" not in src, "review_view must not hard-code a CFR citation (CFR-as-data)"


def test_field_cards_emit_no_disposition_word():
    items = [_item("brand_name", "PASS", field_comparison_id=10)]
    comparisons = [_cmp("brand_name", cmp_id=10)]
    card = review_view.field_cards(items, comparisons)[0]
    blob = " ".join(str(v) for v in card.values()).lower()
    for disposition in ("approved", "needs_correction", "rejected", "needs correction"):
        assert disposition not in blob
