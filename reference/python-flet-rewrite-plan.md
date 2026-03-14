# OpenClaw Python + Flet 完整重写方案

## 总纲领

### 愿景

用 **Python + Flet** 重写 OpenClaw，在保持与现有 TypeScript 版本**协议与数据兼容**的前提下，实现：

- **单一代码库多端**：Web / Desktop / Mobile 共用一套 UI（Flet → Flutter 编译）
- **可扩展的渠道与 Agent 体系**：插件化通道、自研 Agent 运行时、统一 Gateway 协议
- **平滑过渡**：现有配置、会话、记忆数据可直接复用；过渡期原生 App 仍可连接 Python Gateway

### 架构思想

- **Gateway 为中枢**：所有客户端（Flet、原生 App、CLI）仅通过 WebSocket v3 与 Gateway 通信；路由、会话、Agent、通道均在服务端完成。
- **通道与 Agent 解耦**：通道负责收发消息与身份；Agent 负责推理与工具；Gateway 负责绑定、投递、协议转换。二者通过 Gateway 内部 API 协作，不直接耦合。
- **配置与数据为单一真源**：`~/.openclaw/` 下配置、会话、记忆、凭证等与语言无关的格式（JSON5、JSONL、SQLite）直接复用，不做迁移层。
- **UI 仅消费协议**：Flet UI 不承载业务逻辑，只负责连接 Gateway、发送方法、渲染事件；状态与权限以 Gateway 下发的为准。

### 设计原则

- **协议优先兼容**：WebSocket 协议 v3、配置 schema、会话 JSONL 格式与 TS 版一致，便于双轨运行与回退。
- **复用优于重写**：文档、Skills、静态资产、测试数据、Shell 脚本、插件清单等直接复用；仅运行时与 UI 重写。
- **渐进迁移**：可先替换 Gateway，通道与 Agent 逐个迁移，UI 最后替换；不要求一步到位。
- **不引入重型框架**：Agent 运行时自研（核心循环 + 官方 LLM SDK），不使用 LangChain/LangGraph，保持会话格式可控与依赖精简。

---

## 一、当前架构概览

OpenClaw 是多通道 AI 网关，当前技术栈：

- **后端**: TypeScript/Node.js (ESM), Express + WebSocket (`ws`)
- **CLI**: Commander
- **AI 运行时**: Pi embedded runner (`@mariozechner/pi-agent-core`)
- **消息通道**: grammy (Telegram), discord.js, @slack/bolt, Baileys (WhatsApp), signal-cli 等
- **存储**: SQLite (node:sqlite + sqlite-vec), JSON5 配置, JSONL 会话日志
- **原生 App**: SwiftUI (macOS/iOS), Kotlin (Android)
- **Web UI**: Lit Web Components
- **插件系统**: 基于 npm 包的插件 SDK

核心数据流：通道 → Gateway → 路由 → Agent 运行时 → LLM/工具/记忆；Gateway 同时服务原生 App 与 Web UI；配置与插件注入 Gateway。

---

## 二、目标架构 (Python + Flet)

- **后端**: FastAPI + websockets；路由与协议层 Pydantic 模型。
- **Agent 运行时**: 自研 Python 运行时（流式 LLM + 工具循环），使用官方 SDK（openai、anthropic、google-generativeai 等）。
- **通道**: Python SDK（aiogram、discord.py、slack-bolt、neonize 等）对接 Gateway。
- **UI**: Flet 单代码库 → 桌面 / 移动 / Web；系统托盘等由 pystray 等补充。
- **配置与存储**: 继续使用 JSON5、JSONL、SQLite（aiosqlite + sqlite-vec），与现有数据兼容。
- **插件**: Python `entry_points` 发现与加载，语义与 TS 版对齐。

数据流形态不变：通道 → Gateway → 路由 → Agent 运行时 → LLM/工具/记忆；Flet 多端仅作为 Gateway 的客户端。

---

## 三、可复用资产清单

以下与语言无关，可直接在 Python 重写中复用：

| 类别 | 内容摘要 | 复用方式 |
|------|----------|----------|
| 配置与存储 | openclaw.json (JSON5)、会话 JSONL、sessions.json、credentials、memory SQLite、hooks.json5 | 直接读写或 Pydantic 映射 |
| 协议 | WebSocket v3、协议 schema（可生成 Pydantic） | 协议层兼容，过渡期原生 App 可连 Python Gateway |
| 工具与元数据 | tool-display.json、host-env-security-policy.json、A2UI schema、设备标识符映射 | 直接加载 |
| 文档 | Mintlify 文档、docs 配置、i18n 术语表、Agent 模板 | 完全复用 |
| Skills | skills/**/SKILL.md、references、Shell 脚本 | 与语言无关 |
| 插件清单 | extensions/*/openclaw.plugin.json | JSON 直接读 |
| 测试契约与数据 | 审批/命令/Shell/Exec 等 fixture | 测试用例复用 |
| 静态资产 | Logo、favicon、avatar、Chrome 扩展清单等 | 直接使用 |
| 外部调用 | signal-cli、imsg、Playwright、Tailscale、ffmpeg | subprocess 或官方 Python SDK，调用方式一致 |

**复用程度概览**：直接复用（数据/文档/静态资产）约 40%；格式兼容（配置/会话/协议）约 25%；逻辑参考（TS 源码作设计参考）约 25%；需完全重新设计（Agent 运行时、Flet UI、插件加载）约 10%。

---

## 四、技术选型映射

### 4.1 后端核心

| 模块 | 当前 (TypeScript) | 目标 (Python) |
|------|-------------------|---------------|
| HTTP 服务 | Express | FastAPI |
| WebSocket | `ws` | websockets / FastAPI WS |
| CLI | Commander | Typer |
| 配置验证 | Zod | Pydantic v2 |
| 配置文件 | JSON5 | json5 (PyPI) |
| 日志 | tslog | loguru |
| 任务调度 | croner | APScheduler |
| 文件监控 | chokidar | watchdog |
| 异步运行时 | Node event loop | asyncio + uvloop |

### 4.2 AI/Agent 运行时

| 模块 | 当前 | 目标 |
|------|------|------|
| Agent 核心循环 | pi-agent-core | 自研 Python Agent Runtime（流式 LLM + 工具循环） |
| LLM 客户端 | pi-ai (streamSimple) | httpx + 官方 SDK（openai, anthropic, google-generativeai） |
| 工具框架 | pi-coding-agent tools | 自研工具框架（Pydantic schema） |
| 会话管理 | SessionManager (JSONL) | 自研 SessionManager，兼容现有 JSONL |
| 向量搜索 | sqlite-vec (Node) | sqlite-vec (Python bindings) |
| 浏览器 | playwright-core | playwright (Python) |
| TTS | node-edge-tts | edge-tts (Python) |

### 4.3 消息通道

Telegram → aiogram 3 / python-telegram-bot；Discord → discord.py / nextcord；Slack → slack-bolt (Python)；WhatsApp → neonize (whatsmeow Python 绑定)；Signal / iMessage → 继续 subprocess；Matrix → matrix-nio；其余（Google Chat、LINE、Feishu 等）采用对应官方或成熟 Python SDK。

### 4.4 UI (Flet)

桌面：Flet desktop + pystray 系统托盘；移动：Flet mobile (iOS/Android)；Web：Flet web。Voice Wake / PTT 需平台原生能力，桌面可用 sounddevice + vosk/whisper，移动端需 Flutter 插件或降级为按钮触发。

---

## 五、项目结构设计

顶层：`src/openclaw/`（CLI、gateway、agents、channels、routing、config、memory、media、infra、plugins、cron）、`ui/`（Flet 应用、pages、components、theme）、`extensions/`（各渠道插件）、`tests/`。Gateway 内含 protocol（Pydantic 模型）、methods（WS 方法处理器）；agents 内含 runner、stream、session、compaction、models、tools、auth；channels 按渠道分子目录；config 含 schema、io、paths、sessions。具体目录树以代码库为准，此处仅表达分层与职责划分。

---

## 六、关键风险与对策

| 风险点 | 对策摘要 |
|--------|----------|
| **WhatsApp** | 使用 neonize（whatsmeow Python 绑定）；成熟度低于 Baileys，需充分测试；备选为自研 Python 绑定 |
| **Agent 运行时** | Python 完全重写；用官方 LLM SDK 省去手写 SSE；核心循环 + 工具执行 + SessionManager 分阶段（3a–3f）；不用 LangChain，保持会话格式与依赖可控 |
| **macOS 菜单栏/托盘** | pystray 提供托盘与菜单；Flet 主窗口；或轻量 Swift wrapper + subprocess 启动 Flet |
| **Voice Wake / PTT** | 桌面 sounddevice + vosk/whisper；移动端需 Flutter 插件或暂不支持 |
| **性能** | 全面 async + uvloop；aiosqlite、httpx、websockets；瓶颈在 LLM 延迟而非本地 I/O |

Agent 实施子阶段：3a 基础循环 + OpenAI/Anthropic 流式 → 3b 工具框架 + 核心工具 → 3c SessionManager（JSONL 兼容）→ 3d 更多 LLM 提供商 → 3e Compaction → 3f 会话 DAG 与扩展。3a+3b+3c 完成后即有可用运行时。

---

## 七、分阶段实施路线

建议顺序：**Phase 1（基础）** → **Phase 3a–3c（Agent MVP）** → **Phase 2（Gateway）** → **Phase 4（通道，Telegram 优先）** → **Phase 5（Flet UI）** → **Phase 3d–3f（Agent 完善）** → **Phase 6（记忆/RAG、插件、Cron、浏览器等）**。  
各阶段内再拆为具体工作包与里程碑（如 Gateway：FastAPI 骨架 → WebSocket 协议 → 方法处理器；通道：Telegram → Discord → Slack → WhatsApp 等）。时间线以甘特或迭代计划形式在项目内维护，此处不展开具体日期。

---

## 八、关键设计决策总结

1. **协议兼容**：WebSocket v3 完全兼容，过渡期原生 App 可连 Python Gateway。  
2. **配置与数据兼容**：直接读写 `~/.openclaw/` 下 JSON5、JSONL、SQLite，无需迁移。  
3. **WhatsApp**：neonize 实现纯 Python 通道。  
4. **Agent 运行时**：自研，官方 LLM SDK，不用 LangChain；分 6 子阶段，3a–3c 即可用。  
5. **插件**：Python entry_points，与 TS 版语义对齐。  
6. **Flet UI**：单代码库多端；托盘等用 pystray 补充。  
7. **渐进迁移**：可先换 Gateway，再通道与 Agent，最后 UI。

---

## 九、实施优先级（摘要）

1. Phase 1：脚手架、Pydantic 配置、配置/会话兼容层。  
2. Phase 3a–3c：Agent 循环、工具框架、SessionManager。  
3. Phase 2：FastAPI、WebSocket 协议、方法处理器。  
4. Phase 4：通道（Telegram → Discord → Slack → 其他）。  
5. Phase 5：Flet 桌面聊天 → 设置/状态 → 托盘 → 移动 → Web。  
6. Phase 3d–3f：多 LLM、Compaction、DAG/扩展。  
7. Phase 6：记忆/RAG、插件系统、Cron、浏览器自动化。
