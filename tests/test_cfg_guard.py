"""Tests for backing up and restoring the player's CS2 settings."""

from pathlib import Path

import pytest

from highlights.recorder.cfg_guard import CfgGuard, cs2_cfg_dir


@pytest.fixture
def cfg(tmp_path):
    folder = tmp_path / "cfg"
    folder.mkdir()
    (folder / "cs2_user_convars_0_slot0.vcfg").write_text('"volume" "0.48999998"')
    (folder / "cs2_video.txt").write_text('"setting.defaultres" "1280"')
    return folder


def test_cfg_dir_uses_the_account_id(tmp_path):
    path = cs2_cfg_dir(tmp_path, "76561199266315708")
    assert path == tmp_path / "userdata" / "1306049980" / "730" / "local" / "cfg"


def test_changed_settings_are_put_back(cfg, tmp_path):
    with CfgGuard(cfg, tmp_path / "backup") as guard:
        (cfg / "cs2_user_convars_0_slot0.vcfg").write_text('"volume" "1"')
    assert (cfg / "cs2_user_convars_0_slot0.vcfg").read_text() == '"volume" "0.48999998"'
    assert guard.backup_dir.is_dir()


def test_deleted_settings_come_back(cfg, tmp_path):
    with CfgGuard(cfg, tmp_path / "backup"):
        (cfg / "cs2_video.txt").unlink()
    assert (cfg / "cs2_video.txt").read_text() == '"setting.defaultres" "1280"'


def test_untouched_files_are_not_rewritten(cfg, tmp_path):
    guard = CfgGuard(cfg, tmp_path / "backup")
    guard.backup()
    (cfg / "cs2_video.txt").write_text("changed")
    assert guard.restore() == [cfg / "cs2_video.txt"]


def test_restore_runs_even_when_recording_fails(cfg, tmp_path):
    with pytest.raises(RuntimeError), CfgGuard(cfg, tmp_path / "backup"):
        (cfg / "cs2_video.txt").write_text("broken")
        raise RuntimeError("CS2 crashed")
    assert (cfg / "cs2_video.txt").read_text() == '"setting.defaultres" "1280"'


def test_two_backups_in_one_second_do_not_collide(cfg, tmp_path):
    first = CfgGuard(cfg, tmp_path / "backup").backup()
    second = CfgGuard(cfg, tmp_path / "backup").backup()
    assert first != second and first.is_dir() and second.is_dir()


def test_missing_cfg_folder_is_harmless(tmp_path):
    with CfgGuard(Path(tmp_path / "absent"), tmp_path / "backup") as guard:
        pass
    assert guard.backup_dir is None
