"""Tests for sandbox boundary enforcement."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from pyclaw.security.sandbox import (
    ConfigIncludeLoader,
    WorkspaceBoundary,
    is_path_within,
    resolve_config_include,
    sanitize_path,
)


class TestSanitizePath:
    def test_traversal(self) -> None:
        assert "../etc/passwd" not in sanitize_path("../../../etc/passwd")
        assert ".." not in sanitize_path("foo/../../../bar")

    def test_tilde_expansion(self) -> None:
        result = sanitize_path("~/secret/file")
        assert not result.startswith("~")

    def test_variable_interpolation(self) -> None:
        result = sanitize_path("${HOME}/secret")
        assert "${" not in result

    def test_command_substitution(self) -> None:
        result = sanitize_path("$(whoami)/dir")
        assert "$(" not in result

    def test_null_bytes(self) -> None:
        result = sanitize_path("file\x00name")
        assert "\x00" not in result

    def test_double_slash(self) -> None:
        result = sanitize_path("path//to///file")
        assert "//" not in result

    def test_normal_path(self) -> None:
        assert sanitize_path("src/main.py") == "src/main.py"
        assert sanitize_path("docs/reference/plan.md") == "docs/reference/plan.md"

    def test_backslash_normalization(self) -> None:
        result = sanitize_path("path\\to\\file")
        assert "\\" not in result


class TestIsPathWithin:
    def test_within(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            inner = Path(tmpdir) / "subdir"
            inner.mkdir()
            assert is_path_within(inner, tmpdir) is True

    def test_same_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assert is_path_within(tmpdir, tmpdir) is True

    def test_outside(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assert is_path_within("/etc/passwd", tmpdir) is False


class TestWorkspaceBoundary:
    @pytest.fixture
    def workspace(self) -> tuple[WorkspaceBoundary, Path]:
        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "src").mkdir()
        (tmpdir / "src" / "main.py").write_text("print('hi')")
        boundary = WorkspaceBoundary(tmpdir)
        return boundary, tmpdir

    def test_check_within(self, workspace: tuple[WorkspaceBoundary, Path]) -> None:
        boundary, root = workspace
        assert boundary.check(root / "src" / "main.py") is True

    def test_check_outside(self, workspace: tuple[WorkspaceBoundary, Path]) -> None:
        boundary, _ = workspace
        assert boundary.check("/etc/passwd") is False

    def test_resolve_valid(self, workspace: tuple[WorkspaceBoundary, Path]) -> None:
        boundary, root = workspace
        result = boundary.resolve("src/main.py")
        assert result is not None
        assert result.name == "main.py"

    def test_resolve_traversal_sanitized(self, workspace: tuple[WorkspaceBoundary, Path]) -> None:
        boundary, root = workspace
        # After sanitization, "../../../etc/passwd" becomes "etc/passwd" — safe within workspace
        result = boundary.resolve("../../../etc/passwd")
        # The sanitized path resolves within workspace, but the file doesn't exist
        assert result is None or str(result).startswith(str(root.resolve()))

    def test_resolve_absolute_outside(self, workspace: tuple[WorkspaceBoundary, Path]) -> None:
        boundary, _ = workspace
        result = boundary.resolve("/etc/passwd")
        assert result is None

    def test_allowed_external(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            with tempfile.TemporaryDirectory() as external:
                boundary = WorkspaceBoundary(workspace, allowed_external=[external])
                assert boundary.check(Path(external) / "data.json") is True
                assert boundary.check("/other/path") is False


class TestConfigInclude:
    @pytest.fixture
    def config_dir(self) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "base.json").write_text("{}")
        (tmpdir / "sub").mkdir()
        (tmpdir / "sub" / "extra.json").write_text("{}")
        return tmpdir

    def test_resolve_valid_include(self, config_dir: Path) -> None:
        result = resolve_config_include("base.json", config_dir=config_dir)
        assert result is not None
        assert result.name == "base.json"

    def test_resolve_subdirectory(self, config_dir: Path) -> None:
        result = resolve_config_include("sub/extra.json", config_dir=config_dir)
        assert result is not None
        assert result.name == "extra.json"

    def test_reject_traversal(self, config_dir: Path) -> None:
        result = resolve_config_include("../../../etc/passwd", config_dir=config_dir)
        assert result is None

    def test_reject_nonexistent(self, config_dir: Path) -> None:
        result = resolve_config_include("nonexistent.json", config_dir=config_dir)
        assert result is None

    def test_depth_limit(self, config_dir: Path) -> None:
        result = resolve_config_include("base.json", config_dir=config_dir, depth=10)
        assert result is None

    def test_workspace_boundary(self, config_dir: Path) -> None:
        result = resolve_config_include(
            "base.json",
            config_dir=config_dir,
            workspace_root=config_dir,
        )
        assert result is not None


class TestConfigIncludeLoader:
    @pytest.fixture
    def loader_setup(self) -> tuple[ConfigIncludeLoader, Path]:
        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "a.json").write_text("{}")
        (tmpdir / "b.json").write_text("{}")
        loader = ConfigIncludeLoader(tmpdir)
        return loader, tmpdir

    def test_resolve_include(self, loader_setup: tuple[ConfigIncludeLoader, Path]) -> None:
        loader, _ = loader_setup
        result = loader.resolve_include("a.json")
        assert result is not None
        assert loader.loaded_count == 1

    def test_circular_detection(self, loader_setup: tuple[ConfigIncludeLoader, Path]) -> None:
        loader, _ = loader_setup
        loader.resolve_include("a.json")
        result = loader.resolve_include("a.json")
        assert result is None

    def test_max_files_limit(self, loader_setup: tuple[ConfigIncludeLoader, Path]) -> None:
        loader, tmpdir = loader_setup
        # Create many files
        for i in range(25):
            (tmpdir / f"f{i}.json").write_text("{}")

        count = 0
        for i in range(25):
            result = loader.resolve_include(f"f{i}.json")
            if result:
                count += 1

        assert count <= 20
