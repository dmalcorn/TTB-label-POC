"""Government Warning exact verification (Story 3.4, AC1–AC4) — THE three outcomes.

The named highest-value test in project-context ("``test_government_warning.py``
— the three outcomes"). Offline, fast, deterministic — NO real or fake model call
anywhere (this check is deterministic by contract: it must never touch an LLM).

The three outcomes must stay structurally distinct (FR-13 + AC3):
  - **reworded** (present, wrong)        → char-diff FAIL  (diff vs §16.21 text)
  - **absent**   (not present at all)    → plain FAIL      (no diff against empty)
  - **undeterminable** (bold/visual)     → REVIEW          (never a silent PASS)

Plus PASS (exact / incidental-whitespace / all-caps body) and the no-LLM guard.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.engine import checks
from app.engine import run_checks as rc
from app.engine.checks import government_warning as gw
from app.engine.rulesets import Check
from app.engine.rulesets import government_warning as gw_data

# ── shared fixtures (mirror tests/test_field_match.py) ───────────────────────


def _make_db(tmp_path) -> Path:
    db_path = tmp_path / "gov_warning.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26001000000099",
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


def _gw_check() -> Check:
    return Check(
        check_key="government_warning",
        label="Government Warning",
        check_type="DETERMINISTIC",
        cfr_citation=gw_data.CFR_CITATION,
        source_date=gw_data.SOURCE_DATE,
        strategy="government_warning",
    )


def _ctx(conn, submission_id, **kw) -> checks.CheckContext:
    submission = repo.get_submission(conn, submission_id)
    assert submission is not None
    return checks.CheckContext(
        conn=conn,
        submission=submission,
        ocr_text=kw.get("ocr_text", repo.get_submission_ocr_text(conn, submission_id)),
        scratch=kw.get("scratch", {}),
    )


def _evaluate_with_ocr(tmp_path, ocr_text: str):
    """Run the evaluator against a submission whose only label OCR text is ``ocr_text``."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        img = _insert_label_image(conn, sid)
        if ocr_text is not None:
            _insert_ocr(conn, sid, img, ocr_text)
        result = gw.government_warning(_gw_check(), _ctx(conn, sid))
    return result


def _detail_payload(detail: str | None) -> dict:
    """The evaluator encodes the outcome discriminator as a JSON object in ``detail``."""
    assert detail is not None
    return json.loads(detail)


# The canonical compliant statement, assembled from the DATA module (never re-typed).
_COMPLIANT = gw_data.FULL_TEXT


# ── registration / wiring ────────────────────────────────────────────────────


def test_government_warning_is_registered_under_its_strategy():
    """The evaluator plugs into the 3.2 dispatch seam under ``government_warning``."""
    assert checks.get_evaluator("government_warning") is gw.government_warning


# ── PASS (AC2) ───────────────────────────────────────────────────────────────


def test_pass_exact_text(tmp_path):
    result = _evaluate_with_ocr(tmp_path, _COMPLIANT)
    assert result.verdict == "PASS"


def test_pass_incidental_whitespace(tmp_path):
    """Extra spaces / line breaks are incidental ⇒ still PASS (AC2)."""
    noisy = _COMPLIANT.replace(" ", "  ").replace("(2)", "\n\n(2)")
    result = _evaluate_with_ocr(tmp_path, noisy)
    assert result.verdict == "PASS"


def test_pass_all_caps_body(tmp_path):
    """An all-caps body is compliant (AC1/AC2): body compared case-insensitively."""
    result = _evaluate_with_ocr(tmp_path, _COMPLIANT.upper())
    assert result.verdict == "PASS"


def test_pass_with_surrounding_label_text(tmp_path):
    """The warning anchored within other label copy still PASSes (locate by header)."""
    blob = f"STONE'S THROW BOURBON\n750 mL  45% Alc./Vol.\n{_COMPLIANT}\nBottled by Acme"
    result = _evaluate_with_ocr(tmp_path, blob)
    assert result.verdict == "PASS"


# ── FAIL — wording deviation → char-diff (AC3(a)) ────────────────────────────


def test_fail_reworded_carries_char_diff(tmp_path):
    """Reworded body ⇒ FAIL with a char-diff payload (outcome=reworded), not plain."""
    reworded = _COMPLIANT.replace("birth defects", "birth problems")
    result = _evaluate_with_ocr(tmp_path, reworded)
    assert result.verdict == "FAIL"
    payload = _detail_payload(result.detail)
    assert payload["outcome"] == "reworded"
    assert payload.get("diff")  # a non-empty diff against the §16.21 expected text
    assert "expected" in payload and "found" in payload


def test_reworded_found_is_clipped_to_the_warning(tmp_path):
    """The displayed ``found`` is the GOVERNMENT WARNING section only — not the whole OCR
    tail. ``ocr_text[match.start():]`` runs to the end of the blob, so a real label's
    warning is followed by brand/importer/other-panel copy; the reviewer must see the
    warning, not all of it (the ASKANELI brandy bug)."""
    trailing = (
        " CONTAINS SULFITES. Produced and bottled by Acme Distillers, Louisville, KY. "
        "Imported by Foo Wines and Spirits LLC, Boca Raton, FL. PRODUCT OF GEORGIA."
    )
    reworded = _COMPLIANT.replace("birth defects", "birth problems")
    result = _evaluate_with_ocr(tmp_path, reworded + trailing)
    assert result.verdict == "FAIL"
    found = _detail_payload(result.detail)["found"]
    assert "CONTAINS SULFITES" not in found  # trailing label copy is trimmed away
    assert "PRODUCT OF GEORGIA" not in found
    assert found.rstrip().endswith("problems.")  # cut at the statutory end clause
    assert len(found) < len(reworded + trailing)


def test_fail_omitted_clause(tmp_path):
    """An omitted (2) clause ⇒ wording-deviation FAIL with a diff."""
    omitted = f"{gw_data.HEADER} (1) According to the Surgeon General, women should not "
    omitted += "drink alcoholic beverages during pregnancy because of the risk of birth defects."
    result = _evaluate_with_ocr(tmp_path, omitted)
    assert result.verdict == "FAIL"
    assert _detail_payload(result.detail)["outcome"] == "reworded"


def test_missing_segment_marker_is_review_not_fail(tmp_path):
    """A dropped (1)/(2) marker is an OCR-plausible near-miss (every WORD is still present
    and correct — only the marker punctuation/digits differ) ⇒ REVIEW, not a hard FAIL.
    The reviewer confirms the markers against the label."""
    no_markers = _COMPLIANT.replace("(1) ", "").replace("(2) ", "")
    result = _evaluate_with_ocr(tmp_path, no_markers)
    assert result.verdict == "REVIEW"
    assert _detail_payload(result.detail)["outcome"] == "couldnt_verify"


def test_mispunctuation_is_review_not_fail(tmp_path):
    """Mis-punctuation (a missing period) is an OCR-plausible near-miss — the wording is
    intact, only a punctuation mark differs ⇒ REVIEW, not FAIL (the comma-on-the-label /
    OCR-can't-read-it case the reviewer flagged)."""
    mis = _COMPLIANT.replace("birth defects.", "birth defects")
    result = _evaluate_with_ocr(tmp_path, mis)
    assert result.verdict == "REVIEW"
    assert _detail_payload(result.detail)["outcome"] == "couldnt_verify"


def test_missing_comma_after_surgeon_general_is_review(tmp_path):
    """The reviewer's real case: an all-caps warning whose comma after 'SURGEON GENERAL' is
    physically on the label but too faint for OCR. The words are all correct ⇒ REVIEW (a
    human confirms the comma), NEVER a false FAIL and NEVER a silent PASS (the comma is part
    of §16.21 — a true exact match is still required to PASS)."""
    no_comma = _COMPLIANT.upper().replace("SURGEON GENERAL,", "SURGEON GENERAL")
    result = _evaluate_with_ocr(tmp_path, no_comma)
    assert result.verdict == "REVIEW"
    assert _detail_payload(result.detail)["outcome"] == "couldnt_verify"


def test_line_wrap_hyphen_passes(tmp_path):
    """A word split across a line ('PREG- NANCY') is standard typography on a compliant
    label — de-hyphenated before comparison ⇒ exact match ⇒ PASS (not a REVIEW or FAIL)."""
    wrapped = _COMPLIANT.upper().replace("PREGNANCY", "PREG- NANCY")
    result = _evaluate_with_ocr(tmp_path, wrapped)
    assert result.verdict == "PASS"


# ── FAIL — header / Surgeon-General casing (AC1/AC2) ─────────────────────────


def test_fail_title_case_header(tmp_path):
    """A title-case ``Government Warning:`` header ⇒ FAIL (header casing)."""
    titled = _COMPLIANT.replace(gw_data.HEADER, "Government Warning:")
    result = _evaluate_with_ocr(tmp_path, titled)
    assert result.verdict == "FAIL"
    payload = _detail_payload(result.detail)
    assert payload["outcome"] == "reworded"
    assert "header" in payload.get("deviation", "").lower()


def test_fail_lowercase_surgeon_general_in_mixed_case_body(tmp_path):
    """Lowercase ``surgeon general`` in a MIXED-CASE body ⇒ FAIL (casing deviation)."""
    bad = _COMPLIANT.replace("Surgeon General", "surgeon general")
    result = _evaluate_with_ocr(tmp_path, bad)
    assert result.verdict == "FAIL"


def test_fail_lowercase_surgeon_only(tmp_path):
    """Only ``surgeon`` lowercased (``General`` correct) ⇒ FAIL, blaming Surgeon."""
    bad = _COMPLIANT.replace("Surgeon General", "surgeon General")
    result = _evaluate_with_ocr(tmp_path, bad)
    assert result.verdict == "FAIL"
    assert "Surgeon" in _detail_payload(result.detail).get("deviation", "")


def test_fail_lowercase_general_only(tmp_path):
    """Only ``general`` lowercased (``Surgeon`` correct) ⇒ FAIL, blaming General.

    Regression (code review F-casing): the casing check must inspect the SPECIFIC
    word's initial letter, not whole-word membership — so a per-word lowercase is
    caught and correctly attributed."""
    bad = _COMPLIANT.replace("Surgeon General", "Surgeon general")
    result = _evaluate_with_ocr(tmp_path, bad)
    assert result.verdict == "FAIL"
    assert "General" in _detail_payload(result.detail).get("deviation", "")


def test_pass_over_capitalized_surgeon_general(tmp_path):
    """Over-capitalized ``Surgeon GENERAL`` is COMPLIANT (the G is still capital) ⇒ PASS.

    Regression (code review F-casing): §5.2 requires the ``S``/``G`` be CAPITAL; an
    all-caps rendering of a regulated word satisfies that. The prior whole-word
    substring test wrongly FAILed ``Surgeon GENERAL`` / ``SURGEON General`` because the
    mixed-case literal was not a substring — a false reject of more-capitalized text."""
    for i, variant in enumerate(("Surgeon GENERAL", "SURGEON General")):
        body = _COMPLIANT.replace("Surgeon General", variant)
        result = _evaluate_with_ocr(tmp_path / f"v{i}", body)
        assert result.verdict == "PASS", f"{variant!r} should PASS (S/G are capital)"


def test_pass_all_caps_body_with_one_ocr_lowercased_word(tmp_path):
    """An otherwise all-caps body with ONE OCR-lowercased word still PASSes.

    Regression (code review F-casing): a single stray lowercase letter flipped the body
    out of "all-caps", which used to enable the whole-word substring test and then
    falsely FAIL with a misleading "Surgeon must be capitalized" — even though SURGEON
    was fully capital. The initial S/G remain capital, so the warning is compliant."""
    body = _COMPLIANT.upper().replace("OPERATE MACHINERY", "operate machinery")
    result = _evaluate_with_ocr(tmp_path, body)
    assert result.verdict == "PASS"


def test_fail_interleaved_foreign_text_between_clauses(tmp_path):
    """Foreign text interleaved between the (1)/(2) clauses ⇒ wording-deviation FAIL.

    §5.4 step 4 (one statement / separate & apart): the body must be one contiguous
    block. Interleaving breaks the exact prefix match ⇒ reworded FAIL."""
    interleaved = _COMPLIANT.replace("(2)", "Drink responsibly! (2)")
    result = _evaluate_with_ocr(tmp_path, interleaved)
    assert result.verdict == "FAIL"
    assert _detail_payload(result.detail)["outcome"] == "reworded"


# ── multi-occurrence: any compliant occurrence ⇒ PASS (code review F-locate) ──


def test_pass_decoy_header_before_correct_warning(tmp_path):
    """A stylized "GOVERNMENT WARNING:" tagline BEFORE the real warning still PASSes.

    Regression (code review F-locate): the joined OCR text concatenates all label
    images; the locator must evaluate EVERY header occurrence and PASS if any is
    compliant — not condemn the submission on the first (decoy) match."""
    decoy = f"GOVERNMENT WARNING: PLEASE DRINK RESPONSIBLY\n{_COMPLIANT}"
    result = _evaluate_with_ocr(tmp_path, decoy)
    assert result.verdict == "PASS"


def test_pass_reworded_front_then_correct_back(tmp_path):
    """A reworded warning FIRST, then a correct one LATER (front+back labels) ⇒ PASS.

    Regression (code review F-locate): order independence — a compliant occurrence
    anywhere satisfies §16.21, regardless of an earlier deviant one."""
    reworded = _COMPLIANT.replace("birth defects", "birth problems")
    result = _evaluate_with_ocr(tmp_path, f"{reworded}\n{_COMPLIANT}")
    assert result.verdict == "PASS"


def test_fail_when_all_occurrences_deviate(tmp_path):
    """If EVERY occurrence deviates (none compliant) ⇒ FAIL reporting the first one.

    Guards the any-occurrence logic from over-accepting: two distinct reworded
    warnings, neither correct, must still FAIL (not PASS on a near-miss)."""
    a = _COMPLIANT.replace("birth defects", "birth harms")
    b = _COMPLIANT.replace("operate machinery", "operate equipment")
    result = _evaluate_with_ocr(tmp_path, f"{a}\n{b}")
    assert result.verdict == "FAIL"
    assert _detail_payload(result.detail)["outcome"] == "reworded"


# ── AI transcription source (Story: gov-warning reads the VLM reading too) ────


def test_ai_transcription_compliant_passes_even_when_ocr_garbled(tmp_path):
    """When the VLM transcribed a compliant warning, the check PASSes even if OCR garbled
    the back-label header — a clean image read beats noisy OCR (the smoke-test gap)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        scratch = {"llm_extraction": json.dumps({"government_warning": _COMPLIANT})}
        ctx = _ctx(conn, sid, ocr_text="veANMET WARMING blah unreadable smudge", scratch=scratch)
        result = gw.government_warning(_gw_check(), ctx)
    assert result.verdict == "PASS"
    assert _detail_payload(result.detail)["outcome"] == "pass"


def test_ai_transcription_passes_when_ocr_absent(tmp_path):
    """The warning is on the label (AI read it) but OCR found nothing ⇒ PASS, not absent."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        scratch = {"llm_extraction": json.dumps({"government_warning": _COMPLIANT})}
        ctx = _ctx(conn, sid, ocr_text="STONE'S THROW BOURBON 750 mL", scratch=scratch)
        result = gw.government_warning(_gw_check(), ctx)
    assert result.verdict == "PASS"


def test_ai_null_warning_falls_back_to_ocr(tmp_path):
    """A null/absent AI warning field ⇒ evaluate OCR only (unchanged single-source path)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        scratch = {"llm_extraction": json.dumps({"government_warning": None})}
        ctx = _ctx(conn, sid, ocr_text=_COMPLIANT, scratch=scratch)
        result = gw.government_warning(_gw_check(), ctx)
    assert result.verdict == "PASS"  # OCR carried the compliant warning


# ── FAIL — absent → plain, NO diff (AC3(b)) ──────────────────────────────────


def test_fail_absent_is_plain_no_diff(tmp_path):
    """Warning not present in ANY image ⇒ FAIL, plain copy, NO diff against empty."""
    result = _evaluate_with_ocr(tmp_path, "STONE'S THROW BOURBON\n750 mL  45% Alc./Vol.")
    assert result.verdict == "FAIL"
    payload = _detail_payload(result.detail)
    assert payload["outcome"] == "absent"
    assert not payload.get("diff")  # absent NEVER carries a char-diff


def test_fail_absent_when_no_ocr_text(tmp_path):
    """No OCR text at all (no readable label) ⇒ absent FAIL, plain, no diff."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        _insert_label_image(conn, sid)
        result = gw.government_warning(_gw_check(), _ctx(conn, sid))
    assert result.verdict == "FAIL"
    assert _detail_payload(result.detail)["outcome"] == "absent"


# ── REVIEW — bold/visual undeterminable (AC3(c)) ─────────────────────────────


def test_review_when_bold_undeterminable(tmp_path):
    """The bold/visual-styling case ⇒ REVIEW "couldn't verify", never a silent PASS.

    Bold cannot be recovered from OCR text; when the wording is otherwise correct the
    only honest engine call about the bold requirement is REVIEW (the caller signals
    the undeterminable visual attribute via scratch)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, _COMPLIANT)
        ctx = _ctx(conn, sid, scratch={"bold_undeterminable": True})
        result = gw.government_warning(_gw_check(), ctx)
    assert result.verdict == "REVIEW"
    assert _detail_payload(result.detail)["outcome"] == "couldnt_verify"


# ── provenance (Task 3) ──────────────────────────────────────────────────────


def test_no_field_comparison_row_written(tmp_path):
    """The Gov Warning compares against the STATUTE, not a field ⇒ NO field_comparisons."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, _COMPLIANT)
        gw.government_warning(_gw_check(), _ctx(conn, sid))
        rows = conn.execute(
            "SELECT COUNT(*) AS n FROM field_comparisons WHERE submission_id = ?", (sid,)
        ).fetchone()
    assert rows["n"] == 0


def test_result_has_no_field_comparison_id(tmp_path):
    result = _evaluate_with_ocr(tmp_path, _COMPLIANT)
    assert result.field_comparison_id is None


# ── integration through run_checks (3.2 seam) ────────────────────────────────


def test_run_checks_writes_government_warning_row(tmp_path):
    """End-to-end on the 3.2 executor: the gov-warning Check yields a real verdict."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sid = _insert_submission(conn)
        img = _insert_label_image(conn, sid)
        _insert_ocr(conn, sid, img, _COMPLIANT)
        submission = repo.get_submission(conn, sid)
        assert submission is not None
        rc.run_checks(conn, submission)
        row = conn.execute(
            "SELECT verdict, check_type, cfr_citation FROM checklist_items "
            "WHERE submission_id = ? AND check_key = 'government_warning'",
            (sid,),
        ).fetchone()
    assert row is not None
    assert row["verdict"] == "PASS"
    assert row["check_type"] == "DETERMINISTIC"
    assert row["cfr_citation"] == "27 CFR 16.21"


# ── AC4: CFR text lives only as DATA, not in check logic ─────────────────────


def test_warning_text_only_in_data_module_not_in_check_logic():
    """AC4 guard: the §16.21 body must NOT appear inlined in checks/government_warning.py."""
    logic = Path("app/engine/checks/government_warning.py").read_text(encoding="utf-8")
    # A distinctive verbatim slice of the regulation body.
    assert "drink alcoholic beverages during pregnancy" not in logic
    assert "operate machinery, and may cause health problems" not in logic


def test_cfr_citation_not_hardcoded_in_check_logic():
    """AC4 guard: ``27 CFR`` must not be hard-coded in the check logic (lives as data)."""
    logic = Path("app/engine/checks/government_warning.py").read_text(encoding="utf-8")
    assert "27 CFR" not in logic


def test_data_module_carries_citation_and_source_date():
    assert gw_data.CFR_CITATION == "27 CFR 16.21"
    assert gw_data.SOURCE_DATE
    assert gw_data.HEADER == "GOVERNMENT WARNING:"


# ── AC1: NO-LLM guard (mirrors the egress rigor of test_token_gate) ──────────


def test_check_never_imports_a_model_adapter():
    """AC1: the deterministic check must NEVER import/construct a model adapter.

    A static guard over the check's ``import`` statements (mirrors the egress rigor of
    ``test_token_gate.py``) — the Government Warning check NEVER calls an LLM
    (project-context determinism taxonomy). We parse the AST and assert no import pulls
    in a model adapter / provider SDK; prose mentions of "LLM" in docstrings are fine,
    a real import is the finding."""
    import ast

    source = Path("app/engine/checks/government_warning.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    banned = ("adapters.llm", "openai", "anthropic", "google.genai", "google_genai", "langchain")
    for mod in imported:
        low = mod.lower()
        assert not any(b in low for b in banned), f"check imports a model module: {mod!r}"


def test_check_constructs_no_model_client():
    """AC1: belt-and-braces — no model adapter is constructed/CALLED by the check.

    The check builds NO LLM adapter (``get_llm_adapter`` / ``build_extractor`` / etc.) and
    opens no socket. It MAY read the AI's already-persisted transcription (the model ran
    upstream in the VLM stage — reading stored extraction is not a model call, the same as
    field_match), so reading ``llm_results`` is allowed; constructing/calling a model is not.
    A coarse source scan for adapter-construction call names; prose excluded by targeting
    call-like tokens only."""
    logic = Path("app/engine/checks/government_warning.py").read_text(encoding="utf-8")
    for token in ("get_llm_adapter(", "build_extractor("):
        assert token not in logic, f"check logic constructs/calls a model: {token!r}"
