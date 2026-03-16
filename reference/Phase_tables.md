# 规整表格与架构（唯一信息源）

> 本目录中**计划 / 进度 / 差距 / 待办 / 能力矩阵 / 代码统计 / 架构**均以此文档为准。  
> 入口与文档结构见 [REFERENCE_README.md](REFERENCE_README.md)。

---

## 1. Phase 总览表

| num | Phase | 模块/主题 | plan 摘要 | 进度 | 说明 |
|-----|-------|-----------|-----------|------|------|
| 1 | Phase 1 | 基础层 | 脚手架、配置模型、IO 兼容、会话存储 | 已完成 | |
| 2 | Phase 2 | Gateway | FastAPI + WebSocket 协议 v3 + 核心方法处理器 | 已完成 | |
| 3 | Phase 3a | Agent | LLM 流式调用 + 工具执行循环 | 已完成 | |
| 4 | Phase 3b | Agent | BaseTool, Registry, 20+ 内置工具 | 已完成 | |
| 5 | Phase 3c | Agent | SessionManager DAG、文件锁、token 估算、compaction | 已完成 | |
| 6 | Phase 3d | Agent | OpenAI, Anthropic, Google Gemini, Ollama | 已完成 | |
| 7 | Phase 4 | Channels | 通道抽象 + Telegram/Discord/Slack/WhatsApp/Signal/iMessage | 已完成 | |
| 8 | Phase 5 | UI | Flet 桌面聊天 + Session + Tool 可视化 + Markdown + 设置 + 托盘 + Channel 面板 + Onboarding | 已完成 | |
| 9 | Phase 6 | 高级功能 | 记忆/RAG + 插件系统 + 定时任务 | 已完成 | |
| 10 | Phase 7 | Agent/Gateway | Auth Profiles + Subagents + Model Catalog + Skills + Embeddings + CLI + Gateway API | 已完成 | |
| 11 | Phase 8 | P2 增强 | Hooks + Exec 审批 + Heartbeat + Security + Markdown IR + Media Understanding + Pairing + UI 增强 | 已完成 | |
| 12 | Phase 9 | P3 完善 | 7 扩展通道 + ACP + Canvas + Node Host + Daemon + QMD + Voice + Gateway 控制面板 + Gmail Hook + 工具补全 | 已完成 | |
| 13 | Phase 10 | 质量加固 | 测试补全、工程化、CI/CD | 已完成 | |
| 14 | Phase 11 | Infra | mDNS/Bonjour + Tailscale VPN 集成 | 已完成 | |
| 15 | Phase 12 | Channels | 10 个新通道 (Synology, Mattermost, Nextcloud, Tlon, Zalo, ZaloUser, Nostr, LINE, VoiceCall) | 已完成 | |
| 16 | Phase 13 | UI/打包 | Flet build 入口 + 桌面/移动端构建脚本 | 已完成 | |
| 17 | Phase 14 | ACP/Secrets/Bindings/Codex | ACP acpx + External Secrets + Agent Bindings + OpenAI Codex/Responses | 已完成 | |
| 18 | Phase 15 | Channels/Agent | Android Nodes 策略 + Plugin Onboarding Hooks + Discord Thread Lifecycle | 已完成 | |
| 19 | Phase 16 | Memory/Extensions/UI | Memory Plugins (LanceDB) + Non-channel Extensions + Web UI i18n | 已完成 | |
| 20 | Phase 17 | Security | Exec Approval 增强 + Gateway 安全加固 + Sandbox 边界 | 已完成 | |
| 21 | Phase 18 | Agent/Channels/Infra | Auto-reply 引擎 + Typing 管理器 + Outbound 管道 + Delivery Queue + Model Fallback | 已完成 | |
| 22 | Phase 19 | Channels (Feishu) | Reactions + Docx + 高级路由 + 消息增强 + 运行时优化 | 已完成 | |
| 23 | Phase 20 | Channels/Security | Auth Guard + Allowlist 边界 + 安全审计扩展 + 危险工具标记 | 已完成 | |
| 24 | Phase 21 | Gateway/Agent | WS Flood Guard + Compaction 增强 + Config/State 迁移 + Command Gating | 已完成 | |
| 25 | Phase 22 | Channels/Browser/Agent | Telegram 媒体/chunking/退避 + Browser Relay + Link Understanding | 已完成 | |
| 26 | Phase 23 | Extensions/Agent/UI | Memory-core Extension + Gemini CLI Auth + Ollama 增强 + 德语 i18n | 已完成 | |
| 27 | Phase 24 | Auto-reply | 命令注册表 + 核心/会话/模型命令 + 内联指令 + 消息队列 + 回复调度器 | 已完成 | |
| 28 | Phase 25 | Auto-reply/Infra | Block Streaming + 投递目标解析 + 发送服务 + 消息动作 + 通道适配器 + HTML 导出 | 已完成 | |
| 29 | Phase 26 | Agent | OpenAI 兼容 + 9 个中国提供商 + OAuth 流 + Bedrock + 提供商注册表 | 已完成 | |
| 30 | Phase 27 | Channels | 20+ 适配器 Protocol + 草稿流式 + 确认反应 + 模型覆盖 + 提及门控 + 通道健康检查 | 已完成 | |
| 31 | Phase 28 | Config | 环境变量替换 + Config Includes + 备份轮转 + Session Store + 运行时覆盖 + 配置脱敏 | 已完成 | |
| 32 | Phase 29 | Process/Media/Memory | 进程监管器 + 命令队列 + 媒体理解扩展 + 视频管道 + 嵌入 + 批量上传 | 已完成 | |
| 33 | Phase 30 | Gateway | 配置热重载 + 通道健康监控 + 控制面限速 + Hooks 映射 + 服务发现 | 已完成 | |
| 34 | Phase 31 | CLI | Doctor 9 项 + 27 提供商认证 + Onboarding + Status 增强 + Models CLI + Channels CLI | 已完成 | |
| 35 | Phase 32 | Cron/TTS/Logging/Security/Infra | 隔离代理 + 技能快照 + 任务交错 + ElevenLabs/OpenAI TTS + 日志轮转/脱敏 + SSRF + 会话成本 | 已完成 | |
| 36 | Phase 33 | Infra/Plugins | SSH/SCP + 系统事件总线 + 归档 + Lobster/LLM-Task/Copilot/OTEL + Shared 工具 + Exec 加固 | 已完成 | |
| 37 | Phase 34 | Browser | Playwright 薄适配层: Session Manager + Navigation Guard + Agent Tools + Bridge Server + Screenshot | 已完成 | |
| 38 | Phase 35 | Agent | Pi Embedded Runner: Run 循环 + Session Manager + Thinking/Extensions + Tool Guards + Helpers | 已完成 | |
| 39 | Phase 36 | Channels | 通道目录 + 6 通道 Onboarding/Outbound + 5 通道 Status Issues + Config Schema | 已完成 | |
| 40 | Phase 37 | Gateway/Sessions | 15 扩展 RPC + Chat 高级 + Sessions 高级 + Exec Approvals | 已完成 | |
| 41 | Phase 38 | TUI/Models/Wizard/杂项 | Boot-MD + Extra Files + Command Logger + Model Probe/Scan + Wizard Session + Shell 补全 + Discord Voice + VoiceWake + Respawn + 6 额外 LLM 提供商 | 已完成 | |
| 42 | Phase 39 | CLI | pyclaw 主命令 + agent v2 参数 + acp/sessions/logs/system/browser/health 入口对齐 | 已完成 | |
| 43 | Phase 40 | ACP | pyclaw acp / acp client 参数齐全 + session key/label 映射 + token/password file | 已完成 | |
| 44 | Phase 41 | Gateway/CLI | extended/exec_approvals 注册 + usage ledger + status --usage + models probe/scan/auth-overview | 已完成 | |
| 45 | Phase 42 | Browser/CLI | browser CLI 全局参数 + Gateway browser.* RPC + SSRF 导航守卫 + 截图输出 | 已完成 | |
| 46 | Phase 43 | 文档 | PROGRESS/gap/plan 滚动更新 + docs parity contract + pyclaw 命名守卫 | 已完成 | |
| 47 | Phase 44 | Gateway/CLI | gateway status/probe/call/discover + logs.tail RPC + 远程日志 + 文案收敛 | 已完成 | |
| 48 | Phase 45 | Agent | chat.send 默认 embedded runner + runner.mode 开关 + abort/usage 一致性 + 成本记录 | 已完成 | |
| 49 | Phase 46 | Gateway | doctor.run 真实诊断 + system.logs + skills.list 发现技能 | 已完成 | |
| 50 | Phase 47 | CLI | sessions cleanup + security audit + system CLI RPC-first fallback | 已完成 | |
| 51 | Phase 48 | Browser | browser profiles/create-profile/delete-profile/focus/close + RPC 接线 | 已完成 | |
| 52 | Phase 49 | 文档/ACP | pyclaw 文案统一 + ACP token-file/password-file + docs parity 扩展 | 已完成 | |
| 53 | Phase 50 | MCP/Infra | MCP 客户端 (stdio+HTTP) + McpToolAdapter + MCP CLI + Dockerfile + docker-compose | 已完成 | |
| 54 | Phase 51 | Channels/CLI | DingTalk + QQ 通道 + OAuth/Device-Code CLI + ClawHub 技能搜索/安装 + Workspace 模板同步 | 已完成 | |
| 55 | Phase 52 | Social | 社交平台注册表 + Moltbook/ClawdChat 适配 + 社交技能包 + Agent 工具 | 已完成 | |
| 56 | Phase 53 | Agent/UI | ProgressEvent + Gateway 广播 + 工具/技能嵌入 + Flet UI 进度条 + 语音转录 | 已完成 | |
| 57 | Phase 54 | Browser | Gateway browser 方法复用 Playwright 真执行 + profiles/createProfile/deleteProfile/focus/close + 真实截图与 DOM 快照 | 已完成 | |
| 58 | Phase 55 | Gateway | chat.send 接入 chat_advanced 校验/净化/时间注入 + chat.edit/chat.resend + usage/abort 一致性 | 已完成 | |
| 59 | Phase 56 | Gateway/CLI | system.event/heartbeat.last/presence RPC + CLI fallback 显式警告 | 已完成 | |
| 60 | Phase 57 | Gateway | wizard/push/voicewake/tts 改为 NOT_IMPLEMENTED + update.check 真实版本 + web.status 真实状态 | 已完成 | |
| 61 | Phase 58 | 文档 | docs/reference 差距与进度基线重建 + API 参考更新 + 契约测试 | 已完成 | |
| 62 | Phase 59 | Gateway/CLI | gateway status/probe/call/discover 验证对齐 + api-reference 更新 | 已完成 | |
| 63 | Phase 60 | 发布 | Homebrew formula + 分发文档 (pipx/brew) | 已完成 | |
| 64 | Phase 61 | 文档/CI | CI 独立契约测试 step + 季度复核 upstream 流程 + 自动化守护说明 | 已完成 | |
| 65 | Phase 62 | Agent | 本地模型运行时: llama.cpp + MLX + HuggingFace/ModelScope 下载 + manifest + CLI | 已完成 | |
| 66 | Phase 63 | Tools | mss 跨平台截图 + macOS screencapture + send_file 工具 + 工具注册 | 已完成 | |
| 67 | Phase 64 | 分发 | install.sh / install.ps1 + --extras + uninstall 命令 | 已完成 | |
| 68 | Phase 65 | Skills | PDF/DOCX/XLSX/PPTX 读取工具 + SKILL.md + pyproject office extra | 已完成 | |
| 69 | Phase 66 | Infra | HEARTBEAT.md 文件驱动 + compound 间隔 + target=last 通道分发 + 活跃时段 | 已完成 | |
| 70 | Phase 67 | MCP | McpConfigWatcher 配置变更自动重连 + 文档更新 | 已完成 | |
| 71 | Phase 68 | Agent/Infra | Plan/Step + 用户中断 + 意图分析 + 消息总线 + 上下文注入 + Timeline + 每日摘要 + Cron 增强 + 子代理增强 + 数据备份 | 已完成 | |
| 72 | Phase 69 | UI | Flet UI Phase 1 重构: Gateway WebSocket Client + 流式聊天 + 中断 + 编辑/重发 + 管理页面 + 响应式 + 8 页导航 | 已完成 | |
| 73 | Phase 70 | UI | Flutter App 搭建: 9 个功能页面 + 6 个通用组件 + Material 3 + Riverpod | 已完成 | |
| 74 | Phase 71 | UI | Flutter App 完善: 动画 + LaTeX + 图片预览 + 文件附件 + 离线缓存 + 乐观更新 + Dynamic Color + PWA | 已完成 | |
| 75 | Phase 72 | UI | Flet 为唯一客户端 + Flutter 归档 + Material 3/Shimmer 反哺 + flet build 配置 | 已完成 | |
| 76 | Phase 73 | 文档/Gateway | api-reference 帧格式修正 + sessions.get/create/cleanup RPC + 契约测试扩展 | 已完成 | |
| 77 | Phase 74 | 可观测性 | 静默 except:pass → 结构化日志 + Gateway 统一 trace_id | 已完成 | |
| 78 | Phase 75 | UI | 移动端导航全 8 项可达 + error_state/empty_state + Plans/Cron/Channels/System 错误态与重试 | 已完成 | |
| 79 | Phase 76 | Gateway | secrets.reload 规范化 + NOT_IMPLEMENTED 存根文档化 + registration 完整性验证 | 已完成 | |
| 80 | Phase 77 | UI/打包 | Flet 0.81 兼容 + 窗口控制 + 全平台构建脚本 (Web/Desktop/Mobile) + Makefile | 已完成 | |
| 81 | Phase 78 | UI | theme tokens + card_tile + page_header + 代码块复制 + scroll-to-bottom FAB + 空态/错误态补齐 | 已完成 | |

---

## 2. 平台能力矩阵（目标态）

适用于 Flet 多端与 Gateway 一体化排期。

| 平台 | Chat 流式 | Session 管理 | Channel 状态 | Voice | Notify | 备注 |
|------|-----------|--------------|--------------|-------|--------|------|
| Web（Flet） | 目标完善 | 目标完善 | 目标完善 | 可选 | 需补齐 | 作为最先验收端 |
| Desktop（macOS/Windows/Linux） | 目标完善 | 目标完善 | 目标完善 | 目标完善 | 需补齐 | 托盘/菜单栏统一 |
| Android | 目标完善 | 目标完善 | 目标完善 | 目标完善 | 需补齐 | 权限和后台行为重点 |
| iOS | 目标完善 | 目标完善 | 目标完善 | 目标完善 | 需补齐 | 权限和打包签名重点 |

---

## 3. 核心渠道能力矩阵（第一批）

第一批渠道：Telegram / Discord / Slack / WhatsApp / Signal。

| 渠道 | Typing | Placeholder | Reaction | Media | Voice | 当前优先级 |
|------|--------|-------------|----------|-------|-------|------------|
| Telegram | 目标对齐 | 目标对齐 | 目标对齐 | 目标对齐 | 目标增强 | P0 |
| Discord | 目标对齐 | 目标对齐 | 目标对齐 | 目标对齐 | 目标增强 | P0 |
| Slack | 目标对齐 | 目标对齐 | 目标对齐 | 目标对齐 | 可选 | P1 |
| WhatsApp | 目标对齐 | 目标对齐 | 目标对齐 | 目标对齐 | 可选 | P1 |
| Signal | 目标对齐 | 目标对齐 | 目标对齐 | 目标对齐 | 可选 | P1 |

---

## 4. 按模块聚合的工作包

| 模块 | 涉及 Phase | 关键文件/位置 | 说明 |
|------|------------|---------------|------|
| Gateway | 2, 9, 21, 30, 37, 44, 46, 56, 57, 59, 76 | server.py, methods/*, config_reload.py, channel_health.py, discovery.py, ws_guard.py, registration.py | WebSocket v3、配置热重载、通道健康、服务发现、控制面子命令、RPC 扩展、secrets.reload |
| Channels | 4, 15, 19, 20, 22, 27, 36, 51 | channels/*, plugins/catalog.py, plugins/onboarding.py, outbound_adapters.py, status_issues.py, auth_guard.py | 25 通道、catalog、Onboarding/Outbound/Status、Auth Guard、能力矩阵 |
| Agent | 3a–d, 7, 17, 18, 21, 23, 26, 35, 45, 52, 53, 62, 68 | runner.py, stream.py, session.py, auth_profiles/, subagents/, skills/, model_catalog.py, tools/, auto_reply/, embedded_runner/, progress.py, providers/* | 核心循环、LLM 提供商、斜杠命令、Embedded Runner、Progress、本地模型 |
| Config | 1, 28 | config/schema.py, env_substitution.py, includes.py, backup.py, session_store.py, runtime_overrides.py | 环境变量替换、Includes、备份轮转、Session Store、运行时覆盖 |
| CLI | 7, 31, 39, 40, 42, 47, 51, 59, 62 | cli/app.py, commands/* (doctor_flows, auth_providers, onboarding_enhanced, status_enhanced, models_cmd, channels_enhanced, acp_cmd, browser_cmd, sessions_cmd, security_cmd) | pyclaw 主命令、Doctor/Onboarding/Status/Models/Channels/ACP/Browser/sessions cleanup/security audit |
| Browser | 22, 34, 42, 48, 54 | browser/session_manager.py, navigation_guard.py, agent_tools.py, bridge_server.py, screenshot.py, relay.py, gateway/methods/browser_methods.py | Playwright 薄适配、RPC 真执行、profiles/tabs/focus/close |
| Security | 8, 17, 20, 21, 32 | security/exec_approval.py, gateway_hardening.py, sandbox.py, auth_guard.py, allowlist_boundaries.py, audit_extra.py, dangerous_tools.py, ssrf.py, exec_hardening.py | Exec Approval、Gateway 加固、Sandbox、Auth Guard、Allowlist、SSRF、Exec 加固 |
| UI | 5, 69, 70, 71, 72, 75, 77, 78 | ui/app.py, gateway_client.py, theme.py, shimmer.py, responsive_shell.py, components.py, locales/*, tray.py | Flet 重构、Gateway Client、主题/Shimmer、响应式、Flutter 反哺、全平台打包、视觉一致性 |
| Infra | 8, 11, 14, 18, 29, 30, 32, 33, 50, 66, 67 | infra/bonjour.py, tailscale.py, delivery.py, process/supervisor.py, command_queue.py, system_events.py, archive.py, ssh.py, session_cost.py, logging/advanced.py | mDNS、Tailscale、投递队列、进程监管、系统事件、归档、SSH/SCP、会话成本、日志高级 |
| Memory | 6, 16, 23, 29 | memory/store.py, backend.py, lancedb_backend.py, extended.py, plugins/extensions/memory_core.py | SQLite FTS5、LanceDB、批量上传、memory-core 扩展 |
| ACP | 9, 14, 40 | acp/types.py, session.py, server.py, client.py, control_plane.py, acpx_runtime.py, session_mapper.py, event_mapper.py, thread_ownership.py | 协议、session store、acpx 运行时、CLI token-file/password-file |

---

## 5. 差距总览表

| num | 模块/领域 | 差距项 | 优先级 | 状态/Phase |
|-----|-----------|--------|--------|------------|
| 1 | Browser 自动化 | CDP 直接通信、Chrome/Brave/Edge 发现、Playwright AI、Client Actions、Server 生命周期 | P1 | Phase 34/54 已完成核心 RPC；上述为可选深度 |
| 2 | Pi Embedded Runner | Run 循环、Session Manager、Thinking、Tool Guards、Helpers | P1 | Phase 35 已完成 |
| 3 | Channel Plugins 深度 | Per-channel Onboarding/Outbound/Status/Actions/Normalize、Catalog、Extension Runtimes | P2 | Phase 36 已完成 6 通道目录/Onboarding/Outbound/Status；40 扩展 runtime 未做 |
| 4 | Gateway Methods | browser/push/talk/tts/wizard/voicewake/update/usage/logs/system/doctor/skills 等 RPC | P2 | Phase 37/44/46/57 已补齐多数；wizard/push/voicewake/tts 为 NOT_IMPLEMENTED |
| 5 | TUI | Terminal 聊天、输入历史、本地 Shell、会话切换/列表、Overlay、15 终端组件 | P3 | 可选；Flet GUI 替代，设计差异 |
| 6 | Commands/Models 深度 | Model Probe/Scan、Table 格式化、Set Model、Auth Profile Order、Session Store (cmd)、Run Context | P2 | Phase 31/38 已覆盖 probe/scan/auth-overview；其余为可选增强 |
| 7 | Wizard | Clack Prompter、Shell Completion、Wizard Session 多步骤状态 | P3 | Phase 38 有 Wizard Session；Clack/Shell 补全为可选 |
| 8 | Sessions 模块 | Send Policy、Level Overrides、Transcript Events、Input Provenance、Session Label | P2 | Phase 37 Sessions 高级已部分覆盖；其余可选 |
| 9 | Hooks Bundled | boot-md、bootstrap-extra-files、command-logger | P3 | Phase 38 已实现 boot-md/extra-files/command-logger |
| 10 | 其它小差距 | Discord Voice、TLS 指纹、VoiceWake、Push APNS、Clipboard、Process Respawn、Config 通道类型、Agents Schema、Plugin Runtime、剩余 LLM 提供商 | P3 | Discord Voice/VoiceWake/Respawn/Clipboard 已实现；Push APNS/扩展 runtime 等未做 |

---

## 6. 待办与占位表

| num | 类别 | 项 | 优先级 | 完成情况 |
|-----|------|-----|--------|----------|
| 1 | 计划功能 (Phase 52-53) | Agent 社交网络 (Phase 52) | P1 | 已完成 |
| 2 | 计划功能 (Phase 52-53) | Progress Streaming (Phase 53) | P2 | 已完成 |
| 3 | 计划功能 (Phase 52-53) | 语音转录完善 (Phase 53) | P2 | 已完成 |
| 4 | 差距更新 (Phase 54-58) | Browser RPC 真执行化 (Phase 54) | P1 | 已完成 |
| 5 | 差距更新 (Phase 54-58) | Chat 主路径能力收敛 (Phase 55) | P1 | 已完成 |
| 6 | 差距更新 (Phase 54-58) | System/Logs RPC-first (Phase 56) | P2 | 已完成 |
| 7 | 差距更新 (Phase 54-58) | Extended 去占位 (Phase 57) | P2 | 已完成 |
| 8 | 差距更新 (Phase 54-58) | 文档基线重建 (Phase 58) | P2 | 已完成 |
| 9 | 占位/未生产化 | Provider Usage API 真实 HTTP 调用 | P0 | 已完成 |
| 10 | 占位/未生产化 | CLI screenshot 经 Gateway RPC | P0 | 已完成 |
| 11 | 占位/未生产化 | security audit --fix 自动修复 | P0 | 已完成 |
| 12 | 占位/未生产化 | misc_extensions Lobster/LLM-Task/Copilot/OTEL 去存根 | P0 | 已完成 |
| 13 | 占位/未生产化 | Onboarding 通道向导扩展 (12 通道) | P0 | 已完成 |
| 14 | 占位/未生产化 | 未使用依赖清理 (loguru/aiosqlite/watchdog) | P0 | 已完成 |
| 15 | 占位/未生产化 | sqlite-vec 向量搜索 | P3 | 未开始（LanceDB 已替代，可选） |
| 16 | 占位/未生产化 | 插件 entry_points 接入启动流程 | P0 | 已完成 |
| 17 | 占位/未生产化 | Config 热重载接入 Gateway | P0 | 已完成 |
| 18 | 原始方案未完整实现 | Flet UI 功能缺口 (Phase 1 重构) | P2 | 已完成 |
| 19 | 原始方案未完整实现 | Voice Wake 语音唤醒 (sounddevice+vosk) | P3 | 已完成（需用户安装依赖） |
| 20 | TS 未覆盖/Browser 深度 | CDP 直接通信、Chrome 发现、Playwright AI、Client Actions、Server 生命周期 | P2 | 未开始（可选） |
| 21 | TS 未覆盖/Channel 深度 | Extension Runtimes (40 扩展独立 runtime) | P3 | 未开始 |
| 22 | TS 未覆盖/TUI | Terminal 聊天、输入历史、Shell 集成、Overlay、15 终端组件 | P3 | 未开始（可选，Flet GUI 替代） |
| 23 | TS 未覆盖/其它 | Push APNS、Agents Schema、Plugin Runtime 完整 | P3 | 未开始 |
| 24 | 持续追踪 | 持续跟踪 TS 主项目新 commit，识别新差距 | P3 | 进行中 |

---

## 7. 代码统计

| 指标 | 数值 |
|------|------|
| 源码 | ~70,500 行 (~443 个 .py 文件) |
| 测试 | ~20,350 行 (94 个测试文件, 2202 个测试) |
| 测试状态 | 2202/2202 通过 |
| 通道总数 | 25 个 (6 核心 + 7 P3 扩展 + 12 P4/P5 扩展) |

---

## 8. 架构概览

项目路径: `openclaw-py/`。以下为 `src/openclaw/` 主要目录与职责。

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
│   │   ├── irc/, msteams/, matrix/, feishu/, twitch/, bluebubbles/, googlechat/ 等
│   ├── mcp/              # MCP (Model Context Protocol) 客户端
│   ├── cli/              # Typer CLI (25+ 命令)
│   ├── config/           # 配置管理 (Pydantic + JSON5)
│   ├── cron/             # 定时任务 (APScheduler)
│   ├── gateway/          # Gateway 服务器 (FastAPI + WebSocket v3, methods/)
│   ├── hooks/            # 事件 Hook 框架 (registry, loader, bundled)
│   ├── infra/            # 基础设施 (retry, rate_limit, exec_approvals, heartbeat, bonjour, tailscale 等)
│   ├── logging/          # 日志子系统 (subsystem, redact)
│   ├── markdown/         # Markdown IR + 多通道渲染
│   ├── media/            # 媒体处理 (understanding, embeddings)
│   ├── memory/           # 记忆/RAG
│   ├── pairing/          # 设备配对 (store, challenge, setup_code)
│   ├── plugins/          # 插件系统
│   ├── routing/          # 会话路由
│   ├── security/        # 安全 (dm_policy, audit, exec_approval, gateway_hardening, sandbox 等)
│   ├── terminal/        # 终端工具 (ANSI 表格/调色板)
│   ├── acp/              # Agent Control Protocol (types, session, server, client, control_plane, acpx)
│   ├── canvas/           # Canvas Host (handler, server)
│   ├── node_host/        # 无头节点服务 (invoke, runner)
│   ├── daemon/           # 服务管理 (launchd, systemd, schtasks)
│   ├── browser/         # Browser 自动化 (session_manager, navigation_guard, agent_tools, bridge_server, screenshot)
│   └── ui/               # Flet UI (app, gateway_client, theme, shimmer, channels_panel, voice, tray 等)
├── tests/
├── pyproject.toml
└── docs/
```

更细的 Phase 级「新增文件/说明」清单见 [PROGRESS.md](PROGRESS.md)（仅作历史明细，以本节及第 1、4 节为准）。

---

## 9. 平台与 UI 计划摘要

适用于 Flet 多端与 Gateway 一体化排期。

### 9.1 背景与目标

- 夯实多端客户端基础能力（Web/Desktop/Android/iOS）与 Gateway 一体化运行体验。
- 对齐核心渠道客户端能力（Typing/Placeholder/Reaction/Media/Voice）并形成可观测指标。
- 建立平台能力矩阵与阶段化实施路径（1-2 个月排期）。技术主线：**Flet 为唯一长期 UI 主线**，`flutter_app/` 仅作视觉/交互参考。

### 9.2 范围与约束

- **范围**：平台客户端 `ui/`、`flet_app.py`；渠道 `channels/`、`channels/plugins/catalog.py`；网关 `gateway/`；配置与能力声明 `config/schema.py`、catalog 元数据。
- **约束**：不建设独立 Flutter 业务实现；Gateway 协议保持 v3 兼容。

### 9.3 三方实现对比（摘要）

| 维度 | picoclaw | openclaw | openclaw-py（当前） |
|------|----------|----------|----------------------|
| 主要形态 | CLI + Web Launcher + TUI + 多渠道 | Web Control UI + iOS + Android + macOS + TUI | Flet 多端 UI + CLI + 多渠道 |
| UI 技术主线 | 原生 HTML/JS + TUI | Lit + Swift/Kotlin 原生 | Flet（跨平台） |
| 网关协议 | 内部消息总线 + HTTP/Webhook | WebSocket v3 | WebSocket v3 |

| 维度 | picoclaw | openclaw | openclaw-py（当前） |
|------|----------|----------|----------------------|
| 能力接口 | Typing/Placeholder/Reaction/Media 可选 | channel-capabilities + extension metadata | ChannelPlugin + plugin sdk + catalog |
| 核心渠道深度 | Telegram/Discord/Slack 较完整 | 26+ 插件 | 25+ 渠道，能力深度不均 |

### 9.4 平台差距清单（P0/P1/P2）

- **P0**：Gateway-Channel 一体化运行不足；ChannelsConfig 覆盖不完整；平台状态可观测性不足。
- **P1**：Flet 多端体验一致性不够；核心渠道能力不齐；UI 与能力声明耦合不足。
- **P2**：catalog/schema 未单一真源；插件能力声明缺统一 DoD；验收标准与回归基线未工程化。

### 9.5 Phase A/B/C 工作包与 DoD

| 阶段 | 时间 | 目标 | 工作包摘要 | DoD 摘要 |
|------|------|------|------------|----------|
| Phase A | 2 周 | 基础连通与可观测性 | 一体化运行与 channels.list 稳定化；ChannelsConfig 治理；客户端状态观测面板；核心链路指标埋点 | channels.list 非空率达标；配置与核心渠道一致；UI 可查看平台/渠道状态 |
| Phase B | 2-4 周 | 多端体验提升 | 响应式布局与交互一致性；设计反哺（shimmer/theme）；语音/权限/通知梳理；toolbar/menubar 统一接入 | 四端核心流程一致；响应式断点/主题/动效通过回归；权限与异常路径可控 |
| Phase C | 4 周+ | 渠道能力深水区 | 首批核心渠道能力补齐；catalog/schema 单一真源；插件能力声明模板化；跨端回归基线与测试矩阵 | 能力矩阵达标；catalog 漂移收敛；回归基线可复用 |

### 9.6 优先级与时间线

| 优先级 | 时间窗 | 目标摘要 | 对应阶段 |
|--------|--------|----------|----------|
| P0 | 第 1-2 周 | 连通性、配置一致性、基础观测能力 | Phase A |
| P1 | 第 3-6 周 | 多端体验一致性、核心渠道能力对齐 | Phase B + Phase C（前半） |
| P2 | 第 7 周起 | 元数据统一、插件声明规范、回归工程化 | Phase C（后半） |

### 9.7 验收指标（摘要）

- **功能**：渠道在线率、消息成功率、流式时延 P95、跨端一致性。
- **质量**：测试覆盖提升、打包成功率（flet build 多端）、Gateway v3 回归稳定。

### 9.8 风险与缓解

| 风险 | 缓解策略 |
|------|----------|
| 平台权限差异（Android/iOS/Desktop） | 平台权限矩阵与降级路径（可用性优先） |
| 第三方渠道 SDK 不稳定 | 核心渠道锁版本 + 灰度升级 + 回滚预案 |
| 协议兼容漂移 | 统一协议样例与回归用例，版本门禁 |
| catalog/schema 双源维护 | 推进单一真源，增加 schema 校验脚本 |

### 9.9 实施组织建议

- Owner 类型：UI、Channel、Gateway、QA。依赖项：配置变更、SDK 升级、平台证书/签名。DoD：功能、测试、文档、回滚方案齐全。产出物：代码 PR、验证报告、指标快照、发布说明。

### 9.10 UI 优化路线图（Flutter 反哺 → Flet）

| 类别 | 项 | 关键文件/说明 |
|------|-----|---------------|
| 视觉 V | V1 统一 theme 令牌 / V2 列表项卡片化 / V3 空状态 / V4 代码块增强 / V5 页面头部组件化 | theme.py, app.py, components.py |
| 交互 I | I1 消息淡入 / I2 发送按钮缩放 / I3 页面切换过渡 / I4 Streaming 打字指示器 / I5 滚动到底按钮 | app.py, shimmer.py |
| 架构 A | A1 响应式 Shell 模块化 / A2 多语言 JSON 外置 / A3 ToolCallCard 多工具支持 | responsive_shell.py, i18n.py, locales/ |
| 平台 D | D1 Desktop 托盘增强 / D2 Web PWA / D3 键盘快捷键（Cmd+K/N/E） | tray.py, web manifest, app.py |

---

## 10. 差距明细（按领域）

与 §5 差距总览互补，按领域查阅「已实现 vs 未实现」。

| 领域 | 已实现（摘要） | 未实现/待补齐（摘要） |
|------|----------------|------------------------|
| 通道 | 25+ 渠道插件；ChannelPlugin + catalog；核心渠道部分能力 | 能力深度不均；ChannelsConfig 覆盖不全；catalog 与 schema 未单一真源 |
| Agent | 多 Agent 调度、工具调用、流式输出、会话管理 | 多轮记忆与长期记忆策略；Agent 能力声明与 DoD 统一 |
| Gateway | WebSocket v3、多端连接、消息路由 | 一体化运行与状态可观测；协议回归基线工程化 |
| Infra | 配置、日志、健康检查、Flet 多端 | 平台权限矩阵与降级路径；打包/签名/证书流程文档化 |
| Memory | 会话级上下文、流式缓冲 | 跨会话记忆、记忆策略与持久化策略 |
| Hooks | 生命周期与扩展点 | 统一 Hook 契约与版本兼容策略 |

---

## 11. 专项计划索引

以下计划为独立主题，全文仅保留于对应文档；此处仅做索引。

| 专项 | 文档 | 内容摘要 |
|------|------|----------|
| Python + Flet 重写方案 | [python-flet-rewrite-plan.md](python-flet-rewrite-plan.md) | 总纲领（愿景、架构思想、设计原则）、可复用资产、技术选型、阶段路线与风险对策 |
| UI 升级（Flet + Flutter 反哺） | [ui_upgrade_plan.md](ui_upgrade_plan.md) | Gateway Client、Chat/Session/Settings 增强、Phase 1/2 路线、技术选型 |
