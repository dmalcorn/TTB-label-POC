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
