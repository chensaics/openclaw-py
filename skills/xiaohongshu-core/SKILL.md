---
skill_key: claw-redbook-auto
description: Unified Xiaohongshu (Redbook) automation skill covering authentication, publishing, discovery, interaction, analytics, and multi-account workflows. Use when users ask to publish notes, search notes, manage comments, analyze account data, or run end-to-end Redbook operations.
version: 1.0.0
emoji: 📕
homepage: https://github.com/chensaics/openclaw-py
runtime: python-native
launcher: python-native
security-level: elevated
userInvocable: true
disableModelInvocation: false
capability: xiaohongshu-auth, xiaohongshu-publish, xiaohongshu-explore, xiaohongshu-interact, xiaohongshu-analytics
deps: cmd:python
healthcheck: Validate Python runtime and discover available Chrome/Chromium binary before execution.
rollback: Disable automated write actions and fallback to read-only exploration/report mode.
---

# Claw Redbook Auto

Use this skill for end-to-end Xiaohongshu operations. It consolidates:

- automation-pipeline features (publish, interact, collect data)
- operations-knowledge features (content strategy, growth workflow)
- agent-routing features (natural language intent to action plan)

## Capability map

1. **Auth and session**
   - login check and QR login
   - multi-account isolation and default-account switching
   - cached login-state probe to reduce repeated checks
2. **Publishing**
   - graphic note publish, video publish, long-form publish
   - preview/fill-first workflow before final click publish
   - optional scheduled publishing flow
   - automatic hashtag extraction from the last line of content
3. **Explore and retrieval**
   - home feed list pull
   - keyword search with sort/type filters
   - note detail extraction with optional deep comment loading
   - user profile snapshot and note list extraction
4. **Interaction**
   - post comment and reply comment
   - like/unlike and favorite/unfavorite
   - mentions notification data pull
5. **Data and analytics**
   - creator-center content metrics table extraction
   - CSV export
   - structured output for downstream analysis
6. **Runtime and reliability**
   - local or remote CDP target
   - headless/headed execution
   - selector drift handling and fallback waits
   - media URL download and cache reuse

## Execution workflow

Follow this sequence:

1. Identify intent: `auth`, `publish`, `explore`, `interact`, `analytics`, or mixed.
2. Confirm account context: target account, default account, or account switch.
3. Validate runtime: Chrome CDP reachable and required dependencies ready.
4. Dry-run plan:
   - for write actions: require preview mode first when risk is high
   - for read actions: continue directly
5. Execute operation steps with structured checkpoints.
6. Return JSON-like result summary with:
   - `status`
   - `intent`
   - `actions`
   - `artifacts` (IDs, tokens, CSV paths, screenshots)
   - `risks` and `next_steps`

## Safety and policy guardrails

- Reject or pause if content may violate platform rules.
- Avoid repeated interaction spam; add retry backoff and dedupe checks.
- Keep account credentials/profile paths isolated per account.
- For risky actions (mass interaction, scheduled campaigns), require explicit confirmation.
- If selectors become stale, switch to diagnostic mode and report exact failing step.

## Recommended intent templates

- Publish:
  - "发布图文笔记，先预览再发布，账号=brand-main"
- Explore:
  - "搜索关键词并返回点赞前10的图文笔记摘要"
- Interact:
  - "对指定笔记点赞并回复匹配评论"
- Analytics:
  - "抓取内容数据表并导出 CSV，附关键指标总结"
- Compound ops:
  - "检索竞品爆文 -> 收藏 -> 抽取评论观点 -> 生成选题建议"

## Reference

- Detailed merged feature matrix: [feature-matrix.md](feature-matrix.md)
