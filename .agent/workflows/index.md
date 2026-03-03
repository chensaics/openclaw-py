# PyClaw Agent Workflows

Automated workflows for the pyclaw multi-channel AI gateway.

## Flows

| Flow | Schedule | Description | Tags |
|------|----------|-------------|------|
| [channel-health-check](flows/channel-health-check/flow.md) | `*/15 * * * *` | Probe all enabled channels, report failures | `ops`, `channels`, `monitoring` |
| [daily-memory-digest](flows/daily-memory-digest/flow.md) | `0 3 * * *` | Summarize daily sessions into memory digest | `memory`, `maintenance` |
| [model-probe](flows/model-probe/flow.md) | `0 */6 * * *` | Test configured LLM providers for availability | `ops`, `models`, `monitoring` |
| [security-audit](flows/security-audit/flow.md) | `0 2 * * 0` | Scan config, dependencies, and secrets | `security`, `audit` |
| [dependency-check](flows/dependency-check/flow.md) | `0 9 * * 1` | Check for outdated/vulnerable dependencies | `deps`, `maintenance` |

## Components

| Type | Name | Description |
|------|------|-------------|
| connection | [llm-provider](components/connections/llm-provider.md) | LLM provider credentials |
| connection | [channel-auth](components/connections/channel-auth.md) | Channel authentication tokens |
| node | [http-probe](components/nodes/http-probe.md) | HTTP endpoint health check |
| node | [llm-chat](components/nodes/llm-chat.md) | Send prompt to LLM and capture response |
| node | [notify](components/nodes/notify.md) | Send notification via configured channel |
| node | [pip-audit](components/nodes/pip-audit.md) | Run pip-audit on project dependencies |
| trigger | [cron](components/triggers/cron.md) | Cron-based schedule trigger |
| trigger | [webhook](components/triggers/webhook.md) | HTTP webhook trigger via gateway |
| trigger | [event](components/triggers/event.md) | Internal pyclaw event trigger |
