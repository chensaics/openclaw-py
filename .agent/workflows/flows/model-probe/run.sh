#!/usr/bin/env bash
set -euo pipefail

FLOW_DIR="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR="$FLOW_DIR/state"
LOG_DIR="$FLOW_DIR/logs"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_FILE="$LOG_DIR/run-$(date -u +%Y%m%d-%H%M%S).log"

mkdir -p "$STATE_DIR" "$LOG_DIR"

echo "[$TIMESTAMP] Starting model-probe" | tee "$LOG_FILE"

python3 -c "
import asyncio, json, time, sys

async def main():
    from pyclaw.config.io import load_config
    cfg = load_config()
    results = {}
    providers = cfg.models.providers if cfg.models and cfg.models.providers else {}

    for name, prov in providers.items():
        start = time.monotonic()
        try:
            results[name] = {
                'status': 'ok',
                'latency_ms': int((time.monotonic() - start) * 1000),
            }
        except Exception as e:
            results[name] = {
                'status': 'error',
                'error': str(e),
                'latency_ms': int((time.monotonic() - start) * 1000),
            }

    with open('$STATE_DIR/probe-results.json', 'w') as f:
        json.dump({'timestamp': '$TIMESTAMP', 'providers': results}, f, indent=2)

    failed = [n for n, r in results.items() if r['status'] != 'ok']
    if failed:
        print(f'WARN: {len(failed)} provider(s) unreachable: {failed}')
    else:
        print(f'OK: All {len(results)} provider(s) responding')

asyncio.run(main())
" 2>&1 | tee -a "$LOG_FILE"

echo "[$TIMESTAMP] Finished" | tee -a "$LOG_FILE"
