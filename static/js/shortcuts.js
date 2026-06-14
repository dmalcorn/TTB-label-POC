/*
 * Global keyboard power path & shortcut safety (Story 4.10).
 *
 * Same-origin, no build step, no CDN (NFR-2 / UX-DR-6): the MOUSE path is already fully
 * sufficient WITHOUT this script (UX-DR-16 two-track) — every action is a real form
 * button, link, or the [?] trigger. This file only ADDS the additive keyboard power path
 * for the high-volume specialist by DISPATCHING a keystroke to the control that already
 * exists; it never re-implements a behaviour or a gate, so the existing soft-gate /
 * confirm modal / focus-trap all keep working unchanged:
 *
 *   N        Next Submission  → clicks the Queue's /next submit button
 *   A C R    Approve / Needs Correction / Reject → clicks the matching disposition
 *            button, RE-ENTERING disposition.js's click handler so the Notes soft-gate,
 *            the open-REVIEW confirm modal, and the double-submit guard ALL still apply
 *   ← →      Move between label image faces → follows the image pager prev/next link
 *   ?        Open Help → clicks the [?] trigger (help.js opens the dialog)
 *   Esc      Closes the topmost layer — DELEGATED to the owning layer (see below)
 *
 * SHORTCUT SAFETY (UX-DR-16 — load-bearing; these fire IRREVERSIBLE federal acts):
 *   - single-letter shortcuts and the arrow keys are INERT when focus is in any
 *     <input> / <textarea> / <select> / contenteditable (so typing a correction reason
 *     in Notes can never fire R), and
 *   - INERT while a modal owns focus (the disposition confirm modal or the Help dialog) —
 *     a stray R must never reach through an open dialog to commit an act, and
 *   - modifier chords (Ctrl / Meta / Alt) and IME composition are ignored (don't hijack
 *     ⌘R / Ctrl+A), as are events a deeper layer already consumed (defaultPrevented), and
 *   - key autorepeat is ignored (event.repeat) so a HELD key fires a shortcut exactly once
 *     per deliberate press — never machine-guns an irreversible act, and the N / A,C,R
 *     ACTION shortcuts are unmodified-key only (a Shift chord is not one of them; `?` is
 *     the deliberate Shift+/ exception and is matched first).
 *
 * A/C/R click the REAL buttons (no synthesized POST), so this file deliberately contains
 * no form-field creation and no form submission for the disposition path — that is
 * disposition.js's job, and bypassing it would skip the gate. This file also makes no
 * network request / remote-resource reference of any kind (zero egress, NFR-2). Inert /
 * no-throw when a target control is absent (e.g. the access screen).
 *
 * Esc DELEGATION: this handler does NOT add its own Escape→close branch. The two closable
 * layers each own their scoped Esc while they hold focus — disposition.js (the confirm
 * modal) and help.js (the Help dialog) — and because each traps focus, its own listener
 * closes exactly that one topmost layer. A second Esc branch here would double-close or
 * close the wrong layer; do not add one.
 */
(function () {
  "use strict";

  // ── Is focus in a text-entry context? (single-letter shortcuts must stay inert) ──
  function isTextEntry(el) {
    if (!el) {
      return false;
    }
    if (el.isContentEditable) {
      return true;
    }
    var tag = el.tagName;
    if (tag === "TEXTAREA" || tag === "SELECT") {
      return true;
    }
    if (tag === "INPUT") {
      // Any text-bearing input. (A button-like input wouldn't capture typed letters,
      // but treating the whole INPUT family as text entry is the safe, simple choice.)
      return true;
    }
    return false;
  }

  // ── Does a modal currently own focus? (suppress every shortcut but Esc) ──────────
  function modalOpen() {
    var dispoModal = document.querySelector("[data-disposition-modal]");
    if (dispoModal && !dispoModal.hidden) {
      return true;
    }
    var helpPanel = document.getElementById("help-panel");
    if (helpPanel && !helpPanel.hidden) {
      return true;
    }
    return false;
  }

  function clickIfActionable(el) {
    // Only dispatch to a present, enabled control — inert otherwise (no-throw).
    if (el && !el.disabled && el.getAttribute("aria-disabled") !== "true") {
      el.click();
      return true;
    }
    return false;
  }

  function fireNext() {
    // The enabled Queue primary submit (the State-2 empty button is disabled/skipped).
    var btn = document.querySelector('form[action="/next"] button.btn-next');
    return clickIfActionable(btn);
  }

  function fireDisposition(dispoKey) {
    var form = document.querySelector("[data-disposition-form]");
    if (!form) {
      return false;
    }
    // Click the REAL button so disposition.js's gate (soft-gate + confirm modal +
    // double-submit guard) runs — never synthesize the POST.
    var btn = form.querySelector('button[name="disposition"][value="' + dispoKey + '"]');
    return clickIfActionable(btn);
  }

  // The image pager prev/next links (real <a href="?image=…"> — following one is the
  // same JS-free paging the mouse uses; let the native anchor navigation run).
  var PAGER_PREV = '.image-panel__pager-link[rel="prev"]';
  var PAGER_NEXT = '.image-panel__pager-link[rel="next"]';

  function followPager(selector) {
    var link = document.querySelector(selector);
    if (link) {
      link.click();
      return true;
    }
    return false;
  }

  function openHelp() {
    var trigger = document.querySelector("[data-help-open]");
    if (trigger) {
      trigger.click(); // help.js owns the open/focus-trap path
      return true;
    }
    return false;
  }

  var DISPOSITION_BY_KEY = {
    a: "APPROVED",
    c: "NEEDS_CORRECTION",
    r: "REJECTED",
  };

  document.addEventListener("keydown", function (event) {
    // Ignore modifier chords / IME composition / events a deeper layer already handled.
    if (event.ctrlKey || event.metaKey || event.altKey) {
      return;
    }
    if (event.isComposing || event.keyCode === 229) {
      return;
    }
    if (event.defaultPrevented) {
      return;
    }
    // Autorepeat guard: a HELD key fires keydown continuously. A shortcut must fire once
    // per deliberate physical press — never machine-gun an irreversible federal act, and
    // never re-click a disposition button during disposition.js's brief native-submit
    // re-enable window (disposition.js re-enables the clicked button so the form submit
    // carries its value, then re-disables on a 0ms timer; an autorepeat landing in that
    // window would re-enter the click). One press, one dispatch (UX-DR-16 safety).
    if (event.repeat) {
      return;
    }

    // Esc is DELEGATED to the layer that owns focus (help.js / disposition.js) — this
    // handler intentionally does not close anything itself (see header).
    if (event.key === "Escape") {
      return;
    }

    // SAFETY: single-letter shortcuts and the arrows are inert in text entry and while a
    // modal owns focus (UX-DR-16). The target OR the active element being a text field
    // both count (a keydown can target the document while a field holds focus).
    if (isTextEntry(event.target) || isTextEntry(document.activeElement) || modalOpen()) {
      return;
    }

    var key = event.key;

    // ? → open Help. (? is Shift+/, so match by key; Shift is expected here and the
    // modifier guard above only excludes Ctrl/Meta/Alt.)
    if (key === "?") {
      if (openHelp()) {
        event.preventDefault();
      }
      return;
    }

    // Arrow keys → image faces.
    if (key === "ArrowLeft") {
      if (followPager(PAGER_PREV)) {
        event.preventDefault();
      }
      return;
    }
    if (key === "ArrowRight") {
      if (followPager(PAGER_NEXT)) {
        event.preventDefault();
      }
      return;
    }

    // Single-letter ACTION shortcuts (N / A,C,R) are unmodified-key only: a Shift chord
    // is NOT one of these shortcuts. (`?` above is intentionally Shift+/ and was already
    // matched by key before here, so it is unaffected.) This keeps a deliberate Shift+R —
    // or a capital letter the user meant as text elsewhere — from reaching the disposition
    // dispatch; the matching button's own gate would still apply, but the stricter option
    // is the right default for an irreversible federal act (project-context: prefer the
    // more restrictive option around irreversible actions).
    if (event.shiftKey) {
      return;
    }

    // Single-letter actions are case-insensitive.
    var lower = key.length === 1 ? key.toLowerCase() : key;

    if (lower === "n") {
      if (fireNext()) {
        event.preventDefault();
      }
      return;
    }

    if (Object.prototype.hasOwnProperty.call(DISPOSITION_BY_KEY, lower)) {
      if (fireDisposition(DISPOSITION_BY_KEY[lower])) {
        event.preventDefault();
      }
      return;
    }
  });
})();
