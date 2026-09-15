---
name: vault-ledger-entry-rules
description: Encodes the deterministic debit/credit construction logic for Vault Ledger -- the fixed chart of accounts, paid/unpaid heuristic, balance-check invariant, and required test cases. Load-bearing spec; treat as close to unchangeable without deliberate review.
---

# Vault Ledger entry-construction rules

This is the highest-consequence part of the system (Report 1, item 5): it
must never silently produce an unbalanced entry or a guessed account.

## Source of truth

- `src/vault_ledger/rules/rules_spec.json` -- versioned, readable invariants
  in `{id, alternateExpression}` form (style borrowed from the VERAFI paper,
  Report 4 SS2).
- `src/vault_ledger/rules/entry_rules.py` -- the code that enforces them.
- `src/vault_ledger/coa.py` -- the fixed 8-account chart of accounts.

Keep the JSON spec and the code in sync. If you change one, update the other
and re-run the tests below.

## The invariants (do not weaken these)

1. **R1** -- total debits == total credits, always.
2. **R2** -- the predicted expense account must be in the fixed COA. If not,
   reject the entry (raise `RuleViolation`) -- never guess or clamp to a
   nearby account.
3. **R3** -- amount must be strictly > 0.
4. **R4** -- paid -> credit Cash/Bank; unpaid -> credit Accounts Payable.
5. **R5** -- the debit line is always the predicted expense account, never a
   mechanical account (Cash/Bank, Accounts Payable).

## Required test cases

`tests/test_entry_rules.py` must always cover: paid, unpaid, zero amount,
negative amount, unknown/invalid account, and a mechanical account passed in
as the expense account. All of these should raise `RuleViolation` or produce
a balanced entry -- there is no other valid outcome.

## This is deterministic code, not ML

Do not replace any part of this with a model prediction, an LLM call, or a
"best guess" fallback. Report 1 and the VERAFI paper (Report 4 SS2, the
52.4% -> 90.4% -> 94.7% progression from free-text reasoning to tool-based
computation to embedded validation rules) are both explicit that financial
arithmetic and validity checks belong in deterministic code, with the
probabilistic layer (the classifier) feeding it a label and nothing else.

## What NOT to do

- Do not let this layer silently break. Any change here should be run
  against `tests/test_entry_rules.py` before being considered done -- a
  Claude Code hook (`.claude/settings.json`) already enforces this
  automatically on edits to this directory.
- Do not add per-client custom charts of accounts, hierarchy/taxonomy
  masking, or a polished correction UI here -- all explicitly out of scope
  for the MVP per Report 1.
