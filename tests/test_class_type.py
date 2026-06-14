"""Hybrid class/type designation check (Story 3.6, AC1-AC4).

The ONE place an LLM touches a verdict in the whole POC — so the guardrails are the
test's spine:
  - **recognized** designation        → deterministic **PASS**, NO model call (AC1)
  - **cross-label conflict**           → deterministic **FAIL**, both cited (AC3)
  - **ambiguous + model ON**           → VLM escalation, capped **REVIEW**, image-only (AC2)
  - **ambiguous + model OFF**          → rules-only **REVIEW** (AC4)

Offline by construction: a spy/fake ``ModelAdapter`` is injected via the
``checks.class_type.get_llm_adapter`` seam; OCR text is seeded. No real provider, no
network. VLM-only is asserted behaviorally: the fake records its ``run`` calls so a
test can assert (a) the deterministic paths NEVER call the model and (b) the escalation
hands the model an IMAGE and an OCR-free prompt.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import verdict
from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.engine import checks
from app.engine import run_checks as rc
from app.engine.checks import CheckContext
from app.engine.checks import class_type as ct
from app.engine.rulesets import Check
from app.engine.rulesets import class_type as ct_data

# ── shared fixtures (mirror tests/test_government_warning.py) ─────────────────

_DB_SEQ = 0
_TTB_SEQ = 0


def _make_db(tmp_path) -> Path:
    global _DB_SEQ
    _DB_SEQ += 1
    db_path = tmp_path / f"class_type_{_DB_SEQ}.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    global _TTB_SEQ
    _TTB_SEQ += 1
    cols = {
        "ttb_id": f"260010000001{_TTB_SEQ:02d}",
        "beverage_type": "DISTILLED_SPIRITS",
        "brand_name": "Stone's Throw",
        "alcohol_content": "45% Alc./Vol.",
        "net_contents": "750 mL",
        "applicant_name_address": "Acme Distillers, Louisville, KY",
        "class_type_designation": "Kentucky Straight Bourbon Whiskey",
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


def _insert_label_image(conn: sqlite3.Connection, submission_id: int, position: int = 1) -> int:
    cur = conn.execute(
        "INSERT INTO label_images (submission_id, filename, position) VALUES (?, ?, ?)",
        (submission_id, f"front_{position}.png", position),
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


# The Check row exactly as the spirits ruleset carries it (strategy=class_type).
_CHECK = Check(
    check_key="class_type_designation",
    label="Class/type designation",
    check_type="HYBRID",
    cfr_citation="27 CFR 5.141",
    source_date="2022-01-08",
    strategy="class_type",
    field_key="class_type_designation",
)


def _ctx(conn: sqlite3.Connection, submission_id: int) -> CheckContext:
    submission = repo.get_submission(conn, submission_id)
    assert submission is not None
    return CheckContext(
        conn=conn,
        submission=submission,
        ocr_text=repo.get_submission_ocr_text(conn, submission_id),
    )


# ── a spy/fake ModelAdapter injected via the get_llm_adapter seam ────────────


class _SpyModel:
    """A ModelAdapter whose ``run`` records every call (and optionally raises).

    Used to assert (AC1/AC3) the deterministic paths NEVER call the model, and (AC2)
    that the escalation hands the model an IMAGE + an OCR-free prompt. ``status`` of
    the canned result is configurable so a test can prove the model verdict is CAPPED
    at REVIEW (the check must not promote a model 'OK pass' to PASS, nor a model
    'fail' to FAIL)."""

    model_name = "Spy Model"
    model_id = "spy-1"
    model_full_id = "spy-1[test]"
    provider = "local"

    def __init__(
        self, *, raises: bool = False, result_text: str = "looks like a valid whiskey"
    ) -> None:
        self._raises = raises
        self._result_text = result_text
        self.calls: list[dict] = []

    def run(self, task, prompt, *, image_path=None):
        from app.contracts import LlmResult

        self.calls.append({"task": task, "prompt": prompt, "image_path": image_path})
        if self._raises:
            raise RuntimeError("provider unreachable")
        return LlmResult(
            model_name=self.model_name,
            model_id=self.model_id,
            model_full_id=self.model_full_id,
            provider=self.provider,
            task=task,
            result_text=self._result_text,
            prompt_tokens=10,
            completion_tokens=20,
            latency_ms=5,
            requested_at="2026-06-14T00:00:00+00:00",
            responded_at="2026-06-14T00:00:01+00:00",
            status="OK",
        )


# ── registration ─────────────────────────────────────────────────────────────


def test_class_type_evaluator_is_registered():
    """The class_type strategy now resolves to the real evaluator, not the placeholder."""
    assert checks.get_evaluator("class_type") is ct.class_type


# ── AC1: recognized → deterministic PASS, NO model call ──────────────────────


def test_recognized_designation_passes_without_model_call(tmp_path, monkeypatch):
    """AC1 (headline): a catalogued designation → PASS, and the model is NEVER called."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation="Kentucky Straight Bourbon Whiskey")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "KENTUCKY STRAIGHT BOURBON WHISKEY\n45% Alc./Vol.")

    spy = _SpyModel()
    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: spy)
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid))

    assert result.verdict == verdict.PASS
    assert spy.calls == []  # the deterministic recognized path constructs/calls NO model
    assert result.field_comparison_id is None


@pytest.mark.parametrize(
    "designation",
    ["London Dry Gin", "Blanco Tequila", "Vodka", "Caribbean Rum", "VSOP Cognac"],
)
def test_various_recognized_designations_pass(tmp_path, monkeypatch, designation):
    """AC1: a spread of catalogued base classes (gin/tequila/vodka/rum/cognac) → PASS."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation=designation)
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, designation.upper())

    spy = _SpyModel()
    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: spy)
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid))

    assert result.verdict == verdict.PASS
    assert spy.calls == []


# ── AC3: cross-label conflict → deterministic FAIL, both cited, NO model ─────


def test_cross_label_conflict_fails_both_cited_no_model(tmp_path, monkeypatch):
    """AC3: two DIFFERENT recognized base classes across labels → FAIL, both cited, no LLM."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        # application says bourbon; the back label OCR carries a conflicting "VODKA"
        sid = _insert_submission(conn, class_type_designation="Straight Bourbon Whiskey")
        img1 = _insert_label_image(conn, sid, position=1)
        img2 = _insert_label_image(conn, sid, position=2)
        _insert_ocr(conn, sid, img1, "STRAIGHT BOURBON WHISKEY")
        _insert_ocr(conn, sid, img2, "PREMIUM VODKA DISTILLED")

    spy = _SpyModel()
    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: spy)
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid))

    assert result.verdict == verdict.FAIL
    assert spy.calls == []  # conflict is an objective rule violation → deterministic
    detail = (result.detail or "").lower()
    assert "bourbon" in detail and "vodka" in detail  # both conflicting values cited


def test_same_group_variants_are_not_a_conflict(tmp_path, monkeypatch):
    """AC3 (negative): same-group variants ('straight bourbon' + 'bourbon') are NOT a conflict."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation="Straight Bourbon Whiskey")
        img1 = _insert_label_image(conn, sid, position=1)
        img2 = _insert_label_image(conn, sid, position=2)
        _insert_ocr(conn, sid, img1, "STRAIGHT BOURBON WHISKEY")
        _insert_ocr(conn, sid, img2, "KENTUCKY BOURBON WHISKEY 45% ALC/VOL")

    spy = _SpyModel()
    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: spy)
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid))

    assert result.verdict == verdict.PASS  # same whisky group everywhere → recognized PASS
    assert spy.calls == []


# ── AC2: ambiguous + model ON → VLM, capped REVIEW, image-only ───────────────


def test_ambiguous_escalates_to_vlm_capped_at_review(tmp_path, monkeypatch):
    """AC2: an unlisted designation + model ON → VLM escalation, capped at REVIEW (never FAIL)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation="Sasquatch Spirit Elixir")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "SASQUATCH SPIRIT ELIXIR\nA MYSTERIOUS POTION")

    # the model 'fails' the designation; the check must still cap at REVIEW, never FAIL.
    spy = _SpyModel(result_text="this is NOT a valid class/type designation")
    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: spy)
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid))

    assert result.verdict == verdict.REVIEW  # capped — a model opinion never FAILs
    assert len(spy.calls) == 1
    assert result.model_id == "spy-1"  # provenance recorded for the executor to fold in


def test_escalation_is_vlm_only_image_in_never_ocr_text(tmp_path, monkeypatch):
    """AC2 (VLM-only spine): the model is handed an IMAGE path and an OCR-FREE prompt.

    The OCR text MUST NOT appear in the prompt — no OCR→LLM hint anywhere (project-context
    hard rule)."""
    db_path = _make_db(tmp_path)
    ocr_text = "SASQUATCH SPIRIT ELIXIR UNIQUE BOTANICAL BLEND ZZZQ"
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation="Sasquatch Spirit Elixir")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, ocr_text)

    spy = _SpyModel()
    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: spy)
    with connect(db_path) as conn:
        ct.class_type(_CHECK, _ctx(conn, sid))

    assert len(spy.calls) == 1
    call = spy.calls[0]
    assert call["image_path"] is not None  # handed an IMAGE (VLM-only)
    assert "front_1.png" in str(call["image_path"])
    # the OCR text (or its distinctive token) is NEVER in the prompt
    assert ocr_text not in call["prompt"]
    assert "ZZZQ" not in call["prompt"]


def test_escalation_model_raises_degrades_to_review(tmp_path, monkeypatch):
    """AC2: a raising adapter on the escalation path → honest REVIEW (degrade, never crash)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation="Sasquatch Spirit Elixir")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "SASQUATCH SPIRIT ELIXIR")

    spy = _SpyModel(raises=True)
    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: spy)
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid))

    assert result.verdict == verdict.REVIEW


# ── AC4: ambiguous + model OFF → rules-only REVIEW ───────────────────────────


def test_ambiguous_model_off_degrades_to_rules_only_review(tmp_path, monkeypatch):
    """AC4: an unlisted designation + model OFF (get_llm_adapter → None) → REVIEW, no model."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation="Sasquatch Spirit Elixir")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "SASQUATCH SPIRIT ELIXIR")

    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: None)
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid))

    assert result.verdict == verdict.REVIEW
    assert result.detail and result.detail.strip()  # an explanatory, non-empty detail


def test_deterministic_paths_unchanged_by_toggle(tmp_path, monkeypatch):
    """AC4: PASS (AC1) and conflict-FAIL (AC3) are identical with the model OFF."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid_ok = _insert_submission(conn, class_type_designation="Straight Bourbon Whiskey")
        img_ok = _insert_label_image(conn, sid_ok)
        _insert_ocr(conn, sid_ok, img_ok, "STRAIGHT BOURBON WHISKEY")

    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: None)
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid_ok))
    assert result.verdict == verdict.PASS  # recognized PASS regardless of the toggle


# ── no field_comparisons row + run_checks integration + CFR-as-data guard ────


def test_writes_no_field_comparisons_row(tmp_path, monkeypatch):
    """The hybrid check writes NO field_comparisons row (like the Gov Warning / format checks)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation="Straight Bourbon Whiskey")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "STRAIGHT BOURBON WHISKEY")
        submission = repo.get_submission(conn, sid)
        assert submission is not None

    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: None)
    with connect(db_path) as conn:
        submission = repo.get_submission(conn, sid)
        assert submission is not None
        rc.run_checks(conn, submission)
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM field_comparisons WHERE submission_id = ? "
            "AND field_key = 'class_type_designation'",
            (sid,),
        ).fetchone()["n"]
    assert n == 0


def test_run_checks_class_type_row_is_pass_for_recognized(tmp_path, monkeypatch):
    """Integration: through run_checks, a recognized bourbon yields a PASS class_type row."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation="Kentucky Straight Bourbon Whiskey")
        img = _insert_label_image(conn, sid)
        _insert_ocr(
            conn,
            sid,
            img,
            "STONE'S THROW\nKENTUCKY STRAIGHT BOURBON WHISKEY\n45% Alc./Vol.\n750 mL\n"
            "Bottled by Acme Distillers, Louisville, KY",
        )

    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: None)
    with connect(db_path) as conn:
        submission = repo.get_submission(conn, sid)
        assert submission is not None
        rc.run_checks(conn, submission)
        conn.commit()
        row = conn.execute(
            "SELECT verdict FROM checklist_items WHERE submission_id = ? "
            "AND check_key = 'class_type_designation'",
            (sid,),
        ).fetchone()
    assert row is not None
    assert row["verdict"] == verdict.PASS


def test_cfr_citation_not_inlined_in_check_logic():
    """AC1 CFR-as-data guard: '27 CFR' must not appear inlined in checks/class_type.py.

    The citation lives ONLY on the Check row + the class_type DATA module (mirrors the
    3.4/3.5 guards)."""
    logic = Path("app/engine/checks/class_type.py").read_text(encoding="utf-8")
    assert "27 CFR" not in logic


def test_catalog_keyword_resolves_to_a_group():
    """Every recognized keyword maps to a conflict group (DATA integrity for AC3)."""
    for kw in ct_data.RECOGNIZED_CLASS_TYPES:
        assert kw in ct_data.KEYWORD_GROUPS
        assert ct_data.KEYWORD_GROUPS[kw]


# ── code-review regressions (Story 3.6 CR) ───────────────────────────────────


def test_liqueur_group_excluded_from_conflict_groups():
    """DATA: the liqueur group never participates in conflict detection (CR F1).

    A liqueur/cordial is a statement of composition that names its base spirit; it must
    not be one of the mutually-exclusive CONFLICT_GROUPS."""
    assert "liqueur" not in ct_data.CONFLICT_GROUPS
    # every other group IS a conflict group
    assert ct_data.CONFLICT_GROUPS == frozenset(ct_data.KEYWORD_GROUPS.values()) - {"liqueur"}


@pytest.mark.parametrize(
    "designation",
    ["Coffee Liqueur with Rum", "Sloe Gin Liqueur", "Whisky Liqueur", "Cherry Brandy Liqueur"],
)
def test_compound_liqueur_designation_is_not_a_false_conflict(tmp_path, monkeypatch, designation):
    """CR F1: a single compound liqueur designation (liqueur + its base spirit) is a valid
    statement of composition → recognized PASS, NOT a deterministic FAIL."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation=designation)
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, designation.upper())

    spy = _SpyModel()
    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: spy)
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid))

    assert result.verdict == verdict.PASS  # a valid statement of composition, never FAIL
    assert spy.calls == []  # recognized deterministically


def test_conflict_requires_a_declared_base_class_to_anchor():
    """CR F2: the conflict detector is ANCHORED to the declared designation.

    An OCR-only multi-spirit blob with NO declared base class is NOT a deterministic
    conflict (it is genuine ambiguity → the REVIEW path), so ``_detect_conflict``
    returns ``None`` — the un-anchored "any two stray OCR words ⇒ FAIL" behavior is
    gone. (The residual incidental-mention-against-a-declared-product case is a
    documented limitation — see deferred-work.md — because it is not deterministically
    separable from a genuine cross-label conflict, which AC3 requires to FAIL.)"""
    # undeclared designation, OCR carries two spirit groups: no anchor → no FAIL
    assert ct._detect_conflict("", "PREMIUM GIN AND VODKA BLEND") is None
    # declared bourbon + OCR vodka: anchored → a real conflict tuple (AC3)
    conflict = ct._detect_conflict("Straight Bourbon Whiskey", "PREMIUM VODKA DISTILLED")
    assert conflict is not None
    groups, _values = conflict
    assert {"whisky", "vodka"} <= groups


def test_hyphenated_single_malt_is_recognized(tmp_path, monkeypatch):
    """CR F3: a hyphenated multi-word designation ("American Single-Malt Whisky") is
    recognized by the 'single malt' phrase keyword (hyphen ≡ space)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation="American Single-Malt Whisky")
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, "AMERICAN SINGLE-MALT WHISKY")

    spy = _SpyModel()
    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: spy)
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid))

    assert result.verdict == verdict.PASS
    assert spy.calls == []
    assert ct._contains_phrase("single-malt", "single malt")  # the matcher itself


def test_conflict_fail_unchanged_by_toggle(tmp_path, monkeypatch):
    """AC4: a genuine cross-label conflict-FAIL is identical with the model OFF (the
    docstring-overclaim fix from the CR — assert AC3 with the toggle off)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn, class_type_designation="Straight Bourbon Whiskey")
        img1 = _insert_label_image(conn, sid, position=1)
        img2 = _insert_label_image(conn, sid, position=2)
        _insert_ocr(conn, sid, img1, "STRAIGHT BOURBON WHISKEY")
        _insert_ocr(conn, sid, img2, "PREMIUM VODKA DISTILLED")

    monkeypatch.setattr(ct, "get_llm_adapter", lambda settings: None)  # model OFF
    with connect(db_path) as conn:
        result = ct.class_type(_CHECK, _ctx(conn, sid))

    assert result.verdict == verdict.FAIL  # deterministic conflict, model-state irrelevant
    detail = (result.detail or "").lower()
    assert "bourbon" in detail and "vodka" in detail
