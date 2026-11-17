"""Running a long job (recording, editing) in the background.

The window must stay responsive while a reel renders for minutes, so the work
runs on a thread. The window polls a snapshot of the job's progress and can
ask it to cancel; the job stops at its next safe point.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from highlights.progress import CancelToken, Cancelled, Progress

logger = logging.getLogger(__name__)

# work(progress, cancel) -> result. Raising Cancelled ends the job as cancelled.
Work = Callable[[Callable[[Progress], None], CancelToken], Any]


@dataclass
class Job:
    id: str
    title: str
    state: str = "queued"  # queued, running, done, failed, cancelled
    stage: str = ""
    message: str = ""
    fraction: float = 0.0
    result: Any = None
    error: str | None = None
    cancel_token: CancelToken = field(default_factory=CancelToken)

    def snapshot(self) -> dict:
        return {
            "id": self.id, "title": self.title, "state": self.state, "stage": self.stage,
            "message": self.message, "fraction": round(self.fraction, 3),
            "result": self.result, "error": self.error,
        }


class JobRunner:
    """Starts jobs on background threads and keeps their latest state."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}

    def start(self, title: str, work: Work) -> str:
        job = Job(id=uuid.uuid4().hex[:12], title=title)
        with self._lock:
            self._jobs[job.id] = job
        thread = threading.Thread(target=self._run, args=(job, work), daemon=True, name=f"job-{job.id}")
        self._threads[job.id] = thread
        thread.start()
        return job.id

    def _run(self, job: Job, work: Work) -> None:
        def report(event: Progress) -> None:
            with self._lock:
                job.stage, job.message, job.fraction = event.stage, event.message, event.fraction

        with self._lock:
            job.state = "running"
        try:
            result = work(report, job.cancel_token)
        except Cancelled:
            outcome = {"state": "cancelled", "message": "Cancelled"}
        except Exception as error:  # a job must never take the window down with it
            logger.exception("Job %s failed", job.title)
            outcome = {"state": "failed", "error": str(error) or type(error).__name__}
        else:
            outcome = {"state": "done", "result": result, "fraction": 1.0}
        with self._lock:
            for key, value in outcome.items():
                setattr(job, key, value)

    def status(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot() if job else None

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None or job.state not in ("queued", "running"):
            return False
        job.cancel_token.cancel()
        return True

    def wait(self, job_id: str, timeout: float | None = None) -> dict | None:
        """Block until a job ends (for tests and the command line)."""
        thread = self._threads.get(job_id)
        if thread:
            thread.join(timeout)
        return self.status(job_id)
