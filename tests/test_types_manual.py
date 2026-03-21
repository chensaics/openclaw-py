#!/usr/bin/env python3
"""Simple test for SubagentConfig Pydantic models."""

import sys

sys.path.insert(0, "/mnt/g/chensai/openclaw-py/src")

from pyclaw.agents.subagents.types import SubagentConfig

print("Testing SubagentConfig Pydantic model...")

# Test 1: Basic creation with required fields
config = SubagentConfig(
    session_id="test-session",
    parent_session_id="parent-session",
    agent_id="test-agent",
    prompt="Test task",
    provider="test-provider",
    model="test-model",
    workspace_dir="/test/workspace",
    max_depth=1,
    current_depth=0,
    tools_enabled=["read", "write"],
    tools_disabled=["exec"],
    notify_parent=True,
    channel="test-channel",
    chat_id="test-chat",
    label="Test Label",
    metadata={"key": "value"},
    system_prompt="You are a test agent with custom system prompt.",
    tool_context={"tool1": "context1"},
)

print(f"config.session_id: {config.session_id}")
print(f"config.system_prompt: {config.system_prompt}")
print(f"config.tool_context: {config.tool_context}")
print(f"config.tools_enabled: {config.tools_enabled}")
print(f"config.tools_disabled: {config.tools_disabled}")

# Test 2: Serialization
config_dict = config.model_dump()
print("\nSerialized config:")
for key, value in config_dict.items():
    print(f"  {key}: {value}")

# Test 3: Round-trip
reconstructed = SubagentConfig(**config_dict)
print("\nRound-trip successful:")
print(f"  session_id: {reconstructed.session_id}")
print(f" system_prompt: {reconstructed.system_prompt}")
print(f" tool_context: {reconstructed.tool_context}")

print("\n✅ All tests passed!")
