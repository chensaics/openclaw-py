"""External secrets management — audit, configure, apply, reload.

Ported from ``src/secrets/``.
"""

from pyclaw.secrets.audit import run_secrets_audit, SecretsAuditReport
from pyclaw.secrets.resolve import resolve_secret_ref_value, SecretRefResolveCache
from pyclaw.secrets.plan import SecretsApplyPlan, SecretsPlanTarget
from pyclaw.secrets.apply import run_secrets_apply
from pyclaw.secrets.runtime import SecretsRuntime

__all__ = [
    "SecretRefResolveCache",
    "SecretsApplyPlan",
    "SecretsAuditReport",
    "SecretsPlanTarget",
    "SecretsRuntime",
    "resolve_secret_ref_value",
    "run_secrets_apply",
    "run_secrets_audit",
]
