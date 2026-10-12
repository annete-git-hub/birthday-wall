/* =====================================================================
   common.js: helpers shared by every page.
   ===================================================================== */

/**
 * Call the JSON API. Resolves with the parsed body, or throws an Error
 * whose .message is the server's friendly "error" text and whose .status
 * and .data hold the HTTP status and full response body.
 */
async function api(method, url, body) {
  const opts = { method, headers: {}, credentials: "same-origin" };
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(url, opts);
  } catch {
    throw Object.assign(new Error("Could not reach the server. Check your connection and try again."), { status: 0 });
  }

  let data = null;
  try { data = await res.json(); } catch { /* empty or non-JSON body */ }

  if (!res.ok) {
    const err = new Error((data && data.error) || `Request failed (${res.status}).`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

/** Escape text before putting it into innerHTML. Never insert user text without this. */
function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

let toastTimer;
function toast(message) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Fallback for older browsers and non-HTTPS pages
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  toast("Link copied");
}

/** "19 October 2026" from "2026-10-19" without timezone shifting. */
function formatDate(isoDate) {
  const [y, m, d] = String(isoDate).slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}

function formatBytes(n) {
  if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(seconds) {
  const s = Math.round(seconds || 0);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Show a form-level error message inside a form's .form-error element. */
function setFormError(form, message) {
  const el = form.querySelector(".form-error");
  if (el) el.textContent = message || "";
}

// Any button with data-copy-target="elementId" copies that element's text.
document.addEventListener("click", (e) => {
  const copyBtn = e.target.closest("[data-copy-target]");
  if (copyBtn) {
    const target = document.getElementById(copyBtn.dataset.copyTarget);
    if (target) copyText(target.textContent.trim());
  }
  const closeBtn = e.target.closest("[data-close]");
  if (closeBtn) closeBtn.closest("dialog")?.close();
});
