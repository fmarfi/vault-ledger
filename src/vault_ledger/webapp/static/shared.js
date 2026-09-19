// Shared helpers used across every page's own script. Keep this the one
// place that knows how to format money or draw the confidence glyph, so
// the pencil/ink treatment can't drift out of sync between pages.

function formatCurrency(value) {
  return "$" + Number(value).toFixed(2);
}

// Single source of truth for what counts as "high confidence" -- used by
// the glyph below and by the review queue's bulk-select-by-confidence
// action, so the two can't silently drift apart.
const CONFIDENCE_THRESHOLD = 0.6;

// Ink (solid, filled) = high confidence. Pencil (dashed outline) = low.
// The percentage renders but stays hidden until hover via .confidence-pct
// (see style.css) -- secondary info, not the primary cue.
function confidenceGlyphHtml(confidence, threshold = CONFIDENCE_THRESHOLD) {
  const isLow = confidence < threshold;
  const word = isLow ? "Uncertain" : "Matched";
  const pct = Math.round(confidence * 100) + "%";
  const glyph = isLow
    ? '<svg class="confidence-glyph" width="18" height="18" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8.3" stroke="var(--color-pencil)" stroke-width="1.3" stroke-dasharray="2.3 2.3"/></svg>'
    : '<svg class="confidence-glyph" width="18" height="18" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="9" fill="var(--color-ink)"/><path d="M6 10.3L8.3 12.8L14 7" stroke="var(--color-on-ink)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  return `
    <div class="confidence-row">
      ${glyph}
      <span class="confidence-word">${word}</span>
      <span class="confidence-pct figure">${pct}</span>
    </div>
  `;
}

function documentIconHtml() {
  return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="flex-shrink:0"><rect x="4" y="2" width="16" height="20" rx="1" stroke="var(--color-pencil)" stroke-width="1.3"/><path d="M8 8h8M8 12h8M8 16h5" stroke="var(--color-pencil)" stroke-width="1.3" stroke-linecap="round"/></svg>';
}

// Everything rendered via innerHTML that came from OCR'd documents or upload
// filenames must go through this -- a crafted PDF is untrusted input.
function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function csrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.content : "";
}

// Every state-changing request carries the per-session CSRF token; the server
// rejects it with 403 otherwise. 401 means the session ended -> sign in again.
async function fetchJson(url, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = Object.assign({}, options.headers || {});
  if (method !== "GET" && method !== "HEAD") headers["X-CSRF-Token"] = csrfToken();
  const res = await fetch(url, Object.assign({}, options, { headers, credentials: "same-origin" }));
  const body = await res.json().catch(() => ({}));
  if (res.status === 401) {
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname + window.location.search);
    }
    throw new Error("Your session has ended. Please sign in again.");
  }
  if (!res.ok) {
    if (res.status === 403) throw new Error("This page is out of date or your session expired. Reload the page and try again.");
    if (res.status === 429) throw new Error("Too many requests. Please wait a moment and try again.");
    if (res.status === 413) throw new Error(body.error || "That file is too large.");
    throw new Error(body.error || res.statusText);
  }
  return body;
}


// Hardware preflight: warn (once per tab session) when this machine is
// below the recommended spec, on every page. Silent when everything is fine.
async function showHardwareBannerIfNeeded() {
  try {
    if (sessionStorage.getItem("hardware-banner-dismissed")) return;
    const { hardware } = await fetchJson("/api/health");
    if (hardware.level !== "low" && hardware.level !== "critical") return;

    const banner = document.getElementById("hardware-banner");
    banner.className = "hardware-banner hardware-" + hardware.level;
    const text = document.createElement("span");
    text.textContent = hardware.message;
    banner.appendChild(text);
    const dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.className = "btn btn-outline";
    dismiss.textContent = "Dismiss";
    dismiss.addEventListener("click", () => {
      banner.hidden = true;
      try { sessionStorage.setItem("hardware-banner-dismissed", "1"); } catch (e) {}
    });
    banner.appendChild(dismiss);
    banner.hidden = false;
  } catch (e) { /* preflight is advisory; never block the page */ }
}
if (document.body.dataset.auth === "1") showHardwareBannerIfNeeded();
