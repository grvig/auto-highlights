"""Command-line entry point.

Parses a demo, reports players and a highlight plan, and optionally records
(dry-run or live) and stitches the clips into a reel.

    python -m highlights.cli path/to/demo.dem --player semi --dry-run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from highlights import __version__
from highlights.config import Config, ConfigError, EditingConfig, load_config
from highlights.logging_setup import LEVELS, configure_logging, run_log_path
from highlights.preflight import all_passed, run_preflight
from highlights.engine.clip_plan import ClipPlan
from highlights.engine.demo_source import DemoError, DemoSource, Player
from highlights.engine.models import deaths_of_player, kills_by_player
from highlights.engine.multi import Match, players_across
from highlights.pipeline.planning import (
    PlanOptions,
    clip_timing,
    kills_in_plan,
    load_matches,
    open_cache,
    plan_reel,
)
from highlights.pipeline.production import (
    ProductionError,
    clip_requests,
    clips_on_disk,
    produce_reel,
    record_clips,
)
from highlights.pipeline.types import parse_types
from highlights.progress import Progress
from highlights.appdirs import ensure_config
from highlights.setup import SetupError, ensure_tools
from highlights.engine.selection import DEFAULT_MIN_SCORE, ORDERS
from highlights.steam.account import signed_in_account
from highlights.steam.locate import find_steam_root
from highlights.recorder.base import RecordedClip
from highlights.recorder.factory import update_hlae
from highlights.recorder.hlae import BUNDLED_DIR as HLAE_BUNDLED_DIR
from highlights.editor.beats import beat_times, load_samples, tempo_of
from highlights.editor.preview import describe_edit
from highlights.editor.reel import EditOptions
from highlights.stitcher.aspect import PROFILES



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
        "--victim-cams",
        action="store_true",
        help="after quick multi-kills, replay each kill from the victim's eyes",
    )
    parser.add_argument(
        "--slowmo",
        action="store_true",
        help="dip into slow motion on each of the player's kills",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="keep every play instead of the best ~2 minutes when recording",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help=f"with --best: leave out plays scoring under this (default {DEFAULT_MIN_SCORE:g})",
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
        "--setup",
        action="store_true",
        help="find or download everything recording needs (ffmpeg, HLAE) and exit",
    )
    parser.add_argument(
        "--app",
        action="store_true",
        help="open the desktop app window instead of working on the command line",
    )
    parser.add_argument(
        "--app-dev",
        metavar="URL",
        help=argparse.SUPPRESS,  # point the window at `npm run dev` while working on the UI
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
        default="frags",
        help="comma-separated highlight types (default: frags = kill, "
        "multi_kill, ace, clutch). Also death, utility, or all",
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
        "--spectator-hud",
        action="store_true",
        help="keep CS2's spectator HUD (team bar, money, radar) instead of the "
        "clean default with only the kill feed",
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
    edit.add_argument(
        "--music-start",
        type=float,
        default=None,
        metavar="SECONDS",
        help="start the music this far into the track, e.g. to skip a slow intro",
    )
    edit.add_argument("--captions", action="store_true", help="name each highlight on screen")
    edit.add_argument("--cards", action="store_true", help="add title and outro cards")
    edit.add_argument(
        "--transition",
        default=None,
        choices=TRANSITIONS,
        help="how clips join (default: cut, plain hard cuts)",
    )
    edit.add_argument("--teaser", action="store_true", help="open with a slowed flash of the best kill")
    edit.add_argument("--punch-ins", action="store_true", help="zoom in on headshots")
    edit.add_argument("--flashes", action="store_true", help="flash the screen on every kill")
    edit.add_argument("--plain", action="store_true", help="just join the clips, no editing")
    return parser


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
    spectator_hud: bool = False,
) -> int:
    """Record a plan, dry by default. Returns an exit code."""
    warning = pov_recording_warning(not pov_demos, player_name, live)
    if warning:
        print(f"{warning} POV demos here: {', '.join(pov_demos)}", file=sys.stderr)

    if not plan.moments:
        print("\nNothing to record: the plan is empty.")
        return 0

    config = load_config()
    requests = clip_requests(plan, player_name, config, fallback_demo, names)

    if edit_only:
        return stitch_recorded(clips_on_disk(requests), player_name, config, aspect, edit)

    print(f"\nRecording {len(requests)} clip(s) {'live' if live else 'as a dry run'}")
    try:
        clips = record_clips(requests, config, live=live, resume=resume,
                             spectator_hud=spectator_hud, progress=print_progress)
    except ProductionError as error:
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


def editing_style(args: argparse.Namespace, defaults: EditingConfig | None = None) -> EditingConfig:
    """Flags given on the command line, else the config's [editing] defaults."""
    if defaults is None:
        try:
            defaults = load_config().editing
        except ConfigError:
            defaults = EditingConfig()
    return EditingConfig(
        music=args.music or defaults.music,
        music_start=defaults.music_start if args.music_start is None else args.music_start,
        transition=args.transition or defaults.transition,
        pro=args.pro or defaults.pro,
        target_seconds=defaults.target_seconds,
    )


def reel_target(args: argparse.Namespace, style: EditingConfig) -> float | None:
    """Seconds of best plays to keep: --best, else the config's reel length
    when footage is being made, so a recording is not every frag of a match."""
    if args.all:
        return None
    if args.best:
        return args.best
    making_footage = args.record or args.edit_only or (args.dry_run and args.stitch)
    return (style.target_seconds or None) if making_footage else None


def music_tempo(song: Path, config: Config) -> float | None:
    """The track's tempo for the preview, or None if it cannot be read."""
    try:
        return tempo_of(beat_times(load_samples(song, config.ffmpeg_path)))
    except (OSError, subprocess.CalledProcessError):
        return None


def print_progress(event: Progress) -> None:
    """One short line per step of a long job."""
    count = f"{event.done}/{event.total}" if event.total > 1 else ""
    print(f"  [{event.stage} {count}] {event.message}".replace(" ]", "]"), flush=True)


def stitch_recorded(
    clips: list[RecordedClip],
    player_name: str,
    config: Config,
    aspect: str | None = None,
    edit: EditOptions | None = None,
) -> int:
    """Edit (or just join) recorded clips into a reel and say where it went."""
    print(f"\n{'Editing' if edit else 'Stitching'} {len(clips)} clip(s)")
    try:
        result = produce_reel(clips, player_name, config, aspect, edit, progress=print_progress)
    except ProductionError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    if result.chapters:
        print(f"Chapters for the video description: {result.chapters}")
    if result.thumbnail:
        print(f"Thumbnail: {result.thumbnail}")
    print(f"Reel written ({result.shape}): {result.video}")
    return 0


def run_setup() -> int:
    """Find or fetch the tools recording needs. Returns an exit code."""
    try:
        config = load_config(ensure_config())
        tools = ensure_tools(config, print_progress)
    except (ConfigError, SetupError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"ffmpeg: {tools['ffmpeg']}")
    if "hlae" in tools:
        print(f"HLAE:   {tools['hlae']} ({tools.get('hlae_version') or 'installed'})")
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
        print(f"  [{check.mark:<4}] {check.name:<20} {check.detail}")

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
    """Run the command line. Ctrl+C stops cleanly: the game is closed and
    CS2 settings are put back on the way out, then exit code 130."""
    args = build_parser().parse_args(argv)
    use_utf8_output()
    try:
        return run(args)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 130


def default_run_log(args: argparse.Namespace) -> Path | None:
    """A log file for long jobs (recording, editing, setup) next to the cache."""
    if not (args.record or args.edit_only or args.setup):
        return None
    try:
        return run_log_path(load_config().resolved_cache_dir.parent / "logs")
    except (ConfigError, OSError):
        return None


def run_app(dev_url: str | None = None, debug: bool = False) -> int:
    from highlights.app.window import WindowError, open_window  # noqa: PLC0415 - pulls in pywebview

    try:
        open_window(dev_url=dev_url, debug=debug)
    except WindowError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


def run(args: argparse.Namespace) -> int:

    level = args.log_level or ("info" if args.verbose else "warning")
    configure_logging(level=level, log_file=args.log_file or default_run_log(args))

    if args.check:
        return run_check()
    if args.update_hlae:
        return run_update_hlae()
    if args.setup:
        return run_setup()
    if args.app or args.app_dev:
        return run_app(args.app_dev, debug=bool(args.app_dev))

    if not args.demos:
        print("Error: a demo path is required (or use --check)", file=sys.stderr)
        return 1

    cache = None if args.no_cache else open_cache()
    try:
        loaded = load_matches(args.demos, cache, clip_timing())
    except DemoError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    sources, matches = loaded.sources, loaded.matches
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

    style = editing_style(args)
    best = reel_target(args, style)
    options = PlanOptions(
        types=tuple(types), best_seconds=best, min_score=args.min_score, order=args.order,
        slowmo=args.slowmo or style.pro, victim_cams=args.victim_cams,
    )
    reel = plan_reel(loaded, player.steamid, options)
    for label in reel.missing_from:
        print(f"Note: {player.name} is not in {label}", file=sys.stderr)
    plan = reel.plan
    if best:
        print(f"\nBest {best:g}s, {args.order} order")
    print_clip_plan(plan, player.name)

    if args.dry_run or args.record or args.edit_only:
        pov = loaded.pov_demos()
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
                spectator_hud=args.spectator_hud,
                stitch=args.stitch and args.record,
                names=loaded.player_names(),
                aspect=args.aspect,
                edit=None if args.plain else EditOptions(
                    player_name=player.name,
                    captions=args.captions,
                    cards=args.cards,
                    transition=style.transition,
                    music=style.music,
                    maps=loaded.map_names(),
                    kills_shown=kills_in_plan(plan, loaded),
                    punch_ins=args.punch_ins or style.pro,
                    centred_captions=args.aspect == "vertical",
                    music_start=max(style.music_start, 0.0),
                    teaser=args.teaser,
                    flashes=args.flashes or style.pro,
                ),
            )
        except ConfigError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
