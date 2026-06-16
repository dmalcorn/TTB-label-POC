/*
 * Per-image zoom + pan for the label panel (progressive enhancement).
 *
 * Same-origin, no build, no CDN, no dependency (NFR-2). The labels are fully usable
 * without this script — it only ADDS a reading aid for fine print:
 *
 *   - CLICK an image to activate zoom on THAT image (clicking another image, or
 *     double-clicking, releases it). Activating gates the wheel so normal mouse-wheel
 *     scrolling of the panel is untouched until you opt in.
 *   - MOUSE WHEEL zooms toward the cursor (CSS transform; layout/clipping unchanged).
 *   - CLICK-DRAG pans the enlarged image within its frame.
 *   - DOUBLE-CLICK resets to fit and releases.
 *
 * Inert / no-throw when there are no label images.
 */
(function () {
  "use strict";

  var imgs = document.querySelectorAll(".image-panel__img");
  if (!imgs.length) {
    return;
  }

  var MIN = 1;
  var MAX = 6;
  var STEP = 0.0016; // wheel sensitivity (factor per deltaY unit)

  imgs.forEach(function (img) {
    var s = { scale: 1, x: 0, y: 0, active: false, dragging: false, moved: false, ox: 0, oy: 0 };
    var face = img.closest(".image-panel__face") || img.parentElement;

    function apply() {
      img.style.transform =
        "translate(" + s.x + "px," + s.y + "px) scale(" + s.scale + ")";
    }

    function reset() {
      s.scale = 1;
      s.x = 0;
      s.y = 0;
      s.active = false;
      s.dragging = false;
      img.classList.remove("is-zooming");
      img.style.transform = "";
    }
    img.addEventListener("zoomrelease", reset);

    function activate() {
      // Release any other image currently in zoom mode (one at a time).
      var others = document.querySelectorAll(".image-panel__img.is-zooming");
      for (var i = 0; i < others.length; i++) {
        if (others[i] !== img) {
          others[i].dispatchEvent(new CustomEvent("zoomrelease"));
        }
      }
      s.active = true;
      img.classList.add("is-zooming");
    }

    img.addEventListener("click", function () {
      if (s.moved) {
        s.moved = false; // a click that ended a drag — ignore
        return;
      }
      if (!s.active) {
        activate();
      }
    });

    img.addEventListener("dblclick", function (event) {
      event.preventDefault();
      reset();
    });

    img.addEventListener(
      "wheel",
      function (event) {
        if (!s.active) {
          return; // not activated — let the panel scroll normally
        }
        event.preventDefault();
        var rect = face.getBoundingClientRect();
        var fx = event.clientX - rect.left;
        var fy = event.clientY - rect.top;
        var prev = s.scale;
        var next = Math.min(MAX, Math.max(MIN, prev * (1 - event.deltaY * STEP)));
        if (next === prev) {
          return;
        }
        var ratio = next / prev;
        // Keep the content point under the cursor stationary (transform-origin: 0 0).
        s.x = fx - ratio * (fx - s.x);
        s.y = fy - ratio * (fy - s.y);
        s.scale = next;
        if (next === MIN) {
          s.x = 0;
          s.y = 0;
        }
        apply();
      },
      { passive: false }
    );

    img.addEventListener("mousedown", function (event) {
      if (!s.active) {
        return;
      }
      event.preventDefault();
      s.dragging = true;
      s.moved = false;
      s.ox = event.clientX - s.x;
      s.oy = event.clientY - s.y;
    });

    window.addEventListener("mousemove", function (event) {
      if (!s.dragging) {
        return;
      }
      s.moved = true;
      s.x = event.clientX - s.ox;
      s.y = event.clientY - s.oy;
      apply();
    });

    window.addEventListener("mouseup", function () {
      s.dragging = false;
    });
  });
})();
