/*
 * Review-workspace progressive enhancement.
 *
 * Same-origin, no build step, no CDN (NFR-2 / UX-DR-6): the server render is already
 * correct and usable without this script — every checklist row is a real `<a href="#…">`
 * so the mouse path (scroll to the field group) works with JS disabled, and each Pass/Fail
 * control is already rendered (a Match pre-selects Pass). This file ADDS:
 *
 *   1. Smooth-scroll + move focus to the target field group on a checklist-row click.
 *   2. The per-check Pass/Fail call. The SAME control appears on a field card AND on its
 *      checklist row (keyed by `check_key`); clicking either one persists the decision via
 *      `POST /review/{id}/progress` and live-syncs EVERY control for that check_key plus the
 *      checklist row + the "N of M decided" counter. The checklist is the universal decision
 *      surface — even checks with no card are decided there. Optimistic UI reverts on a
 *      failed fetch (honest UI).
 *
 * A per-check call is the reviewer's record/aid — NEVER the overall disposition and never a
 * change to the engine verdict (contract #4). Inert / no-throw when nothing matches.
 */
(function () {
  "use strict";

  var match = window.location.pathname.match(/\/review\/(\d+)/);
  var submissionId = match ? match[1] : null;
  if (submissionId === null) {
    return; // not a review page — nothing to enhance
  }

  var checklist = document.querySelector(".checklist");
  var doneSpan = checklist ? checklist.querySelector("[data-done-count]") : null;

  function recountDecided() {
    // "Decided" = a checklist row carrying a pass/fail decision class.
    if (!checklist || !doneSpan) {
      return;
    }
    doneSpan.textContent = String(checklist.querySelectorAll(".cli--pass, .cli--fail").length);
  }

  function focusTarget(target) {
    // Move focus to the field group (its <section> carries tabindex="-1"); walk to the
    // nearest focusable, non-aria-hidden node so we never focus a hidden marker.
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

  function postDecision(checkKey, decision) {
    var body = new URLSearchParams();
    body.set("check_key", checkKey);
    body.set("decision", decision === null ? "clear" : decision);
    return fetch("/review/" + submissionId + "/progress", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString(),
      credentials: "same-origin",
    }).then(function (resp) {
      if (!resp.ok) {
        throw new Error("decision failed: " + resp.status);
      }
      return resp;
    });
  }

  function groupDecision(group) {
    var active = group.querySelector(".decide__btn.is-active");
    return active ? active.getAttribute("data-decision") : null;
  }

  function applyGroup(group, decision) {
    var btns = group.querySelectorAll(".decide__btn");
    for (var i = 0; i < btns.length; i++) {
      var on = decision !== null && btns[i].getAttribute("data-decision") === decision;
      btns[i].classList.toggle("is-active", on);
      btns[i].setAttribute("aria-pressed", on ? "true" : "false");
    }
  }

  // Sync a decision across EVERY control for this check_key — the card's buttons AND any
  // carded-less checklist-row buttons — plus the read-only result text on a carded row, the
  // row tint, and the count. `decision` is "pass"/"fail" or null (clear).
  function syncDecision(checkKey, decision) {
    var groups = document.querySelectorAll(".decide");
    for (var i = 0; i < groups.length; i++) {
      if (groups[i].getAttribute("data-check-key") === checkKey) {
        applyGroup(groups[i], decision);
      }
    }
    if (checklist) {
      var rows = checklist.querySelectorAll(".cli");
      for (var j = 0; j < rows.length; j++) {
        if (rows[j].getAttribute("data-check-key") !== checkKey) {
          continue;
        }
        rows[j].classList.remove("cli--pass", "cli--fail", "cli--open");
        rows[j].classList.add("cli--" + (decision || "open"));
        rows[j].setAttribute("data-decision", decision || "");
        var txt = rows[j].querySelector("[data-checklist-decision]");
        if (txt) {
          txt.textContent =
            decision === "pass" ? "You passed" : decision === "fail" ? "You failed" : "needs your call";
          txt.className = "cli__decision cli__decision--" + (decision || "open");
        }
      }
    }
    recountDecided();
  }

  // The Pass/Fail buttons live on cards AND checklist rows — delegate on the document.
  document.addEventListener("click", function (event) {
    var btn = event.target.closest ? event.target.closest(".decide__btn") : null;
    if (!btn) {
      return;
    }
    var group = btn.closest(".decide");
    if (!group) {
      return;
    }
    var checkKey = group.getAttribute("data-check-key");
    var decision = btn.getAttribute("data-decision");
    if (!checkKey || !decision) {
      return;
    }

    var prior = groupDecision(group); // null when previously undecided
    syncDecision(checkKey, decision);
    postDecision(checkKey, decision).catch(function () {
      // Honest UI: the call did not persist — revert every synced control + the counter.
      syncDecision(checkKey, prior);
    });
  });

  // Checklist jump-link clicks → smooth-scroll/focus the field group (the anchor works too).
  if (checklist) {
    checklist.addEventListener("click", function (event) {
      var jump = event.target.closest(".cli__jump");
      if (!jump || !checklist.contains(jump)) {
        return;
      }
      var href = jump.getAttribute("href");
      if (href && href.charAt(0) === "#") {
        event.preventDefault();
        scrollToTarget(href);
      }
    });
  }
})();
