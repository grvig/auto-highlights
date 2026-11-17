"""Which kinds of highlight a reel is made of."""

from __future__ import annotations

from highlights.engine.moments import HighlightType

# The player's own plays: what a highlight reel shows by default. Deaths and
# utility are there for anyone who asks, but nobody clips their own deaths.
FRAG_TYPES = (HighlightType.KILL, HighlightType.MULTI_KILL, HighlightType.ACE, HighlightType.CLUTCH)

# Friendly spellings on top of the HighlightType values.
TYPE_ALIASES = {
    "multikill": HighlightType.MULTI_KILL,
    "kills": HighlightType.KILL,
    "deaths": HighlightType.DEATH,
    "clutches": HighlightType.CLUTCH,
    "aces": HighlightType.ACE,
    "util": HighlightType.UTILITY,
}


def parse_types(spec: str) -> list[HighlightType]:
    """Turn "frags", "all" or a comma-separated list into HighlightType values.

    Raises ValueError naming an unknown type.
    """
    if spec.strip().lower() == "all":
        return list(HighlightType)
    if spec.strip().lower() in ("", "frags"):
        return list(FRAG_TYPES)
    result: list[HighlightType] = []
    for token in spec.split(","):
        key = token.strip().lower()
        if not key:
            continue
        result.append(TYPE_ALIASES.get(key) or HighlightType(key))
    return result
