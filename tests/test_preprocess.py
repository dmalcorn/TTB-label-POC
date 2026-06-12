"""Local OpenCV preprocessing tests (Story 2.3, AC1–AC5).

Offline, fast, deterministic — tiny synthetic images are generated in-test with
``cv2`` (NOT the committed fixtures), so the suite runs under
``docker run --network none`` with no GPU and no heavy fixture I/O. Highest-value
assertions (project-context Testing): **deskew-angle detection**, the
**clean-image no-op (no files written)**, **variant paths + log persisted**, and
the **§4 non-goals being structurally impossible** (the module exposes no
measure/verdict surface).
"""

from __future__ import annotations

import json
import sqlite3

import cv2
import numpy as np

from app.db import repositories as repo
from app.db.connection import connect, init_db
from app.pipeline import preprocess, run

# ── synthetic image helpers ──────────────────────────────────────────────────

_LINES = ["STONE'S THROW", "CABERNET SAUVIGNON", "ALC 13.5% BY VOL", "750 ML", "NAPA VALLEY 2021"]


def _label_bgr(angle: float = 0.0, w: int = 600, h: int = 400) -> np.ndarray:
    """A clean, evenly-lit black-text-on-white label (optionally rotated by
    ``angle`` degrees) as a 3-channel BGR array — what a decoded JPEG looks like."""
    gray = np.full((h, w), 255, np.uint8)
    for i, line in enumerate(_LINES):
        cv2.putText(gray, line, (40, 70 + i * 60), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 0, 2, cv2.LINE_AA)
    if angle:
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        gray = cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _write_image(path, angle: float = 0.0) -> None:
    cv2.imwrite(str(path), _label_bgr(angle))


# ── AC1 / AC4: clean image is a no-op-safe pass-through (no files) ────────────


def test_clean_image_skips_all_corrective_steps_and_writes_no_files(tmp_path):
    """AC1/AC4: an already-clean image trips no detector, so NO variant files are
    written and the original is left untouched (not degraded)."""
    src = tmp_path / "clean_01_BRAND.jpg"
    _write_image(src, angle=0.0)
    original_bytes = src.read_bytes()
    out_dir = tmp_path / "gen"

    result = preprocess.preprocess_image(src, out_dir)

    assert result.any_applied is False
    assert result.enhanced_path is None and result.binarized_path is None
    # No variant files written for a clean image (the "omitted, not inert" contract).
    assert not out_dir.exists() or list(out_dir.iterdir()) == []
    # The original file is byte-for-byte untouched.
    assert src.read_bytes() == original_bytes
    # Every corrective step recorded as skipped (a near-no-op log).
    corrective = {
        "denoise",
        "normalize_illumination_glare",
        "clahe_contrast",
        "deskew",
        "perspective_correct",
    }
    applied = {e["step"] for e in result.log if e.get("applied")}
    assert applied.isdisjoint(corrective)


# ── AC1 / AC3: deskew detection + ordered log + per-stage timing + files ──────


def test_deskew_case_detects_angle_logs_transforms_and_writes_both_variants(tmp_path):
    """AC1/AC3: an image rotated by a known angle → deskew detects ≈ that angle
    (within tolerance), the log records the angle + ordered transforms + per-stage
    ms, and an enhanced + binarized file are written."""
    src = tmp_path / "skew_01_BRAND.jpg"
    _write_image(src, angle=7.0)
    out_dir = tmp_path / "gen"

    result = preprocess.preprocess_image(src, out_dir)

    assert result.any_applied is True
    # Both variants written to the out_dir, referenced by relative basename.
    assert result.enhanced_path == "skew_01_BRAND__enhanced.png"
    assert result.binarized_path == "skew_01_BRAND__binarized.png"
    assert (out_dir / result.enhanced_path).exists()
    assert (out_dir / result.binarized_path).exists()

    deskew_entry = next(e for e in result.log if e["step"] == "deskew")
    assert deskew_entry["applied"] is True
    # Detected magnitude ≈ the 7° we induced (sign is the correction direction).
    assert abs(abs(deskew_entry["deskew_angle"]) - 7.0) <= 1.0
    assert "ms" in deskew_entry  # per-stage timing recorded
    # The transform log is ORDERED per image-handling.md §3 (corrective steps in order).
    steps = [e["step"] for e in result.log]
    assert steps[:7] == [
        "decode_normalize_color",
        "to_grayscale",
        "denoise",
        "normalize_illumination_glare",
        "clahe_contrast",
        "deskew",
        "perspective_correct",
    ]
    assert steps[-1] == "binarize"  # binarize logged only when variants are produced


def test_preprocess_is_deterministic(tmp_path):
    """§3: deterministic given the same input (no randomness) — same paths, same
    applied-flags, same detected angle on a repeat run."""
    src = tmp_path / "skew_01_BRAND.jpg"
    _write_image(src, angle=5.0)

    r1 = preprocess.preprocess_image(src, tmp_path / "g1")
    r2 = preprocess.preprocess_image(src, tmp_path / "g2")

    assert r1.enhanced_path == r2.enhanced_path
    assert [e["applied"] for e in r1.log] == [e["applied"] for e in r2.log]
    a1 = next(e for e in r1.log if e["step"] == "deskew")["deskew_angle"]
    a2 = next(e for e in r2.log if e["step"] == "deskew")["deskew_angle"]
    assert a1 == a2
    # Pixel-identical enhanced variants.
    v1 = cv2.imread(str(tmp_path / "g1" / r1.enhanced_path), cv2.IMREAD_GRAYSCALE)
    v2 = cv2.imread(str(tmp_path / "g2" / r2.enhanced_path), cv2.IMREAD_GRAYSCALE)
    assert np.array_equal(v1, v2)


def test_unreadable_source_is_skipped_not_raised(tmp_path):
    """AC4: a missing/corrupt source is recorded honestly and skipped — never
    raised (still-unreadable images are flagged downstream, not failed here)."""
    missing = tmp_path / "nope_01_BRAND.jpg"
    result = preprocess.preprocess_image(missing, tmp_path / "gen")
    assert result.enhanced_path is None and result.binarized_path is None
    assert result.log[0]["step"] == "decode_normalize_color"
    assert result.log[0]["applied"] is False


# ── AC4: §4 non-goals are structurally impossible ────────────────────────────


def test_module_exposes_no_measurement_or_verdict_surface():
    """AC4: the module measures no font/dimension and makes no verdict/reject call
    — structurally, it exposes only image transforms + a log. Guard against a
    future edit quietly adding a measure/verdict function."""
    forbidden = (
        "font",
        "measure",
        "dimension",
        "millimeter",
        "verdict",
        "reject",
        "disposition",
        "approve",
    )
    public = [name for name in dir(preprocess) if not name.startswith("_")]
    offenders = [n for n in public if any(tok in n.lower() for tok in forbidden)]
    assert offenders == [], f"preprocess must expose no measure/verdict surface; found {offenders}"
    # The result carries images + a log ONLY — no verdict/score/reject field.
    fields = set(preprocess.PreprocessResult.__dataclass_fields__)
    assert fields == {"enhanced_path", "binarized_path", "log", "total_ms", "any_applied"}


# ── stage seam: DB helpers, persistence, lifecycle (AC2 / AC3 / AC5) ──────────


def _insert_received(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26001000000001",
        "beverage_type": "WINE",
        "status": "RECEIVED",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    return int(cur.lastrowid)


def _insert_image(conn: sqlite3.Connection, submission_id: int, filename: str, position: int = 1):
    cur = conn.execute(
        "INSERT INTO label_images (submission_id, image_role, position, filename) "
        "VALUES (?, 'BRAND', ?, ?)",
        (submission_id, position, filename),
    )
    conn.commit()
    return int(cur.lastrowid)


def _wire_dirs(monkeypatch, tmp_path):
    """Point the stage's read-only source root at a tmp dir and the generated-images
    root at another, so the stage reads/writes synthetic images only."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    gen_dir = tmp_path / "generated"
    monkeypatch.setattr(preprocess, "SOURCE_IMAGES_DIR", src_dir)
    monkeypatch.setenv("GENERATED_IMAGES_DIR", str(gen_dir))
    return src_dir, gen_dir


def test_stage_persists_variants_and_log_for_a_degraded_image(tmp_path, monkeypatch):
    """AC2/AC3: after the stage runs via the seam against a tmp_path DB, the
    label_images row has enhanced_path/binarized_path/preprocess_log/preprocess_ms
    populated, the log carries the deskew angle, and the original filename is
    unchanged."""
    src_dir, gen_dir = _wire_dirs(monkeypatch, tmp_path)
    _write_image(src_dir / "26150000000001_01_BRAND.jpg", angle=8.0)

    db_path = tmp_path / "p.db"
    init_db(db_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn)
        _insert_image(conn, sid, "26150000000001_01_BRAND.jpg")

    run.process_submission(str(db_path), sid)  # real STAGES include preprocess_stage

    with connect(db_path) as conn:
        img = repo.list_label_images(conn, sid)[0]
        sub = repo.get_submission(conn, sid)
    assert img.filename == "26150000000001_01_BRAND.jpg"  # original untouched
    assert img.enhanced_path == "26150000000001_01_BRAND__enhanced.png"
    assert img.binarized_path == "26150000000001_01_BRAND__binarized.png"
    assert (gen_dir / img.enhanced_path).exists()
    assert img.preprocess_ms is not None and img.preprocess_ms >= 0
    assert img.preprocessed_at is not None
    log = json.loads(img.preprocess_log)
    assert any(e["step"] == "deskew" and e["applied"] for e in log)
    # AC3: preprocessing time contributes to the submission's processing_ms.
    assert sub is not None and sub.processing_ms is not None
    assert sub.processing_ms >= img.preprocess_ms


def test_stage_clean_image_writes_no_variant_files_paths_stay_null(tmp_path, monkeypatch):
    """AC5: a clean image with no detected defects produces NO variant files; the
    row's variant paths stay NULL (OCR will run on the original) — yet the log and
    timing are still recorded (the benchmark wants to know enhancement was a no-op)."""
    src_dir, gen_dir = _wire_dirs(monkeypatch, tmp_path)
    _write_image(src_dir / "26150000000002_01_BRAND.jpg", angle=0.0)

    db_path = tmp_path / "p.db"
    init_db(db_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, ttb_id="26001000000002")
        _insert_image(conn, sid, "26150000000002_01_BRAND.jpg")

    run.process_submission(str(db_path), sid)

    with connect(db_path) as conn:
        img = repo.list_label_images(conn, sid)[0]
    assert img.enhanced_path is None and img.binarized_path is None
    assert not gen_dir.exists() or list(gen_dir.iterdir()) == []
    assert img.preprocess_log is not None  # log still recorded (no-op evidence)
    assert img.preprocess_ms is not None


def test_stage_stashes_variant_paths_in_scratch_for_ocr(tmp_path, monkeypatch):
    """Seam hand-off: the stage stashes each image's variant paths in ctx.scratch
    so the OCR stage (2.4) can consume them without widening the contract."""
    src_dir, _ = _wire_dirs(monkeypatch, tmp_path)
    _write_image(src_dir / "26150000000003_01_BRAND.jpg", angle=6.0)

    db_path = tmp_path / "p.db"
    init_db(db_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, ttb_id="26001000000003")
        lid = _insert_image(conn, sid, "26150000000003_01_BRAND.jpg")
        submission = repo.get_submission(conn, sid)
        images = repo.list_label_images(conn, sid)
        ctx = run.StageContext(conn=conn, submission=submission, label_images=images)
        preprocess.preprocess_stage(ctx)
        variants = ctx.scratch["variants"][lid]
    assert variants["original"] == "26150000000003_01_BRAND.jpg"
    assert variants["enhanced"] == "26150000000003_01_BRAND__enhanced.png"
    assert variants["binarized"] == "26150000000003_01_BRAND__binarized.png"


# ── AC5: registration into the 2.2 seam (no scheduler/status change) ──────────


def test_preprocess_stage_registered_at_front_of_stages():
    """AC5: preprocess plugs into run.STAGES as the FIRST heavy stage, before OCR."""
    assert run.STAGES[0] is preprocess.preprocess_stage
    assert run.STAGES[0].__name__ == "preprocess_stage"


def test_lifecycle_reaches_ready_with_preprocess_stage_present(tmp_path, monkeypatch):
    """AC5: with preprocess registered, a submission still advances all the way to
    READY_FOR_REVIEW (the 2.2 lifecycle spine is unchanged by adding the stage)."""
    src_dir, _ = _wire_dirs(monkeypatch, tmp_path)
    _write_image(src_dir / "26150000000004_01_BRAND.jpg", angle=0.0)

    db_path = tmp_path / "p.db"
    init_db(db_path)
    with connect(db_path) as conn:
        sid = _insert_received(conn, ttb_id="26001000000004")
        _insert_image(conn, sid, "26150000000004_01_BRAND.jpg")

    run.process_submission(str(db_path), sid)

    with connect(db_path) as conn:
        assert repo.get_status(conn, sid) == "READY_FOR_REVIEW"
