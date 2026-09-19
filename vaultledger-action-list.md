# VaultLedger — Action List (as of 2026-09-16)

For a future Claude session or teammate picking this up. Items are grouped by
status: **decided** (user-confirmed, build against these) vs. **open**
(discussed, not yet resolved — needs a decision or real-world data before
building) vs. **proof-of-capability** (material to show investors/customers
that the team is eligible/capable of delivering this).

---

## 📋 2026-09-18 — Diagnostics report + customer panel

Full report (pipeline bottleneck audit + a simulated 6-persona customer
panel — Marijke/freelancer, Tomasz/SME owner, Aisha/bookkeeping firm,
Priya/healthtech founder, Jake/US retailer, Sanne/CFO consultant):
https://claude.ai/artifact/UDCykwi3X8fRYGMb4Gjem1

Bottom line: the deterministic core (rules layer, balance invariant) is
solid and fully tested; everything upstream of it (extraction, category
prediction) is weak for a structural reason — almost no real data has
touched the system yet. Six features came out of the panel, each scoped to
greenlight independently:

1. Persistent review queue (SMALL–MEDIUM) — **done**
2. Bulk confirm (SMALL) — **done**
3. Custom / region-flexible chart of accounts (MEDIUM) — **done** (see
   Open item 10: caveats handled; the US/EU templates are generic
   placeholders, not researched against any real standard)
4. Manual backup & restore (SMALL–MEDIUM) — **done**
5. Honest accuracy panel (SMALL) — **done**
6. Preflight hardware check (SMALL) — **done**

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
   separate problem from categorization cold start. Now partially
   addressed: field parsing is a 3-tier system (exact label match ->
   real-world heuristics -> local LLM fallback via Ollama), verified to
   correctly generalize past keyword-based heuristics on a document
   containing none of their trigger words at all. Still open: no
   systematic real-world document test set, so the actual hit rate across
   real formats is unmeasured, only spot-checked against a handful of
   examples found during development.

6. **Retrain cadence** for the correction-logging loop — immediate vs.
   batched — so the accountant visibly sees the model improve.

7. **Minimum hardware spec** for the on-device model (base classifier and,
   later, the small LLM summary tier). Real data point from dev work: a
   representative low end (Intel i3-1000NG4, 8GB RAM, no GPU) could not
   reasonably run the originally-planned 3-8B model class -- had to scale
   down to ~1.5B (`qwen2.5:1.5b-instruct`) to get workable inference (~7-13s
   per call on CPU alone). Treat 3-8B as an Apple-Silicon-or-better
   assumption, not a safe default across arbitrary customer hardware.

8. **Fine-tuning feasibility and tooling** (distinct from just *running* a
   model, which item 7 covers). LoRA/QLoRA is the standard technique for
   exactly the per-company fine-tune in decided-item 2 -- adapts a small
   open-weight model to a customer's own historical categorized
   transactions without full retraining. Not yet built or tested. Real
   constraint found during dev work: fine-tuning is far more compute-heavy
   than inference, and would be impractically slow on a CPU-only low-power
   machine like the one above -- Apple Silicon (MLX, GPU-accelerated
   on-device fine-tuning) or a modest GPU are the realistic targets. This
   directly bounds item 7: if fine-tuning must also run on-device at the
   customer's site (not just inference), the minimum hardware spec is
   materially higher than what's needed to merely run the model.
   Tooling not yet chosen: MLX (Apple Silicon only, fastest on-device path)
   vs. Hugging Face `transformers`+`peft` (portable, CPU/GPU, slower) vs.
   Unsloth (faster HF-ecosystem LoRA, GPU-oriented). Needs a decision once
   target customer hardware is known.

9. **Market research: USA chart-of-accounts/compliance landscape.** Turkey
   is researched (mandatory Tekdüzen Hesap Planı — see
   /areas/market-notes-turkey-usa.md). USA flagged as a good candidate
   market too but not yet researched — need to check whether a standardized/
   reference COA equivalent exists there before treating anything as fact.

10. **Custom/region-flexible chart of accounts (feature 3, approved in
    principle 2026-09-18) has a real coupling into the classifier that
    needs solving before it's built, not after:**
    - The classifier itself has no hardcoded account list —
      `LogisticRegression.classes_` is just `np.unique()` of whatever
      labels are in `labeled_transactions.csv` at train time
      (`fusion_classifier.py`), so no model weights/parameters are tied to
      the fixed 9-account list.
    - What IS hardcoded is the **validation gate**: `coa.py`'s
      `EXPENSE_ACCOUNTS` is a fixed Python `set`, imported directly by
      `entry_rules.py`, `/api/confirm`, `/api/correct`, and `/api/accounts`.
      Making accounts custom means turning this into a per-installation
      dynamic set read from storage, and swapping every one of those
      call sites from a static import to a lookup.
    - **Cold start per new account**: a brand-new custom account has zero
      training rows, so the model literally cannot predict it until at
      least one document has been manually corrected into it — that
      correction becomes a training row through the M7 loop that already
      exists (`corrections.csv` → `apply_corrections.py` → retrain), so
      the self-healing path already works, it just needs to be surfaced
      in the UI ("new accounts start with no suggestions until you
      correct a few into it") rather than left implicit.
    - **Rename/remove isn't a safe in-place edit**: existing training rows
      and ledger entries reference the old label string. Treat a
      rename/removal as archive-old + add-new, not a mutation, or history
      goes stale.

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
