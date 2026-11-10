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
