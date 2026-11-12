"""Environment readiness checks.

A quick pre-run report: is the config sane, is CS2 where it should be, is
ffmpeg reachable, can we write clips and reels. Deliberately local and
non-destructive — it launches nothing and opens no network connections, so it
is safe to run any time. Whether the game answers on its console is not
checked here, because that means launching it; recording verifies it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from highlights.config import Config, ConfigError
from highlights.recorder.hlae import find_hlae
from highlights.stitcher.runner import ffmpeg_available


@dataclass(frozen=True)
class Check:
    """One readiness check outcome."""

    name: str
    ok: bool
    detail: str


def _writable(directory: Path) -> tuple[bool, str]:
    """Whether a directory exists (or can be made) and accepts a write."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as error:
        return False, f"{directory} ({error})"
    return True, str(directory)


def run_preflight(config: Config) -> list[Check]:
    """Run every readiness check and return their outcomes in report order."""
    checks: list[Check] = []

    try:
        config.validate()
        checks.append(Check("config values", True, "all values in range"))
    except ConfigError as error:
        first = str(error).splitlines()
        checks.append(Check("config values", False, first[-1].strip()))

    exe = config.cs2_executable
    if exe is None:
        checks.append(Check("CS2 install", False, "not found - set cs2_root in config.toml"))
    else:
        source = " (auto-detected)" if config.cs2_root_detected else ""
        checks.append(Check("CS2 install", exe.is_file(), f"{exe}{source}"))

    checks.append(
        Check("ffmpeg", ffmpeg_available(config.ffmpeg_path), config.ffmpeg_path)
    )

    if config.recording.recorder == "hlae":
        hlae_dir = find_hlae(config.recording.hlae_path)
        detail = str(hlae_dir) if hlae_dir else "not found - set paths.hlae or reinstall"
        checks.append(Check("HLAE", hlae_dir is not None, detail))

    clips_ok, clips_detail = _writable(config.clips_dir)
    checks.append(Check("clips dir writable", clips_ok, clips_detail))

    output_ok, output_detail = _writable(config.output_dir)
    checks.append(Check("output dir writable", output_ok, output_detail))

    cache_ok, cache_detail = _writable(config.resolved_cache_dir)
    checks.append(Check("cache dir writable", cache_ok, cache_detail))

    return checks


def all_passed(checks: list[Check]) -> bool:
    return all(check.ok for check in checks)
