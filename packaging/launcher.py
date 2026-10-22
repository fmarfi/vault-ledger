r"""Entry point of the single-file Windows build (see vault_ledger.spec).

The package is shipped as plain files under `<bundle>/src/vault_ledger` with
`<bundle>/data/synthetic` beside it, the same layout as the repo, so every
path the modules derive from their own location (samples, trained model,
templates) resolves inside the bundle without the product code knowing it is
frozen. The bundle is unpacked to a temp folder on every start and removed on
exit, so anything the user owns is pointed elsewhere:

- accounts and books: %LOCALAPPDATA%\VaultLedger (VAULT_DATA_DIR)
- Tesseract: the copy inside the bundle (TESSERACT_CMD)

Both can still be set by hand before starting the exe.
"""

import os
import sys
from pathlib import Path


def main() -> None:
    bundle = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    if getattr(sys, "frozen", False):
        sys.path.insert(0, str(bundle / "src"))
        local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        os.environ.setdefault("VAULT_DATA_DIR", str(local / "VaultLedger"))
        tesseract = bundle / "tesseract" / "tesseract.exe"
        if tesseract.exists():
            os.environ.setdefault("TESSERACT_CMD", str(tesseract))

    from vault_ledger.desktop import main as run

    run()


if __name__ == "__main__":
    main()
