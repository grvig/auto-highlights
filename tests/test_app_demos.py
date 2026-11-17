"""Tests for finding demos."""

import os

from highlights.app.demos import default_folders, find_demos


def make_demo(folder, name, size, mtime):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b"x" * size)
    os.utime(path, (mtime, mtime))
    return path


def test_demos_are_listed_newest_first_with_duplicates_dropped(tmp_path):
    replays, downloads = tmp_path / "replays", tmp_path / "Downloads"
    make_demo(replays, "old.dem", 10, 1_000_000)
    make_demo(replays, "new.dem", 20, 2_000_000)
    make_demo(downloads, "new.dem", 20, 2_000_000)  # the same file, copied
    make_demo(downloads, "faceit.dem", 30, 1_500_000)
    (downloads / "notes.txt").write_text("not a demo")
    demos = find_demos([replays, downloads])
    assert [d["name"] for d in demos] == ["new.dem", "faceit.dem", "old.dem"]
    assert set(demos[0]) == {"path", "name", "folder", "megabytes", "modified"}


def test_missing_folders_are_skipped(tmp_path):
    assert find_demos([tmp_path / "nope"]) == []


def test_default_folders_cover_cs2_replays_and_downloads(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    folders = default_folders(tmp_path / "cs2")
    assert folders[0].as_posix().endswith("cs2/game/csgo/replays")
    assert folders[1] == tmp_path / "Downloads"
    assert default_folders(None) == [tmp_path / "Downloads"]
