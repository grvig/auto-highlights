"""Tests for the CLI entry point."""

import pytest

from highlights.cli import (
    build_parser,
    describe_player_lookup_failure,
    main,
    parse_types,
    pov_recording_warning,
    resolve_player,
)
from highlights.engine.demo_source import Player
from highlights.engine.moments import HighlightType


class FakeSource:
    def __init__(self, names):
        self._players = [
            Player(steamid=str(i), name=name, starting_side="ct")
            for i, name in enumerate(names, start=1)
        ]

    def players(self):
        return self._players


def test_demo_is_optional_at_parse_time_for_check():
    # demo is optional so --check can run without one; it is required at
    # runtime otherwise (see test_missing_demo_argument_exits_nonzero).
    args = build_parser().parse_args([])
    assert args.demos == []


def test_missing_demo_argument_exits_nonzero(capsys):
    exit_code = main([])
    assert exit_code == 1
    assert "demo path is required" in capsys.readouterr().err


def test_parser_reads_demo_and_verbose_flag():
    args = build_parser().parse_args(["match.dem", "--verbose"])
    assert [d.name for d in args.demos] == ["match.dem"]
    assert args.verbose


def test_parser_accepts_several_demos_and_me():
    args = build_parser().parse_args(["a.dem", "b.dem", "c.dem", "--me"])
    assert [d.name for d in args.demos] == ["a.dem", "b.dem", "c.dem"]
    assert args.me


def test_verbose_defaults_off():
    assert not build_parser().parse_args(["match.dem"]).verbose


def test_missing_demo_exits_nonzero_with_message(tmp_path, capsys):
    exit_code = main([str(tmp_path / "absent.dem")])
    assert exit_code == 1
    assert "No demo file" in capsys.readouterr().err


def test_parse_types_all_returns_every_type():
    assert set(parse_types("all")) == set(HighlightType)
    assert set(parse_types("")) == set(HighlightType)


def test_parse_types_accepts_values_and_aliases():
    types = parse_types("kill,multikill,utility")
    assert types == [
        HighlightType.KILL,
        HighlightType.MULTI_KILL,
        HighlightType.UTILITY,
    ]


def test_parse_types_rejects_unknown():
    with pytest.raises(ValueError):
        parse_types("bogus")


def test_parser_reads_player_and_types():
    args = build_parser().parse_args(["m.dem", "-p", "3", "-t", "kill,ace"])
    assert args.player == "3"
    assert args.types == "kill,ace"


def test_parser_reads_record_and_stitch_flags():
    args = build_parser().parse_args(["m.dem", "-p", "3", "--record", "--stitch"])
    assert args.record
    assert args.stitch
    assert not args.dry_run
    assert args.aspect is None  # config decides, stretched by default


def test_parser_reads_aspect():
    assert build_parser().parse_args(["m.dem", "--aspect", "4:3"]).aspect == "4:3"
    with pytest.raises(SystemExit):
        build_parser().parse_args(["m.dem", "--aspect", "21:9"])


def test_dry_run_and_record_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["m.dem", "--dry-run", "--record"])


def test_parser_reads_log_flags(tmp_path):
    args = build_parser().parse_args(
        ["m.dem", "--log-level", "debug", "--log-file", str(tmp_path / "r.log")]
    )
    assert args.log_level == "debug"
    assert args.log_file.name == "r.log"


def test_log_level_rejects_unknown():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["m.dem", "--log-level", "verbose"])


def test_pov_warning_only_fires_for_live_pov_demos():
    # Live recording off a POV demo warns.
    assert pov_recording_warning(is_gotv=False, player_name="semi", live=True)
    # GOTV demos are fine.
    assert pov_recording_warning(is_gotv=True, player_name="semi", live=True) is None
    # Dry run launches nothing, so demo type is irrelevant.
    assert pov_recording_warning(is_gotv=False, player_name="semi", live=False) is None


def test_pov_warning_names_the_player():
    warning = pov_recording_warning(is_gotv=False, player_name="ORYX", live=True)
    assert "ORYX" in warning
    assert "POV demo" in warning


def test_resolve_player_by_number_and_name():
    source = FakeSource(["semi", "ORYX", "HUNTER"])
    assert resolve_player(source, "2").name == "ORYX"
    assert resolve_player(source, "semi").name == "semi"
    assert resolve_player(source, "hunt").name == "HUNTER"  # case-insensitive


def test_resolve_player_ambiguous_returns_none():
    source = FakeSource(["player_one", "player_two"])
    assert resolve_player(source, "player") is None


def test_lookup_failure_distinguishes_absent_from_ambiguous():
    source = FakeSource(["semi", "semiauto", "ORYX"])
    # ambiguous: lists the matches
    ambiguous = describe_player_lookup_failure(source, "semi")
    assert "ambiguous" in ambiguous
    assert "semi" in ambiguous and "semiauto" in ambiguous
    # absent: says so
    assert "no player matching" in describe_player_lookup_failure(source, "zzz")


def test_lookup_failure_reports_out_of_range_number():
    source = FakeSource(["semi", "ORYX"])
    message = describe_player_lookup_failure(source, "9")
    assert "out of range" in message
    assert "1-2" in message


def test_version_flag_prints_version_and_exits(capsys):
    from highlights import __version__

    with pytest.raises(SystemExit) as info:
        build_parser().parse_args(["--version"])
    assert info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_parser_reads_best_and_order():
    args = build_parser().parse_args(["m.dem", "--me", "--best", "60", "--order", "chronological"])
    assert args.best == 60.0
    assert args.order == "chronological"


def test_order_defaults_to_montage_and_rejects_unknown():
    assert build_parser().parse_args(["m.dem"]).order == "montage"
    with pytest.raises(SystemExit):
        build_parser().parse_args(["m.dem", "--order", "shuffle"])


def test_parser_reads_edit_flags(tmp_path):
    args = build_parser().parse_args(
        ["m.dem", "--music", "song.mp3", "--no-captions", "--transition", "cut", "--plain"]
    )
    assert args.music.name == "song.mp3"
    assert args.no_captions and args.plain and not args.no_cards
    assert args.transition == "cut"


def test_editing_is_on_by_default():
    args = build_parser().parse_args(["m.dem"])
    assert not args.plain and args.transition == "fade" and args.music is None
