"""plan.* — task plan management RPC handlers."""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)


def create_plan_handlers() -> dict[str, "MethodHandler"]:

    async def handle_plan_list(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        from pyclaw.agents.planner import PlanManager
        from pyclaw.config.paths import resolve_state_dir

        workspace = resolve_state_dir()
        mgr = PlanManager(workspace)
        plans = mgr.list_plans()
        await conn.send_ok("plan.list", {
            "plans": [p.to_dict() for p in plans],
            "count": len(plans),
        })

    async def handle_plan_get(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        if not params or "planId" not in params:
            await conn.send_error("plan.get", "invalid_params", "Missing 'planId'")
            return

        from pyclaw.agents.planner import PlanManager
        from pyclaw.config.paths import resolve_state_dir

        workspace = resolve_state_dir()
        mgr = PlanManager(workspace)
        plan = mgr.get(params["planId"])
        if not plan:
            await conn.send_error("plan.get", "not_found", "Plan not found")
            return

        await conn.send_ok("plan.get", plan.to_dict())

    async def handle_plan_resume(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        if not params or "planId" not in params:
            await conn.send_error("plan.resume", "invalid_params", "Missing 'planId'")
            return

        from pyclaw.agents.planner import PlanManager, PlanStatus
        from pyclaw.config.paths import resolve_state_dir

        workspace = resolve_state_dir()
        mgr = PlanManager(workspace)
        plan = mgr.get(params["planId"])
        if not plan:
            await conn.send_error("plan.resume", "not_found", "Plan not found")
            return

        if plan.status == PlanStatus.PAUSED:
            plan.status = PlanStatus.RUNNING
            mgr.save(plan)
            await conn.send_ok("plan.resume", {"resumed": True, "plan": plan.to_dict()})
        else:
            await conn.send_ok("plan.resume", {
                "resumed": False,
                "reason": f"Plan status is {plan.status.value}, not paused",
            })

    async def handle_plan_delete(
        params: dict[str, Any] | None, conn: "GatewayConnection"
    ) -> None:
        if not params or "planId" not in params:
            await conn.send_error("plan.delete", "invalid_params", "Missing 'planId'")
            return

        from pyclaw.agents.planner import PlanManager
        from pyclaw.config.paths import resolve_state_dir

        workspace = resolve_state_dir()
        mgr = PlanManager(workspace)
        deleted = mgr.delete(params["planId"])
        await conn.send_ok("plan.delete", {"deleted": deleted})

    return {
        "plan.list": handle_plan_list,
        "plan.get": handle_plan_get,
        "plan.resume": handle_plan_resume,
        "plan.delete": handle_plan_delete,
    }
