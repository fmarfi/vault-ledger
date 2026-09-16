# VaultLedger — Action List (as of 2026-09-16)

For a future Claude session or teammate picking this up. Items are grouped by
status: **decided** (user-confirmed, build against these) vs. **open**
(discussed, not yet resolved — needs a decision or real-world data before
building) vs. **proof-of-capability** (material to show investors/customers
that the team is eligible/capable of delivering this).

---

## ✅ Decided — build against these

1. **Architecture is on-device.** No company data leaves the device. This is
   the core privacy claim and should be treated as a hard constraint on every
   other decision (training, export, LLM summaries, etc.).

2. **Training approach: per-company fine-tune, not cold-start-from-scratch.**
   Consult the company first, use their existing bookkeeping platform export
   (QuickBooks/Xero/etc.) of already-categorized historical transactions to
   fine-tune the model on-device before the tool goes live for that company.
   Labels come from the customer's export (or guided export), not from a
   manual-labeling service — this keeps onboarding software-only, not
   services-heavy.

3. **Export/output: two separate files, not one.**
   - A clean, minimal-row CSV matching the target bookkeeping platform's
     documented *import* schema (not its export schema — these often differ).
   - A separate audit/compliance export carrying everything the import file
     has no place for: every transaction, every correction, confidence
     scores, timestamps. Immutable, complete record.
   - For NL customers specifically, this audit export may need to be a valid
     XAF 4.0 file (RGS-aligned XML) — mandatory as of Jan 1, 2026 — not just
     a generic CSV/Excel log. Not yet verified against the full spec.

4. **MVP export mechanism: manual CSV, not live API integration.** Keeps the
   privacy story simple (human moves the data, no third-party API call
   during normal operation). API integration is a v2 candidate once trust/
   demand is established — not part of MVP scope.

5. **LLM-based plain-language summaries: two-tier, templated tier first.**
   - Tier 1 (MVP): deterministic arithmetic over already-categorized data
     (e.g. period-over-period % change) plugged into a sentence template. No
     model, no hallucination risk. Build this first — expected to deliver
     most of the trust/usefulness value on its own.
   - Tier 2 (v2 polish): small local LLM (3-8B class — Phi/Gemma/Qwen/
     Llama-3.2 class) only for phrasing/synthesizing multiple pre-computed
     facts into a natural paragraph. Never lets the LLM compute the numbers
     itself — always fed pre-calculated values, constrained fill-in-template
     prompting only.

6. **Primary market: Netherlands (RGS + XAF 4.0).** NL is the standard the
   product builds to first. Turkey and USA are candidate expansion markets,
   researched but not being built to yet (see Open, below).

---

## 🔲 Open — needs a decision or real-world check before building

1. **Look at a real QuickBooks or Xero export/import file.** Single highest-
   leverage next step — half a day of work, unblocks multiple open items
   below at once (label quality, export schema, taxonomy mapping).

2. **Base model question:** does each company fine-tune from a shared
   generic base model (allows the base to improve over time, bounds what a
   single company's fine-tune needs to achieve alone), or does each company
   train fully independently? Not yet decided — significantly affects
   accuracy ceiling and whether there's any cross-customer improvement
   mechanism at all.

3. **Minimum labeled-transaction threshold** for fine-tuning to be worth
   running vs. falling back to the base model alone. Needs empirical
   checking against a real export, not a guess.

4. **Label quality handling:** how to detect/exclude low-quality labels
   (Uncategorized/Misc buckets, inconsistent historical categorization) from
   a customer's export before fine-tuning on it.

5. **Document-extraction (OCR) reliability** for new incoming documents —
   separate problem from categorization cold start, not yet addressed by any
   of the training-architecture work above.

6. **Retrain cadence** for the correction-logging loop — immediate vs.
   batched — so the accountant visibly sees the model improve.

7. **Minimum hardware spec** for the on-device model (base classifier and,
   later, the small LLM summary tier).

8. **Market research: USA chart-of-accounts/compliance landscape.** Turkey
   is researched (mandatory Tekdüzen Hesap Planı — see
   /areas/market-notes-turkey-usa.md). USA flagged as a good candidate
   market too but not yet researched — need to check whether a standardized/
   reference COA equivalent exists there before treating anything as fact.

---

## 🎯 Proof-of-capability — for investors/customers

Placeholder section: material that demonstrates the team can actually build
this, to show investors or prospective customers. Not yet built — needs
scoping on what's most convincing given no first customer/validation exists
yet.

Candidates to develop (none decided yet):
- A working demo of the on-device fine-tuning loop on a sample/synthetic
  transaction export (doesn't require a real customer's data).
- A short technical explainer/deck translating the reference-paper research
  already on file (DragoNet, VERAFI, SME literature review) into a
  credibility signal — "here's the state of the art we're building on and
  why our architecture choices follow from it."
- A side-by-side accuracy comparison: baseline categorization vs. the
  fine-tuned approach, on public/synthetic transaction data, to show the
  fine-tuning step has measurable value.
- A one-page architecture/privacy explainer for the on-device + no-data-
  leaves-the-device claim, for compliance-minded prospects.

---

## Suggested immediate next step

Open item 1 (look at a real export file) is the cheapest, highest-leverage
unblock — it informs items 2-4 simultaneously and turns several "needs
real-world data" items into decidable ones.
