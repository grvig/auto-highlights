"""Tests for Steam and CS2 auto-detection, using fake installs on disk."""

from pathlib import Path

from highlights.steam.locate import (
    CS2_EXE_RELATIVE,
    CS2_FOLDER,
    find_cs2_root,
    find_steam_root,
    library_folders,
)


def write_manifest(steam: Path, libraries: dict[str, tuple[Path, list[str]]]) -> None:
    blocks = []
    for key, (path, apps) in libraries.items():
        app_lines = "".join(f'"{app}" "1"\n' for app in apps)
        escaped = str(path).replace("\\", "\\\\")
        blocks.append(f'"{key}" {{ "path" "{escaped}" "apps" {{ {app_lines} }} }}')
    manifest = steam / "steamapps" / "libraryfolders.vdf"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('"libraryfolders" {' + "\n".join(blocks) + "}", encoding="utf-8")


def install_cs2(library: Path) -> Path:
    exe = library / CS2_FOLDER / CS2_EXE_RELATIVE
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    return library / CS2_FOLDER


def test_steam_root_comes_from_the_registry(tmp_path):
    reader = lambda hive, key, value: str(tmp_path) if hive == "HKCU" else None
    assert find_steam_root(reader) == tmp_path


def test_missing_registry_and_defaults_gives_none(tmp_path, monkeypatch):
    monkeypatch.setattr("highlights.steam.locate.DEFAULT_STEAM_ROOTS", (tmp_path / "nope",))
    assert find_steam_root(lambda *a: None) is None


def test_library_folders_reads_paths_and_apps(tmp_path):
    steam, games = tmp_path / "steam", tmp_path / "games"
    write_manifest(steam, {"0": (steam, ["228980"]), "1": (games, ["730"])})
    libraries = dict(library_folders(steam))
    assert libraries[games] == {"730"}


def test_cs2_found_in_the_library_that_holds_it(tmp_path):
    steam, games = tmp_path / "steam", tmp_path / "games"
    write_manifest(steam, {"0": (steam, []), "1": (games, ["730"])})
    expected = install_cs2(games)
    assert find_cs2_root(steam) == expected


def test_empty_stub_folder_is_skipped(tmp_path):
    # Steam lists CS2 on the system library but only an empty stub is there.
    steam, games = tmp_path / "steam", tmp_path / "games"
    (steam / CS2_FOLDER).mkdir(parents=True)  # stub with no cs2.exe
    write_manifest(steam, {"0": (steam, ["730"]), "1": (games, [])})
    expected = install_cs2(games)
    assert find_cs2_root(steam) == expected


def test_no_cs2_anywhere_gives_none(tmp_path):
    steam = tmp_path / "steam"
    write_manifest(steam, {"0": (steam, [])})
    assert find_cs2_root(steam) is None
