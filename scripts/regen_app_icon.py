"""Regenerate resources/icons/lil_bro-01-classic.ico from the design export.

The raw export (docs/icons/windows taskbar icons/exports/) renders the lb_
glyph at ~67% of the tile width, which reads smaller than neighboring
taskbar icons. This script zooms the artwork by ZOOM and center-crops back
to 256px so the glyph fills more of the tile, while keeping the original
squircle silhouette (alpha channel) and the plate's edge highlight (outer
ring composited back from the original).

Dev-only asset tool — requires Pillow (`uv pip install pillow`), not a
runtime dependency. Run from the project root:

    python scripts/regen_app_icon.py [--zoom 1.25]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "icons" / "windows taskbar icons" / "exports" / "lil_bro-01-classic-256.png"
OUT_DIR = ROOT / "resources" / "icons"
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
RING_PX = 3  # width of the original edge ring kept over the zoomed art


def build_master(zoom: float) -> Image.Image:
    src = Image.open(SOURCE).convert("RGBA")
    size = src.width  # square

    # Zoom + center-crop the artwork.
    big_px = round(size * zoom)
    big = src.resize((big_px, big_px), Image.Resampling.LANCZOS)
    off = (big.width - size) // 2
    zoomed = big.crop((off, off, off + size, off + size))

    # Re-composite the original outer ring (edge highlight + AA corners):
    # ring mask = original alpha minus an eroded copy of it.
    alpha = src.getchannel("A")
    eroded = alpha.filter(ImageFilter.MinFilter(RING_PX * 2 + 1))
    ring = Image.composite(
        alpha, Image.new("L", alpha.size, 0),
        eroded.point(lambda p: 0 if int(p) > 128 else 255),
    )
    out = Image.composite(src, zoomed, ring)

    # Original silhouette: corners stay exactly as designed.
    out.putalpha(alpha)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zoom", type=float, default=1.25)
    args = parser.parse_args()

    master = build_master(args.zoom)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    master.save(OUT_DIR / "lil_bro-01-classic-256.png")
    master.save(OUT_DIR / "lil_bro-01-classic.ico", sizes=ICO_SIZES)
    print(f"zoom={args.zoom}: wrote lil_bro-01-classic-256.png + .ico ({len(ICO_SIZES)} frames) to {OUT_DIR}")


if __name__ == "__main__":
    main()
