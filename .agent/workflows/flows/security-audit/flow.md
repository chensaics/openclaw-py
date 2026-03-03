# Flow: Security Audit

Weekly security scan covering config, dependencies, and source code secrets.

## Metadata

- schedule: `0 2 * * 0` (weekly Sunday 02:00 UTC)
- trigger: cron
- tags: security, audit
- on_failure: notify (critical)

## Steps

1. **scan-secrets**: Check source code for hardcoded API keys and tokens
2. **audit-deps**: Run pip-audit for known vulnerabilities
3. **check-config**: Verify config file permissions
4. **generate-report**: Compile findings into structured report
5. **alert-on-findings**: Notify on any security issues

## Nodes Used

- pip-audit, notify

## State Files

- state/last-audit.json: Latest audit results
- state/audit-history.json: Historical records

## Error Handling

- on_error: fail (security scans must not silently skip)
- on_empty: continue
