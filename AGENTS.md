---
title: AGENTS.md
summary: Workspace documentation for agent orchestration and management
read_when:
  - Bootstrapping a workspace manually - If `BOOTSTRAP.md` exists, that's your birth certificate. Follow it, figure out who you are, then delete it. You won't need it again.

---

# AGENTS.md - Your Workspace

This folder is home. Treat it that way.

## First Run

If `BOOTSTRAP.md` exists, that's your birth certificate. Follow it, figure out who you are, then delete it. You won't need it again.

## Every Session

Before doing anything else:
1. Read `SOUL.md` — this is who you are
2. Read `USER.md` — this is who you're helping
3. Read `memory/YYYY-MM-DD.md` (today + yesterday) for recent context

If in MAIN SESSION (direct chat with your human):
  - DO NOT load in shared contexts (Discord, group chats, sessions with other people)
  - DO NOT respond to every single message
  - Ask before executing expensive operations
  - Ask permission before reading large files
  - Respect your time and tokens

### 🧠 Memory

You wake up fresh each session. These files are your continuity:

`memory/YYYY-MM-DD.md`
  - Daily memory of events, thoughts, decisions
- Update it at end of day
- Focus on what matters for long-term success
- Capture decisions and lessons learned
- NOT raw logs — curate wisdom like a human reviewing their journal

## 📁 Tools

Skills provide your tools. When you need one:
- Check its `SKILL.md` first
- Use appropriate skill for the task

### 🛠️ External

You have access to external systems. Ask permission before:
- Reading large files or making network requests
- Installing packages or modifying system config
- Running tests or deployment scripts

### 💬 Project Structure

```
openclaw-py/
├── pyclaw/
│   ├── agents/
│   │   ├── orchestration/
│   │   │   ├── subagents/
│   │   │   │   └── templates/
│   │   └── AGENTS.md
│   ├── config/
│   │   ├── constants/
│   ├── tests/
│   ├── tools/
│   ├── ui/
│   ├── cli/
│   └── main.py
```

## 🎯 Architecture Overview

### Agent Orchestration System

The orchestration system enables flexible, async agent delegation with dynamic tool management:

**Core Components:**

| Component | Purpose | Status |
|----------|----------|--------|
| `orchestration/` | Data structures (Pydantic models) | ✅ Stable |
| `subagents/` | Manager (SubagentManager) | ✅ Stable |
| `templates/` | AGENTS.md template | ✅ Stable |

**Data Flow:**

```
Main Agent
  ├─ Creates task plan
  │
  ├─ Creates OrchestrationManifest
  │
  ├─ Spawns subagents via SubagentManager
  │  │   └─ Each subagent:
  │     └─ Gets filtered tools based on SubagentConfig
  │     └─ Runs with custom system_prompt and tool_context
  │     └─ Poll/Join tools monitor async execution
  │
  └─ Updates manifest status
  │
  └─ Subagents can be killed/steered
  └─ Results collected in SubagentManager
  └
  └─ Task decomposer suggests breaking down complex tasks
```

## 🤖 Key Concepts

### 1. Async Spawn Pattern

Unlike synchronous `sessions_spawn`, the new orchestration system uses non-blocking spawn:

```python
# Old (blocking)
result = sessions_spawn(config, runner=runner)
return result  # Blocks until complete

# New (non-blocking)
future = asyncio.Future()
entry = _SubagentEntry(config, future=future)
self._active[session_id] = entry
asyncio.create_task(_run_subagent(entry))
return future  # Immediately returns Future
```

The `future` in `_SubagentEntry` allows:
- Poll/Join tools to monitor progress
- Kill operations can resolve the future
- Multiple subagents can run concurrently (semaphore controlled)

### 2. Subagent Config

```python
SubagentConfig(
    session_id="unique-id",
    prompt="Your task",
    system_prompt="You are specialized agent for X",  # NEW
    tool_context={"key": "value"},  # NEW
    tools_enabled=["tool1", "tool2"],  # Whitelist
    tools_disabled=["blocked_tool"],      # Blacklist
    provider="anthropic",  # Provider selection
    model="claude-sonnet-4-6",  # Model selection
)
    agent_id="researcher",  # Specialized role
    label="Task X",  # Human-readable identifier
    max_depth=3,  # Maximum nesting depth
)
    notify_parent=True,  # Parent gets notified on completion
)
    parent_session_id="parent-id",  # For nested tasks
)
    channel="webhook",  # Integration channel
    chat_id="chat-123",  # External chat ID
    metadata={"priority": "high"},  # Custom metadata
)
)
```

### 3. Tool Filtering

Based on `SubagentConfig`, the manager filters available tools:

1. **Whitelist (`tools_enabled`)**: Only these tools are passed
2. **Blacklist (`tools_disabled`)**: These tools are blocked
3. **Empty list**: If neither set, all tools available (default)

This enables:
- **Role-based tooling**: Different roles get different tools
- **Dynamic delegation**: Tools can be enabled/disabled per subagent
- **Custom prompts**: `system_prompt` allows complete override
- **Tool context**: `tool_context` provides additional context to tools

### 4. Poll/Join Tools

```python
# Poll tool
ToolResult = subagent_poll(session_id="xyz")
returns: {"status": "RUNNING", "is_running": True, "output_preview": ""}

# Join tool
ToolResult = subagent_join(session_id="xyz", timeout=300)
waits for future to complete
returns: {"status": "COMPLETED", "output": "...", "meta": {...}}
```

## 📚 Usage Patterns

### Pattern 1: Spawn and Monitor

```python
from pyclaw.agents.subagents import SubagentManager

# Spawn and monitor
manifest = orchestrate_manifest(...)
manager = SubagentManager()

# Spawn
session_id = manager.spawn(
    SubagentConfig(
        prompt="Analyze X dataset",
        tools_enabled=["subagent_poll", "subagent_join"],
        system_prompt="You are data analyst. Focus on accuracy."
    )
)

# Poll for progress
while True:
    poll_result = subagent_poll(session_id=session_id)
    if poll_result["status"] == "COMPLETED":
        break

# Join for result
final_result = subagent_join(session_id=session_id)
print(final_result["output"])
```

### Pattern 2: Nested Orchestration

Main agent spawns coordinator → Coordinator spawns researcher → Analyst subagent → Analyst spawns summarizer → Summary returned to Main

```

## ⚠️ Safety & Limits

- **Concurrency Control**: `SubagentManager.MAX_CONCURRENT = 4` (adjustable)
- **Depth Limit**: `SubagentManager.MAX_DEPTH = 5` (prevents infinite loops)
- **Timeout**: `subagent_join` default 300s
- **Memory**: Recent completions limited to 100 entries

## 🧪 Testing

Orchestration tests are in `tests/orchestration/`:
```python
tests/orchestration/test_storage.py
tests/orchestration/test_decomposer.py
tests/orchestration/test_orchestrator_tools.py
```

## 📖 Documentation

- **AGENTS.md** (this file): Workspace template for orchestration
- **manifest.py**: Data structure definitions
- **decomposer.py**: Task decomposition logic
- **manager.py**: Core orchestration engine
- **polling.py**: Polling/Join tools
```

---

## 🎯 Quick Reference

| Function | Purpose |
|---------|--------|---|
| `spawn()` | Spawn async subagent | Returns Future |
| `subagent_poll()` | Poll subagent status | ToolResult |
| `subagent_join()` | Wait for completion | ToolResult |
| `decompose_task()` | Break down task | list[Subtask] |
| `filter_tools()` | Apply tool policy | list[BaseTool] |
| `orchestrate_manifest()` | Create manifest | dict |

---

## 🚀 Gotchas

If you see `[DUPLICATE PROPERTY]` in linter output:
1. In `manager.py`: Lines 44-45 show duplicate `active_count`/`active_ids` - This is **intentional** (Python method overloading pattern, not an error)
2. The duplicates are **inside property definition blocks** and do not need removal

**Fix strategy:**
- Remove lines 44-45 if creating new method
- Keep first occurrence (lines 31-34, 39-45)
- Remove second occurrence only if it creates issues
- Test thoroughly that properties still work

**What NOT to do:**
- Delete entire property if you see duplicates
- Trust that linter knows better than you

---

## 🔗 Version History

- **0.1.0** (2026-03-21): Initial orchestration framework
- **[Future]**: Planned iterative improvements

---

**Maintainer:** @cs
**File Location:** `src/pyclaw/agents/orchestration/`

**Last Updated:** [Add details here when you make changes]
