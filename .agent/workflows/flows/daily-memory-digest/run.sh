#!/usr/bin/env bash
set -euo pipefail

FLOW_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR="$FLOW_DIR/state"
LOG_DIR="$FLOW_DIR/logs"
TODAY=$(date -u +%Y-%m-%d)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_FILE="$LOG_DIR/run-$TODAY.log"

mkdir -p "$STATE_DIR" "$LOG_DIR"

echo "[$TIMESTAMP] Starting daily-memory-digest" | tee "$LOG_FILE"

python3 -c "
import asyncio, json, sys
from pathlib import Path

async def main():
    state_file = Path('$STATE_DIR/cursor.json')
    cursor = json.loads(state_file.read_text()) if state_file.exists() else {}

    try:
        from pyclaw.memory.daily_summary import generate_daily_summary
        await generate_daily_summary()
        print('OK: Daily digest generated for $TODAY')
    except ImportError:
        print('SKIP: daily_summary module not available')

    cursor['last_run'] = '$TIMESTAMP'
    cursor['last_date'] = '$TODAY'
    state_file.write_text(json.dumps(cursor, indent=2))

asyncio.run(main())
" 2>&1 | tee -a "$LOG_FILE"

echo "[$TIMESTAMP] Finished" | tee -a "$LOG_FILE"
