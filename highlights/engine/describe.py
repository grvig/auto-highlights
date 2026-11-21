"""Short, readable names for demos: "Cache 13-11 W" instead of match730_0038...

The map comes from the demo's header; the score is counted from the round
results, from the player's side (teams swap sides at halftime and in
overtime, so the player's team is read at the end of every round). About two
seconds per demo, so answers are kept in a small file and reused.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

TEAM_SIDES = {2: "T", 3: "CT"}
_lock = threading.Lock()


def pretty_map(name: str) -> str:
    """de_cache -> Cache, cs_office -> Office, de_dust2 -> Dust2."""
    bare = name.split("/")[-1]
    for prefix in ("de_", "cs_", "ar_", "dz_"):
        if bare.startswith(prefix):
            bare = bare[len(prefix):]
            break
    return bare.replace("_", " ").title() if bare else name


def read_description(path: Path | str, steamid: str | None = None) -> dict:
    """Map, and the score from steamid's side when they played in it."""
    from demoparser2 import DemoParser  # noqa: PLC0415 - heavy; only when describing

    parser = DemoParser(str(path))
    header = parser.parse_header()
    found = {"map": pretty_map(str(header.get("map_name", ""))), "score": None, "result": None}
    rounds = parser.parse_event("round_end")
    if rounds is None or not len(rounds):
        return found
    ticks = [int(t) for t in rounds["tick"]]
    winners = list(rounds["winner"])
    if steamid:
        teams = parser.parse_ticks(["team_num"], players=[int(steamid)], ticks=ticks)
        if len(teams):
            side_at = dict(zip(teams["tick"], teams["team_num"]))
            won = sum(1 for tick, winner in zip(ticks, winners) if TEAM_SIDES.get(side_at.get(tick)) == winner)
            lost = sum(1 for winner in winners if winner in ("T", "CT")) - won
            found["score"] = [won, lost]
            found["result"] = "W" if won > lost else "L" if won < lost else "T"
    return found


class Descriptions:
    """Descriptions kept in a JSON file, keyed by file, size, time and player."""

    def __init__(self, store: Path, reader=read_description) -> None:
        self.store = Path(store)
        self._read = reader

    def _load(self) -> dict:
        try:
            return json.loads(self.store.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @staticmethod
    def key(path: Path, steamid: str | None) -> str:
        stat = path.stat()
        return f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}|{steamid or ''}"

    def describe(self, path: Path | str, steamid: str | None = None, readable: Path | None = None) -> dict:
        """The description of `path`; `readable` is the demo to read when
        `path` is a compressed download."""
        path = Path(path)
        key = self.key(path, steamid)
        with _lock:
            known = self._load().get(key)
        if known is not None:
            return known
        found = self._read(readable or path, steamid)
        with _lock:
            stored = self._load()
            stored[key] = found
            self.store.parent.mkdir(parents=True, exist_ok=True)
            self.store.write_text(json.dumps(stored, indent=0), encoding="utf-8")
        return found
