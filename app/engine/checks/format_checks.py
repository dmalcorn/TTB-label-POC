"""The ``format_checks`` evaluator — per-type deterministic format checks (Story 3.5).

Plugs into the Story-3.2 dispatch seam (``{strategy: evaluator}`` registry in
``app/engine/checks/__init__.py``) under the ``format_checks`` strategy, with NO
executor change. It validates rule-bound FORMATS / POLICIES deterministically
against the submission's OCR text — distinct from Story 3.3's ``field_match``
(which compares the application VALUE against the label). One evaluator handles
several format checks, dispatched by ``check.check_key``:

  - ``abv_format``           — per-type ABV-presence policy (the cross-type
                               false-reject trap) + acceptable-abbreviation format.
  - ``standards_of_fill``    — §5.203 approved-size table lookup.
  - ``proof_abv_consistency``— proof = 2 × ABV (only when BOTH are present).
  - ``name_address_format``  — §5.66 responsibility-phrase presence (soft → REVIEW).

**NO LLM, by contract (AC1).** These are fixed-rule format checks; an LLM's
nondeterminism is a liability. This module never imports/constructs a model
adapter and never reads the LLM extraction — it reads ONLY ``ctx.ocr_text`` (the
deterministic engine's input) + ``ctx.submission`` application fields. (project-
context determinism taxonomy.)

**CFR rules live as DATA (AC1/AC4).** Every citation + rule literal (the ABV
policy map, the standards-of-fill table, the proof ratio, the responsibility
phrases) is imported from ``app/engine/rulesets/format_checks.py`` — never
inlined here. A grep for the CFR-citation literal inside this logic is a review
finding.

**When unsure, REVIEW — never FAIL (AC4).** A check that cannot be evaluated from
the available data (proof shown but ABV unreadable; net-contents unit not
isolable; an unknown beverage-type policy) returns REVIEW with an explanation,
never a fabricated PASS/FAIL — the costliest error is a false reject.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app import normalize, verdict
from app.engine.checks import CheckContext, CheckResult
from app.engine.rulesets import format_checks as data

if TYPE_CHECKING:
    from app.engine.rulesets import Check

# A keyed sub-evaluator: judges one format Check against the submission's OCR text.
_Handler = Callable[[CheckContext, str], CheckResult]


def format_checks(check: Check, ctx: CheckContext) -> CheckResult:
    """Dispatch one format Check to its keyed sub-evaluator (deterministic, no LLM).

    Routes on ``check.check_key``; an unknown key degrades to an honest REVIEW
    (finalize-don't-abort, FR-9) rather than raising. Reads ONLY ``ctx.ocr_text`` +
    the submission's application fields — never a model. Writes NO ``field_comparisons``
    row (these compare against the statute/policy, not an application field).
    """
    ocr_text = ctx.ocr_text or ""
    handler = _HANDLERS.get(check.check_key)
    if handler is None:
        return CheckResult(
            verdict=verdict.REVIEW,
            detail=f"no format handler for check_key {check.check_key!r}",
        )
    return handler(ctx, ocr_text)


# ── abv_format — the cross-type ABV trap + abbreviation format (AC2) ──────────


def _abv_format(ctx: CheckContext, ocr_text: str) -> CheckResult:
    """Per-type ABV-presence policy (the false-reject trap) + abbreviation format.

    Branches on the per-type policy carried as DATA (``data.ABV_POLICY`` keyed on
    ``beverage_type``) — never a hard-coded ``if beverage_type`` chain. Spirits =
    ALWAYS required ⇒ absent FAILs; table wine ≤14% and malt beverage ⇒ absent is
    NOT failed (the trap). When present, the abbreviation format is verified.
    """
    policy = data.ABV_POLICY.get(ctx.submission.beverage_type)
    abv = _find_abv_pct(ocr_text)

    if abv is None:
        # No ABV statement found on the label. Whether that FAILs depends on the
        # per-type policy (carried as DATA — the cross-type trap).
        return _abv_absent_verdict(ctx, policy)

    # Present — verify the abbreviation/format is one of the accepted forms.
    if not _has_abv_abbreviation(ocr_text):
        return CheckResult(
            verdict=verdict.FAIL,
            detail=(
                f"ABV {abv}% present but lacks an accepted abbreviation "
                f"({', '.join(data.ABV_ABBREVIATION_TOKENS)})"
            ),
        )
    return CheckResult(
        verdict=verdict.PASS, detail=f"ABV statement present and well-formed: {abv}%"
    )


def _abv_absent_verdict(ctx: CheckContext, policy: str | None) -> CheckResult:
    """The verdict when NO ABV statement is on the label — branch on the per-type policy."""
    if policy == data.ABV_ALWAYS_REQUIRED:
        return CheckResult(
            verdict=verdict.FAIL,
            detail="ABV statement required for distilled spirits but not found on label",
        )
    if policy == data.ABV_REQUIRED_ABOVE_14_PCT:
        # Wine: required only > 14% ABV. With no ABV on the label we branch on the
        # APPLICATION ABV: ≤ 14% ⇒ the label may compliantly omit it (a "table/light
        # wine" case) ⇒ PASS; > 14% ⇒ the label SHOULD carry it but we cannot be
        # certain from the label alone ⇒ REVIEW; UNPARSEABLE/absent ⇒ we cannot tell
        # whether the > 14% rule even applies ⇒ REVIEW (defer), never a guessed PASS
        # (AC4). The only non-PASS outcomes here are REVIEW — never a FAIL (the trap).
        app_abv, _ = normalize.parse_numeric(ctx.submission.alcohol_content, "alcohol_content")
        if app_abv is None:
            return CheckResult(
                verdict=verdict.REVIEW,
                detail=(
                    "wine application ABV is unreadable and no ABV on label — cannot "
                    f"confirm the §4.36 > {data.WINE_ABV_REQUIRED_THRESHOLD}% rule; review"
                ),
            )
        if app_abv > data.WINE_ABV_REQUIRED_THRESHOLD:
            return CheckResult(
                verdict=verdict.REVIEW,
                detail=(
                    f"wine application ABV {app_abv}% > "
                    f"{data.WINE_ABV_REQUIRED_THRESHOLD}% but no ABV found on label — review"
                ),
            )
        return CheckResult(
            verdict=verdict.PASS,
            detail="wine ≤ 14% ABV may omit the ABV statement (table/light wine) — not required",
        )
    if policy == data.ABV_OPTIONAL_UNLESS_TRIGGER:
        # Malt beverage: ABV is optional UNLESS the alcohol derives from an added
        # nonbeverage flavor (§7.65) — a trigger NOT knowable from the label. Absent ⇒
        # never a FAIL (the trap), but the trigger is genuinely unevaluable, so we
        # REVIEW (defer to the human) rather than guess a PASS — AC4 "when unsure,
        # REVIEW, never guess." The costliest error is a false reject, so this is a
        # REVIEW, never a FAIL.
        return CheckResult(
            verdict=verdict.REVIEW,
            detail=(
                "malt-beverage ABV is optional unless an added-flavor trigger applies "
                "(§7.65) — trigger not determinable from the label; review"
            ),
        )
    # Unknown beverage-type policy ⇒ defer to the human (never guess).
    return CheckResult(
        verdict=verdict.REVIEW,
        detail=f"ABV-presence policy unknown for beverage type {ctx.submission.beverage_type!r}",
    )


def _has_abv_abbreviation(ocr_text: str) -> bool:
    """Whether the OCR text carries an accepted ABV abbreviation WORD (case-insensitive).

    Matches on a WORD boundary, not a bare substring, so ``"alc"``/``"vol"`` cannot
    spuriously fire inside unrelated words (``calcium``/``revolver``/``evolve``). The
    accepted tokens are words (``alc``/``vol``/``by volume``/``abv``) — ``%`` is the
    value marker, not an abbreviation, so it is not in the DATA list.
    """
    low = ocr_text.casefold()
    return any(_word_present(token, low) for token in data.ABV_ABBREVIATION_TOKENS)


def _word_present(token: str, text: str) -> bool:
    """True if ``token`` appears in ``text`` bounded by non-alphanumerics (word match)."""
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text) is not None


# ── standards_of_fill — §5.203 table lookup (AC3) ────────────────────────────


def _standards_of_fill(ctx: CheckContext, ocr_text: str) -> CheckResult:
    """Look the net-contents size up in the §5.203 approved-size table (as DATA).

    Parses + canonicalizes the net-contents value to ``(Decimal, "ml")`` and
    membership-tests the approved set ⇒ PASS; a parseable off-standard size ⇒ FAIL
    with the §5.203 citation; an unparseable / missing-unit value ⇒ REVIEW (AC4).
    """
    size = _find_net_contents_ml(ocr_text)
    if size is None:
        return CheckResult(
            verdict=verdict.REVIEW,
            detail="no net-contents size isolable from the label text — review",
        )
    if (size, "ml") in data.STANDARDS_OF_FILL:
        return CheckResult(
            verdict=verdict.PASS, detail=f"net contents {size} mL is an approved standard of fill"
        )
    return CheckResult(
        verdict=verdict.FAIL,
        detail=(
            f"net contents {size} mL is not an approved standard of fill "
            f"({data.STANDARDS_OF_FILL_CITATION})"
        ),
    )


# ── proof_abv_consistency — proof = 2 × ABV when BOTH present (AC3) ───────────


def _proof_abv_consistency(ctx: CheckContext, ocr_text: str) -> CheckResult:
    """Verify proof = 2 × ABV — ONLY when both an ABV and a proof token are present.

    Proof is OPTIONAL: its absence is never a FAIL. Proof present but ABV unreadable
    ⇒ REVIEW (cannot verify the rule). Both present ⇒ ``abs(proof − 2×abv) <=
    PROOF_TOLERANCE`` ⇒ PASS else FAIL. ``Decimal`` throughout (never float).
    """
    proof = _find_numeric_for_unit(ocr_text, "proof", "alcohol_content")
    if proof is None:
        # Proof is optional — its absence is not a defect.
        return CheckResult(
            verdict=verdict.PASS, detail="no proof statement (optional) — nothing to verify"
        )

    abv = _find_abv_pct(ocr_text)
    if abv is None:
        return CheckResult(
            verdict=verdict.REVIEW,
            detail=f"proof {proof} present but ABV unreadable — cannot verify proof = 2 × ABV",
        )

    expected_proof = abv * data.PROOF_PER_ABV
    if abs(proof - expected_proof) <= data.PROOF_TOLERANCE:
        return CheckResult(
            verdict=verdict.PASS,
            detail=f"proof {proof} ≈ 2 × ABV {abv}% = {expected_proof} (±{data.PROOF_TOLERANCE})",
        )
    return CheckResult(
        verdict=verdict.FAIL,
        detail=(
            f"proof/ABV mismatch: proof {proof} vs 2 × ABV {abv}% = {expected_proof} "
            f"(tol ±{data.PROOF_TOLERANCE})"
        ),
    )


# ── name_address_format — responsibility-phrase presence (soft → REVIEW) ─────


def _name_address_format(ctx: CheckContext, ocr_text: str) -> CheckResult:
    """Check for a §5.66 responsibility (qualifying) phrase preceding the name/address.

    A permitted phrase ("Bottled By", "Imported By", …) present ⇒ PASS. None found ⇒
    REVIEW (a missing phrase is a soft signal — addresses vary; NOT an auto-FAIL, the
    false-reject guard / the regulatory doc's "address validity flag-REVIEW").
    """
    low = ocr_text.casefold()
    for phrase in data.RESPONSIBILITY_PHRASES:
        if phrase in low:
            return CheckResult(
                verdict=verdict.PASS, detail=f"responsibility phrase present: {phrase!r}"
            )
    return CheckResult(
        verdict=verdict.REVIEW,
        detail="no name/address responsibility phrase found — review the address statement",
    )


# ── numeric extraction helpers (centralized normalizer; Decimal; OCR-only) ───


# A number immediately adjacent (optional whitespace) to a unit token — mirrors the
# normalizer's "number and unit are ONE token" discipline (``_NUMBER_UNIT_RE``) so a
# stray number is never paired with a unit it does not belong to. Units are matched
# case-insensitively; the trailing ``(?![a-z])`` (not ``\b``) stops a word unit from
# bleeding into a following letter (``l`` vs ``alc``) while still matching ``45%`` —
# ``%`` is a non-word char, so a ``\b`` after it would (wrongly) fail before a space.
_TOKEN_RE = re.compile(
    r"(?<![\d.,])([-+]?\d*\.?\d+)\s*(%|proof|milliliters?|millilitres?|ml|liters?|litres?|l)(?![a-z])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _UnitToken:
    """One ``<number><unit>`` occurrence: its ``Decimal`` value, canonical unit, span."""

    value: Decimal
    unit: str
    start: int
    end: int


def _scan_unit_tokens(ocr_text: str, field_key: str) -> list[_UnitToken]:
    """Every ``<number><unit>`` token in the OCR text, re-parsed through ``normalize``.

    Each candidate is re-parsed through the centralized ``normalize.parse_numeric`` so
    the canonical unit + ``Decimal`` come from the one contract, never an inline parse.
    Spans are carried so callers can disambiguate by proximity to a cue word (a stray
    serving/promo numeral must never be mistaken for the net-contents or ABV value).
    """
    tokens: list[_UnitToken] = []
    for match in _TOKEN_RE.finditer(ocr_text):
        candidate = f"{match.group(1)}{match.group(2)}"
        number, unit = normalize.parse_numeric(candidate, field_key)
        if number is not None and unit is not None:
            tokens.append(_UnitToken(number, unit, match.start(), match.end()))
    return tokens


def _find_numeric_for_unit(ocr_text: str, want_unit: str, field_key: str) -> Decimal | None:
    """The first ``Decimal`` whose canonical unit equals ``want_unit`` in the OCR text.

    Used for ``proof`` (the ``proof`` unit only ever attaches to its own number, so the
    first match is unambiguous). ``None`` when no matching-unit token is present.
    """
    for token in _scan_unit_tokens(ocr_text, field_key):
        if token.unit == want_unit:
            return token.value
    return None


# Alcohol-statement cue words: a ``%`` near one of these is the ABV value, not a stray
# promotional/nutrition percentage ("30% off", "% daily value"). Matched as words.
_ABV_CUE_WORDS: tuple[str, ...] = ("alc", "vol", "abv", "alcohol")
# Net-contents cue word: a size token near "net" is the net-contents value.
_NET_CUE_WORDS: tuple[str, ...] = ("net",)
# How far (chars) before/after a unit token we look for a cue word.
_CUE_WINDOW = 24


def _has_cue_near(ocr_text: str, token: _UnitToken, cues: tuple[str, ...]) -> bool:
    """Whether a cue word appears within ``_CUE_WINDOW`` chars around the token's span."""
    low = ocr_text.casefold()
    lo = max(0, token.start - _CUE_WINDOW)
    hi = min(len(low), token.end + _CUE_WINDOW)
    window = low[lo:hi]
    return any(_word_present(cue, window) for cue in cues)


def _find_abv_pct(ocr_text: str) -> Decimal | None:
    """The ABV percentage from the OCR text, or ``None`` if no ``%`` reads as ABV.

    A stray promotional / nutrition ``%`` ("30% off", "100% natural", "% daily value")
    must NOT be mistaken for the ABV statement (it would wrongly read ABV as "present"
    and defeat the per-type absent-policy). So a ``%`` token counts as ABV only when an
    alcohol cue word (alc/vol/abv/alcohol) sits near it; failing a nearby cue, a lone
    ``%`` token is taken as the ABV ONLY when an accepted ABV abbreviation word
    (alc/vol/by volume/abv) appears SOMEWHERE on the label — i.e. a bare ``45%`` paired
    with an ``Alc./Vol.`` on another line is still recognized, but a label whose only
    ``%`` is uncued AND carries no abbreviation word at all (a marketing "100% Estate
    Grown" or "30% OFF") is NOT read as ABV. Without that abbreviation guard, such a
    stray ``%`` would read ABV as "present" and then trip the missing-abbreviation FAIL
    gate — a false reject that defeats the per-type absent-policy (the AC2 cross-type
    trap: a ≤14% table wine / a malt beverage that compliantly omits its ABV must never
    FAIL on incidental marketing copy). Otherwise ``None`` — ABV is treated as not
    present, and the per-type absent-policy applies.
    """
    pct = [t for t in _scan_unit_tokens(ocr_text, "alcohol_content") if t.unit == "%"]
    if not pct:
        return None
    cued = [t for t in pct if _has_cue_near(ocr_text, t, _ABV_CUE_WORDS)]
    if cued:
        return cued[0].value
    # No %-token is cued. A lone % is the ABV value ONLY if an abbreviation word exists
    # somewhere (the bare "45%" … "Alc./Vol." case). With no abbreviation word at all the
    # lone % is incidental marketing/nutrition copy — treat ABV as absent so the per-type
    # policy decides (spirits⇒FAIL-on-absence, ≤14% wine⇒PASS, malt⇒REVIEW), never a
    # false missing-abbreviation FAIL.
    if len(pct) == 1 and _has_abv_abbreviation(ocr_text):
        return pct[0].value
    return None


def _find_net_contents_ml(ocr_text: str) -> Decimal | None:
    """The net-contents size canonicalized to millilitres (``Decimal``), or ``None``.

    Canonicalizes litres → millilitres (×1000) so the §5.203 lookup is a single-unit
    membership test (1.75 L → 1750 mL). A label often carries other volume numerals
    (a serving size, a "makes 4 × 1 L" suggestion) BEFORE the real net-contents, so the
    first ``ml``/``l`` token is the wrong pick: prefer a size token cued by "net"; else
    take the LAST size token (net contents conventionally trails incidental volumes).
    A non-positive parse (an OCR ``-750``/``0`` artifact) is dropped → ``None`` ⇒ REVIEW
    (AC4 — never a guessed FAIL from corrupt input).
    """
    sizes: list[_UnitToken] = []
    for token in _scan_unit_tokens(ocr_text, "net_contents"):
        if token.unit == "ml":
            ml = token.value
        elif token.unit == "l":
            ml = token.value * Decimal("1000")
        else:
            continue
        if ml <= 0:  # OCR noise (stray hyphen / dropped digit) — never a confident FAIL
            continue
        sizes.append(_UnitToken(ml, "ml", token.start, token.end))
    if not sizes:
        return None
    cued = [t for t in sizes if _has_cue_near(ocr_text, t, _NET_CUE_WORDS)]
    if cued:
        return cued[-1].value
    return sizes[-1].value


# ── the keyed sub-evaluator registry (dispatched by check_key) ───────────────

_HANDLERS: dict[str, _Handler] = {
    "abv_format": _abv_format,
    "standards_of_fill": _standards_of_fill,
    "proof_abv_consistency": _proof_abv_consistency,
    "name_address_format": _name_address_format,
}
