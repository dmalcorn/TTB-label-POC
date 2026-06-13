"""The ``government_warning`` check evaluator — deterministic, NO model (Story 3.4).

Plugs into the Story-3.2 dispatch seam (``{strategy: evaluator}`` registry in
``app/engine/checks/__init__.py``) under the ``government_warning`` strategy, with
NO executor change. It verifies the warning against §16.21 (the CFR citation lives
in the ruleset DATA, never re-typed here) entirely deterministically — the single
most rule-bound check in the POC.

**NO LLM, by contract (AC1).** The required wording is fixed by regulation, so an
LLM's nondeterminism is a liability here. This module never imports/constructs a
model adapter; it reads ONLY the submission's joined OCR text (the deterministic
engine's input). (project-context: "the Government Warning check NEVER calls an
LLM"; determinism taxonomy.)

**CFR text lives as DATA (AC4).** The §16.21 expected text + formatting rules are
imported from ``app/engine/rulesets/government_warning.py`` — never inlined here. A
grep for the warning text (or the CFR citation literal) inside this logic is a
review finding.

**The three outcomes never conflate (AC3).** The verdict + a JSON ``detail``
payload carry a structural ``outcome`` discriminator so Story 4.5 renders the
right one and never diffs against empty:
  - ``reworded``       — present but reworded/mis-cased/mis-punctuated → **FAIL**
                         with a char-diff (expected vs found).
  - ``absent``         — not present on ANY label → **FAIL** with plain copy, NO diff.
  - ``couldnt_verify`` — a visual-styling attribute (bold) OCR cannot recover →
                         **REVIEW**, never a silent PASS.
  - ``pass``           — exact wording + correct header/Surgeon-General casing → PASS.

**Whitespace-only normalization (deliberate exception).** This check does NOT route
the body through ``app/normalize.py``: that contract casefolds and strips trailing
punctuation, which would destroy the exact-punctuation and casing assertions this
story depends on. A local whitespace-collapse helper is used instead (whitespace
only — punctuation + case preserved for the targeted checks).
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from app import verdict
from app.engine.checks import CheckContext, CheckResult
from app.engine.rulesets import government_warning as data

if TYPE_CHECKING:
    from app.engine.rulesets import Check

# Outcome discriminators encoded in the JSON ``detail`` payload (AC3). Keep these
# structurally distinct so Story 4.5 renders reworded-with-diff vs absent-plain vs
# couldn't-verify — and never shows a diff against empty.
_OUTCOME_PASS = "pass"
_OUTCOME_REWORDED = "reworded"
_OUTCOME_ABSENT = "absent"
_OUTCOME_COULDNT_VERIFY = "couldnt_verify"

# A case-insensitive, whitespace-tolerant matcher for the header token, used ONLY to
# LOCATE the warning (present-vs-absent). Runs of whitespace between the header words
# are collapsed for matching (OCR introduces incidental spaces / line breaks). The
# all-caps requirement is enforced separately on the located text — locating ≠
# accepting. Built from the DATA header so the token is never re-typed here.
_HEADER_LOCATE = re.compile(
    r"\s+".join(re.escape(part) for part in data.HEADER.split()), re.IGNORECASE
)


def government_warning(check: Check, ctx: CheckContext) -> CheckResult:
    """Verify the Government Warning deterministically against §16.21 (AC1–AC3).

    Reads the submission's joined OCR text (``ctx.ocr_text`` — never a model). Locates
    the warning by its header token; produces one of the four structurally-distinct
    outcomes. Writes NO ``field_comparisons`` row (the "expected" side is the statute,
    not an application field — Task 3): provenance travels in the returned result and
    ``run_checks`` writes the single ``checklist_items`` row.
    """
    ocr_text = ctx.ocr_text or ""

    # (1) Locate by the header token (case-insensitive). The warning may appear on more
    # than one label image (the joined OCR text concatenates all of them), and an early
    # occurrence (a stylized front-label tagline, or a reworded draft) must NOT condemn
    # a later compliant one: §16.21 is satisfied if the warning IS present and correct
    # ANYWHERE. So we evaluate EVERY header occurrence and PASS if any is compliant;
    # only when none pass do we report the FIRST occurrence's deviation (the most
    # prominent one). Absent from ALL images ⇒ AC3(b): plain FAIL, NO diff against empty.
    matches = list(_HEADER_LOCATE.finditer(ocr_text))
    if not matches:
        return _fail_absent()

    first_non_pass: CheckResult | None = None
    for match in matches:
        result = _evaluate_occurrence(ctx, ocr_text, match)
        if result.verdict == verdict.PASS:
            return result
        if first_non_pass is None:
            first_non_pass = result
    # No occurrence was compliant — report the first one's deviation (reworded/casing,
    # or a couldn't-verify REVIEW). ``first_non_pass`` is non-None (matches non-empty).
    assert first_non_pass is not None
    return first_non_pass


def _evaluate_occurrence(ctx: CheckContext, ocr_text: str, match: re.Match[str]) -> CheckResult:
    """Judge ONE located ``GOVERNMENT WARNING:`` occurrence → PASS / reworded-FAIL / REVIEW.

    Never returns the ABSENT outcome (that is a whole-text property handled by the
    caller). Drives steps (2)–(6) of the §16.21 verification against the single span
    starting at ``match``."""
    # The located warning region: from the header to the end of the matched block. We
    # take the text from the header onward and collapse whitespace for comparison.
    located = ocr_text[match.start() :]
    header_found = ocr_text[match.start() : match.end()]

    # (2) Header caps check — the located header must be ALL-CAPS. Compare after
    # whitespace-collapse so incidental OCR spacing inside the token is ignored while
    # CASING is enforced exactly: a title-case ``Government Warning:`` is present-but-
    # deviant ⇒ reworded FAIL (header casing).
    collapsed_header = _collapse_ws(header_found)
    if collapsed_header != data.HEADER:
        return _fail_reworded(
            located,
            deviation=f"header casing: expected {data.HEADER!r}, found {collapsed_header!r}",
        )

    # (3) Body wording check — collapse whitespace, compare case-INSENSITIVELY against
    # the §16.21 expected body, requiring exact wording + punctuation (incl. (1)/(2)).
    # The located region may carry trailing label copy AFTER the warning, so the body
    # is compliant when the expected body is an exact case-insensitive PREFIX of it.
    found_body = _collapse_ws(located[len(header_found) :])
    expected_body = _collapse_ws(data.BODY)
    if not _body_matches(found_body, expected_body):
        return _fail_reworded(located, deviation="body wording / punctuation deviates")

    # The matched warning body span (excludes any trailing label copy) — the window the
    # casing check inspects.
    matched_body = found_body[: len(expected_body)]

    # (4) Surgeon General casing — §5.2: the ``S`` in "Surgeon" and the ``G`` in
    # "General" must be CAPITAL. An all-caps body trivially satisfies this (the letters
    # ARE capital), so the rule only bites a MIXED-CASE body. We enforce the specific
    # INITIAL LETTER positionally (not a mixed-case whole-word substring match): the
    # only violation is a lowercase ``s``/``g`` — an over-capitalized "GENERAL" still
    # has a capital G and is compliant. (Body wording already matched case-insensitively,
    # so each word is present; we check only the casing of its first letter.)
    if not _is_all_caps(matched_body):
        for word in data.RULES.mixed_case_capitals:
            if not _initial_is_capital(matched_body, word):
                return _fail_reworded(located, deviation=f"casing: {word!r} must be capitalized")

    # (5) Bold/visual styling undeterminable ⇒ AC3(c): REVIEW, never a silent PASS.
    # Bold cannot be recovered from OCR text; when a caller signals it could not be
    # confirmed, defer to the human rather than pass-or-fail on a visual attribute.
    if data.RULES.bold_required_but_unverifiable and _bold_undeterminable(ctx):
        return _review_couldnt_verify()

    # (6) Exact wording + correct casing ⇒ PASS.
    return CheckResult(
        verdict=verdict.PASS,
        detail=json.dumps({"outcome": _OUTCOME_PASS, "cfr_citation": data.CFR_CITATION}),
    )


# ── outcome builders (each encodes its discriminator) ────────────────────────


def _fail_absent() -> CheckResult:
    """AC3(b): warning not found on any label — plain copy, NO diff against empty."""
    payload = {
        "outcome": _OUTCOME_ABSENT,
        "message": "Government Warning not found on any label",
        "cfr_citation": data.CFR_CITATION,
    }
    return CheckResult(verdict=verdict.FAIL, detail=json.dumps(payload))


def _fail_reworded(located: str, *, deviation: str) -> CheckResult:
    """AC3(a): present but wrong — FAIL carrying a char-diff vs the §16.21 expected text.

    Diffs the located (whitespace-collapsed) warning against the canonical
    ``data.FULL_TEXT`` so Story 4.5 can render the precise deviation + its text
    equivalent. ``deviation`` is a short human label of what differs."""
    found = _collapse_ws(located)
    expected = _collapse_ws(data.FULL_TEXT)
    payload = {
        "outcome": _OUTCOME_REWORDED,
        "deviation": deviation,
        "expected": expected,
        "found": found,
        "diff": _char_diff(expected, found),
        "cfr_citation": data.CFR_CITATION,
    }
    return CheckResult(verdict=verdict.FAIL, detail=json.dumps(payload))


def _review_couldnt_verify() -> CheckResult:
    """AC3(c): bold/visual styling OCR cannot recover ⇒ REVIEW, never a silent PASS."""
    payload = {
        "outcome": _OUTCOME_COULDNT_VERIFY,
        "message": "couldn't verify bold/visual styling from a photo",
        "cfr_citation": data.CFR_CITATION,
    }
    return CheckResult(verdict=verdict.REVIEW, detail=json.dumps(payload))


# ── helpers (whitespace-only normalization; punctuation + case preserved) ────


def _collapse_ws(text: str) -> str:
    """Collapse runs of whitespace (spaces / line breaks) to a single space and trim.

    Whitespace-ONLY — punctuation and case are preserved (the deliberate exception to
    ``app/normalize.py``; see the module docstring)."""
    return re.sub(r"\s+", " ", text).strip()


def _is_all_caps(text: str) -> bool:
    """True when the text has at least one cased letter and NO lowercase letter.

    An all-caps body is compliant (AC1) and trivially satisfies the Surgeon/General
    capital rule, so the S/G check is skipped for it."""
    return any(c.isalpha() for c in text) and not any(c.islower() for c in text)


def _initial_is_capital(body: str, word: str) -> bool:
    """Whether the regulated ``word`` appears in ``body`` with a CAPITAL initial (§5.2).

    Locates ``word`` case-insensitively (the body already matched §16.21 wording case-
    insensitively, so it IS present) and asserts the FIRST letter of the located
    occurrence is uppercase. This enforces only the ``S``/``G`` capitalization rule: a
    lowercase ``surgeon``/``general`` fails; a correctly- OR over-capitalized rendering
    (``Surgeon``, ``SURGEON``) passes. If the word is somehow not found, treat it as a
    casing failure (conservative — the wording check should have caught a true absence)."""
    idx = body.casefold().find(word.casefold())
    if idx == -1:
        return False
    return body[idx].isupper()


def _body_matches(found_body: str, expected_body: str) -> bool:
    """Whether the located body carries the §16.21 wording exactly (case-insensitive).

    Compliant when the whitespace-collapsed expected body is an exact case-insensitive
    PREFIX of the found body — so a correct warning followed by trailing label copy
    still matches, while any reworded/mis-punctuated/omitted wording does not. Exact
    wording + punctuation (incl. the (1)/(2) markers) is required; only case and
    incidental whitespace are normalized away (AC1/AC2)."""
    head = found_body[: len(expected_body)]
    return head.casefold() == expected_body.casefold()


def _char_diff(expected: str, found: str) -> list[tuple[str, str]]:
    """A compact char-level diff (stdlib ``difflib`` — no new dependency).

    Returns a list of ``(op, segment)`` opcodes (``equal``/``replace``/``delete``/
    ``insert``) over expected→found so Story 4.5 can render the visual char-diff AND a
    forced-colors-safe text equivalent. 3.4 produces the DATA; 4.5 renders it."""
    sm = SequenceMatcher(None, expected, found, autojunk=False)
    out: list[tuple[str, str]] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append(("equal", expected[i1:i2]))
        elif op == "delete":
            out.append(("delete", expected[i1:i2]))
        elif op == "insert":
            out.append(("insert", found[j1:j2]))
        else:  # replace
            out.append(("replace", f"{expected[i1:i2]}\u2192{found[j1:j2]}"))
    return out


def _bold_undeterminable(ctx: CheckContext) -> bool:
    """Whether the caller flagged the warning's bold/visual styling as unconfirmable.

    Bold is a visual attribute OCR cannot recover from a photo. The pipeline forward-
    seam (``ctx.scratch``) may carry a ``bold_undeterminable`` signal; absent it,
    default to False so a clean, exactly-worded warning PASSes (the styling caveat is a
    documented limitation, not a blanket REVIEW). When True ⇒ AC3(c) REVIEW."""
    scratch = ctx.scratch if isinstance(ctx.scratch, dict) else {}
    return bool(scratch.get("bold_undeterminable"))
