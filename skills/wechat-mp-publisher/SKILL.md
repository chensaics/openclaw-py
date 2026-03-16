---
skill_key: claw-wechat-article
description: Unified WeChat Official Account publishing skill. Merges remote wenyan-mcp publishing, local wenyan publish flow, credential loading, and video-aware draft publishing.
version: 1.0.0
emoji: 🚀
homepage: https://github.com/chensaics/openclaw-py
runtime: python-native
launcher: python-native
security-level: elevated
userInvocable: true
disableModelInvocation: false
capability: wechat-mp-local-publish, wechat-mp-remote-publish, wechat-mp-video-draft, wechat-mp-credential-probe
deps: cmd:python
healthcheck: Validate article frontmatter, required CLIs, and optional remote MCP config before publish.
rollback: Switch to dry-run mode and return command plan without executing publish.
---

# Claw WeChat Article

Use this skill when the user asks to publish Markdown content to a WeChat Official Account draft box.

This built-in skill merges two capability families:

- local publish pipeline from `wechat-toolkit` (theme/highlight/video path awareness)
- remote publish pipeline from the prior standalone remote publisher (wenyan-mcp via mcporter)

## Supported modes

1. `probe`
   - validate runtime and article readiness
   - detect missing dependencies and config blockers
   - produce an executable command plan
2. `publish`
   - execute local or remote publish based on payload flags
   - optionally run video-aware publisher when mp4 references are present

## Payload schema

```json
{
  "action": "probe | publish",
  "article_path": "path/to/article.md",
  "remote": false,
  "use_video": "auto | true | false",
  "theme": "lapis",
  "highlight": "solarized-light",
  "dry_run": true,
  "wechat_app_id": "...optional...",
  "wechat_app_secret": "...optional...",
  "mcp_server": "wenyan-mcp",
  "mcp_config_file": "~/.openclaw/mcp.json"
}
```

## Credential resolution

Credentials are resolved in this order:

1. payload fields `wechat_app_id` + `wechat_app_secret`
2. environment variables `WECHAT_APP_ID` + `WECHAT_APP_SECRET`
3. `wechat.env` in this skill directory
4. common OpenClaw `TOOLS.md` locations

## Article requirements

- file must exist
- frontmatter should include `title` and `cover`
- for local video route, `.mp4` references trigger `publish_with_video.js`

## Notes

- Remote mode uses `mcporter` to call `wenyan-mcp.upload_file` then `wenyan-mcp.publish_article`.
- Local mode uses `wenyan publish -f <file> -t <theme> -h <highlight>`.
- If `dry_run` is true, this skill returns the execution plan but does not publish.
