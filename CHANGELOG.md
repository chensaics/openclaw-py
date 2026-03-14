# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- (none yet)

### Changed
- (none yet)

### Fixed
- (none yet)

## [0.1.4] - 2026-03-15

### Added
- Versioned pre-push hook: `scripts/githooks/pre-push`（推送 tag 时跳过测试，由 release workflow 执行）
- `scripts/githooks/README.md` — 安装说明

### Changed
- pre-push：仅对分支推送跑全量 pytest，推送 tag 时跳过，避免与 release 重复
- ci-local.sh：不再跑 pytest，只做 ruff + mypy，pytest 由 pre-push 统一执行
- commit.sh：文案改为“本地检查（ruff + mypy）”

### Fixed
- 测试耗时：`test_infra_misc.test_with_timeout_expired`、`test_cron_tts_logging.test_timeout` 中 `asyncio.sleep(10)` 改为最小必要时长（0.1s / 0.2s），pre-push 全量测试减少约 20 秒

## [0.1.3] - 2026-03-14

### Added
- Responsive shell module (`ui/responsive_shell.py`) — breakpoint-based layout management
- External locale JSON files (`ui/locales/*.json`) — i18n data no longer hardcoded
- Desktop tray quick actions — new chat, toggle theme, mute notifications
- PWA support — manifest, service worker, offline caching for web builds
- Provider/model configuration linkage — switching provider auto-updates model list, base URL, API key hint
- CJK font fallback chain for proper Chinese/Japanese display
- Shimmer loading animation, message fade-in, send button scale animation
- Chat export to Markdown, file attachment support
- Keyboard shortcuts (Cmd/Ctrl+K search, +N new session, +E export)
- Streaming typing indicator with animated dots
- Scroll-to-bottom floating button
- Reusable UI components (`ui/components.py`): page_header, empty_state, card_tile, status_chip
- New UI panels: config, cron, debug, instances, logs, nodes, overview, plans, sessions, skills, system, usage
- Docs site (MkDocs) and GitHub Pages deploy workflow
- Reference docs restructure: PROGRESS.md + REFERENCE_TABLES.md milestone-driven layout

### Changed
- Provider defaults consolidated into single source of truth (`model_catalog._KNOWN_PROVIDERS`)
- Toolbar refactored to `ChatToolbar` class with dynamic model updates
- Chat bubble design enhanced — asymmetric border radius, role-colored avatars, improved shadows
- Provider names use English-first format with CJK in parentheses
- Dependencies reorganized — heavy channel SDKs moved to optional `[channels]` extra
- Reference and docs layout: legacy plans moved/archived, single source in `reference/`

### Fixed
- Dropdown event binding: `on_select` instead of `on_change` for Flet Dropdown
- `ft.alignment.bottom_center` replaced with `ft.Alignment(0, 1)` for Flet compatibility
- ChatMessage search: `_message_content` initialized in constructor
- Tool display metadata: correct nested key access with fallback

## [0.1.0] - 2026-03-04

### Added
- Initial release
- Multi-channel AI gateway (Telegram, Discord, Slack, WeChat, WhatsApp, Matrix, and more)
- 20+ LLM provider support (OpenAI, Anthropic, Google, DeepSeek, Qwen, GLM, MiniMax, etc.)
- WebSocket v3 protocol for UI-gateway communication
- Flet-based cross-platform UI (Web, Desktop, Mobile)
- Agent system with tool calling, planning, and memory
- CLI with interactive setup wizard
- Docker support with multi-stage build
- Cron job scheduling
- Voice interaction (TTS via edge-tts, STT via Whisper API)

[Unreleased]: https://github.com/chensaics/openclaw-py/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/chensaics/openclaw-py/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/chensaics/openclaw-py/compare/v0.1.2...v0.1.3
[0.1.0]: https://github.com/chensaics/openclaw-py/releases/tag/v0.1.0
