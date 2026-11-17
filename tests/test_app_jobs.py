"""Tests for background jobs."""

import threading

from highlights.app.jobs import JobRunner
from highlights.progress import Progress


def test_a_job_reports_progress_and_its_result():
    runner = JobRunner()

    def work(progress, cancel):
        progress(Progress("record", 1, 2, "Recording #001"))
        return {"video": "reel.mp4"}

    status = runner.wait(runner.start("Reel", work), timeout=5)
    assert status["state"] == "done"
    assert status["result"] == {"video": "reel.mp4"}
    assert status["fraction"] == 1.0 and status["message"] == "Recording #001"


def test_a_failing_job_keeps_its_error_message():
    runner = JobRunner()

    def work(progress, cancel):
        raise RuntimeError("CS2 never opened its console")

    status = runner.wait(runner.start("Reel", work), timeout=5)
    assert status["state"] == "failed" and status["error"] == "CS2 never opened its console"


def test_a_job_can_be_cancelled_while_it_runs():
    runner = JobRunner()
    started = threading.Event()

    def work(progress, cancel):
        started.set()
        while True:
            cancel.check()
            threading.Event().wait(0.01)

    job_id = runner.start("Reel", work)
    started.wait(5)
    assert runner.cancel(job_id)
    assert runner.wait(job_id, timeout=5)["state"] == "cancelled"
    assert not runner.cancel(job_id)  # already over


def test_unknown_jobs_have_no_status():
    assert JobRunner().status("nope") is None
