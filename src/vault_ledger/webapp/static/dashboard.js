// Dashboard page: where the books stand today. Every figure comes from
// /api/dashboard (vault_ledger/dashboard.py); this file only draws it.
// Text from documents (vendor, filename) is untrusted, so everything is
// set through textContent -- never innerHTML.

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function setText(id, text) {
  document.getElementById(id).textContent = text;
}

function money(value) {
  return value === null || value === undefined ? "—" : formatCurrency(value);
}

function plural(n, one, many) {
  return `${n} ${n === 1 ? one : many}`;
}

function renderTiles(data) {
  const { review, posted, open_value: open, acceptance } = data;
  const periodWord = data.period === "this" ? "this month" : "last month";

  setText("tile-review-value", String(review.pending));
  setText("tile-review-foot", review.pending
    ? `${review.flagged} flagged for a closer look`
    : "Nothing waiting");

  setText("tile-posted-period", periodWord);
  setText("tile-posted-value", formatCurrency(posted.total));
  const c = posted.comparison;
  let change = "";
  if (posted.count && c.available) {
    change = c.direction === "flat" ? ` · flat vs ${c.label}` : ` · ${c.direction === "up" ? "↑" : "↓"} ${c.pct}% vs ${c.label}`;
  } else if (posted.count) {
    change = ` · nothing posted ${c.label} to compare`;
  }
  setText("tile-posted-foot", plural(posted.count, "entry", "entries") + change);

  setText("tile-open-value", formatCurrency(open.total));
  let openFoot = open.count ? `Across ${plural(open.count, "open document", "open documents")}` : "No open documents";
  if (open.unreadable) openFoot += ` · ${open.unreadable} without a readable amount`;
  setText("tile-open-foot", openFoot);

  if (acceptance.rate === null) {
    setText("tile-accept-value", "—");
    setText("tile-accept-foot", `No entries posted ${periodWord}`);
  } else {
    setText("tile-accept-value", Math.round(acceptance.rate * 100) + "%");
    let foot = `${acceptance.accepted} of ${acceptance.total} without a correction`;
    if (!acceptance.meaningful) foot += ` · small sample (under ${acceptance.min_sample})`;
    setText("tile-accept-foot", foot);
  }
}

function renderReview(data) {
  const rows = document.getElementById("dash-review-rows");
  rows.replaceChildren();
  data.needs_review.forEach((item) => {
    const tr = el("tr");

    const doc = el("td", "dash-doc");
    doc.append(el("div", "dash-doc-vendor", item.vendor || "Unknown vendor"), el("div", "dash-doc-file figure", item.filename));
    const date = el("td", "figure", item.date || "—");
    const amount = el("td", "num figure", money(item.amount));
    const confidence = el("td", "num figure", item.confidence === null ? "—" : Math.round(item.confidence * 100) + "%");

    const status = el("td");
    status.append(item.flagged
      ? el("span", "badge badge-review", "Needs review")
      : el("span", "badge badge-ok", "Ready to confirm"));

    const action = el("td", "num");
    const link = el("a", "dash-link", "Open →");
    link.href = "/#item-" + encodeURIComponent(item.id);
    link.setAttribute("aria-label", `Open ${item.vendor || "item"} in the review queue`);
    action.append(link);

    tr.append(doc, date, amount, confidence, status, action);
    rows.append(tr);
  });

  const empty = data.needs_review.length === 0;
  document.querySelector(".dash-table-wrap").hidden = empty;
  document.getElementById("dash-review-empty").hidden = !empty;
  const more = data.review.pending - data.needs_review.length;
  const moreNote = document.getElementById("dash-review-more");
  moreNote.hidden = more <= 0;
  moreNote.textContent = more > 0 ? `${plural(more, "more item", "more items")} in the review queue.` : "";
}

function renderActivity(data) {
  const list = document.getElementById("dash-activity-list");
  list.replaceChildren();
  data.activity.forEach((event) => {
    const li = el("li", `dash-event dash-event-${event.kind}`);
    li.append(el("i", "dash-event-dot"));
    const body = el("div", "dash-event-body");
    const line = el("div", "dash-event-line");
    line.append(el("b", null, event.vendor || "Unknown vendor"), document.createTextNode(" " + event.text));
    const meta = el("div", "dash-event-meta small muted");
    const time = el("time", null, event.when);
    time.dateTime = event.at;
    time.title = event.at;
    meta.append(time);
    if (event.amount !== null) meta.append(document.createTextNode(" · "), el("span", "figure", formatCurrency(event.amount)));
    body.append(line, meta);
    li.append(body);
    list.append(li);
  });
  document.getElementById("dash-activity-empty").hidden = data.activity.length > 0;
}

function renderReadiness(data) {
  const r = data.readiness;
  setText("dash-ready-sub", `${data.current_month_label} · posted entries against the open queue`);
  const empty = r.pct === null;
  document.getElementById("dash-ready-body").hidden = empty;
  document.getElementById("dash-ready-empty").hidden = !empty;
  setText("dash-ready-pct", empty ? "" : r.pct + "%");
  setText("dash-ready-posted", String(r.posted));
  setText("dash-ready-pending", String(r.pending));
  const bar = document.getElementById("dash-ready-bar");
  bar.setAttribute("aria-valuenow", String(r.pct ?? 0));
  bar.setAttribute("aria-valuetext", `${r.posted} posted, ${r.pending} still in the review queue`);
  document.getElementById("dash-ready-fill").style.width = (r.pct ?? 0) + "%";
}

function renderMix(data) {
  setText("dash-mix-sub", `${data.month_label} · posted entries by expense account`);
  const total = data.posted.total;
  setText("dash-mix-total", data.mix.length ? formatCurrency(total) : "");

  const bars = document.getElementById("dash-mix");
  bars.replaceChildren();
  const largest = data.mix.length ? data.mix[0].amount : 0;
  data.mix.forEach((line) => {
    const row = el("div", "dash-bar-row");
    const track = el("div", "dash-bar-track");
    track.setAttribute("aria-hidden", "true");
    const fill = el("span", "dash-bar-fill");
    // Scaled to the largest account so the biggest bar fills its track;
    // the share label gives the true proportion of the month.
    fill.style.width = (largest > 0 ? (line.amount / largest) * 100 : 0) + "%";
    track.append(fill);
    row.append(
      el("span", "dash-bar-name", line.account),
      track,
      el("span", "dash-bar-amount figure", formatCurrency(line.amount)),
      el("span", "dash-bar-share figure muted", line.share === null ? "" : line.share + "%"),
    );
    bars.append(row);
  });
  const empty = data.mix.length === 0;
  bars.hidden = empty;
  const note = document.getElementById("dash-mix-empty");
  note.hidden = !empty;
  note.textContent = empty
    ? `No expenses posted in ${data.month_label}. Confirm a document in the review queue and its account appears here.`
    : "";
}

let dashSeq = 0;

async function loadDashboard(period) {
  ["this", "last"].forEach((p) => {
    const btn = document.getElementById(`dash-period-${p}`);
    btn.classList.toggle("active", p === period);
    btn.setAttribute("aria-pressed", String(p === period));
  });
  // Drop a slow response for the previous period landing after a newer one.
  const seq = ++dashSeq;
  const error = document.getElementById("dash-error");
  let data;
  try {
    data = await fetchJson(`/api/dashboard?period=${period}`);
  } catch (err) {
    if (seq !== dashSeq) return;
    error.textContent = "Could not load the dashboard: " + err.message;
    error.hidden = false;
    return;
  }
  if (seq !== dashSeq) return;
  error.hidden = true;
  renderTiles(data);
  renderReview(data);
  renderActivity(data);
  renderReadiness(data);
  renderMix(data);
}

document.getElementById("dash-period-this").addEventListener("click", () => loadDashboard("this"));
document.getElementById("dash-period-last").addEventListener("click", () => loadDashboard("last"));

loadDashboard("this");
