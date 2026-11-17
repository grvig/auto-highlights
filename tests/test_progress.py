"""Tests for progress reports and cancel tokens."""

import threading

import pytest

from highlights.progress import CancelToken, Cancelled, Progress


def test_fraction_is_safe_and_capped():
    assert Progress("record", 1, 4).fraction == 0.25
    assert Progress("record", 0, 0).fraction == 0.0
    assert Progress("record", 5, 4).fraction == 1.0


def test_a_token_cancelled_on_another_thread_is_seen():
    token = CancelToken()
    threading.Thread(target=token.cancel).start()
    for _ in range(100):
        if token.cancelled:
            break
        threading.Event().wait(0.01)
    with pytest.raises(Cancelled):
        token.check()
