"""Generate brand icons for the integration using only the standard library.

Produces PNGs under custom_components/azure_foundry_conversation/brand/:
  icon.png (256), icon@2x.png (512), logo.png (256), logo@2x.png (512)

Design: an Azure-blue rounded square with a white speech bubble and three dots.
Run: python scripts/gen_brand.py
"""

from __future__ import annotations

import pathlib
import struct
import zlib

BLUE = (0, 120, 212)
WHITE = (255, 255, 255)

BRAND_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "azure_foundry_conversation"
    / "brand"
)


def _inside_rounded(
    nx: float, ny: float, x0: float, y0: float, x1: float, y1: float, r: float
) -> bool:
    if not (x0 <= nx <= x1 and y0 <= ny <= y1):
        return False
    if (x0 + r) <= nx <= (x1 - r) or (y0 + r) <= ny <= (y1 - r):
        return True
    ccx = x0 + r if nx < x0 + r else x1 - r
    ccy = y0 + r if ny < y0 + r else y1 - r
    return (nx - ccx) ** 2 + (ny - ccy) ** 2 <= r * r


def _in_triangle(
    px: float,
    py: float,
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> bool:
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1 = sign((px, py), a, b)
    d2 = sign((px, py), b, c)
    d3 = sign((px, py), c, a)
    has_neg = d1 < 0 or d2 < 0 or d3 < 0
    has_pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (has_neg and has_pos)


def _color_at(nx: float, ny: float) -> tuple[int, int, int, int]:
    if not _inside_rounded(nx, ny, 0.0, 0.0, 1.0, 1.0, 0.18):
        return (0, 0, 0, 0)

    in_bubble = _inside_rounded(nx, ny, 0.20, 0.24, 0.80, 0.60, 0.10) or _in_triangle(
        nx, ny, (0.30, 0.58), (0.46, 0.58), (0.30, 0.75)
    )
    if in_bubble:
        for dot_x in (0.34, 0.50, 0.66):
            if (nx - dot_x) ** 2 + (ny - 0.42) ** 2 <= 0.044**2:
                return (*BLUE, 255)
        return (*WHITE, 255)

    return (*BLUE, 255)


def _render(size: int, ss: int = 4) -> bytes:
    data = bytearray(size * size * 4)
    inv = 1.0 / ss
    n = ss * ss
    for py in range(size):
        for px in range(size):
            r = g = b = a = 0.0
            for sy in range(ss):
                for sx in range(ss):
                    nx = (px + (sx + 0.5) * inv) / size
                    ny = (py + (sy + 0.5) * inv) / size
                    cr, cg, cb, ca = _color_at(nx, ny)
                    r += cr * ca
                    g += cg * ca
                    b += cb * ca
                    a += ca
            idx = (py * size + px) * 4
            if a > 0:
                data[idx] = int(r / a)
                data[idx + 1] = int(g / a)
                data[idx + 2] = int(b / a)
            data[idx + 3] = int(a / n)
    return bytes(data)


def _write_png(path: pathlib.Path, size: int, rgba: bytes) -> None:
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    raw = bytearray()
    stride = size * 4
    for y in range(size):
        raw.append(0)
        raw.extend(rgba[y * stride : (y + 1) * stride])

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def main() -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    for name, size in (
        ("icon.png", 256),
        ("icon@2x.png", 512),
        ("logo.png", 256),
        ("logo@2x.png", 512),
    ):
        _write_png(BRAND_DIR / name, size, _render(size))
        print(f"wrote {name} ({size}x{size})")


if __name__ == "__main__":
    main()
