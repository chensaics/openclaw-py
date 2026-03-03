# Node: HTTP Probe

Performs HTTP health checks against endpoints with configurable timeout and expected status codes.

## Schema

```yaml
type: node
name: http-probe
inputs:
  url:
    type: string
    required: true
  method:
    type: string
    default: GET
  timeout_seconds:
    type: number
    default: 10
  expected_status:
    type: array
    default: [200, 201, 204]
  headers:
    type: object
    required: false

outputs:
  status_code: number
  response_time_ms: number
  healthy: boolean
  error: string | null

on_error: continue
on_empty: skip
```

## Implementation

```bash
#!/usr/bin/env bash
URL="$1"
TIMEOUT="${2:-10}"
START=$(date +%s%N)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$URL" 2>/dev/null)
END=$(date +%s%N)
ELAPSED=$(( (END - START) / 1000000 ))

if [[ "$HTTP_CODE" =~ ^2 ]]; then
  echo "{\"status_code\": $HTTP_CODE, \"response_time_ms\": $ELAPSED, \"healthy\": true, \"error\": null}"
else
  echo "{\"status_code\": $HTTP_CODE, \"response_time_ms\": $ELAPSED, \"healthy\": false, \"error\": \"HTTP $HTTP_CODE\"}"
fi
```
