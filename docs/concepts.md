# 概念总览

本文档简要介绍 pyclaw 的核心概念，帮助你理解系统的工作方式。完整的技术细节请参阅 [架构设计文档](architecture.md)。

---

## Gateway

Gateway 是 pyclaw 的核心服务进程，负责接收来自各通道和客户端的消息，路由到 Agent 处理，并将回复发送回去。

```
Chat Apps ──┐
CLI ────────┼── Gateway ── Agent Runtime
UI ─────────┤
API ────────┘
```

Gateway 基于 **FastAPI** 构建，暴露两套 API：

- **WebSocket RPC**（`ws://localhost:18789/ws`）：双向实时通信，支持 25+ 方法（chat、sessions、config 等）
- **OpenAI 兼容 HTTP**（`/v1/chat/completions`、`/v1/models`）：可替代 OpenAI SDK 使用

启动 Gateway：`pyclaw gateway`，默认监听 `127.0.0.1:18789`。

详见: [API 参考](api-reference.md) · [配置说明](configuration.md)

## Agent 运行时

Agent 运行时是消息处理的核心循环。收到用户消息后，Agent 执行以下流程：

1. 将用户消息追加到会话
2. 构建系统提示（AGENTS.md + Skills + 上下文）
3. 调用 LLM 流式生成回复
4. 如果 LLM 发出工具调用，执行工具并将结果返回给 LLM
5. 循环直到 LLM 完成回复（无更多工具调用）
6. 将回复追加到会话并推送给客户端

### 多 Provider 支持

pyclaw 统一了不同 LLM 的流式接口，支持 OpenAI、Anthropic、Google Gemini、Ollama 以及 20+ OpenAI 兼容提供商。切换 Provider 只需修改配置，Agent 逻辑无需变动。

### 思维模式

通过 `thinking` 配置控制 LLM 的推理深度：

- `disabled` — 直接生成
- `low` — 简短推理
- `high` — 深度推理（token 消耗更大）

详见: [架构设计 — Agent Runtime](architecture.md#22-agent-runtime)

## 会话

会话（Session）是 Agent 与用户交互的完整对话历史，以 JSONL DAG 格式存储在 `~/.pyclaw/sessions/` 下。

### 会话范围

| 模式 | 说明 |
|------|------|
| `global` | 所有来源共享一个会话 |
| `per-sender` | 每个发送者独立会话 |
| `per-channel-peer` | 按「通道 + 发送者」隔离 |

### 会话重置

会话支持定时重置和空闲重置：

- **定时重置**：每天指定时间（如凌晨 4 点）创建新会话
- **空闲重置**：空闲超过指定时间后自动新建

### 会话压缩

当会话过长时，系统自动进行压缩（compaction），移除早期消息并注入摘要，保持上下文窗口在合理范围内。

## 多 Agent 路由

pyclaw 支持同时运行多个 Agent，通过 **7 级优先级路由** 决定由哪个 Agent 处理消息：

1. 会话绑定（session → agent）
2. 线程绑定（thread → agent）
3. 通道绑定（channel → agent）
4. 群组绑定（chat_id → agent）
5. 用户绑定（sender → agent）
6. 全局绑定（pattern match）
7. 默认 Agent

通过 `bindings` 配置实现路由：

```json5
{
  bindings: [
    { agent: "work", match: { channel: "telegram" } },
    { agent: "home", match: { channel: "discord" } },
  ],
}
```

## 工具

Agent 在对话过程中可以调用 **20+ 内置工具** 完成任务：

| 工具类别 | 示例 |
|----------|------|
| 文件操作 | read_file、write_file、list_dir |
| 搜索 | grep、find、web_search |
| 执行 | exec (shell 命令) |
| 浏览器 | navigate、click、screenshot |
| 记忆 | memory_search、memory_store |
| 网络 | web_fetch |
| 系统 | cron (定时任务) |

### 命令执行审批

危险操作（如 shell 命令）需要通过审批：

- `allowlist` — 匹配的命令直接执行
- `denylist` — 匹配的命令直接拒绝
- 其他命令 — 推送审批请求到 UI/CLI，等待用户确认

### 工作区沙箱

工具操作默认限制在配置的工作区目录内（`tools.restrictToWorkspace`），文件路径会经过规范化以防止目录遍历。

## MCP (Model Context Protocol)

pyclaw 支持通过 MCP 协议连接外部工具服务器，扩展 Agent 的能力。支持两种传输方式：

- **stdio** — 启动本地子进程通信
- **HTTP** — 连接远程 MCP 端点

MCP 服务器中的工具在 Gateway 启动时自动发现，并注册到 Agent 工具池。配置格式与 Claude Desktop / Cursor 兼容。

MCP 配置支持热重载 — 修改 `tools.mcpServers` 后自动断开旧连接并重新连接。

检查状态：`pyclaw mcp status`

## 记忆

pyclaw 实现了双引擎混合记忆系统：

- **SQLite FTS5** — 全文检索，基于关键词匹配
- **LanceDB** — 向量搜索，基于语义匹配

两个引擎的结果通过混合排序（MMR + 时间衰减）融合，近期记忆权重更高。

Agent 可通过 `memory_search` 和 `memory_store` 工具主动使用记忆。

## 消息通道

通道是连接外部消息平台的插件。每个通道实现统一的 `ChannelPlugin` 接口：

- `start()` / `stop()` — 生命周期管理
- `send_reply()` — 发送回复
- `on_message()` — 注册消息回调

pyclaw 内置 **25 个通道**，涵盖 Telegram、Discord、Slack、WhatsApp、DingTalk、QQ、Feishu、Matrix、IRC 等主流平台。

### DM 与群组策略

每个通道可独立配置 DM 策略（`dmPolicy`）和群组策略（`groupPolicy`）：

- `pairing` — 未知发送者需通过配对码验证
- `allowlist` — 仅允许列表中的用户
- `open` — 允许所有人
- `disabled` — 禁用

群组消息默认要求 @mention 才会触发 Agent。

## 子 Agent

Agent 可以在执行过程中 spawn 子 Agent，将子任务委派给专门的 Agent 实例。子 Agent 拥有独立的会话和工具访问，完成后将结果返回给父 Agent。

子 Agent 的生命周期包括：spawn（创建）、steer（重定向）、kill（终止）。

## 技能 (Skills)

通过 SKILL.md 文件注入 Agent 能力。技能被加入系统提示，使 Agent 获得特定领域的知识和工具：

```
~/.pyclaw/workspace/skills/
├── my-skill/
│   └── SKILL.md
└── ...
```

技能可通过 ClawHub marketplace 搜索和安装：

```bash
pyclaw skills search "code review"
pyclaw skills install code-review
```

## 安全模型

pyclaw 在多个层面提供安全保障：

| 层面 | 机制 |
|------|------|
| 命令执行 | allowlist / denylist + 用户审批 |
| 文件访问 | 工作区目录沙箱 |
| 网络 | SSRF 防护（内网 IP / DNS 重绑定拦截） |
| 配置 | 明文密钥扫描与警告 |
| Gateway | 默认绑定 `127.0.0.1`，支持 Token 认证 |

安全审计：`pyclaw security audit [--deep] [--fix]`

---

*相关文档: [架构设计](architecture.md) · [配置说明](configuration.md) · [API 参考](api-reference.md)*
