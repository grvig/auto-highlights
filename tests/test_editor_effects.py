"""Tests for punch-in and flash effects."""

import math

from highlights.editor.effects import effect_filters, flash_filter, punch_in_filter


def test_punch_in_zooms_toward_the_centre_at_each_time():
    chain = punch_in_filter([1.5, 3.25], 1440, 1080)
    assert chain.startswith("zoompan=z='1+")
    assert "(it-1.500)" in chain and "(it-3.250)" in chain
    assert "x='iw/2-(iw/zoom/2)'" in chain and "s=1440x1080:fps=60" in chain


def test_flash_brightens_per_frame():
    chain = flash_filter([2.0])
    assert chain.startswith("eq=brightness='") and chain.endswith(":eval=frame")
    assert "(t-2.000)" in chain


def test_bump_is_strong_at_the_kill_and_gone_soon_after():
    from highlights.editor.effects import FLASH_WIDTH

    at_kill = math.exp(0)
    later = math.exp(-((0.2) / FLASH_WIDTH) ** 2)
    assert at_kill == 1.0 and later < 0.001


def test_no_effects_means_no_filters():
    assert effect_filters([], [], 1440, 1080) == []
    assert len(effect_filters([1.0], [1.0, 2.0], 1440, 1080)) == 2
