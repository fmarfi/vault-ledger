let accountState = null;

function setStatus(id, text, isError = false) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.classList.toggle("status-error", isError);
}

async function postJson(url, body) {
  return fetchJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function loadAccounts() {
  accountState = await fetchJson("/api/accounts/manage");
  renderAccounts();
}

function renderAccounts() {
  const active = document.getElementById("active-accounts");
  const retired = document.getElementById("retired-accounts");
  active.innerHTML = "";
  retired.innerHTML = "";

  accountState.active.forEach((name) => {
    const row = document.createElement("div");
    row.className = "settings-account-row";
    const label = document.createElement("span");
    label.textContent = name;
    row.appendChild(label);
    if (name === accountState.protected) {
      const note = document.createElement("span");
      note.className = "muted small";
      note.textContent = "fallback — always on";
      row.appendChild(note);
    } else {
      const btn = document.createElement("button");
      btn.className = "btn btn-outline";
      btn.type = "button";
      btn.textContent = "Retire";
      btn.addEventListener("click", () => mutate("/api/accounts/retire", { name }, `Retired ${name}.`));
      row.appendChild(btn);
    }
    active.appendChild(row);
  });

  if (!accountState.retired.length) {
    retired.innerHTML = '<div class="muted small">Nothing retired.</div>';
  }
  accountState.retired.forEach((name) => {
    const row = document.createElement("div");
    row.className = "settings-account-row";
    const label = document.createElement("span");
    label.className = "muted";
    label.textContent = name;
    const btn = document.createElement("button");
    btn.className = "btn btn-outline";
    btn.type = "button";
    btn.textContent = "Restore";
    btn.addEventListener("click", () => mutate("/api/accounts/add", { name }, `Restored ${name}.`));
    row.appendChild(label);
    row.appendChild(btn);
    retired.appendChild(row);
  });

  const select = document.getElementById("template-select");
  if (!select.options.length) {
    const labels = { default: "Default (7 accounts)", "generic-us": "Generic US", "generic-eu": "Generic EU" };
    Object.keys(accountState.templates).forEach((key) => {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = labels[key] || key;
      select.appendChild(opt);
    });
  }
}

async function mutate(url, body, okMessage) {
  try {
    accountState = await postJson(url, body);
    renderAccounts();
    setStatus("accounts-status", okMessage);
  } catch (err) {
    setStatus("accounts-status", err.message, true);
  }
}

document.getElementById("add-account-btn").addEventListener("click", async () => {
  const input = document.getElementById("new-account-input");
  await mutate("/api/accounts/add", { name: input.value }, `Added ${input.value.trim()}. It has no suggestions yet — correct a few documents into it to teach the model.`);
  if (!document.getElementById("accounts-status").classList.contains("status-error")) input.value = "";
});

document.getElementById("template-apply-btn").addEventListener("click", () => {
  const key = document.getElementById("template-select").value;
  if (!confirm("Switch to this template? Accounts not in it are retired (not deleted), and past entries keep their accounts.")) return;
  mutate("/api/accounts/template", { template: key }, "Template applied.");
});

document.getElementById("restore-btn").addEventListener("click", async () => {
  const file = document.getElementById("restore-input").files[0];
  if (!file) return setStatus("backup-status", "Choose a backup file first.", true);
  if (!confirm("Replace the current data with this backup? A safety copy of the current data is saved first.")) return;
  const form = new FormData();
  form.append("backup", file);
  try {
    const result = await fetchJson("/api/restore", { method: "POST", body: form });
    setStatus("backup-status", `Restored ${result.restored.join(", ")}. Safety copy: ${result.safety_copy}.`);
    loadAccounts();
  } catch (err) {
    setStatus("backup-status", err.message, true);
  }
});

loadAccounts();

// ---- reading documents: day/month order for ambiguous dates ----
async function loadPreferences() {
  const select = document.getElementById("date-order-select");
  try {
    select.value = (await fetchJson("/api/preferences")).date_order;
  } catch (err) {
    setStatus("reading-status", err.message, true);
  }
}

document.getElementById("date-order-select").addEventListener("change", async (e) => {
  try {
    await postJson("/api/preferences", { date_order: e.target.value });
    setStatus("reading-status", "Saved. Applies to documents processed from now on.");
  } catch (err) {
    setStatus("reading-status", err.message, true);
  }
});

loadPreferences();
