"""Speed & cost statistics with cost-per-1,000 (Story 5.3, FR-22).

The benchmark's **speed + cost** roll-up: it reads every captured ``ocr_results``
timing row (per engine × image variant) and every ``extract_fields`` ``llm_results``
row (per model), and derives the procurement figures the benchmarking plan calls for:

- **latency** — per OCR engine×variant and per LLM model, as **mean / median (p50) /
  p95** over the captured ``latency_ms`` (the deployed app's ~5s claim depends on the
  *tail*, not the mean — benchmarking-plan §6);
- **CPU-only flag** — per OCR engine, from the captured ``ran_on_cpu`` (govt infra has
  no guaranteed GPU — the CPU numbers are the load-bearing ones; §2.1, §3, AC3);
- **cost-per-1,000 Verifications** — for every configuration. One **verification** =
  extracting the matchable fields for **one submission** (§7). Local OCR engines and
  ``provider == local`` models have **$0 marginal API cost** (§7.1, the zero-egress
  floor); provider models cost
  ``((mean_prompt_tokens/1000 × input_price) + (mean_completion_tokens/1000 ×
  output_price)) × 1000`` (§7.2) from a **labeled** pricing table (``ModelPrice``
  carrying ``source`` + ``as_of`` — published API prices proxy an internally-hosted
  model; NFR-5). A model with **no supplied price** yields ``cost_per_1000 = None``
  (honest "not priced"), never a fabricated zero.

**Money is ``Decimal``, never float** (project-context: ``cost_usd`` as decimal/string —
never float math on currency); latency is integer ms summarized to plain floats.
``cost_usd`` is **computed here at analysis time, never persisted** — no schema change
(data-dictionary §4, benchmarking-plan §3).

**Posture.** Pure local analysis: DB **reads only** (SELECT-only repository helpers over
``ocr_results`` / ``llm_results``); it opens no off-host connection, constructs no
provider client, makes no model call (VLM-only purity untouched — it reads captured
*outputs*, never feeds a model), writes nothing, and is never on a request/render path
(AR-5). The figures are **reproducible**: stable sorted iteration, pure functions over
the rows, a fixed nearest-rank percentile method, ``Decimal`` money quantized to a fixed
precision — no wall-clock / RNG (AC4). Story 5.4's report screen consumes this typed
object; it does not re-compute.
"""

from __future__ import annotations

import math
import sqlite3
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from app.db import repositories as repo

# Fixed money precision so the Decimal figures are exact and reproducible (AC4).
_MONEY_QUANTUM = Decimal("0.000001")
# A verification's per-1,000 multiplier (one verification = one submission; §7).
_PER_1000 = Decimal("1000")

# Marker provider whose marginal API cost is $0 by definition (§7.1): the local,
# zero-egress model option. Local OCR engines are likewise $0 API.
_LOCAL_PROVIDER = "local"


# ── latency statistics (the tail, not just the mean) ─────────────────────────


@dataclass(frozen=True, slots=True)
class LatencyStats:
    """Per-extractor latency summary over the captured ``latency_ms`` samples.

    ``mean_ms`` / ``median_ms`` (p50) / ``p95_ms`` in milliseconds (plain floats —
    not currency). ``count`` is the number of non-NULL samples the stats cover; an
    empty sample yields all-``None`` stats with ``count = 0`` (honest, not a fake 0)."""

    count: int = 0
    mean_ms: float | None = None
    median_ms: float | None = None
    p95_ms: float | None = None


def latency_stats(values: Sequence[int | None]) -> LatencyStats:
    """Mean / median / p95 over the non-NULL ``latency_ms`` samples (AC1).

    NULL latencies are dropped from both the statistic and the count. The percentile
    is **nearest-rank** over the sorted samples (a fixed, documented method so re-runs
    are byte-identical — AC4): for ``n`` sorted values, p95 is the value at
    1-based rank ``ceil(0.95 × n)``. Empty sample ⇒ all stats ``None``, ``count = 0``."""
    kept = sorted(v for v in values if v is not None)
    if not kept:
        return LatencyStats()
    return LatencyStats(
        count=len(kept),
        mean_ms=statistics.fmean(kept),
        median_ms=statistics.median(kept),
        p95_ms=float(_nearest_rank(kept, 0.95)),
    )


def _nearest_rank(sorted_values: Sequence[int], percentile: float) -> int:
    """Nearest-rank percentile over an already-sorted, non-empty sequence.

    Deterministic and integer-indexed (no interpolation), so it is stable across
    re-runs and small samples. Rank = ``ceil(percentile × n)`` clamped to ``[1, n]``."""
    n = len(sorted_values)
    rank = max(1, min(math.ceil(percentile * n), n))
    return sorted_values[rank - 1]


# ── per-submission pre-compute throughput (the background cost behind the read) ──


@dataclass(frozen=True, slots=True)
class ProcessingTimeSummary:
    """Per-SUBMISSION end-to-end pre-compute time (``submissions.processing_ms``).

    Distinct from the per-extractor :class:`LatencyStats` above: this is the WHOLE
    background pipeline's wall-time per submission (preprocess → OCR → analysis), which
    runs once at submission time — off the reviewer's read path. It is the throughput
    picture behind the ~5-second read claim (the specialist never waits on it). ``count``
    is the number of processed submissions covered; an empty corpus ⇒ all-``None``."""

    count: int = 0
    min_ms: int | None = None
    median_ms: float | None = None
    mean_ms: float | None = None
    p95_ms: float | None = None
    max_ms: int | None = None


def processing_time_summary(conn: sqlite3.Connection) -> ProcessingTimeSummary:
    """Summarize per-submission ``processing_ms`` across the processed corpus.

    Reads every non-NULL ``submissions.processing_ms`` once (SELECT-only) and reduces to
    count / min / median / mean / p95 / max — reusing :func:`latency_stats` for the
    mean/median/p95 so the method matches the per-extractor figures. Empty sample ⇒ an
    all-``None`` summary with ``count = 0`` (honest, not a fabricated zero)."""
    kept = sorted(repo.list_processing_ms(conn))
    if not kept:
        return ProcessingTimeSummary()
    base = latency_stats(kept)
    return ProcessingTimeSummary(
        count=base.count,
        min_ms=kept[0],
        median_ms=base.median_ms,
        mean_ms=base.mean_ms,
        p95_ms=base.p95_ms,
        max_ms=kept[-1],
    )


# ── pricing basis (labeled — NFR-5) ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """A provider model's published token price + the **labeled** pricing basis.

    ``input_price_per_1k`` / ``output_price_per_1k`` are ``$``/1k-token ``Decimal``
    prices. ``source`` + ``as_of`` are the NFR-5 honesty label: published provider API
    prices **proxy** the cost of an internally-hosted model and **change over time**, so
    every priced figure carries where the price came from and when (benchmarking-plan
    §7.3, data-dictionary §4 "pricing source still open")."""

    input_price_per_1k: Decimal
    output_price_per_1k: Decimal
    source: str
    as_of: str

    @property
    def basis_label(self) -> str:
        """The human-readable pricing basis: ``"<source> (as of <as_of>)"``."""
        return f"{self.source} (as of {self.as_of})"


# A pricing table keyed by ``model_id``. Local engines/``provider == local`` are the
# $0 API floor (no entry needed). A non-local model absent from the table is unpriced.
PricingTable = dict[str, ModelPrice]

# The default pricing table is intentionally TODO-priced (empty): real per-model prices
# + as-of dates drop in after real runs (benchmarking-plan §7.3 "numbers PENDING"). The
# mechanism and the labeling are what this story lands — an unpriced provider model
# honestly reports ``cost_per_1000 = None``, never a fabricated zero.
DEFAULT_PRICING: PricingTable = {}

# The labeled basis for the local/zero-egress $0 floor (§7.1).
_LOCAL_BASIS = "local — $0 marginal API cost"


# ── cost rule (Decimal money; §7.2) ──────────────────────────────────────────


def cost_per_verification(
    mean_prompt_tokens: float,
    mean_completion_tokens: float,
    price: ModelPrice | None,
) -> Decimal | None:
    """Estimated ``$``/verification for one model (benchmarking-plan §7.2).

    ``(mean_prompt_tokens/1000 × input_price) + (mean_completion_tokens/1000 ×
    output_price)`` in **``Decimal``** (never float on currency), quantized to a fixed
    precision for reproducibility. ``price is None`` ⇒ ``None`` (honest "not priced",
    never a fabricated 0). The mean-token means are rounded to ``Decimal`` exactly via
    their string form so float noise never enters the money path."""
    if price is None:
        return None
    prompt = _to_decimal(mean_prompt_tokens) / Decimal("1000") * price.input_price_per_1k
    completion = _to_decimal(mean_completion_tokens) / Decimal("1000") * price.output_price_per_1k
    return (prompt + completion).quantize(_MONEY_QUANTUM)


def cost_per_1000(
    mean_prompt_tokens: float,
    mean_completion_tokens: float,
    price: ModelPrice | None,
) -> Decimal | None:
    """Estimated ``$``/1,000 Verifications: ``cost_per_verification × 1000`` (§7.2).

    ``price is None`` ⇒ ``None``. ``Decimal`` throughout, quantized for reproducibility."""
    per_verif = cost_per_verification(mean_prompt_tokens, mean_completion_tokens, price)
    if per_verif is None:
        return None
    return (per_verif * _PER_1000).quantize(_MONEY_QUANTUM)


def _to_decimal(value: float) -> Decimal:
    """A float token-mean → ``Decimal`` via its string form (no binary-float noise)."""
    return Decimal(str(value))


# ── corpus roll-up ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EngineCost:
    """One OCR engine×variant's speed + CPU-mode figures.

    Local OCR has **$0 marginal API cost** (§7.1), so no per-1,000 token cost is carried
    here — the procurement read is "free at the API line; latency is the cost." ``cpu_only``
    is the captured ``ran_on_cpu`` (AC3; ``None`` only if no row carried the flag)."""

    latency: LatencyStats = field(default_factory=LatencyStats)
    cpu_only: bool | None = None
    cost_per_1000: Decimal = Decimal("0")
    cost_basis: str = _LOCAL_BASIS


@dataclass(frozen=True, slots=True)
class ModelCost:
    """One LLM model's speed + token + cost-per-1,000 figures.

    ``cost_per_1000`` is ``Decimal("0")`` for a ``local`` model (§7.1 floor), a computed
    ``Decimal`` for a priced provider model (§7.2), or ``None`` for an unpriced provider
    model (honest "not priced"). ``cost_basis`` is the labeled pricing basis (NFR-5)."""

    latency: LatencyStats = field(default_factory=LatencyStats)
    mean_prompt_tokens: float | None = None
    mean_completion_tokens: float | None = None
    cost_per_1000: Decimal | None = None
    cost_basis: str | None = None


@dataclass(frozen=True, slots=True)
class CostReport:
    """The whole-corpus speed + cost result: per OCR engine×variant and per LLM model.

    ``engines`` is keyed by ``(engine_name, image_variant)`` and ``models`` by
    ``model_id`` — the SAME keys the accuracy scorer uses (Story 5.2 ``CorpusScore``), so
    speed/cost and accuracy line up row-for-row in the Story 5.4 report. ``verification_count``
    is the number of distinct submissions the figures cover (§7: one verification = one
    submission)."""

    engines: dict[tuple[str, str], EngineCost] = field(default_factory=dict)
    models: dict[str, ModelCost] = field(default_factory=dict)
    verification_count: int = 0


def cost_corpus(conn: sqlite3.Connection, *, pricing: PricingTable | None = None) -> CostReport:
    """Roll up speed + cost over the whole seeded corpus — the harness entrypoint.

    Reads the OCR timing rows and the LLM cost rows ONCE (the SELECT-only readers),
    groups OCR by ``(engine_name, image_variant)`` and LLM by ``model_id`` in stable
    sorted order, and per group computes ``latency_stats``; for OCR the CPU-only flag
    (AC3), for LLM the mean prompt/completion tokens and the cost-per-1,000 via the
    pricing table (local ⇒ $0, unpriced ⇒ None). Deterministic and DB-read-only (AC4,
    AC5). The pricing table defaults to the TODO-priced ``DEFAULT_PRICING``."""
    prices = pricing if pricing is not None else DEFAULT_PRICING

    ocr_rows = repo.list_ocr_latency_for_cost(conn)
    llm_rows = repo.list_llm_cost_rows(conn)

    # Group in stable insertion order (the readers already sort) → reproducible output.
    ocr_groups: dict[tuple[str, str], list[repo.OcrCostRow]] = {}
    for row in ocr_rows:
        ocr_groups.setdefault((row.engine_name, row.image_variant), []).append(row)

    llm_groups: dict[str, list[repo.LlmCostRow]] = {}
    for llm in llm_rows:
        llm_groups.setdefault(llm.model_id or "", []).append(llm)

    engines = {key: _engine_cost(ocr_groups[key]) for key in sorted(ocr_groups)}
    models = {key: _model_cost(key, llm_groups[key], prices) for key in sorted(llm_groups)}

    return CostReport(
        engines=engines,
        models=models,
        verification_count=_count_verifications(conn),
    )


def _engine_cost(rows: list[repo.OcrCostRow]) -> EngineCost:
    """Speed + CPU-mode for one OCR engine×variant (local ⇒ $0 API floor)."""
    return EngineCost(
        latency=latency_stats([r.latency_ms for r in rows]),
        cpu_only=_cpu_only(rows),
    )


def _cpu_only(rows: list[repo.OcrCostRow]) -> bool | None:
    """The CPU-only flag for an engine×variant (AC3).

    ``True`` only if every captured row that recorded the flag ran on CPU; ``False`` if
    any ran on GPU; ``None`` if no row carried the flag at all (honest unknown)."""
    flags = [r.ran_on_cpu for r in rows if r.ran_on_cpu is not None]
    if not flags:
        return None
    return all(flags)


def _model_cost(model_id: str, rows: list[repo.LlmCostRow], prices: PricingTable) -> ModelCost:
    """Speed + token + cost-per-1,000 for one LLM model.

    ``provider == local`` ⇒ ``Decimal("0")`` labeled local (§7.1). Otherwise look up the
    pricing table: priced ⇒ the computed ``Decimal`` with the labeled basis; unpriced ⇒
    ``None`` (honest "not priced")."""
    latency = latency_stats([r.latency_ms for r in rows])
    mean_prompt = _mean_tokens([r.prompt_tokens for r in rows])
    mean_completion = _mean_tokens([r.completion_tokens for r in rows])

    # Local ⇒ $0 ONLY when EVERY row for this model_id agrees it ran locally. A model
    # grouped by model_id could carry a mislabeled/mixed provider; ``any`` would let a
    # single local row stamp the whole (paid) model $0 — the exact fabricated-zero
    # AC2/NFR-5 forbid. ``all`` is honest: a disagreeing group falls through to the
    # pricing table (unpriced ⇒ None), never a fabricated $0.
    providers = [(r.provider or "") for r in rows]
    is_local = bool(providers) and all(p == _LOCAL_PROVIDER for p in providers)
    if is_local:
        return ModelCost(
            latency=latency,
            mean_prompt_tokens=mean_prompt,
            mean_completion_tokens=mean_completion,
            cost_per_1000=Decimal("0"),
            cost_basis=_LOCAL_BASIS,
        )

    price = prices.get(model_id)
    if price is None or mean_prompt is None or mean_completion is None:
        # Unpriced provider model (or no token samples) ⇒ honest "not priced".
        return ModelCost(
            latency=latency,
            mean_prompt_tokens=mean_prompt,
            mean_completion_tokens=mean_completion,
            cost_per_1000=None,
            cost_basis=None,
        )
    return ModelCost(
        latency=latency,
        mean_prompt_tokens=mean_prompt,
        mean_completion_tokens=mean_completion,
        cost_per_1000=cost_per_1000(mean_prompt, mean_completion, price),
        cost_basis=price.basis_label,
    )


def _mean_tokens(values: Sequence[int | None]) -> float | None:
    """Mean over non-NULL token counts; ``None`` if no sample (honest, not 0)."""
    kept = [v for v in values if v is not None]
    if not kept:
        return None
    return statistics.fmean(kept)


def _count_verifications(conn: sqlite3.Connection) -> int:
    """Distinct submissions the figures cover (§7: one verification = one submission)."""
    return len(repo.list_submissions_for_scoring(conn))
