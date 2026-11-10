"""Tests for config loading, focused on the ffmpeg path field."""

import pytest

from highlights.config import ConfigError, load_config

BASE_CONFIG = """
[paths]
cs2_root = "C:/games/cs2"
{ffmpeg_line}

[obs]
password = "pw"
"""


def write_config(tmp_path, ffmpeg_line=""):
    path = tmp_path / "config.toml"
    path.write_text(BASE_CONFIG.format(ffmpeg_line=ffmpeg_line))
    return path


def test_ffmpeg_defaults_to_bare_command(tmp_path):
    config = load_config(write_config(tmp_path))
    assert config.ffmpeg_path == "ffmpeg"


def test_ffmpeg_path_is_read_from_config(tmp_path):
    path = write_config(tmp_path, ffmpeg_line='ffmpeg = "C:/tools/ffmpeg.exe"')
    assert load_config(path).ffmpeg_path == "C:/tools/ffmpeg.exe"


def test_bare_ffmpeg_command_is_not_resolved_to_a_path(tmp_path):
    # A bare command must stay bare, not become an absolute path next to config.
    config = load_config(write_config(tmp_path))
    assert "/" not in config.ffmpeg_path
    assert "\\" not in config.ffmpeg_path


def test_missing_password_still_raises(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[paths]\ncs2_root = "C:/games/cs2"\n[obs]\n')
    with pytest.raises(ConfigError, match="password"):
        load_config(path)


VALID = """
[paths]
cs2_root = "C:/games/cs2"

[obs]
port = 4455
password = "pw"

[clips]
pre_roll_seconds = 3.0
post_roll_seconds = 2.0
"""


def test_validate_accepts_a_good_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(VALID)
    load_config(path).validate()  # must not raise


def test_validate_rejects_bad_port(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(VALID.replace("port = 4455", "port = 70000"))
    with pytest.raises(ConfigError, match="obs.port"):
        load_config(path).validate()


def test_validate_rejects_negative_roll(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(VALID.replace("pre_roll_seconds = 3.0", "pre_roll_seconds = -1.0"))
    with pytest.raises(ConfigError, match="pre_roll_seconds"):
        load_config(path).validate()


def test_validate_reports_all_problems_at_once(tmp_path):
    path = tmp_path / "config.toml"
    bad = VALID.replace("port = 4455", "port = 0").replace(
        "post_roll_seconds = 2.0", "post_roll_seconds = -2.0"
    )
    path.write_text(bad)
    with pytest.raises(ConfigError) as info:
        load_config(path).validate()
    message = str(info.value)
    assert "obs.port" in message
    assert "post_roll_seconds" in message


NO_CS2_ROOT = """
[paths]
output_dir = "./output"

[obs]
password = "pw"
"""


def test_missing_cs2_root_is_auto_detected(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(NO_CS2_ROOT)
    found = tmp_path / "cs2"
    config = load_config(path, locate_cs2=lambda: found)
    assert config.cs2_root == found
    assert config.cs2_root_detected


def test_configured_cs2_root_wins_over_detection(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(BASE_CONFIG.format(ffmpeg_line=""))
    config = load_config(path, locate_cs2=lambda: tmp_path / "elsewhere")
    assert str(config.cs2_root).replace("\\", "/") == "C:/games/cs2"
    assert not config.cs2_root_detected


def test_undetectable_cs2_fails_only_when_recording_needs_it(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(NO_CS2_ROOT)
    config = load_config(path, locate_cs2=lambda: None)  # loading still works
    assert config.cs2_root is None
    with pytest.raises(ConfigError, match="Could not find CS2"):
        config.verify_cs2_install()
