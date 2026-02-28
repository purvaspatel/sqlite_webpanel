/* ============================================================
   SQLite Panel — panel.js
   Lightweight vanilla JS. No frameworks.
   ============================================================ */

// ----------------------------------------------------------
// Theme
// ----------------------------------------------------------
(function () {
  const stored = localStorage.getItem("sqlite-panel-theme");
  if (stored) document.documentElement.setAttribute("data-theme", stored);
})();

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute("data-theme") || "light";
  const next = current === "light" ? "dark" : "light";
  html.setAttribute("data-theme", next);
  localStorage.setItem("sqlite-panel-theme", next);
}

// ----------------------------------------------------------
// Toast notifications
// ----------------------------------------------------------
function showToast(msg, type = "info", duration = 3500) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = "toastOut 0.2s ease forwards";
    setTimeout(() => toast.remove(), 200);
  }, duration);
}

// ----------------------------------------------------------
// Expand/collapse long text
// ----------------------------------------------------------
function toggleText(uid) {
  const preview = document.getElementById(`preview-${uid}`);
  const full = document.getElementById(`full-${uid}`);
  if (!preview || !full) return;
  const isHidden = full.style.display === "none";
  preview.style.display = isHidden ? "none" : "";
  full.style.display = isHidden ? "" : "none";
}

// ----------------------------------------------------------
// Page size selector
// ----------------------------------------------------------
function changePageSize(size) {
  const state = window.PANEL_STATE;
  if (!state) return;
  const url = new URL(window.location.href);
  url.searchParams.set("page_size", size);
  url.searchParams.set("page", "1");
  window.location.href = url.toString();
}

// ----------------------------------------------------------
// Column filter modal
// ----------------------------------------------------------
let _filterColName = null;

function openColumnFilter(colName) {
  _filterColName = colName;
  const modal = document.getElementById("col-filter-modal");
  if (!modal) return;

  const input = document.getElementById("col-filter-input");
  const state = window.PANEL_STATE || {};
  input.value = (state.filters && state.filters[colName]) || "";
  modal.style.display = "flex";
  setTimeout(() => input.focus(), 50);
}

function closeColFilter() {
  const modal = document.getElementById("col-filter-modal");
  if (modal) modal.style.display = "none";
  _filterColName = null;
}

function applyColFilter() {
  const input = document.getElementById("col-filter-input");
  if (!input || !_filterColName) return;
  const val = input.value.trim();
  const state = window.PANEL_STATE || {};
  const url = new URL(window.location.href);
  if (val) {
    url.searchParams.set(`filter_${_filterColName}`, val);
  } else {
    url.searchParams.delete(`filter_${_filterColName}`);
  }
  url.searchParams.set("page", "1");
  window.location.href = url.toString();
}

// ----------------------------------------------------------
// Insert modal
// ----------------------------------------------------------
function openInsertModal() {
  const modal = document.getElementById("insert-modal");
  if (modal) modal.style.display = "flex";
}

function closeInsertModal() {
  const modal = document.getElementById("insert-modal");
  if (modal) {
    modal.style.display = "none";
    const form = document.getElementById("insert-form");
    if (form) form.reset();
  }
}

async function submitInsert(tableName) {
  const prefix = window.PANEL_STATE ? window.PANEL_STATE.prefix : "/admin";
  const form = document.getElementById("insert-form");
  if (!form) return;

  const data = new FormData(form);
  try {
    const resp = await fetch(`${prefix}/table/${tableName}/insert`, {
      method: "POST",
      body: data,
    });
    const json = await resp.json();
    if (json.ok) {
      closeInsertModal();
      showToast("Row inserted successfully", "success");
      setTimeout(() => window.location.reload(), 600);
    } else {
      showToast(json.detail || "Insert failed", "error");
    }
  } catch (e) {
    showToast("Network error", "error");
  }
}

// ----------------------------------------------------------
// Delete row
// ----------------------------------------------------------
async function deleteRow(tableName, pkVal, redirect = false) {
  if (!confirm(`Delete row ${pkVal}? This cannot be undone.`)) return;
  const prefix = window.PANEL_STATE ? window.PANEL_STATE.prefix : "/admin";
  try {
    const resp = await fetch(`${prefix}/table/${tableName}/row/${pkVal}/delete`, {
      method: "POST",
    });
    const json = await resp.json();
    if (json.ok) {
      showToast("Row deleted", "success");
      if (redirect) {
        setTimeout(() => {
          window.location.href = `${prefix}/table/${tableName}`;
        }, 600);
      } else {
        // Remove row from DOM
        const rows = document.querySelectorAll(".data-row");
        // Find and fade out the row
        setTimeout(() => window.location.reload(), 600);
      }
    } else {
      showToast(json.detail || "Delete failed", "error");
    }
  } catch (e) {
    showToast("Network error", "error");
  }
}

// ----------------------------------------------------------
// Inline cell editing (double-click)
// ----------------------------------------------------------
let _activeInlineEdit = null;

function startInlineEdit(td, tableName, pkCol, pkVal, colName) {
  // Abort previous edit
  if (_activeInlineEdit) cancelInlineEdit();

  const original = td.innerHTML;
  const currentText = td.textContent.trim();

  const input = document.createElement("input");
  input.type = "text";
  input.value = currentText === "NULL" ? "" : currentText;
  input.className = "inline-edit-input";

  td.innerHTML = "";
  td.appendChild(input);
  input.focus();
  input.select();

  _activeInlineEdit = { td, original, tableName, pkCol, pkVal, colName };

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") confirmInlineEdit(input.value);
    if (e.key === "Escape") cancelInlineEdit();
  });
  input.addEventListener("blur", () => {
    // Give a tick for Enter handler to fire first
    setTimeout(() => {
      if (_activeInlineEdit) cancelInlineEdit();
    }, 100);
  });
}

function cancelInlineEdit() {
  if (!_activeInlineEdit) return;
  const { td, original } = _activeInlineEdit;
  td.innerHTML = original;
  _activeInlineEdit = null;
}

async function confirmInlineEdit(newValue) {
  if (!_activeInlineEdit) return;
  const { tableName, pkCol, pkVal, colName } = _activeInlineEdit;
  const state = _activeInlineEdit;

  const prefix = window.PANEL_STATE ? window.PANEL_STATE.prefix : "/admin";
  const formData = new FormData();
  formData.append(colName, newValue);

  try {
    const resp = await fetch(`${prefix}/table/${tableName}/row/${pkVal}/update`, {
      method: "POST",
      body: formData,
    });
    const json = await resp.json();
    _activeInlineEdit = null;
    if (json.ok) {
      showToast("Saved", "success", 1800);
      setTimeout(() => window.location.reload(), 400);
    } else {
      showToast(json.detail || "Save failed", "error");
    }
  } catch (e) {
    showToast("Network error", "error");
    cancelInlineEdit();
  }
}

// ----------------------------------------------------------
// Row detail page: edit/save
// ----------------------------------------------------------
function toggleEditMode() {
  const views = document.querySelectorAll(".detail-value-view");
  const edits = document.querySelectorAll(".detail-value-edit");
  const actions = document.getElementById("edit-actions");
  views.forEach((el) => (el.style.display = "none"));
  edits.forEach((el) => (el.style.display = ""));
  if (actions) actions.style.display = "flex";
}

function cancelEdit() {
  const views = document.querySelectorAll(".detail-value-view");
  const edits = document.querySelectorAll(".detail-value-edit");
  const actions = document.getElementById("edit-actions");
  views.forEach((el) => (el.style.display = ""));
  edits.forEach((el) => (el.style.display = "none"));
  if (actions) actions.style.display = "none";
}

async function saveRow(tableName, pkVal) {
  const prefix = window.PANEL_STATE ? window.PANEL_STATE.prefix : "/admin";
  const form = document.getElementById("edit-form");
  if (!form) return;
  const data = new FormData(form);
  try {
    const resp = await fetch(`${prefix}/table/${tableName}/row/${pkVal}/update`, {
      method: "POST",
      body: data,
    });
    const json = await resp.json();
    if (json.ok) {
      showToast("Saved", "success");
      setTimeout(() => window.location.reload(), 500);
    } else {
      showToast(json.detail || "Save failed", "error");
    }
  } catch (e) {
    showToast("Network error", "error");
  }
}

// ----------------------------------------------------------
// Auto-refresh / change detection
// ----------------------------------------------------------
(function startPolling() {
  const container = document.getElementById("table-body-container");
  if (!container) return;

  const fingerprintUrl = container.dataset.fingerprintUrl;
  const tableName = container.dataset.table;
  if (!fingerprintUrl || !tableName) return;

  let lastFingerprint = null;
  let pollTimer = null;
  let notified = false;

  async function poll() {
    try {
      const resp = await fetch(fingerprintUrl, { cache: "no-store" });
      if (!resp.ok) return;
      const data = await resp.json();
      const current = JSON.stringify(data);

      if (lastFingerprint === null) {
        lastFingerprint = current;
        return;
      }

      if (current !== lastFingerprint) {
        lastFingerprint = current;
        if (!notified) {
          notified = true;
          const oldCount = JSON.parse(lastFingerprint || "{}")[tableName];
          const newCount = data[tableName];
          const diff = newCount - (oldCount || 0);
          const msg =
            diff > 0
              ? `${diff} new row${diff > 1 ? "s" : ""} in ${tableName}`
              : `${tableName} has changed`;
          showToast(msg + " — refreshing…", "info", 2500);
          setTimeout(() => {
            notified = false;
            // HTMX-style partial reload of the table body
            htmxRefreshTable();
          }, 1500);
        }
      }
    } catch (_) {
      /* silently ignore network errors during polling */
    }
  }

  function htmxRefreshTable() {
    if (typeof htmx === "undefined") {
      window.location.reload();
      return;
    }
    const state = window.PANEL_STATE || {};
    const prefix = state.prefix || "/admin";
    const params = new URLSearchParams({
      page: state.page || 1,
      page_size: state.pageSize || 50,
      sort: state.sort || "",
      dir: state.dir || "asc",
      search: state.search || "",
    });
    if (state.filters) {
      for (const [k, v] of Object.entries(state.filters)) {
        if (v) params.set(`filter_${k}`, v);
      }
    }
    const url = `${prefix}/table/${tableName}/rows?${params}`;
    htmx.ajax("GET", url, { target: "#table-body-container", swap: "innerHTML" });
  }

  // Poll every 5 seconds
  pollTimer = setInterval(poll, 5000);
  poll();
})();

// ----------------------------------------------------------
// Keyboard shortcuts
// ----------------------------------------------------------
document.addEventListener("keydown", (e) => {
  // / → focus search
  if (e.key === "/" && !e.ctrlKey && !e.metaKey) {
    const search = document.querySelector(".search-input");
    if (search && document.activeElement !== search) {
      e.preventDefault();
      search.focus();
    }
  }
  // Escape → close modals
  if (e.key === "Escape") {
    closeInsertModal();
    closeColFilter();
    cancelInlineEdit();
    cancelEdit();
  }
  // N → new row
  if (
    e.key === "n" &&
    !e.ctrlKey &&
    !e.metaKey &&
    document.activeElement.tagName === "BODY"
  ) {
    const btn = document.querySelector(".btn-primary");
    if (btn && btn.onclick) btn.onclick();
  }
});

// Close modals on backdrop click
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("modal-backdrop")) {
    closeInsertModal();
    closeColFilter();
  }
});

// Expose enumerate helper for Jinja2
// (handled server-side — this is a no-op)
