"""cron.history — execution history RPC handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)


def create_cron_history_handlers() -> dict[str, MethodHandler]:
    async def handle_cron_history(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        from pyclaw.config.paths import resolve_state_dir
        from pyclaw.cron.history import HistoryStore

        persist_path = resolve_state_dir() / "cron_history.json"
        store = HistoryStore(persist_path=persist_path)

        p = params or {}
        job_id = p.get("jobId")
        limit = min(int(p.get("limit", 50)), 200)

        records = store.list_for_job(job_id, limit=limit) if job_id else store.list_recent(limit=limit)

        await conn.send_ok(
            "cron.history",
            {
                "records": [r.to_dict() for r in records],
                "count": len(records),
            },
        )

    return {
        "cron.history": handle_cron_history,
    }
