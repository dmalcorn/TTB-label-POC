/*
 * Help slide-over panel progressive enhancement (Story 4.9).
 *
 * Same-origin, no build step, no CDN (NFR-2 / UX-DR-6): the server render is already
 * correct and usable WITHOUT this script — the Help panel's KB, verdict explainer and
 * keyboard-shortcut list are all static HTML in the page. This file only ADDS polish
 * (UX-DR-16 two-track):
 *
 *   (a) Open: the [?] header control reveals the right-anchored dialog over a scrim,
 *       sets aria-expanded, records the return-focus target, and moves focus inside.
 *   (b) Close: Esc, the close button, or a scrim click hides the panel, restores
 *       aria-expanded, and RETURNS FOCUS to the [?] trigger (EXPERIENCE.md focus mgmt).
 *   (c) Focus trap: while open, Tab / Shift+Tab cycle within the panel (mirrors the
 *       confirm-modal trap in disposition.js).
 *   (d) Search: a LOCAL DOM FILTER over the static KB items — substring match against
 *       each item's question+answer text. Zero matches reveals the calm no-results
 *       state; an empty query restores the full list.
 *
 * Contract: search is a pure local DOM filter — it makes NO network request. This file
 * deliberately contains no network-request, remote-resource, or dynamic-load reference
 * of any kind, so the on-screen promise "everything here is on this server" stays
 * literally true (a no-egress substring guard in tests/test_help_panel.py enforces
 * this). Inert / no-throw when the panel is absent.
 */
(function () {
  "use strict";

  var trigger = document.querySelector("[data-help-open]");
  var panel = document.getElementById("help-panel");
  if (!trigger || !panel) {
    return; // pre-auth (header suppressed) or panel absent — nothing to enhance
  }

  var scrim = document.querySelector("[data-help-scrim]");
  var closeBtn = panel.querySelector("[data-help-close]");
  var searchInput = panel.querySelector("[data-help-search]");
  var kbList = panel.querySelector("[data-help-kb]");
  var kbItems = Array.prototype.slice.call(panel.querySelectorAll("[data-help-kbitem]"));
  var emptyState = panel.querySelector("[data-help-empty]");

  var lastFocused = null;

  // ── Focusable discovery for the trap (visible, enabled, tabbable) ───────────
  function focusables() {
    var nodes = panel.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]),' +
        ' textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    return Array.prototype.slice.call(nodes).filter(function (el) {
      // Skip elements hidden by the no-results toggle or aria-hidden chrome.
      return el.offsetParent !== null && el.getAttribute("aria-hidden") !== "true";
    });
  }

  function isOpen() {
    return !panel.hidden;
  }

  function openPanel() {
    if (isOpen()) {
      return;
    }
    lastFocused = document.activeElement;
    // Reset the filter so a stale query / no-results state from a previous open
    // never persists — the panel always reopens to the full browsable KB (AC2).
    if (searchInput) {
      searchInput.value = "";
      filterKb();
    }
    if (scrim) {
      scrim.hidden = false;
    }
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    if (closeBtn) {
      closeBtn.focus();
    }
  }

  function closePanel() {
    if (!isOpen()) {
      return;
    }
    panel.hidden = true;
    if (scrim) {
      scrim.hidden = true;
    }
    trigger.setAttribute("aria-expanded", "false");
    // Return focus to the [?] control (AC1 / EXPERIENCE.md focus management).
    // Only restore lastFocused if it is still in the document AND reachable (not
    // hidden/detached) — a detached or display:none node keeps its .focus method
    // but focusing it is a silent no-op that drops focus to <body>. The [?] trigger
    // is the canonical return target, so fall back to it otherwise.
    if (
      lastFocused &&
      lastFocused !== document.body &&
      typeof lastFocused.focus === "function" &&
      lastFocused.isConnected &&
      lastFocused.offsetParent !== null
    ) {
      lastFocused.focus();
    } else {
      trigger.focus();
    }
  }

  trigger.addEventListener("click", function (event) {
    event.preventDefault();
    openPanel();
  });

  if (closeBtn) {
    closeBtn.addEventListener("click", closePanel);
  }
  if (scrim) {
    // Only a click that BOTH starts and ends on the scrim itself closes — a
    // text-selection drag inside the panel that releases over the scrim must not
    // discard it (mirrors the disposition.js modal backdrop guard).
    var scrimMousedown = false;
    scrim.addEventListener("mousedown", function (event) {
      scrimMousedown = event.target === scrim;
    });
    scrim.addEventListener("click", function (event) {
      if (scrimMousedown && event.target === scrim) {
        closePanel();
      }
      scrimMousedown = false;
    });
  }

  // Esc closes ONLY when open (don't swallow Esc otherwise); Tab cycles the trap.
  panel.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      event.preventDefault();
      closePanel();
      return;
    }
    if (event.key === "Tab") {
      var items = focusables();
      if (items.length === 0) {
        return;
      }
      var first = items[0];
      var last = items[items.length - 1];
      var active = document.activeElement;
      if (items.indexOf(active) === -1) {
        // Focus is on the panel container or a non-tabbable node — re-anchor it
        // inside the trap rather than letting Tab walk to background content.
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  // ── (d) Local KB filter — no network request ────────────────────────────────
  // Fold curly quotes/apostrophes to straight so the natural keyboard input
  // ("couldn't", "what's") matches the KB copy's typographic quotes, and lower-case.
  function normalizeText(s) {
    return (s || "")
      .replace(/[\u2018\u2019]/g, "'")
      .replace(/[\u201C\u201D]/g, '"')
      .toLowerCase();
  }

  // The searchable corpus is the question + answer TEXT only — never the decorative
  // chevron (aria-hidden) or other chrome, so a query of "›" can't match every item.
  function itemHaystack(item) {
    var q = item.querySelector(".help-kb__q");
    var a = item.querySelector(".help-kb__a");
    var text = (q ? q.textContent : "") + " " + (a ? a.textContent : "");
    return normalizeText(text);
  }

  function filterKb() {
    if (!searchInput) {
      return;
    }
    var query = normalizeText(searchInput.value.trim());
    var matches = 0;
    kbItems.forEach(function (item) {
      if (query === "") {
        item.hidden = false;
        matches += 1;
        return;
      }
      var hit = itemHaystack(item).indexOf(query) !== -1;
      item.hidden = !hit;
      if (hit) {
        matches += 1;
      }
    });
    var noMatches = query !== "" && matches === 0;
    if (emptyState) {
      emptyState.hidden = !noMatches;
    }
    if (kbList) {
      // Hide the (now-empty) list when the calm no-results state is showing.
      kbList.hidden = noMatches;
    }
  }

  if (searchInput) {
    searchInput.addEventListener("input", filterKb);
  }
})();
