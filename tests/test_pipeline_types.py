"""Tests for choosing highlight types."""

import pytest

from highlights.engine.moments import HighlightType
from highlights.pipeline.types import FRAG_TYPES, parse_types


def test_frags_are_the_default():
    assert parse_types("") == list(FRAG_TYPES) == parse_types("frags")
    assert HighlightType.DEATH not in FRAG_TYPES


def test_aliases_and_values_mix():
    assert parse_types("aces, util,kill") == [HighlightType.ACE, HighlightType.UTILITY, HighlightType.KILL]


def test_unknown_types_are_rejected():
    with pytest.raises(ValueError):
        parse_types("kills,headshots")
