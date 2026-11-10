"""A small reader for Valve's KeyValues text format (.vdf).

Steam keeps its library list, signed-in accounts and CS2's video settings in
this format: quoted keys mapped either to quoted strings or to nested braces.
Only reading is needed, so this is a tokenizer plus a recursive parser.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Union

VdfValue = Union[str, "VdfDict"]
VdfDict = dict[str, VdfValue]

_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}


class VdfError(ValueError):
    """Raised when text is not valid KeyValues."""


def _tokens(text: str) -> Iterator[str]:
    """Yield braces and string tokens, skipping whitespace and // comments."""
    i, length = 0, len(text)
    while i < length:
        char = text[i]
        if char.isspace():
            i += 1
        elif text.startswith("//", i):
            newline = text.find("\n", i)
            i = length if newline == -1 else newline + 1
        elif char in "{}":
            yield char
            i += 1
        elif char == '"':
            i, value = _quoted(text, i + 1)
            yield '"' + value
        else:
            start = i
            while i < length and not text[i].isspace() and text[i] not in '{}"':
                i += 1
            yield '"' + text[start:i]


def _quoted(text: str, i: int) -> tuple[int, str]:
    """Read a quoted string starting after its opening quote."""
    out: list[str] = []
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            out.append(_ESCAPES.get(text[i + 1], text[i + 1]))
            i += 2
        elif char == '"':
            return i + 1, "".join(out)
        else:
            out.append(char)
            i += 1
    raise VdfError("Unterminated quoted string")


def _parse_block(tokens: Iterator[str], nested: bool) -> VdfDict:
    result: VdfDict = {}
    for token in tokens:
        if token == "}":
            if not nested:
                raise VdfError("Unexpected closing brace")
            return result
        if token == "{":
            raise VdfError("Opening brace without a key")
        key = token[1:]
        value = next(tokens, None)
        if value is None:
            raise VdfError(f"Key {key!r} has no value")
        result[key] = _parse_block(tokens, nested=True) if value == "{" else value[1:]
    if nested:
        raise VdfError("Missing closing brace")
    return result


def loads(text: str) -> VdfDict:
    """Parse KeyValues text into nested dicts of strings."""
    return _parse_block(_tokens(text), nested=False)


def get_ci(mapping: VdfDict, key: str) -> VdfValue | None:
    """Case-insensitive lookup — Valve files are not consistent about case."""
    wanted = key.lower()
    for existing, value in mapping.items():
        if existing.lower() == wanted:
            return value
    return None
