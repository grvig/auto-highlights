"""Compressed demos: FACEIT serves CS2 demos as .dem.zst (older downloads and
some sites use .dem.gz). Neither the parser nor CS2 can read them packed, so
they are unpacked once into a folder of the app's own and reused after that.
"""

from __future__ import annotations

import gzip
import logging
import shutil
from pathlib import Path
from typing import BinaryIO

from highlights.engine.demo_source import DemoError

logger = logging.getLogger(__name__)

COMPRESSED = (".dem.zst", ".dem.gz")
# Every CS2 demo starts with this.
CS2_MAGIC = b"PBDEMS2\x00"


class UnpackError(DemoError):
    """Raised for an archive that cannot be unpacked into a CS2 demo."""


def is_compressed(path: Path | str) -> bool:
    return str(path).lower().endswith(COMPRESSED)


def unpacked_name(path: Path | str) -> str:
    """match.dem.zst -> match.dem"""
    name = Path(path).name
    return name[: name.lower().rindex(".dem") + len(".dem")]


def _copy_zstd(raw: BinaryIO, out: BinaryIO) -> None:
    import zstandard  # noqa: PLC0415 - only needed for FACEIT demos

    unpacker = zstandard.ZstdDecompressor().decompressobj()
    while chunk := raw.read(1 << 20):
        out.write(unpacker.decompress(chunk))
    if not unpacker.eof:  # a download that stopped partway
        raise UnpackError("the archive is cut short (an unfinished download?)")


def _copy_gzip(raw: BinaryIO, out: BinaryIO) -> None:
    with gzip.GzipFile(fileobj=raw) as packed:  # raises EOFError when cut short
        shutil.copyfileobj(packed, out, 1 << 20)


def unpack_demo(path: Path | str, folder: Path | str) -> Path:
    """The demo inside `path`, unpacked into `folder` (once; reused after)."""
    path, folder = Path(path), Path(folder)
    target = folder / unpacked_name(path)
    try:
        if target.is_file() and target.stat().st_mtime >= path.stat().st_mtime and target.stat().st_size:
            return target
    except OSError:
        pass
    folder.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    logger.info("Unpacking %s", path.name)
    try:
        copy = _copy_zstd if path.name.lower().endswith(".zst") else _copy_gzip
        with path.open("rb") as raw, partial.open("wb") as out:
            copy(raw, out)
        with partial.open("rb") as check:
            if check.read(len(CS2_MAGIC)) != CS2_MAGIC:
                raise UnpackError(f"{path.name} does not contain a CS2 demo")
        partial.replace(target)
    except UnpackError as error:
        partial.unlink(missing_ok=True)
        if str(error).startswith(path.name):
            raise
        raise UnpackError(f"Could not unpack {path.name}: {error}") from None
    except Exception as error:  # zstd, gzip and file errors all mean the same here
        partial.unlink(missing_ok=True)
        raise UnpackError(f"Could not unpack {path.name}: {error}") from error
    return target


def readable_demo(path: Path | str, folder: Path | str | None) -> Path:
    """A path the parser and CS2 can use: unpacked when it is compressed.

    Without a folder the demo is unpacked beside the archive.
    """
    path = Path(path)
    if not is_compressed(path):
        return path
    return unpack_demo(path, folder if folder is not None else path.parent)
