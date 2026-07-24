"""The ffmpeg concat-demuxer list file.

ffmpeg's concat demuxer reads a text file of `file '...'` lines. Its quoting
rules are particular — paths are single-quoted, and a literal single quote is
escaped as the four characters '\\'' — so building the file is isolated here
and tested rather than formatted inline.

Windows paths use backslashes, which ffmpeg accepts inside the quotes; only the
single quote needs escaping.
"""

from __future__ import annotations

from pathlib import Path


def escape_path(path: Path | str) -> str:
    """Escape one path for a concat list entry (without the surrounding quotes)."""
    text = str(path)
    # Close the quote, emit an escaped quote, reopen — ffmpeg's documented form.
    return text.replace("'", "'\\''")


def build_concat_list(clip_paths: list[Path]) -> str:
    """Build the full text of a concat list file from clip paths in order."""
    if not clip_paths:
        raise ValueError("Cannot build a concat list from zero clips")
    lines = [f"file '{escape_path(path)}'" for path in clip_paths]
    return "\n".join(lines) + "\n"


def write_concat_list(clip_paths: list[Path], destination: Path) -> Path:
    """Write the concat list file and return its path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_concat_list(clip_paths), encoding="utf-8")
    return destination
