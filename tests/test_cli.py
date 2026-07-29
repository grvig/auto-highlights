"""Tests for the CLI entry point."""

import pytest

from highlights.cli import build_parser, main, parse_types
from highlights.engine.moments import HighlightType


def test_demo_is_optional_at_parse_time_for_check():
    # demo is optional so --check can run without one; it is required at
    # runtime otherwise (see test_missing_demo_argument_exits_nonzero).
    args = build_parser().parse_args([])
    assert args.demo is None


def test_missing_demo_argument_exits_nonzero(capsys):
    exit_code = main([])
    assert exit_code == 1
    assert "demo path is required" in capsys.readouterr().err


def test_parser_reads_demo_and_verbose_flag():
    args = build_parser().parse_args(["match.dem", "--verbose"])
    assert args.demo.name == "match.dem"
    assert args.verbose


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
