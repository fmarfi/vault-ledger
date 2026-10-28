# Folder build of the desktop app WITH the DragoNet models.
#
#     .venv/Scripts/pip install -e ".[desktop]" -e vaultledger-ml pyinstaller
#     .venv/Scripts/python -m PyInstaller packaging/vault_ledger_full.spec --noconfirm
#
# Result: dist/VaultLedger/ (VaultLedger.exe plus its files, ~2 GB). A folder,
# not one file: PyTorch and the encoder are too large to unpack on every start.
# Needs everything vault_ledger.spec needs, plus vaultledger-ml/models/encoders
# (scripts/fetch_encoder.py) and the runs named in classifier/cascade.py.
#
# vault_ledger and vaultledger are analysed for their imports but shipped as
# plain files in the repo's layout (src/..., vaultledger-ml/...), so every
# path they derive from their own location resolves inside the bundle.

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

REPO = Path(SPECPATH).parent
SRC = REPO / "src"
ML = REPO / "vaultledger-ml"
SYNTH = REPO / "data" / "synthetic"
TESSERACT = Path(os.environ.get("TESSERACT_DIR", r"C:\Program Files\Tesseract-OCR"))

sys.path.insert(0, str(SRC))
from vault_ledger.classifier.cascade import DEFAULT_RUNS  # noqa: E402

ENCODER = ML / "models" / "encoders" / "multilingual-e5-small"
model = SYNTH / "fusion_classifier.json"
for needed, hint in (
    (model, "run the app once before building"),
    (TESSERACT / "tesseract.exe", "install Tesseract or set TESSERACT_DIR"),
    (ENCODER / "model.safetensors", "run vaultledger-ml/scripts/fetch_encoder.py"),
    *((ML / "runs" / run / "model.pt", "train or copy this run") for run in DEFAULT_RUNS),
):
    if not needed.exists():
        raise SystemExit(f"missing {needed}: {hint}")

datas = [
    (str(model), "data/synthetic"),
    (str(SYNTH / "labeled_transactions.csv"), "data/synthetic"),
    (str(SYNTH / "documents"), "data/synthetic/documents"),
]
for root in (SRC / "vault_ledger", ML / "vaultledger"):
    for path in root.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            datas.append((str(path), str(path.parent.relative_to(REPO))))
# The encoder (weights + tokenizer) and the shipped DragoNet runs.
for path in ENCODER.iterdir():
    if path.is_file() and path.name != "README.md":
        datas.append((str(path), str(ENCODER.relative_to(REPO))))
for run in DEFAULT_RUNS:
    for name in ("model.pt", "config.yaml"):
        datas.append((str(ML / "runs" / run / name), f"vaultledger-ml/runs/{run}"))

# Tesseract, as in vault_ledger.spec.
datas.append((str(TESSERACT / "tesseract.exe"), "tesseract"))
datas += [(str(dll), "tesseract") for dll in TESSERACT.glob("*.dll")]
for name in ("eng.traineddata", "osd.traineddata"):
    datas.append((str(TESSERACT / "tessdata" / name), "tesseract/tessdata"))
for folder in (TESSERACT / "tessdata", REPO / "data" / "tessdata"):
    if (folder / "nld.traineddata").exists():
        datas.append((str(folder / "nld.traineddata"), "tesseract/tessdata"))
        break
for folder in ("configs", "tessconfigs"):
    datas.append((str(TESSERACT / "tessdata" / folder), f"tesseract/tessdata/{folder}"))

binaries = []
hiddenimports = collect_submodules("vault_ledger") + collect_submodules("vaultledger")
for package in ("pypdfium2", "pypdfium2_raw", "tokenizers", "sentencepiece", "safetensors"):
    more_datas, more_binaries, more_hidden = collect_all(package)
    datas += more_datas
    binaries += more_binaries
    hiddenimports += more_hidden
# transformers imports model code lazily by name; the encoder is a BERT model
# with an XLM-RoBERTa tokenizer.
hiddenimports += collect_submodules("transformers.models.bert")
hiddenimports += collect_submodules("transformers.models.xlm_roberta")
hiddenimports += collect_submodules("transformers.models.auto")
hiddenimports += ["yaml"]
# transformers checks its dependencies' versions through package metadata.
for dist in ("transformers", "tokenizers", "safetensors", "huggingface_hub", "torch", "numpy",
             "tqdm", "regex", "requests", "packaging", "filelock", "pyyaml"):
    try:
        datas += copy_metadata(dist)
    except Exception:  # not installed: transformers doesn't need it here
        pass

a = Analysis(
    [str(REPO / "packaging" / "launcher.py")],
    pathex=[str(SRC), str(ML)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "fpdf", "tkinter", "matplotlib", "IPython", "hypothesis",
              "torchvision", "torchaudio", "tensorflow", "jax", "flax"],
)
a.pure = [entry for entry in a.pure if entry[0].split(".")[0] not in ("vault_ledger", "vaultledger")]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="VaultLedger",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="VaultLedger", upx=False)
