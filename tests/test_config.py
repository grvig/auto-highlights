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
