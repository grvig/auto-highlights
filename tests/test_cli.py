"""Tests for the CLI entry point."""

import pytest

from highlights.cli import build_parser, main, parse_types
from highlights.engine.moments import HighlightType


def test_parser_requires_a_demo_path():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


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
