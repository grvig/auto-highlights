"""Tests for the death detector."""

from highlights.engine.detectors.deaths import DeathDetector, describe_death
from highlights.engine.moments import HighlightType

from tests.factories import make_context, make_kill


def test_one_moment_per_player_death():
    kills = [
        make_kill(1000, "E1", "P"),  # P dies
        make_kill(1500, "P", "E2"),  # P kills, not a death
        make_kill(2000, "E3", "P"),  # P dies
    ]
    moments = DeathDetector().detect(make_context(kills), "P")
    assert len(moments) == 2
    assert all(m.highlight_type is HighlightType.DEATH for m in moments)
    assert [m.core_tick for m in moments] == [1000, 2000]


def test_no_deaths_yields_nothing():
    kills = [make_kill(1000, "P", "E1")]
    assert DeathDetector().detect(make_context(kills), "P") == []


def test_describe_death_names_the_killer():
    kill = make_kill(1, "E1", "P", weapon="awp", headshot=True)
    text = describe_death(kill)
    assert "att-E1" in text
    assert "awp" in text
    assert "headshot" in text


def test_death_moment_is_padded():
    kills = [make_kill(10_000, "E1", "P")]
    moment = DeathDetector().detect(make_context(kills), "P")[0]
    assert moment.start_tick == 10_000 - 3 * 64
    assert moment.end_tick == 10_000 + 2 * 64
