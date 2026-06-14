"""Story 4.9 — In-UI Help panel.

The Help panel is **static post-auth chrome** rendered in ``templates/base.html`` (so
every screen extending it carries it with zero per-route work). There is **no new
Python route, no DB read/write, no schema change** — this is a template + CSS + JS
story. Search is a **client-side DOM filter** in ``static/js/help.js`` with **no
network call** (the on-screen promise "everything here is on this server" must be
literally true — NFR-2 zero egress).

These tests assert the five ACs at the render + file-content level:

- AC1 — the ``[?]`` trigger is wired (``aria-haspopup="dialog"`` / ``aria-controls`` /
  ``aria-expanded``) and the panel is a focus-trappable ``role="dialog"`` ·
  ``aria-modal="true"`` slide-over; the panel is gated (suppressed pre-auth).
- AC2 — the five mockup regions (search + on-server note, KB list, verdict explainer,
  keyboard shortcuts, no-results state) render with the exact mockup copy.
- AC3 — search is a local DOM filter: ``help.js`` carries no ``fetch``/``XHR``/CDN; the
  full KB renders without JS (progressive enhancement).
- AC4 — colours resolve to the spine ``--verdict-*`` tokens (not the mockup's
  ``#2e8540``/``#b8860b``); no ``@import``/CDN/font URL in the Help CSS; every verdict
  carries icon + word (never colour alone).
- AC5 — mockup scaffolding (device frame, backdrop artwork, frame-label caption) is NOT
  reproduced.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.connection import init_db
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]
BRAND_CSS = REPO_ROOT / "static" / "css" / "brand.css"
HELP_JS = REPO_ROOT / "static" / "js" / "help.js"
BASE_HTML = REPO_ROOT / "templates" / "base.html"
HELP_PARTIAL = REPO_ROOT / "templates" / "_help_panel.html"


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path, *, token: str | None = None) -> TestClient:
    """A fresh app over an isolated temp DB with the background sweep OFF.

    Mirrors the ``tests/test_queue.py`` fixture: ``/queue`` is the cheapest probe of
    the shared ``base.html`` shell (the Help panel rides every screen that extends it).
    """
    db_path = tmp_path / "help.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    if token is None:
        monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ACCESS_TOKEN", token)
    init_db(db_path)
    return TestClient(create_app())


# ── AC1: the trigger is wired + the dialog is a focus-trappable slide-over ─────


def test_help_trigger_is_wired_to_the_dialog(monkeypatch, tmp_path) -> None:
    body = _client(monkeypatch, tmp_path).get("/queue").text
    # The existing [?] control is wired to the panel (reuse, don't recreate).
    assert 'class="app-header__help"' in body
    assert 'aria-haspopup="dialog"' in body
    assert 'aria-controls="help-panel"' in body
    assert 'aria-expanded="false"' in body
    assert "data-help-open" in body


def test_help_dialog_is_an_accessible_slide_over(monkeypatch, tmp_path) -> None:
    body = _client(monkeypatch, tmp_path).get("/queue").text
    assert 'id="help-panel"' in body
    assert 'role="dialog"' in body
    assert 'aria-modal="true"' in body
    # Accessible name wired via aria-labelledby → the title element.
    assert 'aria-labelledby="help-panel-title"' in body
    assert 'id="help-panel-title"' in body
    # The close control + scrim the JS focus-trap/return-focus path drives.
    assert "data-help-close" in body
    assert "data-help-scrim" in body
    assert "Close (Esc)" in body


# ── AC1: gated — the panel never leaks pre-auth ───────────────────────────────


def test_help_panel_is_gated(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path, token="secret")  # no cookie
    resp = client.get("/queue", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/access"


def test_help_panel_absent_on_pre_auth_access_screen(monkeypatch, tmp_path) -> None:
    # The access (deny) page empties the header block ⇒ no Help chrome pre-auth.
    body = _client(monkeypatch, tmp_path, token="secret").get("/access").text
    assert 'id="help-panel"' not in body


# ── AC2: the five regions render with exact mockup copy ───────────────────────


def test_help_search_region_and_on_server_note(monkeypatch, tmp_path) -> None:
    body = _client(monkeypatch, tmp_path).get("/queue").text
    assert "data-help-search" in body
    assert 'placeholder="Ask a question…"' in body
    assert (
        "Everything here is on this server — no internet, nothing leaves the workstation." in body
    )


def test_help_kb_list_has_the_four_questions(monkeypatch, tmp_path) -> None:
    body = _client(monkeypatch, tmp_path).get("/queue").text
    for question in (
        "What exactly must the Government Warning say?",
        "Why didn't the tool check the font size?",
        "The names differ only in capitalization — is that a real mismatch?",
        "What's the difference between Needs Correction and Rejected?",
    ):
        assert question in body, f"missing KB question: {question!r}"
    # Each KB item is filterable by the client-side search.
    assert "data-help-kbitem" in body
    assert "data-help-kb" in body


def test_help_verdict_explainer_icon_word_and_reminder(monkeypatch, tmp_path) -> None:
    body = _client(monkeypatch, tmp_path).get("/queue").text
    # The verdict-vs-disposition reminder (contract #4 register, copy only).
    assert "These are the engine's" in body
    assert "is always your decision." in body
    # Every verdict carries icon + WORD (never colour alone — UX-DR-7).
    for icon, word in (("✓", "PASS"), ("⚠", "REVIEW"), ("✕", "FAIL")):
        assert icon in body, f"missing verdict icon {icon!r}"
        assert word in body, f"missing verdict word {word!r}"
    assert (
        "Color is never the whole story — every status carries an icon and a word "
        "as well as a color." in body
    )


def test_help_keyboard_shortcuts_region(monkeypatch, tmp_path) -> None:
    body = _client(monkeypatch, tmp_path).get("/queue").text
    assert "Next Submission" in body
    assert "Approve · Needs Correction · Reject" in body
    assert "Open Help" in body
    assert "Close this panel" in body
    # The kbd glyphs the mockup depicts.
    for token in ("<kbd>N</kbd>", "<kbd>A</kbd>", "<kbd>?</kbd>", "<kbd>Esc</kbd>"):
        assert token in body, f"missing keyboard token {token!r}"


def test_help_no_results_calm_state(monkeypatch, tmp_path) -> None:
    body = _client(monkeypatch, tmp_path).get("/queue").text
    assert "data-help-empty" in body
    assert "No matches yet for that." in body
    assert "Try fewer words, or browse the common questions above." in body
    assert "You could try" in body


# ── AC3: search is a local DOM filter — no egress ─────────────────────────────


def test_help_js_is_referenced_and_has_no_network_call() -> None:
    base = BASE_HTML.read_text(encoding="utf-8")
    assert "/static/js/help.js" in base, "help.js must be loaded from base.html"
    src = HELP_JS.read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "import(", "https://", "http://", "//cdn"):
        assert forbidden not in src, f"help.js must not contain {forbidden!r} (NFR-2 no egress)"


def test_help_full_kb_renders_without_js(monkeypatch, tmp_path) -> None:
    """Progressive enhancement: the KB + explainer + shortcuts are all in the HTML;
    JS only ADDS the live filter (the render is correct without it)."""
    body = _client(monkeypatch, tmp_path).get("/queue").text
    # All four KB items are present in the server render (not injected by JS).
    assert body.count("data-help-kbitem") == 4


# ── Code-review hardening regressions (help.js focus + filter robustness) ─────


def test_help_js_resets_filter_on_open() -> None:
    """Reopening the panel must restore the full browsable KB — a stale no-results
    state from a prior open must never persist (CR: Edge-Case M4)."""
    src = HELP_JS.read_text(encoding="utf-8")
    open_fn = src[src.index("function openPanel") : src.index("function closePanel")]
    assert 'searchInput.value = ""' in open_fn
    assert "filterKb()" in open_fn, "openPanel must re-run the filter to clear the no-results state"


def test_help_js_filter_folds_curly_quotes() -> None:
    """The natural keyboard apostrophe must match the KB copy's curly apostrophes —
    otherwise the empty-state's own suggested query "couldn't verify" misses
    (CR: Edge-Case M3)."""
    src = HELP_JS.read_text(encoding="utf-8")
    assert "\\u2019" in src, "filter must fold curly → straight apostrophes"
    assert "\\u201C" in src or "\\u201D" in src, "filter must fold curly double quotes"


def test_help_js_filter_scopes_to_question_and_answer_text() -> None:
    """The search corpus must exclude the decorative chevron so a query of "›"
    cannot match every item (CR: Edge-Case M2 / Blind L8)."""
    src = HELP_JS.read_text(encoding="utf-8")
    assert ".help-kb__q" in src and ".help-kb__a" in src, (
        "filter must build its haystack from the Q/A text, not the whole item textContent"
    )


def test_help_js_returns_focus_safely() -> None:
    """Return-focus must not silently drop to <body> when the original element is
    detached/hidden — fall back to the [?] trigger (CR: M1/L5/L6)."""
    src = HELP_JS.read_text(encoding="utf-8")
    assert "isConnected" in src, "return-focus must check the element is still connected"
    assert "document.body" in src, "return-focus must exclude <body> as a focus target"


def test_help_js_scrim_close_guarded_against_drag() -> None:
    """A text-selection drag that releases over the scrim must not close the panel
    (CR: Edge-Case L7 — mirrors the disposition.js backdrop guard)."""
    src = HELP_JS.read_text(encoding="utf-8")
    assert "mousedown" in src, "scrim close must track mousedown to ignore drag-release closes"


# ── AC4: tokens resolve to the spine, self-hosted, colour never alone ─────────


def _help_css_block() -> str:
    """The Help-panel section of brand.css (from its banner header to EOF)."""
    css = BRAND_CSS.read_text(encoding="utf-8")
    marker = "Help panel (Story 4.9)"
    idx = css.find(marker)
    assert idx != -1, "brand.css must contain a 'Help panel (Story 4.9)' block"
    return css[idx:]


def test_help_css_uses_spine_verdict_tokens_not_mockup_hex() -> None:
    block = _help_css_block().lower()
    assert "--verdict-pass" in block
    assert "--verdict-review" in block
    assert "--verdict-fail" in block
    # The mockup's PASS/REVIEW hex must NOT be reintroduced in the Help block.
    assert "#2e8540" not in block, "mockup PASS green leaked — spine #216e29 must win"
    assert "#b8860b" not in block, "mockup REVIEW amber leaked — spine #7a5900 must win"


def test_help_css_is_self_hosted_no_cdn_no_import() -> None:
    block = _help_css_block().lower()
    for forbidden in ("@import", "http://", "https://", "cdn", "googleapis", "fonts.g"):
        assert forbidden not in block, f"Help CSS must not contain {forbidden!r} (NFR-2)"


# ── AC5: no mockup scaffolding ────────────────────────────────────────────────


def test_help_excludes_mockup_scaffolding(monkeypatch, tmp_path) -> None:
    body = _client(monkeypatch, tmp_path).get("/queue").text
    for scaffold in ("browser-bar", "bd-img", "bd-header", "frame-label", "device__chrome"):
        assert scaffold not in body, f"mockup scaffolding {scaffold!r} must not be reproduced"
    # Tokens via the linked self-hosted brand stylesheet, not inline <style>.
    assert "/static/css/brand.css" in body


def test_help_partial_file_exists() -> None:
    assert HELP_PARTIAL.exists(), "templates/_help_panel.html (the slide-over partial) must exist"
