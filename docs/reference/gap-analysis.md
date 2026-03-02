# OpenClaw-Py 功能差距分析与后续计划

> 生成日期: 2026-02-28
>
> 对比原始 TypeScript 项目 (`openclaw/openclaw`) 与 Python 重写项目 (`openclaw-py`)，
> 全面识别尚未实现的功能，按优先级排列。

---

## 当前状态概要

| 指标 | openclaw-py (Python) | openclaw (TypeScript) |
|------|---------------------|-----------------------|
| 源文件数 | 208 个 .py | ~2000 个 .ts |
| 代码量 | ~20,900 LOC | ~150,000+ LOC |
| 测试数 | 97 | 600+ |
| 扩展/插件 | 7 (内置) | 32 |
| 原生应用 | 0 | 4 (macOS, iOS, Android, shared) |

---

## 一、消息通道 (Channels)

### 已实现 (5)

| 通道 | 库 | 状态 |
|------|-----|------|
| Telegram | aiogram | ✅ 完整 |
| Discord | discord.py | ✅ 完整 |
| Slack | slack-bolt (Socket Mode) | ✅ 完整 |
| WhatsApp | neonize (Baileys) | ✅ 完整 (P0) |
| Signal | signal-cli JSON-RPC/SSE | ✅ 完整 (P0) |

### 已实现 — 核心通道 (P2)

| 通道 | 库 | 状态 |
|------|-----|------|
| iMessage | imsg JSON-RPC over stdio | ✅ 完整 (P2) |

### 未实现 — 核心通道

| 通道 | TS 实现 | Python 方案 | 优先级 |
|------|---------|-------------|--------|
| LINE | LINE SDK | linebot-sdk | P4 |

### 已实现 — 扩展通道 (P3)

| 通道 | 库 | 状态 |
|------|-----|------|
| IRC | 原生 TCP/TLS | ✅ 完整 (P3) |
| MS Teams | aiohttp + Graph API | ✅ 完整 (P3) |
| Matrix | matrix-nio | ✅ 完整 (P3) |
| Feishu/飞书 | aiohttp + Open Platform API | ✅ 完整 (P3) |
| Twitch | 原生 IRC/TLS | ✅ 完整 (P3) |
| BlueBubbles | aiohttp + REST | ✅ 完整 (P3) |
| Google Chat | aiohttp + OAuth | ✅ 完整 (P3) |

### 未实现 — 扩展通道 (11)

以下通道在原始项目中作为 `extensions/` 插件存在：

Mattermost, Nextcloud Talk, Nostr, Synology Chat, Tlon/Urbit, Zalo, Zalouser, Voice Call (均 P4)

---

## 二、Agent Runtime

### 已实现

- ✅ 基础 agent 循环 (prompt → LLM streaming → tool execution → loop)
- ✅ 4 个 LLM 提供商 (OpenAI, Anthropic, Google Gemini, Ollama)
- ✅ JSONL 会话存储 (DAG 支持, compaction, file lock)
- ✅ 系统提示词构建 (safety/tooling/skills/memory/workspace/runtime)
- ✅ Token 估算 (字符比率启发式)
- ✅ Subagents 框架 (spawn/steer/kill, 并发限制, 深度限制) — P0 完成
- ✅ Auth Profiles (api_key/token/oauth, 持久化, cooldown, 失败追踪) — P0 完成
- ✅ Model Catalog (14 模型, provider 发现, 别名, 费用, 规范化) — P1 完成
- ✅ Skills 系统 (SKILL.md 发现, 前缀解析, 平台过滤, 提示构建) — P1 完成

- ✅ Tool Policy (group-scoped, plugin allowlist, owner-only) — P2 完成

### 未实现

*Agent Runtime P2 全部完成，无剩余项目。*

### 工具状态

| 工具 | 状态 | 说明 |
|------|------|------|
| `grep` | ✅ | 正则搜索 + 上下文行 + glob 过滤 |
| `find` | ✅ | glob 查找, 按修改时间排序 |
| `ls` | ✅ | 目录列表, 递归树视图 |
| `apply_patch` | ✅ | 统一 diff 解析 + 多文件补丁 |
| `agents_list` | ✅ | 列出可用 agent |
| `sessions_spawn` | ✅ | 生成子 agent 会话 |
| `subagents` | ✅ | list/steer/kill |
| `session_status` | ✅ | 运行时状态卡片 |
| `nodes` | ✅ | 设备节点操作 (list/invoke) — P3 完成 |
| `gateway` | ✅ | 网关状态/配置/重启 — P3 完成 |
| `canvas` | ✅ | Canvas 读写/列表/快照 — P3 完成 |

---

## 三、Gateway

### 已实现

- ✅ FastAPI WebSocket protocol v3
- ✅ 方法: `connect`, `health`, `status`, `config.get/set/patch`, `sessions.*`, `chat.*`
- ✅ Token 认证, 事件广播 (25+ 事件)
- ✅ OpenAI Chat Completions API (`/v1/chat/completions` + `/v1/models`) — P1 完成
- ✅ `models.list`, `models.providers` — P1 完成
- ✅ `agents.list/add/remove` — P1 完成
- ✅ `channels.list/status` — P1 完成

- ✅ `tools.catalog` / `tools.list` — P2 完成
- ✅ `cron.list/add/remove` — P2 完成
- ✅ `device.pair.code/approve/list` — P2 完成
- ✅ Plugin HTTP routes (`PluginRouteRegistry`) — P2 完成

### 已实现 (P3)

- ✅ HTTP 控制面板 (Control UI SPA 服务 + bootstrap config + CSP) — P3 完成
- ✅ Canvas Host (A2UI 静态文件服务 + WebSocket live-reload) — P3 完成
- ✅ Node Host (node.invoke 分发 + system.run/which) — P3 完成

### 未实现

*Gateway P3 全部完成。*

---

## 四、基础设施 (Infra)

### 已实现

- ✅ 通用重试策略 (指数退避 + 抖动)
- ✅ Provider 错误分类 (rate_limit / context_overflow / auth_error)
- ✅ 滑动窗口速率限制 + 认证暴力破解防护
- ✅ Env 变量安全清洗 (security-policy.json)

- ✅ Exec 审批 (allowlist + 交互式 ask + 节点转发) — P2 完成
- ✅ 设备配对 (challenge + allowFrom store + setup code) — P2 完成
- ✅ Heartbeat (心跳运行器 + active hours + wake) — P2 完成
- ✅ Provider 用量追踪 (多 provider 获取) — P2 完成
- ✅ 更新检查 (版本比较 + npm registry + git 状态) — P2 完成

### 未实现

### 已实现 (P3)

- ✅ Daemon/Service (launchd + systemd + schtasks 跨平台服务管理) — P3 完成

### 未实现 (P4)

| 功能 | 来源文件 | 说明 | 优先级 |
|------|---------|------|--------|
| mDNS/Bonjour | `src/infra/bonjour.ts` | 局域网服务发现 (zeroconf) | P4 |
| Tailscale | `src/infra/tailscale.ts` | Tailnet 状态/连接 | P4 |

---

## 五、Memory/RAG

### 已实现

- ✅ SQLite + FTS5 全文搜索
- ✅ 查询扩展 (多语言停用词过滤 + 关键词提取)
- ✅ 时间衰减 (半衰期打分, evergreen 检测)
- ✅ MMR 重排 (Jaccard 相似度)
- ✅ 混合搜索框架 (vector + keyword 合并)
- ✅ Embedding 提供商 (OpenAI, Gemini, Voyage, Mistral, auto) — P1 完成
- ✅ Memory 文件管理 (chunking, 索引, hash, 同步) — P1 完成

- ✅ Session → Memory Hook (bundled session-memory handler) — P2 完成

### 未实现

### 已实现 (P3)

- ✅ QMD 集成 (SQLite + 向量语义搜索 + 标签过滤 + CRUD) — P3 完成

### 未实现

*Memory/RAG P3 全部完成。*

---

## 六、Hooks 系统

### 已实现 (P2)

- ✅ Hook 框架 (事件注册/触发 + HOOK.md 加载 + 模块发现) — P2 完成
- ✅ session-memory (会话保存到记忆文件) — P2 完成
- ✅ Workspace hooks (工作区级 hook 配置) — P2 完成

### 未实现

### 已实现 (P3)

- ✅ Gmail Watcher Hook (Gmail API OAuth2 + 新邮件检测 + 摘要生成) — P3 完成

### 未实现

*Hooks P3 全部完成。*

---

## 七、CLI 命令

### 已实现

- ✅ `setup` (--wizard / --non-interactive --accept-risk / --reset)
- ✅ `doctor` (完整诊断: 系统/配置/凭证/会话/内存/Gateway) — P0 完成
- ✅ `agent` (单轮对话)
- ✅ `gateway` (启动 WebSocket 服务)
- ✅ `ui` (Flet 桌面/Web)
- ✅ `status` (完整: channels, sessions, gateway health, 表格/JSON) — P0 完成
- ✅ `config get/set/list` — P1 完成
- ✅ `agents add/remove/list` — P1 完成
- ✅ `channels list/status` — P1 完成
- ✅ `auth login/logout/status` — P1 完成

- ✅ `devices list/approve/remove` — P2 完成
- ✅ `message send` — P2 完成
- ✅ `pair approve` (快捷方式) — P2 完成

### 已实现 (P3)

- ✅ `service install/uninstall/status/restart/stop` — P3 完成
- ✅ `node` (启动无头节点主机) — P3 完成

### 未实现

*CLI P3 全部完成。*

---

## 八、UI (Flet)

### 已实现

- ✅ ChatView (消息列表, 输入框, 发送, Markdown 渲染) — P1 增强
- ✅ SettingsView (provider, model, API key, 主题切换) — P1 增强
- ✅ Session 管理 UI (侧边栏列表, 切换, 删除, 新建) — P1 完成
- ✅ Tool 调用可视化 (ToolCallCard, tool-display.json 集成) — P1 完成
- ✅ Markdown 渲染 (代码高亮, 表格, GitHub 扩展) — P1 完成
- ✅ Dark/Light 主题切换 — P1 完成
- ✅ 系统托盘图标 (pystray)
- ✅ 桌面模式 + Web 模式

- ✅ Channel 状态面板 (通道连接状态展示) — P2 完成
- ✅ Media 预览 (图片/音频/视频内嵌预览) — P2 完成
- ✅ Onboarding 向导 UI (4 步设置向导) — P2 完成

### 已实现 (P3)

- ✅ Voice 交互 (edge-tts 语音合成 + Whisper 转录 + Flet UI 面板) — P3 完成

### 未实现

*UI P3 全部完成。*

---

## 九、其他缺失领域

### 已实现 (P2)

- ✅ 日志子系统 (subsystem logger + 敏感数据脱敏) — P2 完成
- ✅ Markdown 处理 (IR + render + tables + fences + 通道格式) — P2 完成
- ✅ Security (DM/群组策略 + 配置审计) — P2 完成
- ✅ Media Understanding (OpenAI/Google/Anthropic 多 provider 图像/音频/视频) — P2 完成

### 已实现 (P3)

- ✅ ACP (Agent Control Protocol — NDJSON stdio bridge + session store + client) — P3 完成
- ✅ Canvas Host (HTTP 静态服务 + WebSocket live-reload + 移动端桥接) — P3 完成
- ✅ Node Host (设备无头服务 + invoke 分发 + system.run/which) — P3 完成

### 未实现

*其他领域 P3 全部完成。*

---

## 十、实施优先级建议

### P0 — 立即 ✅ 全部完成

- ~~补全核心通道: WhatsApp, Signal~~
- ~~Subagents 框架~~
- ~~Auth Profiles (多模式认证)~~
- ~~完整 `status` / `doctor` CLI~~
- ~~文件系统工具: `grep`, `find`, `ls`~~

### P1 — 核心功能 ✅ 全部完成

- ~~OpenAI Chat Completions API (`/v1/chat/completions`)~~
- ~~更多 Gateway 方法 (`models.list`, `agents.*`, `channels.*`)~~
- ~~Skills 系统~~
- ~~向量搜索 + Embedding 提供商~~
- ~~Memory 文件管理 (chunking, 索引)~~
- ~~CLI: `config`, `agents`, `channels`, `auth`~~
- ~~UI: Session 管理, Tool 可视化, Markdown 渲染~~
- ~~Terminal 工具 (ANSI 表格)~~
- ~~缺失工具: `apply_patch`, `agents_list`, `sessions_spawn`, `subagents`, `session_status`~~

### P2 — 增强功能 ✅ 全部完成

- ~~Hooks 系统 (事件框架 + session-memory + workspace hooks)~~
- ~~Exec 审批 (allowlist + 交互式 ask)~~
- ~~设备配对 (challenge + token)~~
- ~~Heartbeat (心跳运行器 + active hours)~~
- ~~更新检查 (版本检查 + 通道选择)~~
- ~~Provider 用量追踪~~
- ~~Tool Policy (group-scoped policy)~~
- ~~iMessage 通道~~
- ~~日志脱敏 / Security 审计~~
- ~~Markdown 处理 (IR 转换)~~
- ~~Media Understanding~~
- ~~Gateway: tools.catalog, cron.*, device.pair.*, Plugin HTTP routes~~
- ~~CLI: nodes/devices, message send~~
- ~~UI: Channel 面板, Media 预览, Onboarding~~

### P3 — 完善 ✅ 全部完成

- ~~扩展通道 (IRC, MS Teams, Matrix, Feishu, Twitch, BlueBubbles, Google Chat)~~
- ~~ACP (Agent Control Protocol 桥接)~~
- ~~Canvas Host (A2UI 渲染/导航/快照)~~
- ~~Node Host (设备无头服务)~~
- ~~QMD 集成 (外部记忆后端)~~
- ~~Gateway HTTP 控制面板~~
- ~~Daemon/Service (launchd + systemd + schtasks)~~
- ~~UI: Voice 交互 (edge-tts + whisper)~~
- ~~Gmail Watcher Hook~~
- ~~工具: nodes, gateway, canvas~~
- ~~CLI: service, node~~

### P4 — 远期 (部分已完成)

- ~~原生 Apps 打包 (Flet build macOS/Linux/Windows/iOS/Android)~~
- ~~mDNS/Bonjour 局域网发现~~
- ~~Tailscale 集成~~
- ~~LINE 通道~~
- ~~剩余扩展通道 (Mattermost, Nextcloud Talk, Nostr, Synology Chat, Tlon/Urbit, Zalo, Zalouser, Voice Call)~~

### P5 — 新增差距 (2026.2.25-2026.2.27)

TypeScript 主项目在 2026.2.25-2026.2.27 期间新增的功能，Python 版本需要跟进：

**P0 核心:**

| 功能 | TS 规模 | 说明 |
|------|---------|------|
| ACP / acpx thread-bound agents | ~5,100 LOC / 61 文件 | ACP agents 作为线程运行时, acpx CLI 后端, thread-ownership 扩展 |
| External Secrets 管理 | ~2,800 LOC / 16 文件 | `openclaw secrets` CLI (audit/configure/apply/reload), 运行时快照 |
| Agent Bindings CLI | ~900 LOC / 5 文件 | `openclaw agents bindings/bind/unbind`, account-scoped 路由, 7 级优先级 |
| OpenAI Codex + Responses API | ~1,400 LOC / 10 文件 | WebSocket 传输, `/v1/responses` 端点, context_management |

**P1 增强:**

| 功能 | TS 规模 | 说明 |
|------|---------|------|
| Android Nodes | ~3,300 LOC | 远程设备节点, device/camera/notifications/contacts/calendar/motion/photos 工具 |
| Plugin Onboarding Hooks | ~1,400 LOC / 5 文件 | configureInteractive, configureWhenConfigured 交互式配置 |
| Discord Thread Lifecycle | ~1,570 LOC / 7 文件 | idleHours/maxAgeHours TTL, 自动清扫解绑 |

**P2 扩展:**

| 功能 | TS 规模 | 说明 |
|------|---------|------|
| Memory Plugins (LanceDB) | ~600 LOC / 5 文件 | 可插拔记忆后端, auto-recall/capture |
| Non-channel Extensions | ~2,000 LOC / 30+ 文件 | lobster, llm-task, open-prose, phone-control, diagnostics-otel, copilot-proxy, talk-voice, auth 扩展 |
| Web UI i18n | ~200 LOC | 多语言 UI (en, de, zh) |

**P3 安全:**

| 功能 | TS 规模 | 说明 |
|------|---------|------|
| Security Hardening | ~1,100 LOC / 8 文件 | commandArgv binding, systemRunBindingV1, sandbox 边界, pairing 隔离 |

详细实施计划见 [implement_plan_next.md](implement_plan_next.md)。

---

## 附录: 已实现功能清单

完整的已实现功能清单见 [PROGRESS.md](../PROGRESS.md)。

### 模块统计

| 模块 | 文件数 | 说明 |
|------|--------|------|
| CLI | 14 | app, agent, gateway, setup, status, doctor, config, agents, channels, auth, devices, message, service, node |
| Config | 6 | schema, io, paths, defaults, secrets, sessions |
| Gateway | 19 | server, events, protocol, openai_compat, plugin_routes, control_ui, 12 method handlers |
| Agents | 12 | runner, stream, session, lock, tokens, types, system_prompt, model_catalog, tool_policy, auth_profiles(4), subagents(4), skills(4) |
| Tools | 20 | file, fs, exec, web, memory, session, browser, message, cron, process, tts, image, patch, subagent_tools, registry, nodes, gateway_tools, canvas_tools |
| Channels | 26 | base, manager, telegram, discord, slack, whatsapp, signal, imessage(3), irc(2), msteams(2), matrix(2), feishu(2), twitch(2), bluebubbles(2), googlechat(2) |
| Memory | 10 | store, hybrid, mmr, temporal_decay, query_expansion, embeddings, file_manager, qmd(2) |
| Media | 12 | mime, images, audio, storage, understanding(7) |
| Routing | 3 | session_key, dispatch |
| Terminal | 4 | ansi, palette, table |
| Infra | 6 | retry, rate_limit, exec_approvals, heartbeat, update_check, provider_usage |
| Hooks | 7 | types, registry, loader, bundled/session_memory, bundled/gmail_watcher |
| Logging | 3 | subsystem, redact |
| Security | 3 | dm_policy, audit |
| Markdown | 6 | ir, render, tables, fences, channel_formats |
| Pairing | 4 | store, challenge, setup_code |
| Cron | 2 | scheduler |
| Plugins | 2 | loader |
| ACP | 5 | types, session, server, client |
| Canvas | 3 | handler, server |
| Node Host | 3 | invoke, runner |
| Daemon | 4 | service, launchd, systemd, schtasks |
| UI | 7 | app, tray, channels_panel, media_preview, onboarding, voice |
| **合计** | **~248** | |
