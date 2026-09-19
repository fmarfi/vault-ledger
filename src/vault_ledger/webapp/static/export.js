// Export page. Downloads are plain navigations to endpoints that answer
// with Content-Disposition: attachment, so the browser saves the file and
// this page stays put -- the button state below is the confirmation.

const booksBtn = document.getElementById("export-books-btn");
const auditBtn = document.getElementById("export-audit-btn");

async function loadCounts() {
  let count = 0;
  try {
    ({ count } = await fetchJson("/api/export/summary"));
  } catch (err) {
    document.getElementById("books-count").textContent = "Could not load entry count";
    return;
  }

  const noun = count === 1 ? "entry" : "entries";
  document.getElementById("books-count").textContent = count ? `${count} confirmed ${noun}` : "No entries yet";
  document.getElementById("audit-count").textContent = count ? `${count} ${noun}, full detail` : "No entries yet";
  document.getElementById("export-empty").hidden = count > 0;
  booksBtn.disabled = auditBtn.disabled = count === 0;
}

function startExport(btn, url) {
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Preparing…";
  window.location.href = url;

  setTimeout(() => {
    btn.textContent = "✓ Export started";
    btn.classList.add("btn-done");
  }, 500);
  setTimeout(() => {
    btn.textContent = label;
    btn.classList.remove("btn-done");
    btn.disabled = false;
  }, 3000);
}

booksBtn.addEventListener("click", () => startExport(booksBtn, "/api/export/books"));
auditBtn.addEventListener("click", () => startExport(auditBtn, "/api/export/audit"));

loadCounts();
