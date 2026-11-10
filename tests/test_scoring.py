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
