#!/usr/bin/env bash
set -euo pipefail

FLOW_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$FLOW_DIR/../../.." && pwd)"
STATE_DIR="$FLOW_DIR/state"
LOG_DIR="$FLOW_DIR/logs"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_FILE="$LOG_DIR/run-$(date -u +%Y%m%d-%H%M%S).log"

mkdir -p "$STATE_DIR" "$LOG_DIR"

echo "[$TIMESTAMP] Starting dependency-check" | tee "$LOG_FILE"

echo "--- Checking outdated packages ---" | tee -a "$LOG_FILE"
OUTDATED=$(pip list --outdated --format=json 2>/dev/null || echo "[]")
OUTDATED_COUNT=$(echo "$OUTDATED" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
echo "Found $OUTDATED_COUNT outdated package(s)" | tee -a "$LOG_FILE"

echo "--- Checking vulnerabilities ---" | tee -a "$LOG_FILE"
VULN_COUNT=0
if command -v pip-audit > /dev/null 2>&1; then
    AUDIT_OUTPUT=$(pip-audit --format=json --require-hashes=false 2>/dev/null || echo "{}")
    VULN_COUNT=$(echo "$AUDIT_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
deps = data.get('dependencies', [])
print(sum(1 for d in deps if d.get('vulns')))
" 2>/dev/null || echo "0")
    echo "Found $VULN_COUNT vulnerable package(s)" | tee -a "$LOG_FILE"
else
    echo "SKIP: pip-audit not installed" | tee -a "$LOG_FILE"
fi

python3 -c "
import json
result = {
    'timestamp': '$TIMESTAMP',
    'outdated_count': int('$OUTDATED_COUNT'),
    'vulnerable_count': int('$VULN_COUNT'),
}
with open('$STATE_DIR/dependency-status.json', 'w') as f:
    json.dump(result, f, indent=2)
print(f'Status: {result[chr(34)+chr(111)+chr(117)+chr(116)+chr(100)+chr(97)+chr(116)+chr(101)+chr(100)+chr(95)+chr(99)+chr(111)+chr(117)+chr(110)+chr(116)+chr(34)]} outdated, {result[chr(34)+chr(118)+chr(117)+chr(108)+chr(110)+chr(101)+chr(114)+chr(97)+chr(98)+chr(108)+chr(101)+chr(95)+chr(99)+chr(111)+chr(117)+chr(110)+chr(116)+chr(34)]} vulnerable')
"

echo "[$TIMESTAMP] Finished" | tee -a "$LOG_FILE"
