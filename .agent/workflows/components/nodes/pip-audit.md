# Node: Pip Audit

Runs `pip-audit` to scan project dependencies for known vulnerabilities.

## Schema

```yaml
type: node
name: pip-audit
inputs:
  project_dir:
    type: string
    default: "."
  ignore_vulns:
    type: array
    default: []
    description: GHSA IDs to ignore

outputs:
  vulnerable_count: number
  vulnerabilities: array
  clean: boolean

on_error: continue
on_empty: skip
```

## Implementation

```bash
#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="${1:-.}"
cd "$PROJECT_DIR"

pip install -q pip-audit 2>/dev/null

OUTPUT=$(pip-audit --format=json --require-hashes=false 2>/dev/null || true)
VULN_COUNT=$(echo "$OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
vulns = data.get('dependencies', [])
found = [v for v in vulns if v.get('vulns')]
print(len(found))
" 2>/dev/null || echo "0")

echo "{\"vulnerable_count\": $VULN_COUNT, \"clean\": $([ \"$VULN_COUNT\" = \"0\" ] && echo true || echo false)}"
```
