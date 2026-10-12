# Vault Ledger agent structure

The agent definitions live in `.claude/agents/`, one folder per team. Each team
has an executive who briefs you directly; the main executive sits above the
five team executives and gives you one overall picture.

```
.claude/agents/
  main/         executive                 main executive, above the five teams
  data/         exec-data                 team executive
                synth-spec-architect      1  writes the statistical spec
                synth-corpus-builder      2  vendor and description pools
                synth-generator           3  generates the labelled transactions
                synth-statistical-auditor 4  gate: statistics, leakage, duplicates
                synth-realism-critic      5  gate: blind realism review
                synth-ml-evaluator        6  trains on it, measures the gap to real data
  extraction/   exec-extraction           team executive
                extraction-builder        builds OCR / PDF / field-parsing changes
                ocr-runner                runs extraction on documents and reports results
  model-rules/  exec-model                team executive
                classifier-eval           trains and evaluates the classifier
                rules-validator           gate: debit/credit entry rules
  site/         exec-site                 team executive
                site-builder              builds and tests web app changes
  research/     exec-research             team executive
                research-product-scout    functions worth adding, from comparable products
                research-tech-scout       better methods, libraries and local models
                research-customer-scout   what the customer and their accountant require
                research-skeptic          gate: re-checks every finding at its source
```

## How it works

- **Executives decide, specialists do.** An executive reads the state of its
  team, says which agent should do what next, and reports to you. It does not
  write code.
- **Executives cannot start agents themselves.** They name the agent and the
  task; the Claude Code session you are talking to starts it.
- **Gates are fixed.** The two data gates, the rules gate and the research
  skeptic cannot be skipped
  or loosened by anyone but you. Whoever wrote a change never judges it.
- **Nothing is merged, pushed, or shown to a customer without your approval.**

## Asking for a briefing

In a Claude Code session, ask for the agent by name, for example "get the
extraction executive's briefing" or "ask the main executive where we stand".
`/agents` lists every agent that is loaded.

## Where reports go

| What | Where |
|---|---|
| Design reports and reviews | `docs/reports/` |
| Research crew findings | `docs/reports/research/` |
| Action list and UI brief | `docs/planning/` |
| Synthetic-data gate reports | `data/synthetic/reports/` (branch `synth-data`) |
| Real documents and screenshots for testing | `private/` (never committed) |
