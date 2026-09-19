const loading = document.getElementById("loading");

let ACCOUNTS = [];
let queueItems = []; // last-loaded /api/queue rows -- the single source of
                      // truth for what's rendered; a fresh process or any
                      // confirm/correct/dismiss just refetches this.
let selectedIds = new Set();

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function csvBool(value) {
  // Every field coming back from /api/queue has passed through a CSV
  // round-trip, so booleans arrive as the strings "True"/"False", not
  // real booleans -- normalize once here rather than at every call site.
  return value === "True" || value === true;
}

// Swapped in via <img onerror="handleImgError(this)"> when a queue item's
// filename doesn't resolve to a served sample image (always true for an
// upload, since the temp file isn't kept around for redisplay after a
// refresh) -- an honest placeholder instead of a broken image icon.
function handleImgError(img) {
  const wrap = img.closest(".doc-preview");
  wrap.innerHTML = documentIconHtml();
}

async function loadSamples() {
  const samples = await fetchJson("/api/samples");
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

function setLoading(isLoading) {
  loading.hidden = !isLoading;
}

async function processSample(sample) {
  setLoading(true);
  try {
    await fetchJson("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sample: sample.name }),
    });
    await loadQueue();
  } catch (err) {
    alert("Could not process this document: " + err.message);
  } finally {
    setLoading(false);
  }
}

async function processUpload(file) {
  setLoading(true);
  const formData = new FormData();
  formData.append("document", file);
  try {
    await fetchJson("/api/process", { method: "POST", body: formData });
    await loadQueue();
  } catch (err) {
    alert("Could not process this document: " + err.message);
  } finally {
    setLoading(false);
  }
}

async function loadQueue() {
  queueItems = await fetchJson("/api/queue");
  const liveIds = new Set(queueItems.map((item) => item.id));
  selectedIds.forEach((id) => { if (!liveIds.has(id)) selectedIds.delete(id); });
  renderQueue();
}

function renderQueue() {
  const list = document.getElementById("queue-list");
  // Keep any just-posted cards (their confirmation banner is still on
  // screen) instead of wiping them with the rebuild.
  const posted = Array.from(list.querySelectorAll(".queue-item.is-posted"));
  list.innerHTML = "";
  posted.forEach((card) => list.appendChild(card));
  queueItems.forEach((item) => list.appendChild(renderQueueCard(item)));
  updateQueueMeta();
}

function updateQueueMeta() {
  document.getElementById("queue-empty").hidden = queueItems.length > 0;
  document.getElementById("queue-count").textContent = queueItems.length
    ? `${queueItems.length} pending`
    : "";
  updateBulkToolbar();
}

function showStatus(el, message, isError) {
  el.textContent = message;
  el.className = "status-banner" + (isError ? " is-error" : "");
  el.hidden = false;
}

function renderQueueCard(item) {
  const card = document.createElement("div");
  card.className = "card queue-item";
  card.dataset.id = item.id;

  const needsReview = csvBool(item.needs_review);
  const paid = csvBool(item.paid);
  const confidence = Number(item.confidence);
  const entry = item.entry_json ? JSON.parse(item.entry_json) : null;

  card.innerHTML = `
    <div class="queue-item-header">
      <label class="queue-item-select">
        <input type="checkbox" class="queue-checkbox" ${selectedIds.has(item.id) ? "checked" : ""}>
        <span class="filename small muted">${escapeHtml(item.filename)}</span>
      </label>
      <button class="btn btn-outline dismiss-btn" type="button">Dismiss</button>
    </div>
    <div class="result-grid">
      <div class="doc-preview">
        <img alt="document preview" src="/samples/${encodeURIComponent(item.filename)}" onerror="handleImgError(this)">
      </div>
      <dl class="field-list">
        <dt>Vendor</dt><dd>${escapeHtml(item.vendor)}</dd>
        <dt>Description</dt><dd>${escapeHtml(item.description)}</dd>
        <dt>Date</dt><dd>${escapeHtml(item.date) || "—"}</dd>
        <dt>Amount</dt><dd>${formatCurrency(item.amount)}</dd>
        <dt>Status</dt><dd>${paid ? "Paid" : "Unpaid"}</dd>
      </dl>
    </div>
    <div class="prediction-row">
      <div>
        <div class="predicted-account">${escapeHtml(item.predicted_account)}</div>
        <div>${confidenceGlyphHtml(confidence)}</div>
      </div>
      <div class="badge ${needsReview ? "badge-review" : "badge-ok"}">${needsReview ? "Needs review" : "Auto-suggested"}</div>
    </div>
    <div class="entry-block">${renderEntryHtml(entry, item.rejection_reason)}</div>
    <div class="correction-row">
      <button class="btn btn-primary accept-btn" type="button">Accept as shown</button>
      <select class="account-select"></select>
      <button class="btn btn-secondary correct-btn" type="button">Correct &amp; post</button>
    </div>
    <div class="item-status" hidden></div>
  `;

  const select = card.querySelector(".account-select");
  ACCOUNTS.forEach((account) => {
    const opt = document.createElement("option");
    opt.value = account;
    opt.textContent = account;
    if (account === item.predicted_account) opt.selected = true;
    select.appendChild(opt);
  });

  card.querySelector(".queue-checkbox").addEventListener("change", (e) => {
    if (e.target.checked) selectedIds.add(item.id); else selectedIds.delete(item.id);
    updateBulkToolbar();
  });
  card.querySelector(".dismiss-btn").addEventListener("click", () => dismissItem(item.id));
  card.querySelector(".accept-btn").addEventListener("click", () => confirmItem(item.id, null, card));
  card.querySelector(".correct-btn").addEventListener("click", () => confirmItem(item.id, select.value, card));

  return card;
}

function renderEntryHtml(entry, rejectionReason) {
  if (!entry) {
    return `<div class="error-note">No entry constructed: ${escapeHtml(rejectionReason || "unknown reason")}</div>`;
  }
  const rows = entry.lines.map((line) => `
    <tr>
      <td>${escapeHtml(line.account)}</td>
      <td class="num">${line.debit ? formatCurrency(line.debit) : ""}</td>
      <td class="num">${line.credit ? formatCurrency(line.credit) : ""}</td>
    </tr>
  `).join("");
  return `
    <table class="entry-table">
      <thead><tr><th>Account</th><th>Debit</th><th>Credit</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="muted small">Debits ${formatCurrency(entry.total_debits)} = Credits ${formatCurrency(entry.total_credits)}</div>
  `;
}

function setCardBusy(card, busyBtn, label) {
  card.querySelectorAll("button, select, input").forEach((el) => { el.disabled = true; });
  busyBtn.dataset.label = busyBtn.textContent;
  busyBtn.textContent = label;
  busyBtn.classList.add("is-busy");
}

function clearCardBusy(card, busyBtn) {
  card.querySelectorAll("button, select, input").forEach((el) => { el.disabled = false; });
  busyBtn.textContent = busyBtn.dataset.label;
  busyBtn.classList.remove("is-busy");
}

function postedBannerEl(message) {
  const banner = document.createElement("div");
  banner.className = "posted-banner";
  banner.setAttribute("role", "status");
  banner.innerHTML = '<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="9" fill="var(--color-on-ink)"/><path d="M6 10.3L8.3 12.8L14 7" stroke="var(--color-ink)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const text = document.createElement("span");
  text.textContent = message;
  const link = document.createElement("a");
  link.href = "/ledger";
  link.textContent = "View in ledger";
  banner.append(text, link);
  return banner;
}

// Hold the confirmation on screen long enough to read, then collapse only
// this card -- the other cards keep their state (e.g. a half-chosen
// correction) instead of being rebuilt from a fresh fetch.
function collapseCardAfterDelay(card, delayMs = 2200) {
  setTimeout(() => {
    card.style.maxHeight = card.offsetHeight + "px";
    void card.offsetHeight;
    card.classList.add("is-leaving");
    setTimeout(() => card.remove(), 400);
  }, delayMs);
}

async function confirmItem(id, correctedAccount, card) {
  const item = queueItems.find((row) => row.id === id);
  const status = card.querySelector(".item-status");
  const busyBtn = card.querySelector(correctedAccount ? ".correct-btn" : ".accept-btn");
  status.hidden = true;
  setCardBusy(card, busyBtn, correctedAccount ? "Saving…" : "Posting…");

  try {
    const endpoint = correctedAccount ? "/api/correct" : "/api/confirm";
    const body = correctedAccount ? { id, corrected_account: correctedAccount } : { id };
    await fetchJson(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    clearCardBusy(card, busyBtn);
    showStatus(status, "Could not post: " + err.message, true);
    return;
  }

  const account = correctedAccount || item.predicted_account;
  const wasCorrection = Boolean(correctedAccount) && correctedAccount !== item.predicted_account;
  const message = wasCorrection
    ? `Posted to ${account} · correction logged for training`
    : `Posted to ${account}`;

  selectedIds.delete(id);
  queueItems = queueItems.filter((row) => row.id !== id);
  card.classList.add("is-posted");
  card.querySelector(".correction-row").replaceWith(postedBannerEl(message));
  status.remove();
  updateQueueMeta();
  collapseCardAfterDelay(card);
}

async function dismissItem(id) {
  try {
    await fetchJson(`/api/queue/${id}`, { method: "DELETE" });
    selectedIds.delete(id);
    await loadQueue();
  } catch (err) {
    alert("Could not dismiss: " + err.message);
  }
}

function updateBulkToolbar() {
  const btn = document.getElementById("bulk-confirm-btn");
  btn.disabled = selectedIds.size === 0;
  btn.textContent = selectedIds.size ? `Confirm selected (${selectedIds.size})` : "Confirm selected";
}

document.getElementById("select-high-confidence-btn").addEventListener("click", () => {
  selectedIds = new Set(
    queueItems.filter((item) => Number(item.confidence) >= CONFIDENCE_THRESHOLD).map((item) => item.id)
  );
  document.querySelectorAll(".queue-item:not(.is-posted)").forEach((card) => {
    card.querySelector(".queue-checkbox").checked = selectedIds.has(card.dataset.id);
  });
  updateBulkToolbar();
});

document.getElementById("bulk-confirm-btn").addEventListener("click", async () => {
  const status = document.getElementById("bulk-status");
  const ids = Array.from(selectedIds);
  if (!ids.length) return;

  const btn = document.getElementById("bulk-confirm-btn");
  btn.disabled = true;
  btn.textContent = `Confirming ${ids.length}…`;
  showStatus(status, `Confirming ${ids.length} document(s)…`, false);
  const setCardsLocked = (locked) =>
    document.querySelectorAll(".queue-item:not(.is-posted) button, .queue-item:not(.is-posted) select, .queue-item:not(.is-posted) input")
      .forEach((el) => { el.disabled = locked; });
  setCardsLocked(true);
  let result;
  try {
    result = await fetchJson("/api/queue/bulk_confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
  } catch (err) {
    setCardsLocked(false);
    showStatus(status, "Bulk confirm failed: " + err.message, true);
    updateBulkToolbar();
    return;
  }

  {
    selectedIds.clear();
    const posted = `✓ Posted ${result.confirmed.length} document(s) to the ledger.`;
    showStatus(
      status,
      result.failed.length
        ? `${posted} ${result.failed.length} failed: ${result.failed.map((f) => f.error).join("; ")}`
        : posted,
      result.failed.length > 0
    );
  }
  try {
    await loadQueue();
  } catch (err) {
    showStatus(status, "Posted, but couldn't refresh the queue — reload the page.", true);
  }
});

document.getElementById("file-input").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  document.querySelectorAll(".sample-btn").forEach((b) => b.classList.remove("active"));
  document.getElementById("upload-filename").textContent = file.name;
  processUpload(file);
});

async function init() {
  ACCOUNTS = await fetchJson("/api/accounts");
  await loadSamples();
  await loadQueue();
}

init();
