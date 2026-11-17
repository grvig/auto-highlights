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
    assert "PrivilegesRequired=lowest" in text and "--setup" in text


def test_builds_go_beside_the_parse_cache_by_default(monkeypatch, tmp_path):
    from highlights.config import ClipConfig, Config

    config = Config(cs2_root=None, output_dir=tmp_path / "out", clips_dir=tmp_path / "media" / "clips",
                    clips=ClipConfig())
    monkeypatch.setattr("highlights.config.load_config", lambda: config)
    assert build.default_out() == tmp_path / "media" / "build"
