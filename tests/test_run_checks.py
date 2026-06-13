"""Compliance-engine executor + rulesets-as-data tests (Story 3.2, AC1–AC5).

Offline, fast, deterministic — no real OCR/LLM, no scheduler. The executor and
its dispatch seam are exercised directly against an in-memory-style temp DB, and
the pipeline integration reuses the ``run.STAGES`` seam patterns from
``tests/test_pipeline.py`` so the whole suite runs under
``docker run --network none`` with zero native deps.

Scope guard (3.2): only the FRAMEWORK + spirits DATA + the honest ``REVIEW``
placeholder evaluator are tested here. The real per-strategy evaluators are
Stories 3.3–3.7; this file must NOT assert real field-match / Government-Warning
logic.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db.connection import connect, init_db
from app.engine import run_checks as rc
from app.engine.rulesets import Check, get_ruleset
from app.engine.rulesets.base import CheckType

# ── shared fixtures (mirror tests/test_pipeline.py helpers) ──────────────────


def _make_db(tmp_path) -> Path:
    db_path = tmp_path / "engine.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26001000000001",
        "beverage_type": "DISTILLED_SPIRITS",
        "brand_name": "Stone's Throw",
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


def _checklist_rows(conn: sqlite3.Connection, submission_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM checklist_items WHERE submission_id = ? ORDER BY id",
        (submission_id,),
    ).fetchall()


# ── Task 1 / AC1: rulesets are DATA ──────────────────────────────────────────

_VALID_CHECK_TYPES = {"DETERMINISTIC", "FIELD_MATCH", "HYBRID", "MANUAL"}


def test_distilled_spirits_ruleset_is_data_with_real_citations():
    """AC1: the spirits ruleset enumerates the always-mandatory elements + the
    Government Warning + the same-field-of-vision check, each a data row with a
    non-empty check_key, a valid check_type, a "27 CFR …" citation, and a
    source_date."""
    ruleset = get_ruleset("DISTILLED_SPIRITS")
    assert len(ruleset) >= 7  # brand, class/type, abv, net, name/addr, gov warning, sfov

    keys = {c.check_key for c in ruleset}
    # The always-mandatory spirits elements + Gov Warning + same-field-of-vision.
    assert {
        "brand_name",
        "class_type_designation",
        "alcohol_content",
        "net_contents",
        "name_address",
        "government_warning",
        "same_field_of_vision",
    } <= keys

    for c in ruleset:
        assert isinstance(c, Check)
        assert c.check_key and c.check_key.islower()  # snake_case identifier
        assert c.check_type in _VALID_CHECK_TYPES
        assert c.cfr_citation.startswith("27 CFR ")
        assert c.source_date  # the date the citation was current (post-2022 reorg)
        assert c.label  # human-readable label for the UI
        assert c.strategy  # which evaluator handles it


def test_government_warning_is_deterministic_and_sfov_is_manual():
    """AC1: determinism classes are carried as DATA — the Government Warning is
    DETERMINISTIC (never an LLM), and the positional same-field-of-vision check is
    MANUAL (flag-REVIEW)."""
    by_key = {c.check_key: c for c in get_ruleset("DISTILLED_SPIRITS")}
    assert by_key["government_warning"].check_type == "DETERMINISTIC"
    assert by_key["same_field_of_vision"].check_type == "MANUAL"
    # Post-2022 renumbering: class/type lives at §5.141, not the old §5.35.
    assert "5.141" in by_key["class_type_designation"].cfr_citation
    assert by_key["government_warning"].cfr_citation == "27 CFR 16.21"


def test_wine_and_malt_rulesets_are_empty_until_story_3_8():
    """AC1 / Task 1: spirits is authored at depth now; wine/malt are the Story 3.8
    sentinel — an empty ruleset (a submission with no checks rolls up to REVIEW)."""
    assert get_ruleset("WINE") == ()
    assert get_ruleset("MALT_BEVERAGE") == ()


def test_get_ruleset_unknown_type_is_empty_not_an_error():
    """An unknown beverage type must resolve to an empty ruleset (finalize-don't-
    abort), never raise."""
    assert get_ruleset("MEAD") == ()


def test_check_is_frozen_pure_data():
    """The Check dataclass is frozen (immutable pure data — no logic, no mutation)."""
    c = get_ruleset("DISTILLED_SPIRITS")[0]
    with pytest.raises((AttributeError, TypeError)):
        c.check_key = "mutated"  # type: ignore[misc]


def test_check_type_alias_matches_db_enum():
    """The CheckType Literal mirrors the checklist_items.check_type CHECK enum exactly."""
    import typing

    assert set(typing.get_args(CheckType)) == _VALID_CHECK_TYPES


# ── Task 2 / AC2 / AC3: the executor writes one provenance row per Check ──────


def test_run_checks_writes_one_row_per_check_with_provenance(tmp_path):
    """AC2/AC3: the executor writes exactly one checklist_items row per Check, each
    carrying the Check's provenance verbatim (check_key, check_type, cfr_citation),
    a per-check verdict, and a detail."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        submission = _get_submission(conn, sid)
        result = rc.run_checks(conn, submission)
        conn.commit()
        rows = _checklist_rows(conn, sid)

    ruleset = get_ruleset("DISTILLED_SPIRITS")
    assert len(rows) == len(ruleset)  # exactly one row per Check
    by_key = {r["check_key"]: r for r in rows}
    for check in ruleset:
        row = by_key[check.check_key]
        assert row["cfr_citation"] == check.cfr_citation  # citation as DATA, off the Check
        assert row["check_type"] == check.check_type
        assert row["label"] == check.label
        assert row["verdict"] in {"PASS", "REVIEW", "FAIL", "NA"}
        assert row["detail"]  # an advisory note is recorded
    # With only placeholder (REVIEW) evaluators, the submission rolls up to REVIEW.
    assert result == "REVIEW"


def test_run_checks_sets_engine_verdict_equal_to_rollup(tmp_path):
    """AC2: engine_verdict on the submission equals verdict.rollup over the per-check
    verdicts (the single centralized roll-up — engine & UI can never disagree)."""
    from app import verdict

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        submission = _get_submission(conn, sid)
        rc.run_checks(conn, submission)
        conn.commit()
        rows = _checklist_rows(conn, sid)
        stored = _get_submission(conn, sid).engine_verdict

    expected = verdict.rollup([r["verdict"] for r in rows])
    assert stored == expected == "REVIEW"


def test_run_checks_empty_ruleset_rolls_up_to_review(tmp_path):
    """AC2 / Task 2: an empty ruleset (WINE/MALT until Story 3.8) writes no rows and
    rolls up to REVIEW (rollup's empty policy — never a silent auto-PASS)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, beverage_type="WINE", ttb_id="26001000000099")
        submission = _get_submission(conn, sid)
        result = rc.run_checks(conn, submission)
        conn.commit()
        rows = _checklist_rows(conn, sid)
        stored = _get_submission(conn, sid).engine_verdict

    assert rows == []
    assert result == "REVIEW"
    assert stored == "REVIEW"


def test_run_checks_is_idempotent_delete_then_insert(tmp_path):
    """Task 2: running twice does NOT duplicate rows — a re-run replaces the prior
    checklist (delete-then-insert)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        submission = _get_submission(conn, sid)
        rc.run_checks(conn, submission)
        conn.commit()
        first = len(_checklist_rows(conn, sid))
        rc.run_checks(conn, submission)
        conn.commit()
        second = len(_checklist_rows(conn, sid))

    assert first == second == len(get_ruleset("DISTILLED_SPIRITS"))


def test_run_checks_unknown_strategy_degrades_to_review_not_raise(tmp_path):
    """Task 3: a Check whose strategy is unregistered resolves to the honest REVIEW
    placeholder, never raising (finalize-don't-abort, FR-9)."""
    from app.engine.rulesets.base import Check

    bogus = Check(
        check_key="made_up_check",
        label="Made up",
        check_type="DETERMINISTIC",
        cfr_citation="27 CFR 5.999",
        source_date="2022-01-08",
        strategy="not_a_registered_strategy",
    )
    from app.engine import checks

    ctx = checks.CheckContext(conn=None, submission=None)  # placeholder ignores both
    result = checks.get_evaluator(bogus.strategy)(bogus, ctx)
    assert result.verdict == "REVIEW"


def test_run_checks_records_model_id_provenance_for_llm_checks(tmp_path, monkeypatch):
    """AC3: for an LLM-assisted check, the executor folds the model identification
    into the row's detail provenance."""
    from app.engine import checks

    def model_eval(check, ctx):
        return checks.CheckResult(verdict="REVIEW", detail="class/type judged", model_id="fake-1")

    monkeypatch.setitem(checks.EVALUATORS, "class_type", model_eval)

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        submission = _get_submission(conn, sid)
        rc.run_checks(conn, submission)
        conn.commit()
        row = conn.execute(
            "SELECT detail FROM checklist_items WHERE submission_id = ? AND check_key = ?",
            (sid, "class_type_designation"),
        ).fetchone()

    assert "model=fake-1" in row["detail"]


def test_engine_stage_persist_failure_rolls_back_and_preserves_prior_checklist(
    tmp_path, monkeypatch
):
    """Regression (code review): a persist failure mid-``run_checks`` must NOT corrupt
    the submission's checklist.

    ``run_checks`` is a delete-then-insert unit with no inner commit, so a mid-loop
    failure leaves the DELETE + partial INSERTs pending; if ``engine_stage`` did not
    roll back, the next pipeline commit (``status.record_event``) would FLUSH that
    partial transaction — wiping the prior complete checklist. This forces a
    CHECK-violating verdict (⇒ ``sqlite3.IntegrityError``) on one Check after a clean
    run, then asserts ``engine_stage`` (a) does not raise (finalize-don't-abort, FR-9)
    and (b) leaves the prior checklist + ``engine_verdict`` intact (rolled back).
    """
    from app.engine import checks
    from app.pipeline.run import StageContext

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        submission = _get_submission(conn, sid)

        # 1) A clean run writes the full, valid checklist (all placeholder REVIEW).
        rc.run_checks(conn, submission)
        conn.commit()
        good_count = len(_checklist_rows(conn, sid))
        good_verdict = _get_submission(conn, sid).engine_verdict
        assert good_count == len(get_ruleset("DISTILLED_SPIRITS"))
        assert good_verdict == "REVIEW"

        # 2) Register an evaluator that returns an ILLEGAL verdict for one strategy —
        #    the INSERT trips the verdict CHECK constraint ⇒ IntegrityError mid-loop.
        def bad_eval(check, ctx):
            return checks.CheckResult(verdict="NOT_A_VERDICT", detail="boom")

        monkeypatch.setitem(checks.EVALUATORS, "government_warning", bad_eval)

        # 3) engine_stage must swallow the failure (not raise) AND roll back.
        ctx = StageContext(conn=conn, submission=submission, label_images=[])
        engine_did_raise = False
        try:
            rc.engine_stage(ctx)
        except Exception:  # noqa: BLE001 — the whole point is it must NOT propagate
            engine_did_raise = True

        # Simulate the very next pipeline step committing the connection (status.py
        # commits per step) — the flush that WOULD persist a partial txn if
        # engine_stage had not rolled back.
        conn.commit()

        after_rows = _checklist_rows(conn, sid)
        after_verdict = _get_submission(conn, sid).engine_verdict

    assert engine_did_raise is False  # finalize-don't-abort: the stage self-guards
    # The prior good checklist survived intact — the failed run was rolled back, not
    # half-committed (no DELETE-without-reinsert corruption).
    assert len(after_rows) == good_count
    assert after_verdict == good_verdict


def test_engine_never_imports_disposition():
    """project-context "Recommend, don't decide": the engine modules must NOT import
    disposition (no ``import disposition`` / ``from app.disposition``), so there can
    be no verdict → disposition mapping. (An explanatory docstring may name the
    prohibition; only an actual import is a finding.)"""
    import re

    import app.engine.checks as checks_mod
    import app.engine.run_checks as rc_mod

    # Match real import statements only, not prose mentions of the word.
    import_re = re.compile(
        r"^\s*(?:from\s+\S*disposition\S*\s+import|import\s+\S*disposition)", re.M
    )
    for mod in (rc_mod, checks_mod):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert not import_re.search(src), f"engine module imports disposition: {mod.__file__}"


# ── AC4: CFR citations live ONLY as ruleset data ─────────────────────────────


def test_cfr_citations_appear_only_in_ruleset_data_not_in_logic():
    """AC4: a structural guard — the "27 CFR" literal appears only in ruleset data
    modules (+ tests), never in executor/evaluator logic. A grep for "27 CFR" in
    run_checks.py / checks/__init__.py is a finding."""
    import app.engine.checks as checks_mod
    import app.engine.run_checks as rc_mod

    for mod in (rc_mod, checks_mod):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "27 CFR" not in src, f"CFR citation literal leaked into logic: {mod.__file__}"


def test_every_spirits_check_key_is_registered_in_data_dictionary():
    """project-context "stable identifiers": every check_key the engine writes MUST
    resolve to an entry in docs/data-dictionary.md (the §6.2.1 registry). A new ruleset
    Check with no dictionary entry is a finding — the dictionary is the single index."""
    dd = Path(__file__).resolve().parents[1] / "docs" / "data-dictionary.md"
    text = dd.read_text(encoding="utf-8")
    for check in get_ruleset("DISTILLED_SPIRITS"):
        # The registry lists each key in a backticked table cell `<key>`.
        assert f"`{check.check_key}`" in text, (
            f"check_key {check.check_key!r} is not registered in {dd}"
        )


def _get_submission(conn, sid):
    from app.db import repositories as repo

    return repo.get_submission(conn, sid)
