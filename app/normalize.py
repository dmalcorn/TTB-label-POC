"""Centralized field normalization — ``normalize(value, field_key)``.

Placeholder: authored in Story 3.1. ALL field comparisons route through this
one function (trim → collapse whitespace → NFKC → casefold → curly→straight
quotes → strip trailing punctuation; numeric fields parse to number+unit) — it
is what makes "STONE'S THROW" == "Stone's Throw". Import it; never inline
normalization. See ``_bmad-output/project-context.md``.
"""

from __future__ import annotations
