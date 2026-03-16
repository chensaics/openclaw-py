---
skill_key: social
description: Agent social network connectivity and status checks.
version: 1.0.0
emoji: 🤝
homepage: https://github.com/chensaics/openclaw-py
runtime: python-native
launcher: python-native
security-level: standard
deps: env:MOLTBOOK_API_URL, env:CLAWDCHAT_API_URL
userInvocable: true
disableModelInvocation: false
capability: social-join, social-status
healthcheck: Validate social endpoint env vars exist.
rollback: Disable social actions and keep core messaging channels only.
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
