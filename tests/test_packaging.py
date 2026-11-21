"""Tests for the build script's arguments (no build is run)."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", ROOT / "packaging" / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_the_exe_bundles_the_parsers_but_not_unused_extras(tmp_path):
    args = build.pyinstaller_args(tmp_path)
    assert args[args.index("--name") + 1] == "auto-highlights"
    assert "--onedir" in args and "demoparser2" in args
    excluded = [args[i + 1] for i, a in enumerate(args) if a == "--exclude-module"]
    assert {"matplotlib", "scipy"} <= set(excluded)
    assert args[args.index("--distpath") + 1] == str(tmp_path / "dist")


def test_the_installer_is_given_the_version_and_folders(tmp_path):
    args = build.installer_args(Path("ISCC.exe"), tmp_path / "dist", tmp_path / "inst", "0.1.0")
    assert "/DAppVersion=0.1.0" in args and f"/DSourceDir={tmp_path / 'dist'}" in args
    assert args[-1].endswith("installer.iss")


def test_entry_and_installer_script_exist():
    assert (ROOT / "packaging" / "entry.py").is_file()
    text = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in text
    # the shortcuts open the window: the exe itself, no prompt and no arguments
    shortcut = next(line for line in text.splitlines() if line.startswith('Name: "{group}\\auto-highlights"'))
    assert 'Filename: "{app}\\auto-highlights.exe"' in shortcut and "Parameters" not in shortcut


def test_builds_go_beside_the_parse_cache_by_default(monkeypatch, tmp_path):
    from highlights.config import ClipConfig, Config

    config = Config(cs2_root=None, output_dir=tmp_path / "out", clips_dir=tmp_path / "media" / "clips",
                    clips=ClipConfig())
    monkeypatch.setattr("highlights.config.load_config", lambda: config)
    assert build.default_out() == tmp_path / "media" / "build"


def test_the_packaged_exe_opens_the_window_without_arguments():
    import importlib.util

    spec = importlib.util.spec_from_file_location("entry", ROOT / "packaging" / "entry.py")
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    assert entry.arguments([]) == ["--app"]
    assert entry.arguments(["--check"]) == ["--check"]


def test_the_built_interface_is_bundled(tmp_path):
    args = build.pyinstaller_args(tmp_path)
    data = [args[i + 1] for i, arg in enumerate(args) if arg == "--add-data"]
    assert any(d.endswith("highlights/app/web") and "web" in d.split(build.SEP)[0] for d in data)


def test_the_interface_installs_its_dependencies_only_when_missing(monkeypatch):
    monkeypatch.setattr(build.shutil, "which", lambda name: "npm")
    assert build.ui_commands(install=True) == [["npm", "ci"], ["npm", "run", "build"]]
    assert build.ui_commands(install=False) == [["npm", "run", "build"]]


def test_building_without_node_explains_what_is_missing(monkeypatch):
    import pytest

    monkeypatch.setattr(build.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit, match="Node.js"):
        build.npm()


def test_the_exe_is_windowed_but_keeps_output_streams(monkeypatch):
    import importlib.util as util

    assert "--windowed" in build.pyinstaller_args(Path("out")) and "--console" not in build.pyinstaller_args(Path("out"))
    spec = util.spec_from_file_location("entry", ROOT / "packaging" / "entry.py")
    entry = util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    monkeypatch.setattr(entry.sys, "stdout", None)
    monkeypatch.setattr(entry.sys, "stderr", None)
    monkeypatch.setattr(entry, "attach_console", lambda: False)
    entry.ensure_streams([])
    print("nowhere")  # a windowed exe must not crash on output
    assert entry.sys.stdout is not None and entry.sys.stderr is not None


def test_the_exe_and_installer_carry_the_app_icon():
    args = build.pyinstaller_args(Path("out"))
    assert args[args.index("--icon") + 1].endswith("icon.ico")
    assert (ROOT / "highlights" / "app" / "icon.ico").is_file()
    text = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    assert "SetupIconFile=..\\highlights\\app\\icon.ico" in text


def test_libraries_with_data_files_are_bundled_whole():
    args = build.pyinstaller_args(Path("out"))
    collected = [args[i + 1] for i, a in enumerate(args) if a == "--collect-all"]
    assert {"demoparser2", "awpy", "soundcard", "zstandard"} <= set(collected)
