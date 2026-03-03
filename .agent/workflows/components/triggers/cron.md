# Trigger: Cron

Schedule-based trigger using APScheduler (already bundled in pyclaw).

## Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| schedule | string | yes | - | Cron expression (5-field) |
| timezone | string | no | UTC | Timezone for schedule |
| jitter_seconds | number | no | 0 | Random delay to avoid thundering herd |

## Integration

pyclaw includes APScheduler via the pyclaw.cron module. Workflows register as scheduled jobs
using scheduler.add_job() with trigger="cron" and the appropriate cron fields.
