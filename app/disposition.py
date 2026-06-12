"""Centralized human-disposition enum — ``APPROVED`` / ``NEEDS_CORRECTION`` / ``REJECTED``.

Placeholder: authored in its owning Epic-3 story. Holds the disposition enum
ONLY and has NO dependency on ``verdict.py`` — the engine's advisory verdict and
the human's disposition are different enums in different modules, and no
function maps one to the other. See ``_bmad-output/project-context.md`` →
contract #4 and "Recommend, don't decide".
"""

from __future__ import annotations
