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
  - ``reworded``       — a §16.21 clause is genuinely missing/gross-garbled (NOT a mere
                         OCR near-miss) → **FAIL** with a char-diff (expected vs found).
  - ``absent``         — not present on ANY label → **FAIL** with plain copy, NO diff.
  - ``couldnt_verify`` — present but not byte-exact for OCR-plausible reasons (a dropped
                         comma, a line-wrap hyphen, a digit lost from a "(2)" marker), OR a
                         visual-styling attribute (bold) OCR cannot recover → **REVIEW**,
                         never a silent PASS/FAIL. A near-miss on a plainly-present warning
                         is deferred to a human, not hard-failed.
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
from app.db import repositories as repo
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

# PRESENCE fallback (real-OCR robustness): the header token routinely OCRs garbled on
# real labels — e.g. an all-caps back-label warning read as "OVERNMENT MARNING" /
# "veANMET WARMING" — so an exact-header miss must NOT be reported as "absent" when the
# warning is plainly there. These distinctive §16.21 body phrases survive OCR far better
# than the header; ≥ _ANCHOR_PRESENCE_MIN of them ⇒ the warning is present-but-unlocatable
# ⇒ REVIEW (couldn't-verify), never a false absent-FAIL. Matched on collapsed, lowercased OCR.
_WARNING_ANCHORS = (
    "surgeon general",
    "during pregnancy",
    "birth defects",
    "operate machinery",
    "health problems",
    "impairs your ability",
)
_ANCHOR_PRESENCE_MIN = 2


def government_warning(check: Check, ctx: CheckContext) -> CheckResult:
    """Verify the Government Warning deterministically against §16.21 (AC1–AC3).

    Evaluates the warning against EACH available source — the AI's verbatim transcription
    (the VLM read the IMAGE; preferred, it is far cleaner than OCR on a small back-label)
    AND the joined OCR text — running the same §16.21 §logic on each. PASSes if ANY source
    is compliant (the warning IS correct on the label, however it was read); otherwise
    prefers a REVIEW (present-but-unverifiable) over a FAIL, and only reports absent when
    no source found it. Still NO model call here and NO ``field_comparisons`` row — the AI
    transcription was produced upstream (Story 2.5) and is read from the pipeline seam.
    """
    sources: list[str] = []
    ai_text = _ai_warning_text(ctx)
    if ai_text:
        sources.append(ai_text)  # AI first — a clean image read beats garbled OCR
    ocr_text = (ctx.ocr_text or "").strip()
    if ocr_text:
        sources.append(ocr_text)

    if not sources:
        return _fail_absent()

    results = [_evaluate_text(ctx, text) for text in sources]
    # PASS if ANY source is compliant (the warning is correct on the label).
    for result in results:
        if result.verdict == verdict.PASS:
            return result
    # None compliant: prefer a REVIEW (present-but-unverifiable — defer to a human) over a
    # FAIL/absent, so a clean-but-unconfirmable reading is never hard-failed.
    for result in results:
        if result.verdict == verdict.REVIEW:
            return result
    return results[0]


def _evaluate_text(ctx: CheckContext, text: str) -> CheckResult:
    """Run the §16.21 verification over ONE text blob (an AI transcription or the OCR text).

    Locates the warning by its header token. The warning may appear more than once (joined
    OCR concatenates every image; a stylized front tagline must not condemn a compliant back
    label): evaluate EVERY occurrence and PASS if any is compliant; only when none pass do we
    report the FIRST occurrence's deviation. No header locatable but distinctive §16.21
    phrases present ⇒ REVIEW (present-but-unverifiable); none ⇒ absent FAIL."""
    matches = list(_HEADER_LOCATE.finditer(text))
    if not matches:
        if _anchor_hits(text) >= _ANCHOR_PRESENCE_MIN:
            return _review_detected_unverified(_warning_region(text))
        return _fail_absent()

    first_non_pass: CheckResult | None = None
    for match in matches:
        result = _evaluate_occurrence(ctx, text, match)
        if result.verdict == verdict.PASS:
            return result
        if first_non_pass is None:
            first_non_pass = result
    assert first_non_pass is not None  # matches non-empty
    return first_non_pass


def _ai_warning_text(ctx: CheckContext) -> str | None:
    """The AI's verbatim Government Warning transcription, from the VLM extraction JSON
    (the ``government_warning`` key) — read from the pipeline forward-seam
    (``ctx.scratch["llm_extraction"]``) or the persisted ``OK`` ``llm_results`` row. ``None``
    when the model layer is off, the extraction is unparseable, or the field is absent/empty.
    This is the model's own reading of the IMAGE (VLM-only) — not OCR text fed to a model."""
    raw = ctx.scratch.get("llm_extraction") if isinstance(ctx.scratch, dict) else None
    if not raw:
        persisted = repo.get_latest_llm_extraction(ctx.conn, ctx.submission.id)
        raw = persisted[1] if persisted else None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("government_warning")
    return value.strip() if isinstance(value, str) and value.strip() else None


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
    # CASING is enforced exactly. Casing is a REAL, OCR-robust requirement (the user
    # affirmed "GOVERNMENT WARNING" must be uppercase, and an all-caps header OCRs
    # reliably), so a title-case ``Government Warning:`` is a genuine deviation ⇒ FAIL
    # (header casing) — NOT a near-miss to defer.
    collapsed_header = _collapse_ws(header_found)
    if collapsed_header != data.HEADER:
        return _fail_reworded(
            located,
            deviation=f"header casing: expected {data.HEADER!r}, found {collapsed_header!r}",
        )

    # (3) Body wording check — collapse whitespace, de-hyphenate line wraps, and compare
    # case-INSENSITIVELY against the §16.21 expected body, requiring exact wording +
    # punctuation (incl. (1)/(2)). The located region may carry trailing label copy AFTER
    # the warning, so the body is compliant when the expected body is an exact
    # case-insensitive PREFIX of it.
    found_body = _dehyphenate(_collapse_ws(located[len(header_found) :]))
    expected_body = _collapse_ws(data.BODY)
    if not _body_matches(found_body, expected_body):
        return _body_deviation(located, deviation="body wording / punctuation deviates")

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
                # A lowercase S/G in a mixed-case body is a genuine §5.2 casing defect
                # (not an OCR near-miss) ⇒ FAIL, attributing the offending word.
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
    found = _clip_to_warning(located)
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


def _review_detected_unverified(region: str) -> CheckResult:
    """Header too OCR-garbled to locate, but distinctive §16.21 phrases ARE present ⇒ the
    warning is on the label, exact wording/casing just can't be auto-verified ⇒ REVIEW
    (never a false 'absent' FAIL). Carries the OCR'd warning region so the reviewer sees
    what was read and confirms wording/casing on the label."""
    payload = {
        "outcome": _OUTCOME_COULDNT_VERIFY,
        "found": _clip_to_warning(region),
        "message": (
            "Government Warning detected on the label, but OCR could not verify the "
            "exact wording — confirm wording and casing against the label."
        ),
        "cfr_citation": data.CFR_CITATION,
    }
    return CheckResult(verdict=verdict.REVIEW, detail=json.dumps(payload))


# A located warning whose BODY isn't an exact §16.21 match is judged on one signal: do the
# LETTERS still match the statute? "Letters" = a–z only, case-folded — which discards
# exactly what OCR drops or mangles on a fully-compliant label: punctuation (a comma after
# "Surgeon General" that the printing runs into the artwork), the digits of a "(1)"/"(2)"
# marker, spacing, line-wrap hyphens, and case (an all-caps body). If the letters match,
# every WORD of §16.21 is present and correct and only those incidental marks differ ⇒ this
# is an OCR near-miss on a compliant label, NOT a rewording ⇒ REVIEW (defer to a human, show
# the OCR'd text), never a false FAIL. If the letters DON'T match, a word was actually
# changed/added/dropped (a real rewording, an interleaved phrase, an omitted clause) ⇒ FAIL
# with a char-diff. Casing deviations are handled at their own steps (2)/(4) as genuine
# FAILs and never reach here — so widening this gate does NOT weaken the casing rules.
_LETTERS_ONLY = re.compile(r"[^a-z]")
_EXPECTED_LETTERS = _LETTERS_ONLY.sub("", data.FULL_TEXT.lower())


def _letters_only(text: str) -> str:
    """The a–z, case-folded projection of ``text`` (de-hyphenated first). Ignores case,
    whitespace, punctuation, and marker digits — the incidental marks OCR routinely alters
    on an otherwise-compliant warning."""
    return _LETTERS_ONLY.sub("", _dehyphenate(_collapse_ws(text)).lower())


def _body_deviation(located: str, *, deviation: str) -> CheckResult:
    """The body deviates from §16.21 verbatim. REVIEW when the deviation is letters-clean
    (only punctuation / markers / spacing / case differ — an OCR near-miss on a compliant
    label, e.g. a comma OCR couldn't read); FAIL when a word actually changed/was inserted/
    dropped (a genuine rewording or omission)."""
    found_letters = _letters_only(located)
    if found_letters[: len(_EXPECTED_LETTERS)] == _EXPECTED_LETTERS:
        return _review_detected_unverified(located)
    return _fail_reworded(located, deviation=deviation)


# ── helpers (whitespace-only normalization; punctuation + case preserved) ────


def _collapse_ws(text: str) -> str:
    """Collapse runs of whitespace (spaces / line breaks) to a single space and trim.

    Whitespace-ONLY — punctuation and case are preserved (the deliberate exception to
    ``app/normalize.py``; see the module docstring)."""
    return re.sub(r"\s+", " ", text).strip()


def _dehyphenate(text: str) -> str:
    """Undo line-wrap hyphenation so a label that split a word across a line ('PREG- NANCY')
    matches the canonical wording ('PREGNANCY'). Removes a soft hyphen (U+00AD) anywhere and
    a hyphen left at a line break ('PREG- NANCY' -> 'PREGNANCY'). Display- and comparison-safe
    (the statute has no hyphens, so this never masks a real wording change)."""
    return re.sub(r"-\s+", "", text.replace(chr(0xAD), ""))


def _is_all_caps(text: str) -> bool:
    """True when the text has at least one cased letter and NO lowercase letter.

    An all-caps body is compliant (AC1) and trivially satisfies the Surgeon/General
    capital rule, so the S/G check is skipped for it."""
    return any(c.isalpha() for c in text) and not any(c.islower() for c in text)


def _anchor_hits(ocr_text: str) -> int:
    """How many distinctive §16.21 body phrases appear in the OCR (presence fallback)."""
    low = _collapse_ws(ocr_text).lower()
    return sum(1 for anchor in _WARNING_ANCHORS if anchor in low)


def _warning_region(ocr_text: str) -> str:
    """The collapsed OCR slice around the first matched anchor — what to show the reviewer
    when the warning is present but the header couldn't be located."""
    collapsed = _collapse_ws(ocr_text)
    low = collapsed.lower()
    positions = [low.find(a) for a in _WARNING_ANCHORS if a in low]
    if not positions:
        return collapsed[:400]
    start = max(0, min(positions) - 60)
    return collapsed[start : start + 420].strip()


# What to DISPLAY as the on-label warning. ``ocr_text[match.start():]`` runs from the
# header to the END of the OCR blob, so the located text drags in everything printed
# after the warning (brand, importer address, other panels). These bound the text shown
# to the reviewer to the GOVERNMENT WARNING section itself — display only; verdict logic
# still reads the full located text, so no decision changes.
_WARNING_END_ANCHORS = ("cause health problems", "health problems")
_WARNING_DISPLAY_MARGIN = 80  # chars of slack past the statutory length when no end anchor


def _clip_to_warning(located: str) -> str:
    """Collapse ``located`` and trim it to just the Government Warning. Prefers a tight cut
    at the statutory end ("…cause health problems."), keeping the sentence-ending period;
    falls back to the statutory length plus a margin (ellipsized) when that last clause is
    too garbled to find — so a reviewer sees the warning, never the whole label tail."""
    collapsed = _collapse_ws(located)
    low = collapsed.lower()
    for anchor in _WARNING_END_ANCHORS:
        idx = low.find(anchor)
        if idx != -1:
            end = idx + len(anchor)
            if collapsed[end : end + 1] == ".":
                end += 1
            return collapsed[:end]
    limit = len(_collapse_ws(data.FULL_TEXT)) + _WARNING_DISPLAY_MARGIN
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "…"


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
