# Node: Notify

Sends a notification message through a configured pyclaw channel. Useful for alerting on workflow results.

## Schema

```yaml
type: node
name: notify
connection: channel-auth
inputs:
  channel_type:
    type: string
    required: true
  recipient:
    type: string
    required: true
    description: Chat ID, user ID, or channel name
  message:
    type: string
    required: true
  level:
    type: string
    default: info
    enum: [info, warning, error, critical]

outputs:
  sent: boolean
  message_id: string | null
  error: string | null

on_error: continue
on_empty: skip
```

## Implementation

```python
from pyclaw.channels.manager import get_channel
from pyclaw.channels.base import ChannelReply

async def run(inputs: dict, connection: dict) -> dict:
    level_emoji = {
        "info": "ℹ️", "warning": "⚠️",
        "error": "❌", "critical": "🚨"
    }
    prefix = level_emoji.get(inputs.get("level", "info"), "")
    text = f"{prefix} {inputs['message']}"

    channel = get_channel(inputs["channel_type"])
    reply = ChannelReply(
        chat_id=inputs["recipient"],
        text=text,
    )
    result = await channel.send(reply)
    return {
        "sent": result is not None,
        "message_id": str(result) if result else None,
        "error": None,
    }
```
