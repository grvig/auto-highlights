"""Tests for the utility-damage detector."""

from highlights.engine.detectors.utility_damage import UtilityDamageDetector
from highlights.engine.moments import HighlightType

from tests.factories import make_context, make_damage, make_round


def context(damages):
    return make_context(
        kills=[],
        rounds=[make_round(1, start=0, end=100_000), make_round(2, start=100_000, end=200_000)],
        damages=damages,
    )


def test_he_damage_over_threshold_is_a_moment():
    damages = [
        make_damage(5000, "P", "E1", weapon="hegrenade", damage=30),
        make_damage(5010, "P", "E2", weapon="hegrenade", damage=25),
    ]
    moments = UtilityDamageDetector().detect(context(damages), "P")
    assert len(moments) == 1
    assert moments[0].highlight_type is HighlightType.UTILITY
    assert "HE grenade dealt 55 damage" == moments[0].description


def test_below_threshold_is_ignored():
    damages = [make_damage(5000, "P", "E1", weapon="hegrenade", damage=20)]
    assert UtilityDamageDetector().detect(context(damages), "P") == []


def test_he_and_fire_are_separate_moments():
    damages = [
        make_damage(5000, "P", "E1", weapon="hegrenade", damage=50),
        make_damage(6000, "P", "E1", weapon="inferno", damage=45),
    ]
    moments = UtilityDamageDetector().detect(context(damages), "P")
    assert len(moments) == 2
    labels = {m.description.split(" dealt")[0] for m in moments}
    assert labels == {"HE grenade", "Molotov"}


def test_fire_moment_spans_the_burn():
    damages = [
        make_damage(6000, "P", "E1", weapon="inferno", damage=20),
        make_damage(6300, "P", "E1", weapon="inferno", damage=25),
    ]
    moment = UtilityDamageDetector().detect(context(damages), "P")[0]
    assert moment.core_tick == 6000
    assert moment.start_tick == 6000 - 3 * 64
    assert moment.end_tick == 6300 + 2 * 64


def test_only_the_chosen_players_utility_counts():
    damages = [
        make_damage(5000, "OTHER", "E1", weapon="hegrenade", damage=80),
        make_damage(5000, "P", "E1", weapon="hegrenade", damage=15),
    ]
    assert UtilityDamageDetector().detect(context(damages), "P") == []
