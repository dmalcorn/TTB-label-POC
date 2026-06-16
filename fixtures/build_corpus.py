"""Real-data corpus builder (DEV TOOL — run locally, output is committed).

Builds the demo corpus from REAL public TTB COLA Registry records harvested into
``C:/alcorn/Treasury/label-samples-complete`` by
``targetsetup/scripts/cola_harvest.py``:

    python fixtures/build_corpus.py

Output (committed, baked into the Docker image — same contract as seed.py):
    fixtures/ground_truth.csv   APPLICATION fields + design tags + on-label gt_*
                                + an `images` JSON manifest, one row per submission.
    fixtures/images/*.jpg       the real label artwork, copied + renamed.

Corpus = **5 real COLA records per beverage type** (spirits, wine, malt). Unlike the
earlier build, **NET CONTENTS and ALCOHOL CONTENT are now REAL** — read from the
printable-form boxes 12/13 (see docs/abv-net-contents-investigation.md) for every wine
and spirit. **Country of origin** is real (origin_code). The completeness harvest
preferred records that carry real net/ABV; that pulled import/blend wines without a
single grape varietal, so **grape varietal is dropped** (net + ABV are common-element
requirements and win the tie — Diane's call). **Malt ABV** is the one field still not
published (beer forms leave box 13 blank); it is left blank ⇒ the engine REVIEWs it
(the malt ABV-optional policy), never a false FAIL.

One engineered ~10% failure: a spirit's ABV is filed off the label (THE PEDDLER —
43% filed vs 46% on label) so the field-match flags a clean mismatch.

Identity fields come from the public registry; class/type is cleaned of TTB code
filler ("TABLE RED WINE" → "Red Wine", "VODKA 80-89 PROOF FB" → "Vodka").
``applicant_name_address`` is left blank ⇒ REVIEW (the registry's permit+legal-entity
+street line never matches the short bottler line on the label — verify by eye).

Stdlib + Pillow only (PIL reads real image dimensions); the runtime seed
(app/db/seed.py) stays stdlib-only.
"""

from __future__ import annotations

import collections
import csv
import json
import re
from pathlib import Path

from PIL import Image

FIXTURES_DIR = Path(__file__).parent
IMAGES_DIR = FIXTURES_DIR / "images"
CSV_PATH = FIXTURES_DIR / "ground_truth.csv"
SAMPLES = Path(r"C:/alcorn/Treasury/label-samples-complete")

# Canonical Government Warning — 27 CFR 16.21 (exact wording) — the on-label gt_*
# answer key for records that include a back label.
GOV_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth "
    "defects. (2) Consumption of alcoholic beverages impairs your ability to "
    "drive a car or operate machinery, and may cause health problems."
)

# ── CSV contract (identical column order to seed.py) ──────────────────────────
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
    "country_of_origin",
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

_BEV = {
    "DISTILLED SPIRITS": "DISTILLED_SPIRITS",
    "WINE": "WINE",
    "MALT BEVERAGE": "MALT_BEVERAGE",
}
_US_STATES = {
    "NEW YORK",
    "CALIFORNIA",
    "FLORIDA",
    "MARYLAND",
    "MINNESOTA",
    "OREGON",
    "KENTUCKY",
    "TEXAS",
    "WASHINGTON",
    "COLORADO",
    "ILLINOIS",
    "VIRGINIA",
    "MASSACHUSETTS",
    "PENNSYLVANIA",
    "MICHIGAN",
    "OHIO",
    "WISCONSIN",
    "MISSOURI",
    "GEORGIA",
}
_ROLE = {"front": "BRAND", "back": "BACK", "neck": "NECK"}  # everything else → OTHER

_PERMIT_RE = re.compile(r"^([A-Z]{1,4}-[A-Z]?-?\d[\w-]*)\s")


def _iso_date(mdy: str) -> str:
    mdy = (mdy or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", mdy)
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else "2023-01-01"


def _permit_from_applicant(applicant: str) -> str:
    m = _PERMIT_RE.match((applicant or "").strip())
    return m.group(1) if m else ""


def _clean_origin(raw: str) -> str:
    """The filed origin, label-faithful: drop the registry's "(UNION OF)" parenthetical and
    Title-Case ("SCOTLAND" → "Scotland", "SOUTH AFRICA (UNION OF)" → "South Africa")."""
    return re.sub(r"\([^)]*\)", "", raw or "").strip().title()


# ── normalize the REAL form-box values to label-faithful application strings ──
_NET_UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*"
    r"(MILLILITERS?|MILLILITRES?|ML|CENTILITERS?|CL|LITERS?|LITRES?|L|"
    r"FL\.?\s*OZ\.?|FLUID\s*OUNCES?|OUNCES?|OZ|GALLONS?|GAL|PINTS?|QUARTS?)\b",
    re.I,
)
_NET_UNIT_MAP = {
    "MILLILITER": "mL",
    "MILLILITRE": "mL",
    "ML": "mL",
    "CENTILITER": "cL",
    "CL": "cL",
    "LITER": "L",
    "LITRE": "L",
    "L": "L",
    "FLOZ": "fl oz",
    "FLUIDOUNCE": "fl oz",
    "OUNCE": "fl oz",
    "OZ": "fl oz",
    "GALLON": "Gallons",
    "GAL": "Gallons",
    "PINT": "Pint",
    "QUART": "Quart",
}


def _norm_net(raw: str) -> str:
    """Real Box-12 net contents → a label-faithful string ("750 MILLILITERS" → "750 mL",
    "12 FL. OZ." → "12 fl oz"). A keg's multi-size string ("15.5 GAL. (1/2 BBL) …") keeps
    the FIRST (primary) size. Empty when no quantity is present."""
    m = _NET_UNIT_RE.search(raw or "")
    if not m:
        return ""
    unit = re.sub(r"[.\s]", "", m.group(2).upper()).rstrip("S")
    return f"{m.group(1)} {_NET_UNIT_MAP.get(unit, m.group(2))}"


def _norm_abv(raw: str) -> str:
    """Real Box-13 ABV → "<n>% Alc./Vol." ("46" → "46% Alc./Vol.", "43%" → "43% Alc./Vol.").
    Empty in → empty out (malt forms leave box 13 blank ⇒ the engine REVIEWs it)."""
    raw = (raw or "").strip().rstrip("%").strip()
    return f"{raw}% Alc./Vol." if re.search(r"\d", raw) else ""


# TTB classification CODES carry grouping/category words the label never prints
# ("TABLE RED WINE" is just "Red Wine"; "VODKA 80-89 PROOF FB" is "Vodka"). Drop the
# filler so the field-match compares the label-faithful designation, not TTB's code.
_CLASS_FILLER = {"OTHER", "FOREIGN", "TABLE", "FB", "DISTILLED", "PROOF"}


def _clean_class_type(code: str) -> str:
    code = re.sub(r"\([^)]*\)", " ", code or "")  # drop parenthetical "(SLIVOVITZ)"/"(COOKING)"
    code = re.sub(r"/[^/\s]*", " ", code)  # drop slash groups "/PORT" "/SHERRY"
    code = re.sub(r"\b\d[\d-]*\b", " ", code)  # drop proof ranges "80-89"
    words = [w for w in code.upper().split() if w not in _CLASS_FILLER]
    if "FLAVORED" in words:  # TTB lists it trailing; labels lead with it ("Flavored Rum")
        words.remove("FLAVORED")
        words.insert(0, "FLAVORED")
    return " ".join(w.capitalize() for w in words)


# ── per-record overrides (keyed by the harvested ttb_id) ──────────────────────
# net contents + ABV now come REAL from the form, so the override table is small:
# the engineered ABV failure, plus two class/type cleanups the generic cleaner can't
# resolve to a label-faithful form. gt_* set alongside so the benchmark gold matches.
_OVERRIDES: dict[str, dict[str, str]] = {
    "09335001000045": {  # THE PEDDLER — Single Malt Scotch — ENGINEERED ABV FAILURE
        "alcohol_content": "43% Alc./Vol.",  # filed
        "gt_alcohol_content": "46% Alc./Vol.",  # on label (real) → field-match FAILs
        "expected_verdict": "FAIL",
        "violation_kind": "abv_mismatch",
    },
    "08347001000117": {  # HARD ROCK — code "SOUTH AFRICAN GRAPE BRANDY FB" → label "Grape Brandy"
        "class_type_designation": "Grape Brandy",
        "gt_class_type_designation": "Grape Brandy",
    },
    "10364001000042": {  # SAINT PATRICKS BEST (keg) — code "MALT BEVERAGES SPECIAL…" → "Ale"
        "class_type_designation": "Ale",
        "gt_class_type_designation": "Ale",
    },
}

_OV_MIRROR = (
    ("alcohol_content", "gt_alcohol_content"),
    ("net_contents", "gt_net_contents"),
    ("applicant_name_address", "gt_applicant_name_address"),
)


def _apply_overrides(row: dict, ttb_id: str) -> None:
    ov = _OVERRIDES.get(ttb_id)
    if not ov:
        return
    row.update(ov)
    for app_k, gt_k in _OV_MIRROR:
        if app_k in ov and gt_k not in ov:
            row[gt_k] = ov[app_k]


# Cap the longest side so OCR memory stays bounded (real photos spike PaddleOCR's
# detector). ~1400px keeps label text legible. COLA Online enforces a hard 750 KB
# per-image upload limit, so we mirror it exactly — every committed image is ≤750 KB.
_MAX_DIM = 1400
_MAX_BYTES = 750 * 1024


def _copy_image(src: Path, ttb_id: str, position: int, role: str) -> dict:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9]", "", ttb_id)
    filename = f"{safe_id}_{position:02d}_{role}.jpg"
    dest = IMAGES_DIR / filename
    with Image.open(src) as opened:
        im = opened.convert("RGB")
    w, h = im.size
    if max(w, h) > _MAX_DIM:
        scale = _MAX_DIM / max(w, h)
        im = im.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
    for quality in (85, 75, 65, 55, 45):
        im.save(dest, "JPEG", quality=quality)
        if dest.stat().st_size <= _MAX_BYTES:
            break
    while dest.stat().st_size > _MAX_BYTES and min(im.size) > 240:
        im = im.resize((round(im.width * 0.85), round(im.height * 0.85)), Image.Resampling.LANCZOS)
        im.save(dest, "JPEG", quality=45)
    w, h = im.size
    return {
        "role": role,
        "position": position,
        "filename": filename,
        "mime_type": "image/jpeg",
        "width_px": int(w),
        "height_px": int(h),
        "file_size_bytes": dest.stat().st_size,
    }


def _blank_row() -> dict:
    return {c: "" for c in CSV_COLUMNS}


_SELECT_PER_TYPE = 5  # 5 spirits + 5 wine + 5 malt = the harvested real corpus


def _load_sidecars() -> list[dict]:
    out: list[dict] = []
    for f in sorted(SAMPLES.glob("*.json")):
        if f.name.startswith("harvest_metadata"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _build_real_rows() -> tuple[list[dict], set[str]]:
    by_type: dict[str, list] = {}
    for r in _load_sidecars():
        bev = _BEV.get((r.get("product_type") or "").strip().upper())
        if not bev:
            continue
        imgs = [s for s in r.get("images", []) if (SAMPLES / s["file"]).exists()]
        if not imgs:
            continue
        has_back = any(s.get("role", "").lower() == "back" for s in imgs)
        by_type.setdefault(bev, []).append((not has_back, r, imgs))

    selected: list[tuple[bool, dict, list]] = []
    for items in by_type.values():
        items.sort(key=lambda t: t[0])  # prefer records WITH a back label (gov-warning to read)
        selected.extend(items[:_SELECT_PER_TYPE])

    rows: list[dict] = []
    used: set[str] = set()
    for i, (_, r, imgs) in enumerate(selected):
        ttb_id = r["ttb_id"].strip()
        manifest: list[dict] = []
        has_back = False
        for spec in imgs:  # ALL roles — front/back/neck/strip/… (the "all images" goal)
            src = SAMPLES / spec["file"]
            if not src.exists():
                continue
            role = _ROLE.get(spec.get("role", "").lower(), "OTHER")
            try:
                entry = _copy_image(src, ttb_id, len(manifest) + 1, role)
            except Exception as exc:  # noqa: BLE001 — skip an unreadable/corrupt source image
                print(f"  ! skipping unreadable image {src.name}: {exc}")
                continue
            has_back = has_back or role == "BACK"
            used.add(entry["filename"])
            manifest.append(entry)
        if not manifest:
            continue

        origin = (r.get("origin_code") or "").strip().upper()
        net = _norm_net(r.get("net_contents", ""))
        abv = _norm_abv(r.get("alcohol_content", ""))
        bev = _BEV[(r.get("product_type") or "").strip().upper()]
        cls = _clean_class_type(r.get("class_type_code", ""))
        date = _iso_date(r.get("approval_date", ""))

        row = _blank_row()
        row.update(
            ttb_id=ttb_id,
            serial_number=(r.get("serial") or "").strip(),
            beverage_type=bev,
            source_of_product="DOMESTIC" if origin in _US_STATES else "IMPORTED",
            application_type="LABEL_APPROVAL",
            brand_name=(r.get("brand_name") or "").strip(),
            fanciful_name=(r.get("fanciful_name") or "").strip(),
            class_type_designation=cls,
            # name/address blank ⇒ REVIEW: the registry's permit+legal-entity+street line
            # never matches the short bottler line on the label (a formatting artifact).
            applicant_name_address="",
            plant_registry_no=_permit_from_applicant(r.get("applicant_principal", "")),
            alcohol_content=abv,
            net_contents=net,
            country_of_origin=_clean_origin(origin),
            wine_vintage=(r.get("wine_vintage") or "").strip(),
            formula_id=(r.get("formula") or "").strip(),
            phone=(r.get("phone_number") or "").strip(),
            application_date=date,
            submitted_at=f"{date}T12:{i % 60:02d}:00Z",
            scenario="real_cola",
            # Advisory screen on a real APPROVED COLA: the human verifies. Reconciled to
            # the engine's actual outcome after the OCR run.
            expected_verdict="REVIEW",
            violation_kind="none",
            gt_brand_name=(r.get("brand_name") or "").strip(),
            gt_class_type_designation=cls,
            gt_alcohol_content=abv,
            gt_net_contents=net,
            gt_government_warning=GOV_WARNING if has_back else "",
            images=json.dumps(manifest),
        )
        _apply_overrides(row, ttb_id)
        rows.append(row)
    return rows, used


def main() -> None:
    if not SAMPLES.exists() or not _load_sidecars():
        raise SystemExit(
            f"harvested samples not found under: {SAMPLES}\n"
            "(run targetsetup/scripts/cola_harvest.py first)"
        )

    rows, used = _build_real_rows()

    # purge any image not referenced by the new corpus
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    for old in IMAGES_DIR.glob("*.jpg"):
        if old.name not in used:
            old.unlink()

    with CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in CSV_COLUMNS})

    by_type = collections.Counter(r["beverage_type"] for r in rows)
    real_abv = sum(1 for r in rows if r["alcohol_content"])
    print(f"Wrote {len(rows)} real COLA submissions to {CSV_PATH}")
    print(f"  by type: {dict(by_type)}")
    print(f"  with back label: {sum(1 for r in rows if 'BACK' in r['images'])}/{len(rows)}")
    print(f"  with real net contents: {sum(1 for r in rows if r['net_contents'])}/{len(rows)}")
    print(f"  with real ABV: {real_abv}/{len(rows)}")
    print(f"  images in {IMAGES_DIR}: {len(list(IMAGES_DIR.glob('*.jpg')))}")


if __name__ == "__main__":
    main()
