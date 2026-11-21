"""Plain, JSON-friendly views of matches, players and plans for the window."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from highlights.engine.clip_plan import ClipPlan
from highlights.engine.describe import pretty_map
from highlights.engine.models import deaths_of_player, kills_by_player
from highlights.engine.moments import Moment
from highlights.pipeline.planning import Matches


def match_summary(loaded: Matches) -> list[dict]:
    """One entry per demo: map, kind, rounds and where it lives."""
    return [
        {
            "path": str(source.path),
            "file": source.path.name,
            "map": pretty_map(source.info.map_name),
            "gotv": source.info.is_gotv,
            "rounds": len(match.context.rounds),
        }
        for source, match in zip(loaded.sources, loaded.matches)
    ]


def player_table(loaded: Matches, you: str | None = None) -> list[dict]:
    """Every player across the demos with kills and deaths, best first.

    `you` is the signed-in SteamID, so the window can preselect the player.
    """
    seen: dict[str, dict] = {}
    for match in loaded.matches:
        for player in match.players:
            row = seen.setdefault(player.steamid, {
                "steamid": player.steamid, "name": player.name, "matches": 0,
                "kills": 0, "deaths": 0, "you": player.steamid == you,
            })
            row["matches"] += 1
            row["kills"] += len(kills_by_player(match.context.kills, player.steamid))
            row["deaths"] += len(deaths_of_player(match.context.kills, player.steamid))
    return sorted(seen.values(), key=lambda r: (not r["you"], -r["kills"], r["name"].lower()))


def moment_view(moment: Moment, number: int) -> dict:
    return {
        "number": number,
        "round": moment.round_number,
        "time": moment.timestamp,
        "type": str(moment.highlight_type),
        "description": moment.description,
        "score": moment.score,
        "tags": list(moment.tags),
        "seconds": round(moment.duration_seconds, 1),
        "demo": Path(moment.source_demo).name if moment.source_demo else None,
    }


def match_label(source) -> str:
    """"Cache 1 Jul": the map and the day the demo was saved."""
    try:
        day = datetime.fromtimestamp(Path(source.path).stat().st_mtime)
        when = f" {day.day} {day:%b}"
    except OSError:
        when = ""
    return f"{pretty_map(source.info.map_name)}{when}"


def plan_view(plan: ClipPlan, loaded: Matches | None = None) -> dict:
    labels = {source.path.name: match_label(source) for source in loaded.sources} if loaded else {}
    moments = [moment_view(m, n) for n, m in enumerate(plan.moments, start=1)]
    for moment in moments:
        moment["match"] = labels.get(moment["demo"]) if moment["demo"] else None
    return {
        "moments": moments,
        "count": len(moments),
        "seconds": round(sum(m["seconds"] for m in moments), 1),
    }
