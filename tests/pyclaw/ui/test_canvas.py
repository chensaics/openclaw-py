"""Tests for canvas host -- file resolution, live-reload injection."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pyclaw.canvas.handler import (
    A2UI_PATH,
    CANVAS_HOST_PATH,
    CANVAS_WS_PATH,
    DEFAULT_INDEX_HTML,
    guess_content_type,
    inject_canvas_live_reload,
    resolve_file_within_root,
)


class TestResolveFileWithinRoot:
    def test_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "test.html").write_text("<html></html>")
            result = resolve_file_within_root(p, "test.html")
            assert result is not None
            assert result.name == "test.html"

    def test_index_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / "index.html").write_text("<html></html>")
            result = resolve_file_within_root(p, "")
            assert result is not None
            assert result.name == "index.html"

    def test_subdirectory(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            sub = p / "assets"
            sub.mkdir()
            (sub / "style.css").write_text("body {}")
            result = resolve_file_within_root(p, "assets/style.css")
            assert result is not None
            assert result.name == "style.css"

    def test_directory_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            result = resolve_file_within_root(Path(td), "../../../etc/passwd")
            assert result is None

    def test_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as td:
            result = resolve_file_within_root(Path(td), "missing.txt")
            assert result is None


class TestInjectCanvasLiveReload:
    def test_inject_into_head(self):
        html = "<html><head></head><body></body></html>"
        result = inject_canvas_live_reload(html)
        assert "pyclawSendUserAction" in result
        assert "__pyclaw__/ws" in result

    def test_inject_into_body(self):
        html = "<html><body>Content</body></html>"
        result = inject_canvas_live_reload(html)
        assert "pyclawSendUserAction" in result

    def test_inject_no_markers(self):
        html = "<html>plain</html>"
        result = inject_canvas_live_reload(html)
        assert "pyclawSendUserAction" in result


class TestGuessContentType:
    def test_html(self):
        assert "html" in guess_content_type(Path("index.html"))

    def test_js(self):
        ct = guess_content_type(Path("app.js"))
        assert "javascript" in ct

    def test_css(self):
        ct = guess_content_type(Path("style.css"))
        assert "css" in ct

    def test_unknown(self):
        ct = guess_content_type(Path("file.xyz123"))
        assert ct == "application/octet-stream"


class TestConstants:
    def test_paths(self):
        assert A2UI_PATH == "/__pyclaw__/a2ui"
        assert CANVAS_HOST_PATH == "/__pyclaw__/canvas"
        assert CANVAS_WS_PATH == "/__pyclaw__/ws"

    def test_default_index(self):
        assert "pyclaw Canvas" in DEFAULT_INDEX_HTML
