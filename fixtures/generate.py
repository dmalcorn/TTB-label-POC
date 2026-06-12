"""Synthetic fixture-corpus generator (DEV TOOL — not a runtime dependency).

Run once in the dev virtualenv to (re)produce the committed fixture corpus:

    python fixtures/generate.py

Output (all committed, baked into the Docker image):
    fixtures/ground_truth.csv     one row per submission; APPLICATION fields +
                                  design tags (scenario/expected_verdict/violation_kind)
                                  + on-label Ground Truth (gt_*) + an `images` JSON manifest.
    fixtures/images/*.jpg         synthetic label images, RGB JPEG, named
                                  <ttb_id>_<NN>_<ROLE>.jpg.

OpenCV is used ONLY here (image rendering/distortion). The runtime seed
(`app/db/seed.py`) is stdlib-only and reads the committed CSV + images.

Determinism: a fixed RNG seed makes regeneration byte-stable, so re-running does
not churn the committed corpus. No network, no registry artwork — everything is
synthetic dummy data.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import cv2
import numpy as np

FIXTURES_DIR = Path(__file__).parent
IMAGES_DIR = FIXTURES_DIR / "images"
CSV_PATH = FIXTURES_DIR / "ground_truth.csv"

RNG = np.random.default_rng(20260612)

# Canonical Government Warning — 27 CFR 16.21 (exact wording).
GOV_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)
# A reworded warning (a real §16.21 deviation → FAIL in Epic 3).
GOV_WARNING_REWORDED = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should avoid "
    "alcoholic drinks during pregnancy due to the risk of birth defects. (2) "
    "Drinking alcohol impairs your ability to drive or operate machinery."
)

# ── APPLICATION columns (1:1 with the `submissions` table) ───────────────────
APPLICATION_COLUMNS = [
    "ttb_id",
    "serial_number",
    "beverage_type",
    "source_of_product",
    "application_type",
    "brand_name",
    "fanciful_name",
    "class_type_designation",
    "applicant_name_address",
    "mailing_address",
    "plant_registry_no",
    "alcohol_content",
    "net_contents",
    "grape_varietal",
    "wine_appellation",
    "wine_vintage",
    "formula_id",
    "phone",
    "email",
    "application_date",
    "submitted_at",
]
DESIGN_COLUMNS = ["scenario", "expected_verdict", "violation_kind"]
GT_COLUMNS = [
    "gt_brand_name",
    "gt_class_type_designation",
    "gt_alcohol_content",
    "gt_net_contents",
    "gt_applicant_name_address",
    "gt_government_warning",
]
CSV_COLUMNS = APPLICATION_COLUMNS + DESIGN_COLUMNS + GT_COLUMNS + ["images"]


# ── image rendering ──────────────────────────────────────────────────────────
def _blank(h: int, w: int) -> np.ndarray:
    return np.full((h, w, 3), 245, dtype=np.uint8)


def _wrap(text: str, font, scale: float, thickness: int, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        (tw, _), _ = cv2.getTextSize(trial, font, scale, thickness)
        if tw <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _put_block(img, text, org, scale=0.7, thickness=2, max_w=None, line_gap=14):
    font = cv2.FONT_HERSHEY_SIMPLEX
    x, y = org
    max_w = max_w or (img.shape[1] - 2 * x)
    for line in _wrap(text, font, scale, thickness, max_w):
        cv2.putText(img, line, (x, y), font, scale, (20, 20, 20), thickness, cv2.LINE_AA)
        (_, th), _ = cv2.getTextSize(line, font, scale, thickness)
        y += th + line_gap
    return y


def _rotate(img, angle):
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), borderValue=(245, 245, 245))


def _perspective(img):
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    d = 0.10
    dst = np.float32(
        [[w * d, h * d * 0.5], [w * (1 - d * 0.4), 0], [w, h], [w * 0.05, h * (1 - d * 0.3)]]
    )
    m = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img, m, (w, h), borderValue=(245, 245, 245))


def _glare(img):
    overlay = img.copy()
    h, w = img.shape[:2]
    center = (int(w * 0.62), int(h * 0.4))
    cv2.ellipse(overlay, center, (int(w * 0.22), int(h * 0.3)), 0, 0, 360, (255, 255, 255), -1)
    return cv2.addWeighted(overlay, 0.55, img, 0.45, 0)


def _degrade(img, kind):
    if kind == "rotate":
        return _rotate(img, RNG.uniform(6, 11) * (1 if RNG.random() > 0.5 else -1))
    if kind == "perspective":
        return _perspective(img)
    if kind == "glare":
        return _glare(img)
    return img


def _render_brand(row) -> np.ndarray:
    img = _blank(460, 720)
    cv2.rectangle(img, (12, 12), (708, 448), (60, 60, 60), 2)
    y = 70
    cv2.putText(img, row["gt_brand_name"], (40, y), cv2.FONT_HERSHEY_DUPLEX, 1.3, (15, 15, 15), 3)
    y += 60
    if row["fanciful_name"]:
        y = _put_block(img, row["fanciful_name"], (40, y), scale=0.8)
    if row["gt_class_type_designation"]:
        y = _put_block(img, row["gt_class_type_designation"], (40, y + 6), scale=0.75)
    y = max(y, 300)
    if row["gt_alcohol_content"]:
        y = _put_block(img, row["gt_alcohol_content"], (40, y + 10), scale=0.8)
    if row["gt_net_contents"]:
        _put_block(img, row["gt_net_contents"], (40, y + 6), scale=0.8)
    return img


def _render_back(row) -> np.ndarray:
    img = _blank(620, 720)
    cv2.rectangle(img, (12, 12), (708, 608), (60, 60, 60), 2)
    y = _put_block(img, row["gt_government_warning"], (36, 60), scale=0.62, thickness=2, max_w=648)
    if row["gt_applicant_name_address"]:
        _put_block(img, row["gt_applicant_name_address"], (36, y + 30), scale=0.6)
    return img


def _render_minor(label: str) -> np.ndarray:
    img = _blank(180, 360)
    cv2.rectangle(img, (8, 8), (352, 172), (60, 60, 60), 2)
    _put_block(img, label, (24, 70), scale=0.7)
    return img


def _write_image(img, ttb_id: str, position: int, role: str) -> dict:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{ttb_id}_{position:02d}_{role}.jpg"
    path = IMAGES_DIR / filename
    cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    h, w = img.shape[:2]
    return {
        "role": role,
        "position": position,
        "filename": filename,
        "mime_type": "image/jpeg",
        "width_px": int(w),
        "height_px": int(h),
        "file_size_bytes": int(os.path.getsize(path)),
    }


def _build_images(row) -> list[dict]:
    """Render this submission's image set; returns the label_images manifest."""
    degrade = row["_degrade_kind"] if row["scenario"] == "degraded" else None
    manifest: list[dict] = []

    brand = _render_brand(row)
    if degrade:
        brand = _degrade(brand, degrade)
    manifest.append(_write_image(brand, row["ttb_id"], 1, "BRAND"))

    # The missing-warning violation omits the back label entirely.
    if row["violation_kind"] != "missing_gov_warning":
        back = _render_back(row)
        if degrade:
            back = _degrade(back, degrade)
        manifest.append(_write_image(back, row["ttb_id"], 2, "BACK"))

    # One submission carries the full 10-image set (round-trip AC).
    if row.get("_ten_images"):
        roles = ["NECK", "STRIP"] + ["OTHER"] * 6
        for i, role in enumerate(roles, start=len(manifest) + 1):
            manifest.append(_write_image(_render_minor(f"{role} {i}"), row["ttb_id"], i, role))
    return manifest


# ── corpus definition ────────────────────────────────────────────────────────
_counter = 0


def _ttb_id() -> str:
    global _counter
    _counter += 1
    return f"26150{_counter:09d}"


def _row(**kw) -> dict:
    """Build a submission row; gt_* default to the matching APPLICATION value (clean)."""
    # Seed only APPLICATION + DESIGN columns so the gt_* defaults below take effect.
    row = {c: "" for c in APPLICATION_COLUMNS + DESIGN_COLUMNS}
    row.update(kw)
    row["ttb_id"] = _ttb_id()
    row["application_type"] = row.get("application_type") or "LABEL_APPROVAL"
    row["application_date"] = row.get("application_date") or "2026-05-15"
    row["submitted_at"] = row.get("submitted_at") or "2026-05-15T14:30:00Z"
    row["violation_kind"] = kw.get("violation_kind", "none")
    # Ground Truth (on-label) defaults to the application value (clean match);
    # the caller overrides specific gt_* fields to create a violation.
    row["gt_brand_name"] = kw.get("gt_brand_name", row.get("brand_name", ""))
    row["gt_class_type_designation"] = kw.get(
        "gt_class_type_designation", row.get("class_type_designation", "")
    )
    row["gt_alcohol_content"] = kw.get("gt_alcohol_content", row.get("alcohol_content", ""))
    row["gt_net_contents"] = kw.get("gt_net_contents", row.get("net_contents", ""))
    row["gt_applicant_name_address"] = kw.get(
        "gt_applicant_name_address", row.get("applicant_name_address", "")
    )
    row["gt_government_warning"] = kw.get("gt_government_warning", GOV_WARNING)
    return row


_SPIRITS = dict(
    beverage_type="DISTILLED_SPIRITS",
    source_of_product="DOMESTIC",
    class_type_designation="Kentucky Straight Bourbon Whiskey",
    alcohol_content="45% Alc./Vol.",
    net_contents="750 mL",
    plant_registry_no="DSP-KY-20013",
    phone="502-555-0144",
    email="labels@example-distillery.test",
)
_WINE = dict(
    beverage_type="WINE",
    source_of_product="DOMESTIC",
    class_type_designation="Napa Valley Cabernet Sauvignon",
    alcohol_content="13.5% Alc./Vol.",
    net_contents="750 mL",
    grape_varietal="Cabernet Sauvignon",
    wine_appellation="Napa Valley",
    wine_vintage="2021",
    plant_registry_no="BW-CA-5571",
    phone="707-555-0199",
    email="compliance@example-winery.test",
)
_MALT = dict(
    beverage_type="MALT_BEVERAGE",
    source_of_product="DOMESTIC",
    class_type_designation="India Pale Ale",
    alcohol_content="6.8% Alc./Vol.",
    net_contents="355 mL",
    plant_registry_no="BR-OR-1042",
    phone="503-555-0123",
    email="brewery@example-brewing.test",
)

# Brand pools per type (synthetic, dummy).
_BRANDS = {
    "DISTILLED_SPIRITS": [
        ("Stone's Throw", "Single Barrel Reserve"),
        ("Iron Gate", "Small Batch"),
        ("Copper Hollow", "Bottled in Bond"),
        ("Twelve Pines", "Cask Strength"),
        ("Rivermark", "Straight Rye Whiskey"),
    ],
    "WINE": [
        ("Marble Ridge", "Estate Reserve"),
        ("Quiet Harbor", "Old Vine"),
        ("Lantern Hill", "Barrel Select"),
        ("Cedar & Salt", "Coastal Cuvée"),
        ("Western Meadow", "Block 7"),
    ],
    "MALT_BEVERAGE": [
        ("Foghorn", "Hazy IPA"),
        ("Anvil & Oak", "West Coast IPA"),
        ("Tidewater", "Double IPA"),
        ("Switchback", "Session Ale"),
        ("North Pier", "Amber Lager"),
    ],
}


def _address(brand: str, kind: str) -> str:
    city = {"DISTILLED_SPIRITS": "Bardstown, KY", "WINE": "Napa, CA", "MALT_BEVERAGE": "Bend, OR"}[
        kind
    ]
    verb = {
        "DISTILLED_SPIRITS": "Distilled and Bottled By",
        "WINE": "Produced and Bottled By",
        "MALT_BEVERAGE": "Brewed and Bottled By",
    }[kind]
    return f"{verb} {brand} Co., {city}"


def _build_corpus() -> list[dict]:
    rows: list[dict] = []
    bases = {"DISTILLED_SPIRITS": _SPIRITS, "WINE": _WINE, "MALT_BEVERAGE": _MALT}
    serial = 0

    for kind, base in bases.items():
        brands = _BRANDS[kind]

        # 5 clean → PASS
        for i in range(5):
            serial += 1
            brand, fanciful = brands[i]
            row = _row(
                **base,
                serial_number=f"26-{serial:03d}",
                brand_name=brand,
                fanciful_name=fanciful,
                applicant_name_address=_address(brand, kind),
                scenario="clean",
                expected_verdict="PASS",
            )
            rows.append(row)

        # 4 violation → FAIL (varied check failures)
        violations = [
            ("abv_mismatch", {}),
            ("gov_warning_reworded", {}),
            ("off_standard_fill", {}),
            ("brand_mismatch", {}),
        ]
        for j, (vkind, _extra) in enumerate(violations):
            serial += 1
            brand, fanciful = brands[j % len(brands)]
            row = _row(
                **base,
                serial_number=f"26-{serial:03d}",
                brand_name=brand,
                fanciful_name=fanciful,
                applicant_name_address=_address(brand, kind),
                scenario="violation",
                expected_verdict="FAIL",
                violation_kind=vkind,
            )
            if vkind == "abv_mismatch":
                # Application says one ABV; the label (Ground Truth) shows another.
                row["gt_alcohol_content"] = "40% Alc./Vol." if kind != "WINE" else "11.5% Alc./Vol."
            elif vkind == "gov_warning_reworded":
                row["gt_government_warning"] = GOV_WARNING_REWORDED
            elif vkind == "off_standard_fill":
                # Off-standard metric size (not an approved standard of fill).
                bad = {"DISTILLED_SPIRITS": "720 mL", "WINE": "725 mL", "MALT_BEVERAGE": "330 mL"}[
                    kind
                ]
                row["net_contents"] = bad
                row["gt_net_contents"] = bad
            elif vkind == "brand_mismatch":
                # Label brand differs from the filed brand.
                row["gt_brand_name"] = f"{brand} Select"
            rows.append(row)

        # 3 degraded → REVIEW (clean data, degraded imagery)
        for k, dkind in enumerate(["glare", "rotate", "perspective"]):
            serial += 1
            brand, fanciful = brands[k]
            row = _row(
                **base,
                serial_number=f"26-{serial:03d}",
                brand_name=brand,
                fanciful_name=fanciful,
                applicant_name_address=_address(brand, kind),
                scenario="degraded",
                expected_verdict="REVIEW",
            )
            row["_degrade_kind"] = dkind
            rows.append(row)

    # Mark the first clean spirits submission as the full 10-image set (AC-4).
    rows[0]["_ten_images"] = True
    return rows


def main() -> None:
    rows = _build_corpus()
    # purge any stale generated images so regeneration is clean
    if IMAGES_DIR.exists():
        for old in IMAGES_DIR.glob("*.jpg"):
            old.unlink()

    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        # Force LF so the committed corpus is stable across OSes (matches the repo's
        # line-ending policy; avoids CRLF churn when regenerated on Windows).
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            manifest = _build_images(row)
            out = {c: row.get(c, "") for c in CSV_COLUMNS if c != "images"}
            out["images"] = json.dumps(manifest)
            writer.writerow(out)

    print(f"Wrote {len(rows)} submissions to {CSV_PATH}")
    print(f"Rendered {len(list(IMAGES_DIR.glob('*.jpg')))} images to {IMAGES_DIR}")


if __name__ == "__main__":
    main()
