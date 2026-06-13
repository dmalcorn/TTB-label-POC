"""Centralized verdict roll-up — ``rollup(verdicts)`` (Story 3.1, AC2/AC4).

Pins the severity precedence (any FAIL ⇒ FAIL; else any REVIEW ⇒ REVIEW; else
PASS), the ``NA`` exclusion, the empty / all-``NA`` ⇒ ``REVIEW`` default
(ambiguity defers to human, never a silent auto-PASS), and the engine-vs-human
firewall: ``verdict.py`` imports no ``disposition`` and emits no
``verdict → disposition`` mapping. Pure in-memory: zero I/O, zero DB.
"""

from __future__ import annotations

import app.verdict as verdict_module
from app.verdict import FAIL, NA, PASS, REVIEW, rollup

# ── AC2: severity precedence (most-severe wins) ──────────────────────────────


def test_any_fail_wins_over_everything():
    assert rollup(["PASS", "REVIEW", "FAIL", "NA"]) == "FAIL"
    assert rollup(["FAIL"]) == "FAIL"
    assert rollup(["FAIL", "PASS"]) == "FAIL"


def test_review_wins_when_no_fail():
    assert rollup(["PASS", "REVIEW", "PASS"]) == "REVIEW"
    assert rollup(["REVIEW"]) == "REVIEW"
    assert rollup(["REVIEW", "NA", "PASS"]) == "REVIEW"


def test_all_pass_is_pass():
    assert rollup(["PASS", "PASS", "PASS"]) == "PASS"
    assert rollup(["PASS"]) == "PASS"


# ── NA exclusion + the can't-verify-as-REVIEW domain ─────────────────────────


def test_na_is_excluded_and_never_propagates():
    # NA mixed with PASS must roll up to PASS — NA is filtered before scanning.
    assert rollup(["PASS", "NA", "PASS"]) == "PASS"
    assert rollup(["NA", "FAIL"]) == "FAIL"


# ── Empty / all-NA ⇒ REVIEW (defer to human, never silent auto-PASS) ──────────


def test_empty_rolls_up_to_review():
    assert rollup([]) == "REVIEW"


def test_all_na_rolls_up_to_review():
    assert rollup(["NA"]) == "REVIEW"
    assert rollup(["NA", "NA", "NA"]) == "REVIEW"


# ── fail-safe: unknown / malformed tokens defer to REVIEW, never PASS ─────────


def test_unknown_token_defers_to_review_not_pass():
    # A token outside the legal enum (writer bug, future value, empty cell) must
    # NOT silently auto-PASS — it folds to REVIEW (ambiguity → human).
    assert rollup(["ERROR"]) == "REVIEW"
    assert rollup([""]) == "REVIEW"
    assert rollup(["PASS", "WONKY"]) == "REVIEW"


def test_wrong_case_token_defers_to_review_not_pass():
    # Wrong-case "fail"/"na" must never downgrade severity to PASS.
    assert rollup(["fail"]) == "REVIEW"
    assert rollup([" FAIL"]) == "REVIEW"
    assert rollup(["na"]) == "REVIEW"


def test_real_fail_still_wins_over_unknown_tokens():
    # An exact FAIL still dominates, even mixed with unknown tokens.
    assert rollup(["ERROR", "FAIL"]) == "FAIL"


# ── order-independence / idempotence ─────────────────────────────────────────


def test_order_independent():
    assert rollup(["REVIEW", "FAIL", "PASS"]) == rollup(["PASS", "REVIEW", "FAIL"])
    assert rollup(["PASS", "REVIEW"]) == rollup(["REVIEW", "PASS"])


def test_rollup_output_is_idempotent():
    once = rollup(["PASS", "REVIEW", "FAIL"])
    assert rollup([once]) == once


def test_rollup_accepts_any_iterable():
    # A generator (single-pass iterable) must work — not just a list.
    assert rollup(v for v in ["PASS", "FAIL"]) == "FAIL"


# ── greppable constants match the DB CHECK enums exactly ─────────────────────


def test_module_constants_are_upper_snake_literals():
    assert PASS == "PASS"
    assert REVIEW == "REVIEW"
    assert FAIL == "FAIL"
    assert NA == "NA"


# ── AC4: engine-vs-human firewall — no disposition coupling ───────────────────


def test_verdict_module_does_not_import_disposition():
    # Structural enforcement of "Recommend, don't decide": verdict.py must not
    # IMPORT disposition.py and must contain no verdict → disposition mapping.
    # (The docstring may *name* disposition to document the firewall — what's
    # forbidden is an import and the human enum values appearing as code.)
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(verdict_module))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    assert not any("disposition" in m for m in imported_modules)

    # No human disposition enum value may appear as a string literal (a mapping
    # target would have to materialize one of these).
    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    for human_term in ("APPROVED", "NEEDS_CORRECTION", "REJECTED"):
        assert human_term not in string_literals
