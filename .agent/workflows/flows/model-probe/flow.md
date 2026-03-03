# Flow: Model Probe

Tests all configured LLM providers for availability and latency.

## Metadata

- schedule: `0 */6 * * *` (every 6 hours)
- trigger: cron
- tags: ops, models, monitoring

## Steps

1. **load-providers**: Read configured LLM providers from config
2. **probe-each**: Send a minimal test prompt to each provider
3. **measure-latency**: Record response time and token usage
4. **persist-results**: Write to state/probe-results.json
5. **alert-on-failure**: Notify if any provider is unreachable

## Nodes Used

- llm-chat, notify

## State Files

- state/probe-results.json: Latest probe results
- state/history.json: Historical availability data

## Error Handling

- on_error: continue
- on_empty: skip
