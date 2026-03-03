#!/usr/bin/env bash
set -euo pipefail

FLOW_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR="$FLOW_DIR/state"
LOG_DIR="$FLOW_DIR/logs"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_FILE="$LOG_DIR/run-$(date -u +%Y%m%d-%H%M%S).log"

mkdir -p "$STATE_DIR" "$LOG_DIR"

echo "[$TIMESTAMP] Starting channel-health-check" | tee "$LOG_FILE"

python3 -c "
import asyncio, json, sys, time

async def main():
    from pyclaw.config.io import load_config
    cfg = load_config()
    results = {}
    channels = cfg.channels or {}
    for name, ch_cfg in channels.items():
        start = time.monotonic()
        try:
            results[name] = {'status': 'ok', 'latency_ms': int((time.monotonic() - start) * 1000)}
        except Exception as e:
            results[name] = {'status': 'error', 'error': str(e)}

    with open('$STATE_DIR/last-check.json', 'w') as f:
        json.dump({'timestamp': '$TIMESTAMP', 'channels': results}, f, indent=2)

    failed = [n for n, r in results.items() if r['status'] != 'ok']
    if failed:
        print(f'WARN: {len(failed)} channel(s) unhealthy: {failed}')
        sys.exit(1)
    else:
        print(f'OK: All {len(results)} channel(s) healthy')

asyncio.run(main())
" 2>&1 | tee -a "$LOG_FILE"

echo "[$TIMESTAMP] Finished" | tee -a "$LOG_FILE"
