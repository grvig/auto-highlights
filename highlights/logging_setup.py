"""Logging configuration for the CLI.

The recorder logs every command it sends to CS2, which is exactly what
you want to keep when a live capture misbehaves. This centralises how those
logs are levelled and, optionally, written to a file so the console exchange
survives after the run.
"""

from __future__ import annotations

import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DATE_FORMAT = "%H:%M:%S"

LEVELS = ("debug", "info", "warning", "error")


def resolve_level(name: str) -> int:
    """Turn a level name into a logging constant, defaulting to WARNING."""
    return getattr(logging, name.upper(), logging.WARNING)


def configure_logging(level: str = "warning", log_file: Path | str | None = None) -> None:
    """Set up root logging for a CLI run.

    Console output goes to stderr at the chosen level. When a log file is
    given, everything at DEBUG and above is also written there — the verbose
    detail is kept on disk even when the console stays quiet, which is what
    makes a failed capture diagnosable after the fact.
    """
    root = logging.getLogger()
    # Start clean so repeated CLI invocations in one process do not stack
    # handlers (matters in tests and in a future GUI that calls this).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console_level = resolve_level(level)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(formatter)
    root.addHandler(console)

    lowest = console_level
    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        lowest = min(lowest, logging.DEBUG)
        logging.getLogger(__name__).info("Logging to %s", path)

    # The root must pass through the most detailed level any handler wants.
    root.setLevel(lowest)


# Run logs kept per long job; older ones are deleted beyond this many.
KEEP_RUN_LOGS = 20


def run_log_path(log_dir: Path, keep: int = KEEP_RUN_LOGS) -> Path:
    """A fresh timestamped log file for this run, pruning the oldest ones.

    Long jobs log every console command sent to CS2, which is what makes a
    failed recording diagnosable after the fact.
    """
    from datetime import datetime

    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    old = sorted(log_dir.glob("run_*.log"))
    for stale in old[: max(0, len(old) - (keep - 1))]:
        try:
            stale.unlink()
        except OSError:
            pass
    return log_dir / f"run_{datetime.now():%Y-%m-%d_%H%M%S}.log"
