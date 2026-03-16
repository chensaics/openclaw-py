"""Tests for agent tools — file operations, exec, web, and registry."""

from pathlib import Path

import pytest

from pyclaw.agents.tools.exec_tool import ExecTool
from pyclaw.agents.tools.file_tools import EditTool, ReadTool, WriteTool
from pyclaw.agents.tools.registry import ToolRegistry, create_default_tools
from pyclaw.agents.tools.web_tools import _extract_text_from_html, _is_url_safe
from pyclaw.agents.types import AgentTool

# ---------- Registry ----------


def test_registry_basic():
    reg = ToolRegistry()
    assert len(reg) == 0

    tool = ReadTool()
    reg.register(tool)
    assert len(reg) == 1
    assert "read" in reg
    assert reg.get("read") is tool
    assert reg.get("nonexistent") is None
    assert reg.names() == ["read"]


def test_registry_register_all():
    reg = ToolRegistry()
    tools = [ReadTool(), WriteTool(), EditTool()]
    reg.register_all(tools)
    assert len(reg) == 3
    assert set(reg.names()) == {"read", "write", "edit"}


def test_create_default_tools():
    reg = create_default_tools()
    assert "read" in reg
    assert "write" in reg
    assert "edit" in reg
    assert "exec" in reg
    assert "web_fetch" in reg
    assert "web_search" in reg


def test_create_default_tools_disabled():
    reg = create_default_tools(enable_exec=False, enable_web=False)
    assert "read" in reg
    assert "exec" not in reg
    assert "web_fetch" not in reg


def test_base_tool_satisfies_protocol():
    tool = ReadTool()
    assert isinstance(tool, AgentTool)


# ---------- ReadTool ----------


@pytest.mark.asyncio
async def test_read_file(tmp_path: Path):
    test_file = tmp_path / "hello.txt"
    test_file.write_text("line 1\nline 2\nline 3\n")

    tool = ReadTool(workspace_root=str(tmp_path))
    result = await tool.execute("c1", {"path": str(test_file)})
    assert not result.is_error
    text = result.content[0]["text"]
    assert "line 1" in text
    assert "line 2" in text
    assert "line 3" in text


@pytest.mark.asyncio
async def test_read_file_line_range(tmp_path: Path):
    test_file = tmp_path / "hello.txt"
    test_file.write_text("a\nb\nc\nd\ne\n")

    tool = ReadTool(workspace_root=str(tmp_path))
    result = await tool.execute("c1", {"path": str(test_file), "start_line": 2, "end_line": 4})
    assert not result.is_error
    text = result.content[0]["text"]
    assert "b" in text
    assert "c" in text
    assert "d" in text
    assert "a" not in text.split("|")[0]  # 'a' shouldn't be in line numbers


@pytest.mark.asyncio
async def test_read_file_not_found(tmp_path: Path):
    tool = ReadTool(workspace_root=str(tmp_path))
    result = await tool.execute("c1", {"path": str(tmp_path / "nope.txt")})
    assert result.is_error
    assert "not found" in result.content[0]["text"].lower()


@pytest.mark.asyncio
async def test_read_relative_path(tmp_path: Path):
    (tmp_path / "sub").mkdir()
    test_file = tmp_path / "sub" / "file.txt"
    test_file.write_text("content")

    tool = ReadTool(workspace_root=str(tmp_path))
    result = await tool.execute("c1", {"path": "sub/file.txt"})
    assert not result.is_error
    assert "content" in result.content[0]["text"]


# ---------- WriteTool ----------


@pytest.mark.asyncio
async def test_write_file(tmp_path: Path):
    tool = WriteTool(workspace_root=str(tmp_path))
    target = str(tmp_path / "output.txt")
    result = await tool.execute("c1", {"path": target, "content": "hello world"})
    assert not result.is_error
    assert Path(target).read_text() == "hello world"


@pytest.mark.asyncio
async def test_write_creates_dirs(tmp_path: Path):
    tool = WriteTool(workspace_root=str(tmp_path))
    target = str(tmp_path / "a" / "b" / "file.txt")
    result = await tool.execute("c1", {"path": target, "content": "deep"})
    assert not result.is_error
    assert Path(target).read_text() == "deep"


# ---------- EditTool ----------


@pytest.mark.asyncio
async def test_edit_single_replace(tmp_path: Path):
    test_file = tmp_path / "code.py"
    test_file.write_text("def foo():\n    return 1\n")

    tool = EditTool(workspace_root=str(tmp_path))
    result = await tool.execute(
        "c1",
        {
            "path": str(test_file),
            "old_string": "return 1",
            "new_string": "return 42",
        },
    )
    assert not result.is_error
    assert "return 42" in test_file.read_text()


@pytest.mark.asyncio
async def test_edit_not_found(tmp_path: Path):
    test_file = tmp_path / "code.py"
    test_file.write_text("hello")

    tool = EditTool(workspace_root=str(tmp_path))
    result = await tool.execute(
        "c1",
        {
            "path": str(test_file),
            "old_string": "nonexistent",
            "new_string": "x",
        },
    )
    assert result.is_error
    assert "not found" in result.content[0]["text"].lower()


@pytest.mark.asyncio
async def test_edit_ambiguous(tmp_path: Path):
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\ny = 1\n")

    tool = EditTool(workspace_root=str(tmp_path))
    result = await tool.execute(
        "c1",
        {
            "path": str(test_file),
            "old_string": "= 1",
            "new_string": "= 2",
        },
    )
    assert result.is_error
    assert "2 times" in result.content[0]["text"]


@pytest.mark.asyncio
async def test_edit_replace_all(tmp_path: Path):
    test_file = tmp_path / "code.py"
    test_file.write_text("x = 1\ny = 1\n")

    tool = EditTool(workspace_root=str(tmp_path))
    result = await tool.execute(
        "c1",
        {
            "path": str(test_file),
            "old_string": "= 1",
            "new_string": "= 2",
            "replace_all": True,
        },
    )
    assert not result.is_error
    assert test_file.read_text() == "x = 2\ny = 2\n"


# ---------- ExecTool ----------


@pytest.mark.asyncio
async def test_exec_simple():
    tool = ExecTool()
    result = await tool.execute("c1", {"command": "echo hello"})
    assert not result.is_error
    assert "hello" in result.content[0]["text"]
    assert "[exit code: 0]" in result.content[0]["text"]


@pytest.mark.asyncio
async def test_exec_failure():
    tool = ExecTool()
    result = await tool.execute("c1", {"command": "exit 42"})
    assert result.is_error
    assert "[exit code: 42]" in result.content[0]["text"]


@pytest.mark.asyncio
async def test_exec_timeout():
    tool = ExecTool(timeout=1)
    result = await tool.execute("c1", {"command": "sleep 10"})
    assert result.is_error
    assert "timed out" in result.content[0]["text"].lower()


@pytest.mark.asyncio
async def test_exec_working_directory(tmp_path: Path):
    tool = ExecTool()
    result = await tool.execute(
        "c1",
        {
            "command": "pwd",
            "working_directory": str(tmp_path),
        },
    )
    assert not result.is_error
    assert str(tmp_path) in result.content[0]["text"]


# ---------- WebFetchTool ----------


def test_url_safety_good():
    assert _is_url_safe("https://example.com") is None
    assert _is_url_safe("http://api.github.com/repos") is None


def test_url_safety_blocked():
    assert _is_url_safe("http://localhost:8080") is not None
    assert _is_url_safe("http://127.0.0.1/secret") is not None
    assert _is_url_safe("ftp://example.com") is not None
    assert _is_url_safe("http://10.0.0.1/internal") is not None
    assert _is_url_safe("http://192.168.1.1/admin") is not None


def test_extract_text_from_html():
    html = "<html><head><title>Test</title><script>var x=1;</script></head><body><p>Hello &amp; world</p></body></html>"
    text = _extract_text_from_html(html)
    assert "Hello & world" in text
    assert "var x=1" not in text
    assert "<p>" not in text


# ---------- Path safety ----------


@pytest.mark.asyncio
async def test_read_outside_workspace(tmp_path: Path):
    tool = ReadTool(workspace_root=str(tmp_path / "workspace"))
    result = await tool.execute("c1", {"path": "/etc/passwd"})
    assert result.is_error
    assert "outside" in result.content[0]["text"].lower()


@pytest.mark.asyncio
async def test_write_outside_workspace(tmp_path: Path):
    tool = WriteTool(workspace_root=str(tmp_path / "workspace"))
    result = await tool.execute("c1", {"path": "/tmp/evil.txt", "content": "bad"})
    assert result.is_error
    assert "outside" in result.content[0]["text"].lower()
