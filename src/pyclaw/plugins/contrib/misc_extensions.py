"""Non-channel extensions — lobster, llm-task, copilot-proxy, diagnostics-otel.

Ported from ``extensions/lobster``, ``extensions/llm-task``, etc.

Provides framework/stub implementations for:
- Lobster: typed pipeline workflows with resumable approval
- LLM Task: JSON-only LLM task execution
- Copilot Proxy: Copilot provider proxy plugin
- Diagnostics OTEL: OpenTelemetry diagnostics export
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lobster — Typed Pipeline Workflows
# ---------------------------------------------------------------------------


class PipelineState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineStep:
    """A single step in a Lobster pipeline."""

    step_id: str
    name: str
    action: str = ""
    requires_approval: bool = False
    state: PipelineState = PipelineState.PENDING
    result: Any = None
    error: str = ""


@dataclass
class Pipeline:
    """A Lobster pipeline workflow."""

    pipeline_id: str
    name: str
    steps: list[PipelineStep] = field(default_factory=list)
    state: PipelineState = PipelineState.PENDING
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if self.created_at == 0:
            self.created_at = time.time()

    @property
    def current_step(self) -> PipelineStep | None:
        for step in self.steps:
            if step.state in (
                PipelineState.PENDING,
                PipelineState.RUNNING,
                PipelineState.AWAITING_APPROVAL,
            ):
                return step
        return None

    @property
    def is_complete(self) -> bool:
        return self.state in (PipelineState.COMPLETED, PipelineState.FAILED, PipelineState.REJECTED)

    @property
    def progress_pct(self) -> int:
        if not self.steps:
            return 0
        completed = sum(1 for s in self.steps if s.state == PipelineState.COMPLETED)
        return int((completed / len(self.steps)) * 100)


StepHandler = Any  # Callable[[PipelineStep, Pipeline], Awaitable[Any]]


class LobsterExtension:
    """Lobster pipeline workflow extension with step execution."""

    def __init__(self) -> None:
        self._pipelines: dict[str, Pipeline] = {}
        self._handlers: dict[str, StepHandler] = {}

    @property
    def name(self) -> str:
        return "lobster"

    def register_handler(self, action: str, handler: StepHandler) -> None:
        """Register an async handler for a step action type."""
        self._handlers[action] = handler

    def create_pipeline(self, pipeline_id: str, name: str, steps: list[PipelineStep]) -> Pipeline:
        pipeline = Pipeline(pipeline_id=pipeline_id, name=name, steps=steps)
        self._pipelines[pipeline_id] = pipeline
        return pipeline

    async def run_pipeline(self, pipeline_id: str) -> Pipeline:
        """Execute pipeline steps sequentially, pausing at approval gates."""
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise KeyError(f"Pipeline '{pipeline_id}' not found")

        pipeline.state = PipelineState.RUNNING

        for step in pipeline.steps:
            if step.state == PipelineState.COMPLETED:
                continue

            if step.requires_approval and step.state != PipelineState.APPROVED:
                step.state = PipelineState.AWAITING_APPROVAL
                pipeline.state = PipelineState.AWAITING_APPROVAL
                logger.info(
                    "Pipeline '%s' paused at step '%s' (awaiting approval)",
                    pipeline_id,
                    step.step_id,
                )
                return pipeline

            step.state = PipelineState.RUNNING
            handler = self._handlers.get(step.action)
            if handler:
                try:
                    step.result = await handler(step, pipeline)
                    step.state = PipelineState.COMPLETED
                except Exception as exc:
                    step.state = PipelineState.FAILED
                    step.error = str(exc)
                    pipeline.state = PipelineState.FAILED
                    return pipeline
            else:
                step.state = PipelineState.COMPLETED
                logger.debug("No handler for action '%s', marking step complete", step.action)

        pipeline.state = PipelineState.COMPLETED
        return pipeline

    def approve_step(self, pipeline_id: str, step_id: str) -> bool:
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return False
        for step in pipeline.steps:
            if step.step_id == step_id and step.state == PipelineState.AWAITING_APPROVAL:
                step.state = PipelineState.APPROVED
                return True
        return False

    def reject_step(self, pipeline_id: str, step_id: str) -> bool:
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return False
        for step in pipeline.steps:
            if step.step_id == step_id and step.state == PipelineState.AWAITING_APPROVAL:
                step.state = PipelineState.REJECTED
                pipeline.state = PipelineState.REJECTED
                return True
        return False

    def get_pipeline(self, pipeline_id: str) -> Pipeline | None:
        return self._pipelines.get(pipeline_id)

    def list_pipelines(self) -> list[Pipeline]:
        return list(self._pipelines.values())


# ---------------------------------------------------------------------------
# LLM Task — JSON-only LLM Execution
# ---------------------------------------------------------------------------


@dataclass
class LLMTaskConfig:
    """Configuration for an LLM task."""

    task_id: str
    prompt: str
    model: str = ""
    json_schema: dict[str, Any] | None = None
    max_tokens: int = 4096
    temperature: float = 0.0


@dataclass
class LLMTaskResult:
    """Result from an LLM task."""

    task_id: str
    success: bool
    json_output: dict[str, Any] | None = None
    raw_output: str = ""
    error: str = ""
    tokens_used: int = 0


class LLMTaskExtension:
    """Execute structured JSON-only LLM tasks.

    Can run tasks standalone by calling ``execute()`` with an API key
    and base URL, or prepare requests for external execution via
    ``build_request()`` + ``parse_response()``.
    """

    def __init__(self) -> None:
        self._results: dict[str, LLMTaskResult] = {}

    @property
    def name(self) -> str:
        return "llm-task"

    def build_request(self, config: LLMTaskConfig) -> dict[str, Any]:
        messages = [{"role": "user", "content": config.prompt}]
        body: dict[str, Any] = {
            "messages": messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }
        if config.model:
            body["model"] = config.model
        if config.json_schema:
            body["response_format"] = {"type": "json_object"}
        return body

    async def execute(
        self,
        config: LLMTaskConfig,
        *,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
    ) -> LLMTaskResult:
        """Execute an LLM task and return the parsed JSON result."""
        import os

        import httpx

        effective_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not effective_key:
            return LLMTaskResult(
                task_id=config.task_id,
                success=False,
                error="No API key provided",
            )

        body = self.build_request(config)
        url = f"{base_url.rstrip('/')}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {effective_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                tokens = data.get("usage", {}).get("total_tokens", 0)

                result = self.parse_response(config.task_id, content)
                result.tokens_used = tokens
                return result

        except httpx.HTTPError as exc:
            result = LLMTaskResult(
                task_id=config.task_id,
                success=False,
                error=str(exc),
            )
            self._results[config.task_id] = result
            return result

    def parse_response(self, task_id: str, response_text: str) -> LLMTaskResult:
        try:
            parsed = json.loads(response_text)
            result = LLMTaskResult(
                task_id=task_id, success=True, json_output=parsed, raw_output=response_text
            )
        except json.JSONDecodeError:
            result = LLMTaskResult(
                task_id=task_id,
                success=False,
                raw_output=response_text,
                error="Invalid JSON response",
            )
        self._results[task_id] = result
        return result

    def get_result(self, task_id: str) -> LLMTaskResult | None:
        return self._results.get(task_id)


# ---------------------------------------------------------------------------
# Copilot Proxy
# ---------------------------------------------------------------------------


@dataclass
class CopilotProxyConfig:
    """Configuration for the Copilot proxy extension."""

    device_code_url: str = "https://github.com/login/device/code"
    token_url: str = "https://github.com/login/oauth/access_token"
    api_base: str = "https://api.githubcopilot.com"
    client_id: str = ""


class CopilotProxyExtension:
    """Proxy GitHub Copilot as an LLM provider.

    After authentication via ``set_token()``, use ``chat_completion()``
    to send requests through the Copilot API.
    """

    def __init__(self, config: CopilotProxyConfig | None = None) -> None:
        self._config = config or CopilotProxyConfig()
        self._token: str = ""

    @property
    def name(self) -> str:
        return "copilot-proxy"

    @property
    def is_authenticated(self) -> bool:
        return bool(self._token)

    def set_token(self, token: str) -> None:
        self._token = token

    def build_completion_request(
        self, messages: list[dict[str, str]], model: str = ""
    ) -> dict[str, Any]:
        return {
            "url": f"{self._config.api_base}/chat/completions",
            "headers": {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Editor-Version": "pyclaw/1.0",
            },
            "body": {
                "model": model or "gpt-4o",
                "messages": messages,
                "stream": False,
            },
        }

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str = "",
    ) -> dict[str, Any]:
        """Send a chat completion request via the Copilot API."""
        import httpx

        if not self._token:
            raise RuntimeError("Not authenticated — call set_token() first")

        req = self.build_completion_request(messages, model)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                req["url"],
                headers=req["headers"],
                json=req["body"],
            )
            resp.raise_for_status()
            return resp.json()


# ---------------------------------------------------------------------------
# Diagnostics OTEL
# ---------------------------------------------------------------------------


@dataclass
class OTELSpan:
    """A simplified OpenTelemetry span."""

    trace_id: str
    span_id: str
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "OK"

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000 if self.end_time else 0


@dataclass
class OTELConfig:
    """Configuration for OTEL diagnostics export."""

    endpoint: str = ""
    service_name: str = "pyclaw"
    enabled: bool = False


class DiagnosticsOTELExtension:
    """OpenTelemetry diagnostics export extension.

    Records spans locally and exports them to an OTLP-compatible
    HTTP endpoint (e.g. Jaeger, Grafana Tempo, or an OTEL Collector).
    """

    def __init__(self, config: OTELConfig | None = None) -> None:
        self._config = config or OTELConfig()
        self._spans: list[OTELSpan] = []

    @property
    def name(self) -> str:
        return "diagnostics-otel"

    @property
    def enabled(self) -> bool:
        return self._config.enabled and bool(self._config.endpoint)

    def record_span(self, span: OTELSpan) -> None:
        if self._config.enabled:
            self._spans.append(span)

    def start_span(self, name: str, **attributes: Any) -> OTELSpan:
        """Create and record a new span with auto-generated IDs."""
        import hashlib
        import uuid

        trace_id = hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:32]
        span_id = hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16]
        span = OTELSpan(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            start_time=time.time(),
            attributes=attributes,
        )
        self.record_span(span)
        return span

    def end_span(self, span: OTELSpan, status: str = "OK") -> None:
        span.end_time = time.time()
        span.status = status

    def build_export_payload(self) -> dict[str, Any]:
        return {
            "service": self._config.service_name,
            "spans": [
                {
                    "trace_id": s.trace_id,
                    "span_id": s.span_id,
                    "name": s.name,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration_ms": s.duration_ms,
                    "attributes": s.attributes,
                    "status": s.status,
                }
                for s in self._spans
            ],
        }

    async def export(self) -> int:
        """Export pending spans to the configured OTLP endpoint.

        Returns the number of spans successfully exported.
        """
        if not self.enabled or not self._spans:
            return 0

        import httpx

        payload = self.build_export_payload()
        endpoint = self._config.endpoint.rstrip("/")
        url = f"{endpoint}/v1/traces"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code < 300:
                    count = len(self._spans)
                    self._spans.clear()
                    logger.debug("Exported %d spans to %s", count, url)
                    return count
                logger.warning("OTEL export returned %d", resp.status_code)
                return 0
        except httpx.HTTPError as exc:
            logger.debug("OTEL export failed: %s", exc)
            return 0

    def flush(self) -> int:
        count = len(self._spans)
        self._spans.clear()
        return count

    @property
    def pending_count(self) -> int:
        return len(self._spans)
