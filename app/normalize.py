"""Centralized field normalization — ``normalize(value, field_key)``.

Placeholder: authored in Story 3.1. ALL field comparisons route through this
one function (trim → collapse whitespace → NFKC → casefold → curly→straight
quotes → strip trailing punctuation; numeric fields parse to number+unit) — it
is what makes "STONE'S THROW" == "Stone's Throw". Import it; never inline
normalization. See ``_bmad-output/project-context.md``.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

# The two APPLICATION numeric fields (data-dictionary §alcohol_content,
# §net_contents). For these, ``normalize`` additionally parses to a canonical
# "<number> <unit>" so format/case/abbreviation variants collapse to one
# comparable form (Story 3.3's tolerance bands consume ``parse_numeric``).
NUMERIC_FIELD_KEYS = frozenset({"alcohol_content", "net_contents"})

# Curly → straight quote folding. NFKC does NOT fold these, so the explicit map
# is required; it runs AFTER casefold (casefold never touches quotes), keeping
# the contract order stable and greppable.
_QUOTE_MAP = {
    "\u2018": "'",  # ' LEFT SINGLE QUOTATION MARK
    "\u2019": "'",  # ' RIGHT SINGLE QUOTATION MARK
    "\u201c": '"',  # " LEFT DOUBLE QUOTATION MARK
    "\u201d": '"',  # " RIGHT DOUBLE QUOTATION MARK
    "\u2032": "'",  # ′ PRIME
    "\u2033": '"',  # ″ DOUBLE PRIME
}
_QUOTE_TRANSLATION = str.maketrans(_QUOTE_MAP)

# Trailing punctuation/whitespace stripped at the end of the pipeline. Internal
# punctuation is preserved (only the trailing run is removed).
_TRAILING_PUNCT = ".,;:!?\u2026'\" "

# As-filed unit spelling → canonical lowercase token. Order is longest-match
# first so multi-letter spellings win before the bare "l" alternative in the
# combined regex (regex alternation is left-to-right). Each maps the as-filed
# spelling/case to the one canonical token used for comparison.
_UNIT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("%", "%"),
    ("proof", "proof"),
    ("milliliter", "ml"),
    ("millilitre", "ml"),
    ("ml", "ml"),
    # Fluid ounces — US malt/beer net contents (e.g. "16 FL OZ"). Longest spellings
    # first so the alternation matches "fl oz" before the bare "oz"; the trailing
    # ``(?![a-z])`` boundary keeps each from matching a shorter prefix of a longer word.
    ("fluid ounces", "fl oz"),
    ("fluid ounce", "fl oz"),
    ("fl. oz.", "fl oz"),
    ("fl.oz.", "fl oz"),
    ("fl oz", "fl oz"),
    ("floz", "fl oz"),
    ("oz", "fl oz"),
    # Gallons — keg net contents (e.g. "15.5 Gallons").
    ("gallons", "gal"),
    ("gallon", "gal"),
    ("gal", "gal"),
    ("liter", "l"),
    ("litre", "l"),
    ("l", "l"),
)
_UNIT_CANONICAL: dict[str, str] = {spelling: canonical for spelling, canonical in _UNIT_PATTERNS}

# A number is parsed ONLY when it is immediately adjacent (optional whitespace)
# to a known unit — number and unit are matched as ONE token so they always
# refer to the SAME quantity. This rejects the "first stray number + a unit
# elsewhere" mismatch (e.g. "80 proof (40%)", "5 ml 20%") and handles both the
# spaced ("750 ml") and glued ("750ml") forms. Word units carry a trailing
# boundary so "l" does not bleed into "alc"; "%" needs none (non-word char).
# ``(?<![\d.,])`` rejects a number that is the tail of a larger malformed run —
# e.g. the European decimal "1,5 l" must NOT match "5 l" (and "1.2.3 %" must not
# match "3 %"); such ambiguous forms fail to parse rather than silently mis-parse.
_NUMBER = r"[-+]?\d*\.?\d+"
_UNIT_ALTERNATION = "|".join(re.escape(spelling) for spelling, _ in _UNIT_PATTERNS)
_NUMBER_UNIT_RE = re.compile(rf"(?<![\d.,])({_NUMBER})\s*({_UNIT_ALTERNATION})(?![a-z])")


def normalize(value: str | None, field_key: str) -> str:
    """Centralized field normalization (contract #2) — the single function ALL
    field comparisons route through; never inline this logic.

    Applies the FROZEN order (do not reorder — a reviewer greps against it):

    1. ``None``/empty → return ``""`` early;
    2. trim (``.strip()``);
    3. collapse internal whitespace (runs of any whitespace → one space);
    4. Unicode NFKC (fullwidth/ligature/compatibility folding);
    5. casefold (case-insensitive, eszett-aware);
    6. curly → straight quotes (NFKC does not do this — explicit, after casefold);
    7. strip trailing punctuation.

    For the numeric fields (:data:`NUMERIC_FIELD_KEYS`) the text result is then
    parsed to a canonical ``"<number> <unit>"`` (lowercase unit) so
    ``"45% Alc./Vol."``, ``"45 % alc/vol"``, and ``"45%"`` collapse equal. When a
    numeric field cannot be parsed, the text-pipeline result is returned as-is.

    This is what makes ``"STONE'S THROW" == "Stone's Throw"`` everywhere.
    """
    if value is None:
        return ""
    s = value.strip()  # (2) trim
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s)  # (3) collapse internal whitespace
    s = unicodedata.normalize("NFKC", s)  # (4) NFKC
    s = s.casefold()  # (5) casefold
    s = s.translate(_QUOTE_TRANSLATION)  # (6) curly → straight quotes
    s = s.rstrip(_TRAILING_PUNCT)  # (7) strip trailing punctuation

    if field_key in NUMERIC_FIELD_KEYS:
        number, unit = _parse_numeric_from_normalized(s)
        if number is not None and unit is not None:
            return f"{_format_number(number)} {unit}"
    return s


def parse_numeric(value: str | None, field_key: str) -> tuple[Decimal | None, str | None]:
    """Parse a numeric field's value to ``(Decimal, canonical_unit)``.

    Returns ``(None, None)`` for a non-numeric ``field_key``, a ``None``/empty
    value, or an unparseable value. Uses :class:`~decimal.Decimal` (never
    ``float``) to avoid comparison drift — mirrors the project's "never float
    math on currency" discipline; Story 3.3's tolerance bands consume the value.
    The unit is matched case-insensitively and returned as a canonical lowercase
    token (``%``, ``ml``, ``l``, ``proof``).
    """
    if field_key not in NUMERIC_FIELD_KEYS or value is None:
        return (None, None)
    s = value.strip()
    if not s:
        return (None, None)
    # Reuse the text pipeline's NFKC + casefold so e.g. fullwidth digits and
    # mixed-case units parse the same way comparisons see them.
    s = re.sub(r"\s+", " ", s)
    s = unicodedata.normalize("NFKC", s).casefold()
    return _parse_numeric_from_normalized(s)


def parse_all_numeric(value: str | None, field_key: str) -> list[tuple[Decimal, str]]:
    """Every ``(Decimal, canonical_unit)`` token in ``value``, left to right.

    Like :func:`parse_numeric` but returns ALL ``<number><unit>`` tokens, not just the
    first — so a single line carrying several quantities (e.g. an OCR
    ``"750ml | 12.5% alc./vol."``) yields BOTH the net-contents AND the ABV token, rather
    than shadowing the second behind the first. Each number+unit stays one adjacent token
    (the same :data:`_NUMBER_UNIT_RE` discipline — no cross-quantity pairing); tokens whose
    number or unit is unparseable are skipped. Empty list for a non-numeric ``field_key``,
    an empty value, or a token-less string."""
    if field_key not in NUMERIC_FIELD_KEYS or value is None:
        return []
    s = value.strip()
    if not s:
        return []
    s = re.sub(r"\s+", " ", s)
    s = unicodedata.normalize("NFKC", s).casefold()
    s = _strip_thousands_separators(s)
    out: list[tuple[Decimal, str]] = []
    for match in _NUMBER_UNIT_RE.finditer(s):
        try:
            number = Decimal(match.group(1))
        except InvalidOperation:
            continue
        canonical = _UNIT_CANONICAL.get(match.group(2))
        if canonical is None:
            continue
        out.append((number, canonical))
    return out


def _parse_numeric_from_normalized(s: str) -> tuple[Decimal | None, str | None]:
    """Extract ``(Decimal, canonical_unit)`` from an already text-normalized,
    casefolded string. Internal helper shared by :func:`normalize` and
    :func:`parse_numeric`.

    The number and unit are matched as ONE adjacent token (:data:`_NUMBER_UNIT_RE`)
    so they always describe the same quantity — a stray number elsewhere in the
    string can never be paired with a unit it does not belong to. Returns
    ``(None, None)`` when no ``"<number><unit>"`` token is present.
    """
    s = _strip_thousands_separators(s)
    match = _NUMBER_UNIT_RE.search(s)
    if match is None:
        return (None, None)
    try:
        number = Decimal(match.group(1))
    except InvalidOperation:
        return (None, None)
    canonical = _UNIT_CANONICAL.get(match.group(2))
    if canonical is None:
        return (None, None)
    return (number, canonical)


# A thousands separator is a comma flanked by digits with exactly three digits
# after it and a non-digit (or end) following — e.g. "1,000" / "12,000 ml".
# Stripping these makes "1,000 ml" parse to 1000 ml. Ambiguous comma forms that
# are NOT well-formed thousands groups (e.g. the European decimal "1,5") are left
# untouched, so they fail to parse rather than silently mis-parse.
_THOUSANDS_SEP_RE = re.compile(r"(?<=\d),(?=\d{3}(?:\D|$))")


def _strip_thousands_separators(s: str) -> str:
    return _THOUSANDS_SEP_RE.sub("", s)


def _format_number(number: Decimal) -> str:
    """Render a :class:`Decimal` without exponent or trailing-zero noise so the
    canonical numeric string is stable (``45`` not ``45.0``; ``1.5`` stays).
    """
    normalized = number.normalize()
    # Decimal.normalize() can yield scientific notation for integers (e.g.
    # Decimal("750").normalize() -> 7.5E+2); restore plain form.
    return f"{normalized:f}"
