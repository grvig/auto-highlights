"""Keeps the codebase free of unused imports and undefined names."""

import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "highlights"


def test_pyflakes_finds_nothing():
    pytest.importorskip("pyflakes")
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", str(PACKAGE)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
