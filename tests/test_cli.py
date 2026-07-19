"""Tests for the CLI entry point."""

import pytest

from highlights.cli import build_parser, main


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
