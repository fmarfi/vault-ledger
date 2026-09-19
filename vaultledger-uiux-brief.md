# VaultLedger — UI/UX Build Brief for Claude Code

This is a working brief for building VaultLedger's frontend using Claude
Code, with subagents dividing the work. It reflects only what's actually
been decided about the product — flagged clearly wherever something is
still open, so the agents don't invent architecture that hasn't been
confirmed.

---

## 0. Before any agent writes code

Run a **planning pass first**, not parallel builds from a cold start.
Recommended agent split:

1. **Design-system agent** — establishes the token system (color, type,
   layout, spacing) and a component library. Nothing else starts until this
   exists, or every other agent invents its own defaults and the product
   ends up looking assembled, not designed.
2. **IA/flow agent** — maps the actual screens and user flows from Section 2
   below into a sitemap + flow diagram before any screen is built.
3. **Build agents** (can run in parallel once 1 and 2 exist) — one per major
   flow area: onboarding, review/categorization workspace, exports, summary/
   reporting.
4. **Critique agent** — reviews finished screens against this brief and the
   frontend-design skill's self-critique guidance (see Section 5) before
   anything is called done.

If your Claude Code setup has the `frontend-design` skill available, every
build agent should read it before writing UI code — it governs the
aesthetic/copy standards this brief defers to rather than repeating.

---

## 1. Product grounding (don't design in a vacuum)

**What this is:** An on-device, privacy-first AI bookkeeping tool. No
company transaction data ever leaves the device. Two real users share this
UI with different needs:
- **The accountant/bookkeeper** — the primary user. Reviews, corrects, and
  trusts (or doesn't) the model's categorization suggestions. Professionally
  liable for the output.
- **The business owner** — a lighter-touch user. Wants plain-language
  status, not ledger detail.

**Core loop (decided):** ingest documents/transactions → on-device model
suggests categorization → accountant reviews/corrects → corrections feed
back into the on-device fine-tune → export.

**Non-negotiable constraints that affect UI, not just backend:**
- On-device processing must be *visible*, not just true. If the interface
  looks like every other cloud SaaS dashboard, the privacy claim has no
  visual home. This should shape real design decisions (see Section 3),
  not just a badge in the footer.
- The model starts from a per-company fine-tune on the customer's own
  historical export — it is not a blank slate, but it is also not
  instantly perfect. The UI must show *why* a prediction was made and *how
  confident* the model is, every time. This is not a nice-to-have — it's
  the single highest-priority trust feature identified in product research
  (see technical-notes.md), because the target segment's adoption barrier
  is dominated by trust/knowledge constraints, not cost.
- Launch posture is **suggest-only, mandatory review** — the UI should not
  imply autonomous action the model isn't cleared to take yet.

---

## 2. Screens and flows to build

### 2.1 Onboarding / first-run (accountant-facing)
- Connect or upload the company's historical export (QuickBooks/Xero/etc.)
- Show, concretely, what the on-device fine-tune is doing with it — this is
  the single best trust-building moment in the whole product and should not
  be a generic progress bar. Consider surfacing real signal: "We found
  [N] categorized transactions across [M] accounts in your export" —
  something that proves the tool actually looked at *their* data, not
  boilerplate.
- Handle the low-data case gracefully: if the export is thin or
  low-quality, the UI needs a real state for "starting from the general
  model, not a fine-tuned one yet" — not a silent fallback. Don't design
  only the happy path here.

### 2.2 Review / categorization workspace (accountant-facing, primary screen)
This is where the accountant will spend most of their time — it deserves
the most design attention, not the onboarding flow.
- Transaction list with predicted category, confidence indicator (visibly
  different treatment for low-confidence — not just a small number nobody
  reads), and the reasoning behind the prediction (matched pattern, similar
  past transactions, etc.)
- One-click accept, one-click correct, and **bulk correct** for
  same-pattern transactions (already identified as a high-leverage feature
  — don't make the accountant fix the same mistake 40 times)
- Exception/anomaly flagging for unusual transactions, framed as "please
  review" — not as fraud detection (explicitly out of scope) and not
  alarmist
- A visible signal that corrections are training the model — e.g. a
  correction-rate trend over time — so the investment of reviewing early
  transactions feels rewarded, not wasted

### 2.3 Export
Two genuinely separate outputs (already decided — don't merge these into
one flow with a toggle, they serve different purposes and different
audiences):
- **Bookkeeping-software export**: clean CSV matching the target platform's
  import schema (QuickBooks/Xero — platform TBD). Minimal, transactional.
- **Audit/compliance export**: complete record — every transaction,
  correction, confidence score, timestamp. For NL customers this may need
  to be XAF 4.0 (RGS-aligned XML) specifically, not a generic file — flag
  this in the export UI copy as "Dutch tax audit format" or similar plain
  language, not the acronym alone.
- MVP is manual export/download, not a live API push — the UI should make
  this feel like a deliberate, transparent action ("Export to CSV") rather
  than something the product does silently in the background, since that
  visibility is part of the privacy story.

### 2.4 Summary / reporting (business-owner-facing)
- Plain-language period summaries ("spending on X changed by Y%"),
  deterministic and templated — no ledger jargon, no chart-of-accounts
  detail. This tier needs no model; treat any AI-phrased version as a
  future enhancement layered on top, not a blocker for this screen existing.
- This is a genuinely different register from the accountant workspace —
  don't reuse the same density or vocabulary. If both roles share a login,
  design this as a distinct, simpler view rather than a filtered version of
  the accountant's screen.

### 2.5 Trust / transparency surface (cross-cutting, not a single screen)
Not a separate page — a set of ambient signals that should appear
throughout the app:
- Confidence indicators wherever a prediction appears
- Some persistent, non-intrusive acknowledgment of the on-device/privacy
  architecture — this is the product's core differentiator and should be
  legible in the everyday experience, not confined to a marketing page
- An audit trail / activity log the accountant can actually read, not just
  export

---

## 3. Design direction — do not default

Per the frontend-design skill: this brief deliberately does NOT hand you a
color palette or a component style, because picking one without grounding
it in the actual subject matter produces the generic SaaS-dashboard look
every AI-generated fintech UI defaults to. The design-system agent should:

1. **Ground the visual identity in what makes this product different**:
   on-device, private, built *with* an accountant's trust in mind rather
   than trying to automate them away. What does "private" and
   "trustworthy" look like for a financial tool that isn't the generic
   near-black dashboard with a single accent color? What does "the model
   is showing its work" look like visually, distinct from a black-box AI
   product?
2. **Explicitly avoid the generic tells** listed in the frontend-design
   skill (the warm-cream-and-terracotta look, the near-black-with-neon-
   accent look, the identical-rounded-SaaS-card kit, ALL-CAPS eyebrow
   labels, tracked-out labels, arrow-suffixed buttons) unless a real reason
   specific to this brief justifies one of them.
3. **Design for two registers in one product** — the accountant's dense,
   information-rich review workspace and the business owner's plain-
   language summary view are different jobs and should look and feel
   different, while still clearly being the same product. Work out what
   unifies them (likely the type system and the confidence/trust visual
   language) versus what should differ (density, vocabulary, tone).
4. **Treat confidence/uncertainty as a real design problem**, not just a
   percentage. How predictions of varying confidence are visually
   distinguished is one of the most-used UI patterns in this product — it
   deserves deliberate treatment, not a default progress-bar or star
   rating bolted on.

Follow the frontend-design skill's two-pass process: plan (token system +
layout concept + principles), review the plan against this brief and
explicitly check it isn't the generic default, then build.

---

## 4. Explicitly out of scope for this pass

Don't build UI for any of the following — they're either unbuilt on the
backend or genuinely undecided, and building screens for them will produce
UI that has to be thrown away or will misrepresent the product's actual
state to anyone who sees it (including investors/customers, see below):
- Fraud/anomaly detection as a named feature (only the softer "please
  review this" exception flagging from 2.2 is in scope)
- Live API integrations to QuickBooks/Xero (MVP is manual export only)
- Multi-user/multi-client firm dashboards (target segment not yet decided)
- Any UI implying the base-model-vs-independent-training question (see
  technical-notes.md) has been resolved — don't build screens that assume
  cross-customer learning exists yet

---

## 5. Definition of done for each screen

Before a build agent marks a screen complete, the critique agent should
verify:
- Responsive down to mobile
- Visible keyboard focus states
- Reduced-motion respected
- Real accessible contrast, not just visually-plausible contrast
- Copy follows the frontend-design skill's writing guidance: active voice,
  plain language, consistent vocabulary for the same action throughout the
  flow, no vague error states
- The screen doesn't silently assume an unresolved product question is
  settled (cross-check against Section 4)
- A screenshot review against this brief's Section 1 grounding — does this
  screen still look like a generic fintech dashboard, or does it look like
  *this* product specifically

---

## 6. One more thing worth naming

There is currently no frontend at all — this is a from-scratch build. The
backend/model side is also early (a single notebook doing TF-IDF +
logistic regression on public Kaggle data, not yet on real transaction
data). If any part of this build is intended as investor/customer-facing
proof-of-capability material rather than the eventual production frontend,
say so explicitly to the agents up front — a demo-quality build and a
production-intended build have different acceptable shortcuts (e.g. mocked
data and a fixed demo flow are fine for the former, not the latter), and
conflating the two produces a screen that's over-built for a demo or
under-built for production.
