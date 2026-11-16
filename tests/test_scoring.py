"""Tests for moment scoring."""

from dataclasses import replace

from highlights.engine.moments import HighlightType, Moment
from highlights.engine.scoring import moment_kills, style_points, style_score

from tests.factories import make_kill


def moment(start, end, round_number=1, player="P", htype=HighlightType.MULTI_KILL):
    return Moment(
        round_number=round_number,
        highlight_type=htype,
        player_steamid=player,
        core_tick=end,
        start_tick=start,
        end_tick=end,
        description="x",
    )


def test_moment_kills_are_the_players_own_kills_in_its_window():
    kills = [
        make_kill(1000, "P", "a"),
        make_kill(1500, "OTHER", "b"),  # someone else's kill
        make_kill(1800, "P", "c"),
        make_kill(9000, "P", "d"),  # outside the window
        make_kill(1200, "P", "e", round_number=2),  # other round
    ]
    found = moment_kills(moment(900, 2000), kills)
    assert [k.victim_steamid for k in found] == ["a", "c"]


def test_style_points_add_up_per_kill():
    awp_noscope = replace(make_kill(1, "P", "x"), noscope=True, headshot=True)
    assert style_points(awp_noscope) == 3.5
    assert style_points(make_kill(1, "P", "y")) == 0.0


def test_style_score_sums_kills_and_lists_distinct_tags():
    kills = [
        replace(make_kill(1, "P", "a"), wallbang=True, headshot=True),
        replace(make_kill(2, "P", "b"), wallbang=True, through_smoke=True),
    ]
    points, tags = style_score(kills)
    assert points == 2.5 + 0.5 + 2.5 + 2.0
    assert tags == ("wallbang", "through smoke")  # headshot not called out


def test_no_kills_scores_nothing():
    assert style_score([]) == (0.0, ())


def test_fast_triple_scores_high_and_is_tagged():
    from highlights.engine.scoring import tempo_score

    # three kills 1s apart
    kills = [make_kill(1000, "P", "a"), make_kill(1064, "P", "b"), make_kill(1128, "P", "c")]
    points, tags = tempo_score(kills)
    assert points == 2.0 * 2 * 0.9
    assert tags == ("3 kills in 2.0s",)


def test_spread_out_triple_earns_no_tempo():
    from highlights.engine.scoring import tempo_score

    kills = [make_kill(t, "P", f"v{t}") for t in (1000, 1000 + 25 * 64, 1000 + 51 * 64)]
    assert tempo_score(kills) == (0.0, ())


def test_single_kill_has_no_tempo():
    from highlights.engine.scoring import tempo_score

    assert tempo_score([make_kill(1000, "P", "a")]) == (0.0, ())


def test_clutch_score_grows_with_opponents():
    from highlights.engine.scoring import clutch_score

    one = replace(moment(0, 100, htype=HighlightType.CLUTCH), opponents=1)
    three = replace(moment(0, 100, htype=HighlightType.CLUTCH), opponents=3)
    assert clutch_score(three)[0] > clutch_score(one)[0]
    assert clutch_score(three)[1] == ("1v3",)
    assert clutch_score(moment(0, 100)) == (0.0, ())


def test_clutch_detector_records_opponents():
    from highlights.engine.detectors.clutch import ClutchDetector
    from tests.test_detector_clutch import context

    assert ClutchDetector().detect(context(), "P")[0].opponents == 2


ROSTER = {"P": "ct", "T1": "ct", "E1": "t", "E2": "t", "E3": "t"}


def test_win_probability_matches_known_shapes():
    from highlights.engine.scoring import win_probability

    assert win_probability(1, 1) == 0.5
    assert win_probability(5, 5) == 0.5
    assert win_probability(1, 3) < 0.1
    assert win_probability(2, 1) > 0.8
    assert win_probability(0, 2) == 0.0
    assert win_probability(3, 0) == 1.0


def test_alive_counts_ignore_kills_after_this_one():
    from highlights.engine.scoring import alive_before

    kills = [make_kill(100, "E1", "T1"), make_kill(200, "P", "E1"), make_kill(300, "P", "E2")]
    assert alive_before(kills[1], kills, ROSTER) == (1, 3)  # T1 already down
    assert alive_before(kills[2], kills, ROSTER) == (1, 2)


def test_a_whole_clutch_dwarfs_a_cleanup_kill():
    from highlights.engine.scoring import impact_score

    # P alone wins a 1v3: from ~8% to a won round.
    clutch = [
        make_kill(100, "E1", "T1"),
        make_kill(200, "P", "E1"),
        make_kill(300, "P", "E2"),
        make_kill(400, "P", "E3"),
    ]
    clutch_points, _ = impact_score(clutch[1:], clutch, ROSTER)

    # Five alive against one: the round was already won.
    roster_5v1 = {"P": "ct", "A": "ct", "B": "ct", "C": "ct", "D": "ct", "E1": "t"}
    cleanup = [make_kill(200, "P", "E1")]
    cleanup_points, _ = impact_score(cleanup, cleanup, roster_5v1)

    assert clutch_points > 9.0
    assert cleanup_points < 0.5


def test_big_swings_are_tagged():
    from highlights.engine.scoring import impact_score

    roster = {"P": "ct", "E1": "t", "E2": "t"}
    kills = [make_kill(100, "P", "E1"), make_kill(200, "P", "E2")]  # 1v2 to win
    _, tags = impact_score(kills, kills, roster)
    assert tags == ("swung the round",)


def test_scored_plan_ranks_a_fast_ace_above_a_lone_kill():
    from highlights.engine.clip_plan import build_clip_plan
    from tests.factories import make_context, make_round

    roster = {"P": "ct", **{f"E{i}": "t" for i in range(1, 6)}}
    ace = [make_kill(10_000 + i * 64, "P", f"E{i}", round_number=1) for i in range(1, 6)]
    lone = [make_kill(50_000, "P", "E1", round_number=2)]
    rosters = {1: roster, 2: {"P": "ct", "T1": "ct", "E1": "t", "E2": "t"}}
    ctx = make_context(
        ace + lone,
        rounds=[make_round(1, 0, 40_000), make_round(2, 40_000, 90_000)],
        round_rosters=rosters,
    )
    plan = build_clip_plan(ctx, "P", [HighlightType.KILL, HighlightType.ACE])
    by_type = {m.highlight_type: m for m in plan.moments}
    assert by_type[HighlightType.ACE].score > by_type[HighlightType.KILL].score
    assert "5 kills in 4.0s" in by_type[HighlightType.ACE].tags
    assert "swung the round" in by_type[HighlightType.ACE].tags


def test_scoring_can_be_turned_off():
    from highlights.engine.clip_plan import build_clip_plan
    from tests.factories import make_context

    plan = build_clip_plan(make_context([make_kill(1000, "P", "x")]), "P", [HighlightType.KILL], score=False)
    assert plan.moments[0].score == 0.0


def test_a_death_clip_does_not_score_the_players_own_kills():
    from highlights.engine.clip_plan import build_clip_plan
    from tests.factories import make_context

    # P gets a quick double, then dies a second later: the death clip's window
    # contains the double, but those frags belong to the kill clip.
    kills = [
        make_kill(1000, "P", "E1"),
        make_kill(1040, "P", "E2"),
        make_kill(1100, "E3", "P"),
    ]
    plan = build_clip_plan(make_context(kills), "P", [HighlightType.KILL, HighlightType.DEATH])
    death = next(m for m in plan.moments if m.highlight_type is HighlightType.DEATH)
    assert death.score == 0.0
    assert death.tags == ()


def test_one_taps_score_highest_and_sprays_lose_points():
    from highlights.engine.models import Shot
    from highlights.engine.scoring import accuracy_score

    kills = [make_kill(1000, "P", "a"), make_kill(1200, "P", "b")]
    taps = [Shot(990, "P", "ak47"), Shot(1195, "P", "ak47")]
    spray = [Shot(900 + i * 5, "P", "ak47") for i in range(60)]
    assert accuracy_score(kills, taps, "P") == (4.5, ("one-taps",))
    assert accuracy_score(kills, taps + taps[:1] + [Shot(1100, "P", "ak47")], "P")[1] == ("clean",)
    points, tags = accuracy_score(kills, spray, "P")
    assert points < 0 and tags == ("sprayed",)


def test_knife_swings_grenades_and_other_players_do_not_count():
    from highlights.engine.models import Shot
    from highlights.engine.scoring import accuracy_score

    kills = [make_kill(1000, "P", "a")]
    noise = [Shot(950, "P", "knife_t"), Shot(960, "P", "hegrenade"), Shot(970, "Q", "ak47")] * 5
    assert accuracy_score(kills, noise + [Shot(999, "P", "deagle")], "P")[1] == ("one-taps",)
