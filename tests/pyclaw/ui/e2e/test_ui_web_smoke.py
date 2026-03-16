from __future__ import annotations

import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import closing

import pytest


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_http_ready(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:  # noqa: S310
                status = int(getattr(resp, "status", 200))
                if 200 <= status < 300:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise TimeoutError(f"UI web server not ready: {url}")


def test_ui_web_smoke() -> None:
    """Opt-in real smoke: boot web UI and open it in Playwright."""
    if os.environ.get("PYCLAW_RUN_UI_E2E") != "true":
        pytest.skip("Set PYCLAW_RUN_UI_E2E=true to run web UI smoke E2E.")
    sync_api = pytest.importorskip("playwright.sync_api")

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(  # noqa: S603
        ["pyclaw", "ui", "--web", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_http_ready(url, timeout_s=45.0)
        with sync_api.sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_selector("flt-glass-pane, flt-scene-host, canvas", timeout=45000)
            title = page.title()
            assert isinstance(title, str)
            assert len(title) > 0
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
