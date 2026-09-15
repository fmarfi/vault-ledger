# Report 5 — Vault Ledger MVP: UI/UX Specification

**Purpose:** a build-ready functional spec for the MVP's user interface, meant to hand to a coding agent (or a human developer) alongside Reports 1–4. This covers screens, states, flows, and content/microcopy guidance — not a visual design system (colors/typography are left to whoever implements it, with a few structural principles noted at the end).

**Scope reminder:** single accountant/bookkeeper user, fixed 8-account COA, three document formats (vendor invoice, utility bill, receipt), no multi-user roles, no custom reporting. This spec covers exactly what's needed to demo the core loop from Report 2's Milestone 5 onward — nothing more.

---

## 1. Information architecture — the screens that must exist

```
┌─────────────────────────────────────────┐
│  App shell (persistent nav)              │
│  ┌───────────┬───────────┬─────────────┐ │
│  │  Review   │  Chart of │  Activity /  │ │
│  │  Queue    │  Accounts │  History     │ │
│  │  (home)   │           │              │ │
│  └───────────┴───────────┴─────────────┘ │
└─────────────────────────────────────────┘
```

Three primary screens, plus two supporting views (document upload, entry detail/edit). Nothing else is needed for MVP — no settings, no user management, no reports beyond what's specified in Section 5.

---

## 2. Screen: Review Queue (the home screen, the one used daily)

**Purpose:** this is where the accountant spends nearly all their time. It's the list of documents that have been processed and are awaiting confirmation, plus a way to add new ones.

**Layout: a list/table, one row per document**

| Column | Content |
|---|---|
| Thumbnail | Small preview of the source document (image/PDF first page) |
| Vendor | Extracted vendor name |
| Date | Extracted document date |
| Amount | Extracted total amount |
| Predicted account | The Step 3 classifier's top prediction, shown as text with the account type as a small badge (Expense/Asset/etc.) |
| Confidence | Visual indicator — not just a raw percentage (see 2.1 below) |
| Action | Quick-confirm button (high confidence) or "Review" button (low confidence) |

**2.1 — Confidence display, specifically**

Do not show a bare percentage as the primary signal — accountants don't have an intuition for what "78% confidence" means in accounting terms. Instead:
- **High confidence** (above the Report 1 threshold): a quiet positive indicator (e.g. a filled dot/checkmark), row is quick-confirmable with one click, no forced review.
- **Low confidence** (below threshold): a distinct visual marker (e.g. an outlined/amber indicator) and the row's action button reads "Review" instead of "Confirm" — this is the Report 2 Milestone 6 behavior made visible. Do not let a low-confidence row be one-click-confirmed; force it through the detail view.
- On hover/tap, a raw percentage can be available for accountants who want it, but it's secondary information, not the primary cue.

**2.2 — Sorting and grouping**
- Default sort: newest document first.
- Allow grouping/filtering by: needs review vs. auto-confirmed, predicted account, date range. This is a small feature but meaningfully speeds up daily use once volume grows past a handful of documents.

**2.3 — Bulk actions (explicitly flagged as nice-to-have, not MVP-blocking)**
- Select multiple high-confidence rows, confirm together. Build this only after the single-row flow works end-to-end — don't let it block the core loop.

**2.4 — Empty state**
Per the interface-writing principle (see Section 6): an empty queue is an invitation to act, not a dead end. Copy should point directly at the upload action — e.g. "No documents waiting. Upload an invoice or receipt to get started." — with the upload control immediately visible, not just described.

---

## 3. Screen: Document Upload

**Purpose:** get a document into the pipeline. Minimal by design.

- A drop zone / file picker accepting PDF and common image formats (matching whatever the OCR step in Report 1 actually supports).
- Immediate feedback on upload: the document appears in the Review Queue with a visible "Processing…" state while OCR/extraction/classification run.
- If extraction fails outright (unreadable document, unsupported format): a clear, specific failure state — not a silent drop. State what happened and what to do ("Couldn't read this file. Try a clearer photo or a PDF export.") rather than a generic error.
- No need for a separate "upload" screen if a persistent upload control lives in the Review Queue header instead — simpler information architecture, one less screen to navigate to.

---

## 4. Screen: Entry Detail / Edit (the most important screen in the product)

**Purpose:** where an accountant actually verifies or corrects a proposed entry. This is where trust is won or lost — the design priority here is verifiability, not speed.

**Layout: two-panel, source document next to proposed entry**

```
┌───────────────────┬─────────────────────────┐
│                    │  Vendor:  [extracted]    │
│   Original         │  Date:    [extracted]    │
│   document         │  Amount:  [extracted]    │
│   (image/PDF        │                          │
│   viewer,           │  Proposed Journal Entry: │
│   zoomable)         │  ┌─────────────────────┐ │
│                    │  │ Debit:  [Account ▾]  │ │
│                    │  │         $XXX.XX       │ │
│                    │  │ Credit: [Account ▾]  │ │
│                    │  │         $XXX.XX       │ │
│                    │  └─────────────────────┘ │
│                    │  Why this account:       │
│                    │  [one-line explanation]  │
│                    │                          │
│                    │  [Confirm]  [Save Edit]  │
└───────────────────┴─────────────────────────┘
```

**4.1 — The account selector is constrained, not free text**
The debit/credit account fields are dropdowns/pickers restricted to the fixed COA — never a free-text field. This is a direct UI expression of Report 1's rules-layer invariant: an accountant should not be able to "correct" an entry into an account that doesn't exist in the system. If the account they want isn't in the list, that's a signal the COA itself needs to grow (a backend decision, not something resolved by letting the UI accept arbitrary text).

**4.2 — The balance check is visible, not just enforced silently**
Show running debit and credit totals directly in this view, and visually confirm when they're equal (a simple checkmark or "Balanced" label) before allowing confirm. If they're ever out of balance — which shouldn't happen given the rules layer, but the UI should never assume the backend is infallible — block confirmation and say why in plain language ("Debits and credits don't match — check the amount.").

**4.3 — The explanation line**
A single sentence, not a technical log: something like "Matched on vendor name and description similarity to prior Utilities entries." Per Report 1's VERAFI-derived lesson, this should read as a plain-language business explanation, never expose internal mechanics (model names, confidence math, rule IDs). If no strong explanation is available, omit the line rather than showing a placeholder.

**4.4 — Confirm vs. Edit are two distinct, clear actions**
"Confirm" accepts the proposed entry as-is. "Save Edit" is only enabled once something has actually changed. Never merge these into a single ambiguous "Submit" — per the writing principle in Section 6, an action's label should say exactly what will happen.

**4.5 — What happens after confirm/edit**
- On Confirm: entry leaves the Review Queue, document is marked processed, brief confirmation (not a blocking modal — a toast/inline acknowledgment is enough).
- On Save Edit: same, but this correction is what feeds Report 1's correction loop — log the original prediction and the corrected value together, since this pairing is the actual training signal for future model updates. (This is backend behavior, but the UI is the thing that must reliably capture it — don't let an edit go through without both values being recorded.)

---

## 5. Screen: Chart of Accounts

**Purpose:** a read-focused view for MVP — accountants check what's there and see activity, they don't edit the COA themselves yet (Section 8 explicitly excludes COA editing from MVP scope).

**Layout: simple list**

| Account | Type | Transactions this period | Total this period |
|---|---|---|---|
| Utilities Expense | Expense | 12 | $840.50 |
| Cash/Bank | Asset | — | — |
| ... | ... | ... | ... |

- Clicking an account filters the Activity/History screen (Section 6) to that account — this is more useful than a standalone detail page for MVP.
- No add/edit/delete controls in this screen for MVP (see Section 8).

---

## 6. Screen: Activity / History

**Purpose:** everything that's already been confirmed — the audit trail, and the home of the accuracy dashboard.

**6.1 — Confirmed entries list**
Same row shape as the Review Queue, but showing final state: what was predicted, what it was corrected to (if anything), and when. This is the audit trail described in the earlier conversation — accountants should be able to see the system's track record, not just its current guesses.

**6.2 — The accuracy summary (the investor-pitch number, generated automatically)**
A small, simple stats block at the top of this screen: e.g. "94% of entries confirmed without correction this month" with a basic trend indicator against the prior period. This should be genuinely simple — a number and a short trend line, not a full analytics dashboard. It exists to do double duty: give the accountant confidence the tool is working, and give you a live, defensible number for the pitch instead of one you compile by hand (per Report 2's Milestone 4/8 guidance — never show a fabricated or placeholder number here; if there's not enough data yet, say so plainly rather than showing a misleading stat).

---

## 7. Cross-cutting states every screen needs

These apply across the whole app, not just one screen — worth building once as shared patterns rather than per-screen:

- **Loading/processing state**: while OCR/classification runs on a newly uploaded document, show it in the queue with a clear "Processing…" state rather than hiding it until done — this keeps the accountant informed and matches how the pipeline actually works (it's not instant).
- **Low-confidence / needs-review state**: consistent visual treatment everywhere a prediction appears (queue row, detail view) — one visual language for "the system isn't sure," not different treatments per screen.
- **Error state**: extraction failure, unreadable document, or a rules-layer rejection (e.g. predicted account somehow outside the fixed COA) — always state what happened and what to do next, in plain language, never a raw error code or stack trace.
- **Empty state**: as described in 2.4 — always an invitation to act, never a dead end.

---

## 8. Explicitly out of scope for MVP UI

Keeping this list visible for whoever builds this, so scope doesn't creep mid-build:

- Chart of Accounts editing (add/remove/rename accounts) — COA changes are a backend/config decision for now
- Multi-user accounts, roles, or permissions
- Custom report building or data export beyond what's in the Activity screen
- Settings/configuration screens of any kind
- Notifications (email/push) — the Review Queue itself is the only "inbox" needed
- Mobile-specific layouts — a responsive web view is enough; a dedicated mobile app is not MVP scope

---

## 9. Content and interaction principles (for whoever writes the actual copy/interactions)

A short set of standing rules, worth keeping visible to the building agent throughout, not just applied once:

- **Name things the way an accountant would, not the way the system does.** "Review Queue," not "Prediction Inbox." "Confirm," not "Submit." "Proposed entry," not "Model output."
- **Every action button says exactly what happens.** "Confirm" confirms. "Save Edit" saves an edit. Never a vague "Submit" or "OK" where the actual effect is ambiguous.
- **Keep the vocabulary consistent through a whole flow.** If a button says "Confirm," the resulting acknowledgment should say "Confirmed" — not "Success" or "Done."
- **Errors and empty states speak in the interface's voice, plainly, never apologetically.** State what happened and what to do, not "Oops!" or "Something went wrong."
- **Never expose internal mechanics to the end user** — no confidence math, no model names, no rule IDs, no "TF-IDF" anywhere in the UI. The explanation line (4.3) should read like something a colleague would say, not a debug log.

---

## 10. Suggested build order, mapped to Report 2's milestones

| Report 2 milestone | UI piece to build alongside it |
|---|---|
| M5 — full pipeline works end-to-end (script, no UI) | Nothing yet — this stays a script |
| M5 → demo-ready | Review Queue (bare) + Entry Detail/Edit screen — this is the minimum UI needed to actually demo the loop live |
| M6 — confidence gate | Confidence indicators in the queue and detail view (Section 2.1, 4.2) |
| M7 — correction loop | Ensure Entry Detail's edit flow correctly logs original + corrected values (Section 4.5) |
| M8 — real pilot run | Activity/History screen with the accuracy summary (Section 6.2) — this is what turns pilot data into a presentable number |

Chart of Accounts (Section 5) and bulk actions (Section 2.3) are polish, worth building whenever there's spare capacity — not blocking any milestone above.
