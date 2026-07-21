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


def test_play_demo_quotes_paths_with_spaces():
    built = cmd.play_demo("D:/SteamLibrary/Counter-Strike Global Offensive/m.dem")
    assert built.startswith("playdemo ")
    assert '"D:/SteamLibrary/Counter-Strike Global Offensive/m.dem"' in built


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


def test_spectate_player_uses_account_id():
    assert cmd.spectate_player("76561199266315708") == (
        "spec_player_by_accountid 1306049980"
    )


def test_simple_commands():
    assert cmd.pause() == "demo_pause"
    assert cmd.resume() == "demo_resume"
    assert cmd.disconnect() == "disconnect"
    assert cmd.spectator_mode() == "spec_mode 4"
    assert cmd.hide_hud(True).endswith(" 1")
    assert cmd.hide_hud(False).endswith(" 0")
