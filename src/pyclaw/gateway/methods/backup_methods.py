"""backup.* — data export/import RPC handlers."""

from __future__ import annotations

import logging
from datetime import UTC
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyclaw.gateway.server import GatewayConnection, MethodHandler

logger = logging.getLogger(__name__)


def create_backup_handlers() -> dict[str, MethodHandler]:
    async def handle_backup_export(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        """Trigger a backup export and return the file path."""
        import json
        import zipfile
        from datetime import datetime

        from pyclaw.config.paths import resolve_state_dir

        state_dir = resolve_state_dir()
        if not state_dir.exists():
            await conn.send_error("backup.export", "no_data", "No pyclaw data found")
            return

        datestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_path = state_dir / f"pyclaw-backup-{datestamp}.zip"

        count = 0
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for pattern in ("*.json", "*.json5"):
                for p in state_dir.glob(pattern):
                    name_lower = p.name.lower()
                    if "credential" not in name_lower and "secret" not in name_lower:
                        zf.write(p, f"config/{p.name}")
                        count += 1

            sessions_dir = state_dir / "sessions"
            if sessions_dir.exists():
                for p in sessions_dir.rglob("*.jsonl"):
                    zf.write(p, f"sessions/{p.relative_to(sessions_dir)}")
                    count += 1

            manifest = {
                "version": 1,
                "createdAt": datetime.now(UTC).isoformat(),
                "files": count,
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        await conn.send_ok(
            "backup.export",
            {
                "path": str(output_path),
                "files": count,
            },
        )

    async def handle_backup_status(params: dict[str, Any] | None, conn: GatewayConnection) -> None:
        from pyclaw.config.paths import resolve_state_dir

        state_dir = resolve_state_dir()
        backups = sorted(state_dir.glob("pyclaw-backup-*.zip"), reverse=True)[:10]
        await conn.send_ok(
            "backup.status",
            {
                "backups": [{"path": str(b), "size": b.stat().st_size} for b in backups],
                "count": len(backups),
            },
        )

    return {
        "backup.export": handle_backup_export,
        "backup.status": handle_backup_status,
    }
