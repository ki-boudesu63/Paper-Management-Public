/**
 * Paper Management - Reading Room client-side JavaScript.
 *
 * Handles:
 * - obsidian:// URI generation and navigation (open file / search)
 * - Obsidian search button integration
 *
 * Depends on htmx for partial page updates.
 */

/* ============================================================
 * Obsidian URI helpers
 * ============================================================ */

/**
 * Open a file in Obsidian via obsidian://open URI.
 * Fetches the URI from the server API, then navigates to it.
 *
 * @param {string} filePath - Relative path within the vault.
 */
async function openInObsidian(filePath) {
  try {
    const response = await fetch(
      "/api/obsidian/open?file=" + encodeURIComponent(filePath)
    );
    const data = await response.json();
    if (data.uri) {
      window.location.href = data.uri;
    }
  } catch (err) {
    console.error("Failed to generate Obsidian open URI:", err);
  }
}

/**
 * Open Obsidian search with the given query.
 * Fetches the URI from the server API, then navigates to it.
 *
 * @param {string} query - Search query text.
 */
async function searchInObsidian(query) {
  if (!query.trim()) {
    return;
  }
  try {
    const response = await fetch(
      "/api/obsidian/search?q=" + encodeURIComponent(query)
    );
    const data = await response.json();
    if (data.uri) {
      window.location.href = data.uri;
    }
  } catch (err) {
    console.error("Failed to generate Obsidian search URI:", err);
  }
}

/* ============================================================
 * Event listeners
 * ============================================================ */

document.addEventListener("DOMContentLoaded", function () {
  /* Obsidian search button */
  var searchBtn = document.getElementById("obsidian-search-btn");
  if (searchBtn) {
    searchBtn.addEventListener("click", function () {
      var searchInput = document.querySelector(".search-input");
      var query = searchInput ? searchInput.value : "";
      searchInObsidian(query);
    });
  }
});

/**
 * Delegate click events for dynamically loaded Obsidian open buttons.
 * Uses event delegation on the document body since inspector content
 * is loaded via htmx.
 */
document.addEventListener("click", function (event) {
  var btn = event.target.closest(".obsidian-open-btn");
  if (btn) {
    event.preventDefault();
    var filePath = btn.getAttribute("data-file");
    if (filePath) {
      openInObsidian(filePath);
    }
  }
});

/* ============================================================
 * Toast notification system
 *
 * Shows brief notifications for import results and actions.
 * Toast types: success (green), warning/unsorted (ochre), error (oxblood).
 * Auto-dismiss after TOAST_DURATION_MS.
 * ============================================================ */

var TOAST_DURATION_MS = 4000;
var TOAST_FADE_MS = 200;

/**
 * Ensure the toast container element exists in the DOM.
 *
 * @returns {HTMLElement} The toast container element.
 */
function getToastContainer() {
  var container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    container.setAttribute("aria-live", "polite");
    document.body.appendChild(container);
  }
  return container;
}

/**
 * Show a toast notification.
 *
 * @param {string} message - The message text to display.
 * @param {"success"|"warning"|"error"} type - Toast variant.
 */
function showToast(message, type) {
  var container = getToastContainer();
  var toast = document.createElement("div");
  toast.className = "toast toast--" + (type || "success");
  toast.textContent = message;
  container.appendChild(toast);

  /* Auto-dismiss */
  setTimeout(function () {
    toast.classList.add("toast--dismissing");
    setTimeout(function () {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, TOAST_FADE_MS);
  }, TOAST_DURATION_MS);
}

/**
 * Listen for htmx custom events to trigger toasts.
 * Server can send HX-Trigger response header with toast data.
 * Example header: HX-Trigger: {"showToast": {"message": "...", "type": "success"}}
 */
document.addEventListener("showToast", function (event) {
  if (event.detail && event.detail.message) {
    showToast(event.detail.message, event.detail.type || "success");
  }
});

/* ============================================================
 * Responsive inspector overlay (md breakpoint)
 *
 * At widths < 1280px the inspector is hidden by CSS.
 * When a paper is clicked via htmx, we show the inspector
 * as an overlay and add a backdrop to dismiss it.
 * ============================================================ */

/**
 * After htmx swaps inspector content, show it as overlay on narrow screens.
 */
document.addEventListener("htmx:afterSwap", function (event) {
  if (event.detail.target && event.detail.target.id === "inspector-panel") {
    var inspector = document.getElementById("inspector-panel");
    if (!inspector) return;

    /* Only activate overlay behavior on narrow viewports */
    if (window.innerWidth < 1280) {
      inspector.classList.add("inspector--visible");
      showInspectorBackdrop();
    }
  }
});

/**
 * Show a backdrop behind the inspector overlay; click to dismiss.
 */
function showInspectorBackdrop() {
  var existing = document.getElementById("inspector-backdrop");
  if (existing) {
    existing.classList.add("inspector-backdrop--visible");
    return;
  }

  var backdrop = document.createElement("div");
  backdrop.id = "inspector-backdrop";
  backdrop.className = "inspector-backdrop inspector-backdrop--visible";
  backdrop.addEventListener("click", function () {
    hideInspectorOverlay();
  });
  document.body.appendChild(backdrop);
}

/**
 * Hide the inspector overlay and backdrop.
 */
function hideInspectorOverlay() {
  var inspector = document.getElementById("inspector-panel");
  if (inspector) {
    inspector.classList.remove("inspector--visible");
  }
  var backdrop = document.getElementById("inspector-backdrop");
  if (backdrop) {
    backdrop.classList.remove("inspector-backdrop--visible");
  }
}
