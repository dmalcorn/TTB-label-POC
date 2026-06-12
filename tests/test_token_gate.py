"""Story 1.5 — token-gated access and clean denial.

Verifies the access boundary (FR-25, UX-DR-1, AR-9): a valid cookie reaches the
protected shell; an absent/invalid token is cleanly denied with no data leakage;
`/healthz` + `/static/*` stay exempt (deploy healthcheck + styled gate page);
`ACCESS_TOKEN` empty/absent means the gate is not enforced (clone-and-run); and
the entry/denial screens carry the exact `token-gate.html` copy and a11y hooks.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]

# Markers that would betray protected data on the gate/denial surface (none exist
# yet, but the no-leakage guarantee must hold as those features land).
LEAKAGE_MARKERS = (
    "submission",
    "ttb_id",
    "disposition",
    "benchmark",
    "engine_verdict",
    "label_image",
)


def _client(monkeypatch: pytest.MonkeyPatch, token: str | None) -> TestClient:
    """Build a fresh app with ACCESS_TOKEN set/cleared (config is read at startup)."""
    if token is None:
        monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ACCESS_TOKEN", token)
    return TestClient(create_app())


# --- AC-1 / AC-5: enforcement + cookie flow ---


def test_valid_cookie_reaches_protected_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "secret")
    client.cookies.set("ttb_access", "secret")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "TTB Label Review" in resp.text
    assert 'class="app-header"' in resp.text  # the post-auth shell, header present


def test_absent_token_redirects_to_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "secret")
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/access"


def test_invalid_cookie_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "secret")
    client.cookies.set("ttb_access", "wrong")
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/access"


def test_post_correct_token_sets_cookie_and_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "secret")
    resp = client.post("/access", data={"token": "secret"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    set_cookie = resp.headers["set-cookie"].lower()
    assert "ttb_access=secret" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    # http test transport ⇒ Secure must be OFF (Secure-in-prod only).
    assert "secure" not in set_cookie


def test_post_wrong_token_denial_401_state2(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "secret")
    resp = client.post("/access", data={"token": "nope"}, follow_redirects=False)
    assert resp.status_code == 401
    body = resp.text
    assert 'role="status"' in body
    assert "Access token required." in body
    # Binding State-2 fidelity: the exact denial body copy and the error input class.
    assert "We couldn't verify that token." in body
    assert "usa-input--error" in body
    assert 'aria-invalid="true"' in body
    # Denial must not grant access.
    assert "set-cookie" not in {k.lower() for k in resp.headers}


# --- AC-1: no data leakage / token never echoed ---


def test_denial_leaks_no_protected_data(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "secret")
    state1 = client.get("/access").text.lower()
    state2 = client.post("/access", data={"token": "nope"}, follow_redirects=False).text.lower()
    for marker in LEAKAGE_MARKERS:
        assert marker not in state1, f"State 1 leaks {marker!r}"
        assert marker not in state2, f"State 2 leaks {marker!r}"


def test_token_value_never_echoed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "s3cr3t-token")
    assert "s3cr3t-token" not in client.get("/access").text
    denied = client.post("/access", data={"token": "wrong"}, follow_redirects=False)
    assert "s3cr3t-token" not in denied.text


# --- AC-3: exemptions ---


def test_healthz_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "secret")  # no cookie
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_static_assets_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "secret")  # no cookie
    assert client.get("/static/css/brand.css").status_code == 200
    assert client.get("/static/uswds/css/uswds.min.css").status_code == 200


def test_access_routes_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "secret")  # no cookie
    assert client.get("/access").status_code == 200


# --- AC-4: fail-open when unconfigured ---


def test_gate_open_when_token_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, None)
    assert client.get("/").status_code == 200  # shell reachable, gate not enforced


def test_gate_open_when_token_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "")
    assert client.get("/").status_code == 200


def test_gate_enforced_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(monkeypatch, "secret")
    assert client.get("/", follow_redirects=False).status_code == 303


# --- AC-2: gate screen fidelity (entry copy, no scaffolding, no header) ---


def test_state1_entry_copy_and_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _client(monkeypatch, "secret").get("/access").text
    assert "TTB Label Review" in body
    assert "Enter your access token to begin." in body
    assert "autofocus" in body
    assert ">Enter</button>" in body or "Enter</button>" in body
    assert "Your token was sent with your assignment." in body
    # Pre-auth screen: no app-header, and no mockup-only scaffolding.
    assert 'class="app-header"' not in body
    assert "device__chrome" not in body
    assert "state-label" not in body


# --- Constant-time compare (unit) ---


def test_token_matching_is_constant_time_and_correct(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import Settings
    from app.web import deps

    s = Settings(access_token="secret")
    assert deps.token_matches("secret", s) is True
    assert deps.token_matches("wrong", s) is False
    assert deps.token_matches("", s) is False
    assert deps.token_matches(None, s) is False
    assert deps.token_matches("secret", Settings(access_token=None)) is False
    # The compare must use hmac.compare_digest (no == timing oracle).
    assert "compare_digest" in (REPO_ROOT / "app/web/deps.py").read_text(encoding="utf-8")


def test_token_matching_tolerates_whitespace_and_non_ascii() -> None:
    """Pasted-with-newline must still match; a non-ASCII token must not 500."""
    from app.config import Settings
    from app.web import deps

    # Trailing/leading whitespace (paste artifact) is stripped on both sides.
    assert deps.token_matches("secret\n", Settings(access_token="secret")) is True
    assert deps.token_matches(" secret ", Settings(access_token="secret")) is True
    # Non-ASCII compares safely (UTF-8 bytes) instead of raising TypeError.
    s = Settings(access_token="sécret-✓")
    assert deps.token_matches("sécret-✓", s) is True
    assert deps.token_matches("wrong", s) is False
