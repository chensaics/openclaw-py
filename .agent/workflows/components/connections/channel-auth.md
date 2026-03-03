# Connection: Channel Auth

Authentication tokens for messaging channels, resolved from pyclaw config.

## Schema

```yaml
type: connection
name: channel-auth
source: config  # reads from ~/.openclaw/openclaw.json → channels

fields:
  channel_type:
    type: string
    required: true
    enum: [telegram, discord, slack, dingtalk, feishu, qq, whatsapp, matrix, line, msteams, wechat, irc, nostr, mattermost, nextcloud, synology, twitch, tlon, zalo, signal, bluebubbles, googlechat, imessage, voice_call]
  token:
    type: string
    secret: true
    required: true
  extra:
    type: object
    required: false
    description: Channel-specific additional fields (webhook_url, app_id, etc.)
```

## Resolution

```python
from pyclaw.config.io import load_config

cfg = load_config()
channel_cfg = cfg.channels  # per-channel config with tokens
```
