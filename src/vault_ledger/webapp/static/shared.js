// Shared helpers used across every page's own script. Keep this the one
// place that knows how to format money or draw the confidence glyph, so
// the pencil/ink treatment can't drift out of sync between pages.

function formatCurrency(value) {
  return "$" + Number(value).toFixed(2);
}

// Single source of truth for what counts as "high confidence" -- used by
// the glyph below and by the review queue's bulk-select-by-confidence
// action, so the two can't silently drift apart.
const CONFIDENCE_THRESHOLD = 0.6;

// Ink (solid, filled) = high confidence. Pencil (dashed outline) = low.
// The percentage renders but stays hidden until hover via .confidence-pct
// (see style.css) -- secondary info, not the primary cue.
function confidenceGlyphHtml(confidence, threshold = CONFIDENCE_THRESHOLD) {
  const isLow = confidence < threshold;
  const word = isLow ? "Uncertain" : "Matched";
  const pct = Math.round(confidence * 100) + "%";
  const glyph = isLow
    ? '<svg class="confidence-glyph" width="18" height="18" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8.3" stroke="var(--color-pencil)" stroke-width="1.3" stroke-dasharray="2.3 2.3"/></svg>'
    : '<svg class="confidence-glyph" width="18" height="18" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="9" fill="var(--color-ink)"/><path d="M6 10.3L8.3 12.8L14 7" stroke="var(--color-on-ink)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  return `
    <div class="confidence-row">
      ${glyph}
      <span class="confidence-word">${word}</span>
      <span class="confidence-pct figure">${pct}</span>
    </div>
  `;
}

function documentIconHtml() {
  return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="flex-shrink:0"><rect x="4" y="2" width="16" height="20" rx="1" stroke="var(--color-pencil)" stroke-width="1.3"/><path d="M8 8h8M8 12h8M8 16h5" stroke="var(--color-pencil)" stroke-width="1.3" stroke-linecap="round"/></svg>';
}

async function fetchJson(url, options) {
  const res = await fetch(url, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.error || res.statusText);
  }
  return body;
}
