"""Accuracy scoring against Ground Truth (Story 5.2, FR-21).

The benchmark's **accuracy** scorer: it reads every captured ``ocr_results`` row
(per engine × image variant) and every ``llm_results`` extraction row (per model),
derives each matchable ``field_key``'s value the SAME way the deployed engine does,
and scores it against the human-verified gold value in ``fixtures/ground_truth.csv``.

It computes, per OCR engine (broken out by image variant) and per LLM model:
- **field-match rate** — per ``field_key`` AND aggregate (the production matching
  logic, so the benchmark measures exactly what the deployed app would do; §4.2(a));
- **CER** — character error rate vs the gold strings (the engine-agnostic OCR
  number; §4.2(b), derived/not-persisted);
- **Government-Warning presence/exactness** — extraction fidelity on the long fixed
  Part-16 string (§2.3, §4.3).

**The spine — reuse, never re-implement.** All comparison routes through the
centralized ``app/normalize.py`` (contract #2) on BOTH the gold and the extracted
side, and reuses ``app/engine/checks/field_match.py``'s tolerance constants and
per-field parsers — so the benchmark and the deployed matcher agree by construction
("STONE'S THROW" == "Stone's Throw" ⇒ MATCH; "45% Alc./Vol." == "45%" ⇒ MATCH).

**Posture.** Pure local analysis: DB **reads only** (SELECT-only repository helpers)
plus the committed ground-truth CSV; it opens no off-host connection, makes no model
call (VLM-only purity untouched — it reads outputs, never feeds a model), writes
nothing (``field_comparisons`` stay pipeline-owned — AR-13), and is never on a
request/render path (AR-5). The figures are **reproducible**: stable sorted iteration,
pure functions over the rows, no wall-clock / RNG (Story 5.2 AC4).
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from app import normalize
from app.db import repositories as repo
from app.engine.checks import field_match

# Ground truth lives in the CSV (seed.py keeps the gt_* columns there, never in the
# DB). Resolve the same fixtures dir the seed uses.
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
_GROUND_TRUTH_CSV = FIXTURES_DIR / "ground_truth.csv"

# The matchable field_keys → their gt_* gold column. brand/abv/net/name go through
# field-match; class/type designation is also scored as a field here (its hybrid
# rule lives in the engine, not the benchmark). Government Warning is scored
# separately (presence + exactness), not in this map.
_FIELD_TO_GT: dict[str, str] = {
    "brand_name": "gt_brand_name",
    "class_type_designation": "gt_class_type_designation",
    "alcohol_content": "gt_alcohol_content",
    "net_contents": "gt_net_contents",
    "applicant_name_address": "gt_applicant_name_address",
}
# Stable, sorted field order for reproducible aggregate output (AC4).
SCORED_FIELD_KEYS: tuple[str, ...] = tuple(sorted(_FIELD_TO_GT))

_GOV_WARNING_GT_COLUMN = "gt_government_warning"
# A synthetic field_key for normalizing the Government Warning body (text pipeline).
_GOV_WARNING_FIELD_KEY = "government_warning"

# match_status vocabulary (mirrors field_comparisons.match_status — data, not advice).
_MATCH = "MATCH"
_MISMATCH = "MISMATCH"
_MISSING = "MISSING"
_UNVERIFIABLE = "UNVERIFIABLE"

# Per-field numeric tolerance + the text near-miss floor — REUSED from the deployed
# matcher so the benchmark can never silently disagree with production.
_NUMERIC_TOLERANCE: dict[str, Decimal] = {
    "alcohol_content": field_match.ABV_TOLERANCE,
    "net_contents": field_match.NET_CONTENTS_TOLERANCE,
}
_TEXT_REVIEW_FLOOR = field_match.REVIEW_FLOOR


# ── ground truth ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class GroundTruth:
    """The gold values for one submission (from ``fixtures/ground_truth.csv``)."""

    brand_name: str | None = None
    class_type_designation: str | None = None
    alcohol_content: str | None = None
    net_contents: str | None = None
    applicant_name_address: str | None = None
    government_warning: str | None = None

    def gold_for(self, field_key: str) -> str | None:
        """The gold value for a matchable ``field_key`` (``None`` if not carried)."""
        return getattr(self, field_key, None)


def _nullify(value: str | None) -> str | None:
    """Empty CSV cells become ``None`` (mirrors seed.py ``_nullify``)."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_ground_truth(csv_path: Path | str | None = None) -> dict[str, GroundTruth]:
    """Load the ground-truth gold values, keyed by ``ttb_id``.

    Reads the committed ``fixtures/ground_truth.csv`` (the benchmark's gold standard;
    the ``gt_*`` columns stay in the CSV, never persisted to the DB — see seed.py).
    Stdlib ``csv`` only; empty cells become ``None``."""
    path = Path(csv_path) if csv_path is not None else _GROUND_TRUTH_CSV
    truth: dict[str, GroundTruth] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            ttb_id = (row.get("ttb_id") or "").strip()
            if not ttb_id:
                continue
            truth[ttb_id] = GroundTruth(
                brand_name=_nullify(row.get("gt_brand_name")),
                class_type_designation=_nullify(row.get("gt_class_type_designation")),
                alcohol_content=_nullify(row.get("gt_alcohol_content")),
                net_contents=_nullify(row.get("gt_net_contents")),
                applicant_name_address=_nullify(row.get("gt_applicant_name_address")),
                government_warning=_nullify(row.get(_GOV_WARNING_GT_COLUMN)),
            )
    return truth


# ── the per-field scoring rule (normalize both, then band) ────────────────────


@dataclass(frozen=True, slots=True)
class FieldScore:
    """One field's score against gold: ``match_status`` + normalized ``similarity``."""

    field_key: str
    match_status: str
    similarity: float | None


def score_field(field_key: str, extracted: str | None, gold: str | None) -> FieldScore:
    """Score one extracted value against its gold value (benchmarking-plan §4.3).

    Normalizes BOTH sides via the centralized ``normalize`` (numeric fields parse to
    number+unit), then bands:
    - gold absent ⇒ ``UNVERIFIABLE`` (no gold to score against — excluded from the rate);
    - gold present, extracted empty ⇒ ``MISSING``;
    - numeric fields: same unit AND ``abs(Δ) <= tolerance`` ⇒ ``MATCH`` else ``MISMATCH``;
    - text fields: normalized-equal (or located within the extracted blob, or
      similarity ``>= REVIEW_FLOOR``) ⇒ ``MATCH`` else ``MISMATCH``.

    The extracted side may be a whole OCR blob (the engine locates the value within
    it) or a single LLM-extracted value — both are handled by reusing the deployed
    matcher's substring/window + numeric-by-unit logic, so the benchmark agrees with
    production by construction."""
    if not _has_value(gold):
        return FieldScore(field_key, _UNVERIFIABLE, None)
    if not _has_value(extracted):
        return FieldScore(field_key, _MISSING, None)
    assert extracted is not None and gold is not None  # narrowed by _has_value

    if field_key in normalize.NUMERIC_FIELD_KEYS:
        return _score_numeric(field_key, extracted, gold)
    return _score_text(field_key, extracted, gold)


def _score_numeric(field_key: str, extracted: str, gold: str) -> FieldScore:
    """Numeric score: parse gold's (number, unit), pick the same-unit extracted token."""
    gold_num, gold_unit = normalize.parse_numeric(gold, field_key)
    if gold_num is None:
        # Gold itself unparseable — cannot anchor a numeric comparison.
        return FieldScore(field_key, _UNVERIFIABLE, None)
    ext_nums = field_match._extracted_numbers_for_unit(extracted, field_key, gold_unit)
    if not ext_nums:
        # No same-unit number on the extraction side ⇒ not found.
        return FieldScore(field_key, _MISSING, None)
    tolerance = _NUMERIC_TOLERANCE.get(field_key, Decimal("0"))
    # Mirror field_match: the gold value is confirmed if the CLOSEST same-unit token is
    # within tolerance (a stray OCR neighbour like ``0%`` must not score a false miss).
    closest = min(ext_nums, key=lambda n: abs(gold_num - n))
    if abs(gold_num - closest) <= tolerance:
        return FieldScore(field_key, _MATCH, 1.0)
    return FieldScore(field_key, _MISMATCH, 0.0)


def _score_text(field_key: str, extracted: str, gold: str) -> FieldScore:
    """Text score via the centralized normalizer + difflib (reuses field_match)."""
    gold_norm = normalize.normalize(gold, field_key)
    ext_norm = normalize.normalize(extracted, field_key)
    if gold_norm and gold_norm == ext_norm:
        return FieldScore(field_key, _MATCH, 1.0)
    # The OCR fallback hands the whole label text; a clean substring hit means the
    # gold value was found verbatim on the label ⇒ MATCH (mirrors field_match).
    if gold_norm and gold_norm in ext_norm:
        return FieldScore(field_key, _MATCH, 1.0)
    similarity = field_match._best_similarity(gold_norm, ext_norm)
    if similarity >= _TEXT_REVIEW_FLOOR:
        return FieldScore(field_key, _MATCH, similarity)
    return FieldScore(field_key, _MISMATCH, similarity)


# ── Government Warning presence / exactness ───────────────────────────────────


@dataclass(frozen=True, slots=True)
class GovWarningScore:
    """The Government Warning extraction score: was it present, was it exact."""

    present: bool
    exact: bool


def government_warning_score(extracted: str | None, gold: str | None) -> GovWarningScore:
    """Score Government-Warning extraction fidelity (presence + exactness).

    ``present`` — a non-empty Government-Warning string was extracted. ``exact`` —
    its normalized body equals the normalized gold body. This measures EXTRACTION
    fidelity (does the engine/model read the warning correctly), NOT the deterministic
    compliance verdict (the engine owns that — not re-implemented here). Reuses the
    centralized ``normalize`` for the body comparison."""
    present = _has_value(extracted)
    if not present or not _has_value(gold):
        return GovWarningScore(present=present, exact=False)
    assert extracted is not None and gold is not None
    gold_norm = normalize.normalize(gold, _GOV_WARNING_FIELD_KEY)
    ext_norm = normalize.normalize(extracted, _GOV_WARNING_FIELD_KEY)
    # The OCR side may be a whole blob carrying the warning; an exact-substring hit
    # counts as exact (the verbatim warning was found on the label).
    exact = bool(gold_norm) and (gold_norm == ext_norm or gold_norm in ext_norm)
    return GovWarningScore(present=present, exact=exact)


# ── CER (character error rate, derived — not persisted) ───────────────────────


def cer(extracted: str | None, gold: str | None) -> float:
    """Character error rate = Levenshtein(extracted, gold) / len(gold).

    Both sides are normalized first (the text pipeline) so case/whitespace noise is
    not double-counted. Edges: empty gold ⇒ ``0.0`` if the extraction is also empty,
    else ``1.0``. Pure stdlib edit distance — no new dependency (benchmarking-plan
    §4.2(b); derived, never persisted — §3)."""
    gold_norm = normalize.normalize(gold, _GOV_WARNING_FIELD_KEY)
    ext_norm = normalize.normalize(extracted, _GOV_WARNING_FIELD_KEY)
    if not gold_norm:
        return 0.0 if not ext_norm else 1.0
    return _levenshtein(ext_norm, gold_norm) / len(gold_norm)


def _levenshtein(a: str, b: str) -> int:
    """Levenshtein edit distance (pure stdlib, two-row DP)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]


# ── corpus aggregation ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FieldRate:
    """A single field's aggregate outcome across the corpus for one extractor."""

    match: int = 0
    mismatch: int = 0
    missing: int = 0
    unverifiable: int = 0

    @property
    def denominator(self) -> int:
        """MATCH + MISMATCH + MISSING (UNVERIFIABLE excluded — §4.4)."""
        return self.match + self.mismatch + self.missing

    @property
    def match_rate(self) -> float | None:
        """MATCH / denominator, or ``None`` when nothing was verifiable."""
        denom = self.denominator
        return (self.match / denom) if denom else None


@dataclass(frozen=True, slots=True)
class ExtractorScore:
    """Aggregate accuracy for one extractor (an OCR engine×variant, or an LLM model)."""

    field_rates: dict[str, FieldRate] = field(default_factory=dict)
    gov_warning_present: int = 0
    gov_warning_exact: int = 0
    gov_warning_total: int = 0
    cer_sum: float = 0.0
    cer_count: int = 0

    @property
    def field_match_rate(self) -> float | None:
        """Overall MATCH / (MATCH+MISMATCH+MISSING) across all scored fields."""
        match = sum(r.match for r in self.field_rates.values())
        denom = sum(r.denominator for r in self.field_rates.values())
        return (match / denom) if denom else None

    @property
    def unverifiable_count(self) -> int:
        return sum(r.unverifiable for r in self.field_rates.values())

    @property
    def mean_cer(self) -> float | None:
        return (self.cer_sum / self.cer_count) if self.cer_count else None

    @property
    def gov_warning_presence_rate(self) -> float | None:
        return (
            (self.gov_warning_present / self.gov_warning_total) if self.gov_warning_total else None
        )

    @property
    def gov_warning_exactness_rate(self) -> float | None:
        return (self.gov_warning_exact / self.gov_warning_total) if self.gov_warning_total else None


@dataclass(frozen=True, slots=True)
class CorpusScore:
    """The whole-corpus accuracy result: per OCR engine×variant and per LLM model.

    ``engines`` is keyed by ``(engine_name, image_variant)`` so preprocessed-vs-original
    is comparable (AC5); ``models`` is keyed by ``model_id``. Story 5.4's report screen
    consumes this typed object (it does not re-score)."""

    engines: dict[tuple[str, str], ExtractorScore] = field(default_factory=dict)
    models: dict[str, ExtractorScore] = field(default_factory=dict)
    scored_submissions: int = 0


# Internal mutable accumulators (frozen result dataclasses are built at the end so
# the public shape stays immutable + reproducible).


class _Acc:
    """A mutable accumulator for one extractor, frozen into an ``ExtractorScore``."""

    def __init__(self) -> None:
        self.field_counts: dict[str, dict[str, int]] = {
            fk: {"match": 0, "mismatch": 0, "missing": 0, "unverifiable": 0}
            for fk in SCORED_FIELD_KEYS
        }
        self.gw_present = 0
        self.gw_exact = 0
        self.gw_total = 0
        self.cer_sum = 0.0
        self.cer_count = 0

    def add_field(self, score: FieldScore) -> None:
        bucket = self.field_counts[score.field_key]
        key = {
            _MATCH: "match",
            _MISMATCH: "mismatch",
            _MISSING: "missing",
            _UNVERIFIABLE: "unverifiable",
        }[score.match_status]
        bucket[key] += 1

    def add_gov_warning(self, score: GovWarningScore) -> None:
        self.gw_total += 1
        if score.present:
            self.gw_present += 1
        if score.exact:
            self.gw_exact += 1

    def add_cer(self, value: float) -> None:
        self.cer_sum += value
        self.cer_count += 1

    def freeze(self) -> ExtractorScore:
        field_rates = {
            fk: FieldRate(
                match=c["match"],
                mismatch=c["mismatch"],
                missing=c["missing"],
                unverifiable=c["unverifiable"],
            )
            for fk, c in self.field_counts.items()
        }
        return ExtractorScore(
            field_rates=field_rates,
            gov_warning_present=self.gw_present,
            gov_warning_exact=self.gw_exact,
            gov_warning_total=self.gw_total,
            cer_sum=self.cer_sum,
            cer_count=self.cer_count,
        )


def score_corpus(conn: sqlite3.Connection, *, csv_path: Path | str | None = None) -> CorpusScore:
    """Score the whole seeded corpus against ground truth — the harness entrypoint.

    For every submission (joined to its ground truth by ``ttb_id``), scores every OCR
    engine×variant row and every LLM model extraction row, per matchable field +
    Government Warning + CER, and rolls them up to per-engine/per-variant and per-model
    aggregates. Iterates in stable sorted order so the figures are byte-reproducible
    (AC4). DB **reads only** (AC6)."""
    engine_acc: dict[tuple[str, str], _Acc] = {}
    model_acc: dict[str, _Acc] = {}

    ground_truth = load_ground_truth(csv_path)
    # Fetch the corpus ONCE (sorted by ttb_id for reproducibility — AC4) and derive both
    # the scoring loop and the scored count from it; no second read, no consistency window.
    submissions = repo.list_submissions_for_scoring(conn)
    scored = len({s.ttb_id for s in submissions} & set(ground_truth))

    for submission in submissions:
        truth = ground_truth.get(submission.ttb_id)
        if truth is None:
            # No gold for this submission — nothing to score against; skip it.
            continue

        for ocr in repo.list_ocr_results_for_scoring(conn, submission.id):
            key = (ocr.engine_name, ocr.image_variant)
            acc = engine_acc.setdefault(key, _Acc())
            _score_one_extraction(
                acc,
                truth,
                value_for=lambda fk, text=ocr.extracted_text: _ocr_field_value(text, fk),
                raw_text=ocr.extracted_text,
            )

        for llm in repo.list_llm_results_for_scoring(conn, submission.id):
            model_key = llm.model_id or ""
            acc = model_acc.setdefault(model_key, _Acc())
            _score_one_extraction(
                acc,
                truth,
                value_for=lambda fk, text=llm.result_text: _llm_field_value(text, fk),
                raw_text=llm.result_text,
            )

    engines = {key: engine_acc[key].freeze() for key in sorted(engine_acc)}
    models = {key: model_acc[key].freeze() for key in sorted(model_acc)}
    return CorpusScore(engines=engines, models=models, scored_submissions=scored)


def _score_one_extraction(acc, truth, *, value_for, raw_text) -> None:
    """Score one extractor's reading of one submission into ``acc``."""
    for field_key in SCORED_FIELD_KEYS:
        gold = truth.gold_for(field_key)
        extracted = value_for(field_key)
        acc.add_field(score_field(field_key, extracted, gold))

    gw_extracted = _gov_warning_value(raw_text)
    acc.add_gov_warning(government_warning_score(gw_extracted, truth.government_warning))

    # CER on the Government Warning string (the long fixed string the OCR literature
    # scores; benchmarking-plan §2.3) — the engine-agnostic accuracy number.
    if _has_value(truth.government_warning):
        acc.add_cer(cer(gw_extracted, truth.government_warning))


# ── per-field value derivation (reuse the deployed engine's parsers) ──────────


def _ocr_field_value(raw_text: str | None, field_key: str) -> str | None:
    """The OCR engine's candidate for ``field_key`` — the whole blob (located within).

    Mirrors ``field_match._extracted_from_ocr_text``: the comparator locates the gold
    value within the blob (substring/window for text, same-unit token for numeric), so
    the whole OCR text is the candidate. ``None`` when the blob is empty."""
    if not _has_value(raw_text):
        return None
    return raw_text


def _llm_field_value(result_text: str | None, field_key: str) -> str | None:
    """The model's extracted value for ``field_key`` from its JSON ``result_text``.

    Reuses the deployed extractor's tolerant JSON parse
    (``field_match._field_from_extraction_json``) — a non-JSON / non-object / non-scalar
    payload yields ``None`` (scored as MISSING), exactly as production degrades."""
    if not _has_value(result_text):
        return None
    assert result_text is not None
    return field_match._field_from_extraction_json(result_text, field_key)


def _gov_warning_value(raw_text: str | None) -> str | None:
    """The extracted Government-Warning candidate.

    Two extractor kinds, kept distinct so neither corrupts the other's score:
    - an **LLM JSON object** payload — trust its ``government_warning`` field; if that
      field is absent/empty the model did NOT extract a warning ⇒ ``None`` (so presence
      is honestly ``False`` and CER is not computed over the raw JSON blob);
    - a **non-JSON OCR blob** — the whole text is the candidate (the warning is located
      within it).
    A JSON object is detected with the SAME tolerant parse the deployed extractor uses;
    anything that is not a JSON object is treated as an OCR blob."""
    if not _has_value(raw_text):
        return None
    assert raw_text is not None
    if _is_json_object(raw_text):
        # A structured LLM payload: the field lookup is authoritative — do NOT fall back
        # to the raw JSON string (that would falsely report a present warning and feed a
        # whole-JSON blob into CER).
        return field_match._field_from_extraction_json(raw_text, _GOV_WARNING_FIELD_KEY)
    return raw_text


def _is_json_object(raw_text: str) -> bool:
    """Whether ``raw_text`` parses as a JSON object (an LLM extraction payload).

    Mirrors ``field_match._field_from_extraction_json``'s tolerant parse so OCR blobs
    (never valid JSON objects) and structured model payloads are told apart."""
    try:
        return isinstance(json.loads(raw_text), dict)
    except (ValueError, TypeError):
        return False


def _has_value(value: str | None) -> bool:
    """A value is present iff it is a non-empty, non-whitespace string."""
    return value is not None and bool(value.strip())
