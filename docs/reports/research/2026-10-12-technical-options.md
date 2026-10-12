# Technical options after the extraction fix round, 2026-10-12

By `research-tech-scout`. All sources read on 2026-10-12. Each claim is marked
**S** (sourced: the page says it) or **I** (my inference). Nothing here has been
run on our documents; benchmark figures are what others measured, not what we
would get. Excluded on purpose: everything already being built on
`extraction-locale` (locale profiles, strict amount reader, date validation,
grounding, orientation, local contrast, word-confidence gate).

## What decides most choices: the machine

Checked on the dev machine (Intel x86_64, macOS 15.7, Python 3.9.6) with
`pip index versions`:

- `onnxruntime` installs at most 1.19.2. Upstream stopped shipping Intel-Mac
  binaries and raised the minimum macOS to 14 in the 1.24 line (S:
  https://github.com/microsoft/onnxruntime/releases/tag/v1.24.1).
- `torch` installs at most 2.2.2; 2.2.x was the last Intel-Mac release (S:
  https://dev-discuss.pytorch.org/t/pytorch-macos-x86-builds-deprecation-starting-january-2024/1690,
  seen via search summary, not opened).
- I: anything built on PyTorch (docTR, EasyOCR, Docling, SetFit, GLiNER) is
  frozen on old versions on this machine. This says nothing about Windows or
  Apple-silicon customers, whose hardware we have not been told.

## Recommendation per pipeline step

| Step | Try first | Runner-up | Ruled out |
|---|---|---|---|
| OCR | RapidOCR as a second engine, only for pages that fail the Tesseract confidence gate | Tesseract `tessdata_best` models | Surya, EasyOCR, Docling as OCR, PaddleOCR-VL |
| Layout and tables | Row rebuilding from word boxes we already have (`pytesseract.image_to_data`, `pypdfium2` character boxes) | `pdfplumber` (native PDF), `img2table` (scans) | PyMuPDF, Docling/TableFormer, Granite-Docling |
| Field model (tier 3) | Shorter prompt plus a JSON schema, then the already-pulled `qwen3:1.7b` with thinking off | NuExtract-1.5-tiny | LFM2-Extract, any vision-language model on the i3 |
| Classification | Vendor memory in front of the classifier, full retrain on each confirmed batch | Static embeddings (`model2vec`) as a third feature block | SetFit for now, `partial_fit`, isotonic calibration |
| No-OCR path | Read UBL XML (NLCIUS / Peppol BIS 3) directly | Embedded XML in PDF via `factur-x` | Building a Peppol connection |

## 1. OCR

**RapidOCR.** PaddleOCR's detection and recognition models converted to ONNX;
runs on ONNX Runtime or OpenVINO, no PaddlePaddle needed. Code Apache 2.0;
models redistributed under PaddleOCR's Apache 2.0 (S:
https://github.com/RapidAI/RapidOCR). PaddleOCR itself is Apache 2.0, latest
3.7.0 of 2026-06-11, with a 109-language recognition model (S:
https://github.com/PaddlePaddle/PaddleOCR).

- Evidence: one vendor-run benchmark on 361 SROIE English receipts reported
  character error rate 19.7% docTR 1.0.1, 20.5% PaddleOCR 3.7.0, 28.3% EasyOCR,
  33.6% Tesseract 5.3.4 (S:
  https://imagetotable.ai/references/receipt-ocr-benchmark-results). Limits:
  run on an RTX 4090, not a CPU; the vendor sells a document product; code not
  public; PaddleOCR proper, not the ONNX conversion; no Dutch.
- Not verified: model file sizes (only community figures found, roughly 8 MB
  mobile to 80 MB server per model), whether word-level confidences are
  returned, quality on Dutch, CPU time on an i3.
- Plugs in: a second branch in `extraction/ocr.py`, called only when the
  word-confidence gate fails. I: keeping Tesseract first preserves the
  sub-second path.
- Risk: the Intel-Mac ONNX Runtime freeze above; a second engine to package.
- Experiment: `pip install rapidocr onnxruntime` in a scratch venv, run the 24
  degraded images plus the forced-OCR real invoice, compare fields correct and
  seconds per page against the post-fix Tesseract result. Kill it if it does
  not recover at least the gradient-lighting and 25%-size cases, or takes over
  about 10 s a page.

**Runner-up: `tessdata_best`.** The more accurate Tesseract LSTM models, Apache
2.0 (S: https://github.com/tesseract-ocr/tessdata_best). A file swap, no new
dependency. I found no published comparison against the default models on
receipts, so the gain is unknown. Experiment: same 24 images, same measure.

**Ruled out.** Surya: weights free only under $5M funding or revenue, otherwise
a paid licence (S: https://github.com/datalab-to/surya). EasyOCR: worse than
PaddleOCR in the one benchmark and needs PyTorch. Docling as OCR: 58.4% error
in the same benchmark. PaddleOCR-VL: a 0.9B-parameter model (S: PaddleOCR
README); I: too slow for an i3 that needs 21-27 s for 1.5B text-only.

## 2. Layout and tables

**Try first: use the positions we already get.** Both installed libraries
expose them: `pytesseract.image_to_data` and `pypdfium2`'s `get_charbox` /
`get_text_bounded` (checked in `.venv`). I: grouping words into rows by
vertical overlap, then pairing a label with the right-most amount on its row,
addresses failure 10 with no new dependency, and gives tier 3 clean rows.
The review already lists this as "later"; the point here is that no library is
needed. Experiment: on the real invoice forced through OCR, check that "Total"
and its amount land in the same row and vendor is split from "Bill to".

**Runner-up.** `pdfplumber`: MIT, on MIT `pdfminer.six`, word boxes and table
finding for native PDFs (S: https://github.com/jsvine/pdfplumber). `img2table`:
MIT, OpenCV line detection with Tesseract or RapidOCR underneath, positioned as
a lighter CPU alternative to neural table models; borderless tables are opt-in
and less reliable (S: https://github.com/xavctn/img2table).

**Ruled out.** PyMuPDF: AGPL or paid (S:
https://pymupdf.readthedocs.io/en/latest/about.html). Docling: MIT code but
Python 3.10+ and model licences separate (S:
https://github.com/docling-project/docling); needs PyTorch (I). Granite-Docling
258M: Apache 2.0, but English only and meant to be used inside Docling (S:
https://huggingface.co/ibm-granite/granite-docling-258M).

## 3. Field model, tier 3

`llm_fallback.py` sends up to 4000 characters with `format: "json"`,
temperature 0, model kept resident. I: on a 2-core CPU most of the 21-27 s is
reading the prompt, so the cheapest gain is sending less.

- **Try first.** (a) Send only the rows the rules could not resolve, using
  section 2's rows. (b) Pass a JSON schema to `format` instead of `"json"`;
  Ollama enforces the schema and recommends temperature 0 (S:
  https://docs.ollama.com/capabilities/structured-outputs). (c) Compare
  `qwen3:1.7b`, already pulled on this machine: Apache 2.0, 100+ languages,
  thinking on by default and must be switched off (S:
  https://huggingface.co/Qwen/Qwen3-1.7B). The card states no benchmark.
  Experiment: the 2 real PDFs and 3 Dutch snippets, three runs each, warm; record
  seconds and fields grounded. This also fills the "repeatability" gap.
- **Runner-up: NuExtract-1.5-tiny.** MIT, 0.5B, fine-tuned from Qwen2.5-0.5B,
  takes a JSON template and is trained to copy text as-is, which suits our
  grounding check. Languages listed do not include Dutch; results are charts
  only (S: https://huggingface.co/numind/NuExtract-1.5-tiny). Needs a GGUF
  build; I did not verify one exists.
- **Ruled out.** LFM2-Extract (350M, 1.2B): commercial use ends above $10M
  revenue, Dutch not listed, evaluation self-reported (S:
  https://huggingface.co/LiquidAI/LFM2-350M-Extract,
  https://www.liquid.ai/lfm-license). Not copyleft, but a conditional licence
  inside a product we sell. Gemma: licence not checked.
- Runtime: llama.cpp is MIT with JSON-schema grammars (S:
  https://github.com/ggml-org/llama.cpp). I: no reason to leave Ollama until a
  model we want is missing from it.

## 4. Classification

I: no method fixes 22 rows over 8 accounts. The 0.62 ceiling is what a
default-regularised `LogisticRegression` gives on that little data; it is a
data problem before it is a model problem. Calibration cannot be fitted either:
scikit-learn advises sigmoid for small samples, isotonic only above about 1000,
and requires calibration data disjoint from training (S:
https://scikit-learn.org/stable/modules/calibration.html).

- **Try first: vendor memory.** Before the classifier, look up the normalised
  vendor in this company's confirmed entries; if every past entry used one
  account, propose it with the count shown. I: it learns from one correction,
  needs no training data, and is explainable. No published evidence found;
  DragoNet's finding that vendor alone is weak was across a whole bank, not one
  company's repeat suppliers. Plugs into `pipeline.py` ahead of `predict`;
  rules layer untouched. Retrain the existing model in full on each confirmed
  batch (milliseconds at this size). Experiment: replay the customer's first
  real export in date order; measure share auto-proposed and share wrong.
- **Runner-up: `model2vec` static embeddings.** MIT, numpy-only at inference,
  8-30 MB English models, a 128M-parameter multilingual one (S:
  https://github.com/MinishLab/model2vec; installs here as 0.7.0). Embed vendor
  and description separately and stack beside the two TF-IDF blocks, keeping
  the two-field design. The README gives no scores. Experiment: vendor-disjoint
  split on whichever synthetic set passes its gates, with and without the block.
- **Ruled out.** SetFit: Apache 2.0, 8 examples per class matched full
  fine-tuning on one sentiment dataset (S: https://github.com/huggingface/setfit),
  but needs PyTorch and is the Transformer route the classifier skill forbids.
  `partial_fit`: supported by `SGDClassifier` with a stateless hasher (S:
  https://scikit-learn.org/stable/computing/scaling_strategies.html), needless
  while a full retrain is instant.

## 5. Structured e-invoices

Dutch B2B e-invoicing is voluntary; government has had to accept EN 16931
invoices since 2019; formats are Peppol BIS 3.0 and NLCIUS (SI-UBL 2.0) (S:
European Commission country page, updated 2025-08-14:
https://ec.europa.eu/digital-building-blocks/sites/spaces/DIGITAL/pages/467108895/eInvoicing+in+The+Netherlands).
Vendor sites report a Dutch B2B mandate proposed for 2030; I could not confirm
that at a government source and the Commission page says no plans. Treat as
unverified.

- **Try first:** accept a `.xml` upload and read vendor, date, total and lines
  with the standard library. Fields are exact; no OCR, no model. New module
  beside `pdf.py`. Experiment: ask the customer for three XML invoices they
  have received. If they have none, park this.
- **Runner-up:** `factur-x` (BSD, on BSD `pypdf`, version 7.6 of 2026-10-11)
  pulls embedded XML out of Factur-X / ZUGFeRD PDFs (S:
  https://github.com/akretion/factur-x). I: a Franco-German format, less likely
  in a Dutch inbox.
- **Ruled out:** connecting to Peppol; it is a network service, outside the
  on-device promise.

## Open points for the skeptic

- The PyTorch cut-off and the SetFit paper figures were read from search
  summaries or the README, not the primary page.
- RapidOCR sizes, Dutch quality and confidence output are unverified.
- Customer hardware and operating system are unknown; the Intel-Mac limits may
  not apply to them.
