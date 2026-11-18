"""Tests for blaming a recent CS2 update when recording breaks."""

from datetime import datetime

from highlights.recorder.compat import cs2_updated_at, hook_failure_hint, old_demo_hint

MANIFEST = '"AppState"\n{\n\t"appid"\t\t"730"\n\t"LastUpdated"\t\t"1794976532"\n\t"buildid"\t\t"26748068"\n}\n'


def install(tmp_path, manifest=MANIFEST):
    root = tmp_path / "steamapps" / "common" / "Counter-Strike Global Offensive"
    root.mkdir(parents=True)
    if manifest is not None:
        (tmp_path / "steamapps" / "appmanifest_730.acf").write_text(manifest)
    return root


def test_the_update_time_comes_from_steams_manifest(tmp_path):
    assert cs2_updated_at(install(tmp_path)) == datetime.fromtimestamp(1794976532)


def test_a_recent_update_is_mentioned_with_what_to_do(tmp_path):
    root = install(tmp_path)
    soon = datetime.fromtimestamp(1794976532 + 3600)
    assert "HLAE may not support this build yet" in hook_failure_hint(root, soon)
    assert 'recorder = "window"' in hook_failure_hint(root, soon)
    assert "may refuse demos recorded" in old_demo_hint(root, soon)


def test_an_old_update_or_missing_manifest_says_nothing(tmp_path):
    root = install(tmp_path)
    months_later = datetime.fromtimestamp(1794976532 + 86400 * 60)
    assert hook_failure_hint(root, months_later) == ""
    assert hook_failure_hint(install(tmp_path / "other", manifest=None)) == ""
    assert hook_failure_hint(None) == ""


def test_an_hlae_released_before_the_latest_update_is_flagged(tmp_path):
    from highlights.recorder.compat import hlae_older_than_game

    root = install(tmp_path)
    soon = datetime.fromtimestamp(1794976532 + 3600)
    assert hlae_older_than_game(datetime(2026, 11, 7), root, soon)
    assert not hlae_older_than_game(datetime.fromtimestamp(1794976532 + 60), root, soon)
    assert not hlae_older_than_game(None, root, soon)
