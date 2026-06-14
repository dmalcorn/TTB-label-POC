/*
 * Smart-checklist progressive enhancement (Story 4.6).
 *
 * Same-origin, no build step, no CDN (NFR-2 / UX-DR-6): the server render is already
 * correct and usable without this script — every checklist row is a real `<a href="#…">`
 * so the mouse path (scroll to the field group) works with JS disabled. This file only
 * ADDS polish (UX-DR-16 two-track):
 *
 *   1. Smooth-scroll + move focus to the target field group on a row click.
 *   2. For an actionable (REVIEW/FAIL) row, persist the manual tick via a same-origin
 *      `POST /review/{id}/progress` and update the "N of M done" live counter.
 *
 * A manual tick is an "I looked at this" acknowledgement — NEVER a disposition and never
 * a change to the engine verdict (contract #4). The optimistic UI swap reverts on a
 * failed fetch so we never show a tick that did not persist (honest UI).
 *
 * The script is inert / no-throw when the checklist is absent.
 */
(function () {
  "use strict";

  var checklist = document.querySelector(".checklist");
  if (!checklist) {
    return; // no checklist on this page — nothing to enhance
  }

  // The submission id is in the URL: /review/{id} (the POST goes to /review/{id}/progress).
  var match = window.location.pathname.match(/\/review\/(\d+)/);
  var submissionId = match ? match[1] : null;

  var countRegion = checklist.querySelector("[data-checklist-count]");
  var doneSpan = checklist.querySelector("[data-done-count]");
  var totalSpan = checklist.querySelector("[data-total-count]");

  function recountDone() {
    // Recompute "done" from the DOM so the announced count never drifts from what is
    // shown: a row is done when it is in the muted `done` or human-confirmed `usercheck`
    // state.
    var done = checklist.querySelectorAll(".cli--done, .cli--usercheck").length;
    if (doneSpan) {
      doneSpan.textContent = String(done);
    }
    return done;
  }

  function focusTarget(target) {
    // Move focus so keyboard users land on the field group. The group <section>s
    // carry tabindex="-1" so they are focusable programmatically without entering
    // the tab order. Two anchors are scroll-only `aria-hidden` <span> markers
    // (group-mandatory-text lives inside group-identity; group-conditional is a
    // standalone marker) — focusing an aria-hidden element is a WCAG anti-pattern,
    // so we walk to the nearest focusable, non-hidden element instead. The scroll
    // already landed the viewport; this only repairs WHERE focus goes (UX-DR-16).
    var node = target;
    while (node && node.nodeType === 1) {
      var hidden = node.getAttribute && node.getAttribute("aria-hidden") === "true";
      if (!hidden && node.tabIndex >= 0 && typeof node.focus === "function") {
        node.focus({ preventScroll: true });
        return;
      }
      node = node.parentElement;
    }
  }

  function scrollToTarget(anchorHref) {
    if (!anchorHref || anchorHref.charAt(0) !== "#") {
      return;
    }
    var target = document.getElementById(anchorHref.slice(1));
    if (!target) {
      return;
    }
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    focusTarget(target);
  }

  function postTick(checkKey, ticked) {
    if (submissionId === null) {
      return Promise.reject(new Error("no submission id"));
    }
    var body = new URLSearchParams();
    body.set("check_key", checkKey);
    body.set("ticked", ticked ? "true" : "false");
    // Same-origin relative POST — no cross-origin / CDN request (NFR-2 no egress).
    return fetch("/review/" + submissionId + "/progress", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
      credentials: "same-origin",
    }).then(function (resp) {
      if (!resp.ok) {
        throw new Error("tick failed: " + resp.status);
      }
      return resp;
    });
  }

  function toggleRow(row) {
    var checkKey = row.getAttribute("data-check-key");
    if (!checkKey) {
      return;
    }
    var wasTicked = row.getAttribute("data-ticked") === "true";
    var nowTicked = !wasTicked;

    // Remember the pre-toggle class so a failed POST can revert cleanly.
    var priorClass = row.className;
    var priorTicked = row.getAttribute("data-ticked");

    // Optimistic swap: an actionable row toggles between its open state
    // (open / openfail) and the human-confirmed `usercheck` state.
    if (nowTicked) {
      row.classList.remove("cli--open", "cli--openfail");
      row.classList.add("cli--usercheck");
    } else {
      row.classList.remove("cli--usercheck");
      // Restore the engine register: a FAIL row reverts to openfail, else open.
      if ((row.getAttribute("data-verdict") || "").toUpperCase() === "FAIL") {
        row.classList.add("cli--openfail");
      } else {
        row.classList.add("cli--open");
      }
    }
    row.setAttribute("data-ticked", nowTicked ? "true" : "false");
    recountDone();

    postTick(checkKey, nowTicked).catch(function () {
      // Honest UI: the tick did not persist — revert the optimistic state + counter.
      row.className = priorClass;
      if (priorTicked === null) {
        row.removeAttribute("data-ticked");
      } else {
        row.setAttribute("data-ticked", priorTicked);
      }
      recountDone();
    });
  }

  checklist.addEventListener("click", function (event) {
    var row = event.target.closest(".cli");
    if (!row || !checklist.contains(row)) {
      return;
    }
    // Always do the scroll/focus polish (the anchor would do it too, less smoothly).
    var href = row.getAttribute("href");
    if (href && href.charAt(0) === "#") {
      event.preventDefault();
      scrollToTarget(href);
    }
    // Only actionable rows (REVIEW/FAIL) carry data-actionable; toggle their tick.
    if (row.getAttribute("data-actionable") === "true") {
      toggleRow(row);
    }
  });

  // Mark the live region as ready (defensive — server already set aria-live).
  if (countRegion && totalSpan) {
    countRegion.setAttribute("aria-live", "polite");
  }
})();
