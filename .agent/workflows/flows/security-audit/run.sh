#!/usr/bin/env bash
set -euo pipefail

FLOW_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$FLOW_DIR/../../.." && pwd)"
STATE_DIR="$FLOW_DIR/state"
LOG_DIR="$FLOW_DIR/logs"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_FILE="$LOG_DIR/run-$(date -u +%Y%m%d-%H%M%S).log"

mkdir -p "$STATE_DIR" "$LOG_DIR"

echo "[$TIMESTAMP] Starting security-audit" | tee "$LOG_FILE"

ISSUES=0

echo "--- Checking for hardcoded secrets ---" | tee -a "$LOG_FILE"
if grep -rn 'sk-[a-zA-Z0-9]\{20,\}' "$PROJECT_DIR/src/" --include="*.py" 2>/dev/null | grep -v __pycache__; then
    echo "WARN: Potential API key found" | tee -a "$LOG_FILE"
    ISSUES=$((ISSUES + 1))
fi

if grep -rn 'PRIVATE KEY' "$PROJECT_DIR/src/" --include="*.py" 2>/dev/null; then
    echo "WARN: Private key reference found" | tee -a "$LOG_FILE"
    ISSUES=$((ISSUES + 1))
fi

echo "--- Auditing dependencies ---" | tee -a "$LOG_FILE"
if command -v pip-audit > /dev/null 2>&1; then
    pip-audit --require-hashes=false 2>&1 | tee -a "$LOG_FILE" || ISSUES=$((ISSUES + 1))
else
    echo "SKIP: pip-audit not installed" | tee -a "$LOG_FILE"
fi

echo "{\"timestamp\": \"$TIMESTAMP\", \"issues_found\": $ISSUES}" > "$STATE_DIR/last-audit.json"

if [ "$ISSUES" -gt 0 ]; then
    echo "WARN: $ISSUES security issue(s) found" | tee -a "$LOG_FILE"
    exit 1
else
    echo "OK: No security issues found" | tee -a "$LOG_FILE"
fi

echo "[$TIMESTAMP] Finished" | tee -a "$LOG_FILE"
