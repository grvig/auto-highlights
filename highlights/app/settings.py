"""Reading and changing settings from the app, keeping config.toml readable.

The config file is commented so people can edit it by hand, and a TOML writer
would drop every comment. Values are changed in place instead: an existing
key keeps its line and comment, a new key goes at the end of its section, and
a missing section is added at the end of the file.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

# What the app may change, as (section, key) -> type.
EDITABLE = {
    ("paths", "output_dir"): str,
    ("paths", "clips_dir"): str,
    ("recording", "aspect"): str,
    ("recording", "hud"): str,
    ("recording", "recorder"): str,
    ("editing", "music"): str,
    ("editing", "music_start"): float,
    ("editing", "transition"): str,
    ("editing", "target_seconds"): float,
}


class SettingsError(ValueError):
    """Raised for a setting the app may not change or a value of the wrong kind."""


def toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(float(value)) if isinstance(value, float) else str(value)
    text = str(value).replace("\\", "/")  # paths: forward slashes need no escaping
    return '"' + text.replace('"', '\\"') + '"'


def set_value(text: str, section: str, key: str, value: object) -> str:
    """The config text with section.key set to value, comments untouched."""
    line = f"{key} = {toml_value(value)}"
    header = re.search(rf"^\[{re.escape(section)}\]\s*$", text, re.MULTILINE)
    if header is None:
        return text.rstrip("\n") + f"\n\n[{section}]\n{line}\n"
    body_start = header.end() + 1
    next_header = re.search(r"^\[", text[body_start:], re.MULTILINE)
    body_end = body_start + next_header.start() if next_header else len(text)
    body = text[body_start:body_end]
    existing = re.search(rf"^{re.escape(key)}\s*=.*$", body, re.MULTILINE)
    if existing:
        body = body[:existing.start()] + line + body[existing.end():]
    else:
        trimmed = body.rstrip("\n")
        body = (trimmed + "\n" if trimmed else "") + line + "\n" + ("\n" if next_header else "")
    return text[:body_start] + body + text[body_end:]


def apply_changes(path: Path, changes: dict[str, object]) -> None:
    """Write "section.key": value changes into the config file.

    Every change is checked first and the result must still parse, so a bad
    change leaves the file exactly as it was.
    """
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for dotted, value in changes.items():
        section, _, key = dotted.partition(".")
        kind = EDITABLE.get((section, key))
        if kind is None:
            raise SettingsError(f"{dotted} cannot be changed from the app")
        try:
            value = kind(value)
        except (TypeError, ValueError) as error:
            raise SettingsError(f"{dotted} must be a {kind.__name__}") from error
        text = set_value(text, section, key, value)
    tomllib.loads(text)  # never write a file the app cannot read back
    path.write_text(text, encoding="utf-8", newline="\n")
