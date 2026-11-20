"""Tests for unpacking compressed (FACEIT) demos."""

import gzip
import os

import pytest
import zstandard

from highlights.engine.demo_source import DemoError
from highlights.engine.unpack import (
    CS2_MAGIC,
    UnpackError,
    is_compressed,
    readable_demo,
    unpack_demo,
    unpacked_name,
)

DEMO = CS2_MAGIC + b"rest of a demo" * 1000


def test_compressed_demos_are_recognised_by_name():
    assert is_compressed("a/match.dem.zst") and is_compressed("MATCH.DEM.GZ")
    assert not is_compressed("match.dem") and not is_compressed("notes.zst")
    assert unpacked_name("D:/faceit/1-abc.dem.zst") == "1-abc.dem"


@pytest.mark.parametrize("suffix, pack", [
    (".dem.zst", lambda data: zstandard.ZstdCompressor().compress(data)),
    (".dem.gz", gzip.compress),
])
def test_both_formats_unpack_into_the_given_folder(tmp_path, suffix, pack):
    archive = tmp_path / f"faceit{suffix}"
    archive.write_bytes(pack(DEMO))
    demo = unpack_demo(archive, tmp_path / "cache" / "demos")
    assert demo == tmp_path / "cache" / "demos" / "faceit.dem"
    assert demo.read_bytes() == DEMO
    assert not list((tmp_path / "cache" / "demos").glob("*.part"))


def test_an_unpacked_demo_is_reused(tmp_path):
    archive = tmp_path / "faceit.dem.gz"
    archive.write_bytes(gzip.compress(DEMO))
    first = unpack_demo(archive, tmp_path / "out")
    first.write_bytes(b"marker")  # would be overwritten by a second unpack
    os.utime(first, (archive.stat().st_atime, archive.stat().st_mtime + 60))
    assert unpack_demo(archive, tmp_path / "out").read_bytes() == b"marker"


def test_a_broken_archive_is_a_demo_error_and_leaves_nothing(tmp_path):
    archive = tmp_path / "cut.dem.zst"
    archive.write_bytes(zstandard.ZstdCompressor().compress(DEMO)[:20])
    with pytest.raises(DemoError, match="Could not unpack cut.dem.zst"):
        unpack_demo(archive, tmp_path / "out")
    assert not list((tmp_path / "out").glob("*"))


def test_an_archive_without_a_cs2_demo_is_refused(tmp_path):
    archive = tmp_path / "page.dem.gz"
    archive.write_bytes(gzip.compress(b"<html>not found</html>"))
    with pytest.raises(UnpackError, match="does not contain a CS2 demo"):
        unpack_demo(archive, tmp_path / "out")


def test_plain_demos_pass_through_and_packed_ones_default_beside_the_archive(tmp_path):
    plain = tmp_path / "m.dem"
    assert readable_demo(plain, tmp_path / "cache") == plain
    archive = tmp_path / "f.dem.gz"
    archive.write_bytes(gzip.compress(DEMO))
    assert readable_demo(archive, None) == tmp_path / "f.dem"
