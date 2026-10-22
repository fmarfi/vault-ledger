Background read: `docs/background.md` in full including the ML engine block; spec `docs/reports/vaultledger-ml-implementation-spec.md` sections 2, 6.4, 8.3 to 10, 11, 12, 14; `docs/reports/report-4-paper-reference-digest.md`; `.claude/worktrees/ml-engine/vaultledger-ml/pyproject.toml`; my row (2026-10-13, exec-model, licences and DragoNet figures) in `docs/reports/research/requests.md`. No research finding has passed the skeptic, so none is used here.

# ML engine dependencies: licences, and the DragoNet figures checked against the paper

- Scout: research-tech-scout (stand-in following the definition file). Date read for every source: 2026-10-13.
- Status: draft, not passed by the skeptic. Nobody builds on or quotes this until `requests.md` says "passed".
- Why this task exists: the product is closed source with a no-copyleft decision, and the ML engine spec quotes figures from arXiv:2312.07730 marked [VERIFY]; this report says what may ship and what may be quoted. It does not block ML-M1 to ML-M11.
- I am not a lawyer. Licence verdicts are a reading of the licence texts against the project decision, not legal advice.

## How it was checked, and the limits

1. Licence of each named package: the licence file in the project's own repository, fetched today (links in the table).
2. What each wheel pulls in or bundles on Windows: metadata of the wheels already installed in `.claude/worktrees/ml-engine/vaultledger-ml/.venv` (Python 3.12, win_amd64). Only `METADATA`, `RECORD`, licence and notice files, SBOM files, file names and the Windows file-properties of four DLLs were read. Nothing was installed, imported or executed. Cited below as "local wheel".
3. Versions seen: torch 2.14.1+cpu, onnx 1.23.2, onnxruntime 1.31.0, onnxscript 0.7.2, sentencepiece 0.2.2, scikit-learn 1.9.1, scipy 1.18.1, numpy 2.5.4, pandas 3.0.6, rapidfuzz 3.14.6, pydantic 2.14.1, pydantic-core 2.50.1, pyyaml 6.0.3, jsonschema 4.26.0, pytest 9.1.1, hypothesis 6.169.0, protobuf 7.36.2, joblib 1.6.0, threadpoolctl 3.7.0. Findings about bundled files hold for these versions on Windows x64 only. Mac and Linux wheels bundle different files and were not checked.
4. The paper: the arXiv abstract page and the arXiv HTML full text (v1). The PDF could not be opened on this machine (no PDF renderer), and the fetch tool returns a model-made reading of the page rather than the raw text. I read the HTML three times with different questions and the numbers agreed each time, but the skeptic should check Tables 3 to 5 in the PDF by eye.

## Part 1: licences

### 1.1 Classification used

| Group | Packages | Basis |
|---|---|---|
| Ships at runtime | numpy, pydantic, pyyaml, jsonschema, rapidfuzz, sentencepiece, onnxruntime | `[project] dependencies` in `pyproject.toml`; spec 6.4.6 ("inference path needs ... only onnxruntime, sentencepiece and numpy") |
| Training only | torch, onnx, onnxscript, scikit-learn, pandas | `train` extra in `pyproject.toml`. Two are open: torch (spec 6.4.6 [OPEN], on-device fine-tuning) and scikit-learn (spec 6.4.7: the baseline is the fallback model) |
| Test only | pytest, hypothesis | `dev` extra |

### 1.2 The four findings that need a decision or an action

**F1. Weak copyleft (MPL-2.0) sits inside a runtime dependency. Verdict on onnxruntime: unclear until the user rules.**
- `sourced`: the notice file shipped inside the onnxruntime wheel lists Eigen under "MPL v2.0" (local wheel, `onnxruntime/ThirdPartyNotices.txt`, section "Eigen"; same in the repository: https://github.com/microsoft/onnxruntime/blob/main/ThirdPartyNotices.txt). Eigen states its main licence is MPL2: https://gitlab.com/libeigen/eigen/-/blob/master/COPYING.README.
- `sourced`: `ml_dtypes` (pulled in by onnx and onnxscript, training only) ships a `LICENSE.eigen` file that is the MPL 2.0 text (local wheel).
- Not verified: that Eigen code is actually compiled into the Windows CPU wheel's `onnxruntime.dll`. The notice file lists everything the project may incorporate across all builds (it also lists Android and CUDA components), so the listing alone does not prove it. `my inference`: it very probably is, since Microsoft lists it first among the notices; treat it as present.
- Why it matters: the main executive ruled `hypothesis` test-only because it is MPL-2.0. The same licence in a runtime dependency has to be judged by the same rule, or the rule has to be stated more precisely.
- What MPL-2.0 asks (`sourced`, Mozilla's FAQ, which says it is not the licence itself: https://www.mozilla.org/en-US/MPL/2.0/FAQ/): the copyleft is per file; our own files need not be released; static linking into a proprietary program is allowed; the distributor must tell recipients where the MPL-covered source can be obtained; changes to MPL files must be published. We change no Eigen file.
- `my inference`: if the decision means "nothing that could force our source open", MPL-2.0 used unmodified inside a third-party binary does not do that, and onnxruntime is fine with a notice in the installer. If the decision means "no licence from the copyleft family at all", onnxruntime is a blocker and so is every ONNX-based inference path. Only the user can say which is meant.

**F2. GPL-with-exception code is inside the numpy and scipy wheels. Verdict: fine, but the user should see it once.**
- `sourced`: the licence file inside both wheels lists, for `libscipy_openblas*.dll`: OpenBLAS (BSD-3-Clause), LAPACK (BSD-3-Clause-Open-MPI), and "GCC runtime library ... statically linked ... License: GPL-3.0-or-later WITH GCC-exception-3.1" (local wheel: `numpy-2.5.4.dist-info/licenses/LICENSE.txt` lines 40 to 135; `scipy-1.18.1.dist-info/LICENSE.txt` lines 41 to 136).
- `sourced`: the GNU FAQ on that exception says a program combined with these runtime libraries may be distributed under terms of the distributor's choice when it was built by an "eligible compilation process", and that the GPL then does not extend to the program: https://www.gnu.org/licenses/gcc-exception-3.1-faq.html.
- `my inference`: this is the normal state of every product that ships numpy; the exception exists for this case; no source duty reaches Vault Ledger. It is listed because the decision's wording ("no AGPL or other copyleft") read literally would catch it. numpy is a runtime dependency, so this ships in every build.

**F3. Shipping torch brings an Intel-proprietary DLL with no licence text in the wheel. Verdict on torch if shipped: unclear.**
- `sourced`: `torch/lib/libiomp5md.dll` in the Windows CPU wheel has file properties "Intel Corporation, Intel(R) OpenMP* Runtime Library" (local wheel, Windows file properties). The wheel's licence folder has an LLVM OpenMP licence and about a hundred others, but no Intel licence text; a search of every licence file in the wheel for GPL, LGPL, MPL or Intel licence names found none (local wheel). PyTorch's `NOTICE` does not mention Intel either: https://github.com/pytorch/pytorch/blob/main/NOTICE.
- `sourced`: Intel's own PyPI package of this runtime is marked "Other/Proprietary License (Intel End User License Agreement for Developer Tools)": https://pypi.org/project/intel-openmp/. Intel's licence index lists oneMKL under the proprietary "Intel Simplified Software License", which allows redistribution of unmodified binaries with the notice kept and forbids reverse engineering: https://www.intel.com/content/www/us/en/developer/articles/license/end-user-license-agreement.html.
- Not verified: whether Intel MKL is linked into `torch_cpu.dll` (PyTorch's Windows notes name MKL as a build component but do not say what the official wheel contains: https://docs.pytorch.org/docs/2.14/notes/windows.html), and under exactly which Intel licence the DLL in the wheel is redistributed. I could not find the wheel build script.
- `my inference`: this is not copyleft, so it does not breach the decision as worded. It is a redistribution-terms question: we would pass on a proprietary binary whose terms the wheel does not carry. Separately, `torch_cpu.dll` alone is about 306 MB (local wheel), next to a spec target of a model under 25 MB (C2).
- `my inference`: the cheap way out is already in the spec: `finetune_backend` numpy heads (6.4.6, section 12). With that, torch stays training-only and the question disappears.

**F4. Not a licence matter, but it touches the first decision in the background: the onnxruntime wheel says it sends telemetry by default.**
- `sourced`: `onnxruntime/Privacy.md` inside the installed 1.31.0 wheel says official builds have telemetry on by default; that Windows official releases use a built-in telemetry SDK which sends trace events to Microsoft over HTTPS; and that setting `ORT_DISABLE_TELEMETRY=1` before the runtime starts prevents the uploader, the events and a persistent device identifier from being created (local wheel; repository copy: https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md). The notice file also lists `microsoft/cpp_client_telemetry`.
- Not verified: that this particular PyPI wheel contains the uploader, what the events contain, and that the switch works. I observed no network traffic; I only read the file.
- `my inference`: spec constraint C1 and section 11 forbid any network call in the inference path. Until someone measures it, the inference code should set `ORT_DISABLE_TELEMETRY=1` before importing onnxruntime, and a test should check that. Cheap experiment: run one inference with the network monitored (or blocked by firewall rule and logged), with and without the variable. This should become its own research request; it is outside my row.

### 1.3 Per package

"Local wheel" means the metadata described above. Verdict words: fine / fine only if not shipped / blocker / unclear.

| Package | Licence in its own repository | Notable things pulled in or bundled on Windows (licence) | Group | Verdict and reason |
|---|---|---|---|---|
| torch | BSD-3-Clause style: https://github.com/pytorch/pytorch/blob/main/LICENSE `sourced` | Wheel declares "Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT". Bundles `libiomp5md.dll` (Intel, proprietary, see F3), `uv.dll` (libuv, licence file in wheel), mimalloc, sleef, XNNPACK, protobuf and others with their licence files. Requires filelock (MIT), typing-extensions (PSF-2.0), setuptools, sympy (BSD), mpmath (BSD), networkx (BSD-3), jinja2 and markupsafe (BSD-3), fsspec (BSD-3). All local wheel, `sourced` | Training only; open in spec 6.4.6 | **Not shipped: fine.** Using it on our own machines distributes nothing. **Shipped for on-device fine-tuning: unclear** (F3: Intel binary without its terms, MKL not verified). No copyleft found |
| onnx | Apache-2.0: https://github.com/onnx/onnx/blob/main/LICENSE `sourced` | protobuf (BSD-3-Clause: https://github.com/protocolbuffers/protobuf/blob/main/LICENSE), ml_dtypes (Apache-2.0, plus Eigen MPL-2.0 file, see F1), typing-extensions, numpy; bundles `msvcp140.dll` (Microsoft runtime) | Training only | **Fine only if not shipped**, because of the MPL file in ml_dtypes; if F1 is ruled acceptable it becomes fine. Spec gives no reason to ship it |
| onnxruntime | MIT: https://github.com/microsoft/onnxruntime/blob/main/LICENSE `sourced` | Requires flatbuffers (Apache 2.0, wheel metadata only), numpy, packaging (Apache-2.0 OR BSD-2-Clause), protobuf (BSD-3). The DLL's notice file lists Eigen (MPL-2.0), a telemetry SDK, and Mbed TLS used under Apache-2.0. No separate math DLL in the wheel | Ships at runtime | **Unclear**: F1 (MPL-2.0 inside) needs the user's reading of the decision. Also F4 (telemetry) before it runs on a customer machine. Apache and MIT notices must be reproduced in the installer |
| onnxscript | MIT: https://github.com/microsoft/onnxscript/blob/main/LICENSE `sourced` | onnx, onnx_ir (Apache-2.0), ml_dtypes, sympy, numpy, packaging, typing-extensions | Training only | **Fine only if not shipped** (same ml_dtypes point as onnx). Export tool; no reason to ship |
| sentencepiece | Apache-2.0: https://github.com/google/sentencepiece/blob/master/LICENSE `sourced` | No Python dependencies. Repository vendors `third_party/darts_clone`, `libsais`, `rapidhash` (https://github.com/google/sentencepiece/tree/master/third_party); their licences were not read. The wheel contains no licence file at all (local wheel) | Ships at runtime | **Fine.** Two actions: we must add the Apache-2.0 text ourselves since the wheel has none; the skeptic or a follow-up should read the three vendored licences (unverified) |
| scikit-learn | BSD-3-Clause: https://github.com/scikit-learn/scikit-learn/blob/main/COPYING `sourced` | scipy (BSD-3-Clause: https://github.com/scipy/scipy/blob/main/LICENSE.txt; wheel bundles OpenBLAS with the GCC runtime, see F2), joblib (BSD-3: https://github.com/joblib/joblib/blob/main/LICENSE.txt), threadpoolctl (BSD-3: https://github.com/joblib/threadpoolctl/blob/master/LICENSE), narwhals (MIT), numpy; in this environment also cloudpickle (BSD-3). Bundles `vcomp140.dll` and `msvcp140.dll` (Microsoft runtime files, named in the wheel's COPYING) | Training only; fallback model per 6.4.7 | **Training only: fine. Shipped as the fallback: fine** on licence (F2 note applies through scipy). But see 1.4: today it cannot be the fallback in an installed product |
| numpy | BSD-3-Clause: https://github.com/numpy/numpy/blob/main/LICENSE.txt `sourced` | Wheel declares "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0". Bundles `libscipy_openblas64_*.dll`: OpenBLAS BSD-3, LAPACK BSD-3-Clause-Open-MPI, GCC runtime GPL-3.0-or-later WITH GCC-exception-3.1; and `msvcp140.dll` | Ships at runtime | **Fine**, with F2 shown to the user once |
| pandas | BSD-3-Clause: https://github.com/pandas-dev/pandas/blob/main/LICENSE `sourced` | python-dateutil (dual Apache-2.0 / BSD per its licence file), six (MIT), tzdata (Apache-2.0), numpy; bundles `msvcp140.dll` | Training only | **Fine** either way. No copyleft found. The draft package code imports it nowhere today (import search of `vaultledger/`, 2026-10-13) |
| rapidfuzz | MIT: https://github.com/rapidfuzz/RapidFuzz/blob/main/LICENSE `sourced` | No Python dependencies; bundles `msvcp140.dll` | Ships at runtime | **Fine** |
| pydantic | MIT: https://github.com/pydantic/pydantic/blob/main/LICENSE `sourced` | pydantic-core (MIT: https://github.com/pydantic/pydantic-core/blob/main/LICENSE; its SBOM lists about 100 Rust crates, all MIT, Apache-2.0, Unicode, Zlib, BSD or Unlicense; one is "MIT OR Apache-2.0 OR LGPL-2.1-or-later", a choice, so MIT applies), annotated-types (MIT), typing-extensions (PSF-2.0), typing-inspection (MIT) | Ships at runtime | **Fine** |
| pyyaml | MIT: https://github.com/yaml/pyyaml/blob/main/LICENSE `sourced` | No dependencies. The wheel has a compiled `_yaml` extension; `my inference`: it contains libyaml, whose licence I did not read today (unverified) | Ships at runtime | **Fine**, libyaml licence to be confirmed by the skeptic |
| jsonschema | MIT: https://github.com/python-jsonschema/jsonschema/blob/main/COPYING `sourced` | attrs (MIT), jsonschema-specifications (MIT), referencing (MIT), rpds-py (MIT; its SBOM lists only MIT / Apache-2.0 / Unicode crates). Wheel metadata only for these four | Ships at runtime | **Fine** |
| pytest | MIT: https://github.com/pytest-dev/pytest/blob/main/LICENSE `sourced` | pluggy (MIT), iniconfig (MIT), packaging, pygments (BSD-2-Clause), colorama on Windows (licence file present, not read) | Test only | **Fine**; no reason to ship |
| hypothesis | MPL-2.0, confirmed: https://github.com/HypothesisWorks/hypothesis/blob/master/LICENSE.txt `sourced`; wheel metadata says `License-Expression: MPL-2.0` | sortedcontainers (Apache 2.0) | Test only, by ruling | **Fine only if not shipped.** See 1.5 |

Microsoft runtime DLLs (`msvcp140.dll`, `vcomp140.dll`) are proprietary but listed by Microsoft as redistributable, unmodified, by holders of a Visual Studio licence, under that licence's terms: https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution (`sourced`). `my inference`: whoever builds our installer needs to check that they hold such a licence or rely on the copies inside the wheels; not a copyleft matter.

### 1.4 Things the classification exposed

- `sourced` (pyproject and spec 6.4.7): scikit-learn is in the `train` extra, yet the spec calls the baseline "the fallback if DragoNet doesn't beat it on real data". A product installed without extras cannot load a scikit-learn model. `my inference`: either scikit-learn (with scipy, joblib, threadpoolctl) moves to the runtime dependencies when the fallback is chosen, or the baseline is exported to ONNX or to plain numpy arrays so the runtime list does not change. Licence-wise both are fine. A pickled scikit-learn model is also tied to the scikit-learn version that wrote it, which matters for an installed product. Decide when real data picks the model, not now.
- `my inference`: the runtime list is small, so the obligations for the installer are: one third-party notices file with the MIT, BSD, Apache-2.0 texts and copyright lines, the numpy bundled-licence text, the onnxruntime notices file, and (if F1 is accepted) a line saying where Eigen's source is.

### 1.5 hypothesis: what would breach the test-only ruling

`my inference`, from the pyproject layout and the files seen in the environment:

1. Moving `hypothesis` from the `dev` extra into `[project] dependencies` or the `train` extra.
2. Importing `hypothesis` from any module under `vaultledger/` (property tests live in `tests/` only; no strategies or helpers in the package).
3. Building the installer from the development environment, or with `pip install ".[dev]"`. A bundler that copies `site-packages` would also pick up the top-level files `_hypothesis_pytestplugin.py`, `_hypothesis_ftz_detector.py` and `_hypothesis_globals.py`.
4. Shipping the `tests/` folder in a way that makes the product install or need hypothesis.
5. Copying code out of hypothesis into our own files.

Check that keeps it true: build the product environment from the runtime dependencies only and assert that `hypothesis`, `pytest`, `torch`, `onnx`, `onnxscript`, `pandas` are absent from it. Today the draft package imports none of them (import search, 2026-10-13).

## Part 2: what arXiv:2312.07730 says

Paper: Busson et al., "Hierarchical Classification of Financial Transactions Through Context-Fusion of Transformer-based Embeddings and Taxonomy-aware Attention Layer", arXiv:2312.07730v1, submitted 12 December 2023. Abstract: https://arxiv.org/abs/2312.07730. Full text read: https://arxiv.org/html/2312.07730v1.

What it was measured on (`sourced`, Section 3): two private data sets of BTG Pactual, a Brazilian bank; 151,867 card transactions and 151,838 current-account transactions from April to June 2021; labelled by 8 volunteers into 15 macro and 82 micro categories defined by the bank's specialists. The activity text of the account data is in Brazilian Portuguese; the language of merchant names and of the card activity text is not stated. Evaluation: "the same 10-fold split" (Section 5); the paper does not say the split was grouped by merchant, does not report spread across folds, and does not say how F1 is averaged.

None of these figures says anything about what Vault Ledger would get. Different country, language, taxonomy, input fields and document type; and `my inference`: an ungrouped split lets the same merchant appear in training and test, which our own evaluation forbids (spec section 11), so our numbers should be expected to be lower for that reason alone.

| Claim in the spec or report 4 | What the paper states | Where | Verdict |
|---|---|---|---|
| Merchant name alone about 57 to 59% macro-F1 | Best model (Transformer), merchant name only, F1 at macro-category level: 56.78 (card), 59.14 (current account). Micro-category level: 46.02 and 45.15 | Table 3 | Numbers supported. The wording is not: in the paper "macro" is the taxonomy level, and the averaging of F1 is not stated. "macro-F1" must not be read as macro-averaged F1 |
| Activity field alone about 89 to 93% | Transformer, activity only, macro-category F1: 89.07 (card), 93.24 (current account). Micro: 76.98 and 85.41. The paper says this fails when a transaction is registered under the wrong activity | Table 4 and the discussion in Section 5 | Supported |
| Both fused about 93% macro-F1 at macro level | Transformer + Context Fusion, macro-category F1: 93.02 (card), 95.07 (current account). Abstract: 93% and 95%. A plain Transformer on both fields without the fusion layer: 92.53 and 93.79 | Table 5; abstract | Supported for the card data only. The spec leaves out the 95.07 on the other data set; "macro-F1" wording as above |
| The mask adds about 1 point on micro | Micro-category F1 with the taxonomy-aware layer against without: 84.54 against 83.66 (card, +0.88), 86.66 against 85.67 (current account, +0.99). The authors state 0.9% and 1%. Macro-category figures are unchanged by it. It is applied at inference only | Table 5; Section 4.4; Section 5 | Supported |
| Data set size, 151,867 card transactions (report 4 line 17) | 151,867 card and 151,838 current-account transactions | Section 3 | Supported. The spec does not carry the number; the request's "151k+" is right |
| The fusion operator | Concatenate the two contextual embeddings, pass through a feed-forward network with ReLU, then a linear layer with sigmoid; one such output per head (macro and micro) | Section 4.3 | The spec's `concat[hA, hB, hA*hB, abs(hA-hB), hN]` with GELU is not the paper's. The spec already says its values are its own; it should say the same of the operator |
| The encoder | A stack of Transformer encoder layers over word-level token embeddings with positional encoding, multi-head attention and a two-layer ReLU feed-forward block | Sections 4.1, 4.2 | Supported in general terms |
| Layer sizes (embedding size, layers, heads, hidden units, sequence length, vocabulary, optimizer, epochs, batch size) | Not in the paper. All of these appear only as symbols or not at all | n/a | The spec's d=128, L=2, 4 heads, ff 256, SentencePiece 8000 are the spec's own choices and no number may be attributed to the paper |
| Whether the two encoders share weights | Not in the paper. One symbol is used for the encoder stack applied to both inputs, which reads more like one shared stack than two | Section 4.1 | **The spec disagrees with the paper.** Line 285 says the encoders "do not share weights ... as in DragoNet" and line 230 says each field has "its own Transformer encoder". The paper states neither. `my inference` from the notation: if anything, shared. "as in DragoNet" should be removed; the default stays a spec choice to be tested |

Which field is the second input (`sourced`, Sections 1, 3 and 4.1): the business activity of the merchant, as a text description. For card data it is the text of the ISO 18245 merchant category code (296 descriptions); for account data the text of the Brazilian CNAE economic-activity code (695 activities). It is a registered attribute of the merchant from a fixed list, not free text about the purchase.
- The spec ("activity") agrees with the paper.
- Report 4 is loose rather than wrong: its heading says "description alone" and its table row "Description/activity only", but its line 32 describes the field correctly and warns that an invoice description is a noisier thing. Anyone reading only the heading would conclude the paper measured free-text descriptions. It did not.
- `my inference`, and it matters for both products: the paper gives no evidence about a free-text description field at all. Its 89 to 93% is for a controlled-vocabulary field. The spec's Field B concatenates our description with an activity text that is empty until the SBI research passes, so the paper's activity-only and fused figures do not transfer even as an upper bound we could aim at.

Two further statements in report 4 that the paper does not support as written:
- "10-fold cross-validation" (line 17): the paper says only "the same 10-fold split" (Section 5). `sourced`.
- "Even the simplest classical model benefited from having both fields ... should see most of this same gain" (line 30): true against name-only (TF-IDF + Random Forest, card: 38.59 to 80.95, Tables 3 and 5). But against activity-only the gain is small on card data (75.07 to 80.95) and negative on the account data (73.62 activity-only against 72.35 with both, Tables 4 and 5; another shallow model drops from 74.55 to 66.36). `sourced` for the numbers; `my inference`: the fusion gain is shown for the deep models, not for the TF-IDF baseline, which is what our spec builds first.

What may be quoted, if the skeptic passes this: the table rows above, each with "on two private Brazilian bank data sets of about 152,000 transactions each, labelled in-house, 10-fold split, one preprint, activity field taken from a code list". Never as an expectation for Vault Ledger.

Not checked: whether the paper was later published in a reviewed venue; whether code or data are public (I found no statement that they are).

## Recommendation, per the scout format

| Step | Try first | Runner-up | Ruled out |
|---|---|---|---|
| Inference runtime | onnxruntime with `ORT_DISABLE_TELEMETRY=1` set and tested, after the user rules on F1 | Export weights to plain numpy and run the small model without onnxruntime (removes F1 and F4; costs speed and work; not measured) | Shipping onnx or onnxscript |
| On-device fine-tuning | Head-only fine-tuning in numpy (`finetune_backend`), so torch is never shipped | Ship torch after F3 is cleared with the actual licence text and MKL status | Shipping torch as it stands, without knowing the Intel terms |
| Fallback model | Keep scikit-learn training-only; export the chosen baseline to arrays or ONNX | Move scikit-learn to runtime dependencies (licence fine) | none |
| Tests | hypothesis and pytest in `dev` only, with a check that the product environment lacks them | none | hypothesis in any runtime path |

Cheap experiments: (1) build an environment from the runtime dependencies alone and list every installed distribution and DLL with its licence; that is the real shipping list. (2) The telemetry check in F4. (3) For F3, read the licence strings of `torch_cpu.dll` and `torch.__config__` once in a throwaway environment to settle whether MKL is in it.

## Self-check

- Every one of the 14 package rows has a link to the licence file in the project's repository: yes.
- Every figure row has a location in the paper or "not in the paper": yes.
- First line is "Background read:": yes.
- Open and unverified items are named where they occur: Eigen actually compiled in (F1); MKL and the Intel licence in torch (F3); telemetry behaviour (F4); sentencepiece vendored licences; libyaml; Mac and Linux wheels; paper tables to be re-read in the PDF.

## Sources (all read 2026-10-13)

- Repository licence files: links in table 1.3.
- https://github.com/microsoft/onnxruntime/blob/main/ThirdPartyNotices.txt (first 100,000 characters read online; full file read in the local wheel)
- https://gitlab.com/libeigen/eigen/-/blob/master/COPYING.README
- https://www.mozilla.org/en-US/MPL/2.0/FAQ/ (the licensor's FAQ, not the licence)
- https://www.gnu.org/licenses/gcc-exception-3.1-faq.html
- https://pypi.org/project/intel-openmp/
- https://www.intel.com/content/www/us/en/developer/articles/license/end-user-license-agreement.html (first 100,000 characters read)
- https://docs.pytorch.org/docs/2.14/notes/windows.html
- https://github.com/pytorch/pytorch/blob/main/NOTICE
- https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution
- https://github.com/google/sentencepiece/tree/master/third_party
- https://arxiv.org/abs/2312.07730 and https://arxiv.org/html/2312.07730v1
- Local wheel metadata under `.claude/worktrees/ml-engine/vaultledger-ml/.venv/Lib/site-packages` (read only)
