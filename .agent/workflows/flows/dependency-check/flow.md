# Flow: Dependency Check

Weekly check for outdated or vulnerable Python dependencies.

## Metadata

- schedule: `0 9 * * 1` (weekly Monday 09:00 UTC)
- trigger: cron
- tags: deps, maintenance

## Steps

1. **list-outdated**: Run pip list --outdated
2. **check-vulnerabilities**: Run pip-audit for CVE matches
3. **categorize**: Split into critical, major, minor
4. **persist-results**: Write to state/dependency-status.json
5. **notify-if-needed**: Alert on critical vulnerabilities only

## Nodes Used

- pip-audit, notify

## State Files

- state/dependency-status.json: Current status
- state/update-log.json: History of detected updates

## Error Handling

- on_error: continue
- on_empty: skip
