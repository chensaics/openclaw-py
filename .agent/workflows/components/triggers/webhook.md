# Trigger: Webhook

HTTP endpoint trigger exposed through the pyclaw gateway.

## Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| path | string | yes | - | URL path under /api/workflows/ |
| method | string | no | POST | HTTP method |
| auth | string | no | bearer | Auth type: none, bearer, api_key |
| secret | string | no | - | Shared secret for verification |

## Integration

Register webhook endpoints via the gateway FastAPI router at /api/workflows/trigger/{flow_name}.
The endpoint validates auth, loads the named flow, and executes it with the request payload as trigger data.
