"""Picking a font that can draw a given piece of text.

Player names are often Chinese, Korean or Cyrillic, which a Latin display
font draws as empty boxes. Text that needs more than Latin gets a font with
wide coverage instead. Fonts bundled with the app win over system ones.
"""

from __future__ import annotations

from pathlib import Path

BUNDLED_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
SYSTEM_DIR = Path("C:/Windows/Fonts")

# In order of preference.
DISPLAY_FONTS = ("display.ttf", "segoeuib.ttf", "bahnschrift.ttf", "arialbd.ttf")
WIDE_FONTS = ("wide.ttc", "msyhbd.ttc", "msyh.ttc", "malgunbd.ttf", "YuGothB.ttc")


class FontError(Exception):
    """Raised when no usable font is installed."""


def needs_wide_font(text: str) -> bool:
    """Whether text has characters outside Latin, Greek and punctuation."""
    return any(ord(ch) > 0x24F and not 0x2000 <= ord(ch) <= 0x206F for ch in text)


def find_font(text: str = "", search: tuple[Path, ...] | None = None) -> Path:
    """The best installed font for drawing `text`."""
    folders = search or (BUNDLED_DIR, SYSTEM_DIR)
    names = WIDE_FONTS if needs_wide_font(text) else DISPLAY_FONTS + WIDE_FONTS
    for name in names:
        for folder in folders:
            candidate = Path(folder) / name
            if candidate.is_file():
                return candidate
    raise FontError("No usable font found for captions; install Bahnschrift or Arial")


def filter_path(path: Path) -> str:
    """A path as ffmpeg's filter syntax needs it: forward slashes, colon escaped."""
    return Path(path).as_posix().replace(":", "\\:")
