"""Story 1.4 — vendored USWDS app shell & Treasury brand layer.

Verifies the shell renders from `templates/base.html`, every asset is same-origin
(the firewall posture, NFR-2/AR-8 — the unit-level guardian of the `--network none`
proof), the Treasury brand layer loads after USWDS, mockup-only placeholder data is
excluded, and the vendored assets exist and serve.

The shell is verified on the reviewer's real landing screen — the queue (`/queue`,
Story 4.1) — since Story 4 retired the `/` placeholder demonstrator: the root now
redirects into the queue (see `test_root_redirects_to_landing`).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.connection import init_db
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]

# Hosts/markers that would betray an off-host asset (CDN / Google Fonts / external).
FORBIDDEN_ASSET_MARKERS = (
    "http://",
    "https://",
    "//cdn",
    "cdn.",
    "googleapis",
    "gstatic",
    "unpkg",
    "jsdelivr",
    "fonts.google",
)


class _AssetRefCollector(HTMLParser):
    """Collect every asset-bearing attribute (href/src) from the rendered HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.refs.append(value)


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    """A fresh app over an isolated temp DB with the sweep OFF.

    The shell now renders on the gated queue screen (the `/` placeholder is gone),
    so the screen reads the DB — point ``DATABASE_PATH`` at a throwaway file and
    create the schema up-front via :func:`init_db` (``TestClient(create_app())``
    used without a ``with`` block does not fire the lifespan/startup ``init_db``).
    ``ACCESS_TOKEN`` is cleared so the gate is fail-open for these shell checks.
    """
    db_path = tmp_path / "shell.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    init_db(db_path)
    return TestClient(create_app())


def _shell_html(monkeypatch: pytest.MonkeyPatch, tmp_path) -> str:
    """The rendered shell, as served on the reviewer's real landing (the queue)."""
    resp = _client(monkeypatch, tmp_path).get("/queue")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    return resp.text


def test_root_redirects_to_landing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """GET / sends the reviewer to the queue (the Story-1.4 placeholder is retired)."""
    resp = _client(monkeypatch, tmp_path).get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/queue"


def test_landing_renders_shell_with_header(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """AC-3/AC-5: the landing renders the shell — header title + the [?] Help control."""
    html = _shell_html(monkeypatch, tmp_path)
    assert "TTB Label Review" in html
    assert 'class="app-header"' in html
    # The Help control is present and focusable (its panel arrives in Story 4.4).
    assert 'aria-label="Help"' in html


def test_shell_assets_are_all_same_origin(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """AC-1: every href/src is same-origin under /static — no CDN, no Google Fonts."""
    html = _shell_html(monkeypatch, tmp_path)
    refs = _AssetRefCollector()
    refs.feed(html)
    assert refs.refs, "expected the shell to reference vendored assets"
    for ref in refs.refs:
        low = ref.lower()
        for marker in FORBIDDEN_ASSET_MARKERS:
            assert marker not in low, f"off-host asset reference detected: {ref!r}"
        assert ref.startswith("/static/"), f"asset is not same-origin /static: {ref!r}"


def test_uswds_css_loads_before_brand_css(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """AC-2: brand layer must load AFTER USWDS so the Treasury delta wins."""
    html = _shell_html(monkeypatch, tmp_path)
    uswds_pos = html.find("/static/uswds/css/uswds.min.css")
    brand_pos = html.find("/static/css/brand.css")
    assert uswds_pos != -1 and brand_pos != -1
    assert uswds_pos < brand_pos


def test_shell_excludes_placeholder_agent(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """AC-3: mockup-only placeholder data (J. Park) is not reproduced."""
    assert "J. Park" not in _shell_html(monkeypatch, tmp_path)


def test_healthz_still_ok(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Regression: the liveness route is untouched by the shell wiring."""
    resp = _client(monkeypatch, tmp_path).get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- Vendored asset presence + serving (AC-1 / AC-4 host-side stand-in) ---

VENDORED_ASSETS = (
    "static/uswds/css/uswds.min.css",
    "static/uswds/js/uswds.min.js",
    "static/uswds/js/uswds-init.min.js",
    "static/css/brand.css",
    "static/uswds/fonts/public-sans/PublicSans-Regular.woff2",
    "static/uswds/fonts/roboto-mono/roboto-mono-v5-latin-regular.woff2",
    "static/uswds/img/sprite.svg",
)


def test_vendored_assets_exist_on_disk() -> None:
    """AC-1/AC-4: the committed assets are what ship (no runtime download)."""
    for rel in VENDORED_ASSETS:
        assert (REPO_ROOT / rel).is_file(), f"missing vendored asset: {rel}"


def test_vendored_assets_serve_200(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """AC-1/AC-4: each vendored asset is served same-origin (200)."""
    client = _client(monkeypatch, tmp_path)
    for rel in VENDORED_ASSETS:
        resp = client.get("/" + rel)
        assert resp.status_code == 200, f"{rel} served {resp.status_code}"


def test_brand_css_self_hosts_public_sans() -> None:
    """AC-2: Public Sans is self-hosted via @font-face pointing at a vendored woff2."""
    brand = (REPO_ROOT / "static/css/brand.css").read_text(encoding="utf-8")
    assert "@font-face" in brand
    assert re.search(r'font-family:\s*"Public Sans"', brand)
    assert "/static/uswds/fonts/public-sans/" in brand
