// Overview page: one period's spend, how it compares to the month before,
// and where it went by account. All figures come from /api/overview.

function changeSentence(comparison) {
  if (!comparison.available) {
    return `No spending posted ${comparison.label} to compare against.`;
  }
  if (comparison.direction === "flat") {
    return `Spending is flat compared to ${comparison.label}.`;
  }
  return `Spending is ${comparison.direction} ${comparison.pct}% from ${comparison.label}.`;
}

let requestSeq = 0;

async function loadOverview(period) {
  document.getElementById("period-this").classList.toggle("active", period === "this");
  document.getElementById("period-last").classList.toggle("active", period === "last");

  // Guard against a slow response for the previous tab landing after a
  // faster one for the current tab.
  const seq = ++requestSeq;
  let data;
  try {
    data = await fetchJson(`/api/overview?period=${period}`);
  } catch (err) {
    if (seq !== requestSeq) return;
    document.getElementById("overview-change").textContent = "Could not load the overview: " + err.message;
    return;
  }
  if (seq !== requestSeq) return;

  document.getElementById("overview-month").textContent = data.month_label;
  document.getElementById("overview-total").textContent = formatCurrency(data.total);
  document.getElementById("overview-change").textContent = data.entry_count
    ? changeSentence(data.comparison)
    : "";

  const empty = document.getElementById("overview-empty");
  const breakdown = document.getElementById("overview-breakdown");
  empty.hidden = data.entry_count > 0;
  breakdown.hidden = data.entry_count === 0;

  const lines = document.getElementById("overview-lines");
  lines.innerHTML = "";
  data.lines.forEach((line) => {
    const row = document.createElement("div");
    row.className = "overview-line";
    const name = document.createElement("span");
    name.textContent = line.account;
    const amount = document.createElement("span");
    amount.className = "figure";
    amount.textContent = formatCurrency(line.amount);
    row.append(name, amount);
    lines.appendChild(row);
  });
}

document.getElementById("period-this").addEventListener("click", () => loadOverview("this"));
document.getElementById("period-last").addEventListener("click", () => loadOverview("last"));

loadOverview("this");
