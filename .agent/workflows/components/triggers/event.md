# Trigger: Event

Internal pyclaw event trigger, integrated with the hooks system.

## Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| event_type | string | yes | - | message, session, agent, gateway, command, channel |
| event_action | string | no | - | Sub-action filter (e.g. message:received) |
| filter | object | no | - | Additional filter conditions |

## Integration

Uses pyclaw.hooks.registry.register_hook() to listen for internal events.
When a matching event fires, the workflow is triggered with the event data.
Supports both sync and async handlers via the existing hook infrastructure.
