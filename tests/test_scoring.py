"""Accuracy-scoring tests (Story 5.2, all ACs).

**Offline by construction.** A temp SQLite is seeded with a tiny corpus plus
hand-written ``ocr_results`` / ``llm_results`` rows — no provider call, no network,
no real OCR. Scoring is a pure read/compute step, so the whole suite runs under
``docker run --network none``. Highest-value tests: the "STONE'S THROW" MATCH and
"45% vs 40%" MISMATCH scoring class, reproducibility (twice ⇒ identical),
both-variants separation, Government-Warning presence/exactness, and the
egress/read-only structural guard.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict
from pathlib import Path

from app.benchmark import scoring
from app.db.connection import connect, init_db

# Gold values for the tiny test corpus (mirrors the fixtures/ground_truth.csv gt_*
# columns). Keyed by ttb_id.
_GOV_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "scoring.db"
    init_db(db_path)
    return db_path


def _write_ground_truth_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    """Write a minimal ground_truth.csv with the gt_* columns scoring reads."""
    import csv

    header = [
        "ttb_id",
        "gt_brand_name",
        "gt_class_type_designation",
        "gt_alcohol_content",
        "gt_net_contents",
        "gt_applicant_name_address",
        "gt_government_warning",
    ]
    path = tmp_path / "ground_truth.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in header})
    return path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26001000000001",
        "beverage_type": "DISTILLED_SPIRITS",
        "brand_name": "Stone's Throw",
        "status": "READY_FOR_REVIEW",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})"
    cur = conn.execute(sql, tuple(cols.values()))
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_image(conn: sqlite3.Connection, submission_id: int) -> int:
    cur = conn.execute(
        "INSERT INTO label_images (submission_id, image_role, position, filename) "
        "VALUES (?, 'BRAND', 1, 'front.jpg')",
        (submission_id,),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _insert_ocr(
    conn: sqlite3.Connection,
    submission_id: int,
    image_id: int,
    *,
    engine_name: str,
    text: str,
    image_variant: str = "ORIGINAL",
    confidence: float = 0.9,
    status: str = "OK",
) -> None:
    conn.execute(
        "INSERT INTO ocr_results "
        "(label_image_id, submission_id, engine_name, extracted_text, confidence, "
        " image_variant, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (image_id, submission_id, engine_name, text, confidence, image_variant, status),
    )


def _insert_llm(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    model_id: str,
    result_text: str,
    model_name: str = "Fake Model",
    provider: str = "local",
    task: str = "extract_fields",
    status: str = "OK",
) -> None:
    conn.execute(
        "INSERT INTO llm_results "
        "(submission_id, task, model_name, model_id, provider, result_text, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (submission_id, task, model_name, model_id, provider, result_text, status),
    )


# A whole-label OCR blob carrying every matchable value (the engine locates each
# field within it). Brand cased differently from gold ("STONE'S THROW") to prove
# normalization collapses the difference.
def _ocr_blob(*, abv: str = "45% Alc./Vol.", brand: str = "STONE'S THROW") -> str:
    return (
        f"{brand}\n"
        "Kentucky Straight Bourbon Whiskey\n"
        f"{abv}\n"
        "750 mL\n"
        "Distilled and Bottled By Stone's Throw Co., Bardstown, KY\n"
        f"{_GOV_WARNING}\n"
    )


def _llm_json(*, brand: str = "Stone's Throw", abv: str = "45% Alc./Vol.") -> str:
    import json

    return json.dumps(
        {
            "brand_name": brand,
            "class_type_designation": "Kentucky Straight Bourbon Whiskey",
            "alcohol_content": abv,
            "net_contents": "750 mL",
            "applicant_name_address": ("Distilled and Bottled By Stone's Throw Co., Bardstown, KY"),
            "government_warning": _GOV_WARNING,
        }
    )


def _seed_one(tmp_path: Path, *, ttb_id: str = "26001000000001") -> tuple[Path, Path]:
    """Seed a single clean submission with one OCR engine + one LLM model row."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(
            conn,
            ttb_id=ttb_id,
            brand_name="Stone's Throw",
            class_type_designation="Kentucky Straight Bourbon Whiskey",
            alcohol_content="45% Alc./Vol.",
            net_contents="750 mL",
            applicant_name_address="Distilled and Bottled By Stone's Throw Co., Bardstown, KY",
        )
        img_id = _insert_image(conn, sub_id)
        _insert_ocr(conn, sub_id, img_id, engine_name="tesseract", text=_ocr_blob())
        _insert_llm(conn, sub_id, model_id="fake-1", result_text=_llm_json())
    csv_path = _write_ground_truth_csv(
        tmp_path,
        [
            {
                "ttb_id": ttb_id,
                "gt_brand_name": "Stone's Throw",
                "gt_class_type_designation": "Kentucky Straight Bourbon Whiskey",
                "gt_alcohol_content": "45% Alc./Vol.",
                "gt_net_contents": "750 mL",
                "gt_applicant_name_address": (
                    "Distilled and Bottled By Stone's Throw Co., Bardstown, KY"
                ),
                "gt_government_warning": _GOV_WARNING,
            }
        ],
    )
    return db_path, csv_path


# ── AC1: per-field + aggregate field-match rates, normalize both sides ────────


def test_brand_matches_across_normalization_stones_throw():
    """ "STONE'S THROW" (OCR) vs gold "Stone's Throw" ⇒ MATCH (the spine case)."""
    score = scoring.score_field("brand_name", "STONE'S THROW", "Stone's Throw")
    assert score.match_status == "MATCH"
    assert score.similarity == 1.0


def test_numeric_mismatch_45_vs_40_is_a_mismatch():
    score = scoring.score_field("alcohol_content", "40% Alc./Vol.", "45% Alc./Vol.")
    assert score.match_status == "MISMATCH"


def test_numeric_match_45_pct_variants():
    score = scoring.score_field("alcohol_content", "45%", "45% Alc./Vol.")
    assert score.match_status == "MATCH"


def test_missing_when_gold_present_extracted_empty():
    score = scoring.score_field("brand_name", "", "Stone's Throw")
    assert score.match_status == "MISSING"


def test_unverifiable_when_gold_absent():
    score = scoring.score_field("brand_name", "Stone's Throw", None)
    assert score.match_status == "UNVERIFIABLE"


def test_corpus_scores_per_field_and_aggregate(tmp_path):
    db_path, csv_path = _seed_one(tmp_path)
    with connect(db_path) as conn:
        result = scoring.score_corpus(conn, csv_path=csv_path)

    # One engine, one model — both should match every field on the clean fixture.
    engine = result.engines[("tesseract", "ORIGINAL")]
    assert engine.field_match_rate == 1.0
    assert engine.field_rates["brand_name"].match_rate == 1.0
    model = result.models["fake-1"]
    assert model.field_match_rate == 1.0
    assert model.field_rates["alcohol_content"].match_rate == 1.0


def test_unverifiable_excluded_from_denominator(tmp_path):
    """A gold-absent field is UNVERIFIABLE and excluded from the match-rate denom."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn, brand_name="Stone's Throw")
        img_id = _insert_image(conn, sub_id)
        _insert_ocr(conn, sub_id, img_id, engine_name="tesseract", text=_ocr_blob())
    csv_path = _write_ground_truth_csv(
        tmp_path,
        [{"ttb_id": "26001000000001", "gt_brand_name": "Stone's Throw"}],  # only brand gold
    )
    with connect(db_path) as conn:
        result = scoring.score_corpus(conn, csv_path=csv_path)
    engine = result.engines[("tesseract", "ORIGINAL")]
    # Only brand_name has gold ⇒ the other fields are UNVERIFIABLE, not counted.
    assert engine.unverifiable_count >= 1
    assert engine.field_match_rate == 1.0  # the one verifiable field matched


# ── AC2: Government Warning presence / exactness ──────────────────────────────


def test_gov_warning_present_and_exact():
    s = scoring.government_warning_score(_GOV_WARNING, _GOV_WARNING)
    assert s.present is True
    assert s.exact is True


def test_gov_warning_present_but_not_exact():
    deviated = _GOV_WARNING.replace("birth defects", "birth problems")
    s = scoring.government_warning_score(deviated, _GOV_WARNING)
    assert s.present is True
    assert s.exact is False


def test_gov_warning_absent():
    s = scoring.government_warning_score("", _GOV_WARNING)
    assert s.present is False
    assert s.exact is False


def test_llm_json_without_gov_warning_scores_absent_not_raw_blob(tmp_path):
    """An LLM JSON payload that OMITS government_warning ⇒ present=False (not the raw JSON).

    Regression: ``_gov_warning_value`` must NOT fall back to the whole JSON string for a
    structured payload — that would falsely report a present warning and feed the JSON
    blob into CER. Only a non-JSON OCR blob falls back to its raw text."""
    import json

    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn, brand_name="Stone's Throw")
        # A model that extracted the other fields but NO government_warning key.
        _insert_llm(
            conn,
            sub_id,
            model_id="no-gw",
            result_text=json.dumps({"brand_name": "Stone's Throw", "net_contents": "750 mL"}),
        )
    csv_path = _write_ground_truth_csv(
        tmp_path,
        [{"ttb_id": "26001000000001", "gt_government_warning": _GOV_WARNING}],
    )
    with connect(db_path) as conn:
        result = scoring.score_corpus(conn, csv_path=csv_path)

    model = result.models["no-gw"]
    # The warning was scored (gold present) but NOT found in the extraction.
    assert model.gov_warning_total == 1
    assert model.gov_warning_present == 0
    assert model.gov_warning_presence_rate == 0.0
    # CER on the (absent) warning is the empty-extraction-vs-present-gold edge ⇒ 1.0,
    # NOT a Levenshtein over the raw JSON blob (which would be < 1.0 by coincidence).
    assert model.mean_cer == 1.0


def test_gov_warning_value_helper_distinguishes_json_from_blob():
    """The helper trusts a JSON object's field and falls back only for a non-JSON blob."""
    import json

    # JSON object lacking the field ⇒ None (no raw-blob fallback).
    assert scoring._gov_warning_value(json.dumps({"brand_name": "x"})) is None
    # JSON object carrying the field ⇒ the field value.
    with_gw = json.dumps({"government_warning": _GOV_WARNING})
    assert scoring._gov_warning_value(with_gw) == _GOV_WARNING
    # Non-JSON OCR blob ⇒ the whole blob (the warning is located within it downstream).
    blob = f"SOME BRAND\n{_GOV_WARNING}\n"
    assert scoring._gov_warning_value(blob) == blob


# ── AC3: CER ──────────────────────────────────────────────────────────────────


def test_cer_zero_on_exact_after_normalize():
    assert scoring.cer("Stone's Throw", "STONE'S THROW") == 0.0


def test_cer_known_fraction_on_one_edit():
    # "abcd" vs "abce": 1 substitution / len 4 = 0.25 (normalize is identity here).
    assert scoring.cer("abcd", "abce") == 0.25


def test_cer_empty_gold_edges():
    assert scoring.cer("", "") == 0.0
    assert scoring.cer("anything", "") == 1.0


# ── AC4: reproducibility ──────────────────────────────────────────────────────


def test_score_corpus_is_reproducible(tmp_path):
    db_path, csv_path = _seed_one(tmp_path)
    with connect(db_path) as conn:
        first = scoring.score_corpus(conn, csv_path=csv_path)
    with connect(db_path) as conn:
        second = scoring.score_corpus(conn, csv_path=csv_path)
    assert asdict(first) == asdict(second)
    assert repr(first) == repr(second)


# ── AC5: both-variants (preprocessed vs original) ─────────────────────────────


def test_variants_scored_separately(tmp_path):
    """ORIGINAL vs ENHANCED rows for the same engine score independently."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(
            conn, brand_name="Stone's Throw", alcohol_content="45% Alc./Vol."
        )
        img_id = _insert_image(conn, sub_id)
        # ORIGINAL misreads the label entirely (gold brand absent from the blob);
        # ENHANCED reads it correctly. A fully-wrong blob is used here rather than
        # _ocr_blob, whose producer line embeds the gold brand verbatim.
        _insert_ocr(
            conn,
            sub_id,
            img_id,
            engine_name="tesseract",
            image_variant="ORIGINAL",
            text=(
                "MOUNTAIN RIDGE CELLARS\n"
                "California Red Wine\n"
                "13.5% Alc./Vol.\n"
                "750 mL\n"
                "Produced and Bottled By Mountain Ridge Cellars, Napa, CA\n"
                f"{_GOV_WARNING}\n"
            ),  # gold brand "Stone's Throw" appears nowhere
        )
        _insert_ocr(
            conn,
            sub_id,
            img_id,
            engine_name="tesseract",
            image_variant="ENHANCED",
            text=_ocr_blob(brand="STONE'S THROW"),  # clean
        )
    csv_path = _write_ground_truth_csv(
        tmp_path,
        [
            {
                "ttb_id": "26001000000001",
                "gt_brand_name": "Stone's Throw",
                "gt_alcohol_content": "45% Alc./Vol.",
            }
        ],
    )
    with connect(db_path) as conn:
        result = scoring.score_corpus(conn, csv_path=csv_path)

    original = result.engines[("tesseract", "ORIGINAL")]
    enhanced = result.engines[("tesseract", "ENHANCED")]
    # The two variants are distinct keys and the enhanced brand scores better.
    assert original.field_rates["brand_name"].match_rate == 0.0
    assert enhanced.field_rates["brand_name"].match_rate == 1.0


# ── AC6: egress / read-only structural guard ──────────────────────────────────

_OFF_HOST_CLIENT = re.compile(
    r"\b(?:Async)?OpenAI\(|"
    r"\b(?:Async)?Anthropic\(|"
    r"genai\.Client\(|"
    r"httpx\.(?:Client|AsyncClient)\(|"
    r"requests\.(?:get|post|put|delete|patch|head|request|Session)\(|"
    r"\bClientSession\(|"
    r"\burlopen\(|"
    r"\bsocket\("
)


def _scoring_source() -> str:
    path = Path(__file__).resolve().parents[1] / "app" / "benchmark" / "scoring.py"
    return path.read_text(encoding="utf-8")


def test_scoring_constructs_no_off_host_client():
    """Scoring is local analysis — it opens no off-host connection (NFR-2, AC6)."""
    assert not _OFF_HOST_CLIENT.search(_scoring_source())


def test_scoring_issues_no_write_sql():
    """Scoring is DB-read-only — no INSERT/UPDATE/DELETE in the module (AR-13, AC6)."""
    src = _scoring_source().upper()
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM"):
        assert verb not in src, f"scoring.py must not issue {verb!r}"
