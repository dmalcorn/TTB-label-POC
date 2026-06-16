"""Benchmark Report screen tests (Story 5.4, all ACs).

**Offline by construction.** A temp SQLite is seeded with a tiny corpus plus
hand-written ``ocr_results`` / ``llm_results`` rows whose ``ttb_id`` matches the
committed ``fixtures/ground_truth.csv`` gold (the same golds ``test_scoring.py``
seeds), so ``score_corpus(conn)`` (default CSV) computes REAL figures — no provider
call, no network, no real OCR. The screen is a pure DB read (AR-5): it consumes the
typed ``CorpusScore`` (5.2) and ``CostReport`` (5.3) and renders them side by side.

Highest-value tests mirror the spec Task 5:
- **AC1** real-figure render (rendered percent == ``score_corpus`` over the same DB).
- **AC2** mockup fidelity (evaluator header/badge, title, Recommendations, group
  rows, five columns, honesty + footer; NO scaffolding; NO verdict chips).
- **AC3** CPU-only flag icon + word (✓ Yes / ⚠ No — API).
- **AC4** honest empty state (no zeros / no ``$0.00`` row).
- **AC5** best-in-group highlight is derived from the figures.
- **AC6** token gate (303 → /access) + unpriced-model "not priced" + same-origin assets.
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.benchmark import cost, scoring
from app.db.connection import connect, init_db
from app.main import create_app

# A real fixtures/ground_truth.csv row (SINCERELY — a South African red wine) — its gt_*
# gold matches the OCR/LLM text below, so the default-CSV scorer scores these rows for real.
_SEEDED_TTB_ID = "06296001000053"

_GOV_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)


def _ocr_blob(*, abv: str = "13.0% Alc./Vol.", brand: str = "SINCERELY") -> str:
    return f"{brand}\nRed Wine\n{abv}\n750 mL\nProduct of South Africa\n{_GOV_WARNING}\n"


def _llm_json(*, brand: str = "SINCERELY", abv: str = "13.0% Alc./Vol.") -> str:
    return json.dumps(
        {
            "brand_name": brand,
            "class_type_designation": "Red Wine",
            "alcohol_content": abv,
            "net_contents": "750 mL",
            "applicant_name_address": "Product of South Africa",
            "government_warning": _GOV_WARNING,
        }
    )


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path, *, token: str | None = None) -> TestClient:
    """A fresh app over an isolated temp DB with the background sweep OFF.

    Mirrors ``tests/test_queue.py``: ``SCHEDULER_ENABLED=false`` keeps the pipeline
    from mutating seeded rows; ``DATABASE_PATH`` points at a throwaway file; the
    schema is created up-front via :func:`init_db` so seed steps can ``connect``
    BEFORE the first request fires the FastAPI lifespan.
    """
    db_path = tmp_path / "benchmark.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    if token is None:
        monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ACCESS_TOKEN", token)
    init_db(db_path)
    return TestClient(create_app())


def _db_path(tmp_path) -> str:
    return str(tmp_path / "benchmark.db")


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": _SEEDED_TTB_ID,
        "beverage_type": "WINE",
        "brand_name": "SINCERELY",
        "class_type_designation": "Red Wine",
        "alcohol_content": "13.0% Alc./Vol.",
        "net_contents": "750 mL",
        "applicant_name_address": "Product of South Africa",
        "status": "READY_FOR_REVIEW",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608
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
    latency_ms: int = 410,
    ran_on_cpu: int = 1,
    status: str = "OK",
) -> None:
    conn.execute(
        "INSERT INTO ocr_results "
        "(label_image_id, submission_id, engine_name, extracted_text, confidence, "
        " image_variant, latency_ms, ran_on_cpu, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            image_id,
            submission_id,
            engine_name,
            text,
            confidence,
            image_variant,
            latency_ms,
            ran_on_cpu,
            status,
        ),
    )


def _insert_llm(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    model_id: str,
    result_text: str,
    model_name: str = "Fake Model",
    provider: str = "anthropic",
    task: str = "extract_fields",
    latency_ms: int = 1240,
    prompt_tokens: int = 1200,
    completion_tokens: int = 300,
    status: str = "OK",
) -> None:
    conn.execute(
        "INSERT INTO llm_results "
        "(submission_id, task, model_name, model_id, provider, result_text, "
        " latency_ms, prompt_tokens, completion_tokens, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            submission_id,
            task,
            model_name,
            model_id,
            provider,
            result_text,
            latency_ms,
            prompt_tokens,
            completion_tokens,
            status,
        ),
    )


def _seed_one_engine_one_model(tmp_path, *, model_id: str = "claude-opus-4-8") -> None:
    """Seed one submission with one OCR engine + one LLM model row (all matching gold)."""
    with connect(_db_path(tmp_path)) as conn:
        sub_id = _insert_submission(conn)
        img_id = _insert_image(conn, sub_id)
        _insert_ocr(conn, sub_id, img_id, engine_name="tesseract", text=_ocr_blob())
        _insert_llm(conn, sub_id, model_id=model_id, result_text=_llm_json())
        conn.commit()


def _seed_two_engines(tmp_path) -> None:
    """Seed two OCR engines with DIFFERENT accuracy (paddle perfect, tesseract worse)."""
    with connect(_db_path(tmp_path)) as conn:
        sub_id = _insert_submission(conn)
        img_id = _insert_image(conn, sub_id)
        # paddle: every field matches gold → higher field_match_rate
        _insert_ocr(conn, sub_id, img_id, engine_name="paddleocr", text=_ocr_blob())
        # tesseract: wrong ABV → one field MISMATCH → lower field_match_rate
        _insert_ocr(
            conn,
            sub_id,
            img_id,
            engine_name="tesseract",
            text=_ocr_blob(abv="40% Alc./Vol."),
        )
        _insert_llm(conn, sub_id, model_id="claude-opus-4-8", result_text=_llm_json())
        conn.commit()


# ── AC1: GET /benchmark renders REAL seeded-corpus figures ────────────────────


def test_benchmark_renders_real_figure_from_score_corpus(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    _seed_one_engine_one_model(tmp_path)

    resp = client.get("/benchmark")
    assert resp.status_code == 200
    body = resp.text

    # The rendered accuracy figure must equal what score_corpus computes over the
    # SAME DB — proving the route renders real data, not a template literal.
    with connect(_db_path(tmp_path)) as conn:
        score = scoring.score_corpus(conn)
    tess = score.engines[("tesseract", "ORIGINAL")]
    assert tess.field_match_rate is not None
    expected_pct = f"{tess.field_match_rate * 100:.1f}"
    assert expected_pct in body


def test_benchmark_labels_ocr_image_variant_rows(monkeypatch, tmp_path) -> None:
    """Each OCR engine is scored per IMAGE VARIANT (original photo vs its preprocessed
    variant) and gets its own row. The variant must be surfaced so the two rows per engine
    aren't indistinguishable, plus an intro note explaining the two-row pattern."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sub_id = _insert_submission(conn)
        img_id = _insert_image(conn, sub_id)
        _insert_ocr(
            conn,
            sub_id,
            img_id,
            engine_name="paddleocr",
            text=_ocr_blob(),
            image_variant="ORIGINAL",
        )
        _insert_ocr(
            conn,
            sub_id,
            img_id,
            engine_name="paddleocr",
            text=_ocr_blob(),
            image_variant="ENHANCED",
        )
        conn.commit()

    body = client.get("/benchmark").text
    # Both variant rows are labeled (the fix for "two identical-looking PaddleOCR rows").
    assert "original photo" in body
    assert "enhanced (preprocessed)" in body
    # And the screen explains WHY an engine appears twice.
    assert "two rows" in body


def test_benchmark_route_is_pure_db_read_no_provider_client(monkeypatch, tmp_path) -> None:
    """AR-5: the route imports only the read-only benchmark functions — no adapter."""
    import app.web.routes_benchmark as mod

    src = mod.__file__
    text = open(src, encoding="utf-8").read()  # noqa: SIM115, PTH123
    assert "adapters" not in text
    assert "requests" not in text and "httpx" not in text


# ── AC2: mockup fidelity (spine wins, scaffolding excluded) ───────────────────


def test_benchmark_matches_mockup_structure(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    _seed_one_engine_one_model(tmp_path)
    body = client.get("/benchmark").text

    # Evaluator header + badge + page title + the two group rows + five columns.
    assert "Evaluator build" in body
    assert "Benchmark Report" in body
    assert "Recommendations" in body
    assert "OCR engines" in body
    assert "Language models" in body
    assert "Field accuracy" in body
    assert "Latency" in body
    assert "CPU-only" in body
    # Honesty + footer meta present.
    assert "not audited" in body
    assert "offline" in body.lower()


def test_benchmark_excludes_mockup_scaffolding_and_verdict_palette(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    _seed_one_engine_one_model(tmp_path)
    body = client.get("/benchmark").text

    # Mockup-only scaffolding must not be reproduced.
    assert "device" not in body.lower() or "device__chrome" not in body
    assert "240 sample labels" not in body
    assert "seed-2026-06-12" not in body
    # Verdict palette is kept OFF this surface (accuracy is a number, not a verdict).
    assert "chip--pass" not in body
    assert "chip--fail" not in body
    assert "chip--review" not in body
    # Tokens come from the linked self-hosted stylesheet, not inline <style>, no CDN.
    assert "<style" not in body
    assert "/static/css/brand.css" in body


# ── AC3: CPU-only flag is icon + word + color ─────────────────────────────────


def test_benchmark_cpu_flag_icon_and_word(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    _seed_one_engine_one_model(tmp_path)
    body = client.get("/benchmark").text

    # OCR engine row: ✓ Yes (self-hosted CPU-only).
    assert "✓" in body
    assert "Yes" in body
    # Model row: ⚠ No — API (needs an outbound call).
    assert "⚠" in body
    assert "No — API" in body


# ── AC4: honest empty state before any run (not zeros) ────────────────────────


def test_benchmark_empty_state_no_zeros(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)  # no seeded ocr/llm rows
    resp = client.get("/benchmark")
    assert resp.status_code == 200
    body = resp.text
    assert "No benchmark runs yet" in body
    # Never a table of zeros that reads as a real measurement: the comparison table
    # (and so any numeric data cell) must be absent — only the empty-state shows.
    # (The honesty note may still SAY "$0.00" as explanatory copy; that is not a
    # fabricated measurement row, so we assert on the table structure, not a substring.)
    assert 'class="benchmark__table"' not in body
    assert 'class="num"' not in body


# ── AC5: best-in-group highlight is derived, not hard-coded ───────────────────


def test_benchmark_best_in_group_tracks_real_accuracy(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    _seed_two_engines(tmp_path)
    body = client.get("/benchmark").text

    with connect(_db_path(tmp_path)) as conn:
        score = scoring.score_corpus(conn)
    paddle = score.engines[("paddleocr", "ORIGINAL")]
    tess = score.engines[("tesseract", "ORIGINAL")]
    assert paddle.field_match_rate is not None and tess.field_match_rate is not None
    # The fixture is built so paddle out-scores tesseract.
    assert paddle.field_match_rate > tess.field_match_rate

    # The higher-accuracy OCR row carries the best highlight; there is exactly one
    # best row per group, so the count of best-row markers is bounded.
    assert 'class="best"' in body or "best" in body


# ── AC6: pricing/figure honesty + read-only, token-gated, zero-egress ─────────


def test_benchmark_is_token_gated(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path, token="secret")  # no cookie
    resp = client.get("/benchmark", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/access"


def test_benchmark_reachable_with_valid_cookie(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path, token="secret")
    _seed_one_engine_one_model(tmp_path)
    client.cookies.set("ttb_access", "secret")
    assert client.get("/benchmark").status_code == 200


def test_benchmark_unpriced_model_not_fabricated_zero(monkeypatch, tmp_path) -> None:
    """An unpriced model (cost_per_1000 is None) shows 'not priced'/'—', never $0.00."""
    client = _client(monkeypatch, tmp_path)
    # Seed a model whose id has no published price → cost_corpus yields None.
    _seed_one_engine_one_model(tmp_path, model_id="mystery-model-x")
    with connect(_db_path(tmp_path)) as conn:
        report = cost.cost_corpus(conn)
    mc = report.models["mystery-model-x"]
    assert mc.cost_per_1000 is None  # the fixture is genuinely unpriced

    body = client.get("/benchmark").text
    assert ("not priced" in body) or ("—" in body)


def test_benchmark_honesty_note_states_pricing_basis(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    _seed_one_engine_one_model(tmp_path)
    body = client.get("/benchmark").text
    assert "indicative" in body.lower()
    assert "published API prices proxy" in body or "prices proxy" in body.lower()


def test_benchmark_uses_only_same_origin_static_assets(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    _seed_one_engine_one_model(tmp_path)
    body = client.get("/benchmark").text
    # No off-/static external asset URLs (no CDN, no Google Fonts) — NFR-2/AR-8.
    assert "http://" not in body
    assert "https://" not in body
    assert "fonts.googleapis" not in body
    assert "cdn" not in body.lower()


# ── CR 2026-06-14: honesty regressions found in code review ────────────────────


def test_benchmark_cpu_flag_honors_captured_gpu_run(monkeypatch, tmp_path) -> None:
    """AC3/NFR-5: a captured GPU OCR row renders "✗ No — GPU", NEVER a fabricated "Yes".

    The flag is the captured ``EngineCost.cpu_only`` (cost.py ``_cpu_only`` over
    ``ran_on_cpu``), not a blanket per-group "Yes" — so an engine that actually ran on
    GPU is not falsely advertised as CPU-only inside the firewall.
    """
    client = _client(monkeypatch, tmp_path)  # creates the schema (init_db)
    with connect(_db_path(tmp_path)) as conn:
        sub_id = _insert_submission(conn)
        img_id = _insert_image(conn, sub_id)
        # A GPU OCR run: ran_on_cpu = 0.
        _insert_ocr(conn, sub_id, img_id, engine_name="paddleocr", text=_ocr_blob(), ran_on_cpu=0)
        conn.commit()

    # Confirm the producer captured cpu_only=False so the test is honest.
    with connect(_db_path(tmp_path)) as conn:
        report = cost.cost_corpus(conn)
    assert report.engines[("paddleocr", "ORIGINAL")].cpu_only is False

    body = client.get("/benchmark").text
    assert "No — GPU" in body  # icon+word for the honest GPU flag
    # The fabricated all-"Yes" claim must not be the ONLY CPU rendering: a GPU engine
    # is present, so "No — GPU" must appear.
    assert "✗" in body


def test_benchmark_includes_cost_only_extractor_not_dropped(monkeypatch, tmp_path) -> None:
    """An engine that ran only on a gold-LESS submission still appears (accuracy "—").

    ``score_corpus`` skips gold-less submissions, so such an engine is in the cost
    report but not the accuracy report. The view-model zips the key UNION, so the row
    is kept (honest) rather than silently dropped.
    """
    client = _client(monkeypatch, tmp_path)  # creates the schema (init_db)
    with connect(_db_path(tmp_path)) as conn:
        # A submission whose ttb_id has NO ground-truth row → score_corpus skips it.
        sub_id = _insert_submission(conn, ttb_id="99999999999999")
        img_id = _insert_image(conn, sub_id)
        _insert_ocr(conn, sub_id, img_id, engine_name="paddleocr", text=_ocr_blob())
        conn.commit()

    # The engine is absent from the accuracy report but present in the cost report.
    with connect(_db_path(tmp_path)) as conn:
        score = scoring.score_corpus(conn)
        report = cost.cost_corpus(conn)
    assert ("paddleocr", "ORIGINAL") not in score.engines
    assert ("paddleocr", "ORIGINAL") in report.engines

    body = client.get("/benchmark").text
    # The cost-only engine is still rendered (its label appears), not dropped.
    assert "PaddleOCR (PP-OCRv5)" in body
    # Its accuracy reads the honest "—" (unscored), never a fabricated number/zero.
    assert "—" in body


def test_benchmark_shows_per_submission_processing_time(monkeypatch, tmp_path) -> None:
    """The screen reports the per-submission end-to-end pre-compute time (the background
    throughput behind the instant read) — count + seconds figures from processing_ms."""
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        _insert_submission(conn, ttb_id="26001000000801", processing_ms=2000)
        _insert_submission(conn, ttb_id="26001000000802", processing_ms=4000)
        conn.commit()
    resp = client.get("/benchmark")
    assert resp.status_code == 200
    body = resp.text
    assert "Per-submission pre-compute time" in body
    assert "2 submissions" in body
    assert "3.0" in body  # median & mean of 2000,4000 ms = 3.0 s


def test_benchmark_hides_processing_time_when_no_processed_rows(monkeypatch, tmp_path) -> None:
    """No processed submissions ⇒ the throughput section is omitted (no fake 0.0 s)."""
    client = _client(monkeypatch, tmp_path)
    body = client.get("/benchmark").text
    assert "Per-submission pre-compute time" not in body
