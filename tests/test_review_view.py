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


def _ocr_blob_cmp(field_key: str, application_value: str, blob: str, cmp_id: int = 10):
    """An OCR-fallback comparison: extracted_value is the WHOLE label blob, sourced from
    an OCR row (no LLM) — the case the card must isolate down to this field's snippet."""
    return FieldComparison(
        id=cmp_id,
        submission_id=1,
        field_key=field_key,
        application_value=application_value,
        extracted_value=blob,
        match_status="MATCH",
        similarity=1.0,
        source_ocr_result_id=7,  # OCR-sourced ...
        source_llm_result_id=None,  # ... not LLM ⇒ extracted_value is the whole blob
        extracted_source="ocr:tesseract",
        created_at="2026-06-14T00:00:00Z",
    )


def test_field_cards_ocr_fallback_isolates_text_field_not_whole_blob():
    """OCR-only fallback stores the WHOLE label OCR blob as a field's extracted_value;
    the card must show just this field's located snippet, never the entire label dump."""
    blob = (
        "OLD TOM DISTILLERY\nKentucky Straight Bourbon Whiskey\n"
        "45% Alc./Vol. (90 Proof)\n750 mL\n"
        "GOVERNMENT WARNING: According to the Surgeon General..."
    )
    card = review_view.field_cards(
        [_item("brand_name", "PASS", item_id=1, field_comparison_id=10)],
        [_ocr_blob_cmp("brand_name", "Old Tom Distillery", blob)],
    )[0]
    ev = card["extracted_value"] or ""
    assert ev == "OLD TOM DISTILLERY"  # the located field value, not the dump
    assert "GOVERNMENT WARNING" not in ev
    assert "\n" not in ev  # not the multi-line blob


def test_field_cards_ocr_fallback_isolates_numeric_line_by_unit():
    """A numeric field isolates the matching-unit line — net_contents shows the mL line,
    not the % ABV line elsewhere in the blob."""
    blob = "OLD TOM DISTILLERY\n45% Alc./Vol. (90 Proof)\n750 mL"
    card = review_view.field_cards(
        [_item("net_contents", "PASS", item_id=1, field_comparison_id=10)],
        [_ocr_blob_cmp("net_contents", "750 mL", blob)],
    )[0]
    ev = card["extracted_value"] or ""
    assert "750" in ev
    assert "Alc" not in ev  # not the ABV line


def test_field_cards_numeric_isolates_value_sharing_a_line_with_other_units():
    """ABV shares ONE OCR line with net contents + proof (the BLACK SHEEP line). The ABV
    card must still show that line — not "(not found)" — even though the ml/proof tokens
    come first on the line (parse_all_numeric, not first-token-only)."""
    blob = "BLACK SHEEP\n750ml! / 151 Proof / Alc. 75.5% by Vol.\nCORN WHISKEY"
    card = review_view.field_cards(
        [_item("alcohol_content", "PASS", item_id=1, field_comparison_id=10)],
        [_ocr_blob_cmp("alcohol_content", "75.5% Alc./Vol.", blob)],
    )[0]
    ev = card["extracted_value"] or ""
    assert "75.5%" in ev


def test_field_cards_llm_sourced_value_shown_verbatim():
    """An LLM-sourced (structured) per-field value is already isolated — show as-is."""
    cmp_llm = FieldComparison(
        id=10,
        submission_id=1,
        field_key="brand_name",
        application_value="Old Tom Distillery",
        extracted_value="Old Tom Distillery",
        match_status="MATCH",
        similarity=1.0,
        source_ocr_result_id=None,
        source_llm_result_id=3,
        extracted_source="llm:gpt-4o-mini",
        created_at="2026-06-14T00:00:00Z",
    )
    card = review_view.field_cards(
        [_item("brand_name", "PASS", item_id=1, field_comparison_id=10)], [cmp_llm]
    )[0]
    assert card["extracted_value"] == "Old Tom Distillery"


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


def test_field_cards_dangling_comparison_surfaces_error_card_not_silent_drop():
    """A field_comparison_id pointing at no comparison row is a check that couldn't
    complete — surface a visible honest ERROR card (Story 4.11 AC2), never a silent
    drop. The card carries the engine REVIEW register (never a guessed PASS/FAIL),
    is flagged a problem, and shows the plain "couldn't be completed" note."""
    items = [_item("brand_name", "PASS", item_id=1, field_comparison_id=999)]
    cards = review_view.field_cards(items, [])
    assert len(cards) == 1
    card = cards[0]
    assert card["state"] == "error"
    assert card["field_key"] == "brand_name"
    assert card["is_problem"] is True
    assert card["verdict"] == verdict.REVIEW
    assert card["note"] == review_view._CHECK_ERROR_NOTE
    # an honest error draws no fabricated char-diff
    assert card["diff_application"] is None
    assert card["diff_extracted"] is None


def test_field_cards_dangling_comparison_keeps_sibling_clean_cards():
    """The other checks still render when one check errored (AC2: 'Other checks still shown')."""
    items = [
        _item("brand_name", "PASS", item_id=1, field_comparison_id=10),
        _item("alcohol_content", "PASS", item_id=2, field_comparison_id=999),
    ]
    comparisons = [_cmp("brand_name", cmp_id=10)]
    cards = review_view.field_cards(items, comparisons)
    by_key = {c["field_key"]: c for c in cards}
    assert by_key["brand_name"]["state"] == "match"
    assert by_key["alcohol_content"]["state"] == "error"


# ── LLM-unavailable degrade notice (Story 4.11 AC3) ──────────────────────────


def test_llm_notice_degraded_carries_experience_copy():
    notice = review_view.llm_notice(True)
    assert notice is not None
    assert notice["text"] == "LLM check unavailable — showing OCR result"


def test_llm_notice_not_degraded_is_none():
    assert review_view.llm_notice(False) is None


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


def test_state_mismatch_shows_plain_values_no_diff():
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
    # NO character-level redline — the two values are shown verbatim for eyeball compare.
    assert card["diff_application"] is None
    assert card["diff_extracted"] is None
    assert card["application_value"] == "Stone's Throw"
    assert card["extracted_value"] == "Stoned Throw"


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
    # no redline markup — the plain note + values carry it
    assert card["diff_application"] is None
    assert card["diff_extracted"] is None


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
    # no redline markup — the note + the two plain values convey the near-miss
    assert card["diff_application"] is None
    assert card["diff_extracted"] is None


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


def test_differ_states_show_plain_values_no_diff_equivalent():
    """The differ states (soft / near_miss / mismatch) no longer draw a char-diff or its
    screen-reader equivalent — the two raw values are shown verbatim for eyeball compare."""
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
        assert card["diff_text_equivalent"] is None
        assert card["diff_application"] is None
        # the raw values are shown verbatim instead of a redline
        assert card["application_value"] == app_val
        assert card["extracted_value"] == ext_val


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


# ── Government Warning comparison card (Story 4.5) ────────────────────────────
# The card reads the single ``government_warning`` checklist row and parses its
# engine-written JSON ``detail`` payload (outcome discriminator). It is NOT a
# field_comparisons card. The presenter dispatches on the stored outcome and
# renders the engine's already-computed char-diff opcodes (pure render, AR-5).

import json  # noqa: E402  (kept local to the gov-warning block for readability)

_GW_CITATION = "27 CFR 16.21"


def _gw_item(detail: str | None, vdt: str, *, cfr_citation: str | None = _GW_CITATION):
    """A ``government_warning`` checklist row (no field_comparison_id — it is not a
    field card; the 'required' side is the §16.21 statute in the engine payload)."""
    return _item(
        "government_warning",
        vdt,
        check_type="MANUAL",
        item_id=99,
        field_comparison_id=None,
        label="Government Warning",
        cfr_citation=cfr_citation,
        detail=detail,
    )


def _pass_detail() -> str:
    return json.dumps({"outcome": "pass", "cfr_citation": _GW_CITATION})


def _reworded_detail() -> str:
    # The engine's _char_diff emits (op, segment); JSON round-trips tuples as
    # 2-element lists. A ``replace`` segment is "<expected>\u2192<found>".
    return json.dumps(
        {
            "outcome": "reworded",
            "deviation": "header casing: expected 'GOVERNMENT WARNING:'",
            "expected": "GOVERNMENT WARNING: text",
            "found": "Government Warning: text",
            "diff": [
                ["replace", "GOVERNMENT WARNING\u2192Government Warning"],
                ["equal", ": text"],
            ],
            "cfr_citation": _GW_CITATION,
        }
    )


def _absent_detail() -> str:
    return json.dumps(
        {
            "outcome": "absent",
            "message": "Government Warning not found on any label",
            "cfr_citation": _GW_CITATION,
        }
    )


def _couldnt_verify_detail() -> str:
    return json.dumps(
        {
            "outcome": "couldnt_verify",
            "message": "couldn't verify bold/visual styling from a photo",
            "cfr_citation": _GW_CITATION,
        }
    )


def test_gov_warning_card_none_when_no_row():
    """No government_warning checklist row ⇒ None (template renders honest empty)."""
    items = [_item("brand_name", "PASS", field_comparison_id=10)]
    assert review_view.government_warning_card(items) is None


def test_gov_warning_card_pass_quiet_no_diff():
    card = review_view.government_warning_card([_gw_item(_pass_detail(), "PASS")])
    assert card is not None
    assert card["verdict"] == verdict.PASS
    assert card["chip_class"] == "chip--pass"
    assert card["chip_word"] == "PASS"
    assert card["outcome"] == "pass"
    assert card["diff_required"] is None
    assert card["diff_onlabel"] is None
    # A compliant pass draws no diff/stack, but carries a plain confirmation note so the
    # card is not a bare green chip (the on-label warning matched the required statement).
    assert card["note"] == review_view._GW_PASS_NOTE
    assert "matches" in card["note"].lower()


def test_gov_warning_card_reworded_fail_shows_plain_required_and_onlabel():
    card = review_view.government_warning_card([_gw_item(_reworded_detail(), "FAIL")])
    assert card is not None
    assert card["verdict"] == verdict.FAIL
    assert card["chip_class"] == "chip--fail"
    assert card["chip_word"] == "FAIL"
    assert card["outcome"] == "reworded"
    # The required §16.21 text and the OCR'd on-label text are carried verbatim — NO redline.
    assert card["required_text"] == "GOVERNMENT WARNING: text"
    assert card["onlabel_text"] == "Government Warning: text"
    assert card["diff_required"] is None
    assert card["diff_onlabel"] is None
    assert card["diff_text_equivalent"] is None


def test_gov_warning_card_absent_fail_plain_no_diff():
    card = review_view.government_warning_card([_gw_item(_absent_detail(), "FAIL")])
    assert card is not None
    assert card["verdict"] == verdict.FAIL
    assert card["chip_word"] == "FAIL"
    assert card["outcome"] == "absent"
    assert card["diff_required"] is None
    assert card["diff_onlabel"] is None
    assert card["required_text"] is None
    assert card["onlabel_text"] is None
    assert card["note"] == "Required Government Warning not found on the submitted images"


def test_gov_warning_card_couldnt_verify_review_no_diff():
    card = review_view.government_warning_card([_gw_item(_couldnt_verify_detail(), "REVIEW")])
    assert card is not None
    assert card["verdict"] == verdict.REVIEW
    assert card["chip_class"] == "chip--review"
    assert card["chip_word"] == "REVIEW"
    assert card["outcome"] == "couldnt_verify"
    assert card["diff_required"] is None
    assert card["diff_onlabel"] is None
    assert card["note"]
    assert "verify" in card["note"].lower()


def test_gov_warning_card_malformed_detail_degrades_to_review():
    """A non-JSON / garbled detail degrades to a REVIEW card — no crash, no silent PASS."""
    card = review_view.government_warning_card([_gw_item("not-json{", "FAIL")])
    assert card is not None
    # Honest degrade: never a silent PASS; renders the couldn't-verify-style REVIEW.
    assert card["verdict"] == verdict.REVIEW
    assert card["outcome"] == "couldnt_verify"
    assert card["diff_required"] is None


def test_gov_warning_card_none_detail_degrades_to_review():
    card = review_view.government_warning_card([_gw_item(None, "FAIL")])
    assert card is not None
    assert card["verdict"] == verdict.REVIEW
    assert card["outcome"] == "couldnt_verify"


def test_gov_warning_card_cfr_from_row_then_payload_fallback():
    # Row carries the citation (ruleset data) ⇒ used directly.
    card = review_view.government_warning_card([_gw_item(_pass_detail(), "PASS")])
    assert card["cfr_citation"] == _GW_CITATION
    # Row citation null ⇒ fall back to the payload's cfr_citation.
    card2 = review_view.government_warning_card(
        [_gw_item(_pass_detail(), "PASS", cfr_citation=None)]
    )
    assert card2["cfr_citation"] == _GW_CITATION


def test_gov_warning_card_emit_no_disposition_word():
    card = review_view.government_warning_card([_gw_item(_reworded_detail(), "FAIL")])
    blob = " ".join(str(v) for v in card.values()).lower()
    for disposition in ("approved", "needs_correction", "rejected", "needs correction"):
        assert disposition not in blob


def test_gov_warning_card_unknown_outcome_degrades_to_review():
    """An UNKNOWN outcome on a valid dict is ambiguous ⇒ fail-safe REVIEW, never a
    silent PASS (matches the codebase's ambiguity⇒REVIEW rule)."""
    detail = json.dumps({"outcome": "some_future_outcome", "cfr_citation": _GW_CITATION})
    card = review_view.government_warning_card([_gw_item(detail, "FAIL")])
    assert card is not None
    assert card["verdict"] == verdict.REVIEW
    assert card["outcome"] == "couldnt_verify"
    assert card["diff_required"] is None
    assert card["note"]


def test_gov_warning_card_missing_outcome_key_degrades_to_review():
    """A valid dict with NO ``outcome`` key degrades to REVIEW — never the quiet PASS."""
    detail = json.dumps({"cfr_citation": _GW_CITATION})
    card = review_view.government_warning_card([_gw_item(detail, "FAIL")])
    assert card is not None
    assert card["verdict"] == verdict.REVIEW
    assert card["outcome"] == "couldnt_verify"


def test_gov_warning_card_pass_carries_no_stack_text():
    """The quiet pass card carries NO required/on-label text — the engine persists none
    for a pass, so the template draws no empty mono stack (AR-5: no OCR re-read)."""
    card = review_view.government_warning_card([_gw_item(_pass_detail(), "PASS")])
    assert card is not None
    assert card["outcome"] == "pass"
    assert card["required_text"] is None
    assert card["onlabel_text"] is None
    assert card["diff_required"] is None
    assert card["diff_onlabel"] is None


def test_gov_warning_template_has_no_cfr_literal():
    """CFR citations come from data — no ``27 CFR`` literal in the gov-warning markup
    (AC4: the grep guard covers the templates, not only the presenter). Jinja comments
    are stripped at render, so the production markup must carry no literal at all."""
    for tpl in ("templates/_gov_warning_card.html", "templates/review.html"):
        src = (REPO_ROOT / tpl).read_text(encoding="utf-8")
        assert "27 CFR" not in src, f"{tpl} must not hard-code a CFR citation (CFR-as-data)"


# ── Smart checklist presenter (Story 4.6) ────────────────────────────────────
# `smart_checklist` turns the SAME `checklist_items` rows into the per-type
# table-of-contents: one row per check, pre-ticking auto-PASS/NA (muted `done`),
# highlighting REVIEW (`open`) / FAIL (`openfail`), promoting a manually-ticked
# REVIEW/FAIL to `usercheck`, and counting "N of M done" over the merged set
# (auto ∪ manual). Pure read-model, AR-5-safe (no OCR/LLM/engine import).


def _ck(check_key: str, vdt: str, *, check_type: str = "FIELD_MATCH", item_id: int = 1):
    return _item(check_key, vdt, check_type=check_type, item_id=item_id)


def test_smart_checklist_header_type_word_title_cased():
    vm = review_view.smart_checklist(
        [_ck("brand_name", "PASS")], beverage_type="DISTILLED_SPIRITS", decisions={}
    )
    # Header word is title-cased (mockup "Distilled Spirits"), NOT the all-caps banner.
    assert vm["type_word"] == "Distilled Spirits"


def test_smart_checklist_one_row_per_item_in_id_order():
    items = [
        _ck("brand_name", "PASS", item_id=1),
        _ck("alcohol_content", "REVIEW", item_id=2),
        _ck("net_contents", "FAIL", item_id=3),
    ]
    vm = review_view.smart_checklist(items, beverage_type="WINE", decisions={})
    assert [r["check_key"] for r in vm["rows"]] == ["brand_name", "alcohol_content", "net_contents"]
    assert vm["total"] == 3


def test_smart_checklist_match_pre_selects_pass_decided():
    vm = review_view.smart_checklist(
        [_ck("brand_name", "PASS")], beverage_type="WINE", decisions={}
    )
    row = vm["rows"][0]
    assert row["decision"] == "pass"  # a Match pre-selects Pass
    assert row["decided"] is True
    assert row["is_problem"] is False
    assert row["chip_word"] == "PASS"


def test_smart_checklist_na_pre_selects_pass_decided():
    vm = review_view.smart_checklist(
        [_ck("standards_of_fill", "NA")], beverage_type="WINE", decisions={}
    )
    row = vm["rows"][0]
    assert row["decision"] == "pass"
    assert row["decided"] is True
    assert row["is_problem"] is False


def test_smart_checklist_na_renders_own_word_and_check_icon_not_review_failsafe():
    """Regression: an NA row is a muted auto-tick (state=done), so the template
    renders ``icon  chip_word  machine_tag``. NA must carry its OWN word/icon —
    without them it inherited the REVIEW fail-safe and read "! REVIEW auto",
    wrongly flagging a not-applicable check as a problem (AC2)."""
    vm = review_view.smart_checklist(
        [_ck("standards_of_fill", "NA")], beverage_type="WINE", decisions={}
    )
    row = vm["rows"][0]
    assert row["chip_word"] == "N/A"
    assert row["icon"] == "\u2713"  # ✓ (the auto-verified check, NOT "!")


def test_smart_checklist_review_undecided_is_open_problem():
    vm = review_view.smart_checklist(
        [_ck("alcohol_content", "REVIEW")], beverage_type="WINE", decisions={}
    )
    row = vm["rows"][0]
    assert row["decision"] == ""
    assert row["decided"] is False
    assert row["is_problem"] is True
    assert row["chip_word"] == "REVIEW"


def test_smart_checklist_fail_undecided_is_problem():
    vm = review_view.smart_checklist(
        [_ck("net_contents", "FAIL")], beverage_type="WINE", decisions={}
    )
    row = vm["rows"][0]
    assert row["decision"] == ""
    assert row["decided"] is False
    assert row["is_problem"] is True
    assert row["chip_word"] == "FAIL"


def test_smart_checklist_review_decided_pass():
    vm = review_view.smart_checklist(
        [_ck("alcohol_content", "REVIEW")],
        beverage_type="WINE",
        decisions={"alcohol_content": "pass"},
    )
    row = vm["rows"][0]
    assert row["decision"] == "pass"
    assert row["decided"] is True


def test_smart_checklist_match_can_be_overridden_to_fail():
    vm = review_view.smart_checklist(
        [_ck("brand_name", "PASS")],
        beverage_type="WINE",
        decisions={"brand_name": "fail"},
    )
    row = vm["rows"][0]
    assert row["decision"] == "fail"
    assert row["decided"] is True


def test_smart_checklist_fail_decided_fail():
    vm = review_view.smart_checklist(
        [_ck("net_contents", "FAIL")],
        beverage_type="WINE",
        decisions={"net_contents": "fail"},
    )
    row = vm["rows"][0]
    assert row["decision"] == "fail"
    assert row["decided"] is True


def test_smart_checklist_done_count_counts_decided():
    items = [
        _ck("brand_name", "PASS", item_id=1),  # match → pre-pass (decided)
        _ck("class_type_designation", "NA", item_id=2),  # NA → pre-pass (decided)
        _ck("alcohol_content", "REVIEW", item_id=3),  # explicit pass (decided)
        _ck("net_contents", "FAIL", item_id=4),  # undecided
    ]
    vm = review_view.smart_checklist(
        items, beverage_type="WINE", decisions={"alcohol_content": "pass"}
    )
    # 2 pre-pass matches + 1 explicit = 3 decided of 4.
    assert vm["done_count"] == 3
    assert vm["total"] == 4


def test_smart_checklist_explicit_pass_on_match_not_double_counted():
    """An explicit Pass on an already-pre-passed Match must not inflate the count."""
    items = [_ck("brand_name", "PASS", item_id=1), _ck("net_contents", "FAIL", item_id=2)]
    vm = review_view.smart_checklist(items, beverage_type="WINE", decisions={"brand_name": "pass"})
    assert vm["done_count"] == 1
    assert vm["total"] == 2


def test_smart_checklist_empty_is_zero_of_zero():
    vm = review_view.smart_checklist([], beverage_type="WINE", decisions={})
    assert vm["rows"] == []
    assert vm["done_count"] == 0
    assert vm["total"] == 0


def test_smart_checklist_anchor_maps_identity_to_group_anchor():
    vm = review_view.smart_checklist(
        [_ck("brand_name", "PASS")], beverage_type="WINE", decisions={}
    )
    assert vm["rows"][0]["anchor"] == "group-identity"


def test_smart_checklist_anchor_maps_gov_warning():
    vm = review_view.smart_checklist(
        [_ck("government_warning", "FAIL", check_type="DETERMINISTIC")],
        beverage_type="WINE",
        decisions={},
    )
    assert vm["rows"][0]["anchor"] == "group-gov-warning"


def test_smart_checklist_anchor_conditional_for_unmapped_manual():
    vm = review_view.smart_checklist(
        [_ck("allergen_disclosure", "REVIEW", check_type="MANUAL")],
        beverage_type="WINE",
        decisions={},
    )
    assert vm["rows"][0]["anchor"] == "group-conditional"


def test_smart_checklist_unknown_verdict_treated_as_problem_not_muted():
    """Fail-safe: an unmapped/garbled verdict renders as a problem (open), never a
    silent muted done (carry 4.5's ambiguity⇒REVIEW instinct)."""
    vm = review_view.smart_checklist([_ck("brand_name", "WAT")], beverage_type="WINE", decisions={})
    row = vm["rows"][0]
    assert row["decided"] is False
    assert row["is_problem"] is True
    assert row["decision"] == ""


def test_smart_checklist_unknown_beverage_type_degrades_word():
    vm = review_view.smart_checklist(
        [_ck("brand_name", "PASS")], beverage_type="CIDER", decisions={}
    )
    # Unknown type still yields a word (title-cased), never blank / crash.
    assert vm["type_word"] == "Cider"


def test_smart_checklist_emits_no_disposition_word():
    items = [_ck("net_contents", "FAIL")]
    vm = review_view.smart_checklist(items, beverage_type="WINE", decisions={})
    blob = " ".join(str(v) for v in vm["rows"][0].values()).lower()
    for disposition in ("approved", "needs_correction", "rejected", "needs correction"):
        assert disposition not in blob


def test_smart_checklist_reuses_chip_class_and_icon():
    vm = review_view.smart_checklist(
        [
            _ck("brand_name", "PASS", item_id=1),
            _ck("alcohol_content", "REVIEW", item_id=2),
            _ck("net_contents", "FAIL", item_id=3),
        ],
        beverage_type="WINE",
        decisions={},
    )
    by_key = {r["check_key"]: r for r in vm["rows"]}
    assert by_key["brand_name"]["chip_class"] == "chip--pass"
    assert by_key["alcohol_content"]["chip_class"] == "chip--review"
    assert by_key["net_contents"]["chip_class"] == "chip--fail"
    assert by_key["brand_name"]["icon"] == "\u2713"
    assert by_key["net_contents"]["icon"] == "\u2717"


# ── Disposition action bar (Story 4.8) ───────────────────────────────────────


def test_action_bar_three_controls_none_selected():
    vm = review_view.action_bar(draft_notes=None, has_open_review=False)
    keys = [c["key"] for c in vm["controls"]]
    assert keys == ["APPROVED", "NEEDS_CORRECTION", "REJECTED"]
    # None of the three controls is pre-selected / defaulted (AC1 / contract #4).
    assert all(not c.get("selected", False) for c in vm["controls"])


def test_action_bar_uses_dispo_classes_never_verdict_classes():
    vm = review_view.action_bar(draft_notes=None, has_open_review=False)
    classes = {c["key"]: c["css_class"] for c in vm["controls"]}
    assert classes["APPROVED"] == "dispo--approve"
    assert classes["NEEDS_CORRECTION"] == "dispo--correct"
    assert classes["REJECTED"] == "dispo--reject"
    # No verdict (chip--/usa-alert--) class ever leaks onto a disposition control.
    for c in vm["controls"]:
        blob = " ".join(str(v) for v in c.values())
        assert "chip--" not in blob
        assert "usa-alert--" not in blob


def test_action_bar_emits_no_verdict_to_disposition_mapping():
    # The view-model takes NO verdict/engine_verdict argument — there is no place to
    # map a verdict onto a disposition. Whatever the engine verdict, the controls are
    # identical + none-selected.
    a = review_view.action_bar(draft_notes=None, has_open_review=False)
    b = review_view.action_bar(draft_notes=None, has_open_review=True)
    assert [c["key"] for c in a["controls"]] == [c["key"] for c in b["controls"]]
    assert all(not c.get("selected", False) for c in a["controls"])
    assert all(not c.get("selected", False) for c in b["controls"])


def test_action_bar_requires_notes_for_correct_and_reject_only():
    vm = review_view.action_bar(draft_notes=None, has_open_review=False)
    assert "NEEDS_CORRECTION" in vm["requires_notes_for"]
    assert "REJECTED" in vm["requires_notes_for"]
    assert "APPROVED" not in vm["requires_notes_for"]


def test_action_bar_rehydrates_draft_notes():
    vm = review_view.action_bar(draft_notes="reset the heading to all caps", has_open_review=False)
    assert vm["notes_value"] == "reset the heading to all caps"
    # No draft ⇒ empty string (a textarea pre-fill, never the literal "None").
    blank = review_view.action_bar(draft_notes=None, has_open_review=False)
    assert blank["notes_value"] == ""


def test_action_bar_has_open_review_passthrough():
    assert review_view.action_bar(draft_notes=None, has_open_review=True)["has_open_review"] is True
    assert (
        review_view.action_bar(draft_notes=None, has_open_review=False)["has_open_review"] is False
    )


def test_action_bar_emits_no_disposition_is_not_a_verdict_word():
    # The controls carry the human disposition WORDS — but never an engine verdict
    # word (PASS/REVIEW/FAIL) as a control label (those belong to the chips).
    vm = review_view.action_bar(draft_notes=None, has_open_review=False)
    labels = {c["label"] for c in vm["controls"]}
    assert labels == {"Approve", "Needs Correction", "Reject"}
