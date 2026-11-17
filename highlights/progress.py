"""Progress reports and cancelling for long jobs.

Recording and editing a reel takes minutes. Each long step reports what it is
doing through a callback, so the command line can print it and the desktop
app can draw a progress bar; and each step checks a cancel token between
units of work, so a Cancel button stops cleanly between clips rather than
killing the game mid-write.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Progress:
    stage: str  # "record", "edit" or "export"
    done: int
    total: int
    message: str = ""

    @property
    def fraction(self) -> float:
        return 0.0 if self.total <= 0 else min(1.0, self.done / self.total)


ProgressFn = Callable[[Progress], None]


def ignore(_: Progress) -> None:
    """The progress callback used when nobody is listening."""


class Cancelled(Exception):
    """Raised by a step that noticed its job was cancelled."""


class CancelToken:
    """Set from one thread (the Cancel button), checked from the worker."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        """Raise Cancelled if the job has been cancelled."""
        if self._event.is_set():
            raise Cancelled("Cancelled")
