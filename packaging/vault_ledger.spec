# Single-file Windows build of the desktop app.
#
#     .venv/Scripts/pip install -e ".[desktop]" pyinstaller
#     .venv/Scripts/python -m PyInstaller packaging/vault_ledger.spec --noconfirm
#
# Result: dist/VaultLedger.exe. Needs on the build machine: Tesseract (UB
# Mannheim installer, or TESSERACT_DIR), and a trained model at
# data/synthetic/fusion_classifier.json (run the app or the pipeline once).
#
# vault_ledger itself is analysed for its imports but shipped as plain files,
# not inside the archive; launcher.py explains why.

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

REPO = Path(SPECPATH).parent
SRC = REPO / "src"
SYNTH = REPO / "data" / "synthetic"
TESSERACT = Path(os.environ.get("TESSERACT_DIR", r"C:\Program Files\Tesseract-OCR"))

model = SYNTH / "fusion_classifier.json"
if not model.exists():
    raise SystemExit(f"no trained model at {model}; run the app once before building")
if not (TESSERACT / "tesseract.exe").exists():
    raise SystemExit(f"no tesseract.exe in {TESSERACT}; install it or set TESSERACT_DIR")

datas = [
    (str(model), "data/synthetic"),
    # kept so the model can be retrained in place if the json is ever unreadable
    (str(SYNTH / "labeled_transactions.csv"), "data/synthetic"),
    (str(SYNTH / "documents"), "data/synthetic/documents"),
]
for path in (SRC / "vault_ledger").rglob("*"):
    if path.is_file() and "__pycache__" not in path.parts:
        datas.append((str(path), str(path.parent.relative_to(REPO))))

# Tesseract: the program, its DLLs, English and orientation data only.
datas.append((str(TESSERACT / "tesseract.exe"), "tesseract"))
datas += [(str(dll), "tesseract") for dll in TESSERACT.glob("*.dll")]
for name in ("eng.traineddata", "osd.traineddata"):
    datas.append((str(TESSERACT / "tessdata" / name), "tesseract/tessdata"))
for folder in ("configs", "tessconfigs"):
    datas.append((str(TESSERACT / "tessdata" / folder), f"tesseract/tessdata/{folder}"))

binaries = []
hiddenimports = collect_submodules("vault_ledger")
for package in ("pypdfium2", "pypdfium2_raw"):
    more_datas, more_binaries, more_hidden = collect_all(package)
    datas += more_datas
    binaries += more_binaries
    hiddenimports += more_hidden

a = Analysis(
    [str(REPO / "packaging" / "launcher.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "fpdf", "tkinter", "matplotlib", "IPython"],
)
a.pure = [entry for entry in a.pure if entry[0].split(".")[0] != "vault_ledger"]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="VaultLedger",
    console=False,
    upx=False,
)
