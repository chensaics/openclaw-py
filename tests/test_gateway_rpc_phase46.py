"""Phase 46 tests — extended RPC de-placeholdering: doctor, system.logs, skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper: fake GatewayConnection
# ---------------------------------------------------------------------------


class FakeConn:
    def __init__(self) -> None:
        self.responses: list[tuple[str, dict[str, Any]]] = []
        self.errors: list[tuple[str, str, str]] = []

    async def send_ok(self, method: str, payload: dict[str, Any]) -> None:
        self.responses.append((method, payload))

    async def send_error(self, method: str, code: str, msg: str) -> None:
        self.errors.append((method, code, msg))


# ---------------------------------------------------------------------------
# 46a: doctor.run returns real checks
# ---------------------------------------------------------------------------


class TestDoctorRPC:
    """Verify doctor.run now returns non-empty check results."""

    @pytest.mark.asyncio
    async def test_doctor_returns_checks(self) -> None:
        from pyclaw.gateway.methods.extended import create_extended_handlers

        handlers = create_extended_handlers()
        conn = FakeConn()

        await handlers["doctor.run"](None, conn)

        assert len(conn.responses) == 1
        method, payload = conn.responses[0]
        assert method == "doctor.run"
        assert len(payload["checks"]) > 0
        assert "summary" in payload
        assert payload["summary"]["passed"] + payload["summary"]["failed"] + payload["summary"]["warnings"] >= 0
        assert "platform" in payload
        assert "pythonVersion" in payload

    @pytest.mark.asyncio
    async def test_doctor_checks_have_structure(self) -> None:
        from pyclaw.gateway.methods.extended import create_extended_handlers

        handlers = create_extended_handlers()
        conn = FakeConn()

        await handlers["doctor.run"](None, conn)

        for check in conn.responses[0][1]["checks"]:
            assert "name" in check
            assert "category" in check
            assert "severity" in check
            assert "message" in check


# ---------------------------------------------------------------------------
# 46b: system.logs reads from real log file
# ---------------------------------------------------------------------------


class TestSystemLogsRPC:
    """Verify system.logs returns file content (or empty when no file)."""

    @pytest.mark.asyncio
    async def test_logs_empty_when_no_file(self, tmp_path: Path) -> None:
        from pyclaw.gateway.methods.extended import create_extended_handlers

        handlers = create_extended_handlers()
        conn = FakeConn()

        with patch("pyclaw.config.paths.resolve_state_dir", return_value=tmp_path):
            await handlers["system.logs"]({"lines": 10}, conn)

        assert len(conn.responses) == 1
        assert conn.responses[0][1]["count"] == 0

    @pytest.mark.asyncio
    async def test_logs_reads_lines(self, tmp_path: Path) -> None:
        from pyclaw.gateway.methods.extended import create_extended_handlers

        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "pyclaw.log"
        log_file.write_text("\n".join(f"[INFO] line {i}" for i in range(30)))

        handlers = create_extended_handlers()
        conn = FakeConn()

        with patch("pyclaw.config.paths.resolve_state_dir", return_value=tmp_path):
            await handlers["system.logs"]({"lines": 10}, conn)

        payload = conn.responses[0][1]
        assert payload["count"] == 10
        assert "[INFO]" in payload["logs"][-1]

    @pytest.mark.asyncio
    async def test_logs_level_filter(self, tmp_path: Path) -> None:
        from pyclaw.gateway.methods.extended import create_extended_handlers

        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "pyclaw.log"
        log_file.write_text("[INFO] ok\n[ERROR] bad\n[INFO] fine\n[WARNING] hmm\n")

        handlers = create_extended_handlers()
        conn = FakeConn()

        with patch("pyclaw.config.paths.resolve_state_dir", return_value=tmp_path):
            await handlers["system.logs"]({"lines": 50, "level": "error"}, conn)

        payload = conn.responses[0][1]
        assert payload["count"] == 1
        assert "ERROR" in payload["logs"][0]


# ---------------------------------------------------------------------------
# 46c: skills.list returns discoverable skills
# ---------------------------------------------------------------------------


class TestSkillsListRPC:
    """Verify skills.list attempts skill discovery."""

    @pytest.mark.asyncio
    async def test_skills_list_no_crash_when_no_skills(self) -> None:
        from pyclaw.gateway.methods.extended import create_extended_handlers

        handlers = create_extended_handlers()
        conn = FakeConn()

        # discover_skills may or may not be importable; either way it should not crash
        await handlers["skills.list"](None, conn)

        assert len(conn.responses) == 1
        payload = conn.responses[0][1]
        assert "skills" in payload
        assert "count" in payload
        assert isinstance(payload["skills"], list)

    @pytest.mark.asyncio
    async def test_skills_list_with_mocked_skills(self, tmp_path: Path) -> None:
        """Verify skills.list populates from load_skill_entries results."""
        from pyclaw.gateway.methods.extended import create_extended_handlers

        mock_skill = MagicMock()
        mock_skill.name = "test-skill"
        mock_skill.source = "workspace"
        mock_skill.description = "A test skill"
        mock_skill.enabled = True

        handlers = create_extended_handlers()
        conn = FakeConn()

        def fake_load(skill_dir: Any, **kwargs: Any) -> list:
            return [mock_skill]

        # Patch at both module levels since __init__.py re-exports
        with (
            patch("pyclaw.agents.skills.load_skill_entries", side_effect=fake_load),
            patch("pyclaw.agents.skills.loader.load_skill_entries", side_effect=fake_load),
        ):
            await handlers["skills.list"](None, conn)

        payload = conn.responses[0][1]
        assert payload["count"] >= 1
        names = [s["name"] for s in payload["skills"]]
        assert "test-skill" in names


# ---------------------------------------------------------------------------
# 46d: extended handlers total count (after browser removal + log materialization)
# ---------------------------------------------------------------------------


class TestExtendedHandlerCount:
    """Verify the correct number of handlers are registered."""

    def test_handler_count(self) -> None:
        from pyclaw.gateway.methods.extended import create_extended_handlers

        handlers = create_extended_handlers()
        # 15 original - 2 browser = 13
        assert len(handlers) == 13
