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
    error_text: str | None = None,
) -> int:
    """Insert one :class:`OcrResult` as an ``ocr_results`` row; return its id."""
    cur = conn.execute(
        """
        INSERT INTO ocr_results
            (label_image_id, submission_id, engine_name, engine_version,
             extracted_text, confidence, word_boxes, latency_ms, ran_on_cpu,
             status, error_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            result.status,
            error_text,
        ),
    )
    return int(cur.lastrowid)


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
    return int(cur.lastrowid)
