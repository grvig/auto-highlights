"""Tests for changing settings from the app without losing comments."""

import tomllib

import pytest

from highlights.app.settings import SettingsError, apply_changes, set_value

CONFIG = """# Real config.

[paths]
# Where finished reels are written.
output_dir = "D:/auto-highlights/output"

[editing]
# "cut" (plain hard cuts) or "fade".
transition = "cut"
pro = false
"""


def test_an_existing_value_changes_and_its_comment_stays():
    text = set_value(CONFIG, "editing", "transition", "fade")
    assert '# "cut" (plain hard cuts) or "fade".\ntransition = "fade"\n' in text
    assert tomllib.loads(text)["editing"]["pro"] is False


def test_a_new_key_joins_its_section():
    text = set_value(CONFIG, "paths", "clips_dir", "D:\\auto-highlights\\clips")
    data = tomllib.loads(text)
    assert data["paths"]["clips_dir"] == "D:/auto-highlights/clips"
    assert text.index("clips_dir") < text.index("[editing]")


def test_a_missing_section_is_added_at_the_end():
    data = tomllib.loads(set_value(CONFIG, "recording", "aspect", "4:3"))
    assert data["recording"] == {"aspect": "4:3"}


def test_changes_are_written_and_checked(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(CONFIG, encoding="utf-8")
    apply_changes(path, {"editing.target_seconds": "90", "editing.music": "C:/music/track.mp3"})
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["editing"]["target_seconds"] == 90.0
    assert data["editing"]["music"] == "C:/music/track.mp3"
    assert "# Real config." in path.read_text(encoding="utf-8")


def test_settings_the_app_may_not_touch_are_refused_and_nothing_is_written(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(CONFIG, encoding="utf-8")
    with pytest.raises(SettingsError, match="cannot be changed"):
        apply_changes(path, {"editing.transition": "fade", "paths.cs2_root": "C:/"})
    with pytest.raises(SettingsError, match="must be a float"):
        apply_changes(path, {"editing.target_seconds": "two minutes"})
    assert path.read_text(encoding="utf-8") == CONFIG


def test_a_first_run_without_a_file_creates_one(tmp_path):
    path = tmp_path / "config.toml"
    apply_changes(path, {"recording.aspect": "stretched"})
    assert tomllib.loads(path.read_text(encoding="utf-8"))["recording"]["aspect"] == "stretched"
