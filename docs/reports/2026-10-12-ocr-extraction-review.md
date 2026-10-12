# OCR and extraction review, 2026-10-12

Measured by `ocr-runner` on branch `synth-data` (extraction code identical to
`master` at f9fa142). Read-only run; nothing was changed. Fixes are being built
on branch `extraction-locale`.

Scope of the evidence: 9 synthetic sample documents, 2 real PDFs (one English
invoice, one Dutch telecom bill), 24 degraded copies of the 3 sample images,
and 3 hand-written Dutch text snippets. No real scan or phone photo was tested.

## Method in use

Everything runs on the machine. No document is sent to an outside service.

| Step | Method | Notes |
|---|---|---|
| PDF text | `pypdfium2` native text layer | First page only |
| Image / scanned PDF | Tesseract 5.5.3, `eng` only | EXIF upright, greyscale, upscale below 900 px, global autocontrast; scanned PDFs rasterised at 200 DPI |
| Fields, tier 1 | Exact `Label: value` lines | Milliseconds |
| Fields, tier 2 | Hand-written rules | Company suffix, the word "Total", table header, three date formats; escalates on more than one candidate |
| Fields, tier 3 | Local model via Ollama (`qwen2.5:1.5b-instruct`) | Amount must appear in the document text, else the answer is discarded |

## Results

| Input | Result |
|---|---|
| 9 synthetic samples (PNG, native PDF, scanned PDF) | 9 of 9 correct at tier 1, under 1 s each (first OCR call 1.9 s) |
| Real English invoice (native PDF) | Correct, via tier 3, 21 s |
| Same invoice forced through OCR | Correct except description ("Pro1"), 29 s |
| Real Dutch telecom bill | No output (both native and OCR) |
| 3 Dutch text snippets | 0 of 3 returned fields |
| 24 degraded sample images | 15 of 24 fully correct |

Degraded variants per document (invoice / utility bill / receipt):

| Variant | Outcome |
|---|---|
| 40% size, 2 degree tilt, uniform low contrast, JPEG quality 20 | all correct |
| 25% size | error / **silently wrong on all five fields** / error |
| 5 degree tilt | date lost / vendor and date wrong / date lost |
| 90 degree rotation | all three fail closed, 6-7 s each in tier 3 |
| Blur radius 1.5 | vendor casing only / date lost / **description invented by the model** |
| Gradient lighting plus noise | empty OCR on all three |

## Failure modes, most serious first

1. **Comma-decimal amounts cannot be read at any tier.** The amount pattern
   requires a dot decimal. The local model had the right amount on 4 of 4 Dutch
   inputs and was rejected each time, because the grounding check uses the same
   pattern.
2. **Silent wrong amount on European thousands format.** `Total: € 1.234,56`
   returns 1.23 at tier 1 with no error.
3. **Silent garbage on low-resolution input.** The 25% utility bill returned
   2712.10 for a true 212.10, a garbled vendor and a flipped paid flag, with no
   error. There is no OCR confidence gate.
4. **Dates are fragile and never validated.** A tilt splits digits
   (`03/1 4/2026`) and the date silently becomes empty; `93/01/2026` was
   accepted; `dd-mm-yyyy`, `dd.mm.yyyy` and day-first month names are not
   recognised; the date is stored as a raw string.
5. **The local model can return text that is not in the document.** Only the
   amount is checked. Observed: an invented description, dates rewritten to ISO
   form, and the document type returned as the vendor.
6. **No orientation handling**, although Tesseract's orientation data (`osd`)
   is installed.
7. **English-only rules.** No Dutch labels, legal suffixes or paid keywords, so
   any Dutch document depends entirely on tier 3.
8. **First page only.**
9. **Tier-3 latency:** 21-27 s per real document on this machine.
10. **Table and column order.** OCR separates labels from their amounts and
    merges the vendor line with the "Bill to" block; it worked only because the
    model coped.
11. **Uneven lighting gives empty OCR**; the contrast step is global.

Vendor and description were never merged into one field in any run that
returned fields.

## Adjustments

In progress on `extraction-locale` (Dutch itself is deliberately not included):

- Locale profile: every language-specific set (labels, suffixes, month names,
  paid words, number and date style, Tesseract language) in one profile,
  English as default, so a Dutch profile can be added later without touching
  the parsing logic.
- One strict amount reader shared by all tiers and the grounding check; it
  never returns a truncated number.
- Dates validated as real calendar dates and normalised.
- Grounding extended to vendor, description and date.
- Orientation correction, local contrast correction, and a word-confidence
  score; a poorly read document goes to human review instead of bulk confirm.

Later, not started:

- Dutch profile, plus the `nld` Tesseract language pack
  (`brew install tesseract-lang`).
- All pages of a PDF.
- Use word positions to keep table columns together.
- Try a faster or newer local model for tier 3.

## Not tested

- Real scans or phone photos.
- Dutch text with accented characters through OCR.
- Repeatability of the local model (one run per input), cold versus warm
  timing, behaviour with Ollama stopped.
- Encrypted or image-only real PDFs, currencies other than EUR and USD, batch
  concurrency.
