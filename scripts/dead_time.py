"""How much dead time a planned reel's clips carry.

    python scripts/dead_time.py DEMO [DEMO ...] --player NAME [--seconds 120]

For every planned clip: seconds before the player's first shot or hit,
seconds after their last action, and the longest quiet stretch inside. Used
to tune clip timing against real demos rather than by feel.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from highlights.config import load_config  # noqa: E402
from highlights.engine.fights import fight_ticks  # noqa: E402
from highlights.pipeline.planning import (  # noqa: E402
    PlanOptions,
    clip_timing,
    load_matches,
    open_cache,
    plan_reel,
)

QUIET_SECONDS = 3.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Dead time in a planned reel")
    parser.add_argument("demos", nargs="+")
    parser.add_argument("--player", required=True)
    parser.add_argument("--seconds", type=float, default=120)
    args = parser.parse_args()

    config = load_config()
    loaded = load_matches(args.demos, open_cache(config), clip_timing(config))
    player = next(sid for sid, name in loaded.player_names().items() if name == args.player)
    plan = plan_reel(loaded, player, PlanOptions(best_seconds=args.seconds)).plan
    contexts = {m.context.demo_path: m.context for m in loaded.matches}

    rows = []
    for moment in plan.moments:
        ctx = contexts[Path(moment.source_demo)]
        rate = ctx.tickrate
        action = fight_ticks(ctx, player) + [k.tick for k in ctx.kills if k.attacker_steamid == player]
        for window in moment.windows:
            inside = sorted(t for t in action if window.start_tick <= t <= window.end_tick)
            if not inside:
                continue
            gaps = [b - a for a, b in zip(inside, inside[1:])] or [0]
            rows.append((moment.round_number, str(moment.highlight_type),
                         (window.end_tick - window.start_tick) / rate,
                         (inside[0] - window.start_tick) / rate,
                         (window.end_tick - inside[-1]) / rate, max(gaps) / rate))

    print(f"{'rnd':>3} {'type':11} {'len':>5} {'lead':>5} {'tail':>5} {'gap':>5}")
    for rnd, kind, length, lead, tail, gap in rows:
        print(f"{rnd:>3} {kind:11} {length:5.1f} {lead:5.1f} {tail:5.1f} {gap:5.1f}")
    total = sum(r[2] for r in rows) or 1
    lead = sum(r[3] for r in rows)
    tail = sum(r[4] for r in rows)
    quiet = sum(max(0, r[5] - QUIET_SECONDS) for r in rows)
    print(f"\n{len(rows)} clips, {total:.0f}s: before first action {lead:.0f}s ({lead / total:.0%}), "
          f"after last {tail:.0f}s ({tail / total:.0%}), "
          f"quiet stretches over {QUIET_SECONDS:g}s inside {quiet:.0f}s ({quiet / total:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
