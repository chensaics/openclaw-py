# Xiaohongshu Skills Merge Matrix

This matrix merges the three referenced projects into one core capability set.

## Source projects

- `vivy-yi/xiaohongshu-skills`: operations knowledgebase (139 skill docs, strategy and learning paths)
- `white0dew/XiaohongshuSkills`: production CDP automation (publish/search/interact/data extraction)
- `autoclaw-cc/xiaohongshu-skills`: modular skill architecture (`xhs-auth`, `xhs-publish`, `xhs-explore`, `xhs-interact`, `xhs-content-ops`)

## Unified capability set

### A) Operations knowledge layer

- Content creation planning and topic strategy
- Account positioning, growth, and brand playbooks
- Data analysis and optimization loop
- Monetization and long-term operation guidance
- Platform compliance and risk management guidance

### B) Automation execution layer

- Auth: login check, QR login, account switch, account list/default account
- Publish: text/image, video, long-form, preview-before-publish, scheduled publish
- Discover: home feeds, keyword search, feed detail with comments/replies
- Interact: comment, reply, like/unlike, favorite/unfavorite
- Analytics: creator-center content table extraction and CSV export
- Runtime: local/remote CDP, headless mode, media download/cache, selector-fix resilience

### C) Agent orchestration layer

- Natural language to intent decomposition
- Multi-step chained workflows (search -> collect -> summarize -> action)
- Structured JSON outputs for tool-to-tool handoff
- Safe-mode fallbacks for unstable DOM or policy-sensitive actions

## Default composite workflows

1. **Publish workflow**
   - `check_login` -> `prepare_media` -> `fill_publish` -> `preview` -> `confirm_publish`
2. **Research workflow**
   - `search_feeds` -> `rank/filter` -> `get_feed_detail` -> `extract_insights`
3. **Interaction workflow**
   - `resolve_target_feed` -> `like/favorite` -> `comment/reply` -> `verify_result`
4. **Ops analytics workflow**
   - `content_data` -> `export_csv` -> `summarize_trends` -> `next_content_plan`

## Integration constraints

- All write operations should support dry-run/preview mode.
- Every action should emit structured checkpoints and failure reason.
- Account context is mandatory for write operations.
- Add anti-spam backoff and duplicate-action guard.

## Suggested future implementation split

- `skills/claw-redbook-auto/` keeps policy + orchestration contract.
- Runtime scripts can evolve in a separate `skills/claw-redbook-auto/scripts/` package.
- Keep selector definitions centralized to reduce maintenance cost after platform UI changes.
