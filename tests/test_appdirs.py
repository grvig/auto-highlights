"""Tests for where an installed app keeps its files."""

import tomllib

from highlights import appdirs


def test_installed_copies_live_under_local_app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "me"))
    assert appdirs.app_data_dir() == tmp_path / "Local" / "auto-highlights"
    assert appdirs.videos_dir() == tmp_path / "me" / "Videos" / "auto-highlights"
    assert appdirs.tools_dir() == tmp_path / "Local" / "auto-highlights" / "tools"


def test_a_source_checkouts_config_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(appdirs, "repo_root", lambda: tmp_path / "repo")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    (tmp_path / "repo").mkdir()
    assert appdirs.config_location() == tmp_path / "Local" / "auto-highlights" / "config.toml"
    (tmp_path / "repo" / "config.toml").write_text("")
    assert appdirs.config_location() == tmp_path / "repo" / "config.toml"


def test_first_run_writes_a_working_starter_config(tmp_path, monkeypatch):
    monkeypatch.setattr(appdirs, "repo_root", lambda: tmp_path / "repo")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "me"))
    path = appdirs.ensure_config()
    paths = tomllib.loads(path.read_text(encoding="utf-8"))["paths"]
    assert paths["output_dir"].endswith("me/Videos/auto-highlights")
    assert paths["hlae"].endswith("auto-highlights/tools/hlae")
    path.write_text("# edited\n")
    assert appdirs.ensure_config() == path and path.read_text() == "# edited\n"  # never overwritten


def test_the_starter_config_loads(tmp_path, monkeypatch):
    from highlights.config import load_config

    monkeypatch.setattr(appdirs, "repo_root", lambda: tmp_path / "repo")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    config = load_config(appdirs.ensure_config(), locate_cs2=lambda: None)
    config.validate()
    assert config.clips_dir == tmp_path / "Local" / "auto-highlights" / "clips"
