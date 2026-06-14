/*
 * Disposition commit-zone progressive enhancement (Story 4.8).
 *
 * Same-origin, no build step, no CDN (NFR-2 / UX-DR-6): the server render is already
 * correct and usable WITHOUT this script — the `.commit` form is a real `<form
 * method="post">`, a disposition button submits it, and the SERVER enforces the
 * Needs-Correction / Reject notes soft-gate (AC5 safety net) and the double-decide
 * guard (409). This file only ADDS polish (UX-DR-16 two-track):
 *
 *   (a) Debounced autosave of the Notes textarea to `POST /review/{id}/progress`
 *       as `draft_notes`, so a mid-review reload keeps the typed reason (AR-14).
 *   (b) A client soft-gate: a blank reason on Needs Correction / Reject blocks the
 *       submit, focuses the textarea, and announces via an aria-live region (never
 *       colour-only, UX-DR-15) — the server still rejects it if JS is off.
 *   (c) A calm confirm modal before a commit that leaves an open REVIEW/FAIL item
 *       (focus-trapped, Esc closes, returns focus), then re-submits the captured choice.
 *   (d) Disables the bar on submit (double-submit guard, AC3).
 *
 * A disposition is the human decision — the engine never makes it (contract #4). This
 * script reads the engine's "open review" hint only to WORD the confirm prompt; it
 * never pre-selects or recommends a control. Inert / no-throw when the bar is absent.
 */
(function () {
  "use strict";

  var form = document.querySelector("[data-disposition-form]");
  if (!form) {
    return; // not the review workspace — nothing to enhance
  }

  var textarea = form.querySelector("[name='notes']");
  var progressUrl = form.getAttribute("data-progress-url");
  var hasOpenReview = form.getAttribute("data-has-open-review") === "true";
  var modal = document.querySelector("[data-disposition-modal]");
  var buttons = Array.prototype.slice.call(
    form.querySelectorAll("button[name='disposition']")
  );

  // ── (a) Debounced Notes autosave ───────────────────────────────────────────
  var saveTimer = null;
  function scheduleSave() {
    if (!progressUrl || !textarea) {
      return;
    }
    if (saveTimer !== null) {
      window.clearTimeout(saveTimer);
    }
    saveTimer = window.setTimeout(saveNotes, 600);
  }
  function saveNotes() {
    saveTimer = null;
    var body = new URLSearchParams();
    body.set("draft_notes", textarea.value);
    // Same-origin relative POST — no cross-origin / CDN request (NFR-2 no egress).
    fetch(progressUrl, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
      credentials: "same-origin",
    }).catch(function () {
      // Autosave is best-effort: a failed beacon is silent (the textarea still holds
      // the text; the final commit POST carries the authoritative `notes`).
    });
  }
  if (textarea) {
    textarea.addEventListener("input", function () {
      // Typing a reason lifts the soft-gate's invalid state (set below when a blank
      // Needs Correction / Reject was blocked) so the field no longer reads invalid
      // to a screen reader, then the autosave beacon still fires.
      textarea.removeAttribute("aria-invalid");
      scheduleSave();
    });
  }

  // ── aria-live announcer for the soft-gate (created lazily, same origin) ──────
  var announcer = null;
  function announce(message) {
    if (!announcer) {
      announcer = document.createElement("p");
      announcer.setAttribute("aria-live", "assertive");
      announcer.className = "usa-sr-only";
      announcer.style.position = "absolute";
      announcer.style.width = "1px";
      announcer.style.height = "1px";
      announcer.style.overflow = "hidden";
      announcer.style.clip = "rect(0 0 0 0)";
      form.appendChild(announcer);
    }
    announcer.textContent = "";
    // Reassign on the next frame so a repeated identical message still announces.
    window.setTimeout(function () {
      announcer.textContent = message;
    }, 30);
  }

  function notesAreBlank() {
    return !textarea || textarea.value.trim() === "";
  }

  function disableBar() {
    buttons.forEach(function (btn) {
      btn.disabled = true;
    });
  }

  // Submit the form FOR a specific disposition value (mirrors a native button submit,
  // which a programmatic form.submit() would NOT carry). A hidden field carries the
  // chosen disposition so the server sees the same payload a click would have sent.
  function submitWith(value) {
    disableBar();
    var hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "disposition";
    hidden.value = value;
    form.appendChild(hidden);
    form.submit();
  }

  // ── (c) Confirm modal ──────────────────────────────────────────────────────
  var pendingValue = null;
  var lastFocused = null;
  var modalTitle = modal ? modal.querySelector("[data-modal-title]") : null;
  var modalBody = modal ? modal.querySelector("[data-modal-body]") : null;
  var modalConfirm = modal ? modal.querySelector("[data-modal-confirm]") : null;
  var modalCancel = modal ? modal.querySelector("[data-modal-cancel]") : null;

  function openModal(value) {
    if (!modal) {
      // No modal scaffold — fall straight through to submit (server still guards).
      submitWith(value);
      return;
    }
    pendingValue = value;
    lastFocused = document.activeElement;
    if (modalBody) {
      modalBody.textContent =
        "Some checklist items are still open for review. Recording this decision " +
        "commits it as the official disposition. You can Undo right after.";
    }
    if (modalTitle) {
      modalTitle.textContent = "Record this decision with items still open?";
    }
    modal.hidden = false;
    if (modalConfirm) {
      modalConfirm.focus();
    }
  }

  function closeModal() {
    if (!modal) {
      return;
    }
    modal.hidden = true;
    pendingValue = null;
    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus();
    }
  }

  if (modalConfirm) {
    modalConfirm.addEventListener("click", function () {
      var value = pendingValue;
      if (value !== null) {
        submitWith(value);
      }
    });
  }
  if (modalCancel) {
    modalCancel.addEventListener("click", closeModal);
  }
  if (modal) {
    modal.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeModal();
        return;
      }
      // Minimal focus trap: keep Tab cycling between Cancel and Confirm.
      if (event.key === "Tab") {
        var focusables = [modalCancel, modalConfirm].filter(Boolean);
        if (focusables.length === 0) {
          return;
        }
        var first = focusables[0];
        var last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    });
    // A click on the dim backdrop (outside the card) cancels.
    modal.addEventListener("click", function (event) {
      if (event.target === modal) {
        closeModal();
      }
    });
  }

  // ── Intercept each disposition click: soft-gate, then (maybe) confirm ────────
  buttons.forEach(function (btn) {
    btn.addEventListener("click", function (event) {
      var value = btn.value;
      var requiresNotes = btn.getAttribute("data-requires-notes") === "true";

      // (b) Soft-gate: a Needs Correction / Reject with a blank reason never submits.
      // Mark the Notes field aria-invalid (a persistent state a screen reader reports,
      // not just the transient live announcement) and focus it, in the maker's voice.
      if (requiresNotes && notesAreBlank()) {
        event.preventDefault();
        if (textarea) {
          textarea.setAttribute("aria-invalid", "true");
          textarea.focus();
        }
        announce("Add a short reason for the maker before sending this back.");
        return;
      }

      // (c) Committing while a REVIEW/FAIL item is still open ⇒ confirm first.
      if (hasOpenReview) {
        event.preventDefault();
        openModal(value);
        return;
      }

      // (d) Clean path: let the native submit proceed but guard double-submit.
      disableBar();
      // Re-enable the clicked button's value so the native submit still carries it
      // (a disabled submit button is omitted from the payload). We disabled AFTER the
      // browser captured this click's submitter, so the value is already in flight; the
      // other two stay disabled to block a second decision.
      btn.disabled = false;
      window.setTimeout(function () {
        btn.disabled = true;
      }, 0);
    });
  });
})();
