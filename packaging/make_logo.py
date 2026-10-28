"""Draw the Vault Ledger symbol as vector geometry and write every logo file.

    .venv/Scripts/python packaging/make_logo.py

The shapes are traced from the brand guidelines board (symbol and app icon)
and cleaned up: exact symmetry, 45-degree cuts, the brand colours. One source
of geometry feeds the SVGs the app shows and the raster sizes of the Windows
icon, so the logo is sharp at any size.

Writes:
  src/vault_ledger/webapp/static/logo.svg       symbol, for light backgrounds
  src/vault_ledger/webapp/static/logo-reversed.svg  symbol, for dark backgrounds (app header)
  src/vault_ledger/webapp/static/app-icon.svg   app icon tile (also the favicon)
  packaging/vault_ledger.ico                    Windows icon, 16-256 px
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "src" / "vault_ledger" / "webapp" / "static"

FOREST = "#1C2B24"
PAGE_CREAM = "#EEF0E4"
CARD_CREAM = "#F7F8F2"
SAGE = "#B9C2AC"
BRASS = "#8C7A4E"

# Symbol geometry, centred on x = 0. Units are board pixels.
CHEVRON = [(-99, 0), (0, 99), (99, 0), (99, 34), (0, 133), (-99, 34)]  # y from its top edge
CHEVRON_TOP = 103  # y of the chevron's top edge below the diamond's top
H = 12.35  # half width of the centre bar
DIAMOND = [(0, 0), (14, 14), (0, 28), (-14, 14)]
CENTRE_BAR = [(-H, 34.2), (0, 45.4), (H, 34.2), (H, 166.7), (0, 179.2), (-H, 166.7)]
# Side bar (left one; the right one is its mirror image): a folded top and a
# 45-degree foot parallel to the chevron.
OUTER, INNER = -60.7, -34.8
SIDE_BAR = [(OUTER, 48.2), (OUTER + 7.8, 52.6), (INNER, 34.9), (INNER, 148.0), (OUTER, 122.1)]


def _mirror(points):
    return [(-x, y) for x, y in reversed(points)]


def shapes(chevron=FOREST, sides=SAGE, centre=BRASS, diamond=BRASS):
    """(colour, polygon) pairs of the symbol, y from the diamond's top."""
    chev = [(x, y + CHEVRON_TOP) for x, y in CHEVRON]
    return [
        (chevron, chev),
        (sides, SIDE_BAR),
        (sides, _mirror(SIDE_BAR)),
        (centre, CENTRE_BAR),
        (diamond, DIAMOND),
    ]


WIDTH, HEIGHT = 198.0, CHEVRON_TOP + 133.0  # symbol bounding box


def _svg_polygons(items, dx, dy, scale=1.0):
    out = []
    for colour, points in items:
        coords = " ".join(f"{(x + dx) * scale:.2f},{(y + dy) * scale:.2f}" for x, y in points)
        out.append(f'  <polygon fill="{colour}" points="{coords}"/>')
    return "\n".join(out)


def symbol_svg(items=None) -> str:
    pad = 4
    w, h = WIDTH + 2 * pad, HEIGHT + 2 * pad
    body = _svg_polygons(items or shapes(), WIDTH / 2 + pad, pad)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.2f} {h:.2f}" '
        f'role="img" aria-label="Vault Ledger">\n{body}\n</svg>\n'
    )


# App icon: the reversed symbol on a forest tile with rounded corners.
TILE = 512
TILE_RADIUS = 112
ICON_SCALE = 1.62  # symbol size inside the tile


def _icon_items():
    return shapes(chevron=PAGE_CREAM, sides=SAGE, centre=CARD_CREAM, diamond=CARD_CREAM)


def _icon_offsets():
    dx = TILE / 2 / ICON_SCALE
    dy = (TILE / ICON_SCALE - HEIGHT) / 2
    return dx, dy


def app_icon_svg() -> str:
    dx, dy = _icon_offsets()
    body = _svg_polygons(_icon_items(), dx, dy, ICON_SCALE)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TILE} {TILE}" role="img" aria-label="Vault Ledger">\n'
        f'  <rect width="{TILE}" height="{TILE}" rx="{TILE_RADIUS}" fill="{FOREST}"/>\n{body}\n</svg>\n'
    )


def app_icon_png(size: int) -> Image.Image:
    """The app icon at `size` px, drawn 8x larger and scaled down (anti-aliased)."""
    big = size * 8
    k = big / TILE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=TILE_RADIUS * k, fill=FOREST)
    dx, dy = _icon_offsets()
    for colour, points in _icon_items():
        draw.polygon([((x + dx) * ICON_SCALE * k, (y + dy) * ICON_SCALE * k) for x, y in points], fill=colour)
    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    (STATIC / "logo.svg").write_text(symbol_svg(), encoding="utf-8")
    (STATIC / "logo-reversed.svg").write_text(symbol_svg(_icon_items()), encoding="utf-8")
    (STATIC / "app-icon.svg").write_text(app_icon_svg(), encoding="utf-8")
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    largest = app_icon_png(256)
    largest.save(REPO / "packaging" / "vault_ledger.ico", sizes=[(s, s) for s in sizes],
                 append_images=[app_icon_png(s) for s in sizes[:-1]])
    print("wrote logo.svg, logo-reversed.svg, app-icon.svg, vault_ledger.ico")


if __name__ == "__main__":
    main()
