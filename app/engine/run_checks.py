"""The compliance-engine executor + its pipeline stage (Story 3.2, AC2/AC3/AC5).

:func:`run_checks` loads a submission's ruleset (``get_ruleset`` — rulesets-as-
DATA), dispatches each :class:`~app.engine.rulesets.Check` to its evaluator (the
``{strategy: evaluator}`` seam in ``app/engine/checks``), writes **one
``checklist_items`` row per Check** carrying the Check's provenance verbatim
(``check_key``/``label``/``cfr_citation``/``check_type`` — never recomputed) plus
the per-check verdict + an advisory ``detail``, then rolls the per-check verdicts
up via the centralized ``app/verdict.py:rollup`` (Story 3.1) and persists the
submission's advisory ``engine_verdict``.

**Recommend, don't decide.** This module imports ``verdict`` but NEVER
``disposition``; there is no ``verdict → disposition`` mapping anywhere. The
rolled-up ``engine_verdict`` is advisory only.

**CFR citations as data (AC4).** No CFR citation literal lives here — every
citation written to a ``checklist_items`` row is read off the ruleset ``Check``.

**Empty/all-NA ruleset ⇒ REVIEW.** A submission whose ruleset is empty (WINE/MALT
until Story 3.8) or whose checks are all ``NA`` rolls up to ``REVIEW`` via
``rollup``'s empty-policy — never a silent auto-PASS.

:func:`engine_stage` wires the executor into ``run.STAGES`` as the LAST stage
(after preprocess/ocr/llm), all background pre-compute — the engine NEVER runs on
a ``GET`` read path (the 5s contract).
"""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

from app import verdict
from app.db import repositories as repo
from app.engine.checks import CheckContext, CheckResult, get_evaluator
from app.engine.rulesets import Check, get_ruleset

if TYPE_CHECKING:  # avoid a run.py ↔ engine import cycle (run imports engine_stage)
    from app.pipeline.run import StageContext

logger = logging.getLogger(__name__)


def _evaluate(check: Check, ctx: CheckContext) -> CheckResult:
    """Dispatch one Check to its evaluator, downgrading any escaping exception to a
    truthful ``REVIEW`` result.

    Evaluators are expected to self-guard, but this is defensive depth: one
    misbehaving evaluator must not abort the whole checklist (finalize-don't-abort,
    FR-9) — the Check still gets an honest REVIEW row.
    """
    evaluator = get_evaluator(check.strategy)
    try:
        return evaluator(check, ctx)
    except Exception as exc:  # noqa: BLE001 — degrade to REVIEW, never abort the run
        logger.exception("Evaluator for check %s raised; defaulting to REVIEW", check.check_key)
        return CheckResult(verdict=verdict.REVIEW, detail=f"evaluator error: {type(exc).__name__}")


def _detail_with_provenance(result: CheckResult) -> str | None:
    """Fold the model identification into ``detail`` for LLM-assisted checks (AC3).

    The compared inputs already live in ``result.detail`` (the evaluator's job); for
    a model-assisted check we additionally record the model id so the provenance is
    complete and traceable. Never logs or stores secrets.
    """
    if result.model_id:
        base = result.detail or ""
        suffix = f"model={result.model_id}"
        return f"{base} | {suffix}".strip(" |") if base else suffix
    return result.detail


def run_checks(conn: sqlite3.Connection, submission: repo.Submission) -> str:
    """Execute a submission's ruleset into a checklist + rolled-up engine verdict.

    Loads ``get_ruleset(submission.beverage_type)``; for each Check, dispatches to
    its evaluator and writes one ``checklist_items`` row with full provenance; then
    rolls the per-check verdicts up via ``verdict.rollup`` and persists
    ``engine_verdict``. Returns the rolled-up verdict.

    Idempotent: prior ``checklist_items`` rows for the submission are cleared first
    (delete-then-insert) so re-processing (a re-sweep / reset) does not duplicate
    rows. The caller (the engine stage) owns the commit.
    """
    submission_id = submission.id
    ruleset = get_ruleset(submission.beverage_type)

    # delete-then-insert idempotency: a re-run replaces the checklist, never appends.
    repo.delete_checklist_items(conn, submission_id)

    # The deterministic engine's input is the submission's joined OCR text — read it
    # ONCE and share it across evaluators. OCR text feeds ONLY the engine (never a
    # model). LLM extraction results are passed for the hybrid class/type check (3.6).
    ctx = CheckContext(
        conn=conn,
        submission=submission,
        ocr_text=repo.get_submission_ocr_text(conn, submission_id),
        llm_results=[],
    )

    per_check_verdicts: list[str] = []
    for check in ruleset:
        result = _evaluate(check, ctx)
        per_check_verdicts.append(result.verdict)
        repo.insert_checklist_item(
            conn,
            submission_id,
            check_key=check.check_key,
            label=check.label,
            cfr_citation=check.cfr_citation,  # citation as DATA (AC4) — off the Check
            check_type=check.check_type,  # determinism class as DATA — off the Check
            verdict=result.verdict,
            detail=_detail_with_provenance(result),
            field_comparison_id=result.field_comparison_id,
        )

    # The SINGLE centralized roll-up (Story 3.1). Empty/all-NA ⇒ REVIEW (its policy).
    rolled = verdict.rollup(per_check_verdicts)
    repo.set_engine_verdict(conn, submission_id, rolled)
    return rolled


def engine_stage(ctx: StageContext) -> None:
    """Pipeline stage (Story 3.2, AC5): run the compliance engine over the submission.

    Registered LAST in ``run.STAGES`` (after preprocess/ocr/llm). Executes
    :func:`run_checks` so every submission reaching ``READY_FOR_REVIEW`` carries a
    complete, explainable checklist and a non-NULL ``engine_verdict``. Self-guards
    (the orchestrator also wraps it) so an engine failure is recorded honestly and
    the submission still finalizes (FR-9). Commits once at the end (commit-per-stage).
    """
    try:
        run_checks(ctx.conn, ctx.submission)
        ctx.conn.commit()
    except Exception:  # noqa: BLE001 — record honestly, never abort the submission
        # ``run_checks`` is a delete-then-insert unit of work with NO commit inside,
        # so a mid-way failure (a CHECK-violating evaluator return ⇒ IntegrityError,
        # or any non-DB error) leaves the DELETE + partial INSERTs PENDING on the
        # connection. We MUST roll those back here: the very next pipeline step
        # (``status.record_event``) commits the connection, which would otherwise
        # FLUSH the partial transaction — wiping the prior checklist and persisting
        # an incomplete one with a stale ``engine_verdict``. Rolling back keeps the
        # submission's last good checklist intact; the checklist is lost for THIS
        # run, not corrupted. Catch broadly (not just ``sqlite3.Error``) so a
        # non-DB failure cannot escape to ``run.py`` and trigger that same flush.
        ctx.conn.rollback()
        logger.exception("Engine stage failed to persist for submission %s", ctx.submission.id)
