"""Task planner — multi-step plan creation, tracking, and step detection.

Allows the agent to decompose complex tasks into steps, track progress,
pause/resume, and detect step completion through explicit markers,
transition words, or iteration timeouts.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PlanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class StepProgress:
    current: int = 0
    total: int = 0


@dataclass
class Step:
    id: int
    description: str
    status: StepStatus = StepStatus.PENDING
    result: str = ""
    progress: StepProgress = field(default_factory=StepProgress)
    started_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
        }
        if self.result:
            d["result"] = self.result
        if self.progress.total > 0:
            d["progress"] = {"current": self.progress.current, "total": self.progress.total}
        if self.started_at:
            d["startedAt"] = self.started_at
        if self.completed_at:
            d["completedAt"] = self.completed_at
        return d


@dataclass
class Plan:
    id: str
    goal: str
    status: PlanStatus = PlanStatus.PENDING
    steps: list[Step] = field(default_factory=list)
    current_step_index: int = 0
    iteration_count: int = 0
    created_at: float = field(default_factory=time.time)

    @property
    def current_step(self) -> Step | None:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    @property
    def is_complete(self) -> bool:
        return self.status in (PlanStatus.COMPLETED, PlanStatus.FAILED)

    def advance_step(self, result: str = "") -> bool:
        """Mark current step complete and advance to next. Returns False if no more steps."""
        step = self.current_step
        if step:
            step.status = StepStatus.COMPLETED
            step.result = result
            step.completed_at = time.time()

        self.current_step_index += 1
        self.iteration_count = 0

        if self.current_step_index >= len(self.steps):
            self.status = PlanStatus.COMPLETED
            return False

        next_step = self.steps[self.current_step_index]
        next_step.status = StepStatus.RUNNING
        next_step.started_at = time.time()
        return True

    def start(self) -> None:
        """Start the plan, marking the first step as running."""
        self.status = PlanStatus.RUNNING
        if self.steps:
            self.steps[0].status = StepStatus.RUNNING
            self.steps[0].started_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "currentStepIndex": self.current_step_index,
            "iterationCount": self.iteration_count,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        steps = []
        for s in data.get("steps", []):
            prog = s.get("progress", {})
            steps.append(Step(
                id=s["id"],
                description=s["description"],
                status=StepStatus(s.get("status", "pending")),
                result=s.get("result", ""),
                progress=StepProgress(
                    current=prog.get("current", 0),
                    total=prog.get("total", 0),
                ),
                started_at=s.get("startedAt", 0.0),
                completed_at=s.get("completedAt", 0.0),
            ))
        return cls(
            id=data["id"],
            goal=data["goal"],
            status=PlanStatus(data.get("status", "pending")),
            steps=steps,
            current_step_index=data.get("currentStepIndex", 0),
            iteration_count=data.get("iterationCount", 0),
            created_at=data.get("createdAt", time.time()),
        )

    def to_context_string(self) -> str:
        """Generate a compact plan summary for LLM system prompt injection."""
        lines = [f"## Active Plan: {self.goal}"]
        lines.append(f"Status: {self.status.value} | Step {self.current_step_index + 1}/{len(self.steps)}")
        lines.append("")
        for s in self.steps:
            marker = "→" if s.status == StepStatus.RUNNING else ("✓" if s.status == StepStatus.COMPLETED else "○")
            lines.append(f"  {marker} Step {s.id}: {s.description} [{s.status.value}]")
            if s.result:
                lines.append(f"    Result: {s.result[:120]}")
        return "\n".join(lines)

    def generate_progress_summary(self) -> str:
        """Human-readable progress summary."""
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        total = len(self.steps)
        pct = int(completed / total * 100) if total else 0
        current = self.current_step
        current_desc = current.description if current else "—"
        return f"Plan: {self.goal} — {completed}/{total} steps ({pct}%) — Current: {current_desc}"


# ---------------------------------------------------------------------------
# Step Detector
# ---------------------------------------------------------------------------

_DONE_MARKERS = re.compile(
    r"\[(?:done|完成|step\s*done|步骤完成)\]",
    re.IGNORECASE,
)

_TRANSITION_WORDS = re.compile(
    r"(?:^|\n)\s*(?:now|next|then|接下来|现在|然后|continue|moving\s+on|下一步)",
    re.IGNORECASE,
)


class StepDetector:
    """Detect step completion from LLM output."""

    def __init__(self, *, max_iterations_per_step: int = 5) -> None:
        self.max_iterations_per_step = max_iterations_per_step

    def is_step_complete(self, text: str, iteration_count: int) -> bool:
        """Return True if the current step appears complete."""
        if _DONE_MARKERS.search(text):
            return True
        if _TRANSITION_WORDS.search(text):
            return True
        if iteration_count >= self.max_iterations_per_step:
            return True
        return False


_STEP_DECL = re.compile(
    r"\[Step(?:\s+\d+)?]\s*(.+)",
    re.IGNORECASE,
)


def extract_step_declarations(text: str) -> list[str]:
    """Extract ``[Step] description`` declarations from LLM output."""
    return [m.group(1).strip() for m in _STEP_DECL.finditer(text)]


_CONTINUE_INTENT = re.compile(
    r"^(?:继续|接着|go\s+on|continue|keep\s+going|proceed)$",
    re.IGNORECASE,
)


def is_continue_intent(message: str) -> bool:
    """Check if a user message indicates they want to resume a paused plan."""
    return bool(_CONTINUE_INTENT.match(message.strip()))


# ---------------------------------------------------------------------------
# Plan Manager
# ---------------------------------------------------------------------------

class PlanManager:
    """Manage plans with in-memory cache and file persistence."""

    def __init__(self, workspace: Path | None = None) -> None:
        self._workspace = workspace
        self._plans: dict[str, Plan] = {}

    def get(self, plan_id: str) -> Plan | None:
        if plan_id in self._plans:
            return self._plans[plan_id]
        plan = self._load_from_disk(plan_id)
        if plan:
            self._plans[plan_id] = plan
        return plan

    def get_for_session(self, session_key: str) -> Plan | None:
        """Get the active plan for a session (session_key == plan_id convention)."""
        return self.get(session_key)

    def save(self, plan: Plan) -> None:
        self._plans[plan.id] = plan
        self._persist_to_disk(plan)

    def create(
        self,
        plan_id: str,
        goal: str,
        step_descriptions: list[str],
    ) -> Plan:
        steps = [
            Step(id=i + 1, description=desc)
            for i, desc in enumerate(step_descriptions)
        ]
        plan = Plan(id=plan_id, goal=goal, steps=steps)
        self.save(plan)
        return plan

    def delete(self, plan_id: str) -> bool:
        removed = self._plans.pop(plan_id, None) is not None
        if self._workspace:
            path = self._plan_path(plan_id)
            if path.exists():
                path.unlink()
                removed = True
        return removed

    def list_plans(self) -> list[Plan]:
        return list(self._plans.values())

    def _plan_path(self, plan_id: str) -> Path:
        assert self._workspace
        safe = plan_id.replace("/", "_").replace("\\", "_")
        return self._workspace / ".sessions" / safe / "plan.json"

    def _persist_to_disk(self, plan: Plan) -> None:
        if not self._workspace:
            return
        path = self._plan_path(plan.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_from_disk(self, plan_id: str) -> Plan | None:
        if not self._workspace:
            return None
        path = self._plan_path(plan_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Plan.from_dict(data)
        except Exception:
            logger.warning("Failed to load plan %s", plan_id)
            return None
