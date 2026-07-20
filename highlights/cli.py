"""Command-line entry point for inspecting a demo.

Layer 1 only — parses and reports. Launches no game and records nothing.

    python -m highlights.cli path/to/demo.dem
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from highlights.engine.clip_plan import build_clip_plan
from highlights.engine.demo_source import DemoError, DemoSource, Player
from highlights.engine.detection import DetectionContext
from highlights.engine.models import deaths_of_player, kills_by_player
from highlights.engine.moments import HighlightType

# CLI-friendly aliases on top of the HighlightType values.
_TYPE_ALIASES = {
    "multikill": HighlightType.MULTI_KILL,
    "kills": HighlightType.KILL,
    "deaths": HighlightType.DEATH,
    "clutches": HighlightType.CLUTCH,
    "aces": HighlightType.ACE,
    "util": HighlightType.UTILITY,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="highlights",
        description="Parse a CS2 demo and report its players, stats, and highlights.",
    )
    parser.add_argument("demo", type=Path, help="path to a .dem file")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show parsing progress"
    )
    parser.add_argument(
        "-p",
        "--player",
        help="player to plan highlights for: 1-based number or name substring",
    )
    parser.add_argument(
        "-t",
        "--types",
        default="all",
        help="comma-separated highlight types (default: all). "
        "e.g. kill,multi_kill,ace,clutch,death,utility",
    )
    return parser


def parse_types(spec: str) -> list[HighlightType]:
    """Turn a --types string into HighlightType values."""
    if spec.strip().lower() in ("", "all"):
        return list(HighlightType)
    result: list[HighlightType] = []
    for token in spec.split(","):
        key = token.strip().lower()
        if not key:
            continue
        if key in _TYPE_ALIASES:
            result.append(_TYPE_ALIASES[key])
        else:
            result.append(HighlightType(key))  # raises ValueError if unknown
    return result


def resolve_player(source: DemoSource, selector: str) -> Player | None:
    """Find a player by 1-based roster number or case-insensitive name match."""
    players = source.players()
    if selector.isdigit():
        index = int(selector)
        return players[index - 1] if 1 <= index <= len(players) else None
    lowered = selector.lower()
    matches = [p for p in players if lowered in p.name.lower()]
    return matches[0] if len(matches) == 1 else None


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


def print_clip_plan(
    source: DemoSource, player: Player, types: list[HighlightType]
) -> None:
    ctx = DetectionContext.from_source(source)
    plan = build_clip_plan(ctx, player.steamid, types)
    selected = ", ".join(str(t) for t in plan.selected_types)

    print(f"\nHighlight plan for {player.name}")
    print(f"Types      : {selected}")
    print(f"Moments    : {len(plan)}  ({plan.total_seconds:.0f}s of footage)")
    print(f"  {'#':<3} {'RND':>3} {'TIME':>6} {'TYPE':<11} DESCRIPTION")
    print(f"  {'-' * 60}")
    for index, moment in enumerate(plan.moments, start=1):
        print(
            f"  {index:<3} {moment.round_number:>3} {moment.timestamp:>6} "
            f"{str(moment.highlight_type):<11} {moment.description}"
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

    if args.player:
        try:
            types = parse_types(args.types)
        except ValueError as error:
            print(f"Error: unknown highlight type ({error})", file=sys.stderr)
            return 1
        player = resolve_player(source, args.player)
        if player is None:
            print(
                f"Error: no unique player matching '{args.player}'",
                file=sys.stderr,
            )
            return 1
        print_clip_plan(source, player, types)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
