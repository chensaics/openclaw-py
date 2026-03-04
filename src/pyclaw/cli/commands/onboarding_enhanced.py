"""Enhanced onboarding — interactive + non-interactive modes, full flow.

Ported from ``src/commands/onboard*.ts``.

Provides:
- Interactive onboarding (step-by-step wizard)
- Non-interactive onboarding (headless/CI mode)
- Risk acknowledgment step
- Gateway configuration
- Provider authentication selection
- Skills installation
- Completion/finalization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class OnboardingMode(str, Enum):
    INTERACTIVE = "interactive"
    NON_INTERACTIVE = "non_interactive"
    RESUME = "resume"


class OnboardingStep(str, Enum):
    RISK_ACK = "risk_ack"
    GATEWAY_CONFIG = "gateway_config"
    AUTH_SELECT = "auth_select"
    PROVIDER_AUTH = "provider_auth"
    SKILLS_INSTALL = "skills_install"
    CHANNELS_SETUP = "channels_setup"
    FINALIZE = "finalize"
    COMPLETE = "complete"


@dataclass
class OnboardingState:
    """Persistent state for an onboarding session."""

    mode: OnboardingMode = OnboardingMode.INTERACTIVE
    current_step: OnboardingStep = OnboardingStep.RISK_ACK
    completed_steps: list[str] = field(default_factory=list)
    selected_provider: str = ""
    gateway_port: int = 18789
    gateway_bind: str = "loopback"
    skills_installed: list[str] = field(default_factory=list)
    channels_configured: list[str] = field(default_factory=list)
    risk_acknowledged: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.current_step == OnboardingStep.COMPLETE

    @property
    def progress_pct(self) -> int:
        all_steps = list(OnboardingStep)
        idx = all_steps.index(self.current_step)
        return int((idx / max(len(all_steps) - 1, 1)) * 100)


@dataclass
class StepResult:
    """Result from executing a single onboarding step."""

    step: OnboardingStep
    success: bool
    message: str = ""
    next_step: OnboardingStep | None = None
    data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Step Handlers
# ---------------------------------------------------------------------------


def handle_risk_ack(state: OnboardingState, *, acknowledged: bool = False) -> StepResult:
    """Handle risk acknowledgment step."""
    if not acknowledged:
        return StepResult(
            step=OnboardingStep.RISK_ACK,
            success=False,
            message="Risk acknowledgment required before proceeding",
            data={"prompt": "pyclaw can execute commands on your system. Do you understand and accept the risks?"},
        )
    state.risk_acknowledged = True
    state.completed_steps.append(OnboardingStep.RISK_ACK.value)
    return StepResult(
        step=OnboardingStep.RISK_ACK,
        success=True,
        message="Risk acknowledged",
        next_step=OnboardingStep.GATEWAY_CONFIG,
    )


def handle_gateway_config(
    state: OnboardingState,
    *,
    port: int = 18789,
    bind: str = "loopback",
) -> StepResult:
    """Handle gateway configuration step."""
    state.gateway_port = port
    state.gateway_bind = bind
    state.completed_steps.append(OnboardingStep.GATEWAY_CONFIG.value)
    return StepResult(
        step=OnboardingStep.GATEWAY_CONFIG,
        success=True,
        message=f"Gateway configured: bind={bind}, port={port}",
        next_step=OnboardingStep.AUTH_SELECT,
    )


def handle_auth_select(
    state: OnboardingState,
    *,
    provider: str = "",
) -> StepResult:
    """Handle provider auth selection step."""
    if not provider:
        from pyclaw.cli.commands.auth_providers import list_available_providers

        providers = list_available_providers()
        return StepResult(
            step=OnboardingStep.AUTH_SELECT,
            success=False,
            message="Select an LLM provider",
            data={"providers": providers},
        )
    state.selected_provider = provider
    state.completed_steps.append(OnboardingStep.AUTH_SELECT.value)
    return StepResult(
        step=OnboardingStep.AUTH_SELECT,
        success=True,
        message=f"Provider selected: {provider}",
        next_step=OnboardingStep.PROVIDER_AUTH,
    )


def handle_provider_auth(
    state: OnboardingState,
    *,
    api_key: str = "",
) -> StepResult:
    """Handle provider authentication step."""
    if not api_key:
        from pyclaw.cli.commands.auth_providers import get_provider_auth_info

        info = get_provider_auth_info(state.selected_provider)
        return StepResult(
            step=OnboardingStep.PROVIDER_AUTH,
            success=False,
            message=f"Enter API key for {state.selected_provider}",
            data={"provider_info": info},
        )

    from pyclaw.cli.commands.auth_providers import apply_api_key_auth

    result = apply_api_key_auth(state.selected_provider, api_key)
    if not result.success:
        return StepResult(
            step=OnboardingStep.PROVIDER_AUTH,
            success=False,
            message=result.error,
        )

    state.completed_steps.append(OnboardingStep.PROVIDER_AUTH.value)
    return StepResult(
        step=OnboardingStep.PROVIDER_AUTH,
        success=True,
        message=f"Authenticated with {state.selected_provider}",
        next_step=OnboardingStep.SKILLS_INSTALL,
    )


def handle_skills_install(
    state: OnboardingState,
    *,
    skills: list[str] | None = None,
    skip: bool = False,
) -> StepResult:
    """Handle skills installation step."""
    if skip:
        state.completed_steps.append(OnboardingStep.SKILLS_INSTALL.value)
        return StepResult(
            step=OnboardingStep.SKILLS_INSTALL,
            success=True,
            message="Skills installation skipped",
            next_step=OnboardingStep.FINALIZE,
        )

    installed = skills or []
    state.skills_installed = installed
    state.completed_steps.append(OnboardingStep.SKILLS_INSTALL.value)
    return StepResult(
        step=OnboardingStep.SKILLS_INSTALL,
        success=True,
        message=f"Installed {len(installed)} skill(s)",
        next_step=OnboardingStep.FINALIZE,
    )


def handle_finalize(state: OnboardingState) -> StepResult:
    """Handle finalization step."""
    state.current_step = OnboardingStep.COMPLETE
    state.completed_steps.append(OnboardingStep.FINALIZE.value)
    return StepResult(
        step=OnboardingStep.FINALIZE,
        success=True,
        message="Onboarding complete! Run 'pyclaw gateway run' to start.",
        next_step=OnboardingStep.COMPLETE,
        data={
            "provider": state.selected_provider,
            "gateway_port": state.gateway_port,
            "skills": state.skills_installed,
        },
    )


# ---------------------------------------------------------------------------
# Non-Interactive Flow
# ---------------------------------------------------------------------------


def run_non_interactive(
    *,
    provider: str,
    api_key: str,
    port: int = 18789,
    bind: str = "loopback",
    skills: list[str] | None = None,
) -> OnboardingState:
    """Run the full onboarding flow non-interactively."""
    state = OnboardingState(mode=OnboardingMode.NON_INTERACTIVE)

    handle_risk_ack(state, acknowledged=True)
    state.current_step = OnboardingStep.GATEWAY_CONFIG

    handle_gateway_config(state, port=port, bind=bind)
    state.current_step = OnboardingStep.AUTH_SELECT

    handle_auth_select(state, provider=provider)
    state.current_step = OnboardingStep.PROVIDER_AUTH

    result = handle_provider_auth(state, api_key=api_key)
    if not result.success:
        state.errors.append(result.message)
        return state

    state.current_step = OnboardingStep.SKILLS_INSTALL
    handle_skills_install(state, skills=skills, skip=not skills)

    state.current_step = OnboardingStep.FINALIZE
    handle_finalize(state)

    return state
