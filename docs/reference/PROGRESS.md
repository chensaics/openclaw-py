# OpenClaw Python 重写 -- 执行进度

> 最后更新: 2026-03-02
> 项目路径: `/Users/cs/projects/openclaw-py/`

## 当前状态概览

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1: 基础层 | **已完成** | 脚手架、配置模型、IO 兼容、会话存储 |
| Phase 2: Gateway | **已完成** | FastAPI + WebSocket 协议 v3 + 核心方法处理器 |
| Phase 3a: Agent 核心循环 | **已完成** | LLM 流式调用 + 工具执行循环 |
| Phase 3b: 工具框架 | **已完成** | BaseTool, Registry, 20+ 内置工具 |
| Phase 3c: SessionManager | **已完成** | DAG entries, 文件锁, token 估算, compaction |
| Phase 3d: LLM 提供商 | **已完成** | OpenAI, Anthropic, Google Gemini, Ollama |
| Phase 4: 消息通道 | **已完成** | 通道抽象层 + Telegram + Discord + Slack + WhatsApp + Signal + iMessage |
| Phase 5: Flet UI | **已完成** | 桌面聊天 + Session 管理 + Tool 可视化 + Markdown + 设置 + 系统托盘 + Channel 面板 + Onboarding |
| Phase 6: 高级功能 | **已完成** | 记忆/RAG + 插件系统 + 定时任务 |
| Phase 7: P0/P1 功能完善 | **已完成** | Auth Profiles + Subagents + Model Catalog + Skills + Embeddings + CLI + Gateway API |
| Phase 8: P2 增强功能 | **已完成** | Hooks + Exec 审批 + Heartbeat + Security + Markdown IR + Media Understanding + Pairing + UI 增强 |
| Phase 9: P3 完善功能 | **已完成** | 7 扩展通道 + ACP + Canvas + Node Host + Daemon + QMD + Voice + Gateway 控制面板 + Gmail Hook + 工具补全 |
| Phase 10: 质量加固 | **已完成** | 15 个新测试文件 (~2,900 LOC) + pytest-cov + CI/CD + pyproject 工程化 |
| Phase 11: 基础设施 P4 | **已完成** | mDNS/Bonjour 局域网发现 + Tailscale VPN 集成 |
| Phase 12: 扩展通道 P4 | **已完成** | 10 个新通道 (Synology, Mattermost, Nextcloud, Tlon, Zalo, ZaloUser, Nostr, LINE, VoiceCall) |
| Phase 13: 原生 App 打包 | **已完成** | Flet build 入口 + 桌面/移动端构建脚本 |
| Phase 14: 核心功能对齐 | **已完成** | ACP/acpx + External Secrets + Agent Bindings + OpenAI Codex/Responses |
| Phase 15: 重要增强 | **已完成** | Android Nodes 策略 + Plugin Onboarding Hooks + Discord Thread Lifecycle |
| Phase 16: 扩展功能 | **已完成** | Memory Plugins (LanceDB) + Non-channel Extensions + Web UI i18n |
| Phase 17: 安全加固 | **已完成** | Exec Approval 增强 + Gateway 安全加固 + Sandbox 边界 |
| Phase 18: 核心管道补全 | **已完成** | Auto-reply 引擎 + Typing 管理器 + Outbound 管道 + Delivery Queue + Model Fallback |
| Phase 19: Feishu 深度对齐 | **已完成** | Reactions + Docx + 高级路由 + 消息增强 + 运行时优化 |
| Phase 20: 通道安全统一 | **已完成** | Auth Guard + Allowlist 边界 + 安全审计扩展 + 危险工具标记 |
| Phase 21: Gateway + Agent 加固 | **已完成** | WS Flood Guard + Compaction 增强 + Config/State 迁移 + Command Gating |
| Phase 22: Telegram + Browser 增强 | **已完成** | Telegram 媒体上下文/chunking/退避 + Browser Relay + Link Understanding |
| Phase 23: Extensions + 杂项 | **已完成** | Memory-core Extension + Gemini CLI Auth + Ollama 增强 + 德语 i18n |
| Phase 24: 斜杠命令系统 | **已完成** | 命令注册表 + 核心/会话/模型命令 + 内联指令 + 消息队列 + 回复调度器 |
| Phase 25: 流式分块 + 投递管道 | **已完成** | Block Streaming + 投递目标解析 + 发送服务 + 消息动作 + 通道适配器 + HTML 导出 |
| Phase 26: LLM 提供商扩展 | **已完成** | OpenAI 兼容适配器 + 9 个中国提供商 + OAuth 流 (MiniMax/Qwen/Copilot) + Bedrock + 提供商注册表 |
| Phase 27: Channel Plugin SDK | **已完成** | 20+ 适配器 Protocol + 草稿流式 + 确认反应 + 模型覆盖 + 提及门控 + 通道健康检查 |
| Phase 28: Config 系统深化 | **已完成** | 环境变量替换 + Config Includes + 备份轮转 + Session Store + 运行时覆盖 + 配置脱敏 |
| Phase 29: 进程管理 + 媒体扩展 | **已完成** | 进程监管器 + 命令队列 + Groq/Mistral/Deepgram/xAI 媒体理解 + 视频管道 + Voyage/Mistral 嵌入 + 批量上传 |
| Phase 30: Gateway 高级功能 | **已完成** | 配置热重载 + 通道健康监控 + 控制面限速 + Hooks 映射 + 服务发现 (mDNS + Tailscale) |
| Phase 31: Commands/Doctor/Onboarding | **已完成** | Doctor 9 项诊断 + 27 提供商认证 + 交互/非交互 Onboarding + Status 增强 + Models CLI + Channels CLI |
| Phase 32: Cron/TTS/Logging 高级 | **已完成** | 隔离代理运行器 + 技能快照 + 任务交错 + 超时策略 + 会话收割器 + Webhook 触发 + ElevenLabs/OpenAI TTS + 日志轮转/脱敏 + SSRF 防护 + 会话成本 |
| Phase 33: Infra 杂项 + 非通道扩展 | **已完成** | SSH/SCP + 系统事件总线 + 归档管理 + Lobster/LLM-Task/Copilot/OTEL 扩展 + Shared 工具 + Exec 加固 |
| Phase 34: Browser 自动化 | **已完成** | Playwright 薄适配层: Session Manager + Navigation Guard + Agent Tools + Bridge Server + Screenshot |
| Phase 35: Pi Embedded Runner | **已完成** | Run 循环 + Session Manager + Thinking/Extensions + Tool Guards + Provider Helpers |
| Phase 36: Channel Plugins 深度 | **已完成** | 通道目录 + 6 通道 Onboarding 向导 + 6 通道 Outbound 适配 + 5 通道 Status Issues + Config Schema |
| Phase 37: Gateway Methods + Sessions | **已完成** | 15 扩展 RPC 方法 + Chat 高级 (附件/净化/中止) + Sessions 高级 (覆盖/标签/转录) + Exec Approvals |
| Phase 38: TUI/Models/Wizard/杂项 | **已完成** | Boot-MD + Extra Files + Command Logger + Model Probe/Scan + Wizard Session + Shell 补全 + Discord Voice + VoiceWake + Respawn + 6 额外 LLM 提供商 |
| Phase 39: CLI 命令面覆盖 | **已完成** | `pyclaw` 主命令切换 + `agent` v2 参数面 + `acp/sessions/logs/system/browser/health` 入口对齐 |
| Phase 40: ACP 生产化 | **已完成** | `pyclaw acp`/`acp client` 参数齐全 + session key/label 映射 + require-existing/reset 语义 + token/password file |
| Phase 41: Usage/Cost + 方法接线 | **已完成** | extended/exec_approvals 注册可达 + usage ledger 持久化聚合 + `status --usage` + models probe/scan/auth-overview |
| Phase 42: Browser CLI 端到端 | **已完成** | browser CLI 全局 `--url/--token/--timeout` + Gateway `browser.*` RPC + SSRF 导航守卫 + 截图输出链路 |
| Phase 43: 文档一致性收敛 | **已完成** | `PROGRESS/gap/plan` 滚动更新 + docs parity contract 测试 + `pyclaw` 命名一致性守卫 |
| Phase 44: Gateway 控制面 + Logs RPC + 去重 | **已完成** | `gateway status/probe/call/discover` 子命令树 + `logs.tail` RPC + CLI 远程日志 + `pyclaw` 文案全量收敛 + extended.py browser 占位移除 |
| Phase 45: Embedded Runner 主路径接线 | **已完成** | `chat.send` 默认走 embedded runner + `runner.mode` 配置开关(embedded/legacy) + abort/usage 一致性 + 成本记录 |
| Phase 46: 扩展 RPC 去占位 | **已完成** | `doctor.run` 接入真实诊断 + `system.logs` 读取日志文件(含 level 过滤) + `skills.list` 发现技能 |
| Phase 47: CLI 深水区收敛 | **已完成** | `sessions cleanup --dry-run/--enforce/--active-key` + `security audit --deep/--fix/--json` + system CLI RPC-first fallback |
| Phase 48: Browser 控制深化 | **已完成** | `browser profiles/create-profile/delete-profile/focus/close` 子命令 + RPC 接线 |
| Phase 49: 命名一致性 + 契约加固 | **已完成** | ACP `--token-file/--password-file` + `pyclaw` 文案统一 + docs parity 扩展测试 |
| Phase 50: MCP + Docker 部署 | **已完成** | MCP 客户端 (stdio+HTTP) + McpToolAdapter + MCP CLI + Dockerfile + docker-compose.yml |
| Phase 51: DingTalk + QQ + OAuth CLI + 技能市场 | **已完成** | DingTalk Stream 通道 + QQ WebSocket 通道 + OAuth/Device-Code CLI + ClawHub 技能搜索/安装 + Workspace 模板同步 |
| Phase 52: Agent 社交网络 | **已完成** | 社交平台注册表 + Moltbook/ClawdChat 适配 + 社交技能包 + Agent 工具 |
| Phase 53: Progress + 语音 | **已完成** | ProgressEvent + Gateway 广播 + 工具/技能嵌入 + Flet UI 进度条 + 语音转录 |
| Phase 54: Browser RPC 真执行化 | **已完成** | Gateway browser 方法改为复用 Playwright 实际执行器 + profiles/createProfile/deleteProfile/focus/close RPC 实现 + 真实截图与 DOM 快照 |
| Phase 55: Chat 主路径收敛 | **已完成** | chat.send 接入 chat_advanced 参数校验/内容净化/时间注入 + chat.edit/chat.resend 实现 + usage/abort 一致性 |
| Phase 56: System/Logs RPC-first | **已完成** | system.event/heartbeat.last/presence Gateway RPC + CLI fallback 显式警告 |
| Phase 57: Extended 去占位 | **已完成** | wizard/push/voicewake/tts 改为 NOT_IMPLEMENTED + update.check 读取真实版本 + web.status 反映真实 Gateway 状态 |
| Phase 58: 文档基线重建 | **已完成** | docs/reference 差距与进度基线重建 + API 参考更新 + 契约测试 |
| Phase 59: Gateway 控制面子命令补齐 | **已完成** | `gateway status/probe/call/discover` 已在 Phase 44 实现完毕，验证确认对齐 + api-reference 文档更新 |
| Phase 60: 发布与分发最后一环 | **已完成** | Homebrew formula + 分发文档完善 (pipx/brew 安装路径) |
| Phase 61: 契约与文档持续守护 | **已完成** | CI 独立契约测试 step + 季度复核 upstream 流程文档 + 自动化守护说明 |
| Phase 62: 本地模型运行时 | **已完成** | llama.cpp + MLX 后端 + HuggingFace/ModelScope 下载 + manifest 管理 + CLI 命令 (download/local/delete-local/select) |
| Phase 63: 桌面截图 + 文件发送 | **已完成** | mss 跨平台截图 + macOS screencapture + send_file 工具 + 工具注册 |
| Phase 64: 一键安装脚本 | **已完成** | install.sh (macOS/Linux) + install.ps1 (Windows) + --extras 参数 + uninstall 命令 |
| Phase 65: Office 文件技能包 | **已完成** | PDF/DOCX/XLSX/PPTX 读取工具 + SKILL.md + pyproject office extra |
| Phase 66: Heartbeat 增强 | **已完成** | HEARTBEAT.md 文件驱动 + compound 间隔 (2h30m) + target=last 通道分发 + 活跃时段 |
| Phase 67: MCP 热重载 | **已完成** | McpConfigWatcher 配置变更自动重连 + 文档更新 |

## 代码统计

- 源码: **~58,000 行** (~410 个 .py 文件)
- 测试: **~17,300 行** (78 个测试文件, 1848 个测试)
- 测试状态: **1848/1848 通过**
- 通道总数: **25 个** (6 核心 + 7 P3 扩展 + 12 P4/P5 扩展)

---

## 架构概览

```
openclaw-py/
├── src/openclaw/
│   ├── agents/           # Agent 运行时
│   │   ├── runner.py     # 核心循环 (stream → tool → loop)
│   │   ├── stream.py     # 多提供商 LLM 流式 (OpenAI/Anthropic/Gemini/Ollama)
│   │   ├── session.py    # JSONL DAG 会话管理 + compaction
│   │   ├── auth_profiles/# 多模式认证 (API key/token/OAuth)
│   │   ├── subagents/    # 子 Agent 管理 (spawn/steer/kill)
│   │   ├── skills/       # Skills 系统 (SKILL.md 发现/过滤/提示 + 技能市场)
│   │   ├── workspace_sync.py # Workspace 模板同步
│   │   ├── model_catalog.py # 模型目录 (provider + 元数据)
│   │   ├── tool_policy.py   # 工具策略 (group/plugin allowlist)
│   │   └── tools/        # 20+ 内置工具 (含 MCP 外部工具)
│   ├── channels/         # 消息通道 (25 个)
│   │   ├── telegram/     # aiogram
│   │   ├── discord/      # discord.py
│   │   ├── slack/        # slack-bolt
│   │   ├── whatsapp/     # neonize (Baileys)
│   │   ├── signal/       # signal-cli JSON-RPC/SSE
│   │   ├── imessage/     # imsg JSON-RPC (P2)
│   │   ├── irc/          # 原生 TCP/TLS (P3)
│   │   ├── msteams/      # Bot Framework + Graph API (P3)
│   │   ├── matrix/       # matrix-nio (P3)
│   │   ├── feishu/       # Feishu Open Platform (P3)
│   │   ├── twitch/       # Twitch IRC (P3)
│   │   ├── bluebubbles/  # REST webhook (P3)
│   │   └── googlechat/   # Google Chat webhook (P3)
│   ├── mcp/              # MCP (Model Context Protocol) 客户端
│   │   ├── types.py      # JSON-RPC 2.0 + McpServerConfig
│   │   ├── client.py     # 服务器连接 + 工具发现
│   │   ├── registry.py   # 多服务器管理 + McpToolAdapter
│   │   ├── stdio_transport.py  # 子进程 stdio 传输
│   │   └── http_transport.py   # 远程 HTTP 传输
│   ├── cli/              # Typer CLI (25+ 命令)
│   ├── config/           # 配置管理 (Pydantic + JSON5)
│   ├── cron/             # 定时任务 (APScheduler)
│   ├── gateway/          # Gateway 服务器
│   │   ├── server.py     # FastAPI + WebSocket v3
│   │   ├── openai_compat.py # OpenAI Chat Completions API
│   │   ├── plugin_routes.py # 插件 HTTP 路由
│   │   └── methods/      # 20+ 方法处理器
│   ├── hooks/            # 事件 Hook 框架 (P2)
│   │   ├── registry.py   # register/trigger/clear
│   │   ├── loader.py     # HOOK.md 发现
│   │   └── bundled/      # session-memory
│   ├── infra/            # 基础设施
│   │   ├── retry.py      # 重试策略
│   │   ├── rate_limit.py # 速率限制
│   │   ├── exec_approvals.py # Exec 审批 (P2)
│   │   ├── heartbeat.py  # 心跳运行器 (P2)
│   │   ├── update_check.py  # 更新检查 (P2)
│   │   └── provider_usage.py # Provider 用量 (P2)
│   ├── logging/          # 日志子系统 (P2)
│   │   ├── subsystem.py  # 分类彩色日志
│   │   └── redact.py     # 敏感数据脱敏
│   ├── markdown/         # Markdown IR + 多通道渲染 (P2)
│   │   ├── ir.py         # 中间表示
│   │   ├── render.py     # 可插拔标记渲染
│   │   ├── channel_formats.py # WhatsApp/Telegram/Signal/Slack
│   │   ├── tables.py     # 表格转换
│   │   └── fences.py     # 代码块检测
│   ├── media/            # 媒体处理
│   │   ├── understanding/# 多 Provider 媒体理解 (P2)
│   │   │   ├── providers/ # OpenAI/Google/Anthropic
│   │   │   └── apply.py  # 编排
│   │   ├── images.py, audio.py, mime.py, storage.py
│   │   └── embeddings.py # 向量嵌入
│   ├── memory/           # 记忆/RAG
│   ├── pairing/          # 设备配对 (P2)
│   │   ├── store.py      # 请求/allowFrom 持久化
│   │   ├── challenge.py  # 挑战响应流程
│   │   └── setup_code.py # 二维码/深链接编码
│   ├── plugins/          # 插件系统
│   ├── routing/          # 会话路由
│   ├── security/         # 安全 (P2)
│   │   ├── dm_policy.py  # DM/群组访问策略
│   │   └── audit.py      # 配置安全审计
│   ├── terminal/         # 终端工具 (ANSI 表格/调色板)
│   ├── acp/              # Agent Control Protocol (P3)
│   │   ├── types.py      # 协议类型
│   │   ├── session.py    # 会话存储 + TTL 驱逐
│   │   ├── server.py     # NDJSON stdio 桥接
│   │   └── client.py     # 子进程客户端
│   ├── canvas/           # Canvas Host (P3)
│   │   ├── handler.py    # 文件解析 + live-reload 注入
│   │   └── server.py     # HTTP + WebSocket 服务
│   ├── node_host/        # 无头节点服务 (P3)
│   │   ├── invoke.py     # 命令分发 (system.run/which)
│   │   └── runner.py     # Gateway WebSocket 连接
│   ├── daemon/           # 服务管理 (P3)
│   │   ├── service.py    # 跨平台抽象
│   │   ├── launchd.py    # macOS LaunchAgent
│   │   ├── systemd.py    # Linux systemd
│   │   └── schtasks.py   # Windows 计划任务
│   └── ui/               # Flet UI
│       ├── app.py        # 主应用 (Chat + Settings + Channels)
│       ├── channels_panel.py # 通道状态面板 (P2)
│       ├── media_preview.py  # 媒体预览 (P2)
│       ├── onboarding.py    # 首次使用向导 (P2)
│       ├── voice.py      # Voice 交互 (P3)
│       └── tray.py       # 系统托盘
├── tests/                # 9 个测试文件, 97 个测试
├── pyproject.toml        # Hatch + 依赖
└── docs/
    ├── PROGRESS.md       # 本文档
    └── reference/
        ├── gap-analysis.md
        └── python-flet-rewrite-plan.md
```

---

## P2 增强功能清单 (Phase 8)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Hooks 系统 | 6 | 事件注册/触发, HOOK.md 加载, session-memory bundled hook |
| Exec 审批 | 1 | allowlist, 交互式审批, 节点转发 |
| Heartbeat | 1 | 心跳运行器, active hours, wake |
| 更新检查 | 1 | 版本比较, npm registry, git 状态 |
| Provider 用量 | 1 | 多 provider 用量获取 |
| Tool Policy | 1 | group-scoped, plugin allowlist, owner-only |
| 设备配对 | 4 | challenge flow, allowFrom store, setup code |
| 日志子系统 | 3 | subsystem logger, 敏感数据脱敏 |
| Security | 3 | DM/群组策略, 配置审计 |
| Markdown | 6 | IR, render, tables, fences, 通道格式转换 |
| iMessage | 3 | JSON-RPC client, channel 实现 |
| Media Understanding | 7 | 类型, 注册, apply, 3 providers |
| Gateway 扩展 | 4 | tools.catalog, cron.*, device.pair.*, plugin routes |
| CLI 扩展 | 2 | devices, message send |
| UI 增强 | 3 | channels panel, media preview, onboarding |

**新增: 47 个文件, ~4,500 行代码**

---

## P3 完善功能清单 (Phase 9)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| 扩展通道 | 14 | IRC, MS Teams, Matrix, Feishu, Twitch, BlueBubbles, Google Chat (每个 2 文件) |
| ACP | 5 | types, session (TTL + 驱逐), server (NDJSON stdio), client |
| Canvas Host | 3 | handler (文件解析 + live-reload), server (HTTP + WebSocket) |
| Node Host | 3 | invoke (system.run/which 分发), runner (Gateway 连接) |
| Daemon | 4 | service 抽象, launchd (macOS), systemd (Linux), schtasks (Windows) |
| QMD | 2 | SQLite 存储 + 向量语义搜索 + 标签 + CRUD |
| Gateway 控制面板 | 1 | SPA 服务 + bootstrap config + CSP 安全头 |
| Gmail Watcher | 1 | Gmail API OAuth2 + 新邮件检测 + 摘要 |
| Voice UI | 1 | edge-tts 语音合成 + Whisper 转录 + Flet 面板 |
| 工具补全 | 3 | nodes (list/invoke), gateway (status/config/restart), canvas (read/write/list/snapshot) |
| CLI 扩展 | 2 | service (install/uninstall/status/restart/stop), node (启动无头节点) |

**新增: 40 个文件, ~3,400 行代码**

---

### Phase 10-13: 质量加固 + P4 功能 + 原生 App

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| 测试补全 (10a) | 15 | hooks, markdown, security, pairing, infra, acp, daemon, qmd, logging, canvas, node_host, terminal, gateway methods, ext channels, tools extra |
| 工程化 (10b) | 0 | pyproject.toml: coverage, optional deps, scripts |
| CI/CD (10c) | 2 | .github/workflows/ci.yml + release.yml |
| mDNS (11a) | 1 | infra/bonjour.py (zeroconf 服务发现) |
| Tailscale (11b) | 1 | infra/tailscale.py (CLI 集成, funnel, whois) |
| 简单通道 (12a) | 6 | Synology Chat, Mattermost, Nextcloud Talk |
| 中等通道 (12b) | 6 | Tlon/Urbit, Zalo Bot, Zalo User |
| 复杂通道 (12c) | 4 | Nostr (NIP-04), LINE Messaging API |
| Voice Call (12d) | 4 | Twilio provider + 抽象层 + channel + types |
| 原生 App (13) | 3 | flet_app.py 入口 + build-desktop.sh + build-mobile.sh |

**新增: ~22 个源码文件 + 15 个测试文件, ~4,800 行代码**

---

### Phase 14: 核心功能对齐 (P0)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| ACP 增强 (14a) | 5 | control_plane.py, acpx_runtime.py, session_mapper.py, event_mapper.py, thread_ownership.py |
| Secrets (14b) | 8 | secrets/ 模块 (\_\_init\_\_, audit, resolve, plan, apply, runtime) + CLI + Gateway method |
| Bindings (14c) | 2 | routing/bindings.py (7 级优先级路由) + CLI (bindings/bind/unbind) |
| Codex (14d) | 3 | openresponses_http.py + transports/\_\_init\_\_.py + transports/codex.py |
| 测试 | 4 | test_acp_enhanced.py, test_secrets.py, test_bindings.py, test_openresponses.py |

**新增: ~17 个源码文件 + 4 个测试文件, ~2,700 行代码, 92 个新测试**

---

### Phase 15: 重要增强 (P1)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Android Nodes (15a) | 1 | node_command_policy.py (平台命令白名单 + 能力发现 + 工具定义生成) |
| Onboarding Hooks (15b) | 1 | plugins/onboarding.py (configureInteractive + configureWhenConfigured + OnboardingRunner) |
| Thread Lifecycle (15c) | 1 | channels/thread_bindings_policy.py (idle/max-age TTL + 自动清扫 + 多层配置解析) |
| 现有文件增强 | 1 | tools/nodes.py (集成 node_command_policy) |
| 测试 | 3 | test_node_command_policy.py, test_onboarding_hooks.py, test_thread_lifecycle.py |

**新增: 4 个源码文件 + 3 个测试文件, ~1,100 行代码, 52 个新测试**

---

### Phase 16: 扩展功能 (P2)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Memory Backend (16a) | 2 | memory/backend.py (MemoryBackend 协议 + MemoryManager + auto-recall/capture) + memory/lancedb_backend.py |
| Extensions (16b) | 1 | plugins/extensions.py (Extension 基类 + ExtensionRegistry + 拓扑排序依赖加载) |
| i18n (16c) | 1 | ui/i18n.py (I18n 管理器 + 3 语言内置翻译 + 文件加载 + 全局实例) |
| 测试 | 3 | test_memory_backend.py, test_extensions.py, test_i18n.py |

**新增: 4 个源码文件 + 3 个测试文件, ~1,200 行代码, 40 个新测试**

---

### Phase 17: 安全加固 (P3)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Exec Approval (17a) | 1 | security/exec_approval.py (CommandArgvRule + SystemRunApprovalBindingV1 + ExecApprovalPolicy) |
| Gateway Hardening (17b) | 1 | security/gateway_hardening.py (env hashing + HTTP auth 规范化 + pairing metadata pinning + webhook replay guard) |
| Sandbox (17c) | 1 | security/sandbox.py (路径消毒 + WorkspaceBoundary + ConfigIncludeLoader 深度/循环检测) |
| 测试 | 3 | test_exec_approval.py, test_gateway_hardening.py, test_sandbox.py |

**新增: 3 个源码文件 + 3 个测试文件, ~1,300 行代码, 73 个新测试**

---

### Phase 18: 核心管道补全 (P0-P1)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Auto-reply (18a) | 1 | agents/auto_reply.py (NO_REPLY 抑制 + 流式 sentinel 过滤 + HEARTBEAT 检测 + 时间戳) |
| Typing (18b) | 1 | channels/typing_manager.py (跨通道 typing + TTL 安全网 + 断路器 + run-scoped 生命周期) |
| Outbound (18c) | 1 | channels/outbound.py (消息分片 + 格式 fallback Markdown→HTML→plain + 通道 max size) |
| Delivery (18d) | 1 | infra/delivery.py (异步投递队列 + 指数退避重试 + 优先级 + deferred 恢复) |
| Model Fallback (18e) | 1 | agents/model_fallback.py (多级 fallback 链 + 错误分类 + cooldown + 同 provider fallback) |
| 测试 | 5 | test_auto_reply.py, test_typing_manager.py, test_outbound.py, test_delivery.py, test_model_fallback.py |

**新增: 5 个源码文件 + 5 个测试文件, ~1,800 行代码, 80 个新测试**

---

### Phase 19: Feishu 深度对齐 (P1-P2)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Reactions (19a) | 1 | feishu/reactions.py (reaction.created/deleted 事件解析 + 合成 turn + 通知模式 off/own/all) |
| Docx (19b) | 1 | feishu/docx.py (表格创建/写入 + 图片/文件上传 + 权限管理 + 顺序块插入) |
| Routing (19c) | 1 | feishu/routing.py (group session scope 4 模式 + reply-in-thread + groupSenderAllowFrom + 多级覆盖) |
| Messages (19d) | 1 | feishu/messages.py (merge_forward 展开 + rich-text 解析 + 媒体类型映射 + share_chat) |
| Runtime (19e) | 1 | feishu/runtime.py (probe 缓存 10min TTL + typing backoff 断路器 + webhook 速率限制) |
| 测试 | 1 | test_feishu_enhanced.py |

**新增: 5 个源码文件 + 1 个测试文件, ~1,400 行代码, 60 个新测试**

---

### Phase 20: 通道安全统一 (P1-P2)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Auth Guard (20a) | 1 | channels/auth_guard.py (统一 DM/group/reaction/interaction/file_upload 授权 + fail-closed + rate limiter + deny log + owner bypass) |
| Allowlist 边界 (20b) | 1 | security/allowlist_boundaries.py (DM-group 隔离 + pairing-store DM-only 强制 + 通道级 scope + 违规检测) |
| 审计扩展 (20c) | 1 | security/audit_extra.py (Gateway HTTP/TLS/CORS + plugins 信任/隔离 + hooks 安全 + channels 审计) |
| 危险工具 (20d) | 1 | security/dangerous_tools.py (风险注册表 + skill 扫描 + 外部内容策略 + HTML 消毒) |
| 测试 | 1 | test_channel_security.py |

**新增: 4 个源码文件 + 1 个测试文件, ~1,800 行代码, 68 个新测试**

---

### Phase 21: Gateway + Agent 加固 (P2)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| WS Flood Guard (21a) | 1 | gateway/ws_guard.py (per-IP 滑动窗口限速 + 自动 ban + IP 上限 + 采样日志 + 事件审计) |
| Compaction (21b) | 1 | agents/compaction_policy.py (identifier 保留 + 近重复检测 + 不可用工具修剪 + 角色保留策略) |
| Config 迁移 (21c) | 1 | config/migrations.py (版本检测 + v1→v2→v3 迁移 + dry-run + State 迁移框架) |
| Command Gating (21d) | 1 | channels/command_gating.py (16 个内置命令权限 + 通道/全局覆盖 + owner_only + deny_unlisted) |
| 测试 | 1 | test_gateway_agent_hardening.py |

**新增: 4 个源码文件 + 1 个测试文件, ~1,500 行代码, 51 个新测试**

---

### Phase 22: Telegram + Browser 增强 (P2-P3)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Telegram 增强 (22a) | 1 | channels/telegram/enhanced.py (Reply 媒体上下文提取 + 4096-char chunking + MarkdownV2 转义 + HTML fallback + sendChatAction 退避断路器) |
| Browser Relay (22b) | 1 | browser/relay.py (Chrome Extension WebSocket relay + CORS origin 验证 + token 认证 + 心跳/重连 + 会话管理) |
| Link Understanding (22c) | 1 | agents/link_understanding.py (URL 提取 + OG metadata 解析 + 内容类型分类 + 格式化上下文注入) |
| 测试 | 1 | test_telegram_browser.py |

**新增: 3 个源码文件 + 1 个测试文件, ~1,200 行代码, 58 个新测试**

---

### Phase 23: Extensions + 杂项 (P2-P3)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Memory-core (23a) | 1 | plugins/extensions/memory_core.py (Extension 生命周期 + 4 个 memory tools + auto-recall/capture hooks + 关键词搜索) |
| Gemini CLI Auth (23b) | 1 | plugins/extensions/gemini_cli_auth.py (PKCE 生成 + OAuth URL 构建 + token 交换/刷新 + 凭证管理) |
| Ollama 增强 (23c) | 1 | agents/providers/ollama_enhanced.py (加固 autodiscovery + context window 统一解析 + 日志降级 + 能力检测) |
| i18n 德语 (23d) | 1 | ui/locales/de.json (48 个翻译键覆盖全部 UI 类别) |
| 测试 | 1 | test_extensions_misc.py |

**新增: 4 个源码文件 + 1 个测试文件, ~1,000 行代码, 42 个新测试**

---

### Phase 24: 斜杠命令系统 (P0)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| 命令注册表 (24a) | 1 | auto_reply/commands_registry.py (CommandDef/ParsedCommand 定义 + 前缀匹配解析 + scope 检查 + 20+ 内置命令注册) |
| 核心命令 (24b) | 1 | auto_reply/commands_core.py (/help, /status, /whoami, /context, /usage, /export 处理器) |
| 会话命令 (24c) | 1 | auto_reply/commands_session.py (/session new/reset/list/idle/max-age + /stop + /compact) |
| 模型命令 (24d) | 1 | auto_reply/commands_model.py (/model 切换+前缀匹配 + /think low/medium/high + /debug) |
| 内联指令 (24e) | 1 | auto_reply/directives.py (@think/@model/@verbose/@reasoning/@elevated/@exec 解析 + fast-lane + 持久化) |
| 消息队列 (24f) | 1 | auto_reply/message_queue.py (steer/interrupt/followup/collect 模式 + 防抖 + 上限 + 丢弃策略 + 去重) |
| 回复调度器 (24g) | 1 | auto_reply/reply_dispatcher.py (路由分发 + 来源路由 + LRU 去重 + 调度器注册表) |
| 测试 | 1 | test_auto_reply_commands.py |

**新增: 7 个源码文件 + 1 个测试文件, ~1,613 行源码 + 462 行测试, 46 个新测试**

---

### Phase 25: 流式分块 + 投递管道 (P0-P1)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| 流式分块 (25a) | 1 | auto_reply/block_streaming.py (per-provider min/max chars + 段落刷新 + 块合并 + 流式指令过滤) |
| 投递目标解析 (25b) | 1 | infra/outbound/target_resolver.py (agent binding 路由 + 会话来源 + 多通道目标 + 通道选择) |
| 发送服务 (25c) | 1 | infra/outbound/send_service.py (统一发送 + 信封/身份 + conversation-id + 格式 fallback) |
| 消息动作 (25d) | 1 | infra/outbound/message_actions.py (reaction/button/pin/delete 动作 + retry + 队列执行) |
| 通道适配器 (25e) | 1 | infra/outbound/channel_adapters.py (ChannelAdapter Protocol + 能力检测 + 适配器注册表 + 选择器) |
| HTML 导出 (25f) | 1 | auto_reply/export_html.py (Markdown→HTML + 工具调用渲染 + dark/light 主题 + CSS 样式) |
| 测试 | 1 | test_streaming_delivery.py |

**新增: 6 个源码文件 + 1 个测试文件, ~918 行源码 + 337 行测试, 33 个新测试**

---

### Phase 26: LLM 提供商扩展 (P1)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| OpenAI 兼容适配器 (26a) | 1 | agents/providers/openai_compat.py (通用 OpenAI-compat API + SSE/NDJSON 解析 + 5 预配置: Together/OpenRouter/Fireworks/Groq/Perplexity) |
| 中国提供商 (26b) | 1 | agents/providers/cn_providers.py (9 提供商: Moonshot/Volcengine/BytePlus/MiniMax/Xiaomi/Qianfan/Zhipu/DeepSeek/Qwen + 模型映射) |
| OAuth 提供商 (26c) | 1 | agents/providers/oauth_providers.py (PKCE + MiniMax Portal OAuth + Qwen Portal OAuth + GitHub Copilot Device Flow) |
| 提供商注册表 (26d) | 1 | agents/providers/registry.py (统一注册/发现/激活 + qualified name 解析 + builder 协议) |
| Bedrock 提供商 (26e) | 1 | agents/providers/bedrock.py (Converse Stream API + 8 模型映射 + boto3 配置 + 工具格式转换) |
| 测试 | 1 | test_providers_extended.py |

**新增: 5 个源码文件 + 1 个测试文件, ~1,205 行源码 + 509 行测试, 63 个新测试**

---

### Phase 27: Channel Plugin SDK (P1)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| 适配器协议 (27a) | 1 | channels/plugin_sdk/adapters.py (20+ Protocol: config/auth/pairing/security/groups/mentions/outbound/status/streaming/threading/actions/commands/heartbeat/directory/resolver/elevated/agentPrompt/agentTools/typing/webhook + 能力检测) |
| 草稿流式 (27b) | 1 | channels/plugin_sdk/draft_stream.py (DraftStream 生命周期 + throttle + stop/clear + DraftStreamManager) |
| 确认反应 (27c) | 1 | channels/plugin_sdk/ack_reactions.py (5 reaction scopes + 5 status types + emoji 映射 + AckReactionManager) |
| 模型覆盖 (27d) | 1 | channels/plugin_sdk/model_overrides.py (channel/group 模型选择 + allowed/blocked 列表 + CapabilitySchema) |
| 提及门控 (27e) | 1 | channels/plugin_sdk/mention_gating.py (@mention 检测 + 命令旁路 + user ID 模式 + 提及剥离) |
| 通道状态检查 (27f) | 1 | channels/plugin_sdk/status_issues.py (健康检查框架 + ConfigSchema → JSON Schema + MediaLimits + 内置检查) |
| 测试 | 1 | test_plugin_sdk.py |

**新增: 6 个源码文件 + 1 个测试文件, ~1,140 行源码 + 485 行测试, 54 个新测试**

---

### Phase 28: Config 系统深化 (P1-P2)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| 环境变量替换 (28a) | 1 | config/env_substitution.py (${VAR} 语法 + ${VAR:-default} + $${} 转义 + 大写限制 + 递归替换 + 校验) |
| Config Includes (28b) | 1 | config/includes.py ($include 路径解析 + 深度/循环/文件数限制 + 深度合并) |
| 备份轮转 (28c) | 1 | config/backup.py (写入前自动备份 + 最大保留数 + 时间戳命名 + 原子写入) |
| Session Store (28d) | 1 | config/session_store.py (CRUD + JSONL 转录 + 投递记录 + 磁盘预算 + 列表/过滤) |
| 运行时覆盖 (28e) | 1 | config/runtime_overrides.py (群组策略 + 通道能力覆盖 + 插件自动启用 + 配置快照脱敏) |
| 测试 | 1 | test_config_advanced.py |

**新增: 5 个源码文件 + 1 个测试文件, ~913 行源码 + 405 行测试, 45 个新测试**

---

### Phase 29: 进程管理 + 媒体理解扩展 (P2)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| 进程监管器 (29a) | 1 | process/supervisor.py (spawn/cancel/scope-based 生命周期 + 递归终止 + 重启退避 + PTY 适配) |
| 命令队列 (29b) | 1 | process/command_queue.py (lane-based 队列 + drain/clear + CommandLaneClearedError + GatewayDrainingError) |
| 媒体理解扩展 (29c) | 1 | media/understanding/extended.py (Groq 音频/视觉 + Mistral 视觉 + Deepgram 音频转录 + xAI 视觉 + 提供商选择) |
| 视频理解 (29d) | 1 | media/understanding/video.py (帧提取时间戳 + Moonshot/MiniMax 视频适配器 + 音频预检 + 并发限制器) |
| Memory 扩展 (29e) | 1 | memory/extended.py (Voyage/Mistral 嵌入提供商 + 批量上传管道 + 远程嵌入 HTTP 客户端) |
| 测试 | 1 | test_process_media.py |

**新增: 5 个源码文件 + 1 个测试文件, ~1,272 行源码 + 486 行测试, 58 个新测试**

---

### Phase 30: Gateway 高级功能 (P2)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| 配置热重载 (30a) | 1 | gateway/config_reload.py (文件监听 + 配置 diff + hot/restart 策略 + 防抖) |
| 通道健康监控 (30b) | 1 | gateway/channel_health.py (周期检查 + 冷却 + 最大重启限制/小时 + 历史记录) |
| 控制面限速 (30c) | 1 | gateway/control_plane_rate_limit.py (per device+IP 滑动窗口 3 req/60s) |
| Hooks 映射 (30d) | 1 | gateway/hooks_mapping.py (gmail/webhook 预设 + 模板替换 + resolve/apply) |
| 服务发现 (30e) | 1 | gateway/discovery.py (mDNS 广播 + Tailscale DNS + URL 解析优先级) |
| 测试 | 1 | test_gateway_advanced.py |

**新增: 5 个源码文件 + 1 个测试文件, ~966 行源码 + 396 行测试, 46 个新测试**

---

### Phase 31: Commands / Doctor / Onboarding (P2)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Doctor 诊断 (31a) | 1 | cli/commands/doctor_flows.py (9 项诊断: config/auth/sandbox/gateway/workspace/memory/state/security/platform + 修复建议 + 注册表) |
| Provider 认证 (31b) | 1 | cli/commands/auth_providers.py (27 提供商 AuthSpec + API Key/OAuth/Device Code 流 + CredentialStore 持久化 + 验证) |
| Onboarding 增强 (31c) | 1 | cli/commands/onboarding_enhanced.py (7 步流程 + 交互/非交互模式 + 风险确认 + Gateway + 认证 + 技能) |
| Status 增强 (31d) | 1 | cli/commands/status_enhanced.py (8 子系统收集器 + summary/deep/scan 模式 + 文本格式化) |
| Models CLI (31e) | 1 | cli/commands/models_cmd.py (12 内置模型 + 别名管理 + fallback 链 + 图像 fallback + 提供商列表) |
| Channels CLI (31f) | 1 | cli/commands/channels_enhanced.py (9 通道 Spec + 能力列表 + 配置验证 + 配置变换器 + 摘要) |
| 测试 | 1 | test_cli_enhanced.py |

**新增: 6 个源码文件 + 1 个测试文件, ~1,557 行源码 + 474 行测试, 75 个新测试**

---

### Phase 32: Cron/TTS/Logging 高级 (P2-P3)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Cron 高级 (32a) | 1 | cron/advanced.py (隔离代理运行器 + 技能快照 + 任务交错 + 超时策略 + 会话收割器 + Webhook 触发) |
| TTS 扩展 (32b) | 1 | agents/tts_extended.py (ElevenLabs + OpenAI TTS 提供商 + 自动模式 off/always/inbound/tagged + 长文本摘要 + 语音验证 + 指令解析) |
| Logging 高级 (32c) | 1 | logging/advanced.py (文件轮转 + 大小限制 + 标识符脱敏 email/IP/phone/API key + 诊断会话状态 + 日志行解析与过滤) |
| SSRF 防护 (32d) | 1 | security/ssrf.py (私有 IP/localhost 拦截 + DNS 解析验证 + 域名白名单/黑名单 + 端口限制 + SSRFGuard) |
| 会话成本 (32e) | 1 | infra/session_cost.py (token 计费 + 7 个模型定价 + 用量聚合 + 格式化输出 + UsageAggregator) |
| 测试 | 1 | test_cron_tts_logging.py |

**新增: 5 个源码文件 + 1 个测试文件, ~950 行源码 + 325 行测试, 53 个新测试**

---

### Phase 33: Infra 杂项 + 非通道扩展 (P3)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| SSH/SCP (33a) | 1 | infra/ssh.py (SSH config 解析 + 主机别名解析 + 隧道命令构建 local/reverse + SCP 传输命令构建) |
| 系统事件 (33b) | 1 | infra/system_events.py (EventBus 发布/订阅 + 全局处理器 + 事件历史 + PresenceManager 在线/离线/闲置 + WakeManager 睡眠/唤醒) |
| 归档管理 (33c) | 1 | infra/archive.py (会话/配置归档 + gzip 压缩 + 路径管理 + 归档列表 + 留存清理) |
| 非通道扩展 (33d) | 1 | plugins/contrib/misc_extensions.py (Lobster 管道工作流 + LLM-Task JSON 执行 + Copilot Proxy + Diagnostics OTEL 导出) |
| Shared 工具 (33e) | 1 | shared/utils.py (推理标签提取/剥离 + 代码区域检测 + frontmatter 解析 + API key 遮蔽 + 安全 JSON + 超时包装 + 并发控制 + 用量聚合) |
| Exec 加固 (33f) | 1 | security/exec_hardening.py (命令混淆检测 6 种模式 + 包装器解析 + 安全二进制策略 + 审批转发构建) |
| 测试 | 1 | test_infra_misc.py |

**新增: 6 个源码文件 + 1 个测试文件, ~1,050 行源码 + 480 行测试, 68 个新测试**

---

### Phase 34: Browser 自动化 (Playwright 薄适配层) (P1)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Session Manager (34a) | 1 | browser/session_manager.py (Playwright browser/context 生命周期 + Profile 持久化 + 并发限制 + 空闲超时清理) |
| Navigation Guard (34b) | 1 | browser/navigation_guard.py (SSRF 安全导航 + data:/blob:/javascript: URL 策略 + 重定向链检查 + 域名黑白名单) |
| Agent Tools (34c) | 1 | browser/agent_tools.py (19 种 Action Type + BrowserToolExecutor + DOM 快照 + 工具定义 + tool call 解析) |
| Bridge Server (34d) | 1 | browser/bridge_server.py (Token 认证注册 + Tab 发现/缓存 + DOM 快照转发 + CSRF 保护 + Relay 整合) |
| Screenshot (34e) | 1 | browser/screenshot.py (Playwright/CDP 双通道截图 + 全页/元素/区域 + 裁剪缩放 + Base64/DataURL 编码) |
| 测试 | 1 | test_browser_automation.py |

**新增: 5 个源码文件 + 1 个测试文件, ~1,200 行源码 + 430 行测试, 62 个新测试**

---

### Phase 35: Pi Embedded Runner (P1)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Run 循环 (35a) | 1 | agents/embedded_runner/run.py (RunConfig/RunRecord + Payload 构建 + 图片注入/修剪 + RunTracker + Message) |
| Session Manager (35b) | 1 | agents/embedded_runner/session_manager.py (会话缓存 + TTL 驱逐 + 历史限制 + 图片修剪 + Lane 解析) |
| Thinking (35c) | 1 | agents/embedded_runner/thinking.py (Thinking block 提取/剥离 + 上下文修剪 + 压缩安全检查 + AbortSignal) |
| Tool Guards (35d) | 1 | agents/embedded_runner/tool_guards.py (白名单/黑名单 + 上下文守卫 + 结果截断 + Schema 分割 + 缓存 TTL) |
| Helpers (35e) | 1 | agents/embedded_runner/helpers.py (错误映射 + OpenAI/Anthropic/Google Turn 构建 + 去重 + Bootstrap + Gemini Schema 清洗) |
| 测试 | 1 | test_embedded_runner.py |

**新增: 5 个源码文件 + 1 个测试文件, ~1,100 行源码 + 500 行测试, 69 个新测试**

---

### Phase 36: Channel Plugins 深度 (P2)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Channel Catalog (36a) | 1 | channels/plugins/catalog.py (6 内置通道目录 + UI 元数据 + MediaLimits + ActionSpec + AccountHelper + 分类/摘要) |
| Per-channel Onboarding (36b) | 1 | channels/plugins/onboarding.py (6 通道 Onboarding 向导 + 步骤验证 + 配置生成 + 流程注册表) |
| Per-channel Outbound (36c) | 1 | channels/plugins/outbound_adapters.py (6 通道 Outbound 适配器 + 消息分块 + 格式 fallback + 目标标准化) |
| Status Issues (36d) | 1 | channels/plugins/status_issues.py (5 通道问题检查器 + Config Schema 自动生成 + JSON Schema 导出) |
| 测试 | 1 | test_channel_plugins_deep.py |

**新增: 4 个源码文件 + 1 个测试文件, ~1,100 行源码 + 380 行测试, 44 个新测试**

---

### Phase 37: Gateway Methods + Sessions (P2)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| 扩展 RPC (37a) | 1 | gateway/methods/extended.py (15 个新 RPC: browser/tts/usage/system/doctor/skills/wizard/push/voicewake/update/web) |
| Chat 高级 (37b) | 1 | gateway/methods/chat_advanced.py (附件处理 + 内容净化 + 时间注入 + 参数验证 + ChatAbortManager) |
| Sessions 高级 (37c) | 1 | sessions/advanced.py (会话覆盖 + 转录事件 + 标签 + 输入来源追踪 + 发送策略) |
| Exec Approvals RPC (37d) | 1 | gateway/methods/exec_approvals.py (approve/deny/list/get/create + ApprovalStore + 过期/取消) |
| 测试 | 1 | test_gateway_methods_extended.py |

**新增: 4 个源码文件 + 1 个测试文件, ~1,050 行源码 + 370 行测试, 48 个新测试**

---

### Phase 38: TUI/Models/Wizard/杂项 (P3)

| 模块 | 新增文件 | 说明 |
|------|---------|------|
| Bundled Hooks (38a) | 1 | hooks/bundled/extra_hooks.py (Boot-MD 检查 + 工作空间文件加载 + 命令日志记录) |
| Models 深度 (38b) | 1 | cli/commands/models_deep.py (Model Probe + Scan + Auth Overview + Set Default + 表格格式化) |
| Wizard 会话 (38c) | 1 | wizard/session.py (多步骤状态机 + Clack 风格提示 + Shell 补全 + Gateway 引导 + Setup/Channel Wizard) |
| 杂项 (38d) | 1 | infra/misc_extras.py (Discord Voice + TLS 指纹 + VoiceWake + Respawn Tracker + Clipboard + Channel 校验 + Schema 清理) |
| 额外提供商 (38e) | 1 | agents/providers/extra_providers.py (Venice + HuggingFace + NvidiaNIM + vLLM + LiteLLM + KimiCoding) |
| 测试 | 1 | test_final_extras.py |

**新增: 5 个源码文件 + 1 个测试文件, ~1,300 行源码 + 450 行测试, 40 个新测试**

---

## 环境信息

- Python: 3.14.2
- 包管理: pip + venv
- 虚拟环境: `/Users/cs/projects/openclaw-py/.venv/`
- 构建系统: Hatch

---

## 当前状态

Phase 0-58 均已完成。项目包含:

- **~375 个 .py 源码文件** / **~51,000 LOC**
- **63 个测试文件** / **1,681 个测试全部通过**
- **23 个消息通道** (Telegram, Discord, Slack, WhatsApp, Signal, iMessage, IRC, MS Teams, Matrix, Feishu, Twitch, BlueBubbles, Google Chat, Synology, Mattermost, Nextcloud, Tlon, Zalo, ZaloUser, Nostr, LINE, Voice Call, Web)
- **CI/CD** (GitHub Actions: test + lint + release to PyPI)
- **原生 App 打包** (Flet build macOS/Linux/Windows/iOS/Android)
- **安全加固** (Exec approval bindings, sandbox boundaries, env hashing, webhook replay protection)

## 功能对齐状态

TypeScript 主项目 2026.2.25-2026.2.27 新增的 11 项功能已全部对齐 (Phase 14-17)。
Phase 18-23 补全了核心管道、通道安全、Gateway 加固、Extensions 等。
Phase 24-25 新增了完整的斜杠命令系统 (命令注册/解析/分发 + 内联指令 + 消息队列) 和流式投递管道 (block streaming + 目标解析 + 发送服务 + 消息动作 + 通道适配器 + HTML 导出)。
Phase 26-28 扩展了 LLM 提供商 (中国区、OAuth、Bedrock)、Channel Plugin SDK 和深化了配置系统。
Phase 29 新增了进程监管器、命令队列、扩展媒体理解 (Groq/Mistral/Deepgram/xAI + 视频管道) 和嵌入提供商 (Voyage/Mistral + 批量上传)。
Phase 30-31 新增了 Gateway 高级功能 (配置热重载、通道健康监控、控制面限速、Hooks 映射、服务发现) 和 CLI 增强 (Doctor 诊断、27 提供商认证、Onboarding、Status/Models/Channels CLI)。
Phase 32-33 新增了 Cron 高级 (隔离代理/任务交错/会话收割)、TTS 扩展 (ElevenLabs/OpenAI)、Logging 高级 (轮转/脱敏/解析)、SSRF 防护、会话成本追踪、SSH/SCP、系统事件总线、归档管理、非通道扩展 (Lobster/LLM-Task/Copilot/OTEL)、Shared 工具和 Exec 加固。
Phase 34-35 新增了 Browser 自动化 (Playwright 薄适配层: Session Manager/Navigation Guard/Agent Tools/Bridge Server/Screenshot) 和 Pi Embedded Runner (Run 循环/Session Manager/Thinking-Extensions/Tool Guards/Provider Helpers)。
Phase 36-38 完成了 Channel Plugins 深度 (6 通道目录/Onboarding/Outbound/Status Issues)、Gateway Methods + Sessions (15 扩展 RPC + Chat 高级 + Sessions 高级 + Exec Approvals)、以及最终杂项 (Boot-MD/Extra Files/Command Logger/Model Probe-Scan/Wizard Session/Shell 补全/Discord Voice/VoiceWake/Respawn/6 额外 LLM 提供商)。
Phase 39-43 已完成命令面与接线层对齐：CLI 主命令统一为 **`pyclaw`**（无 `openclaw` 兼容别名），ACP/Usage/Browser 关键路径已形成端到端可用链路，并加入文档-命令契约测试防回归。
Phase 54-58 重点修复了"文档已完成但实现占位"的关键差距：Browser RPC 改为 Playwright 真执行、Chat 接入参数校验/净化/编辑/重发、System/Logs 补齐 Gateway RPC、Extended 占位方法改为 NOT_IMPLEMENTED 或真实状态。
Phase 59-61 补全了 Gateway CLI 子命令验证、Homebrew formula 分发、CI 契约测试独立步骤与 upstream 持续对比流程。
详见 [20260301_plan.md](reference/20260301_plan.md) 和 [20260301gap.md](reference/20260301gap.md)。

### CoPaw 对比 (2026-03-02)

基于 [agentscope-ai/CoPaw](https://github.com/agentscope-ai/CoPaw) v0.0.3 对比分析，识别出 6 项差异化能力 (Phase 62-67)，**已全部实现**：
- **Phase 62**: 本地模型运行时 — llama.cpp / MLX 双后端 + HuggingFace/ModelScope 下载管理
- **Phase 63**: 桌面截图 (`mss` 跨平台) + 通用文件发送 (`send_file`) 工具
- **Phase 64**: 一键安装脚本 (`install.sh` / `install.ps1`) + `pyclaw uninstall` 命令
- **Phase 65**: Office 文件技能包 — PDF/DOCX/XLSX/PPTX 读取工具 + SKILL 配置
- **Phase 66**: Heartbeat 增强 — HEARTBEAT.md 文件驱动 + compound 间隔 + target=last 通道分发
- **Phase 67**: MCP 热重载 — `McpConfigWatcher` 配置变更自动重连
详见 [copaw_comparison_plan.md](reference/copaw_comparison_plan.md)。

### maxclaw 对比 (2026-03-02)

基于 `/mnt/g/chensai/maxclaw` (Go 项目) 对比分析，识别出 12 项可借鉴功能，**已全部实现** (Phase 68-69)：
- **Phase 68**: 任务规划 (Plan/Step)、用户中断 (cancel/append)、意图分析 (双语规则引擎)、消息总线 (异步双通道)、运行时上下文 (contextvars 注入)、消息 Timeline、每日摘要服务、Cron 增强 (every/once/history/通知)、子代理增强 (notify_parent)、数据备份/恢复 (CLI + Gateway RPC)
- **Phase 69**: Flet UI Phase 1 重构 — Gateway WebSocket Client (`ui/gateway_client.py`)、流式聊天 (逐 token 渲染)、中断按钮、消息编辑/重发、Plan/Cron/System 管理页面、Session 搜索/分组、Settings 增强 (动态模型/语言/主题色)、响应式布局、toolbar/menubar 接入、8 页导航
- 新增 111 个单元测试 (84 Phase 68 + 27 Phase 69)
详见 [maxclaw_comparison_plan.md](reference/maxclaw_comparison_plan.md) 和 [ui_upgrade_plan.md](reference/ui_upgrade_plan.md)。

### Flutter App 搭建 (Phase 70, 2026-03-02)

基于 [ui_upgrade_plan.md](reference/ui_upgrade_plan.md) Phase 2 方案，搭建了完整的 Flutter 原生客户端项目 `flutter_app/`：

- **核心层**: Gateway Client (Dart WebSocket v3)、6 个数据模型 (Message/Session/Plan/CronJob/Agent/Channel)、5 个 Riverpod Provider、Material 3 主题系统 (ColorScheme.fromSeed + 动态配色)
- **功能页面** (9 个): Chat (流式消息 + Markdown + 中断 + 编辑/重发)、Sessions (搜索 + 日期分组)、Agents (工具标签)、Channels (状态指示)、Plans (进度条 + Stepper)、Cron (添加表单 + 三种调度)、System (Doctor 诊断)、Backup (导出)、Settings (模型选择/主题切换/Gateway 连接)
- **通用组件** (6 个): MessageBubble (头像 + 圆角气泡 + 阴影 + 呼吸动画)、ToolCallCard (ExpansionTile + 运行状态)、PlanProgress (线性指示器)、ModelSelector、CodeBlock (语法标签 + 一键复制)、ResponsiveShell (Desktop NavigationRail / Mobile NavigationBar 三端自适应)
- **测试**: 30 个单元测试 (GatewayClient 7 + Models 23)
- **技术栈**: Flutter 3.x + Riverpod 2.x + go_router + flutter_markdown + google_fonts + web_socket_channel + Material 3

### Flutter App 完善 (Phase 71, 2026-03-02)

对 Phase 70 搭建的 Flutter 客户端进行全面增强，补齐计划中的高级特性：

- **动画系统**: Shimmer 骨架屏加载占位、Stagger 列表项依次出现动画、打字机光标闪烁效果 (staggered dot + blinking cursor)、Hero 转场 (Session avatar)、页面切换淡入淡出 (go_router CustomTransitionPage)、发送按钮弹性缩放动画
- **LaTeX 公式**: `flutter_math_fork` 集成，支持 `$...$` 行内公式和 `$$...$$` 块级公式，含错误回退
- **图片预览**: `photo_view` 全屏查看 + Hero 放大动画 + 手势缩放 + 加载/错误状态
- **文件附件**: `file_picker` 多选上传 + 文件类型图标映射 (PDF/图片/音频/视频/Office/压缩包) + 附件预览条 + 删除标签
- **离线缓存**: `Hive` 本地存储 (`LocalCache`) — 缓存 sessions/config/gateway_url/theme_mode/seed_color
- **乐观更新**: Session 删除即时从 UI 移除，失败时回滚
- **Dynamic Color**: `seedColorProvider` 实时切换主题色 + `ThemePicker` 8 色选择器 + 选中指示 + 持久化到 Hive
- **独立 Provider**: `CronNotifier` (60s 自动刷新 + cron.executed 事件监听)、`SystemNotifier` (30s 自动刷新)
- **PWA**: `web/manifest.json` + `web/index.html` (loading spinner + theme-color + standalone display)
- **桌面窗口**: `DesktopWindow` 配置 (min/default 尺寸常量 + 平台检测)
- **统计**: 46 个 Dart 源文件, ~4980 行代码, 4 个测试文件 49 个测试用例

### Flet + Flutter 融合 (Phase 72, 2026-03-02)

分析 Flet 与 Flutter 的关系后，发现 Flet 底层就是 Flutter 渲染引擎，维护两套独立 UI（Python-Flet + Dart-Flutter）
造成代码冗余。决定以 Flet UI 为唯一客户端，将 Flutter App 的设计精华反哺到 Flet UI。

- **文档更新**: README.md 项目统计 (440 .py + 46 .dart / 66,400 + 4,980 LOC)、20260302_todo.md Phase 72 分项 + 优先级表
- **Flutter App 归档**: `flutter_app/ARCHIVE_NOTICE.md` 标记用途，README.md 标注 "[Archived]"
- **Material 3 配色反哺**: `theme.py` 新增 `PRESET_SEED_COLORS` (8 预设色)、`StatusColors`、`RoleColors`、`CodeBlockColors`、`surface_container_high`、`primary_container`、`card_border_radius`、`input_border_radius`、`role_color()` 方法、`list_seed_presets()`
- **Shimmer + 动画反哺**: 新建 `shimmer.py` — `ShimmerContainer` (脉冲动画)、`shimmer_chat_skeleton()` (聊天骨架)、`shimmer_list_tile()` (列表骨架)、`stagger_fade_in()` (交错淡入)
- **ui_upgrade_plan.md 更新**: Phase 2 从 "Flutter 原生美化" 改为 "Flet 高级增强 + Flutter 设计反哺"，技术选型更新，里程碑状态更新
- **flet build 配置**: `pyproject.toml` 新增 `[tool.flet]` 构建配置，`flet_app.py` 已支持 `flet build` + `flet run` 双模式
- **构建脚本**: `scripts/build-desktop.sh` + `scripts/build-mobile.sh` 使用 `--module-name flet_app`

## 参考文档

- 完整重写方案: [python-flet-rewrite-plan.md](reference/python-flet-rewrite-plan.md)
- 功能差距分析: [gap-analysis.md](reference/gap-analysis.md)
- P0-P13 实施计划: [implement_plan_20260228.md](reference/implement_plan_20260228.md)
- Phase 14+ 后续计划: [implement_plan_next.md](reference/implement_plan_next.md)
- UI 升级计划: [ui_upgrade_plan.md](reference/ui_upgrade_plan.md)
- 原始 TypeScript 项目: `openclaw/openclaw`
