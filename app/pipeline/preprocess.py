"""Local OpenCV image preprocessing — the first heavy pipeline stage (Story 2.3).

Cleans up imperfect label photos (skew, glare, low contrast, noise, off-angle)
**before OCR** so a readable-but-imperfect image is handled without bouncing a
correction cycle back to the applicant (FR-10). Everything here is **pure local
``cv2`` on the CPU** — no LLM, no network — so it runs under
``docker run --network none`` with zero egress (image-handling.md §5; the
"OpenCV image enhancement" row of the outbound-calls inventory is classified
``none``).

The ordered, **conditional** chain follows ``docs/image-handling.md`` §3: decode/
color-normalize → grayscale → denoise → illumination/glare → CLAHE contrast →
deskew → perspective → binarization. Every corrective step runs **only when its
detector says it is needed**, so an already-clean image is never degraded
(over-denoise / over-threshold can *lower* OCR accuracy). A clean image therefore
produces **no variant files at all** — OCR then runs on the original (AC5; the
"omitted, not inert, when no preprocessing was applied" UI contract, UX-DR-13).

Two derived outputs (engine-aware, image-handling.md §3): an **enhanced**
grayscale variant (PaddleOCR's preferred input) and a **binarized** variant
(Tesseract's preferred input). Both are written to the generated-images root and
referenced by path on ``label_images`` (D7/AR-7); the original is untouched.

Non-goals (image-handling.md §4, AC4) — this module **never**:
- measures font size / physical dimensions (no reliable pixel→mm from a photo),
- fabricates unreadable text (it normalizes pixels; the engines read what's there),
- auto-rejects: an image still unreadable after enhancement is left for the
  engine to flag ``REVIEW`` downstream, not failed here.
It returns images + a log only — there is deliberately no verdict/measure call.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from app.config import get_settings
from app.db import repositories as repo

if TYPE_CHECKING:  # avoid a run.py ↔ preprocess.py import cycle (run imports this stage)
    from app.pipeline.run import StageContext

logger = logging.getLogger(__name__)

# Where the original (seeded) images live — baked read-only into the image at
# /app/fixtures/images, mirroring app/db/seed.FIXTURES_DIR. `label_images.filename`
# is a bare basename; the source path is this root + that name. Tests monkeypatch
# this to point at synthetic images. (When real uploads land post-POC this becomes
# configurable; seeded fixtures stay read-only either way.)
SOURCE_IMAGES_DIR: Path = Path(__file__).resolve().parents[2] / "fixtures" / "images"

# Variant filename suffixes (PNG = lossless, the right format for an OCR input).
_ENHANCED_SUFFIX = "__enhanced.png"
_BINARIZED_SUFFIX = "__binarized.png"

# Detector thresholds — conservative so a clean image trips nothing. Tuned for the
# 0–255 grayscale domain. Each is documented at its use site.
_NOISE_SIGMA_THRESHOLD = 3.0  # Immerkær noise sigma above which denoise helps
_GLARE_FRACTION_THRESHOLD = 0.01  # ≥1% near-white pixels ⇒ glare hotspots present
_ILLUMINATION_SPREAD_THRESHOLD = 60.0  # background max−min ⇒ uneven lighting
_LOW_CONTRAST_STD_THRESHOLD = 40.0  # global intensity std below which CLAHE helps
_DESKEW_MIN_ANGLE_DEG = 0.5  # ignore sub-degree skew (within measurement noise)
_CLAHE_CLIP_LIMIT = 2.0


@dataclass
class PreprocessResult:
    """The outcome of preprocessing one image.

    ``enhanced_path`` / ``binarized_path`` are basenames **relative to the
    out_dir** the variants were written into (``None`` when the image was clean
    and no variant was produced). ``log`` is the ordered per-step record (each
    ``{step, applied, ms, **params}``) — the benchmark/audit trail. ``total_ms``
    is the whole-image wall-time. ``any_applied`` is the gate: ``True`` iff at
    least one *corrective* step ran (and therefore variants were written).
    """

    enhanced_path: str | None
    binarized_path: str | None
    log: list[dict[str, Any]] = field(default_factory=list)
    total_ms: int = 0
    any_applied: bool = False


# ── individual steps (each a small, pure, detector-gated function) ────────────
# Corrective steps return ``(image, applied, params)``; structural steps (decode,
# grayscale, binarize) are unconditional transforms with no detector.


def decode_normalize_color(src_path: str | Path) -> np.ndarray | None:
    """Step 1 — decode to a 3-channel BGR (RGB-equivalent) array; ``None`` if the
    file is missing or unreadable. ``IMREAD_COLOR`` drops any alpha and yields a
    consistent 3-channel input regardless of source (honoring the RGB-not-CMYK
    constraint; OpenCV decodes to BGR)."""
    img = cv2.imread(str(src_path), cv2.IMREAD_COLOR)
    return img  # cv2 returns None on a missing/corrupt file — caller treats as unreadable


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """Step 2 — BGR → single-channel gray; downstream skew/threshold work on
    intensity and color channels only add noise."""
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _estimate_noise_sigma(gray: np.ndarray) -> float:
    """Immerkær's fast noise estimate: convolve with a Laplacian-of-Laplacian mask
    and scale. Higher ⇒ more sensor/JPEG noise. Deterministic, O(pixels)."""
    h, w = gray.shape
    if h < 3 or w < 3:
        return 0.0
    mask = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64)
    conv = cv2.filter2D(gray.astype(np.float64), -1, mask)
    sigma = float(np.sum(np.abs(conv)) * np.sqrt(0.5 * np.pi) / (6.0 * (w - 2) * (h - 2)))
    return sigma


def denoise(gray: np.ndarray) -> tuple[np.ndarray, bool, dict[str, Any]]:
    """Step 3 — remove sensor/compression noise *only* when it is actually present
    (over-denoising smears text and hurts OCR). Detector: Immerkær noise sigma."""
    sigma = _estimate_noise_sigma(gray)
    params: dict[str, Any] = {"noise_sigma": round(sigma, 3)}
    if sigma <= _NOISE_SIGMA_THRESHOLD:
        return gray, False, params
    out = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
    return out, True, params


def normalize_illumination_glare(gray: np.ndarray) -> tuple[np.ndarray, bool, dict[str, Any]]:
    """Step 4 — even out uneven lighting and blown-out **glare** hotspots (the
    exact "imperfect image" the brief calls out) so text isn't lost under a bright
    patch. Detector: **background unevenness** — the luma spread of a heavily
    smoothed background estimate. This deliberately does NOT fire on a uniformly
    lit page that is merely mostly-white (a plain label), only on a real lighting
    gradient or a localized hotspot. Technique: divide by the background estimate
    to flatten the gradient, then inpaint any genuinely saturated (post-smoothing)
    hotspot so it doesn't read as a hole in the text."""
    # Heavy smoothing so text-density variation averages out — what remains is the
    # lighting field, not the print. A flat field ⇒ small spread ⇒ skip.
    background = cv2.GaussianBlur(gray, (0, 0), sigmaX=max(gray.shape) / 8.0)
    spread = float(int(background.max()) - int(background.min()))
    # A "true" hotspot stays saturated even after the heavy blur (a blown region),
    # unlike white paper broken up by text. Used only to decide whether to inpaint.
    hotspot_fraction = float(np.mean(background >= 250))
    params: dict[str, Any] = {
        "illumination_spread": round(spread, 1),
        "hotspot_fraction": round(hotspot_fraction, 4),
    }
    if spread < _ILLUMINATION_SPREAD_THRESHOLD:
        return gray, False, params

    # Background division flattens uneven illumination; rescale back to 0–255.
    safe_bg = np.where(background == 0, 1, background).astype(np.float32)
    normalized = gray.astype(np.float32) / safe_bg
    normalized = cv2.normalize(normalized, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    if hotspot_fraction >= _GLARE_FRACTION_THRESHOLD:  # inpaint genuine blown hotspots
        hotspots = (background >= 250).astype(np.uint8) * 255
        normalized = cv2.inpaint(normalized, hotspots, 3, cv2.INPAINT_TELEA)
    return normalized, True, params


def clahe_contrast(gray: np.ndarray) -> tuple[np.ndarray, bool, dict[str, Any]]:
    """Step 5 — Contrast-Limited Adaptive Histogram Equalization lifts faint,
    low-contrast text locally without over-amplifying noise. Detector: low global
    intensity standard deviation."""
    std = float(np.std(gray))
    params: dict[str, Any] = {"intensity_std": round(std, 2), "clahe_clip": _CLAHE_CLIP_LIMIT}
    if std >= _LOW_CONTRAST_STD_THRESHOLD:
        return gray, False, params
    clahe = cv2.createCLAHE(clipLimit=_CLAHE_CLIP_LIMIT, tileGridSize=(8, 8))
    return clahe.apply(gray), True, params


def _detect_skew_angle(gray: np.ndarray) -> float:
    """Detected text skew in degrees (the angle to ROTATE BY to straighten). Builds
    a foreground mask (Otsu, text = white), takes the ``minAreaRect`` over the
    foreground coordinates, and normalizes its angle into (-45, 45]. Deterministic."""
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(mask)
    if coords is None or len(coords) < 10:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    # OpenCV reports the rect angle in [-90, 0) (legacy) or (0, 90]; fold to (-45, 45].
    if angle > 45:
        angle -= 90
    elif angle < -45:
        angle += 90
    return float(angle)


def deskew(gray: np.ndarray) -> tuple[np.ndarray, bool, dict[str, Any]]:
    """Step 6 — straighten a tilted scan/photo so OCR line-detection works. The
    **detected angle is logged** (image-handling.md §3). Sub-degree skew is left
    alone (within measurement noise; rotating it would only resample)."""
    angle = _detect_skew_angle(gray)
    params: dict[str, Any] = {"deskew_angle": round(angle, 3)}
    if abs(angle) < _DESKEW_MIN_ANGLE_DEG:
        return gray, False, params
    h, w = gray.shape
    center = (w / 2, h / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated, True, params


def perspective_correct(gray: np.ndarray) -> tuple[np.ndarray, bool, dict[str, Any]]:
    """Step 7 — flatten an **off-angle** photo where the label is shot from a slant,
    rectifying to a front-on view. Conservative detector: a single dominant convex
    quadrilateral covering most (but not all) of the frame. Skips otherwise — a
    false perspective warp is far more damaging to OCR than leaving the image be."""
    params: dict[str, Any] = {"quad_found": False}
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return gray, False, params

    h, w = gray.shape
    frame_area = float(h * w)
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if not (0.30 * frame_area <= area <= 0.97 * frame_area):
        return gray, False, params  # nothing label-sized and sub-frame ⇒ no off-angle quad
    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
    if len(approx) != 4 or not cv2.isContourConvex(approx):
        return gray, False, params

    quad = _order_quad(approx.reshape(4, 2).astype(np.float32))
    # Skip a quad that is already axis-aligned (a straight crop, not an off-angle shot).
    if _is_axis_aligned(quad):
        return gray, False, params
    dst_w, dst_h = _target_size(quad)
    dst = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], np.float32)
    matrix = cv2.getPerspectiveTransform(quad, dst)
    warped = cv2.warpPerspective(gray, matrix, (dst_w, dst_h))
    params["quad_found"] = True
    return warped, True, params


def _order_quad(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as TL, TR, BR, BL (by coordinate sums/diffs)."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    rect[0] = pts[np.argmin(s)]  # top-left  — smallest x+y
    rect[2] = pts[np.argmax(s)]  # bottom-right — largest x+y
    rect[1] = pts[np.argmin(d)]  # top-right — smallest y−x
    rect[3] = pts[np.argmax(d)]  # bottom-left — largest y−x
    return rect


def _is_axis_aligned(quad: np.ndarray, tol: float = 3.0) -> bool:
    """True if the quad's edges are within ``tol`` px of axis-aligned (a plain crop,
    no perspective to correct)."""
    tl, tr, br, bl = quad
    return (
        abs(tl[1] - tr[1]) <= tol
        and abs(bl[1] - br[1]) <= tol
        and abs(tl[0] - bl[0]) <= tol
        and abs(tr[0] - br[0]) <= tol
    )


def _target_size(quad: np.ndarray) -> tuple[int, int]:
    tl, tr, br, bl = quad
    width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    return max(width, 1), max(height, 1)


def binarize(gray: np.ndarray) -> np.ndarray:
    """Step 8 — crisp black-text-on-white for the OCR engines (esp. Tesseract).
    Adaptive Gaussian threshold handles residual uneven lighting better than a
    single global Otsu cut. Produced as the OCR-input variant, alongside the
    enhanced grayscale."""
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize=31, C=10
    )


# ── orchestration: the full conditional chain for one image ───────────────────


def _timed(step_name: str, fn: Any, *args: Any) -> tuple[Any, dict[str, Any]]:
    """Run a corrective step, returning ``(image, log_entry)`` with timing + params.
    ``fn`` returns ``(image, applied, params)``."""
    start = time.monotonic()
    image, applied, params = fn(*args)
    entry = {"step": step_name, "applied": applied, "ms": int((time.monotonic() - start) * 1000)}
    entry.update(params)
    return image, entry


def preprocess_image(src_path: str | Path, out_dir: str | Path) -> PreprocessResult:
    """Run the ordered, conditional OpenCV chain on one image.

    Writes an **enhanced** and a **binarized** variant into ``out_dir`` (PNG)
    **only if at least one corrective step was needed**; a clean image produces no
    files and ``enhanced_path``/``binarized_path`` stay ``None`` (AC1/AC4/AC5).
    Returns the relative variant basenames, the ordered transform log (incl.
    detected deskew angle + CLAHE clip), and per-stage/total timing. Never raises
    on an unreadable image — it records the skip and returns cleanly (AC4: still-
    unreadable images are flagged downstream, not failed here). Deterministic.
    """
    overall_start = time.monotonic()
    log: list[dict[str, Any]] = []

    img = decode_normalize_color(src_path)
    if img is None:
        log.append({"step": "decode_normalize_color", "applied": False, "note": "unreadable"})
        return PreprocessResult(None, None, log, int((time.monotonic() - overall_start) * 1000))
    log.append({"step": "decode_normalize_color", "applied": True})

    gray = to_grayscale(img)
    log.append({"step": "to_grayscale", "applied": True})

    gray, entry = _timed("denoise", denoise, gray)
    log.append(entry)
    gray, entry = _timed("normalize_illumination_glare", normalize_illumination_glare, gray)
    log.append(entry)
    gray, entry = _timed("clahe_contrast", clahe_contrast, gray)
    log.append(entry)
    gray, entry = _timed("deskew", deskew, gray)
    log.append(entry)
    gray, entry = _timed("perspective_correct", perspective_correct, gray)
    log.append(entry)

    # Gate on the CORRECTIVE steps only (decode/grayscale/binarize are structural):
    # if the image was clean, write nothing so OCR uses the original (AC5, UX-DR-13).
    corrective = {
        "denoise",
        "normalize_illumination_glare",
        "clahe_contrast",
        "deskew",
        "perspective_correct",
    }
    any_applied = any(e["applied"] for e in log if e["step"] in corrective)

    total_ms = int((time.monotonic() - overall_start) * 1000)
    if not any_applied:
        return PreprocessResult(None, None, log, total_ms, any_applied=False)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(src_path).stem
    enhanced_name = f"{stem}{_ENHANCED_SUFFIX}"
    binarized_name = f"{stem}{_BINARIZED_SUFFIX}"
    # cv2.imwrite returns False (it does NOT raise) on a failed write — un-writable
    # root, full disk, bad encode. Never persist a variant path for a file that was
    # not actually written, or OCR (2.4) would read a dangling path: drop a failed
    # variant to None so the row references only files that exist.
    enhanced_ok = bool(cv2.imwrite(str(out_dir / enhanced_name), gray))
    binarized_ok = bool(cv2.imwrite(str(out_dir / binarized_name), binarize(gray)))
    if not enhanced_ok:
        logger.warning("Preprocess: failed to write enhanced variant %s", enhanced_name)
    if not binarized_ok:
        logger.warning("Preprocess: failed to write binarized variant %s", binarized_name)
    log.append({"step": "binarize", "applied": binarized_ok})
    return PreprocessResult(
        enhanced_name if enhanced_ok else None,
        binarized_name if binarized_ok else None,
        log,
        total_ms,
        any_applied=True,
    )


# ── the stage adapter (registered into run.STAGES — Story 2.2 seam) ───────────


def preprocess_stage(ctx: StageContext) -> None:
    """Story 2.3 pipeline stage: preprocess every label image of the submission.

    For each ``label_images`` row it resolves the source image, runs
    :func:`preprocess_image` into the configured generated-images root, persists
    the variant paths + transform log + per-image ``preprocess_ms`` onto the row
    (:func:`repo.update_label_image_variants`), and stashes the variant paths in
    ``ctx.scratch['variants']`` for the OCR stage (2.4) to consume. The stage's
    wall-time rolls into ``submissions.processing_ms`` via ``run.py``'s loop timer
    (this stage runs inside it) — no separate accumulation is needed. A
    missing/unreadable source, or any unexpected per-image failure, is recorded
    honestly and skipped — never raised, and never aborts the other images (AC4).
    Registered at the FRONT of :data:`run.STAGES`, before OCR.
    """
    # All derived variants live under this single, purgeable root (config
    # GENERATED_IMAGES_DIR), kept separate from the read-only seeded fixtures.
    # TODO(epic-6-reset / AR-12 / FR-27): POST /reset must purge this root when it
    # re-seeds — this story owns producing the files under one clearly-named dir and
    # leaving this hook; it does NOT implement reset.
    generated_root = Path(get_settings().generated_images_dir)
    variants: dict[int, dict[str, str | None]] = ctx.scratch.setdefault("variants", {})

    for image in ctx.label_images:
        # Per-image isolation: one bad image (a cv2.error on a pathological input, a
        # write/DB failure) must not skip the rest of a multi-image submission. Log
        # an honest skip and move on — the row keeps its NULL preprocess columns and
        # the engine flags REVIEW downstream (AC4: skip, don't fail the batch).
        try:
            src_path = SOURCE_IMAGES_DIR / image.filename
            if not src_path.exists():
                logger.warning(
                    "Preprocess: source image missing for label_image %s: %s", image.id, src_path
                )
                result = PreprocessResult(
                    None,
                    None,
                    [
                        {
                            "step": "decode_normalize_color",
                            "applied": False,
                            "note": "source_missing",
                        }
                    ],
                    0,
                )
            else:
                result = preprocess_image(src_path, generated_root)

            repo.update_label_image_variants(
                ctx.conn,
                image.id,
                enhanced_path=result.enhanced_path,
                binarized_path=result.binarized_path,
                preprocess_log=result.log,
                preprocess_ms=result.total_ms,
                preprocessed_at=datetime.now(UTC).isoformat(),
            )
            variants[image.id] = {
                "original": image.filename,
                "enhanced": result.enhanced_path,
                "binarized": result.binarized_path,
            }
        except Exception:  # noqa: BLE001 — one bad image must not skip the rest (AC4)
            logger.exception(
                "Preprocess: unexpected failure on label_image %s; skipping it", image.id
            )
            variants[image.id] = {"original": image.filename, "enhanced": None, "binarized": None}

    ctx.conn.commit()  # commit-per-stage: durable before OCR runs (mirrors status.py)
