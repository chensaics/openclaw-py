# 架构设计文档

本文档面向开发者，介绍 OpenClaw-Py 的整体架构、核心组件和设计决策。

---

## 1. 总览

OpenClaw-Py 是一个多通道 AI 网关，将 AI Agent 连接到 25+ 消息平台。核心设计目标：

- **通道无关**：Agent 逻辑与通道解耦，新通道只需实现 `ChannelPlugin` 接口
- **Provider 无关**：统一的流式接口屏蔽 LLM 差异
- **可扩展**：通过 Python entry_points 和 SKILL.md 注入能力
- **跨平台**：Flet UI 在桌面、移动端、Web 复用同一套代码

```
┌─────────────┐   ┌──────────────┐   ┌─────────────┐
│ Flet UI     │   │  CLI (Typer) │   │ ACP Bridge  │
└──────┬──────┘   └──────┬───────┘   └──────┬──────┘
       │                 │                   │
       └─────────┬───────┘───────────────────┘
                 │ WebSocket v3 / HTTP
       ┌─────────▼─────────┐
       │  Gateway (FastAPI) │
       │  ┌───────────────┐ │
       │  │ RPC Handlers  │ │
       │  │ OpenAI Compat │ │
       │  └───────┬───────┘ │
       └──────────┼─────────┘
                  │
       ┌──────────▼─────────┐
       │   Agent Runtime    │
       │  ┌──────────────┐  │
       │  │ Runner Loop  │  │  prompt → LLM stream → tool exec → loop
       │  │ Session DAG  │  │
       │  │ Sub-agents   │  │
       │  └──────────────┘  │
       └──────────┬─────────┘
           ┌──────┼──────┐
           ▼      ▼      ▼
       ┌──────┐ ┌────┐ ┌──────┐
       │Tools │ │MCP │ │Skills│
       └──────┘ └────┘ └──────┘
```

---

## 2. 核心组件

### 2.1 Gateway Server

`src/pyclaw/gateway/server.py`

- FastAPI 应用，暴露 WebSocket (`/ws`) 和 HTTP 端点
- WebSocket 采用 JSON 帧协议 v3，支持请求/响应/事件三种帧类型
- 方法分发：按 `method` 字段路由到 `methods/` 下的处理函数
- 支持多客户端并发连接
- 启动时加载插件 (`_load_plugins`) 和配置监控 (`_start_config_watcher`)

```python
class GatewayServer:
    def register_handler(self, method: str, handler: MethodHandler) -> None: ...
    async def _dispatch(self, method: str, params: dict, conn: GatewayConnection) -> Any: ...
```

### 2.2 Agent Runtime

`src/pyclaw/agents/runner.py`

核心执行循环：

```
while not done:
    response = await llm.stream(messages, tools)
    for chunk in response:
        if chunk.is_tool_call:
            result = await tool_registry.execute(chunk.tool, chunk.args)
            messages.append(tool_result(result))
        elif chunk.is_text:
            yield chunk.text
    if no_tool_calls:
        done = True
```

设计特点：

- **多 Provider 统一流式**：`stream.py` 将 OpenAI / Anthropic / Gemini / Ollama 的流式 API 归一化为相同的 chunk 格式
- **工具执行沙箱**：通过 `tool_guards.py` 控制危险操作审批
- **会话持久化**：JSONL DAG 格式，支持分支和压缩
- **子 Agent**：`subagents/` 管理 spawn / steer / kill 生命周期

### 2.3 Channels

`src/pyclaw/channels/`

每个通道是一个独立目录，包含 `channel.py` 实现 `ChannelPlugin` 基类：

```python
class ChannelPlugin(ABC):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send_reply(self, reply: ChannelReply) -> None: ...
    def on_message(self, callback) -> None: ...
```

通道管理器 (`manager.py`) 统一管理所有通道的生命周期。

Plugin SDK (`plugin_sdk/`) 定义了 20 个 Protocol 接口：

| Protocol | 用途 |
|----------|------|
| `ConfigAdapter` | 配置 schema + 验证 |
| `AuthAdapter` | 认证 |
| `OutboundAdapter` | 消息发送 |
| `ActionsAdapter` | 反应、置顶 |
| `StreamingAdapter` | 草稿/流式消息 |
| `HeartbeatAdapter` | 连接心跳 |
| `DirectoryAdapter` | 用户目录 |
| ... | 共 20 个 |

运行时通过 `detect_capabilities(plugin)` 探测通道支持哪些能力。

### 2.4 配置系统

`src/pyclaw/config/`

- **Pydantic v2 schema** (`schema.py`)：强类型配置模型，30+ 配置节
- **JSON5 格式**：支持注释和尾逗号
- **环境变量替换** (`env_substitution.py`)：`${VAR}` / `${VAR:-default}` 语法
- **$include 分拆** (`includes.py`)：大配置文件可拆分为多个 JSON5
- **版本迁移** (`migrations.py`)：v1 → v2 → v3 自动迁移
- **热重载** (`runtime_overrides.py`)：后台轮询检测文件变更，触发回调
- **原子写入** (`backup.py`)：先写临时文件再原子重命名，保留备份

### 2.5 MCP 客户端

`src/pyclaw/mcp/`

实现 MCP (Model Context Protocol) 客户端，连接外部工具服务器：

- **stdio transport**：启动子进程，通过 stdin/stdout 通信
- **HTTP transport**：通过 HTTP 连接远程 MCP 服务器
- **工具注册表**：将发现的工具映射为 Agent 可用的 tool schema
- 配置格式兼容 Claude Desktop 和 Cursor

### 2.6 Memory

`src/pyclaw/memory/`

双引擎记忆系统：

```
┌─────────────┐   ┌─────────────┐
│ SQLite FTS5 │   │  LanceDB    │
│ (关键词搜索) │   │ (向量搜索)  │
└──────┬──────┘   └──────┬──────┘
       └────────┬────────┘
          ┌─────▼─────┐
          │  Hybrid   │  MMR + 时间衰减
          │  Ranker   │
          └───────────┘
```

- **SQLite + FTS5**：全文检索，低延迟
- **LanceDB**：向量搜索，语义匹配
- **混合排序**：关键词和向量结果融合
- **MMR**：最大边际相关性，减少冗余
- **时间衰减**：近期记忆权重更高

### 2.7 UI (Flet)

`src/pyclaw/ui/`

基于 Flet 的跨平台 UI：

| 模块 | 功能 |
|------|------|
| `app.py` | 主应用 + ChatView + NavigationRail |
| `theme.py` | Light/Dark 主题 |
| `agents_panel.py` | Agent 管理面板 |
| `toolbar.py` | 聊天工具栏 |
| `menubar.py` | 桌面菜单栏 |
| `voice.py` | 语音交互 (TTS + STT) |
| `onboarding.py` | 4 步设置向导 |
| `tray.py` | 系统托盘 |
| `i18n.py` | 多语言 (en/zh-CN/ja) |
| `permissions.py` | 移动端权限管理 |

---

## 3. 数据流

### 3.1 用户消息 → Agent 回复

```
User (Flet/CLI/Channel)
  │
  ▼
Gateway.chat.send(sessionId, message)
  │
  ▼
AgentRunner.run(session, message)
  │
  ├─ append user message to session
  │
  ├─ build system prompt (AGENTS.md + skills + context)
  │
  ├─ LLM.stream(messages, tools)
  │     │
  │     ├─ text delta → push chat.delta event
  │     │
  │     └─ tool_call → ToolRegistry.execute()
  │           │
  │           ├─ built-in tool
  │           ├─ MCP tool (stdio/HTTP)
  │           └─ approval gate (if exec/patch)
  │
  ├─ append assistant message to session
  │
  └─ push chat.done event
```

### 3.2 通道消息路由

```
Channel (Telegram/Discord/...)
  │
  ▼
ChannelPlugin.on_message(callback)
  │
  ▼
ChannelManager → Routing (7-tier priority)
  │
  ▼
AgentRunner.run(...)  ← 选定的 Agent
  │
  ▼
Channel.send_reply(response)
```

路由优先级：

1. 会话绑定 (session → agent)
2. 线程绑定 (thread → agent)
3. 通道绑定 (channel → agent)
4. 群组绑定 (chat_id → agent)
5. 用户绑定 (sender → agent)
6. 全局绑定 (pattern match)
7. 默认 Agent

---

## 4. 安全模型

### 4.1 命令执行审批

```
Agent 请求执行命令
  │
  ▼
ToolGuards.check_policy(command)
  │
  ├─ allow_list → 直接执行
  ├─ deny_list → 拒绝
  └─ approval_required → 推送审批请求到 UI/CLI
        │
        ▼
      用户审批/拒绝
```

### 4.2 工作区沙箱

- 工具操作限制在配置的工作区目录内
- 文件路径规范化防止目录遍历
- 环境变量过滤敏感信息

### 4.3 网络安全

- **SSRF 防护**：阻止对内网 IP / DNS 重绑定的请求
- **Secret 扫描**：检测配置中的明文密钥并警告
- **Gateway 绑定**：默认绑定 `127.0.0.1`，防止未授权访问
- **TLS 指纹**：验证远程连接的证书

---

## 5. 扩展机制

### 5.1 Plugin (entry_points)

通过 Python `entry_points` 机制自动发现第三方插件：

```toml
# 第三方包的 pyproject.toml
[project.entry-points."pyclaw.plugins"]
my_plugin = "my_package.plugin:MyPlugin"
```

Gateway 启动时自动加载所有已安装的插件。

### 5.2 SKILL.md

Agent 能力注入：

```
~/.pyclaw/workspace/skills/
├── my-skill/
│   └── SKILL.md    # 包含系统提示和工具定义
└── ...
```

技能在 Agent 系统提示中被注入，可通过 ClawHub marketplace 安装。

### 5.3 Hook 系统

事件钩子 (HOOK.md)：

```markdown
# HOOK.md
## on_message_received
Run sentiment analysis before processing.
```

支持 `before_send` / `after_send` / `on_error` 等生命周期钩子。

---

## 6. 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Web 框架 | FastAPI | 原生 async，WebSocket 支持好 |
| CLI 框架 | Typer + Rich | 类型安全 + 丰富输出 |
| 配置格式 | JSON5 | 支持注释，兼容 JSON |
| 会话存储 | JSONL (文件) | 无需数据库，便于调试 |
| 向量引擎 | LanceDB | 零配置，嵌入式 |
| UI 框架 | Flet | 单一 Python 代码库跨平台 |
| LLM 流式 | 统一 chunk 格式 | 屏蔽 Provider 差异 |
| 进程管理 | asyncio subprocess | 与 async 架构一致 |
| 日志 | stdlib logging | 无额外依赖 |
| 类型系统 | Pydantic v2 | 验证 + 序列化 |

---

## 7. 目录结构

```
src/pyclaw/
├── __init__.py
├── main.py               # 入口
│
├── agents/               # Agent 运行时
│   ├── runner.py          # 核心循环
│   ├── stream.py          # 多 Provider 流式
│   ├── session.py         # 会话存储
│   ├── system_prompt.py   # 系统提示构建
│   ├── tokens.py          # Token 计数
│   ├── embedded_runner/   # 嵌入式运行器
│   ├── providers/         # LLM Provider 适配
│   ├── subagents/         # 子 Agent 管理
│   ├── skills/            # SKILL.md 系统
│   ├── tools/             # 20+ 内置工具
│   ├── progress.py        # 进度事件
│   └── types.py           # 共享类型
│
├── gateway/              # Gateway 服务
│   ├── server.py          # FastAPI + WebSocket
│   ├── openai_compat.py   # OpenAI API 兼容层
│   ├── protocol/          # 帧定义
│   ├── methods/           # RPC 方法处理器
│   └── events.py          # 事件广播
│
├── channels/             # 25 个消息通道
│   ├── base.py            # ChannelPlugin 基类
│   ├── manager.py         # 通道管理器
│   ├── plugin_sdk/        # 20 个 Protocol 接口
│   ├── plugins/           # 通道增强 (onboarding/outbound/actions/normalize)
│   └── <channel>/         # 各通道实现
│
├── config/               # 配置管理
├── mcp/                  # MCP 客户端
├── memory/               # 记忆系统
├── security/             # 安全策略
├── secrets/              # 密钥管理
├── hooks/                # 事件钩子
├── plugins/              # 扩展系统
├── routing/              # 消息路由
├── media/                # 媒体处理
├── social/               # Agent 社交网络
├── infra/                # 基础设施
├── cli/                  # CLI 命令
├── ui/                   # Flet UI
└── web/                  # Web API
```
