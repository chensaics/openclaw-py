"""Agent runner — core agent loop with streaming LLM + tool execution.

Implements the fundamental loop:
  prompt -> stream LLM -> if tool_use: execute tools -> loop
  until the LLM stops requesting tools.

Integrates:
- Plan/Step tracking (F01)
- Interrupt system (F02)
- Intent analysis (F03)
- Message bus peek (F04)
- RuntimeContext injection (F10)
- Message-level Timeline (F06)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from pyclaw.agents.session import AgentMessage, SessionManager, TimelineKind
from pyclaw.agents.stream import build_tool_definitions, stream_llm
from pyclaw.agents.types import AgentEvent, AgentTool, ModelConfig, ToolCall, ToolResult

logger = logging.getLogger(__name__)


async def run_agent(
    prompt: str,
    session: SessionManager,
    model: ModelConfig,
    tools: list[AgentTool] | None = None,
    system_prompt: str | None = None,
    max_turns: int = 50,
    abort_event: asyncio.Event | None = None,
    *,
    interrupt_ctx: Any | None = None,
    plan: Any | None = None,
    runtime_context: Any | None = None,
    session_key: str = "",
) -> AsyncIterator[AgentEvent]:
    """Run the agent loop, yielding events as they occur.

    The loop continues until the LLM produces a response without tool calls,
    or max_turns is reached, or abort_event is set.

    New optional parameters:
    - ``interrupt_ctx``: An :class:`InterruptibleContext` for cancel/append support.
    - ``plan``: An active :class:`Plan` to track multi-step execution.
    - ``runtime_context``: A :class:`RuntimeContext` to inject into tools.
    - ``session_key``: Session key for message bus peek.
    """
    from pyclaw.agents.tools.runtime_context import RuntimeContext, set_runtime_context, reset_runtime_context

    ctx_token = None
    if runtime_context:
        ctx_token = set_runtime_context(runtime_context)

    interrupt_task: asyncio.Task[None] | None = None
    if interrupt_ctx and session_key:
        from pyclaw.agents.interrupt import check_incoming_messages
        interrupt_task = asyncio.create_task(
            check_incoming_messages(session_key, interrupt_ctx)
        )

    # Lazy-import planner components
    step_detector = None
    if plan:
        from pyclaw.agents.planner import StepDetector
        step_detector = StepDetector()

    try:
        async for event in _agent_loop(
            prompt=prompt,
            session=session,
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            max_turns=max_turns,
            abort_event=abort_event,
            interrupt_ctx=interrupt_ctx,
            plan=plan,
            step_detector=step_detector,
        ):
            yield event
    finally:
        if interrupt_task and not interrupt_task.done():
            interrupt_task.cancel()
            try:
                await interrupt_task
            except asyncio.CancelledError:
                pass

        if ctx_token is not None:
            reset_runtime_context(ctx_token)


async def _agent_loop(
    *,
    prompt: str,
    session: SessionManager,
    model: ModelConfig,
    tools: list[AgentTool] | None,
    system_prompt: str | None,
    max_turns: int,
    abort_event: asyncio.Event | None,
    interrupt_ctx: Any | None,
    plan: Any | None,
    step_detector: Any | None,
) -> AsyncIterator[AgentEvent]:
    yield AgentEvent(type="agent_start")

    messages = session.get_messages_as_dicts()

    effective_system = system_prompt or ""
    if plan and hasattr(plan, "to_context_string"):
        plan_ctx = plan.to_context_string()
        effective_system = f"{effective_system}\n\n{plan_ctx}" if effective_system else plan_ctx

    if effective_system and not any(m["role"] == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": effective_system})

    messages.append({"role": "user", "content": prompt})
    session.append_message(AgentMessage(role="user", content=prompt))

    tool_defs = build_tool_definitions(tools) if tools else None
    tools_by_name = {t.name: t for t in tools} if tools else {}
    turn = 0

    while turn < max_turns:
        if abort_event and abort_event.is_set():
            yield AgentEvent(type="error", error="aborted")
            break

        if interrupt_ctx and interrupt_ctx.is_cancelled:
            yield AgentEvent(type="error", error="interrupted")
            break

        if interrupt_ctx:
            appended = interrupt_ctx.drain_appended()
            for extra in appended:
                messages.append({"role": "user", "content": f"[Additional context] {extra}"})

        turn += 1
        yield AgentEvent(type="message_start")

        completion_text = ""
        completion_tool_calls: list[ToolCall] = []
        usage: dict[str, int] | None = None

        async for event in stream_llm(model, messages, tool_defs):
            if interrupt_ctx and interrupt_ctx.is_cancelled:
                break

            if event.type == "message_update":
                yield event
                if event.delta:
                    completion_text += event.delta

            elif event.type == "message_end":
                usage = event.usage

            elif event.type == "_completion":
                if event.result:
                    completion_text = event.result.get("text", "")
                    for tc_data in event.result.get("tool_calls", []):
                        completion_tool_calls.append(
                            ToolCall(
                                id=tc_data["id"],
                                name=tc_data["name"],
                                arguments=tc_data["arguments"],
                            )
                        )

        if interrupt_ctx and interrupt_ctx.is_cancelled:
            yield AgentEvent(type="error", error="interrupted")
            break

        assistant_msg_obj = AgentMessage.from_dict(
            _build_assistant_message(completion_text, completion_tool_calls)
        )

        if plan and step_detector:
            plan.iteration_count += 1
            if step_detector.is_step_complete(completion_text, plan.iteration_count):
                plan.advance_step(result=completion_text[:200])
                assistant_msg_obj.add_timeline(
                    TimelineKind.PLAN,
                    f"Step advanced to {plan.current_step_index + 1}/{len(plan.steps)}",
                )
                yield AgentEvent(type="tool_end", name="plan_step", result={
                    "step": plan.current_step_index,
                    "progress": plan.generate_progress_summary(),
                })

        messages.append(assistant_msg_obj.to_dict())
        session.append_message(assistant_msg_obj)

        if usage:
            try:
                from pyclaw.infra.session_cost import record_usage

                persisted_session_id = session.path.stem if str(session.path) != "/dev/null" else session.session_id
                record_usage(
                    session_id=persisted_session_id,
                    provider=model.provider,
                    model=model.model_id,
                    input_tokens=int(usage.get("input_tokens", 0) or 0),
                    output_tokens=int(usage.get("output_tokens", 0) or 0),
                    has_api_key=bool(model.api_key),
                )
            except Exception:
                pass
            yield AgentEvent(type="message_end", usage=usage)
        else:
            yield AgentEvent(type="message_end")

        if not completion_tool_calls:
            break

        for tc in completion_tool_calls:
            yield AgentEvent(type="tool_start", name=tc.name, tool_call_id=tc.id)

            tool = tools_by_name.get(tc.name)
            if tool:
                try:
                    result = await tool.execute(tc.id, tc.arguments)
                except Exception as e:
                    result = ToolResult.text(f"Error: {e}", is_error=True)
            else:
                result = ToolResult.text(f"Unknown tool: {tc.name}", is_error=True)

            yield AgentEvent(
                type="tool_end",
                name=tc.name,
                tool_call_id=tc.id,
                result={"content": result.content, "is_error": result.is_error},
            )

            tool_result_msg = AgentMessage.from_dict(_build_tool_result_message(tc.id, result))
            tool_result_msg.add_timeline(
                TimelineKind.TOOL_RESULT,
                f"{tc.name}: {'error' if result.is_error else 'ok'}",
            )
            messages.append(tool_result_msg.to_dict())
            session.append_message(tool_result_msg)

    if plan and not plan.is_complete:
        from pyclaw.agents.planner import PlanStatus
        if all(s.status.value == "completed" for s in plan.steps):
            plan.status = PlanStatus.COMPLETED

    yield AgentEvent(type="agent_end")


def _build_assistant_message(text: str, tool_calls: list[ToolCall]) -> dict[str, Any]:
    """Build an assistant message dict with optional tool calls."""
    msg: dict[str, Any] = {"role": "assistant"}

    if tool_calls:
        msg["content"] = text or None
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            }
            for tc in tool_calls
        ]
    else:
        msg["content"] = text

    return msg


def _build_tool_result_message(tool_call_id: str, result: ToolResult) -> dict[str, Any]:
    """Build a tool result message dict."""
    content_text = "\n".join(
        block.get("text", "") for block in result.content if block.get("type") == "text"
    )
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content_text,
    }
