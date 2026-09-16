---
name: vault-ledger-ocr-extraction
description: How to run and validate OCR extraction against Vault Ledger's 3 target document formats (invoice, utility bill, receipt), including the mandatory vendor/description separation checkpoint.
---

# Vault Ledger OCR extraction

## Scope

Exactly 3 target document formats for the MVP: generic itemized vendor
invoice, utility-style bill, retail receipt. No other formats are in scope
yet (Report 1, "Explicitly NOT ASAP").

## Tooling

- OCR: `pytesseract` wrapping the `tesseract` binary
  (`src/vault_ledger/extraction/ocr.py`). Requires `tesseract` installed via
  `brew install tesseract` on macOS -- this is a real external dependency,
  check `which tesseract` before assuming OCR tests will run. Small/low-res
  images are auto-upscaled + contrast-corrected before OCR (`_prepare_for_ocr`)
  since Tesseract needs roughly 300-DPI-equivalent text height.
- PDFs: `src/vault_ledger/extraction/pdf.py`, routed to automatically from
  `extract_raw_text()` when the path ends in `.pdf`. First page only. Tries
  the native text layer first (via `pypdfium2`, exact and fast for
  born-digital PDFs); if that's empty/too sparse (a scanned PDF), rasterizes
  the page and runs it through the same OCR path as images.
- Field parsing: three tiers, escalating only on failure
  (`src/vault_ledger/extraction/field_parser.py`).
  1. Exact match against our synthetic label convention (`Label: value`).
  2. Real-world heuristic fallback (company-suffix-based vendor,
     table-header-based description, "Total" without a colon, ISO and
     written-month-name dates, paid/unpaid inferred from receipt language).
     Built from real documents encountered during development, not designed
     upfront -- keep adding to it as new formats show up, with a synthetic
     regression test (not the real file -- see below) for each one.

     **Load-bearing design rule, found via a real bug:** when a heuristic
     finds more than one plausible candidate for a field (e.g. two lines
     both look like "the total", or two lines both carry a company legal
     suffix), it must treat that the same as finding zero -- raise, and let
     tier 3 resolve it. It must NOT guess by picking whichever matched
     first, and must NOT try to disambiguate by hardcoding a list of
     qualifier phrases ("excluding tax", "before tax", ...) -- that list is
     always incomplete and always one phrasing behind. Bounded, stable
     lexical facts (currency symbols, legal-entity suffixes, month names)
     are fine to enumerate -- they're closed sets. Open-ended judgment
     calls about which of several plausible values is correct are not.
     See `_find_vendor` and `_find_amount_raw` in field_parser.py, and the
     module docstring, for the concrete pattern.

     A related trap a code review caught: don't overcorrect a bad guess
     into an overly broad rejection rule either. An early version of the
     vendor fix rejected any candidate line containing a digit at all
     (trying to reject "Page 1 of 1" generally) -- that would have broken
     legitimate vendor names like "7-Eleven" or "Store 24". The fix that
     survived review checks for actual ambiguity (multiple suffix matches)
     and a narrow, stable boilerplate-line pattern (pagination, a bare
     "Invoice"/"Receipt" label) instead of a content-free proxy signal.

     Escalating to tier 3 for one ambiguous field must not discard a
     *different* field's already-reliable heuristic result. `_infer_paid`
     has no ambiguous-candidates failure mode (it's a keyword-presence
     check, confident or not) -- `parse_fields` keeps its answer even when
     the LLM tier ran to resolve a different field, and only defers to the
     LLM's own paid/unpaid guess when the heuristic found no signal at all.
     A real invoice caught the LLM getting this wrong when escalation
     silently overrode an otherwise-correct heuristic result.
  3. Local LLM (`extraction/llm_fallback.py`), only reached when 1-2 both
     fail. Reads the whole document and proposes fields; its claimed
     amount is cross-checked against real currency values found by regex
     in the source text, so it can't hallucinate a number that isn't
     actually in the document. Requires Ollama running locally with a
     small model pulled (see that module's docstring) -- fails closed
     (falls through to the tier-2 error) if unavailable, never raises its
     own exception. Genuinely generalizes past keyword-based heuristics
     (verified on a document containing none of tier 1/2's trigger words
     at all -- no "Total", no "Description/Items/Service" -- see git
     history), at the cost of seconds instead of milliseconds per call.
- Synthetic samples: `src/vault_ledger/synthetic_samples.py` is the single
  source of truth for the 3 canonical sample documents, used by both the
  image generator (`data/synthetic/generate_documents.py`) and the tests.

## Local-only OCR is a deliberate decision, not a placeholder

Hosted Document AI APIs (AWS Textract, Google Document AI, Azure Document
Intelligence) were researched and explicitly rejected for privacy reasons:
by default they use customer document content to improve/train their
models unless you opt out, and even opted out, the document still leaves
the machine and is processed by a third party. That's incompatible with
Vault Ledger's privacy stance. **Do not add a hosted OCR/Document AI call
without raising it with the user first** -- this isn't a "we haven't gotten
to it yet" gap, it's a considered no.

Tier 3's local LLM (Ollama) stays inside this same constraint -- it's the
answer to "how do we generalize past heuristics without a hosted API," not
an exception to the local-only rule. The deployment model is: Ollama runs
on the company's own server/machine, the model weights are downloaded once
(a generic public model, not customer data) and cached on local disk, and
every extraction call after that is offline inference against the cache --
no network call, no third party, ever, after that one-time download. The
same local model is a plausible reuse point for account classification
(few-shot from recent corrections instead of a hosted call) and for the
plain-language summary feature -- not built yet, but the infrastructure
choice here doesn't foreclose it.

Model size on this dev machine (`qwen2.5:1.5b-instruct`, ~1.5B params) was
picked down from the 3-8B range because this specific machine (Intel
i3-1000NG4, 8GB RAM, no GPU) is close to a real lower bound for CPU-only
inference, not just "slower than cloud." Fine-tuning (as opposed to just
running) a model is a much heavier operation and would be impractically
slow on hardware like this -- Apple Silicon (MLX) or a modest GPU are the
realistic targets for an actual per-company fine-tuning step later.

Also avoid **PyMuPDF/`fitz`** for any PDF work -- it's AGPL-3.0, which would
force either open-sourcing the whole product or a paid Artifex commercial
license for a closed-source SaaS. `pypdfium2` (Apache-2.0/BSD) is the
chosen PDF library for exactly this reason.

## The mandatory checkpoint: vendor/description separation

Report 1's single biggest flagged risk: the two-field classifier gain is
entirely dependent on extraction quality. If vendor and description bleed
together into one string, the classifier never gets the benefit that
justified the two-field design.

**Every time extraction or field-parsing logic changes, run
`tests/test_field_parser.py::test_vendor_and_description_are_separate_fields`
and treat a failure as blocking** -- not a warning, not a "fix later." This
is a standalone checkpoint independent of classifier accuracy, per Report 1.

## How to run and validate against a new sample

1. Add the new sample to `src/vault_ledger/synthetic_samples.py` (or, once
   real documents exist, a real-document equivalent) with its expected
   vendor/description/amount/paid values.
2. Regenerate images: `python data/synthetic/generate_documents.py`.
3. Run OCR: `extract_raw_text(path)` from `ocr.py`.
4. Run field parsing: `parse_fields(raw_text)` from `field_parser.py`.
5. Assert the separation checkpoint above, then assert the parsed fields
   match expectations.

## What NOT to do

- Don't optimize OCR accuracy yet -- the loop working end-to-end is the
  priority, not extraction accuracy (Report 1, item 2).
- Don't reach for deep OCR models. Report 4's SME-paper benchmarks show
  template-matching and layout-feature approaches hit 95%+ on structured
  documents cheaply -- consistent with treating this as an engineering
  problem, not a research one.
- Don't let extraction merge vendor and description "just this once" for
  convenience -- see the checkpoint above.
- Don't commit a real document a user uploaded for testing into the repo or
  the test suite, even as a fixture -- it may contain personal data (an
  email address, a real billing account). Reproduce the tricky
  characteristic that broke parsing in a fabricated synthetic fixture
  instead (see the `_REALWORLD_RECEIPT_TEXT`-style fixtures in
  `test_field_parser.py` for the pattern).
- Don't expect tiers 1-2 to generalize indefinitely -- that's what tier 3
  (local LLM) is for. If tier 3 itself starts missing things regularly,
  that's a signal to revisit model size/prompt quality with the user, not
  to reach for a hosted API (still a considered no, see above).
- Don't let the LLM's output through unchecked. The amount-grounding check
  in `llm_fallback.py` is load-bearing -- a small model asked to extract a
  number will occasionally just make one up that looks plausible. Any new
  field pulled from the LLM tier should get a similar "is this actually in
  the source text" check before being trusted, not just whether the JSON
  parsed.
