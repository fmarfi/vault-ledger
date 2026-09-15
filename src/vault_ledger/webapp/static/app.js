const resultSection = document.getElementById("result-section");
const loading = document.getElementById("loading");

let currentResult = null; // last /api/process response, used by the correction step

async function loadSamples() {
  const res = await fetch("/api/samples");
  const samples = await res.json();
  const container = document.getElementById("samples");

  samples.forEach((sample) => {
    const btn = document.createElement("button");
    btn.className = "sample-btn";
    btn.textContent = labelFor(sample.format_type);
    btn.addEventListener("click", () => {
      document.querySelectorAll(".sample-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      processSample(sample);
    });
    container.appendChild(btn);
  });
}

function labelFor(formatType) {
  return {
    invoice: "Sample invoice",
    utility_bill: "Sample utility bill",
    receipt: "Sample receipt",
  }[formatType] || formatType;
}

async function loadAccounts() {
  const res = await fetch("/api/accounts");
  const accounts = await res.json();
  const select = document.getElementById("account-select");
  select.innerHTML = "";
  accounts.forEach((account) => {
    const opt = document.createElement("option");
    opt.value = account;
    opt.textContent = account;
    select.appendChild(opt);
  });
}

function setLoading(isLoading) {
  loading.hidden = !isLoading;
  if (isLoading) resultSection.hidden = true;
}

async function processSample(sample) {
  setLoading(true);
  const res = await fetch("/api/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sample: sample.name }),
  });
  await handleProcessResponse(res, sample.image_url);
}

async function processUpload(file) {
  setLoading(true);
  const formData = new FormData();
  formData.append("document", file);
  const res = await fetch("/api/process", { method: "POST", body: formData });
  await handleProcessResponse(res, URL.createObjectURL(file));
}

async function handleProcessResponse(res, imageUrl) {
  setLoading(false);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    alert("Could not process this document: " + (body.error || res.statusText));
    return;
  }
  const result = await res.json();
  currentResult = result;
  renderResult(result, imageUrl);
}

function renderResult(result, imageUrl) {
  document.getElementById("doc-image").src = imageUrl;
  document.getElementById("f-vendor").textContent = result.vendor;
  document.getElementById("f-description").textContent = result.description;
  document.getElementById("f-date").textContent = result.date || "—";
  document.getElementById("f-amount").textContent = formatCurrency(result.amount);
  document.getElementById("f-status").textContent = result.paid ? "Paid" : "Unpaid";

  document.getElementById("predicted-account").textContent = result.predicted_account;
  const pct = Math.round(result.confidence * 100);
  document.getElementById("confidence-bar").style.width = pct + "%";
  document.getElementById("confidence-label").textContent = `${pct}% confidence`;

  const reviewBadge = document.getElementById("review-badge");
  if (result.needs_review) {
    reviewBadge.textContent = "Needs review";
    reviewBadge.className = "badge badge-review";
  } else {
    reviewBadge.textContent = "Auto-suggested";
    reviewBadge.className = "badge badge-ok";
  }

  renderEntry(result.entry, result.rejection_reason);

  document.getElementById("account-select").value = result.predicted_account;
  document.getElementById("correction-status").textContent = "";

  resultSection.hidden = false;
}

function renderEntry(entry, rejectionReason) {
  const body = document.getElementById("entry-body");
  const balanceNote = document.getElementById("balance-check");
  const rejectionNote = document.getElementById("rejection-note");
  body.innerHTML = "";

  if (!entry) {
    balanceNote.textContent = "";
    rejectionNote.hidden = false;
    rejectionNote.textContent = "No entry constructed: " + rejectionReason;
    return;
  }

  rejectionNote.hidden = true;
  entry.lines.forEach((line) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${line.account}</td>
      <td class="num">${line.debit ? formatCurrency(line.debit) : ""}</td>
      <td class="num">${line.credit ? formatCurrency(line.credit) : ""}</td>
    `;
    body.appendChild(row);
  });
  balanceNote.textContent = `Debits ${formatCurrency(entry.total_debits)} = Credits ${formatCurrency(entry.total_credits)}`;
}

function formatCurrency(value) {
  return "$" + Number(value).toFixed(2);
}

document.getElementById("file-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  document.querySelectorAll(".sample-btn").forEach((b) => b.classList.remove("active"));
  document.getElementById("upload-filename").textContent = file.name;
  processUpload(file);
});

document.getElementById("accept-btn").addEventListener("click", () => {
  document.getElementById("correction-status").textContent = "Accepted as shown.";
});

document.getElementById("correct-btn").addEventListener("click", async () => {
  if (!currentResult) return;
  const correctedAccount = document.getElementById("account-select").value;
  const status = document.getElementById("correction-status");
  status.textContent = "Saving correction…";

  const res = await fetch("/api/correct", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      vendor: currentResult.vendor,
      description: currentResult.description,
      predicted_account: currentResult.predicted_account,
      corrected_account: correctedAccount,
      amount: currentResult.amount,
      paid: currentResult.paid,
      date: currentResult.date,
    }),
  });

  const body = await res.json();
  if (!res.ok) {
    status.textContent = "Could not save correction: " + body.error;
    return;
  }

  renderEntry(body.entry, null);
  status.textContent = `Logged correction to corrections.csv (→ ${correctedAccount}).`;
});

loadSamples();
loadAccounts();
