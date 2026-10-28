const loading = document.getElementById("loading");

let ACCOUNTS = [];
let queueItems = []; // last-loaded /api/queue rows -- the single source of
                      // truth for what's rendered; a fresh process or any
                      // confirm/correct/dismiss just refetches this.
let selectedIds = new Set();

function csvBool(value) {
  // Every field coming back from /api/queue has passed through a CSV
  // round-trip, so booleans arrive as the strings "True"/"False", not
  // real booleans -- normalize once here rather than at every call site.
  return value === "True" || value === true;
}

// Swapped in via <img onerror="handleImgError(this)"> when a queue item has
// no document to show (an upload queued before documents were kept, or a
// file that can't be rendered) -- an honest placeholder instead of a broken
// image icon.
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

// One or more files (the file picker, or dropped on the page): processed one
// at a time through the same /api/process as a single upload.
const ACCEPTED_FILE = /\.(pdf|png|jpe?g|tiff?|bmp|gif|webp)$/i;

async function processFiles(files) {
  const status = document.getElementById("upload-status");
  status.hidden = true;
  const accepted = files.filter((f) => ACCEPTED_FILE.test(f.name) || f.type.startsWith("image/") || f.type === "application/pdf");
  const skipped = files.length - accepted.length;
  const failed = [];
  setLoading(true);
  try {
    for (let i = 0; i < accepted.length; i++) {
      const file = accepted[i];
      loading.textContent = accepted.length > 1
        ? `Processing ${i + 1} of ${accepted.length}: ${file.name}…`
        : `Processing ${file.name}…`;
      const formData = new FormData();
      formData.append("document", file);
      try {
        await fetchJson("/api/process", { method: "POST", body: formData });
        await loadQueue();
      } catch (err) {
        failed.push(`${file.name}: ${err.message}`);
      }
    }
  } finally {
    setLoading(false);
    loading.textContent = "Processing…";
  }
  const notes = [];
  if (failed.length) notes.push(`Could not process ${failed.length}: ${failed.join("; ")}`);
  if (skipped) notes.push(`${skipped} file(s) skipped: only PDF and image files can be processed.`);
  if (notes.length) showStatus(status, notes.join(" "), true);
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
  // screen) instead of wiping them with the rebuild, and any card being
  // edited, so a refresh never throws away half-typed corrections.
  const posted = Array.from(list.querySelectorAll(".queue-item.is-posted"));
  const editing = new Map(
    Array.from(list.querySelectorAll(".queue-item.is-editing")).map((card) => [card.dataset.id, card])
  );
  list.innerHTML = "";
  posted.forEach((card) => list.appendChild(card));
  queueItems.forEach((item) => list.appendChild(editing.get(item.id) || renderQueueCard(item)));
  updateQueueMeta();
}

function updateQueueMeta() {
  document.getElementById("queue-empty").hidden = queueItems.length > 0;
  document.getElementById("queue-count").textContent = queueItems.length
    ? `${queueItems.length} pending`
    : "";
  applyQueueFilter();
  updateBulkToolbar();
}

// ---- search + filter chips (client-side only) -------------------------------

let queueFilter = "all";

function isFlagged(item) {
  return csvBool(item.needs_review) || Boolean(item.rejection_reason);
}

const FILTERS = {
  all: () => true,
  review: (item) => isFlagged(item),
  ready: (item) => !isFlagged(item) && !item.possible_duplicate,
  duplicate: (item) => Boolean(item.possible_duplicate),
};

function matchesSearch(item, query) {
  if (!query) return true;
  return [item.vendor, item.description, item.filename, item.date, item.amount, item.predicted_account]
    .join(" ").toLowerCase().includes(query);
}

function applyQueueFilter() {
  const query = document.getElementById("queue-search").value.trim().toLowerCase();
  const byId = new Map(queueItems.map((item) => [item.id, item]));
  let shown = 0;
  document.querySelectorAll("#queue-list .queue-item:not(.is-posted)").forEach((card) => {
    const item = byId.get(card.dataset.id);
    // A card being edited stays visible whatever the filter says.
    const visible = card.classList.contains("is-editing")
      || (item && FILTERS[queueFilter](item) && matchesSearch(item, query));
    card.hidden = !visible;
    if (visible) shown++;
  });
  document.querySelectorAll(".filter-chip").forEach((chip) => {
    const name = chip.dataset.filter;
    chip.setAttribute("aria-pressed", String(name === queueFilter));
    chip.querySelector(".filter-count").textContent = queueItems.filter(FILTERS[name]).length;
  });
  document.getElementById("queue-no-match").hidden = shown > 0 || queueItems.length === 0;
}

document.querySelectorAll(".filter-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    queueFilter = chip.dataset.filter;
    applyQueueFilter();
  });
});
document.getElementById("queue-search").addEventListener("input", applyQueueFilter);

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
  let entry = null;
  try { entry = item.entry_json ? JSON.parse(item.entry_json) : null; } catch (_) { entry = null; }

  card.innerHTML = `
    <div class="queue-item-header">
      <label class="queue-item-select">
        <input type="checkbox" class="queue-checkbox" ${selectedIds.has(item.id) ? "checked" : ""}>
        <span class="filename small muted">${escapeHtml(item.filename)}</span>
      </label>
      <div class="queue-item-actions">
        <button class="btn btn-outline edit-btn" type="button">Edit details</button>
        <button class="btn btn-outline dismiss-btn" type="button">Dismiss</button>
      </div>
    </div>
    ${duplicateNoteHtml(item)}
    <div class="result-grid">
      <div class="doc-preview">
        <img alt="document preview" title="Click to enlarge" src="/api/queue/${encodeURIComponent(item.id)}/document" onerror="handleImgError(this)" onclick="this.closest('.result-grid').classList.toggle('doc-enlarged')">
      </div>
      <dl class="field-list">
        <dt>Vendor</dt><dd>${escapeHtml(item.vendor)}</dd>
        <dt>Description</dt><dd>${escapeHtml(item.description)}</dd>
        <dt>Date</dt><dd>${dateCellHtml(item)}</dd>
        <dt>Amount</dt><dd>${formatCurrency(item.amount)}</dd>
        <dt>Status</dt><dd>${paid ? "Paid" : "Unpaid"}</dd>
      </dl>
    </div>
    <div class="prediction-row">
      <div>
        <div class="predicted-account">${escapeHtml(item.predicted_account)}</div>
        <div>${confidenceGlyphHtml(confidence)}</div>
        ${decidedByHtml(item.decided_by)}
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
  fillAccountSelect(select, draftAccounts.get(item.id) || item.predicted_account);

  card.querySelector(".queue-checkbox").addEventListener("change", (e) => {
    if (e.target.checked) selectedIds.add(item.id); else selectedIds.delete(item.id);
    updateBulkToolbar();
  });
  card.querySelector(".dismiss-btn").addEventListener("click", () => dismissItem(item.id));
  card.querySelector(".edit-btn").addEventListener("click", () => startEditing(card, item));
  card.querySelector(".accept-btn").addEventListener("click", () => confirmItem(item.id, null, card));
  card.querySelector(".correct-btn").addEventListener("click", () => confirmItem(item.id, select.value, card));
  select.addEventListener("change", () => draftAccounts.set(item.id, select.value));

  return card;
}

function fillAccountSelect(select, chosen) {
  ACCOUNTS.forEach((account) => {
    const opt = document.createElement("option");
    opt.value = account;
    opt.textContent = account;
    if (account === chosen) opt.selected = true;
    select.appendChild(opt);
  });
}

function duplicateNoteHtml(item) {
  const match = item.possible_duplicate ? item.duplicate_of : null;
  if (!match) return '<div class="duplicate-note" hidden></div>';
  return `<div class="duplicate-note" role="note">${duplicateText(match)}</div>`;
}

function duplicateText(match) {
  const where = match.source === "ledger" ? "already in the ledger" : "also in the review queue";
  return `<strong>Possible duplicate</strong> · same vendor, amount and date as
    <span class="filename">${escapeHtml(match.filename || "another document")}</span> (${where}).
    Check before posting; bulk confirm skips it.`;
}

function decidedByHtml(decidedBy) {
  return decidedBy ? `<div class="decided-by muted small">decided by ${escapeHtml(decidedBy)}</div>` : "";
}

// ---- edit details before posting -------------------------------------------
// The field list becomes inputs; every change asks /preview what the
// classifier and the rules make of the edited fields. The journal lines are
// never edited by hand: the server builds them (construct_entry).

// Account the reviewer picked on a card, kept across a re-render (Save draft
// re-runs the model and stores its suggestion, not this choice).
const draftAccounts = new Map();
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const PREVIEW_DELAY_MS = 300;

// Dates are stored as YYYY-MM-DD; `date_written` is how the document wrote
// it. `date_assumed` means the day/month order came from the setting, not
// from the document, so the reviewer is asked to check it.
function longDate(iso) {
  if (!ISO_DATE.test(iso || "")) return iso || "";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}

// The other reading of an ambiguous date (day and month swapped), or "".
function swappedDate(iso) {
  if (!ISO_DATE.test(iso || "")) return "";
  const [y, m, d] = iso.split("-");
  return Number(d) <= 12 && d !== m ? `${y}-${d}-${m}` : "";
}

function dateCellHtml(item) {
  if (!item.date) return "—";
  const written = item.date_written && item.date_written !== item.date
    ? `<div class="muted small">On the document: ${escapeHtml(item.date_written)}</div>` : "";
  const assumed = csvBool(item.date_assumed)
    ? `<div class="date-assumed small">Day/month order assumed — open Edit details to check</div>` : "";
  return `${escapeHtml(longDate(item.date))}${written}${assumed}`;
}

function dateNoteHtml(item) {
  const written = item.date_written || "";
  if (csvBool(item.date_assumed) && ISO_DATE.test(item.date || "")) {
    const other = swappedDate(item.date);
    return `<div class="date-assumed small">On the document: ${escapeHtml(written)}, read as
      <strong>${escapeHtml(longDate(item.date))}</strong> (from your date-order setting).
      ${other ? `<button type="button" class="btn-link date-switch">Use ${escapeHtml(longDate(other))}</button> ·` : ""}
      <button type="button" class="btn-link date-keep">Looks right</button></div>`;
  }
  if (written && written !== item.date) {
    return `<div class="muted small">On the document: ${escapeHtml(written)}</div>`;
  }
  return "";
}

function startEditing(card, item) {
  card.classList.add("is-editing");
  const paid = csvBool(item.paid);
  const storedDate = item.date || "";
  const dateIsIso = ISO_DATE.test(storedDate);
  const dateAssumed = csvBool(item.date_assumed);
  const uid = "edit-" + item.id;
  const form = document.createElement("form");
  form.className = "edit-form";
  form.noValidate = true;
  form.innerHTML = `
    <label for="${uid}-vendor">Vendor</label>
    <input id="${uid}-vendor" class="text-input" name="vendor" maxlength="200" autocomplete="off">
    <label for="${uid}-description">Description</label>
    <textarea id="${uid}-description" class="text-input" name="description" maxlength="1000" rows="2"></textarea>
    <label for="${uid}-date">Date</label>
    <div>
      <input id="${uid}-date" class="text-input" name="date" type="date">
      ${!dateIsIso && storedDate ? `<div class="muted small">On the document: ${escapeHtml(storedDate)} — pick the date to replace it, or leave it as read.</div>` : dateNoteHtml(item)}
    </div>
    <label for="${uid}-amount">Amount</label>
    <input id="${uid}-amount" class="text-input figure" name="amount" type="number" step="0.01" min="0.01" inputmode="decimal">
    <span id="${uid}-paid-label">Status</span>
    <div class="paid-toggle" role="radiogroup" aria-labelledby="${uid}-paid-label">
      <label><input type="radio" name="paid" value="true" ${paid ? "checked" : ""}> Paid</label>
      <label><input type="radio" name="paid" value="false" ${paid ? "" : "checked"}> Unpaid</label>
    </div>
  `;
  // Values set as properties, never through HTML: they came from OCR.
  form.elements.vendor.value = item.vendor || "";
  form.elements.description.value = item.description || "";
  form.elements.date.value = dateIsIso ? storedDate : "";
  form.elements.amount.value = Number.isFinite(Number(item.amount)) ? Number(item.amount).toFixed(2) : "";
  card.querySelector(".field-list").replaceWith(form);

  const select = card.querySelector(".account-select");
  const state = {
    item, form, select, seq: 0, timer: null, suggestion: item.predicted_account,
    // An assumed date is only sent once the reviewer confirmed or changed it.
    dateTouched: dateIsIso && !dateAssumed, accountPicked: draftAccounts.has(item.id),
  };

  card.querySelector(".prediction-row").innerHTML = `
    <div>
      <div class="muted small">Model suggests</div>
      <div class="predicted-account suggestion-account"></div>
      <div class="suggestion-confidence"></div>
      <div class="suggestion-decided-by"></div>
    </div>
    <div class="suggestion-note" hidden></div>
  `;
  renderSuggestion(card, state, {
    predicted_account: item.predicted_account,
    confidence: Number(item.confidence),
    decided_by: item.decided_by,
  });

  const actions = document.createElement("div");
  actions.className = "correction-row edit-actions";
  actions.innerHTML = `
    <label class="muted small" for="${uid}-account">Post to</label>
    <button class="btn btn-primary post-btn" type="button">Post</button>
    <button class="btn btn-secondary save-btn" type="button">Save draft</button>
    <button class="btn btn-outline cancel-btn" type="button">Cancel</button>
    <span class="key-hints muted small" aria-hidden="true">
      <kbd>Enter</kbd> refresh · <kbd>Ctrl</kbd>+<kbd>S</kbd> save draft · <kbd>Ctrl</kbd>+<kbd>Enter</kbd> post · <kbd>Esc</kbd> cancel
    </span>
  `;
  select.id = `${uid}-account`;
  actions.insertBefore(select, actions.querySelector(".post-btn"));
  card.querySelector(".correction-row:not(.edit-actions)").replaceWith(actions);
  card.querySelector(".edit-btn").hidden = true;
  card.setAttribute("aria-keyshortcuts", "Control+S Control+Enter Escape");

  const settleDate = (note) => {
    state.dateTouched = true;
    if (note) note.replaceWith(Object.assign(document.createElement("div"), { className: "muted small", textContent: "Date checked." }));
    schedulePreview(card, state);
  };
  form.querySelector(".date-switch")?.addEventListener("click", (e) => {
    form.elements.date.value = swappedDate(form.elements.date.value) || form.elements.date.value;
    settleDate(e.target.closest(".date-assumed"));
  });
  form.querySelector(".date-keep")?.addEventListener("click", (e) => settleDate(e.target.closest(".date-assumed")));

  form.addEventListener("input", (e) => {
    if (e.target.name === "date") state.dateTouched = true;
    schedulePreview(card, state);
  });
  form.addEventListener("submit", (e) => { e.preventDefault(); previewNow(card, state); });
  select.addEventListener("change", () => {
    state.accountPicked = true;
    draftAccounts.set(item.id, select.value);
    previewNow(card, state);
  });
  actions.querySelector(".post-btn").addEventListener("click", () => postEdited(card, state));
  actions.querySelector(".save-btn").addEventListener("click", () => saveDraft(card, state));
  actions.querySelector(".cancel-btn").addEventListener("click", () => cancelEditing(card, state));
  card.addEventListener("keydown", (e) => onEditKey(e, card, state));

  form.elements.vendor.focus();
  previewNow(card, state);
}

function onEditKey(e, card, state) {
  if (!card.classList.contains("is-editing") || card.classList.contains("is-busy-card")) return;
  if (e.key === "Escape") {
    e.preventDefault();
    cancelEditing(card, state);
  } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    postEdited(card, state);
  } else if ((e.key === "s" || e.key === "S") && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    saveDraft(card, state);
  } else if (e.key === "Enter" && e.target.tagName === "INPUT" && e.target.type !== "radio") {
    e.preventDefault();
    previewNow(card, state);
  }
}

// The edited fields as the server expects them. The date is only sent once
// the reviewer touched it, so a date the picker cannot show (`14 maart
// 2026`) is kept as read instead of being wiped.
function editedFields(state) {
  const f = state.form.elements;
  const fields = {
    vendor: f.vendor.value,
    description: f.description.value,
    amount: f.amount.value,
    paid: f.paid.value === "true",
  };
  if (state.dateTouched) fields.date = f.date.value;
  return fields;
}

function schedulePreview(card, state) {
  clearTimeout(state.timer);
  state.timer = setTimeout(() => previewNow(card, state), PREVIEW_DELAY_MS);
}

async function previewNow(card, state) {
  clearTimeout(state.timer);
  const seq = ++state.seq;
  const status = card.querySelector(".item-status");
  let result;
  try {
    result = await fetchJson(`/api/queue/${encodeURIComponent(state.item.id)}/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign(editedFields(state), { account: state.select.value })),
    });
  } catch (err) {
    if (seq !== state.seq) return;
    showStatus(status, err.message, true);
    card.querySelector(".entry-block").classList.add("is-stale");
    return;
  }
  if (seq !== state.seq || !card.classList.contains("is-editing")) return; // a newer edit is on its way
  status.hidden = true;
  const block = card.querySelector(".entry-block");
  block.classList.remove("is-stale");
  block.innerHTML = renderEntryHtml(result.entry, result.rejection_reason);
  renderSuggestion(card, state, result);
  const dup = card.querySelector(".duplicate-note");
  dup.hidden = !result.possible_duplicate;
  dup.innerHTML = result.possible_duplicate ? duplicateText(result.duplicate_of) : "";
}

// Shows the model's suggestion for the edited fields. It never changes the
// account select by itself; if they differ the reviewer gets "Use it".
function renderSuggestion(card, state, result) {
  state.suggestion = result.predicted_account;
  card.querySelector(".suggestion-account").textContent = result.predicted_account;
  card.querySelector(".suggestion-confidence").innerHTML = confidenceGlyphHtml(Number(result.confidence));
  card.querySelector(".suggestion-decided-by").innerHTML = decidedByHtml(result.decided_by);
  const note = card.querySelector(".suggestion-note");
  if (state.select.value === result.predicted_account) {
    note.hidden = true;
    note.innerHTML = "";
    return;
  }
  note.innerHTML = `
    <span>Model now suggests <strong>${escapeHtml(result.predicted_account)}</strong>
    · <span class="figure">${Math.round(Number(result.confidence) * 100)}%</span></span>
    <button class="btn btn-outline use-suggestion-btn" type="button">Use it</button>
  `;
  note.hidden = false;
  note.querySelector(".use-suggestion-btn").addEventListener("click", () => {
    state.select.value = result.predicted_account;
    state.accountPicked = false;
    draftAccounts.delete(state.item.id);
    previewNow(card, state);
  });
}

function cancelEditing(card, state) {
  clearTimeout(state.timer);
  state.seq++;
  card.classList.remove("is-editing");
  const item = queueItems.find((row) => row.id === state.item.id) || state.item;
  const fresh = renderQueueCard(item);
  card.replaceWith(fresh);
  applyQueueFilter();
  const editBtn = fresh.querySelector(".edit-btn");
  if (editBtn) editBtn.focus();
}

async function saveDraft(card, state) {
  clearTimeout(state.timer);
  state.seq++; // drop any preview still in flight
  const status = card.querySelector(".item-status");
  const btn = card.querySelector(".save-btn");
  status.hidden = true;
  setCardBusy(card, btn, "Saving…");
  try {
    await fetchJson(`/api/queue/${encodeURIComponent(state.item.id)}/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(editedFields(state)),
    });
  } catch (err) {
    clearCardBusy(card, btn);
    showStatus(status, "Could not save: " + err.message, true);
    return;
  }
  if (state.accountPicked) draftAccounts.set(state.item.id, state.select.value);
  card.classList.remove("is-editing");
  try {
    await loadQueue(); // re-renders this card from the saved row
  } catch (err) {
    showStatus(status, "Saved, but couldn't refresh the queue — reload the page.", true);
    return;
  }
  const saved = document.querySelector(`.queue-item[data-id="${CSS.escape(state.item.id)}"] .item-status`);
  if (saved) showStatus(saved, "Draft saved. Still in the queue until it is posted.", false);
}

async function postEdited(card, state) {
  clearTimeout(state.timer);
  state.seq++;
  await confirmItem(state.item.id, state.select.value, card, editedFields(state), state.suggestion);
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
  card.classList.add("is-busy-card");
  card.querySelectorAll("button, select, input, textarea").forEach((el) => { el.disabled = true; });
  busyBtn.dataset.label = busyBtn.textContent;
  busyBtn.textContent = label;
  busyBtn.classList.add("is-busy");
}

function clearCardBusy(card, busyBtn) {
  card.classList.remove("is-busy-card");
  card.querySelectorAll("button, select, input, textarea").forEach((el) => { el.disabled = false; });
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

// `edits` (from edit mode) are posted instead of the extracted fields; then
// `prediction` is the model's suggestion for the edited fields, which is
// what the server compares the account against.
async function confirmItem(id, correctedAccount, card, edits = null, prediction = null) {
  const item = queueItems.find((row) => row.id === id);
  const status = card.querySelector(".item-status");
  const busyBtn = card.querySelector(edits ? ".post-btn" : correctedAccount ? ".correct-btn" : ".accept-btn");
  status.hidden = true;
  setCardBusy(card, busyBtn, correctedAccount && !edits ? "Saving…" : "Posting…");

  try {
    const endpoint = correctedAccount ? "/api/correct" : "/api/confirm";
    const body = Object.assign(
      correctedAccount ? { id, corrected_account: correctedAccount } : { id },
      edits || {}
    );
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

  const predicted = prediction || item.predicted_account;
  const account = correctedAccount || predicted;
  const wasCorrection = Boolean(correctedAccount) && correctedAccount !== predicted;
  card.classList.remove("is-editing");
  draftAccounts.delete(id);
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
    queueItems.filter((item) => !csvBool(item.needs_review) && Number(item.confidence) >= CONFIDENCE_THRESHOLD).map((item) => item.id)
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
    document.querySelectorAll(".queue-item:not(.is-posted) :is(button, select, input, textarea)")
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

function startUploads(files) {
  if (!files.length) return;
  document.querySelectorAll(".sample-btn").forEach((b) => b.classList.remove("active"));
  document.getElementById("upload-filename").textContent = files.length === 1
    ? files[0].name
    : `${files.length} files`;
  processFiles(files);
}

document.getElementById("file-input").addEventListener("change", (e) => {
  const files = Array.from(e.target.files);
  e.target.value = ""; // choosing the same file again still fires "change"
  startUploads(files);
});

// Drag and drop anywhere on the page. Always preventDefault on files, or
// the desktop window (WebView2) would navigate away to the dropped file.
let dragDepth = 0;
const hasFiles = (e) => Array.from(e.dataTransfer?.types || []).includes("Files");
document.addEventListener("dragenter", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  dragDepth++;
  document.body.classList.add("is-dropping");
});
document.addEventListener("dragover", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = loading.hidden ? "copy" : "none";
});
document.addEventListener("dragleave", (e) => {
  if (!hasFiles(e)) return;
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) document.body.classList.remove("is-dropping");
});
document.addEventListener("drop", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  dragDepth = 0;
  document.body.classList.remove("is-dropping");
  if (!loading.hidden) return; // one batch at a time
  startUploads(Array.from(e.dataTransfer.files));
});

async function init() {
  ACCOUNTS = await fetchJson("/api/accounts");
  await loadSamples();
  await loadQueue();
}

init();
