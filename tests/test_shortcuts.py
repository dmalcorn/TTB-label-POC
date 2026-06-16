"""Story 4.10 — Keyboard power path & shortcut safety.

The keyboard power path is **purely additive** progressive enhancement (UX-DR-16
two-track): one new same-origin script ``static/js/shortcuts.js`` wired globally in
``templates/base.html``, plus ARIA-only ``aria-keyshortcuts`` discoverability hints on
the controls it drives. There is **no new Python route, no DB read/write, no schema
change, and no structural template change** — the handler *dispatches* keystrokes to
controls that already exist (the ``/next`` form button, the disposition buttons, the
image pager links, the ``[?]`` Help trigger).

The keyboard behaviour itself is client-side JS that pytest cannot execute, so the
highest-value tests are **file-content guards** over ``static/js/shortcuts.js`` asserting
the load-bearing safety invariants (single-letter shortcuts inert in text entry + while a
modal owns focus; modifier chords ignored; A/C/R dispatched to the real buttons so the
disposition gate is never bypassed). These mirror the JS-guard pattern in
``tests/test_help_panel.py``.

ACs:

- AC1 — the documented path is live: N (Next), A/C/R (routed through the disposition
  gate), ←/→ (image faces), ? (Help), Esc (close topmost layer, delegated to the owning
  layer). Discoverability via ``aria-keyshortcuts``.
- AC2 — single-letter shortcuts (and arrows) are inert in any input/textarea/
  contenteditable AND while a modal owns focus; modifier chords (Ctrl/Meta/Alt) ignored.
- AC3 — the mouse path is fully sufficient with the script absent; the script changes no
  route/template structure and never fires on load.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.connection import connect, init_db
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]
SHORTCUTS_JS = REPO_ROOT / "static" / "js" / "shortcuts.js"
BASE_HTML = REPO_ROOT / "templates" / "base.html"
ACTION_BAR = REPO_ROOT / "templates" / "_action_bar.html"


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path, *, token: str | None = None) -> TestClient:
    db_path = tmp_path / "shortcuts.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    if token is None:
        monkeypatch.delenv("ACCESS_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ACCESS_TOKEN", token)
    init_db(db_path)
    return TestClient(create_app())


def _db_path(tmp_path) -> str:
    return str(tmp_path / "shortcuts.db")


def _insert_submission(conn: sqlite3.Connection, **overrides) -> int:
    cols = {
        "ttb_id": "26009000000000",
        "beverage_type": "DISTILLED_SPIRITS",
        "brand_name": "Stone's Throw",
        "status": "IN_REVIEW",
        "submitted_at": "2026-06-01T12:00:00Z",
    }
    cols.update(overrides)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO submissions ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608
    cur = conn.execute(sql, tuple(cols.values()))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


# ── AC1/AC3: the script is wired globally (Queue AND Review) ───────────────────


def test_shortcuts_file_exists() -> None:
    assert SHORTCUTS_JS.exists(), "static/js/shortcuts.js (the global key handler) must exist"


def test_shortcuts_js_wired_in_base_outside_per_page_block() -> None:
    base = BASE_HTML.read_text(encoding="utf-8")
    assert "/static/js/shortcuts.js" in base, "shortcuts.js must load from base.html (global)"
    # It must live OUTSIDE the per-page {% block scripts %} so it rides every screen.
    block_idx = base.find("{% block scripts %}")
    tag_idx = base.find("/static/js/shortcuts.js")
    assert block_idx != -1, "base.html must declare a scripts block"
    assert tag_idx < block_idx, (
        "the global shortcuts.js tag must precede (be outside) the per-page block"
    )


def test_shortcuts_js_present_on_queue(monkeypatch, tmp_path) -> None:
    body = _client(monkeypatch, tmp_path).get("/queue").text
    assert "/static/js/shortcuts.js" in body


def test_shortcuts_js_present_on_review(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    body = client.get(f"/review/{sid}").text
    assert "/static/js/shortcuts.js" in body


# ── AC3/NFR-2: no egress — the handler only dispatches DOM events ──────────────


def test_shortcuts_js_has_no_network_call() -> None:
    src = SHORTCUTS_JS.read_text(encoding="utf-8")
    for forbidden in ("fetch(", "XMLHttpRequest", "import(", "https://", "http://", "//cdn"):
        assert forbidden not in src, (
            f"shortcuts.js must not contain {forbidden!r} (NFR-2 no egress)"
        )


# ── AC2: single-letter shortcuts inert in text entry (the load-bearing test) ──


def test_shortcuts_js_inert_in_text_entry() -> None:
    """Typing a correction reason in Notes must NEVER fire R — the handler must
    early-return when focus is in an input/textarea/select/contenteditable (UX-DR-16)."""
    src = SHORTCUTS_JS.read_text(encoding="utf-8")
    assert "TEXTAREA" in src, "handler must detect a <textarea> as text entry"
    assert "INPUT" in src, "handler must detect an <input> as text entry"
    assert "SELECT" in src, "handler must detect a <select> as text entry"
    assert "isContentEditable" in src or "contenteditable" in src, (
        "handler must detect contenteditable as text entry"
    )


# ── AC2: single-letter shortcuts inert while a modal owns focus ───────────────


def test_shortcuts_js_inert_while_modal_owns_focus() -> None:
    """A stray R must never reach through an open dialog (the disposition confirm
    modal or the Help panel) to commit a federal act (UX-DR-16)."""
    src = SHORTCUTS_JS.read_text(encoding="utf-8")
    assert "data-disposition-modal" in src, (
        "handler must detect the disposition confirm modal as open"
    )
    assert "help-panel" in src, "handler must detect the Help dialog as open"


# ── AC2: modifier chords are not hijacked ─────────────────────────────────────


def test_shortcuts_js_ignores_modifier_chords() -> None:
    src = SHORTCUTS_JS.read_text(encoding="utf-8")
    for mod in ("ctrlKey", "metaKey", "altKey"):
        assert mod in src, f"handler must ignore {mod} chords (don't hijack browser/OS keys)"
    assert "defaultPrevented" in src, "handler must skip events a deeper layer already consumed"


def test_shortcuts_js_guards_against_key_autorepeat() -> None:
    """A HELD key fires keydown continuously. A shortcut must fire once per deliberate
    press — never machine-gun an irreversible federal act, and never re-click a disposition
    button during disposition.js's brief native-submit re-enable window. The handler must
    skip autorepeat events (event.repeat)."""
    src = SHORTCUTS_JS.read_text(encoding="utf-8")
    assert "event.repeat" in src, (
        "handler must skip autorepeat events so a held key never fires a shortcut twice "
        "(UX-DR-16 safety: one press, one dispatch)"
    )


def test_shortcuts_js_action_keys_require_no_shift() -> None:
    """The N / A,C,R action shortcuts are unmodified-key only: a Shift chord (e.g. Shift+R,
    or a capital letter meant as text) must not reach the disposition dispatch. `?` (Shift+/)
    is matched before this guard, so it stays reachable."""
    src = SHORTCUTS_JS.read_text(encoding="utf-8")
    assert "shiftKey" in src, (
        "the single-letter action branch must early-return on a Shift chord (the stricter "
        "default around an irreversible federal act)"
    )


# ── AC1/AC3: dispatch to existing controls, never re-implement the gate ────────


def test_shortcuts_js_dispatches_to_existing_controls() -> None:
    src = SHORTCUTS_JS.read_text(encoding="utf-8")
    # ? → the Help trigger; N → the /next submit; arrows → the pager links.
    assert "data-help-open" in src, "? must dispatch to the existing Help trigger"
    assert "/next" in src, "N must target the existing /next form button"
    assert 'rel="prev"' in src or "rel='prev'" in src, "← must follow the existing prev pager link"
    assert 'rel="next"' in src or "rel='next'" in src, "→ must follow the existing next pager link"
    # A/C/R must select the real disposition buttons (so disposition.js's gate runs).
    assert "data-disposition-form" in src, "A/C/R must locate the existing disposition form"
    assert 'name="disposition"' in src or "name='disposition'" in src, (
        "A/C/R must click the real disposition buttons (route through the gate)"
    )


def test_shortcuts_js_does_not_bypass_the_disposition_gate() -> None:
    """A/C/R must .click() the real button (re-entering disposition.js's soft-gate +
    confirm modal), NEVER synthesize the disposition POST — that would bypass the gate
    AC2 guards against. So this file must not create a hidden disposition input or
    submit a form itself for the disposition path."""
    src = SHORTCUTS_JS.read_text(encoding="utf-8")
    assert "createElement" not in src, (
        "shortcuts.js must not build form fields — that is disposition.js's job; "
        "it must click the real button so the gate runs"
    )
    assert ".submit(" not in src, (
        "shortcuts.js must not submit a form directly (that bypasses the disposition gate)"
    )


def test_shortcuts_js_delegates_esc_to_owning_layer() -> None:
    """Esc closes the topmost layer, but each layer (help.js / disposition.js) owns its
    own scoped Esc while it holds focus — shortcuts.js must NOT add a second Esc close
    (that would double-close / close the wrong layer)."""
    src = SHORTCUTS_JS.read_text(encoding="utf-8")
    lowered = src.lower()
    assert "delegat" in lowered or "topmost" in lowered or "owning layer" in lowered, (
        "the Esc delegation must be documented so it is not 'fixed' by adding an Esc branch"
    )
    # No dispatch branch toggling `hidden` on an Escape press.
    assert 'key === "Escape"' not in src or "hidden = true" not in src, (
        "shortcuts.js must not add its own Escape→close branch"
    )


# ── AC1: aria-keyshortcuts discoverability hints on the live controls ─────────


def test_queue_next_keeps_keyshortcut_hint(monkeypatch, tmp_path) -> None:
    # A READY submission makes the queue non-empty so the ENABLED Next button renders
    # (the State-2 disabled button carries no shortcut — it is inert by design).
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        _insert_submission(conn, status="READY_FOR_REVIEW")
    body = client.get("/queue").text
    assert 'aria-keyshortcuts="N"' in body, "the Next Submission button keeps its N hint"


def test_action_bar_buttons_carry_keyshortcut_hints(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    body = client.get(f"/review/{sid}").text
    for hint in ('aria-keyshortcuts="A"', 'aria-keyshortcuts="C"', 'aria-keyshortcuts="R"'):
        assert hint in body, f"a disposition button is missing its {hint} discoverability hint"


def test_action_bar_template_maps_keyshortcut_by_disposition_key() -> None:
    # The ARIA hint is added by the disposition KEY (A/C/R) — a structure-preserving,
    # ARIA-only addition (AC3 — no control/structure change).
    src = ACTION_BAR.read_text(encoding="utf-8")
    assert "aria-keyshortcuts" in src, "the action-bar buttons must declare aria-keyshortcuts"


# ── AC3: the mouse path is unchanged — structure preserved ────────────────────


def test_mouse_path_still_sufficient_on_queue(monkeypatch, tmp_path) -> None:
    body = _client(monkeypatch, tmp_path).get("/queue").text
    # The real /next POST form + its submit button still render (mouse-only path).
    assert 'action="/next"' in body
    assert "btn-next" in body


def test_mouse_path_still_sufficient_on_review(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    with connect(_db_path(tmp_path)) as conn:
        sid = _insert_submission(conn)
    body = client.get(f"/review/{sid}").text
    # The real disposition POST form still renders (mouse-only path).
    assert "data-disposition-form" in body
    assert f'action="/review/{sid}/disposition"' in body
