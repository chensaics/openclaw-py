"""Pytest configuration — session-level setup shared across all tests."""

from __future__ import annotations

import os


def pytest_configure(config: object) -> None:
    """Disable ANSI color output so CLI help-text assertions work in any environment.

    typer/rich detects terminal capabilities via TERM and NO_COLOR.
    Without this, CI runners with TERM=xterm emit escape codes that break
    string-contains assertions like ``assert '--url' in result.stdout``.
    """
    os.environ["NO_COLOR"] = "1"
    os.environ["TERM"] = "dumb"
