"""Centralized field normalization — ``normalize`` / ``parse_numeric`` (Story 3.1).

The project's highest-value test (project-context Testing): the **SM-C2
zero-false-FAIL class** — ``"STONE'S THROW" == "Stone's Throw"`` — plus one
assertion per pipeline step in the frozen order (trim → collapse whitespace →
NFKC → casefold → curly→straight quotes → strip trailing punctuation) and the
numeric number+unit parse. Pure unit tests: no DB, no I/O, no fixtures.
"""

from __future__ import annotations

from decimal import Decimal

from app.normalize import NUMERIC_FIELD_KEYS, normalize, parse_numeric

# ── AC1: the SM-C2 zero-false-FAIL class ─────────────────────────────────────


def test_sm_c2_stones_throw_straight_apostrophe():
    assert normalize("STONE'S THROW", "brand_name") == normalize("Stone's Throw", "brand_name")


def test_sm_c2_stones_throw_curly_apostrophe():
    # U+2019 RIGHT SINGLE QUOTATION MARK on one side, straight ' on the other.
    assert normalize("STONE\u2019S THROW", "brand_name") == normalize("Stone's Throw", "brand_name")


def test_sm_c2_mixed_curly_and_straight_collapse_equal():
    assert normalize("Stone\u2019s Throw", "brand_name") == normalize("STONE'S THROW", "brand_name")


# ── one test per pipeline step ───────────────────────────────────────────────


def test_step_trim_leading_trailing_whitespace():
    assert normalize("  Acme  ", "brand_name") == normalize("Acme", "brand_name")


def test_step_collapse_internal_whitespace():
    assert normalize("Old   Tom   Gin", "brand_name") == normalize("Old Tom Gin", "brand_name")


def test_step_collapse_mixed_whitespace_kinds():
    # tabs / newlines collapse to a single space too.
    assert normalize("Old\t\nTom", "brand_name") == normalize("Old Tom", "brand_name")


def test_step_nfkc_fullwidth_folds_to_ascii():
    # Fullwidth latin (U+FF21 …) NFKC-folds to ASCII.
    assert normalize("\uff21\uff22\uff23", "brand_name") == normalize("ABC", "brand_name")


def test_step_nfkc_ligature_folds():
    # The ﬁ ligature (U+FB01) folds to "fi" under NFKC.
    assert normalize("\ufb01nest", "brand_name") == normalize("finest", "brand_name")


def test_step_casefold_is_case_insensitive():
    assert normalize("BRAND", "brand_name") == normalize("brand", "brand_name")


def test_step_casefold_handles_eszett():
    # casefold (not lower) folds ß → ss.
    assert normalize("STRASSE", "brand_name") == normalize("Stra\u00dfe", "brand_name")


def test_step_curly_double_quotes_fold_to_straight():
    assert normalize("\u201cFoo\u201d", "brand_name") == normalize('"Foo"', "brand_name")


def test_step_strip_trailing_punctuation():
    assert normalize("Acme.", "brand_name") == normalize("Acme", "brand_name")
    assert normalize("Acme!!!", "brand_name") == normalize("Acme", "brand_name")
    assert normalize("Acme\u2026", "brand_name") == normalize("Acme", "brand_name")


def test_internal_punctuation_is_preserved():
    # Only TRAILING punctuation is stripped; internal punctuation stays.
    assert normalize("A.B.C", "brand_name") != normalize("ABC", "brand_name")


# ── None / empty ─────────────────────────────────────────────────────────────


def test_none_returns_empty_string():
    assert normalize(None, "brand_name") == ""


def test_empty_and_whitespace_only_returns_empty_string():
    assert normalize("", "brand_name") == ""
    assert normalize("   ", "brand_name") == ""


# ── numeric fields: canonical "<number> <unit>" collapse ─────────────────────


def test_numeric_field_keys_constant():
    assert NUMERIC_FIELD_KEYS == frozenset({"alcohol_content", "net_contents"})


def test_alcohol_content_format_variants_collapse_equal():
    assert normalize("45% Alc./Vol.", "alcohol_content") == normalize(
        "45 % alc/vol", "alcohol_content"
    )
    assert normalize("45%", "alcohol_content") == normalize("45% Alc./Vol.", "alcohol_content")


def test_net_contents_unit_case_collapses_equal():
    assert normalize("750 mL", "net_contents") == normalize("750 ml", "net_contents")


def test_net_contents_canonical_string_shape():
    assert normalize("750 mL", "net_contents") == "750 ml"


def test_alcohol_content_canonical_string_shape():
    assert normalize("45% Alc./Vol.", "alcohol_content") == "45 %"


# ── parse_numeric → (Decimal, unit) ──────────────────────────────────────────


def test_parse_numeric_abv_percent():
    assert parse_numeric("45% Alc./Vol.", "alcohol_content") == (Decimal("45"), "%")


def test_parse_numeric_returns_decimal_not_float():
    number, _unit = parse_numeric("45.5% Alc./Vol.", "alcohol_content")
    assert isinstance(number, Decimal)
    assert number == Decimal("45.5")


def test_parse_numeric_net_contents_ml():
    assert parse_numeric("750 mL", "net_contents") == (Decimal("750"), "ml")


def test_parse_numeric_litre_unit_lowercased():
    assert parse_numeric("1.5 L", "net_contents") == (Decimal("1.5"), "l")


def test_parse_numeric_proof_unit():
    assert parse_numeric("90 proof", "alcohol_content") == (Decimal("90"), "proof")


def test_parse_numeric_unparseable_returns_none_none():
    assert parse_numeric("not a number", "alcohol_content") == (None, None)
    assert parse_numeric(None, "net_contents") == (None, None)
    assert parse_numeric("", "alcohol_content") == (None, None)


def test_parse_numeric_non_numeric_field_returns_none_none():
    # parse_numeric only applies to the numeric field keys.
    assert parse_numeric("Stone's Throw", "brand_name") == (None, None)


# ── number+unit must be matched ADJACENTLY (no stray-number/unit mismatch) ────


def test_no_space_unit_canonicalizes_same_as_spaced():
    # "750mL" (glued) and "750 mL" (spaced) MUST collapse equal — a false
    # MISMATCH otherwise. (Patched: word-unit detection no longer relies on a
    # digit→letter word boundary that never fires.)
    assert normalize("750mL", "net_contents") == normalize("750 mL", "net_contents")
    assert normalize("750mL", "net_contents") == "750 ml"
    assert parse_numeric("750mL", "net_contents") == (Decimal("750"), "ml")
    assert parse_numeric("1.5l", "net_contents") == (Decimal("1.5"), "l")


def test_unit_is_paired_with_its_adjacent_number_not_a_stray_one():
    # "80 proof (40%)": the canonical pair must be the proof reading next to 80,
    # NOT (80, %) grabbing a number and a unit from different parts of the string.
    assert parse_numeric("80 proof (40%)", "alcohol_content") == (Decimal("80"), "proof")


def test_bare_unit_with_no_adjacent_number_is_unparseable():
    # A unit token with no number next to it must not rescue a stray number.
    assert parse_numeric("l 1.5", "net_contents") == (None, None)
    assert parse_numeric("proof", "alcohol_content") == (None, None)


def test_thousands_separator_is_handled_not_truncated():
    # "1,000 ml" is 1000 ml, NOT 1 ml (silent 1000x error before the patch).
    assert parse_numeric("1,000 ml", "net_contents") == (Decimal("1000"), "ml")
    assert parse_numeric("12,000 ml", "net_contents") == (Decimal("12000"), "ml")


def test_ambiguous_comma_decimal_refuses_rather_than_misparses():
    # European decimal "1,5 l" is ambiguous; refuse (None, None) rather than
    # silently read it as 5 l or 1 l.
    assert parse_numeric("1,5 l", "net_contents") == (None, None)


def test_malformed_multi_dot_number_is_unparseable():
    # "1.2.3 %" must not silently truncate to 1.2 % — refuse instead.
    assert parse_numeric("1.2.3 %", "alcohol_content") == (None, None)
