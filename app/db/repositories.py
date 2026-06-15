"""Typed read layer over the mock COLA database.

Reads return Pydantic v2 models validated at the read boundary (AR-13). Field
names mirror the schema columns 1:1 (snake_case across DB ↔ Python ↔ JSON).
Raw SQL lives only here and in ``connection.py`` — the data boundary.

Timestamps/dates are kept as ISO-8601 ``str`` (the as-filed text SQLite stores),
not parsed to ``datetime`` — matching the data-dictionary's as-filed storage.
Enum columns are typed as ``Literal`` over their CHECK vocabularies so the read
boundary validates them too (AR-13): the database ``CHECK`` is the write-time
source of truth, and these aliases mirror it 1:1 — keep the two in lockstep.

Reads return Pydantic models. The pipeline write helpers
(:func:`insert_ocr_result` / :func:`insert_llm_result`, Story 2.1) persist the
centralized ``OcrResult`` / ``LlmResult`` adapter shapes — the one place the
contract field names map to columns. Raw SQL stays inside ``app/db/``.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Literal

from pydantic import BaseModel

from app.contracts import LlmResult, OcrResult

# Enum vocabularies — mirror the `TEXT + CHECK` constraints in `schema.sql`
# (UPPER_SNAKE). The DB CHECK remains the write-time source of truth; these
# Literals validate the same values at the read boundary. Keep in lockstep.
BeverageType = Literal["WINE", "DISTILLED_SPIRITS", "MALT_BEVERAGE"]
SourceOfProduct = Literal["DOMESTIC", "IMPORTED"]
ApplicationType = Literal["LABEL_APPROVAL", "EXEMPTION", "DISTINCTIVE_BOTTLE", "RESUBMISSION"]
Status = Literal["RECEIVED", "PROCESSING", "READY_FOR_REVIEW", "IN_REVIEW", "DECIDED"]
EngineVerdict = Literal["PASS", "REVIEW", "FAIL"]
Disposition = Literal["APPROVED", "NEEDS_CORRECTION", "REJECTED"]
ImageRole = Literal["BRAND", "BACK", "NECK", "STRIP", "OTHER"]


class Submission(BaseModel):
    """One mock COLA application (``submissions`` row)."""

    id: int
    ttb_id: str
    serial_number: str | None = None
    beverage_type: BeverageType
    source_of_product: SourceOfProduct | None = None
    application_type: ApplicationType | None = None
    # APPLICATION-category fields (Form 5100.31 / e-filed)
    brand_name: str | None = None
    fanciful_name: str | None = None
    class_type_designation: str | None = None
    applicant_name_address: str | None = None
    mailing_address: str | None = None
    plant_registry_no: str | None = None
    alcohol_content: str | None = None
    net_contents: str | None = None
    grape_varietal: str | None = None
    wine_appellation: str | None = None
    wine_vintage: str | None = None
    formula_id: str | None = None
    phone: str | None = None
    email: str | None = None
    # lifecycle + rolled-up engine result
    status: Status
    engine_verdict: EngineVerdict | None = None
    disposition: Disposition | None = None
    application_date: str | None = None
    submitted_at: str | None = None
    decided_at: str | None = None
    specialist_id: str | None = None
    decision_notes: str | None = None
    correction_due_at: str | None = None
    processing_ms: int | None = None
    created_at: str
    updated_at: str


class LabelImage(BaseModel):
    """One label image (``label_images`` row); 1–10 per submission."""

    id: int
    submission_id: int
    image_role: ImageRole | None = None
    position: int | None = None
    filename: str
    mime_type: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    label_width_in: float | None = None
    label_height_in: float | None = None
    file_size_bytes: int | None = None
    # Local-OpenCV preprocessing outputs (Story 2.3). Paths are RELATIVE to the
    # generated-images root; NULL when a clean image needed no enhancement.
    enhanced_path: str | None = None
    binarized_path: str | None = None
    preprocess_log: str | None = None
    preprocess_ms: int | None = None
    preprocessed_at: str | None = None
    created_at: str


class ChecklistItem(BaseModel):
    """One per-check result for a submission (``checklist_items`` row).

    The read shape the Review Workspace shell (Story 4.3) renders: the per-check
    ``verdict`` feeds the suggested-verdict roll-up via ``app/verdict.py:rollup``,
    and ``check_key`` / ``check_type`` drive the chevron step grouping. Field names
    mirror the columns 1:1 (snake_case); the enum-ish columns stay plain ``str``
    (the write-time ``CHECK`` is the source of truth)."""

    id: int
    submission_id: int
    check_key: str
    label: str | None = None
    cfr_citation: str | None = None
    check_type: str | None = None
    verdict: str | None = None
    detail: str | None = None
    field_comparison_id: int | None = None
    created_at: str


class FieldComparison(BaseModel):
    """One APPLICATION-vs-EXTRACTED field comparison (``v_field_comparisons`` row).

    The read shape the stacked comparison cards (Story 4.4) render. Read from the
    ``v_field_comparisons`` VIEW — never the raw table — so ``extracted_source`` is
    the DERIVED display label (``ocr:<engine_name>`` / ``llm:<model_id>``, or
    ``None`` when neither source FK is set) the schema reconstructs by joining the
    source row, never re-derived in Python. ``application_value`` / ``extracted_value``
    are the RAW (un-normalized) stored text — the UI shows raw; normalization is
    comparison-only (Contract #2). Field names mirror the view's columns 1:1
    (snake_case); the enum-ish ``match_status`` stays plain ``str`` (the write-time
    ``CHECK`` is the source of truth)."""

    id: int
    submission_id: int
    field_key: str
    application_value: str | None = None
    extracted_value: str | None = None
    source_ocr_result_id: int | None = None
    source_llm_result_id: int | None = None
    match_status: str | None = None
    similarity: float | None = None
    extracted_source: str | None = None
    created_at: str


class ReviewProgress(BaseModel):
    """The specialist's IN-PROGRESS review state (``review_progress`` row, AR-14).

    WEB-LAYER-written, kept strictly separate from the pipeline-owned
    ``checklist_items`` — this is the smart-checklist tick-state (Story 4.6) and
    the draft Notes (``draft_notes``, written by Story 4.8). ``ticked_check_keys``
    is the parsed JSON array of manually-ticked ``check_key``s (validated at the
    read boundary, AR-13); the stored array is kept sorted + de-duplicated. Field
    names mirror the columns 1:1 (snake_case)."""

    submission_id: int
    ticked_check_keys: list[str] = []
    draft_notes: str | None = None
    updated_at: str


def get_submission(conn: sqlite3.Connection, submission_id: int) -> Submission | None:
    """Read one submission by surrogate id; ``None`` if absent."""
    row = conn.execute(
        "SELECT * FROM submissions WHERE id = ?",
        (submission_id,),
    ).fetchone()
    return Submission.model_validate(dict(row)) if row is not None else None


def get_submission_by_ttb_id(conn: sqlite3.Connection, ttb_id: str) -> Submission | None:
    """Read one submission by its public TTB ID; ``None`` if absent."""
    row = conn.execute(
        "SELECT * FROM submissions WHERE ttb_id = ?",
        (ttb_id,),
    ).fetchone()
    return Submission.model_validate(dict(row)) if row is not None else None


def list_label_images(conn: sqlite3.Connection, submission_id: int) -> list[LabelImage]:
    """List a submission's label images in display order (position ascending)."""
    rows = conn.execute(
        "SELECT * FROM label_images WHERE submission_id = ? ORDER BY position",
        (submission_id,),
    ).fetchall()
    return [LabelImage.model_validate(dict(row)) for row in rows]


def get_label_image(conn: sqlite3.Connection, image_id: int) -> LabelImage | None:
    """Read one label image by surrogate id; ``None`` if absent.

    The single-row read behind the Story-4.7 image-serving route: the route resolves
    the on-disk path entirely from this row (never a client-supplied path) and verifies
    ``submission_id`` matches the path before streaming the file."""
    row = conn.execute(
        "SELECT * FROM label_images WHERE id = ?",
        (image_id,),
    ).fetchone()
    return LabelImage.model_validate(dict(row)) if row is not None else None


def list_checklist_items(conn: sqlite3.Connection, submission_id: int) -> list[ChecklistItem]:
    """List a submission's ``checklist_items`` in insertion (ruleset) order.

    The Review Workspace shell read (Story 4.3): one row per Check, ordered by ``id``
    so the order matches the ruleset that produced them. The shell rolls these
    per-check ``verdict`` values up via ``app/verdict.py:rollup`` (the SAME roll-up
    the engine used) and groups them into chevron steps. Returns ``[]`` for a
    submission with no checklist (an empty/unmapped ruleset)."""
    rows = conn.execute(
        "SELECT * FROM checklist_items WHERE submission_id = ? ORDER BY id",
        (submission_id,),
    ).fetchall()
    return [ChecklistItem.model_validate(dict(row)) for row in rows]


def list_field_comparisons(conn: sqlite3.Connection, submission_id: int) -> list[FieldComparison]:
    """List a submission's field comparisons in id order (the stacked cards read).

    Reads the ``v_field_comparisons`` VIEW (Story 4.4) — never the raw table — so
    ``extracted_source`` is the DERIVED display label the schema reconstructs by
    joining the source OCR/LLM row, never re-derived here. Ordered by ``id`` so the
    order matches the field-match evaluator that produced them; problems-first
    re-ordering is a presentation concern handled in the view layer. Returns ``[]``
    for a submission with no comparisons. A pure pre-computed read (AR-5)."""
    rows = conn.execute(
        "SELECT * FROM v_field_comparisons WHERE submission_id = ? ORDER BY id",
        (submission_id,),
    ).fetchall()
    return [FieldComparison.model_validate(dict(row)) for row in rows]


def get_submission_ocr_text(conn: sqlite3.Connection, submission_id: int) -> str:
    """The submission's OCR text — every ``OK`` ``ocr_results`` row joined in id order.

    The input the **deterministic compliance engine** (Epic 3 — Field Match,
    Government Warning) reads to locate/compare values; per-field parsing into
    ``field_comparisons`` is Epic 3, not here. It is deliberately **never** fed to the
    VLM extraction stage (Story 2.5) — the model reads the label image on its own so
    the OCR-vs-model benchmark stays a true head-to-head. ``ERROR`` rows and rows with
    NULL/blank ``extracted_text`` are skipped; returns an empty string when there is no
    readable text."""
    rows = conn.execute(
        "SELECT extracted_text FROM ocr_results "
        "WHERE submission_id = ? AND status = 'OK' AND extracted_text IS NOT NULL "
        "AND TRIM(extracted_text) <> '' ORDER BY id",
        (submission_id,),
    ).fetchall()
    return "\n".join(row["extracted_text"] for row in rows)


# ── benchmark scoring read helpers (Story 5.2) ───────────────────────────────
# SELECT-only readers that surface the per-engine/per-model RAW rows so the
# accuracy scorer can score EVERY engine (× image variant) and EVERY model
# independently against ground truth (AR-4 — per-engine/per-model storage is
# already separate; these just expose it). Read-only: no writes here.


class OcrScoringRow(BaseModel):
    """One ``OK`` ``ocr_results`` row, the subset the accuracy scorer needs.

    Keyed for scoring by ``(engine_name, image_variant)`` so the both-variants
    rows (Story 2.4 / AR-7: ORIGINAL vs ENHANCED/BINARIZED) score separately and
    preprocessed-vs-original stays comparable (Story 5.2 AC5)."""

    engine_name: str
    image_variant: str
    extracted_text: str | None = None
    confidence: float | None = None


class LlmScoringRow(BaseModel):
    """One ``OK`` ``extract_fields`` ``llm_results`` row for accuracy scoring."""

    model_id: str | None = None
    model_name: str | None = None
    provider: str | None = None
    result_text: str | None = None


class ScoringSubmission(BaseModel):
    """The minimal submission identity the corpus scorer iterates (Story 5.2)."""

    id: int
    ttb_id: str
    beverage_type: BeverageType


def list_submissions_for_scoring(conn: sqlite3.Connection) -> list[ScoringSubmission]:
    """Every submission's ``(id, ttb_id, beverage_type)`` in ``ttb_id`` order.

    Sorted by ``ttb_id`` so the corpus scorer iterates in a stable, reproducible
    order (Story 5.2 AC4). Read-only."""
    rows = conn.execute(
        "SELECT id, ttb_id, beverage_type FROM submissions ORDER BY ttb_id, id"
    ).fetchall()
    return [ScoringSubmission.model_validate(dict(row)) for row in rows]


def list_ocr_results_for_scoring(
    conn: sqlite3.Connection, submission_id: int
) -> list[OcrScoringRow]:
    """The submission's ``OK`` OCR rows for scoring, in ``(engine, variant, id)`` order.

    Returns one row per ``(engine_name, image_variant)`` OCR result so the scorer
    can break accuracy out by variant (AC5). ``ERROR`` rows are skipped. Read-only."""
    rows = conn.execute(
        "SELECT engine_name, image_variant, extracted_text, confidence "
        "FROM ocr_results WHERE submission_id = ? AND status = 'OK' "
        "ORDER BY engine_name, image_variant, id",
        (submission_id,),
    ).fetchall()
    return [OcrScoringRow.model_validate(dict(row)) for row in rows]


def list_llm_results_for_scoring(
    conn: sqlite3.Connection, submission_id: int
) -> list[LlmScoringRow]:
    """The submission's ``OK`` ``extract_fields`` LLM rows for scoring, in id order.

    Only the displayed/extraction task is scored for accuracy (``classify`` and
    other tasks are not field extractions). Read-only."""
    rows = conn.execute(
        "SELECT model_id, model_name, provider, result_text "
        "FROM llm_results WHERE submission_id = ? AND status = 'OK' "
        "AND task = 'extract_fields' ORDER BY id",
        (submission_id,),
    ).fetchall()
    return [LlmScoringRow.model_validate(dict(row)) for row in rows]


# ── benchmark cost/speed read helpers (Story 5.3) ────────────────────────────
# SELECT-only readers that surface the per-engine/per-model RAW timing + token
# columns the speed/cost roll-up needs (latency_ms, ran_on_cpu, prompt/completion
# tokens). Per-engine/per-model storage is already separate (AR-4); these just
# expose it. Read-only: no writes here. Money is NOT computed here — cost.py owns
# the Decimal cost math; this layer only hands over the raw integer inputs.


class OcrCostRow(BaseModel):
    """One ``OK`` ``ocr_results`` row's speed inputs (Story 5.3).

    Keyed for speed roll-up by ``(engine_name, image_variant)`` — the SAME key the
    accuracy scorer uses (``OcrScoringRow``) — so speed and accuracy line up
    row-for-row in the Story 5.4 report. ``ran_on_cpu`` carries the CPU-only flag
    (govt infra has no guaranteed GPU — AC3)."""

    engine_name: str
    image_variant: str
    latency_ms: int | None = None
    ran_on_cpu: bool | None = None


class LlmCostRow(BaseModel):
    """One ``OK`` ``extract_fields`` ``llm_results`` row's speed + token inputs."""

    model_id: str | None = None
    model_name: str | None = None
    provider: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def list_ocr_latency_for_cost(conn: sqlite3.Connection) -> list[OcrCostRow]:
    """Every ``OK`` OCR row's ``(engine, variant, latency_ms, ran_on_cpu)`` (Story 5.3).

    Corpus-wide (not per-submission) since speed/cost rolls up across the whole
    seeded corpus. Sorted by ``(engine_name, image_variant, id)`` so the roll-up
    iterates in a stable, reproducible order (AC4). Read-only."""
    rows = conn.execute(
        "SELECT engine_name, image_variant, latency_ms, ran_on_cpu "
        "FROM ocr_results WHERE status = 'OK' "
        "ORDER BY engine_name, image_variant, id"
    ).fetchall()
    return [OcrCostRow.model_validate(dict(row)) for row in rows]


def list_llm_cost_rows(conn: sqlite3.Connection) -> list[LlmCostRow]:
    """Every ``OK`` ``extract_fields`` LLM row's speed + token inputs (Story 5.3).

    Corpus-wide; only the extraction task feeds the cost figure (``classify`` and
    other tasks are not field-extraction verifications). Sorted by
    ``(model_id, id)`` for reproducibility (AC4). Read-only."""
    rows = conn.execute(
        "SELECT model_id, model_name, provider, latency_ms, prompt_tokens, "
        "completion_tokens FROM llm_results WHERE status = 'OK' "
        "AND task = 'extract_fields' ORDER BY model_id, id"
    ).fetchall()
    return [LlmCostRow.model_validate(dict(row)) for row in rows]


# ── pipeline write helpers (Story 2.1) ───────────────────────────────────────
# Persist the centralized adapter shapes. Each engine/model gets its OWN row
# (per-engine/per-model storage, never merged — AR-4). The contract→column
# mapping lives ONLY here: OcrResult.text → extracted_text; word_boxes → JSON;
# total_tokens is a DB-generated column and is NEVER inserted.
#
# Transaction ownership: these helpers issue the INSERT but DO NOT commit — the
# caller owns the unit of work so a submission's multiple engine/model rows
# commit atomically (AR-4). Use ``connect(...)`` (commits on clean exit) or call
# ``conn.commit()`` yourself; a bare ``get_connection(...)`` that closes without
# a commit discards the rows. See app/db/connection.py.


def insert_ocr_result(
    conn: sqlite3.Connection,
    *,
    submission_id: int,
    label_image_id: int,
    result: OcrResult,
    image_variant: str = "ORIGINAL",
    error_text: str | None = None,
) -> int:
    """Insert one :class:`OcrResult` as an ``ocr_results`` row; return its id.

    ``image_variant`` (Story 2.4) records WHICH image variant this row OCR'd —
    ``'ORIGINAL'`` / ``'ENHANCED'`` / ``'BINARIZED'`` — so the both-variants rows
    are distinguishable for the Epic-5 benchmark (AR-7). It is a writer-supplied
    discriminator, not part of the centralized ``OcrResult`` shape; it defaults to
    ``'ORIGINAL'`` so the clean-image path and any pre-2.4 caller need no change.
    """
    cur = conn.execute(
        """
        INSERT INTO ocr_results
            (label_image_id, submission_id, engine_name, engine_version,
             extracted_text, confidence, word_boxes, latency_ms, ran_on_cpu,
             image_variant, status, error_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            label_image_id,
            submission_id,
            result.engine_name,
            result.engine_version,
            result.text,  # contract `text` → column `extracted_text`
            result.confidence,
            json.dumps(result.word_boxes) if result.word_boxes is not None else None,
            result.latency_ms,
            result.ran_on_cpu,
            image_variant,
            result.status,
            error_text,
        ),
    )
    assert cur.lastrowid is not None  # guaranteed by a successful INSERT
    return cur.lastrowid


def insert_llm_result(
    conn: sqlite3.Connection,
    *,
    submission_id: int,
    result: LlmResult,
    label_image_id: int | None = None,
    is_benchmark_only: bool = False,
) -> int:
    """Insert one :class:`LlmResult` as an ``llm_results`` row; return its id.

    ``total_tokens`` is omitted: the column is ``GENERATED ALWAYS AS
    (prompt_tokens + completion_tokens) STORED`` and inserting it would raise.
    """
    cur = conn.execute(
        """
        INSERT INTO llm_results
            (submission_id, label_image_id, task, model_name, model_id,
             model_full_id, provider, is_benchmark_only, prompt_tokens,
             completion_tokens, latency_ms, requested_at, responded_at,
             result_text, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            submission_id,
            label_image_id,
            result.task,
            result.model_name,
            result.model_id,
            result.model_full_id,
            result.provider,
            is_benchmark_only,
            result.prompt_tokens,
            result.completion_tokens,
            result.latency_ms,
            result.requested_at,
            result.responded_at,
            result.result_text,
            result.status,
        ),
    )
    assert cur.lastrowid is not None  # guaranteed by a successful INSERT
    return cur.lastrowid


# ── pipeline lifecycle write helpers (Story 2.2) ─────────────────────────────
# The raw SQL behind the background sweep's status machine. These live here (the
# data boundary — SQL only in app/db/) and are the SQL primitives that the
# orchestration layer ``app/pipeline/status.py`` composes into atomic, ordered,
# vocabulary-checked lifecycle steps. They DO NOT commit (the 2.1 convention):
# the caller — ``status.py`` — owns each short transaction and commits per step
# so PROCESSING is durable/visible (the atomic claim) and readers never block.


def get_status(conn: sqlite3.Connection, submission_id: int) -> str | None:
    """Read just the lifecycle ``status`` of one submission; ``None`` if absent.

    A light single-column read used to compute ``from_status`` for the
    forward-only transition guard — avoids validating the whole row.
    """
    row = conn.execute(
        "SELECT status FROM submissions WHERE id = ?",
        (submission_id,),
    ).fetchone()
    return row["status"] if row is not None else None


def claim_for_processing(conn: sqlite3.Connection, submission_id: int) -> bool:
    """Atomically claim a ``RECEIVED`` submission for processing (the AR-2 guard).

    Conditional ``UPDATE … WHERE status='RECEIVED'``: only the worker that flips
    the row sees ``rowcount == 1``; an overlapping sweep that lost the race gets
    ``0`` and must no-op. This is what makes the sweep idempotent and double-
    process-safe regardless of batch overlap. The caller commits.
    """
    cur = conn.execute(
        "UPDATE submissions SET status = 'PROCESSING' WHERE id = ? AND status = 'RECEIVED'",
        (submission_id,),
    )
    return cur.rowcount == 1


def update_status(conn: sqlite3.Connection, submission_id: int, status: str) -> None:
    """Write a submission's lifecycle ``status`` (forward-order is enforced one
    level up, in ``status.advance``). The caller commits."""
    conn.execute(
        "UPDATE submissions SET status = ? WHERE id = ?",
        (status, submission_id),
    )


def insert_audit_event(
    conn: sqlite3.Connection,
    *,
    submission_id: int,
    event_type: str,
    actor: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    note: str | None = None,
) -> int:
    """Append one ``audit_events`` row; return its id. ``occurred_at`` is stamped
    by the DB default (``CURRENT_TIMESTAMP``). The caller commits.

    ``event_type`` membership in the fixed vocabulary is enforced one level up in
    ``status.py`` (and by the DB ``CHECK``)."""
    cur = conn.execute(
        """
        INSERT INTO audit_events
            (submission_id, event_type, actor, from_status, to_status, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (submission_id, event_type, actor, from_status, to_status, note),
    )
    assert cur.lastrowid is not None  # guaranteed by a successful INSERT
    return cur.lastrowid


def update_processing_ms(conn: sqlite3.Connection, submission_id: int, processing_ms: int) -> None:
    """Roll the total pre-compute time into ``submissions.processing_ms`` (the DB
    ``CHECK`` enforces ``>= 0``). The caller commits."""
    conn.execute(
        "UPDATE submissions SET processing_ms = ? WHERE id = ?",
        (processing_ms, submission_id),
    )


def list_processing_ms(conn: sqlite3.Connection) -> list[int]:
    """Every non-NULL ``submissions.processing_ms`` (per-submission whole-pipeline
    pre-compute wall-time, ms) — the sample behind the benchmark throughput summary.
    SELECT-only; NULLs (not-yet-processed rows) are excluded."""
    rows = conn.execute(
        "SELECT processing_ms FROM submissions WHERE processing_ms IS NOT NULL"
    ).fetchall()
    return [int(r[0]) for r in rows]


def list_received_ids(conn: sqlite3.Connection, limit: int) -> list[int]:
    """List ``RECEIVED`` submission ids, oldest-first, capped at ``limit`` — the
    bounded batch the background sweep claims each tick (AC1/AC5).

    Ordered by ``submitted_at`` then ``id`` so the order is stable even when
    several rows share a ``submitted_at`` (the seed stamps coarse timestamps)."""
    rows = conn.execute(
        "SELECT id FROM submissions WHERE status = 'RECEIVED' ORDER BY submitted_at, id LIMIT ?",
        (limit,),
    ).fetchall()
    return [int(r["id"]) for r in rows]


# ── queue read helpers (Story 4.1) ───────────────────────────────────────────
# The web layer's "Next Submission" serve + the queue stats strip read here. Both
# are pure DB reads (the 5s read contract, AR-5) ordered oldest-first by
# `submitted_at` then `id` for a stable, fair selection — mirroring
# `list_received_ids` and backed by `idx_submissions_queue (status, beverage_type,
# submitted_at)`. The optional `beverage_type` is parameterized (never string-
# interpolated); Story 4.1 calls with the default `None`, Story 4.2 exposes it
# through the route.


def get_oldest_ready_submission_id(
    conn: sqlite3.Connection, *, beverage_type: str | None = None
) -> int | None:
    """The oldest ``READY_FOR_REVIEW`` submission id (oldest-first), or ``None``.

    Skips every unready status (``RECEIVED``/``PROCESSING``/``IN_REVIEW``/
    ``DECIDED``) — the queue never serves a partially-processed submission. With
    ``beverage_type`` set, restricts to that type (Story 4.2's by-type serve).
    """
    if beverage_type is None:
        row = conn.execute(
            "SELECT id FROM submissions WHERE status = 'READY_FOR_REVIEW' "
            "ORDER BY submitted_at, id LIMIT 1"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM submissions WHERE status = 'READY_FOR_REVIEW' "
            "AND beverage_type = ? ORDER BY submitted_at, id LIMIT 1",
            (beverage_type,),
        ).fetchone()
    return int(row["id"]) if row is not None else None


def count_ready_for_review(conn: sqlite3.Connection, *, beverage_type: str | None = None) -> int:
    """Count submissions waiting in the queue (``READY_FOR_REVIEW``).

    The live "N waiting" figure for the queue stats strip — the only honestly-
    computable queue stat in the POC. With ``beverage_type`` set, counts that type.
    """
    if beverage_type is None:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM submissions WHERE status = 'READY_FOR_REVIEW'"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM submissions WHERE status = 'READY_FOR_REVIEW' "
            "AND beverage_type = ?",
            (beverage_type,),
        ).fetchone()
    return int(row["n"])


# ── preprocessing write helper (Story 2.3) ───────────────────────────────────
# Persists the local-OpenCV preprocess stage's outputs onto the existing
# `label_images` row (architecture D7 — referenced "by path in label_images").
# The contract→column mapping lives ONLY here: the ordered transform/param/timing
# log is JSON-encoded (like `word_boxes`), paths are stored RELATIVE to the
# generated-images root, and the original `filename` is never touched. Does NOT
# commit — the pipeline stage owns the unit of work (the 2.1/2.2 convention).


def update_label_image_variants(
    conn: sqlite3.Connection,
    label_image_id: int,
    *,
    enhanced_path: str | None,
    binarized_path: str | None,
    preprocess_log: object,
    preprocess_ms: int,
    preprocessed_at: str,
) -> None:
    """Record one image's preprocessing outputs on its ``label_images`` row.

    ``enhanced_path``/``binarized_path`` are paths RELATIVE to the generated-images
    root (``None`` when a clean image produced no variant). ``preprocess_log`` is any
    JSON-serializable object (the ordered transform log) and is ``json.dumps``-ed
    here. The caller commits.
    """
    conn.execute(
        """
        UPDATE label_images
           SET enhanced_path   = ?,
               binarized_path  = ?,
               preprocess_log  = ?,
               preprocess_ms   = ?,
               preprocessed_at = ?
         WHERE id = ?
        """,
        (
            enhanced_path,
            binarized_path,
            json.dumps(preprocess_log) if preprocess_log is not None else None,
            preprocess_ms,
            preprocessed_at,
            label_image_id,
        ),
    )


# ── compliance-engine write helpers (Story 3.2) ──────────────────────────────
# The raw SQL the engine executor (`app/engine/run_checks.py`) uses to persist one
# `checklist_items` row per Check and to set the submission's rolled-up
# `engine_verdict`. Raw SQL stays inside `app/db/` (the data boundary). Like the
# 2.1/2.2 helpers these DO NOT commit — the engine stage owns the unit of work so a
# submission's whole checklist commits atomically.


def insert_checklist_item(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    check_key: str,
    label: str | None,
    cfr_citation: str | None,
    check_type: str | None,
    verdict: str | None,
    detail: str | None = None,
    field_comparison_id: int | None = None,
) -> int:
    """Insert one ``checklist_items`` row (one per Check); return its id.

    Carries the Check's provenance as DATA — ``check_key``/``label``/``cfr_citation``/
    ``check_type`` come straight off the ruleset row (never recomputed), plus the
    per-check ``verdict`` and an advisory ``detail`` (the inputs compared / why it
    flagged). ``field_comparison_id`` links a field-match check to its comparison row
    (Story 3.3). The ``CHECK`` constraints enforce the ``check_type`` and ``verdict``
    vocabularies. The caller commits.
    """
    cur = conn.execute(
        """
        INSERT INTO checklist_items
            (submission_id, check_key, label, cfr_citation, check_type,
             verdict, detail, field_comparison_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            submission_id,
            check_key,
            label,
            cfr_citation,
            check_type,
            verdict,
            detail,
            field_comparison_id,
        ),
    )
    assert cur.lastrowid is not None  # guaranteed by a successful INSERT
    return cur.lastrowid


def set_engine_verdict(conn: sqlite3.Connection, submission_id: int, verdict: str) -> None:
    """Persist the rolled-up advisory ``engine_verdict`` on a submission.

    ``verdict`` is the output of ``app/verdict.py:rollup`` — domain ``PASS/REVIEW/
    FAIL`` (no ``NA``), matching the ``submissions.engine_verdict`` CHECK exactly.
    Advisory only — never a disposition. The caller commits.
    """
    conn.execute(
        "UPDATE submissions SET engine_verdict = ? WHERE id = ?",
        (verdict, submission_id),
    )


def delete_checklist_items(conn: sqlite3.Connection, submission_id: int) -> None:
    """Delete a submission's ``checklist_items`` rows — the delete half of the
    executor's delete-then-insert idempotency (re-processing must not duplicate
    rows). The caller commits."""
    conn.execute(
        "DELETE FROM checklist_items WHERE submission_id = ?",
        (submission_id,),
    )


# ── field-comparison write + extracted-value reads (Story 3.3) ───────────────
# The raw SQL the field-match evaluator (`app/engine/checks/field_match.py`) uses
# to persist one `field_comparisons` row per matchable field and to resolve the
# EXTRACTED-value source (the highest-confidence OCR row, or the latest OK LLM
# extraction). Raw SQL stays inside `app/db/` (the data boundary). Like the
# 2.1/2.2/3.2 helpers the write DOES NOT commit — the engine stage owns the unit of
# work so a submission's whole checklist + comparisons commit atomically.


def delete_field_comparisons(conn: sqlite3.Connection, submission_id: int) -> None:
    """Delete a submission's ``field_comparisons`` rows — the delete half of the
    engine's delete-then-insert idempotency (a re-run must not duplicate comparison
    rows alongside the checklist). The caller commits."""
    conn.execute(
        "DELETE FROM field_comparisons WHERE submission_id = ?",
        (submission_id,),
    )


def insert_field_comparison(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    field_key: str,
    application_value: str | None,
    extracted_value: str | None,
    match_status: str,
    similarity: float | None = None,
    source_ocr_result_id: int | None = None,
    source_llm_result_id: int | None = None,
) -> int:
    """Insert one ``field_comparisons`` row (one per matchable field); return its id.

    Stores the RAW (un-normalized) ``application_value``/``extracted_value`` — the UI
    shows raw; normalization is comparison-only. ``match_status`` is the comparison
    outcome (``MATCH/MISMATCH/MISSING/UNVERIFIABLE``); ``similarity`` is the
    normalized 0–1 ratio (``None`` when not computed). Provenance is normalized: AT
    MOST ONE source FK is set (the table ``CHECK`` enforces it) — the review UI's
    ``v_field_comparisons`` view derives ``extracted_source`` from it. The caller
    commits.
    """
    cur = conn.execute(
        """
        INSERT INTO field_comparisons
            (submission_id, field_key, application_value, extracted_value,
             source_ocr_result_id, source_llm_result_id, match_status, similarity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            submission_id,
            field_key,
            application_value,
            extracted_value,
            source_ocr_result_id,
            source_llm_result_id,
            match_status,
            similarity,
        ),
    )
    assert cur.lastrowid is not None  # guaranteed by a successful INSERT
    return cur.lastrowid


def get_best_ocr_result_id(conn: sqlite3.Connection, submission_id: int) -> int | None:
    """The id of the submission's highest-confidence ``OK`` ``ocr_results`` row.

    The contributing OCR row the field-match evaluator records as the provenance FK
    for an OCR-sourced extracted value (recommended: the most-confident reading).
    ``NULL`` confidences sort last; ``None`` when the submission has no ``OK`` row.
    """
    row = conn.execute(
        "SELECT id FROM ocr_results "
        "WHERE submission_id = ? AND status = 'OK' "
        "ORDER BY confidence IS NULL, confidence DESC, id LIMIT 1",
        (submission_id,),
    ).fetchone()
    return int(row["id"]) if row is not None else None


def get_best_ocr_confidence(conn: sqlite3.Connection, submission_id: int) -> float | None:
    """The ``confidence`` of the submission's highest-confidence ``OK`` OCR row.

    Used by the field-match low-confidence safety valve (``OCR_CONFIDENCE_FLOOR``):
    an apparent match read from a low-confidence OCR row is forced to REVIEW.
    ``None`` when there is no ``OK`` row or its confidence is NULL.
    """
    row = conn.execute(
        "SELECT confidence FROM ocr_results "
        "WHERE submission_id = ? AND status = 'OK' "
        "ORDER BY confidence IS NULL, confidence DESC, id LIMIT 1",
        (submission_id,),
    ).fetchone()
    if row is None or row["confidence"] is None:
        return None
    return float(row["confidence"])


def get_latest_llm_extraction(
    conn: sqlite3.Connection, submission_id: int
) -> tuple[int, str] | None:
    """The latest ``OK`` ``extract_fields`` ``llm_results`` row as ``(id, result_text)``.

    The structured VLM extraction the field-match evaluator parses per ``field_key``
    (the LLM-assisted extracted-value source; provenance FK = this row id). Scoped to
    the displayed extraction (``is_benchmark_only = 0``); ``None`` when the model
    layer was off (the OCR-only path). Most-recent row wins (``id`` DESC).
    """
    row = conn.execute(
        "SELECT id, result_text FROM llm_results "
        "WHERE submission_id = ? AND task = 'extract_fields' AND status = 'OK' "
        "AND is_benchmark_only = 0 AND result_text IS NOT NULL "
        "ORDER BY id DESC LIMIT 1",
        (submission_id,),
    ).fetchone()
    if row is None:
        return None
    return (int(row["id"]), row["result_text"])


def llm_extraction_unavailable(conn: sqlite3.Connection, submission_id: int) -> bool:
    """Whether the submission's DISPLAYED VLM extraction degraded (Story 4.11 AC3).

    ``True`` iff a displayed (``is_benchmark_only = 0``) ``extract_fields``
    ``llm_results`` row exists with ``status = 'ERROR'`` — the model layer was enabled
    and attempted the read but was unreachable, so the comparison fell back to OCR
    (FR-12; see ``app/pipeline/llm.py``). ``False`` when the extraction succeeded OR
    when the model layer was config-off (no ``llm_results`` row at all — the clean
    OCR-only path, which is NOT a degrade and shows no notice). Pure read; no commit.
    """
    row = conn.execute(
        "SELECT 1 FROM llm_results "
        "WHERE submission_id = ? AND task = 'extract_fields' AND status = 'ERROR' "
        "AND is_benchmark_only = 0 LIMIT 1",
        (submission_id,),
    ).fetchone()
    return row is not None


# ── review-progress read + upsert helpers (Story 4.6, AR-14) ─────────────────
# The smart checklist's IN-PROGRESS tick-state — the ONE web-layer write the
# Review Workspace makes (via POST /review/{id}/progress). Read back by the
# AR-5-pure GET /review/{id} to rehydrate ticks across navigate-away + reload.
# Strictly separate from the pipeline-owned `checklist_items`. The web handler
# owns the unit of work — these helpers issue SQL but DO NOT commit (the
# `connect()` context manager commits on clean exit).


def get_review_progress(conn: sqlite3.Connection, submission_id: int) -> ReviewProgress | None:
    """Read a submission's in-progress review state; ``None`` if no row yet.

    ``ticked_check_keys`` is parsed from its stored JSON array at the read
    boundary (AR-13) into a ``list[str]``.
    """
    row = conn.execute(
        "SELECT * FROM review_progress WHERE submission_id = ?",
        (submission_id,),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["ticked_check_keys"] = json.loads(data["ticked_check_keys"])
    return ReviewProgress.model_validate(data)


def get_ticked_check_keys(conn: sqlite3.Connection, submission_id: int) -> set[str]:
    """The set of manually-ticked ``check_key``s for a submission (empty if none)."""
    progress = get_review_progress(conn, submission_id)
    return set(progress.ticked_check_keys) if progress is not None else set()


def set_check_tick(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    check_key: str,
    ticked: bool,
) -> None:
    """Add or remove one ``check_key`` from a submission's manual tick-state (upsert).

    Reads the current set, applies the tick/un-tick, and writes back a sorted +
    de-duplicated JSON array — bumping ``updated_at``. An ``ON CONFLICT`` upsert
    keyed on ``submission_id`` creates the row on first tick and preserves any
    Story-4.8 ``draft_notes`` already present. The caller commits.
    """
    keys = get_ticked_check_keys(conn, submission_id)
    if ticked:
        keys.add(check_key)
    else:
        keys.discard(check_key)
    encoded = json.dumps(sorted(keys))
    conn.execute(
        "INSERT INTO review_progress (submission_id, ticked_check_keys, updated_at) "
        "VALUES (?, ?, CURRENT_TIMESTAMP) "
        "ON CONFLICT(submission_id) DO UPDATE SET "
        "ticked_check_keys = excluded.ticked_check_keys, updated_at = CURRENT_TIMESTAMP",
        (submission_id, encoded),
    )


def get_draft_notes(conn: sqlite3.Connection, submission_id: int) -> str | None:
    """Read a submission's in-progress draft Notes (``review_progress.draft_notes``).

    The Story-4.8 Notes autosave layer, rehydrated by the AR-5-pure
    ``GET /review/{id}`` into the textarea so a mid-review reload keeps the typed
    reason. ``None`` when no ``review_progress`` row exists yet."""
    progress = get_review_progress(conn, submission_id)
    return progress.draft_notes if progress is not None else None


def set_draft_notes(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    draft_notes: str | None,
) -> None:
    """Upsert a submission's in-progress draft Notes (Story 4.8, AR-14).

    Mirrors :func:`set_check_tick`'s ``ON CONFLICT(submission_id)`` upsert but
    writes only ``draft_notes`` — PRESERVING any existing ``ticked_check_keys`` (the
    new row defaults the array to ``'[]'`` only when it did not exist). Bumps
    ``updated_at``. A manual draft is an in-progress reason — NEVER a disposition
    (contract #4). The caller commits (``connect()`` commits on clean exit)."""
    conn.execute(
        "INSERT INTO review_progress (submission_id, draft_notes, updated_at) "
        "VALUES (?, ?, CURRENT_TIMESTAMP) "
        "ON CONFLICT(submission_id) DO UPDATE SET "
        "draft_notes = excluded.draft_notes, updated_at = CURRENT_TIMESTAMP",
        (submission_id, draft_notes),
    )


# ── disposition write helpers (Story 4.8) ────────────────────────────────────
# The web layer's ONLY writes to the human-decision columns: `disposition`,
# `decided_at`, `decision_notes`, `correction_due_at`. These NEVER touch the
# pipeline-owned engine columns (`engine_verdict` / `checklist_items` / comparisons)
# — contract #4 / pipeline-is-only-writer. Each flips `status` and the decision
# columns TOGETHER in one statement (the cross-column CHECK is symmetric +
# per-statement, so they cannot be set independently); the matching audit row + the
# commit are owned by `app/pipeline/status.py` (`record_decision` on DECIDED,
# `reopen` on UNDONE). These helpers DO NOT commit.


def record_disposition(
    conn: sqlite3.Connection,
    submission_id: int,
    *,
    disposition: str,
    decision_notes: str | None,
    decided_at: str,
) -> bool:
    """Atomically commit the human decision: set ``status='DECIDED'`` AND the three
    decision columns in ONE ``UPDATE`` (Story 4.8, AC3).

    The schema cross-column CHECK is symmetric and evaluated **per-statement** in
    SQLite — ``(status='DECIDED' ⇒ disposition NOT NULL)`` AND ``(status<>'DECIDED' ⇒
    disposition NULL)``. So neither ``status`` nor ``disposition`` can be set on its
    own without tripping the other branch; they MUST flip together in a single
    statement. The status lifecycle move is therefore co-located here, with the audit
    row written by ``status.record_decision`` on the same connection. ``decided_at`` is
    an ISO-8601 string (the as-filed storage convention). Does NOT commit.

    The UPDATE is a **compare-and-swap**: it fires only ``WHERE status='IN_REVIEW'`` so
    the row's open state IS the claim — collapsing the caller's check-then-act into one
    atomic statement. Two concurrent dispositions on the same row can no longer both
    win: the loser's UPDATE matches zero rows (the winner already flipped it off
    ``IN_REVIEW``). Returns ``True`` iff exactly the open row was claimed; ``False``
    means it was missing or no longer ``IN_REVIEW`` (already decided / never opened) —
    the caller turns that into a calm 409, the first decision standing."""
    cur = conn.execute(
        "UPDATE submissions SET status = 'DECIDED', disposition = ?, "
        "decision_notes = ?, decided_at = ? WHERE id = ? AND status = 'IN_REVIEW'",
        (disposition, decision_notes, decided_at, submission_id),
    )
    return cur.rowcount == 1


def clear_disposition(conn: sqlite3.Connection, submission_id: int) -> bool:
    """Atomically undo the decision: NULL the human decision columns AND flip
    ``status`` back to ``READY_FOR_REVIEW`` in ONE ``UPDATE`` (Story 4.8 undo, AC4).

    Clears ``disposition`` / ``decided_at`` / ``decision_notes`` AND
    ``correction_due_at`` (the deadline is only valid for ``NEEDS_CORRECTION`` per the
    schema CHECK, so it must clear with the disposition). Because the cross-column
    CHECK is symmetric + per-statement, the ``status`` move back to ``READY_FOR_REVIEW``
    is co-located in this single statement (the audit ``UNDONE`` row is written by
    ``status.reopen`` on the same connection). The ``review_progress`` row (ticks +
    draft notes) is deliberately UNTOUCHED — the undo reopens with the prior progress
    restored. Does NOT commit.

    The UPDATE is a **compare-and-swap** gated ``WHERE status='DECIDED'`` so the undo
    claims the decided row atomically — two concurrent undos cannot both succeed, and
    an undo of a row that is not (or no longer) ``DECIDED`` matches zero rows. Returns
    ``True`` iff the decided row was claimed; ``False`` means missing or not
    ``DECIDED`` — the caller surfaces a calm 409."""
    cur = conn.execute(
        "UPDATE submissions SET status = 'READY_FOR_REVIEW', disposition = NULL, "
        "decided_at = NULL, decision_notes = NULL, correction_due_at = NULL "
        "WHERE id = ? AND status = 'DECIDED'",
        (submission_id,),
    )
    return cur.rowcount == 1
