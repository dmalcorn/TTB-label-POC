"""Demo-operations orchestration (Story 6.1) — the reset that re-arms the demo.

``reset(settings)`` restores the demo to its seeded, fully-pending state so the
evaluator can re-run it indefinitely (FR-27, AR-12). It does TWO things, in order:

1. **DB re-seed (the atomic unit, AC-1).** Calls Story 1.3's transactional
   :func:`app.db.seed.seed` — one ``BEGIN…COMMIT`` that ``DELETE``s all
   ``submissions`` (the FK ``ON DELETE CASCADE`` clears ``label_images`` /
   ``ocr_results`` / ``llm_results`` / ``field_comparisons`` / ``checklist_items``
   / ``audit_events`` / ``review_progress``) then reloads the fixture corpus at
   ``status='RECEIVED'``. Because every row returns at ``RECEIVED``, the
   cross-column CHECK guarantees the decision columns (``disposition`` /
   ``decided_at`` / ``decision_notes``) and ``engine_verdict`` are NULL — no
   column surgery is needed. The wipe is the clear. We do NOT re-implement it.

2. **Generated-images purge (best-effort cleanup, AC-2).** Empties the derived
   OpenCV-variants root (:attr:`Settings.generated_images_dir`) so the now-orphaned
   ``*__enhanced.png`` / ``*__binarized.png`` files do not accumulate across resets.

The DB commit is the success boundary: the re-seed is the authoritative state and
must be atomic; the FS purge is a follow-on. A purge failure must NOT corrupt the
already-committed re-seed, so it is swallowed + logged — mirroring the boot-degraded
posture of ``_seed_if_empty`` in ``app/main.py``. This is 100% local work (a DB
transaction + a local FS purge): zero egress, so ``docker run --network none``
serves ``/reset`` fully (NFR-2). The read-only seeded fixtures under
``fixtures/images/`` (baked into the image) are NEVER touched — only the derived
root, whose path comes from ``settings`` (no user input, no traversal surface).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.config import Settings
from app.db.seed import seed

logger = logging.getLogger(__name__)

# Repo root (``app/web/ops.py`` → parents[2]) and the read-only, baked-in fixtures
# tree. The derived-images purge must NEVER resolve to one of these (or an ancestor
# of them): AC-2 binds that ``fixtures/images/`` is never touched. The default
# ``generated_images_dir`` honors this, but ``GENERATED_IMAGES_DIR`` is operator
# env — a misconfig (``.``, the WORKDIR, a parent of ``fixtures/``) must be refused,
# not silently ``rmtree``'d.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES_DIR = _REPO_ROOT / "fixtures"
_PROTECTED_ROOTS = frozenset({_REPO_ROOT, _FIXTURES_DIR, _FIXTURES_DIR / "images"})


def purge_generated_images(generated_images_dir: str | Path) -> None:
    """Empty the derived generated-images root, then re-create it empty.

    Deletes the directory tree and re-creates the bare root so the next pipeline
    sweep can write variants into it without a ``mkdir`` race. A missing root is a
    no-op (a fresh demo that never preprocessed anything) — never an error. Only
    the **derived** root passed here is touched; ``fixtures/images/`` is never
    referenced. The caller passes ``settings.generated_images_dir`` — never a
    *request*-supplied path — but ``GENERATED_IMAGES_DIR`` IS operator env, so a
    path-safety guard refuses any root that is the repo root, the read-only
    ``fixtures/`` tree, or an ancestor of either (AC-2: fixtures NEVER touched).
    """
    root = Path(generated_images_dir)
    resolved = root.resolve()
    # Refuse to purge the repo root, the baked-in fixtures, or any ancestor of
    # them (an ancestor's rmtree would take fixtures/source with it). A misconfig
    # is logged and skipped, never destructive.
    if any(resolved == p or resolved in p.parents for p in _PROTECTED_ROOTS):
        logger.error(
            "Refusing to purge generated-images root %r: it resolves to or above a "
            "protected path (repo root / fixtures). Check GENERATED_IMAGES_DIR.",
            str(root),
        )
        return
    if not resolved.exists():
        return  # nothing derived yet — clean reset, no error
    if not resolved.is_dir():
        # A stray file where the dir was expected: remove it so the next sweep's
        # mkdir succeeds, rather than letting rmtree raise on a non-directory.
        resolved.unlink()
        resolved.mkdir(parents=True, exist_ok=True)
        return
    shutil.rmtree(resolved, ignore_errors=False)
    resolved.mkdir(parents=True, exist_ok=True)


def reset(settings: Settings) -> int:
    """Restore the demo to its seeded state: transactional DB re-seed + FS purge.

    Returns the re-seeded submission count. The DB re-seed (atomic, rollback on
    failure) is the success boundary; the generated-images purge is a best-effort
    follow-on whose failure is logged and swallowed so it can never corrupt the
    already-committed corpus.
    """
    count = seed(settings.database_path)
    try:
        purge_generated_images(settings.generated_images_dir)
    except Exception:
        # The corpus is already consistent (committed) — the DB commit is the
        # success boundary. ANY failure to clean the best-effort derived-images
        # root must not undo the reset nor 500 a committed re-seed (e.g. an
        # `sqlite3`-unrelated `OSError`, a stale-FS race, or a `shutil` edge):
        # log and continue, matching the boot-degraded posture of `_seed_if_empty`.
        logger.exception(
            "Reset re-seeded the corpus but could not purge the generated-images "
            "root %r; the demo is restored, orphaned derived variants remain.",
            settings.generated_images_dir,
        )
    return count
