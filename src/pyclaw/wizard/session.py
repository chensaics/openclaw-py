"""Wizard session — multi-step session state, prompt wrappers, shell completion, finalization.

Ported from ``src/commands/wizard*.ts`` and ``src/commands/setup*.ts``.

Provides:
- Wizard session state machine
- Clack-style prompt wrappers for step rendering
- Shell completion setup helpers
- Gateway configuration guidance
- Wizard finalization (summary and next steps)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyclaw.constants.runtime import DEFAULT_GATEWAY_PORT

logger = logging.getLogger(__name__)


class WizardState(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class StepStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class WizardStep:
    """A step in the wizard flow."""

    step_id: str
    title: str
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    answer: Any = None
    error: str = ""
    skippable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_done(self) -> bool:
        return self.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)


@dataclass
class WizardSession:
    """State for a multi-step wizard."""

    session_id: str
    wizard_type: str = "setup"
    state: WizardState = WizardState.NOT_STARTED
    steps: list[WizardStep] = field(default_factory=list)
    current_step_idx: int = 0
    created_at: float = 0.0
    completed_at: float = 0.0
    collected_config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at == 0:
            self.created_at = time.time()

    @property
    def current_step(self) -> WizardStep | None:
        if 0 <= self.current_step_idx < len(self.steps):
            return self.steps[self.current_step_idx]
        return None

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps if s.is_done)
        return done / len(self.steps)

    @property
    def is_complete(self) -> bool:
        return self.state == WizardState.COMPLETED

    def advance(self) -> WizardStep | None:
        """Mark current step completed and move to next."""
        current = self.current_step
        if current and current.status != StepStatus.SKIPPED:
            current.status = StepStatus.COMPLETED

        self.current_step_idx += 1
        if self.current_step_idx >= len(self.steps):
            self.state = WizardState.COMPLETED
            self.completed_at = time.time()
            return None

        next_step = self.steps[self.current_step_idx]
        next_step.status = StepStatus.ACTIVE
        return next_step

    def skip_current(self) -> WizardStep | None:
        """Skip the current step if skippable."""
        current = self.current_step
        if current and current.skippable:
            current.status = StepStatus.SKIPPED
            return self.advance()
        return current

    def set_answer(self, value: Any) -> None:
        """Set the answer for the current step."""
        current = self.current_step
        if current:
            current.answer = value
            if current.step_id:
                self.collected_config[current.step_id] = value

    def cancel(self) -> None:
        self.state = WizardState.CANCELLED

    def start(self) -> WizardStep | None:
        """Start the wizard, activating the first step."""
        self.state = WizardState.IN_PROGRESS
        if self.steps:
            self.steps[0].status = StepStatus.ACTIVE
            return self.steps[0]
        self.state = WizardState.COMPLETED
        return None


# ---------------------------------------------------------------------------
# Clack-style prompt wrappers
# ---------------------------------------------------------------------------


@dataclass
class PromptOption:
    """An option for a select prompt."""

    value: str
    label: str
    hint: str = ""


def format_intro(title: str) -> str:
    """Format a wizard intro banner."""
    bar = "─" * (len(title) + 4)
    return f"┌{bar}┐\n│  {title}  │\n└{bar}┘"


def format_step_header(step: WizardStep, idx: int, total: int) -> str:
    """Format a step header for display."""
    return f"◆  Step {idx + 1}/{total}: {step.title}"


def format_step_description(step: WizardStep) -> str:
    if not step.description:
        return ""
    return f"│  {step.description}"


def format_summary(config: dict[str, Any]) -> str:
    """Format collected configuration as a summary."""
    lines = ["┌─ Configuration Summary ─┐"]
    for key, value in config.items():
        display = str(value)
        if len(display) > 50:
            display = display[:47] + "..."
        lines.append(f"│  {key}: {display}")
    lines.append("└" + "─" * 25 + "┘")
    return "\n".join(lines)


def format_completion(wizard_type: str) -> str:
    """Format a wizard completion message."""
    return f"✔  {wizard_type.title()} wizard completed successfully!"


# ---------------------------------------------------------------------------
# Shell completion setup
# ---------------------------------------------------------------------------


def generate_bash_completion(binary_name: str = "pyclaw") -> str:
    """Generate bash completion script."""
    return f"""# {binary_name} bash completion
_{binary_name}_completions() {{
    local cur="${{COMP_WORDS[COMP_CWORD]}}"
    local commands="gateway agent config channels models status doctor send login"
    COMPREPLY=($(compgen -W "$commands" -- "$cur"))
}}
complete -F _{binary_name}_completions {binary_name}
"""


def generate_zsh_completion(binary_name: str = "pyclaw") -> str:
    """Generate zsh completion script."""
    return f"""#compdef {binary_name}
_arguments \\
  '1:command:(gateway agent config channels models status doctor send login)' \\
  '*::arg:->args'
"""


def generate_fish_completion(binary_name: str = "pyclaw") -> str:
    """Generate fish completion script."""
    commands = ["gateway", "agent", "config", "channels", "models", "status", "doctor", "send", "login"]
    lines = [f"# {binary_name} fish completion"]
    for cmd in commands:
        lines.append(f"complete -c {binary_name} -n '__fish_use_subcommand' -a '{cmd}'")
    return "\n".join(lines)


SHELL_COMPLETIONS: dict[str, Any] = {
    "bash": generate_bash_completion,
    "zsh": generate_zsh_completion,
    "fish": generate_fish_completion,
}


# ---------------------------------------------------------------------------
# Gateway configuration guidance
# ---------------------------------------------------------------------------


@dataclass
class GatewaySetupGuide:
    """Gateway setup guidance steps."""

    mode: str = "local"  # local | remote
    bind: str = "loopback"
    port: int = DEFAULT_GATEWAY_PORT
    auto_start: bool = True

    def to_config_dict(self) -> dict[str, Any]:
        return {
            "gateway": {
                "mode": self.mode,
                "bind": self.bind,
                "port": self.port,
            }
        }

    def to_run_command(self) -> str:
        return f"pyclaw gateway run --bind {self.bind} --port {self.port}"


# ---------------------------------------------------------------------------
# Setup wizard factory
# ---------------------------------------------------------------------------


def create_setup_wizard(session_id: str = "") -> WizardSession:
    """Create the initial setup wizard."""
    return WizardSession(
        session_id=session_id or f"setup-{int(time.time())}",
        wizard_type="setup",
        steps=[
            WizardStep("provider", "LLM Provider", "Choose your AI provider"),
            WizardStep("api_key", "API Key", "Enter your API key", metadata={"sensitive": True}),
            WizardStep("model", "Default Model", "Choose your default model", skippable=True),
            WizardStep("channel", "Messaging Channel", "Set up a messaging channel (optional)", skippable=True),
            WizardStep("gateway", "Gateway Mode", "Configure the gateway", skippable=True),
            WizardStep("confirm", "Confirm", "Review and save configuration"),
        ],
    )


def create_channel_wizard(channel_type: str, session_id: str = "") -> WizardSession:
    """Create a channel-specific setup wizard."""
    return WizardSession(
        session_id=session_id or f"channel-{channel_type}-{int(time.time())}",
        wizard_type=f"channel-{channel_type}",
        steps=[
            WizardStep("info", "Channel Info", f"Setting up {channel_type}"),
            WizardStep("credentials", "Credentials", f"Enter {channel_type} credentials"),
            WizardStep("options", "Options", "Configure channel options", skippable=True),
            WizardStep("confirm", "Confirm", "Save channel configuration"),
        ],
    )
