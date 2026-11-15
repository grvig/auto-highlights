"""Command-line entry point.

Parses a demo, reports players and a highlight plan, and optionally records
(dry-run or live) and stitches the clips into a reel.

    python -m highlights.cli path/to/demo.dem --player semi --dry-run
"""

from __future__ import annotations

import argparse
import contextlib
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from highlights import __version__
from highlights.config import Config, ConfigError, load_config
from highlights.logging_setup import LEVELS, configure_logging
from highlights.preflight import all_passed, run_preflight
from highlights.engine.cache import DemoCache
from highlights.engine.clip_plan import ClipPlan
from highlights.engine.demo_source import DemoError, DemoSource, Player
from highlights.engine.models import deaths_of_player, kills_by_player
from highlights.engine.moments import HighlightType
from highlights.engine.multi import (
    Match,
    build_multi_plan,
    match_from_source,
    players_across,
)
from highlights.engine.scoring import moment_kills
from highlights.engine.selection import ORDERS, arrange, select_best
from highlights.steam.account import signed_in_account
from highlights.steam.locate import find_steam_root
from highlights.recorder.base import RecordedClip
from highlights.recorder.cs2_controller import Cs2Error
from highlights.recorder.dry_run import DryRunRecorder
from highlights.recorder.naming import build_clip_requests, sanitise_part
from highlights.recorder.factory import build_live_recorder, settings_guard, update_hlae
from highlights.recorder.hlae import BUNDLED_DIR as HLAE_BUNDLED_DIR
from highlights.recorder.hlae import HlaeError
from highlights.recorder.session import already_recorded, record_requests
from highlights.editor.beats import beat_times, load_samples, tempo_of
from highlights.editor.fonts import FontError
from highlights.editor.preview import describe_edit
from highlights.editor.probe import ProbeError
from highlights.editor.reel import EditOptions, ReelBuilder
from highlights.stitcher.runner import StitchError
from highlights.stitcher.aspect import PROFILES, convert
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


# xfade transitions offered on the command line, plus hard cuts.
TRANSITIONS = ("fade", "cut", "fadeblack", "fadewhite", "smoothleft", "zoomin")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="highlights",
        description="Parse a CS2 demo and report its players, stats, and highlights.",
    )
    parser.add_argument(
        "demos",
        type=Path,
        nargs="*",
        help="one or more .dem files; several are pooled into one plan",
    )
    parser.add_argument(
        "--me",
        action="store_true",
        help="plan for the Steam account signed in on this PC",
    )
    parser.add_argument(
        "--pro",
        action="store_true",
        help="frag-movie style: slow motion, punch-ins and flashes on kills",
    )
    parser.add_argument(
        "--slowmo",
        action="store_true",
        help="dip into slow motion on each of the player's kills",
    )
    parser.add_argument(
        "--best",
        type=float,
        metavar="SECONDS",
        help="keep only the strongest moments, filling about this many seconds",
    )
    parser.add_argument(
        "--order",
        choices=ORDERS,
        default="montage",
        help="with --best: montage (hook, build, best last) or chronological",
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
        "--update-hlae",
        action="store_true",
        help="download the newest HLAE release (recording does this automatically)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="parse the demo from scratch instead of using the parse cache",
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
        help="also write full DEBUG logs here — keeps the CS2 console "
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
        help="log what would be recorded without launching CS2",
    )
    mode.add_argument(
        "--record",
        action="store_true",
        help="record the plan for real: launches CS2 through HLAE and renders "
        "every clip (falls back to capturing an already running CS2 window)",
    )
    parser.add_argument(
        "--stitch",
        action="store_true",
        help="after recording, concatenate the clips into one reel (needs "
        "ffmpeg; has no effect on --dry-run, which writes no clips)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="with --record: keep clips an interrupted run already recorded",
    )
    parser.add_argument(
        "--edit-only",
        action="store_true",
        help="skip recording and re-edit the clips already on disk into a reel",
    )
    parser.add_argument(
        "--aspect",
        choices=sorted(PROFILES),
        help="shape of the stitched reel (default from config: stretched, "
        "4:3 stretched to fill 16:9)",
    )
    edit = parser.add_argument_group("editing (with --stitch)")
    edit.add_argument("--music", type=Path, help="your own music track to cut the reel to")
    edit.add_argument("--no-captions", action="store_true", help="leave out highlight captions")
    edit.add_argument("--no-cards", action="store_true", help="leave out the title and outro cards")
    edit.add_argument(
        "--transition",
        default="fade",
        choices=TRANSITIONS,
        help="how clips join (default: fade; cut for hard cuts)",
    )
    edit.add_argument("--punch-ins", action="store_true", help="zoom in on headshots")
    edit.add_argument("--flashes", action="store_true", help="flash the screen on every kill")
    edit.add_argument("--plain", action="store_true", help="just join the clips, no editing")
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


class HasPlayers(Protocol):
    """A single demo, or the combined roster of several."""

    def players(self) -> list[Player]: ...


@dataclass(frozen=True)
class Roster:
    """Players pooled across several demos, numbered for --player."""

    entries: list[Player]

    def players(self) -> list[Player]:
        return self.entries


def print_matches(sources: list[DemoSource], matches: list[Match]) -> Roster:
    """Summarise several demos and the players across them."""
    print(f"\nMatches ({len(sources)}):")
    for index, source in enumerate(sources, start=1):
        info = source.info
        kind = "GOTV" if info.is_gotv else "POV"
        rounds = len(source.round_list())
        print(f"  {index}. {info.map_name:<12} {kind:<4} {rounds:>2} rounds  {source.path.name}")

    pooled = players_across(matches)
    print(f"\nPlayers across all matches ({len(pooled)}):")
    for index, (player, count) in enumerate(pooled, start=1):
        print(f"  {index:<3} {player.name:<24} in {count} of {len(matches)}")
    return Roster([player for player, _ in pooled])


def choose_player(
    roster: HasPlayers, selector: str | None, me: bool
) -> tuple[Player | None, str]:
    """Resolve --me or --player to a player, or explain why it failed."""
    if me:
        steam_root = find_steam_root()
        account = signed_in_account(steam_root) if steam_root else None
        if account is None:
            return None, "no signed-in Steam account found; use --player instead"
        player = next((p for p in roster.players() if p.steamid == account.steamid), None)
        if player is None:
            return None, "the signed-in Steam account is not in these demos"
        return player, ""
    player = resolve_player(roster, selector or "")
    if player is None:
        return None, describe_player_lookup_failure(roster, selector or "")
    return player, ""


def resolve_player(source: HasPlayers, selector: str) -> Player | None:
    """Find a player by 1-based roster number or case-insensitive name match."""
    players = source.players()
    if selector.isdigit():
        index = int(selector)
        return players[index - 1] if 1 <= index <= len(players) else None
    lowered = selector.lower()
    matches = [p for p in players if lowered in p.name.lower()]
    return matches[0] if len(matches) == 1 else None


def describe_player_lookup_failure(source: HasPlayers, selector: str) -> str:
    """Explain why resolve_player returned nothing: absent, out of range, or

    ambiguous — and for ambiguity, list the names that matched so the user can
    pick a more specific one.
    """
    players = source.players()
    if selector.isdigit():
        return f"player number {selector} is out of range (1-{len(players)})"
    matches = [p for p in players if selector.lower() in p.name.lower()]
    if not matches:
        return f"no player matching '{selector}'"
    names = ", ".join(p.name for p in matches)
    return f"'{selector}' is ambiguous — matches: {names}"


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


def print_clip_plan(plan: ClipPlan, player_name: str) -> None:
    selected = ", ".join(str(t) for t in plan.selected_types)

    print(f"\nHighlight plan for {player_name}")
    print(f"Types      : {selected}")
    print(f"Moments    : {len(plan)}  ({plan.total_seconds:.0f}s of footage)")
    breakdown = ", ".join(
        f"{count} {htype}" for htype, count in plan.counts_by_type().items()
    )
    if breakdown:
        print(f"Breakdown  : {breakdown}")
    print(f"  {'#':<3} {'SCORE':>5} {'RND':>3} {'TIME':>6} {'LEN':>5} {'TYPE':<11} DESCRIPTION")
    print(f"  {'-' * 72}")
    for index, moment in enumerate(plan.moments, start=1):
        length = f"{moment.duration_seconds:.0f}s"
        tags = f"  [{', '.join(moment.tags)}]" if moment.tags else ""
        print(
            f"  {index:<3} {moment.score:>5.1f} {moment.round_number:>3} {moment.timestamp:>6} "
            f"{length:>5} {str(moment.highlight_type):<11} {moment.description}{tags}"
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
    plan: ClipPlan,
    player_name: str,
    *,
    fallback_demo: Path,
    pov_demos: list[str],
    live: bool,
    stitch: bool = False,
    names: dict[str, str] | None = None,
    aspect: str | None = None,
    edit: EditOptions | None = None,
    resume: bool = False,
    edit_only: bool = False,
    preview_edit: bool = False,
) -> int:
    """Record a plan, dry by default. Returns an exit code."""
    warning = pov_recording_warning(not pov_demos, player_name, live)
    if warning:
        print(f"{warning} POV demos here: {', '.join(pov_demos)}", file=sys.stderr)

    if not plan.moments:
        print("\nNothing to record: the plan is empty.")
        return 0

    config = load_config()
    requests = build_clip_requests(
        plan=plan,
        demo_path=fallback_demo,
        player_name=player_name,
        output_dir=config.clips_dir,
        extension="mp4",
        names=names,
    )

    if edit_only:
        clips = [
            RecordedClip(r, r.output_path, succeeded=already_recorded(r),
                         error=None if already_recorded(r) else "not recorded yet")
            for r in requests
        ]
        return stitch_recorded(clips, player_name, config, aspect, edit)

    try:
        recorder = build_live_recorder(config) if live else DryRunRecorder()
    except HlaeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"\nRecording {len(requests)} clip(s) with the {recorder.name} backend")
    try:
        with settings_guard(config) if live else contextlib.nullcontext():
            clips = record_requests(recorder, requests, skip_existing=resume and live)
    except Cs2Error as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    failed = [c for c in clips if not c.succeeded]
    print(f"Done: {len(clips) - len(failed)} succeeded, {len(failed)} failed")
    for clip in failed:
        print(f"  #{clip.index:03d} {clip.error}", file=sys.stderr)

    if preview_edit and edit:
        print("\nEdit preview:")
        for line in describe_edit(requests, edit, lambda song: music_tempo(song, config)):
            print(f"  {line}")

    if stitch:
        stitch_code = stitch_recorded(clips, player_name, config, aspect, edit)
        if stitch_code != 0:
            return stitch_code

    return 1 if failed else 0


def kills_in_plan(plan: ClipPlan, sources: list[DemoSource], matches: list[Match]) -> int:
    """How many of the player's kills the planned moments contain."""
    by_demo = {source.path: match.context for source, match in zip(sources, matches)}
    total = 0
    for moment in plan.moments:
        context = by_demo.get(Path(moment.source_demo)) if moment.source_demo else None
        context = context or matches[0].context
        total += len(moment_kills(moment, context.kills))
    return total


def music_tempo(song: Path, config: Config) -> float | None:
    """The track's tempo for the preview, or None if it cannot be read."""
    try:
        return tempo_of(beat_times(load_samples(song, config.ffmpeg_path)))
    except (OSError, subprocess.CalledProcessError):
        return None


def stitch_recorded(
    clips: list[RecordedClip],
    player_name: str,
    config: Config,
    aspect: str | None = None,
    edit: EditOptions | None = None,
) -> int:
    """Edit (or just join) recorded clips into a reel in the chosen shape."""
    profile = PROFILES.get(aspect or config.recording.aspect, PROFILES["stretched"])
    reel_name = f"{sanitise_part(player_name)}_highlights.mp4"
    reel_path = config.clips_dir / f"_joined_{reel_name}"
    print(f"\n{'Editing' if edit else 'Stitching'} {len(clips)} clip(s) into {reel_name}")
    try:
        if edit:
            builder = ReelBuilder(edit, config.clips_dir / "edit", config.ffmpeg_path)
            output = builder.build(clips, reel_path)
        else:
            output = stitch_clips(clips, reel_path, config.ffmpeg_path, work_dir=config.clips_dir)
        final = convert(output, config.output_dir / reel_name, profile, config.ffmpeg_path)
    except (StitchError, RuntimeError, ValueError, OSError,
            subprocess.CalledProcessError, FontError, ProbeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Reel written ({profile.name}): {final}")
    return 0


def run_update_hlae() -> int:
    """Install or update HLAE. Returns an exit code."""
    try:
        config = load_config()
    except ConfigError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    target = config.recording.hlae_path or HLAE_BUNDLED_DIR
    version = update_hlae(target)
    if version is None:
        print("Could not update HLAE; see the log.", file=sys.stderr)
        return 1
    print(f"HLAE {version} ready at {target}")
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


def open_cache() -> DemoCache | None:
    """The parse cache from config, or None when there is no usable config.

    Parsing still works without a config file; it just is not cached.
    """
    try:
        return DemoCache(load_config().resolved_cache_dir)
    except ConfigError:
        return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    use_utf8_output()

    level = args.log_level or ("info" if args.verbose else "warning")
    configure_logging(level=level, log_file=args.log_file)

    if args.check:
        return run_check()
    if args.update_hlae:
        return run_update_hlae()

    if not args.demos:
        print("Error: a demo path is required (or use --check)", file=sys.stderr)
        return 1

    cache = None if args.no_cache else open_cache()
    try:
        sources = [DemoSource(path, cache=cache) for path in args.demos]
    except DemoError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    matches = [match_from_source(source) for source in sources]
    if len(sources) == 1:
        print_match_summary(sources[0])
        print_players(sources[0])
        roster = sources[0]
    else:
        roster = print_matches(sources, matches)

    if not (args.player or args.me):
        return 0
    try:
        types = parse_types(args.types)
    except ValueError as error:
        print(f"Error: unknown highlight type ({error})", file=sys.stderr)
        return 1
    player, reason = choose_player(roster, args.player, args.me)
    if player is None:
        print(f"Error: {reason}", file=sys.stderr)
        return 1

    multi = build_multi_plan(matches, player.steamid, types, slowmo=args.slowmo or args.pro)
    for label in multi.missing_from:
        print(f"Note: {player.name} is not in {label}", file=sys.stderr)
    plan = multi.plan
    if args.best:
        chosen = select_best(plan.moments, args.best)
        plan = replace(plan, moments=arrange(chosen, plan.moments, args.order))
        print(f"\nBest {args.best:g}s, {args.order} order")
    print_clip_plan(plan, player.name)

    if args.dry_run or args.record or args.edit_only:
        pov = [s.path.name for s in sources if not s.info.is_gotv]
        try:
            return run_recording(
                plan,
                player.name,
                fallback_demo=sources[0].path,
                pov_demos=pov,
                live=args.record,
                resume=args.resume,
                edit_only=args.edit_only,
                preview_edit=args.stitch and args.dry_run,
                stitch=args.stitch and args.record,
                names={p.steamid: p.name for s in sources for p in s.players()},
                aspect=args.aspect,
                edit=None if args.plain else EditOptions(
                    player_name=player.name,
                    captions=not args.no_captions,
                    cards=not args.no_cards,
                    transition=args.transition,
                    music=args.music,
                    maps={s.path: s.info.map_name for s in sources},
                    kills_shown=kills_in_plan(plan, sources, matches),
                    punch_ins=args.punch_ins or args.pro,
                    flashes=args.flashes or args.pro,
                ),
            )
        except ConfigError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
