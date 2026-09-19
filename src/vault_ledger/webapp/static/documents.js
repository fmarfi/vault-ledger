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
    row.style.gridTemplateColumns = "2.2fr 1.6fr 110px 130px 1.8fr";
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
    `;
    rowsContainer.appendChild(row);
  });
}

loadDocuments();
