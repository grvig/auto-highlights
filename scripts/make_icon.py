"""Draw the app's icon: an amber tile with a play mark inside crosshair ticks.

    python scripts/make_icon.py

Writes packaging/icon.ico (every size Windows asks for) and
packaging/icon.png (256 px). The same mark is drawn as SVG in ui/src/Logo.tsx;
change both together.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
AMBER = (227, 168, 18, 255)
INK = (20, 16, 5, 255)
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
# The design grid: a 64-unit square, the same numbers as the SVG.
GRID = 64


def draw(size: int) -> Image.Image:
    scale = 8  # draw large, shrink once: clean edges at every size
    big = size * scale
    unit = big / GRID
    image = Image.new("RGBA", (big, big), AMBER)
    pen = ImageDraw.Draw(image)

    def box(x0, y0, x1, y1):
        pen.rectangle([x0 * unit, y0 * unit, x1 * unit - 1, y1 * unit - 1], fill=INK)

    # crosshair ticks, with a gap where the play mark sits
    box(30, 6, 34, 16)
    box(30, 48, 34, 58)
    box(6, 30, 16, 34)
    box(48, 30, 58, 34)
    # play mark
    pen.polygon([(25 * unit, 21 * unit), (25 * unit, 43 * unit), (43 * unit, 32 * unit)], fill=INK)
    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    out = ROOT / "packaging"
    largest = draw(256)
    largest.save(out / "icon.png")
    largest.save(out / "icon.ico", sizes=[(s, s) for s in SIZES],
                 append_images=[draw(s) for s in SIZES[:-1]])
    print(f"Wrote {out / 'icon.ico'} and {out / 'icon.png'}")


if __name__ == "__main__":
    main()
