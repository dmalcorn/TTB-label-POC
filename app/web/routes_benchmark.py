"""Benchmark Report screen (Story 5.4).

``GET /benchmark`` → the evaluator-facing procurement study: the candidate OCR
engines and language models laid side by side on field accuracy, latency, cost per
1,000 verifications, and the CPU-only flag, with grounded recommendations and the
"indicative, not audited" honesty note.

This is a thin **presentation layer over the two DONE producers**: it CONSUMES the
typed ``CorpusScore`` (Story 5.2 ``app.benchmark.scoring.score_corpus``) and
``CostReport`` (Story 5.3 ``app.benchmark.cost.cost_corpus``) — it never re-scores,
re-times, or re-prices (those are the centralized 5.2/5.3 contracts; AR-4 keeps them
engine-agnostic). The two reports use the SAME keys, so the route zips them
row-for-row, labels each row at the presentation boundary, and renders.

It honors the 5-second read contract (AR-5): a pure pre-computed DB read via
``connect()`` + the two read-only benchmark functions. It constructs NO provider
client, opens NO off-host socket, and runs NO OCR/inference at request time — it is
not on any model path. It carries no route-level exemption, so the ``app/main.py``
token-gate middleware protects it like every screen (Story 1.5). All template assets
are same-origin ``/static`` (NFR-2/AR-8). The screen is read-only — no form, no
decision/disposition control.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse

from app.benchmark import cost, scoring
from app.db.connection import connect

router = APIRouter()

# ── presentation-boundary display names ───────────────────────────────────────
# The typed aggregates are keyed by raw `engine_name` / `model_id` and do NOT retain
# friendly `model_name`/`provider`, so the mockup's labels are resolved HERE (never
# baked into the scorer's SQL — that keeps 5.2/5.3 engine-agnostic, AR-4 — and never
# hard-coded inside the template). An unknown key falls back to its raw value verbatim
# (honest, never blank).
_ENGINE_LABELS: dict[str, tuple[str, str]] = {
    # engine_name → (display name, muted sub-line)
    "paddleocr": ("PaddleOCR (PP-OCRv5)", "self-hosted, vendored"),
    "paddle": ("PaddleOCR (PP-OCRv5)", "self-hosted, vendored"),
    "tesseract": ("Tesseract 5", "self-hosted, vendored · fallback"),
}
_MODEL_LABELS: dict[str, str] = {
    # a coarse model_id → family label map; the figures come ONLY from the aggregates.
    "claude-opus-4-8": "Claude",
    "gpt-4o-mini": "GPT",
    "gemini-2.0-flash": "Gemini",
    "local-vlm": "Local VLM",
}
_MODEL_SUBLINE = "API · price proxies internal cost"


def _engine_label(engine_name: str) -> tuple[str, str]:
    """Friendly (name, sub-line) for an OCR engine; raw name verbatim if unknown."""
    return _ENGINE_LABELS.get(engine_name, (engine_name, "self-hosted"))


def _model_label(model_id: str) -> str:
    """Friendly display name for a model id, falling back to the raw id verbatim."""
    return _MODEL_LABELS.get(model_id, model_id or "—")


# ── the view-model rendered by the template ───────────────────────────────────


@dataclass(frozen=True, slots=True)
class BenchmarkRow:
    """One comparison-table row: a labeled zip of accuracy (5.2) + speed/cost (5.3).

    Figures are pre-formatted strings so the template stays presentation-only: the
    accuracy percent / latency / cost honesty (``None`` ⇒ "—" / "not priced", never a
    fabricated ``0`` or ``$0.00``) is decided here at the boundary.
    """

    name: str
    subline: str
    accuracy: str  # "96.4" percent-to-one-decimal, or "—"
    latency: str  # integer ms with thousands separator, or "—"
    cost: str  # "$0.00" / "$3.10" / "not priced"
    cost_basis: str  # the NFR-5 pricing-basis label (AC6), or "" when none captured
    cpu_only: bool | None  # True ⇒ ✓ Yes; False ⇒ ✗ No — GPU; None ⇒ ? unknown
    is_best: bool


def _fmt_accuracy(rate: float | None) -> str:
    """A field-match fraction in [0,1] → a one-decimal percent, or "—" when unscored."""
    return "—" if rate is None else f"{rate * 100:.1f}"


def _fmt_latency(mean_ms: float | None) -> str:
    """Mean latency → whole ms with a thousands separator, or "—" on an empty sample."""
    return "—" if mean_ms is None else f"{round(mean_ms):,}"


def _fmt_cost(cost_per_1000: Decimal | None) -> str:
    """A per-1,000 cost → ``$X.XX``; an unpriced model (``None``) → honest "not priced".

    Never fabricates ``$0.00`` for an unpriced provider model — local OCR genuinely
    carries ``Decimal("0")`` and renders ``$0.00`` with its "$0 marginal" basis.
    """
    if cost_per_1000 is None:
        return "not priced"
    return f"${cost_per_1000:.2f}"


def _fmt_seconds(ms: float | None) -> str:
    """Milliseconds → seconds to one decimal (e.g. ``3.2``), or "—" on an empty sample."""
    return "—" if ms is None else f"{ms / 1000:.1f}"


def _best_key(
    rates: dict[str, float | None],
) -> str | None:
    """The key with the highest field-match rate (ties broken by sorted key).

    Skips keys whose rate is ``None`` (unscored). Returns ``None`` when no key has a
    verifiable rate — so the highlight tracks the real data, never a template literal.
    """
    scored = {k: r for k, r in rates.items() if r is not None}
    if not scored:
        return None
    # max by rate; ``sorted`` first makes the tie-break stable (lowest key wins).
    return max(sorted(scored), key=lambda k: scored[k])


def _build_engine_rows(score: scoring.CorpusScore, report: cost.CostReport) -> list[BenchmarkRow]:
    """Zip the OCR accuracy + speed/cost aggregates by their shared key, label, format.

    Iterates the **union** of the accuracy and cost keysets in stable sorted key
    order: ``score_corpus`` only accumulates engines seen on a ground-truth-having
    submission, while ``cost_corpus`` groups every captured ``OK`` row corpus-wide —
    so an engine that ran only on gold-less submissions appears in cost but not
    accuracy. Iterating the union keeps that engine in the table (accuracy "—") rather
    than silently dropping it. Marks the best-in-group (highest ``field_match_rate``)
    row ``is_best``; the CPU-only flag is the captured ``EngineCost.cpu_only`` (AC3 —
    never fabricated), not a blanket "Yes".
    """
    keys = sorted(set(score.engines) | set(report.engines))
    rates = {
        f"{name}\x00{variant}": (
            score.engines[(name, variant)].field_match_rate
            if (name, variant) in score.engines
            else None
        )
        for (name, variant) in keys
    }
    best = _best_key(rates)
    rows: list[BenchmarkRow] = []
    for engine_name, variant in keys:
        es = score.engines.get((engine_name, variant))
        ec = report.engines.get((engine_name, variant))
        label, subline = _engine_label(engine_name)
        rows.append(
            BenchmarkRow(
                name=label,
                subline=subline,
                accuracy=_fmt_accuracy(es.field_match_rate if es else None),
                latency=_fmt_latency(ec.latency.mean_ms if ec else None),
                # Local OCR is genuinely $0 marginal API cost (cost.py _LOCAL_BASIS).
                cost=_fmt_cost(ec.cost_per_1000 if ec else None),
                cost_basis=(ec.cost_basis if ec else ""),
                # Honest captured flag: True (CPU) / False (a GPU row) / None (unknown).
                cpu_only=(ec.cpu_only if ec else None),
                is_best=(f"{engine_name}\x00{variant}" == best),
            )
        )
    return rows


def _build_model_rows(score: scoring.CorpusScore, report: cost.CostReport) -> list[BenchmarkRow]:
    """Zip the model accuracy + speed/cost aggregates by ``model_id``, label, format.

    Iterates the **union** of the accuracy and cost keysets (see ``_build_engine_rows``)
    so a model that ran only on gold-less submissions still appears (accuracy "—")
    rather than being dropped. Surfaces ``ModelCost.cost_basis`` (the NFR-5 pricing
    basis) so a priced model's dollar figure carries its provenance (AC6).
    """
    keys = sorted(set(score.models) | set(report.models))
    rates = {k: (score.models[k].field_match_rate if k in score.models else None) for k in keys}
    best = _best_key(rates)
    rows: list[BenchmarkRow] = []
    for model_id in keys:
        ms = score.models.get(model_id)
        mc = report.models.get(model_id)
        rows.append(
            BenchmarkRow(
                name=_model_label(model_id),
                subline=_MODEL_SUBLINE,
                accuracy=_fmt_accuracy(ms.field_match_rate if ms else None),
                latency=_fmt_latency(mc.latency.mean_ms if mc else None),
                cost=_fmt_cost(mc.cost_per_1000 if mc else None),
                cost_basis=(mc.cost_basis or "" if mc else ""),
                cpu_only=False,
                is_best=(model_id == best),
            )
        )
    return rows


@router.get("/benchmark", response_class=HTMLResponse)
def benchmark(request: Request) -> Response:
    """Render the Benchmark Report from the real seeded-corpus figures (read-only).

    Pure pre-computed DB read (AR-5): score + cost the captured corpus rows via the
    two read-only benchmark functions, zip/label/format them into the view-model, and
    render. No provider client, no socket, no inference. When no scorable rows exist
    yet, ``has_data`` is False and the template shows the honest "No benchmark runs
    yet" empty state instead of a table of zeros (AC4 / NFR-5).
    """
    settings = request.app.state.settings
    templates = request.app.state.templates
    with connect(settings.database_path) as conn:
        score = scoring.score_corpus(conn)
        report = cost.cost_corpus(conn)
        proc = cost.processing_time_summary(conn)

    engine_rows = _build_engine_rows(score, report)
    model_rows = _build_model_rows(score, report)
    has_data = bool(engine_rows or model_rows)

    return templates.TemplateResponse(
        request,
        "benchmark.html",
        {
            "has_data": has_data,
            "engine_rows": engine_rows,
            "model_rows": model_rows,
            "fixture_count": score.scored_submissions,
            # Per-submission pre-compute throughput (the background cost behind the
            # instant read) — pre-formatted to seconds so the template stays presentational.
            "processing_time": {
                "count": proc.count,
                "median_s": _fmt_seconds(proc.median_ms),
                "mean_s": _fmt_seconds(proc.mean_ms),
                "p95_s": _fmt_seconds(proc.p95_ms),
                "min_s": _fmt_seconds(proc.min_ms),
                "max_s": _fmt_seconds(proc.max_ms),
            },
        },
    )
