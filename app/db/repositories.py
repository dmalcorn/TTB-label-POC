"""Typed read layer over the mock COLA database.

Reads return Pydantic v2 models validated at the read boundary (AR-13). Field
names mirror the schema columns 1:1 (snake_case across DB ↔ Python ↔ JSON).
Raw SQL lives only here and in ``connection.py`` — the data boundary.

Timestamps/dates are kept as ISO-8601 ``str`` (the as-filed text SQLite stores),
not parsed to ``datetime`` — matching the data-dictionary's as-filed storage.
Enum columns are typed ``str``; the database ``CHECK`` constraints are the
source of truth, so they are not re-validated in Python.

Seeding/writes are Story 1.3+; this module is read-only.
"""

from __future__ import annotations

import sqlite3

from pydantic import BaseModel


class Submission(BaseModel):
    """One mock COLA application (``submissions`` row)."""

    id: int
    ttb_id: str
    serial_number: str | None = None
    beverage_type: str
    source_of_product: str | None = None
    application_type: str | None = None
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
    status: str
    engine_verdict: str | None = None
    disposition: str | None = None
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
    image_role: str | None = None
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
