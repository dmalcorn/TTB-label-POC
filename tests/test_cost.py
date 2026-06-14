"""Speed & cost statistics tests (Story 5.3, all ACs).

**Offline by construction.** A temp SQLite is seeded with a tiny corpus plus
hand-written ``ocr_results`` / ``llm_results`` rows carrying ``latency_ms`` /
``ran_on_cpu`` / token counts — no provider call, no network, no real OCR.
Speed/cost is a pure read/compute step, so the whole suite runs under
``docker run --network none``. Highest-value tests: the **cost-per-1,000**
``Decimal`` computation (priced / local-$0 / unpriced-None), the **latency
mean/median/p95** sample, the **CPU-only flag**, **reproducibility** (twice ⇒
identical), and the **egress/read-only structural guard**.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from app.benchmark import cost
from app.db.connection import connect, init_db


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "cost.db"
    init_db(db_path)
    return db_path


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26001000000001",
        "beverage_type": "DISTILLED_SPIRITS",
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
    latency_ms: int | None = 100,
    ran_on_cpu: bool | None = True,
    image_variant: str = "ORIGINAL",
    status: str = "OK",
) -> None:
    conn.execute(
        "INSERT INTO ocr_results "
        "(label_image_id, submission_id, engine_name, extracted_text, latency_ms, "
        " ran_on_cpu, image_variant, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            image_id,
            submission_id,
            engine_name,
            "text",
            latency_ms,
            ran_on_cpu,
            image_variant,
            status,
        ),
    )


def _insert_llm(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    model_id: str,
    latency_ms: int | None = 1000,
    prompt_tokens: int | None = 1000,
    completion_tokens: int | None = 200,
    model_name: str = "Fake Model",
    provider: str = "local",
    task: str = "extract_fields",
    status: str = "OK",
) -> None:
    conn.execute(
        "INSERT INTO llm_results "
        "(submission_id, task, model_name, model_id, provider, latency_ms, "
        " prompt_tokens, completion_tokens, result_text, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            submission_id,
            task,
            model_name,
            model_id,
            provider,
            latency_ms,
            prompt_tokens,
            completion_tokens,
            "{}",
            status,
        ),
    )


# ── AC1: latency mean/median/p95 over the captured samples ───────────────────


def test_latency_stats_over_known_sample():
    """mean/median/p95 + count over a known ms sample; documented percentile method."""
    stats = cost.latency_stats([100, 200, 300, 400, 500])
    assert stats.count == 5
    assert stats.mean_ms == 300.0
    assert stats.median_ms == 300.0
    # nearest-rank p95 of 5 sorted values ⇒ the top value.
    assert stats.p95_ms == 500.0


def test_latency_stats_excludes_null_latency():
    """NULL latency rows are dropped from the statistic and the count (AC1)."""
    stats = cost.latency_stats([100, None, 300, None])
    assert stats.count == 2
    assert stats.mean_ms == 200.0


def test_latency_stats_empty_sample_is_none_not_zero():
    """An empty/all-NULL sample ⇒ stats None, count 0 (honest, not a fake 0)."""
    stats = cost.latency_stats([None, None])
    assert stats.count == 0
    assert stats.mean_ms is None
    assert stats.median_ms is None
    assert stats.p95_ms is None


def test_corpus_latency_keyed_by_engine_variant_and_model(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        img_id = _insert_image(conn, sub_id)
        _insert_ocr(conn, sub_id, img_id, engine_name="tesseract", latency_ms=100)
        _insert_ocr(
            conn, sub_id, img_id, engine_name="tesseract", latency_ms=300, image_variant="BINARIZED"
        )
        _insert_llm(conn, sub_id, model_id="fake-1", latency_ms=1000)
    with connect(db_path) as conn:
        report = cost.cost_corpus(conn)

    # OCR keyed (engine, variant); the two variants are distinct keys.
    assert report.engines[("tesseract", "ORIGINAL")].latency.mean_ms == 100.0
    assert report.engines[("tesseract", "BINARIZED")].latency.mean_ms == 300.0
    # LLM keyed model_id.
    assert report.models["fake-1"].latency.mean_ms == 1000.0
    assert report.verification_count == 1


# ── AC2: cost-per-1,000 (Decimal, local-$0, unpriced-None, labeled basis) ─────


def test_cost_per_1000_from_known_tokens_and_price():
    """Hand-computed Decimal: 1000 prompt + 200 completion @ $0.003/$0.015 per 1k."""
    price = cost.ModelPrice(
        input_price_per_1k=Decimal("0.003"),
        output_price_per_1k=Decimal("0.015"),
        source="provider price list",
        as_of="2026-06-14",
    )
    # per-verification = (1000/1000 * 0.003) + (200/1000 * 0.015) = 0.003 + 0.003 = 0.006
    per_verif = cost.cost_per_verification(1000.0, 200.0, price)
    assert per_verif == Decimal("0.006000")
    per_1000 = cost.cost_per_1000(1000.0, 200.0, price)
    assert per_1000 == Decimal("6.000000")
    assert isinstance(per_1000, Decimal)


def test_unpriced_model_yields_none_not_zero():
    """No supplied price ⇒ cost is None (honest 'not priced'), never a fabricated 0."""
    assert cost.cost_per_1000(1000.0, 200.0, None) is None


def test_local_model_is_zero_api_cost_labeled(tmp_path):
    """A provider=local model ⇒ $0 marginal API cost, labeled local (AC2/§7.1)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        _insert_image(conn, sub_id)
        _insert_llm(conn, sub_id, model_id="local-vlm", provider="local")
    with connect(db_path) as conn:
        report = cost.cost_corpus(conn)
    model = report.models["local-vlm"]
    assert model.cost_per_1000 == Decimal("0")
    assert model.cost_basis is not None
    assert "local" in model.cost_basis.lower()


def test_priced_model_carries_pricing_basis_label(tmp_path):
    """A priced provider model surfaces its source + as-of date in the basis label."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        _insert_image(conn, sub_id)
        _insert_llm(
            conn,
            sub_id,
            model_id="gpt-x",
            provider="openai",
            prompt_tokens=1000,
            completion_tokens=200,
        )
    pricing = {
        "gpt-x": cost.ModelPrice(
            input_price_per_1k=Decimal("0.003"),
            output_price_per_1k=Decimal("0.015"),
            source="OpenAI published prices",
            as_of="2026-06-14",
        )
    }
    with connect(db_path) as conn:
        report = cost.cost_corpus(conn, pricing=pricing)
    model = report.models["gpt-x"]
    assert model.cost_per_1000 == Decimal("6.000000")
    assert model.cost_basis is not None
    assert "OpenAI published prices" in model.cost_basis
    assert "2026-06-14" in model.cost_basis


def test_unpriced_provider_model_in_corpus_is_none(tmp_path):
    """A non-local model with no pricing-table entry ⇒ cost_per_1000 None (not 0)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        _insert_image(conn, sub_id)
        _insert_llm(conn, sub_id, model_id="gemini-x", provider="google")
    with connect(db_path) as conn:
        report = cost.cost_corpus(conn)  # default table is TODO/empty
    assert report.models["gemini-x"].cost_per_1000 is None


def test_money_is_decimal_never_float():
    """Cost math is Decimal; floats never enter the currency path."""
    price = cost.ModelPrice(
        input_price_per_1k=Decimal("0.01"),
        output_price_per_1k=Decimal("0.02"),
        source="x",
        as_of="y",
    )
    result = cost.cost_per_1000(500.0, 500.0, price)
    assert isinstance(result, Decimal)


# ── AC3: CPU-only flag ───────────────────────────────────────────────────────


def test_cpu_only_flag_true_and_false(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        img_id = _insert_image(conn, sub_id)
        _insert_ocr(conn, sub_id, img_id, engine_name="tesseract", ran_on_cpu=True)
        _insert_ocr(
            conn,
            sub_id,
            img_id,
            engine_name="paddleocr",
            ran_on_cpu=False,
            image_variant="ENHANCED",
        )
    with connect(db_path) as conn:
        report = cost.cost_corpus(conn)
    assert report.engines[("tesseract", "ORIGINAL")].cpu_only is True
    assert report.engines[("paddleocr", "ENHANCED")].cpu_only is False


def test_cpu_only_flag_none_when_unflagged(tmp_path):
    """An OCR engine whose rows never recorded ran_on_cpu ⇒ cpu_only None (honest unknown)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        img_id = _insert_image(conn, sub_id)
        _insert_ocr(conn, sub_id, img_id, engine_name="tesseract", ran_on_cpu=None)
    with connect(db_path) as conn:
        report = cost.cost_corpus(conn)
    assert report.engines[("tesseract", "ORIGINAL")].cpu_only is None


def test_local_ocr_engine_carries_zero_api_cost_floor(tmp_path):
    """Every OCR engine×variant carries the $0 marginal API-cost floor, labeled local (§7.1)."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        img_id = _insert_image(conn, sub_id)
        _insert_ocr(conn, sub_id, img_id, engine_name="tesseract")
    with connect(db_path) as conn:
        report = cost.cost_corpus(conn)
    engine = report.engines[("tesseract", "ORIGINAL")]
    assert engine.cost_per_1000 == Decimal("0")
    assert "local" in engine.cost_basis.lower()


def test_mixed_provider_model_not_fabricated_zero(tmp_path):
    """A model_id with a mislabeled local row mixed among paid rows must NOT be $0.

    Grouping is by model_id; `any(provider==local)` would let one local row stamp the
    whole paid model $0 — the fabricated zero AC2/NFR-5 forbid. With no price supplied,
    the honest result is cost_per_1000 None, never Decimal('0')."""
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        _insert_image(conn, sub_id)
        _insert_llm(conn, sub_id, model_id="gpt-x", provider="local")
        _insert_llm(conn, sub_id, model_id="gpt-x", provider="openai")
    with connect(db_path) as conn:
        report = cost.cost_corpus(conn)  # no pricing for gpt-x
    model = report.models["gpt-x"]
    assert model.cost_per_1000 is None
    assert model.cost_per_1000 != Decimal("0")


# ── AC4: reproducible across the corpus ──────────────────────────────────────


def test_cost_corpus_is_reproducible(tmp_path):
    db_path = _make_db(tmp_path)
    with connect(db_path) as conn:
        sub_id = _insert_submission(conn)
        img_id = _insert_image(conn, sub_id)
        _insert_ocr(conn, sub_id, img_id, engine_name="tesseract", latency_ms=100)
        _insert_ocr(conn, sub_id, img_id, engine_name="paddleocr", latency_ms=250)
        _insert_llm(conn, sub_id, model_id="fake-1")
    pricing = {
        "fake-1": cost.ModelPrice(
            input_price_per_1k=Decimal("0.003"),
            output_price_per_1k=Decimal("0.015"),
            source="x",
            as_of="2026-06-14",
        )
    }
    with connect(db_path) as conn:
        first = cost.cost_corpus(conn, pricing=pricing)
    with connect(db_path) as conn:
        second = cost.cost_corpus(conn, pricing=pricing)
    assert asdict(first) == asdict(second)


# ── AC5: egress / read-only structural guard ─────────────────────────────────

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


def _cost_source() -> str:
    path = Path(__file__).resolve().parents[1] / "app" / "benchmark" / "cost.py"
    return path.read_text(encoding="utf-8")


def test_cost_constructs_no_off_host_client():
    """Cost is local analysis — it opens no off-host connection (NFR-2, AC5)."""
    assert not _OFF_HOST_CLIENT.search(_cost_source())


def test_cost_issues_no_write_sql():
    """Cost is DB-read-only — no INSERT/UPDATE/DELETE in the module (AR-13, AC5)."""
    src = _cost_source().upper()
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM"):
        assert verb not in src, f"cost.py must not issue {verb!r}"
