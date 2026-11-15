"""Tests for config loading, focused on the ffmpeg path field."""

import pytest

from highlights.config import ConfigError, load_config

BASE_CONFIG = """
[paths]
cs2_root = "C:/games/cs2"
{ffmpeg_line}
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


def test_an_old_obs_section_is_ignored(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[paths]\ncs2_root = "C:/games/cs2"\n[obs]\npassword = "pw"\n')
    load_config(path).validate()  # must not raise


VALID = """
[paths]
cs2_root = "C:/games/cs2"

[clips]
pre_roll_seconds = 3.0
post_roll_seconds = 2.0
"""


def test_validate_accepts_a_good_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(VALID)
    load_config(path).validate()  # must not raise


def test_validate_rejects_a_tiny_render_size(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(VALID + "\n[recording]\nwidth = 100\n")
    with pytest.raises(ConfigError, match="too small"):
        load_config(path).validate()


def test_validate_rejects_negative_roll(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(VALID.replace("pre_roll_seconds = 3.0", "pre_roll_seconds = -1.0"))
    with pytest.raises(ConfigError, match="pre_roll_seconds"):
        load_config(path).validate()


def test_validate_reports_all_problems_at_once(tmp_path):
    path = tmp_path / "config.toml"
    bad = VALID.replace("post_roll_seconds = 2.0", "post_roll_seconds = -2.0")
    bad += "\n[recording]\nframerate = 1000\n"
    path.write_text(bad)
    with pytest.raises(ConfigError) as info:
        load_config(path).validate()
    message = str(info.value)
    assert "framerate" in message
    assert "post_roll_seconds" in message


NO_CS2_ROOT = """
[paths]
output_dir = "./output"
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


def test_cache_dir_defaults_next_to_clips(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(NO_CS2_ROOT.replace('output_dir = "./output"', 'clips_dir = "media/clips"'))
    config = load_config(path, locate_cs2=lambda: None)
    assert config.resolved_cache_dir == (tmp_path / "media" / "cache").resolve()


def test_cache_dir_can_be_configured(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(NO_CS2_ROOT.replace('output_dir = "./output"', 'cache_dir = "elsewhere"'))
    config = load_config(path, locate_cs2=lambda: None)
    assert config.resolved_cache_dir == (tmp_path / "elsewhere").resolve()


def test_recording_defaults_to_hlae_at_4x3_stretched(tmp_path):
    rec = load_config(write_config(tmp_path)).recording
    assert (rec.recorder, rec.width, rec.height, rec.framerate) == ("hlae", 1440, 1080, 60)
    assert rec.aspect == "stretched"
    assert rec.hlae_path is None


def test_recording_section_and_hlae_path_are_read(tmp_path):
    path = write_config(tmp_path, 'hlae = "D:/tools/hlae"')
    path.write_text(path.read_text() + '\n[recording]\nrecorder = "window"\nwidth = 1280\nheight = 960\n')
    config = load_config(path)
    assert config.recording.recorder == "window"
    assert (config.recording.width, config.recording.height) == (1280, 960)
    assert config.recording.hlae_path.as_posix().endswith("D:/tools/hlae")


def test_validate_rejects_unknown_recorder(tmp_path):
    path = write_config(tmp_path)
    path.write_text(path.read_text() + '\n[recording]\nrecorder = "obs"\n')
    with pytest.raises(ConfigError, match="recording.recorder"):
        load_config(path).validate()


def test_editing_defaults_are_read(tmp_path):
    path = write_config(tmp_path)
    path.write_text(
        path.read_text() + '\n[editing]\nmusic = "music/track.mp3"\npro = true\ntransition = "cut"\n'
    )
    editing = load_config(path).editing
    assert editing.music.name == "track.mp3" and editing.music.is_absolute()
    assert editing.pro and editing.transition == "cut" and editing.music_start == 0.0
