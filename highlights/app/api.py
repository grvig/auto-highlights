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
from highlights.config import Config, ConfigError, load_config
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
from highlights.pipeline.types import parse_types
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
    ) -> None:
        self._load_config = config_loader
        self.jobs = runner or JobRunner()
        self._you = you or _signed_in_steamid
        self._loaded: tuple[tuple[str, ...], Matches] | None = None
        self._plan: ClipPlan | None = None

    def _config(self) -> Config | None:
        try:
            return self._load_config()
        except ConfigError as error:
            logger.warning("No usable config: %s", error)
            return None

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
        return {**plan_view(reel.plan), "missing_from": reel.missing_from}


def _signed_in_steamid() -> str | None:
    root = find_steam_root()
    account = signed_in_account(root) if root else None
    return account.steamid if account else None
