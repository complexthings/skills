"""Precompute the half-block Raster cells the bands draw when pictures are off.

The hooks module has no Node and no PNG decoder, so each PNG the terminal draws
gets a `<name>.<columns>x<rows>.cells` file beside it in orca-helpers/hooks/assets:
the RasterProps `cells`, base64 of little-endian u32 [codePoint, fg, bg] triplets.
Each cell is two pixels stacked, downsampled from the PNG: `▀` with the top pixel
as foreground and the bottom as background. A transparent pixel is the terminal's
default color, so a cell with only its bottom pixel draws `▄` and an empty one a space.

Run from the repo root: python3 orca-helpers/art/icons/cells.py
Self-test: python3 orca-helpers/art/icons/cells.py --test
"""

import base64
import collections
import pathlib
import re
import struct
import sys

from export import decode, encode

ASSETS = pathlib.Path(__file__).resolve().parents[2] / "hooks/assets"
DEFAULT = 0x01000000
UPPER, LOWER, SPACE = 0x2580, 0x2584, 0x20

# Each PNG name the bands draw, and the Image's columns and rows it is drawn at.
SIZES = [
    (r"(check|wave|upcoming|flag)_\d+", [(2, 1)]),
    (r"orca_\d+", [(2, 1), (4, 2)]),
    (r"avatars/\w+_24_\d+", [(4, 2)]),
    (r"avatars/[a-z]+_(default|selected|main|disabled|writing|waiting)_\d+", [(9, 5)]),
]


def pixel(rows, x0, x1, y0, y1):
    """The block's most common opaque color as 0xRRGGBB, or DEFAULT under 30% opaque.

    Below half, not most: the 4x2 orca and the small icons are mostly transparent at their edges."""
    block = [rows[y][x] for y in range(y0, y1) for x in range(x0, x1)]
    opaque = [(r << 16) | (g << 8) | b for r, g, b, a in block if a >= 128]
    return collections.Counter(opaque).most_common(1)[0][0] if 10 * len(opaque) >= 3 * len(block) else DEFAULT


def cells(rows, columns, height):
    w, h = len(rows[0]), len(rows)
    px = [[pixel(rows, x * w // columns, (x + 1) * w // columns, y * h // (2 * height), (y + 1) * h // (2 * height)) for x in range(columns)] for y in range(2 * height)]
    words = []
    for y in range(height):
        for top, bottom in zip(px[2 * y], px[2 * y + 1]):
            if top != DEFAULT:
                words += [UPPER, top, bottom]
            elif bottom != DEFAULT:
                words += [LOWER, bottom, DEFAULT]
            else:
                words += [SPACE, DEFAULT, DEFAULT]
    return base64.b64encode(struct.pack(f"<{len(words)}I", *words)).decode()


def main():
    written = 0
    for png in sorted(ASSETS.rglob("*.png")):
        name = png.relative_to(ASSETS).with_suffix("").as_posix()
        sizes = [s for pattern, sizes in SIZES if re.fullmatch(pattern, name) for s in sizes]
        if not sizes:
            continue
        rows = decode(png)
        for c, r in sizes:
            png.with_name(f"{png.stem}.{c}x{r}.cells").write_text(cells(rows, c, r))
            written += 1
    print(f"{written} cells files")


def test():
    R, B, T = (255, 0, 0, 255), (0, 0, 255, 255), (0, 0, 0, 0)
    # A 4x4 RGBA PNG through export's encoder and decoder: red over blue, then transparent over blue, then nothing.
    rows = [[R, R, T, T], [R, R, T, T], [B, B, B, B], [B, B, B, B]]
    tmp = pathlib.Path(__file__).with_name("_cells_test.png")
    try:
        tmp.write_bytes(encode(rows))
        assert decode(tmp) == rows
    finally:
        tmp.unlink(missing_ok=True)
    got = struct.unpack("<6I", base64.b64decode(cells(rows, 2, 1)))
    assert got == (UPPER, 0xFF0000, 0x0000FF, LOWER, 0x0000FF, DEFAULT), got
    empty = struct.unpack("<3I", base64.b64decode(cells([[T, T], [T, T]], 1, 1)))
    assert empty == (SPACE, DEFAULT, DEFAULT), empty
    # Every shipped PNG has its cells at each drawn size, one triplet per cell.
    for png in ASSETS.glob("orca_*.png"):
        assert len(base64.b64decode(png.with_name(f"{png.stem}.4x2.cells").read_text())) == 4 * 2 * 12, png
    print("ok")


if __name__ == "__main__":
    test() if sys.argv[1:] == ["--test"] else main()
