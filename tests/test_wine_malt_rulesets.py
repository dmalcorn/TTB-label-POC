"""Wine & malt-beverage rulesets at full depth (Story 3.8, AC1–AC3).

This story is a DATA-authoring story: the wine and malt-beverage rulesets are
authored as ``Check`` tuples (``app/engine/rulesets/wine.py`` /
``malt_beverage.py``) that point each per-type element at an EXISTING evaluator
(the 3.3–3.7 dispatch seam) — the same deterministic implementations are REUSED
via ruleset data, never re-coded per type (AC3).

Coverage:
  - **AC1** the conditional flag-only element retained for the POC (country of origin)
    exists as a DATA row with its real CFR citation. The formula/ingredient-conditional
    disclosures (sulfites, coloring, FD&C Yellow No. 5, …) were trimmed — see
    docs/tradeoffs-and-limitations.md and the "trimmed" tests below.
  - **AC2** the checklist contents differ correctly by type, end-to-end through
    ``run_checks`` (no ABV demand on a ≤14% table wine; malt ABV conditional;
    spirits-only rows absent from wine/malt; type-specific fields present).
  - **AC3** reuse, not re-code: every wine/malt ``strategy`` resolves to an already
    registered REAL evaluator; no new evaluator module is introduced.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.engine import checks
from app.engine import run_checks as rc
from app.engine.checks import EVALUATORS, placeholder_evaluator
from app.engine.rulesets import get_ruleset
from app.engine.rulesets.malt_beverage import MALT_BEVERAGE_RULESET
from app.engine.rulesets.wine import WINE_RULESET

# ── shared fixtures (mirror tests/test_format_checks.py) ─────────────────────


_DB_SEQ = 0
_TTB_SEQ = 0


def _make_db(tmp_path) -> Path:
    global _DB_SEQ
    _DB_SEQ += 1
    db_path = tmp_path / f"wine_malt_{_DB_SEQ}.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    global _TTB_SEQ
    _TTB_SEQ += 1
    cols = {
        "ttb_id": f"260010000000{_TTB_SEQ:02d}",
        "beverage_type": "WINE",
        "brand_name": "Sunny Valley",
        "alcohol_content": None,
        "net_contents": "750 mL",
        "applicant_name_address": "Sunny Valley Vineyards, Napa, CA",
        "class_type_designation": "Table Wine",
        "status": "PROCESSING",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_label_image(conn: sqlite3.Connection, submission_id: int) -> int:
    cur = conn.execute(
        "INSERT INTO label_images (submission_id, filename, position) VALUES (?, ?, ?)",
        (submission_id, "front.png", 1),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_ocr(
    conn: sqlite3.Connection,
    submission_id: int,
    label_image_id: int,
    text: str,
    *,
    confidence: float = 0.95,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO ocr_results
            (label_image_id, submission_id, engine_name, extracted_text,
             confidence, ran_on_cpu, image_variant, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (label_image_id, submission_id, "tesseract", text, confidence, True, "ORIGINAL", "OK"),
    )
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def _run(tmp_path, ocr_text, **subm) -> tuple[Path, int]:
    """Seed a submission + OCR, run the engine, return (db_path, submission_id)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, **subm)
        img = _insert_label_image(conn, sid)
        if ocr_text is not None:
            _insert_ocr(conn, sid, img, ocr_text)
        submission = repo.get_submission(conn, sid)
        assert submission is not None
        rc.run_checks(conn, submission)
    return db_path, sid


def _checklist(tmp_path, ocr_text, **subm) -> dict[str, str]:
    """{check_key: verdict} for a run-through-the-engine submission."""
    db_path, sid = _run(tmp_path, ocr_text, **subm)
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT check_key, verdict FROM checklist_items WHERE submission_id = ?",
            (sid,),
        ).fetchall()
    return {r["check_key"]: r["verdict"] for r in rows}


# ── wiring: the WINE / MALT rulesets are now non-empty (AC2) ─────────────────


def test_wine_ruleset_is_non_empty():
    assert get_ruleset("WINE") is WINE_RULESET
    assert len(WINE_RULESET) > 0


def test_malt_ruleset_is_non_empty():
    assert get_ruleset("MALT_BEVERAGE") is MALT_BEVERAGE_RULESET
    assert len(MALT_BEVERAGE_RULESET) > 0


def test_unknown_type_still_empty_finalize_dont_abort():
    """An unmapped beverage type still rolls up via the empty-ruleset policy (FR-9)."""
    assert get_ruleset("MEAD_OR_OTHER") == ()


def test_check_keys_unique_within_each_ruleset():
    for ruleset in (WINE_RULESET, MALT_BEVERAGE_RULESET):
        keys = [c.check_key for c in ruleset]
        assert len(keys) == len(set(keys)), f"duplicate check_key in {keys}"


# ── AC3: reuse, not re-code — every strategy is an already-registered evaluator ──


def test_every_wine_strategy_resolves_to_a_real_evaluator():
    """AC3: wine reuses the 3.3–3.7 evaluators — no strategy falls to the placeholder."""
    for check in WINE_RULESET:
        evaluator = checks.get_evaluator(check.strategy)
        assert evaluator is not placeholder_evaluator, (
            f"wine check {check.check_key!r} strategy {check.strategy!r} has no real evaluator"
        )


def test_every_malt_strategy_resolves_to_a_real_evaluator():
    for check in MALT_BEVERAGE_RULESET:
        evaluator = checks.get_evaluator(check.strategy)
        assert evaluator is not placeholder_evaluator, (
            f"malt check {check.check_key!r} strategy {check.strategy!r} has no real evaluator"
        )


def test_no_new_evaluator_strategy_introduced():
    """AC3: every wine/malt strategy is one of the already-registered keys (reuse)."""
    registered = set(EVALUATORS)
    assert {c.strategy for c in WINE_RULESET} <= registered
    assert {c.strategy for c in MALT_BEVERAGE_RULESET} <= registered


# ── AC1: the conditional checks exist as DATA with real per-part citations ────


def _by_key(ruleset) -> dict[str, object]:
    return {c.check_key: c for c in ruleset}


def test_wine_conditional_disclosures_trimmed_to_country_of_origin():
    """POC scope (docs/tradeoffs-and-limitations.md): the formula/ingredient-conditional
    wine disclosures and the §4.72 standards-of-fill flag were removed (no application
    signal to anchor them — they could only emit an un-actionable REVIEW); only country
    of origin, which keys off the import / source-of-product flag, is retained."""
    keys = {c.check_key for c in WINE_RULESET}
    assert "country_of_origin" in keys
    assert keys.isdisjoint(
        {
            "sulfite_declaration",
            "fdc_yellow_5",
            "cochineal_carmine",
            "appellation_of_origin",
            "standards_of_fill",
        }
    )


def test_malt_conditional_disclosures_trimmed_to_country_of_origin():
    """POC scope: malt's §7.63(b) formula/ingredient-conditional disclosures were removed;
    only country of origin (import-anchored) is retained."""
    keys = {c.check_key for c in MALT_BEVERAGE_RULESET}
    assert "country_of_origin" in keys
    assert keys.isdisjoint(
        {"fdc_yellow_5", "cochineal_carmine", "sulfite_declaration", "aspartame_disclosure"}
    )


def test_wine_citations_are_part_4_or_part_16():
    """Wine citations are 27 CFR Part 4 (un-renumbered) / Part 16, or the truthful
    CBP 19 CFR 134.11 for country-of-origin — never a Part 5/7 (spirits/malt) cite."""
    for check in WINE_RULESET:
        # CFR-as-data is recorded truthfully: country-of-origin is CBP-governed
        # (19 CFR 134.11, doc §3), so it is the one legitimate non-27-CFR citation.
        if check.check_key == "country_of_origin":
            assert check.cfr_citation == "19 CFR 134.11"
            continue
        assert check.cfr_citation.startswith("27 CFR ")
        section = check.cfr_citation.removeprefix("27 CFR ")
        assert section.startswith(("4.", "16.")), (
            f"unexpected wine citation {check.cfr_citation!r} on {check.check_key!r}"
        )
        assert not section.startswith(("5.", "7.")), (
            f"wine must not carry a spirits/malt citation: {check.cfr_citation!r}"
        )


def test_malt_citations_are_part_7_or_part_16():
    """Malt citations are 27 CFR Part 7 (post-2022) or Part 16 — never Part 4/5."""
    for check in MALT_BEVERAGE_RULESET:
        assert check.cfr_citation.startswith("27 CFR ")
        section = check.cfr_citation.removeprefix("27 CFR ")
        assert not section.startswith(("4.", "5.")), (
            f"malt must not carry a wine/spirits citation: {check.cfr_citation!r}"
        )


def test_each_check_carries_its_citation_as_data():
    """Citations live on the Check rows (mirrors the spirits ruleset) — never empty."""
    for ruleset in (WINE_RULESET, MALT_BEVERAGE_RULESET):
        for check in ruleset:
            assert check.cfr_citation
            assert check.source_date


# ── AC2: the checklist contents differ correctly by type ─────────────────────


def test_wine_table_wine_without_abv_is_not_failed(tmp_path):
    """AC2 (the trap): a ≤14% table wine with no ABV on the label is NOT failed."""
    verdicts = _checklist(
        tmp_path,
        "SUNNY VALLEY TABLE WINE\n750 mL",
        beverage_type="WINE",
        alcohol_content="12.5% Alc./Vol.",  # ≤14% application value
    )
    assert "abv_format" in verdicts
    assert verdicts["abv_format"] != "FAIL"


def test_malt_beverage_without_abv_is_not_failed(tmp_path):
    """AC2: malt-beverage ABV is conditional — absent ⇒ never FAIL (REVIEW)."""
    verdicts = _checklist(
        tmp_path,
        "HOPPY LAGER\n12 FL OZ",
        beverage_type="MALT_BEVERAGE",
        alcohol_content=None,
        net_contents="12 FL OZ",
        class_type_designation="Lager",
    )
    assert "abv_format" in verdicts
    assert verdicts["abv_format"] != "FAIL"
    assert verdicts["abv_format"] == "REVIEW"


def test_wine_with_incidental_marketing_percent_is_not_failed(tmp_path):
    """AC2 (the trap, closing the incidental-% hole): a ≤14% table wine that omits its
    ABV but prints unrelated marketing copy carrying a ``%`` ("100% Estate Grown") must
    NOT be read as an ABV statement and FAILed for a missing abbreviation. The stray %
    is uncued and the label has no ABV abbreviation word, so ABV is treated as absent
    and the ≤14% wine policy applies ⇒ PASS, never FAIL."""
    verdicts = _checklist(
        tmp_path,
        "SUNNY VALLEY TABLE WINE\n100% ESTATE GROWN\n750 mL",
        beverage_type="WINE",
        alcohol_content="12.5% Alc./Vol.",  # ≤14% application value
    )
    assert "abv_format" in verdicts
    assert verdicts["abv_format"] != "FAIL"
    assert verdicts["abv_format"] == "PASS"


def test_malt_with_incidental_marketing_percent_is_not_failed(tmp_path):
    """AC2 (the trap): a malt beverage that omits its ABV but prints a marketing ``%``
    ("100% Natural") must surface the conditional ABV as REVIEW (optional-unless-trigger),
    never a false missing-abbreviation FAIL from the incidental percentage."""
    verdicts = _checklist(
        tmp_path,
        "HOPPY LAGER\n100% NATURAL\n12 FL OZ",
        beverage_type="MALT_BEVERAGE",
        alcohol_content=None,
        net_contents="12 FL OZ",
        class_type_designation="Lager",
    )
    assert "abv_format" in verdicts
    assert verdicts["abv_format"] != "FAIL"
    assert verdicts["abv_format"] == "REVIEW"


def test_wine_checklist_omits_spirits_only_checks(tmp_path):
    """AC2: wine has no same-field-of-vision, no proof, no §5.203 standards-of-fill."""
    verdicts = _checklist(
        tmp_path,
        "SUNNY VALLEY TABLE WINE\n750 mL",
        beverage_type="WINE",
    )
    assert "same_field_of_vision" not in verdicts
    assert "proof_abv_consistency" not in verdicts
    # wine standards-of-fill is §4.72 flag-REVIEW, not the spirits §5.203 check_key


def test_malt_checklist_omits_spirits_and_wine_only_checks(tmp_path):
    """AC2: malt has no standards-of-fill, no proof, no same-field-of-vision."""
    verdicts = _checklist(
        tmp_path,
        "HOPPY LAGER\n12 FL OZ",
        beverage_type="MALT_BEVERAGE",
        net_contents="12 FL OZ",
    )
    assert "standards_of_fill" not in verdicts
    assert "proof_abv_consistency" not in verdicts
    assert "same_field_of_vision" not in verdicts


def test_wine_has_grape_varietal_field_check():
    """AC2: wine carries a grape_varietal field check; malt + spirits do not."""
    assert "grape_varietal" in {c.check_key for c in WINE_RULESET}
    assert "grape_varietal" not in {c.check_key for c in MALT_BEVERAGE_RULESET}


def test_malt_has_fanciful_name_field_check():
    """AC2: malt carries a fanciful_name field check; wine references it differently."""
    assert "fanciful_name" in {c.check_key for c in MALT_BEVERAGE_RULESET}


def test_government_warning_present_in_both_types():
    """Part 16 applies to all beverage types ≥0.5% ABV — gov warning is reused."""
    for ruleset in (WINE_RULESET, MALT_BEVERAGE_RULESET):
        by_key = _by_key(ruleset)
        assert "government_warning" in by_key
        assert by_key["government_warning"].cfr_citation == "27 CFR 16.21"
        assert by_key["government_warning"].strategy == "government_warning"


def test_conditional_flag_only_check_routes_to_review_with_citation(tmp_path):
    """AC1+AC3: the retained flag-only row (country of origin) produces a REVIEW (deferred),
    reusing the positional strategy, with its citation carried as DATA."""
    db_path, sid = _run(
        tmp_path,
        "SUNNY VALLEY\nPRODUCT OF FRANCE\n750 mL",
        beverage_type="WINE",
    )
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT verdict, cfr_citation FROM checklist_items "
            "WHERE submission_id = ? AND check_key = 'country_of_origin'",
            (sid,),
        ).fetchone()
    assert row is not None
    assert row["verdict"] == "REVIEW"
    assert row["cfr_citation"] == "19 CFR 134.11"


def test_run_checks_writes_one_row_per_wine_check(tmp_path):
    """End-to-end: every wine Check yields exactly one checklist_items row."""
    db_path, sid = _run(tmp_path, "SUNNY VALLEY TABLE WINE\n750 mL", beverage_type="WINE")
    with connect(db_path) as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM checklist_items WHERE submission_id = ?", (sid,)
        ).fetchone()["n"]
    assert n == len(WINE_RULESET)


# ── purity: the ruleset modules are DATA-only (mirror distilled_spirits.py) ──


def test_ruleset_modules_have_no_evaluator_imports():
    """The data modules import NOTHING from the engine evaluators — pure data."""
    import ast

    for module in ("app/engine/rulesets/wine.py", "app/engine/rulesets/malt_beverage.py"):
        source = Path(module).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported += [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        for mod in imported:
            assert "engine.checks" not in mod, f"{module} imports an evaluator: {mod!r}"
            assert "run_checks" not in mod, f"{module} imports the executor: {mod!r}"
