# Flow: Daily Memory Digest

Summarizes daily agent sessions into a consolidated memory digest using LLM.

## Metadata

- schedule: `0 3 * * *` (daily 03:00 UTC)
- trigger: cron
- tags: memory, maintenance

## Steps

1. **collect-sessions**: Gather session logs from the past 24 hours
2. **extract-key-points**: Parse important events and user preferences
3. **summarize**: Use LLM to create a concise daily summary
4. **write-digest**: Save to memory/YYYY-MM-DD.md
5. **update-cursor**: Track last processed session timestamp

## Nodes Used

- llm-chat

## State Files

- state/cursor.json: Last processed session timestamp
- state/stats.json: Running statistics

## Error Handling

- on_error: retry (3 attempts with exponential backoff)
- on_empty: skip
