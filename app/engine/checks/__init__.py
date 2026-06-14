"""The check-evaluator dispatch seam (Story 3.2, Task 3).

Mirrors the pipeline's ``run.STAGES`` seam (Story 2.2): a ``{strategy: evaluator}``
registry where each per-strategy evaluator plugs in with **no executor change** —
the whole point of the seam. Stories 3.3–3.7 each register their real evaluator
under their strategy key:

  - ``field_match``        → Story 3.3
  - ``government_warning`` → Story 3.4
  - ``format_checks``      → Story 3.5
  - ``class_type``         → Story 3.6
  - ``flag_only`` / ``positional`` → Story 3.7

In 3.2 there are NO real evaluators — every strategy (registered or not) resolves
to the honest :func:`placeholder_evaluator`, which returns ``REVIEW`` with
``"not yet evaluated by the engine"``. That yields a complete, TRUTHFUL checklist
now (every submission gets one row per Check) without faking PASS/FAIL results.

An unknown/unregistered strategy resolves to the same honest default and NEVER
raises (finalize-don't-abort, FR-9).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from app import verdict

if TYPE_CHECKING:
    from app.db.repositories import Submission
    from app.engine.rulesets import Check

# The per-check verdict domain — the ``checklist_items.verdict`` enum (includes
# NA, unlike the rolled-up submission verdict). ``app/verdict.py`` exposes the
# PASS/REVIEW/FAIL constants and the NA token; we alias the input domain here.
CheckVerdict = Literal["PASS", "REVIEW", "FAIL", "NA"]


@dataclass
class CheckContext:
    """Everything an evaluator needs to judge one Check.

    Bundles the DB connection, the submission, the submission's joined OCR text
    (``repo.get_submission_ocr_text`` — the deterministic engine's input; OCR text
    feeds ONLY the engine, never a model), and the LLM extraction results. A
    ``scratch`` dict carries pipeline artifacts forward (e.g. the LLM stage's
    extraction) without widening this signature as evaluators are added (3.3–3.7).
    """

    conn: Any  # sqlite3.Connection
    submission: Submission
    ocr_text: str = ""
    llm_results: list[Any] = field(default_factory=list)
    scratch: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CheckResult:
    """One evaluator's verdict for one Check.

    ``verdict`` is in the per-check domain (``PASS/REVIEW/FAIL/NA``). ``detail`` is a
    concise advisory string recording the inputs compared / why it flagged
    (provenance — AC3). ``field_comparison_id`` links to a ``field_comparisons`` row
    (Story 3.3). ``model_id`` identifies the model for LLM-assisted checks (AC3) —
    the executor folds it into ``detail`` provenance.
    """

    verdict: CheckVerdict
    detail: str | None = None
    field_comparison_id: int | None = None
    model_id: str | None = None


# An evaluator scores one Check against the context. 3.3–3.7 implement real ones.
Evaluator = Callable[["Check", CheckContext], CheckResult]


def placeholder_evaluator(check: Check, ctx: CheckContext) -> CheckResult:
    """The honest 3.2 default for EVERY strategy: defer to the human (``REVIEW``).

    Returns ``REVIEW`` with an explicit "not yet evaluated" detail — a complete,
    truthful checklist now, never a fabricated PASS/FAIL. Stories 3.3–3.7 replace
    this per-strategy with real logic behind the same seam.
    """
    return CheckResult(verdict=verdict.REVIEW, detail="not yet evaluated by the engine")


# The {strategy: evaluator} registry. Every lookup falls through to the honest
# placeholder default (see `get_evaluator`) for any not-yet-registered strategy.
# Stories 3.3–3.7 register their real evaluator here (one line each), with no
# executor edit. Story 3.3 registers ``field_match`` (see the bottom-of-module
# registration — kept after the definitions to avoid an import cycle).
EVALUATORS: dict[str, Evaluator] = {}


def get_evaluator(strategy: str) -> Evaluator:
    """Resolve a strategy to its evaluator, defaulting to the honest placeholder.

    An unknown/unregistered strategy resolves to :func:`placeholder_evaluator`
    (``REVIEW``) — it NEVER raises (finalize-don't-abort, FR-9). This is what makes
    the seam safe: adding a Check with a not-yet-implemented strategy degrades to a
    truthful REVIEW row instead of crashing the engine stage.
    """
    return EVALUATORS.get(strategy, placeholder_evaluator)


# ── per-strategy registrations (Stories 3.3–3.7) ─────────────────────────────
# Imported AFTER the seam definitions above so the evaluator modules can import
# CheckContext/CheckResult from this package without a cycle. Each module's import
# is the single line that wires its strategy into EVALUATORS.
from app.engine.checks.class_type import class_type as _class_type  # noqa: E402
from app.engine.checks.field_match import field_match as _field_match  # noqa: E402
from app.engine.checks.format_checks import format_checks as _format_checks  # noqa: E402
from app.engine.checks.government_warning import (  # noqa: E402
    government_warning as _government_warning,
)

EVALUATORS["field_match"] = _field_match
EVALUATORS["government_warning"] = _government_warning
EVALUATORS["format_checks"] = _format_checks
EVALUATORS["class_type"] = _class_type
