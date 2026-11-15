"""Tests for the CS2 console command builders."""

import pytest

from highlights.recorder import cs2_commands as cmd


def test_account_id_conversion_uses_steam_base():
    # semi's real SteamID64 from the sample demo.
    assert cmd.account_id_from_steamid64("76561199266315708") == 1_306_049_980


def test_account_id_accepts_int_and_str():
    assert cmd.account_id_from_steamid64(76561198000000000) == cmd.account_id_from_steamid64(
        "76561198000000000"
    )


def test_account_id_rejects_nonsense():
    with pytest.raises(cmd.CommandError):
        cmd.account_id_from_steamid64("not-a-steamid")
    with pytest.raises(cmd.CommandError):
        cmd.account_id_from_steamid64(123)  # below the base


def test_play_demo_reads_from_the_replays_folder():
    assert cmd.play_demo("semi_nuke.dem") == "playdemo replays/semi_nuke"
    assert cmd.play_demo("semi_nuke") == "playdemo replays/semi_nuke"


def test_play_demo_rejects_paths():
    with pytest.raises(cmd.CommandError, match="bare file name"):
        cmd.play_demo("D:/demos/m.dem")


def test_play_demo_rejects_empty_path():
    with pytest.raises(cmd.CommandError):
        cmd.play_demo("   ")


def test_goto_tick():
    assert cmd.goto_tick(10_128) == "demo_gototick 10128"


def test_goto_tick_rejects_negative():
    with pytest.raises(cmd.CommandError):
        cmd.goto_tick(-1)


def test_timescale_formats_cleanly():
    assert cmd.set_timescale(1.0) == "demo_timescale 1"
    assert cmd.set_timescale(0.5) == "demo_timescale 0.5"


def test_timescale_rejects_zero_or_negative():
    with pytest.raises(cmd.CommandError):
        cmd.set_timescale(0)


def test_spectate_player_quotes_the_name():
    assert cmd.spectate_player("semi") == 'spec_player "semi"'
    assert cmd.spectate_player("臻咘 踔") == 'spec_player "臻咘 踔"'
    assert cmd.spectate_player('a"b') == 'spec_player "ab"'


def test_spectate_player_rejects_empty_name():
    with pytest.raises(cmd.CommandError):
        cmd.spectate_player("  ")


def test_step_ticks():
    assert cmd.step_ticks(320) == "demo_step_tick 320"
    with pytest.raises(cmd.CommandError):
        cmd.step_ticks(0)


def test_movie_setup_cleans_the_hud_and_keeps_sound():
    assert "cl_draw_only_deathnotices 1" in cmd.MOVIE_SETUP
    assert "snd_mute_losefocus 0" in cmd.MOVIE_SETUP
    assert cmd.MOVIE_SETUP[0] == "sv_cheats 1"


def test_simple_commands():
    assert cmd.pause() == "demo_pause"
    assert cmd.resume() == "demo_resume"
    assert cmd.disconnect() == "disconnect"
    assert cmd.spectator_mode() == "spec_mode 2"
    assert cmd.toggle_demo_ui() == "demoui"
    assert cmd.hide_hud(True).endswith(" 1")
    assert cmd.hide_hud(False).endswith(" 0")


def test_footage_settings_are_put_back_to_the_players_values():
    player = {"hud_showtargetid": "true", "spec_show_xray": "0",
              "cl_hud_telemetry_ping_show": "2", "snd_mute_losefocus": "false"}
    commands = cmd.restore_settings(player)
    assert "hud_showtargetid 1" in commands
    assert "spec_show_xray 0" in commands
    assert "cl_hud_telemetry_ping_show 2" in commands
    assert "snd_mute_losefocus 0" in commands
    assert "cl_draw_only_deathnotices 0" in commands  # default, not in the file
    assert not any(c.startswith("sv_cheats") for c in commands)
