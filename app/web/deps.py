"""Web-layer access boundary for the token gate (Story 1.5).

The single shared access token (env `ACCESS_TOKEN`, surfaced via `app/config.py`
`Settings`) gates the whole app — there are no accounts, roles, or IdP (out of
scope per architecture). These helpers are pure and side-effect-free so the
enforcement guard (wired in `app/main.py`) and the access router can share one
constant-time comparison and one exemption list.

Security posture (FR-25 / AR-9):
- Constant-time compare via `hmac.compare_digest` — never `==` (timing oracle).
- The token / cookie value is never logged.
- Fail-OPEN only when the token is unset/empty (clone-and-run dev); fail-CLOSED
  for every non-exempt route once `ACCESS_TOKEN` is configured.
"""

from __future__ import annotations

import hmac

from fastapi import Request

from app.config import Settings

# Name of the HttpOnly cookie carrying the shared token after a successful entry.
ACCESS_COOKIE = "ttb_access"

# Never gated: the liveness probe (Docker/Railway healthcheck), the gate's own
# entry/denial surface, and the self-hosted assets (so the gate page renders
# fully styled — same-origin USWDS + Public Sans — and the offline styling proof
# from Story 1.4 still holds).
EXEMPT_PATHS = frozenset({"/healthz", "/access"})
EXEMPT_PREFIXES = ("/static/",)


def gate_enabled(settings: Settings) -> bool:
    """True iff a non-empty `ACCESS_TOKEN` is configured.

    `None` and `""` are treated identically (resolves the deferred empty-vs-absent
    decision): both mean "gate not enforced" so a clean clone boots usable.
    """
    return bool(settings.access_token)


def is_exempt(path: str) -> bool:
    """True for paths that must be reachable without a token."""
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def token_matches(submitted: str | None, settings: Settings) -> bool:
    """Constant-time check of a submitted token against the configured one."""
    expected = settings.access_token
    if not expected or not submitted:
        return False
    return hmac.compare_digest(submitted, expected)


def has_valid_access(request: Request, settings: Settings) -> bool:
    """True iff the request carries a valid access cookie (constant-time)."""
    return token_matches(request.cookies.get(ACCESS_COOKIE), settings)
