// Documents page. Shows only what's actually been posted to the ledger --
// there's no persistence yet for a document that's been processed but not
// confirmed (that only lives in the Review Queue page's own memory until
// you act on it), so this list is the real, confirmed record, not a
// speculative "everything ever uploaded" view.

function statusGlyphHtml(wasCorrected) {
  // Every row here is a posted (confirmed) entry -- "corrected" vs.
  // "confirmed" describes the journey, not whether it's final.
  return `
    <div style="display:flex;align-items:center;gap:6px;">
      <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="9" fill="var(--color-ink)"/><path d="M6 10.3L8.3 12.8L14 7" stroke="var(--color-on-ink)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      <span class="small">${wasCorrected ? "Corrected" : "Confirmed"}</span>
    </div>
  `;
}

const DOC_COLUMNS = "2.2fr 1.6fr 110px 130px 1.8fr 170px";

// View: the first page as an image under the row. Download: the file as it
// was added (served as an attachment, never opened inside the app).
function addDocumentActions(row, doc) {
  const cell = row.querySelector(".doc-actions");
  if (!doc.has_document || !doc.document_id) {
    cell.innerHTML = '<span class="muted small">Not stored</span>';
    cell.title = "Posted before originals were linked to entries, or demo data.";
    return;
  }
  const id = encodeURIComponent(doc.document_id);
  const view = Object.assign(document.createElement("button"), { type: "button", className: "btn-link small", textContent: "View" });
  const download = Object.assign(document.createElement("a"), { className: "btn-link small", textContent: "Download original", href: `/api/documents/${id}/original` });
  download.setAttribute("download", "");
  view.setAttribute("aria-expanded", "false");
  cell.append(view, " · ", download);

  let panel = null;
  view.addEventListener("click", () => {
    if (!panel) {
      panel = document.createElement("div");
      panel.className = "doc-viewer";
      const img = Object.assign(document.createElement("img"), { alt: `First page of ${doc.filename}`, src: `/api/documents/${id}/preview` });
      img.addEventListener("error", () => { panel.textContent = "This document can't be shown. Try Download original."; });
      img.addEventListener("click", () => panel.classList.toggle("doc-viewer-large"));
      img.title = "Click to enlarge";
      panel.append(img);
      row.after(panel);
    } else {
      panel.hidden = !panel.hidden;
    }
    view.textContent = panel.hidden ? "View" : "Hide";
    view.setAttribute("aria-expanded", String(!panel.hidden));
  });
}

async function loadDocuments() {
  const docs = await fetchJson("/api/documents");
  document.getElementById("doc-count").textContent = docs.length;

  const rowsContainer = document.getElementById("doc-rows");
  const emptyState = document.getElementById("empty-state");

  if (docs.length === 0) {
    emptyState.hidden = false;
    return;
  }

  docs.forEach((doc) => {
    const row = document.createElement("div");
    row.className = "ledger-row";
    row.style.gridTemplateColumns = DOC_COLUMNS;
    const postedDate = new Date(doc.confirmed_at).toLocaleDateString();
    row.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;">
        ${documentIconHtml()}
        <span class="figure small">${escapeHtml(doc.filename)}</span>
      </div>
      <div>${escapeHtml(doc.vendor)}</div>
      <div class="figure small muted">${postedDate}</div>
      <div>${statusGlyphHtml(doc.was_corrected === "True")}</div>
      <div class="small" style="color: var(--color-ink-soft);">${escapeHtml(doc.account)}</div>
      <div class="doc-actions"></div>
    `;
    rowsContainer.appendChild(row);
    addDocumentActions(row, doc);
  });
}

loadDocuments();


async function loadStats() {
  const stats = await fetchJson("/api/stats");
  if (!stats.total) return;

  const pct = (rate) => (rate === null ? "—" : Math.round(rate * 100) + "%");
  const body = document.getElementById("stats-body");
  const caveat = stats.meaningful
    ? ""
    : `<p class="muted small">Only ${stats.total} posted so far — too few to read much into (${stats.min_sample}+ is a fairer sample).</p>`;
  const top = stats.corrected_into.slice(0, 3)
    .map(([account, n]) => `${escapeText(account)} (${n})`).join(", ");

  body.innerHTML = `
    <div style="display:flex;gap:40px;flex-wrap:wrap;margin:8px 0 12px;">
      <div><div class="ledger-total-figure">${pct(stats.first_pass_rate)}</div><div class="muted small">all ${stats.total} posted</div></div>
      <div><div class="ledger-total-figure">${pct(stats.recent_first_pass_rate)}</div><div class="muted small">last ${stats.recent_days} days (${stats.recent_total})</div></div>
    </div>
    ${caveat}
    ${top ? `<p class="muted small">Most often corrected into: ${top}.</p>` : ""}
    <p class="muted small">This counts how often a reviewer accepted the proposal unchanged. It is not a measure of accuracy on new documents.</p>
  `;
  document.getElementById("stats-card").hidden = false;
}

function escapeText(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

loadStats();
