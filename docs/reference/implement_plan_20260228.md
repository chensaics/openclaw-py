# OpenClaw-Py 后续实施计划 (Phase 10+)

> 生成日期: 2026-02-28
>
> P0-P3 全部完成 (208 文件, ~20,900 LOC)。后续工作分为两个方向：
> (A) 质量加固 -- 补充测试覆盖率、CI、打包发布流程；
> (B) P4 功能扩展 -- 剩余通道、基础设施、原生 App。
> 建议先完成质量加固再推进 P4 功能。

---

## 当前状态

- **208 个 .py 文件 / ~20,900 LOC** -- P0 到 P3 全部完成
- **97 个测试通过** -- 但仅覆盖 ~10 个模块 (config, gateway server, channels base, memory store, session, tools, runner, plugins, cron, routing)
- **无 CI** -- 无 GitHub Actions 配置
- **无覆盖率工具** -- 没有 pytest-cov / coverage 配置
- **可选依赖未声明** -- matrix-nio, neonize 等未列入 `pyproject.toml`

---

## Phase 10: 质量加固 (建议优先)

### 10a. 测试补全

当前 ~25 个模块无任何测试。按重要性分批补充：

**批次 1 -- 核心路径 (~8 个测试文件)**

- `tests/test_hooks.py` -- hook 注册/触发/loader/session-memory
- `tests/test_markdown.py` -- IR 解析/渲染/tables/fences/channel formats
- `tests/test_security.py` -- dm_policy 决策/security audit
- `tests/test_pairing.py` -- pairing store/challenge/setup code
- `tests/test_infra.py` -- exec_approvals/heartbeat/update_check
- `tests/test_acp.py` -- session store TTL + 驱逐/types
- `tests/test_daemon.py` -- launchd plist 生成/systemd unit 生成
- `tests/test_qmd.py` -- QMD CRUD + 语义搜索

**批次 2 -- 次要模块 (~5 个测试文件)**

- `tests/test_logging.py` -- subsystem logger/redact
- `tests/test_canvas.py` -- file resolution/live-reload injection
- `tests/test_node_host.py` -- invoke dispatch/env sanitization
- `tests/test_terminal.py` -- ANSI table/palette
- `tests/test_gateway_methods.py` -- 关键 RPC method handlers

**批次 3 -- 通道实现 (~2 个测试文件)**

- `tests/test_ext_channels.py` -- 扩展通道基本实例化 + 消息解析
- `tests/test_tools_extra.py` -- nodes/gateway/canvas tool handlers

### 10b. 项目工程化

- 在 `pyproject.toml` 中添加 `[project.scripts]` 入口和测试/lint 脚本
- 添加 `pytest-cov` 依赖 + `[tool.coverage]` 配置 (目标: 60%+ 行覆盖率)
- 声明可选依赖组 (`pyproject.toml` `[project.optional-dependencies]`):
  - `matrix` -> `matrix-nio`
  - `whatsapp` -> `neonize`
  - `voice` -> `edge-tts`
  - `all` -> 全部可选
- 修复 `src/openclaw/ui/app.py` 中 2 个 TODO

### 10c. CI / CD

- 添加 `.github/workflows/ci.yml`:
  - pytest + coverage report
  - ruff check
  - mypy strict
  - 矩阵: Python 3.12 + 3.13
- 添加 `.github/workflows/release.yml`:
  - 自动发布到 PyPI (on tag push)

---

## Phase 11: P4 功能 -- 基础设施

### 11a. mDNS/Bonjour 局域网发现

- 新模块: `src/openclaw/infra/bonjour.py` (~150 LOC)
- 使用 `zeroconf` 库 (Python 原生 mDNS)
- 核心 API: `start_gateway_bonjour_advertiser()`, `stop_advertiser()`
- 参考 TS: `src/infra/bonjour.ts` (281 LOC)

### 11b. Tailscale 集成

- 新模块: `src/openclaw/infra/tailscale.py` (~250 LOC)
- 通过 `tailscale` CLI 子进程: `status --json`, `funnel`, `serve`, `whois`
- 核心 API: `find_tailscale_binary()`, `get_tailnet_hostname()`, `ensure_funnel()`, `read_tailscale_whois_identity()`
- 参考 TS: `src/infra/tailscale.ts` (500 LOC)

---

## Phase 12: P4 功能 -- 扩展通道

按复杂度从低到高实施：

### 12a. 简单通道 (~3 个, 各 ~150 LOC)

| 通道 | 方案 | 复杂度 |
|------|------|--------|
| Synology Chat | aiohttp webhook | 简单 |
| Mattermost | aiohttp + WebSocket | 中等 |
| Nextcloud Talk | aiohttp webhook | 中等 |

### 12b. 中等通道 (~3 个, 各 ~200-300 LOC)

| 通道 | 方案 | 复杂度 |
|------|------|--------|
| Tlon/Urbit | aiohttp SSE client | 中等 |
| Zalo (Bot) | aiohttp + Zalo API | 中等 |
| Zalouser | subprocess + zca-cli | 复杂 |

### 12c. 复杂通道 (~2 个)

| 通道 | 方案 | 复杂度 |
|------|------|--------|
| Nostr | nostr-sdk (Python) | 复杂 (~400 LOC) |
| LINE | linebot-sdk-python | 复杂 (~500 LOC, 核心通道) |

### 12d. Voice Call (最复杂)

- TS 实现: **47 文件 / ~11,000 LOC** -- 包含 Twilio/Telnyx/Plivo 三家 provider
- Python 方案: `twilio`, `aiohttp` + webhooks + STT/TTS pipeline
- 建议作为独立子项目，分阶段实现:
  1. Twilio provider (单一 provider 先跑通)
  2. 通用 provider 抽象
  3. Telnyx / Plivo 扩展

---

## Phase 13: P4 功能 -- 原生应用

使用 Flet/Flutter 构建跨平台原生 App。这是最大的工作项。

### 13a. Flet 打包 (桌面)

- 将现有 Flet UI (`src/openclaw/ui/`) 打包为独立桌面应用
- `flet build macos` / `flet build linux` / `flet build windows`
- 添加应用图标、签名、自动更新

### 13b. Flet 移动端

- `flet build ios` / `flet build android`
- 适配移动端布局 (响应式)
- 推送通知集成
- App Store / Play Store 发布流程

### 13c. Flutter 原生增强 (可选)

- 如果 Flet 无法满足性能/UX 需求，使用纯 Flutter 重写前端
- 复用 Python 后端 (Gateway API)，Flutter 作为纯客户端

---

## 实施优先级总结

| Phase | 预估新增文件 | 预估新增 LOC | 依赖 |
|-------|------------|------------|------|
| 10: 质量加固 | ~17 | ~2,500 | 无 |
| 11: mDNS + Tailscale | ~2 | ~400 | 无 |
| 12: 扩展通道 | ~20 | ~3,000 | 部分需第三方 SDK |
| 13: 原生 Apps | ~5-10 | ~1,000 (config) | Flet build toolchain |

优先级: Phase 10 -> Phase 11 -> Phase 12 -> Phase 13

---

## 执行状态 (2026-02-28)

所有 Phase 已完成:

- Phase 10a: 15 个测试文件, 261 个测试全部通过
- Phase 10b: pyproject.toml 工程化 (coverage, optional deps, scripts)
- Phase 10c: GitHub Actions CI + Release workflows
- Phase 11a: mDNS/Bonjour 局域网服务发现
- Phase 11b: Tailscale VPN 集成
- Phase 12a: Synology Chat + Mattermost + Nextcloud Talk
- Phase 12b: Tlon/Urbit + Zalo Bot + Zalo User
- Phase 12c: Nostr (NIP-04) + LINE Messaging API
- Phase 12d: Voice Call (Twilio provider + channel abstraction)
- Phase 13: Flet build 入口 + 桌面/移动端构建脚本

最终统计: **230 个 .py 文件 / ~22,800 LOC / 261 tests passing**
