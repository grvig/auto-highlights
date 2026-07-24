"""Running ffmpeg.

Isolates the one place a subprocess is actually spawned, so everything above it
stays pure and testable. The runner callable is injectable; the default shells
out to ffmpeg, but tests pass a fake.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from highlights.stitcher.ffmpeg_command import ConcatCommand

logger = logging.getLogger(__name__)


class StitchError(Exception):
    """Raised when ffmpeg is missing or fails to produce the reel."""


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str


# A runner takes an argument list and returns a RunResult.
Runner = Callable[[list[str]], RunResult]


def _default_runner(args: list[str]) -> RunResult:
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
    )
    return RunResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def ffmpeg_available(ffmpeg: str) -> bool:
    """Whether the configured ffmpeg can be found.

    A bare command is looked up on PATH; an explicit path is checked directly.
    """
    if Path(ffmpeg).is_absolute() or ("/" in ffmpeg or "\\" in ffmpeg):
        return Path(ffmpeg).is_file()
    return shutil.which(ffmpeg) is not None


def run_concat(
    command: ConcatCommand,
    ffmpeg: str,
    runner: Runner | None = None,
) -> Path:
    """Run one concat command, returning the output path or raising StitchError."""
    if not ffmpeg_available(ffmpeg):
        raise StitchError(
            f"ffmpeg not found ('{ffmpeg}'). Install it and put it on PATH, or "
            "set the ffmpeg path in config.toml."
        )

    run = runner or _default_runner
    logger.info(
        "Stitching -> %s (%s)",
        command.output_path,
        "re-encode" if command.re_encoded else "stream copy",
    )
    logger.debug("ffmpeg args: %s", " ".join(command.args))

    result = run(command.args)
    if result.returncode != 0:
        # ffmpeg puts its real error on the last stderr lines.
        tail = "\n".join(result.stderr.strip().splitlines()[-5:])
        raise StitchError(
            f"ffmpeg failed (exit {result.returncode}) writing "
            f"{command.output_path.name}:\n{tail}"
        )

    if not command.output_path.exists():
        raise StitchError(
            f"ffmpeg reported success but {command.output_path} was not written"
        )
    logger.info("Wrote %s", command.output_path)
    return command.output_path
