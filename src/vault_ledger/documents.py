"""Uploaded documents kept for the review queue.

An upload is stored next to the rest of the user's data, named after its queue
item id, so the reviewer can look at the document while confirming or
correcting the proposed entry. Kept after confirm (it is the record behind the
ledger entry), deleted on dismiss.

Shown in the page only as `preview_png`, a re-render of the first page (the
only page the pipeline reads) to a PNG. The original file is offered only as
a download (Content-Disposition: attachment, application/octet-stream), so
uploaded bytes are never rendered in the app's own origin.

Not part of `backup.py` yet: a backup holds the books, not the originals.
"""

from __future__ import annotations

import io
import re
import shutil
from pathlib import Path

from vault_ledger.userdata import resolve

DOCUMENTS_DIR = Path(__file__).resolve().parents[2] / "data" / "documents"
ITEM_ID_RE = re.compile(r"[0-9a-f]{12}")
SUFFIX_RE = re.compile(r"\.[A-Za-z0-9]{1,8}")
PREVIEW_SCALE = 150 / 72  # PDF points -> pixels at 150 dpi
PREVIEW_MAX_SIDE = 2000


def _dir() -> Path:
    return resolve("documents", DOCUMENTS_DIR)


def find(item_id: str) -> Path | None:
    if not isinstance(item_id, str) or not ITEM_ID_RE.fullmatch(item_id):
        return None
    folder = _dir()
    if not folder.is_dir():
        return None
    return next((p for p in sorted(folder.iterdir()) if p.stem == item_id and p.is_file()), None)


def stored_ids() -> set[str]:
    """Item ids that have a stored document (one directory listing)."""
    folder = _dir()
    if not folder.is_dir():
        return set()
    return {p.stem for p in folder.iterdir() if p.is_file() and ITEM_ID_RE.fullmatch(p.stem)}


def store(item_id: str, source: str | Path, suffix: str) -> Path:
    """Move a processed upload into the documents folder under its item id."""
    if not ITEM_ID_RE.fullmatch(item_id):
        raise ValueError("invalid queue item id")
    if not SUFFIX_RE.fullmatch(suffix):
        suffix = ".bin"
    folder = _dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{item_id}{suffix.lower()}"
    shutil.move(str(source), target)
    return target


def remove(item_id: str) -> bool:
    path = find(item_id)
    if path is None:
        return False
    path.unlink(missing_ok=True)
    return True


def preview_png(item_id: str) -> bytes | None:
    """First page of the stored document as PNG bytes, or None if there is no
    stored document or it cannot be rendered."""
    path = find(item_id)
    if path is None:
        return None
    try:
        if path.suffix == ".pdf":
            import pypdfium2

            pdf = pypdfium2.PdfDocument(str(path))
            try:
                image = pdf[0].render(scale=PREVIEW_SCALE).to_pil()
            finally:
                pdf.close()
        else:
            from PIL import Image, ImageOps

            with Image.open(path) as opened:
                image = ImageOps.exif_transpose(opened)
                image.load()
        image = image.convert("RGB")
        image.thumbnail((PREVIEW_MAX_SIDE, PREVIEW_MAX_SIDE))
        out = io.BytesIO()
        image.save(out, "PNG")
        return out.getvalue()
    except Exception:  # noqa: BLE001 -- unreadable file: the page shows its placeholder
        return None
