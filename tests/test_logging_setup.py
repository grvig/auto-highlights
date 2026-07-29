"""Tests for logging configuration."""

import logging

import pytest

from highlights.logging_setup import configure_logging, resolve_level


@pytest.fixture(autouse=True)
def _restore_logging():
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in saved:
        root.addHandler(handler)
    root.setLevel(saved_level)


def test_resolve_level_maps_names():
    assert resolve_level("debug") == logging.DEBUG
    assert resolve_level("INFO") == logging.INFO
    assert resolve_level("nonsense") == logging.WARNING


def test_console_only_sets_a_single_handler():
    configure_logging(level="info")
    handlers = logging.getLogger().handlers
    assert len(handlers) == 1
    assert handlers[0].level == logging.INFO


def test_repeated_calls_do_not_stack_handlers():
    configure_logging(level="info")
    configure_logging(level="warning")
    assert len(logging.getLogger().handlers) == 1


def test_log_file_captures_debug_even_when_console_is_quiet(tmp_path):
    log_file = tmp_path / "logs" / "run.log"
    configure_logging(level="warning", log_file=log_file)

    logging.getLogger("highlights.test").debug("a detailed debug line")

    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8")
    assert "a detailed debug line" in contents


def test_file_handler_is_added_alongside_console(tmp_path):
    configure_logging(level="error", log_file=tmp_path / "run.log")
    handlers = logging.getLogger().handlers
    assert len(handlers) == 2
    levels = {type(h).__name__: h.level for h in handlers}
    assert levels["FileHandler"] == logging.DEBUG


def test_root_passes_through_lowest_level(tmp_path):
    configure_logging(level="error", log_file=tmp_path / "run.log")
    # File wants DEBUG, so the root must not filter above DEBUG.
    assert logging.getLogger().level == logging.DEBUG
