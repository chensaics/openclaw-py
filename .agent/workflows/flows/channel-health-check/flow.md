# Flow: Channel Health Check

Probes all enabled messaging channels and reports failures.

## Metadata

- schedule: `*/15 * * * *` (every 15 minutes)
- trigger: cron
- tags: ops, channels, monitoring
- on_failure: notify

## Steps

1. **load-channels**: Read enabled channels from pyclaw config
2. **probe-each**: For each channel, attempt a status check via its API
3. **collect-results**: Aggregate pass/fail per channel
4. **persist-state**: Write results to state/last-check.json
5. **alert-on-failure**: If any channel is down, send notification

## Nodes Used

- http-probe, notify

## State Files

- state/last-check.json: Latest results with timestamps
- state/downtime-log.json: Historical downtime records

## Error Handling

- on_error: continue (probe remaining channels)
- on_empty: skip
