"""Tests for session manager JSONL compatibility, locking, tokens, and compaction."""

import json
import tempfile
from pathlib import Path

import pytest

from pyclaw.agents.session import AgentMessage, SessionManager
from pyclaw.agents.session_lock import SessionLockError, acquire_session_lock
from pyclaw.agents.tokens import estimate_message_tokens, estimate_messages_tokens, estimate_tokens
from pyclaw.routing.session_key import build_main_session_key, parse_session_key


def test_session_manager_empty():
    mgr = SessionManager.in_memory()
    assert mgr.messages == []


def test_session_manager_load_existing_jsonl():
    """Should load a JSONL file in TypeScript SessionManager format."""
    lines = [
        json.dumps({"type": "session", "version": 3, "id": "abc123"}),
        json.dumps(
            {
                "type": "message",
                "message": {"role": "user", "content": "Hello"},
            }
        ),
        json.dumps(
            {
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": "Hi! How can I help?",
                },
            }
        ),
        json.dumps(
            {
                "type": "custom",
                "customType": "pyclaw.cache-ttl",
                "data": {"ttl": 300},
            }
        ),
        json.dumps(
            {
                "type": "message",
                "message": {
                    "role": "user",
                    "content": "What's the weather?",
                },
            }
        ),
        json.dumps(
            {
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me check..."},
                        {
                            "type": "tool_use",
                            "id": "tc_1",
                            "name": "web_fetch",
                            "input": {"url": "https://weather.example.com"},
                        },
                    ],
                },
            }
        ),
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write("\n".join(lines) + "\n")
        tmp_path = Path(f.name)

    try:
        mgr = SessionManager.open(tmp_path)

        assert mgr.session_id == "abc123"
        assert len(mgr.messages) == 4
        assert mgr.messages[0].role == "user"
        assert mgr.messages[0].content == "Hello"
        assert mgr.messages[1].role == "assistant"
        assert mgr.messages[3].role == "assistant"
        assert isinstance(mgr.messages[3].content, list)
        assert len(mgr.custom_entries) == 1
    finally:
        tmp_path.unlink(missing_ok=True)


def test_session_manager_append():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        tmp_path = Path(f.name)

    try:
        mgr = SessionManager(path=tmp_path)
        mgr.write_header()
        mgr.append_message(AgentMessage(role="user", content="Hi"))
        mgr.append_message(AgentMessage(role="assistant", content="Hello!"))

        # Reload and verify
        mgr2 = SessionManager.open(tmp_path)
        assert len(mgr2.messages) == 2
        assert mgr2.messages[0].content == "Hi"
        assert mgr2.messages[1].content == "Hello!"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_session_key_parsing():
    key = "agent:main:telegram:direct:12345"
    parsed = parse_session_key(key)
    assert parsed is not None
    assert parsed.agent_id == "main"
    assert parsed.rest == "telegram:direct:12345"


def test_session_key_main():
    key = build_main_session_key("main")
    assert key == "agent:main:main"

    parsed = parse_session_key(key)
    assert parsed is not None
    assert parsed.agent_id == "main"
    assert parsed.rest == "main"


def test_session_key_invalid():
    assert parse_session_key("invalid") is None
    assert parse_session_key("agent:") is None
    assert parse_session_key("agent:id:") is None


# ---------- DAG entries (id / parentId) ----------


def test_session_dag_entries(tmp_path: Path):
    """Appended entries should carry id and parentId fields."""
    session_file = tmp_path / "dag.jsonl"
    mgr = SessionManager(path=session_file)
    mgr.write_header()
    mgr.append_message(AgentMessage(role="user", content="a"))
    mgr.append_message(AgentMessage(role="assistant", content="b"))

    lines = [json.loads(l) for l in session_file.read_text().strip().split("\n")]
    # header, msg1, msg2
    assert len(lines) == 3
    assert lines[0]["type"] == "session"
    assert "id" in lines[1]
    assert "id" in lines[2]
    assert lines[2]["parentId"] == lines[1]["id"]


# ---------- Token estimation ----------


def test_estimate_tokens_basic():
    assert estimate_tokens("") == 0
    tokens = estimate_tokens("Hello, world!")
    assert tokens > 0


def test_estimate_message_tokens():
    msg = {"role": "user", "content": "Hello there, how are you?"}
    tokens = estimate_message_tokens(msg)
    assert tokens > 4  # at least the base overhead


def test_estimate_messages_tokens():
    msgs = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    total = estimate_messages_tokens(msgs)
    assert total > 8


def test_estimate_tokens_with_tool_calls():
    msg = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "NYC"}'},
            }
        ],
    }
    tokens = estimate_message_tokens(msg)
    assert tokens > 10


# ---------- Session locking ----------


def test_session_lock_basic(tmp_path: Path):
    session_file = tmp_path / "test.jsonl"
    session_file.touch()

    with acquire_session_lock(session_file):
        lock_file = session_file.with_suffix(".jsonl.lock")
        assert lock_file.exists()

    assert not lock_file.exists()


def test_session_lock_reentrant_fails(tmp_path: Path):
    session_file = tmp_path / "test.jsonl"
    session_file.touch()

    with acquire_session_lock(session_file), pytest.raises(SessionLockError):
        with acquire_session_lock(session_file):
            pass


def test_session_lock_stale_cleanup(tmp_path: Path):
    """Stale locks from dead processes should be cleaned up."""
    session_file = tmp_path / "test.jsonl"
    session_file.touch()

    # Create a stale lock (PID that doesn't exist)
    lock_file = session_file.with_suffix(".jsonl.lock")
    lock_file.write_text(json.dumps({"pid": 999999999, "createdAt": 0}))

    with acquire_session_lock(session_file):
        assert lock_file.exists()

    assert not lock_file.exists()


# ---------- Compaction ----------


def test_session_compact_basic():
    mgr = SessionManager.in_memory()
    for i in range(10):
        mgr.messages.append(
            AgentMessage(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
        )

    result = mgr.compact("Summary of earlier conversation", keep_last_n=4)
    assert result["tokens_before"] > result["tokens_after"]
    # 1 summary system msg + 4 kept messages
    assert len(mgr.messages) == 5
    assert mgr.messages[0].role == "system"
    assert "Summary" in str(mgr.messages[0].content)
    assert mgr.compaction_count == 1


def test_session_compact_too_few_messages():
    """Compaction should be a no-op when there are fewer messages than keep_last_n."""
    mgr = SessionManager.in_memory()
    mgr.messages.append(AgentMessage(role="user", content="Hi"))
    mgr.messages.append(AgentMessage(role="assistant", content="Hello"))

    result = mgr.compact("Summary", keep_last_n=4)
    assert result["tokens_before"] == result["tokens_after"]
    assert len(mgr.messages) == 2


def test_session_estimate_tokens():
    mgr = SessionManager.in_memory()
    mgr.messages.append(AgentMessage(role="user", content="Hello world"))
    tokens = mgr.estimate_tokens()
    assert tokens > 0
