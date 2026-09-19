let ledgerData = {}; // { account: { total, entries } }
let activeAccount = null;

async function loadLedger() {
  ledgerData = await fetchJson("/api/ledger");
  const names = Object.keys(ledgerData);

  if (names.length === 0) {
    document.getElementById("empty-state").hidden = false;
    document.getElementById("ledger-table-wrap").hidden = true;
    return;
  }

  activeAccount = names[0];
  renderTabs(names);
  renderAccount(activeAccount);
}

function renderTabs(names) {
  const container = document.getElementById("account-tabs");
  container.innerHTML = "";
  names.forEach((name) => {
    const btn = document.createElement("button");
    btn.className = "account-tab" + (name === activeAccount ? " active" : "");
    btn.innerHTML = `
      <div class="tab-name">${escapeHtml(name)}</div>
      <div class="tab-total">${formatCurrency(ledgerData[name].total)}</div>
    `;
    btn.addEventListener("click", () => {
      activeAccount = name;
      document.querySelectorAll(".account-tab").forEach((t) => t.classList.remove("active"));
      btn.classList.add("active");
      renderAccount(name);
    });
    container.appendChild(btn);
  });
}

function renderAccount(name) {
  const data = ledgerData[name];
  document.getElementById("active-account-name").textContent = name;
  document.getElementById("active-total").textContent = formatCurrency(data.total);
  document.getElementById("active-count").textContent =
    `across ${data.entries.length} entr${data.entries.length === 1 ? "y" : "ies"}`;

  const rowsContainer = document.getElementById("account-rows");
  rowsContainer.innerHTML = "";
  document.getElementById("ledger-table-wrap").hidden = false;
  document.getElementById("empty-state").hidden = true;

  data.entries.forEach((entry) => {
    const row = document.createElement("div");
    row.className = "ledger-row";
    row.style.gridTemplateColumns = "110px 2fr 2fr 100px";
    row.innerHTML = `
      <div class="figure small muted">${escapeHtml(entry.date) || "—"}</div>
      <div style="font-weight: 500; font-size: 13.5px;">${escapeHtml(entry.vendor)}</div>
      <div class="small" style="color: var(--color-ink-soft);">${escapeHtml(entry.description)}</div>
      <div class="figure ledger-num">${formatCurrency(entry.amount)}</div>
    `;
    rowsContainer.appendChild(row);
  });
}

loadLedger();
