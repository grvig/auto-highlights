"""What the app window can ask for.

Every public method takes and returns JSON-friendly values and never raises:
problems come back as {"error": "..."} for the window to show. Loaded demos
and the last plan are kept between calls, so planning after picking a player
does not parse the demos again.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from highlights.app.demos import default_folders, find_demos
from highlights.app.jobs import JobRunner
from highlights.app.serialize import match_summary, plan_view, player_table
from highlights.app.settings import SettingsError, apply_changes
from highlights.appdirs import config_location
from highlights.config import Config, ConfigError, load_config
from highlights.editor.reel import EditOptions
from highlights.engine.clip_plan import ClipPlan
from highlights.engine.demo_source import DemoError
from highlights.pipeline.planning import (
    Matches,
    PlanOptions,
    clip_timing,
    load_matches,
    open_cache,
    plan_reel,
)
from highlights.pipeline.production import clip_requests, produce_reel, record_clips
from highlights.pipeline.types import parse_types
from highlights.progress import Progress
from highlights.steam.account import signed_in_account
from highlights.steam.locate import find_steam_root

logger = logging.getLogger(__name__)


def _error(message: str) -> dict:
    return {"error": message}


class AppApi:
    def __init__(
        self,
        config_loader: Callable[[], Config] = load_config,
        runner: JobRunner | None = None,
        you: Callable[[], str | None] | None = None,
        config_path: Path | None = None,
    ) -> None:
        self._load_config = config_loader
        self.config_path = config_path or config_location()
        self.jobs = runner or JobRunner()
        self._you = you or _signed_in_steamid
        self._loaded: tuple[tuple[str, ...], Matches] | None = None
        self._plan: ClipPlan | None = None
        self._planned_for: tuple[tuple[str, ...], str] | None = None

    def _config(self) -> Config | None:
        try:
            return self._load_config()
        except ConfigError as error:
            logger.warning("No usable config: %s", error)
            return None

    # --- settings ----------------------------------------------------------

    def settings(self) -> dict:
        """The settings the app shows, with where its files go."""
        config = self._config()
        if config is None:
            return {"configured": False}
        return {
            "configured": True,
            "output_dir": str(config.output_dir),
            "clips_dir": str(config.clips_dir),
            "aspect": config.recording.aspect,
            "hud": config.recording.hud,
            "recorder": config.recording.recorder,
            "music": str(config.editing.music) if config.editing.music else None,
            "music_start": config.editing.music_start,
            "transition": config.editing.transition,
            "target_seconds": config.editing.target_seconds,
        }

    def save_settings(self, changes: dict) -> dict:
        """Apply "section.key": value changes and return the new settings."""
        before = self.config_path.read_bytes() if self.config_path.is_file() else None
        try:
            apply_changes(self.config_path, changes)
            self._load_config().validate()
        except (SettingsError, ConfigError, OSError) as error:
            # a value the app rejects must not stay behind in the file
            if before is None:
                self.config_path.unlink(missing_ok=True)
            else:
                self.config_path.write_bytes(before)
            return _error(str(error))
        return self.settings()

    # --- choosing demos and a player ---------------------------------------

    def find_demos(self) -> dict:
        config = self._config()
        return {"demos": find_demos(default_folders(config.cs2_root if config else None))}

    def analyze(self, paths: list[str]) -> dict:
        """Parse the chosen demos (cached) and list their players."""
        if not paths:
            return _error("Pick at least one demo.")
        try:
            loaded = self._matches(paths)
        except DemoError as error:
            return _error(str(error))
        return {"matches": match_summary(loaded), "players": player_table(loaded, self._you())}

    def _matches(self, paths: list[str]) -> Matches:
        key = tuple(str(Path(p)) for p in paths)
        if self._loaded is None or self._loaded[0] != key:
            config = self._config()
            loaded = load_matches(key, open_cache(config) if config else None, clip_timing(config))
            self._loaded = (key, loaded)
        return self._loaded[1]

    # --- planning ----------------------------------------------------------

    def plan(self, paths: list[str], steamid: str, options: dict | None = None) -> dict:
        """The plays a reel would show, with the same defaults as the CLI."""
        options = options or {}
        try:
            loaded = self._matches(paths)
            config = self._config()
            target = options.get("seconds", config.editing.target_seconds if config else 120)
            plan_options = PlanOptions(
                types=tuple(parse_types(options.get("types", "frags"))),
                best_seconds=None if options.get("all") else (target or None),
                order=options.get("order", "montage"),
                victim_cams=bool(options.get("victim_cams", False)),
                slowmo=bool(options.get("slowmo", False)),
            )
            reel = plan_reel(loaded, steamid, plan_options)
        except (DemoError, ValueError) as error:
            return _error(str(error))
        self._plan = reel.plan
        self._planned_for = (tuple(paths), steamid)
        return {**plan_view(reel.plan), "missing_from": reel.missing_from}

    # --- rendering ---------------------------------------------------------

    def render(self, paths: list[str], steamid: str, options: dict | None = None) -> dict:
        """Record and produce the planned reel in the background. Returns a job id.

        Uses the plan from the last plan() call for these demos and player,
        so the reel is exactly what the window showed.
        """
        options = options or {}
        if self._plan is None or self._planned_for != (tuple(paths), steamid):
            planned = self.plan(paths, steamid, options)
            if "error" in planned:
                return planned
        config = self._config()
        if config is None:
            return _error("Set up the app first: no config was found.")
        loaded, plan = self._matches(paths), self._plan
        if not plan.moments:
            return _error("No plays to record for this player.")
        player = loaded.player_names().get(steamid, steamid)
        edit = _edit_options(options, player, loaded)

        def work(report, cancel):
            progress = overall(report)
            requests = clip_requests(plan, player, config, Path(paths[0]), loaded.player_names())
            clips = record_clips(requests, config, live=not options.get("dry_run"),
                                 resume=bool(options.get("resume")), progress=progress, cancel=cancel)
            cancel.check()
            recorded = [c for c in clips if c.succeeded]
            if options.get("dry_run"):
                return {"recorded": len(recorded), "failed": len(clips) - len(recorded)}
            result = produce_reel(clips, player, config, options.get("aspect"), edit,
                                  progress=progress, cancel=cancel)
            return {
                "video": str(result.video), "shape": result.shape,
                "chapters": str(result.chapters) if result.chapters else None,
                "thumbnail": str(result.thumbnail) if result.thumbnail else None,
                "recorded": len(recorded), "failed": len(clips) - len(recorded),
            }

        return {"job": self.jobs.start(f"{player} reel", work)}

    def job(self, job_id: str) -> dict:
        return self.jobs.status(job_id) or _error("No such job.")

    def cancel(self, job_id: str) -> dict:
        return {"cancelled": self.jobs.cancel(job_id)}


def _edit_options(options: dict, player: str, loaded: Matches) -> EditOptions | None:
    """Plain hard cuts unless the window asked for extras."""
    if options.get("plain"):
        return None
    music = options.get("music")
    return EditOptions(
        player_name=player,
        captions=bool(options.get("captions")),
        cards=bool(options.get("cards")),
        transition=options.get("transition", "cut"),
        music=Path(music) if music else None,
        maps=loaded.map_names(),
    )


# How much of the overall bar each stage fills: recording is most of the wait.
STAGE_SPANS = {"record": (0.0, 0.8), "edit": (0.8, 0.95), "export": (0.95, 1.0)}


def overall(report: Callable[[Progress], None]) -> Callable[[Progress], None]:
    """Turn per-stage progress into one bar from 0 to 1 across all stages."""
    def forward(event: Progress) -> None:
        start, end = STAGE_SPANS.get(event.stage, (0.0, 1.0))
        done = start + (end - start) * event.fraction
        report(Progress(event.stage, round(done * 1000), 1000, event.message))
    return forward


def _signed_in_steamid() -> str | None:
    root = find_steam_root()
    account = signed_in_account(root) if root else None
    return account.steamid if account else None
