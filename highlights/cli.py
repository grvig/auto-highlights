"""Command-line entry point for inspecting a demo.

Layer 1 only — parses and reports. Launches no game and records nothing.

    python -m highlights.cli path/to/demo.dem
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from highlights.engine.demo_source import DemoError, DemoSource
from highlights.engine.models import deaths_of_player, kills_by_player


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="highlights",
        description="Parse a CS2 demo and report its players and stats.",
    )
    parser.add_argument("demo", type=Path, help="path to a .dem file")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show parsing progress"
    )
    return parser


def print_match_summary(source: DemoSource) -> None:
    info = source.info
    rounds = source.round_list()
    kills = source.kill_list()

    print(f"\nMap        : {info.map_name}")
    print(f"Server     : {info.server_name}")
    print(f"Demo type  : {'GOTV' if info.is_gotv else 'POV'} ({info.client_name})")
    print(f"Tickrate   : {info.tickrate}")
    print(f"Rounds     : {len(rounds)}")
    print(f"Kills      : {len(kills)}")

    if not info.is_gotv:
        print(
            "\nWarning: this is a POV demo. Only the recording player's "
            "perspective exists, so other players cannot be spectated."
        )


def print_players(source: DemoSource) -> None:
    kills = source.kill_list()
    players = source.players()

    print(f"\nPlayers ({len(players)}):")
    print(f"  {'#':<3} {'SIDE':<5} {'NAME':<24} {'K':>4} {'D':>4} {'K/D':>6}")
    print(f"  {'-' * 50}")

    for index, player in enumerate(players, start=1):
        kill_count = len(kills_by_player(kills, player.steamid))
        death_count = len(deaths_of_player(kills, player.steamid))
        ratio = kill_count / death_count if death_count else float(kill_count)
        print(
            f"  {index:<3} {player.starting_side.upper():<5} {player.name:<24} "
            f"{kill_count:>4} {death_count:>4} {ratio:>6.2f}"
        )


def use_utf8_output() -> None:
    """Stop the Windows console's default codec choking on non-Latin names.

    Plenty of real matches have players with Chinese or Cyrillic names, and
    cp1252 raises UnicodeEncodeError on the first one.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    use_utf8_output()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    try:
        source = DemoSource(args.demo)
    except DemoError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print_match_summary(source)
    print_players(source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
