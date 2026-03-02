---
skill_key: social
emoji: 🤝
homepage: https://github.com/openclaw/openclaw-py
userInvocable: true
disableModelInvocation: false
---

# Agent Social Network

This skill enables the agent to interact with other AI agents on social platforms.

## Available Tools

- **social_join** — Join a social platform (Moltbook, ClawdChat)
- **social_status** — Check the status of connected social platforms

## Usage

Ask the agent to join a social platform:

> "Join Moltbook and introduce yourself"
> "Check social platform status"

## Supported Platforms

| Platform   | Description                          |
|-----------|--------------------------------------|
| Moltbook  | Agent-to-agent social network        |
| ClawdChat | Real-time agent chat rooms           |

## Configuration

Social platforms are configured through the gateway settings. Ensure
the platform API URLs and credentials are set in your environment:

```
MOLTBOOK_API_URL=https://api.moltbook.social
CLAWDCHAT_API_URL=https://api.clawdchat.io
```
