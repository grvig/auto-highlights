"""Command-line entry point.

Parses a demo, reports players and a highlight plan, and optionally records
(dry-run or live) and stitches the clips into a reel.

    python -m highlights.cli path/to/demo.dem --player semi --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from highlights import __version__
from highlights.config import Config, ConfigError, load_config
from highlights.logging_setup import LEVELS, configure_logging
from highlights.preflight import all_passed, run_preflight
from highlights.engine.clip_plan import build_clip_plan
from highlights.engine.demo_source import DemoError, DemoSource, Player
from highlights.engine.detection import DetectionContext
from highlights.engine.models import deaths_of_player, kills_by_player
from highlights.engine.moments import HighlightType
from highlights.recorder.base import RecordedClip
from highlights.recorder.cs2_controller import Cs2Controller, Cs2Error
from highlights.recorder.dry_run import DryRunRecorder
from highlights.recorder.naming import build_clip_requests, sanitise_part
from highlights.recorder.obs_backend import ObsRecorder
from highlights.recorder.obs_client import ObsClient, ObsError
from highlights.recorder.session import record_requests
from highlights.stitcher.runner import StitchError
from highlights.stitcher.stitch import stitch_clips

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
    parser.add_argument(
        "demo", type=Path, nargs="?", help="path to a .dem file"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report environment readiness (config, CS2, ffmpeg, folders) and "
        "exit; needs no demo and launches nothing",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show progress (INFO logs)"
    )
    parser.add_argument(
        "--log-level",
        choices=LEVELS,
        help="console log level; overrides --verbose",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="also write full DEBUG logs here — keeps the CS2/OBS command "
        "exchange for diagnosing a failed capture",
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="log what would be recorded without launching CS2 or OBS",
    )
    mode.add_argument(
        "--record",
        action="store_true",
        help="record the plan for real (needs CS2 running with -netconport "
        "and OBS with its WebSocket server enabled)",
    )
    parser.add_argument(
        "--stitch",
        action="store_true",
        help="after recording, concatenate the clips into one reel (needs "
        "ffmpeg; has no effect on --dry-run, which writes no clips)",
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
    breakdown = ", ".join(
        f"{count} {htype}" for htype, count in plan.counts_by_type().items()
    )
    if breakdown:
        print(f"Breakdown  : {breakdown}")
    print(f"  {'#':<3} {'RND':>3} {'TIME':>6} {'LEN':>5} {'TYPE':<11} DESCRIPTION")
    print(f"  {'-' * 66}")
    for index, moment in enumerate(plan.moments, start=1):
        length = f"{moment.duration_seconds:.0f}s"
        print(
            f"  {index:<3} {moment.round_number:>3} {moment.timestamp:>6} "
            f"{length:>5} {str(moment.highlight_type):<11} {moment.description}"
        )


def pov_recording_warning(is_gotv: bool, player_name: str, live: bool) -> str | None:
    """Warn before a live capture off a POV demo, which has one perspective.

    Only for live recording — a dry run launches nothing, so the demo type
    does not matter there.
    """
    if not live or is_gotv:
        return None
    return (
        "\nWarning: this is a POV demo, which only holds one player's "
        f"perspective. Spectating {player_name} may not work unless they are "
        "the player who recorded it. GOTV demos spectate any player."
    )


def run_recording(
    source: DemoSource,
    player: Player,
    types: list[HighlightType],
    live: bool,
    stitch: bool = False,
) -> int:
    """Record the player's plan, dry by default. Returns an exit code."""
    warning = pov_recording_warning(source.info.is_gotv, player.name, live)
    if warning:
        print(warning, file=sys.stderr)

    ctx = DetectionContext.from_source(source)
    plan = build_clip_plan(ctx, player.steamid, types)
    if not plan.moments:
        print("\nNothing to record: the plan is empty.")
        return 0

    config = load_config()
    requests = build_clip_requests(
        plan=plan,
        demo_path=source.path,
        player_name=player.name,
        output_dir=config.clips_dir,
    )

    if live:
        recorder = ObsRecorder(
            cs2=Cs2Controller(config.cs2_root),
            obs=ObsClient(
                host=config.obs.host,
                port=config.obs.port,
                password=config.obs.password,
            ),
            output_dir=config.clips_dir,
        )
    else:
        recorder = DryRunRecorder()

    print(f"\nRecording {len(requests)} clip(s) with the {recorder.name} backend")
    try:
        clips = record_requests(recorder, requests)
    except (Cs2Error, ObsError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    failed = [c for c in clips if not c.succeeded]
    print(f"Done: {len(clips) - len(failed)} succeeded, {len(failed)} failed")
    for clip in failed:
        print(f"  #{clip.index:03d} {clip.error}", file=sys.stderr)

    if stitch:
        stitch_code = stitch_recorded(clips, player, config)
        if stitch_code != 0:
            return stitch_code

    return 1 if failed else 0


def stitch_recorded(
    clips: list[RecordedClip], player: Player, config: Config
) -> int:
    """Stitch recorded clips into a final reel. Returns an exit code."""
    reel_name = f"{sanitise_part(player.name)}_highlights.mkv"
    reel_path = config.output_dir / reel_name
    print(f"\nStitching {len(clips)} clip(s) into {reel_name}")
    try:
        output = stitch_clips(
            clips, reel_path, config.ffmpeg_path, work_dir=config.clips_dir
        )
    except StitchError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Reel written: {output}")
    return 0


def run_check() -> int:
    """Print the environment readiness report. Returns an exit code."""
    try:
        config = load_config()
    except ConfigError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    checks = run_preflight(config)
    print("\nEnvironment check:")
    for check in checks:
        mark = "OK  " if check.ok else "FAIL"
        print(f"  [{mark}] {check.name:<20} {check.detail}")

    if all_passed(checks):
        print("\nAll checks passed.")
        return 0
    print("\nSome checks failed — see above.")
    return 1


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

    level = args.log_level or ("info" if args.verbose else "warning")
    configure_logging(level=level, log_file=args.log_file)

    if args.check:
        return run_check()

    if args.demo is None:
        print("Error: a demo path is required (or use --check)", file=sys.stderr)
        return 1

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

        if args.dry_run or args.record:
            try:
                return run_recording(
                    source,
                    player,
                    types,
                    live=args.record,
                    stitch=args.stitch and args.record,
                )
            except ConfigError as error:
                print(f"Error: {error}", file=sys.stderr)
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
