"""Config and state migration framework — version detection and auto-migration.

Ported from ``src/config/migrations/`` and ``src/infra/state-migrations/``.

Provides:
- Config version detection from ``$schema`` or ``version`` fields
- Ordered migration steps with rollback metadata
- State migration for session/pairing/agent stores
- Dry-run mode for previewing changes
"""

from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class MigrationStep:
    """A single migration step."""

    id: str
    from_version: str
    to_version: str
    description: str
    migrate: Callable[[dict[str, Any]], dict[str, Any]]
    rollback: Callable[[dict[str, Any]], dict[str, Any]] | None = None


@dataclass
class MigrationResult:
    """Result of a migration run."""

    success: bool
    from_version: str
    to_version: str
    steps_applied: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False
    duration_ms: float = 0.0


def detect_config_version(config: dict[str, Any]) -> str:
    """Detect the config version from schema or version fields."""
    # $schema field (e.g. "https://openclaw.ai/config/v2")
    schema = config.get("$schema", "")
    if schema:
        parts = schema.rstrip("/").split("/")
        for part in reversed(parts):
            if part.startswith("v") and part[1:].isdigit():
                return str(part)
        return "v1"

    # Explicit version
    version = config.get("version", config.get("configVersion", ""))
    if version:
        return str(version) if str(version).startswith("v") else f"v{version}"

    # Heuristic: check for v2-style keys
    if "agents" in config and isinstance(config.get("agents"), dict):
        return "v2"

    return "v1"


def detect_state_version(state: dict[str, Any]) -> str:
    """Detect the state file version."""
    return str(state.get("version", state.get("stateVersion", "1")))


class ConfigMigrationRegistry:
    """Registry of config migration steps, executed in order."""

    def __init__(self) -> None:
        self._steps: list[MigrationStep] = []

    def register(self, step: MigrationStep) -> None:
        """Register a migration step."""
        self._steps.append(step)
        self._steps.sort(key=lambda s: s.from_version)

    def get_path(self, from_version: str, to_version: str) -> list[MigrationStep]:
        """Get the ordered list of steps to migrate between versions."""
        path: list[MigrationStep] = []
        current = from_version

        for step in self._steps:
            if step.from_version == current:
                path.append(step)
                current = step.to_version
                if current == to_version:
                    break

        return path

    def migrate(
        self,
        config: dict[str, Any],
        *,
        target_version: str = "",
        dry_run: bool = False,
    ) -> MigrationResult:
        """Run migrations on a config dict.

        Args:
            config: The config to migrate (modified in-place unless dry_run).
            target_version: Target version. Empty = latest.
            dry_run: If True, return what would change without modifying config.
        """
        start = time.time()
        current = detect_config_version(config)

        if not target_version and self._steps:
            target_version = self._steps[-1].to_version

        if current == target_version:
            return MigrationResult(
                success=True,
                from_version=current,
                to_version=current,
                dry_run=dry_run,
            )

        path = self.get_path(current, target_version)
        if not path:
            return MigrationResult(
                success=False,
                from_version=current,
                to_version=target_version,
                errors=[f"No migration path from {current} to {target_version}"],
                dry_run=dry_run,
            )

        working = copy.deepcopy(config) if dry_run else config
        steps_applied: list[str] = []
        errors: list[str] = []

        for step in path:
            try:
                working = step.migrate(working)
                steps_applied.append(step.id)
                logger.info("Migration applied: %s (%s → %s)", step.id, step.from_version, step.to_version)
            except Exception as exc:
                errors.append(f"Step {step.id} failed: {exc}")
                logger.error("Migration failed: %s — %s", step.id, exc)
                break

        if not dry_run and not errors:
            config.clear()
            config.update(working)

        elapsed = (time.time() - start) * 1000

        return MigrationResult(
            success=len(errors) == 0,
            from_version=current,
            to_version=path[-1].to_version if steps_applied else current,
            steps_applied=steps_applied,
            errors=errors,
            dry_run=dry_run,
            duration_ms=elapsed,
        )

    @property
    def step_count(self) -> int:
        return len(self._steps)


# ---------------------------------------------------------------------------
# Built-in migrations
# ---------------------------------------------------------------------------

def _migrate_v1_to_v2(config: dict[str, Any]) -> dict[str, Any]:
    """Migrate config from v1 to v2 format.

    v2 changes:
    - ``allowFrom`` → nested under channel configs
    - ``model`` → ``agents.default.model``
    - Adds ``version: "v2"``
    """
    result = dict(config)

    # Move top-level model to agents
    if "model" in result and "agents" not in result:
        model = result.pop("model")
        result["agents"] = {"default": {"model": model}}

    # Move top-level allowFrom into channel defaults
    if "allowFrom" in result:
        allow_from = result.pop("allowFrom")
        channels = result.setdefault("channels", {})
        defaults = channels.setdefault("defaults", {})
        defaults.setdefault("allowFrom", allow_from)

    # Move top-level systemPrompt
    if "systemPrompt" in result:
        prompt = result.pop("systemPrompt")
        agents = result.setdefault("agents", {})
        default_agent = agents.setdefault("default", {})
        default_agent.setdefault("systemPrompt", prompt)

    result["version"] = "v2"
    return result


def _migrate_v2_to_v3(config: dict[str, Any]) -> dict[str, Any]:
    """Migrate config from v2 to v3.

    v3 changes:
    - ``gateway.authToken`` → ``gateway.token``
    - ``exec.security`` → ``exec.approval``
    - Adds ``version: "v3"``
    """
    result = dict(config)

    # Rename gateway auth
    gateway = result.get("gateway", {})
    if "authToken" in gateway:
        gateway["token"] = gateway.pop("authToken")

    # Rename exec security
    exec_cfg = result.get("exec", {})
    if "security" in exec_cfg:
        exec_cfg["approval"] = exec_cfg.pop("security")

    result["version"] = "v3"
    return result


def create_default_registry() -> ConfigMigrationRegistry:
    """Create a registry with built-in migrations."""
    registry = ConfigMigrationRegistry()

    registry.register(MigrationStep(
        id="config-v1-to-v2",
        from_version="v1",
        to_version="v2",
        description="Restructure to nested agents/channels format",
        migrate=_migrate_v1_to_v2,
    ))

    registry.register(MigrationStep(
        id="config-v2-to-v3",
        from_version="v2",
        to_version="v3",
        description="Rename gateway.authToken and exec.security",
        migrate=_migrate_v2_to_v3,
    ))

    return registry


# ---------------------------------------------------------------------------
# State migrations
# ---------------------------------------------------------------------------

class StateMigrationRegistry:
    """Registry for state file migrations (sessions, pairing, etc.)."""

    def __init__(self) -> None:
        self._steps: list[MigrationStep] = []

    def register(self, step: MigrationStep) -> None:
        self._steps.append(step)
        self._steps.sort(key=lambda s: s.from_version)

    def migrate(self, state: dict[str, Any], *, target_version: str = "") -> MigrationResult:
        """Migrate a state dict to the target version."""
        start = time.time()
        current = detect_state_version(state)

        if not target_version and self._steps:
            target_version = self._steps[-1].to_version

        if current == target_version:
            return MigrationResult(success=True, from_version=current, to_version=current)

        steps_applied: list[str] = []
        errors: list[str] = []
        working = state

        for step in self._steps:
            if step.from_version == current:
                try:
                    working = step.migrate(working)
                    steps_applied.append(step.id)
                    current = step.to_version
                    if current == target_version:
                        break
                except Exception as exc:
                    errors.append(f"Step {step.id} failed: {exc}")
                    break

        if not errors:
            state.clear()
            state.update(working)

        return MigrationResult(
            success=len(errors) == 0,
            from_version=detect_state_version(state),
            to_version=current,
            steps_applied=steps_applied,
            errors=errors,
            duration_ms=(time.time() - start) * 1000,
        )
