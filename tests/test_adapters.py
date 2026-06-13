"""Engine-agnostic storage + adapter protocols (Story 2.1, AC2/AC3).

Covers: the ocr_results/llm_results tables exist with the generated total_tokens
column (Task 2); the OcrEngine/ModelAdapter protocols are satisfiable and
runtime-checkable (Task 3); the contract→column write path round-trips
(Task 4); and two distinct engines persist independent rows with NO schema
change — the procurement swap-and-compare proof (Task 5).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.adapters.llm.base import ModelAdapter
from app.adapters.ocr.base import OcrEngine
from app.contracts import LlmResult, OcrResult
from app.db import repositories as repo
from app.db.connection import connect, init_db


def _make_db(tmp_path) -> Path:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def _seed_submission_and_image(conn: sqlite3.Connection) -> tuple[int, int]:
    cur = conn.execute(
        "INSERT INTO submissions (ttb_id, beverage_type, status) VALUES (?, ?, ?)",
        ("26001000000001", "DISTILLED_SPIRITS", "PROCESSING"),
    )
    assert cur.lastrowid is not None  # guaranteed by a successful INSERT
    sub_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO label_images (submission_id, position, filename) VALUES (?, ?, ?)",
        (sub_id, 1, "front.jpg"),
    )
    assert cur.lastrowid is not None  # guaranteed by a successful INSERT
    img_id = cur.lastrowid
    conn.commit()
    return sub_id, img_id


# ── Task 2: tables + indexes + generated column ──────────────────────────────


def test_ocr_and_llm_tables_exist(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert {"ocr_results", "llm_results"} <= names


def test_per_engine_indexes_exist(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        idx = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
    assert {"idx_ocr_results_engine", "idx_llm_results_model"} <= idx


def test_total_tokens_is_generated(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id, _ = _seed_submission_and_image(conn)
        repo.insert_llm_result(
            conn,
            submission_id=sub_id,
            result=LlmResult(model_id="claude-opus-4-8", prompt_tokens=10, completion_tokens=20),
        )
        total = conn.execute("SELECT total_tokens FROM llm_results").fetchone()[0]
    assert total == 30


def test_total_tokens_generated_is_null_when_one_part_missing(tmp_path):
    # The DB generated column must mirror LlmResult.total_tokens (NULL if either
    # part is NULL) — SQLite `10 + NULL` is NULL. Guards the "can't drift" claim
    # at the column level, not just the in-memory property.
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id, _ = _seed_submission_and_image(conn)
        repo.insert_llm_result(
            conn,
            submission_id=sub_id,
            result=LlmResult(model_id="m", prompt_tokens=10, completion_tokens=None),
        )
        total = conn.execute("SELECT total_tokens FROM llm_results").fetchone()[0]
    assert total is None


# ── Task 3: adapter protocols are satisfiable + runtime-checkable ─────────────


class _StubEngine:
    """A new OCR engine as just a class implementing the protocol — no DDL change."""

    def __init__(self, name: str, version: str = "0.0-stub"):
        self.name = name
        self.version = version

    def extract(self, image_path: str | Path, *, ran_on_cpu: bool = True) -> OcrResult:
        return OcrResult(
            engine_name=self.name,
            engine_version=self.version,
            text=f"text-from-{self.name}",
            word_boxes=[{"text": "STONE'S", "box": [0, 0, 10, 10]}],
            confidence=0.91,
            latency_ms=42,
            ran_on_cpu=ran_on_cpu,
            status="OK",
        )


class _StubModel:
    model_name = "Stub Model"
    model_id = "stub-1"
    model_full_id = "stub-1[test]"
    provider = "local"

    def run(self, task: str, prompt: str, *, image_path=None) -> LlmResult:
        return LlmResult(
            model_name=self.model_name,
            model_id=self.model_id,
            model_full_id=self.model_full_id,
            provider=self.provider,
            task=task,
            result_text="ok",
            prompt_tokens=1,
            completion_tokens=2,
            status="OK",
        )


def test_stub_engine_satisfies_protocol():
    assert isinstance(_StubEngine("tesseract"), OcrEngine)


def test_stub_model_satisfies_protocol():
    assert isinstance(_StubModel(), ModelAdapter)


# ── Task 4: contract → column round-trip ─────────────────────────────────────


def test_ocr_result_round_trips_with_name_mapping(tmp_path):
    db_path = _make_db(tmp_path)
    result = _StubEngine("tesseract").extract("front.jpg")
    # Insert in one connection, then read back through a SEPARATE connection so
    # the assertions prove the write committed and survives connection close
    # (the helper delegates commit to `connect()`'s clean exit) — not just that
    # a row is visible to its own uncommitted transaction.
    with connect(db_path) as conn:
        sub_id, img_id = _seed_submission_and_image(conn)
        row_id = repo.insert_ocr_result(
            conn, submission_id=sub_id, label_image_id=img_id, result=result
        )
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM ocr_results WHERE id = ?", (row_id,)).fetchone()
    # contract `text` landed in column `extracted_text`
    assert row["extracted_text"] == "text-from-tesseract"
    assert row["engine_name"] == "tesseract"
    assert row["ran_on_cpu"] == 1
    # word_boxes persisted as JSON TEXT and round-trips
    assert json.loads(row["word_boxes"])[0]["text"] == "STONE'S"


def test_llm_result_does_not_insert_total_tokens(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id, _ = _seed_submission_and_image(conn)
        row_id = repo.insert_llm_result(
            conn,
            submission_id=sub_id,
            result=LlmResult(model_id="m", prompt_tokens=7, completion_tokens=5),
            is_benchmark_only=True,
        )
        row = conn.execute("SELECT * FROM llm_results WHERE id = ?", (row_id,)).fetchone()
    assert row["total_tokens"] == 12  # DB-computed, not inserted
    assert row["is_benchmark_only"] == 1


# ── Task 5: engine-agnosticism proof — two engines, independent rows ──────────


def test_two_engines_store_independent_rows_no_schema_change(tmp_path):
    db_path = _make_db(tmp_path)
    engines = [_StubEngine("tesseract"), _StubEngine("paddleocr")]
    with connect(db_path) as conn:
        sub_id, img_id = _seed_submission_and_image(conn)
        for eng in engines:  # adding the 2nd engine needed zero DDL/caller change
            repo.insert_ocr_result(
                conn, submission_id=sub_id, label_image_id=img_id, result=eng.extract("front.jpg")
            )
        rows = conn.execute(
            "SELECT engine_name FROM ocr_results WHERE submission_id = ? ORDER BY engine_name",
            (sub_id,),
        ).fetchall()
    # two independent, separately-queryable per-engine rows for the same image
    assert [r["engine_name"] for r in rows] == ["paddleocr", "tesseract"]


def test_two_models_store_independent_rows_queryable_by_model_id(tmp_path):
    # AC2's LLM half: two different models on the same submission each get their
    # OWN row, independently queryable by model_id — no merged-only storage.
    db_path = _make_db(tmp_path)
    results = [
        LlmResult(
            model_id="claude-opus-4-8", task="extract", prompt_tokens=10, completion_tokens=20
        ),
        LlmResult(model_id="gemini-2-flash", task="extract", prompt_tokens=5, completion_tokens=7),
    ]
    with connect(db_path) as conn:
        sub_id, _ = _seed_submission_and_image(conn)
        for res in results:  # adding the 2nd model needed zero DDL/caller change
            repo.insert_llm_result(conn, submission_id=sub_id, result=res)
        rows = conn.execute(
            "SELECT model_id, total_tokens FROM llm_results WHERE submission_id = ? "
            "ORDER BY model_id",
            (sub_id,),
        ).fetchall()
    assert [r["model_id"] for r in rows] == ["claude-opus-4-8", "gemini-2-flash"]
    # each row carries its own independently-computed generated total
    assert [r["total_tokens"] for r in rows] == [30, 12]
    # a single model is isolable by model_id
    with connect(db_path) as conn:
        one = conn.execute(
            "SELECT model_id FROM llm_results WHERE model_id = ?", ("gemini-2-flash",)
        ).fetchall()
    assert len(one) == 1
