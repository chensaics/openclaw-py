"""Secrets plan types — plan structure for secrets apply workflow.

Ported from ``src/secrets/plan.ts``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pyclaw.config.secrets import SecretRef


@dataclass
class SecretProviderSetup:
    """Configuration for a secret provider in the plan."""

    kind: Literal["env", "file", "exec"]
    env_prefix: str | None = None
    file_path: str | None = None
    exec_command: str | None = None
    exec_args: list[str] = field(default_factory=list)


@dataclass
class SecretsPlanTarget:
    """A single target for secrets apply — a config path that should use a SecretRef."""

    path: str  # JSON path, e.g. "models.providers.openai.apiKey"
    ref: SecretRef
    current_value: str | None = None
    expected_type: str = "string"  # "string" | "string-or-object"
    provider_id: str | None = None


@dataclass
class SecretsApplyPlan:
    """Plan describing how to apply secrets to the config."""

    targets: list[SecretsPlanTarget] = field(default_factory=list)
    providers: dict[str, SecretProviderSetup] = field(default_factory=dict)
    scrub_env: bool = False
    scrub_legacy: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "targets": [
                {
                    "path": t.path,
                    "ref": {"source": t.ref.source, "provider": t.ref.provider, "id": t.ref.id},
                    "currentValue": t.current_value,
                    "expectedType": t.expected_type,
                    "providerId": t.provider_id,
                }
                for t in self.targets
            ],
            "providers": {
                k: {
                    "kind": v.kind,
                    **({"envPrefix": v.env_prefix} if v.env_prefix else {}),
                    **({"filePath": v.file_path} if v.file_path else {}),
                    **({"execCommand": v.exec_command} if v.exec_command else {}),
                }
                for k, v in self.providers.items()
            },
            "scrubEnv": self.scrub_env,
            "scrubLegacy": self.scrub_legacy,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SecretsApplyPlan:
        targets = []
        for t in data.get("targets", []):
            ref_data = t.get("ref", {})
            targets.append(
                SecretsPlanTarget(
                    path=t.get("path", ""),
                    ref=SecretRef(
                        source=ref_data.get("source", "env"),
                        provider=ref_data.get("provider", "default"),
                        id=ref_data.get("id", ""),
                    ),
                    current_value=t.get("currentValue"),
                    expected_type=t.get("expectedType", "string"),
                    provider_id=t.get("providerId"),
                )
            )
        providers = {}
        for k, v in data.get("providers", {}).items():
            providers[k] = SecretProviderSetup(
                kind=v.get("kind", "env"),
                env_prefix=v.get("envPrefix"),
                file_path=v.get("filePath"),
                exec_command=v.get("execCommand"),
            )
        return cls(
            targets=targets,
            providers=providers,
            scrub_env=data.get("scrubEnv", False),
            scrub_legacy=data.get("scrubLegacy", False),
        )
