"""Tests for message timeline (F06) — session.py extensions."""

from pyclaw.agents.session import (
    AgentMessage,
    TimelineActivity,
    TimelineEntry,
    TimelineKind,
)


class TestTimelineEntry:
    def test_create_entry(self) -> None:
        activity = TimelineActivity(
            activity_type="tool_exec",
            summary="Executed grep tool",
            detail="Found 3 matches",
        )
        entry = TimelineEntry(kind=TimelineKind.TOOL_CALL, activity=activity)
        assert entry.kind == TimelineKind.TOOL_CALL
        assert entry.activity.summary == "Executed grep tool"

    def test_serialization(self) -> None:
        entry = TimelineEntry(
            kind=TimelineKind.TOOL_RESULT,
            activity=TimelineActivity(
                activity_type="tool_result",
                summary="grep: ok",
            ),
        )
        d = entry.to_dict()
        assert d["kind"] == "tool_result"
        assert d["activity"]["summary"] == "grep: ok"

        restored = TimelineEntry.from_dict(d)
        assert restored.kind == TimelineKind.TOOL_RESULT
        assert restored.activity.summary == "grep: ok"


class TestAgentMessageTimeline:
    def test_message_without_timeline(self) -> None:
        msg = AgentMessage(role="assistant", content="hello")
        d = msg.to_dict()
        assert "timeline" not in d

    def test_add_timeline(self) -> None:
        msg = AgentMessage(role="assistant", content="test")
        msg.add_timeline(TimelineKind.TOOL_CALL, "Called read_file")
        assert msg.timeline is not None
        assert len(msg.timeline) == 1
        assert msg.timeline[0].kind == TimelineKind.TOOL_CALL

    def test_multiple_timeline_entries(self) -> None:
        msg = AgentMessage(role="assistant", content="test")
        msg.add_timeline(TimelineKind.TOOL_CALL, "Called tool A")
        msg.add_timeline(TimelineKind.TOOL_RESULT, "Tool A: ok")
        msg.add_timeline(TimelineKind.PLAN, "Advanced to step 2")

        assert len(msg.timeline) == 3

    def test_timeline_serialization_roundtrip(self) -> None:
        msg = AgentMessage(role="assistant", content="test")
        msg.add_timeline(TimelineKind.STATUS, "Agent started", detail="model: gpt-4o")

        d = msg.to_dict()
        assert "timeline" in d
        assert len(d["timeline"]) == 1

        restored = AgentMessage.from_dict(d)
        assert restored.timeline is not None
        assert len(restored.timeline) == 1
        assert restored.timeline[0].kind == TimelineKind.STATUS
        assert restored.timeline[0].activity.detail == "model: gpt-4o"

    def test_from_dict_no_timeline(self) -> None:
        d = {"role": "user", "content": "hello"}
        msg = AgentMessage.from_dict(d)
        assert msg.timeline is None
